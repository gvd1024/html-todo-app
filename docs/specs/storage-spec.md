# HTML-ToDo-App — Storage Spec

| Field | Value |
|---|---|
| **Scope** | How the app loads, saves and watches task files in different places: demo data, a local folder, OneDrive (personal and work), and Google Drive. The architecture behind R1-9 (phone) and R1-10 (work OneDrive). |
| **Baseline** | App v0.1.1: two stores, `MemStore` and `FsStore`, in `app/todo.html`. PoC v0.0.2: Microsoft Graph proven on Android (see round-1 spec, R1-10 Step 1). |
| **Spec status** | Draft. Discussing; nothing approved for build. |
| **Last updated** | 2026-10-16 |

## Direction (Geoff, 2026-10-16)

> "My goal is to get a prototype working asap that I can start using right away... the one key factor is preserving the .md files on onedrive. So we will never test on real data only test data." … "I am commited to leveraging ms onedrive for the datastore since that is the solution I will try to get workign at my work." … "start with the most limiting aspects of setting up a html web app that works on both pc and android chrome while sharing the access to .md files."

- **OneDrive is the datastore.** Google Drive is out of the prototype path; its parts below are kept only as notes for later.
- **Test data only:** the OneDrive folder `HTML-ToDo-App-Test` (copies). Never point builds or tests at real task files.
- **Goal:** a usable prototype ASAP: the same task files from PC Chrome and Android Chrome.
- **Discussion order:** most limiting first, item by item.

## Ground rules

Same rules as the round specs: no code until Geoff approves; only named items get built. Each item moves through `Open → Discussing → Decided → Approved for build → Built → Verified`. Decisions go in the Decision log at the bottom.

## Summary

| # | Item | Status | Recommendation |
|---|---|---|---|
| S-1 | Where this design lives | Discussing | This separate spec; R1-9 and R1-10 point here |
| S-2 | Connector interface | **Decided** | A + D: the existing interface keyed by relative path, with an opaque version token |
| S-3 | Conflict safety per service | **Decided** | A + E: the strongest check per service (OneDrive `If-Match`), and a **Keep both** button |
| S-4 | Change detection | Open | B: a connector-specific watcher behind one `changes()` call |
| S-5 | Sign-in and staying signed in | **Decided** (confirm after the 2026-10-17 retest) | B (automatic redirect), with A (button) as fallback |
| S-6 | Locations and switching | Open | A: a saved list of locations in the browser |
| S-7 | Delete behavior | Open | A: recoverable deletes everywhere |
| S-8 | Caching and offline | Open | A: cache by version, read-only offline |
| S-9 | Build order | Open | OneDrive connector first, then Google Drive |
| S-11 | File and folder naming rules | **Decided** (rules); feature is future | One-way slug with dashes, plus Windows/OneDrive safety rules; `parent:` stays the hierarchy's source of truth |
| S-10 | How the PC reaches the files | **Decided** | A for the prototype (OneDrive web connection on PC and phone); pivot to C later |

---

## Background: what the app does today

All storage goes through one small object, `S.store`, with four methods. Everything else (parsing, the board, the editor, demote and promote) never touches storage directly.

| Method | `FsStore` (local folder) | Used by |
|---|---|---|
| `list()` → `[{name, mtime}]` | Folder entries, filtered to `.md` and `_todo.json` | `loadAll`, `poll` (every 4 s) |
| `read(name)` → `{text, mtime}` | Reads the file | `loadAll`, `poll`, `reloadOne` |
| `write(name, text, expected)` → `mtime` | If `expected` is set and the file's modified time differs, it throws `ConflictError`, which leads to the "File changed on disk" dialog | `saveTask`, `saveConfig` |
| `remove(name)` | Deletes the file | `removeTask` |

**The good news:** the app already has an interface with a conflict check, and the dual-access test (2026-10-15) proved it works across OneDrive sync. New services can plug into the same four methods.

**What doesn't fit yet:**
- Cloud services identify files by **ID**, not name, and Google Drive allows two files with the same name.
- Their version is an **eTag** or version number, not a modified time.
- Changes are found with a **cursor** (delta / changes), not by listing everything.
- They need **sign-in**.

