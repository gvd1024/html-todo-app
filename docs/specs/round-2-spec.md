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

## Decision log

| Date | Item | Decision | Notes |
|---|---|---|---|
| 2026-10-20 | R2-2 | **Built** (build 2026-10-20b): Today view replaces By due date; Upcoming/Today/Overdue, Today/Tmrw buttons, Change due date… | Awaiting Geoff's check |
| 2026-10-20 | R2-1 | **Built** (build 2026-10-20a): engine, Recycle/Copy check-off, editor Repeat controls, ↻, data format 3. Skip-missed corrected to "after today" | Awaiting Geoff's check |
| 2026-10-20 | R2-1, R2-2 | **Approved for build.** R2-2: time runs upward (Upcoming furthest-first with "+ N later" at the very top; Overdue most-recent-first); Today stays put when Upcoming expands | Building |
| 2026-10-20 | R2-2 | Upcoming = next 7 days, plus a "+ N later" row to reveal the rest; collapse defaults reset per app start (may change later) | Confirmed |
| 2026-10-20 | R2-2 | **Decided:** sections Upcoming (collapsed) / Today (fixed open) / Overdue (collapsed), with counts; one-tap Today/Tomorrow per section + ⋯ Change due date…; no list labels; ↻ for recurring; undated hidden; last-used view kept. Assumed: Upcoming = all future; collapse resets per app start | Not yet approved for build |
| 2026-10-20 | R2-1 | **Decided:** plain-English `repeat:`; modes **Recycle** (same file, reset everything, no log) and **Copy** (original completed as a normal task, copy carries the series: new id, shared `series:`, name `<slug>-YYYYMMDD.md`, fresh subtasks); next date per task: **Skip missed** (default) / **Catch up** / **From completion**; Undo; data format 3 | Not yet approved for build |
| 2026-10-20 | — | Round 2 opened with R2-1 (recurring tasks) and R2-2 (Today view), at Geoff's request | Discussing |

## Change history of this spec
- 2026-10-20 — v4: R2-1 and R2-2 built.
- 2026-10-20 — v3: R2-2 decided.
- 2026-10-20 — v2: R2-1 decided (two modes, three next-date rules, YYYYMMDD copy names).
- 2026-10-20 — v1: R2-1 and R2-2 drafted with options and recommendations.
