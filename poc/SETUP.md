# OneDrive PoC — setup (about 20 minutes)

This is a throwaway test page for spec item R1-10, step 1. It checks that a web page on your Android phone can create, read, update and delete `.md` files in your **personal** OneDrive. It is not the Task Board.

You do three things, in order: put the page on GitHub Pages, register it with Microsoft, and put a few test files in OneDrive. Then you test it on your phone.

---

## A. Put the page on GitHub Pages (about 5 min)

The proof of concept lives in the `poc/` folder of the `html-todo-app` repository, alongside the app and the specs.

1. Make sure the repository is pushed to GitHub. See `HANDOFF.md` at the repository root.
2. On github.com, open the repository and go to **Settings → Pages**. Under "Build and deployment", set **Source** to *Deploy from a branch*, **Branch** to `main`, and folder to `/ (root)`, then click **Save**.
   - Free GitHub Pages needs a **public** repository. Only code and docs are public; your task files stay in OneDrive and Google Drive.
3. Wait about 1 minute, then open:
   `https://gvd1024.github.io/html-todo-app/poc/`
   You should see the dark "OneDrive PoC" page. The **Redirect URI** shown on the page is what you'll paste in step B.

## B. Register the app with Microsoft (about 10 min)

This step is where the page gets permission (`Files.ReadWrite`) to read and write your OneDrive. **Claude never gets this access.** The access token stays in your browser and is used only by this page.

1. Go to **https://entra.microsoft.com** and sign in with your **personal** Microsoft account (the one that owns your OneDrive).
   - If it says you don't have access or need a directory or tenant, go to **https://portal.azure.com** instead and sign up for the free Azure account. That creates the directory app registrations need. Microsoft may ask for a card to verify your identity; there's no charge for this. If you hit this step, tell Claude what the screen says.
2. Go to **Applications → App registrations → + New registration**.
   - **Name:** `TaskBoard PoC`
   - **Supported account types:** *Accounts in any organizational directory and personal Microsoft accounts*. This lets the same registration try your work account later.
   - **Redirect URI:** platform **Single-page application (SPA)**, and the address exactly as the page shows it, e.g. `https://gvd1024.github.io/html-todo-app/poc/`. Include the trailing `/`.
   - Click **Register**.
3. On the app's **Overview** page, copy the **Application (client) ID**. It's a 36-character ID and isn't secret.
4. Go to **API permissions → + Add a permission → Microsoft Graph → Delegated permissions**, tick **Files.ReadWrite**, and click **Add permissions**. (`User.Read` is already there.) For a personal account, no admin approval is needed; you approve it yourself the first time you sign in.
5. Optional, for testing on your PC: go to **Authentication → Single-page application → Add URI** and add `http://localhost:8000/poc/` (serve the repository root with `python -m http.server 8000`).

You don't need a client secret or certificate. Ignore those sections.

## C. Prepare a test folder in OneDrive (about 2 min)

1. In OneDrive (web, PC or phone), create a folder named **`TaskBoard-Test`** at the top level.
2. Copy 3–5 task `.md` files into it, e.g. the ones from `HTML_ToDo_Files` in Google Drive. **Use copies**, not your only versions.

## D. Test on your phone

1. Open `https://gvd1024.github.io/html-todo-app/poc/` in **Chrome** on your phone.
2. Paste the **client ID** and tap **Sign in with Microsoft**. On the consent screen, "TaskBoard PoC wants to… access your files", tap **Accept**. Microsoft may say the app is unverified; that's expected for a personal test app.
3. Work through the **Test checklist** on the page. The conflict test goes like this:
   1. Open a file on the page.
   2. Edit the same file somewhere else: in the OneDrive app, on onedrive.com, or on the PC. Save it there.
   3. Change the text on the page and tap **Save**. You should see the orange **412** box.
4. For the change-detection test, edit a file on the PC and watch the log for **CHANGE DETECTED**. The timestamps show how long it took.
5. Tap **Copy results + log** and paste the result into the chat with Claude.
6. Optional: in Chrome, use **⋮ → Add to Home screen** so it opens like an app.
7. **Next day:** open the page again. If it shows your account without asking for a password, staying signed in works.

## Undo everything afterwards

- **Microsoft access:** delete the app registration in Entra. Also remove its permission at https://account.live.com/consent/Manage.
- **GitHub:** turn off Pages, or delete the `poc/` folder.
- **OneDrive:** delete the `TaskBoard-Test` folder.

## Troubleshooting

| What you see | Likely cause |
|---|---|
| `AADSTS50011` redirect URI mismatch | The Redirect URI in Entra doesn't exactly match the page's, including the trailing `/` and https. |
| `AADSTS700016` application not found | Client ID typo, or the registration doesn't allow personal accounts. |
| `unauthorized_client` / the app isn't enabled for consumers | Supported account types doesn't include personal Microsoft accounts. |
| `404` when listing | The folder name doesn't match. Check the "OneDrive folder" field on the page. |
| Page is blank | Check that the `vendor` folder was uploaded with `msal-browser.min.js` inside. |