## How the services compare

| | Local folder (`FsStore`) | OneDrive: Microsoft Graph | Google Drive API v3 |
|---|---|---|---|
| **Where it runs** | Desktop Chrome or Edge only | Any browser, including Android | Any browser, including Android |
| **Sign-in** | None (browser asks for folder permission) | MSAL.js, redirect flow (proven on Android) | Google Identity Services (GIS) token client. *Not yet tested on Android.* |
| **File identity** | Name | ID (names unique per folder) | ID (**names can repeat** in a folder) |
| **Version token** | Modified time | eTag | `version` number / `modifiedTime` |
| **Conditional save** | Check, then write (small race window) | **True**: `If-Match` → 412 (proven) | **None** in v3. Check, then write (race window). |
| **Create without overwriting** | Check, then create | `conflictBehavior=fail` → 409 | Not enforced. The app must check for the name first. |
| **Delete** | Permanent | Goes to the OneDrive recycle bin | Permanent, unless we set `trashed=true` (recoverable) |
| **Watch for changes** | List and compare | Delta query: any folder on personal OneDrive, **root only on work OneDrive** | `changes.list` with a page token (whole Drive; filter to our folder) |
| **Speed seen so far** | Instant | 0.35–2.6 s per call (PoC log) | Not tested yet |

---

## S-1 — Where this design lives

**Problem:** the storage design was spread across R1-9 and R1-10 in the round-1 spec. It affects both items and future rounds, so it needs one home. (HANDOFF listed this as a decision to make.)

**Options**
- **A — This separate spec**, with R1-9 and R1-10 linking here for the storage parts.
    - **Pros:** one place for the architecture; round specs stay about user-facing items.
    - **Cons:** one more file to keep in sync.
- **B — Keep it inside R1-9/R1-10.**
    - **Pros:** fewer files.
    - **Cons:** the design gets duplicated or split across two items; round-1 grows very long.

**Recommendation:** A.

**Decision:** —

---

## S-2 — Connector interface

**Problem:** one interface that the board can use without knowing which service is behind it.

**Options**
- **A — Keep the file-name interface; generalize the version token.** The four methods stay, keyed by file name. `mtime` becomes an opaque `version`: modified time for local files, eTag for OneDrive, `version` for Google Drive. Each cloud connector keeps a private name → ID map. Additions:
    - `create(name, text)`, which fails if the name already exists;
    - `remove(name, expected)`;
    - `changes()` (see S-4);
    - sign-in methods (see S-5);
    - a `caps` object describing what the service can guarantee, e.g. `{ trueConditionalWrite, recoverableDelete, watch: 'delta' | 'changes' | 'list' }`.
    - **Pros:** smallest change to the app; parsing, the board and demote/promote don't change; the file contract stays name-based, which matches how Claude and people see the files.
    - **Cons:** connectors must handle the name → ID map, including Google Drive's duplicate names (treated like today's `duplicate id` chip: shown, never silently merged).
- **B — Switch the whole app to IDs.**
    - **Pros:** matches cloud APIs exactly.
    - **Cons:** big change throughout the app; local folders have no IDs; breaks the "file name is the handle" idea in the contract.
- **C — Use a generic library** (for example a virtual file system package).
    - **Pros:** less code of our own.
    - **Cons:** lock-in and extra weight; no library covers MSAL + GIS + the File System Access API with true conditional writes.
- **D — Path-keyed (a variant of A).** Same as A, but the key is a relative path (`archive/old-task.md`) instead of a bare name. The prototype still uses a flat folder.
    - **Pros:** room for subfolders later (archive, attachments, per-list folders) with no interface change.
    - **Cons:** a little more connector code (walking subfolders), unused at first.
- **E — Task-level store.** Connectors deal in tasks (`getTasks`, `saveTask`) and parse files themselves.
    - **Pros:** could later sit on a database.
    - **Cons:** duplicated parsing per connector; moves away from plain `.md` as the truth; against the low-lock-in principle.
- **F — Local-first sync engine.** The app edits a browser-database copy; a background process syncs with OneDrive.
    - **Pros:** instant UI and full offline editing.
    - **Cons:** the biggest build; hard merge logic. It's S-8 option B, for a later round.

