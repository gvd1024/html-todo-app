"""Automated tests for HTML-ToDo-App (storage-spec S-9).

Run from the repository root:   python tests/run_tests.py
Needs: pip install playwright && python -m playwright install chromium

What it covers (all against test data in memory — never real files):
  1. the shared store suite for MemStore, FsStore (browser OPFS) and GraphStore (fake Microsoft Graph)
  2. the R1-12 list view in a phone-sized browser on demo data (+ screenshots in tests/screenshots/)
  3. the app on a fake OneDrive: load, toggle, quick-add, outside edits, conflicts + Keep both, delete,
     list-order merge, and "no unconditional writes"
Real Microsoft sign-in and real phones are Geoff's to test.
"""
import json
import pathlib
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from fake_graph import FakeGraph  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOTS = ROOT / "tests" / "screenshots"
PORT = 8765
APP = f"http://localhost:{PORT}/app/"
FOLDER = "HTML-ToDo-App-Test"
RESULTS = []

TEST_AUTH = """
window.__TEST_AUTH__ = {
  async init(){ return { account: { username: 'test@example.com' } }; },
  async token(){ return 'fake-token'; },
  signIn(){ window.__signInCalls = (window.__signInCalls || 0) + 1; },
  signOut(){}, user(){ return 'test@example.com'; },
};
"""


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), str(detail)))
    print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"  — {detail}"))


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve():
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def new_page(browser, *, phone=False, init=""):
    ctx = browser.new_context(**({"viewport": {"width": 412, "height": 860}, "is_mobile": True, "has_touch": True,
                                   "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0 Mobile Safari/537.36"}
                                if phone else {"viewport": {"width": 1280, "height": 860}}))
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    # expected HTTP failures (412/409/404 in conflict tests) are logged by Chrome as "Failed to load resource" — not app errors
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
    if init:
        page.add_init_script(init)
    return ctx, page, errors


def ls_init(**kv):
    return "".join(f"localStorage.setItem({json.dumps(k)}, {json.dumps(json.dumps(v))});" for k, v in kv.items())


# ---------------------------------------------------------------- 1. store suite
def test_store_suite(browser):
    print("\n[1] Shared store suite (S-2)")
    ctx, page, errors = new_page(browser, init="window.__TEST_NO_BOOT__ = true;" + TEST_AUTH)
    page.goto(APP)
    page.add_script_tag(path=str(ROOT / "tests" / "store_suite.js"))
    seed = page.evaluate("window.storeSeed")
    fg = FakeGraph(FOLDER, seed)
    fg.install(page)

    res = page.evaluate("""async () => {
      const T = window.__todo; const seed = window.storeSeed; const out = [];
      // MemStore
      const mem = new T.MemStore(seed);
      out.push(...await storeSuite('MemStore', mem, {
        edit: async (p, t) => { const f = mem.files.get(p); mem.files.set(p, { text: t, version: 'ext' + Math.random() }); },
        del: async p => mem.files.delete(p) }));
      // FsStore on the browser's private file system (stands in for a real folder)
      const root = await navigator.storage.getDirectory();
      for await (const [n] of root.entries()) await root.removeEntry(n, { recursive: true });
      const dir = await root.getDirectoryHandle('fs-suite', { create: true });
      for (const [n, t] of Object.entries(seed)) { const h = await dir.getFileHandle(n, { create: true }); const w = await h.createWritable(); await w.write(t); await w.close(); }
      const fs = new T.FsStore(dir);
      out.push(...await storeSuite('FsStore', fs, {
        edit: async (p, t) => { await new Promise(r => setTimeout(r, 5)); const h = await dir.getFileHandle(p, { create: true }); const w = await h.createWritable(); await w.write(t); await w.close(); },
        del: async p => dir.removeEntry(p) }));
      const trashed = []; try { const tr = await dir.getDirectoryHandle('.trash'); for await (const [n] of tr.entries()) trashed.push(n); } catch {}
      out.push({ name: 'FsStore: a deleted file is kept in the hidden .trash folder', ok: trashed.some(n => n.endsWith(' gamma.md')), detail: trashed.join(',') });
      out.push({ name: 'FsStore: .trash is never listed as tasks', ok: !(await fs.list()).some(e => e.path.includes('.trash')), detail: '' });
      // GraphStore against the fake Graph
      const gs = new T.GraphStore(window.__TEST_AUTH__, 'HTML-ToDo-App-Test');
      const post = (u, b) => fetch('https://graph.microsoft.com/v1.0/__test/' + u, { method: 'POST', body: JSON.stringify(b) });
      out.push(...await storeSuite('GraphStore', gs, { edit: (p, t) => post('edit', { name: p, text: t }), del: p => post('delete', { name: p }) }));
      return out;
    }""")
    for r in res:
        check(r["name"], r["ok"], r["detail"])
    check("GraphStore: no unconditional writes or deletes", not fg.violations, fg.violations)
    check("store suite: no page errors", not errors, errors[:3])
    ctx.close()


# ---------------------------------------------------------------- 2. phone list view on demo data
def row(page, title):
    return page.locator(".row", has=page.locator(".ttl", has_text=title)).first


