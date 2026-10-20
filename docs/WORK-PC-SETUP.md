HTML-ToDo-App — work PC setup (local folder only, no sign-in, network locked)
=============================================================================

What this is: a to-do app that's a single web page. In this setup it runs from files on your PC, keeps your tasks as plain .md files in a folder you pick, and is blocked by the browser from connecting to anything.

1. DOWNLOAD (pinned version "work-test-1", about 1 MB)
   https://github.com/gvd1024/html-todo-app/archive/refs/tags/work-test-1.zip
   (Project page, if you need it: https://github.com/gvd1024/html-todo-app)

2. UNZIP somewhere local, NOT inside OneDrive, for example:
   C:\Users\<you>\Apps\html-todo-app-work-test-1\
   You only need the "app" folder inside it.

3. OPTIONAL: VERIFY THE FILES (PowerShell, in the unzipped folder):
   Get-FileHash app\index.html, app\vendor\msal-browser.min.js, app\vendor\toastui-editor-all.min.js, app\vendor\js-yaml.min.js
   Expected SHA-256:
   86555A91B842220EDFE680C6BEC80639A986A76A93005FDE792C9C270E980B9D  app\index.html
   4E11FE5EFA6D1B09257E8269054C24E6B9755A745445936AAB4C2DC8EA876675  app\vendor\msal-browser.min.js
   B5A27D149EF87CF315857B199459B5B600C035C3FBF1C5E0FCFF7F8E1C11B7BF  app\vendor\toastui-editor-all.min.js
   45DC3DD03DC07A06705A2C2989B8C7F709013F04BD5386E3279D4E447F07EBD7  app\vendor\js-yaml.min.js
   (These match the ZIP download. A git clone on Windows may convert line endings and change the first one.)

4. MAKE A TEST FOLDER for the task files, e.g.
   C:\Users\<you>\Documents\HTML-ToDo-App-Test
   Use dummy test tasks only to start.

5. OPEN THE APP: double-click app\index.html (it opens in Edge or Chrome).
   Then: ... (top right) → Settings →
     - tick "Network lock: Block all network access"
     - choose "A local folder on this PC"
     - Apply (the page reloads)
   Pick your test folder and allow "edit" access.
   The folder is empty, so the app offers "Add sample tasks". Click it.

6. EVERY NEW BROWSER SESSION: click "Reconnect <folder>" once to re-allow the folder (normal for local files).

7. OPTIONAL CHECKS
   - Press F12 → Console. Any blocked connection attempt would show as a "Content-Security-Policy" message.
   - The app made no network requests when opened from disk (tested). With the network lock on, the browser blocks them even if something tried.

Notes
- Settings are stored per browser, and for pages opened from disk Chrome/Edge likely share that storage among ALL local HTML files. So the Network lock and other settings aren't isolated to this app. Fine for one app; just be aware.
- Deleting a task in local-folder mode keeps a copy in a hidden ".trash" folder inside your task folder (from the version after work-test-1).
- To use Claude at work on this: clone or unzip the repo and run Claude Code in it. It reads CLAUDE.md and HANDOFF.md (section "WORK PC — read this first").
- Security review with full details: SECURITY-REVIEW.md in the ZIP.
- Later (optional): put the task folder inside your work OneDrive sync folder for backup. Still no sign-in needed.

UPDATING TO work-test-2 (MVP complete, build 2026-10-19m)
---------------------------------------------------------
1. Download: https://github.com/gvd1024/html-todo-app/archive/refs/tags/work-test-2.zip
2. Unzip into a NEW folder next to the old one (e.g. ...\Apps\html-todo-app-work-test-2\). Keep the old one until the new one works.
3. Optional verify (PowerShell, in the new folder):
   Get-FileHash app\index.html, app\sw.js, appendor\msal-browser.min.js, appendor	oastui-editor-all.min.js, appendor\js-yaml.min.js
   BBCA8D2A24055704F42E73FF507DB77610A125598E27765745566C74814EB6B9  app\index.html
   C1C706D96CCF05BB4A46338957167BCEC345097E5E59CF9B6D48FC0A29AE7EBC  app\sw.js
   4E11FE5EFA6D1B09257E8269054C24E6B9755A745445936AAB4C2DC8EA876675  appendor\msal-browser.min.js   (unchanged)
   B5A27D149EF87CF315857B199459B5B600C035C3FBF1C5E0FCFF7F8E1C11B7BF  appendor	oastui-editor-all.min.js   (unchanged)
   45DC3DD03DC07A06705A2C2989B8C7F709013F04BD5386E3279D4E447F07EBD7  appendor\js-yaml.min.js   (unchanged)
4. Double-click the NEW app\index.html. Settings (including the Network lock) usually carry over, since local pages share browser storage.
   If it asks for a folder (or shows Reconnect), pick the same task folder again. Your task files are untouched; they live in that folder, not in the app.
5. Check: ... → Settings shows "build 2026-10-19m".