**Recommendation:** A + D. Sketch:

```js
// Every connector implements this. Version tokens are opaque strings or numbers; the app only compares them for equality.
interface Store {
  name: string;                 // shown in the header, e.g. "Personal · OneDrive"
  caps: { trueConditionalWrite: boolean, recoverableDelete: boolean, watch: 'delta'|'changes'|'list' };
  signIn?(): Promise<void>;     // cloud only (S-5)
  ensureSession?(): Promise<boolean>;
  list(): Promise<{name, version}[]>;
  read(name): Promise<{text, version}>;
  write(name, text, expected): Promise<version>;   // throws ConflictError on mismatch
  create(name, text): Promise<version>;            // throws ExistsError if taken
  remove(name, expected?): Promise<void>;          // ConflictError if changed since loaded
  changes(): Promise<{name, version, deleted?}[]>; // only what changed since the last call (S-4)
}
```

**Decision (Geoff, 2026-10-16):** **A + D.** Keep the existing store calls, keyed by **relative path** from the location's root folder, with an opaque `version` (eTag on OneDrive, modified time locally). Add `create`, `changes()`, sign-in methods and `caps`. The prototype uses a flat folder; paths allow subfolders later without an interface change.

**Implementation notes:**
- In the sketch, `name` means a relative path with `/` separators. The prototype's `list()` returns only the top level.
- The OneDrive connector keeps a private path → item-ID map, filled by `list()` and `changes()`. OneDrive names are unique per folder and case-insensitive, so the map compares lowercased paths.
- The app's `mtime` fields are renamed to `version` and compared only for equality.

**Acceptance criteria:**
- `MemStore`, `FsStore` and the OneDrive connector all pass the same store test suite: list, read, write, conflict, create-exists, remove and changes.
- The board code has no connector-specific branches.

---

## S-3 — Conflict safety per service

**Problem:** the app must never silently overwrite someone else's edit (Claude, the phone, another PC). The services offer different guarantees (see the comparison table).

**Options**
- **A — Use each service's strongest check, and show which kind in the UI.**
    - **OneDrive:** `If-Match` (no race).
    - **Local:** check, then write (as today).
    - **Google Drive:** read `version` just before writing, then **read back after writing**. If the version jumped by more than one, someone else wrote in the gap: show the conflict dialog, with both versions available.
    - **Pros:** best available safety per service; the race on Google Drive becomes detectable instead of silent.
    - **Cons:** an extra request per save on Google Drive; the read-back catches a lost update after the fact, it doesn't prevent it.
- **B — Lowest common denominator (check, then write) everywhere.**
    - **Pros:** simple and uniform.
    - **Cons:** throws away OneDrive's real protection.
- **C — Lock files** (for example `.lock-<task>.md` while editing).
    - **Pros:** prevents most collisions on any service.
    - **Cons:** stale locks after crashes; Claude and the OneDrive app don't know about them; clutter.

- **D — Last save wins** (no checks).
    - **Pros:** simplest.
    - **Cons:** silent data loss. Rejected: preserving the `.md` files is the top priority.
- **E — Keep both.** On conflict, save my version as a copy, e.g. `board-view (conflict PC 2026-10-16).md`, the way OneDrive does.
    - **Pros:** no edit is ever lost.
    - **Cons:** duplicate tasks (flagged by the existing "duplicate id" chip) to merge by hand.
- **F — Automatic merge** (field by field, line by line).
    - **Pros:** fewest interruptions.
    - **Cons:** complex; a bad merge can quietly corrupt a task. Rejected for now.

**Recommendation:** A, with E as an extra choice in the conflict dialog.

**Decision (Geoff, 2026-10-16):** **A + E.**
- **OneDrive:** every write and delete uses `If-Match` with the loaded eTag.
- **Conflict dialog:** three choices: *Use disk version* / *Overwrite with mine* / **Keep both**.
- **`_todo.json`** (list order) gets the same version check. On conflict it's merged automatically instead of showing a dialog: keep the other side's order, then add any lists only this side has.
- The Google Drive read-back check stays here as a note for later.