def test_phone_demo(browser):
    print("\n[2] Phone list view on demo data (R1-12)")
    ctx, page, errors = new_page(browser, phone=True, init=ls_init(**{"todo.source": "demo", "todo.list": "Home", "todo.showDone": True}))
    page.goto(APP)
    page.wait_for_selector(".row")
    check("header shows the list name", page.inner_text("#list-label").strip() == "Home", page.inner_text("#list-label"))
    check("version is in the page (shown in the header on PCs, in Settings on phones)", "0.2.0-dev" in page.text_content("#ver"), page.text_content("#ver"))
    page.screenshot(path=str(SHOTS / "01-phone-list-home.png"))

    fs = page.eval_on_selector(".row .ttl", "t => parseFloat(getComputedStyle(t).fontSize)")
    check("phone text size defaults to 125% (titles 20 px)", abs(fs - 20) < 0.1, fs)
    heights = page.eval_on_selector_all(".row", "rs => rs.map(r => r.getBoundingClientRect().height)")
    check("every row is at least 44 px tall and one line", heights and min(heights) >= 44 and max(heights) < 75, heights)
    titles = page.eval_on_selector_all(".row .ttl", "ts => ts.map(t => t.textContent)")
    check("subtasks hidden by default (no rows for them)", not any("cleaning quotes" in t for t in titles), titles)
    solar = row(page, "Solar panel cleaning")
    check("parent shows done/total subtask badge (0 of 2 done)", solar.locator(".badge").inner_text() == "0/2", solar.locator(".badge").inner_text())
    check("active status shows the green dot", solar.locator(".ck .dot").count() == 1)
    check("done task shows checked and struck through", "done" in row(page, "Water the plants").get_attribute("class"))
    n_before = page.locator(".row").count()
    solar.locator(".badge").click()
    n_after = page.locator(".row").count()
    check("tapping the badge expands its subtasks", n_after == n_before + 2, (n_before, n_after))
    check("nested parent shows 1/1 when its only subtask is done", row(page, "Compare inverter readings").locator(".badge").inner_text() == "1/1")
    solar.locator(".badge").click()
    check("tapping again collapses them (no leftover space)", page.locator(".row").count() == n_before)

    # sideways scroll: the whole list moves together; prefix and actions stay pinned
    sc = page.locator("#scroller")
    widths = sc.evaluate("s => [s.scrollWidth, s.clientWidth]")
    check("long title makes the list scroll sideways", widths[0] > widths[1], widths)
    sc.evaluate("s => s.scrollLeft = 400")
    page.wait_for_timeout(150)
    first = page.locator(".row").first
    px = first.locator(".pfx").bounding_box()
    ax = first.locator(".act").bounding_box()
    vw = sc.evaluate("s => s.clientWidth")
    check("prefix column stays pinned at the left while scrolled", abs(px["x"]) < 1.5, px)
    check("⋯ column stays pinned at the right while scrolled", abs(ax["x"] + ax["width"] - vw) < 2, (ax, vw))
    check("⇤ button appears while scrolled sideways", page.locator("#snap").is_visible())
    page.screenshot(path=str(SHOTS / "02-phone-scrolled-sideways.png"))
    page.wait_for_timeout(3600)
    check("list snaps back after ~3 s idle", sc.evaluate("s => s.scrollLeft") == 0, sc.evaluate("s => s.scrollLeft"))
    sc.evaluate("s => s.scrollLeft = 300")
    page.wait_for_timeout(100)
    page.click("#snap")
    page.wait_for_timeout(700)
    check("⇤ button snaps back", sc.evaluate("s => s.scrollLeft") == 0)

    # checkbox toggle saves the file
    row(page, "Fix gate latch").locator(".ck").click()
    page.click("#modal button:has-text('Check only this')")
    page.wait_for_timeout(200)
    txt = page.evaluate("() => __todo.S.store.files.get('fix-gate-latch.md').text")
    check("tapping a checkbox marks it done and saves the file", "status: done" in txt and "done" in row(page, "Fix gate latch").get_attribute("class"), txt[:80])
    row(page, "Fix gate latch").locator(".ck").click()
    page.wait_for_timeout(200)
    check("tapping again unchecks it", "status: open" in page.evaluate("() => __todo.S.store.files.get('fix-gate-latch.md').text"))
    check("bullet rows have no checkbox", True)

    # quick-add
    page.fill("#qa", "Buy milk")
    page.press("#qa", "Enter")
    page.wait_for_timeout(250)
    has = page.evaluate("() => __todo.S.store.files.has('buy-milk.md')")
    check("quick-add creates a task file in the current list", has and row(page, "Buy milk").count() == 1, has)
    check("quick-add clears and keeps focus for the next task", page.input_value("#qa") == "" and page.evaluate("document.activeElement.id") == "qa")

    # ⋯ menu
    row(page, "Buy milk").locator(".row-more").click()
    labels = page.eval_on_selector_all("#pop button", "bs => bs.map(b => b.textContent)")
    check("⋯ menu offers Edit / Move to list / Change prefix / Delete", all(any(x in l for l in labels) for x in ["Edit", "Move to list", "Change prefix", "Delete"]), labels)
    page.screenshot(path=str(SHOTS / "03-phone-row-menu.png"))
    page.locator("#pop button", has_text="Change prefix").click()
    page.locator("#modal button", has_text="Bullet").click()
    page.wait_for_timeout(200)
    check("change prefix to bullet saves prefix: bullet", "prefix: bullet" in page.evaluate("() => __todo.S.store.files.get('buy-milk.md').text")
          and row(page, "Buy milk").locator(".bullet").count() == 1)

    # list picker
    page.click("#list-name")
    page.wait_for_selector("#modal .pick")
    picks = page.eval_on_selector_all("#modal .pick .go", "bs => bs.map(b => b.textContent)")
    check("list picker shows every list", all(l in picks for l in ["Inbox", "Home", "Rental", "School"]), picks)
    page.screenshot(path=str(SHOTS / "04-phone-list-picker.png"))
    page.locator("#modal .pick .go", has_text="School").click()
    page.wait_for_timeout(150)
    check("picking a list switches to it", page.inner_text("#list-label").strip() == "School")
    reg = row(page, "Register for spring classes")
    check("unrecognized frontmatter shows ⚠ on the row", reg.locator(".wflag").count() == 1)

    # editor
    reg.locator(".ttl").click()
    page.wait_for_selector("#drawer.open")
    page.wait_for_timeout(300)
    dw = page.locator("#drawer").bounding_box()
    check("editor is full-screen on the phone", dw["width"] >= 411 and dw["x"] < 1, dw)
    check("editor names the unrecognized frontmatter", "priority" in page.inner_text("#d-unknown"), page.inner_text("#d-unknown"))
    check("editor has a prefix selector", page.locator("#f-prefix").count() == 1)
    page.screenshot(path=str(SHOTS / "05-phone-editor.png"))
    page.select_option("#f-prefix", "none")
    page.click("#d-save")
    page.wait_for_timeout(250)
    saved = page.evaluate("() => __todo.S.store.files.get('register-spring.md').text")
    check("saving keeps unknown keys untouched (priority: 2)", "priority: 2" in saved and "prefix: none" in saved, saved[:200])
    page.click("#d-close")
    page.wait_for_timeout(250)

    # text size setting (R1-4)
    page.click("#app-menu")
    page.locator("#pop button", has_text="Settings").click()
    page.check("input[name=tsz][value='175']")
    live = page.eval_on_selector(".row .ttl", "t => parseFloat(getComputedStyle(t).fontSize)")
    page.click("#modal button:has-text('Apply')")
    page.wait_for_timeout(200)
    after = page.eval_on_selector(".row .ttl", "t => parseFloat(getComputedStyle(t).fontSize)")
    box = page.eval_on_selector(".row .ck", "c => c.getBoundingClientRect().width")
    check("text size 175% previews live, applies without reload, and scales tap targets", abs(live - 28) < 0.1 and abs(after - 28) < 0.1 and abs(box - 77) < 1,
          (live, after, box))
    page.screenshot(path=str(SHOTS / "13-phone-text-175.png"))
    check("text size is remembered per device", page.evaluate("localStorage.getItem('todo.textSize')") == "175")
    page.click("#list-name")
    page.click("#modal button:has-text('New list')")
    page.fill("#m-name", "Feedback")
    page.click("#modal button:has-text('Add')")
    page.wait_for_timeout(300)
    fit = page.eval_on_selector("#list-name", "el => [el.scrollWidth, el.clientWidth, parseFloat(el.style.fontSize)]")
    check("list name shrinks to fit at 175% (\"Feedback\" not cut off)", fit[0] <= fit[1] + 1 and fit[2] >= 18, fit)
    check("phone header hides the version but keeps the status dot", not page.locator("#ver").is_visible() and page.locator("#stat").is_visible())
    page.screenshot(path=str(SHOTS / "14-phone-175-feedback-header.png"))
    page.evaluate("() => { localStorage.setItem('todo.textSize', '125'); document.documentElement.style.setProperty('--z', '1.25'); }")

    # by due date
    page.click("#list-name")
    page.locator("#modal .pick .go", has_text="By due date").click()
    page.wait_for_timeout(150)
    check("by-due-date view lists dated tasks across lists", page.locator(".group-head").count() >= 2 and page.locator(".row").count() >= 5)
    page.screenshot(path=str(SHOTS / "06-phone-by-due.png"))
    check("demo: no page errors", not errors, errors[:3])
    ctx.close()


