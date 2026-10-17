# HANDOFF — current state (updated 2026-10-17, after the overnight MVP build)

## Read in this order
1. `CLAUDE.md`: rules, file contract (data format 2), code map, testing.
2. This file: the current state and what's next.
3. `docs/specs/storage-spec.md`: the architecture (S-1 to S-12) and the **MVP build plan + build log (S-9)**.
4. `docs/specs/round-1-spec.md`: round-1 items. **R1-12** is the phone list view.
5. Optional background: `private/` (local only, git-ignored).

## Current state
| Thing | State |
|---|---|
| App `app/index.html` | **v0.2.0-dev**, data format 2. Built overnight 2026-10-17: S-9 Phases 0 (except 0.3), 1 and 2, plus a **Phase 3 first cut** (the R1-12 phone list view). OneDrive connector, sign-in with the automatic bounce, conflict dialog with Keep both. Live at `https://gvd1024.github.io/html-todo-app/app/`. `app/todo.html` redirects there. Restore point for v0.1.1: git tag `v0.1.1`. |
| Automated tests | `python tests/run_tests.py` → **119 checks pass** (store suite for all 3 connectors, phone list view, fake-OneDrive flows, sign-in bounce, draft restore, expired change feed, expired sign-in). Screenshots: `tests/screenshots/`. |
| **Blocker for real use** | **Azure redirect URI for the app isn't registered yet (S-9 step 0.3).** Until then, signing in on `/app/` ends in Microsoft error AADSTS50011. |
| OneDrive test folder `HTML-ToDo-App-Test` | Reseeded 2026-10-17: 18 varied test tasks plus `_todo.json` (format 2). Includes deliberate test cases: a long title, 2-level subtasks, done, active, bullet, none, a body checklist, an unknown key (`priority`), and an old status (`waiting`). `poc-test.md` removed. |
| Specs | storage-spec: S-2 to S-8 and S-10 to S-12 decided; S-9 decided, with a build log listing **10 assumptions to confirm**. round-1: R1-7 and R1-8 obsolete; R1-11 built; R1-12 first cut built. |
| OneDrive PoC `poc/` | v0.0.2. R1-10 Step 1: 4 of 5 pass; **sign-in persistence retest still pending** (see below). Kept as a reference and test tool. |
| Repository / Pages | `https://github.com/gvd1024/html-todo-app` (public, `main`), via the `gh` CLI (`C:\Program Files\GitHub CLI\gh.exe`, logged in as `gvd1024`, repo-local noreply identity). Pages serves `main`, root. |
| Azure registration | `HTML-ToDo-App PoC`, client ID `18f50dc2-e8ba-4b12-8735-1cf7d6c873cd`, in Geoff's free Azure "Default Directory". Redirect URIs so far: `/html-todo-app/poc/` only. |

## Next steps (Geoff), in order
- [ ] **1. Azure (about 1 minute, S-9 step 0.3):** portal.azure.com → App registrations → `HTML-ToDo-App PoC` → **Authentication** → under *Single-page application*, **Add URI**:
  - `https://gvd1024.github.io/html-todo-app/app/`
  - `http://localhost:8000/app/` (optional, for local testing)
  - → **Save**.
- [ ] **2. Phone:** open `https://gvd1024.github.io/html-todo-app/app/` in Chrome → **Sign in with Microsoft** → the **Home** list from the test folder should appear. Try it out:
  - Switch lists (tap the big name).
  - Check and uncheck items.
  - Open a task.
  - Change a prefix.
  - Quick-add.
  - Scroll the long title sideways (in Test List).
  - Expand **Plan the garden** with its badge.
- [ ] **3. PC:** the same address in Chrome. Edit something on one device and watch it appear on the other within about 10 s.
- [ ] **4. Review** the 10 assumptions in storage-spec S-9 → *Build log*, and the screenshots in `tests/screenshots/` (or just use the app). Tell Claude what to change.
- [ ] **5. Sign-in persistence retest** (pending since 2026-10-16, R1-10 finding 5): after Chrome has been fully closed for a while, open the app. Pass = Microsoft signs you back in **without typing your email or password** (the app bounces there automatically).
- [ ] **6. Approve the next phase** when ready: Phase 4 (checking/Undo/done-hiding/delete), then Phase 5 (long-press move).

## Next steps (Claude, only once Geoff asks)
- Fix whatever Geoff's phone and PC check turns up in Phases 2–3.
- Phase 4, then Phase 5, each only after approval (storage-spec S-9).
- Follow-ups parked: the spell-check setup for the CLI (Code Spell Checker + Ctrl+G external editor; verify how Claude Code picks the editor on Windows); the S-12 Claude-access tests for the other surfaces; the work-account test (R1-10); connecting the Super Productivity MCP to Claude Code.

## Key decisions (details in the specs)
- **OneDrive is the datastore** (personal now, work later). Test data only for builds and tests; current "real" tasks may be changed until the MVP runs, then they're protected (CLAUDE.md rule 10).
- The prototype uses the OneDrive web connection on **both** PC and phone (S-10 A; per-device choice later).
- Storage interface keyed by relative path with opaque versions (S-2); OneDrive `If-Match` on every write, plus **Keep both** (S-3); delta change detection with three rules (S-4); automatic sign-in bounce with fallback to the button (S-5).
- Phone list view (R1-12): one list at a time, one line per task, pinned prefix and ⋯, sideways scroll, subtask badges, quick-add; the board is retired.
- Contract: data format 2 adds `prefix` and `completed`; statuses are open / active / done / archived; unknown frontmatter is kept and flagged, never auto-changed.

## Known technical facts to carry forward
- **MSAL Browser 5.x** keeps its cache key in a *session* cookie, so a Chrome restart always loses the cached sign-in. Microsoft also caps SPA silent refresh at 24 h. Hence the automatic bounce (S-5).
- **Personal OneDrive** supports folder delta; **work OneDrive** only root delta, so `GraphStore` falls back to listing.
- **Microsoft checks the redirect URI only after the account step**, so a missing URI shows up as AADSTS50011 after you sign in.
- **File System Access API** works only in desktop Chrome and Edge.
- **Claude's access to OneDrive tasks:** through the synced folder `C:\Users\gvd10\OneDrive\HTML-ToDo-App-Test` (CLI test passed, S-12). Chat and Android surfaces need an MCP server (S-12 paths 2–3).
- **Hosting:** GitHub Pages; claude.ai artifact pages can't host the Microsoft sign-in.
