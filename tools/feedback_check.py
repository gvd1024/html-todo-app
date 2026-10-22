"""Feedback review: find new or changed items in Geoff's Feedback list (see CLAUDE.md, "Feedback review").

An item is one top-level line of a task body together with its indented sub-lines, or a task's title.
Discussed items are recorded in private/feedback-ledger.json (local, git-ignored); the task files are only read.

    python tools/feedback_check.py               # list new / changed items, each with a key
    python tools/feedback_check.py ack KEY ...   # record items as discussed (their current text)
    python tools/feedback_check.py ack-all       # record every current item (baseline)

Options: --folder PATH (default: the OneDrive task folder), --list NAME (default: Feedback).
"""
import difflib, hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "private" / "feedback-ledger.json"
FOLDER = Path(r"C:\Users\gvd10\OneDrive\HTML-ToDo-App")


def frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    fm = {}
    for line in text[3:end].splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip("'\"")
    return fm, text[end + 4:].split("\n", 1)[1] if "\n" in text[end + 4:] else ""


def items_of(body):
    out, cur = [], None
    for raw in body.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            continue
        if line[0] in " \t" and cur is not None:
            cur.append(line)
        else:
            cur = [line]
            out.append(cur)
    return ["\n".join(i) for i in out]


def key(tid, text):
    return hashlib.sha1((tid + "\0" + text).encode("utf-8")).hexdigest()[:8]


def collect(folder, listname):
    found = []
    for f in sorted(folder.glob("*.md")):
        if f.name.startswith(("_", ".")) or f.name.lower() == "readme.md":
            continue
        fm, body = frontmatter(f.read_text(encoding="utf-8"))
        if fm.get("list") != listname or fm.get("status") in ("archived",):
            continue
        tid = fm.get("id", f.name)
        entries = [("title", "title: " + fm.get("title", ""))] + [("line", t) for t in items_of(body)]
        for kind, text in entries:
            found.append({"key": key(tid, text), "id": tid, "file": f.name, "title": fm.get("title", ""),
                          "status": fm.get("status", ""), "kind": kind, "text": text})
    return found


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    folder, listname = FOLDER, "Feedback"
    if "--folder" in args:
        i = args.index("--folder"); folder = Path(args[i + 1]); del args[i:i + 2]
    if "--list" in args:
        i = args.index("--list"); listname = args[i + 1]; del args[i:i + 2]
    ledger = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {"items": {}}
    seen = ledger["items"]                                   # task id -> [discussed texts]
    items = collect(folder, listname)
    cmd = args[0] if args else "check"

    if cmd in ("ack", "ack-all"):
        want = set(args[1:])
        done = []
        for it in items:
            if cmd == "ack-all" or it["key"] in want:
                texts = seen.setdefault(it["id"], [])
                if it["text"] not in texts:
                    texts.append(it["text"])
                done.append(it["key"])
        LEDGER.parent.mkdir(exist_ok=True)
        LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        missing = want - set(done)
        print(f"recorded {len(done)} item(s) as discussed" + (f"; not found: {', '.join(sorted(missing))}" if missing else ""))
        return

    new = [it for it in items if it["text"] not in seen.get(it["id"], [])]
    print(f"Feedback list: {len(items)} item(s) in {len({i['id'] for i in items})} task(s); {len(new)} new or changed.")
    for n, it in enumerate(new, 1):
        old = seen.get(it["id"], [])
        first = it["text"].split("\n", 1)[0]
        match = difflib.get_close_matches(first, [o.split("\n", 1)[0] for o in old], n=1, cutoff=0.6)
        label = "CHANGED" if match else ("NEW TASK" if it["kind"] == "title" else "NEW")
        print(f"\n[{n}] {label}  key={it['key']}  {it['file']} — “{it['title']}” ({it['status']})")
        print("    " + it["text"].replace("\n", "\n    "))
        if match:
            prev = next(o for o in old if o.split("\n", 1)[0] == match[0])
            print("    was:\n      " + prev.replace("\n", "\n      "))


if __name__ == "__main__":
    main()
