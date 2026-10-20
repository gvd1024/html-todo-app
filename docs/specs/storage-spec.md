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
| S-4 | Change detection | **Decided** | B + three rules: delta on personal OneDrive, listing (or root delta) on work OneDrive |
| S-5 | Sign-in and staying signed in | **Decided** (confirm after the 2026-10-17 retest) | B (automatic redirect), with A (button) as fallback |
| S-6 | Locations and switching | **Decided** | C for the prototype (one folder setting, default `HTML-ToDo-App-Test`); A later |
| S-7 | Delete behavior | **Decided** | Recoverable: OneDrive recycle bin plus a 5 s in-app Undo; confirm before deleting a parent's subtasks |
| S-8 | Caching and offline | **Decided** | C for the prototype (no cache, parallel loading); A when startup feels slow |
| S-9 | Build order (MVP build plan) | **Decided** | Phases 0–6: prep → storage refactor → OneDrive + sign-in → phone list view → checking/done/delete → long-press move → acceptance and go-live |
| S-12 | Claude can create, read, update and delete the same files | **Open**, requirement | Synced folder on the PC; a local MCP server for desktop Chat; a remote MCP server for Android and the web |
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

**Decision (Geoff, 2026-10-16):** **B with the three rules:**
1. Reload a file only if its version differs from what's loaded. This fixes bursts and own-write echoes, deletes included.
2. Check right away on `visibilitychange`.
3. Poll about every 10 s on the phone and about every 5 s on the PC (configurable).

**Work OneDrive implications (explained to Geoff 2026-10-16):** on OneDrive for Business and SharePoint, a delta query works only at the **drive root**, not on a folder. The method still works at work, using one of two fallbacks:
- **(a) Listing:** list the task folder's children every poll. One small request returns every file's eTag; fine for hundreds of files.
- **(b) Root delta:** run delta on the whole drive (start with `token=latest` to skip the initial full scan) and keep only items whose parent path is the task folder. More efficient, but noisier.
- **Choice:** the prototype (personal OneDrive) uses folder delta. Work starts with (a) for simplicity.
- **The real work risks aren't S-4.** They're the R1-10 IT questions: app consent, and conditional access on a personal phone.

**Acceptance criteria:**
- A PC or Claude edit shows on the phone within about 15 s while the app is in the foreground, and right away after it returns to the foreground.
- No duplicate reloads from one save.
- The app's own writes and deletes are never reported as outside changes.

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

- **C — One location for the prototype:** a single folder setting (default `HTML-ToDo-App-Test`), changeable in Settings.
    - **Pros:** fastest; it's all the prototype needs.
    - **Cons:** switching folders means changing a setting, not a picker.

**Recommendation:** C now, A later. Set-up per device is a one-time minute.

**Decision (Geoff, 2026-10-16):** **C for the prototype, A later.**
- **Now:** after sign-in, the app opens one OneDrive folder from a setting.
- **Code:** "location" is one object (`{name, type, folder}`), so the list of locations (A) is additive later.
- **When A arrives:** with work OneDrive, or the per-device choice from S-10 (C).

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
- **C — Recoverable plus in-app Undo:** like A, plus a 5 s Undo bar that re-creates the file from the copy still in memory.
    - **Pros:** matches the checkbox Undo (R1-12).
    - **Cons:** a little more code; the restored file gets a new OneDrive item ID (harmless, because the app works by path).

**Recommendation:** C.

