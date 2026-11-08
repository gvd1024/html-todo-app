"""R2-5: convert a task folder from the flat list layout (data format 2/3) to the folder layout (data format 4).

    python tools/migrate_to_folders.py PATH            # preview only: prints the plan, changes nothing
    python tools/migrate_to_folders.py PATH --apply    # back up, then convert

What it does (see docs/specs/round-2-spec.md, R2-5 "Implementation discussion"):
- Every task file in the top of PATH moves into the folder named by its `list:` line; `list: Inbox` (or no list:)
  stays at the top, which the app shows as "/ (root)". A subtask follows its parent's list (a family shares a folder).
- The `list:` line is removed from the frontmatter. Nothing else in the file changes: key order, unknown keys, the
  body and the file's line endings are kept byte for byte.
- Files are MOVED (os.replace), then the list: line is removed in place, so OneDrive sees a move and keeps each file's
  history. Each file is re-read right before it's moved; if it changed since the plan was made, the run stops (S-12).
- _todo.json gets {"format": 4, "folders": [...]} (the old "lists" order, Inbox left out) and keeps any other keys.
  It is written LAST, so an interrupted run can simply be run again.
- Before anything changes, the whole folder is zipped into private/backups/ (git-ignored).
"""
import datetime
import json
import os
import re
import sys
import zipfile
from pathlib import Path

LIST_LINE = re.compile(rb"^list:[ \t]*(.*?)[ \t]*\r?\n", re.M)
BAD_NAME = re.compile(r'[/\\:*?"<>|]')
RESERVED = re.compile(r"^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?$", re.I)
REPO = Path(__file__).resolve().parent.parent


def is_task(name):
    return name.lower().endswith(".md") and not name.startswith(("_", ".")) and name.lower() != "readme.md"


def front(raw):
    """(frontmatter bytes, start, end) of a file's leading --- block, or None."""
    m = re.match(rb"---\r?\n(.*?\r?\n)---[ \t]*(\r?\n|$)", raw, re.S)
    return (m.group(1), m.start(1), m.end(1)) if m else None


def field(fm, key):
    m = re.search(rb"^" + key.encode() + rb":[ \t]*(.*?)[ \t]*\r?$", fm, re.M)
    if not m:
        return ""
    v = m.group(1).decode("utf-8", "replace").strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        v = v[1:-1]
    return v


def folder_error(name):
    if BAD_NAME.search(name):
        return 'contains one of / \\ : * ? " < > |'
    if name.startswith((".", "_")):
        return "starts with . or _"
    if name.endswith((" ", ".")):
        return "ends with a space or a dot"
    if RESERVED.match(name):
        return "is a Windows reserved name"
    return ""


def plan(root):
    cfg_path = root / "_todo.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    fmt = cfg.get("format") or 0
    if fmt >= 4 or "folders" in cfg:
        raise SystemExit(f"{root} already uses the folder layout (format {fmt}). Nothing to do.")
    tasks = {}
    for name in sorted(os.listdir(root)):
        p = root / name
        if not p.is_file() or not is_task(name):
            continue
        raw = p.read_bytes()
        fb = front(raw)
        fm = fb[0] if fb else b""
        tasks[name] = {"raw": raw, "id": field(fm, "id"), "parent": field(fm, "parent"), "list": field(fm, "list") or "Inbox",
                       "title": field(fm, "title"), "has_list": bool(fb and LIST_LINE.search(fm))}
    by_id = {t["id"]: n for n, t in tasks.items() if t["id"]}
    notes = []
    for n, t in tasks.items():                         # a family shares the top ancestor's list
        seen, cur = set(), t
        while cur["parent"] and cur["parent"] in by_id and cur["parent"] not in seen:
            seen.add(cur["parent"]); cur = tasks[by_id[cur["parent"]]]
        if cur["list"] != t["list"]:
            notes.append(f"  {n}: list '{t['list']}' → follows its parent's list '{cur['list']}'")
        t["dir"] = "" if cur["list"] in ("", "Inbox") else cur["list"]
    dirs = sorted({t["dir"] for t in tasks.values() if t["dir"]})
    errs = [f"  folder '{d}': {folder_error(d)}" for d in dirs if folder_error(d)]
    lower = {}
    for d in dirs:
        if d.lower() in lower and lower[d.lower()] != d:
            errs.append(f"  folders '{d}' and '{lower[d.lower()]}' differ only in capitals")
        lower[d.lower()] = d
    for n, t in tasks.items():
        if t["dir"]:
            dest = root / t["dir"] / n
            if dest.exists():
                errs.append(f"  {t['dir']}/{n} already exists")
    order = [l for l in cfg.get("lists", []) if l not in ("", "Inbox")]
    folders = [l for l in order if l in dirs or not folder_error(l)] + [d for d in dirs if d not in order]
    return cfg, tasks, folders, notes, errs


