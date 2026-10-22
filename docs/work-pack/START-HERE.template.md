# HTML-ToDo-App — build {BUILD}

**Install a new build (about a minute):**
1. Extract this ZIP into your HTA root folder (e.g. `C:\Users\<you>\Apps\HTA\`). It creates `html-todo-app-{BUILD}\` next to the older builds.
2. Close any open HTA tab, then open `html-todo-app-{BUILD}\app\index.html` in Edge or Chrome. Settings (⋯ → Settings) should show build **{BUILD}**.
3. It remembers your task folder from the last build. If it asks, click **Allow** for folder access.
   - First time only: ⋯ → Settings → tick **Network lock**, choose **A local folder on this PC**, Apply. The app shows where your task folder goes: **`data`**, next to the build folders (`<root>\data`). Copy the path, create the folder if it isn't there yet, and pick it.
   - Already using another task folder? Keep it: the app remembers it, and any folder with task files works.

**Optional checks:** `SHA256SUMS.txt` lists every file's SHA-256 hash; in PowerShell, `Get-FileHash app\index.html` should match.

**Claude Code at work:** start `claude` in this folder (or in the root, with a one-line `CLAUDE.md` there pointing to the newest build). It reads `CLAUDE.md` here and logs your feedback to `..\HTA-feedback.md`. Paste that file into the home session when you get home.

**Old builds:** keep a couple for rollback; delete the rest. They all share the same task folder; avoid having two builds open at once.
