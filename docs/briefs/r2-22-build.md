# Brief: build R2-22 reminders (Phase 1 + HTA Alarms), unattended cloud session

**For:** a Claude Code session on claude.ai/code (cloud), working on a copy of `gvd1024/html-todo-app` while Geoff's PC is off.
**Written:** 2026-11-14 by the home Claude, with Geoff's decisions.
**Approved by Geoff:** yes, he asked for this overnight build, with several implement → test → improve rounds.

## 0. Read first, in this order
1. `CLAUDE.md`: the working rules. Rules **10, 12, 13, 14** matter most here, and so does the task-file contract.
2. `HANDOFF.md`: the current state.
3. `docs/specs/round-2-spec.md` → **R2-22** (the design, limits, phases, blockers), plus R2-1 (recurring tasks) and R2-5 (folders).
4. `app/index.html`: the app. Find `parseTask`, `serializeTask`, `KNOWN`, `saveTask`, the recurring code (`parseRepeat`, `nextDue`, the check-off roll), the editor drawer (`fillDrawer`, `#f-due`), `checkFormat`, `DATA_FORMAT`, `poll`, `GraphStore`.
5. `tests/run_tests.py`, `tests/fake_graph.py`, `tests/store_suite.js`: how testing works.

## 1. Hard rules for this session (non-negotiable)
- **Work on a branch** (e.g. `r2-22-reminders`, or the branch the environment gives you). **Never push to or merge into `main`.** `main` is the live app on GitHub Pages and Geoff's phone; Geoff merges after testing.
- **Never touch real data.** The cloud has no access to it anyway: no OneDrive, no `private/`. Tests use the demo store, OPFS and `fake_graph.py` only.
- **Never commit secrets or keys.** The signing key exists only on Geoff's PC and as GitHub Actions secrets (below). Never print secrets in logs.
- **Public repo:** no employer names or work paths; no personal data beyond what's already in the repo.
- **One code path (rule 13):** HTA changes go in the shared layers and work for every store (MemStore, FsStore, GraphStore). HTA Alarms is separate Kotlin code by necessity, but it must follow the **same task-file contract**. Prove that with shared test fixtures (section 5).
- **Commit only when the full test suite passes:** `python tests/run_tests.py`, plus the Android unit tests. Commit messages end with the `Co-Authored-By` line the environment asks for.
- If something is truly blocked (a tool can't be installed, an API is missing), **don't fake it**. Write it in the report (section 7) and continue with what you can do.

## 2. Geoff's decisions (2026-11-13/14), all final
| Topic | Decision |
|---|---|
| Order | **Phone first.** Phase 1 (HTA field + data format 5), then Phase 2 (HTA Alarms). The PC popup (Phase 3) is **not** in this session. |
| Reminders per task | **Several.** |
| Text | `remind_text:` optional. The title is used when it's empty **or doesn't exist**. One text per task, shared by all its reminders. |
| Voice | Text-to-speech only. **No voice recording** anywhere. |
| Snooze | **10 min / 1 hour / tomorrow (same time) / custom.** |
| Ringing | Speak the text, pause about 4 s, repeat for **3 minutes**. Then stop and leave a persistent "Missed reminder" notification (tap → open the task's actions). |
| Repeating tasks | The reminder **moves with the due date, keeping its time of day.** |
| Phone checks | **As soon as possible after :00, :15, :30, :45**, plus on app open and on the HTA handoff. Alarms ring at the exact minute; a reminder found already past rings at once, marked "late". |
| Limits shown in the UI | HTA's Remind field shows the note (R2-22). HTA Alarms has a status panel (R2-22). |
| Phone | Samsung Galaxy S23 Ultra (SM-S918U1), **Android 17, One UI 9.0**. |
| Scope | Personal OneDrive only (folder setting, default `HTML-ToDo-App`). No work data. |

## 3. Phase 1: HTA (web app), data format 5
**Data (update the contract in `CLAUDE.md` and the spec):**
```yaml
remind: 2026-11-14 17:00                          # one reminder: a plain string
remind: [2026-11-14 09:00, 2026-11-14 17:00]      # several: a YAML flow list, sorted
remind_text: Pick up the baby from daycare        # optional
```
- The format is `YYYY-MM-DD HH:MM`, 24-hour, **local time, no zone**. js-yaml CORE_SCHEMA keeps it a string; verify that, and test it.
- **Key order:** put `remind` and `remind_text` right after `due` (before `repeat`), and update `KNOWN` and the contract block. Unknown keys and the existing order are still kept.
- **Invalid values** (not a real date-time) → ⚠ and kept untouched, like a bad `due`. They never ring.
- **Write style:** one reminder is written as a scalar; several as a sorted flow list; none removes the key. A task with no reminders never gains the key.
- **Status:** done / archived / deleted tasks never ring. A reminder in the past stays until dismissed (helpers show it as missed or late).
- **Repeating (R2-1):**
    - When check-off rolls `due` forward (Recycle), every `remind` entry moves by the **same number of days**, keeping its time.
    - In Copy mode ("keep copies"), the **copy** gets the shifted reminders and the completed original loses `remind`.
    - Without a due date, the reminders stay as they are.
    - Test all three.
- **DATA_FORMAT → 5.**
    - `checkFormat` treats 5 as current. A folder written by this build shows format 5, so older builds open it read-only (expected, per the 2026-11-08a check).
    - Don't break format-4 folders: this build opens them normally. Decide and document when `_todo.json` gets bumped to 5: recommended **only when the first `remind` is written** in that folder, so a folder without reminders stays readable by older builds. Test it.
- **Editor UI** (phone and PC, in the drawer next to Due):
    - A **Remind** section: a list of date+time entries, each with ✕, and **+ Add reminder**.
    - Quick picks: in 1 hour, this evening 18:00, tomorrow 09:00, at the due date 09:00.
    - Use native `<input type="datetime-local">`, and check that it's usable on the phone.
    - An optional **Reminder text** input (placeholder = the title).
    - The **limits note** (R2-22 wording): it rings on the phone via HTA Alarms; set elsewhere, it reaches the phone by the next quarter hour; needs the phone on and HTA Alarms not force-stopped. Also a **warning** when a reminder is less than 15 minutes ahead and the device isn't the phone.
    - Class names must be unique to the app (see the `CLAUDE.md` CSS note).
- **List and Today views:** a small 🔔 on rows with a future reminder (tooltip: the next time).
- **In-app reminder popup** (while HTA is open, any device):
    - When a reminder's time arrives, show a modal with Dismiss / Snooze (10 min, 1 hour, tomorrow, custom) / Open task.
    - Writes go through the normal save path (If-Match, conflicts, trash rules).
    - **Dismiss removes that one entry; Snooze or Reschedule replaces that entry.**
    - It must not fire twice for the same entry across tabs: use a `localStorage` note of "shown" entries.
- **Handoff to HTA Alarms (Android only):** after a reminder is added, changed or removed in HTA on an Android phone, poke HTA Alarms so it syncs now.
    - Use an `intent:` link: `intent://sync#Intent;scheme=htaalarms;package=io.github.gvd1024.htaalarms;S.browser_fallback_url=…;end`. Find a way that **doesn't navigate away** or break the app when HTA Alarms isn't installed: e.g. only after a user tap ("Send to phone alarm now"), or a hidden iframe if Chrome allows it.
    - Document what actually works. If nothing is reliable without navigating, make it an explicit small button in the Remind section and say so in the report.
- **BUILD:** bump it (e.g. `2026-11-15a`). `APP_VERSION` stays.
- **Tests (new group `r222` in `run_tests.py`)** covering:
    - parse and serialize (scalar, list, empty, invalid → ⚠, unknown keys and CRLF kept)
    - key order
    - the editor UI (add, remove, quick picks, text)
    - the popup (dismiss, snooze, reschedule; no double fire)
    - repeating shifts (Recycle and Copy)
    - the format-5 bump rule
    - OneDrive writes still always use If-Match (the `fake_graph` violation check)
    - the 🔔 marker
    - every connector where storage is involved
    - **The full suite must stay green** (currently 735 checks).

## 4. Phase 2: HTA Alarms (Android, Kotlin), in `android/` at the repo root
**Identity and sign-in:**
- **Package / applicationId:** `io.github.gvd1024.htaalarms`. **App name:** "HTA Alarms".
- **Microsoft sign-in:** MSAL for Android, single-account mode.
    - Client ID `18f50dc2-e8ba-4b12-8735-1cf7d6c873cd` (the same Azure registration as HTA, "HTML-ToDo-App PoC")
    - Authority `https://login.microsoftonline.com/common`; scopes `Files.ReadWrite`, `User.Read`
    - Redirect URI `msauth://io.github.gvd1024.htaalarms/aJ6Exuuw7N1kKUzxtANItriZ0Vw%3D`
    - Signature hash `aJ6Exuuw7N1kKUzxtANItriZ0Vw=`: the permanent release key's base64 SHA-1. Geoff registers this "Android" platform in Azure.
    - **Sign-in only works in APKs signed with that key**, i.e. the GitHub Actions release build (below). Debug or cloud builds can't sign in. Design for that: unit tests mock the Graph layer.
- **Settings:** the OneDrive folder (default `HTML-ToDo-App`, same meaning as HTA's setting), the check mode (quarter-hour exact, the default, vs. battery-friendly), and a test alarm button ("Speak a test reminder in 1 minute").

**The checker:**
- Graph **delta** of the task folder, like HTA's `GraphStore.changes()`: track items by id, folders by id, re-path renamed folders; `MAX_DEPTH = 1`; skip `.`/`_` names, `.trash`, `README.md`.
- Read only the frontmatter of tasks (download the file; it's small).
- Keep a local index: task id → path, eTag, title, `remind_text`, entries, status.
- **Schedule the next check** with `setExactAndAllowWhileIdle` at the next :00/:15/:30/:45. **Re-arm** on: boot (`BOOT_COMPLETED`), `TIME_SET`, `TIMEZONE_CHANGED`, `MY_PACKAGE_REPLACED`, app open, and the `htaalarms://sync` handoff.

**Alarms:**
- One `AlarmManager.setAlarmClock` per (task, entry), with stable request codes; cancel what's gone.
- Permission: `USE_EXACT_ALARM`, which suits an alarm-clock app and avoids the user-granted `SCHEDULE_EXACT_ALARM`. Check Android 17's rules and document them.

**Ringing:**
- A full-screen intent notification (category ALARM) opens an activity over the lock screen (`showWhenLocked`, `turnScreenOn`).
- A foreground service (pick the right foreground-service type for Android 17 and document why) runs **TextToSpeech** with `AudioAttributes` `USAGE_ALARM`, so it plays in silent mode and on the alarm volume.
- Speak the text, pause about 4 s, repeat for 3 minutes. Then stop, and post a persistent "Missed: …" notification.
- If several are due at once, queue them, or speak them in sequence with one screen listing them.

**Buttons (ringing screen and missed notification):**
- **Dismiss:** remove that entry.
- **Snooze:** 10 min / 1 hour / tomorrow same time / custom → replace that entry.
- **Reschedule:** date + time picker → replace that entry.

**Write-back:** re-download the file with its eTag, edit **only** the `remind` line(s) **line-level** (keep every other byte: key order, unknown keys, CRLF/LF, body), then `PUT` with **If-Match**.
- On 412, re-read and retry once.
- If the entry is gone (changed elsewhere), just stop ringing.
- **Never** rewrite the whole frontmatter through a YAML library.

**Status panel (home screen of the app):**
- last check, next check, signed-in account, folder
- the upcoming reminders list (tap → snooze, reschedule, dismiss)
- a green/red line for each requirement, each with a button to the right Settings screen:
    - notifications
    - exact alarms
    - full-screen intents (Android 14+ `canUseFullScreenIntent`)
    - battery optimization ignored
    - alarms allowed in Do Not Disturb (if detectable)
    - alarm volume > 0
    - **Samsung "Never sleeping apps"**: not detectable; show instructions plus a button to Samsung's battery settings, with a generic fallback
- the limits text (R2-22): rings only if the phone is on and the app isn't force-stopped; changes made elsewhere arrive by the next quarter hour

**Build setup:**
- **Gradle Kotlin DSL**, current stable AGP and Kotlin.
- `minSdk` 29 or higher is fine (the phone is Android 17). `targetSdk`/`compileSdk`: the newest stable SDK you can install; aim for the Android 17 API level if available, and document what you used.
- Keep dependencies few and well known: MSAL, AndroidX, coroutines, kotlinx-serialization if needed. **No analytics or tracking.**
- **Unit tests (JVM)** for:
    - the frontmatter read and line-level edit, against the shared fixtures (section 5)
    - the `remind` parsing (scalar, list, invalid)
    - quarter-hour scheduling math
    - snooze math, including "tomorrow" across DST changes
    - delta bookkeeping (fake Graph responses)
    - the repeat-and-roll interplay, if the app touches it (it shouldn't; HTA rolls)
- Robolectric is optional.

**GitHub Actions:** add `.github/workflows/hta-alarms.yml`.
- Triggers: push on any branch touching `android/**`, plus `workflow_dispatch`.
- Steps:
    - JDK 17 (or what AGP needs) and the Android SDK
    - `./gradlew test assembleRelease`
    - **If the secrets exist**, sign the release APK with them. The secrets are `HTA_ALARMS_KEYSTORE_B64` (base64 PKCS12), `HTA_ALARMS_KEYSTORE_PASSWORD` (store and key password) and `HTA_ALARMS_KEY_ALIAS` (`htaalarms`). Decode the keystore to a temp file in the runner, sign, then delete it.
    - Upload `hta-alarms-<version>.apk` as a workflow artifact.
    - If the secrets are missing, build a debug APK and say so in the job summary.
- **Never echo secrets.** Store type PKCS12.
- Version: `versionName` = the HTA `BUILD`-style date, plus `versionCode` that always increases (e.g. from the run number or the date).
- Also consider a second workflow (or job) that runs the web tests `python tests/run_tests.py` with Playwright, so Geoff can see green checks on the branch.

## 5. Shared contract fixtures (rule 13)
Create `tests/fixtures/frontmatter/`: tricky task files and the expected result of each edit. Cover:
- CRLF files
- unknown keys
- odd key order
- quoted titles
- BOM
- no trailing newline
- `remind` as a scalar or a list
- an invalid `remind`
- a body containing `---`

Edits:
- remove an entry
- replace an entry
- add one (HTA only)

**Both** the JS tests (a small runner using the app's functions in the page) and the Kotlin unit tests must produce byte-identical output from the same fixtures.

## 6. Work in rounds (Geoff asked for quality)
Do **at least three** rounds, each one: **implement → run every test → review your own diff critically (correctness, the contract, rule 13, Android 17 behavior, battery, security: no tokens in logs) → fix → re-test.**

Suggested shape:
1. **Round 1:** Phase 1 complete with tests; the Android skeleton that builds; a test alarm that speaks.
2. **Round 2:** the checker plus delta, scheduling, the ringing service, write-back, the status panel, the fixtures in both languages, the CI workflow.
3. **Round 3:** edge cases, plus a review pass with the `/code-review` skill if available (or a careful manual review). Then: DST and time-zone changes, reboot, several reminders at the same minute, a task deleted while ringing, a 412 conflict, sign-in expiry (show it red in the status panel, and keep the scheduled alarms ringing anyway), offline (alarms already scheduled still ring), and the read-only format check.

Commit after each green round, with clear messages, and push the branch.

## 7. The report (required): `docs/briefs/r2-22-report.md`
Commit this at the end. In Geoff's style: short sections, plain words, checklists.
- **What's built** (Phase 1, Phase 2), the test counts, and what each round changed.
- **What couldn't be done or verified**, and why.
- **Geoff's steps**, in order:
    1. Check the Azure Android platform entry (should already be done).
    2. Get the signed APK from the GitHub Actions run.
    3. Install it on the S23. Allow installs from that source.
    4. Grant the permissions, guided by the status panel. Add the app to Never sleeping apps.
    5. Sign in.
    6. Use the test alarm with the screen off, in silent mode, and in DND.
    7. Test real reminders set from HTA on `localhost:8000`, using the **test folder** `HTML-ToDo-App-Test` first, **not** the real folder.
- **The rollout plan for data format 5:** update the PC and phone HTA before the first reminder is written; the work PC pack.
- **Open questions** for Geoff.
- Update R2-22 in the spec with "Phase 1 — as built" and "Phase 2 — as built" (status **Built**, not Verified), plus the decision log and change history, and update `HANDOFF.md` and the `CLAUDE.md` contract and code map.
