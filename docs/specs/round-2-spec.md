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
| R2-4 | Default task folder next to the app | Open | **A:** the app shows the sibling folder's path to paste into the folder picker |
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

**Status:** Open.

---

## Decision log

| Date | Item | Decision | Notes |
|---|---|---|---|
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
- 2026-10-21 — v8: R2-4 added (default local task folder next to the app); OneDrive default renamed to `HTML-ToDo-App`.
- 2026-10-20 — v7: R2-3 approved and built.
- 2026-10-20 — v6: R2-3 decided (B + list/date chips), details pitched.
- 2026-10-20 — v5: R2-3 (quick-add in the Today view) added as Open.
- 2026-10-20 — v4: R2-1 and R2-2 built.
- 2026-10-20 — v3: R2-2 decided.
- 2026-10-20 — v2: R2-1 decided (two modes, three next-date rules, YYYYMMDD copy names).
- 2026-10-20 — v1: R2-1 and R2-2 drafted with options and recommendations.