def backup(root):
    out = REPO / "private" / "backups"
    out.mkdir(parents=True, exist_ok=True)
    z = out / f"{root.name}-{datetime.datetime.now():%Y-%m-%d-%H%M%S}-before-folders.zip"
    n = 0
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for dp, _, fns in os.walk(root):
            for f in fns:
                full = Path(dp) / f
                zf.write(full, full.relative_to(root)); n += 1
    with zipfile.ZipFile(z) as zf:
        bad = zf.testzip()
    if bad:
        raise SystemExit(f"backup check failed at {bad}")
    return z, n


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    if len(args) != 1:
        raise SystemExit(__doc__)
    root = Path(args[0])
    cfg, tasks, folders, notes, errs = plan(root)
    moves = [(n, t) for n, t in tasks.items() if t["dir"]]
    stay = [(n, t) for n, t in tasks.items() if not t["dir"]]
    print(f"{root}: {len(tasks)} task files, data format {cfg.get('format') or '?'}")
    for d in folders:
        k = [n for n, t in moves if t["dir"] == d]
        print(f"  {d}/  ← {len(k)} file(s)")
    print(f"  / (root)  ← {len(stay)} file(s) stay at the top")
    print(f"  list: lines to remove: {sum(1 for t in tasks.values() if t['has_list'])}")
    print(f'  _todo.json → {{"format": 4, "folders": {json.dumps(folders)}}} (+ {len([k for k in cfg if k not in ("format", "lists")])} other key(s) kept)')
    if notes:
        print("Families kept together:"); print("\n".join(notes))
    if errs:
        print("STOPPED — fix these first:"); print("\n".join(errs)); raise SystemExit(1)
    if not apply:
        print("\nPreview only. Run again with --apply to convert."); return

    z, n = backup(root)
    print(f"\nBackup: {z} ({n} files, verified)")
    done = 0
    for name, t in tasks.items():
        src = root / name
        if src.read_bytes() != t["raw"]:                # S-12: changed since the plan was made → stop
            raise SystemExit(f"STOPPED: {name} changed while converting ({done} done). Run again to continue.")
        dst = root / t["dir"] / name if t["dir"] else src
        if t["dir"]:
            (root / t["dir"]).mkdir(exist_ok=True)
            os.replace(src, dst)                      # a move: OneDrive keeps the file's identity and history
        if t["has_list"]:
            raw = t["raw"]; fb = front(raw)
            fm = LIST_LINE.sub(b"", fb[0], count=1)
            new = raw[:fb[1]] + fm + raw[fb[2]:]
            dst.write_bytes(new)
            if dst.read_bytes() != new:
                raise SystemExit(f"STOPPED: {dst} didn't read back as written.")
        done += 1
    for d in folders:
        (root / d).mkdir(exist_ok=True)
    cfg.pop("lists", None)
    out = {**cfg, "format": 4, "folders": folders}
    cfgp = root / "_todo.json"
    raw = cfgp.read_bytes() if cfgp.exists() else b""
    nl = "\r\n" if b"\r\n" in raw else "\n"
    cfgp.write_text(json.dumps(out, indent=2).replace("\n", nl) + nl, encoding="utf-8", newline="")
    print(f"Converted: {done} task files; {len(moves)} moved into {len(folders)} folder(s); _todo.json is format 4.")


if __name__ == "__main__":
    main()