**Decision (Geoff, 2026-10-16):** **C (recoverable plus in-app Undo).**
- **OneDrive:** `DELETE` sends the item to the OneDrive recycle bin (personal and work).
- **Confirm:** *"Delete 'X'? You can restore it from the OneDrive recycle bin."*
- **Undo:** a 5 s bar re-creates the file with `create()`.
- **A parent with subtasks:** *"Also delete its N subtasks?"* → Delete all / Cancel. Everything goes to the recycle bin, and Undo restores all of it.
- **Local folder:** still permanent (the browser API can't use the Windows recycle bin), and the confirm text says so.

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

**Recommendation (revised for the prototype):** C plus parallel loading now; A next; B as a possible later round.

**Decision (Geoff, 2026-10-16):** **C for the prototype.**
- **Loading:** no browser cache. Each open lists the folder, then reads files in parallel (about 6 at a time).
- **Offline:** the header status icon shows "offline", and edits are blocked with a message.
- **Next step:** move to **A** (IndexedDB cache by version, read-only offline) when startup feels slow, or once real tasks grow past a few dozen.

---

## S-9 — Build order (MVP build plan)

**Goal:** the MVP Geoff can start using for real: the same OneDrive task files from Android Chrome and PC Chrome, in the R1-12 phone list view. Built on the decisions in this spec (S-2 to S-8, S-10, S-11) and in round-1 R1-12.

**How the build runs**
- **Approvals:** each phase starts only when Geoff approves it, and ends with Geoff's own check on the PC and phone. Status goes `Approved for build → Built → Verified`.
- **Test data:** all testing uses the OneDrive folder `HTML-ToDo-App-Test` (rule 10).
- **Branching:** work goes straight to `main`, in small commits, because the phone can only test what GitHub Pages serves. Before Phase 1, tag the current app `v0.1.1` so it can always be restored (`git checkout v0.1.1 -- app/`).
- **Automated tests:** Playwright in headless Chromium, with a simulated Graph API for the OneDrive store, as in the Cowork session. Real sign-in and real-phone checks are Geoff's.
- **Sizes** are relative (S / M / L), not time promises.

### Phase 0 — Prep (S)

| # | Task | Who |
|---|---|---|
| 0.1 | Tag `v0.1.1` in git and push the tag | Claude |
| 0.2 | **Versioning (R1-6, minimal):** app version `0.2.0-dev` shown in the header; **data-format version 2** for the new keys `prefix` and `completed` (written to `_todo.json` as `"format": 2`). The full R1-6 scheme can follow later. *Needs Geoff's OK.* | Geoff decides |
| 0.3 | Add redirect URIs to the Azure registration `HTML-ToDo-App PoC`: `https://gvd1024.github.io/html-todo-app/app/` and `http://localhost:8000/app/`. The app will be served as `app/index.html` so the URI has no file name. | Geoff (Claude guides) |
| 0.4 | Install the test harness: `pip install playwright` and `playwright install chromium` (about 150 MB). *Needs Geoff's OK.* | Claude |
| 0.5 | Reset the test folder: remove `poc-test.md`, and add 10–15 varied test tasks (long titles, subtasks two levels deep, done items, bullets, body checklists, one unknown frontmatter key) so every R1-12 behavior can be exercised | Claude |

**Done when:** the tag exists, redirect URIs are added, the harness runs a trivial test, and the test folder is seeded.

### Phase 1 — Storage interface refactor (S-2) (S/M)

- Rename `mtime` to an opaque `version` across the app; key files by **relative path**.
- Add `create()`, `remove(path, expected)`, `changes()` and `caps` to `MemStore` and `FsStore`.
- Give `_todo.json` a version check and an automatic merge on conflict (S-3).
- Apply the S-11 slug rules to new file names (reserved names, 40 characters, case-insensitive uniqueness, Unicode kept).
- No visible change yet.

**Done when:** one shared store test suite passes for `MemStore` and `FsStore`, and the v0.1.1 board still works.

### Phase 2 — OneDrive connector and sign-in (M/L)

- Add the **GraphStore**, ported from the PoC:
    - list, read, write with `If-Match`, `create` with `conflictBehavior=fail`, recycle-bin `remove` with `If-Match`;
    - `changes()` via folder delta (S-4 rules: reload only on a version change, check on `visibilitychange`, poll about 10 s on the phone and 5 s on the PC);
    - parallel reads, about 6 at a time (S-8 C).
- **Sign-in (S-5):**
    - MSAL redirect;
    - an automatic redirect when the session is gone, with a loop guard and the Sign in button as fallback;
    - drafts saved across redirects.
- **One folder setting** (S-6 C), default `HTML-ToDo-App-Test`. The app moves to `app/index.html`.
- **Conflict dialog:** adds **Keep both** (S-3).
- **Header status icon:** signed in / syncing / offline / conflict.

**Done when:**
- The store test suite passes against the simulated Graph.
- On Geoff's PC and phone, the **existing views** load the test folder over OneDrive.
- The dual-access tests (2026-10-15) pass again, now app ↔ app.

### Phase 3 — Phone list view (R1-12) (L)

- **Retire the board view.** It becomes the new **list view**, the default on all devices.
- **Header:** a large list name, which opens the list-picker sheet with task counts (the phone remembers the last list viewed), plus the status icon.
- **Rows:**
    - one line each, at least 44 px tall;
    - a sticky prefix cell (checkbox / active dot / bullet / none, with ⚠ for unrecognized frontmatter);
    - the title (tap → editor);
    - the subtask badge `open/total` in an accent color (tap → expand or collapse; zero space when collapsed);
    - a sticky ⋯ menu: Edit / Move to list / Change prefix / Delete.
- **Sideways scrolling:** the whole list scrolls together, with a ⇤ button and an automatic snap back on list switch, editor close or 3 s idle (7a).
- **Quick-add box** at the bottom.
- **Editor:** full-screen on the phone, with a prefix selector and the unrecognized-frontmatter notice.

**Done when:** the R1-12 acceptance checks for layout pass on Geoff's phone, and the same view works on PC Chrome.

### Phase 4 — Checking, done items and delete (M)

- **Checkbox toggle:** saves immediately, with a 5 s Undo.
- **"Check all / Check only this / Cancel"** dialog when subtasks or body `- [ ]` lines are open.
- **The `completed` date:** set on check, removed on uncheck.
- **Done items hidden,** with a "Show done" toggle (done items can be unchecked).
- **Delete:** confirm, then recycle bin, with a 5 s Undo; a parent's subtasks are included (S-7).

**Done when:** R1-12 decisions 3, 8 and 14 and S-7 pass on the phone, and no unconditional writes exist anywhere (searched in code and logged in tests).

### Phase 5 — Long-press move (M, needs the most phone testing)

- Long press (400 ms) → flash → drag.
- **Drop on a row's middle** = make it a child (the row highlights).
- **Drop on a row's edge** = reorder (a line shows).
- **Drag left** = un-nest.
- Dropping onto a collapsed parent makes the item its last child.
- Children move with their parent; `list` is updated to match.
- The list auto-scrolls near its edges.

**Done when:** Geoff can reorder, nest and un-nest reliably on his phone without accidental drags while scrolling.

### Phase 6 — MVP acceptance and go-live (S)

- **A full checklist on the PC and phone:** everything above, plus a CRUD pass by Claude through the synced folder while the app is open on both devices (S-12).
- **The sign-in persistence check** across a Chrome restart (S-5).
- **Go-live:**
    1. Geoff chooses the real OneDrive folder.
    2. Claude migrates the current real tasks (from Google Drive `HTML_ToDo_Files`) into it, by hand, showing the changes.
    3. **Rule 10's protection of real files takes effect from here.**

### Build log

**2026-10-17 (overnight, Claude alone; Geoff approved "0–2 plus Phase 3 first cut"):**

| Phase | Status | What happened |
|---|---|---|
| 0 Prep | **Built**, except 0.3 | 0.1 tag `v0.1.1` pushed. 0.2 `0.2.0-dev` / data format 2 in code. **0.3 (Azure redirect URIs) waits on Geoff.** 0.4 Playwright + Chromium installed. 0.5 test folder reseeded: `poc-test.md` removed; 13 varied tasks plus `_todo.json` added (18 tasks total). |
| 1 Storage refactor | **Built** | `app/todo.html` → `app/index.html` (`todo.html` now redirects). Path keys, opaque versions, `create`/`remove(expected)`/`changes()`/`caps`; `_todo.json` version check and merge; S-11 slugs. The shared store suite passes for MemStore and FsStore. |
| 2 OneDrive + sign-in | **Verified** 2026-10-17 (phone and PC sign-in, live two-way sync, sign-in persists overnight) | `GraphStore` ported from the PoC; `MsalAuth` with the automatic bounce and loop guard; drafts survive the redirect; folder setting; Keep both; status icon; parallel loading. Passes the store suite and the app flows against a strict fake Graph (no unconditional writes). The live page loads the real MSAL and reaches Microsoft with the right client ID and redirect URI. |
| 3 Phone list view | **First cut built**, awaiting Geoff's review | R1-12 layout: list picker, one-line rows, prefixes and active dot, subtask badges, sideways scroll with pinned columns, ⇤ and 3 s snap-back, quick-add, ⋯ menu, full-screen editor with a prefix selector, ⚠ for unrecognized frontmatter, by-due-date view. Board and Outline retired. Screenshots in `tests/screenshots/`. |

**Automated tests:** `python tests/run_tests.py` → 119 checks, all passing (2026-10-17).

**Hardening added after the first pass (same night):**
- **Expired sign-in at start-up** (account remembered, but Microsoft's 24 h limit has passed) now bounces to Microsoft once, instead of showing a load error.
- **No repeated "signed out" messages** on every poll.
- **Expired change feed** (OneDrive returns 410 after a long sleep) triggers a full reload, so edits made in the gap aren't missed.
- **The bounce passes a login hint** (the last account used), so Microsoft can skip the account picker.
- **The one-automatic-bounce guard lasts for the whole browser session** (cleared when Chrome restarts), so an account whose token can never be refreshed can't cause a redirect loop.
- **Editor toolbar on phones:** checklist and list buttons come first, and the overflow ⋯ button is visible.

**Assumptions made while building (please confirm or change):**
1. **Subtask badge position:** in the pinned right column next to ⋯, not right after the title, so it stays visible and tappable even when a long title is cut off.
2. **"Show done" is ON by default for now.** Hiding items on check (R1-12 #3) arrives in Phase 4, together with the 5 s Undo, so a mis-tap can't make a task vanish with no way back.
3. **Outline view retired too** (it was the board's sibling). *By due date* is kept, as an entry in the list picker.
4. **Search** moved into the ⋯ app menu. **Add subtask** added to the row ⋯ menu (not in the R1-12 list, but the old card menu had it).
5. **Delete in this cut** still moves subtasks up a level (the v0.1.1 behavior). S-7's "also delete N subtasks" plus Undo arrives in Phase 4.
6. **The automatic sign-in bounce applies only to returning users** (once signed in on that browser). A first visit shows the Sign in button.
7. **No `ssoSilent` attempt** before redirecting: Chrome's third-party-cookie limits make the hidden-iframe method unreliable, so the bounce is a plain redirect.
8. **The status icon is tappable:** it signs in when signed out; otherwise it shows its explanation.
9. **`completed:` isn't written yet** (Phase 4); the key is already recognized, so it isn't flagged.
10. **The Azure client ID** is built in; an override is possible via `localStorage` (`todo.clientId`) only, with no UI.

### After the MVP (not in this plan)

- **PC layout parity extras** (R1-12 #5).
- **Locations list** and per-device choice (S-6 A / S-10 C).
- **Cache** (S-8 A) and the done-file **archive** (R1-12 #14).
- **Claude access** from desktop Chat and Android (S-12 paths 2–4, the remote MCP server).
- **Work OneDrive** (R1-10, after the work-account test).
- **Remaining round-1 items:**
    - R1-1, R1-3 and R1-4 still apply to the editor.
    - **R1-2** is covered by quick-add.
    - **R1-7 and R1-8** were board-only and become obsolete when the board is retired, pending Geoff's confirmation.
- **The checklist → task-in-folder feature** (S-11).

**Decision (Geoff, 2026-10-17):** plan accepted. Phase 0 questions: (1) `0.2.0-dev` plus data format 2: yes; (2) install Playwright: yes; (3) the app moves to `app/index.html` (`/app/`): yes; (4) build on `main` with the `v0.1.1` tag as the safety net: yes. R1-7 and R1-8 obsolete. Phases still start only when Geoff approves each one.

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

## S-12 — Claude can create, read, update and delete the same task files

**Requirement** (Geoff, 2026-10-16): "I do want you to be able to do crud from as much of the following as possible: the pc desktop claude code app; the pc desktop claude cowork app; the pc desktop claude chat app; the pc claude code cli; the android claude cowork app; the android claude chat app. … please add this as a requirement and dont forget to add this to our testing."

**Why it matters:** the app's purpose is that Geoff and Claude work on the same task files. Until 2026-10-16, Claude had only **read** the OneDrive test folder; it had never created, updated or deleted anything there.

**Clarification (2026-10-16):** the earlier "no server" principle applies to the **app** (data lives only in plain files; the app needs no backend). It does **not** forbid a small server whose only job is Claude's access to OneDrive. Geoff already runs a custom MCP server for Super Productivity and is fine with a custom MCP server for this, on PC and Android, hosted on a free service for personal use (probably not acceptable at work).

**Access paths**

| Path | How | Covers | Notes |
|---|---|---|---|
| **1. Synced folder** | Claude's file tools on `C:\Users\gvd10\OneDrive\HTML-ToDo-App-Test`; OneDrive syncs it | Claude Code CLI, desktop Code tab, desktop Cowork (folder connected) | No new software. The PC must be on, with OneDrive syncing. No version check: Claude must re-read a file right before editing it. |
| **2. Local MCP server** | A filesystem MCP server or desktop extension in the Claude desktop config, pointed at the synced folder | Desktop Chat | Like Geoff's existing `sp-local-rest`. PC only. |
| **3. Remote MCP server** | A small hosted server that signs in to OneDrive (Microsoft Graph) as Geoff and exposes list, read, create, update and delete on **one allowed folder**, using the same eTag / `If-Match` safety as the app. Added as a custom connector in claude.ai, it appears in all Claude apps. | Android Chat, claude.ai web, desktop Chat, and maybe Android Cowork | **Hosting:** GitHub Pages can't run servers. Candidates: Cloudflare Workers (free; remote-MCP templates with OAuth), Vercel or Netlify functions, Azure Functions (Geoff's free Azure account). Holds an OneDrive refresh token: lock it to Geoff's account and the allowed folder. Probably needs IT approval at work. |
| **4. Microsoft 365 connector** | The built-in claude.ai connector | Chat surfaces | **Verify:** HANDOFF says it doesn't expose OneDrive file writing. Check its actual tools before ruling it in or out. |

**Starting assessment per surface (verify; don't assume)**

| Surface | Expected path | Confidence | Test status |
|---|---|---|---|
| PC Claude Code CLI | 1 | High | **Passed 2026-10-16** (all 6 steps; see results below) |
| PC desktop app, Code tab | 1 | High | Not tested |
| **Work PC, Claude Code CLI** (local-folder mode in the work OneDrive sync folder) | 1 | High | **Passed create/read/update 2026-10-19**; delete and a concurrent edit still pending |
| PC desktop app, Cowork | 1 | Medium-high | Not tested |
| PC desktop app, Chat | 2 (or 3, or 4) | Medium (needs setup) | Not tested |
| Android Claude app, Chat | 3 (or 4) | Medium (needs the remote MCP server) | Not tested |
| Android Claude app, Cowork | 3, if Cowork with connectors exists on Android | Unknown: verify that Android Cowork exists and what it can reach | Not tested |

**Test checklist (run per surface, test folder only):**
1. Create `claude-test-<surface>.md` with valid frontmatter (`list: Test List`).
2. Read it back.
3. Geoff sees it in the app on the PC and the phone.
4. Claude updates its body; the change appears on both devices.
5. Conflict: Geoff edits the same file in the app, then Claude re-reads it before writing and doesn't overwrite blindly.
6. Claude deletes it; it disappears on both devices.

**Results: PC Claude Code CLI (2026-10-16, path 1, test folder):**
1. **Create:** created `claude-test-cli.md` and read it back.
2. **Seen on both devices:** Geoff saw it on the phone and in the PC app.
3. **Update:** Claude appended a line; Geoff saw it on both devices.
4. **Conflict:** Claude snapshotted the file (22:28:02, 207 bytes). Geoff then edited it in the app (22:30:25, 219 bytes, adding "Geoff edit"). Before writing, Claude compared against the snapshot, **detected the change and did not write**, showed the diff, then re-read and merged its line below Geoff's. Both edits were kept.
5. **Delete:** the file disappeared from the phone and the PC app; OneDrive keeps it in the online recycle bin.

Note: the test folder also has `poc-test.md`, left by the PoC page's create test; it is not Claude's.

**Rules for Claude when editing task files (all paths):**
- Re-read right before writing.
- Keep the frontmatter key order and any unknown keys.
- Never touch real task folders unless Geoff says so.
- Prefer the path with a version check (path 3) when it exists.

**Decision:** — (requirement accepted; paths and build order to decide)

---

## Decision log

| Date | Item | Decision | Notes |
|---|---|---|---|
| 2026-10-19 | S-12 | Work PC: Claude Code CLI path 1 passed create/read/update on the same files HTA uses (local-folder mode, work OneDrive sync folder) | Delete and conflict pending |
| 2026-10-17 | S-9 | **Phase 2 verified by Geoff:** sign-in on phone and PC; a phone check-off showed on the PC and a PC quick-add showed on the phone within seconds; no sign-in needed after the night | S-10 A acceptance met |
| 2026-10-17 | S-9 | Overnight build: Phases 0 (except 0.3), 1, 2 and a Phase 3 first cut **Built**; 119 automated checks pass; 10 assumptions listed in the S-9 build log | Awaiting Geoff: Azure redirect URIs, then phone and PC check |
| 2026-10-17 | S-9 | MVP build plan accepted (Phases 0–6); versioning `0.2.0-dev` / data format 2; Playwright; app at `/app/`; build on `main` with the `v0.1.1` tag | Phases are approved one at a time |
| 2026-10-16 | S-6, S-7, S-8 | Prototype trims: **S-6 C** (one folder setting), **S-7 C** (recycle bin plus 5 s Undo, confirm for subtasks), **S-8 C** (no cache, parallel loading) | Decided |
| 2026-10-16 | S-12 | **PC Claude Code CLI passed all steps:** create, read, update and delete on the OneDrive-synced test folder, seen on the phone and PC; a manual version check caught Geoff's concurrent edit, and nothing was overwritten | Next: the other five surfaces |
| 2026-10-16 | S-12 | **Added requirement:** Claude CRUD on the same task files from six surfaces (PC CLI, desktop Code, desktop Cowork, desktop Chat, Android Chat, Android Cowork). "No server" clarified as app-only; a custom remote MCP server for Claude's access is acceptable (personal) | Testing starts with the PC CLI |
| 2026-10-16 | S-4 | **B + three rules**; work OneDrive uses listing (or root delta), since folder delta is personal-only | Decided |
| 2026-10-16 | S-11 | Added (future feature: checklist line → task file in a folder named after the parent). Decided **A**: `parent:` stays the truth. Naming: a one-way dash slug with Windows/OneDrive safety rules; the original text is preserved in `title:` | Feature deferred; rules apply now |
| 2026-10-16 | S-3 | **A + E:** OneDrive `If-Match` on every write; conflict dialog gains **Keep both**; `_todo.json` gets a version check plus an automatic merge (gap found in `saveConfig`) | Decided |
| 2026-10-16 | S-2 | **A + D:** the existing interface keyed by relative path, with an opaque version token; options E (task-level store) and F (local-first sync) considered and rejected for now | Decided |
| 2026-10-16 | S-5 | **B with A as fallback:** automatic redirect when the cached session is gone, with a loop guard, falling back to the Sign in button; drafts preserved across redirects | Confirm after the 2026-10-17 retest |
| 2026-10-16 | S-10 | **A for the prototype:** OneDrive web connection on PC and phone; `FsStore` kept as is. **Pivot to C** (per-device choice) later, via S-6 | Decided |
| 2026-10-16 | — | **Direction:** OneDrive is the committed datastore (personal now, work later); test data only; prototype ASAP on PC + Android; discuss the most limiting items first | Google Drive deferred |
| 2026-10-16 | — | Spec created as a draft from R1-9/R1-10 notes, the PoC results and the app's current store code | Nothing approved |

## Change history of this spec

- 2026-10-17 — v11: S-9 build log (Phases 0–2 and Phase 3 first cut built; assumptions listed).
- 2026-10-17 — v10: S-9 decided; Phase 0 questions answered.
- 2026-10-17 — v9: S-9 rewritten as the phased MVP build plan (draft).
- 2026-10-16 — v8: S-6 (C), S-7 (C: recoverable plus Undo) and S-8 (C) decided for the prototype.
- 2026-10-16 — v7: S-4 decided; S-12 added (Claude CRUD requirement, access paths, test checklist).
- 2026-10-16 — v6: S-3 decided (A + E); S-11 added and decided (A).
- 2026-10-16 — v5: S-2 decided (A + D); options D, E and F added.
- 2026-10-16 — v4: S-5 decided (B with A fallback).
- 2026-10-16 — v3: added S-10, decided A, with C later.
- 2026-10-16 — v2: Direction section (OneDrive committed, test data only, prototype ASAP).
- 2026-10-16 — v1 draft: S-1 to S-9 with options and recommendations.
