# CLAUDE.md — HTML-ToDo-App project

Claude Code reads this file automatically at the start of every session in this repository. Read `HANDOFF.md` next for the current state.

## What this is
**HTML-ToDo-App** is a personal task app that Geoff and Claude both work on. Every task is one Markdown file with YAML frontmatter. `app/index.html` is a phone-first list view (plus by-due-date) over a folder of those files, on phone and PC. Claude edits the same files directly. **Goal (2026-10-19):** eventually replace Super Productivity and Microsoft To Do, with Claude helping manage Geoff's personal and work tasks.

The long-term goal is one board that can open task folders in several places:
- a local folder on the PC
- Google Drive (personal tasks)
- Microsoft OneDrive (personal, then **work** OneDrive for work tasks)

with **full create/read/update/delete from Geoff's Android phone** on the exact same files.

## Working rules (Geoff's standing instructions — follow them strictly)
1. **Don't start a new revision of the app until Geoff explicitly says so.** Discussing, writing specs and pitching options are fine. Changing app code is not, until approved.
2. **Address only the items Geoff names.** Even items marked Decided in the spec aren't built until he names them.
3. **Every feedback round gets a Markdown spec** in `docs/specs/round-N-spec.md`:
   - Number each item (R1-1, R1-2, …).
   - Quote Geoff's wording, restate the problem, and pitch options A/B/C/D with pros and cons, plus a recommendation.
   - Add details as each item is discussed: decision, implementation notes, acceptance criteria.
   - Log every decision in the spec's Decision log, and keep the spec's change history.
   - Statuses: `Open → Discussing → Decided → Approved for build → Built → Verified`.
