# Task Board

This is a local task board. Each task is its own Markdown file. `todo.html` gives you a board, an outline, and a by-due-date view. Claude, Obsidian, or any text editor can read and change the same files.

## Run it
1. Keep `todo.html` and the `vendor/` folder together. Everything works offline and needs no CDN.
2. Open `todo.html` in **Chrome or Edge on desktop**. Firefox and Safari can't write to local folders.
3. Click **Open folder…** and choose your tasks folder, for example `My Drive/Tasks/`. If the folder is empty, the page offers to add sample tasks.
   - Use a separate folder for tasks, not the folder this app lives in.
   - Chrome remembers the folder. On later visits, click **Reconnect** to allow access again.
   - If Chrome won't remember the folder when you open `todo.html` straight from disk, serve it locally instead: run `python -m http.server` in this folder and open `http://localhost:8000/todo.html`.

Until you open a folder, the page runs on demo data kept in memory, and nothing is saved.

## File contract (for people and for Claude)
One task per `.md` file in the tasks folder. Every task file starts with YAML frontmatter:

```markdown
---
id: t-20261012-ab12        # stable and unique; never change it
title: Fix gate latch
status: open               # open | doing | waiting | done | archived
list: Home                 # which column/list the task is in
collections: [repairs]     # optional; a task can be in several
parent: t-20261010-cd34    # optional; makes this a subtask
order: 3.5                 # position among siblings; fractions are fine
due: 2026-10-20            # optional, YYYY-MM-DD
demoted_into: t-...        # only on archived tasks that were demoted
---
Free-form Markdown notes. Checklists use - [ ] / - [x].
```

Rules:
- **Fields:** the page preserves any extra frontmatter keys, but don't rename the ones above.
- **File names:** a file name is a short slug of the original title. Renaming a task's title does not rename its file.
- **Subtasks:** a subtask always has the same `list` as its parent.
- **List order:** `_todo.json` holds the list order: `{"lists": ["Inbox", "Home", ...]}`.
- **Skipped files:** names starting with `_` or `.`, and `README.md`, are not treated as tasks.
- **Demoting:** demoting a task turns it into a checklist line in another task's notes. If you keep the original file, it becomes `status: archived` and the line ends in a link like `[↗](file-name.md)`. **Promote** uses that link to restore the original file with all its fields.

## Sync behavior
- **Outside changes:** every 4 seconds the page checks whether files changed outside it (Claude, Obsidian, Google Drive) and reloads them.
- **Conflicts:** before saving, the page checks that the file hasn't changed since it was loaded. If it has, it asks whether to keep the disk version or overwrite it.
- **What's remembered per browser:** which tasks are collapsed and which editor mode you last used. These are saved in the browser, not in the task files.

## Libraries (all MIT licensed, in `vendor/`)
- Toast UI Editor 3.2.2, bundled with its ProseMirror dependencies
- SortableJS 1.15.2
- js-yaml 4.1.0
