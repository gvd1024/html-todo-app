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
| R2-1 | Recurring tasks | Discussing | Readable `repeat:` phrases; roll the same file forward on completion; next date from the due date, skipping missed ones |
| R2-2 | Today view (rework "By due date") | Discussing | Overdue + Today at the top with quick **Today / Tomorrow** buttons; upcoming below |

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

**Acceptance criteria (draft):**
- Overdue and Today sections are correct by local date.
- The buttons change `due:` (conditional save) with Undo.
- Rows move between sections immediately.
- Works on phone (the buttons fit at 125–175 % text) and PC.

---

## Decision log

| Date | Item | Decision | Notes |
|---|---|---|---|
| 2026-10-20 | — | Round 2 opened with R2-1 (recurring tasks) and R2-2 (Today view), at Geoff's request | Discussing |

## Change history of this spec
- 2026-10-20 — v1: R2-1 and R2-2 drafted with options and recommendations.
