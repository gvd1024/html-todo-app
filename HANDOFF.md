# HANDOFF — current state (updated 2026-10-18)

## Read in this order
1. `CLAUDE.md`: rules, file contract (data format 2), code map, testing.
2. This file: the current state and what's next. **If you're the Claude Code session on Geoff's WORK PC, read "WORK PC — read this first" below.**
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

## WORK PC — read this first (for Geoff's work Claude Code session)
**Context (Geoff, 2026-10-18):**
- **AI at work is encouraged.** Geoff's leadership encourages using Claude on the codebase (bug fixes, features, improvements), **including access to personal drives and OneDrive**. So Claude helping with this app at work is in line with company direction. Still: only touch the task/test folders Geoff names.
- **Start local, not cloud.** Geoff would be fine using the app **only on the work PC, against a local or OneDrive-synced folder through the file system**, with no Microsoft sign-in. Phone access to work tasks is a nice-to-have for later. (Work apps on his phone live in a managed, partitioned work profile, run via a Microsoft app Geoff believes is called "Hub" — probably Intune's Company Portal or Microsoft Edge with app protection. To be confirmed.)
- **No IS proposal yet.** First prove the conservative local setup.

### Plan: the most conservative way to run it at work (local-only, no sign-in)
**Verified 2026-10-18:** opened straight from disk (`file://…/app/index.html`), the app makes **no network requests at all** in any mode. MSAL only contacts Microsoft if Sign in is pressed. The browser's folder picker (File System Access API) works from disk in Chrome and Edge.

**Steps:**
1. **Get a pinned copy onto the work PC** (no hosting, no auto-updates). Any one of:
   - **(a)** Download the repo ZIP once from GitHub ("Code → Download ZIP", or a tagged release), then check the SHA-256 checksums (see `SECURITY-REVIEW.md`).
   - **(b)** `git clone https://github.com/gvd1024/html-todo-app` (read-only, no login).
   - **(c)** Email a ZIP to yourself. **Caveat:** many corporate mail filters strip or quarantine `.html`/`.js` attachments or ZIPs containing them. If it arrives, verify the checksums.
   - Only the `app/` folder is needed (`index.html` plus `vendor/` plus `icons/`).
2. **Put it somewhere local,** e.g. `C:\Users\<you>\Apps\HTML-ToDo-App\` (not inside OneDrive, so it can't sync or auto-change).
3. **Make a test folder.** The most conservative choice is a plain local folder (e.g. `Documents\HTML-ToDo-App-Test`). Next step: a folder inside the **work OneDrive sync folder**, so tasks are backed up and visible in OneDrive (still no Graph and no sign-in, since OneDrive's own sync app moves the files).
4. **Open `app\index.html` in Edge or Chrome** (double-click, or drag into the browser) → ⋯ → **Settings** → **A local folder on this PC** → Apply → pick the test folder → allow edit access. An empty folder offers **Add sample tasks**.
5. **Each new browser session,** Chrome/Edge asks again for permission to the folder: click **Reconnect "<folder>"**. That's expected for local files.
6. **Optional:** create a desktop shortcut to the local `index.html`.

**Optional hardening, a "local edition" (proposed, NOT built; needs Geoff's OK):** a copy of the app with the MSAL library removed, the default set to *local folder*, and a Content Security Policy that **blocks all network access** (`connect-src 'none'`). The browser itself then guarantees nothing leaves the PC. It's the strongest statement for IS, and a small build.

**Known limits in local mode:** PC only (Chrome/Edge desktop); no phone; the conflict check uses modified time (weaker than OneDrive's `If-Match`, fine for one person); polling every ~5 s picks up edits made elsewhere (Claude, other PCs via OneDrive sync).

### ⚠ Project risk #1 for work: the Azure / Entra app registration
**Why it's a risk:** reaching **work** OneDrive through Microsoft Graph (needed for phone access, and for the web version without a synced folder) requires an app registration that the **company's tenant** accepts. Geoff may not be able to set that up himself.
- **The plan so far:** reuse the existing registration `HTML-ToDo-App PoC` (in Geoff's **personal** Azure "Default Directory", multitenant: any organization + personal accounts), and have Geoff consent with his work account.
- **Likely blocker:** Azure already warns *"End users cannot grant consent to newly registered multitenant apps without verified publishers"*. Most company tenants block that, or need admin approval.
- **If it manifests, ways around it (best first):**
  1. **Don't need it:** use local-folder mode on the work PC (the plan above). No registration and no consent. Covers the PC; no phone.
  2. **Register in the company tenant:** Geoff (if the tenant setting "Users can register applications" is on) or IT creates a **single-tenant** registration in the work Entra ID: SPA platform, redirect URI of wherever the app is hosted, least-privilege permission (row 3 below). The app needs only a different client ID (setting `todo.clientId`; a UI field can be added).
  3. **Admin consent:** IT grants tenant admin consent to the existing multitenant app for Geoff only. Less attractive to IS, since the app is owned outside the company.
  4. **Publisher verification:** requires a Microsoft Partner (MPN) ID. Unrealistic for a personal project.
  5. **Phone without Graph:** not really possible. An Intune-managed browser (Edge) opening a company-hosted copy still needs Graph (needs 2 or 3). Otherwise, view tasks in the OneDrive app as plain files.

### Work red flags and how Geoff plans to handle them (from the 2026-10-18 discussion)
| # | Red flag | Approach |
|---|---|---|
| 1 | AI touching work data | Leadership **encourages** Claude, including drives/OneDrive. Keep Claude to the folders Geoff names. |
| 2 | App registered in a personal tenant (unverified publisher) | **Avoid it initially:** local-folder mode needs no registration. Later: a company-tenant registration (see risk #1). |
| 3 | Permission too broad (`Files.ReadWrite` = the whole OneDrive) | **Local mode: no Graph permission at all.** If Graph is used later, restrict it: `Files.ReadWrite.AppFolder` (only `/Apps/<app>/`) or a selected-files permission. Personal use can be restricted too once Geoff uses the app for real. |
| 4 | Code served from a personal GitHub Pages site | **Don't rely on GitHub at runtime:** run a pinned, reviewed local copy from disk. GitHub (or email) is only a one-time download source. Later options: host on company infrastructure. |
| 5 | Work data on a personal phone | **PC-only to start.** Phone later only through what IS already allows (managed work profile / app protection). |
| 6 | Shadow IT / support | A single-user pilot; data stays plain `.md` files in Geoff's own folder or work OneDrive; nothing lost if stopped. |
| 7 | Unmaintained library (Toast UI Editor, last release 2023-02) | Pinned plus checksummed. If it becomes an issue: replace it with a maintained, permissively licensed (MIT/Apache) editor, or a dependency-free editor (plain text area plus preview), which Claude can write. |
| — | Security review | `SECURITY-REVIEW.md` (2026-10-18): no malicious code; only Microsoft destinations; findings F1–F6 with fixes (link guard, official MSAL build, CSP, least privilege, hosting). |

### Original work-account test (Graph sign-in) — later, optional
Only if Geoff wants to know whether the company blocks consent: open the hosted app, sign in with the work account, and **screenshot** the result. (a) a permissions screen → Accept; (b) "Need admin approval" → **stop, don't request it**; (c) a device/compliance block → stop. Dummy test folder only. Results go to round-1 R1-10.

## Next steps (Geoff), in order
- [ ] **1. Work PC, local-only setup** (above; most conservative: no sign-in, no network). Optional later: the Graph sign-in test.
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
