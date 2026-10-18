# HANDOFF — current state (updated 2026-10-18)

## Read in this order
1. `CLAUDE.md`: rules, file contract (data format 2), code map, testing.
2. This file: the current state and what's next. **If you're the Claude Code session on Geoff's WORK PC, go to "Work-account test" below.**
3. `docs/specs/storage-spec.md`: the architecture (S-1 to S-12) and the MVP build plan + build log (S-9).
4. `docs/specs/round-1-spec.md`: round-1 items (R1-4 text size, R1-12 phone list view, R1-13 home-screen app).
5. Optional background: `private/` (only on Geoff's home PC; local and git-ignored).

## Current state
| Thing | State |
|---|---|
| App `app/index.html` | **v0.2.0-dev**, data format 2, live at `https://gvd1024.github.io/html-todo-app/app/`. **In daily use on Geoff's phone and home PC** against personal OneDrive `HTML-ToDo-App-Test`. **Installed on the phone** as a home-screen app (R1-13: own window, no address bar). Restore point for v0.1.1: git tag `v0.1.1`. |
| Built since the MVP build | R1-4 text-size setting (100–175 %, phones default 125 %); shrink-to-fit list name; slimmer phone header (● and ⋯ at the right edge); R1-12 #15 in-app pull to refresh; R1-13 installable app (manifest, icons, no-cache service worker). |
| Verified by Geoff | S-9 Phase 2: phone and PC sign-in, live two-way sync in seconds, sign-in survives overnight (2026-10-17). R1-13 install (2026-10-18). |
| Automated tests | `python tests/run_tests.py` → **127 checks pass**. Screenshots: `tests/screenshots/`. |
| Specs | storage-spec: S-2 to S-12 decided; S-9 build log has **10 assumptions to confirm**. round-1: R1-4 built, R1-7/R1-8 obsolete, R1-11 built, R1-12 first cut built, R1-13 verified. |
| Azure registration | `HTML-ToDo-App PoC`, client ID `18f50dc2-e8ba-4b12-8735-1cf7d6c873cd`, in Geoff's free Azure "Default Directory" (personal). Account types: any organization + personal. SPA redirect URIs: `/html-todo-app/poc/`, `/html-todo-app/app/`. Azure shows a warning: *"End users cannot grant consent to newly registered multitenant apps without verified publishers"*, which is exactly what the work test checks. |
| Repository / Pages | `https://github.com/gvd1024/html-todo-app` (public, `main`). On the home PC: `gh` CLI logged in as `gvd1024`, repo-local noreply identity. Pages serves `main`, root. |

## Work-account test (R1-10) — today, on Geoff's WORK PC
**Goal:** find out whether Geoff's company allows this app to reach his **work** OneDrive. It's the main unknown for R1-10. The app already supports it in principle: the Azure registration accepts work accounts, and the folder is a setting.

**Rules for this test (for Geoff and for any Claude session on the work PC):**
- **Dummy data only.** Use a new, empty `HTML-ToDo-App-Test` folder in the work OneDrive and the app's sample tasks. No real work content.
- **If Microsoft asks for admin approval, STOP and screenshot.** Do **not** click "request approval" (it would send a request to IT). That screen is itself the answer.
- **Claude on the work PC must not read or modify anything in the work OneDrive except the dummy test folder,** and only if Geoff asks. Don't change company settings or install anything on the work PC without Geoff's explicit OK.
- **Phone: leave it alone today.** The installed app holds one account (personal) at a time; multiple locations come later (storage-spec S-6).

**Getting this repo on the work PC (Claude Code CLI):** the repo is public, so a read-only clone needs no login: `git clone https://github.com/gvd1024/html-todo-app` (into `C:\dev\github.com\gvd1024\html-todo-app\` if Geoff wants the same layout). **Don't push from the work PC** unless Geoff explicitly sets up the `gvd1024` GitHub login there. Instead, record results in a local, uncommitted file `work-test-results.md` and/or tell Geoff, who brings them back to the home session, where they get logged in round-1 R1-10.

**Steps (about 10 minutes):**
- [ ] **1. Test folder:** in the **work** OneDrive (website or File Explorer), create an **empty** top-level folder `HTML-ToDo-App-Test`.
- [ ] **2. Sign in:** open `https://gvd1024.github.io/html-todo-app/app/` in Edge or Chrome, then **Sign in with Microsoft** with the **work** account. **Screenshot what Microsoft shows:**
  - **(a) A permissions screen** ("HTML-ToDo-App PoC wants to… read and write your files", maybe marked unverified) → **Accept** → continue to step 3. Best case.
  - **(b) "Need admin approval"** → **stop** and screenshot. IT controls consent (likely, given the Azure warning).
  - **(c) "You can't get there from here", or a device/compliance message** → **stop** and screenshot. Conditional access blocks it.
  - **(d) Anything else** (an AADSTS error code, etc.) → screenshot, including the code.
- [ ] **3. If (a):** the app opens the work folder `HTML-ToDo-App-Test`. It's empty, so it offers **Add sample tasks** → click it (writes about 15 demo `.md` files plus `_todo.json`).
- [ ] **4. Quick checks:**
  - Check a task off; quick-add one; open one, edit and save.
  - In the **work OneDrive website**, open the folder and confirm the `.md` files exist and changed.
  - **Edit a file in the OneDrive website** (it can edit text files), then watch the app: does the change appear within about 10–15 s? This tests the **work-OneDrive fallback**. Folder delta isn't supported there, so `GraphStore` should switch to re-listing the folder. It's untested against real work OneDrive; if changes never appear, or the status icon turns red or ⚠, note it and screenshot.
  - Pull down to refresh: does it update?
- [ ] **5. Bring back:** the step-2 screenshot; if signed in, the results of steps 3–4 (what worked, roughly how long changes took); screenshots of anything odd.
- [ ] **6. Afterwards:** ⋯ → **Sign out** if the PC is shared. Delete the dummy folder whenever (deleted files go to the work OneDrive recycle bin).

**What the outcomes mean for R1-10:**
- **(a) + checks pass:** work OneDrive is technically and policy-wise possible for Geoff's own files. Next: the location list (S-6), so the phone can hold personal **and** work, and asking IT whether using a personal tool is acceptable (R1-10 blocker 3).
- **(b):** needs an IT admin to grant consent for this app (or a verified publisher). Next: decide whether to ask IT (R1-10 blockers 1 and 3).
- **(c):** company device rules block it. The phone (unmanaged) is probably blocked too. Next: options in R1-10 (B: work PC only via the synced folder, which the app also supports through Settings → local folder; C: a phone fallback).

## Next steps (Geoff), in order
- [ ] **1. Work-account test** (above).
- [ ] **2. Review** the 10 assumptions in storage-spec S-9 → *Build log* (or just keep using the app and report what feels off).
- [ ] **3. Approve Phase 4** when ready: check-off with 5 s Undo, done items hidden (+ Show done), the "Check all / Check only this" dialog, `completed:` dates, delete with confirm + Undo (subtasks included). Then Phase 5 (long-press move).
- [ ] Optional: prove sign-in persistence after a **forced** Chrome close (swipe it out of recents, wait, open the ToDo app).

## Next steps (Claude, only once Geoff asks)
- Log the work-test results in round-1 R1-10 (and adjust S-4/S-6 if the work fallback misbehaves).
- Phase 4, then Phase 5, each only after approval (storage-spec S-9).
- Small fixes queued: the grey horizontal scrollbar line above quick-add; `CLAUDE.md`'s "What this is" paragraph still describes the old board app.
- Parked follow-ups: spell-check setup for the CLI (Code Spell Checker + Ctrl+G external editor); S-12 Claude-access tests for the other surfaces; connecting the Super Productivity MCP to Claude Code.

## Key decisions (details in the specs)
- **OneDrive is the datastore** (personal now, work later). Builds and tests use test data; the current "real" tasks may be changed until the MVP runs, then they're protected (CLAUDE.md rule 10).
- The prototype uses the OneDrive web connection on **both** PC and phone (S-10 A; per-device choice later).
- Storage interface keyed by relative path with opaque versions (S-2); OneDrive `If-Match` on every write, plus **Keep both** (S-3); delta change detection with three rules, listing fallback on work OneDrive (S-4); automatic sign-in bounce with fallback to the button (S-5).
- Phone list view (R1-12): one list at a time, one line per task, pinned prefix and ⋯, sideways scroll, subtask badges, quick-add, pull to refresh; the board is retired. Text size is a per-device setting (R1-4). Installable as a home-screen app (R1-13).
- Contract: data format 2 adds `prefix` and `completed`; statuses are open / active / done / archived; unknown frontmatter is kept and flagged, never auto-changed.

## Known technical facts to carry forward
- **MSAL Browser 5.x** keeps its cache key in a *session* cookie, so a browser restart loses the cached sign-in; Microsoft also caps SPA silent refresh at 24 h. Hence the automatic bounce (S-5). With "Stay signed in", the bounce is invisible in practice.
- **Personal OneDrive** supports folder delta; **work OneDrive** only root delta, so `GraphStore` falls back to listing (any 400/403/501 from folder delta switches it). Not yet tested against real work OneDrive.
- **Microsoft checks the redirect URI only after the account step**, so a missing URI shows up as AADSTS50011 after you sign in.
- **File System Access API** works only in desktop Chrome and Edge.
- **Claude's access to OneDrive tasks:** through the synced folder `C:\Users\gvd10\OneDrive\HTML-ToDo-App-Test` on the home PC (CLI test passed, S-12). Chat and Android surfaces need an MCP server (S-12 paths 2–3).
- **Hosting:** GitHub Pages. The installed app's service worker caches nothing, so every launch loads the latest version from Pages.
