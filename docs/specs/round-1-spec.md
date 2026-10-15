# HTML-ToDo-App — Round 1 Spec

| Field | Value |
|---|---|
| **App** | HTML-ToDo-App (`todo.html`) |
| **Current build (baseline)** | v0.1.1. v0.1.0 was the first build; v0.1.1 added the dark theme. |
| **Target build** | v0.2.0 |
| **Source of findings** | All three tasks in the Feedback list: "Toast UI Changes" (`round-1.md`) → R1-1 to R1-5; "Board View" (`board-view.md`) → R1-7, R1-8; "Access from Android Phone" (`access-from-android-phone.md`) → R1-9. Plus R1-6 (versioning) and R1-10 (work OneDrive), which Geoff raised in chat. |
| **Spec status** | Discussing — nothing approved for build |
| **Last updated** | 2026-10-14 |

## Ground rules

1. **No code until approved.** Nothing in this spec gets built until Geoff explicitly says to start the next revision.
2. **Only named items get built.** Only items Geoff names are built, even if other items are decided.
3. **Each item moves through these statuses:** `Open` → `Discussing` → `Decided` → `Approved for build` → `Built` → `Verified`.
4. **Decisions are logged.** As each item is discussed, the chosen option, any extra details and the acceptance criteria are added under that item, and the decision is added to the Decision log at the bottom.
5. **Scope:** every task in the Feedback list, plus items Geoff raises in chat. Anything new gets the next R1 number; nothing is added without Geoff asking.

## Summary

| # | Finding | Status | Leading option | Decision |
|---|---|---|---|---|
| R1-1 | Checklist toolbar icon looks like a dropdown | Open | A + B | — |
| R1-2 | Enter in the title box should save and close | Open | B | — |
| R1-3 | Save & close button (keep plain Save?) | Open | A | — |
| R1-4 | Font is too small | Open | A | — |
| R1-5 | What is Collections for? | Open | A | — |
| R1-6 | Track the app version | Open | A + C | — |
| R1-7 | Reorder lists by dragging | Open | A | — |
| R1-8 | Clicking the open task again should close the editor | Open | A + B | — |
| R1-9 | Use the board from an Android phone (**key requirement**) | Discussing | C (Drive backend) | — |
| R1-10 | Work tasks on work OneDrive, usable from Android (**requirement**) | Discussing | Check with IT first, then A | — |
| R1-11 | Rename the app to HTML-ToDo-App | Built | — | Display name HTML-ToDo-App; slugs stay `html-todo-app` |

---

## R1-1 — Checklist toolbar icon looks like a dropdown

**Reported:** "checkbox icon looks like its a dropdown"

**Problem (restated):** In the editor toolbar, the "task list / checkbox" button doesn't clearly say "insert a checklist item." A small mark under the icon makes it look like it opens a menu. A button whose purpose isn't obvious slows down the most common action in a to-do app: adding checklist items.

**Root cause (to confirm):** probably the dark theme's highlight for the active button, or the button's tooltip, showing as a small box under the icon. I'll confirm this in a browser before choosing a fix.

**Options**

- **A — Remove the stray mark.** A CSS fix that hides the leftover indicator, keeps Toast UI's icon, and adds a clear "Checklist item" tooltip.
    - **Pros:** tiny change; Toast UI's look is otherwise unchanged.
    - **Cons:** the icon itself may still be unclear.
- **B — Replace the icon.** Use a clearer custom icon, such as ☑ or a box with a check plus lines.
    - **Pros:** clear at a glance.
    - **Cons:** it won't match the style of the other toolbar icons.
- **C — Labeled button for the common action.** Give the checklist button a text label ("☑ Checklist") and leave the other icons as they are.
    - **Pros:** impossible to misread.
    - **Cons:** takes more room in the toolbar.
- **D — Typing shortcuts.** Document and support typing `[ ] ` at the start of a line to create a checkbox, plus a keyboard shortcut (e.g. Ctrl+Shift+C). Can be combined with any of the above.
    - **Pros:** fastest for heavy users.
    - **Cons:** hard to discover without a hint.

**Recommendation:** A first. If the icon is still unclear without the stray mark, do B. Add D's shortcut either way.

