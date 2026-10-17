# HANDOFF — from the Cowork session to Claude Code (2026-10-14)

## Read in this order
1. `CLAUDE.md`: rules, file format, code map.
2. This file: the current state and what's next.
3. `docs/specs/round-1-spec.md`: every open item and the decision log.
4. Optional, for background: `private/memory-export.md` and `private/cowork-session-transcript.md`. These are local only and git-ignored, because the repository is public.

## Current state
| Thing | State |
|---|---|
| App `app/todo.html` | **v0.1.1**. Works on desktop Chrome or Edge against a local or Drive-synced folder. Dark theme. Geoff is using it on `HTML_ToDo_Files` (Google Drive for desktop). |
| Round 1 spec | 10 items. R1-9 and R1-10 are *Discussing*; the rest are *Open*. **Nothing is approved for build in the app.** |
| OneDrive proof of concept `poc/` | **v0.0.2** (client ID built in). **Phone test passed 2026-10-15** on Android Chrome against personal OneDrive `HTML-ToDo-App-Test`: CRUD OK, 412 conflict detected, change detection 2–3 s. **Step 1: 4 of 5 criteria pass.** Silent sign-in **failed** after about 12 h (username and password needed again); open issue, see spec R1-10 finding 5. Dual-access test with the real app (PC, OneDrive-synced folder) plus the PoC (phone): 5/5 pass. |
| Repository | Local: `C:\dev\github.com\gvd1024\html-todo-app\`. Remote: **`https://github.com/gvd1024/html-todo-app`** (public, `main`), with git and GitHub driven by the `gh` CLI. |
| GitHub Pages | **Live** from `main`, root: `https://gvd1024.github.io/html-todo-app/poc/` and `/app/todo.html` both return 200. |
| Microsoft Entra app registration | **Done** (2026-10-15) in Geoff's free Azure "Default Directory": `HTML-ToDo-App PoC`, client ID `18f50dc2-e8ba-4b12-8735-1cf7d6c873cd`, any tenant + personal accounts, SPA redirect `/html-todo-app/poc/`, `Files.ReadWrite`. Built into PoC v0.0.2. |

## Update 2026-10-15
- The folder and repository were renamed `taskboard` → `html-todo-app` before git init. Geoff renamed the folder by hand and re-pointed the Claude Code project at it. All paths, the remote and the Pages/Entra redirect address use `html-todo-app`.
- Geoff may switch between the Claude desktop Code tab and the Claude Code CLI in this folder. Continuity comes from `CLAUDE.md`, this file and the spec, so keep them current. Don't run two sessions on the folder at once.
- Git is still **not** initialized.

## Update 2026-10-15/16: git and GitHub set up
Geoff now runs the Claude Code **CLI** in the VS Code built-in terminal (terminal panel on the right, `/ide` connected). He chose the **`gh` CLI** over GitHub Desktop, with Claude running the commands.
- **Setup:**
  - `gh` 2.102.0 is installed at `C:\Program Files\GitHub CLI\gh.exe` and logged in as `gvd1024` (HTTPS, keyring). Terminals opened before the install don't have `gh` on PATH, so use the full path with `&`.
  - The repo-local identity is `Geoffrey V. Davis II <35988830+gvd1024@users.noreply.github.com>`, a noreply address that keeps personal email out of the public history. The global git config is unchanged.
  - `.gitignore` excludes `private/` and `.claude/settings.local.json`.
- **Published:**
  - Initial commit `4b0187c` (15 files) was pushed with `gh repo create --public`.
  - Pages was enabled through the API and built successfully.
- **Follow-up to remind Geoff about: spell check in the CLI prompt.** The plan is to install the VS Code extension "Code Spell Checker" (streetsidesoftware), then point Claude Code's external editor (Ctrl+G, or Ctrl+X then Ctrl+E) at VS Code (`code --wait`). Long prompts then get written in a spell-checked VS Code tab. First verify how Claude Code picks the editor on Windows, and whether VS Code grabs Ctrl+G.
- **Possible follow-up:** the Super Productivity MCP (`sp-local-rest`) is configured only in Claude desktop, not in Claude Code, so todo requests don't work from the CLI yet.

