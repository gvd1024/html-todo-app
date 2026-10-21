# HTML-ToDo-App (v0.2.0-dev)

A task list where each task is its own Markdown file. The same files open on your Android phone and your PC (through OneDrive), and Claude, Obsidian or any text editor can read and change them too.

## Run it
- **Phone or PC, with OneDrive (the default):** open `https://gvd1024.github.io/html-todo-app/app/` in Chrome and tap **Sign in with Microsoft**. The app opens the OneDrive folder set in **⋯ → Settings** (default `HTML-ToDo-App-Test`).
  - The page's address must be a redirect URI of the Azure app registration (`HTML-ToDo-App PoC`): `https://gvd1024.github.io/html-todo-app/app/`, and `http://localhost:8000/app/` for local testing.
  - After the first sign-in, the app re-signs you in automatically when the browser forgets the session (with "Stay signed in" on, that's a quick bounce, no typing).
- **A local folder (desktop Chrome/Edge):** ⋯ → Settings → *A local folder on this PC*.
- **Demo data:** ⋯ → Settings → *Demo data* (nothing is saved).
- **Network lock:** ⋯ → Settings → *Block all network access*. The browser then stops the page from connecting anywhere (use a local folder). Good for a work PC where tasks must stay local.
- **From disk, no web server:** double-click `app/index.html`. It makes no network requests unless you sign in.
- **Locally:** `python -m http.server 8000` from the repository root, then `http://localhost:8000/app/`.

## Using it
- The big name at the top is the current list — tap it to switch lists, add or rename lists, or open **Today** (all lists).
- **Today view:** *Upcoming* (next 7 days, collapsed; furthest date on top, with “+ N later” above), *Today*, and *Overdue* (collapsed; newest first). Future is up, past is down.
    - One-tap buttons: **Today** / **Tmrw** to reschedule (5 s Undo); ⋯ → **Change due date…** for any date.
    - Tasks without a due date don't appear. For a recurring task, the buttons move just this occurrence.
    - **Quick-add here** has two chips: the **list** (remembered) and the **date** (Today by default; tap for Tomorrow, a week, any date, or No date).
- Tap the box to check a task off; tap the title to open the editor; tap **⋯** for Edit, Move to list, Change prefix, Add subtask and Delete.
- A **1/3** badge means the task has subtasks (1 of 3 still open) — tap it to show or hide them.
- Long titles: drag the whole list sideways; the boxes and ⋯ stay put; **⇤** (or waiting 3 seconds) brings it back.
- Type in the box at the bottom and press Enter to add a task to the current list.
- ⚠ on a row means its file has frontmatter the app doesn't recognize. The app keeps it untouched.
- **Recurring tasks:** in the editor, set **Repeat** (Daily, Weekdays, Weekly, Every 2 weeks, Monthly, Yearly, or Custom like "every 3 days" or "monthly on last day").
    - **Mode:** **Recycle** (the same task moves to its next date, everything unchecked) or **Copy** (the finished one is kept as done, and a copy is made for the next date).
    - **Next date:** *Skip missed*, *Catch up*, or *From completion*.
    - Recurring tasks show **↻**.
- If a file changed elsewhere while you were editing, Save offers **Use their version / Overwrite with mine / Keep both** (Keep both saves yours as a separate `(conflict …)` copy).

## File contract (data format 2)
One task per `.md` file. Every task file starts with YAML frontmatter:

```markdown
---
id: t-20261012-ab12        # stable and unique; never change it
title: Fix gate latch      # the exact text shown in the list
status: open               # open | active | done | archived
prefix: checkbox           # optional: checkbox | bullet | none (missing = checkbox)
list: Home                 # which list the task is in
collections: [repairs]     # optional; a task can be in several
parent: t-20261010-cd34    # optional; makes this a subtask
order: 3.5                 # position among siblings; fractions are fine
due: 2026-10-20            # optional, YYYY-MM-DD
completed: 2026-10-17      # optional; the day it was checked done
demoted_into: t-...        # only on archived tasks that were demoted
---
Free-form Markdown notes. Checklists use - [ ] / - [x].
```

Rules:
- **Fields:** the app keeps any extra frontmatter keys untouched (and flags them with ⚠). Don't rename the ones above.
- **File names:** a short slug of the original title (lowercase, dashes, up to 40 characters). Renaming a task's title does not rename its file.
- **Subtasks:** a subtask always has the same `list` as its parent.
- **List order:** `_todo.json` holds `{"format": 2, "lists": ["Inbox", "Home", ...]}`.
- **Skipped files:** names starting with `_` or `.`, and `README.md`, are not tasks.
- **Demoting:** demoting a task turns it into a checklist line in another task's notes. If you keep the original file, it becomes `status: archived` and the line ends in a link like `[↗](file-name.md)`. **Promote** uses that link to restore the original file with all its fields.

## Sync behavior
- **Outside changes:** the app checks OneDrive for changes about every 10 seconds on a phone and 5 on a PC, and right away when you come back to it. Only files that really changed are reloaded.
- **Safe saves:** every save says "only if the file is still the version I loaded" (OneDrive `If-Match`). If it isn't, you get the conflict dialog — nothing is overwritten silently.
- **Deletes** go to the OneDrive recycle bin.

## Libraries (all MIT licensed, in `vendor/`)
- Toast UI Editor 3.2.2, bundled with its ProseMirror dependencies
- MSAL Browser 5.22.0 (Microsoft sign-in)
- js-yaml 4.1.0
- SortableJS 1.15.2 (for the upcoming long-press move)
