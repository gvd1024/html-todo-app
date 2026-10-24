# Stress test results (2026-10-23, build 2026-10-21c)

**Question (Geoff):** "find the border limit for the number of realistic small task files managed by the HTA … at what limit (how many tasks) performance begins to be what most developers would consider … unacceptable slowness or have other problems."

## Short answer
| How HTA is used | Becomes unacceptable at about | What breaks first |
|---|---|---|
| **OneDrive** (phone and PC, your normal setup) | **200–400 task files**, counting done ones | **Startup:** every file is downloaded one by one (6 at a time) on every app start. Over 4 s at ~200 files with a 120 ms network, ~400 with a fast 50 ms one |
| **Local folder on a PC** (work) | **~4,000–5,000** | Startup over 4 s; the background check every 5 s re-reads every file's details (22 % of the time at 5k) |
| **Phone, any storage, once loaded** | **~3,000** (spread over lists) · **~1,000 open in one list** | Check-off and quick-add take over 0.5 s, because every change redraws the whole list |
| **PC, once loaded** | **~10,000** (spread) · **~3,000–4,000 open in one list** | Same: full redraws |

**So for HTA as it's built today, the limit that matters is the OneDrive startup: a few hundred task files.** Your real folder has 34, which is fine (about 1 s). Done tasks count too, because every file is read at startup.

## Thresholds used (common developer standards)
- **Actions** (tap → screen updated), Google's INP: **≤ 200 ms good**, **> 500 ms poor**.
- **Startup:** **≤ 2.5 s good**, **> 4 s poor** (in the spirit of LCP).
- **Smoothness:** a frame slower than 50 ms is visible stutter.
- **Background work while idle:** more than ~5 % of the time is a cost; more than 20 % is poor (battery, fans, a slow PC). A screen freeze over 100 ms is poor.

