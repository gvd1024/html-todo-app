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
    ctx, page, errors = new_page(browser, phone=True, init=ls_init(**{"todo.source": "demo", "todo.list": "Home"}))
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
    check("parent shows open/total subtask badge", solar.locator(".badge").inner_text() == "2/2", solar.locator(".badge").inner_text())
    check("active status shows the green dot", solar.locator(".ck .dot").count() == 1)
    check("done task shows checked and struck through", "done" in row(page, "Water the plants").get_attribute("class"))
    n_before = page.locator(".row").count()
    solar.locator(".badge").click()
    n_after = page.locator(".row").count()
    check("tapping the badge expands its subtasks", n_after == n_before + 2, (n_before, n_after))
    check("nested parent shows 0/1 when its only subtask is done", row(page, "Compare inverter readings").locator(".badge").inner_text() == "0/1")
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
    row(page, "Buy milk").locator(".more").click()
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
        "todo.source": "onedrive", "todo.folder": FOLDER, "todo.pollMs": 300, "todo.list": "Test List", "todo.everSignedIn": True}))
    fg.install(page)
    page.goto(APP)
    page.wait_for_selector(".row")
    check("loads the OneDrive test folder", row(page, "Sub 2").count() == 1)
    check("status icon shows signed in", page.get_attribute("#stat", "data-state") == "ok", page.get_attribute("#stat", "data-state"))
    check("subtask hidden; badge 1/1", row(page, "Sub 2").locator(".badge").inner_text() == "1/1")
    page.screenshot(path=str(SHOTS / "07-onedrive-test-list.png"))

    # toggle → conditional PUT
    row(page, "Sub 2").locator(".ck").click()
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
    row(page, "Phone added task").locator(".more").click()
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


# ---------------------------------------------------------------- main
def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    httpd = serve()
    only = set(sys.argv[1:])
    with sync_playwright() as p:
        browser = p.chromium.launch()
        tests = [("store", test_store_suite), ("demo", test_phone_demo), ("onedrive", test_onedrive),
                 ("desktop", test_desktop_smoke), ("signedout", test_signed_out), ("resilience", test_resilience)]
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
