# R2-22 build report — reminders (Phase 1 + HTA Alarms)

**From:** the unattended cloud session (claude.ai/code), 2026-11-14/15, per `docs/briefs/r2-22-build.md`.
**Branch:** `claude/vibrant-mccarthy-dqcpgi` (nothing on `main`). **HTA build:** 2026-11-15a. **Data format:** 5.
**Status in the spec:** R2-22 **Built** (not Verified).

## TL;DR
- [x] HTA (web app): reminders in the task files, the editor's Remind section, 🔔 on rows, an in-app popup, the handoff to HTA Alarms. All stores, one code path.
- [x] HTA Alarms (Android): checker, alarms, spoken ringing screen, write-back, status panel. CI_LINE
- [x] One set of tricky task files (`tests/fixtures/frontmatter/`) that HTA and HTA Alarms must both edit byte for byte. Both do.
- [ ] Nothing has run on a real phone or against real OneDrive yet. That's your part (steps below).
- [ ] **One decision of mine needs your OK:** on a *repeating* task, Dismiss/Snooze don't remove the reminder from the file (see Open questions #1).

## What's built

### Phase 1 — HTA (build 2026-11-15a, data format 5)
- **Task files:**
    - `remind: 2026-11-14 17:00` for one reminder, `remind: [2026-11-14 09:00, 2026-11-14 17:00]` for several (sorted). Local time, 24 h, no zone.
    - `remind_text:` optional, shared by the task's reminders. Empty or missing → the title.
    - Both go right after `due`. A task with no reminders never gets either key.
    - A bad value (not a real date and time) → ⚠, kept as is, never rings.
    - Files that start with a BOM (Notepad's "UTF-8 with BOM") are now read correctly, and the BOM is kept. Before, HTA didn't see their frontmatter at all.
- **Format 5 in `_todo.json`:** only when a folder's **first** reminder is written (`_todo.json` is written first, then the task). A folder without reminders stays at 4, so older builds keep working on it. It never goes back down.
- **Repeating tasks:** check-off moves every reminder by the same number of days as the due date, same time of day. Copy mode: the copy gets them, the completed original loses them. No due date → unchanged.
- **Editor (phone and PC):** a Remind section under Due.
    - Each reminder is a native date+time box with ✕. **+ Add reminder** (next full hour, then adjust it).
    - Quick picks: In 1 hour · This evening 18:00 (Tomorrow 18:00 after 6 pm) · Tomorrow 09:00 · At the due date 09:00 (when there's a due date).
    - Reminder text box (placeholder: the title).
    - The limits note (R2-22 wording), shown once there's a reminder.
    - Warnings: a time already passed; and on a PC, a reminder less than 15 minutes ahead ("HTA Alarms may ring up to 15 minutes late").
- **Lists and Today:** 🔔 on rows with a reminder (tooltip: when). Greyed 🔔 = it already went off and wasn't answered; tap it to answer.
- **In-app popup** (any device, while HTA is open):
    - Text (or title), folder, due date, the time, "late" if more than 2 minutes past.
    - Snooze 10 min / 1 hour / Tomorrow / Pick… · Open task · Dismiss.
    - Dismiss removes that one entry; Snooze and Pick replace it. The write changes **only the remind line** (same edit as HTA Alarms), with If-Match. If the file changed, it re-reads and tries once more; if the reminder is already gone (dismissed on the phone), it says so and writes nothing.
    - Never shows twice: another tab or a reload doesn't show it again (a note in the browser's storage).
- **Handoff to HTA Alarms (Android only):** a **📲 Send to HTA Alarms now** button in the Remind section, and an automatic poke after each reminder change **only if** you switch it on: Settings → "Tell HTA Alarms right away" (off by default).

### Phase 2 — HTA Alarms (`android/`)
- **Package** `io.github.gvd1024.htaalarms`, app name "HTA Alarms". Android 17 (API 37) target, works from Android 10.
- **Sign-in:** MSAL, single account, HTA's Azure registration, redirect `msauth://io.github.gvd1024.htaalarms/aJ6Exuuw7N1kKUzxtANItriZ0Vw%3D`. Only the signed release APK can sign in.
- **Checks:** as soon as possible after :00, :15, :30, :45 (an exact alarm), plus app open, reboot, clock or time-zone change, app update, and HTA's handoff. Reads OneDrive's change feed and downloads only task files that changed. A big first read is done in parts (it keeps going a minute later).
- **Alarms:** one real Android alarm-clock alarm per reminder (⏰ in the status bar), exact to the minute. A reminder found already past rings at once, marked late.
- **Ringing:** full-screen over the lock screen; speaks the text (or title) on the **alarm volume** (plays in silent mode), pauses ~4 s, repeats for 3 minutes. Then stops and leaves a persistent **"Missed: …"** notification (tap → its buttons). Several at once: spoken one after another, listed together.
- **Buttons:** Dismiss · Snooze 10 min / 1 hour / Tomorrow / until… · Reschedule… (date + time). Written back to the task file, only the remind line, If-Match, one retry on 412. If the reminder was already changed elsewhere, or the task was checked off or deleted, it just stops.
- **Status panel (home screen):** account (red if sign-in expired), folder and its data format, last/next check, Check now, **Test alarm in 1 min**, Settings (folder, check mode: quarter hour or battery-friendly), the reminders list (tap → buttons), and a green/red line with a button for each: notifications, exact alarms, full-screen alerts, battery restriction, alarms in Do Not Disturb, alarm volume, Samsung "Never sleeping apps" (can't be detected: instructions + a button). The limits text at the bottom.
- **Safe failures:** offline or signed out → alarms already set still ring; buttons then change only the phone, and say so. A folder from a newer HTA (format > 5) → never written to.

### Shared contract (rule 13)
- `tests/fixtures/frontmatter/`: 15 task files (CRLF, unknown keys, odd key order, quoted title and value, BOM, no trailing newline, scalar/list/block-list `remind`, invalid values, a body with `---` and a fake `remind:` line, comments, no frontmatter, two `remind` keys, a map value, `remind: []`) and 24 edits (remove, replace, add, "gone", "refused") with the exact expected bytes, written by hand in `tests/fixtures/make_frontmatter_fixtures.py`.
- HTA's test (group `r222`) and HTA Alarms' JUnit test both produce byte-identical output for all of them.

## Tests
TESTS_SECTION

## The rounds
1. **Round 1 — build it.** Phase 1 complete with the `r222` group; the shared fixtures (written by hand first, then both implementations made to match); `android/core` with its JUnit tests; the Android app; both CI workflows.
2. **Round 2 — first CI runs + my own review.**
    - CI: `setup-android` broke on the runner → use the runner's own SDK manager; AGP 9 and the Kotlin plugin must share one class loader. Then the **signed release APK built first time**, and its signature hash matches Azure's.
    - Fixed: `_todo.json` was rewritten on every reminder save after the first bump; rows marked `hidden` still showed (the Android-only button appeared on PCs); a phone-only snooze and the test alarm rang again on every re-plan; the checker would never finish a big first read inside a broadcast's time limit (now: by content tag, 4 downloads at a time, a time budget, progress saved, a follow-up a minute later); a button could wait behind a 90-second check.
3. **Round 3 — code review (`/code-review`, 6 findings, all fixed).**
    - A reminder found in the past now rings late only within **a day** (both apps). Older ones show as missed (greyed 🔔 / the Missed list), so a first sign-in doesn't speak a month of old reminders.
    - A background ring start that Android refuses leaves a Missed notice instead of crashing.
    - If Android stops the ringing service early, what was ringing becomes "Missed", never silently lost.
    - Two files with the same task id (a conflict copy) ring once, like HTA.
    - A duplicate timer when text-to-speech fails to start.
    - Edge cases covered by tests: DST both ways (snooze "tomorrow", ring times in the skipped and the doubled hour, quarter-hour checks), a time-zone change, several reminders at the same minute, a task deleted or checked off while ringing, 412 conflicts (retry once, then "changed on this phone only"), two `remind` keys (never written), sign-in expiry (red line + notification; alarms already set keep ringing), offline (same), a folder from a newer HTA (never written).

## What couldn't be done or verified
- [ ] **Nothing ran on a phone.** No Android device or emulator here. The ringing path (screen off, silent, Do Not Disturb), the full-screen screen over the lock screen, text-to-speech, Samsung's battery manager and Android 17's exact rules can only be proven on the S23.
- [ ] **No real Microsoft sign-in or OneDrive.** HTA Alarms' Graph calls are written to Microsoft's documented API and the same patterns HTA uses, but only the logic around them is tested (fakes). HTA's side is tested against `fake_graph.py` as always.
- [ ] **The handoff link (`intent://…`) is untested in Chrome on Android.** What I know: Chrome only opens an app link right after a tap, and a page can't tell whether it worked. That's why it's a button, and the automatic poke is a Settings switch. If HTA Alarms isn't installed, Chrome goes to the fallback (this page + `#no-hta-alarms`), which should be a same-page jump with a note, not a reload; unverified. HTA Alarms' "sync" screen is invisible and closes at once.
- [ ] **Local Android SDK:** installing the SDK here needed accepting Google's SDK licence on your behalf, which this session's safety check refused. So the Android app is built only by GitHub Actions (where the workflow accepts it); the plain-Kotlin core is built and tested here too.
- [ ] **This sandbox's Chromium crashes** (SIGTRAP, no message) in 4 existing test groups (`localfolder`, `devicecopy`, `agentr1`, `r28p1`), on untouched `main` too. The runner now restarts the browser and carries on. GitHub's runner doesn't crash: see the web-tests workflow.
- [ ] **No app-module unit tests** (Android classes): everything testable without a phone is in `core` (13 JUnit tests, plus the 24 fixture edits).
- [ ] **Samsung "Never sleeping apps"** can't be detected by an app; the panel shows instructions and tries Samsung's battery screen.
- [ ] **Do Not Disturb:** Android 15+ "modes" are approximated by the interruption filter and the alarms category; the line can say "unknown" (yellow).

## Your steps (in order)
1. **Azure:** check that the registration "HTML-ToDo-App PoC" has the **Android** platform: package `io.github.gvd1024.htaalarms`, signature hash `aJ6Exuuw7N1kKUzxtANItriZ0Vw=` (should already be done).
2. **Get the APK:** GitHub → Actions → "HTA Alarms (Android)" → the latest green run on branch `claude/vibrant-mccarthy-dqcpgi` → Artifacts → `hta-alarms-2026-11-15a.apk` (a zip with the APK in it). The run's summary says whether it's signed. (The first signed one: run #3, artifact `hta-alarms-2026-11-15a.apk`; later pushes make newer runs with the same name — take the newest.)
3. **Install on the S23:** open the APK on the phone (download it there, or copy it over). Allow "Install unknown apps" for that source (Chrome or My Files) when asked.
4. **Permissions:** open HTA Alarms and work down the "This phone" list until every line is green: notifications, full-screen alerts, no battery restriction, alarm volume. Then Settings → Battery → Background usage limits → **Never sleeping apps** → add HTA Alarms (the "Open" button tries to take you there).
5. **Sign in** (button at the top). Check that the folder is `HTML-ToDo-App-Test` for now: **Settings → folder** (see step 7).
6. **Test alarm:** tap **Test alarm in 1 min**, then lock the phone. Try it three times: screen off; silent mode; Do Not Disturb on. It should light the screen, show the ringing screen and speak for 3 minutes (then nothing, for a test). Note what Samsung does.
7. **Real reminders on the test folder first** (not your real folder):
    - Make or reuse the copy folder `HTML-ToDo-App-Test` in OneDrive (rule 10).
    - On the PC: `python -m http.server 8000` in the repository (branch checked out) → `http://localhost:8000/app/` → Settings → OneDrive folder `HTML-ToDo-App-Test`.
    - Add a reminder 20+ minutes ahead on a task. Watch HTA Alarms pick it up by the next quarter hour (status panel), then ring. Try Dismiss, Snooze 10 min, Reschedule, and check the task file in HTA after each.
    - A reminder less than 15 minutes ahead from the PC: HTA warns; the phone rings late (at the next quarter-hour check), marked late.
    - Repeating task with a reminder: check it off in HTA, see the reminder move to the next date.
    - On the phone in HTA (the installed web app pointed at `localhost` won't reach your PC, so use the branch build another way, or skip): the 📲 button.
8. **Tell me** what worked and what didn't (or put it in Feedback). Only after that: merge, and the rollout below.

## Rollout plan for data format 5
1. **Don't add a reminder to the real folder until every device runs build 2026-11-15a or later.** The first reminder turns the folder's `_todo.json` to 5, and older builds then open it read-only (safe, but annoying).
2. Merge the branch to `main` (GitHub Pages updates the phone's installed HTA and the home PC's browser on the next launch; the service worker caches nothing). Check the header says 2026-11-15a on the phone and the PC.
3. **Work PC:** the next work pack must be this build or later before any reminder is written to the work folder. The work folder only gets format 5 when a reminder is written there, so until then nothing changes at work. (Work reminders stay on the work PC; HTA Alarms is personal OneDrive only.)
4. Claude (any instance) writing task files by hand: follow the new contract lines in CLAUDE.md (only the `remind` line changes; sorted list; format 5 in `_todo.json` first).

## Open questions for you
1. **Repeating tasks and Dismiss (my decision, please confirm).** The brief says Dismiss removes the entry. On a repeating task that would end your daily alarm after the first Dismiss (nothing left to move with the due date). So on a **repeating** task (a `repeat:` and a real `due`), Dismiss and Snooze in the popup / HTA Alarms stay on that device, and the reminder moves on when you check the task off in HTA. Reschedule in HTA's editor still changes the file. OK, or would you rather have Dismiss on a repeating task *also* roll the task forward (check it off)?
2. **Reminders older than a day** don't ring late; they show as missed. OK, or a different limit?
3. **Handoff:** keep the automatic poke off by default (switch in Settings), or on once you've seen it work?
4. **HTA's in-app popup on the phone:** it also pops up while HTA is open, next to HTA Alarms speaking. Keep it on the phone, or let HTA Alarms be the only one there?
5. **Snooze "until…"** in HTA Alarms picks a time today (or tomorrow if passed); "Reschedule…" picks a date and time. Is that the split you want?