**Implementation notes:**
- **Keep both:**
    - Writes my text to `<base> (conflict <device> <YYYY-MM-DD>).md` via `create()`, adding `-2`, `-3` if needed.
    - Then reloads the disk version into the board.
    - The copy keeps the same `id`, so the board shows it with the "duplicate id" chip until it's merged by hand.
    - Device name: "PC" or "Phone" from the user agent, editable later.
- **Gap found in the current code:** `saveConfig()` writes `_todo.json` with no version check (`expected = null`), so a PC save can silently overwrite a list reorder done on the phone. Fixed by the above.

**Acceptance criteria:**
- No write path is unconditional.
- The 412 conflict test passes on PC and phone, with all three dialog choices working.
- Concurrent list reorders on two devices don't lose either change.

---

## S-4 — Change detection

**Problem:** the board picks up outside edits by listing the folder every 4 s. That's fine locally, but too slow and wasteful on cloud services. The PoC log (R1-10, findings 2–4) also showed:
- **bursts:** one PC save produced three change events;
- **echo:** the app's own delete came back as a change;
- **background pauses:** Chrome stops timers while the phone screen is off.

**Options**
- **A — Keep listing, everywhere.**
    - **Pros:** one code path.
    - **Cons:** each list is a full round trip (0.5–2.6 s on OneDrive); battery and data use on the phone.
- **B — One `changes()` call; each connector picks its method.**
    - Delta on personal OneDrive.
    - Listing on work OneDrive, because delta works only at the drive root there.
    - `changes.list` on Google Drive.
    - Listing locally.
    - Rules shared by all connectors:
        1. Reload a file only if its version differs from what's loaded (this fixes bursts and echoes, because the app records the version its own writes return).
        2. Treat a missing file as deleted only after it misses twice, or after a check confirms it.
        3. Check right away on `visibilitychange` (when the page comes back to the foreground).
        4. Poll every ~10 s on the phone and every 4 s on the desktop.
    - **Pros:** efficient where the service allows it; one behavior for the board.
    - **Cons:** three watcher implementations to test.
- **C — Push notifications (webhooks).**
    - **Pros:** instant.
    - **Cons:** needs a server; we have none. Rejected.

**Recommendation:** B.

**Decision:** —

---

## S-5 — Sign-in and staying signed in

**Problem:** the PoC showed (R1-10, finding 5):
- MSAL Browser 5.22.0 keeps its cache key in a **session cookie**, so the page forgets the sign-in whenever Chrome restarts.
- Microsoft also caps silent refresh for browser apps at **24 h**.
- Geoff had to type a password because Microsoft's own "Stay signed in" wasn't set. It is now set, and the retest is due 2026-10-17.

