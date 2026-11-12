# HTML-ToDo-App — build {BUILD}: work PC setup

Tasks are **folders** now (data format 4): each folder in your task folder is a list. Files at the top are in "/ (root)".

## The two folders (keep these paths; don't move them later)
| Folder | Holds |
|---|---|
| `C:\HTA\App` | the app, docs, specs, tools (this folder) |
| `C:\HTA\Data` | **your task files only**. Never put it inside `App`; never email it. |

## First-time setup (about 5 minutes)
0. **Download the zip** in Chrome or Edge from **https://github.com/gvd1024/html-todo-app/releases/latest**: the file `html-todo-app-<build>.zip` under *Assets*. Don't email zips to work; the mail filter quarantines them.
1. **Extract the zip into `C:\HTA`**: right-click the zip → *Extract All…* → type `C:\HTA` → Extract. You get `C:\HTA\App\` (with `app\`, `docs\`, this file …).
   - If Windows blocked the download: right-click the zip → *Properties* → tick **Unblock** → OK, before extracting.
2. **Create the data folder** `C:\HTA\Data` (empty) in File Explorer, if it isn't there yet.
3. **Open the app:** in Chrome or Edge, open **`file:///C:/HTA/App/app/index.html`**. Bookmark it, or drag it to the bookmarks bar. The header should show **{BUILD}**.
4. **Network lock (recommended at work):** ⋯ → Settings → tick **Network lock**. It blocks all internet connections from the app (your tasks never leave the PC). Apply.
5. **Pick the task folder:** ⋯ → Settings → **A local folder on this PC** → *Open a local folder…* → choose **`C:\HTA\Data`** → **Allow** (edit access).
   - It asks "This folder has no task files…": choose **Start empty**.
6. **Make your folders:** tap the folder name at the top-left → **New folder** (e.g. one per area of work). Tasks you add go into the folder you're in; Today's quick-add goes to "/ (root)".
7. **Every later start:** open the bookmark → click **Reconnect "Data"** (Chrome asks again after the app is closed; expected for now).

## Check it (2 minutes)
- Add a task with a subtask in a folder, and check File Explorer: both `.md` files are in `C:\HTA\Data\<folder>\`.
- Delete a test task → ⋯ → **Recently deleted** → Restore. It comes back.

## Backups (recommended)
`docs\WORK-PC-BACKUP.md` sets up an automatic copy of the task folder into your work OneDrive every 30 minutes (built-in Windows tools, no admin). Use **`C:\HTA\Data`** as the task folder in it.

## Claude Code at work
- Open a terminal **in `C:\HTA\App`** and run `claude`. It reads `CLAUDE.md` here: the roles, the no-data rules, and how to log feedback.
- Ask it: *"Read CLAUDE.md and START-HERE.md and help me check my HTA setup."*
- Feedback goes to `C:\HTA\App\HTA-feedback.md`. To bring it home, say *"send it home"*. Claude prepares a text block (feedback, plus any code changes as text), and you paste it into the **body** of an email to your personal address. **No attachments.** Never send anything from `C:\HTA\Data`.

## Updating to a new build later
1. Close HTA.
2. Copy `C:\HTA\App\HTA-feedback.md` somewhere safe.
3. Download the new zip from **https://github.com/gvd1024/html-todo-app/releases/latest**, extract it into `C:\HTA`, and choose **Replace** when asked.
4. Open the same bookmark. `Data` is untouched, and the app remembers it (one Reconnect click).

## Optional
`SHA256SUMS.txt` lists every file's SHA-256 hash. In PowerShell, `Get-FileHash C:\HTA\App\app\index.html` should match the line for `app\index.html`.