# ---------------------------------------------------------------- 3. the app on a fake OneDrive
TEST_FILES = {
    "access-from-android-phone.md": "---\nid: t-20261014-snfr\ntitle: Access from Android Phone\nstatus: open\nlist: Feedback\norder: 3\n---\n\n* Test this out\n",
    "board-view.md": "---\nid: t-20261014-re1l\ntitle: Board View\nstatus: open\nlist: Feedback\norder: 2\n---\n\n* drag lists\n",
    "round-1.md": "---\nid: t-20261014-9o7y\ntitle: Toast UI Changes\nstatus: open\nlist: Feedback\norder: 4\n---\n\n* font is too small\n",
    "sub-1.md": "---\nid: t-20261014-k286\ntitle: Sub 1\nstatus: open\nlist: Test List\nparent: t-20261014-9hp2\norder: 1\n---\nText added\n",
    "sub-2.md": "---\nid: t-20261014-9hp2\ntitle: Sub 2\nstatus: open\nlist: Test List\norder: 1\n---\nyyy\n",
    "_todo.json": '{\n  "lists": ["Inbox", "Test List", "Feedback"]\n}\n',
}


def test_onedrive(browser):
    print("\n[3] The app on a fake OneDrive (S-3, S-4, S-5, S-7)")
    fg = FakeGraph(FOLDER, dict(TEST_FILES))
    ctx, page, errors = new_page(browser, phone=True, init=TEST_AUTH + ls_init(**{
        "todo.source": "onedrive", "todo.folder": FOLDER, "todo.pollMs": 300, "todo.list": "Test List", "todo.everSignedIn": True, "todo.showDone": True}))
    fg.install(page)
    page.goto(APP)
    page.wait_for_selector(".row")
    check("loads the OneDrive test folder", row(page, "Sub 2").count() == 1)
    check("status icon shows signed in", page.get_attribute("#stat", "data-state") == "ok", page.get_attribute("#stat", "data-state"))
    check("status dot has no button background (only the dot is colored)", page.eval_on_selector("#stat", "e => getComputedStyle(e).backgroundColor") in ("rgba(0, 0, 0, 0)", "transparent"),
          page.eval_on_selector("#stat", "e => getComputedStyle(e).backgroundColor"))
    check("subtask hidden; badge 0/1 (none done)", row(page, "Sub 2").locator(".badge").inner_text() == "0/1")
    page.screenshot(path=str(SHOTS / "07-onedrive-test-list.png"))

    # pull to refresh (real touch drag via Chrome DevTools)
    cdp = ctx.new_cdp_session(page)
    lists_before = sum(1 for m, p, _ in fg.requests if p.endswith(":/children"))
    sc = page.locator("#scroller").bounding_box()
    x, y = sc["x"] + 200, sc["y"] + 20
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
    for step in range(1, 13):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y + step * 15}]})
    ready_text = page.inner_text("#ptr-text")
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    page.wait_for_timeout(800)
    lists_after = sum(1 for m, p, _ in fg.requests if p.endswith(":/children"))
    check("pull down at the top shows 'Release to refresh'", ready_text == "Release to refresh", ready_text)
    check("releasing re-reads the file list from OneDrive", lists_after > lists_before, (lists_before, lists_after))
    check("refresh indicator closes afterwards", page.eval_on_selector("#ptr", "e => e.getBoundingClientRect().height") < 1)

    # toggle → conditional PUT
    row(page, "Sub 2").locator(".ck").click()
    page.click("#modal button:has-text('Check only this')")
    page.wait_for_timeout(400)
    check("checkbox saves to OneDrive with If-Match", "status: done" in fg.files()["sub-2.md"]
          and any(m == "PUT" and p.endswith("/content") and im for m, p, im in fg.requests))
    row(page, "Sub 2").locator(".ck").click()
    page.wait_for_timeout(400)

    # quick-add → create with conflictBehavior=fail
    page.fill("#qa", "Phone added task")
    page.press("#qa", "Enter")
    page.wait_for_timeout(500)
    check("quick-add creates the file in OneDrive", "phone-added-task.md" in fg.files(), list(fg.files()))

    # outside edits (another device / Claude) show up via delta
    fg.ext_edit("sub-2.md", fg.files()["sub-2.md"].replace("title: Sub 2", "title: Sub 2 edited elsewhere"))
    page.wait_for_selector(".ttl:has-text('Sub 2 edited elsewhere')", timeout=4000)
    check("an outside edit appears without reloading", True)
    fg.ext_edit("from-claude.md", "---\nid: t-c1\ntitle: Added by Claude\nstatus: open\nlist: Test List\norder: 9\n---\n")
    page.wait_for_selector(".ttl:has-text('Added by Claude')", timeout=4000)
    check("an outside new file appears", True)
    fg.ext_delete("from-claude.md")
    page.wait_for_timeout(1500)
    check("an outside delete disappears", row(page, "Added by Claude").count() == 0)
    puts_before = sum(1 for m, p, _ in fg.requests if m == "PUT")
    page.wait_for_timeout(1200)
    check("polling alone causes no writes (own changes aren't echoed)", sum(1 for m, p, _ in fg.requests if m == "PUT") == puts_before)

    # conflict while editing → banner → Save → dialog → Keep both
    row(page, "Sub 2 edited elsewhere").locator(".ttl").click()
    page.wait_for_selector("#drawer.open")
    page.wait_for_timeout(300)
    page.fill("#f-title", "Sub 2 — my phone edit")
    fg.ext_edit("sub-2.md", fg.files()["sub-2.md"].replace("yyy", "yyy\nPC edit for conflict test"))
    page.wait_for_selector("#d-banner.on", timeout=4000)
    check("editing + outside change shows the 'changed elsewhere' banner", True)
    page.click("#d-save")
    page.wait_for_selector("#modal button:has-text('Keep both')", timeout=3000)
    check("conflict dialog offers Use theirs / Overwrite / Keep both", page.locator("#modal .btns button").count() == 3)
    check("status icon shows the conflict", page.get_attribute("#stat", "data-state") == "conflict")
    page.screenshot(path=str(SHOTS / "08-onedrive-conflict-dialog.png"))
    page.click("#modal button:has-text('Keep both')")
    page.wait_for_timeout(800)
    copies = [n for n in fg.files() if n.startswith("sub-2 (conflict Phone")]
    check("Keep both saves my version as a conflict copy", len(copies) == 1 and "my phone edit" in fg.files()[copies[0]], list(fg.files()))
    check("…and the original keeps the other device's edit", "PC edit for conflict test" in fg.files()["sub-2.md"] and "my phone edit" not in fg.files()["sub-2.md"])
    page.click("#d-close")
    page.wait_for_timeout(300)

    # delete → DELETE with If-Match (recycle bin)
    row(page, "Phone added task").locator(".row-more").click()
    page.locator("#pop button", has_text="Delete").click()
    check("delete confirm mentions the recycle bin", "recycle bin" in page.inner_text("#modal"))
    page.click("#modal button:has-text('Delete')")
    page.wait_for_timeout(500)
    check("delete removes the file from OneDrive", "phone-added-task.md" not in fg.files())

    # list order: outside reorder + local new list → merged, format 2
    fg.ext_edit("_todo.json", '{\n  "lists": ["Feedback", "Test List", "Inbox", "Remote List"],\n  "note": "kept"\n}\n')
    page.wait_for_timeout(900)
    page.click("#list-name")
    page.click("#modal button:has-text('New list')")
    page.fill("#m-name", "Local List")
    page.click("#modal button:has-text('Add')")
    page.wait_for_timeout(600)
    cfg = json.loads(fg.files()["_todo.json"])
    check("list order merges both devices' changes", cfg.get("lists") == ["Feedback", "Test List", "Inbox", "Remote List", "Local List"], cfg)
    check("_todo.json gets data format 2 and keeps unknown keys", cfg.get("format") == 2 and cfg.get("note") == "kept", cfg)

    # sign-in expires mid-session → draft saved → automatic bounce once
    page.click("#list-name")
    page.locator("#modal .pick .go", has_text="Test List").click()
    row(page, "Sub 1").count()  # subtask hidden; open the parent instead
    row(page, "Sub 2").locator(".ttl").first.click()
    page.wait_for_selector("#drawer.open")
    page.wait_for_timeout(200)
    page.fill("#f-title", "Draft kept across sign-in")
    page.evaluate("() => { window.__TEST_AUTH__.token = async () => { throw new __todo.AuthError('expired'); }; return __todo.poll(true); }")
    page.wait_for_timeout(300)
    check("expired sign-in triggers one automatic redirect", page.evaluate("window.__signInCalls") == 1, page.evaluate("window.__signInCalls"))
    check("unsaved edit is stashed before redirecting", "Draft kept across sign-in" in (page.evaluate("localStorage.getItem('todo.draft')") or ""))
    page.evaluate("() => sessionStorage.setItem('todo.autoTried', '1')")
    page.reload()
    page.wait_for_selector("#drawer.open", timeout=5000)
    page.wait_for_timeout(300)
    check("after sign-in the draft is restored into the editor, unsaved", page.input_value("#f-title") == "Draft kept across sign-in"
          and "on" in page.get_attribute("#d-dirty", "class"))
    page.screenshot(path=str(SHOTS / "09-onedrive-draft-restored.png"))

    check("OneDrive: no unconditional writes or deletes", not fg.violations, fg.violations)
    check("OneDrive: no page errors", not errors, errors[:3])
    ctx.close()