## Next steps (Geoff)
- [x] Create and publish the GitHub repository and enable Pages. Done with the `gh` CLI (see above).
- [x] Register the app in Entra (done 2026-10-15, via a free Azure directory):
  - **Platform:** single-page app (SPA).
  - **Accounts:** "any org directory + personal Microsoft accounts".
  - **Redirect URI:** `https://gvd1024.github.io/html-todo-app/poc/`.
  - **Permission:** delegated `Files.ReadWrite`.
  - If a personal account can't register without a directory, a free Azure sign-up provides one. Note what the screen says.
- [x] Create the `HTML-ToDo-App-Test` folder in personal OneDrive (done; 5 copied task files).
- [x] Run the checklist on the Android phone (passed 2026-10-15).
- [x] Paste the **Copy results + log** output to Claude (done; analyzed in R1-10).
- [x] Silent sign-in check (2026-10-15, about 12 h later): **failed**, password required.
- [x] Signed in again 2026-10-16 08:47 and tapped **Yes** on "Stay signed in?".
- [ ] **Retest 2026-10-17 morning:** open the PoC on the phone. It will show "Not signed in" (expected; MSAL's key is in a session cookie). Tap Sign in: pass if Microsoft signs you in **without asking for email or password**.

## Next steps (Claude, only once Geoff asks)
- Analyze the proof-of-concept results. Record them in R1-10 (Step 1) and the Decision log.
- If the proof of concept passes: draft the **storage connector interface**. Design it against **both** Microsoft Graph and the Google Drive API, then decide whether R1-9 and R1-10 move into their own architecture spec (`docs/specs/storage-spec.md`).
- Possible follow-up test: sign in to the same proof of concept with the **work** account, to answer the IT questions empirically.

## Key decisions so far
- One Markdown file per task, with YAML frontmatter, as the single source of truth. No server.
- Board: lists are a **field** (`list:`), not folders. Ordering is fractional. Subtasks use `parent:`.
- Editor: Toast UI (with a known side effect: it reformats Markdown when it saves).
- Demote and promote keep data by archiving the original file and adding a link to it.
- Specs are Markdown, one per round, with numbered items.
- Phone CRUD on the same files is a **key requirement** (R1-9). Work OneDrive with phone access is a requirement (R1-10) and the hardest item, so it's being proven first with **personal** OneDrive.
- The proof of concept uses `Files.ReadWrite` (any folder), not the narrower AppFolder permission.
- Proposed build order:
  1. Proofs of concept.
  2. Storage interface, data-format version (R1-6C) and the Collections decision (R1-5).
  3. Hosting, the Google Drive connector and the phone layout.
  4. The OneDrive connector and location switcher.
  5. The UI items.

## Known technical facts to carry forward
- **Graph vs Google Drive:**
  - Graph supports a true conditional save (`If-Match` → 412). The Drive API v3 doesn't, so the Drive connector has to check the modified time before writing, which leaves a small race window.
  - On **personal** OneDrive, the delta query works on any folder. On work OneDrive and SharePoint it works only at the drive **root**, so that connector falls back to periodically listing the folder.
- **Browser limits:**
  - The File System Access API works only in desktop Chrome and Edge. Android and Firefox can't use it.
  - The Google Drive Android app doesn't keep a synced folder on the phone.
- **Claude's access:**
  - Claude can reach Google Drive files through the connector.
  - The Microsoft 365 connector doesn't expose OneDrive file reading and writing, so for OneDrive, Claude works through a synced folder on the PC.
- **Hosting:** artifact pages on claude.ai can't host the Google or Microsoft sign-in flow (external hosts are blocked, and sign-in needs a fixed https address). That's why the app is hosted on GitHub Pages.
