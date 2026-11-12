# HTML-ToDo-App — Round 2 Spec

| Field | Value |
|---|---|
| **App** | HTML-ToDo-App (`app/index.html`) |
| **Baseline** | v0.2.0-dev, build 2026-10-19m (the MVP: storage-spec S-9 Phases 1–5, plus round-1 fixes) |
| **Theme** | Features toward replacing Super Productivity and Microsoft To Do (Geoff's goal, 2026-10-19) |
| **Spec status** | Discussing. Nothing approved for build. |
| **Last updated** | 2026-10-20 |

## Ground rules
Same as round 1:
- No code until Geoff approves; only named items get built.
- Statuses: `Open → Discussing → Decided → Approved for build → Built → Verified`.
- Decisions are logged at the bottom.

## Summary

| # | Item | Status | Recommendation |
|---|---|---|---|
| R2-1 | Recurring tasks | **Built** | Plain-English `repeat:` phrases; two modes per task (**Recycle** = same file, **Copy** = keep a record); three next-date rules |
| R2-2 | Today view (rework "By due date") | **Built** | Upcoming (collapsed) · Today · Overdue (collapsed); one-tap Today/Tomorrow; ⋯ → Change due date… |
| R2-4 | Default task folder next to the app | **Built** | B: `<root>\data`, path shown to paste into the folder dialog, plus a check on the pick |
| R2-6 | Phone still opens in desktop mode (R1-15 not holding) | **Built** (A 2026-10-24c; sign-in C + editor fix 2026-10-31a) | Sign-in no longer leaves the app window; editor fits a desktop-mode phone; ⤢ bigger notes. Awaiting Geoff's check |
| R2-7 | Scale: support many more tasks | **A built** | **A** first (a copy on each device + change-only sync), then B; C only if needed |
| R2-8 | Don't lose anything (data-safety review) | **Phase 1 verified** (PC and phone; build 2026-11-01b, on `main` since 2026-11-07) · **Restore with subtasks: verified on PC** (build 2026-11-07a, on `main` since 2026-11-07) · Phase 1 = Deleted A, C, D · Overwritten A–C · Checked off D · Hidden C, D · Phase 2 with R2-5 folders (Deleted B, Hidden A) · Moving tasks in: deferred | Phase 1 designed for folders from day one |
| R2-5 | A folder per list (file-explorer model) | **Built** (2026-11-08b, data format 4, branch `r2-5-folders`); awaiting Geoff's test, then the real-folder migration | Full implementation discussion before any build; after the R2-8 safeguards; prototype on the test folder |
| R2-9 | Add tasks by voice with Amazon Echo (Alexa) | **Open** | Try 2b (Claude sweeps Alexa's own to-do list via an MCP server), then 2a (a home-PC sweeper); 1 (a private Alexa skill) as the official fallback |
| R2-10 | Build number in the header, version in Settings | **Built** (2026-11-07b) | A: the plain build at the top right (PCs); version stays in Settings |
| R2-11 | Enter tasks and subtasks one after another | **Built** (2026-11-07c; verified on PC and phone) | Enter in a new task's title = save + next sibling; inline "+ Add subtask…" line; ⋯ → Add subtask opens it |
| R2-12 | Save & close subdued until there's a change | **Built** (2026-11-07c; verified on PC and phone) | Subdued, still closes |
| R2-13 | Clear a due date on the phone | **Built** (2026-11-07c; verified on PC and phone) | ✕ next to Due in the editor; "No date" in Change due date… |
| R2-14 | Today view: ↑ ↓ ● instead of Today / Tmrw | **Built** (2026-11-07c; verified on PC and phone) | From the due date; ● hidden on today rows |
| R2-15 | Delete all: readable button | **Built** (2026-11-07c; verified on PC and phone) | White on deep red |
| R2-21 | Home ↔ work: shuttle one package by email (two Claude instances) | Roles decided | git bundle + hand-off .md; no data; only home pushes |
| R2-20 | Work PC: no Reconnect every start; sharing with coworkers | Open | Installed app from a web address keeps the folder (tested); stable address before sharing |
| R2-19 | A way to hide the "Add subtask…" lines | Open | Show the line only on demand (recommended) |
| R2-18 | Show that files are being changed (busy indicator) | Open | Spinning status icon + progress toast for multi-file actions (recommended) |
| R2-17 | Review the repeat options; month-end dates drift | Open | Plain `monthly` from the 29th–31st drifts to the 28th; Geoff to review |
| R2-16 | Explain the repeat "Next date" choices | **Built** (2026-11-09a, branch) | Tooltips (PC only) |
| R2-3 | Quick-add in the Today view | **Built** | B + tappable **list** and **date** chips on the input line |

---

## R2-1 — Recurring tasks

**Reported** (Geoff, 2026-10-20): "Recurring tasks" (first of two items to work on; listed 2026-10-19 as a feature Super Productivity / MS To Do have and HTA doesn't).

**Problem (restated):** some tasks come back on a schedule ("water plants every 3 days", "pay rent on the 1st", "weekly review on Fridays"). Today each would need a new file by hand. The app needs:
1. a way to **store** a schedule in the task file;
2. what happens when you **check it off**;
3. a way to **set** it in the editor.

### Q1 — How the schedule is written in the file
- **A — Plain-English phrases** with a small fixed grammar:
    - **Format:** `repeat: daily` · `repeat: weekdays` · `repeat: weekly on mon, thu` · `repeat: every 2 weeks` · `repeat: monthly on day 1` · `repeat: monthly on last day` · `repeat: yearly` · `repeat: every 3 days after done`.
    - **Pros:** easy for Geoff and Claude to read and type in the raw file; fits "plain files people and Claude edit".
    - **Cons:** our own mini-language. It must be documented, and unknown phrases are flagged ⚠ and left alone.
- **B — The calendar standard (iCalendar RRULE).** `repeat: FREQ=WEEKLY;BYDAY=MO,TH`.
    - **Pros:** an open standard, very expressive, convertible to calendars.
    - **Cons:** hard to read or type by hand.
- **C — Both:** phrases in the file, converted to RRULE internally.
    - **Pros:** readable now; calendar export possible later.
    - **Cons:** slightly more code.

**Recommendation:** **A**, designed so each phrase maps cleanly to an RRULE (so C is a later add-on, not a rewrite).

### Q2 — What happens when you check a recurring task off
- **A — Roll forward in place (same file).**
    - Checking it moves `due:` to the next date, re-opens it, resets its body checklist (`- [x]` → `- [ ]`) and re-opens its subtasks.
    - It records `last_done: <date>`, plus an optional one-line history in the body, e.g. "Done 2026-10-20".
    - The Undo bar shows "Next: Fri 24 Oct".
    - **Pros:** one file per routine; no clutter (a daily task doesn't create 365 files a year); Claude sees one stable file.
    - **Cons:** no per-occurrence file. History is a date list, not separate files.
- **B — Complete and create the next one** (MS To Do style). The checked task stays `done` (and hides); a **new file** is created for the next date (copy of title, notes and subtasks with checkboxes reset).
    - **Pros:** a full record of each occurrence; familiar from To Do.
    - **Cons:** many files over time (needs the archive feature); duplicate titles; subtasks get duplicated each time.
- **C — Per task: A by default, B as an option** (`repeat: … keep history`).
    - **Pros:** flexible.
    - **Cons:** two behaviors to learn and test.

**Recommendation:** **A**, with a short "Done …" log appended to the notes so history isn't lost.

### Q3 — How the next date is calculated
- **A — From the due date, skipping missed ones.** "Weekly on Mon" overdue by 3 weeks → next Monday from **today**, not three back-to-back past Mondays.
- **B — Strictly the next one after the old due date** (may still be in the past; you catch up one at a time).
- **C — From the day you complete it:** only for phrases ending in `after done` (e.g. "every 3 days after done": next = completion day + 3).

**Recommendation:** **A**, plus **C** for `… after done` phrases (good for chores like watering plants).

### Q4 — Setting it in the app
- **Editor:** a **Repeat** field (next to Due) with presets.
    - **Presets:** None · Daily · Weekdays · Weekly (on the due day) · Every 2 weeks · Monthly (on the due date) · Yearly · Custom… (type a phrase, checked live, with an example).
    - **No due date set:** choosing a repeat sets due = today.
- **List:** a small **↻** next to the title of recurring tasks.
- **Claude:** can set or edit `repeat:` directly in the files, using the same phrases.

### Other details to decide
1. **Subtasks of a recurring task:** reset them to open each time (rec.), or leave them?
2. **Body checklist:** reset `- [x]` lines each time (rec.)?
3. **Stopping a series:** clear the Repeat field. Optional extra: `repeat: … until 2026-12-31` (rec.: later).
4. **Data contract:** new keys `repeat` (after `due`) and `last_done` (after `completed`). This is **data format 3** (old app versions would show them as ⚠ unknown keys and keep them).

**Acceptance criteria (draft):**
- Each phrase computes the right next date: weekdays skip weekends; "monthly on day 31" → the last day in short months; leap years handled.
- Checking off rolls forward in place, resets checklists and subtasks (if chosen), shows "Next: …" with Undo, and the Undo restores everything exactly.
- An unknown phrase → ⚠, and the checkbox behaves as a normal task (no roll-forward).
- Works the same on phone, PC and in local-folder mode; conflict-safe like any save.

### Decisions (Geoff, 2026-10-20)

**Q1 — Format: A, plain English.** For example `repeat: weekly on mon, thu`. The phrases are designed to map to iCalendar RRULE later.

**Q2 — Two modes per task** (Geoff: "generally i want options"):
- **Recycle (the default):** checking it off **reuses the same file**.
    - **Moves forward:** `due:` advances to the next date.
    - **Unchecks everything:** the task itself, **all its subtasks** and **all `- [ ]` lines** in its notes.
    - **Keeps** whatever was added, removed or changed in the notes and subtasks.
    - **Records nothing** about the completion.
- **Copy (keep a record):** *"the original file remains handled like any regular task, and the app makes a copy of the task and the copy gets the new date with all checkmarks reset."*
    1. **The original** is completed like any task (status `done`, `completed:` date; its notes and checkmarks stay as they were). It **stops repeating**: its `repeat:` moves to the copy, so only one task in a series is ever live.
    2. **The copy** gets the next date, with every checkbox reset (task, subtasks, notes). It gets a **new id**, and all copies share a **`series:`** key (the first task's id), so every past completion can be found.
    3. **The copy's file name:** the title slug plus the new date as **YYYYMMDD**, no dashes, e.g. `water-the-plants-20261027.md` (slug ≤ 40 characters, then `-YYYYMMDD`; a further `-2` etc. if it's taken).
    4. **Subtasks:** the copy gets **fresh copies of all subtasks**, unchecked. The originals stay with the completed task, as they were.
    5. **In the editor:** a choice **Recycle / Copy** next to Repeat. **In the file:** part of the phrase, `…, keep copies`.
    6. **Undo** (5 s) removes the copy (and its subtask copies) and reopens the original.
    7. **Clutter:** completed originals are hidden while *Show done* is off; the archive feature can tidy them later.

**Q3 — Next date: all three, chosen per task** (Geoff: "How about all 3 options?").

| Editor choice | Phrase | Behavior |
|---|---|---|
| **Skip missed** (default) | *(nothing extra)* | The next date from the schedule that's **after today** (corrected 2026-10-20: "today or later" would make an overdue daily task due today again) |
| **Catch up** | `…, catch up` | **Strictly the next** date after the old due date, even if still in the past |
| **From completion** | `…, after done` | Counts from the **day it's checked off** (e.g. `every 3 days, after done`) |

**Details** (all per Claude's recommendations, confirmed by Geoff): resets apply in both modes; `series:` and `repeat:` move as above; Undo; clutter handled by Show done and the later archive.

**Grammar (initial set):** `daily` · `weekdays` · `every N days` · `weekly` (on the due date's weekday) · `weekly on mon, thu` · `every N weeks [on …]` · `monthly` (on the due date's day) · `monthly on day N` · `monthly on last day` · `every N months` · `yearly`. Optional suffixes, comma-separated, in any order: `keep copies` · `catch up` · `after done` (`catch up` and `after done` are mutually exclusive). Unknown phrases → ⚠, kept untouched, no roll-forward.

**Data contract → format 3:** new keys `repeat` (after `due`) and `series` (after `repeat`). Older app versions see them as ⚠ unknown keys and keep them.

**Status:** **Built 2026-10-20 (build 2026-10-20a).** Awaiting Geoff's check.
- **Tests:** a `recurring` group: 14 date-engine cases (overdue skip/catch-up/after-done, weekdays, multi-day weekly, fortnights, the 31st across short months, last day, leap years), parser rejects, Recycle and Copy flows (including subtask copies and Undo), editor presets, untouched phrases preserved, unknown phrases.
- **Demo data** has two examples: *Collect rent* (Rental, Recycle) and *Weekly review* (School, Copy).

---

## R2-2 — Today view (rework "By due date")

**Reported** (Geoff, 2026-10-20): "lets modify the existing by due date view to show today but also older tasks with quick "Today" "Tomorrow" buttons."

**Problem (restated):**
- The current *By due date* view lists all dated tasks grouped as Overdue / Today / Next 7 days / Later, with no quick way to reschedule.
- Geoff wants a daily-driver view centred on **today**, which also surfaces **overdue** tasks, with one-tap **Today** and **Tomorrow** buttons to reschedule them.

### Q1 — What the view shows
- **A — Today only:** Overdue + Today. Future tasks don't appear at all.
    - **Pros:** focused.
    - **Cons:** you can't see tomorrow's load without another view.
- **B — Today first, upcoming below:**
    - Sections: **Overdue**, **Today**, then a collapsed **Upcoming (next 7 days)**, plus **Later** (collapsed by default, tap to expand).
    - **Pros:** one view does it all.
    - **Cons:** longer list.
- **C — Two views:** a new **Today** view (A) plus the existing **By due date** kept as is.
    - **Pros:** both.
    - **Cons:** one more entry in the list picker.

**Recommendation:** **B**, renamed **"Today"** in the list picker (it replaces "By due date").

### Q2 — The quick buttons
- **Overdue rows:** **Today** and **Tomorrow**.
- **Today rows:** **Tomorrow** only (moving it to today is pointless).
- **Upcoming/Later rows:** **Today** (pull a task forward).
- **After a tap:** the row moves to its new section, with a 5 s **Undo**.
- **Layout on a phone:**
    - **A — Two small buttons** ("Today" "Tmrw") in the pinned right column, before ⋯.
        - **Pros:** one tap.
        - **Cons:** takes title width (titles still scroll sideways).
    - **B — One calendar button** that opens a tiny menu: Today / Tomorrow / Next week / Pick a date…
        - **Pros:** compact; more choices.
        - **Cons:** two taps.
    - **C — A, plus "Pick a date…" in the ⋯ menu.**

**Recommendation:** **C**: Today and Tomorrow are one tap, as asked; anything else goes through ⋯ → "Change due date…".

### Q3 — Other details
1. **Show the list name** on each row (tasks come from all lists), as a small muted label after the title (rec.).
2. **Recurring tasks** (R2-1) show ↻; rescheduling one moves only this occurrence.
3. **Tasks without a due date** don't appear here. A future "My Day" (adding undated tasks to today) would be a separate item.
4. **Should it be the default view on the phone** when the app opens? (Rec.: no; keep the last-used view, so if you leave it on Today, it opens on Today.)

### Decisions (Geoff, 2026-10-20)
- **Q1 — Layout, top to bottom** (Geoff: "start out with Upcoming at the top but (collapsed by default), below it today (no collapse symbol), below that Overdue (collapsed by default)"):
    1. **Upcoming:** collapsed by default; tap the header to expand.
    2. **Today:** always open, with no collapse control.
    3. **Overdue:** collapsed by default; tap to expand.
    - Collapsed headers show a count, e.g. "Overdue · 4".
    - Renamed **"Today"** in the list picker; it replaces "By due date".
- **Q2 — Buttons: yes to all.** Overdue rows: **Today · Tomorrow**. Today rows: **Tomorrow**. Upcoming rows: **Today**. Plus ⋯ → **Change due date…**, and a 5 s Undo after a tap.
- **Q3:**
    1. **No** list name on the rows.
    2. **Yes:** ↻ on recurring tasks; the buttons move only this occurrence.
    3. **Yes:** tasks without a due date are not shown.
    4. **Yes:** the app opens in the last-used view.
- **Confirmed 2026-10-20:**
    - **Upcoming covers the next 7 days** (Geoff: "lets start with the next 7 days, but maybe allow user to view tasks beyond that somehow"). The last row of Upcoming reads **"+ N later (after <date>)"**; tapping it adds the rest to the section (proposed option A; alternatives: a separate Later section, or a days setting).
    - Upcoming and Overdue start collapsed each time the app starts and keep their state within a session. Geoff may change this later.

- **Time runs upward** (Geoff, 2026-10-20: "scrolling up is the future and down is the past … as I scroll up to the top the very top item is a later button"):
    - **Upcoming:** sorted **furthest first** (the farthest date at the top, tomorrow just above Today). Its **very top row is "+ N later"**; tapping it reveals the later tasks above it.
    - **Overdue:** sorted **most recent first** (yesterday just below Today, the oldest at the bottom).
    - Expanding Upcoming keeps **Today** where it was on screen (no jump).

**Status:** **Built 2026-10-20 (build 2026-10-20b).** Awaiting Geoff's check.
- **Implementation notes:**
    - The Upcoming and Overdue headers sit at the top of their sections. "+ N later (after <date>)" is the first row under the Upcoming header; tapping it replaces itself with the later tasks.
    - Expanding or revealing keeps the Today header at the same screen position (the app adjusts the scroll).
    - Buttons read **Today** and **Tmrw** to save width. ⋯ → **Change due date…** offers Today, Tomorrow, In a week, or any date.
    - An open editor for the same task picks up the new date.
    - Internally the view key is still `due`, so a phone left on "By due date" opens on Today.
- **Tests:** a `today` group (30 checks): section order and counts, default collapse, sort orders, Today staying put, "+ N later", each button with Undo, the dialog, a recurring task, fit at 175 %, collapse reset after a restart.

**Acceptance criteria:**
- Overdue and Today sections are correct by local date.
- The buttons change `due:` (conditional save) with Undo.
- Rows move between sections immediately.
- Works on phone (the buttons fit at 125–175 % text) and PC.

---

## R2-3 — Quick-add in the Today view

**Reported** (Geoff, 2026-10-20, asking to add Claude's suggestion from the R2-2 build: "add the quick-add option to the spec").

**Problem (restated):**
- In the Today view, the quick-add box still says "Add a task to <last list>…", but it adds the task to the **first** list in `_todo.json`, so the placeholder can be wrong.
- The new task gets **no due date**. Undated tasks are hidden in the Today view, so the task you just typed vanishes from the screen.

### Options
- **A — Due today, first list:** quick-add in Today creates the task with `due: today` in the first list; the placeholder says so ("Add to Inbox, due today…").
    - **Pros:** smallest change; the task appears right under Today.
    - **Cons:** "first list" is an accident of list order.
- **B — Due today, a chosen default list:** like A, but Settings gets **"Today view adds to: <list>"** (defaults to the first list); the placeholder names it.
    - **Pros:** predictable; you pick an inbox-style list once.
    - **Cons:** one more setting.
- **C — Ask each time:** after typing, a small sheet asks which list (last one used is preselected); due today.
    - **Pros:** tasks land in the right list at once.
    - **Cons:** an extra tap on every add, which works against "quick".
- **D — Section-aware:** the date depends on what's on screen, e.g. typing `tmrw` or `fri` at the end of the title sets that date (a tiny date parser); plain text = today. Combine with A or B for the list.
    - **Pros:** fast scheduling without the date picker.
    - **Cons:** more code; parsing surprises (a title that really ends in "fri").

**Recommendation:** **B** now; D could be a later add-on (it would also help quick-add in normal lists).

### Decision (Geoff, 2026-10-20)
- **B, with two tappable chips** (Geoff: "go with B but clicking on the list name (at the right of the input line) lets you chose a different list / same thing with the due date box, by default is shows today, but clicking on it allows you to pick different dates or even choose no date").
- **Layout:** `[ Add a task…            ] [Inbox ▾] [Today ▾]`
    - **List chip:** shows the target list; tap → the list sheet (same as the list picker) → pick another list.
    - **Date chip:** shows **Today** by default; tap → Today · Tomorrow · In a week · Pick a date… · **No date**.

### Details to confirm (with recommendations)
1. **What the list chip starts on.**
    - **A — A Settings default** ("Today view adds to: <list>"), as in B; the chip starts there each time you open Today.
    - **B — Remember the last choice** (per device); no new setting.
    - **Rec.: B.** The chip already shows the list, so a separate setting adds little; the first time it starts on the first list.
2. **How long a changed date sticks.**
    - **A — Resets to Today after each add.**
    - **B — Sticks while you stay in the Today view** (add several tasks for Friday in a row); back to Today when you leave the view or restart.
    - **Rec.: B.** The chip always shows the date, so a sticky date is visible, not hidden.
3. **Where the new task shows up.** Due today → under Today right away. Tomorrow or later → in Upcoming, which may be collapsed; no date → not in this view at all.
    - **Rec.:** in those two cases a toast says where it went ("Added to Inbox — Fri 23 Oct, in Upcoming" / "Added to Inbox, no date").
4. **Phone width at 125–175 % text.** Labels stay short (Today, Tmrw, Fri 23, No date); a long list name is cut with "…" (max about 8 characters at 175 %) so the input keeps most of the line.
5. **Normal list views (not part of this decision).** The same chips could work there (list chip = the list on screen, date chip = **No date** by default). **Rec.:** later, as its own item, if you want it.

**Details confirmed** (Geoff, 2026-10-20: "recs are fine, approve R2-3"): 1-B, 2-B, 3 toast, 4 short labels.

**Status:** **Built 2026-10-20 (build 2026-10-20c).** Awaiting Geoff's check.
- **Implementation notes:** the chips show only in the Today view; normal list views are unchanged (that list, no date). The list choice is stored per device (`todo.qaList`). The chips drop the ▾ and cap their font at 17 px, so at 175 % text the input keeps over half the line.
- **Tests:** 12 more checks in the `today` group (defaults, both chips, sticky date, No date, Pick a date, toasts, fit at 175 %, reset on leaving the view, list remembered).

---

## R2-4 — Default task folder next to the app

**Reported** (Geoff, 2026-10-21, while renaming the OneDrive folder to `HTML-ToDo-App`): "For the App: B, but I want the default folder to be a sibling of the App folder that the HTML app index page is in".

**Problem (restated):**
- **Done (2026-10-21, build 2026-10-21a):** the OneDrive default is now `HTML-ToDo-App`.
- **Still open:** when the app runs **from disk** (the work zips), the task folder should by default sit next to the app. The assumed layout (to confirm) is a sibling of the **build folder**, because a sibling of `app\` would be inside each build and left behind by the next one:
  ```
  <root>    html-todo-app-2026-10-21app\index.html
    HTML-ToDo-App\              ← default task folder
  ```
- **Browser limit (verified):** the File System Access API lets a page open a folder only after you pick it in the browser's dialog. A page can't open a folder by path, can't check that one exists, and can't make the dialog start in a given path. (`startIn` only takes Desktop, Documents and similar, or a folder you already picked.)
- **OneDrive mode (phone, PC browser):** the app comes from GitHub Pages, so it has no folder of its own. The default stays `HTML-ToDo-App` at the top of OneDrive.

### Options
- **A — Show the path to paste:** when a local folder is needed, the app works out `<root>\HTML-ToDo-App` from its own address and shows it with a **Copy** button. Paste it into the dialog's address bar, then pick it (or create it with *New folder* the first time). New builds already remember the folder, so this happens once per PC or browser.
    - **Pros:** small; works within the browser's rules.
    - **Cons:** still one paste and one click.
- **B — A, plus a check:** after you pick, if the folder isn't named `HTML-ToDo-App` or doesn't look like a task folder (no `_todo.json`, no `.md` files), the app asks "Use this folder anyway?"
    - **Pros:** catches picking the build folder or `app\` by mistake.
    - **Cons:** a bit more code; an extra prompt for a new empty folder.
- **C — Leave it as is:** pick the folder once; new builds remember it.
    - **Pros:** no work.
    - **Cons:** no guidance the first time.

**Recommendation:** **B**. The sideways check guards the top priority (the `.md` files) cheaply.

### Decision (Geoff, 2026-10-21)
- "yes next to the build folder, approve B for R2-4 but lets change the default folder to just data not HTML-ToDo-App".
- **Default local folder:** **`<root>\data`**. The OneDrive default stays `HTML-ToDo-App` (that's the folder renamed on 2026-10-21).

**Status:** **Built 2026-10-21 (build 2026-10-21b).** Awaiting Geoff's check.
- **Implementation notes:**
    - Opening a local folder (start screen or Settings) first shows **Choose your task folder** with the suggested path and **Copy path**. The path is worked out from the page's own `file:` address: drop `index.html`, `app` and the build folder, then add `data`. Served over http (Pages, tests), it shows a generic hint instead.
    - **The check after picking:** it asks first if the folder looks like the app's own (`index.html`, `app` or `vendor` at its top), or if it has no task files and isn't named `data`. A folder that already has task files opens directly, whatever its name, so an existing work folder keeps working.
    - Already-remembered folders are untouched; the guide appears only when picking.
- **Tests:** a `localfolder` group (15 checks): path cases (spaces, a network share, http), each check outcome, Choose another / Use it anyway, and the guide opened from disk.

---

## R2-5 — A folder per list (file-explorer model)

**Reported** (Geoff, 2026-10-21):
- "I think each list should have its own folder, what do you think?"
- Then: "please capture context that i want to explore a model that resembles the file explorer where user move files from one folder to another instead of changing the list name in frontmatter. Maybe leveraging the underlying os file management system?"

**Problem (restated):**
- **Today:** all task files sit flat in one folder, and `list:` in the frontmatter decides the list. Moving a task to another list edits that line.
- **What Geoff wants to explore:** lists that behave like **folders in a file explorer**. A list *is* a folder, and moving a task means moving its file, whether in the app, in Windows Explorer, or in the OneDrive app. The OS or cloud file system does the work, and the app follows.
- **Related decisions:** S-11 A (`parent:` is the truth for subtasks, not folders). S-11 plans a future "checklist line → task in a folder" feature, and S-6 plans multiple locations.

### Why it's attractive
- What you see in Explorer and the OneDrive phone app matches the app, list by list.
- **Per-list sharing:** OneDrive shares folders, so one list (e.g. Groceries) could be shared without the rest.
- Claude can be pointed at one list's folder.
- Renaming a list = renaming one folder, instead of rewriting `list:` in every file.
- It's a step toward S-6, where a list folder could live in another location.

### "Leveraging the OS file management" — what that can mean
1. **Moves made outside the app (works in every mode):** you drag a file to another folder in Explorer or the OneDrive app, and the app picks it up on its next check.
    - The key is **matching by `id`**: a file that vanishes from `Home\` and appears in `Rental\` with the same `id` counts as a **move**, not a delete plus a new task. Its subtasks follow their `parent:`.
2. **Moves made in the app, using the file system's own move:**
    - **OneDrive:** Microsoft Graph moves a file in one server-side operation (PATCH `parentReference`). That's the same move as in the OneDrive app, keeps the file's history, and is safe.
    - **Local folder:** Chrome's file-system access has a `move()` method. It is documented for the browser's private sandbox; whether it works on real folders the user picked is **to be verified (rule 8)**.
        - If it does, it's a true OS move.
        - If not, the move is copy, check, then delete. The deleted copy goes to `.trash`, so an interruption leaves a duplicate (which the app detects by `id`), never a loss.
3. **A web page can't drive Explorer itself.** It can't open Explorer at a folder or run OS commands. A desktop wrapper (a small local helper or packaged app) could, but that's a much bigger step and adds lock-in. It's only listed so it's on the map.

### Options (from the first discussion)
- **A — Stay flat** (today): no work and no move risk, but no folder browsing or sharing.
- **B — The folder is the truth.**
    - `list:` stays in each file as a readable copy, and the app fixes it when it disagrees with the folder.
    - Moving a task in the app moves the file, and its subtasks go along.
    - Files in the top folder show in **Inbox**. Folders below a list folder are task folders (the future S-11 feature).
- **C — Folders only for organizing, `list:` stays the truth:** new tasks go into their list's folder, but files are accepted anywhere and never moved. Least risk, but Explorer slowly drifts out of step with the app.
- **D — B, but only for the lists you choose** (e.g. one shared list); other lists stay flat. Most flexible, but two layouts to understand.

**Leaning (Claude):** **B.** It's the only option where Explorer and OneDrive always show the truth, and it fits Geoff's file-explorer idea. **Decide before the Phase 6 migration**, while real data is small.

### Things to explore before deciding
- **Verify** `move()` on folders the user picked (Chrome and Edge on Windows), or settle on copy, check, delete.
- **Detecting moves:** match by `id` across folders. What happens with two files that share an `id` (a copy made in Explorer)? The app should flag it, not guess.
- **Sync cost:** OneDrive's change feed already covers subfolders. Local folders and the work-OneDrive listing fallback would scan every list folder on each check, on top of the slowdown already seen on the work PC, so checking less often or smarter may be needed.
- **List order and empty lists:** order stays in `_todo.json`. A folder without an entry there shows up as a new list at the end.
- **Folder names** follow the S-11 slug rules, with Windows-safe names. The display name is kept in `_todo.json`, so "Home & Garden" can live in `home-garden\`.
- **A possible UI:** an explorer-like list picker (folders, with counts), and long-press move → "Move to list…" as a real file move.
- **Data format 4:** older builds must refuse the folder layout, not misread it.
- **Migration:** a one-time move of the existing files (OneDrive `HTML-ToDo-App`, work `data\`), done by hand with Geoff's approval (rule 10).

### Storage discussion (2026-10-31)
- **Asked** (Geoff): "Is there any DB focused approach (instead of individual files) that fits my requirements? I want to discuss the idea of organizing the files into folders (replacing lists with folders)".
- **Database options considered:**
    - **One SQLite or JSON file in OneDrive:** whole-file sync conflicts between devices; loses OneDrive's per-task versions and recycle bin.
    - **Free cloud databases** (Firestore, Supabase, D1, Turso, PocketBase): a second system, lock-in, and not usable on the work PC.
    - **Microsoft services:** ruled out in R2-7 G.
    - **Per-device change logs:** complex, and Claude can't edit them.
- **Conclusion:** files stay the source of truth. Each device already has a database copy (R2-7 A), and more speed comes from R2-7 B, D and C.

### Cons of B (reviewed 2026-10-31)
**Data safety:**
1. **One delete removes a whole list:** an accidental delete of a folder in Explorer or the OneDrive app takes a whole list, due-dated tasks included. The app must notice "a folder disappeared" (an extension of R2-8 Deleted B).
2. **A move looks like delete + new:**
    - **OneDrive:** a moved item keeps its id, so the change feed shows a clean move.
    - **Local folder:** no item ids, so the app must match by task `id`. An interrupted move can leave a duplicate.
3. **Subtasks can be left behind** when the parent is dragged in Explorer.
4. **Folder vs. `list:` disagreement:** an edit to `list:` without a move means the app rewrites the file on its own.
5. **Demote/promote links (`[↗](file.md)`) are paths:** a move breaks them. Links must resolve by `id` or be rewritten.
6. **Sharing a folder lets others delete tasks.** Folders shared *with* Geoff come through a different Graph path (remote items); how the change feed handles them is unverified.

**Effort:**

7. **The biggest change since the MVP:**
    - all three stores
    - sync, and the device copy (keyed by path)
    - the move UI and Needs attention
    - the links
    - tests
8. **Renaming a list on a local folder** is copy + delete, since Chrome can't rename a folder.
9. **The work PC's background check** has to scan every folder.

**Constraints:**

10. **Folder-name rules:** Windows-safe names, case-insensitive. Display names mapped via `_todo.json`.
11. **Which subfolders are lists?** Archive folders (R2-7 D) and task folders (S-11) also nest.
12. **Claude, scripts and imports move files** instead of editing a line.

**Compatibility:**

13. **Data format 4:** older builds must refuse the layout; the work pack and the work PC migrate separately.
    - **Note (2026-11-07):** no build checks `format` today. The app writes `"format": 3` to `_todo.json` but never reads it back. So the refusal has to be built, and an old build (e.g. the work PC's) won't refuse anything; it only keeps unknown keys (⚠). The check must ship, and be installed everywhere (the phone, the PC, the work pack), **before** any folder is migrated.
14. **One-time migration** of the real folder (rule 10).

### Why B, and the benefit for AI management (Geoff, 2026-10-31)
- **Geoff's reasons:**
    - "I do expect to occasionally manage the files directly using windows file explorer and other apps (vs code, notepad++, etc)".
    - More importantly, "I will have you (Claude) manage these tasks for me".
- **The benefit for AI, assessed honestly:**
    - **Claude Code (which can search):** small. `list: Home` is as easy to find as `Home\`.
    - **AIs and tools that only see paths** (OneDrive connectors, Copilot in OneDrive, editor file trees): real. The structure is visible without opening files.
    - **The biggest gain is least privilege:** one folder can be given to an AI, tool or person without exposing the rest.
- **Cost for AI:** more steps per move (subtasks, `list:`, links), so more chances to leave something half done. Needs attention and repairs in the app mitigate this.
- **What matters more than folders for safe AI management:**
    - the file contract and CLAUDE.md rules
    - Needs attention (R2-8 Hidden A)
    - trash and deleted-elsewhere notices (R2-8 Deleted A/B)
    - a change history: see the git-history note in R2-8 Long-term

### Decision (Geoff, 2026-10-31): "yes record B as decided"
**B: the folder is the list.** Geoff's additions follow, with Claude's notes. All of them are to be settled in the implementation discussion.
1. **Rename "List" to "Folder"** everywhere people read it, "to literally match what it is":
    - UI: the folder picker, "Add a task to *Home*…", the editor field, Needs attention messages.
    - Docs, CLAUDE.md and the task-file contract.
    - Internal code names can follow gradually.
    - **Open:** what the top-level folder (today's Inbox) is called.
2. **Subtasks must be in the same folder as their parent** ("seriously consider a rule"). **Claude: recommended, yes.**
    - It is already today's contract ("a subtask's `list` always matches its parent's"); folders just make it physical.
    - **Moving a parent** in the app moves its whole subtree.
    - **Moving a subtask alone** to another folder un-nests it (it becomes a top-level task there), after asking.
    - **A parent dragged in Explorer without its subtasks:** Needs attention flags it, with one tap to "Move N subtasks to *Folder*". Whether the app may do this automatically is to be decided.
    - Subtasks are **not** nested as subfolders of their parent. `parent:` stays the truth for nesting (S-11 A).
3. **Consider removing `list:` (or a `folder:` key) from the frontmatter.** **Claude: leaning remove.**
    - **Pro:** one source of truth. No mismatch case (con 4), no rewrites by the app, and moves are a pure file move (con 12 shrinks).
    - **Cost:**
        - A file read on its own (or sitting in the trash) doesn't say which folder it came from. So the trash index and Needs attention record the original folder.
        - Tools that read a single file without its path lose that information.
        - The import writes the path, not a field.
    - **Alternative:** keep the line as a read-only hint the app keeps in step. That still brings back con 4.
4. **A UI for moving a task to another folder:**
    - ⋯ → **Move to folder…** opens a picker with counts, plus "New folder…".
    - Long-press drag onto a folder in the picker.
    - Undo; subtasks travel with the parent; the open editor follows the file.
5. **Open questions for the implementation discussion:**
    - **Nested folders:** one level of folders, or a tree (e.g. `Home\Garden`)? And how they coexist with archive and task folders (con 11).
    - **Display names vs. folder names**, and their order (`_todo.json`).
    - **Links by `id`:** demote/promote (con 5).
    - **Detecting a deleted folder** and offering Restore (con 1).
    - **Shared folders** (con 6).
    - **The work PC:** speed (con 9), and its own migration (con 13).
    - **Format 4 refusal** in older builds and the work pack. It doesn't exist yet (see con 13); it's needed first, or a separate early build adds just the check.
    - **Migrating the real folder**, after removing the 500 bulk-test tasks.

**Order:**
1. The R2-8 safeguards (Deleted A/B, Hidden A).
2. A prototype on the `HTML-ToDo-App-Test` copy folder.
3. Migrate the real folder.
4. Then the SP / To Do import, straight into folders.

**Gate (Geoff): "make sure that when I am ready to implement this change, we fully discuss how to make it happen but not break anything and still comply with other requirements."** Before any build:
- a full implementation discussion covering every item above, the cons list and the R2-8 decisions
- a compatibility check against the task-file contract, R2-7 A (device copy), R2-6, the work-PC setup and the network lock
- a migration plan Geoff approves

### Implementation discussion (started 2026-11-08)
**Decisions so far (Geoff, 2026-11-08):**
1. **Nesting:** "lets start out with one level deep only allowed. But where possible, structure the design and implementation in a way that supports a tree structure later."
    - Every folder is identified by its path relative to the task folder, using `/`: `Real Todo` now, `Home/Garden` later.
    - "One level" is a single validation rule that can be lifted later, without moving files or changing the format.
2. **"List" is replaced by "Folder" completely:** "i want to comletely remove the idea of a list and replace it with the idea of a folder."
    - **UI:** the folder picker, Move to folder…, "Add a task to *Folder*…".
    - **`_todo.json`:** `"lists"` becomes `"folders"`, which holds only the display order, as paths (tree-ready).
3. **No folder field in the frontmatter; the path is the truth** (Geoff agreed with Claude's recommendation). `list:` is removed from every file in the migration.
    - **Reasons:**
        - Every tool that sees a file sees its path: Explorer, editors, Graph's `parentReference`, Claude.
        - With a tree, a field would make renaming or moving a folder rewrite every file beneath it. Without one it rewrites nothing.
        - No disagreement between a field and the location.
    - **Accepted cost:** a file seen completely on its own, without its location, doesn't say where it belongs. The trash note already records the original path.
4. **Same-folder rule, enforced:** "I will have it enforce the parent/child/grandchild all being in the same folder rule." A whole family sits in the exact same folder.
    - Moving a task in the app moves its subtree. Making a task a subtask of one in another folder moves it (with its subtree) into that folder.
    - Subtasks are still not subfolders; `parent:` stays the truth for nesting.
5. **Moving a subtask alone to another folder:** "give me the option to cancel or make it a top level task in the new folder."
6. **Subtasks left behind by a move outside the app** (e.g. a parent dragged in Explorer without them): **ask, one tap**.
    - They still show under the parent, marked ⚠, with "Move N subtasks to *Folder*".
    - Nothing moves until Geoff taps.
7. **No Home or Inbox folder.** Files directly in the task folder belong to the top folder, shown as **"/ (root)"**.
    - **Why `/`:** OneDrive, the phone, web paths and the app's own folder paths all use it. Windows also accepts `/`.
8. **Folder-name rules** (Geoff asked about leading slashes; a slash is refused anywhere, since it means "subfolder"):
    - no `/ \ : * ? " < > |`
    - not starting with `.` or `_` (hidden/system, e.g. `.trash`)
    - no trailing space or dot
    - no Windows reserved names (`CON`, `NUL`, `COM1`, …)
    - unique ignoring case

    So no folder can ever be named "/ (root)".

9. **New tasks outside a folder** (e.g. quick-add in the Today view) go to **/ (root)**. The folder chip still picks another and remembers the last pick.
10. **Managing folders in the app:** create, rename, and delete **only when empty**, so one tap can never wipe out a folder of tasks.
11. **A whole folder disappears** (deleted or renamed outside the app): **warn and explain**.
    - **Deleted:** "The folder *X* (N tasks, M with due dates) is gone", with the task names and where to restore (OneDrive's recycle bin).
    - **Renamed:** shows up as the same task ids in a new folder, so the app says "renamed to …" instead.
12. **The data-format check ships first, as its own small build** ("Small build now"). See *Step 0* below.
13. **Migration:** "Claude runs a script, you convert my OneDrive folder from this PC. I don't have any .md files on my work pc to perserve."
    - So there's **no in-app converter**.
    - Claude converts `HTML-ToDo-App` with a script after a fresh backup, once the folder build is on the phone and the PC.
14. **An unconverted (flat, format ≤ 3) folder in the folder build:** read-only until converted. Only one layout to support.
15. **Folders shared with Geoff by others:** not in this build. Sharing one of his own folders works anyway, since it's a OneDrive folder.
16. **The work PC:** "I will delete everything from my work version of the app, nothing was important or used. but after this build I will start using at my work for real."
    - No work-PC migration; it starts empty, in the folder layout.
    - The work pack with the folder build is what goes there.

### Step 0 — the data-format check (approved 2026-11-08, built as 2026-11-08a)
**What:** `_todo.json`'s `format` is now read on load and whenever the file changes.
- **If it's newer than the build knows** (`DATA_FORMAT`, still 3), the folder opens **read-only**: every write, create and delete is refused. That covers task files, the trash and `_todo.json` itself.
- **On screen:** a red bar ("Read-only: this folder was updated by a newer version of HTML-ToDo-App (data format 4; this one knows 3). Reload to update the app.") with **Reload**. Quick-add is off.
- **A refused change** (e.g. a check-off) is undone on screen, with a toast.
- **Diagnostics:** the log records it.
- **Format 2 and 3 folders** are unaffected.

**Why first:** every device must run this before any folder is converted. Otherwise an older build would treat the folder layout as an empty or partial folder and could write into it.

**Tests:** group `fmtcheck` (10 checks, fake OneDrive):
- a format-2 folder is normal
- a format-4 change arriving mid-session turns the app read-only on the next check
- a check-off and a delete are refused, and the file and the trash are untouched
- `_todo.json` is never rewritten
- a cold start on a format-4 folder shows the bar, tasks still visible
- no writes without If-Match; no page errors

Full suite: 637 checks pass.

**Status:** Built; pushed to `main` as 2026-11-08a.

### The folder build — as built (approved 2026-11-08: "yes, start the folder build"; build 2026-11-08b, data format 4, branch `r2-5-folders`)
**Before building:**
- **Microsoft's docs:**
    - **A move** is `PATCH` of `parentReference` (+ `name`) and honours `If-Match` (412).
    - **The change feed** has no paths ("track items by id").
    - **A folder rename** doesn't resend the folder's files.
    - **Not stated in the docs:** a move onto a taken name, and whether a deleted folder's files are tombstoned. Both are handled defensively (unique name and retry; everything under a deleted folder is dropped).
- **Chrome's `move()` on picked folders:** feature-detected at run time, and checked after it runs. Otherwise copy, then delete; an interruption leaves a duplicate (flagged ⚠), never a loss.

**Storage (all three stores and the device copy):**
- **Listing:** covers one level of folders.
- **New operations:** `move()`, `folders()`, `createFolder()`, `renameFolder()`, `removeFolder()` (empty only, and only when there are no files at all).
- **OneDrive:**
    - a move is one `PATCH`, so the item, and its history, stays
    - folders are tracked by item id; their ids are saved with the device copy's bookmark (device-copy format 2)
    - a renamed folder's files are re-pathed by the app
    - a deleted folder takes everything under it
- **Local folder:** checks folder names ignoring case.
- **The read-only guard** (Step 0) covers the new operations.

**App:**
- **`t.list` is the folder path**, from where the file is; `list:` is no longer read or written. `saveTask` moves the file when the folder changed (`moveFile`: same name when free, otherwise the unique-name rule).
- **"List" → "Folder" in the UI:**
    - the Folders picker: "/ (root)" first, counts, ✎ Rename / Delete (empty only), "＋ New folder", "Today (all folders)"
    - ⋯ → **Move to folder…**
    - the editor's **Folder** field with "＋ New folder…"
    - "Add a task to *Folder*…"
    - the quick-add folder chip, which starts at / (root)
- **The decisions, as built:**
    - **4:** Move to folder… moves the whole family.
    - **5:** a subtask alone: "Move a subtask?", with **Cancel / Make it a top-level task in *Folder***.
    - **6:** a family split outside the app: **⚠ N** on the parent opens "Subtasks in another folder", with **Move them to *Folder*** (nothing moves without a tap).
    - **8:** the folder-name rules, checked when a folder is created or renamed.
    - **11:** a folder gone outside the app:
        - **Deleted:** "The folder *X* is gone", listing its tasks (due-dated first) and where to restore.
        - **Renamed:** "renamed to …", and `_todo.json` follows.
    - **14:** a flat format ≤ 3 folder opens read-only: "still uses the old list layout … has to be converted to folders first (Claude does this)". No Reload button.
- **Folder changes made elsewhere** (made, renamed, deleted) show on the next check, even when no task changed.
- **`_todo.json`:** `{"format": 4, "folders": [...]}`, the order only; `lists` is dropped.
- **Demote (keep):** the archived file moves into the target's folder; the link is its name there. **Promote** finds it in the target's folder, then anywhere, then by `demoted_into`.
- **Restore** from Recently deleted puts a task back into its folder and on screen.
- **Recurring copies** are named `<slug>-YYYYMMDD.md` in the task's folder.
- **Demo data** is in folders (Home, Rental, School; Inbox tasks at the root).

**Migration tool:** `tools/migrate_to_folders.py`.
- **Preview** by default.
- **`--apply`:**
    - zips the folder into `private/backups/` first
    - moves each file into its list's folder (Inbox → root; a family follows its top parent) with a real move
    - removes only the `list:` line, byte for byte otherwise (CRLF kept)
    - re-checks each file before touching it
    - writes `_todo.json` last, so a re-run continues
- **Tried on a copy of the real data (42 tasks):**
    - every file landed in the right folder, identical except for the `list:` line
    - a re-run says "already uses the folder layout"
    - edge cases checked: CRLF, unknown keys, a child whose `list:` disagreed with its parent's

**Tools:** `feedback_check.py` reads `<task folder>/Feedback/` (or `list: Feedback` in an old flat folder).

**Tests:**
- **The shared store suite:** +17 checks per store: folder paths listed, depth limit, `folders()`, move keeps text, a stale move and a taken name refused, create/rename/remove folder, case-insensitive names.
- **New group `r25`** (43 checks: demo, plus fake OneDrive with moves, strays, folders made/renamed/deleted elsewhere, and a restart from the device copy).
- **`fmtcheck`:** format 5 and old-layout folders.
- **Old flat fixtures:** `fake_graph.py` converts them (`to_v4`).
- **Full suite:** **725 checks pass**.

**Real bugs found by the tests and fixed:**
- A restored task inside a folder didn't reappear until a refresh.
- A recurring "keep copies" copy lost its dated name inside a folder.
- Folder changes alone (no task changed) didn't refresh the picker.
- The local folder treated "Empty" and "empty" as different.
- The chosen folder was reset to "/ (root)" before the folder list had loaded.

**Next:**
1. Convert the `HTML-ToDo-App-Test` copy folder with the tool.
2. Geoff tests at `localhost:8000`.
3. With his OK: back up and convert the real folder.
4. Merge, then a phone check.

**Follow-up (Geoff's test, 2026-11-08):** after dragging a parent in Explorer, its subtasks looked moved (they show under the parent) though their files hadn't moved; ⚠ 4 on the parent moved them. Geoff: "add the per-row marker". **Built (2026-11-08c):** each subtask row whose file is in another folder than its parent's shows "⚠ in *Folder*".

**Bug found in Geoff's test (2026-11-08), fixed in 2026-11-08d:** a second, stale T1/T2/T3 "in / (root)" with `list: "Test List"`. OneDrive and Explorer were correct (the conversion moved the files); the **device copy** in the browser still held the pre-conversion files. The new build skipped an old-format copy but didn't delete it, so its files came back on the next start (no change feed reports files deleted before the bookmark). Fix: a device copy from another format is deleted, then everything downloads fresh. Without it, every device would have shown all tasks twice after the real conversion. Test added (fails without the fix). Claude first blamed OneDrive sync, wrongly; decision 13 (script conversion) stays.

**Bug found in the work-PC simulation (W6, 2026-11-11), fixed in 2026-11-11a:**
- **What happened:** in a local folder, the parent was dragged alone in Explorer (Home Stuff → Work). The app then showed:
    - "Project A ⚠" with the tip "two files share id"
    - no ⚠ 2 button
    - its subtasks as top-level tasks in Home Stuff
- **Cause:** a local folder (and work OneDrive's listing) reports a move as "new at B" before "gone from A". The new file was taken for a second file with the same id, and the app gave it a temporary id. The deletion then removed the real id, so the subtasks had no parent.
- **Fix:**
    - `applyChanges` handles deletions first.
    - `healTwin` gives the id back to a same-id twin when the other file is confirmed gone.
- **Test:** r25 section C (local folder). It fails without the fix.
- **Not affected:** OneDrive, where a move is one item.

**Status:** Built, being tested by Geoff (all tested steps passed so far).

**Real-folder cleanup (Geoff, 2026-11-08: "you can delete all tasks currently in every list except the "Real Todo", "Feedback", and "Entertainment" lists. When you are done with the migration, I only want those 3 folders"):**
- **Done 2026-11-08, before any migration:**
    - **Backup:** a zip of the whole folder (559 files, verified) in `private/backups/` (local, git-ignored).
    - **Deleted:** 516 files (Home: the 500 bulk-test tasks plus 11 early test tasks; Test List: 5) went to the Windows Recycle Bin and OneDrive's recycle bin.
    - **`_todo.json`:** Inbox, Home and Test List removed from its lists.
- **Remaining:** 42 tasks (Real Todo 33, Feedback 5, Entertainment 4). No family crossed lists.
- **After the migration:** `/ (root)` (empty) plus the folders `Real Todo`, `Feedback`, `Entertainment`.

**Status:** **Built** (2026-11-08b, branch `r2-5-folders`), awaiting Geoff's test on the copy folder; the real folder is converted only with his OK.

---

## R2-6 — Phone still opens in desktop mode (R1-15 not holding)

**Reported** (Geoff, 2026-10-21, Feedback list → *Android Phone*): "Every time I start the app it defaults in "Desktop" mode / Still happening". In the review he added:
- "When I leave the HTA app open on my phone over night, it will open up in desktop mode again"
- "after i close the app from the android app tray (completely close it), when I open it again, it goes into phone mode … It stays that way for (i think) the whole day, but the next day it goes back to desktop mode"
- To show it, he forced Desktop site on in a Chrome tab: the app showed the PC layout (version in the header, nothing scaled).

**Problem (restated):**
- R1-15's phone check (phone label, **or** touch-only plus a short screen side ≤ 600 px) runs once, at load.
- In Chrome's current Desktop-site mode it decides **PC** even on a fresh load, so the page isn't scaled.
- The likely cause is that Chrome now reports a wider screen or a precise pointer in that mode. **To be confirmed with real values.**
- The installed app slips back into desktop mode by itself overnight. That's Chrome's behaviour, which a page can't control, and the app has to cope with it.

**Plan (Geoff, 2026-10-21: "implement step 1 now"):**
1. **Diagnostics (built, build 2026-10-21c):**
    - ⋯ → Settings → **Diagnostics** shows what the browser reports: phone label and UA hints, pointer and hover media queries, touch points, screen, window and viewport sizes, pixel ratio, orientation, installed app or tab, load type and discarded flag.
    - It also shows what the app decided, plus a log of the last 20 loads and returns to the screen. It has a Copy button.
    - **Tests:** a `diag` group (12 checks).
2. **Geoff:** paste the Diagnostics from a Chrome tab with Desktop site on, and one from phone mode.
3. **The fix:** a phone check based on those values, re-run whenever the app comes back to the screen, plus a test that copies the phone's exact values.

**Diagnostics (Geoff, 2026-10-24, installed app on Android, build 2026-10-24b):**
- **Bad start:** the browser label is a Linux desktop (`X11; Linux x86_64`, no "Mobile"), and the page is laid out 979×1972 on a 339×727 screen. That's Chrome's Desktop-site mode. The app decided PC.
- **Good start:** label `Android … Mobile`, 338×682. The app decided phone.
- **Both starts** report `pointer: coarse`, **`any-pointer: fine` = true**, `any-hover` = false and 5 touch points.
- R1-15's touch-only test required "no fine pointer anywhere". This phone always reports one, so the fallback never fired.
- **Log pattern:** each bad load comes in the same minute as a good one (a second window that Chrome opens in desktop mode). The cause is in Chrome's launch handling.
- **Chrome settings checked by Geoff:** Desktop site off, no exception for the site.

**Options for the fix (step 3):**
- **A:** count "touch + nothing can hover" as touch-only as well. A laptop's trackpad or mouse always hovers, so touch laptops stay PCs.
- **B:** A plus a hidden "force phone mode" setting.
- **C:** look for Chrome's cause in its settings (done: nothing found).

**Decision (Geoff, 2026-10-24): "implement A".**
- **Built** (build 2026-10-24c): `TOUCH_ONLY` = coarse pointer and (no fine pointer, **or** touch points > 0 with no hover anywhere). The existing desktop-site zoom then scales the page back to the real screen width (979 / 339 ≈ 2.9).
- **The plan's "re-run when the app returns to the screen"** isn't needed for this case: the bad window is a fresh load, which the check already covers.
- **Tests** (`desktopsite` group, +7 checks):
    - Geoff's exact desktop-mode values → phone, laid out 339 wide.
    - The same phone in a normal start → phone, not scaled.
    - A touch laptop (touch + hovering trackpad), at 1280 and at 1024 wide → still a PC.

**Status:** A built (build 2026-10-24c).

**Follow-up (Geoff, 2026-10-31):** the phone's Task Edit screen was unusable, cut off on the left with no way to scroll (screenshot). He also asked for a way to make the notes box much larger on phone and PC.
- **Cause (reproduced):**
    - With A, a desktop-mode start is scaled about 2.9× to the phone's width.
    - The editor's width was `min(760px, 100vw)`, and Chrome's 100vw is 979 px in that mode. So the editor came out 760 px wide, was scaled to ~2,200 px, and was anchored to the right edge.
    - In a normal start the editor was fine.
- **The real cause of desktop-mode starts (theory):** the automatic sign-in **redirect**.
    - In Geoff's log, each desktop-mode load came within a minute after a good load.
    - Microsoft limits this kind of app's sign-in to about 24 hours, so the app bounced through Microsoft's page once a day. Navigating the whole window away and back is the likely trigger.
- **Discussed:**
    - **Roll back A?** No. It's correct, and it only acts when Chrome is already in desktop mode.
    - **Can the app switch Chrome to mobile mode?** No. A page can't change Chrome's desktop-site mode, and Chrome ignores the page's viewport in that mode. A per-device "force phone layout" setting would only repeat what A does, so it was left optional.
- **Decision (Geoff, 2026-10-31): "do 1 'confirm the theory' … also implement C … also implement 3 (fix edit screen layout)".**
- **Built (build 2026-10-31a):**
    1. **Confirm the theory:**
        - Diagnostics log a line with the phone/PC decision on every return from a redirect sign-in ("back from Microsoft (redirect)").
        - Every sign-in step is logged too: background renewal ok/failed, popup ok/failed (reason), redirect, expired mid-session.
        - The log keeps 40 lines (was 20).
    2. **Sign-in C:** background renewal first, then a popup on a tap, and the redirect only as the last resort.
        - **The automatic redirect is gone.** An expired sign-in shows "Your sign-in expired — tap Sign in to continue".
        - **Finding:** MSAL 5 returns popup and background answers through a **redirect bridge** page, and the app didn't have one. So the hidden-frame renewal inside `acquireTokenSilent` could never have worked. That is the likely reason for the daily redirect.
        - **The bridge:** MSAL's official one (`vendor/msal-redirect-bridge.min.js`, 5.22.0), run by a script at the top of `app/index.html` when the address carries a popup/silent answer. It uses the same redirect URI, so no Azure change.
        - **Fallback rules:** if a popup can't open or can't report back → the redirect, in the same tap. If you close the popup → a hint, and the next tap uses the redirect.
        - **Signed out mid-session:** the tasks stay on screen. The editor shows a "sign-in expired … Sign in" bar, because on a phone it covers the status icon. A popup sign-in keeps unsaved edits in place.
    3. **Editor layout:**
        - On a phone, the editor is exactly the screen's width in every start mode, and it scrolls when the fields and notes don't fit.
        - **⤢ Bigger notes** (end of the notes toolbar): hides the fields, checklist and footer; the Save buttons and the changed-elsewhere banner stay. On a PC it also widens the editor to the full window. ⤡ puts everything back, and opening another task resets it.
- **Tests:** a new `r26` group (39 checks).
    - Sign-in paths: silent ok, popup ok, popup blocked, bridge timeout, popup closed, expired mid-session with an unsaved edit.
    - The bridge, run with MSAL's real bridge script: a popup answer reaches the app window and starts no app; a redirect answer is left to the app.
    - The editor in Geoff's exact desktop-mode and normal starts.
    - ⤢ on phone and PC.
    - The old sign-in tests now expect no automatic redirect.
- **Not testable here:** real Microsoft popups and background renewal on Geoff's phone. Chrome may block the hidden frame's sign-in cookies, in which case the popup does the work.

**Status:** Built (build 2026-10-31a). Awaiting Geoff's check: phone sign-in after a night, the editor, ⤢, and a Diagnostics paste after a few days.

---

## R2-7 — Scale: support many more tasks

**Reported** (Geoff, 2026-10-23):
- Feedback list → *List view*: "Stress test performance with 10k tasks"
- After the results: "any ideas on how to support more tasks? I'm willing to explore other methods for data storage like sqlite or other ideas, but still using ms onedrive as the cloud storage for the tasks and allowing the basic html app to work on phone and pc like it does now. Just consider alternative free sources of data storage in the cloud"
- Then: "i am leaning towards starting with a, b, or c"

**Problem (restated):** the stress test (`docs/stress-test-results.md`, harness `tests/stress.py`) found HTA becomes unacceptably slow at:
- **~200–400 task files on OneDrive** (startup over 4 s): every file is downloaded on every start, 6 at a time.
- **~3,000 on the phone and ~10,000 on the PC once loaded** (actions over 0.5 s): every change redraws the whole list.
- **~1,000 open tasks in a single list** on the phone.
- **~4,000–5,000 in a PC local folder:** slow startup, plus the background check re-reads every file every 5 s.

**Constraints (Geoff):** OneDrive stays the cloud store; the plain HTML app keeps working on phone and PC; free; low lock-in (rule 9); ideally Claude can still edit tasks as `.md` files.

### Options
- **A — A copy on each device + change-only sync.**
    - The app keeps every file, plus OneDrive's change bookmark (delta link), in browser storage (IndexedDB).
    - **Startup:** draw from the copy at once, then ask OneDrive what changed since the bookmark (usually 1–2 requests) and download only those files.
    - **A new device** downloads everything once, in the background.
    - Local folders get the same copy, plus a cheaper background check.
- **B — Redraw only what changed:**
    - a subtask index (by parent) instead of scanning every task per row
    - update only the rows an action touches
    - a virtual list (only the rows on screen) for very long lists
- **C — A snapshot index file in OneDrive** (`_index.json.gz`): every task plus its file version. Any device downloads one file instead of thousands, then fetches only files whose version differs. The `.md` files stay the truth.
- **D — Archive old done tasks** (e.g. `archive/2026/` or a monthly done journal) to keep the live folder small.
- **E — SQLite:** fine as the device copy in A (SQLite in the browser). **Not** as the OneDrive format: whole-file sync, no merging between phone and PC, and Claude can't edit it.
- **F — A free Azure database** (Cosmos DB lifetime free tier, or the Azure SQL free offer) **plus a small backend** for keys and sign-in. Scales far, but it's a second system and a separate Azure subscription; at work it needs IT and can't run with the network lock; tasks leave plain files. **Not recommended.**
- **G — Microsoft 365 / Graph data services:** none works on **both** work and personal accounts.
    - SharePoint / Microsoft Lists and the Excel workbook API: work only.
    - Dataverse: business licences.
    - To Do: works on both, but has a fixed task model and lock-in.
    - **Ruled out.**
- **H — Stopgaps:** more parallel downloads, Graph `$batch` (20 per call). 2–4× faster, still proportional to the file count.

### A vs. B vs. C
They fix **different bottlenecks**, so they're not true alternatives: A and C attack **startup**, B attacks **actions once loaded**.

| | **A — device copy + change-only sync** | **B — partial redraws** | **C — snapshot index in OneDrive** |
|---|---|---|---|
| **Fixes** | Startup on every launch (the ~200–400 limit) | Action speed once loaded (the ~3k phone / ~10k PC limit) | Startup, mainly the first load on a new or cleared device |
| **Startup at 10k tasks** | ~1 s, from the device copy, + 1–2 requests | Unchanged (still downloads everything) | One index download (~1–2 MB at 10k) + checks, every launch |
| **Data format change** | None | None | A new shared file in OneDrive |
| **Works offline** | Yes, opens from the copy | No change | No |
| **Writes** | Unchanged (one file per save) | Unchanged | Every save also updates the index: double the writes, and index conflicts between phone and PC |
| **When Claude or Explorer edits a file** | Picked up by the change feed (as now) | n/a | The index goes stale for that file until fixed up (version check) |
| **Risk** | Sync bugs: stale copy, an expired bookmark (must fall back to a full re-read), browser storage evicted on the phone (ask for persistent storage; rebuild if lost) | Regressions in the list UI (badges, expand, move, Today, demote) | Index drift and write contention; one more thing that can corrupt |
| **Effort** | Medium: store layer, plus tests against the fake OneDrive | Medium–large: rework of the list rendering | Medium, plus ongoing upkeep |
| **Builds toward** | B (indexes) and C (C is basically A's copy published to OneDrive) | — | — |

**Recommendation: A first, then B; C only if needed.**
1. **A fixes the limit you'd hit first, and by far:** ~200–400 files today → effectively unlimited for startup. It also makes every daily launch instant and offline-capable.
2. **A changes nothing about the data:** no new files, no extra writes, no new conflict cases between devices. C adds a shared index that every save must update, which is exactly the kind of contention the files-plus-conditional-writes design avoids.
3. **A is groundwork:** B's indexes live on the same in-memory/device model, and C is A's copy uploaded. C only adds value when **new devices** are common; you have two.
4. **B matters later:** it only bites past ~3k tasks on the phone (or ~1k open in one list). It's still worth doing after A, together with D (archive) to keep lists short.

**Verification for any option:** re-run `tests/stress.py` before and after (the Feedback item "Stress test chosen option" tracks this), plus new sync tests against `fake_graph.py`:
- stale copy
- an expired bookmark (410 → full re-read)
- edits from another device while offline
- a cleared browser storage

**Decision (Geoff, 2026-10-23):** "can you implement A but keep in mind and try to design it with the idea that we may have to change up the data source from a to c or maybe even F with the addition of B and other options that improve the performance without actually changing the underlying data storage option".

### A — as built (build 2026-10-23a)
- **Layers:** app ⇄ `CachedStore` (the device copy) ⇄ source store.
    - A **source** is any store with the usual interface plus `snapshot()` (every file + a change bookmark) and, optionally, `changesSince(bookmark)`.
    - Today's sources: `GraphStore` (OneDrive; delta link as the bookmark) and `FsStore` (local folder; no bookmark, so it lists file versions).
    - **Swapping later:** C (an index file) or F (a backend) becomes another source, or seeds the copy, with no change to the app or the copy. B is drawing-only and doesn't touch this layer.
- **Device copy:** IndexedDB `hta-device-copy`, keyed by a scope (OneDrive account + folder, or folder name). The files and the bookmark are saved in **one transaction**. Writes always go to the source first, with the same conditional writes as before. A cached file is used only when its version matches what the source reports. If IndexedDB fails, the app works as before.
- **Startup:** the copy is drawn at once, then checked: one change-feed request with the bookmark, or a full re-check if the bookmark expired. Only differing files are downloaded.
- **Offline start:** shows the copy, marked offline, and catches up when the connection is back.
- **Diagnostics** show the copy's state; **Clear device copy** forces a full re-download.
- **A → C path kept open:** the copy is one list of records (path, version, content, source metadata) plus a bookmark, so it can be exported as an index file.
- **Tests:** a `devicecopy` group (22 checks): second start downloads nothing; edits and deletes made elsewhere while closed; own saves; expired bookmark; offline start and catch-up; Clear device copy; local folder. The `onedrive` and `resilience` checks now accept the change feed as a re-check. 341 checks pass.
- **Stress test** (`docs/stress-test-results.md`, "After R2-7 A"): OneDrive limit **200–400 → ~8,000–10,000 tasks on the PC (~25–40×)** and **~2,000–3,000 on the phone (~7–10×)**. The limit is now redrawing (B). The local-folder background check is unchanged (~5,000).

**Status:** A built 2026-10-23, awaiting Geoff's check on phone and PC. B, C, D and the cheaper local-folder check are not approved.

## R2-8 — Don't lose anything (data-safety review)

**Asked** (Geoff, 2026-10-31), before moving all his to-dos from other apps into HTA: "I want to make absolutely sure I do not loose any info. I want to explore with you all the different ways my todo items can get unintentionally deleted or checked off, lost (no longer showing in a list that it should), or other ways of loosing track of items". Later: "the most important tasks to not loose track of are tasks with a due date".

**Approach:** one category at a time. Each path gets its protection today, how likely it is, the gap, options and a decision.
- **Categories:** Deleted · Overwritten · Checked off by mistake · Hidden but still there · Moving tasks in · Long-term.
- **Context:** Geoff has a **Microsoft 365 Family** subscription, so OneDrive's **Files Restore** can roll the whole OneDrive back to any point in the last 30 days.

### 1. Deleted (reviewed 2026-10-31, from the code)
| # | How | Protection today | Gap |
|---|---|---|---|
| 1 | Delete in the app (⋯ → Delete…) | Confirm dialog; Undo for 5 s rebuilds the exact file; OneDrive recycle bin / local `.trash`; If-Match (no delete if changed elsewhere) | After 5 s only via OneDrive's website. No "recently deleted" view. A parent deletes all its subtasks with one confirm. No extra warning for due-dated tasks |
| 2 | Demote without "Keep it" | "Keep it, archived" is ticked by default. Nothing is deleted if saving the line fails | No Undo. "Title only" drops the due date. Even with details, the due date becomes text inside another task, so **it leaves the Today view** |
| 3 | Deleted outside the app (Explorer, OneDrive web, another device, a script) | OneDrive recycle bin (on the PC also the Windows Recycle Bin) | **The app quietly drops it from the list**; there's only a message if that task was open in the editor. **The biggest gap** |
| 4 | Claude deletes files | CLAUDE.md rule 10 | Nothing in the app catches it; same as #3 |
| 5 | "Use theirs" on a file deleted elsewhere | The dialog asks | Your unsaved edit is discarded with it |
| 6 | OneDrive itself | Recycle bin 30 days (sooner if the bin passes ~10 % of storage); mass-delete prompt; Files Restore (M365) | Nothing of the app's own after 30 days |
| 7 | Clear device copy / Sign out | Only the browser's copy is removed | — |
| 8 | Work PC local folder | `.trash` for deletes made in the app | No cloud copy of the folder (see Long-term) |

**Options:**
- **A, a trash folder for every store:** before deleting, the app saves a copy in a hidden trash folder inside the task folder. Local folders already do this; OneDrive would be new. It's shared by all devices, kept until emptied, and Claude can read it. Plus a **Recently deleted** view (⋯ menu) with **Restore**, due dates shown first.
- **B, a notice when tasks disappear from elsewhere:** the device copy still has the last text of a file that vanished. Save it into the same trash and show "N tasks were deleted elsewhere: … — Restore / OK", with due-dated tasks first and highlighted.
- **C, protect due dates in Demote:** a due-dated task is always kept (archived, restorable), and the dialog warns "This task is due … — it will leave the Today view".
- **D, extra care deleting due-dated tasks and parents:** the Delete dialog shows the due date and names the subtasks; Undo lasts longer (e.g. 15 s).
- **E, soft delete only** (`status: deleted`, purged later): not chosen; it changes the file format and clutters the folder.

**Decision (Geoff, 2026-10-31): "add A, B, C and D to the spec".** Status: **Decided**, not yet approved for build.

**Details to settle at build time (recommendations):**
- **Trash folder name:** `.trash`, the same name local folders already use. Names starting with `.` are never tasks.
- **Each trashed copy:** the file's exact text, plus who and when (deleted here, or noticed as gone from elsewhere), kept in a small index next to it.
- **Emptying:** never automatic at first. Later maybe "empty items older than N days" in the Recently deleted view.
- **B:** the notice only covers files the device had seen. A file created and deleted elsewhere while this device was closed never reaches it; OneDrive's recycle bin still has it.

### 2. Overwritten (reviewed 2026-10-31, from the code)
| # | How | Protection today | Gap |
|---|---|---|---|
| 1 | Two devices (or Claude) save the same task | If-Match → conflict dialog (*Use their version / Overwrite with mine / Keep both*); local folder: version check with a tiny race | The dialog doesn't show what differs. **Use theirs** discards your edit with no copy. **Overwrite** discards theirs (only OneDrive version history has it). A due date changed on one device can be reverted blindly |
| 2 | Editing while the file changes elsewhere | Banner; Save always asks (Geoff tested it) | — |
| 3 | Unsaved edits lost: offline, Android closes the app, battery | A failed save keeps the text in the editor. The PC warns on tab close. A failed check-off reverts with a message | **Unsaved editor text is only in memory** (stashed only before a sign-in redirect). Medium risk on the phone |
| 4 | The Formatted editor re-writes the notes when they are edited | Notes untouched unless edited (T1-2) | Re-styles the whole body; Markdown it doesn't support can be altered or dropped. Raw mode is exact |
| 5 | Recurring task, Recycle mode | By design | No record of completions; checklist ticks wiped; missed dates skipped by default |
| 6 | Undo, Today/Tmrw buttons | Undo uses the same version check | One tap changes a due date; Undo lasts only 5 s |
| 7 | Parts of the file the user didn't touch | Key order, unknown keys, body and line endings kept | YAML comments dropped, unknown keys moved to the end (T1-9) |
| 8 | OneDrive conflict copies (`task-PCNAME.md`) | Shown as a separate task, duplicate id flagged | Two copies of one task (see Hidden) |
| 9 | Stale device copy | Version-matched only; `keepOpenEdit` | — |

**Outside the app:** OneDrive version history per file; Microsoft 365 Files Restore (30 days). The work PC's local folder has neither.

**Options:**
- **A, show the difference in the conflict dialog:** what differs (due date first, then title, status, list, notes), which version is newer, and where it came from.
- **B, never discard a version silently:** the losing side of *Use theirs* or *Overwrite* goes into the trash from Deleted A, labelled "replaced on …", restorable from Recently deleted. This also covers the local folder.
- **C, auto-save unsaved edits on the device:** the open task's unsaved changes are saved on the device every few seconds. On the next open: "You had unsaved changes to *…* (due …) — Restore / Discard".
- **D, keep notes exact in Formatted mode** (keep untouched parts, warn, or open in Raw): not chosen now. It stays in the agent-rounds decision list.
- **E, a done-log for Recycle tasks:** not chosen.
- **F, keep YAML comments and key order (T1-9):** not chosen now.

**Decision (Geoff, 2026-10-31): "add just A, B, and C to the spec".** Status: **Decided**, not yet approved for build.

**Details to settle at build time (recommendations):**
- **C:** save on every change (debounced about 2 s) in the browser's storage, keyed by task. Clear it on a successful save or Discard. Offer it only when the file's version still matches; otherwise show it next to the newer version (as the conflict dialog does).
- **B:** in the trash index, label the entry with the version's source ("from this device" or "from elsewhere") and the time.

### 3. Checked off by mistake (reviewed 2026-10-31, from the code)
| # | How | Protection today | Gap |
|---|---|---|---|
| 1 | Mis-tap on a row's checkbox | 44 px tap areas; scrolling isn't a tap; Undo for 5 s | The task vanishes at once (Show done is off by default) and leaves the Today view; after 5 s nothing points to it |
| 2 | Two check-offs in a row | Undo | Only the last action can be undone (a new Undo replaces the old one) |
| 3 | The "Check all" dialog | Asks; Cancel / Check only this / Check all; Undo restores everything | **Check all** is the highlighted default: one hurried tap ticks the task, every subtask and every `- [ ]` line in its notes |
| 4 | Recurring, Recycle mode | Undo | No dialog; one tap moves the due date and unchecks the checklist |
| 5 | Recurring, Keep-copies mode | Undo | 5 s limit |
| 6 | A checkbox inside the notes (Formatted editor) | Needs Save | Save & close keeps a stray tick unnoticed |
| 7 | Status dropdown in the editor | Needs Save | — |
| 8 | Space on a focused checkbox (PC) | Same as a tap, with Undo | — |
| 9 | Claude marks a task done | CLAUDE.md rule 10 | Invisible in the app |
| 10 | Another device checks it off | Synced like any change | It just disappears |

**The risk is losing track, not losing data:** the file keeps everything, plus `status: done` and `completed:`.

**Options pitched:**
- **A:** a Recently done view.
- **B:** a longer, stacking Undo.
- **C:** due-dated tasks stay visible, struck through, after check-off.
- **D:** a safer Check all.
- **E:** confirm an early or checklist-heavy Recycle.
- **F:** notes checkbox safeguards.
- **G:** a notice for check-offs from elsewhere.

**Decision (Geoff, 2026-10-31): "just add D but only the (require a second tap if it has subtasks in either the markdown or actual subtask files)".**
- **D as decided:** when a task has open subtasks (subtask files) **or** unchecked `- [ ]` lines in its notes, **Check all** needs a second, deliberate tap to confirm. For example, the button turns into "Tap again to check all 3 subtasks and 4 items", or a short confirm step names the counts.
- **Unchanged:** **Check only this** and Cancel; which button is highlighted (Geoff chose only the second-tap part); a task without subtasks or checklist lines still checks off in one tap.
- A–C and E–G are not chosen.

Status: **Decided**, not yet approved for build.

### 4. Hidden but still there (reviewed 2026-10-31, from the code)
| # | How | Visible where | Gap |
|---|---|---|---|
| 1 | Done | Show done | By design |
| 2 | Archived (demoted, kept) | Show archived | Its due date is now text inside another task; not in Today |
| 3 | Broken header (YAML can't be read) | Read-only in **Inbox** with ⚠, title from the file name | List and due date unreadable → not in its list, **not in Today** |
| 4 | Unreadable due date | Its list, with ⚠ | **Not in Today** (YYYY-MM-DD only) |
| 5 | Ignored names: `_`/`.` prefix, `README.md`, not `.md`, **in a subfolder** (both stores read the top folder only) | Nowhere | Invisible with no warning. Higher risk during an import |
| 6 | Open subtask under a done parent ("Check only this") | Today (if due); hidden in the list view unless Show done | Only a toast at check-off |
| 7 | Wrong list (moved, `list:` typo, demote) | That list; Today if due | A typo makes a new list; no counts in the list picker (T1-13) |
| 8 | Search left on | Filters both the lists and Today | **Only a toast says it's active** |
| 9 | Today sections | Today open; Overdue and Upcoming collapsed with counts; "+ N later" | By design (R2-2) |
| 10 | Duplicates (conflict copies, Keep both, imports) | Both shown | Confusing, not hidden |
| 11 | Unknown status | Shown with ⚠ | — |
| 12 | Orphan subtask | Top level | — |
| 13 | Not uploaded yet by OneDrive | Not on other devices yet | See Long-term |
| 14 | Due-dated subtasks | Today and under the parent | — |

**Options pitched:**
- **A:** a "Needs attention" check.
- **B:** due dates still findable when the header is broken.
- **C:** a search banner.
- **D:** open Overdue by default (or an overdue badge).
- **E:** list-picker counts.
- **F:** open subtasks of a done parent stay visible.

**Decision (Geoff, 2026-10-31): "add A, C and D (but for D just show the overdue count as badge, keep overdue collapsed)".**
- **A, Needs attention:** one place lists everything the app can't place properly:
    - a broken header
    - an unreadable due date
    - non-`.md` files and anything in a subfolder of the task folder
    - duplicate ids
    - open subtasks under done parents
    - a list that isn't in `_todo.json` (a likely typo)

  Due-related items come first. It shows as a badge on ⋯ and as a section at the top of the Today view when it isn't empty.
- **C, search banner:** while a search is active, a bar under the header ("Filtering: *…* — ✕ Clear") in the lists and in Today.
- **D, overdue badge:** the overdue count shows as a badge where the Today view is opened (and in its header). **Overdue stays collapsed.**
- B, E and F are not chosen. E stays in the agent-rounds decision list as T1-13.

Status: **Decided**, not yet approved for build.

### 5. Moving tasks in (from Super Productivity and Microsoft To Do)
**Deferred (Geoff, 2026-10-31): "lets put this discusson off for now, but remind me to discuss this when we begin to talk about importing the existing tasks from spa and ms todo".** What was pitched is kept here for that discussion.

**Risks:**
- **A due date shifts by a day:** To Do stores due dates as midnight in a time zone.
- **Fields with no HTA place:** due times, reminders, importance ★, My Day, SP time estimates and time spent, attachments.
- **Repeats that don't translate:** "2nd Tuesday" and similar become ⚠ and stop rolling forward.
- **Statuses that don't match:** in progress, waiting, deferred.
- **Structure:** SP subtasks; To Do steps → `- [ ]` lines; projects, tags, categories.
- **Invisible files** from a conversion bug (Hidden #3–#5).
- **Duplicates** on a re-run.
- **Tasks added to the old apps after the import.**
- **Too much done history.**

**Proposed plan:** nothing touches the real folder until step 5.
1. **Read-only inventory** into a private report in `private/`.
2. **Agree the mapping** with Geoff.
3. **Convert into a staging folder**, e.g. OneDrive `HTML-ToDo-App-Import`.
4. **Automatic check:**
    - one file per source task
    - every due date matches the source
    - counts per list match
    - every repeat phrase parses
    - Needs attention (Hidden A) is empty

   Then Geoff reviews it in the app.
5. **Move into the real folder**, after showing the list. Re-runs are safe, because each file keeps its source id.
6. **Run both side by side** for 1–2 weeks with the old apps read-only, then a final catch-up pass.

**Open questions (recommendations):**
- **Q1, what to import:** open tasks only.
- **Q2, how to read the data:**
    - SP: its backup JSON export.
    - To Do: Microsoft Graph's To Do API, which needs a read-tasks permission on the Azure registration plus Geoff's consent.
- **Q3, due times and reminders:** keep them as an "Imported: …" line in the notes. The alternative is new fields (format 4).
- **Q4, the source link:** a new known optional field `source:`.
- **Q5, untranslatable repeats:** convert them by hand from the report, or add "Nth weekday" support.
- **Q6, lists:** map 1:1 with a rename/merge table. Importance, My Day and tags become `collections`.
- **Q7, before importing:** build Hidden A (Needs attention) and Deleted A (trash) first, and remove the 500 bulk test tasks.

Status: **Deferred**. Raise it again when the import is discussed.

### Build order with R2-5 folders (Geoff, 2026-10-31)
**Question (Geoff):** "would the R2-8 safeguards need to be changed after we switch from lists to folders? If so, then we should change the order and switch to folders first...?"

**Effect of folders on each safeguard:**
- **Large:** Deleted B and Hidden A.
    - **Deleted B:** a move in Explorer looks like delete + new, so it needs move detection by `id`, plus a "folder deleted" notice.
    - **Hidden A:** the checks change. Files in subfolders become normal; new checks: a subtask in the wrong folder, duplicate ids from an interrupted move, a folder/`list:` mismatch.
- **Small, if designed for folders from the start:** Deleted A and Overwritten B (the trash records full paths, and Restore re-creates folders), and Overwritten A ("folder" in the comparison).
- **None:** Deleted C, D; Overwritten C (if keyed by task id); Checked off D; Hidden C, D.

**Options:**
1. **All safeguards first:** Deleted B and Hidden A get built twice.
2. **Folders first:** the riskiest change, including migrating the real files, happens without a safety net.
3. **Split.**

**Decision (Geoff, 2026-10-31): "record option 3 and approve phase 1".**
- **Phase 1: Approved for build.**
    - **Covers:** Deleted A, C, D · Overwritten A, B, C · Checked off D · Hidden C, D.
    - **Designed for folders from day one:** the trash keeps each file's full relative path, and Restore re-creates missing folders. Auto-saved edits are keyed by task `id`.
- **Phase 2** (after the R2-5 implementation discussion): R2-5 folders, built together with **Deleted B** and **Hidden A (Needs attention)**, which share the "match tasks by `id` across paths" machinery.
- **Then:** a prototype on the test folder → migrate the real folder → the SP/To Do import.
- **Until Phase 2:** deletions made outside the app are covered only by OneDrive's recycle bin, version history and Files Restore.

### Phase 1 — as built (build 2026-11-01b; verified on PC 2026-11-07, merged to `main`)

**Geoff's PC test (2026-10-31 to 2026-11-07, `HTML-ToDo-App-Test` on real OneDrive, served from `http://localhost:8000/app/`): all 7 passed.** Delete dialog + Recently deleted + Restore (the `.trash` folder on real OneDrive, no trash files shown as tasks after a refresh); demote guard; conflict comparison + replaced version in the trash; unsaved-changes offer (Restore and Discard); Check all second tap, revert and Undo; search bar; overdue badge. **Phone check (2026-11-07): passed** (build number, Recently deleted at phone size, Check all). It found that subtasks restore one at a time → the restore follow-up below.
**Status: Built** (Deleted A, C, D · Overwritten A, B, C · Checked off D · Hidden C, D). Built on the branch `r2-8-phase1`, not merged; Geoff's check on phone and PC is next.

**Deleted A — trash for every store + Recently deleted:**
- **When:** before the app deletes a task file (⋯ → Delete…, Demote without "Keep it"), it saves the file's exact text in the task folder's hidden `.trash/` folder. Only Undo of the app's own just-created recurring copy skips the trash. If the trash copy can't be saved, nothing is deleted; if the delete then fails (changed elsewhere), the trash entry is removed again.
- **All stores:** demo (in memory), local folder (the copy `FsStore.remove` used to make is now made by the app, for every store), OneDrive (new: the existing conditional create, `conflictBehavior=fail`, under `.trash/`; OneDrive creates the folder).
- **Layout:** no shared index file (two devices would conflict). Each entry is two files with one name:
    - `.trash/<YYYYMMDD-HHMMSS>-<6 random>-<slug>.md`: the file's exact text (line endings kept).
    - `.trash/<same>.json` (sidecar): `{ "format": 1, "path", "id", "title", "due", "deletedAt", "reason", "by", "device" }`.
        - `path`: the full relative path it came from (R2-5 folders restore into the right folder).
        - `reason`: `deleted` | `replaced`. `by`: `this device` | `elsewhere` (whose version it is). `device`: `Phone` | `PC` (where it was trashed). `deletedAt`: ISO time.
- **Older copies** from the local folder's own trash (`<UTC stamp> name.md`, no sidecar) still show and restore.
- **Never a task:** `isTaskPath` now rejects any path inside a folder whose name starts with `.`. Every store still reads only the top folder (Phase 1). **OneDrive's change feed** covers subfolders and (per Graph's docs) leaves out `parentReference.path`, so `GraphStore` now keys every item by its path relative to the task folder and treats a file as a task only when its parent is the task folder's own id (one extra metadata request per session). A task moved into a subfolder elsewhere now leaves the list instead of lingering.
- **⋯ → Recently deleted:** due-dated entries first (highlighted, "With a due date"), then the rest; each newest first, with title, due, original path, when, and the reason ("Deleted on Phone", "Replaced: your version, not used", "Replaced: the other version, overwritten"). Full screen on a phone, a dialog on a PC.
- **Restore** re-creates the file at its original path (missing folders are created by the store). If the name is taken, it uses the same unique-name rule as Undo (`name-2.md`). Then the entry (both files) is removed. Nothing is emptied automatically.
- **Undo** (now 15 s for deletes) removes the matching trash entries after re-creating the files.

**Deleted C:** if the task being demoted (or a subtask demoted with it) has a due date, "Keep it, archived" is ticked and disabled, with "This task is due *date* — it will leave the Today view." (a subtask is named). `doDemote` enforces it too.

**Deleted D:** the Delete dialog shows the task's due date and names its subtasks with their due dates (up to 10, then "and N more"). Undo for deletes lasts 15 s; other Undos stay 5 s.

**Overwritten A:** before *Use their version / Overwrite with mine / Keep both*, the app reads their current version and shows what differs: **due date first** (highlighted), then title, status, list, prefix, repeat, collections, notes ("changed" + line counts + the first differing line). It says when theirs was saved and by whom (OneDrive: `lastModifiedDateTime` + `lastModifiedBy`; local folder: the file's modified time), when yours was edited, and which is newer. If theirs was deleted, it says so. On a 338 px phone the choices stay at the bottom of the dialog.

**Overwritten B:** *Use their version* saves your version in the trash first (`replaced`, `this device`); *Overwrite with mine* saves their current text first (`replaced`, `elsewhere`). If that copy can't be saved, nothing is replaced. *Keep both* is unchanged.

**Overwritten C:** while the editor has unsaved changes, a draft is saved ~2 s after typing stops (and at once when the app goes to the background) in `localStorage`:
- **Key:** `todo.autodraft|<store scope>|<task id>`. The scope is the device copy's (OneDrive `onedrive|account|folder`, local folder `local|<folder id>|<name>`), or `demo`.
- **Value:** `{ id, file, version, isNew, list, parent, order, fields, body, title, due, savedAt }`.
- **Cleared** on a successful save, Discard, or closing with no changes. An untouched new task isn't kept.
- **On the next start** (after the tasks load): "You had unsaved changes to *title* (due *date*) — Restore / Discard", newest first. Restore opens the editor with the draft applied and unsaved. If the file changed since, the "changed elsewhere" banner is up, so Save goes through the conflict dialog. A draft whose task no longer exists offers **Restore as new task**.
- The sign-in stash (`todo.draft`) is unchanged and runs first; its own draft isn't offered twice.

**Checked off D:** in the "Check off …?" dialog the first tap on **Check all** arms it ("Tap again to check all 3 subtasks and 4 items"); it stays the highlighted button, in the same colour (build 2026-11-01b; 2026-11-01a turned it red). A second tap at least 300 ms later checks everything; after 4 s it reverts. Check only this, Cancel and the highlighted button are unchanged. The recurring keep-copies path uses the same dialog.

**Hidden C:** while a search is active, a bar under the header in the lists and in Today: "Filtering: “*q*”" with **✕ Clear**.

**Hidden D:** the overdue count (open tasks with a real `YYYY-MM-DD` due before today, ignoring Show done and the search) is a red badge next to the header's list name, on the Today entry of the list picker, and on the Overdue header. Hidden at 0. Overdue stays collapsed.

**Tests:** new group `r28p1` (97 checks), plus 5 trash checks per store in the shared store suite (15). The fake OneDrive (`tests/fake_graph.py`) now has real folders: PUT by path creates them, the change feed covers the subtree without `parentReference.path`, and `:/children` lists one folder. Its If-Match checks are unchanged. Covered:
- the trash on all three stores
- trash files never shown as tasks, including after delta polls, a file put in `.trash` elsewhere, and a restart from the device copy
- Restore to the original path, including a missing folder and a taken name
- Undo removing trash entries; the 15 s Undo
- the demote guard; the delete dialog's subtask list
- the conflict diff at 338 px; replaced versions in the trash
- drafts after a restart (same version, changed version, deleted task)
- Check all's second tap and revert; the search bar; the overdue badge
- no page errors; escaped hostile text
- **Review fixes (build 2026-11-01b, Geoff: "do the fixes first"):** hostile task text (title, due, notes, `<script>`) in the delete dialog, the armed check-off dialog, the conflict comparison, Recently deleted (a replaced version) and the unsaved-changes offer is shown as text and never runs; the armed Check all isn't recoloured.

Existing tests that click Check all now tap twice. The local folder's "copy kept in `.trash`" store check became "remove() makes no copy of its own" (the app's trash covers it). Full suite: **557 checks pass** (2026-11-01a); see the change history for 2026-11-01b.

**For review:**
- **Not yet verified against real OneDrive:** a folder named `.trash` (leading dot) and creating it by path; `parentReference.id` in the folder's change feed.
- Recently deleted reads one sidecar per entry, which is slow on OneDrive with hundreds of entries.
- Restoring a *replaced* version while the task exists gives a second file with the same `id` (shown with ⚠, like Keep both).
- Subtasks restore one by one.

### 6. Long-term
Reviewed 2026-10-31. Geoff chose not to add these options to the spec.

**Note (Geoff, 2026-10-31: "note the git history"):** revisit a **local-only git history of the task folder** when Claude (or another AI) starts managing tasks regularly.
- **How:** a scheduled job commits the folder daily, kept on the home PC only.
- **Why:** any change, including an AI's bulk change, can be found and undone precisely, which goes beyond OneDrive's 30-day safety nets.

### Follow-up: restore a task with its subtasks (Geoff, 2026-11-07)
**Found** in Geoff's phone check of Phase 1: "When i deleted a task with subtasks (the task itself was a subtask of another task), and then tapped delete all... I restored the parent task, but none of its subtasks were automatically restored. I had to seperately restored each of the parent tasks subtasks". **Asked:** "Is there a way to modify the restore function so I have the option to restor the task and all it's subtasks just like the delete screen gives me the option…". Also: "what about restoring a task with 7 levels of subtasks?"

**Options pitched:**
- **A:** Restore asks, like Delete does.
- **B:** a grouped list (one entry per delete).
- **C:** both.

Claude recommended A plus a "+ N subtasks" note on the parent's entry.

**Decision (Geoff, 2026-11-07): A plus the "+ N subtasks" note, with both details as recommended. Approved for build** ("add it to the spec and you are approved to build it").
1. **Subtasks deleted separately, earlier, are included** (they still point to the parent). They're listed, marked "deleted separately", before you confirm.
2. **Restoring a subtask alone while its parent is in the trash asks:** "Its parent *X* is also in Recently deleted — restore it too?"

**As built (build 2026-11-07a; merged to `main` 2026-11-07):**
- **How entries hang together:** by task `id` and `parent:`, not by deletion time. The sidecar now records `parent`. Entries from before this build have no `parent` in their sidecar, so it is read from the trashed file once. Replaced versions don't count (their task still exists). For an id that's in the trash twice, the newest entry wins.
- **The list:** a parent's entry says **"+ N subtasks"**, counting every level.
- **Restore, in order:**
    1. **Its parent is in the trash too (decision 2):** "Restore its parent too? — Its parent *X* is also in Recently deleted (and N tasks above it) — restore them too?" Buttons: **Cancel / Only this task / Restore parent too**. "Too" brings back the chain of trashed parents up to the first one that exists.
    2. **It has trashed subtasks:** "Restore *X* and its N subtasks (L levels)?" The list is indented as a tree (first 10, then "and N more"), with due dates. Subtasks deleted earlier are marked "deleted separately" (decision 1). Buttons: **Cancel / Only this task / Restore all**.
- **Any depth:**
    - Subtasks are found level by level until a level turns up nothing; a loop of parent ids stops.
    - Files are restored **top level first**, so a subtask never comes back before its parent.
    - A task that's already back is skipped, but its trashed subtasks are still found.
    - A taken file name gets the unique-name rule; nesting goes by `id`, so it's unaffected.
- **Progress and failures:**
    - "Restoring 9 of 24…" while it runs.
    - If it stops (e.g. the connection drops), what's back stays back: "Restored 9 of 24 — 15 are still in Recently deleted." Restore on the highest remaining entry finishes the job.
- **Undo:** one Undo (15 s) for the whole restore. It deletes the restored tasks again, subtasks first, so they go back to the trash.
- **Not changed:** a task with nothing related in the trash restores at once, as before.

**Tests:**
- **Demo:** the Phase 1 restore now asks; "+ 3 subtasks"; Only this task.
- **New group (fake OneDrive, phone):** a 7-level tree plus a sibling.
    - the delete dialog lists all 7
    - "+ 7 subtasks", and "+ 3" on a middle task, with the parent removed from the sidecars
    - the dialog: 7 subtasks, 7 levels, indented as a tree
    - hostile titles stay text
    - Restore all: exact text back, trash empty, every parent before its subtasks
    - one Undo
    - decision 2: a middle task's chain of 3 parents, then its own subtasks; the sibling restores without a question
    - a connection lost after 3 files, then finishing from the highest remaining entry
    - decision 1: "deleted separately" marked; Only this task; finishing from the next level
    - no writes without If-Match, no page errors

  Full suite: **591 checks pass**.

**Status:** **Verified on PC** (2026-11-07). Geoff's restore tests on the copy folder all passed: the deep tree, Undo, the parent question, Only this task, and a subtask with its own subtasks. Merged to `main` at his request ("the restore tests all passed, merge it").

### Speed of delete and restore (Geoff, 2026-11-07)
**Noticed** while testing the follow-up: "it does take a little longer to process a deep level task tree". **Asked:** "does the delete or restore process change the files themselves at all?"

**Why it's slow:** each task is handled one at a time, one OneDrive request per step.
- **Delete** is 3 requests: copy to `.trash`, write the `.json` note, delete the original (which also goes to OneDrive's recycle bin).
- **Restore** is about 4: read the copy, create the file, remove the copy, remove the note.
- **Opening Recently deleted** reads each note, and for entries from before build 2026-11-07a, the file too.
- **An 8-task tree** is about 30 requests in a row.

**Files are not changed:**
- The trash copy is the exact text, and Restore writes it back unchanged.
- Delete never edits the task first.
- **What does differ after a restore:** OneDrive sees a new file, with a new item id, new dates, and version history starting again (the old history stays with the deleted original in the recycle bin). A taken name gets the unique-name rule.

**Options:**
- **A. Each level in parallel:** all subtasks of one level at once, then the next level (parents still first). Small change; noticeably faster on deep or wide trees.
- **B. A real move instead of copy + delete:** Graph `PATCH` of the item's parent into `.trash` and back.
    - **Pros:** one request per file instead of 3–4; the file keeps its OneDrive id and version history (a data-safety gain).
    - **Cons:** a bigger change, and the local-folder store (`FsStore`, the work PC) needs checking; Chrome's `move()` support for folders must be verified.
- **C. Graph JSON batching:** up to 20 requests in one call. The fastest and the most complex.

**Recommendation (Claude):** B, as the long-term fix.

**Decision (Geoff, 2026-11-07):** recorded, **no action**. "I will explore this further if I feel the delete / restore process is unacceptable. For now, I am guessing I will rarely need to delete and even more rarely need to restore a delete."

**Status:** Open (parked).

---

## R2-9 — Add tasks by voice with Amazon Echo (Alexa)

**Asked** (Geoff, 2026-10-31): "is it possible to somehow use the amazon alexa device to add items to the HTA lists / files? I am open to multiple different options but for now, lets limit to using my existing echo devices (not creating my own voice to text device)". Geoff also shared a research note on Amazon list APIs (kept outside the repo).

**Problem:** capture a task by voice on the Echo devices Geoff already has, and have it land as a normal HTA task file (data format 3) without retyping.

**Constraints found (2026-10-31):**
- **No official way for outside apps to read Alexa's own to-do or shopping lists.** Amazon withdrew third-party access to Alexa lists (mid-2024, as far as we know); that is what ended the Todoist and Any.do list syncs.
- **IFTTT has no "you said something to Alexa" trigger any more.** Checked in Geoff's IFTTT account on 2026-10-31: every Alexa service there only goes the other way (IFTTT makes Alexa speak or run a routine).
- **Alexa Routines** only react to fixed phrases, so they can't carry a task's text.
- **The Alexa Shopping Actions "AddToList" task** only adds to the Amazon **Wish List**.
- **Amazon's product APIs** (Product Advertising API, Selling Partner API) and catalog scrapers return product and price data. They are only relevant if HTA ever gets a shopping list with product links.

### Approach 1 — talk to HTA directly: a private custom Alexa skill
- **Saying:** "Alexa, ask HTA to add *call the plumber*" / "…add *renew registration* due Friday". Alexa confirms: "Added *call the plumber* to Inbox." It can ask "Anything else?" to add several in a row.
- **How:**
    - An Alexa-hosted skill (Amazon's free hosting), left in **development** stage. It works on every Echo signed in to Geoff's Amazon account, with no publishing or certification.
    - The free-text slot (`AMAZON.SearchQuery`) carries the task text; `AMAZON.DATE` carries a spoken due date.
    - The skill creates a new `.md` in the OneDrive folder through Microsoft Graph, with a conditional create (`conflictBehavior=fail`), as the app does.
- **Microsoft sign-in:** Alexa **account linking** with the Microsoft account (OAuth authorization-code grant). This needs a "Web" platform with Alexa's redirect URLs and a client secret, on the existing Azure registration or a separate one.
- **Pros:** official and stable; the task is in HTA within seconds; works with the PC off.
- **Cons:**
    - The skill's name must be said ("ask HTA…").
    - A new component to build and maintain; account linking is fiddly the first time.
    - What's said goes through Amazon.

### Approach 2 — Alexa's own list as an inbox, swept into HTA
- **Saying:** the built-in "Alexa, add *call the plumber* to my to-do list". This gives the most natural phrase and Alexa's best recognition.
- **How:** a sweeper reads Alexa's list, creates one HTA task per item, then deletes (or completes) the item on Alexa, so the Alexa list works as a queue.
- **Unofficial:** the sweeper logs in as Geoff through Amazon's private app interface. It can break when Amazon changes it, and the Amazon login (with two-step verification) has to be renewed now and then.
- **Fails safe:** if the sweeper breaks, items just wait on Alexa's list. Nothing is lost; they stop moving until it's fixed.
- **Alexa's shopping list** could be swept the same way, into an HTA "Shopping" list.
- **Ways to run the sweeper:**
    - **2a. A script on the home PC.** Windows Task Scheduler runs it about every 15 minutes. It writes into the synced OneDrive folder, so it needs no Microsoft sign-in.
        - **Pro:** simple, nothing to host.
        - **Con:** runs only while the PC is on (items wait until then); the Amazon login is re-done when it expires.
    - **2b. Claude sweeps when asked.** An Alexa-list MCP server (community projects exist, e.g. `GraysonCAdams/alexa-mcp` on the alexa-remote2 library, and `thesethrose/alexa-shopping-list`) lets Claude read the list. Claude creates the files following the task-file contract ("sweep my Alexa list").
        - **Pro:** almost nothing to build; fits the goal of Claude managing tasks; Claude can tidy items on the way (a due date from "by Friday", the right list).
        - **Con:** manual, or tied to a Claude session; third-party code holds the Amazon login, so it must be read before installing.
    - **2c. Home Assistant.** Home Assistant 2026.7 exposes Alexa shopping and to-do lists as to-do entities in its core Alexa Devices integration; the custom `lonlazer/ha-alexa-todo-lists` did this earlier. An automation would write the files.
        - **Pro:** runs all the time; Home Assistant's community maintains the Amazon side.
        - **Con:** only sensible if Geoff runs Home Assistant; otherwise it adds a whole home server for one feature.

### Common to every option
- **Where tasks land:** the **Inbox** list by default (open question: one list per spoken word, e.g. "…to my shopping list" → Shopping).
- **The file:** a new `id`, `title` (the spoken text), `status: open`, `list`, `order` at the end, and `due` only when a real date was said. The file name follows the S-11 slug rules.
- **Duplicates:** a sweeper deletes the item from Alexa only after the file is written. A retry must not create a second file (match on the Alexa item's id, kept in a small local record).
- **Real data (rule 10):** prototype against `HTML-ToDo-App-Test` first, then switch to the real folder with Geoff's OK.
- **Secrets:** Amazon cookies, Microsoft tokens and client secrets stay local and git-ignored (`private/`), never in the public repository.
- **Not to depend on:** the research note's tool names were checked on 2026-10-31. Community tools' maintenance status was not; check each repository before relying on it.

### Recommendation (Claude)
1. **Try 2b first.** It's nearly free to try, and shows whether the natural phrase really changes Geoff's habits.
2. **If it does, build 2a** so it runs on its own.
3. **Keep Approach 1 as the fallback** if Amazon closes the unofficial route; 1 and 2 can also run side by side.

**Open questions:**
- One fixed list (Inbox), or a spoken list name?
- Should spoken due dates be supported in the first version?
- For 2b, which MCP server, after reading its code?
- For Approach 1: the existing Azure registration, or a separate one for the skill?

**Status:** Open (options pitched; nothing decided or approved).

---

## R2-10 — Build number in the header, version in Settings

**Asked** (Geoff, 2026-11-07), about the "v0.2.0-dev" at the top right: "what is that for?" Then: "i would rather see the build number at the top and the version being worked on in the setting".

**Options:**
- **A:** the plain build (`2026-11-07a`) at the top right. About the same width as `v0.2.0-dev`; the tooltip on a PC says "Build".
- **B:** "build 2026-11-07a". Clearer, but wider on a phone.

**Decision (Geoff, 2026-11-07): A ("go ahead with the plain version"), approved.**

**As built (build 2026-11-07b):**
- The header label shows `BUILD` instead of `v` + `APP_VERSION`.
- Settings already showed the version, build and data format ("HTML-ToDo-App v0.2.0-dev · build … · data format 3"); unchanged.
- Phones still hide the header label to save room, so on a phone the build is in Settings, as before.

**Status:** Built (pushed to `main` directly, as agreed).

---

## R2-11 — Enter tasks and subtasks one after another

**Asked** (Geoff, 2026-11-07): "I want the UI to make it easier to enter multiple tasks/subtasks one right after the other... When entering tasks or subtasks, enter should save the current task/subtask and allow the user to enter a new task/subtasks."

**Today:**
- The **quick-add line** at the bottom already works this way: Enter saves, clears the line, and keeps the cursor there.
- The gap is the **editor**: ⋯ → Add subtask (and new tasks from menus) open it, and Enter in the title does nothing.

**Options:**
- **A:** Enter in the editor's title saves and opens the next blank one.
- **B:** an inline "+ Add subtask…" line under an expanded parent's subtasks, which works like the quick-add line (type, Enter, type, Enter) without opening the editor.
- **C:** both.

Explained to Geoff with a sketch:
```
☐ Plan garden                        2/3  ⋯
     ☑ Buy seeds
     ☐ Till the beds
     + Add subtask…          ← tap, type, Enter
```

**Decision (Geoff, 2026-11-07): C, both ("i want you to do both").** Details, as recommended:
1. **The editor, for a new task:** Enter in the title saves it, then opens a new blank **sibling**: the same parent and list, placed right after it, with the cursor in the title.
    - **Copied:** only the parent and list. The due date, collections, notes and prefix start empty.
    - **Stopping:** Enter on an **empty** title closes the editor and drops the blank task. ✕, the back gesture and Save & close also stop.
2. **The editor, for an existing task:** Enter in the title means **Save & close**. Only new tasks chain, so fixing a typo in an old title doesn't create an empty task.
3. **The inline line:** "+ Add subtask…" appears under every **expanded** parent in the list views. The Today view is flat, so it has none.
    - Enter saves a subtask (title only) under that parent, at the end, and keeps the line ready for the next one.
    - A small **⤢** on the line opens the typed title in the full editor, for a date or notes.
4. **⋯ → Add subtask** expands the parent and puts the cursor in its "Add subtask…" line, even if it has no subtasks yet. It no longer opens the editor.

**Implementation notes:**
- **Phone keyboard:** `enterkeyhint="next"` on the chaining title and on the inline line; IME composition is ignored, as in quick-add.
- **Saving:** each Enter saves through the normal `saveTask` (conditional create). A failed save keeps the text in the line or the editor and doesn't move on.
- **The ⤢ handoff:** it opens the editor on a new, unsaved task, with the typed title and the parent set.
- **Nested parents:** a subtask that is itself expanded gets its own line.

**Acceptance:**
- Five subtasks can be entered with five Enters from the inline line, and land in order.
- A chain in the editor creates siblings and stops on an empty Enter, leaving no blank file.
- Enter on an existing task's title saves and closes.
- ⋯ → Add subtask focuses the inline line.
- Works on phone and PC.

**Approved for build** (Geoff, 2026-11-07: "include in the next build with the rest of these new feature (R2-11 through R2-14)"). **Built** in build 2026-11-07c; **verified on PC** by Geoff ("it all looks good merge") and merged to `main` 2026-11-07.
- **As built:** exactly as decided.
    - The line is a plain `.addsub` element, not a `.row`, so a long-press never tries to move it.
    - A redraw (a sync, a save) keeps what's being typed and the cursor.
    - The editor's + subtask button keeps opening the editor, so it starts an Enter chain.

---

## R2-12 — Save & close subdued until there's a change

**Asked** (Geoff, 2026-11-07): "The save button stays subdued until there is a change to save, Save & close should to the same".

**Today:** Save is disabled until something changes. Save & close is always fully coloured; with no changes it just closes.

**Options:**
- **A:** Save & close looks subdued, like Save, when nothing has changed, but a tap still closes the editor.
- **B:** disabled; close with ✕ or the back gesture.

**Decision (Geoff, 2026-11-07): A ("Subdued, still closes").**
- It shows full green as soon as there's a change, the same moment Save turns on.
- **A brand-new task** counts as "changed" once its title isn't empty.

**Approved for build** (Geoff, 2026-11-07: "include in the next build with the rest of these new feature (R2-11 through R2-14)"). **Built** in 2026-11-07c. Opening another task drops a blank new one (it is no longer counted as "changed").

---

## R2-13 — Clear a due date on the phone

**Asked** (Geoff, 2026-11-07): "for the pc app, i can clear a date from the date picker. but for the phone app, there is not clear date or any other way to clear out a due date".

**Today:**
- The phone uses Android's own date picker, which has no Clear.
- ⋯ → **Change due date…** has no "No date", and the app's quick reschedule (`setDue`) ignores an empty date.

**Options:**
- **A:** a ✕ next to the editor's Due field.
- **B:** "No date" in Change due date….
- **C:** "No date" in the quick-add date chip.

**Decision (Geoff, 2026-11-07): A and B.**
- **The ✕ (phone and PC):** shown only while there's a date. It clears the field, and the change is saved with Save as usual.
- **"No date" in Change due date…:** clears it at once, with Undo, like the other date changes.
- **A recurring task with its date cleared** keeps its `repeat:`. As today, its next date is counted from today when it's checked off.

**Approved for build** (Geoff, 2026-11-07: "include in the next build with the rest of these new feature (R2-11 through R2-14)"). **Built** in 2026-11-07c. In the editor, a recurring task's date is set to today only when the Due field wasn't touched, so a date cleared on purpose stays cleared.

---

## R2-14 — Today view: ↑ ↓ ● instead of Today / Tmrw

**Asked** (Geoff, 2026-11-07): "In Today view, replace today, and tomorrow buttons with much smaller up arrow icon (move to next day), down arrow icon (move to previous day), and a dot icon (move to today)".

**Today:** Upcoming rows get **Today**, Today rows get **Tmrw**, and Overdue rows get both, as text buttons.

**Decision (Geoff, 2026-11-07):**
- **Counted from the task's due date:**
    - ↑ = one day later, ↓ = one day earlier, even for overdue tasks (due Nov 10 → Nov 11 / Nov 9).
    - ● = today.
    - Up means later, matching the view's time running upward.
- **Which rows:** ↑ and ↓ on every row. ● on every row except those already due today.

**Implementation notes:**
- **Size:** small icons, narrower than the text buttons, but each keeps a touch target about 32 px tall, so it's still easy to hit on the phone.
- **Quick taps:** a task can move several days with quick taps. The row moves between sections as its date crosses today.
    - **Undo** restores the date from before the first tap of a quick series, not just the last step.
    - **Saves:** rapid taps can be combined into one save after a short pause.
- **Recurring tasks:** they move just this occurrence, as the current buttons do (`setDue`). Tooltips on the PC: "Move to the next day", "Move to the previous day", "Move to today".
- **Not changed:** ⋯ → Change due date…, and the list views (no arrows there).

**Approved for build** (Geoff, 2026-11-07: "include in the next build with the rest of these new feature (R2-11 through R2-14)"). **Built** in 2026-11-07c.
- **The buttons:** plain blue icons, 24 px wide, without borders. The first try (bordered 32 px squares) took more room than Today/Tmrw had. Each keeps a 44 px tall tap area.
- **Lined up:** a blank space takes ●'s place on today's rows, so ↑ ↓ line up down the list.
- **Quick taps:** saved once, 0.7 s after the last tap.

---

## R2-15 — Delete all: readable button

**Asked** (Geoff, 2026-11-07): "Delete all button is red text on blue, which is hard to read. Add it as a spec item and include in the next build with the rest of these new feature (R2-11 through R2-14)". Found during the R2-8 phone test. The same button style was on `main` before R2-8.

**Cause:** the delete dialog's button has both `primary` (blue background) and `danger` (red text) classes.

**Decision (Geoff, 2026-11-07):** fix it in the R2-11 build. **Built** in 2026-11-07c: `primary danger` buttons are white text on a deep red (`#c9302c`, contrast about 5.6:1). This covers Delete and Delete all; other danger-only buttons (e.g. Discard) are unchanged.

**Status:** Verified on PC (2026-11-07), merged to `main`.

---

## R2-16 — Explain the repeat "Next date" choices

**Asked** (Geoff, 2026-11-09): "for the repeat next date options, please add a tooltip that explains what the differences are".

**Built (build 2026-11-09a, on branch `r2-5-folders`):** the editor's **Next date** field has a tooltip explaining all three choices, and each choice has its own. Example used: a task every 3 days, due Nov 2, checked off Nov 12.
- **Skip missed** (default): stays on the original rhythm but skips the dates already missed; the next date is the first one on the schedule after today → Nov 14.
- **Catch up:** the next date after the old due date, even if it's still in the past, so every missed one comes up in turn → Nov 5.
- **From completion:** counted from the day it's checked off → Nov 15. Good for "every N days since I last did it".

**Note:** tooltips appear on hover, so on the PC only; phones don't show them. **Decided (2026-11-09):** no visible line under the field on phones ("no need to add the line under the field for the phone").

**Status:** Built.

---

## R2-17 — Review the repeat options; month-end dates drift

**Asked** (Geoff, 2026-11-09): "add R2-17 that I need to look more closely at the repeat options and capture the issue we found just now". It started from: "for all these repeat option, what happen if its a monthly repeat and the date starts as the 31 day of the month? What happens on days when there is no 31st day?"

**Part 1: Geoff reviews the repeat options.** Geoff wants to look more closely at the repeat choices (schedules, Recycle / Keep copies, Skip missed / Catch up / From completion) before anything changes. To discuss when he raises it.

**Part 2: the issue found (checked by running the app's own `nextDue`/`stepAfter`, build 2026-11-09a).**

*What works:* the editor's **Monthly** writes `monthly on day N` (`repBase`), so the day is kept. A short month uses its last day, then the day comes back: Jan 31 → Feb 28 → Mar 31 → Apr 30 → May 31. `monthly on last day` also works (Feb 28, Mar 31, Apr 30, …). Due Jan 31, missed until Apr 10, with `on day 31`:
- Skip missed → Apr 30, then May 31.
- Catch up → Feb 28 → Mar 31 → Apr 30.

*The bug:* a plain `monthly` (typed in Custom, or written by Claude) or `every N months` takes its day from the **current** due date (`want = r.mday ?? anchor.getDate()`, with the anchor being the current due). After one short month the day shrinks for good. All three Next date choices drift:
- `monthly`: Jan 31 → Feb 28 → **Mar 28 → Apr 28 → May 28 …**
- `every 2 months`: Dec 31 → Feb 28 → **Apr 28 → Jun 28 …**
- `yearly` from Feb 29: → Feb 28 every year after, even in leap years (2032).

This affects only days 29–31; days 1–28 are fine.

*A quirk (not a bug, but surprising):* **From completion** with `monthly on day 31` means "the next 31st (or month end) after I check it off", not "a month after I check it off". For example, checked off Feb 10 → Feb 28 (18 days later).

**Options for the drift:**
- **A. Write the day into the file on the first roll** *(recommended)*. When a plain `monthly` / `every N months` / `yearly` rolls forward, the app rewrites the phrase as `monthly on day 31` (yearly: an equivalent form), so the file says what it does.
  - Pros: self-describing; works for Claude edits too.
  - Cons: the app changes the `repeat:` text on its own (a small exception to "never rewrites on its own").
- **B. Keep the start day in a new key** (e.g. `repeat_day: 31`).
  - Pros: the phrase stays untouched.
  - Cons: a new frontmatter key and data-format change, for a small problem.
- **C. Use `series` / history to find the original day.**
  - Pros: no file change.
  - Cons: Recycle mode keeps no history, so this doesn't work there.
- **D. Leave it, and only warn (⚠)** on a plain `monthly` whose due is the 29th–31st.
  - Pros: no behavior change.
  - Cons: the drift still happens if the warning is ignored.

**Also to decide:** whether From completion with `on day N` should instead mean "one month after completion".

**Status:** Open (Geoff to review the repeat options; not approved for build).

---

## R2-18 — Show that files are being changed (busy indicator)

**Asked** (Geoff, 2026-11-09, during the folder tests, after moving a family of 6 files): "add to the list of things to work on some kind of spinner icon or something letting the user know that files are being changed".

**Problem:** some actions change many files one after another, and in OneDrive each file is a separate round trip:
- moving a family to another folder (R2-5)
- deleting or restoring a task tree (R2-8; deep trees noticeably slower, see R2-8 restore notes A–C)
- Check all, recurring copies with subtasks, Delete all in Recently deleted

During that time the screen gives little feedback. The only sign is the header status icon, which turns to a static **⟳** "Syncing…" (`setStat`, `S.busy`/`S.syncing`). It is small, doesn't move, is covered by the editor on phones, and doesn't say what's happening or how far along it is. So it's unclear whether a tap worked, and the user may tap again or close the app halfway.

**Options:**
- **A. Animate the existing status icon.** The ⟳ spins whenever a write is in flight.
  - Pros: tiny change; the icon is always in the same place.
  - Cons: still small; says nothing about what or how much; hidden under the phone editor.
- **B. A progress toast for multi-file actions** *(recommended, together with A)*. A bottom toast such as "Moving 6 files… 3 of 6", then "Moved 6 files" (with Undo where one exists).
  - Pros: clear; shows progress; the same toast area the app already uses; works on phone and PC.
  - Cons: each multi-file action needs a counter hooked in.
- **C. A thin progress bar under the header** (like a browser's loading bar) for any store activity.
  - Pros: visible without words; generic.
  - Cons: no detail; another moving element.
- **D. Block the screen with a spinner overlay** until the action finishes.
  - Pros: impossible to miss; prevents double taps.
  - Cons: heavy-handed; blocks reading the list for seconds on slow connections; a stuck request looks like a frozen app.

**Recommendation:** A + B. Also, while a multi-file action runs, disable a second start of the same action. Add a warning when the app or tab is closed mid-action (`beforeunload`).

**To decide:**
- Which actions count (any write, or only multi-file ones)?
- Should a single-file save also show anything beyond the spinning icon?

**Status:** Open (not approved for build).

---

## R2-19 — A way to hide the "Add subtask…" lines

**Asked** (Geoff, 2026-11-09, during the folder tests): "add some way to hide the "Add subtask..." input box from the main list view (now I guess called the Folder view?)".

**Background:** R2-11 (build 2026-11-07c) puts an inline "+ Add subtask…" line under **every expanded parent** in the folder view (the list view; with R2-5 each list is a folder). It's fast for entering several subtasks, but with many expanded parents it adds a full-width empty row under each family, which is visual clutter when only reading the list. The other ways to add a subtask stay:
- ⋯ → Add subtask (focuses that line)
- the editor's **+ Subtask** button
- Enter-chaining in a new subtask's title

**Options:**
- **A. A setting:** Settings → "Show Add subtask lines" (on/off).
  - Pros: simple; each device chooses.
  - Cons: all or nothing; when off, the fast path is only through ⋯.
- **B. Show the line only on demand** *(recommended)*. Hidden by default; **⋯ → Add subtask** (and the editor's + Subtask, if wanted) opens it under that parent. It stays while you keep entering subtasks and disappears when you leave it empty.
  - Pros: a clean list by default; the fast multi-entry from R2-11 is still one tap away; no setting to manage.
  - Cons: one extra tap compared with today when you want to add a subtask.
- **C. Shrink it to a small "+" at the end of each parent row** that opens the line.
  - Pros: always visible, low clutter.
  - Cons: another small target on already-busy rows, especially on the phone (the ⋯ column is there).
- **D. Show it only on hover** (PC).
  - Pros: no clutter on the PC.
  - Cons: phones have no hover, so it would need another rule there.

**Option:** B can be combined with A, so "always show" stays available for anyone who prefers today's behavior.

**Status:** Open (not approved for build).

---

## R2-20 — Work PC: open the local folder without "Reconnect" every start; sharing with coworkers

**Asked** (Geoff, 2026-11-11, work-PC simulation W9): "i keep having to choose reconnect "Data". Is there any way to make it so I don't have to keep doing that every time I start the app up?" Also: "I would like to share this app with my coworkers so they can use it too on their system". And: "What is the best way to make this behave like a real applications that remembers where the data folder is on start up?"

**Problem:** the work pack opens as a `file:///` page. Chrome forgets the folder permission when the page closes, so every start shows **Reconnect "data"**. The app can't skip it: asking for access needs a click. Windows file permissions don't matter here (it's Chrome's permission), and no Chrome policy grants folder access.

**Experiment (2026-11-11):**
- Setup: the 11a pack served at `http://localhost:8001/app/`, installed as an app, `data` picked once, app closed and restarted.
- **Result: it opened straight to the tasks, with no Reconnect screen.**
- So a normal web address plus an installed app keeps the folder permission (Chrome's persistent permissions).

**Options for the work PC:**
- **A. Install from GitHub Pages** *(recommended)*: `https://gvd1024.github.io/html-todo-app/app/`, picking the local `data` folder once (Geoff can reach github.io at work).
  - Pros: no server to run; updates itself.
  - Pros: tasks stay in the local folder; nothing is sent in local-folder mode, with no sign-in.
  - Cons: always runs the live `main` build, not the nightly pack.
  - Cons: needs internet to start (the service worker caches nothing; S-8 offline is a later item).
- **B. A local server for the pack** (`localhost`), as in the experiment.
  - Pros: keeps the nightly pack.
  - Cons: a server must be running (Python or similar, started at login) before the app starts.
- **C. A real desktop app** (Tauri/Electron wrapper around the same `index.html`).
  - Pros: opens a fixed path with no prompts.
  - Cons: an installer per PC, much more setup, likely IT approval.
- **D. Keep `file:///`**, and make the one click easier (e.g. Enter or any tap reconnects).

**Sharing with coworkers (with A):** each person installs from the same link and picks their own folder. Their tasks stay on their own PC. Before sharing:
- **A "stable" address** that only gets builds Geoff has used for a while, so test builds don't reach coworkers. For example, a `stable` branch or a `/stable/` copy published from a tagged release.
- **Check the employer's policy** on outside web apps, even with local data.
- Work OneDrive mode would need the employer's IT to approve the Azure app; local folder needs nothing.
- The repo is public, so the code and specs are visible.
- **Offline start** (cache the app shell, S-8) becomes more useful once others depend on it.

**Option B in detail (Claude, 2026-11-11):**
- **The server:** a tiny web server on the work PC that serves the app's files at `http://localhost:8001` (listening on 127.0.0.1 only), with the tasks still in the local `data` folder.
- **Server types:**
    1. **A PowerShell script** (`serve.ps1`, .NET `HttpListener`): no install, and no admin needed for `localhost`. Risk: script execution blocked by company policy.
    2. **Python** `http.server`, if Python is present or allowed.
    3. **A single-file server program** (e.g. `miniserve.exe`): no installer, but security tools may block unknown programs.
- **Auto-start:**
    - a shortcut in the Startup folder (`shell:startup`), started hidden at log-on
    - or a Task Scheduler "at log on" task (restarts if stopped)
    - or one "HTA" shortcut that starts the server if needed, then opens the app
- **Keep the address fixed:** Chrome remembers the folder permission **per address**, so the server must always serve one fixed folder (e.g. `C:\HTA\app\`). An update replaces that folder's contents, so the installed app and its remembered `data` folder keep working.
- **No internet needed** to start, unlike option A.

**Setup tool (Geoff, 2026-11-11):** "i want a setup app (or script) that presents these prefilled options but allows the user to customize".
- **What it asks for**, each **prefilled with the recommended value** and editable:
    - **Server URL:** `http://localhost:8001/app/` (port and path).
    - **Folders:** where the app goes (recommended `C:\HTA\app\`, fixed across updates) and where the task data goes (recommended `C:\HTA\data\`, kept apart from the app so updates never touch it).
    - **Server type:** PowerShell script (recommended) / Python / single-file server program. Ideally it checks which ones work on this PC and preselects the first that does.
    - **Auto-start method:** Startup-folder shortcut, hidden (recommended) / Task Scheduler at log-on / an "HTA" shortcut that starts the server and opens the app.
- **Other settings Claude recommends making customizable:**
    - Listen only on this PC (127.0.0.1): on (recommended; off would expose the tasks to the network).
    - Browser: Chrome / Edge (Chromium-based, needed for local folders), detected.
    - Create desktop and Start-menu shortcuts: yes.
    - Open the app and install it as an app at the end: yes.
    - **Update mode:** re-running setup with a newer pack replaces only the app folder (never `data`), after a backup of the old app folder.
    - Uninstall: removes the auto-start, the shortcuts and the app folder, never `data`.
    - A log file of what setup did (for troubleshooting at work).
    - A port check: if 8001 is taken, suggest the next free one.
- **Form:** a guided script (PowerShell with prompts, Enter keeps the prefilled value), or a small form. It ships in the work pack, documented in `START-HERE.md`.
- **Sharing:** coworkers run the same setup and change only what they need.
- **When to build (Geoff):** "Don't do this yet… make this the last thing you do before packaging the next" work pack. So it's built and tested as the **final step before the next work pack** is made. It is not built now.

**More setup-tool requirements (Geoff, 2026-11-11):**
- "stays the same across updates" should be a **warning** in the setup app. Changing the app folder or the URL after installing loses Chrome's remembered folder permission and the installed app; setup says so whenever those two are edited, or differ from a previous install.
- "the setup app should either be able to set everything up or give instructions on how to setup what the app cannot". Every step either runs automatically or, if it can't (blocked script, no Python, a Chrome prompt only the user can click, an IT approval), prints **numbered manual instructions** for that step. It ends with a checklist of what's done and what's left.

**Work pack always includes a Markdown file for the work Claude Code CLI (Geoff, 2026-11-11):** "the install package you give me should always include a md file for my work claude code cli to read so it can help me manage and use the HTA". The pack already carries a work-PC `CLAUDE.md` (from `docs/work-pack/*.template.md`). Make it a **required, checked part of every pack**:
- `make_work_pack.py` fails without it.
- It covers the task-file format, how to run, update and repair the setup, the data-folder rules (never touch `data` without asking), the server/auto-start troubleshooting, and the coordination channel below.

**Coordinating the work CLI with the personal CLI (Geoff: "not sure how to make this happen, think up some ideas"):**
The two machines share no folder or account today. The rule throughout: **only app feedback and build notes cross over, never work task content or employer names** (rule 12).
- **A. Carry a file (exists today).** The work CLI writes `HTA-feedback.md` (items `F-YYYYMMDD-N`), and Geoff brings it home. The personal CLI turns it into spec items and answers in the next pack's notes.
    - Pros: no accounts, works on any locked-down PC.
    - Cons: manual; one round trip per pack.
- **B. A private GitHub "bridge" repository** (e.g. `gvd1024/hta-bridge`, private) as a mailbox: `inbox-home/` and `inbox-work/` Markdown messages. Each CLI reads and writes through `gh` or git, and a message is moved to `done/` when handled. The personal CLI checks it at session start, like the Feedback review; the work CLI does the same.
    - Pros: near real-time; history kept; both sides automated.
    - Cons: needs GitHub access and a login on the work PC (company policy); must stay private and free of work content.
- **C. GitHub Issues on the public repo** for bugs and feature requests from work.
    - Pros: built in.
    - Cons: public, so only generic wording is allowed; easy to leak something by mistake.
- **D. Email to self** with a fixed subject (the personal side reads it through the Gmail connector).
    - Pros: no new accounts.
    - Cons: messy to parse; the work email policy may forbid it.
- **E. A shared notes doc** (e.g. a Claude Doc, if available on both).
    - Pros: easy to read.
    - Cons: depends on that tool being allowed at work.

**Recommendation:** B, if GitHub works on the work PC (Geoff can reach github.io), with A as the fallback that always works. Both CLIs get the same message format, and the work `CLAUDE.md` and this repo's `CLAUDE.md` describe the check-at-start routine.

**Status:** Open (experiment done; Geoff to decide A/B/C/D and the stable address; the setup tool is approved as the last step before the next work pack).

---

## R2-21 — Home ↔ work: shuttle one package by email (two Claude instances)

**Asked** (Geoff, 2026-11-11): "Lets start out just shuttling a package back and forth with the code, applications, install app, html files, .md files, specs, everything."

**Roles (Geoff's words, condensed):**
1. **Only the home Claude** (personal PC) commits and pushes development work to GitHub.
2. **Either Claude may change the code, apps, etc.**, but every change is documented and coordinated with the other instance through `.md` files.
3. **Either Claude packages the latest version** into a single zip that extracts on the other PC. **No data in the zip.**
4. **The work Claude never uses actual data in feedback, and work data is never shared in any way.**
5. The package travels by email: personal email → work email → back to personal email.

This replaces the "mailbox" ideas in R2-20 for now (R2-20 coordination option A, extended to code).

**Problems Claude sees, and the proposed handling:**
- **P1. Both sides edit the same files.** A plain zip can't merge two sets of changes, so the newer zip would silently undo the other side's work.
  - **Handling:** the package carries the **git history as a `git bundle`** (one file) next to the extracted files.
  - The work Claude commits locally (never pushes) and packages its commits.
  - The home Claude fetches the bundle, merges (conflicts are shown, not lost), runs the tests, and pushes.
  - Each package names the build it was based on (`based-on`), so stale packages are detected.
  - Simple rule for the start: **only one side changes code at a time**; the package is the baton.
- **P2. Email filters.** Work email often blocks or strips `.zip` attachments, or ones containing `.html`, `.js` or `.ps1`.
  - **Handling:** test once with a small pack. Fallbacks: rename to `.zip.txt`, a password-protected zip, or a OneDrive/Drive link instead of an attachment.
- **P3. Company policy (data-loss prevention).** Sending files from work email to a personal address can be flagged or forbidden, even when it's only Geoff's own code.
  - **Handling:** Geoff checks the policy. The package must never contain anything from work, so that it's clean if reviewed.
- **P4. Accidental data in the zip.** Task files, `_todo.json`, `.trash`, the device copy, logs, `private/`, backups, the feedback ledger.
  - **Handling:** the packager builds from an **allow-list** (app, tools, tests, docs, specs), never from a whole folder.
  - It refuses any `.md` with task frontmatter outside test fixtures, and any path named `data`, `.trash` or `private`.
  - It **scans for blocked words**: the home side scans for Geoff's personal info; the work side keeps its own local list (the employer name, work paths), which is never committed or shipped.
- **P5. Feedback without real data.** The work Claude writes feedback with **made-up examples** ("a task with 3 subtasks"), never real titles or text, and no screenshots of real tasks.
- **P6. Build names.** Work-side builds use their own suffix (e.g. `2026-11-12w1`) so they never clash with home builds; the home Claude assigns the final build number on merge.
- **P7. Integrity.** The package keeps `SHA256SUMS.txt`, checked by the receiving side before use (it carries scripts that run, e.g. setup).
- **P8. Instructions travel too.** The package contains a work-side `CLAUDE.md` and a home-side guide, so whichever Claude opens it knows the roles and routine.

**Package contents (both directions):**
- the full code tree, apps, setup tool (R2-20), tools, tests, specs, docs
- `git bundle` (P1), `SHA256SUMS.txt`
- `HANDOFF-<from>-<date>.md`: what changed, why, what was tested, open questions, `based-on` build
- the running coordination log `docs/coordination/LOG.md`: one entry per hand-off, appended by each side
- **never** any data (P4)

**Routine when a package arrives:**
1. Check the sums.
2. Read the hand-off and the log.
3. Merge the bundle (home: merge, test, push; work: fast-forward the local copy).
4. Act on the open questions.

**Status:** Decided by Geoff (roles); the process and P1–P8 handling are to be confirmed. Built together with the R2-20 setup tool before the next work pack.

---

## Agent rounds (designer/tester, 2026-10-23)
An automated tester agent tests the app and writes a report; a designer agent fixes what it finds. Work happens on the `agent-rounds` branch (not `main`). Findings are numbered **T1-n** (round 1). Rule: data safety first; nothing that changes how the app looks or behaves beyond what the specs already decide is built without Geoff.

**Round 1 — fixed (build 2026-10-23b, test group `agentr1`):**
| # | Finding | Fix |
|---|---|---|
| T1-1 (critical) | Editing during the device-copy start-up window could silently drop another device's edit | A full load now treats the open editor like the change check does: an untouched editor is refilled; an edited one keeps the version it started from, shows the banner, and Save gets the conflict dialog |
| T1-2 | Saving from the editor re-formatted the whole body (`- [ ]` → `* [ ]`, escapes, indents) even when only a field changed | An untouched body is written back byte for byte |
| T1-3 | Local-folder device copy keyed by the folder's name, so another folder named `data` showed the first folder's tasks | Each picked folder gets its own id (matched with `isSameEntry`); the old name-only copies are dropped |
| T1-4 | A recurring task with an unreadable `due` wrote `due: NaN-NaN-NaN` | `due` must be a real `YYYY-MM-DD` date, else ⚠ and kept; such a task checks off normally (no roll-forward); saving other fields keeps it |
| T1-5 | CRLF files: checklist lines not recognized (no Check all dialog, no promote list) | Files are read as LF and written back in their own line endings |
| T1-7 | The Today view didn't roll over at midnight | Redraws when the date changes (checked every minute and on return to the app) |
| T1-8 | Sign out left every task file in the browser's device copy | Sign out deletes that account's copy |
| T1-10 | Today/Tmrw buttons and the Upcoming/Overdue headers were under 44 px (R1-12 #8) | Headers are 44 px; the compact buttons keep their look with a 44 px tap area |
| T1-11 | Titles not reachable by keyboard; dialogs not announced | Titles are focusable (Enter/Space opens); dialogs have `role=dialog`/`aria-modal`, take focus (never while typing) and return it on close |

**Round 1 — for Geoff to decide:**
- **T1-6** `monthly` from the 29th–31st (and `yearly` from Feb 29) drifts to the 28th for good, because each roll-forward re-anchors on the new due date. *Rec.:* when such a task rolls forward, write the intent into the file (`monthly` → `monthly on day 31`); for `yearly` on Feb 29, return to Feb 29 in leap years.
- **T1-9** Saving drops YAML comments and moves unknown keys below the known ones (values are kept). *Rec.:* update only the changed lines of the frontmatter in place, so comments and key order survive; until then, note in CLAUDE.md that the app normalizes them.
- **T1-12** Today view rows show no date. *Rec.:* a small muted date on Upcoming and Overdue rows (matches the Feedback item *List view*).
- **T1-13** List-picker counts include hidden subtasks (Home 9 vs 7 rows). *Rec.:* count top-level open tasks.
- **T1-14** `_todo.json` format isn't checked, and saving relabels a newer format as 3. *Rec.:* if `format` > the app's, open read-only with a banner and never write `_todo.json`; do it before R2-5.
- **T1-15** The PC view is the phone layout stretched wide. *Rec.:* cap the content width (~760 px) first; extra PC info later.
- **Also from T1-2:** when the body *is* edited in the Formatted editor, it still re-formats Markdown (`*` bullets, escapes). *Rec.:* either default new devices to Raw mode or restore the original list marker after editing.
- **Also from T1-8:** copies for folders or accounts no longer used are never cleaned up. *Rec.:* drop copies unused for 30 days.

**Round 2 — fixed (build 2026-10-24a, test group `agentr2`):** the tester re-tested every round-1 fix as fixed.
| # | Finding | Fix |
|---|---|---|
| T2-1 (major) | With the task open (PC side panel), Check all / Recycle / Copy from its row, then a notes edit + Save, wrote the old notes back: done but unchecked, silently | After the app changes the open task, a clean drawer is refilled (status, date, notes). Undo waits while the editor has unsaved edits. (Check-off already did.) |
| T2-2 | After T1-4, an unreadable `due` couldn't be removed in the editor | The bad value is kept only while the Due field is untouched; using the field (e.g. clearing it) replaces it |
| T2-3 | After *Keep both* on a file deleted elsewhere, the editor carried on editing the conflict copy under the original's name | The editor closes; the toast names the saved copy |
| T2-4 | A new or cleared device showed an empty list until every file had downloaded | A "Downloading your tasks to this device… n / total" line until the first download finishes |
| T2-5 | Demote (keep) left the archived task's `list` different from its new parent's | The archived task takes the target's list |

**Round 2 — for Geoff to decide:**
- **T2-4, further:** draw tasks as they arrive during the first download (faster to see on a phone with 1,000+ tasks), with actions enabled only once a task's file and its subtasks are in. Not built: acting on a half-loaded list (missing subtasks, missing `_todo.json`) is a data-safety risk, so it needs its own design.
- **Sign out vs. the device copy (from T1-8):** Sign out now deletes this account's copy, so the next sign-in downloads everything again (the progress line above shows it). The tradeoff is privacy (nothing left in the browser, important on a shared or work PC) vs. a slow first start (stress: ~20 s per 1,000 tasks). *Rec.:* keep deleting (sign-out is rare and usually means "leave nothing behind"); optionally add a "Keep this device's copy" tick box to the sign-out step later.

**Round 3 — fixed (build 2026-10-24b, test group `agentr3`).** The tester's verdict on 2026-10-24a: safe to merge for daily use, nothing must-fix; every T1/T2 data-safety fix held.
| # | Finding | Fix |
|---|---|---|
| T3-1 | Typing in the open editor while a Check-all save was still in flight, then Save, reverted the checkmarks. The banner promised "Save will ask", but it didn't | While the "changed elsewhere" banner is up, Save always goes through the conflict dialog (*Use their version / Overwrite with mine / Keep both*) |
| T3-2 | During the first download, menu actions replaced the progress line with "No tasks…", quick-add came on (a task added then stayed hidden until the next check) and the list picker was empty | Until the first download finishes, the list keeps the progress line, quick-add stays off and the list picker says it's still downloading |

**Decisions waiting for Geoff (all agent rounds, consolidated):**
| # | Item | Recommendation |
|---|---|---|
| T1-14 | `_todo.json` format isn't checked; saving relabels a newer format as 3 | Open read-only with a banner when `format` > the app's; never write `_todo.json` then. **Do before R2-5** (data safety) |
| T1-9 | Saving drops YAML comments and moves unknown keys below the known ones | Patch only the changed frontmatter lines in place |
| T1-2 (rest) | Editing notes in the Formatted editor re-formats Markdown (`*` bullets, escapes) | Restore the original list marker after editing, or default new devices to Raw |
| T1-6 | `monthly` from the 29th–31st and `yearly` from Feb 29 drift to the 28th | On roll-forward, write the intent into the phrase (`monthly on day 31`); Feb 29 in leap years |
| T3-3 | Phone editor: the notes get only ~¼ of the screen (fields above, the promote list below); Geoff's own Feedback item *Edit task screen* asks for a full-screen notes box | Phones: fields behind a collapsible "Details" row, promote moved into a per-line menu, notes fill the rest. Take it with that Feedback item |
| T1-12 | Today view rows show no date | A small muted date on Upcoming and Overdue rows (also in Feedback *List view*) |
| T1-13 | List-picker counts include hidden subtasks | Count top-level open tasks |
| T1-15 | The PC view is the phone layout stretched wide | Cap the content width (~760 px) first |
| T2-4 (rest) | First download: tasks appear only when every file is in | Draw rows read-only as they arrive; enable actions when the load finishes |
| T1-8 (rest) | Sign out deletes the device copy, so the next sign-in downloads everything again | Keep it (privacy); optionally a "Keep this device's copy" tick box |
| T1-8 (rest) | Copies for folders or accounts no longer used are never cleaned up | Drop copies unused for 30 days |

---

## Decision log

| Date | Item | Decision | Notes |
|---|---|---|---|
| 2026-11-11 | R2-21 | **Roles decided (Geoff):** only home pushes to GitHub; either side may change code, documented in .md; either side packages one zip, no data; work data never shared; email shuttle | Process P1–P8 to confirm |
| 2026-11-11 | R2-20 | **Added (Open):** experiment showed an installed app at a web address reopens the local folder with no Reconnect; options A–D and sharing notes | Not approved for build |
| 2026-11-09 | R2-19 | **Added (Open):** a way to hide the inline "Add subtask…" lines; options A–D | Not approved for build |
| 2026-11-09 | R2-18 | **Added (Open):** busy indicator while files are being changed; options A–D | Not approved for build |
| 2026-11-09 | R2-17 | **Added (Open):** Geoff to review the repeat options; month-end drift of a plain `monthly`/`yearly` recorded with options A–D | Not approved for build |
| 2026-11-09 | R2-16 | No visible hint line on phones (Geoff) | — |
| 2026-11-09 | R2-16 | **Added and built:** tooltips on the repeat "Next date" choices | On the folder branch |
| 2026-11-08 | R2-5 | **Folder build approved** ("yes, start the folder build") **and built** (2026-11-08b, data format 4) | 725 checks pass; migration tool tried on a copy of the real data |
| 2026-11-08 | R2-5 | **Decisions 9–16:** new tasks → / (root); folders: create, rename, delete-if-empty; a vanished folder → warn and explain; format check first as its own build; migration by Claude's script (no in-app converter); flat folders read-only in the folder build; shared-with-me folders out; work PC starts fresh | Step 0 (format check) built as 2026-11-08a |
| 2026-11-08 | R2-5 | **Implementation decisions 1–8:** one level (tree-ready); List → Folder everywhere; no folder field (path is the truth, `list:` removed); same-folder rule enforced; subtask alone → Cancel / top-level there; left behind → ask, one tap; top = "/ (root)", no Home/Inbox; folder-name rules | Real folder cleaned: 516 test files deleted (backup kept); 42 tasks in 3 lists remain |
| 2026-11-07 | R2-11–15 | **Verified on the phone** (keyboard Enter in the add line and the editor, due ✕, ↑ ↓ ● tap size) | |
| 2026-11-07 | R2-11–15 | **Verified on PC and merged to `main`** (build 2026-11-07c) at Geoff's request ("it all looks good merge") | Phone check passed the same day |
| 2026-11-07 | R2-11–15 | **Approved and built** as one build (2026-11-07c, branch `r2-11-fast-entry`); R2-15 added (Delete all readable). Geoff: the phone keeps the build in Settings only; the 500 bulk-test tasks stay (for performance); the Feedback review waits | 627 checks pass |
| 2026-11-07 | R2-11 | **C (both)**: editor Enter chains new siblings (parent + list only; empty Enter stops); Enter on an existing task = Save & close; inline "+ Add subtask…" line with ⤢; ⋯ → Add subtask opens it | Not yet approved for build |
| 2026-11-07 | R2-12 | **A**: Save & close subdued until a change, still closes | Not yet approved for build |
| 2026-11-07 | R2-13 | **A + B**: ✕ next to Due; "No date" in Change due date… | Not yet approved for build |
| 2026-11-07 | R2-14 | **↑ ↓ ●** from the due date; ● hidden on today rows | Not yet approved for build |
| 2026-11-07 | R2-10 | **A decided and approved** (the plain build in the header; version in Settings) | Built as 2026-11-07b |
| 2026-11-07 | R2-8 | **Restore follow-up verified on PC and merged to `main`** (build 2026-11-07a) | |
| 2026-11-07 | R2-8 | **Delete/restore speed:** options A (levels in parallel), B (a real OneDrive move; Claude recommends), C (batching) recorded; **no action** until Geoff finds it unacceptable | Files' content is never changed; a restore is a new OneDrive item |
| 2026-11-07 | R2-8 | **Restore follow-up: A + "+ N subtasks" note decided and approved for build**; subtasks deleted separately are included (marked); a subtask whose parent is trashed asks to restore the parent too | Built as 2026-11-07a on branch `r2-8-restore-tree` |
| 2026-11-07 | R2-8 | **Phase 1 verified on the phone** | |
| 2026-11-07 | R2-8 | **Phase 1 verified on PC (all 7 tests) and merged to `main`** at Geoff's request ("yes, merge it") | Phone check on the live app next |
| 2026-10-31 | R2-9 | **Added** (Alexa voice capture); options 1, 2a–2c pitched; nothing decided | IFTTT has no Alexa trigger (checked); Alexa list API withdrawn |
| 2026-11-01 | R2-8 | **Review fixes (build 2026-11-01b):** hostile-text tests for the new dialogs; armed Check all keeps its colour. Next: Geoff tests on the copy folder, then merge on his OK | |
| 2026-11-01 | R2-8 | **Phase 1 built on branch r2-8-phase1, awaiting review** (build 2026-11-01a; 557 checks pass) | Not merged to `main`; Geoff approves the merge |
| 2026-10-31 | R2-8 | **Order: option 3 (split). Phase 1 approved for build**; Phase 2 = folders + Deleted B + Hidden A | Folders change Deleted B and Hidden A a lot; the rest not, or little |
| 2026-10-31 | R2-5 | **B decided** (the folder is the list). Additions: rename List → Folder; subtasks must share the parent's folder (recommended); consider dropping `list:` from the frontmatter (leaning remove); a Move-to-folder UI. Gate: full implementation discussion first | Storage: files stay the source of truth (no database) |
| 2026-10-31 | R2-8 | **Long-term reviewed:** nothing added except a note to revisit a local git history when AI management starts | |
| 2026-10-31 | R2-8 | **Moving tasks in: deferred** until the import from SP and To Do is discussed (plan and Q1–Q7 kept in the spec) | |
| 2026-10-31 | R2-8 | **Hidden: A (Needs attention), C (search banner), D (overdue count badge; Overdue stays collapsed) decided**; B, E, F not chosen | |
| 2026-10-31 | R2-8 | **Checked off by mistake: D decided** (Check all needs a second tap when there are subtasks or checklist lines); A–C, E–G not chosen | |
| 2026-10-31 | R2-8 | **Overwritten: A, B, C decided** (diff in conflict dialog, losing version to trash, auto-saved drafts); D, E, F not chosen | |
| 2026-10-31 | R2-8 | Added (data-safety review). **Deleted: A, B, C, D decided**; E (soft delete) not chosen | Geoff has Microsoft 365 Family (Files Restore) |
| 2026-10-31 | R2-6 | **Confirm-the-theory logging, sign-in C, editor layout fix + ⤢ bigger notes approved and built** (build 2026-10-31a); A kept; Chrome's mode can't be set by a page | Redirect bridge was missing, so background renewal never worked |
| 2026-10-24 | R2-6 | **A approved and built** (build 2026-10-24c): "touch + nothing hovers" counts as touch-only | From Geoff's diagnostics: his phone reports a fine pointer; Chrome site settings clean |
| 2026-10-24 | Agent rounds | **Merged to main** at Geoff's request; Geoff's PC checks (device copy, banner/conflict dialog, Check all + Undo, sign-out, Clear device copy, keyboard) all passed | Phone pass pending |
| 2026-10-23 | R2-7 | **A approved and built** (build 2026-10-23a): device copy + change-only sync, source-swappable | OneDrive limit ~25–40× (PC), ~7–10× (phone) |
| 2026-10-21 | R2-6 | **Step 1 approved and built** (build 2026-10-21c): diagnostics in Settings | Fix follows Geoff's diagnostics paste |
| 2026-10-21 | R2-4 | **Approved (B) and built** (build 2026-10-21b): next to the build folder, default name `data`; OneDrive default stays `HTML-ToDo-App` | Awaiting Geoff's check |
| 2026-10-20 | R2-3 | **Approved and built** (build 2026-10-20c): details 1–4 as recommended | Awaiting Geoff's check |
| 2026-10-20 | R2-3 | **Decided:** option B plus a tappable list chip and date chip (default Today; other dates or no date) on the quick-add line | Details 1–4 to confirm; not yet approved for build |
| 2026-10-20 | R2-2 | **Built** (build 2026-10-20b): Today view replaces By due date; Upcoming/Today/Overdue, Today/Tmrw buttons, Change due date… | Awaiting Geoff's check |
| 2026-10-20 | R2-1 | **Built** (build 2026-10-20a): engine, Recycle/Copy check-off, editor Repeat controls, ↻, data format 3. Skip-missed corrected to "after today" | Awaiting Geoff's check |
| 2026-10-20 | R2-1, R2-2 | **Approved for build.** R2-2: time runs upward (Upcoming furthest-first with "+ N later" at the very top; Overdue most-recent-first); Today stays put when Upcoming expands | Building |
| 2026-10-20 | R2-2 | Upcoming = next 7 days, plus a "+ N later" row to reveal the rest; collapse defaults reset per app start (may change later) | Confirmed |
| 2026-10-20 | R2-2 | **Decided:** sections Upcoming (collapsed) / Today (fixed open) / Overdue (collapsed), with counts; one-tap Today/Tomorrow per section + ⋯ Change due date…; no list labels; ↻ for recurring; undated hidden; last-used view kept. Assumed: Upcoming = all future; collapse resets per app start | Not yet approved for build |
| 2026-10-20 | R2-1 | **Decided:** plain-English `repeat:`; modes **Recycle** (same file, reset everything, no log) and **Copy** (original completed as a normal task, copy carries the series: new id, shared `series:`, name `<slug>-YYYYMMDD.md`, fresh subtasks); next date per task: **Skip missed** (default) / **Catch up** / **From completion**; Undo; data format 3 | Not yet approved for build |
| 2026-10-20 | — | Round 2 opened with R2-1 (recurring tasks) and R2-2 (Today view), at Geoff's request | Discussing |

## Change history of this spec
- 2026-11-11 — v50: R2-21 (home↔work package shuttle, roles, problems P1–P8) added.
- 2026-11-11 — v47: R2-20 (work PC without Reconnect; sharing with coworkers) added, Open.
- 2026-11-11 — v48: R2-20 option B details and the setup tool (to build last, before the next work pack).
- 2026-11-11 — v49: R2-20 setup warnings + manual-step instructions; work CLI md always in the pack; work↔home CLI coordination options A–E.
- 2026-11-11 — v46: R2-5 bug from W6 (Explorer move in a local folder split the family's ids) fixed in 2026-11-11a.
- 2026-11-09 — v45: R2-19 (hide the Add subtask lines) added, Open.
- 2026-11-09 — v44: R2-18 (busy indicator while files change) added, Open.
- 2026-11-09 — v43: R2-17 (review repeat options; month-end drift) added, Open. R2-16 phone-line decision logged.
- 2026-11-09 — v42: R2-16 (repeat Next date tooltips) added and built.
- 2026-11-08 — v41: R2-5 folder build (format 4) built: storage, UI, rules, migration tool, tests.
- 2026-11-08 — v40: R2-5 decisions 9–16; Step 0 (data-format check) approved and built (2026-11-08a).
- 2026-11-08 — v39: R2-5 implementation discussion started (decisions 1–8); real-folder cleanup recorded.
- 2026-11-07 — v38: R2-11 to R2-15 verified on the phone.
- 2026-11-07 — v37: R2-11 to R2-15 verified on PC and merged (2026-11-07c).
- 2026-11-07 — v36: R2-11 to R2-14 approved and built; R2-15 (Delete all readable) added and built (build 2026-11-07c).
- 2026-11-07 — v35: R2-11 to R2-14 added and decided (fast entry, Save & close subdued, clear due date, Today arrows).
- 2026-11-07 — v34: R2-5 note: the data-format check doesn't exist yet and must be built before format 4.
- 2026-11-07 — v33: R2-10 added and built (build number in the header).
- 2026-11-07 — v32: R2-8 restore follow-up verified on PC and merged (2026-11-07a).
- 2026-11-07 — v31: R2-8 delete/restore speed options A–C recorded (B recommended), parked by Geoff.
- 2026-11-07 — v30: R2-8 Phase 1 verified on the phone; restore follow-up (restore with subtasks at any depth, parent question) decided, approved and built (2026-11-07a).
- 2026-11-07 — v29: R2-8 Phase 1 verified on PC (Geoff's 7 tests on the copy folder) and merged to `main`.
- 2026-10-31 — v28: R2-9 added (add tasks by voice with Amazon Echo): constraints, two approaches with sweeper variants, recommendation, open questions.
- 2026-11-01 — v27: R2-8 Phase 1 review fixes (build 2026-11-01b): hostile-text tests for the new dialogs; the armed Check all is no longer red.
- 2026-11-01 — v26: R2-8 Phase 1 built (build 2026-11-01a, branch `r2-8-phase1`): trash + Recently deleted, demote/delete care, conflict diff, replaced versions kept, auto-saved drafts, Check all second tap, search bar, overdue badge.
- 2026-10-31 — v25: R2-8 build order (option 3) recorded; Phase 1 approved for build.
- 2026-10-31 — v24: R2-5 B decided, with cons, AI reasoning, Geoff's additions and an implementation gate; storage discussion recorded; R2-8 Long-term note (git history).
- 2026-10-31 — v23: R2-8 category 5 Moving tasks in deferred (plan and questions kept).
- 2026-10-31 — v22: R2-8 category 4 Hidden decided (A, C, D badge only).
- 2026-10-31 — v21: R2-8 category 3 Checked off by mistake decided (D, second tap).
- 2026-10-31 — v20: R2-8 category 2 Overwritten decided (A–C).
- 2026-10-31 — v19: R2-8 (data-safety review) added; category 1 Deleted decided (A–D).
- 2026-10-31 — v18: R2-6 follow-up: editor cut off in desktop mode, sign-in redirect as the likely cause; logging, sign-in C, editor fix and ⤢ built (build 2026-10-31a).
- 2026-10-24 — v17: R2-6 diagnostics analysed, A approved and built (build 2026-10-24c); Geoff's PC checks of the agent-round build recorded.
- 2026-10-24 — v16: Agent rounds, round 3 (T3-1, T3-2 fixed; T3-3 for Geoff) and a consolidated list of decisions waiting for Geoff (build 2026-10-24b).
- 2026-10-24 — v15: Agent rounds, round 2 (T2-1 … T2-5) fixed or listed for Geoff (build 2026-10-24a).
- 2026-10-23 — v14: Agent rounds section; round 1 (T1-1 … T1-15) fixed or listed for Geoff (build 2026-10-23b).
- 2026-10-23 — v13: R2-7 A built; stress results added.
- 2026-10-23 — v12: R2-7 (scale) added, with options A–H and an A/B/C comparison.
- 2026-10-21 — v11: R2-6 added (from the Feedback review); step 1 built.
- 2026-10-21 — v10: R2-5 (a folder per list, file-explorer model) captured for exploration.
- 2026-10-21 — v9: R2-4 approved (B, folder `data`) and built.
- 2026-10-21 — v8: R2-4 added (default local task folder next to the app); OneDrive default renamed to `HTML-ToDo-App`.
- 2026-10-20 — v7: R2-3 approved and built.
- 2026-10-20 — v6: R2-3 decided (B + list/date chips), details pitched.
- 2026-10-20 — v5: R2-3 (quick-add in the Today view) added as Open.
- 2026-10-20 — v4: R2-1 and R2-2 built.
- 2026-10-20 — v3: R2-2 decided.
- 2026-10-20 — v2: R2-1 decided (two modes, three next-date rules, YYYYMMDD copy names).
- 2026-10-20 — v1: R2-1 and R2-2 drafted with options and recommendations.