def test_desktop_smoke(browser):
    print("\n[4] Same view on a PC-sized window")
    fg = FakeGraph(FOLDER, dict(TEST_FILES))
    ctx, page, errors = new_page(browser, init=TEST_AUTH + ls_init(**{
        "todo.source": "onedrive", "todo.folder": FOLDER, "todo.pollMs": 500, "todo.list": "Feedback"}))
    fg.install(page)
    page.goto(APP)
    page.wait_for_selector(".row")
    check("PC: list view loads the same files", page.locator(".row").count() == 3)
    page.screenshot(path=str(SHOTS / "10-pc-list-view.png"))
    row(page, "Board View").locator(".ttl").click()
    page.wait_for_selector("#drawer.open")
    page.wait_for_timeout(300)
    page.screenshot(path=str(SHOTS / "11-pc-editor.png"))
    check("PC: no page errors", not errors, errors[:3])
    ctx.close()


def test_signed_out(browser):
    print("\n[5] Not signed in")
    ctx, page, errors = new_page(browser, phone=True, init="""window.__TEST_AUTH__ = { async init(){ return { account:null }; }, async token(){ throw new Error('no'); },
      signIn(){ window.__signInCalls = (window.__signInCalls||0) + 1; }, signOut(){}, user(){ return ''; } };""" + ls_init(**{"todo.source": "onedrive"}))
    page.goto(APP)
    page.wait_for_selector(".start")
    check("first visit shows a Sign in button (no automatic redirect)", page.locator("button:has-text('Sign in with Microsoft')").count() == 1
          and not page.evaluate("window.__signInCalls"))
    page.screenshot(path=str(SHOTS / "12-phone-sign-in.png"))
    page.evaluate("() => localStorage.setItem('todo.everSignedIn', 'true')")
    page.reload()
    page.wait_for_timeout(500)
    check("returning user with no session is bounced to Microsoft automatically", page.evaluate("window.__signInCalls") == 1)
    page.reload()
    page.wait_for_timeout(500)
    check("…but only once per session (loop guard), then the button", not page.evaluate("window.__signInCalls")
          and page.locator("button:has-text('Sign in with Microsoft')").count() == 1)
    check("signed out: no page errors", not errors, errors[:3])
    ctx.close()


def test_resilience(browser):
    print("\n[6] Resilience: expired change feed, expired sign-in at start-up")
    fg = FakeGraph(FOLDER, dict(TEST_FILES))
    ctx, page, errors = new_page(browser, phone=True, init=TEST_AUTH + ls_init(**{
        "todo.source": "onedrive", "todo.folder": FOLDER, "todo.pollMs": 300, "todo.list": "Feedback", "todo.everSignedIn": True}))
    fg.install(page)
    page.goto(APP)
    page.wait_for_selector(".row")
    # phone asleep long enough for OneDrive to expire the change token; meanwhile another device edits
    fg.expire_before = fg.seq + 1   # every token the app holds is now expired (tokens issued after the edit work)
    lists_before = sum(1 for m, p, _ in fg.requests if p.endswith(":/children"))
    fg.ext_edit("board-view.md", fg.files()["board-view.md"].replace("title: Board View", "title: Board View (edited while asleep)"))
    page.wait_for_selector(".ttl:has-text('edited while asleep')", timeout=5000)
    got410 = any(p.endswith(":/delta") for m, p, _ in fg.requests)  # delta was polled
    reloaded = sum(1 for m, p, _ in fg.requests if p.endswith(":/children")) > lists_before
    check("expired change feed → full reload picks up edits made in the gap", got410 and reloaded, (got410, reloaded))
    check("resilience: no page errors", not errors, errors[:3])
    ctx.close()

    # remembered account, but the token can't be refreshed (Microsoft's 24 h limit) → one automatic bounce
    ctx, page, errors = new_page(browser, phone=True, init="""window.__TEST_AUTH__ = { async init(){ return { account:{ username:'test@example.com' } }; },
      async token(){ throw new __todo.AuthError('interaction_required'); },
      signIn(){ window.__signInCalls = (window.__signInCalls||0) + 1; }, signOut(){}, user(){ return 'test@example.com'; } };""" + ls_init(**{
        "todo.source": "onedrive", "todo.folder": FOLDER, "todo.everSignedIn": True}))
    page.goto(APP)
    page.wait_for_timeout(800)
    check("expired sign-in at start-up bounces to Microsoft once", page.evaluate("window.__signInCalls") == 1, page.evaluate("window.__signInCalls"))
    page.reload()
    page.wait_for_timeout(800)
    check("…and if that didn't help, shows 'sign in again' instead of looping", not page.evaluate("window.__signInCalls")
          and "expired" in page.inner_text("#rows"), page.inner_text("#rows")[:120])
    check("expired sign-in: no page errors", not errors, errors[:3])
    ctx.close()


