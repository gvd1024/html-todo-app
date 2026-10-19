# HTML-ToDo-App — Security review

| Field | Value |
|---|---|
| **Date** | 2026-10-18 |
| **Reviewed version** | app v0.2.0-dev (repository state at commit `505ba1c` plus this file and the new hostile-file test) |
| **Reviewer** | Claude (AI assistant, Claude Code CLI) at Geoff's request |
| **Status** | Self-review. It is **not** a substitute for an independent review. The commands under "How to verify this yourself" let anyone re-check every claim. |

## Summary
- **What it is:** HTML-ToDo-App is a **static web page with no server of its own**. It runs entirely in the browser, signs in with Microsoft, and reads and writes `.md` files in **one folder of the signed-in user's own OneDrive** through Microsoft Graph.
- **Where data goes:** task data never goes anywhere except the user's OneDrive. Verified by reading all of our code, by scanning every third-party library, and by recording every network request in a live session.
- **Findings:** no malicious code was found. Six findings are listed below; none is an active vulnerability as tested. **F4 (broad file permission)** and **F5 (who controls the hosted code)** matter most for a workplace deployment.

## Architecture and data flow
```
 Browser (phone or PC)                         Microsoft (the user's own tenant / account)
 ┌────────────────────────────┐   sign-in     ┌───────────────────────────────┐
 │ index.html + vendor/*.js   │ ────────────► │ login.microsoftonline.com     │
 │ (static files, no backend) │ ◄──── token ─ │ (MSAL, auth code + PKCE)      │
 │                            │   files       ├───────────────────────────────┤
 │                            │ ◄───────────► │ graph.microsoft.com (OneDrive)│
 └────────────────────────────┘               │ + OneDrive file-download host │
        ▲ page files only                     └───────────────────────────────┘
 gvd1024.github.io (GitHub Pages, static hosting)
```
- **Sign-in:** Microsoft's MSAL.js (Browser 5.22.0), authorization-code flow with PKCE, redirect mode. **No client secret exists.**
- **Permissions (delegated, granted by the user at sign-in):** `Files.ReadWrite` and `User.Read`. See F4.
- **Token storage:** MSAL's cache in `localStorage`, encrypted by MSAL with a key held in a session cookie.
- **App settings in `localStorage`:** folder name, text size, last list, and an unsaved draft during a sign-in redirect.
- **Writes:** every update and delete is conditional (`If-Match` with the file's eTag). Creates use `conflictBehavior=fail`. Deletes go to the OneDrive recycle bin.
- **Service worker (`app/sw.js`, 8 lines):** passes page loads to the network and **caches nothing**.
- **Tests (`tests/`):** run only on a developer PC; never loaded by the app.

## Network destinations
| Destination | Purpose | Where in code |
|---|---|---|
| `gvd1024.github.io` | Serves the app's own static files | hosting |
| `login.microsoftonline.com` | Microsoft sign-in (MSAL) | `MsalAuth`, `vendor/msal-browser.min.js` |
| `graph.microsoft.com` | List, read, write and delete files in the chosen OneDrive folder | `GraphStore.req()` (`app/index.html`) |
| OneDrive's pre-authenticated download URLs (returned by Graph) | Read file contents | `GraphStore.read()` |

**There are no other destinations.**
- **No analytics, telemetry, fonts, CDNs or external scripts.** Every script is loaded from the app's own `vendor/` folder.
- **Runtime check:** a recorded browser session (load, open the editor, switch modes, save, close) contacted only the app host, Graph and the download host.
- **MSAL's other built-in addresses** (`login.microsoftonline.us`/`.de`, `login.chinacloudapi.cn`) are for sovereign clouds and aren't used with the `/common` authority.
- **`aka.ms`** appears only in MSAL's error-message text.

## Our code (fully read)
| File | Lines | Result |
|---|---|---|
| `app/index.html` | ~1,470 | **No `eval`, no `new Function`, no dynamic script loading, no `sendBeacon`, no WebSocket.** Exactly two `fetch` calls (Graph and the OneDrive download URL). All 11 `innerHTML` writes escape file-derived text (titles, list names, statuses, file names, unknown keys, checklist text) through `esc()`. |
| `app/sw.js` | 8 | Network-only for page loads. No caching, and it doesn't touch API requests. |
| `app/todo.html` | 6 | Redirect to `./`. |
| `app/manifest.webmanifest` | 17 | Static metadata. |
| `poc/index.html` | ~340 | The old OneDrive proof of concept. Same Graph and Microsoft destinations, with escaped output. Not used by the app. |
| `tests/*` | ~750 | Test harness (Playwright, plus a fake Graph). Not loaded by the app. |

**Hostile-file test (added to `tests/run_tests.py`, group `security`):** task files with script and `onerror` payloads in the title, list name, status, prefix, an unknown key and the body (including `<script>` and a `javascript:` link) are loaded, listed, opened in both editor modes, and shown in menus.
- **Result: nothing executes.** The markup shows as text.
- **A positive control proves the test works:** the same payload injected without escaping *does* fire.

## Third-party libraries
| File | Library | Verification | SHA-256 |
|---|---|---|---|
| `app/vendor/js-yaml.min.js` | js-yaml 4.1.0 | ✅ **Byte-identical** to npm `js-yaml@4.1.0` `dist/js-yaml.min.js` | `45dc3dd03dc07a06705a2c2989b8c7f709013f04bd5386e3279d4e447f07ebd7` |
| `app/vendor/Sortable.min.js` | SortableJS 1.15.2 (not loaded yet) | ✅ **Byte-identical** to npm `sortablejs@1.15.2` `Sortable.min.js` | `ca68430703c4f5960e90735867c6e94d29b5a3de37107d8100e5a301007e9e6e` |
| `app/vendor/toastui-editor.css` | Toast UI Editor 3.2.2 | ✅ **Byte-identical** to npm `@toast-ui/editor@3.2.2` `dist/toastui-editor.css` | `c0ceb967b8c97038dccaa2a35c2222ec35b53a0022febbb6a22715c23ead9211` |
| `app/vendor/toastui-editor-dark.css` | Toast UI Editor 3.2.2 | ✅ **Byte-identical** to npm `dist/theme/toastui-editor-dark.css` | `ed442a29f63a60567231efb1d17293e2b1e0ba8bdf8bc5176f9b55e01ad22001` |
| `app/vendor/msal-browser.min.js` (= `poc/vendor/…`) | MSAL Browser 5.22.0 | ⚠ **Not byte-identical** (bundled with esbuild earlier). Reports version 5.22.0; scan found only Microsoft sign-in domains. **See F2.** | `4e11fe5efa6d1b09257e8269054c24e6b9755a745445936aab4c2dc8ea876675` |
| `app/vendor/toastui-editor-all.min.js` | Toast UI Editor 3.2.2 + ProseMirror + DOMPurify | ⚠ **Not byte-identical** (bundled with esbuild, since npm has no single-file "all" build). Scan: no `eval`/`new Function`/`sendBeacon`; the only external URL in code is the Google Analytics usage-statistics endpoint, **disabled** (see F3). | `b5a27d149ef87cf315857b199459b5b600c035c3fbf1c5e0fcff7f8e1c11b7bf` |

The official npm `@azure/msal-browser@5.22.0` `lib/msal-browser.min.js` has SHA-256 `5ce42b98842c06a0d00233253f46684f43dd398b46cb7dd5e1441f1bfd9caa6d`.

## Findings and recommendations
| # | Severity | Finding | Recommendation |
|---|---|---|---|
| **F1** | Low | A `javascript:` link written in a task's Markdown body survives as a real `<a href="javascript:…">` in the editor's **formatted** view. In testing, clicking it did **not** execute (the editor doesn't follow links on click), so it's a latent risk, not an exploit. | Add a capture-phase click guard on the editor that blocks `javascript:`/`data:`/`vbscript:` links, plus a CSP (F6). About 5 lines. |
| **F2** | Info | The MSAL bundle can't be verified byte-for-byte. | Replace it with npm's official `lib/msal-browser.min.js` (5.22.0), so anyone can verify it by checksum. |
| **F3** | Info | The Toast UI bundle can't be verified byte-for-byte, and it contains Toast UI's usage-statistics code (Google Analytics). The app sets `usageStatistics: false`, and the runtime capture confirmed no request to Google. | Keep it disabled. Optionally, commit a reproducible build script (`npm i @toast-ui/editor@3.2.2` + esbuild) so the bundle can be rebuilt and compared. **Note: Toast UI Editor's last release (3.2.2) was 2023-02-17**, so the project looks unmaintained. Consider a maintained editor before wider or work use. |
| **F4** | **Medium (work)** | `Files.ReadWrite` lets the app read and write **every file in the user's OneDrive**, not just the task folder. The app only touches the one configured folder, but the permission allows more. | For work: use `Files.ReadWrite.AppFolder` (only `/Apps/<app name>/`) or a selected-files permission if IT prefers, at the cost of the task folder living in the app folder. |
| **F5** | **Medium (work)** | The code that runs with access to your files is served from a **personal GitHub account's Pages site**. Whoever controls that account controls the code. | Enable 2FA (and branch protection) on the GitHub account. For work: host a **reviewed, pinned copy** on company infrastructure (SharePoint, an internal static host, or Azure Static Web Apps in the company tenant) with the company's own app registration. The app is just static files, so this is easy. |
| **F6** | Low (partly addressed) | No *always-on* Content Security Policy. **Since 2026-10-18 there's an opt-in Network lock** (Settings): a CSP blocking all connections (`connect-src 'none'`, plus images, frames, forms and workers), tested served and from disk. | Add a CSP that allows scripts only from the app's own origin, and network calls only to `login.microsoftonline.com`, `graph.microsoft.com` and OneDrive's download hosts. The browser then enforces the "data goes only to Microsoft" promise. Test on real devices before relying on it. |

**Other observations (no action needed):**
- Tokens are short-lived, and MSAL encrypts its cache.
- No secrets in the repository: the Azure client ID is public by design.
- Data stays in plain `.md`/`.json` files in the user's own OneDrive.
- **The work-OneDrive path hasn't been tested yet.**

## Network lock (added 2026-10-18)
- **Where:** Settings → *Network lock: Block all network access*.
- **What happens when on:** an inline script at the top of `<head>` writes this policy before any other resource loads:
  `connect-src 'none'; img-src 'self' data: blob: file:; media-src 'none'; frame-src 'none'; child-src 'none'; worker-src 'none'; object-src 'none'; form-action 'none'; manifest-src 'self' file:; font-src 'self' data: file:`
- **The app with the lock on:** OneDrive/MSAL is disabled and the service worker isn't registered.
- **Tests** (`tests/run_tests.py`, group `netlock`), from a web server and from `file://`:
    - a Graph fetch, an image beacon and an analytics fetch are all blocked (Chrome failure reason `csp`), with no response from any outside host;
    - CSP violation events are raised;
    - with the lock off, the same fetch goes through (control).
- **Limits:**
    - The setting lives in the browser's `localStorage`.
    - Top-level navigation isn't covered by CSP; the app performs none while locked.
    - Script sources aren't restricted, but all scripts are the app's own local files.

## How to verify this yourself
```bash
git clone https://github.com/gvd1024/html-todo-app && cd html-todo-app
# 1) every network destination in our code
grep -noE "https?://[a-zA-Z0-9.-]+" app/index.html app/sw.js
grep -nE "fetch\(|eval\(|new Function|sendBeacon|importScripts|WebSocket" app/index.html app/sw.js
# 2) byte-compare the vendored libraries with the official npm releases (downloads only, nothing runs)
mkdir /tmp/v && cd /tmp/v && for p in js-yaml@4.1.0 sortablejs@1.15.2 @toast-ui/editor@3.2.2 @azure/msal-browser@5.22.0; do npm pack $p; done
for t in *.tgz; do mkdir -p "${t%.tgz}" && tar -xzf "$t" -C "${t%.tgz}"; done
sha256sum */package/dist/js-yaml.min.js */package/Sortable.min.js */package/dist/toastui-editor.css */package/dist/theme/toastui-editor-dark.css */package/lib/msal-browser.min.js
# 3) domains inside the two bundled libraries
grep -oE "https?://[a-zA-Z0-9.-]+\.[a-z]{2,}" app/vendor/toastui-editor-all.min.js app/vendor/msal-browser.min.js | sort | uniq -c
# 4) the automated tests, including hostile task files (needs Python + Playwright)
python tests/run_tests.py
```
