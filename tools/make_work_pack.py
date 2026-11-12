"""Build the work-PC pack: dist/html-todo-app-<BUILD>.zip, one top folder App/ (extract into C:\\HTA -> C:\\HTA\\App).

The pack carries the whole committed tree (R2-21: code, apps, tools, tests, docs, specs) and never any data:
it refuses task-like .md files outside tests/ and any data/.trash/private path. The work-PC CLAUDE.md and
START-HERE.md (docs/work-pack/*.template.md) are required.

Usage (from the repository root):
    python tools/make_work_pack.py              # build the zip only
    python tools/make_work_pack.py --release    # also tag build-<BUILD> and publish a GitHub release with the zip
    python tools/make_work_pack.py --release --replace   # same build number again: replace that release and tag

Files come from the committed HEAD (git show), never the working tree, so private/ and stray files can't leak.
The tree must be clean and HEAD pushed, so the release matches what's on GitHub.
"""
import datetime, hashlib, io, re, subprocess, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"


def git(*a, text=True):
    r = subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=text)
    if r.returncode:
        sys.exit(f"git {' '.join(a)} failed: {r.stderr}")
    return r.stdout


def show(path):
    return subprocess.run(["git", "-C", str(ROOT), "show", f"HEAD:{path}"], capture_output=True, check=True).stdout


def main():
    release, replace = "--release" in sys.argv, "--replace" in sys.argv
    if git("status", "--porcelain").strip():
        sys.exit("Working tree not clean: commit first.")
    commit = git("rev-parse", "--short", "HEAD").strip()
    build = re.search(r"const BUILD = '([^']+)'", show("app/index.html").decode()).group(1)
    name = f"html-todo-app-{build}"
    top = "App"                                     # R2-21: extract into C:\\HTA -> C:\\HTA\\App
    files = [f for f in git("ls-tree", "-r", "--name-only", "HEAD").split("\n") if f]

    # published path -> repo path: the whole committed tree (R2-21), the home CLAUDE.md/HANDOFF.md under docs/project/
    layout = {}
    for f in files:
        if f in ("CLAUDE.md", "HANDOFF.md", "README.md", ".gitignore"):
            continue
        layout[f] = f
    layout.update({"docs/project/PROJECT-CLAUDE.md": "CLAUDE.md", "docs/project/HANDOFF.md": "HANDOFF.md",
                   "docs/project/README.md": "README.md"})
    # never any data (R2-21 P4)
    for out, src in layout.items():
        low = "/" + out.lower()
        if any(x in low for x in ("/data/", "/.trash/", "/private/", "/backups/")) or low.endswith("_todo.json"):
            sys.exit(f"Refusing: {out} looks like task data.")
        if out.endswith(".md") and not out.startswith("tests/"):
            head = show(src)[:400].decode("utf-8", "replace")
            if head.startswith("---") and "\nid: t-" in head:
                sys.exit(f"Refusing: {out} looks like a task file.")
    for t in ("docs/work-pack/CLAUDE.template.md", "docs/work-pack/START-HERE.template.md"):
        if t not in files:
            sys.exit(f"Missing {t}: the work-PC guide must be in every pack.")
    fill = {"{BUILD}": build, "{COMMIT}": commit, "{DATE}": datetime.date.today().isoformat()}
    templates = {"CLAUDE.md": "docs/work-pack/CLAUDE.template.md", "START-HERE.md": "docs/work-pack/START-HERE.template.md"}

    blobs = {}
    for out, src in templates.items():
        t = show(src).decode("utf-8")
        for k, v in fill.items():
            t = t.replace(k, v)
        blobs[out] = t.encode("utf-8")
    for out, src in sorted(layout.items()):
        blobs[out] = show(src)
    sums = "".join(f"{hashlib.sha256(b).hexdigest().upper()}  {p.replace('/', chr(92))}\n" for p, b in sorted(blobs.items()))
    blobs["SHA256SUMS.txt"] = sums.encode()

    DIST.mkdir(exist_ok=True)
    zpath = DIST / f"{name}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p, b in sorted(blobs.items()):
            z.writestr(f"{top}/{p}", b)
    zsha = hashlib.sha256(zpath.read_bytes()).hexdigest().upper()
    index_sha = hashlib.sha256(blobs["app/index.html"]).hexdigest().upper()
    print(f"built {zpath} ({len(blobs)} files, {zpath.stat().st_size // 1024} KB)\n  zip SHA-256 {zsha}\n  app/index.html SHA-256 {index_sha}")

    if not release:
        return
    git("fetch", "-q", "origin")
    if git("rev-parse", "HEAD").strip() != git("rev-parse", "origin/main").strip():
        sys.exit("HEAD isn't pushed to origin/main: push first.")
    tag = f"build-{build}"
    exists = subprocess.run(["gh", "release", "view", tag], cwd=ROOT, capture_output=True).returncode == 0
    if exists and not replace:
        sys.exit(f"Release {tag} already exists. Bump BUILD, or rerun with --replace to republish this build.")
    if exists:
        subprocess.run(["gh", "release", "delete", tag, "-y", "--cleanup-tag"], cwd=ROOT, check=True)
        subprocess.run(["git", "-C", str(ROOT), "fetch", "-q", "--prune", "--prune-tags", "origin"], check=False)
        subprocess.run(["git", "-C", str(ROOT), "tag", "-d", tag], capture_output=True)
    notes = (f"Work-PC pack for build **{build}** (commit `{commit}`).\n\n"
             f"Download **{name}.zip**, extract it into `C:\\HTA` (it creates `C:\\HTA\\App`), open `C:\\HTA\\App\\app\\index.html`. "
             f"See START-HERE.md inside.\n\n"
             f"- ZIP SHA-256: `{zsha}`\n- app/index.html SHA-256: `{index_sha}`\n- Every file: SHA256SUMS.txt inside the ZIP.\n")
    subprocess.run(["gh", "release", "create", tag, str(zpath), "--target", git("rev-parse", "HEAD").strip(),
                    "--title", f"HTA build {build}", "--notes", notes], cwd=ROOT, check=True)
    url = f"https://github.com/gvd1024/html-todo-app/releases/download/{tag}/{name}.zip"
    print(f"released {tag}\n  download: {url}")


if __name__ == "__main__":
    main()
