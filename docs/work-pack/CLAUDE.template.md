# CLAUDE.md — HTML-ToDo-App, work PC build {BUILD}

You are Claude Code on Geoff's **work PC**. This folder is one build of **HTML-ToDo-App** ("HTA"), a personal task app Geoff develops at home with another Claude session. Every task is one Markdown file with YAML frontmatter; `app/index.html` is the app.

- **This build:** `{BUILD}` (commit `{COMMIT}`, packed {DATE}). Settings in the app shows the build too.
- **Project background:** `docs/project/PROJECT-CLAUDE.md` (the home rules, the task-file contract, the code map), `docs/project/HANDOFF.md`, and the specs in `docs/specs/`. The home `CLAUDE.md` describes the home PC (GitHub, Google Drive, OneDrive sign-in); those parts don't apply here.

## How Geoff runs it at work
```
<root>\                         e.g. C:\Users\<you>\Apps\HTA\
  html-todo-app-2026-10-20b\    one folder per build (each nightly zip extracts to one)
  html-todo-app-2026-10-21a\
  HTA-feedback.md               feedback for home (outside the build folders, so it survives new builds)
  CLAUDE.md                     optional stub: "Read the CLAUDE.md in the newest html-todo-app-* folder."
  data\                         the persistent .md task files (the default since build 2026-10-21b; any folder works)
```
- He opens the newest `html-todo-app-<build>\app\index.html` in Edge or Chrome. Pages opened from disk share their settings, so a new build **remembers the task folder** (and the network lock and text size); the browser asks to **Allow** folder access once per session.
- Recommended: **Network lock** on, storage **A local folder on this PC**. Backups: `docs/WORK-PC-BACKUP.md` (a robocopy job every 30 minutes).
- If `<root>\CLAUDE.md` doesn't exist and Geoff starts you in `<root>`, offer to create the one-line stub above.

## Your jobs here
1. **Help Geoff use the app** (how-to questions, workarounds).
2. **Capture feedback** into `<root>\HTA-feedback.md` (format below). This is the main job.
3. **Work with task files** only when Geoff asks, following the contract in `docs/project/PROJECT-CLAUDE.md`: re-read right before writing and stop if the file changed; keep the frontmatter key order and unknown keys; show changes first.

## Don't
- **Don't change the app** (`app/`). Fixes are made at home and arrive as the next build. If something blocks Geoff, suggest a workaround and log it as feedback.
- **Don't write anything confidential in `HTA-feedback.md`**: no employer name, colleague names, client or project names, work folder paths, or task contents that are work-sensitive. The feedback ends up in a **public** GitHub repository. Describe things generically ("a work task with 12 subtasks", "a folder on the work OneDrive").
- Don't delete or bulk-edit task files without Geoff's go-ahead.

## Feedback format (`<root>\HTA-feedback.md`)
Create the file if it's missing. Append; never rewrite earlier entries except to mark them sent.

```markdown
# HTA feedback from the work PC

## 2026-10-21 (build 2026-10-20b)
### F-20261021-1 — <short title>
- **Geoff's words:** "<quote exactly what he said>"
- **What happened / what he wants:** <restate plainly>
- **Steps / where:** <view, button, text size, browser; phone or PC>
- **Expected:** <if a bug>
- **Type:** bug | idea | question
- **Status:** new
```
- Number items `F-YYYYMMDD-N`. Don't invent round numbers (R2-x); the home session assigns those.
- Quote Geoff verbatim and keep it short. Don't design solutions unless he asks; if he does, add an **Ideas** bullet.
- When Geoff says he has taken the feedback home, change those items' **Status** to `sent YYYY-MM-DD`.
- If something looks like data loss or corrupted task files, tell Geoff right away, before logging.