**Open questions:** Does the problem go away once the stray mark is removed, or is the icon itself the issue?

**Decision:** —

**Implementation notes:** —

**Acceptance criteria:** —

---

## R1-2 — Enter in the title box should save and close

**Reported:** "enter when in title box just saves task and closes it (for easy entry of lots of tasks or subtasks"

**Problem (restated):** Adding many tasks or subtasks in a row is slow. Each one takes a click on "+ Add task", typing the title, a click on Save, then a click on ✕. The real goal is entering tasks quickly, not only what the Enter key does.

**Options**

- **A — Enter = save & close.** Exactly what was asked.
    - **Pros:** simple and predictable.
    - **Cons:** adding the next task still needs a click.
- **B — Enter = save & close; Shift+Enter = save & start the next one.** Shift+Enter saves, then opens a new blank task in the same place: same list, or same parent if it's a subtask.
    - **Pros:** covers both single tasks and quick runs of tasks.
    - **Cons:** you need to learn the Shift variant.
- **C — Enter = save & start the next one, while adding new tasks.** In a new task, Enter saves it and opens the next blank one; Esc on an empty title stops. On an existing task, Enter = save & close.
    - **Pros:** fastest way to add a batch.
    - **Cons:** Enter behaves differently for new and existing tasks.
- **D — Add tasks right on the board.** "+ Add task" (and "+ Subtask" on a card) becomes a text box in the column itself: type, press Enter, the card appears, and the box stays ready for the next one. The editor panel is only for details.
    - **Pros:** best for brain-dumping a list and keeps the editor uncluttered.
    - **Cons:** more work to build; two ways to create tasks.

**Edge cases to settle:**

- Enter with an empty title: do nothing, or discard the new task?
- Typing with an input method editor (IME) for other languages: Enter must not save while text is still being composed.
- Should Enter in other fields (Due, Collections) also save?

**Recommendation:** B now. Consider D in a later round if adding tasks in bulk is a common need.

**Decision:** —

**Implementation notes:** —

**Acceptance criteria:** —

---

## R1-3 — "Save & close" button (keep plain Save?)

**Reported:** "Save and exit button (not sure whether to keep Save button)"

**Problem (restated):** Most edits end with "save, then close," which currently takes two clicks on two separate buttons. It isn't clear whether "save but keep editing" deserves its own button.

**Options**

- **A — One main button: "Save & close."** Ctrl+S still saves without closing. ✕ closes and asks first if there are unsaved changes.
    - **Pros:** one obvious action; long notes can still be saved mid-edit with Ctrl+S.
    - **Cons:** saving in place relies on knowing the shortcut.
- **B — Both buttons.** "Save & close" is the main button; "Save" is smaller next to it.
    - **Pros:** everything is visible.
    - **Cons:** more clutter in the header.
- **C — Autosave.** Changes are saved automatically about 1–2 seconds after you stop typing, and there is no Save button, just "Saved ✓" and Close.
    - **Pros:** nothing to remember.
    - **Cons:** much more frequent writes to Google Drive; more chance of conflicts while Claude or another device edits the same file; half-finished edits get saved; the editor's Markdown rewriting happens on every pause.
- **D — Save on close.** No Save button; closing the panel saves, with Ctrl+S as a backup. A "Discard changes" option is needed.
    - **Pros:** a simple mental model.
    - **Cons:** closing to back out of an edit becomes risky.

**Recommendation:** A. Autosave (C) fits poorly with a folder shared through Google Drive and edited by Claude.

**Related:** R1-2. Enter in the title box would trigger the same save-and-close action.

**Decision:** —

**Implementation notes:** —

**Acceptance criteria:** —

---

## R1-4 — Font is too small

**Reported:** "font is too small"

**Problem (restated):** The base text size is 14px, and tags and file names are 11–12px. That's tiring to read on a typical desktop monitor at normal viewing distance.

**Options**

- **A — Raise the base size to 16px and scale everything else to match.** Cards, editor, chips, buttons and headings all grow proportionally, from a single size setting.
    - **Pros:** easy fix; one setting.
    - **Cons:** cards get taller, so fewer fit on screen.