## How it was measured
- `tests/stress.py` (Playwright + Chrome on Geoff's home PC) generates realistic task folders in the browser. Real data is never touched.
- **Shapes:**
    - **spread:** 10 lists weighted like real use, ~55 % done (hidden), 20 % subtasks, half with due dates, 3 % recurring. Bodies are 40 % empty, 40 % short notes, 15 % checklists, 5 % long (30–80 lines).
    - **onelist:** everything open in one list, the worst case.
- **Stores:**
    - `mem`: in memory, the pure app cost.
    - `opfs`: the local-folder store on the browser's private disk, standing in for a PC folder.
    - `net`: OneDrive's request pattern with a simulated delay per request.
- **Phone stand-in:** phone screen size plus Chrome's CPU slowdown ×4 (roughly a mid-range phone). Not a substitute for the real phone.
- **Actions timed:** startup, switching to the biggest list, Today view, search, check-off, quick-add, opening the editor, scrolling, and one idle background check. The times include two screen refreshes (~33 ms floor).
- Raw tables: `tests/stress-results/*.md` (and `.json`).

## Key numbers
**PC, local folder (opfs), spread:**

| Tasks | Startup | Switch list | Check-off | Quick-add | Background check (every 5 s) |
|---|---|---|---|---|---|
| 1,000 | 0.7 s | 35 ms | 34 ms | 33 ms | 0.23 s |
| 2,000 | 1.4 s | 59 ms | 50 ms | 45 ms | 0.45 s |
| 5,000 | **4.2 s** | 157 ms | 199 ms | 206 ms | **1.1 s** |
| 10,000 | 9.0 s | 382 ms | **623 ms** | **575 ms** | 2.6 s |
| 20,000 | 18.5 s | 1.3 s | 2.3 s | 2.3 s | 4.9 s (screen freezes ~0.5 s) |

**PC, in memory (app cost only), spread:** fine up to 5,000. At 10,000 check-off is 433 ms; at 20,000, 1.6 s; at 50,000, 13.7 s.

**Phone stand-in (×4 CPU), spread:**

| Tasks | Startup (local) | Switch list | Check-off | Quick-add |
|---|---|---|---|---|
| 1,000 | 1.7 s | 100 ms | 220 ms | 100 ms |
| 2,000 | 3.7 s | 151 ms | 354 ms | 184 ms |
| 5,000 | 8.6 s | 970 ms | **1.0 s** | **1.0 s** |
| 10,000 | 20 s | 1.5 s | 3.1 s | 1.6 s |

**Worst case, one list with every task open:**
- **PC:** check-off 217 ms at 2,000, 959 ms at 5,000.
- **Phone stand-in:** 717 ms at 1,000, 1.5 s at 2,000. Scrolling stutters from ~2,000 rows.

**OneDrive request pattern (startup only; each file is one request, 6 at a time):**

| Network delay per request | 100 files | 500 files | 1,000 files |
|---|---|---|---|
| 50 ms (fast Wi-Fi) | 1.2 s | 5.5 s | 10.8 s |
| 120 ms (typical) | 2.4 s | 11.0 s | 21.7 s |
| 250 ms (mobile data) | 5.0 s | 23.0 s | 45.5 s |

The real OneDrive delay wasn't measured; these delays are assumptions. Microsoft may also throttle thousands of quick requests.

## What held up well
- **The Today view** stays fast at every size (under 0.2 s on the PC even at 50,000), because Upcoming and Overdue start collapsed.
- **Opening the editor** doesn't depend on the number of tasks (~0.1 s PC, ~0.3 s phone stand-in).
- **Scrolling** is smooth up to a few thousand rows on screen.
- **Memory** stays small: ~20 MB at 10,000 tasks, ~100 MB at 50,000.
- **Nothing crashed**, even at 50,000.

## Why it slows down (root causes)
1. **OneDrive startup downloads every file, every time, 6 at a time, with no saved copy.** Cost = files × network delay.
2. **Every change redraws the whole list.** Each row also counts its subtasks by scanning all tasks, so the cost grows faster than the list.
3. **The local-folder background check re-reads every file's details every 5 s,** even when nothing changed. This is a plausible part of the work-PC slowdown, since that folder sits inside OneDrive's sync folder.

## Fix directions (for a spec item; not built)
- **Keep a local copy of the files** (in the browser's database) and download only files whose OneDrive version changed. OneDrive's change list gives every file's version in a few requests (200 per page). Startup would then be ~1–2 s for thousands of files, after the first time.
    - Smaller wins: more downloads at once, or Graph's `$batch` (20 files per request).
- **Draw only what changed,** and index subtasks by parent, so actions stay fast as lists grow. A "virtual list" that draws only the rows on screen would handle a very long single list.
- **Make the local-folder check cheaper:** check less often when idle or in the background, and only when the app is visible. Chrome's new folder-change notifications could replace polling where available.
- **Move old done tasks out of the live folder,** e.g. a yearly archive folder (the "done journal" idea). That keeps the file count down whatever else is done.

---

# After R2-7 A: device copy + change-only sync (2026-10-23, build 2026-10-23a)
**What changed:** each device keeps a copy of every file and OneDrive's change bookmark. A launch draws from the copy, then asks OneDrive what changed (one request) and downloads only those files. The **first launch on a new device** still downloads everything, once.

**Measured:** the same harness, plus a **second launch** (the everyday case). "Ready" = the copy is checked against OneDrive. Simulated OneDrive at 120 ms per request.

| Tasks | PC: on screen | PC: ready | PC: check-off | Phone stand-in: on screen | Phone: ready | Phone: check-off |
|---|---|---|---|---|---|---|
| 1,000 | 26 ms | 0.18 s (1 request) | 151 ms | 119 ms | 0.61 s | 434 ms |
| 2,000 | 53 ms | 0.23 s | 164 ms | 229 ms | 0.78 s | 470 ms |
| 5,000 | 157 ms | 0.39 s | 280 ms | 674 ms | 1.6 s | **1.3 s** |
| 10,000 | 390 ms | 0.85 s | **614 ms** | 1.9 s | 3.9 s | 3.0 s |
| 20,000 | 1.1 s | 2.3 s | 1.9 s | — | — | — |
| 50,000 | 6.5 s | 13 s | 11 s | — | — | — |

(Check-off includes the save to OneDrive, ~120 ms here.)

**Local folder (PC), second launch:** 1,000: 0.25 s · 5,000: 1.8 s · 10,000: 3.5 s · 20,000: 8.3 s (was 0.7 / 4.2 / 9.0 / 18.5 s). The **background check is unchanged** (A doesn't touch it): 1.1 s of every 5 s at 5,000 tasks, so that remains the local-folder limit.

## New limits (where it becomes unacceptable)
| Setup | Before A | After A | Gain | What limits it now |
|---|---|---|---|---|
| **OneDrive on the PC** | 200–400 | **~8,000–10,000** | **~25–40×** | Actions (full redraws): check-off over 0.5 s at ~10k |
| **OneDrive on the phone** | 200–400 | **~2,000–3,000** | **~7–10×** | Actions (full redraws): check-off ~0.5 s at 2k, 1.3 s at 5k. Startup is fine to ~10k |
| **Local folder on the PC** | ~4,000–5,000 | **~5,000** for the background check; startup is fine to ~10k | ~1× (startup ~2×) | The 5 s background check re-reads every file's details |

**Next bottlenecks:** R2-7 **B** (redraw only what changed) for OneDrive on both devices, and a cheaper background check for local folders.