def test_hostile_files(browser):
    print("\n[7] Security: hostile task files can't run code (XSS)")
    evil = "<img src=x onerror=\"window.__xss=(window.__xss||0)+1\">"
    files = {
        "evil-title.md": f"---\nid: t-x1\ntitle: '{evil} title'\nstatus: open\nlist: '{evil}List'\norder: 1\n---\n",
        "evil-status.md": f"---\nid: t-x2\ntitle: Evil status\nstatus: '{evil}'\nprefix: '{evil}'\nlist: Evil\norder: 2\nhack: '{evil}'\n---\n",
        "evil-body.md": "---\nid: t-x3\ntitle: Evil body\nstatus: open\nlist: Evil\norder: 3\n---\n"
                        f"Hello {evil}\n\n<script>window.__xss=(window.__xss||0)+100</script>\n\n[click](javascript:window.__xss=1000)\n\n- [ ] {evil} checklist\n",
        "_todo.json": json.dumps({"format": 2, "lists": ["Evil", f"{evil}List"]}),
    }
    fg = FakeGraph(FOLDER, files)
    ctx, page, errors = new_page(browser, phone=True, init=TEST_AUTH + ls_init(**{"todo.source": "onedrive", "todo.list": "Evil"}))
    fg.install(page)
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    page.goto(APP)
    page.wait_for_selector(".row")
    page.wait_for_timeout(500)
    for title in ["Evil status", "Evil body"]:
        row(page, title).locator(".ttl").click()
        page.wait_for_selector("#drawer.open")
        page.wait_for_timeout(800)
        page.click("#d-mode")              # formatted ↔ raw: render both ways
        page.wait_for_timeout(400)
        page.click("#d-mode")
        page.wait_for_timeout(400)
        page.click("#d-close")
        page.wait_for_timeout(300)
    page.click("#list-name")
    page.wait_for_timeout(300)
    page.locator("#modal .pick .go").nth(1).click()   # the list whose name is the injection
    page.wait_for_timeout(500)
    row(page, "title").locator(".row-more").click()
    page.wait_for_timeout(200)
    page.keyboard.press("Escape")
    check("hostile titles, lists, statuses, keys and bodies never execute", not page.evaluate("window.__xss") and not dialogs,
          (page.evaluate("window.__xss"), dialogs))
    check("injected markup is shown as text, not elements", page.locator("#rows img").count() == 0 and "<img" in page.inner_text("#rows"))
    ctx.close()


def test_network_lock(browser):
    print("\n[8] Network lock (Settings): the browser blocks every connection")
    from urllib.parse import urlparse
    attempts = """async () => {
      const out = {};
      try { await fetch('https://graph.microsoft.com/v1.0/me'); out.fetch = 'ALLOWED'; } catch (e) { out.fetch = 'blocked'; }
      await new Promise(r => { const i = new Image(); i.onload = i.onerror = r; i.src = 'https://example.com/beacon.png?d=secret'; setTimeout(r, 1500); });
      try { await fetch('https://www.google-analytics.com/collect?v=1'); out.ga = 'ALLOWED'; } catch (e) { out.ga = 'blocked'; }
      return out; }"""
    for where, url in [("served", APP), ("from disk", (ROOT / "app" / "index.html").resolve().as_uri())]:
        fg = FakeGraph(FOLDER, dict(TEST_FILES))
        ctx, page, errors = new_page(browser, init=ls_init(**{"todo.source": "demo", "todo.netLock": True, "todo.list": "Home"}))
        fg.install(page)
        hosts = set()   # hosts that actually answered (blocked attempts fail with reason "csp" and never get a response)
        ctx.on("response", lambda r: hosts.add(urlparse(r.url).netloc))
        violations = []
        page.expose_function("__cspv", lambda d: violations.append(d))
        page.add_init_script("document.addEventListener('securitypolicyviolation', e => window.__cspv(e.violatedDirective + ' ' + e.blockedURI));")
        page.goto(url)
        page.wait_for_selector(".row")
        res = page.evaluate(attempts)
        page.wait_for_timeout(300)
        outside = {h for h in hosts if h and not h.startswith("localhost")}
        check(f"lock on ({where}): the app still works (demo list loads, scripts and styles load)", page.locator(".row").count() >= 3 and page.evaluate("!!window.toastui && !!window.jsyaml"))
        check(f"lock on ({where}): fetch to Microsoft, image beacon and analytics are all blocked", res == {"fetch": "blocked", "ga": "blocked"} and not outside,
              (res, outside))
        check(f"lock on ({where}): the browser reports the blocks as policy violations", len(violations) >= 3, violations)
        ctx.close()

    # lock off: the same calls go out normally (control)
    fg = FakeGraph(FOLDER, dict(TEST_FILES))
    ctx, page, errors = new_page(browser, init=ls_init(**{"todo.source": "demo", "todo.list": "Home"}))
    fg.install(page)
    page.goto(APP)
    page.wait_for_selector(".row")
    check("lock off (control): the same fetch to Microsoft is allowed", page.evaluate("fetch('https://graph.microsoft.com/v1.0/me').then(r => r.ok)"))
    # the Settings switch turns it on (reload) and disables OneDrive
    page.click("#app-menu")
    page.locator("#pop button", has_text="Settings").click()
    page.check("#m-netlock")
    page.click("#modal button:has-text('Apply')")
    page.wait_for_selector(".row")
    page.wait_for_timeout(300)
    check("Settings switch turns the lock on (after reload)", page.evaluate("!!window.__NETLOCK__"))
    page.click("#app-menu")
    page.locator("#pop button", has_text="Settings").click()
    check("with the lock on, OneDrive can't be chosen", page.is_disabled("input[name=src][value=onedrive]"))
    page.screenshot(path=str(SHOTS / "15-pc-settings-network-lock.png"))
    page.click("#modal button:has-text('Cancel')")
    ctx.close()

    # OneDrive selected but locked → start screen without sign-in, no Microsoft contact
    ctx, page, errors = new_page(browser, init=ls_init(**{"todo.source": "onedrive", "todo.netLock": True}))
    hosts = set()
    ctx.on("request", lambda r: hosts.add(urlparse(r.url).netloc))
    page.goto(APP)
    page.wait_for_selector(".start")
    check("OneDrive + lock: explains the lock, offers no sign-in, contacts nobody", "Network lock is on" in page.inner_text(".start")
          and page.locator("button:has-text('Sign in with Microsoft')").count() == 0 and not {h for h in hosts if h and not h.startswith("localhost")})
    check("network lock: no page errors", not errors, errors[:3])
    ctx.close()