**Options**
- **A — Show a Sign in button when the session is lost** (the PoC's behavior).
    - **Pros:** simple; the user knows what's happening.
    - **Cons:** an extra tap after every Chrome restart, which happens often on Android.
- **B — Redirect automatically when no session is cached.** On load, if the connector has no usable cached account, it goes straight to Microsoft (or Google) and back. With "Stay signed in" set, that's a 1–2 s bounce with no typing.
    - Unsaved edits are never lost to the redirect: the drawer's draft is saved to the browser before leaving.
    - A loop guard stops after one failed attempt and shows the button.
    - **Pros:** feels like staying signed in.
    - **Cons:** a visible page bounce; depends on the identity provider's cookie (which Geoff controls with "Stay signed in").
- **C — Use an older MSAL version** that doesn't encrypt its cache.
    - **Pros:** survives Chrome restarts for up to 24 h.
    - **Cons:** gives up Microsoft's security fix; still capped at 24 h; makes an upgrade harder later. Not recommended.

**Google Drive note:** Google Identity Services gives a browser app only a 1 h access token, with no refresh token. It's renewed by calling Google again, which can be silent if Google remembers the user. The same auto-renew approach applies, but **whether it's silent on Android Chrome is untested**. A small Drive PoC should check this (see S-9).

**Recommendation:** B, pending tomorrow's retest. If Microsoft still asks for a password after "Stay signed in", revisit.

**Applies to the PC too** (S-10 = A): desktop Chrome also clears session cookies on a full close, unless "Continue where you left off" is on.

**Decision (Geoff, 2026-10-16):** **B with A as fallback.** On load, if there's no usable cached account, redirect to Microsoft once automatically. If that fails or loops, show the Sign in button. To be confirmed by the 2026-10-17 retest; if Microsoft still asks for a password, investigate why its session isn't kept.

**Implementation notes:**
- **Loop guard:** set a `sessionStorage` flag before the automatic redirect. If the page loads with the flag set and still no account, show the button and don't redirect again.
- **Unsaved edits:** before any redirect, write the drawer's draft (task file name, text and version) to `localStorage`. After sign-in, restore it into the drawer and mark it unsaved. Its version is kept, so a changed file still conflicts.
- **Silent first:** try `acquireTokenSilent` / `ssoSilent` before redirecting. Use `prompt: 'none'`-style behavior only where MSAL supports it, and fall back to a normal redirect.
- **Mid-session expiry:** if a silent token refresh fails during use, save the draft and use the same redirect path.

**Acceptance criteria:**
- After a Chrome restart on Android and on the PC, opening the app returns to the board signed in with no typing, provided Microsoft still remembers the account.
- No redirect loops.
- No unsaved edit is lost across a sign-in redirect.

---

## S-6 — Locations and switching

**Problem:** personal tasks (Google Drive), work tasks (work OneDrive) and possibly local folders must coexist without ever mixing (R1-10).

**Options**
- **A — A saved list of locations in the browser** (`localStorage`): each entry has a name, a connector type, an account hint and a folder path. A picker in the header switches between them. Each location is fully separate: its own session, cache and watcher.
    - **Pros:** simple; no shared config file to sync; nothing moves between services.
    - **Cons:** each device needs its locations added once.
- **B — A shared `_locations.json`** in one of the services.
    - **Pros:** set up once for all devices.
    - **Cons:** chicken-and-egg (which service holds it?); leaks the work location's details into personal storage.

**Recommendation:** A. Set-up per device is a one-time minute.

**Decision:** —

---

## S-7 — Delete behavior

**Problem:**
- Deleting a task removes its file.
- OneDrive keeps deleted files in its recycle bin; Google Drive's API deletes permanently unless told to trash.
- The local folder deletes permanently.

**Options**
- **A — Recoverable deletes everywhere:** OneDrive default (recycle bin); Google Drive `trashed=true`; local folder unchanged (the browser API can't move files to the Windows recycle bin), but the confirmation says so.
    - **Pros:** a mistaken delete can be undone in the service's own UI.
    - **Cons:** the local folder stays the exception.
- **B — Permanent everywhere.**
    - **Pros:** uniform.
    - **Cons:** risky on the phone, where it's easy to tap the wrong thing.

**Recommendation:** A.

**Decision:** —

---

## S-8 — Caching and offline

**Problem:** loading every file over the network on each visit is slow on a phone. The PoC's first listing alone took 2.0–2.6 s.

**Options**
- **A — Cache file contents in the browser (IndexedDB), keyed by version.** Show the cached board immediately, then refresh only the changed files. Offline, the board is **read-only**, with a banner.
    - **Pros:** fast start; no risk of offline edits colliding.
    - **Cons:** no editing without a connection.
- **B — Full offline editing with a sync queue.**
    - **Pros:** works anywhere.
    - **Cons:** much bigger build; conflict handling gets hard. Better as a later round.
- **C — No cache.**
    - **Pros:** simplest.
    - **Cons:** slow start every time.

**Recommendation:** A now, with B as a possible later round.

**Decision:** —

---

## S-9 — Build order

**Problem:** what to build first, following Geoff's rule of resolving the most architecturally dependent problems first.

**Proposed phases** (each needs Geoff's approval before it starts):
1. **Interface refactor** (S-2): add `version`, `create`, `caps` and `changes()` to the existing stores, with no visible change. A safe first step, testable with the existing Playwright setup.
2. **OneDrive connector** in the app (S-3 to S-5, S-7), on personal OneDrive. Most of the hard parts are already proven by the PoC. Test on the phone against `HTML-ToDo-App-Test`.
3. **Phone layout** (R1-9): make the board usable on a small touch screen.
4. **Location switcher** (S-6) and **cache** (S-8).
5. **Google Drive connector.** First a small Drive PoC like the OneDrive one, to test sign-in on Android and the S-3 read-back check.
6. **Work OneDrive.** Blocked on the work-account test and the IT questions in R1-10.

**Why OneDrive before Google Drive** (the reverse of the earlier plan in R1-10): OneDrive is already proven end to end on the phone and has the stronger conflict guarantee; Google Drive's phone sign-in is still untested. Google Drive is where Geoff's live personal tasks are, though, so if phone access to *those* tasks matters most, swap phases 2 and 5.

**Open question for Geoff:** which tasks do you most want on the phone first: personal (Google Drive) or the OneDrive test setup on the way to work tasks?

**Decision:** —

---

## S-11 — File and folder naming rules

**Reported** (Geoff, 2026-10-16): "Eventually I want to incorporate the ability to turn a markdown style todo item (with the .md - [ ] plain text) into its own task. in a folder that has the name of the parent task file. … The key is having a standard way to translate regular text into unique file and/or folder names that work on windows file explorer."

**The future feature (not in the prototype):** turn a checklist line like `- [ ] Buy filters` inside `rental.md` into a task file `rental/buy-filters.md`; deeper levels nest the same way. It's the reverse of the existing demote, for lines that were never tasks. S-2's path keys (D) make this possible without changing the interface.

**Key points (discussed 2026-10-16):**
1. **One-way conversion is enough.** The exact original text is stored in the file's frontmatter `title:` (e.g. `title: Buy-Filters` vs `title: Buy Filters`). Demote rebuilds the checkbox line from `title`, as the current `demoteLines()` already does, so checkbox → task → checkbox returns identical text. The file name is only a handle and never needs converting back. This matches the existing contract rule: "file names are a slug of the title when created; renaming the title doesn't rename the file."
2. **Separator: dash.**
    - It's readable, already used, and safe in Windows, OneDrive, URLs and Markdown links.
    - Underscore clashes with the "names starting with `_` are not tasks" rule.
    - Rare characters (`·`, `~`, `+`) risk breaking URLs and tools.
3. **Slug rules** (extend the current `slug()`):
    - strip `< > : " / \ | ? *` and control characters; no trailing dot or space;
    - keep Unicode letters and digits (today, non-English titles can collapse to `task`);
    - lowercase, with spaces and punctuation runs → single `-`;
    - avoid Windows reserved names (`con`, `prn`, `aux`, `nul`, `com1`–`com9`, `lpt1`–`lpt9`; append `-task`);
    - max **40** characters per name;
    - uniqueness is **case-insensitive within the folder**, with `-2`, `-3`… suffixes;
    - avoid OneDrive-blocked names (e.g. `desktop.ini`, `.lock`, names containing `_vti_`).
4. **Path length:** keep full paths well under Windows' ~260-character limit. With 40-character names, cap nesting at about 4 levels, and warn before exceeding it.
5. **A file and a folder with the same base name** (`rental.md` beside `rental/`) are fine on Windows and OneDrive. It's the Obsidian "folder note" convention.
6. **Links:** demote's `[↗](…)` link must encode each path segment separately, not the whole path with `encodeURIComponent` (that would turn `/` into `%2F`), and should be relative to the file that contains it.

**Options for the hierarchy's source of truth**
- **A — `parent:` stays the truth; folders are organization only.** New subtasks made from a checklist line go into the parent's folder, but the app works wherever a file sits (including today's flat subtasks). Dragging to a new parent does not move files.
    - **Pros:** simple; nothing breaks if folders and `parent:` drift apart.
    - **Cons:** the folder layout can drift from the board hierarchy.
- **B — The folder is the truth.** Re-parenting moves the file (cheap on OneDrive; the ID is kept).
    - **Pros:** folders always mirror the board.
    - **Cons:** more to build; moves can break links; Claude and other tools must move files correctly too.

**Decision (Geoff, 2026-10-16):** **A.** `parent:` remains the source of truth. The slug rules above apply to every new file from the prototype on. The checklist → task-in-folder feature is a **future item**, not part of the prototype. A "tidy folders" action (move files to match `parent:`) can be considered later if drift bothers Geoff.

---

## S-10 — How the PC reaches the files

**Problem:** the phone must use the OneDrive web connection (Microsoft Graph). The PC can either open the folder the OneDrive sync app keeps on disk (`FsStore`, works today) or use the same web connection.

**Options**
- **A — The web connection on both devices.**
    - **Pros:** one storage path to build and test; the PC and phone behave the same, with OneDrive's true conditional save everywhere; no dependence on the OneDrive sync app or Chrome folder access on a locked-down work PC.
    - **Cons:** the PC must sign in too; about 1 s per save; no PC editing offline.
- **B — Synced folder on the PC, web connection on the phone.**
    - **Pros:** works today (dual-access test, 2026-10-15); instant saves; the PC works offline.
    - **Cons:** two paths; a weaker conflict check on the PC (modified time, with sync timing in between); depends on the sync app and Chrome folder access at work.
- **C — Both available, chosen per device** (the location list, S-6).
    - **Pros:** most flexible.
    - **Cons:** more UI and choices; not needed for a prototype.

Claude's access is the same in all options: Claude edits the synced folder on the PC, and OneDrive carries the change to both devices.

**Decision (Geoff, 2026-10-16):** **A for the initial prototype.** The prototype is built and tested around the OneDrive web connection on both PC and Android. `FsStore` stays in the code unchanged. **Pivot to C later:** Geoff wants per-device choice (synced folder or web connection) after the prototype, through the location list in S-6.

**Implementation notes:** the PC signs in through the same MSAL redirect flow as the phone. The same Azure registration works (`HTML-ToDo-App PoC`), but its redirect URI must also include the app's address (e.g. `https://gvd1024.github.io/html-todo-app/app/`). Add `http://localhost:8000/app/` for local testing.

**Acceptance criteria:** the prototype on PC Chrome and on Android Chrome, both signed in to personal OneDrive, shows the same `HTML-ToDo-App-Test` tasks, and edits on either appear on the other.

---

## Decision log

| Date | Item | Decision | Notes |
|---|---|---|---|
| 2026-10-16 | S-11 | Added (future feature: checklist line → task file in a folder named after the parent). Decided **A**: `parent:` stays the truth. Naming: a one-way dash slug with Windows/OneDrive safety rules; the original text is preserved in `title:` | Feature deferred; rules apply now |
| 2026-10-16 | S-3 | **A + E:** OneDrive `If-Match` on every write; conflict dialog gains **Keep both**; `_todo.json` gets a version check plus an automatic merge (gap found in `saveConfig`) | Decided |
| 2026-10-16 | S-2 | **A + D:** the existing interface keyed by relative path, with an opaque version token; options E (task-level store) and F (local-first sync) considered and rejected for now | Decided |
| 2026-10-16 | S-5 | **B with A as fallback:** automatic redirect when the cached session is gone, with a loop guard, falling back to the Sign in button; drafts preserved across redirects | Confirm after the 2026-10-17 retest |
| 2026-10-16 | S-10 | **A for the prototype:** OneDrive web connection on PC and phone; `FsStore` kept as is. **Pivot to C** (per-device choice) later, via S-6 | Decided |
| 2026-10-16 | — | **Direction:** OneDrive is the committed datastore (personal now, work later); test data only; prototype ASAP on PC + Android; discuss the most limiting items first | Google Drive deferred |
| 2026-10-16 | — | Spec created as a draft from R1-9/R1-10 notes, the PoC results and the app's current store code | Nothing approved |

## Change history of this spec

- 2026-10-16 — v6: S-3 decided (A + E); S-11 added and decided (A).
- 2026-10-16 — v5: S-2 decided (A + D); options D, E and F added.
- 2026-10-16 — v4: S-5 decided (B with A fallback).
- 2026-10-16 — v3: added S-10, decided A, with C later.
- 2026-10-16 — v2: Direction section (OneDrive committed, test data only, prototype ASAP).
- 2026-10-16 — v1 draft: S-1 to S-9 with options and recommendations.