4. **Specs are Markdown only.** No HTML copies.
5. **Versioning:** app version in `APP_VERSION` (shown in the header) plus a separate **data format** (`DATA_FORMAT`, written to `_todo.json`). Released: v0.1.0, v0.1.1 (git tag `v0.1.1`). In progress: **v0.2.0-dev**, data format 2 (adds `prefix`, `completed`; statuses open/active/done/archived). The full R1-6 scheme can follow later.
6. **Geoff reviews before anything is executed.** Propose, wait for approval, then act. He wants detailed technical explanations with honest tradeoffs, and both simple and more complex options. He prefers phased checklists and a casual, direct tone.
7. **Resolve the hardest or most architecturally dependent problems first** (Geoff's design approach). The storage and phone requirements (R1-9, R1-10) come before UI polish.
8. **Verify before saying something doesn't exist.** Geoff has caught wrong "that's not possible" answers before.
9. **Prefer open, swappable, low-lock-in choices** (Geoff's principle). Data stays in plain `.md` and `.json`.
10. **Test data for builds and tests.** Builds and tests use the OneDrive folder `HTML-ToDo-App-Test` (copies). Preserving the `.md` files is the top priority.
    - **Until the MVP runs**, the existing "real" tasks (Google Drive `AI Brain/HTML_ToDo_Files`) aren't important, and Claude may fix or migrate them by hand (Geoff, 2026-10-16).
    - **Once the MVP runs**, Geoff will use the app for real (rapid prototyping in his personal life). From then on, real task files are protected: never touch them unless Geoff asks, and show changes first.
    - `AI Brain/ToDo App/` belongs to a different, older app (Vue plus `server.js`). Don't modify it.
11. **OneDrive is the committed datastore** (personal now, work later; decided 2026-10-16). The architecture lives in `docs/specs/storage-spec.md`.
12. **Public repo hygiene:** never write the employer's name or work folder paths in committed files. Say "work OneDrive" / "work PC".

## Task file contract (don't break it) — data format 2
```markdown
---
id: t-20261012-ab12        # stable, unique, never change
title: Fix gate latch      # the exact display text (file name is only a handle)
status: open               # open | active | done | archived
prefix: checkbox           # optional: checkbox | bullet | none (missing = checkbox)
list: Home                 # which list the task is in
collections: [repairs]     # optional (R1-5 may rename this to tags; read both if so)
parent: t-20261010-cd34    # optional → subtask
order: 3.5                 # fractional ordering among siblings
due: 2026-10-20            # optional, YYYY-MM-DD
completed: 2026-10-17      # optional: set when checked done, removed when unchecked
demoted_into: t-...        # only on archived tasks that were demoted
---
Free-form Markdown body; checklists are - [ ] / - [x].
```
- Keep frontmatter keys in this order. **Keep any unknown keys untouched**; the app shows ⚠ for unknown keys or values (e.g. old `doing`/`waiting`) and never rewrites them on its own. Claude migrates old values by hand (R1-12).
- `_todo.json` holds `{"format": 2, "lists": [...]}` plus any other keys it already has (keep them). The app version-checks it and merges list order on conflict.
- These files are not tasks: names starting with `_` or `.`, and `README.md`.
- A subtask's `list` always matches its parent's. `parent:` is the source of truth for nesting (S-11), not folders.
- File names are a slug of the title when the task is created (S-11 rules: lowercase, dashes, max 40 characters, Unicode letters kept, Windows reserved names avoided, case-insensitive unique). Renaming the title doesn't rename the file.
- **Demote:** a task becomes a checklist line in another task's body. When the original is kept, it becomes `status: archived` plus `demoted_into`, and the line ends with a link like `[↗](file.md)` (each path segment URL-encoded). **Promote** restores from that link; the nested body text wins over the archived file's body.
- **When Claude edits task files:** re-read right before writing and stop if the file changed (S-12); keep the key order and unknown keys.

## Code map
- `app/index.html` — the whole app (vanilla JS, single file), **v0.2.0-dev** (MVP build in progress, see storage-spec S-9). Served at `/app/`; `app/todo.html` just redirects there. Main parts:
  - **Storage (storage-spec S-2):** one interface — `list / read / write(path, text, expectedVersion) / create / remove / changes()` keyed by relative path with an opaque version. Connectors: `MemStore` (demo), `FsStore` (local folder, File System Access API; deletes keep a copy in the folder's hidden `.trash`), `GraphStore` (OneDrive via Microsoft Graph: `If-Match` writes → 412, `conflictBehavior=fail` creates → 409, deletes to the recycle bin, folder delta for changes, listing fallback for work OneDrive).
  - **Sign-in (S-5):** `MsalAuth` (MSAL Browser 5.22.0, redirect flow). Automatic bounce through Microsoft once per session when the cached sign-in is gone; unsaved edits are stashed in `localStorage` and restored after.
  - **Files:** `parseTask` and `serializeTask` use js-yaml with CORE_SCHEMA, so dates stay strings.
  - **UI (R1-12):** the phone-first list view (one list at a time, sticky prefix and ⋯ columns, sideways scroll with ⇤ and snap-back, subtask badges, quick-add), list-picker sheet, by-due-date view, full-screen Toast UI editor on phones with a prefix selector, demote and promote. The board view is retired.
  - **Sync (S-4):** `poll()` every ~10 s on phones / ~5 s on PCs plus on `visibilitychange`; reloads a file only when its version differs from the loaded one; conflict dialog with *Use theirs / Overwrite / Keep both*.
  - Settings (⋯ menu): text size; **Network lock** (R1-14: a CSP written at the top of `<head>` blocks all connections; OneDrive is off while on); storage choice (OneDrive folder, local folder, demo). Defaults: OneDrive folder `HTML-ToDo-App-Test`, client ID of the Azure registration `HTML-ToDo-App PoC`.
  - Installable app (R1-13): `app/manifest.webmanifest`, `app/icons/`, `app/sw.js` (no caching).
  - Security: see `SECURITY-REVIEW.md`. Tests include hostile task files (XSS) and the network lock.
- `app/vendor/` — libraries kept in the repository so the app works offline:
  - Toast UI Editor, bundled with ProseMirror by esbuild (the npm package has no "all" bundle)
  - MSAL Browser 5.22.0 (`msal-browser.min.js`, same file as the PoC)
  - js-yaml 4.1.0
  - SortableJS 1.15.2 (not loaded right now; kept for the Phase 5 long-press move)
- `poc/index.html` — the OneDrive proof of concept (R1-10 step 1), kept as a reference and test tool.
- `tests/` — automated tests: `run_tests.py` (Playwright), `fake_graph.py` (a strict in-memory Microsoft Graph), `store_suite.js` (the shared store suite), `screenshots/` (phone and PC screenshots from the last run).
- `docs/specs/` — round specs and `storage-spec.md`.
- `private/` — **git-ignored, local only**: Geoff's project memory export and the transcript of the Cowork session that produced all of this. Read these for background; never commit them, never copy their contents into committed files (the repository is public).

## Testing
- **Run:** `python tests/run_tests.py` from the repository root (or name groups: `store demo onedrive desktop signedout`). Needs `pip install playwright` and `python -m playwright install chromium` (installed on Geoff's PC 2026-10-17).
- **What it covers:** the store suite for all three connectors (OPFS stands in for a real folder; `fake_graph.py` for OneDrive, and it records any write without `If-Match` as a violation), the R1-12 list view at phone size, conflicts and Keep both, list-order merge, the sign-in bounce, and draft restore.
- **Not covered automatically:** real Microsoft sign-in and real phones (touch, Android back gesture). Geoff tests those.
- **Serve locally:** `python -m http.server 8000` from the repository root → `http://localhost:8000/app/` (needs that address as a redirect URI in Azure for sign-in).

## Where things live
- **Personal tasks (live data):** Google Drive folder `HTML_ToDo_Files`. Lists: Inbox, Test List, Feedback. The Feedback list holds the round-1 feedback tasks.
- **OneDrive proof-of-concept data:** personal OneDrive folder `HTML-ToDo-App-Test`. Use copies only.
- **GitHub:** repository `https://github.com/gvd1024/html-todo-app` (public; `main`). Git and GitHub operations go through the `gh` CLI, logged in as `gvd1024`. Commits use the repo-local noreply identity `35988830+gvd1024@users.noreply.github.com`.
- **GitHub Pages:** `https://gvd1024.github.io/html-todo-app/` (served from `main`, root). The app is at `/app/` and the proof of concept at `/poc/`. Each page's Microsoft redirect URI must be registered in Azure exactly, including the trailing slash.
- **Geoff's machines:** Windows PC (C: drive only) and an Android phone.
- **Code location:** `C:\dev\`, organized the way the code is hosted: `C:\dev\<host>\<account>\<repo>\`. Keep it **outside OneDrive**.
    - This repository: `C:\dev\github.com\gvd1024\html-todo-app\` (renamed from `taskboard` on 2026-10-14).
    - **Naming:** the app is called **HTML-ToDo-App** everywhere people read a name (docs, app title, Azure registration `HTML-ToDo-App PoC`). Folder, repo and URLs stay lowercase `html-todo-app`. Short form **HTA** is fine (Geoff uses it). Never call it "Task Board" or "TaskBoard" (old name, dropped 2026-10-15).
    - GitHub accounts: `gvd1024` (personal; this project) and `sivhold` (for a later project, at `C:\dev\github.com\sivhold\`).
    - Two GitHub accounts on one PC means each repository needs the right git identity and login. Set this per folder when the first `sivhold` repository is created.