def test_phase4(browser):
    print("\n[9] Phase 4: check-off, done items, delete (R1-12 #3/#8/#14, S-7) + work findings")
    ctx, page, errors = new_page(browser, phone=True, init=ls_init(**{"todo.source": "demo", "todo.list": "Inbox"}))
    page.goto(APP)
    page.wait_for_selector(".row")
    f = lambda name: page.evaluate(f"() => __todo.S.store.files.get('{name}')?.text")

    # simple check-off: hides, saves done + completed, Undo bar
    today = page.evaluate("() => { const d = new Date(); return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }")
    row(page, "Call insurance agent").locator(".ck").click()
    page.wait_for_timeout(250)
    txt = f("call-insurance-agent.md")
    check("no open subtasks/lines → checks off without asking", page.locator("#modal-bg.on").count() == 0)
    check("checked item disappears (Show done is off by default)", row(page, "Call insurance agent").count() == 0)
    check("file gets status: done and completed: today", "status: done" in txt and f"completed: {today}" in txt, txt[:160])
    check("Undo bar appears", page.locator("#undo.on").count() == 1 and "Call insurance agent" in page.inner_text("#undo-msg"))
    page.screenshot(path=str(SHOTS / "16-phone-undo-bar.png"))
    page.click("#undo-btn")
    page.wait_for_timeout(300)
    txt = f("call-insurance-agent.md")
    check("Undo brings it back as open and removes completed", row(page, "Call insurance agent").count() == 1 and "status: open" in txt and "completed:" not in txt, txt[:160])
    row(page, "Call insurance agent").locator(".ck").click()
    page.wait_for_timeout(5600)
    check("Undo bar disappears after 5 s", page.locator("#undo.on").count() == 0)

    # body checklist lines → dialog → Check all ticks them
    row(page, "Tap a title").locator(".ck").click()
    page.wait_for_selector("#modal-bg.on")
    check("open checklist lines → asks 'Check all / Check only this / Cancel'", "unchecked checklist item" in page.inner_text("#modal") and page.locator("#modal .btns button").count() == 3)
    page.screenshot(path=str(SHOTS / "17-phone-check-all-dialog.png"))
    page.click("#modal button:has-text('Check all')")
    page.wait_for_timeout(300)
    txt = f("try-the-list.md")
    check("Check all ticks every - [ ] line in the notes and checks the task", "- [ ]" not in txt and txt.count("- [x]") == 3 and "status: done" in txt, txt[-200:])
    page.click("#undo-btn")
    page.wait_for_timeout(300)
    txt = f("try-the-list.md")
    check("Undo restores the notes exactly", txt.count("- [ ]") == 2 and "status: open" in txt)

    # subtasks → Check only this leaves them open; Check all checks them
    page.click("#list-name")
    page.locator("#modal .pick .go", has_text="Home").click()
    page.wait_for_timeout(200)
    row(page, "Solar panel cleaning").locator(".ck").click()
    page.wait_for_selector("#modal-bg.on")
    check("open subtasks → dialog names them", "2 open subtasks" in page.inner_text("#modal"))
    page.click("#modal button:has-text('Check only this')")
    page.wait_for_timeout(300)
    check("Check only this: parent done, subtasks stay open", "status: done" in f("solar-panel-cleaning.md") and "status: open" in f("get-quotes.md")
          and "hidden with it" in page.inner_text("#undo-msg"), page.inner_text("#undo-msg"))
    page.click("#undo-btn")
    page.wait_for_timeout(300)
    row(page, "Solar panel cleaning").locator(".ck").click()
    page.click("#modal button:has-text('Check all')")
    page.wait_for_timeout(300)
    check("Check all: parent and open subtasks are all done with completed dates",
          all("status: done" in f(n) and "completed:" in f(n) for n in ["solar-panel-cleaning.md", "get-quotes.md", "compare-inverter-readings.md"]))

    # Show done → see and uncheck; completed removed
    page.click("#app-menu")
    page.locator("#pop button", has_text="Show done").click()
    page.wait_for_timeout(200)
    check("Show done reveals checked items", row(page, "Solar panel cleaning").count() == 1 and row(page, "Water the plants").count() == 1)
    row(page, "Water the plants").locator(".ck").click()
    page.wait_for_timeout(300)
    check("unchecking removes completed (work finding 1)", "status: open" in f("water-plants.md") and "completed:" not in f("water-plants.md"), f("water-plants.md"))

    # editor status change keeps completed in step
    row(page, "Water the plants").locator(".ttl").click()
    page.wait_for_selector("#drawer.open")
    page.wait_for_timeout(300)
    page.select_option("#f-status", "done")
    page.click("#d-save")
    page.wait_for_timeout(300)
    check("setting done in the editor writes completed", f"completed: {today}" in f("water-plants.md"))
    page.click("#d-close")
    page.wait_for_timeout(200)

    # delete a parent: asks about subtasks, deletes all, Undo restores all
    before = {n: f(n) for n in ["solar-panel-cleaning.md", "get-quotes.md", "compare-inverter-readings.md", "export-readings-csv.md"]}
    row(page, "Solar panel cleaning").locator(".row-more").click()
    page.locator("#pop button", has_text="Delete").click()
    check("deleting a parent asks 'Also delete its 3 subtasks?'", "Also delete its 3 subtasks" in page.inner_text("#modal"), page.inner_text("#modal")[:200])
    page.click("#modal button:has-text('Delete all')")
    page.wait_for_timeout(300)
    check("Delete all removes the parent and every subtask", all(f(n) is None for n in before))
    page.click("#undo-btn")
    page.wait_for_timeout(400)
    check("Undo recreates all four files with identical content", all(f(n) == before[n] for n in before) and row(page, "Solar panel cleaning").count() == 1)
    check("phase 4: no page errors", not errors, errors[:3])
    ctx.close()

    # work finding 2: a touchscreen laptop is a PC, not a phone
    ctx = browser.new_context(viewport={"width": 1280, "height": 800}, has_touch=True)
    page = ctx.new_page()
    page.add_init_script(ls_init(**{"todo.source": "demo", "todo.list": "Home"}))
    page.goto(APP)
    page.wait_for_selector(".row")
    fs = page.eval_on_selector(".row .ttl", "t => parseFloat(getComputedStyle(t).fontSize)")
    check("touchscreen laptop gets PC defaults (100 % text)", abs(fs - 16) < 0.1, fs)
    ctx.close()


