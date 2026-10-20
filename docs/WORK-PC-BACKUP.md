HTML-ToDo-App — automatic backup of a LOCAL task folder (work PC)
=================================================================

Goal: keep the task folder OUTSIDE OneDrive (so OneDrive doesn't watch it constantly), but copy it into OneDrive every 30 minutes.
You get:
- a copy off the PC;
- OneDrive's version history and recycle bin on the copies;
- far less OneDrive activity.

Uses only built-in Windows tools (robocopy + Task Scheduler). No admin rights needed for your own account.

What it does and doesn't do
- Copies new and changed .md files (and _todo.json) to the backup folder every 30 minutes.
- Never deletes anything in the backup. A task you delete locally stays in the backup copy (safer).
- Skips Chrome's temporary *.crswap files.
- Older versions of a changed file: use OneDrive's "Version history" on the backup copy.
- Edits made in the last <30 minutes before a failure aren't in the backup yet.


STEP 1 — Decide the two folders
-------------------------------
Task folder (local, the app uses this):    C:\Users\<you>\Documents\HTML-ToDo-Tasks
Backup folder (inside your work OneDrive): <your work OneDrive folder>\HTML-ToDo-Backup

To find your work OneDrive folder path, open PowerShell and run:
    $env:OneDriveCommercial
(If that prints nothing, open File Explorer, click your work OneDrive in the left pane, and copy the path from the address bar.)

Never point the app at the backup folder. The app uses the task folder only.


STEP 2 — Test the copy once by hand (PowerShell)
------------------------------------------------
Paste these lines, adjusting the two paths if yours differ:

    $src = "$env:USERPROFILE\Documents\HTML-ToDo-Tasks"
    $dst = "$env:OneDriveCommercial\HTML-ToDo-Backup"
    robocopy "$src" "$dst" /E /R:1 /W:1 /XF *.crswap /NFL /NDL /NP

Expected: a short summary table at the end, and the files now appear in the backup folder (check in File Explorer).
(robocopy's exit codes 0–3 mean success. Only 8 or higher means a problem.)


STEP 3 — Schedule it every 30 minutes (PowerShell, same window)
---------------------------------------------------------------
Paste all of this:

    $copyArgs = "--headless robocopy.exe `"$src`" `"$dst`" /E /R:1 /W:1 /XF *.crswap /NFL /NDL /NP"
    $action   = New-ScheduledTaskAction -Execute "conhost.exe" -Argument $copyArgs
    $trigger  = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Days 3650)
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries
    Register-ScheduledTask -TaskName "HTML-ToDo backup" -Action $action -Trigger $trigger -Settings $settings -Description "Copies the HTML-ToDo task folder into OneDrive every 30 minutes"

Notes:
- "conhost.exe --headless" runs robocopy without a window popping up every 30 minutes. If you DO see a black window flash, tell Claude; there's a fallback.
- "StartWhenAvailable" means that if the PC was asleep or off at a scheduled time, it runs as soon as it can.


STEP 4 — Run it now and check
-----------------------------
    Start-ScheduledTask -TaskName "HTML-ToDo backup"
    Start-Sleep 5
    Get-ScheduledTaskInfo -TaskName "HTML-ToDo backup" | Select-Object LastRunTime, LastTaskResult, NextRunTime

LastTaskResult 0–3 = OK (robocopy's success codes). Then edit a task in the app, run the Start- line again, and confirm the backup copy changed.


RESTORE (if something goes wrong)
---------------------------------
- A deleted or broken task:
  1. Copy it back from the backup folder into the task folder.
  2. In the app, pull down to refresh (or ⋯ → Refresh).
- An older version of a file: in OneDrive (website or File Explorer), right-click the file in HTML-ToDo-Backup → Version history.
- Also remember: the app's own 5-second Undo, and the hidden .trash folder inside the task folder (it holds copies of tasks deleted in the app).


UNDO / REMOVE THE BACKUP JOB
----------------------------
    Unregister-ScheduledTask -TaskName "HTML-ToDo backup" -Confirm:$false
(The backup folder and its files stay where they are. Delete them yourself if you want.)
