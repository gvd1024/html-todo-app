"""Build the nightly work-PC pack: dist/html-todo-app-<BUILD>.zip, one top folder html-todo-app-<BUILD>/.

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
    files = git("ls-tree", "-r", "--name-only", "HEAD").split("\n")

    # published path -> repo path
    layout = {}
    for f in files:
        if f.startswith("app/"):
            layout[f] = f
        elif f.startswith("docs/specs/"):
            layout[f] = f
    layout.update({
        "docs/project/PROJECT-CLAUDE.md": "CLAUDE.md", "docs/project/HANDOFF.md": "HANDOFF.md",
        "docs/project/README.md": "README.md", "docs/SECURITY-REVIEW.md": "SECURITY-REVIEW.md",
        "docs/WORK-PC-BACKUP.md": "docs/WORK-PC-BACKUP.md",
    })
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
            z.writestr(f"{name}/{p}", b)
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
             f"Download **{name}.zip**, extract it into your HTA root folder, open `{name}\\app\\index.html`. "
             f"See START-HERE.md inside.\n\n"
             f"- ZIP SHA-256: `{zsha}`\n- app/index.html SHA-256: `{index_sha}`\n- Every file: SHA256SUMS.txt inside the ZIP.\n")
    subprocess.run(["gh", "release", "create", tag, str(zpath), "--target", git("rev-parse", "HEAD").strip(),
                    "--title", f"HTA build {build}", "--notes", notes], cwd=ROOT, check=True)
    url = f"https://github.com/gvd1024/html-todo-app/releases/download/{tag}/{name}.zip"
    print(f"released {tag}\n  download: {url}")


if __name__ == "__main__":
    main()