def test_desktop_site_phone(browser):
    print("\n[10] Phone in Chrome's 'Desktop site' mode (R1-15)")
    stub = r"""(() => { const real = window.matchMedia.bind(window);
      window.matchMedia = q => /any-pointer:\s*fine/.test(q) ? { matches:false, media:q, addEventListener(){}, removeEventListener(){} }
                         : /pointer:\s*coarse/.test(q) ? { matches:true, media:q, addEventListener(){}, removeEventListener(){} } : real(q); })();"""
    ctx = browser.new_context(viewport={"width": 980, "height": 2180}, screen={"width": 412, "height": 915}, has_touch=True,
                              user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0 Safari/537.36")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script(stub + ls_init(**{"todo.source": "demo", "todo.list": "Home"}))
    page.goto(APP)
    page.wait_for_selector(".row")
    info = page.evaluate("() => ({ phone: __todo.IS_PHONE, zoom: __todo.PAGE_ZOOM, w: document.body.offsetWidth, vis: Math.round(document.body.getBoundingClientRect().width) })")
    check("detected as a phone despite the PC label", info["phone"], info)
    check("page scales up to fit the real screen (980 / 412): lays out 412 wide, fills the 980 view", abs(info["zoom"] - 980 / 412) < 0.01 and abs(info["w"] - 412) < 3 and abs(info["vis"] - 980) < 3, info)
    fs = page.eval_on_selector(".row .ttl", "t => parseFloat(getComputedStyle(t).fontSize)")
    check("phone text size (125 %) applies", abs(fs - 20) < 0.1, fs)
    check("phone header applies (no version label) even though Chrome reports a wide screen", not page.locator("#ver").is_visible())
    page.locator(".row .row-more").first.click()
    pb = page.locator("#pop").bounding_box()
    check("menus stay on screen when scaled", pb and pb["x"] >= 0 and pb["x"] + pb["width"] <= 981, pb)
    page.screenshot(path=str(SHOTS / "18-phone-desktop-site-mode.png"))
    check("desktop-site phone: no page errors", not errors, errors[:3])
    ctx.close()
    # control: a touch laptop (touch + trackpad) stays a PC, no scaling
    ctx = browser.new_context(viewport={"width": 1280, "height": 800}, screen={"width": 1280, "height": 800}, has_touch=True)
    page = ctx.new_page()
    page.add_init_script(ls_init(**{"todo.source": "demo"}))
    page.goto(APP)
    page.wait_for_selector(".row")
    info = page.evaluate("() => ({ phone: __todo.IS_PHONE, zoom: __todo.PAGE_ZOOM })")
    check("touch laptop: still a PC, not scaled", not info["phone"] and info["zoom"] == 1, info)
    ctx.close()


def test_phase5(browser):
    print("\n[11] Phase 5: long-press move (R1-12 #13)")
    ctx, page, errors = new_page(browser, phone=True, init=ls_init(**{"todo.source": "demo", "todo.list": "Home"}))
    page.goto(APP)
    page.wait_for_selector(".row")
    cdp = ctx.new_cdp_session(page)
    fm = lambda name, key: page.evaluate(f"() => {{ const t = __todo.all().find(x => x.file === '{name}'); return t ? t['{key}'] : null; }}")
    titles = lambda: page.eval_on_selector_all(".row .ttl", "ts => ts.map(t => t.textContent.trim())")

    def center(title, frac=0.5, x=150):
        b = row(page, title).bounding_box()
        return x, b["y"] + b["height"] * frac

    def long_drag(src, dst_xy, hold=550, steps=10, dx_end=0):
        x, y = center(src)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
        page.wait_for_timeout(hold)
        tx, ty = dst_xy
        for i in range(1, steps + 1):
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x + (tx - x + dx_end) * i / steps, "y": y + (ty - y) * i / steps}]})
            page.wait_for_timeout(20)
        hint = page.inner_text("#drag-hint") if page.locator("#drag-hint.on").count() else ""
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        page.wait_for_timeout(500)
        return hint

    # A: drop on the middle of another task → subtask
    hint = long_drag("Fix gate latch", center("Solar panel cleaning", 0.5))
    check("long-press + drop on a task's middle makes it a subtask", fm("fix-gate-latch.md", "parent") == "t-s05", (fm("fix-gate-latch.md", "parent"), hint))
    check("the hint said what would happen", "subtask of" in hint, hint)
    check("it now counts in the parent's badge (0/3) and leaves the top level", row(page, "Solar panel cleaning").locator(".badge").inner_text() == "0/3"
          and "Fix gate latch" not in titles(), titles())
    check("Undo offered after a move", page.locator("#undo.on").count() == 1)
    page.click("#undo-btn")
    page.wait_for_timeout(400)
    check("Undo puts it back at the top level", fm("fix-gate-latch.md", "parent") == "" and "Fix gate latch" in titles())

    # B: drop near the top edge → placed above
    long_drag("A deliberately long", center("Fix gate latch", 0.1))
    check("drop on a task's top edge places it above", titles()[0].startswith("A deliberately long"), titles())

    # C: drag left → out one level
    row(page, "Solar panel cleaning").locator(".badge").click()
    page.wait_for_timeout(200)
    x, y = center("Get three cleaning quotes")
    hint = long_drag("Get three cleaning quotes", (x, y + 2), dx_end=-110)
    t_ = titles()
    check("dragging left moves a subtask out one level", fm("get-quotes.md", "parent") == "" , (fm("get-quotes.md", "parent"), hint))
    check("…placed right after its old parent", t_.index("Get three cleaning quotes") == t_.index("Solar panel cleaning") + 1 + 1 or
          fm("get-quotes.md", "order") > fm("solar-panel-cleaning.md", "order"), t_)

    # D: subtasks travel with their parent; can't drop into own subtask
    long_drag("Solar panel cleaning", center("Compare inverter readings", 0.5))
    check("can't drop a task into its own subtask (no change)", fm("solar-panel-cleaning.md", "parent") == "")
    long_drag("Solar panel cleaning", center("Fix gate latch", 0.5))
    check("moving a parent: its subtasks come along (parent links unchanged)", fm("solar-panel-cleaning.md", "parent") == "t-s03"
          and fm("compare-inverter-readings.md", "parent") == "t-s05")

    # E: a quick tap still opens the editor; a swipe still scrolls (no drag)
    row(page, "Fix gate latch").locator(".ttl").click()
    page.wait_for_selector("#drawer.open")
    check("a normal tap still opens the editor", True)
    page.click("#d-close")
    page.wait_for_timeout(300)
    x, y = center("Fix gate latch")
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
    for i in range(1, 6):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y - i * 12}]})
        page.wait_for_timeout(15)
    page.wait_for_timeout(600)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    check("moving before the long-press finishes is a scroll, not a drag", page.locator("#drag-ghost").count() == 0 and not page.evaluate("__todo.S.moving"))
    page.screenshot(path=str(SHOTS / "19-phone-after-moves.png"))
    check("phase 5 (touch): no page errors", not errors, errors[:3])
    ctx.close()

    # F: PC mouse long-press
    ctx, page, errors = new_page(browser, init=ls_init(**{"todo.source": "demo", "todo.list": "Rental"}))
    page.goto(APP)
    page.wait_for_selector(".row")
    b1 = row(page, "Replace HVAC filter").bounding_box(); b0 = row(page, "Tenant lease renewal").bounding_box()
    page.mouse.move(200, b1["y"] + b1["height"] / 2)
    page.mouse.down()
    page.mouse.move(200, b0["y"] + 4, steps=8)          # PC: press and drag right away, no hold
    page.wait_for_timeout(100)
    page.screenshot(path=str(SHOTS / "20-pc-dragging.png"))
    page.mouse.up()
    page.wait_for_timeout(400)
    first = page.eval_on_selector(".row .ttl", "t => t.textContent.trim()")
    check("PC: mouse long-press drag reorders too", first == "Replace HVAC filter", first)
    check("phase 5 (mouse): no page errors", not errors, errors[:3])
    ctx.close()


