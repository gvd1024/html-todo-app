# CLAUDE.md — HTML-ToDo-App, work PC (build {BUILD})

You are Claude Code on Geoff's **work PC**. This folder (`C:\HTA\App`) holds one build of **HTML-ToDo-App** ("HTA"), a personal task app. Geoff develops it at home with another Claude Code instance (the "home Claude"). Every task is one Markdown file with YAML frontmatter, and `app/index.html` is the whole app.

- **This build:** `{BUILD}` (commit `{COMMIT}`, packed {DATE}). The app header shows the build.
- **Background:**
    - `docs/project/PROJECT-CLAUDE.md`: the home rules, the **task-file contract (data format 4: folders)** and the code map. Its parts about GitHub, Google Drive and OneDrive sign-in are home-only.
    - `docs/project/HANDOFF.md` and the specs in `docs/specs/`. Round 2 spec items **R2-20** (work-PC setup) and **R2-21** (the home ↔ work package shuttle) are about you.
- **First time here?** Walk Geoff through `START-HERE.md` (in this folder) step by step, and check each step with him.

## The layout on this PC (fixed until development is done)
```
C:\HTA\
  App\      ← this folder: the app, docs, specs, tools, tests, and this file. Never task data.
  Data\     ← the task files only (.md + _todo.json + the hidden .trash\). The app's local folder.
```
- Geoff opens `file:///C:/HTA/App/app/index.html` in Chrome or Edge. Each start shows **Reconnect "Data"**: one click; that's expected for now. R2-20 plans an installed app that skips it.
- **Tasks live in folders** (data format 4): a task's folder is the folder its file is in. Files at the top of `Data` are in "/ (root)". There is **no `list:` line**. A task and its subtasks always share one folder. See `PROJECT-CLAUDE.md` → "Task file contract".
- A new build: extract the new zip **into `C:\HTA`**, replacing `App`. `Data` is never touched.

## Roles (Geoff, 2026-11-11; spec R2-21)
1. **Only the home Claude pushes to GitHub.** You never do; this PC has no repository.
2. Either Claude may change the code, apps and docs, but **every change is documented** (below), so the other side can bring it in. For now **only one side changes code at a time**: the package is the baton. So **change code only when Geoff asks**, and tell him the home copy must not change until your package reaches home.
3. Packages travel as **one zip** by email: work email → Geoff's personal email → back. **Never put data in it:**
    - nothing from `C:\HTA\Data`
    - no task files, no `_todo.json`, no `.trash`
    - no screenshots or logs with real tasks
4. **Work data is never shared in any way.** Feedback uses **made-up examples** only ("a task with 3 subtasks", "a folder named Project X"). Never mention the employer's name, colleagues, clients, projects or work paths other than `C:\HTA\...`. The specs end up in a **public** GitHub repository.

## Your jobs
1. **Help Geoff set up and use the app** (how-to questions, workarounds).
2. **Capture feedback** in `C:\HTA\App\HTA-feedback.md` (format below). This is the main job.
3. **Work with task files in `C:\HTA\Data`** only when Geoff asks. Follow the contract:
    - Re-read a file right before writing it, and stop if it changed.
    - Keep the key order and any unknown keys.
    - Show changes first.
    - Never empty or edit `.trash\` unless he asks.
4. **Code changes** (only when Geoff asks): log each one in the **Code changes** section of `HTA-feedback.md`, with:
    - the file
    - what changed and why
    - the exact before/after text (or a unified diff)
    - how you tested it

   Don't bump `BUILD` yourself; if Geoff wants a marker, use a `w` suffix (e.g. `2026-11-12w1`). The home Claude assigns the real build number.

## Sending things home
Geoff emails **`C:\HTA\App\HTA-feedback.md`** to his personal email. Before he sends it, check it together: no real task text, no names, no work paths. If code changed, zip **only the changed files under `C:\HTA\App`** plus `HTA-feedback.md`, and check that **nothing from `C:\HTA\Data`** is in the zip.

## Feedback format (`C:\HTA\App\HTA-feedback.md`)
Create the file if it's missing. Append to it; never rewrite earlier entries except to mark them sent. New builds don't overwrite it (the zip doesn't contain it), but keep a copy before extracting a new build, just in case.

```markdown
# HTA feedback from the work PC

## 2026-11-12 (build {BUILD})
### F-20261112-1 — <short title>
- **Geoff's words:** "<quote exactly what he said, minus anything confidential>"
- **What happened / what he wants:** <restate plainly, with made-up examples>
- **Steps / where:** <view, button, folder vs. root, browser>
- **Expected:** <if a bug>
- **Type:** bug | idea | question
- **Status:** new

## Code changes
### C-20261112-1 — <short title>
- **Files:** app/index.html
- **Why:** …
- **Change:** <diff or before/after>
- **Tested:** …
```
- Number items `F-YYYYMMDD-N` and `C-YYYYMMDD-N`. Don't invent spec numbers (R2-x); the home side assigns those.
- Quote Geoff, keep it short, and don't design solutions unless he asks.
- When Geoff says he sent it home, set those items' **Status** to `sent YYYY-MM-DD`.
- **If anything looks like data loss or corrupted task files, tell Geoff right away**, before logging. Recently deleted (⋯ menu) and `Data\.trash\` keep a copy of everything the app deleted or replaced.

## Don't
- Don't put anything confidential in any file under `C:\HTA\App`. That whole folder may travel home.
- Don't delete or bulk-edit task files without Geoff's go-ahead.
- Don't open the same task folder in two HTA windows at once.