- **B — 15px.** A middle step.
    - **Pros:** smaller change in layout.
    - **Cons:** may still feel small.
- **C — Text-size control in the app.** An A− / A+ control (or a setting), remembered per browser.
    - **Pros:** each screen can use what suits it.
    - **Cons:** one more control; overlaps with browser zoom.
- **D — Compact / Comfortable toggle.** Changes text size and spacing together.
    - **Pros:** good for big boards.
    - **Cons:** more styling to maintain.

**Stopgap available today:** Ctrl + `+` zooms the whole page, and Chrome remembers the zoom level.

**Open questions:** Is it the board, the editor, or both? Which monitor and resolution?

**Recommendation:** A, built on that single size setting so that C or D is easy to add later.

**Decision:** —

**Implementation notes:** —

**Acceptance criteria:** —

---

## R1-5 — What is Collections for?

**Reported:** "What is Collections for? Is it just a tag? How do I use it?"

**Problem (restated):** The field's purpose isn't clear, and right now it doesn't do much. It shows as a violet `#chip` and search can find it, but nothing else uses it. The original idea was groupings across lists: for example, `#wild-flower-manor` on tasks in Home, Rental and Inbox, while each task still lives in one list. The app doesn't yet do anything with that.

**Options**

- **A — Rename it Tags and make it useful.**
    - Clicking a tag filters the board to that tag, with a "✕ clear" control in the header.
    - The editor suggests tags you've already used, to avoid near-duplicates like `repair` vs `repairs`.
    - **Pros:** familiar idea; small change.
    - **Cons:** it's still "just tags."
- **B — Remove the field.** Lists and subtasks handle all the organizing.
    - **Pros:** simplest app.
    - **Cons:** no way to group across lists.
- **C — Turn Collections into views across lists.** A sidebar or menu lists each collection; choosing one shows all its tasks from every list, laid out like a board or an outline.
    - **Pros:** a real "project across areas" feature.
    - **Cons:** much more to build; it overlaps with lists.
- **D — Let a task belong to several lists.** Replace `list` with a set of lists, so the same card shows in several columns.
    - **Pros:** no separate idea to learn.
    - **Cons:** drag-and-drop gets ambiguous (move or copy?), and ordering within each list gets messy.

**Data note:** A and C can keep reading the existing `collections:` field from your current files. If it's renamed to `tags:` in the files, the app should read both and write only `tags:` from then on.

**Open questions:** Beyond lists and subtasks, what grouping do you actually reach for? For example: by property, by person, by context (phone / errands / computer)?

**Recommendation:** A. Revisit C only if you find yourself filtering by the same tag all the time.

**Decision:** —

**Implementation notes:** —

**Acceptance criteria:** —

---

## R1-6 — Track the app version

**Raised:** Geoff, in chat. "I guess we need to keep track of the version by adding a version number?"

**Problem (restated):** There's no way to tell which build of `todo.html` is open, or what changed between builds. That matters as rounds pile up, and when copies exist on more than one machine.

**Options**

