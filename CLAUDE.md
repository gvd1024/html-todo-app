# CLAUDE.md — Task Board project

Claude Code reads this file automatically at the start of every session in this repository. Read `HANDOFF.md` next for the current state.

## What this is
**Task Board** is a personal task app that Geoff and Claude both work on. Every task is one Markdown file with YAML frontmatter. `app/todo.html` is a board, outline and by-due-date view over a folder of those files. Claude edits the same files directly.

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
5. **Versioning:** the app is at **v0.1.1** (0.1.0 was the first build; 0.1.1 added the dark theme). Round 1 targets **v0.2.0**. The exact scheme is still being decided in spec item R1-6; the leading idea is an app version plus a separate data-format version. Once R1-6 is decided, update the version and changelog on every build.
6. **Geoff reviews before anything is executed.** Propose, wait for approval, then act. He wants detailed technical explanations with honest tradeoffs, and both simple and more complex options. He prefers phased checklists and a casual, direct tone.
7. **Resolve the hardest or most architecturally dependent problems first** (Geoff's design approach). The storage and phone requirements (R1-9, R1-10) come before UI polish.
8. **Verify before saying something doesn't exist.** Geoff has caught wrong "that's not possible" answers before.
9. **Prefer open, swappable, low-lock-in choices** (Geoff's principle). Data stays in plain `.md` and `.json`.

## Task file contract (don't break it)
```markdown
---
id: t-20261012-ab12        # stable, unique, never change
title: Fix gate latch
status: open               # open | doing | waiting | done | archived
list: Home                 # list / column
collections: [repairs]     # optional (R1-5 may rename this to tags; read both if so)
parent: t-20261010-cd34    # optional → subtask
order: 3.5                 # fractional ordering among siblings
due: 2026-10-20            # optional, YYYY-MM-DD
demoted_into: t-...        # only on archived tasks that were demoted
---
Free-form Markdown body; checklists are - [ ] / - [x].
```
- Keep frontmatter keys in this order. Keep any unknown keys untouched.
- `_todo.json` holds `{"lists": [...]}`, the list order.
- These files are not tasks: names starting with `_` or `.`, and `README.md`.
- A subtask's `list` always matches its parent's.
- File names are a slug of the title when the task is created. Renaming the title doesn't rename the file.
- **Demote:** a task becomes a checklist line in another task's body. When the original is kept, it becomes `status: archived` plus `demoted_into`, and the line ends with a link like `[↗](file.md)`. **Promote** restores from that link; the nested body text wins over the archived file's body.

## Code map
- `app/todo.html` — the whole app (vanilla JS, single file). Its main parts:
  - **Storage:** `MemStore` (demo data) and `FsStore` (File System Access API). Planned additions are a Google Drive store and a OneDrive store with the same interface.
  - **Files:** `parseTask` and `serializeTask` use js-yaml with CORE_SCHEMA, so dates stay strings.
  - **Editing:** a SortableJS board with nested drop zones; the Toast UI Editor 3.2.2 drawer with Raw/Formatted toggle; demote and promote.
  - **Sync:** a poll every 4 seconds; a conflict check by file modified time before writing.
- `app/vendor/` — libraries kept in the repository so the app works offline:
  - Toast UI Editor, bundled with ProseMirror by esbuild (the npm package has no "all" bundle)
  - SortableJS 1.15.2
  - js-yaml 4.1.0
- `poc/index.html` — the OneDrive proof of concept (R1-10 step 1). It uses MSAL Browser 5.22.0 (`poc/vendor/msal-browser.min.js`, bundled with esbuild as an IIFE that exposes `window.msal`) and Microsoft Graph. Sign-in uses redirect, not a popup, because popups fail on phones. Saves are conditional (`If-Match` eTag → 412), new files use `conflictBehavior=fail` → 409, and it watches for changes with a delta query.
- `docs/specs/` — round specs.
- `private/` — **git-ignored, local only**: Geoff's project memory export and the transcript of the Cowork session that produced all of this. Read these for background; never commit them, never copy their contents into committed files (the repository is public).

## Testing approach used so far
- **Headless Chromium + Playwright:**
  - Real mouse drag tests.
  - The browser's sandboxed file storage (OPFS) stands in for a real folder when testing `FsStore`.
  - A simulated `fetch` stands in for Graph.
- **Not tested yet:** real Microsoft or Google sign-in, and real phones. Geoff tests those himself.
- **Serve locally:** `python -m http.server 8000` from the repository root.

## Where things live
- **Personal tasks (live data):** Google Drive folder `HTML_ToDo_Files`. Lists: Inbox, Test List, Feedback. The Feedback list holds the round-1 feedback tasks.
- **OneDrive proof-of-concept data:** personal OneDrive folder `TaskBoard-Test`. Use copies only.
- **GitHub Pages:** `https://<username>.github.io/html-todo-app/`. The proof of concept is at `/poc/`, and the Microsoft redirect URI must match it exactly, including the trailing slash.
- **Geoff's machines:** Windows PC (C: drive only) and an Android phone.
- **Code location:** `C:\dev\`, organized the way the code is hosted: `C:\dev\<host>\<account>\<repo>\`. Keep it **outside OneDrive**.
    - This repository: `C:\dev\github.com\gvd1024\html-todo-app\` (renamed from `taskboard` on 2026-10-14; the app's display name is still "Task Board").
    - GitHub accounts: `gvd1024` (personal; this project) and `sivhold` (for a later project, at `C:\dev\github.com\sivhold\`).
    - Two GitHub accounts on one PC means each repository needs the right git identity and login. Set this per folder when the first `sivhold` repository is created.