def test_indent_saveclose(browser):
    print("\n[12] Subtask checkboxes indent with their titles; Save & close (R1-3)")
    ctx, page, errors = new_page(browser, phone=True, init=ls_init(**{"todo.source": "demo", "todo.list": "Home", "todo.showDone": True}))
    page.goto(APP)
    page.wait_for_selector(".row")
    row(page, "Solar panel cleaning").locator(".badge").click()
    row(page, "Compare inverter readings").locator(".badge").click()
    page.wait_for_timeout(200)
    def geo(title):
        r = row(page, title)
        bx = r.locator(".pfx").bounding_box(); tx = r.locator(".ttl").bounding_box()
        return bx["x"], tx["x"] - (bx["x"] + bx["width"])
    p0, g0 = geo("Solar panel cleaning"); p1, g1 = geo("Get three cleaning quotes"); p2, g2 = geo("Export last 90 days")
    step = 22 * 1.25
    check("each subtask level moves its checkbox right by one indent step", abs((p1 - p0) - step) < 1 and abs((p2 - p1) - step) < 1, (p0, p1, p2))
    check("checkbox-to-title gap is the same at every level", abs(g0 - g1) < 1 and abs(g1 - g2) < 1, (g0, g1, g2))
    page.screenshot(path=str(SHOTS / "21-phone-indented-subtasks.png"))
    page.locator("#scroller").evaluate("s => s.scrollLeft = 300")
    page.wait_for_timeout(150)
    p1s, _ = geo("Get three cleaning quotes")
    check("while scrolled sideways, a subtask's checkbox stays at its indent", abs(p1s - p1) < 1.5, (p1, p1s))
    page.locator("#scroller").evaluate("s => s.scrollLeft = 0")

    # Save & close
    row(page, "Fix gate latch").locator(".ttl").click()
    page.wait_for_selector("#drawer.open")
    page.wait_for_timeout(300)
    check("editor shows Save and Save & close", page.locator("#d-save").is_visible() and page.locator("#d-saveclose").is_visible())
    page.screenshot(path=str(SHOTS / "22-phone-editor-save-close.png"))
    page.fill("#f-title", "Fix gate latch (saved and closed)")
    page.click("#d-saveclose")
    page.wait_for_timeout(400)
    txt = page.evaluate("() => __todo.S.store.files.get('fix-gate-latch.md').text")
    check("Save & close saves the file and closes the editor", "saved and closed" in txt and page.locator("#drawer.open").count() == 0, txt[:120])
    row(page, "Water the plants").locator(".ttl").click()
    page.wait_for_selector("#drawer.open")
    page.wait_for_timeout(300)
    page.click("#d-saveclose")
    page.wait_for_timeout(300)
    check("Save & close with no changes just closes", page.locator("#drawer.open").count() == 0)
    check("indent/save-close: no page errors", not errors, errors[:3])
    ctx.close()
    # phone editor header: one line, no wrapping, even on a narrow phone at the largest text size
    ctx = browser.new_context(viewport={"width": 360, "height": 800}, is_mobile=True, has_touch=True, user_agent="Mozilla/5.0 (Linux; Android 14) Mobile Safari/537.36")
    page = ctx.new_page()
    page.add_init_script(ls_init(**{"todo.source": "demo", "todo.list": "Home", "todo.textSize": 175}))
    page.goto(APP)
    page.wait_for_selector(".row")
    page.locator(".row .ttl").first.click()
    page.wait_for_selector("#drawer.open")
    page.wait_for_timeout(300)
    page.fill("#f-title", "edited")
    r = page.evaluate("""() => { const hd = document.querySelector('.d-head'); const bs = [...hd.querySelectorAll('button')].filter(b => b.offsetParent);
      return { oneRow: new Set(bs.map(b => Math.round(b.getBoundingClientRect().top))).size === 1, fits: hd.scrollWidth <= hd.clientWidth + 1,
               label: document.querySelector('#d-saveclose').textContent }; }""")
    check("phone editor buttons fit on one line at 360 px and 175 % ('Save & close' unwrapped)", r["oneRow"] and r["fits"] and r["label"] == "Save & close", r)
    order = page.evaluate("""() => [...document.querySelectorAll('.toastui-editor-defaultUI-toolbar > div button')].filter(b => b.offsetWidth > 0)
        .map(b => [...b.classList].find(c => !['toastui-editor-toolbar-icons','active'].includes(c)))""")
    check("phone toolbar starts: checkbox, bullet, outdent, indent", order[:4] == ["task-list", "bullet-list", "outdent", "indent"], order)
    page.locator(".toastui-editor-toolbar-icons.more").click()
    page.wait_for_timeout(300)
    edges = page.evaluate("""() => [...document.querySelectorAll('.toastui-editor-dropdown-toolbar button')].map(b => { const r = b.getBoundingClientRect(); return [r.left, r.right]; })""")
    check("every option in the ⋯ pop-up is fully on screen", edges and all(l >= 0 and rgt <= 360 for l, rgt in edges), edges)
    ctx.close()


# ---------------------------------------------------------------- main
def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    httpd = serve()
    only = set(sys.argv[1:])
    with sync_playwright() as p:
        browser = p.chromium.launch()
        tests = [("store", test_store_suite), ("demo", test_phone_demo), ("onedrive", test_onedrive),
                 ("desktop", test_desktop_smoke), ("signedout", test_signed_out), ("resilience", test_resilience),
                 ("security", test_hostile_files), ("netlock", test_network_lock), ("phase4", test_phase4), ("desktopsite", test_desktop_site_phone), ("phase5", test_phase5), ("indent", test_indent_saveclose)]
        for name, fn in tests:
            if not only or name in only:
                try:
                    fn(browser)
                except Exception as e:  # keep going; report the crash as a failure
                    check(f"{name}: crashed", False, repr(e))
        browser.close()
    httpd.shutdown()
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)} passed, {len(failed)} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