- **A — Version number in the app plus a changelog.**
    - A version number (e.g. `0.2.0`) is shown small in the header, or in the tooltip on the title.
    - A `CHANGELOG.md` file next to `todo.html` lists each version, its date and the spec items it delivered (e.g. "0.2.0 — R1-1, R1-2, R1-4").
    - **Pros:** standard and simple.
    - **Cons:** the number has to be updated by hand for every build (I'd do that each round).
- **B — Date-based versions** (e.g. `2026.10.15`).
    - **Pros:** no numbering decisions.
    - **Cons:** says nothing about how big a change was.
- **C — A separate version for the file format.** Add a format version to `_todo.json` (e.g. `"format": 1`), separate from the app version.
    - The app version changes every build; the format version changes only when the structure of the task files changes (for example, if `collections` becomes `tags` in R1-5).
    - This lets a newer app upgrade older files safely, and lets an older app warn instead of damaging newer files.
    - **Pros:** protects your data as the app evolves.
    - **Cons:** one more number.
- **D — One version for each round.** Round N ships as 0.(N+1).0; fixes made between rounds increase the last number.

**Proposed numbering:**

- 0.1.0 — first build
- 0.1.1 — dark theme
- 0.2.0 — this round
- 1.0.0 — once you're using it day to day and the file format is stable

**Recommendation:** A + C, using D's numbering.

**Decision:** —

**Implementation notes:** —

**Acceptance criteria:** —

---

## R1-7 — Reorder lists by dragging

**Reported** (task "Board View"): "drag lists to reorder instead of clicking the "Move list left/right""

**Problem (restated):** To move a list, you open the list's ⋯ menu and click "Move list left/right" once for each position. Getting a list from the far right to the far left takes several clicks. Every other move on the board is drag-and-drop, so lists feel inconsistent.

**Options**

- **A — Drag a list by its header.** Grab the list's title bar and drag it sideways. The other lists slide out of the way, and the new order is saved to `_todo.json` when you drop it.
    - **Pros:** matches how cards move; the drag library the board already uses handles this.
    - **Cons:** grabbing the header must not interfere with clicking the ⋯ menu or the list name.
- **B — Drag handle only.** A small ⋮⋮ grip in the header is the only place that starts a drag.
    - **Pros:** no accidental list drags.
    - **Cons:** smaller target; one more icon.
- **C — Option A, and keep the menu items.** Drag works, and "Move left/right" stays in the ⋯ menu.
    - **Pros:** still works without a mouse (keyboard or touch).
    - **Cons:** a slightly longer menu.

**Notes:**

- In Outline view, lists are stacked top to bottom, so the same drag would move them up and down.
- Two people (or you and Claude) changing the list order at the same moment is rare. If it happens, whoever saves last wins, the same as other `_todo.json` changes today.

**Recommendation:** A, keeping the menu items as in C. If you start grabbing lists by accident, switch to B's handle.

**Decision:** —

**Implementation notes:** —

**Acceptance criteria:** —

---

## R1-8 — Clicking the open task again should close the editor

**Reported** (task "Board View"): "click a second time closes the task ui"

**Problem (restated):** Once a task's editor panel is open, the only ways to close it are the ✕ button or Esc. Clicking the same card again (the natural "I'm done looking at this" gesture) does nothing, so you have to move to the far corner of the screen to close it.

**Options**

- **A — Toggle on the same card.** Clicking the title of the task that's already open closes the panel. Clicking a different task switches the panel to that task, as it does now.
    - **Pros:** exactly what was asked; easy to learn.
    - **Cons:** none significant.
- **B — Mark the open task on the board.** The card being edited gets a blue outline, so it's obvious which card to click again to close it.
    - **Pros:** makes A discoverable; helps when the panel covers part of the board.
    - **Cons:** none significant.
- **C — Click the empty board to close.** Clicking empty space on the board (not a card) closes the panel.
    - **Pros:** a big, forgiving target.
    - **Cons:** easy to close by accident, for example after a missed drag.

**Unsaved changes:** with any option, closing with unsaved changes asks first (Save / Discard / Keep editing), as ✕ does today. If R1-3 adopts "Save & close," this prompt stays the same.

**Recommendation:** A + B. Leave C out to avoid accidental closes.

**Decision:** —

**Implementation notes:** —

**Acceptance criteria:** —

---

## R1-9 — Use the board from an Android phone

**Reported** (task "Access from Android Phone"): "Test this out"

**Requirement (Geoff, 2026-10-14):** "I want to be able to open the app from my phone and do CRUD operations on the exact same tasks (content) on my phone." This is a key requirement for the app, and it's the reason Google Drive was chosen as home for the AI brain folder.

**Problem (restated):** You want to see and update your tasks from your phone. The current board can't do that: it relies on Chrome's ability to open a local folder, which only Chrome and Edge on desktop support. On Android, "Open folder…" shows a "not available" message. A second obstacle is that the Google Drive app on Android doesn't keep a synced copy of a folder on the phone, so there's no local folder to open even if the browser could.

**Step 0 — Test (what was asked):** open `todo.html` on the phone and confirm what happens. Expected result: the demo board loads, and Open folder… says folder access isn't available. This gives us a baseline before choosing an option.

**Options**

- **A — Obsidian on Android.** Sync the tasks folder to the phone with an app like Syncthing or FolderSync, and open it as an Obsidian vault. Task files show as notes; Obsidian's Bases feature can show them as a table grouped by list.
    - **Pros:** free; works offline; no new code.
    - **Cons:** a different interface from the board; no drag-and-drop; one more sync app to keep running.
- **B — Read-only phone snapshot.** Claude (or a script) generates an HTML page of the current tasks into Drive, which you open on the phone.
    - **Pros:** simple and readable anywhere.
    - **Cons:** read-only, and only as fresh as the last time it was generated.
- **C — Phone version that talks to Google Drive directly.** The board loads and saves task files through Google's Drive API, signing in with your Google account. It still has no server of its own; your Drive stays the only storage.
    - **Pros:** the same board on any device, phone included; no sync app needed.
    - **Cons:** needs a one-time Google Cloud setup (free) and sign-in; slower than local files; offline use is limited; the biggest build of these options.
- **D — Ask Claude from the phone.** In the Claude Android app with the Google Drive connector, say "add 'buy filters' to Rental" or "what's due this week?". This works today; it's what I did earlier when I listed your tasks.
    - **Pros:** available now; no code.
    - **Cons:** no visual board; every change goes through chat.

**Feasibility (2026-10-14):** yes, the one-`.md`-file-per-task approach meets the requirement. The files on Google Drive stay the single source of truth; what needs to change is how the app reaches them.

- **On desktop today:** the browser opens the folder that Google Drive for desktop keeps on your PC.
- **On the phone:** that path doesn't exist. The app has to talk to the Google Drive API directly, which is option C.
- **The pieces C needs:**
    - **A third way to load and save files.** The app already has two (demo data in memory, and a local folder), so a Google Drive version slots in alongside them. Parsing, the editor, demote and promote don't change.
    - **An https web address for the app.** Google sign-in won't work from a file opened off disk or from a claude.ai artifact page. Free options include GitHub Pages, Cloudflare Pages and Netlify.
    - **A one-time Google Cloud setup (free):** a project with the Drive API turned on, an OAuth web client ID, and you as the only test user. Google shows an "unverified app" screen the first time you sign in.
    - **Sign-in through Google:** the browser gets a short-lived access token and refreshes it in the background.
    - **The same conflict check as today,** using the file's modified time on Drive, plus checking the folder for changes every few seconds.
- **How edits reach each device:** a change made on the phone is written to Drive, Drive for desktop brings it down to the PC, and the desktop board picks it up. Claude's Drive connector sees the same files.
- **Tradeoffs:**
    - No offline use on the phone at first.
    - Each save takes a moment longer than a local file.
    - You depend on Google's API for phone access. Your data stays plain `.md` files, though, and the Drive-specific part is one isolated piece that could be swapped for Dropbox or WebDAV later.
- **Rejected for this requirement:**
    - **A (Obsidian):** works on the same files, but it isn't this app.
    - **B (snapshot):** read-only.
    - **D (Claude chat):** has no board interface; it remains a good companion.
    - **A native Android app wrapper:** possible, but it means sideloading and much more work.

**Recommendation:** Run Step 0. Use D right away, since it needs nothing new. Then decide between A (quick, free, local) and C (the real phone board, a bigger project). C probably deserves its own round.

**Open questions:** On the phone, do you mostly want to check tasks off and glance at them, or also reorganize (drag, nest, demote)? That decides whether A or D is enough, or whether C is worth building.

**Decision:** —

**Implementation notes:** —

**Acceptance criteria:** —

---

## R1-10 — Work tasks on work OneDrive, usable from Android

**Requirement (Geoff, 2026-10-14):** "I would like it to also use my works MS OneDrive as the common file storage location so I can access my work items on my android phone through my local android work onedrive app."

**Problem (restated):** Work tasks should live in your **work** OneDrive (Microsoft 365), not your personal Google Drive. The same board should open them, and you should be able to do CRUD on them from your Android phone, where your work OneDrive app is already signed in. So the app needs more than one storage location: personal tasks in Google Drive, work tasks in work OneDrive. Each location is kept separate, and you switch between them in the app.

**What's feasible, honestly:**

- **Work PC:** this already works in principle. The OneDrive sync app keeps the work folder on your PC, and the board opens it with "Open folder…" just like the Google Drive folder. The one risk is that IT may have turned off this browser feature on managed machines.
- **Android, through the OneDrive app itself: no.** The OneDrive app can open a single `.md` file in a text viewer or editor, but it can't run the board, and it doesn't keep a synced folder a browser could open. That's the same limit as Google Drive in R1-9.
- **Android, in the phone's browser, signed in with your work account: yes, in principle.** The board talks to OneDrive through Microsoft's official API (Microsoft Graph), the same way R1-9's option C talks to Google Drive. The files stay in work OneDrive, so they still show up in the OneDrive app, and edits from either side are seen by the other.

**Options**

- **A — OneDrive backend plus a location switcher.** Add a way to load and save files through Microsoft Graph, next to the Google Drive one from R1-9. The header gets a location picker (e.g. "Personal · Google Drive" / "Work · OneDrive").
    - **Pros:** meets the requirement fully; same app and same file format everywhere.
    - **Cons:** needs an app registration in Microsoft Entra ID in your **work** organization, and your company's policies have to allow it (see Blockers).
- **B — Work PC only.** Use work tasks through the synced OneDrive folder on the work PC; no phone access.
    - **Pros:** no IT involvement; works today.
    - **Cons:** fails the phone part of the requirement.
- **C — Phone fallback without the board.** Open the `.md` files from the OneDrive app in a Markdown editor app on the phone.
    - **Pros:** no code.
    - **Cons:** raw files with no board; your company's mobile app policy may block opening work files in an unmanaged app.
- **D — Keep work tasks in Google Drive.** **Not recommended:** work data in a personal account likely breaks company policy.

**Blockers to check with IT, or by trying it:**

1. **App registration and consent.** Can you register an app, or consent to one, that reads and writes your own OneDrive files? Many companies let staff consent to low-access permissions themselves; others require an admin to approve.
2. **Phone access rules.** Your company may require a managed device or approved apps before work data opens on a phone. If so, a browser-based app on your phone may be blocked even with a valid sign-in.
3. **Policy on personal tools.** Is it acceptable to keep work task files in work OneDrive and read them with a personal tool hosted on GitHub Pages? The files never leave OneDrive, but some policies still prohibit it.
4. **Claude's access.** The Microsoft 365 connector doesn't expose OneDrive file reading and writing, so Claude can't reach work tasks the way it reaches your Google Drive tasks. On the work PC, a Cowork session with the work folder connected would work.

**Architecture impact (affects R1-9 too):**

- **One app, several storage connectors:** demo, local folder, Google Drive, OneDrive. A saved list of locations (name plus connector plus folder) is kept in the browser.
- **Locations never mix.** Work and personal tasks stay in separate folders on separate services, and nothing moves between them by accident.
- **Build order:** build the Google Drive connector first (no outside approvals needed), then OneDrive once IT questions 1–3 are answered.

**Open questions:**

- **Is the browser on your phone acceptable**, or must it literally be inside the OneDrive app? Inside the OneDrive app isn't technically possible for a custom board.
- **Is the work PC a company-managed machine** with locked-down Chrome or Edge?

### Step 1 — Prove it with a personal OneDrive (agreed 2026-10-14)

**Why:** R1-10 is the toughest item. A **personal** Microsoft account uses the same Microsoft Graph API as a work account, but none of the company policies apply. So it tests the technical approach first, separately from the IT questions. If it works on personal OneDrive, the only open questions for work OneDrive are about policy.

**Design**

- **Sign-in:** Microsoft's sign-in library for browser apps (MSAL.js, using the authorization-code flow with PKCE). There's no client secret and no server.
- **Scopes (permissions):** `Files.ReadWrite` lets the app use any folder you pick. The alternative, `Files.ReadWrite.AppFolder`, is narrower but limits the app to `/Apps/<app name>/`. Plus `User.Read` and `offline_access`.
- **One app registration for both accounts:** set "Supported account types" to "any organization directory + personal Microsoft accounts", so the same registration can later attempt a work-account sign-in.
- **Graph calls the OneDrive connector would use:**
    - **List:** `GET /me/drive/root:/{folder}:/children?$select=id,name,eTag,lastModifiedDateTime,size,@microsoft.graph.downloadUrl`
    - **Read:** fetch the `downloadUrl`. It's pre-authenticated, which avoids redirect and CORS problems.
    - **Update:** `PUT /me/drive/items/{id}/content` with `If-Match: {eTag}`. A `412` response means someone else changed the file, which triggers the existing conflict dialog. This is a **true** conditional write, safer than the Google Drive check (no race window).
    - **Create:** `PUT /me/drive/root:/{folder}/{name}:/content?@microsoft.graph.conflictBehavior=fail`. A `409` response means the name is taken.
    - **Delete:** `DELETE /me/drive/items/{id}` with `If-Match`.
    - **Watch for changes:** a delta query on the folder (`/delta`, which returns only what changed since the last check). Personal OneDrive supports this on any folder, but **work OneDrive supports it only at the drive root**, so the connector falls back to periodic listing there. Real proof that the storage interface needs to hide these differences.
    - **Load quickly:** keep each file's content in the browser's local storage, keyed by eTag. Only changed files are downloaded again. A first load of many files uses `$batch`, which bundles up to 20 requests per call.
- **Hosting:** the page needs an https address for Microsoft sign-in, for example GitHub Pages. Desktop testing can use `http://localhost`.
- **Desktop and phone:** the phone always uses the OneDrive connector. The PC can use either the OneDrive sync folder (local, works offline) or the same connector. Both see the same files.
- **Claude's access:** for personal OneDrive, Claude reaches the files through a Cowork session with the OneDrive folder on your PC connected, not through a connector. That's a difference from Google Drive, where the connector works.

**Proof-of-concept plan** (a throwaway `poc.html`, not the app)

1. **Prep:** create a `HTML-ToDo-App-Test` folder in your personal OneDrive and copy 3–5 task `.md` files into it.
2. **Register the app** in the Microsoft Entra admin center. Choose single-page application (SPA) as the platform, with the GitHub Pages address and `http://localhost:8000` as redirect addresses. Note the client ID. No secret is needed. *Registering may require an Entra directory tied to your personal account, which a free Azure sign-up provides. We'll confirm during setup.*
3. **Host** `poc.html` on GitHub Pages.
4. **On your phone (Chrome),** in this order:
    1. Sign in.
    2. List the folder.
    3. Open a file.
    4. Edit and save it.
    5. Create a file, then delete it.
    6. Edit a file in the OneDrive app, then try saving the same file in the test page. **Expected:** a 412 conflict.
    7. Change a file on the PC and time how long the page takes to notice.
    8. Reopen the page the next day and see whether it signs in silently.

**Proof of concept succeeds if:**

- [ ] Sign-in works on Android Chrome.
- [ ] Create, read, update and delete all work on the same files that show in the OneDrive app and on the PC.
- [ ] The conflict is detected (412).
- [ ] Changes appear on the other device within about 30 seconds.
- [ ] Having to sign in again is no more than about daily and is painless.

**Recommendation:** Run Step 1 (the personal OneDrive proof of concept) first. Separately, ask IT questions 1–3, or try a quick test sign-in once the R1-9 proof of concept exists. If allowed, do A after the Google Drive connector. Until then, use B on the work PC.

**Decision:** —

**Implementation notes:** —

**Acceptance criteria:** —

---

## R1-11 — Rename the app to HTML-ToDo-App

**Reported** (in chat, 2026-10-15): "I do not like the name "TaskBoard" for this app. I want you to change the context everywhere you can to state that this app should be called "HTML-ToDo-App"."

**Decision:** The display name is **HTML-ToDo-App** in docs, the app title and heading, the PoC page and the Azure app registration (`HTML-ToDo-App PoC`). The local folder, GitHub repository and Pages URLs keep the lowercase slug `html-todo-app` (URL convention; nothing breaks). The OneDrive test folder becomes `HTML-ToDo-App-Test`. Old decision-log rows keep the old name as history.

**Implementation notes:** Text-only change in `app/todo.html` (`<title>`, `<h1>`, header comment), approved by Geoff 2026-10-15. No version bump yet (versioning is R1-6).

**Acceptance criteria:** No "Task Board"/"TaskBoard" outside history rows and the vendor folder; the app and PoC pages on GitHub Pages show the new name.

---

## Decision log

| Date | Item | Decision | Notes |
|---|---|---|---|
| 2026-10-15 | R1-10 | App registered: `HTML-ToDo-App PoC`, client ID `18f50dc2-e8ba-4b12-8735-1cf7d6c873cd`, "Any Entra ID Tenant + Personal Microsoft accounts", SPA redirect `https://gvd1024.github.io/html-todo-app/poc/`, delegated `Files.ReadWrite` + `User.Read`. PoC v0.0.2 has the client ID built in (Geoff's choice, so it needn't be typed on the phone) | Ready for phone test |
| 2026-10-15 | R1-11 | App renamed to **HTML-ToDo-App** (display name everywhere); slugs stay `html-todo-app`; OneDrive test folder `HTML-ToDo-App-Test`; app title text changed with Geoff's approval | Built |
| 2026-10-15 | R1-10 | Setup finding: a personal Microsoft account can't register apps in Entra without a directory ("does not exist in tenant 'Microsoft Services'", also in portal.azure.com). Fix: free Azure sign-up (phone + card verification, no charge), which created "Default Directory". App registrations are free | Registration in progress |
| 2026-10-15 | — | Repository published: `github.com/gvd1024/html-todo-app` (public) with Pages live; set up with the `gh` CLI instead of GitHub Desktop | — |
| 2026-10-14 | — | Project folder and repository renamed from `taskboard` to `html-todo-app`; Pages and Entra redirect address is now `/html-todo-app/poc/`. Earlier log rows keep the old name as history | Do before git init |
| 2026-10-14 | — | Spec created; all items Open | No build work approved |
| 2026-10-14 | — | Moving development to Claude Code. A repository package was prepared: `taskboard` (app/, poc/, docs/specs/, CLAUDE.md, HANDOFF.md; private/ is git-ignored). The proof-of-concept address moves to `/taskboard/poc/` | Repository must be public for free GitHub Pages |
| 2026-10-14 | R1-10 | Geoff approved building the throwaway proof of concept (not the app). Built PoC v0.0.1 (`taskboard-poc.zip`: index.html + MSAL bundle + SETUP.md); tested against a simulated Graph API. Uses `Files.ReadWrite`, granted by Geoff on the Microsoft consent screen | Waiting on Geoff's GitHub Pages + Entra setup and phone test |
| 2026-10-14 | R1-10 | Geoff agrees R1-10 is the toughest item. Approach: prove it first with **personal** OneDrive on the phone (Step 1); design and proof-of-concept plan recorded | Proof of concept not yet approved to build |
| 2026-10-14 | R1-10 | Added: work tasks in work OneDrive with Android access. Feasible through Microsoft Graph in the phone browser, not inside the OneDrive app; depends on company policy | IT questions pending |
| 2026-10-14 | R1-9 | Elevated to key requirement: full CRUD on the same Drive files from Android. Feasibility recorded; leaning C | Hosting choice and Google Cloud setup still to decide |
| 2026-10-14 | R1-7 to R1-9 | Added from the "Board View" and "Access from Android Phone" tasks; all Open | Markdown chosen as the spec format; HTML copy removed |

## Change history of this spec

- 2026-10-14 — v1 of the spec: R1-1 to R1-6 captured, with options and recommendations.
- 2026-10-15 — v8: added R1-11 (rename to HTML-ToDo-App); logged GitHub publish and the Azure-directory finding for R1-10.
- 2026-10-14 — v7: logged the move to Claude Code and the repository layout.
- 2026-10-14 — v6: logged PoC build and approval.
- 2026-10-14 — v5: R1-10 Step 1 (personal OneDrive design and proof-of-concept plan).
- 2026-10-14 — v4: added R1-10 (work OneDrive requirement).
- 2026-10-14 — v3: R1-9 updated with the phone requirement and the Drive-backend feasibility notes.
- 2026-10-14 — v2: added R1-7, R1-8 and R1-9 (the rest of the Feedback list); scope rule updated.
