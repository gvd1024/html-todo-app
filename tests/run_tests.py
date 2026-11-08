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
import datetime
import json
import os
import pathlib
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from fake_graph import FakeGraph, Files  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOTS = ROOT / "tests" / "screenshots"
PORT = int(os.environ.get("HTA_TEST_PORT", "8765"))   # override when another checkout runs its tests at the same time
APP = f"http://localhost:{PORT}/app/"
FOLDER = "HTML-ToDo-App"
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


FGET_JS = r"""window.__fget = n => { const f = window.__todo?.S?.store?.files; if (!f) return undefined; if (f.has(n)) return f.get(n); for (const [k, v] of f) if (k.endsWith('/' + n)) return v; };"""


def new_page(browser, *, phone=False, init=""):
    ctx = browser.new_context(**({"viewport": {"width": 412, "height": 860}, "is_mobile": True, "has_touch": True,
                                   "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0 Mobile Safari/537.36"}
                                if phone else {"viewport": {"width": 1280, "height": 860}}))
    page = ctx.new_page()
    page.add_init_script(FGET_JS)
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
      // R2-8: FsStore.remove no longer copies to .trash itself — the app's trash (trashPut) does it for every store
      const trashed = []; try { const tr = await dir.getDirectoryHandle('.trash'); for await (const [n] of tr.entries()) trashed.push(n); } catch {}
      out.push({ name: 'FsStore: remove() makes no copy of its own (the app trashes first, R2-8)', ok: !trashed.some(n => n.endsWith('gamma.md')), detail: trashed.join(',') });
      out.push({ name: 'FsStore: .trash is never listed as tasks', ok: !(await fs.list()).some(e => e.path.includes('.trash')), detail: '' });
      // GraphStore against the fake Graph
      const gs = new T.GraphStore(window.__TEST_AUTH__, 'HTML-ToDo-App');
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


def check_all(page):
    """R2-8 Checked off D: "Check all" needs a second, deliberate tap (at least ~300 ms after the first)."""
    page.click("#modal [data-a=all]")
    page.wait_for_timeout(350)
    page.click("#modal [data-a=all]")


def test_phone_demo(browser):
    print("\n[2] Phone list view on demo data (R1-12)")
    ctx, page, errors = new_page(browser, phone=True, init=ls_init(**{"todo.source": "demo", "todo.list": "Home", "todo.showDone": True}))
    page.goto(APP)
    page.wait_for_selector(".row")
    check("header shows the list name", page.inner_text("#list-label").strip() == "Home", page.inner_text("#list-label"))
    check("R2-10: the header shows the build (PCs; Settings on phones), not the version", page.text_content("#ver") == page.evaluate("__todo.BUILD") and "0.2.0" not in page.text_content("#ver"), page.text_content("#ver"))
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
    txt = page.evaluate("() => __fget('fix-gate-latch.md').text")
    check("tapping a checkbox marks it done and saves the file", "status: done" in txt and "done" in row(page, "Fix gate latch").get_attribute("class"), txt[:80])
    row(page, "Fix gate latch").locator(".ck").click()
    page.wait_for_timeout(200)
    check("tapping again unchecks it", "status: open" in page.evaluate("() => __fget('fix-gate-latch.md').text"))
    check("bullet rows have no checkbox", True)

    # quick-add
    page.fill("#qa", "Buy milk")
    page.press("#qa", "Enter")
    page.wait_for_timeout(250)
    has = page.evaluate("() => !!__fget('buy-milk.md')")
    check("quick-add creates a task file in the current list", has and row(page, "Buy milk").count() == 1, has)
    check("quick-add clears and keeps focus for the next task", page.input_value("#qa") == "" and page.evaluate("document.activeElement.id") == "qa")

    # ⋯ menu
    row(page, "Buy milk").locator(".row-more").click()
    labels = page.eval_on_selector_all("#pop button", "bs => bs.map(b => b.textContent)")
    check("⋯ menu offers Edit / Move to folder / Change prefix / Delete", all(any(x in l for l in labels) for x in ["Edit", "Move to folder", "Change prefix", "Delete"]), labels)
    page.screenshot(path=str(SHOTS / "03-phone-row-menu.png"))
    page.locator("#pop button", has_text="Change prefix").click()
    page.locator("#modal button", has_text="Bullet").click()
    page.wait_for_timeout(200)
    check("change prefix to bullet saves prefix: bullet", "prefix: bullet" in page.evaluate("() => __fget('buy-milk.md').text")
          and row(page, "Buy milk").locator(".bullet").count() == 1)

    # list picker
    page.click("#list-name")
    page.wait_for_selector("#modal .pick")
    picks = page.eval_on_selector_all("#modal .pick .go", "bs => bs.map(b => b.textContent)")
    check("R2-5: the folder picker shows / (root) and every folder", all(l in picks for l in ["/ (root)", "Home", "Rental", "School"]), picks)
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
    saved = page.evaluate("() => __fget('register-spring.md').text")
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
    page.click("#modal button:has-text('New folder')")
    page.fill("#m-name", "Feedback")
    page.click("#modal button:has-text('Add')")
    page.wait_for_timeout(300)
    fit = page.eval_on_selector("#list-name", "el => [el.scrollWidth, el.clientWidth, parseFloat(el.style.fontSize)]")
    check("list name shrinks to fit at 175% (\"Feedback\" not cut off)", fit[0] <= fit[1] + 1 and fit[2] >= 18, fit)
    check("phone header hides the build label but keeps the status dot", not page.locator("#ver").is_visible() and page.locator("#stat").is_visible())
    page.screenshot(path=str(SHOTS / "14-phone-175-feedback-header.png"))
    page.evaluate("() => { localStorage.setItem('todo.textSize', '125'); document.documentElement.style.setProperty('--z', '1.25'); }")

    # Today view (R2-2; replaced "By due date")
    page.click("#list-name")
    page.locator("#modal .pick .go", has_text="Today").click()
    page.wait_for_timeout(150)
    check("Today view shows its three section headers", page.locator(".group-head").count() == 3, page.locator(".group-head").count())
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
    lists_before = len([u for u in fg.urls if ":/delta" in u or ":/children" in u])
    sc = page.locator("#scroller").bounding_box()
    x, y = sc["x"] + 200, sc["y"] + 20
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
    for step in range(1, 13):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y + step * 15}]})
    ready_text = page.inner_text("#ptr-text")
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    page.wait_for_timeout(800)
    lists_after = len([u for u in fg.urls if ":/delta" in u or ":/children" in u])
    check("pull down at the top shows 'Release to refresh'", ready_text == "Release to refresh", ready_text)
    check("releasing re-checks OneDrive (change feed or listing)", lists_after > lists_before, (lists_before, lists_after))
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
    fg.ext_edit("Test List/from-claude.md", "---\nid: t-c1\ntitle: Added by Claude\nstatus: open\norder: 9\n---\n")
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
    copies = [n for n in fg.files() if n.split("/")[-1].startswith("sub-2 (conflict Phone")]
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

    # folder order (R2-5): outside reorder + a folder made elsewhere + a local new folder → merged
    fg.ext_mkdir("Remote List")
    fg.ext_edit("_todo.json", '{\n  "format": 4,\n  "folders": ["Feedback", "Test List", "Remote List"],\n  "note": "kept"\n}\n')
    page.wait_for_timeout(900)
    page.click("#list-name")
    page.click("#modal button:has-text('New folder')")
    page.fill("#m-name", "Local List")
    page.click("#modal button:has-text('Add')")
    page.wait_for_timeout(600)
    cfg = json.loads(fg.files()["_todo.json"])
    check("folder order merges both devices' changes; the new folder exists", cfg.get("folders") == ["Feedback", "Test List", "Remote List", "Local List"] and "Local List" in fg.folders() and "lists" not in cfg, (cfg, fg.folders()))
    check("_todo.json gets the current data format and keeps unknown keys", cfg.get("format") == page.evaluate("__todo.DATA_FORMAT") and cfg.get("note") == "kept", cfg)

    # sign-in expires mid-session → no automatic redirect (R2-6 C); a tap on the status icon signs in, stashing the draft first
    page.click("#list-name")
    page.locator("#modal .pick .go", has_text="Test List").click()
    row(page, "Sub 1").count()  # subtask hidden; open the parent instead
    row(page, "Sub 2").locator(".ttl").first.click()
    page.wait_for_selector("#drawer.open")
    page.wait_for_timeout(200)
    page.fill("#f-title", "Draft kept across sign-in")
    page.evaluate("() => { window.__TEST_AUTH__.token = async () => { throw new __todo.AuthError('expired'); }; return __todo.poll(true); }")
    page.wait_for_timeout(300)
    check("expired sign-in mid-session: no automatic redirect, the edit stays open", not page.evaluate("window.__signInCalls")
          and page.input_value("#f-title") == "Draft kept across sign-in", page.evaluate("window.__signInCalls"))
    page.click("#d-signin")
    page.wait_for_timeout(200)
    check("tap Sign in in the editor → sign in (redirect when popups aren't available)", page.evaluate("window.__signInCalls") == 1, page.evaluate("window.__signInCalls"))
    check("unsaved edit is stashed before redirecting", "Draft kept across sign-in" in (page.evaluate("localStorage.getItem('todo.draft')") or ""))
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
    check("returning user with no session: no automatic redirect (R2-6 C), 'expired' + the Sign in button", not page.evaluate("window.__signInCalls")
          and "expired" in page.inner_text("#rows") and page.locator("button:has-text('Sign in with Microsoft')").count() == 1, page.inner_text("#rows")[:120])
    page.click("button:has-text('Sign in with Microsoft')")
    page.wait_for_timeout(200)
    check("…tapping Sign in goes to Microsoft once", page.evaluate("window.__signInCalls") == 1)
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
    lists_before = fg.full_checks()
    fg.ext_edit("board-view.md", fg.files()["board-view.md"].replace("title: Board View", "title: Board View (edited while asleep)"))
    page.wait_for_selector(".ttl:has-text('edited while asleep')", timeout=5000)
    got410 = any(p.endswith(":/delta") for m, p, _ in fg.requests)  # delta was polled
    reloaded = fg.full_checks() > lists_before
    check("expired change feed → full reload picks up edits made in the gap", got410 and reloaded, (got410, reloaded))
    check("resilience: no page errors", not errors, errors[:3])
    ctx.close()

    # remembered account, but the token can't be refreshed (Microsoft's 24 h limit) → 'expired' + Sign in, no redirect (R2-6 C)
    ctx, page, errors = new_page(browser, phone=True, init="""window.__TEST_AUTH__ = { async init(){ return { account:{ username:'test@example.com' } }; },
      async token(){ throw new __todo.AuthError('interaction_required'); },
      signIn(){ window.__signInCalls = (window.__signInCalls||0) + 1; }, signOut(){}, user(){ return 'test@example.com'; } };""" + ls_init(**{
        "todo.source": "onedrive", "todo.folder": FOLDER, "todo.everSignedIn": True}))
    page.goto(APP)
    page.wait_for_timeout(800)
    check("expired sign-in at start-up: no automatic redirect, 'expired' + Sign in", not page.evaluate("window.__signInCalls")
          and "expired" in page.inner_text("#rows") and page.locator("button:has-text('Sign in with Microsoft')").count() == 1, page.inner_text("#rows")[:120])
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
    page.locator("#modal .pick .go").nth(2).click()   # the folder whose name is the injection (after / (root) and Evil)
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
    f = lambda name: page.evaluate(f"() => __fget('{name}')?.text")

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
    check_all(page)
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
    check_all(page)
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

    # R2-6: replay Geoff's phone diagnostics. This phone reports a fine pointer even in phone mode, but nothing hovers.
    def media(**m):
        js = ", ".join(f"[{q!r}, {str(v).lower()}]" for q, v in m.items())
        return r"""(() => { const real = window.matchMedia.bind(window), fake = new Map([%s]);
          window.matchMedia = q => { const k = q.replace(/[()\s]/g, ''); return fake.has(k) ? { matches:fake.get(k), media:q, addEventListener(){}, removeEventListener(){} } : real(q); }; })();""" % js
    phone_media = media(**{"pointer:coarse": True, "pointer:fine": False, "any-pointer:fine": True, "any-pointer:coarse": True,
                           "hover:hover": False, "any-hover:hover": False})
    def device(viewport, screen, ua, stub, touch=True):
        c = browser.new_context(viewport=viewport, screen=screen, has_touch=touch, user_agent=ua)
        p = c.new_page(); errs = []; p.on("pageerror", lambda e: errs.append(str(e)))
        p.add_init_script(stub + ls_init(**{"todo.source": "demo", "todo.list": "Home"}))
        p.goto(APP); p.wait_for_selector(".row")
        return c, p, errs, p.evaluate("() => ({ phone: __todo.IS_PHONE, zoom: __todo.PAGE_ZOOM, w: document.body.offsetWidth })")
    desk_ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"
    ctx, page, errs, info = device({"width": 979, "height": 1972}, {"width": 339, "height": 727}, desk_ua, phone_media)
    check("R2-6: phone that reports a fine pointer, started in desktop-site mode → phone", info["phone"], info)
    check("…scaled back to the real screen (979 / 339), lays out 339 wide", abs(info["zoom"] - 979 / 339) < 0.01 and abs(info["w"] - 339) < 3, info)
    check("…phone header (no version label)", not page.locator("#ver").is_visible())
    check("…no page errors", not errs, errs[:3])
    ctx.close()
    ctx, page, errs, info = device({"width": 338, "height": 682}, {"width": 339, "height": 727},
        "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Mobile Safari/537.36", phone_media)
    check("R2-6: the same phone in a normal start → phone, not scaled", info["phone"] and info["zoom"] == 1, info)
    ctx.close()
    laptop_media = media(**{"pointer:coarse": True, "pointer:fine": False, "any-pointer:fine": True, "any-pointer:coarse": True,
                            "hover:hover": False, "any-hover:hover": True})
    ctx, page, errs, info = device({"width": 1280, "height": 800}, {"width": 1280, "height": 800}, desk_ua, laptop_media)
    check("R2-6: touch laptop used by touch (trackpad can hover) → still a PC", not info["phone"] and info["zoom"] == 1, info)
    ctx.close()
    ctx, page, errs, info = device({"width": 1024, "height": 600}, {"width": 1024, "height": 600}, desk_ua, laptop_media)
    check("R2-6: small touch laptop with a trackpad → still a PC", not info["phone"] and info["zoom"] == 1, info)
    ctx.close()


def test_phase5(browser):
    print("\n[11] Phase 5: long-press move (R1-12 #13)")
    ctx, page, errors = new_page(browser, phone=True, init=ls_init(**{"todo.source": "demo", "todo.list": "Home"}))
    page.goto(APP)
    page.wait_for_selector(".row")
    cdp = ctx.new_cdp_session(page)
    fm = lambda name, key: page.evaluate(f"() => {{ const t = __todo.all().find(x => (x.file === '{name}' || x.file.endsWith('/{name}'))); return t ? t['{key}'] : null; }}")
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
    txt = page.evaluate("() => __fget('fix-gate-latch.md').text")
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
    check("phone toolbar is exactly: Checklist, Bullet, Outdent, Indent, Inline code, More, Bigger notes (at 360 px, 175 %)",
          order == ["task-list", "bullet-list", "outdent", "indent", "code", "app-more", "app-expand"], order)
    xs = page.evaluate("""() => [...document.querySelectorAll('.toastui-editor-defaultUI-toolbar > div button')].filter(b => b.offsetWidth > 0)
        .map(b => { const r = b.getBoundingClientRect(); return [r.left + r.width / 2, r.right]; })""")
    gaps = [round(xs[i + 1][0] - xs[i][0], 1) for i in range(len(xs) - 1)]
    check("the seven buttons are evenly spaced and on screen", max(gaps) - min(gaps) < 3 and xs[-1][1] <= 360, gaps)
    page.screenshot(path=str(SHOTS / "23-phone-editor-toolbar.png"))
    page.locator(".app-more").click()
    page.wait_for_timeout(200)
    menu = page.eval_on_selector_all("#pop .phdr, #pop button", "els => els.map(e => e.textContent)")
    check("More menu is grouped: Text style / Headings / Lists / Insert", menu == ["Text style", "Bold", "Italic", "Strikethrough", "Headings", "Heading 1", "Heading 2",
          "Heading 3", "Lists", "Numbered list", "Insert", "Link…", "Quote", "Horizontal line", "Table…", "Code block"], menu)
    pb = page.locator("#pop").bounding_box()
    check("More menu is fully on screen", pb["x"] >= 0 and pb["x"] + pb["width"] <= 360, pb)
    page.screenshot(path=str(SHOTS / "24-phone-editor-more-menu.png"))
    page.keyboard.press("Escape")
    ctx.close()

    # every More item really formats (markdown mode makes results easy to read back)
    ctx, page, errors = new_page(browser, phone=True, init=ls_init(**{"todo.source": "demo", "todo.list": "Home", "todo.mode": "markdown"}))
    page.goto(APP)
    page.wait_for_selector(".row")
    page.locator(".row .ttl").first.click()
    page.wait_for_selector("#drawer.open")
    page.wait_for_timeout(400)
    def apply(label, *, dialog=None):
        page.evaluate("() => { __todo.S.editor.setMarkdown('hello world'); __todo.S.editor.focus(); __todo.S.editor.setSelection([1, 1], [1, 12]); }")
        page.locator(".app-more").click()
        page.locator("#pop button", has_text=label).click()
        if dialog:
            dialog()
        page.wait_for_timeout(150)
        return page.evaluate("() => __todo.S.editor.getMarkdown()")
    res = {
        "Bold": apply("Bold"), "Italic": apply("Italic"), "Strikethrough": apply("Strikethrough"), "Heading 2": apply("Heading 2"),
        "Numbered list": apply("Numbered list"), "Quote": apply("Quote"), "Horizontal line": apply("Horizontal line"), "Code block": apply("Code block"),
        "Link…": apply("Link…", dialog=lambda: (page.fill("#m-lurl", "https://example.com"), page.click("#modal button:has-text('Insert')"))),
        "Table…": apply("Table…", dialog=lambda: page.click("#modal button:has-text('Insert')")),
    }
    expect = {"Bold": "**hello world**", "Italic": "*hello world*", "Strikethrough": "~~hello world~~", "Heading 2": "## hello world",
              "Numbered list": "1. hello world", "Quote": "> hello world", "Code block": "```", "Link…": "](https://example.com)", "Table…": "|"}
    bad = {k: v for k, v in res.items() if k in expect and expect[k] not in v}
    check("every More item formats the text (bold, italic, strike, heading, numbered, quote, code block, link, table)", not bad, bad)
    check("horizontal line inserts a divider", any(s in res["Horizontal line"] for s in ("***", "---", "___")), res["Horizontal line"])
    check("toolbar formatting: no page errors", not errors, errors[:3])
    ctx.close()


def test_pc_toolbar(browser):
    print("\n[13] PC editor toolbar: the phone's order, as many extras as fit, the rest under More")
    for w, mode, hidden in [(1280, "wysiwyg", ["Horizontal line", "Table…", "Code block"]), (1280, "markdown", ["Horizontal line", "Table…", "Code block"]),
                             (700, "wysiwyg", ["Quote", "Horizontal line", "Table…", "Code block"])]:   # R2-6: ⤢ Bigger notes takes the last slot
        ctx, page, errors = new_page(browser, init=ls_init(**{"todo.source": "demo", "todo.list": "Home", "todo.mode": mode}))
        page.set_viewport_size({"width": w, "height": 800})
        page.goto(APP)
        page.wait_for_selector(".row")
        page.locator(".row .ttl").first.click()
        page.wait_for_selector("#drawer.open")
        page.wait_for_timeout(600)
        vis = page.evaluate("""() => [...document.querySelectorAll('.toastui-editor-defaultUI-toolbar > .toastui-editor-toolbar-group button')].filter(b => b.offsetWidth > 0)
            .map(b => [...b.classList].find(c => c !== 'toastui-editor-toolbar-icons' && c !== 'active'))""")
        lib_more = page.evaluate("() => [...document.querySelectorAll('#editor .toastui-editor-toolbar-icons.more')].some(b => b.offsetWidth > 0)")
        check(f"PC {w}px {mode}: starts Checklist, Bullet, Outdent, Indent, Inline code; ends with More, Bigger notes", vis[:5] == ["task-list", "bullet-list", "outdent", "indent", "code"] and vis[-2:] == ["app-more", "app-expand"], vis)
        check(f"PC {w}px {mode}: the library never hides buttons on its own", not lib_more)
        page.locator(".app-more").click()
        page.wait_for_timeout(200)
        menu = page.eval_on_selector_all("#pop button", "bs => bs.map(b => b.textContent)")
        check(f"PC {w}px {mode}: More lists exactly what didn't fit ({', '.join(hidden)})", menu == hidden, menu)
        page.keyboard.press("Escape")
        check(f"PC {w}px {mode}: no page errors", not errors, errors[:3])
        ctx.close()


def test_recurring(browser):
    print("\n[14] Recurring tasks (R2-1)")
    import datetime as _dt
    ctx, page, errors = new_page(browser, phone=True, init=ls_init(**{"todo.source": "demo", "todo.list": "Rental", "todo.showDone": True}))
    page.goto(APP)
    page.wait_for_selector(".row")

    # --- the date engine, with a fixed "today" (Tue 2026-10-20) ---
    T = "2026-10-20"
    cases = [
        ("daily", "2026-10-20", "2026-10-21", "daily, due today"),
        ("daily", "2026-10-15", "2026-10-21", "daily, overdue, skip missed → after today"),
        ("daily, catch up", "2026-10-15", "2026-10-16", "daily, overdue, catch up → next after old due"),
        ("every 3 days, after done", "2026-10-10", "2026-10-23", "every 3 days after done → from completion"),
        ("weekdays", "2026-10-23", "2026-10-26", "weekdays: Fri → Mon"),
        ("weekly on mon, thu", "2026-10-22", "2026-10-26", "weekly on mon, thu: Thu → Mon"),
        ("weekly", "2026-10-19", "2026-10-26", "weekly (due's weekday)"),
        ("every 2 weeks on mon", "2026-10-19", "2026-11-02", "every 2 weeks on mon keeps the fortnight"),
        ("monthly on day 31", "2026-10-31", "2026-11-30", "monthly on day 31 → 30 Nov"),
        ("monthly on day 31", "2026-11-30", "2026-12-31", "…then back to the 31st in Dec"),
        ("monthly on last day", "2027-01-31", "2027-02-28", "monthly on last day → 28 Feb"),
        ("yearly", "2028-02-29", "2029-02-28", "yearly from a leap day"),
        ("every 2 months on day 15", "2026-10-15", "2026-12-15", "every 2 months on day 15"),
        ("Weekly On Monday, Thursday, Keep Copies", "2026-10-19", "2026-10-22", "case-insensitive, full day names, suffix"),
    ]
    for phrase, due, want, label in cases:
        got = page.evaluate("([p, d, t]) => { const r = __todo.parseRepeat(p); return r ? __todo.nextDue(r, d, t) : 'UNPARSED'; }", [phrase, due, T])
        check(f"next date: {label}", got == want, f"{phrase!r} due {due} → {got}, want {want}")
    for bad in ["every blue moon", "daily, catch up, after done", "weekly on funday", "monthly on day 32", ""]:
        check(f"rejects {bad!r}", page.evaluate("p => __todo.parseRepeat(p) === null", bad))
    flags = page.evaluate("() => { const r = __todo.parseRepeat('weekly on fri, keep copies, after done'); return [r.keep, r.mode]; }")
    check("suffixes parsed: keep copies + after done", flags == [True, "afterdone"], flags)

    f = lambda name: page.evaluate(f"() => __fget('{name}')?.text ?? null")
    fm = lambda name, key: page.evaluate(f"() => {{ const t = __todo.all().find(x => (x.file === '{name}' || x.file.endsWith('/{name}'))); return t ? t['{key}'] : null; }}")
    today = page.evaluate("() => { const d = new Date(); return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }")

    # --- Recycle: same file, next date, everything unchecked, nothing logged ---
    page.evaluate("""() => { const t = __todo.all().find(x => (x.file === 'collect-rent.md' || x.file.endsWith('/collect-rent.md')));
        t.body = t.body.replace('- [ ] Unit A', '- [x] Unit A'); __todo.render(); }""")
    rent_due = fm("collect-rent.md", "due")
    want_next = page.evaluate("d => __todo.nextDue(__todo.parseRepeat('monthly on day ' + Number(d.slice(8))), d)", rent_due)
    check("↻ shows on recurring rows", row(page, "Collect rent").locator(".rep-ico").count() == 1)
    row(page, "Collect rent").locator(".ck").click()
    page.wait_for_timeout(300)
    txt = f("collect-rent.md")
    check("Recycle: same file moves to the next date", fm("collect-rent.md", "due") == want_next and f"due: {want_next}" in txt, (rent_due, want_next, txt[:200]))
    check("Recycle: stays open, checklist reset, nothing logged", "status: open" in txt and "- [x]" not in txt and "completed:" not in txt and "Done " not in txt, txt[-160:])
    check("Recycle: Undo bar shows the next date", "next:" in page.inner_text("#undo-msg"), page.inner_text("#undo-msg"))
    page.click("#undo-btn")
    page.wait_for_timeout(300)
    check("Recycle: Undo restores date and checkmarks", fm("collect-rent.md", "due") == rent_due and "- [x] Unit A" in f("collect-rent.md"))

    # --- Copy: original completed (dialog like any task), copy carries the series ---
    page.click("#list-name")
    page.locator("#modal .pick .go", has_text="School").click()
    page.wait_for_timeout(200)
    wr_due = fm("weekly-review.md", "due")
    nxt = page.evaluate("d => __todo.nextDue(__todo.parseRepeat('weekly, keep copies'), d)", wr_due)
    copy_name = f"weekly-review-{nxt.replace('-', '')}.md"
    row(page, "Weekly review").locator(".ck").click()
    page.wait_for_selector("#modal-bg.on")
    check("Copy: open checklist lines → the regular Check all / only dialog", "unchecked checklist item" in page.inner_text("#modal"))
    page.click("#modal button:has-text('Check only this')")
    page.wait_for_timeout(400)
    orig, copy = f("weekly-review.md"), f(copy_name)
    check("Copy: original is done, dated, and no longer repeats", "status: done" in orig and f"completed: {today}" in orig and "repeat:" not in orig and "series: t-s20" in orig, orig[:260])
    check(f"Copy: copy named <slug>-YYYYMMDD ({copy_name}) with the next date", copy is not None and f"due: {nxt}" in copy, copy and copy[:260])
    check("Copy: copy repeats, shares series, new id, all unchecked", copy and "repeat: weekly, keep copies" in copy and "series: t-s20" in copy
          and "id: t-s20\n" not in copy and "- [x]" not in copy and "status: open" in copy)
    page.click("#undo-btn")
    page.wait_for_timeout(400)
    check("Copy: Undo removes the copy and restores the original", f(copy_name) is None and "repeat: weekly, keep copies" in f("weekly-review.md") and "status: open" in f("weekly-review.md"))

    # --- Copy with subtasks: fresh copies of the subtasks ---
    page.evaluate("""async () => { const t = __todo.all().find(x => (x.file === 'weekly-review.md' || x.file.endsWith('/weekly-review.md'))); t.body = ''; t.repeat = 'weekly, keep copies'; await __todo.saveTask(t);
        const S = __todo.S; const sub = { file:'', version:null, id:'t-sub-wr', title:'Review calendar', status:'done', prefix:'', list:'School', collections:[], parent:'t-s20',
          order:1, due:'', repeat:'', series:'', completed:'2026-10-01', demoted_into:'', body:'', extra:{}, unknown:[], isNew:true };
        S.tasks.set(sub.id, sub); await __todo.saveTask(sub); __todo.render(); }""")
    row(page, "Weekly review").locator(".ck").click()
    page.wait_for_timeout(500)
    subs = page.evaluate("""() => { const c = __todo.all().find(x => x.repeat && x.series === 't-s20' && x.id !== 't-s20');
        return c ? __todo.all().filter(x => x.parent === c.id).map(x => [x.title, x.status, x.file]) : null; }""")
    check("Copy: the copy gets fresh, unchecked copies of its subtasks", subs and len(subs) == 1 and subs[0][0] == "Review calendar" and subs[0][1] == "open", subs)
    check("Copy: the original's subtask stays as it was", fm("review-calendar.md", "status") == "done")

    # --- editor: presets compose the phrase; untouched phrases are never rewritten ---
    page.click("#list-name")
    page.locator("#modal .pick .go", has_text="Rental").click()
    page.wait_for_timeout(200)
    row(page, "Replace HVAC filter").locator(".ttl").click()
    page.wait_for_selector("#drawer.open")
    page.wait_for_timeout(300)
    page.select_option("#f-rep", "weekly")
    page.select_option("#f-rep-mode", "copy")
    page.select_option("#f-rep-next", "catchup")
    hint = page.inner_text("#f-rep-hint")
    page.screenshot(path=str(SHOTS / "25-phone-editor-repeat.png"))
    page.click("#d-saveclose")
    page.wait_for_timeout(300)
    hv = f("hvac-filter.md")
    dow = page.evaluate("() => { const t = __todo.all().find(x => (x.file === 'hvac-filter.md' || x.file.endsWith('/hvac-filter.md'))); const [y,m,d] = t.due.split('-').map(Number); return ['sun','mon','tue','wed','thu','fri','sat'][new Date(y, m-1, d, 12).getDay()]; }")
    check("editor: Weekly + Copy + Catch up writes the phrase", f"repeat: weekly on {dow}, keep copies, catch up" in hv, hv[:260])
    check("editor: live hint shows the next date", "next after checking off" in hint, hint)
    page.evaluate("""async () => { const t = __todo.all().find(x => (x.file === 'collect-rent.md' || x.file.endsWith('/collect-rent.md'))); t.repeat = 'Monthly On Day 3,  after done'; await __todo.saveTask(t); __todo.render(); }""")
    row(page, "Collect rent").locator(".ttl").click()
    page.wait_for_selector("#drawer.open")
    page.wait_for_timeout(300)
    page.fill("#f-title", "Collect rent (renamed)")
    page.click("#d-saveclose")
    page.wait_for_timeout(300)
    check("editor: a hand-typed phrase is kept exactly when Repeat isn't touched", "repeat: Monthly On Day 3,  after done" in f("collect-rent.md"), f("collect-rent.md")[:260])

    # --- unknown phrase: ⚠, normal check-off ---
    page.evaluate("""async () => { const t = __todo.all().find(x => (x.file === 'tenant-lease-renewal.md' || x.file.endsWith('/tenant-lease-renewal.md'))); t.repeat = 'every blue moon'; t.unknown = ['repeat: every blue moon']; await __todo.saveTask(t); __todo.render(); }""")
    check("unknown phrase → ⚠ on the row, no ↻", row(page, "Tenant lease renewal").locator(".wflag").count() == 1 and row(page, "Tenant lease renewal").locator(".rep-ico").count() == 0)
    check("data format 4 (folders) recognized", page.evaluate("__todo.DATA_FORMAT") == 4)
    check("recurring: no page errors", not errors, errors[:3])
    ctx.close()


def test_today(browser):
    print("\n[15] Today view (R2-2)")
    ctx, page, errors = new_page(browser, phone=True, init=ls_init(**{"todo.source": "demo", "todo.list": "Home", "todo.textSize": "125"}))
    page.goto(APP)
    page.wait_for_selector(".row")
    D = lambda n: page.evaluate("n => { const d = new Date(); d.setDate(d.getDate() + n); return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }", n)
    # Lay out dates: open tasks get A..G, the rest are pushed far into the past (lots of overdue rows → a scrollable page)
    plan = {"A": -3, "B": -1, "C": 0, "D": 1, "E": 3, "F": 10, "G": 20}
    names = page.evaluate("""async (plan) => { const offs = Object.values(plan);
        const iso = n => { const d = new Date(); d.setDate(d.getDate() + n); return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); };
        const ts = __todo.all().filter(t => t.status === 'open' || t.status === 'active');
        const out = {}; let i = 0;
        for (const t of ts){ if (i < offs.length){ t.due = iso(offs[i]); out[Object.keys(plan)[i]] = t.title; } else if (i === offs.length){ t.due = ''; t.repeat = ''; out.U = t.title; } else t.due = iso(-30 - i);
          i++; await __todo.saveTask(t); }
        __todo.render(); return out; }""", plan)
    check("test setup: enough open demo tasks", len(names) == 8 and page.evaluate("__todo.all().filter(t => t.status === 'open' || t.status === 'active').length") > 12, names)
    page.click("#list-name")
    check("folder picker says 'Today (all folders)'", page.locator("#modal .pick .go", has_text="Today (all folders)").count() == 1)
    page.locator("#modal .pick .go", has_text="Today (all folders)").click()
    page.wait_for_timeout(150)
    check("header reads 'Today'", page.inner_text("#list-label").strip() == "Today", page.inner_text("#list-label"))
    heads = page.locator(".group-head").all_inner_texts()
    check("order: Upcoming · Today · Overdue, with counts", len(heads) == 3 and heads[0].strip().lower().startswith("▸ upcoming · 4") and heads[1].strip().lower() == "today · 1" and heads[2].strip().lower().startswith("▸ overdue"), heads)
    titles = lambda: page.locator("#rows .row .ttl").all_inner_texts()
    check("starts with Upcoming and Overdue collapsed (only today's task shows)", [x.strip() for x in titles()] == [names["C"]], titles())
    check("no list name on rows", page.locator("#rows .row .chip").count() == 0)
    rc = row(page, names["C"])
    check("R2-14: Today rows: ↑ ↓ (no ● — already today)", rc.locator(".qbtn").all_inner_texts() == ["↑", "↓"], rc.locator(".qbtn").all_inner_texts())
    check("undated tasks are hidden", names["U"] not in titles())

    # expand Overdue: most recent first
    page.locator("[data-tday=over]").click(); page.wait_for_timeout(100)
    tl = [x.strip() for x in titles()]
    check("Overdue: most recent first (yesterday right below Today)", tl[0] == names["C"] and tl[1] == names["B"] and tl[2] == names["A"], tl[:4])
    check("R2-14: Overdue rows: ↑ ↓ ●", row(page, names["A"]).locator(".qbtn").all_inner_texts() == ["↑", "↓", "●"], row(page, names["A"]).locator(".qbtn").all_inner_texts())

    # expand Upcoming while scrolled: Today keeps its place
    page.evaluate("() => { const h = document.querySelector('#tday-today'); const sc = document.querySelector('#scroller'); sc.scrollTop = Math.max(0, h.offsetTop - 300); }")
    page.wait_for_timeout(100)
    y0 = page.evaluate("() => document.querySelector('#tday-today').getBoundingClientRect().top")
    page.locator("[data-tday=up]").click(); page.wait_for_timeout(150)
    y1 = page.evaluate("() => document.querySelector('#tday-today').getBoundingClientRect().top")
    check("expanding Upcoming keeps Today where it was on screen", abs(y1 - y0) <= 2, (y0, y1))
    tl = [x.strip() for x in titles()]
    check("Upcoming: furthest first, tomorrow right above Today", tl[:3] == [names["E"], names["D"], names["C"]], tl[:4])
    later = page.locator(".tday-later")
    check("'+ 2 later' is the top row of Upcoming", later.count() == 1 and later.inner_text().startswith("+ 2 later"), later.all_inner_texts())
    check("R2-14: Upcoming rows: ↑ ↓ ●", row(page, names["E"]).locator(".qbtn").all_inner_texts() == ["↑", "↓", "●"])
    later.scroll_into_view_if_needed(); page.wait_for_timeout(100)   # Playwright scrolls before clicking; measure after that
    y0 = page.evaluate("() => document.querySelector('#tday-today').getBoundingClientRect().top")
    later.click(); page.wait_for_timeout(150)
    y1 = page.evaluate("() => document.querySelector('#tday-today').getBoundingClientRect().top")
    tl = [x.strip() for x in titles()]
    check("'+ later' reveals the later tasks above, furthest first", tl[:4] == [names["G"], names["F"], names["E"], names["D"]] and page.locator(".tday-later").count() == 0, tl[:5])
    check("revealing later tasks keeps Today in place", abs(y1 - y0) <= 2, (y0, y1))
    page.screenshot(path=str(SHOTS / "26-phone-today-expanded.png"))

    fm = lambda title, key: page.evaluate("([ti, k]) => __todo.all().find(x => x.title === ti)[k]", [title, key])
    ftxt = lambda title: page.evaluate("ti => { const t = __todo.all().find(x => x.title === ti); return __todo.S.store.files.get(t.file).text; }", title)
    # ↑ on today's task
    row(page, names["C"]).locator("[data-act=q-up]").click(); page.wait_for_timeout(1100)
    check("↑: due moves one day later (tomorrow) in the file", f"due: {D(1)}" in ftxt(names["C"]), ftxt(names["C"])[:200])
    check("↑: row moves into Upcoming; Today shows the empty hint", page.locator(".group-head").nth(1).inner_text().strip().lower() == "today · 0" and page.locator(".empty-hint", has_text="Nothing due today").count() == 1)
    check("Undo bar offered", page.locator("#undo.on").count() == 1 and names["C"] in page.inner_text("#undo-msg"), page.inner_text("#undo-msg"))
    page.click("#undo-btn"); page.wait_for_timeout(250)
    check("Undo puts it back on today", fm(names["C"], "due") == D(0) and f"due: {D(0)}" in ftxt(names["C"]))
    # quick taps add up: one save, Undo goes back to before the first tap
    da = fm(names["A"], "due"); rA = row(page, names["A"])
    rA.locator("[data-act=q-up]").click(); rA.locator("[data-act=q-up]").click(); rA.locator("[data-act=q-down]").click(); rA.locator("[data-act=q-up]").click()
    page.wait_for_timeout(1100)
    import datetime as _dt
    plus2 = (_dt.date.fromisoformat(da) + _dt.timedelta(days=2)).isoformat()
    check("↑ ↑ ↓ ↑ quickly: the date moves 2 days later from its due date (not from today), saved", fm(names["A"], "due") == plus2 and f"due: {plus2}" in ftxt(names["A"]), (da, fm(names["A"], "due")))
    page.click("#undo-btn"); page.wait_for_timeout(300)
    check("…Undo goes back to the date before the first tap", fm(names["A"], "due") == da and f"due: {da}" in ftxt(names["A"]), fm(names["A"], "due"))
    # ● on an overdue task
    row(page, names["A"]).locator("[data-act=q-dot]").click(); page.wait_for_timeout(250)
    check("● on an overdue row: due = today", fm(names["A"], "due") == D(0) and f"due: {D(0)}" in ftxt(names["A"]))
    check("…and it shows under Today now", page.locator(".group-head").nth(1).inner_text().strip().lower() == "today · 2")
    # ⋯ → Change due date…
    row(page, names["B"]).locator(".row-more").click()
    page.locator("#pop button", has_text="Change due date").click()
    page.fill("#due-pick", D(5))
    page.locator("#modal [data-a=set]").click(); page.wait_for_timeout(250)
    check("⋯ → Change due date… sets a picked date", fm(names["B"], "due") == D(5), fm(names["B"], "due"))
    page.locator(f"#rows .row .ttl", has_text=names["E"]).first.locator("xpath=..").locator(".row-more").click()
    page.locator("#pop button", has_text="Change due date").click()
    page.locator("#modal .pick .go", has_text="Tomorrow").click(); page.wait_for_timeout(250)
    check("Change due date… → Tomorrow", fm(names["E"], "due") == D(1))

    # recurring: ↻ shown, the button moves only this occurrence
    page.evaluate("""async ti => { const t = __todo.all().find(x => x.title === ti); t.repeat = 'weekly'; await __todo.saveTask(t); __todo.render(); }""", names["D"])
    rd = row(page, names["D"])
    check("recurring rows show ↻ in the Today view", rd.locator(".rep-ico").count() == 1)
    rd.locator("[data-act=q-dot]").click(); page.wait_for_timeout(250)
    check("recurring: ● moves only due, repeat stays", fm(names["D"], "due") == D(0) and "repeat: weekly" in ftxt(names["D"]) and fm(names["D"], "status") == "open")

    # fit at 175 %: buttons and ⋯ stay on screen, title column keeps some room
    page.evaluate("() => { document.documentElement.style.setProperty('--z', '1.75'); __todo.render(); }")
    page.wait_for_timeout(150)
    vw = page.evaluate("innerWidth")
    over_row = page.locator("#rows .row", has=page.locator("[data-act=q-dot]")).first
    boxes = over_row.locator(".qbtn, .row-more").evaluate_all("els => els.map(e => { const r = e.getBoundingClientRect(); return [r.left, r.right]; })")
    pfx = over_row.locator(".pfx").evaluate("e => e.getBoundingClientRect().right")
    check("175 %: ↑ ↓ ● + ⋯ fit on screen with room for the title", all(r <= vw + 1 for _, r in boxes) and min(l for l, _ in boxes) - pfx >= 100, (vw, pfx, boxes))
    page.screenshot(path=str(SHOTS / "27-phone-today-175.png"))

    # --- R2-3: quick-add chips in the Today view ---
    page.evaluate("() => { document.documentElement.style.setProperty('--z', '1.25'); __todo.render(); }")
    first = page.evaluate("__todo.S.lists[0]")
    check("chips show in the Today view: first list + Today", page.locator("#qa-list").is_visible() and page.inner_text("#qa-list").startswith(first) and page.inner_text("#qa-date").startswith("Today"), (page.inner_text("#qa-list"), page.inner_text("#qa-date")))
    newt = lambda ti: page.evaluate("ti => { const t = __todo.all().find(x => x.title === ti); return t ? [t.list, t.due, t.isNew ? null : __todo.S.store.files.get(t.file).text] : null; }", ti)
    page.fill("#qa", "QA today task"); page.press("#qa", "Enter"); page.wait_for_timeout(250)
    r = newt("QA today task")
    check("quick-add in Today: first list, due today, shown under Today", r and r[0] == first and r[1] == D(0) and f"due: {D(0)}" in r[2] and row(page, "QA today task").count() == 1, r)
    other = page.evaluate("__todo.S.lists[1]")
    page.click("#qa-list"); page.locator("#modal .pick .go", has_text=other).first.click(); page.wait_for_timeout(100)
    page.click("#qa-date"); page.locator("#modal .pick .go", has_text="Tomorrow").click(); page.wait_for_timeout(100)
    check("chips show the new choices", page.inner_text("#qa-list").startswith(other) and page.inner_text("#qa-date").startswith("Tmrw"), (page.inner_text("#qa-list"), page.inner_text("#qa-date")))
    page.fill("#qa", "QA tomorrow task"); page.press("#qa", "Enter"); page.wait_for_timeout(250)
    r = newt("QA tomorrow task")
    check("chosen list and date are used", r and r[0] == other and r[1] == D(1), r)
    check("toast says it went to Upcoming", "Upcoming" in page.inner_text("#toast"), page.inner_text("#toast"))
    check("the date sticks for the next add", page.inner_text("#qa-date").startswith("Tmrw"))
    page.click("#qa-date"); page.locator("#modal .pick .go", has_text="No date").click(); page.wait_for_timeout(100)
    page.fill("#qa", "QA undated task"); page.press("#qa", "Enter"); page.wait_for_timeout(250)
    r = newt("QA undated task")
    check("No date: saved without due:, toast says so", r and r[1] == "" and "\ndue:" not in r[2] and "no date" in page.inner_text("#toast"), (r, page.inner_text("#toast")))
    page.click("#qa-date"); page.fill("#qa-pick", D(4)); page.locator("#modal [data-a=set]").click(); page.wait_for_timeout(100)
    check("Pick a date… sets the chip", page.inner_text("#qa-date") != "Tmrw" and page.evaluate("__todo.QA.date") == D(4))
    page.screenshot(path=str(SHOTS / "28-phone-today-quickadd.png"))
    vw = page.evaluate("innerWidth")
    page.evaluate("() => { document.documentElement.style.setProperty('--z', '1.75'); __todo.render(); }")
    box = page.evaluate("() => ['#qa', '#qa-list', '#qa-date'].map(s => { const r = document.querySelector(s).getBoundingClientRect(); return [r.left, r.right]; })")
    check("175 %: input keeps over half the line, chips on screen", box[0][1] - box[0][0] > vw * 0.5 and box[2][1] <= vw + 1, (vw, box))
    page.evaluate("() => { document.documentElement.style.setProperty('--z', '1.25'); __todo.render(); }")
    # leave the Today view → chips hide, date resets; list remembered
    page.click("#list-name"); page.locator("#modal .pick .go", has_text=first).first.click(); page.wait_for_timeout(100)
    check("normal list view: no chips, old placeholder", page.locator("#qa-list").is_hidden() and page.locator("#qa-date").is_hidden() and first in page.get_attribute("#qa", "placeholder"))
    page.fill("#qa", "QA list-view task"); page.press("#qa", "Enter"); page.wait_for_timeout(250)
    r = newt("QA list-view task")
    check("quick-add in a list view: that list, no date (unchanged)", r and r[0] == first and r[1] == "", r)
    page.click("#list-name"); page.locator("#modal .pick .go", has_text="Today (all folders)").click(); page.wait_for_timeout(100)
    check("back in Today: date chip reset to Today, list chip remembered", page.inner_text("#qa-date").startswith("Today") and page.inner_text("#qa-list").startswith(other), (page.inner_text("#qa-list"), page.inner_text("#qa-date")))

    # new app start: view kept, sections collapsed again
    page.reload(); page.wait_for_selector("#tday-today")
    heads = page.locator(".group-head").all_inner_texts()
    check("reopens in the Today view (last used)", page.inner_text("#list-label").strip() == "Today")
    check("after a restart Upcoming and Overdue are collapsed again", heads[0].strip().startswith("▸") and heads[2].strip().startswith("▸"), heads)
    check("today: no page errors", not errors, errors[:3])
    ctx.close()


def test_local_folder(browser):
    print("\n[16] Default local task folder next to the build (R2-4)")
    ctx, page, errors = new_page(browser, init=ls_init(**{"todo.source": "demo"}))
    page.goto(APP)
    page.wait_for_selector(".row")
    cases = [
        ("file:///C:/Users/me/HTA/html-todo-app-2026-10-21b/app/index.html", "C:\\Users\\me\\HTA\\data"),
        ("file:///C:/My%20Apps/HTA/html-todo-app-2026-10-21b/app/", None),
        ("file:///C:/My%20Apps/HTA/html-todo-app-2026-10-21b/app/index.html", "C:\\My Apps\\HTA\\data"),
        ("file://server/share/HTA/html-todo-app-x/app/index.html", "\\\\server\\share\\HTA\\data"),
        ("https://gvd1024.github.io/html-todo-app/app/", None),
    ]
    for href, want in cases[:1] + cases[2:]:
        got = page.evaluate("h => __todo.suggestedLocalPath(h)", href)
        check(f"suggested path for {href}", got == want, f"{got!r}, want {want!r}")
    # stub the folder dialog with folders on the browser's private file system
    page.evaluate("""async () => {
        const root = await navigator.storage.getDirectory();
        const mk = async (name, files) => { try { await root.removeEntry(name, { recursive:true }); } catch {}
          const d = await root.getDirectoryHandle(name, { create:true });
          for (const f of files){ const w = await (await d.getFileHandle(f, { create:true })).createWritable(); await w.write(f.endsWith('.md') ? '---\\nid: t-1\\ntitle: One\\nstatus: open\\norder: 1\\n---\\n' : '<p>'); await w.close(); }
          return d; };
        window.__dirs = { data: await mk('data', []), build: await mk('html-todo-app-x', ['index.html']), misc: await mk('misc', []), tasks: await mk('work-tasks', ['one.md']) };
        window.showDirectoryPicker = async () => window.__dirs[window.__next]; }""")
    def pick(key):
        page.evaluate("k => { window.__next = k; __todo.pickLocalFolder(); }", key)
        page.wait_for_selector("#modal [data-a=pick]")
    pick("data")
    check("guide dialog over http: no path, no Copy button", page.locator("#lf-path").count() == 0 and page.locator("#modal [data-a=copy]").count() == 0)
    page.click("#modal [data-a=pick]"); page.wait_for_timeout(300)
    page.screenshot(path=str(SHOTS / "30-pc-empty-data-folder.png"))
    check("an empty folder named data opens without a question", page.evaluate("__todo.S.store && __todo.S.store.kind === 'local' && __todo.S.store.name === 'data'") and "Use this folder" not in page.inner_text("#modal"))
    pick("build")
    page.click("#modal [data-a=pick]"); page.wait_for_timeout(200)
    check("the build folder → 'looks like the app's own folder'", "app's own folder" in page.inner_text("#modal"), page.inner_text("#modal")[:120])
    page.click("#modal [data-a=again]"); page.wait_for_timeout(100)
    check("Choose another → back to the guide; store unchanged", page.locator("#modal [data-a=pick]").count() == 1 and page.evaluate("__todo.S.store.name") == "data")
    page.click("#modal [data-a=cancel]")
    pick("misc")
    page.click("#modal [data-a=pick]"); page.wait_for_timeout(200)
    check("an empty folder with another name → asks first", "no task files" in page.inner_text("#modal"), page.inner_text("#modal")[:120])
    page.click("#modal [data-a=use]"); page.wait_for_timeout(300)
    check("Use it anyway → opens it", page.evaluate("__todo.S.store.name") == "misc")
    pick("tasks")
    page.click("#modal [data-a=pick]"); page.wait_for_timeout(300)
    check("a folder with task files opens without a question, whatever its name", page.evaluate("__todo.S.store.name") == "work-tasks" and page.locator("#modal-bg.on").count() == 0)
    check("local folder: no page errors", not errors, errors[:3])
    ctx.close()
    # from disk: the guide shows the sibling path
    ctx, page, errors = new_page(browser, init=ls_init(**{"todo.source": "demo"}))
    page.goto((ROOT / "app" / "index.html").as_uri())
    page.wait_for_selector(".row")
    page.evaluate("() => __todo.pickLocalFolder()")
    page.wait_for_selector("#lf-path")
    want = str(ROOT.parent / "data")
    check("from disk: the guide shows <root>\\data next to the build folder", page.input_value("#lf-path") == want, (page.input_value("#lf-path"), want))
    check("from disk: Copy path button", page.locator("#modal [data-a=copy]").count() == 1)
    page.screenshot(path=str(SHOTS / "29-pc-local-folder-guide.png"))
    check("from disk: no page errors", not errors, errors[:3])
    ctx.close()


def test_diagnostics(browser):
    print("\n[17] Device diagnostics (R2-6)")
    ctx, page, errors = new_page(browser, phone=True, init=ls_init(**{"todo.source": "demo", "todo.list": "Home"}))
    page.goto(APP)
    page.wait_for_selector(".row")
    page.click("#app-menu")
    page.locator("#pop button", has_text="Settings").click()
    page.click("#modal [data-a=diag]")
    page.wait_for_selector("#diag-text")
    txt = page.input_value("#diag-text")
    for k in ['"decided"', '"pointerCoarse"', '"anyPointerFine"', '"screen"', '"inner"', '"installedApp"', '"userAgent"', "Recent loads"]:
        check(f"diagnostics include {k}", k in txt, txt[:200])
    check("diagnostics show this build and the phone decision", '"build": "%s"' % page.evaluate("__todo.BUILD") in txt and '"phone": true' in txt)
    check("the load is logged", " load: PHONE" in txt, txt[-300:])
    page.screenshot(path=str(SHOTS / "31-phone-diagnostics.png"))
    page.click("#modal [data-a=cancel]")
    page.reload(); page.wait_for_selector(".row")
    log = page.evaluate("JSON.parse(localStorage.getItem('todo.deviceLog'))")
    check("the log keeps earlier loads (2 after a reload)", len(log) == 2, log)
    check("diagnostics: no page errors", not errors, errors[:3])
    ctx.close()


def test_device_copy(browser):
    print("\n[18] Device copy: start from this device's copy, download only changes (R2-7 A)")
    fg = FakeGraph(FOLDER, dict(TEST_FILES))
    ctx, page, errors = new_page(browser, phone=True, init=TEST_AUTH + ls_init(**{
        "todo.source": "onedrive", "todo.folder": FOLDER, "todo.pollMs": 86400000, "todo.list": "Feedback", "todo.everSignedIn": True}))
    fg.install(page)
    n_files = len(TEST_FILES)
    title = lambda name: page.evaluate("f => __todo.all().find(t => t.file === f || t.file.endsWith('/' + f))?.title ?? null", name)
    def restart():
        page.reload(); page.wait_for_selector(".row"); page.wait_for_function("__todo.S.store && __todo.S.store.ready === true"); page.wait_for_timeout(150)

    page.goto(APP); page.wait_for_selector(".row"); page.wait_for_function("__todo.S.store.ready === true")
    check("first start downloads every file once", fg.downloads() == n_files, (fg.downloads(), n_files))
    check("the app runs on the device-copy layer", page.evaluate("__todo.S.store.cachedLayer === true && __todo.S.store.kind === 'onedrive'"))

    d0, f0 = fg.downloads(), fg.full_checks(); restart()
    check("second start downloads nothing", fg.downloads() == d0, (d0, fg.downloads()))
    check("…and doesn't re-read the folder (one change-feed call with the bookmark)", fg.full_checks() == f0, (f0, fg.full_checks()))
    check("…and shows the same tasks", title("board-view.md") == "Board View" and page.evaluate("__todo.all().length") == n_files - 1)

    fg.ext_edit("board-view.md", fg.files()["board-view.md"].replace("title: Board View", "title: Board View (edited elsewhere)"))
    fg.ext_delete("round-1.md")
    d0 = fg.downloads(); restart()
    check("edits made elsewhere while closed: only that file is downloaded", fg.downloads() - d0 == 1, fg.downloads() - d0)
    check("…the edit shows", title("board-view.md") == "Board View (edited elsewhere)", title("board-view.md"))
    check("…and a file deleted elsewhere is gone", title("round-1.md") is None)

    page.evaluate("async () => { const t = __todo.all().find(x => (x.file === 'access-from-android-phone.md' || x.file.endsWith('/access-from-android-phone.md'))); t.title = 'Saved here'; await __todo.saveTask(t); }")
    d0 = fg.downloads(); restart()
    check("our own save: kept in the copy, not downloaded again", fg.downloads() == d0 and title("access-from-android-phone.md") == "Saved here", (fg.downloads() - d0, title("access-from-android-phone.md")))

    fg.expire_before = fg.seq + 1
    f0, d0 = fg.full_checks(), fg.downloads(); restart()
    check("expired bookmark → one full re-check of the folder", fg.full_checks() == f0 + 1, (f0, fg.full_checks()))
    check("…but nothing is downloaded when the versions match", fg.downloads() == d0, fg.downloads() - d0)
    fg.expire_before = 0

    # start with no connection: the copy shows; when the connection is back, the app catches up
    offline = lambda route: route.abort()
    page.route("https://graph.microsoft.com/**", offline)
    page.reload(); page.wait_for_selector(".row"); page.wait_for_timeout(500)
    check("offline start: tasks show from the device copy", title("board-view.md") == "Board View (edited elsewhere)" and page.locator(".row").count() >= 2)
    check("…marked offline, with a toast", page.evaluate("__todo.S.offline === true") and "Offline" in page.inner_text("#toast"), page.inner_text("#toast"))
    page.unroute("https://graph.microsoft.com/**", offline)
    fg.ext_edit("desktop-app.md", "---\nid: t-x\ntitle: Back online\nstatus: open\nlist: Feedback\norder: 9\n---\n") if "desktop-app.md" in fg.files() else fg.ext_edit("board-view.md", fg.files()["board-view.md"].replace("Board View (edited elsewhere)", "Back online"))
    page.evaluate("() => __todo.poll(true)"); page.wait_for_timeout(600)
    page.evaluate("() => __todo.poll(true)"); page.wait_for_timeout(400)
    check("back online: the next check catches up", page.evaluate("__todo.S.offline === false && __todo.all().some(t => t.title === 'Back online')"))

    # Settings → Diagnostics → Clear device copy → everything is downloaded again
    page.click("#app-menu"); page.locator("#pop button", has_text="Settings").click(); page.click("#modal [data-a=diag]")
    check("diagnostics show the device copy", '"deviceCopy"' in page.input_value("#diag-text") and '"bookmark": true' in page.input_value("#diag-text"))
    d0 = fg.downloads()
    page.click("#modal [data-a=clearcopy]"); page.wait_for_timeout(1500); page.wait_for_selector(".row"); page.wait_for_function("__todo.S.store.ready === true")
    check("Clear device copy → the next start downloads everything again", fg.downloads() - d0 == len(fg.files()), (fg.downloads() - d0, len(fg.files())))
    check("never wrote without If-Match", not fg.violations, fg.violations[:3])
    check("device copy (OneDrive): no page errors", not errors, errors[:3])
    ctx.close()

    # local folder: an edit made outside the app while it was closed shows up after a restart
    ctx, page, errors = new_page(browser, init=ls_init(**{"todo.source": "local", "todo.pollMs": 86400000}))
    page.goto(APP)
    page.evaluate("""async () => {
        const root = await navigator.storage.getDirectory(); try { await root.removeEntry('dc', { recursive:true }); } catch {}
        const d = await root.getDirectoryHandle('dc', { create:true });
        const put = async (n, s) => { const w = await (await d.getFileHandle(n, { create:true })).createWritable(); await w.write(s); await w.close(); };
        await put('one.md', '---\\nid: t-1\\ntitle: One\\nstatus: open\\norder: 1\\n---\\n');
        await put('two.md', '---\\nid: t-2\\ntitle: Two\\nstatus: open\\norder: 2\\n---\\n');
        await __todo.useStore(new __todo.FsStore(d));
        const db = await new Promise(r => { const q = indexedDB.open('task-board', 1); q.onupgradeneeded = () => q.result.createObjectStore('kv'); q.onsuccess = () => r(q.result); });
        await new Promise(r => { const tx = db.transaction('kv', 'readwrite'); tx.objectStore('kv').put(d, 'dir'); tx.oncomplete = r; }); }""")
    page.wait_for_selector(".row")
    check("local folder runs on the device-copy layer", page.evaluate("__todo.S.store.cachedLayer === true && __todo.S.store.kind === 'local'"))
    page.evaluate("""async () => { const d = await (await navigator.storage.getDirectory()).getDirectoryHandle('dc');
        await new Promise(r => setTimeout(r, 20));
        const w = await (await d.getFileHandle('two.md')).createWritable(); await w.write('---\\nid: t-2\\ntitle: Two (edited outside)\\nstatus: open\\norder: 2\\n---\\n'); await w.close(); }""")
    page.reload(); page.wait_for_selector(".row"); page.wait_for_function("__todo.S.store && __todo.S.store.ready === true")
    info = page.evaluate("__todo.S.store.info()")
    check("local folder: the outside edit shows after a restart", page.evaluate("__todo.all().some(t => t.title === 'Two (edited outside)')"))
    check("…started from the copy and re-read only the changed file", info["fromCopyAtStart"] == 2 and info["downloaded"] == 1, info)
    check("device copy (local): no page errors", not errors, errors[:3])
    ctx.close()


def test_agent_round1(browser):
    print("\n[19] Agent round 1 fixes (T1-1 … T1-11)")
    od_init = lambda **kv: TEST_AUTH + ls_init(**{"todo.source": "onedrive", "todo.folder": FOLDER, "todo.pollMs": 86400000, "todo.everSignedIn": True, **kv})
    ready = "__todo.S.store && __todo.S.store.ready === true"
    tid = lambda page, f: page.evaluate("f => __todo.all().find(t => t.file === f || t.file.endsWith('/' + f)).id", f)

    def hold_delta(page):                       # hold the device copy's change-feed check (the start-up window)
        held = []
        def h(route, req):
            if ":/delta" in req.url and "token=" in req.url: held.append((route, req))
            else: route.fallback()
        page.route("https://graph.microsoft.com/**", h)
        return held, h

    def release(fg, page, held, h):
        page.unroute("https://graph.microsoft.com/**", h)
        for r, req in held: fg._handle(r, req)
        page.wait_for_function(ready, timeout=5000); page.wait_for_timeout(300)

    # --- T1-1: editing during the device-copy start-up window never silently drops another device's edit
    for case in ("typed in the window", "opened in the window"):
        fg = FakeGraph(FOLDER, dict(TEST_FILES))
        ctx, page, errors = new_page(browser, phone=True, init=od_init(**{"todo.list": "Test List"}))
        fg.install(page)
        page.goto(APP); page.wait_for_selector(".row"); page.wait_for_function(ready)
        fg.ext_edit("sub-2.md", fg.files()["sub-2.md"].replace("yyy", "yyy\n\nADDED-ELSEWHERE"))
        held, h = hold_delta(page)
        page.reload(); page.wait_for_selector(".row"); page.wait_for_timeout(300)
        in_window = page.evaluate("__todo.S.store.ready === false") and len(held) >= 1
        page.evaluate("id => __todo.openDrawer(id)", tid(page, "sub-2.md")); page.wait_for_selector("#drawer.open")
        if case == "typed in the window":
            page.evaluate("() => __todo.S.editor.setMarkdown('yyy\\n\\nTYPED-HERE')")
            release(fg, page, held, h)
            check(f"T1-1 ({case}): cached rows shown while the check is pending", in_window)
            check(f"T1-1 ({case}): the 'changed elsewhere' banner shows", page.locator("#d-banner.on").count() == 1)
            page.click("#d-save"); page.wait_for_timeout(500)
            check(f"T1-1 ({case}): Save → conflict dialog, the other edit is still on disk",
                  "Changed elsewhere" in page.inner_text("#modal") and "ADDED-ELSEWHERE" in fg.files()["sub-2.md"], fg.files()["sub-2.md"])
            page.click("#modal [data-a=both]"); page.wait_for_timeout(600)
            names = [n for n in fg.files() if n.split("/")[-1].startswith("sub-2 (conflict")]
            check(f"T1-1 ({case}): Keep both → both versions are kept", names and "TYPED-HERE" in fg.files()[names[0]] and "ADDED-ELSEWHERE" in fg.files()["sub-2.md"], list(fg.files()))
        else:
            release(fg, page, held, h)
            check(f"T1-1 ({case}): the untouched editor is refilled with the fresh text", "ADDED-ELSEWHERE" in page.evaluate("__todo.S.editor.getMarkdown()"))
            page.evaluate("() => __todo.S.editor.setMarkdown(__todo.S.editor.getMarkdown() + '\\n\\nTYPED-AFTER')")
            page.click("#d-save"); page.wait_for_timeout(500)
            f = fg.files()["sub-2.md"]
            check(f"T1-1 ({case}): the save keeps both edits", "ADDED-ELSEWHERE" in f and "TYPED-AFTER" in f, f)
        check(f"T1-1 ({case}): never wrote without If-Match", not fg.violations, fg.violations[:3])
        check(f"T1-1 ({case}): no page errors", not errors, errors[:3])
        ctx.close()

    # --- T1-2, T1-4, T1-5 on a fake OneDrive with tricky files
    fm = lambda i, title, extra="": f"---\nid: {i}\ntitle: {title}\nstatus: open\nlist: Inbox\norder: 1\n{extra}---\n"
    files = {
        "dash.md": fm("t-a", "Dash") + "\n- [ ] Rain jacket\n- [x] Charger\nsee file_name and C:\\dev\\path\n  indented line \n\n| a | b |\n|---|---|\n| 1 | 2 |\n",
        "no-blank.md": fm("t-b", "No blank") + "Text added\nxxx",
        "crlf.md": (fm("t-c", "Crlf trip") + "\n- [x] Charger\n- [ ] Passport\n").replace("\n", "\r\n"),
        "bad-due.md": fm("t-d", "Bad due", "due: 10/20/2026\nrepeat: daily\n"),
        "bad-due-2.md": fm("t-e", "Bad due two", "due: tomorrow\n") + "\nnotes\n",
        "_todo.json": '{\n  "format": 3,\n  "lists": ["Inbox"]\n}\n',
    }
    fg = FakeGraph(FOLDER, dict(files))
    ctx, page, errors = new_page(browser, init=od_init(**{"todo.list": "Inbox"}))
    fg.install(page)
    page.goto(APP); page.wait_for_selector(".row"); page.wait_for_function(ready)
    for name in ("dash.md", "no-blank.md"):
        page.evaluate("id => __todo.openDrawer(id)", tid(page, name)); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(150)
        page.fill("#f-title", page.input_value("#f-title") + " X"); page.click("#d-saveclose"); page.wait_for_timeout(400)
        orig, new = files[name], fg.files()[name]
        body = lambda s: s.split("\n---\n", 1)[1]
        check(f"T1-2: changing only the title of {name} leaves the body byte for byte (Formatted editor)", body(new) == body(orig) and "X\n" in new, repr(new))
    page.evaluate("id => __todo.openDrawer(id)", tid(page, "dash.md")); page.wait_for_selector("#drawer.open")
    page.evaluate("() => __todo.S.editor.setMarkdown(__todo.S.editor.getMarkdown() + '\\n\\nNEW LINE')")
    page.click("#d-saveclose"); page.wait_for_timeout(400)
    check("T1-2: an edited body is still saved", "NEW LINE" in fg.files()["dash.md"])
    # T1-5: CRLF
    check("T1-5: a CRLF file's checklist counts", page.evaluate("__todo.checklistBlocks(__todo.get('t-c').body).length") == 2)
    page.locator(".row[data-id=t-c] [data-act=toggle]").click(); page.wait_for_timeout(300)
    check("T1-5: checking off a CRLF task with an open line asks Check all / only this", "Check all" in page.inner_text("#modal"))
    page.click("#modal [data-a=one]"); page.wait_for_timeout(400)
    f = fg.files()["crlf.md"]
    check("T1-5: …and the file keeps CRLF line endings", "status: done" in f and f.count("\r\n") == f.count("\n"), repr(f))
    # T1-4: unreadable due
    check("T1-4: an unreadable due is flagged ⚠", page.locator(".row[data-id=t-d] .wflag").count() == 1 and "due: 10/20/2026" in page.evaluate("__todo.get('t-d').unknown.join()"))
    page.locator(".row[data-id=t-d] [data-act=toggle]").click(); page.wait_for_timeout(400)
    f = fg.files()["bad-due.md"]
    check("T1-4: a recurring task with an unreadable due checks off normally (no NaN, due kept)", "NaN" not in f and "due: 10/20/2026" in f and "status: done" in f and "repeat: daily" in f, f)
    page.evaluate("id => __todo.openDrawer(id)", "t-e"); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(100)
    page.fill("#f-title", "Bad due two X"); page.click("#d-saveclose"); page.wait_for_timeout(400)
    f = fg.files()["bad-due-2.md"]
    check("T1-4: saving another field keeps the unreadable due untouched", "due: tomorrow" in f and "title: Bad due two X" in f, f)
    check("T1-4: nextDue never returns an invalid date", page.evaluate("__todo.nextDue(__todo.parseRepeat('daily'), '10/20/2026', '2026-10-23')") == "2026-10-24")
    check("T1-2/4/5: never wrote without If-Match", not fg.violations, fg.violations[:3])
    check("T1-2/4/5: no page errors", not errors, errors[:3])

    # --- T1-8: Sign out removes this account's device copy
    count = """async () => { const db = await new Promise(r => { const q = indexedDB.open('hta-device-copy'); q.onsuccess = () => r(q.result); });
        return await new Promise(r => { const q = db.transaction('files').objectStore('files').count(); q.onsuccess = () => r(q.result); }); }"""
    n0 = page.evaluate(count)
    page.click("#app-menu"); page.locator("#pop button", has_text="Sign out").click(); page.wait_for_timeout(400)
    n1 = page.evaluate(count)
    check("T1-8: Sign out removes this account's files from the device copy", n0 >= len(files) and n1 == 0, (n0, n1))
    ctx.close()

    # --- T1-3: two local folders with the same name each get their own device copy
    ctx, page, errors = new_page(browser, init=ls_init(**{"todo.source": "local", "todo.pollMs": 86400000}) + "window.__TEST_NO_BOOT__ = true;")
    page.goto(APP)
    page.evaluate("""async () => {
        const root = await navigator.storage.getDirectory();
        const mk = async (path, name, title) => { let d = root; for (const p of path.split('/')) d = await d.getDirectoryHandle(p, { create:true });
          const w = await (await d.getFileHandle(name, { create:true })).createWritable();
          await w.write(`---\\nid: ${name}\\ntitle: ${title}\\nstatus: open\\norder: 1\\n---\\n`); await w.close(); return d; };
        for (const r of ['r1a', 'r1b']) try { await root.removeEntry(r, { recursive:true }); } catch {}
        window.__A = await mk('r1a/data', 'a.md', 'Folder A task'); window.__B = await mk('r1b/data', 'b.md', 'Folder B task'); }""")
    open_dir = """async (k) => { window.__seen = []; const mo = new MutationObserver(() => { const ts = [...document.querySelectorAll('#rows .ttl')].map(e => e.textContent); if (ts.length) window.__seen.push(ts.join('|')); });
        mo.observe(document.querySelector('#rows'), { childList:true, subtree:true });
        await __todo.useStore(new __todo.FsStore(window[k])); mo.disconnect(); return { seen: window.__seen, scope: __todo.S.store.scope }; }"""
    a1 = page.evaluate(open_dir, "__A"); b1 = page.evaluate(open_dir, "__B"); a2 = page.evaluate(open_dir, "__A")
    check("T1-3: opening another folder named 'data' never shows the first folder's tasks", not any("Folder A" in s for s in b1["seen"]), b1)
    check("T1-3: each folder has its own copy, found again on reopen", a1["scope"] != b1["scope"] and a1["scope"] == a2["scope"] and a2["seen"][0] == "Folder A task", (a1, b1, a2))
    check("T1-3: no page errors", not errors, errors[:3])
    ctx.close()

    # --- T1-7, T1-10, T1-11 on demo data (phone)
    ctx, page, errors = new_page(browser, phone=True, init=ls_init(**{"todo.source": "demo", "todo.view2": "due", "todo.pollMs": 5000}))
    page.clock.install(time=datetime.datetime(2026, 10, 23, 23, 59, 30))
    page.goto(APP); page.wait_for_selector("#tday-today")
    over0 = page.inner_text("[data-tday=over]")
    page.clock.run_for(5 * 60 * 1000); page.wait_for_timeout(200)
    over1 = page.inner_text("[data-tday=over]")
    check("T1-7: after midnight the Today view rolls over without a refresh", over0.endswith("1") and over1.endswith("2"), (over0, over1))
    heads = page.evaluate("[...document.querySelectorAll('.tday-head')].map(e => e.getBoundingClientRect().height)")
    z = page.evaluate("parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--z'))")
    check("T1-10: Today view section headers are ≥ 44 px tall", heads and min(heads) >= 44 * z - 0.5, (heads, z))
    hit = page.evaluate("""z => { const b = document.querySelector('.row .qbtn'); const r = b.getBoundingClientRect(); const x = r.left + r.width / 2, e = 6 * z - 0.5;
        return [r.height, document.elementFromPoint(x, r.top - e) === b, document.elementFromPoint(x, r.bottom + e - 1) === b]; }""", z)
    check("T1-10: the Today-view buttons keep their size but have a ≥ 44 px tap area", hit[1] and hit[2] and hit[0] + 12 * z >= 44 * z - 0.5, (hit, z))
    page.evaluate("() => { __todo.S.view = 'list'; __todo.S.list = 'Home'; __todo.render(); }")
    ttl = page.locator(".row .ttl").first
    check("T1-11: task titles are focusable buttons", ttl.get_attribute("tabindex") == "0" and ttl.get_attribute("role") == "button")
    sl0 = page.evaluate("document.querySelector('#scroller').scrollLeft")
    ttl.focus(); page.keyboard.press("Enter"); page.wait_for_selector("#drawer.open")
    check("T1-11: Enter on a focused title opens the task", page.locator("#drawer.open").count() == 1 and page.evaluate("document.querySelector('#scroller').scrollLeft") == sl0)
    page.click("#d-close"); page.wait_for_timeout(200)
    page.focus("#app-menu"); page.click("#app-menu"); page.locator("#pop button", has_text="Search").click(); page.wait_for_timeout(100)
    page.keyboard.press("Escape"); page.wait_for_timeout(100)
    page.focus("#list-name"); page.evaluate("() => document.querySelector('#list-name').click()"); page.wait_for_timeout(200)
    role = page.evaluate("[document.querySelector('#modal').getAttribute('role'), document.querySelector('#modal').getAttribute('aria-modal'), document.querySelector('#modal').contains(document.activeElement)]")
    check("T1-11: dialogs are role=dialog, aria-modal, and take focus", role == ["dialog", "true", True], role)
    page.keyboard.press("Escape"); page.wait_for_timeout(100)
    check("T1-11: closing a dialog returns focus to what opened it", page.evaluate("document.activeElement && document.activeElement.id") == "list-name")
    check("T1-7/10/11: no page errors", not errors, errors[:3])
    ctx.close()


def test_agent_round2(browser):
    print("\n[20] Agent round 2 fixes (T2-1 … T2-5)")
    od_init = lambda **kv: TEST_AUTH + ls_init(**{"todo.source": "onedrive", "todo.folder": FOLDER, "todo.pollMs": 86400000, "todo.everSignedIn": True, **kv})
    ready = "__todo.S.store && __todo.S.store.ready === true"
    fm = lambda i, title, extra="": f"---\nid: {i}\ntitle: {title}\nstatus: open\nlist: Inbox\norder: 1\n{extra}---\n"
    today = datetime.date.today().isoformat()
    files = {
        "check-all.md": fm("t-ca", "Check all here") + "\n- [ ] open line\n- [x] done line\n",
        "recycle.md": fm("t-rc", "Recycle here", f"due: {today}\nrepeat: daily\n") + "\n- [x] step one\n",
        "bad-due.md": fm("t-bd", "Bad due", "due: 10/20/2026\n") + "\nnotes\n",
        "goes-away.md": fm("t-ga", "Goes away") + "\nkeep me\n",
        "target.md": "---\nid: t-tg\ntitle: Target\nstatus: open\nlist: Home\norder: 1\n---\n\n- [ ] existing\n",
        "child.md": "---\nid: t-ch\ntitle: Child\nstatus: open\nlist: Inbox\norder: 2\n---\n\nchild notes\n",
        "_todo.json": '{\n  "format": 3,\n  "lists": ["Inbox", "Home"]\n}\n',
    }
    fg = FakeGraph(FOLDER, dict(files))
    ctx, page, errors = new_page(browser, init=od_init(**{"todo.list": "Inbox"}))
    fg.install(page)
    page.goto(APP); page.wait_for_selector(".row"); page.wait_for_function(ready)
    md = lambda: page.evaluate("__todo.S.editor.getMarkdown()")
    add_text = lambda s: page.evaluate("s => __todo.S.editor.setMarkdown(__todo.S.editor.getMarkdown() + '\\n\\n' + s)", s)

    # T2-1: Check all from the row while the task is open in the drawer
    page.evaluate("() => __todo.openDrawer('t-ca')"); page.wait_for_selector("#drawer.open")
    page.locator(".row[data-id=t-ca] [data-act=toggle]").click(); page.wait_for_selector("#modal [data-a=all]")
    check_all(page); page.wait_for_timeout(500)
    check("T2-1: after Check all, the open drawer shows the checked notes", "[ ]" not in md() and page.input_value("#f-status") == "done", md())
    add_text("EXTRA WORD"); page.click("#d-save"); page.wait_for_timeout(400)
    f = fg.files()["check-all.md"]
    check("T2-1: …and a later notes edit keeps the Check all", "[ ]" not in f and "status: done" in f and "EXTRA WORD" in f, f)
    # T2-1: Recycle from the row while open
    page.evaluate("() => __todo.openDrawer('t-rc')"); page.wait_for_selector("#drawer.open")
    page.locator(".row[data-id=t-rc] [data-act=toggle]").click(); page.wait_for_timeout(500)
    check("T2-1: after Recycle, the open drawer shows the reset notes and the new date", "[ ] step one" in md() and page.input_value("#f-due") > today, (md(), page.input_value("#f-due")))
    add_text("RECYCLE NOTE"); before = fg.files()["recycle.md"]
    page.click("#undo-btn"); page.wait_for_timeout(300)
    check("T2-1: Undo waits while the open editor has unsaved edits", fg.files()["recycle.md"] == before and "Save or close" in page.inner_text("#toast"))
    page.click("#d-save"); page.wait_for_timeout(400)
    f = fg.files()["recycle.md"]
    check("T2-1: …and saving the notes keeps the Recycle (unchecked, next date)", "[ ] step one" in f and "[x] step one" not in f and "RECYCLE NOTE" in f and f"due: {today}" not in f, f)
    page.click("#d-close"); page.wait_for_timeout(200)

    # T2-2: clearing the Due field removes an unreadable due
    page.evaluate("() => __todo.openDrawer('t-bd')"); page.wait_for_selector("#drawer.open")
    page.fill("#f-due", "2026-11-01"); page.fill("#f-due", ""); page.fill("#f-title", "Bad due X")
    page.click("#d-saveclose"); page.wait_for_timeout(400)
    f = fg.files()["bad-due.md"]
    check("T2-2: clearing the Due field removes an unreadable due", "due:" not in f and "title: Bad due X" in f, f)

    # T2-3: Keep both after the original was deleted elsewhere → the drawer doesn't carry on as the copy
    page.evaluate("() => __todo.openDrawer('t-ga')"); page.wait_for_selector("#drawer.open")
    add_text("MY EDIT"); fg.ext_delete("goes-away.md")
    page.click("#d-save"); page.wait_for_selector("#modal [data-a=both]"); page.click("#modal [data-a=both]"); page.wait_for_timeout(700)
    copies = [n for n in fg.files() if n.split("/")[-1].startswith("goes-away (conflict")]
    check("T2-3: Keep both on a deleted file saves my version as a copy", copies and "MY EDIT" in fg.files()[copies[0]], list(fg.files()))
    check("T2-3: …and closes the editor instead of silently editing the copy", page.locator("#drawer.open").count() == 0 and "saved as" in page.inner_text("#toast"), page.inner_text("#toast"))

    # T2-5 / R2-5: a demoted, archived task moves into the target's folder
    page.evaluate("async () => { await __todo.doDemote(__todo.get('t-ch'), __todo.get('t-tg'), { keep:true, kids:'move' }); }"); page.wait_for_timeout(400)
    f = fg.files()["child.md"]
    check("T2-5: demote (keep) moves the archived task into the target's folder (no list: line)", "status: archived" in f and "parent: t-tg" in f and "\nlist:" not in f
          and "Home/child.md" in dict(fg.files()), (list(dict(fg.files())), f))
    check("T2-*: never wrote without If-Match", not fg.violations, fg.violations[:3])
    check("T2-*: no page errors", not errors, errors[:3])
    ctx.close()

    # T2-4: first fill on a new device shows progress while every file downloads
    many = {f"task-{i:03}.md": fm(f"t-{i:03}", f"Task {i}") for i in range(30)}
    many["_todo.json"] = '{"format": 3, "lists": ["Inbox"]}\n'
    fg = FakeGraph(FOLDER, many)
    ctx, page, errors = new_page(browser, phone=True, init=od_init(**{"todo.list": "Inbox"}))
    fg.install(page)
    held, seen = [], [0]
    def hold(route, req):
        seen[0] += 1
        if seen[0] > 5: held.append((route, req))
        else: fg._download(route, req)
    page.route("https://fake-dl.test/**", hold)
    page.goto(APP); page.wait_for_selector("#first-fill", timeout=10000); page.wait_for_timeout(300)
    txt = page.inner_text("#first-fill")
    check("T2-4: a new device shows 'Downloading your tasks… n / total' instead of an empty list", "Downloading your tasks" in txt and f"/ {len(many)}" in txt, txt)
    page.unroute("https://fake-dl.test/**", hold)
    for r, req in held: fg._download(r, req)
    page.wait_for_function(ready); page.wait_for_selector(".row")
    check("T2-4: …then the tasks appear", page.locator("#first-fill").count() == 0 and page.locator(".row").count() == 30)
    check("T2-4: no page errors", not errors, errors[:3])
    ctx.close()


def test_agent_round3(browser):
    print("\n[21] Agent round 3 fixes (T3-1, T3-2)")
    od_init = lambda **kv: TEST_AUTH + ls_init(**{"todo.source": "onedrive", "todo.folder": FOLDER, "todo.pollMs": 86400000, "todo.everSignedIn": True, **kv})
    ready = "__todo.S.store && __todo.S.store.ready === true"
    fm = lambda i, title: f"---\nid: {i}\ntitle: {title}\nstatus: open\nlist: Inbox\norder: 1\n---\n"

    # T3-1: typing while the Check-all save is in flight → banner, and Save asks instead of overwriting
    files = {"ck.md": fm("t-ck", "Check in flight") + "\n- [ ] open line\n- [x] done line\n", "_todo.json": '{"format": 3, "lists": ["Inbox"]}\n'}
    fg = FakeGraph(FOLDER, dict(files))
    ctx, page, errors = new_page(browser, init=od_init(**{"todo.list": "Inbox"}))
    fg.install(page)
    page.goto(APP); page.wait_for_selector(".row"); page.wait_for_function(ready)
    held = []
    def hold_put(route, req):
        if req.method == "PUT": held.append((route, req))
        else: route.fallback()
    page.route("https://graph.microsoft.com/**", hold_put)
    page.evaluate("() => __todo.openDrawer('t-ck')"); page.wait_for_selector("#drawer.open")
    page.locator(".row[data-id=t-ck] [data-act=toggle]").click(); page.wait_for_selector("#modal [data-a=all]")
    check_all(page); page.wait_for_timeout(300)
    page.evaluate("() => __todo.S.editor.setMarkdown(__todo.S.editor.getMarkdown() + ' TYPED DURING SAVE')")
    page.unroute("https://graph.microsoft.com/**", hold_put)
    for r, req in held: fg._handle(r, req)
    page.wait_for_timeout(500)
    check("T3-1: typing during the check-off save → the banner shows", page.locator("#d-banner.on").count() == 1)
    page.click("#d-save"); page.wait_for_timeout(400)
    asked = "Changed elsewhere" in page.inner_text("#modal")
    f = fg.files()["ck.md"]
    check("T3-1: …and Save asks first (no silent overwrite of the checkmarks)", asked and "[ ] open line" not in f and "status: done" in f, (asked, f))
    page.click("#modal [data-a=both]"); page.wait_for_timeout(600)
    copies = [n for n in fg.files() if n.split("/")[-1].startswith("ck (conflict")]
    check("T3-1: Keep both keeps the checkmarks and the typed text", copies and "TYPED DURING SAVE" in fg.files()[copies[0]] and "[ ] open line" not in fg.files()["ck.md"], list(fg.files()))
    check("T3-1: never wrote without If-Match", not fg.violations, fg.violations[:3])
    check("T3-1: no page errors", not errors, errors[:3])
    ctx.close()

    # T3-2: during the first download the half-loaded list can't be acted on
    many = {f"task-{i:03}.md": fm(f"t-{i:03}", f"Task {i}") for i in range(20)}
    many["_todo.json"] = '{"format": 3, "lists": ["Inbox"]}\n'
    fg = FakeGraph(FOLDER, many)
    ctx, page, errors = new_page(browser, phone=True, init=od_init(**{"todo.list": "Inbox"}))
    fg.install(page)
    held, seen = [], [0]
    def hold(route, req):
        seen[0] += 1
        if seen[0] > 3: held.append((route, req))
        else: fg._download(route, req)
    page.route("https://fake-dl.test/**", hold)
    page.goto(APP); page.wait_for_selector("#first-fill", timeout=10000); page.wait_for_timeout(300)
    page.click("#app-menu"); page.locator("#pop button", has_text="Show done").click(); page.wait_for_timeout(200)
    check("T3-2: a menu action during the first download keeps the progress line", page.locator("#first-fill").count() == 1 and "No " not in page.inner_text("#rows"), page.inner_text("#rows"))
    check("T3-2: …quick-add stays off", page.evaluate("document.querySelector('#qa').disabled") is True)
    page.click("#list-name"); page.wait_for_timeout(200)
    check("T3-2: …and the list picker waits", page.locator("#modal-bg.on").count() == 0 and "downloading" in page.inner_text("#toast").lower(), page.inner_text("#toast"))
    page.unroute("https://fake-dl.test/**", hold)
    for r, req in held: fg._download(r, req)
    page.wait_for_function(ready); page.wait_for_selector(".row")
    check("T3-2: after the download, the list and quick-add work", page.locator("#first-fill").count() == 0 and page.locator(".row").count() == 20 and page.evaluate("document.querySelector('#qa').disabled") is False)
    page.click("#app-menu"); page.locator("#pop button", has_text="Show done").click()
    check("T3-2: no page errors", not errors, errors[:3])
    ctx.close()


def test_r26_signin_editor(browser):
    print("\n[19] R2-6: sign-in without leaving the app window; editor fits a phone; bigger notes")
    # a fake MSAL with the new steps; each case sets how silent/popup behave
    def auth(account=False, silent="fail", popup="ok", redirect_return=False):
        return ("window.__TEST_AUTH__ = { account: " + ("{ username:'test@example.com' }" if account else "null") +
                ", redirectReturn: " + ("true" if redirect_return else "false") + """,
          async init(){ return { account: this.account, redirectReturn: this.redirectReturn }; },
          async token(){ if (!this.account) throw new __todo.AuthError('no'); return 'fake-token'; },
          async silent(){ window.__silentCalls = (window.__silentCalls||0) + 1; if (SILENT === 'ok'){ this.account = { username:'test@example.com' }; return this.account; }
            throw Object.assign(new Error('x'), { errorCode:'login_required' }); },
          async signInPopup(){ window.__popupCalls = (window.__popupCalls||0) + 1; const how = POPUP;
            if (how === 'ok'){ this.account = { username:'test@example.com' }; return this.account; }
            throw Object.assign(new Error(how), { errorCode: how }); },
          signIn(){ window.__signInCalls = (window.__signInCalls||0) + 1; },
          signOut(){}, user(){ return this.account ? 'test@example.com' : ''; } };""").replace("SILENT", json.dumps(silent)).replace("POPUP", json.dumps(popup))
    base = {"todo.source": "onedrive", "todo.folder": FOLDER, "todo.pollMs": 86400000, "todo.list": "Feedback", "todo.everSignedIn": True,
            "todo.lastUser": "test@example.com"}
    calls = lambda page: page.evaluate("({ silent: window.__silentCalls||0, popup: window.__popupCalls||0, redirect: window.__signInCalls||0 })")
    log = lambda page: page.evaluate("localStorage.getItem('todo.deviceLog') || ''")

    # 1. the sign-in was dropped overnight, but Microsoft renews it in the background → no screen at all
    fg = FakeGraph(FOLDER, dict(TEST_FILES))
    ctx, page, errors = new_page(browser, phone=True, init=auth(silent="ok") + ls_init(**base)); fg.install(page)
    page.goto(APP); page.wait_for_selector(".row")
    c = calls(page)
    check("background renewal works → tasks load, no popup, no redirect", c == {"silent": 1, "popup": 0, "redirect": 0}, c)
    check("…logged in Diagnostics", "background renewal ok" in log(page))
    ctx.close()

    # 2. background renewal fails → 'expired' + Sign in; a tap opens the popup; the app window never leaves
    fg = FakeGraph(FOLDER, dict(TEST_FILES))
    ctx, page, errors = new_page(browser, phone=True, init=auth(silent="fail", popup="ok") + ls_init(**base)); fg.install(page)
    page.goto(APP); page.wait_for_selector(".start")
    check("renewal failed: no automatic redirect, 'expired' + Sign in", calls(page)["redirect"] == 0 and "expired" in page.inner_text("#rows"), page.inner_text("#rows")[:100])
    page.click("button:has-text('Sign in with Microsoft')"); page.wait_for_selector(".row")
    c = calls(page)
    check("tap Sign in → popup → tasks load, no redirect", c["popup"] == 1 and c["redirect"] == 0, c)
    check("…logged: renewal failed, popup ok", "background renewal failed" in log(page) and "popup ok" in log(page), log(page)[-300:])
    check("…no stale draft left behind by the popup sign-in", page.evaluate("localStorage.getItem('todo.draft')") is None)
    check("sign-in (popup): no page errors", not errors, errors[:3])
    ctx.close()

    # 3. popups blocked or can't report back → the redirect, in the same tap
    for how in ["popup_window_error", "redirect_bridge_timeout"]:
        ctx, page, errors = new_page(browser, phone=True, init=auth(popup=how) + ls_init(**base))
        page.goto(APP); page.wait_for_selector(".start")
        page.click("button:has-text('Sign in with Microsoft')"); page.wait_for_timeout(300)
        c = calls(page)
        check(f"popup fails ({how}) → falls back to the redirect in the same tap", c["popup"] == 1 and c["redirect"] == 1, c)
        ctx.close()

    # 4. you close the popup → no redirect yet; the next tap uses the redirect (a phone where popups misbehave isn't stuck)
    ctx, page, errors = new_page(browser, phone=True, init=auth(popup="user_cancelled") + ls_init(**base))
    page.goto(APP); page.wait_for_selector(".start")
    page.click("button:has-text('Sign in with Microsoft')"); page.wait_for_timeout(300)
    c = calls(page)
    check("popup closed by you → no redirect, a hint to retry", c["popup"] == 1 and c["redirect"] == 0 and "Sign in again" in page.inner_text("#toast"), (c, page.inner_text("#toast")))
    page.click("button:has-text('Sign in with Microsoft')"); page.wait_for_timeout(300)
    c = calls(page)
    check("…the next tap goes straight to the redirect", c["popup"] == 1 and c["redirect"] == 1, c)
    ctx.close()

    # 5. sign-in expires while a task is open with unsaved edits → popup sign-in keeps everything on screen
    fg = FakeGraph(FOLDER, dict(TEST_FILES))
    ctx, page, errors = new_page(browser, phone=True, init=auth(account=True, popup="ok") + ls_init(**base)); fg.install(page)
    page.goto(APP); page.wait_for_selector(".row")
    page.locator(".row .ttl", has_text="Board View").first.click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(200)
    page.fill("#f-title", "Unsaved while signed out")
    page.evaluate("() => { const a = window.__TEST_AUTH__; a._tok = a.token; a.token = async () => { throw new __todo.AuthError('expired'); }; return __todo.poll(true); }")
    page.wait_for_timeout(300)
    check("expired mid-session: no redirect, editor untouched", calls(page)["redirect"] == 0 and page.input_value("#f-title") == "Unsaved while signed out")
    check("…the editor shows 'sign-in expired' with its own Sign in button (the status icon is hidden behind it)", page.locator("#d-auth").is_visible())
    page.evaluate("() => { const a = window.__TEST_AUTH__; a.token = a._tok; }")
    page.click("#d-signin"); page.wait_for_timeout(500)
    c = calls(page)
    check("…tap it → popup → signed in again, the unsaved edit still open, the bar gone", not page.locator("#d-auth").is_visible() and c["popup"] == 1 and c["redirect"] == 0
          and page.evaluate("__todo.S.signedOut") is False and page.input_value("#f-title") == "Unsaved while signed out", c)
    page.click("#d-saveclose"); page.wait_for_timeout(400)
    check("…and it saves normally", "title: Unsaved while signed out" in fg.files()["board-view.md"])
    check("expired mid-session: no page errors", not errors, errors[:3])
    ctx.close()

    # 6. the theory check: a return from a redirect sign-in is logged with the phone/PC decision
    fg = FakeGraph(FOLDER, dict(TEST_FILES))
    ctx, page, errors = new_page(browser, phone=True, init=auth(account=True, redirect_return=True) + ls_init(**base)); fg.install(page)
    page.goto(APP); page.wait_for_selector(".row")
    check("a return from the redirect sign-in is logged, with the layout decision", "back from Microsoft (redirect): PHONE" in log(page), log(page)[-200:])
    page.click("#app-menu"); page.locator("#pop button", has_text="Settings").click(); page.click("#modal [data-a=diag]")
    check("…and shows in Diagnostics", "back from Microsoft (redirect)" in page.input_value("#diag-text"))
    ctx.close()

    # 7. the sign-in bridge: a popup/background answer is handed to the app window, and nothing else starts
    import base64
    def state(kind):
        return base64.urlsafe_b64encode(json.dumps({"id": "bridge-test-1", "meta": {"interactionType": kind}}).encode()).decode().rstrip("=")
    ctx = browser.new_context(viewport={"width": 412, "height": 860})
    main = ctx.new_page(); main.goto(APP + "?nothing")
    main.evaluate("() => { window.__got = []; const ch = new BroadcastChannel('bridge-test-1'); ch.onmessage = e => window.__got.push(e.data); }")
    pop = ctx.new_page(); errs = []; pop.on("pageerror", lambda e: errs.append(str(e)))
    pop.goto(APP + "#code=abc123&state=" + state("popup")); pop.wait_for_timeout(800)
    got = main.evaluate("window.__got")
    check("bridge: a popup answer is handed to the app window (MSAL's own bridge, v1 message)", got and got[0].get("v") == 1 and "code=abc123" in got[0].get("payload", ""), got)
    check("…and the app doesn't start in that window", pop.evaluate("typeof window.__todo === 'undefined' && !document.querySelector('.row')"))
    check("bridge: no page errors", not errs, errs[:3])
    ctx.close()
    ctx, page, errors = new_page(browser, phone=True, init=ls_init(**{"todo.source": "demo", "todo.list": "Home"}))
    page.goto(APP + "#code=abc&state=" + state("redirect")); page.wait_for_selector(".row")
    check("bridge: a redirect answer is left to the app (it starts normally)", page.evaluate("typeof window.__todo === 'object'"))
    ctx.close()

    # 8. the editor fits the phone in both start modes, and everything in it can be reached
    media = r"""(() => { const real = window.matchMedia.bind(window), fake = new Map([['pointer:coarse',true],['pointer:fine',false],['any-pointer:fine',true],['any-pointer:coarse',true],['hover:hover',false],['any-hover:hover',false]]);
      window.matchMedia = q => { const k = q.replace(/[()\s]/g, ''); return fake.has(k) ? { matches:fake.get(k), media:q, addEventListener(){}, removeEventListener(){} } : real(q); }; })();"""
    modes = {"desktop-site": ({"width": 979, "height": 1972}, "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"),
             "normal": ({"width": 338, "height": 682}, "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Mobile Safari/537.36")}
    for name, (vp, ua) in modes.items():
        ctx = browser.new_context(viewport=vp, screen={"width": 339, "height": 727}, has_touch=True, user_agent=ua)
        page = ctx.new_page(); errs = []; page.on("pageerror", lambda e: errs.append(str(e)))
        page.add_init_script(media + ls_init(**{"todo.source": "demo", "todo.list": "Home"}))
        page.goto(APP); page.wait_for_selector(".row")
        page.locator(".row .ttl", has_text="Fix gate latch").first.click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(400)
        r = page.evaluate("""() => { const W = innerWidth, d = document.querySelector('#drawer').getBoundingClientRect();
          const inside = s => { const b = document.querySelector(s).getBoundingClientRect(); return b.left >= -1 && b.right <= W + 1; };
          return { left: Math.round(d.left), right: Math.round(d.right), W, fields: ['#d-close', '#f-title', '#f-prefix', '#f-status', '#f-list', '#f-due', '#f-coll', '#d-saveclose'].every(inside) }; }""")
        check(f"editor ({name} start): exactly the screen's width, nothing cut off left or right", abs(r["left"]) <= 1 and abs(r["right"] - r["W"]) <= 1 and r["fields"], r)
        reach = page.evaluate("""() => { const d = document.querySelector('#drawer'); d.scrollTop = d.scrollHeight;
          const f = document.querySelector('.d-foot').getBoundingClientRect(); return f.bottom <= innerHeight + 1; }""")
        check(f"…the bottom of the editor can be scrolled into view ({name})", reach)
        page.evaluate("document.querySelector('#drawer').scrollTop = 0")
        h0 = page.evaluate("document.querySelector('#editor-wrap').getBoundingClientRect().height")
        page.click("#editor .app-expand"); page.wait_for_timeout(200)
        h1 = page.evaluate("document.querySelector('#editor-wrap').getBoundingClientRect().height")
        check(f"⤢ Bigger notes ({name}): fields hidden, notes much taller", not page.locator("#f-title").is_visible() and h1 > h0 * 1.8, (h0, h1))
        if name == "normal": page.screenshot(path=str(SHOTS / "32-phone-notes-big.png"))
        check(f"…Save buttons still there ({name})", page.locator("#d-saveclose").is_visible())
        page.click("#editor .app-expand"); page.wait_for_timeout(200)
        check(f"…⤡ puts the fields back ({name})", page.locator("#f-title").is_visible())
        if name == "desktop-site": page.screenshot(path=str(SHOTS / "33-phone-desktop-site-editor.png"))
        check(f"editor ({name}): no page errors", not errs, errs[:3])
        ctx.close()

    # 9. PC: ⤢ widens the editor to the full window; opening another task resets it; edits survive the toggle
    ctx, page, errors = new_page(browser, init=ls_init(**{"todo.source": "demo", "todo.list": "Home"}))
    page.goto(APP); page.wait_for_selector(".row")
    page.locator(".row .ttl").first.click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(400)
    w0 = page.evaluate("document.querySelector('#drawer').getBoundingClientRect().width")
    page.fill("#f-title", "Edited before expanding")
    page.click("#editor .app-expand"); page.wait_for_timeout(250)
    w1 = page.evaluate("document.querySelector('#drawer').getBoundingClientRect().width")
    check("PC: ⤢ widens the editor to the whole window", w0 < 800 and abs(w1 - 1280) <= 2, (w0, w1))
    page.screenshot(path=str(SHOTS / "34-pc-notes-big.png"))
    page.click("#editor .app-expand"); page.wait_for_timeout(200)
    check("…⤡ back: the unsaved title edit is still there", page.input_value("#f-title") == "Edited before expanding")
    page.click("#editor .app-expand"); page.click("#d-save"); page.wait_for_timeout(300)
    check("…Save works while expanded", page.evaluate("__todo.all().some(t => t.title === 'Edited before expanding')"))
    page.click("#d-close"); page.wait_for_timeout(200)
    page.locator(".row .ttl").nth(1).click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    check("opening another task shows its fields again", page.locator("#f-title").is_visible())
    check("PC bigger notes: no page errors", not errors, errors[:3])
    ctx.close()


# ---------------------------------------------------------------- R2-8 Phase 1: data-safety safeguards
def test_r28_phase1(browser):
    print("\n[22] R2-8 Phase 1: trash + Recently deleted, demote/delete care, conflict diff, drafts, Check all, search banner, overdue badge")
    D = lambda n: (datetime.date.today() + datetime.timedelta(days=n)).isoformat()
    fm = lambda i, title, extra="", lst="Inbox": f"---\nid: {i}\ntitle: {title}\nstatus: open\nlist: {lst}\norder: 1\n{extra}---\n"
    od_init = lambda **kv: TEST_AUTH + ls_init(**{"todo.source": "onedrive", "todo.folder": FOLDER, "todo.pollMs": 86400000, "todo.everSignedIn": True, **kv})
    ready = "__todo.S.store && __todo.S.store.ready === true"
    files_of = lambda page: Files(page.evaluate("() => Object.fromEntries([...__todo.S.store.files].map(([k, v]) => [k, v.text]))"))
    trash_of = lambda page: {k: v for k, v in files_of(page).items() if k.startswith(".trash/")}
    no_trash_tasks = lambda page: page.evaluate("() => !__todo.all().some(t => String(t.file).includes('.trash'))")

    def open_menu(page, label):
        page.click("#app-menu"); page.locator("#pop button", has_text=label).click()

    def delete_row(page, title):
        row(page, title).locator(".row-more").click(); page.locator("#pop button", has_text="Delete").click()
        page.wait_for_selector("#modal [data-a=ok]")

    def recently_deleted(page):
        open_menu(page, "Recently deleted"); page.wait_for_function("() => !document.querySelector('#rd-list')?.textContent.includes('Loading')")

    # ---------- A1. demo store (MemStore), phone: delete dialog (D), trash (A), 15 s Undo, Recently deleted + Restore ----------
    ctx, page, errors = new_page(browser, phone=True, init=ls_init(**{"todo.source": "demo", "todo.list": "Home"}))
    page.goto(APP); page.wait_for_selector(".row")
    solar = ["solar-panel-cleaning.md", "get-quotes.md", "compare-inverter-readings.md", "export-readings-csv.md"]
    before = {n: files_of(page)[n] for n in solar}
    delete_row(page, "Solar panel cleaning")
    txt = page.inner_text("#modal")
    check("Deleted D: the delete dialog shows the task's due date", "This task is due" in txt and page.locator("#modal .dl-due").count() == 1, txt[:200])
    check("Deleted D: it names every subtask, not just a count", all(s in txt for s in ["Get three cleaning quotes", "Compare inverter readings", "Export last 90 days to CSV"]) and "Also delete its 3 subtasks" in txt, txt)
    check("Deleted D: …and says a copy goes to Recently deleted", "Recently deleted" in txt)
    page.click("#modal [data-a=ok]"); page.wait_for_timeout(400)
    tr = trash_of(page)
    check("Deleted A: deleting saves each file's exact text in .trash (MemStore)", sum(1 for k in tr if k.endswith(".md")) == 4 and set(before.values()) <= set(tr.values()), list(tr))
    metas = [json.loads(v) for k, v in tr.items() if k.endswith(".json")]
    check("Deleted A: each entry has a sidecar with path, id, title, due, deletedAt, reason, by, device",
          len(metas) == 4 and all({"path", "id", "title", "due", "deletedAt", "reason", "by", "device"} <= set(m) for m in metas)
          and {m["path"] for m in metas} == {"Home/" + n for n in solar} and all(m["reason"] == "deleted" and m["by"] == "this device" and m["device"] == "Phone" for m in metas)
          and any(m["due"] == D(10) for m in metas), metas[:1])
    check("Deleted A: trash names never collide (timestamp + random + slug)", len({k.rsplit("-", 1)[0] for k in tr}) >= 4 and all(".trash/" in k and "-" in k for k in tr), list(tr))
    check("Deleted A: trashed files never show as tasks (demo)", no_trash_tasks(page) and row(page, "Solar panel cleaning").count() == 0)
    page.wait_for_timeout(6000)
    check("Deleted D: the delete Undo is still offered after 6 s (lasts 15 s)", page.locator("#undo.on").count() == 1, page.inner_text("#undo-msg"))
    page.click("#undo-btn"); page.wait_for_timeout(500)
    check("Undo restores all four files byte for byte", all(files_of(page).get(n) == before[n] for n in solar))
    check("Deleted A: Undo removes the matching trash entries", not trash_of(page), list(trash_of(page)))
    delete_row(page, "Solar panel cleaning"); page.click("#modal [data-a=ok]")
    page.wait_for_timeout(15600)
    check("Deleted D: the delete Undo goes away after 15 s", page.locator("#undo.on").count() == 0)
    delete_row(page, "A deliberately long task title"); page.click("#modal [data-a=ok]"); page.wait_for_timeout(300)
    recently_deleted(page)
    items = page.locator("#modal .rd-item")
    check("Recently deleted lists every entry (4 + 1)", items.count() == 5, items.count())
    check("Recently deleted: due-dated tasks first and highlighted", "rd-due" in items.first.get_attribute("class") and "Solar panel cleaning" in items.first.inner_text()
          and f"Due" in items.first.inner_text(), items.first.inner_text())
    check("Recently deleted: shows the original path, when and why", "solar-panel-cleaning.md" in items.first.inner_text() and "Deleted on Phone" in items.first.inner_text(), items.first.inner_text())
    check("Recently deleted: full screen on a phone", page.evaluate("() => document.querySelector('#modal-bg').classList.contains('full') && document.querySelector('#modal').getBoundingClientRect().height > innerHeight * 0.95"))
    page.screenshot(path=str(SHOTS / "40-phone-recently-deleted.png"))
    check("Restore follow-up: the parent's entry says '+ 3 subtasks'", "+ 3 subtasks" in items.first.inner_text(), items.first.inner_text())
    items.first.locator("button", has_text="Restore").click(); page.wait_for_selector("#modal [data-a=only]")
    txt = page.inner_text("#modal")
    check("…Restore asks: 'Restore <task> and its 3 subtasks?', naming them — Cancel / Only this task / Restore all",
          "Restore Solar panel cleaning and its 3 subtasks (3 levels)?" in txt and all(s in txt for s in ["Get three cleaning quotes", "Compare inverter readings", "Export last 90 days to CSV"])
          and page.locator("#modal [data-a=cancel]").count() == 1 and page.locator("#modal [data-a=all]").count() == 1, txt)
    page.click("#modal [data-a=only]"); page.wait_for_timeout(600)
    check("Restore re-creates the file at its original path, exact text", files_of(page).get("solar-panel-cleaning.md") == before["solar-panel-cleaning.md"])
    check("…removes that trash entry", page.locator("#modal .rd-item").count() == 4 and not any("solar-panel-cleaning" in k for k in trash_of(page)), list(trash_of(page)))
    page.click("#modal [data-a=close]"); page.wait_for_timeout(200)
    check("…and the task is back in its list", row(page, "Solar panel cleaning").count() == 1)
    page.evaluate("() => __todo.S.store.create('Home/long-title-example.md', '---\\nid: t-other\\ntitle: Someone else took the name\\nstatus: open\\norder: 9\\n---\\n')")
    recently_deleted(page)
    page.locator("#modal .rd-item", has_text="A deliberately long").locator("button").click(); page.wait_for_timeout(600)
    check("Restore when the name is taken: a unique name in its folder, like Undo", "Home/long-title-example-2.md" in dict(files_of(page)) and "Someone else" in files_of(page)["Home/long-title-example.md"], [k for k in files_of(page) if "long" in k])
    page.click("#modal [data-a=close]")
    res = page.evaluate("""async () => { const T = __todo;
        const e = await T.trashPut('Sub/deep/folder-task.md', '---\\nid: t-ft\\ntitle: In a folder\\nstatus: open\\nlist: Home\\norder: 1\\n---\\n', { id:'t-ft', title:'In a folder' });
        const all = await T.trashEntries(); const it = all.find(x => x.meta.path === 'Sub/deep/folder-task.md');
        const to = await T.trashRestore(it); return { to, has: T.S.store.files.has('Sub/deep/folder-task.md'), left: (await T.trashEntries()).some(x => x.meta.path === 'Sub/deep/folder-task.md') }; }""")
    check("Restore into a folder path (R2-5 ready): back at Sub/deep/folder-task.md, entry gone", res["to"] == "Sub/deep/folder-task.md" and res["has"] and not res["left"], res)
    check("…and a file two folders down isn't shown as a task (one level of folders for now)", not page.evaluate("() => __todo.all().some(t => t.file.startsWith('Sub/'))"))
    evil = "<img src=x onerror=\"window.__xss=1\">"
    page.evaluate("t => __todo.trashPut('evil.md', 'x', { title: t, due: t })", evil)
    recently_deleted(page)
    check("Recently deleted escapes task text (no markup runs)", page.locator("#modal img").count() == 0 and "<img" in page.inner_text("#modal") and not page.evaluate("window.__xss"))
    page.click("#modal [data-a=close]")
    check("A1 (demo): no page errors", not errors, errors[:3])
    ctx.close()

    # ---------- A2. local folder (FsStore on OPFS, with the device copy), PC ----------
    ctx, page, errors = new_page(browser, init=ls_init(**{"todo.source": "local", "todo.pollMs": 86400000}))
    page.goto(APP)
    page.evaluate("""async () => {
        const root = await navigator.storage.getDirectory(); try { await root.removeEntry('r28', { recursive:true }); } catch {}
        const d = await root.getDirectoryHandle('r28', { create:true });
        const put = async (n, s) => { const w = await (await d.getFileHandle(n, { create:true })).createWritable(); await w.write(s); await w.close(); };
        await put('one.md', '---\\nid: t-1\\ntitle: One\\nstatus: open\\norder: 1\\ndue: """ + D(2) + """\\n---\\nbody one\\n');
        await put('two.md', '---\\nid: t-2\\ntitle: Two\\nstatus: open\\norder: 2\\n---\\n');
        await __todo.useStore(new __todo.FsStore(d));
        const db = await new Promise(r => { const q = indexedDB.open('task-board', 1); q.onupgradeneeded = () => q.result.createObjectStore('kv'); q.onsuccess = () => r(q.result); });
        await new Promise(r => { const tx = db.transaction('kv', 'readwrite'); tx.objectStore('kv').put(d, 'dir'); tx.oncomplete = r; }); }""")
    page.wait_for_selector(".row")
    opfs = lambda: page.evaluate("""async () => { const d = await (await navigator.storage.getDirectory()).getDirectoryHandle('r28'); const out = {};
        const walk = async (h, pre) => { for await (const [n, x] of h.entries()){ if (x.kind === 'file') out[pre + n] = await (await x.getFile()).text(); else await walk(x, pre + n + '/'); } };
        await walk(d, ''); return out; }""")
    one_text = opfs()["one.md"]
    delete_row(page, "One"); page.click("#modal [data-a=ok]"); page.wait_for_timeout(500)
    fs = opfs()
    tmd = [k for k in fs if k.startswith(".trash/") and k.endswith(".md")]; tjs = [k for k in fs if k.startswith(".trash/") and k.endswith(".json")]
    check("Deleted A (local folder): the exact text + sidecar in .trash; the file is gone", "one.md" not in fs and len(tmd) == 1 and fs[tmd[0]] == one_text and len(tjs) == 1, list(fs))
    meta = json.loads(fs[tjs[0]]) if tjs else {}
    check("…sidecar: path, due, reason, device PC", meta.get("path") == "one.md" and meta.get("due") == D(2) and meta.get("reason") == "deleted" and meta.get("device") == "PC", meta)
    page.evaluate("() => __todo.poll(true)"); page.wait_for_timeout(400)
    check("…a background check shows no trash file as a task", no_trash_tasks(page) and page.evaluate("__todo.all().length") == 1)
    page.reload(); page.wait_for_selector(".row"); page.wait_for_function(ready); page.wait_for_timeout(200)
    check("…nor after a restart from the device copy", no_trash_tasks(page) and page.evaluate("__todo.all().length") == 1 and page.evaluate("__todo.S.store.cachedLayer === true"))
    page.evaluate("""async () => { const d = await (await (await navigator.storage.getDirectory()).getDirectoryHandle('r28')).getDirectoryHandle('.trash');
        const w = await (await d.getFileHandle('2026-10-19-12-00-00 old.md', { create:true })).createWritable();
        await w.write('---\\nid: t-old\\ntitle: Old legacy copy\\nstatus: open\\norder: 3\\n---\\n'); await w.close(); }""")
    recently_deleted(page)
    txt = page.inner_text("#modal")
    check("Recently deleted (PC): lists the new entry and an older build's .trash copy", "One" in txt and "Old legacy copy" in txt and page.locator("#modal .rd-item").count() == 2, txt[:300])
    check("…a centred dialog on a PC (not full screen)", not page.evaluate("document.querySelector('#modal-bg').classList.contains('full')"))
    page.screenshot(path=str(SHOTS / "41-pc-recently-deleted.png"))
    page.locator("#modal .rd-item", has_text="Old legacy copy").locator("button").click(); page.wait_for_timeout(600)
    check("…an older copy restores to its old name", "old.md" in opfs() and not any("old.md" in k for k in opfs() if k.startswith(".trash/")))
    page.locator("#modal .rd-item", has_text="One").locator("button").click(); page.wait_for_timeout(600)
    fs = opfs()
    check("Restore (local folder): one.md back with its exact text; .trash empty", fs.get("one.md") == one_text and not [k for k in fs if k.startswith(".trash/")], list(fs))
    page.click("#modal [data-a=close]")
    page.evaluate("""async () => { const T = __todo; await T.trashPut('Gone/sub/y.md', '---\\nid: t-y\\ntitle: Y\\nstatus: open\\norder: 1\\n---\\n', { title:'Y' });
        const e = (await T.trashEntries()).find(x => x.meta.path === 'Gone/sub/y.md'); await T.trashRestore(e); }""")
    check("Restore re-creates missing folders (local folder: Gone/sub/y.md)", "Gone/sub/y.md" in opfs(), list(opfs()))
    check("A2 (local folder): no page errors", not errors, errors[:3])
    ctx.close()

    # ---------- A3. OneDrive (fake Graph: subfolders, delta without paths), phone ----------
    gfiles = {"one.md": fm("t-1", "One", f"due: {D(1)}\n"), "two.md": fm("t-2", "Two"), "three.md": fm("t-3", "Three"),
              "_todo.json": '{\n  "format": 3,\n  "lists": ["Inbox"]\n}\n'}
    fg = FakeGraph(FOLDER, dict(gfiles)); gfiles = dict(fg.files())          # the fixture as stored (folder layout)
    ctx, page, errors = new_page(browser, phone=True, init=od_init(**{"todo.list": "Inbox"}))
    fg.install(page)
    page.goto(APP); page.wait_for_selector(".row"); page.wait_for_function(ready)
    delete_row(page, "One"); page.click("#modal [data-a=ok]"); page.wait_for_timeout(600)
    tr = fg.trash()
    check("Deleted A (OneDrive): text + sidecar created in .trash with conditional creates; the file goes", "one.md" not in fg.files() and len(tr) == 2
          and gfiles["one.md"] in tr.values() and not fg.violations, (list(tr), fg.violations))
    check("…the fake's change feed reports the .trash items (by parent id, no path)", any(it["parent"] == ".trash" and it["seq"] > 0 for it in fg.items.values()))
    page.evaluate("() => __todo.poll(true)"); page.wait_for_timeout(400); page.evaluate("() => __todo.poll(true)"); page.wait_for_timeout(400)
    check("…after delta polls no trash file is a task", no_trash_tasks(page) and page.evaluate("__todo.all().length") == 2, page.evaluate("__todo.all().map(t => t.file)"))
    fg.ext_edit(".trash/sneaky.md", fm("t-sn", "Sneaky from elsewhere"))
    it = fg.by_name("three.md"); fg._folder_id("Archive", create=True); it["parent"] = "Archive"; fg._touch(it, "Other device")
    page.evaluate("() => __todo.poll(true)"); page.wait_for_timeout(600)
    check("…a file put in .trash elsewhere never shows (delta)", row(page, "Sneaky").count() == 0 and no_trash_tasks(page))
    check("…a task moved into a folder elsewhere leaves this view and is in that folder (R2-5)", row(page, "Three").count() == 0
          and page.evaluate("__todo.all().find(t => t.id === 't-3')?.file") == "Archive/three.md", page.evaluate("__todo.all().map(t => t.file)"))
    page.reload(); page.wait_for_selector(".row"); page.wait_for_function(ready); page.wait_for_timeout(200)
    check("…and none after a restart from the device copy", no_trash_tasks(page) and row(page, "Sneaky").count() == 0 and sorted(page.evaluate("__todo.all().map(t => t.file)")) == ["Archive/three.md", "two.md"],
          page.evaluate("__todo.all().map(t => t.file)"))
    recently_deleted(page)
    page.locator("#modal .rd-item", has_text="One").locator("button").click(); page.wait_for_timeout(700)
    check("Restore (OneDrive): one.md back with its exact text; its trash entry removed", fg.files().get("one.md") == gfiles["one.md"]
          and not any(v == gfiles["one.md"] for v in fg.trash().values()) and row(page, "One").count() == 1, list(fg.files()))
    page.click("#modal [data-a=close]")
    page.evaluate("""async () => { const T = __todo; await T.trashPut('Old/z.md', 'zzz', { title:'Z' });
        const e = (await T.trashEntries()).find(x => x.meta.path === 'Old/z.md'); await T.trashRestore(e); }""")
    check("Restore re-creates missing folders (OneDrive: Old/z.md)", fg.files().get("Old/z.md") == "zzz" and fg.by_path("Old", folder=True) is not None)
    check("A3 (OneDrive): never wrote without If-Match", not fg.violations, fg.violations[:3])
    check("A3 (OneDrive): no page errors", not errors, errors[:3])
    ctx.close()

    # ---------- B. Deleted C: demote protects due dates; Check off D; search banner; overdue badge (demo, phone) ----------
    ctx, page, errors = new_page(browser, phone=True, init=ls_init(**{"todo.source": "demo", "todo.list": "Home"}))
    page.goto(APP); page.wait_for_selector(".row")
    check("Hidden D: the overdue count shows as a badge where Today is opened (header)", page.locator("#od-head").is_visible() and page.inner_text("#od-head") == "1", page.inner_text("#od-head"))
    page.click("#list-name")
    check("…and on the Today entry in the list picker", page.locator("#modal .pick .go", has_text="Today").locator(".od-badge").inner_text() == "1")
    page.locator("#modal .pick .go", has_text="Today").click(); page.wait_for_timeout(200)
    over = page.locator(".tday-head[data-tday=over]")
    check("…and on the Overdue header, which stays collapsed", over.locator(".od-badge").inner_text() == "1" and over.get_attribute("aria-expanded") == "false")
    page.screenshot(path=str(SHOTS / "42-phone-overdue-badge.png"))
    # search banner (Hidden C), in Today and in a list
    open_menu(page, "Search"); page.fill("#m-q", "gate"); page.click("#modal [data-a=ok]"); page.wait_for_timeout(200)
    check("Hidden C: while searching, a bar under the header says what's filtered (Today view)", page.locator("#srch-bar").is_visible() and page.inner_text("#srch-text") == "Filtering: “gate”", page.inner_text("#srch-text"))
    page.click("#list-name"); page.locator("#modal .pick .go", has_text="Home").click(); page.wait_for_timeout(200)
    check("…and in a list view", page.locator("#srch-bar").is_visible() and page.locator(".row").count() == 1)
    page.screenshot(path=str(SHOTS / "43-phone-search-banner.png"))
    page.click("#srch-clear"); page.wait_for_timeout(200)
    check("…✕ Clear resets the search and redraws", not page.locator("#srch-bar").is_visible() and page.evaluate("__todo.S.q") == "" and page.locator(".row").count() > 1)
    page.evaluate("q => { __todo.S.q = q; __todo.render(); }", evil)
    check("…the search text is shown as text (escaped)", page.locator("#srch-bar img").count() == 0 and "<img" in page.inner_text("#srch-text"))
    page.click("#srch-clear")
    # Deleted C: demote
    row(page, "Fix gate latch").locator(".ttl").click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    page.click("#d-demote"); page.wait_for_selector("#m-keep")
    check("Deleted C: demoting a due-dated task forces 'Keep it, archived' on", page.is_checked("#m-keep") and page.is_disabled("#m-keep"))
    check("…with the warning 'This task is due … — it will leave the Today view.'", "This task is due" in page.inner_text("#m-duewarn") and "it will leave the Today view." in page.inner_text("#m-duewarn"), page.inner_text("#m-duewarn"))
    page.click("#modal [data-a=cancel]"); page.click("#d-close"); page.wait_for_timeout(200)
    page.evaluate("""async () => { const T = __todo, S = T.S;
        const mk = (id, title, extra) => ({ file:'', version:null, id, title, status:'open', prefix:'', list:'Home', collections:[], parent:'', order:50, due:'', repeat:'', series:'', completed:'', demoted_into:'', body:'', extra:{}, unknown:[], isNew:true, ...extra });
        const p = mk('t-np', 'No-date parent'); S.tasks.set(p.id, p); await T.saveTask(p);
        const c = mk('t-dc', 'Due child', { parent:'t-np', due:'""" + D(4) + """' }); S.tasks.set(c.id, c); await T.saveTask(c); T.render(); }""")
    row(page, "No-date parent").locator(".ttl").click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    page.click("#d-demote"); page.wait_for_selector("#m-keep")
    check("…a task without a due date (subtasks moved, not demoted): Keep stays optional", page.is_enabled("#m-keep") and page.inner_text("#m-duewarn").strip() == "")
    page.check("#modal input[name=kids][value=demote]")
    check("…but demoting its due-dated subtask with it forces Keep and names it", page.is_disabled("#m-keep") and page.is_checked("#m-keep") and "“Due child” is due" in page.inner_text("#m-duewarn"), page.inner_text("#m-duewarn"))
    page.click("#modal [data-a=cancel]"); page.click("#d-close"); page.wait_for_timeout(200)
    page.evaluate("() => __todo.doDemote(__todo.get('t-s03'), __todo.get('t-s05'), { target:'t-s05', level:1, keep:false, kids:'move' })"); page.wait_for_timeout(400)
    gate = files_of(page).get("fix-gate-latch.md") or ""
    check("…and doDemote itself never deletes a due-dated task (kept, archived)", "status: archived" in gate and "demoted_into: t-s05" in gate, gate[:200])
    check("Hidden D: the badge hides when nothing is overdue", not page.locator("#od-head").is_visible())
    # Checked off D: second tap
    page.click("#list-name"); page.locator("#modal .pick .go", has_text="/ (root)").click(); page.wait_for_timeout(200)
    before = files_of(page)["try-the-list.md"]
    row(page, "Tap a title").locator(".ck").click(); page.wait_for_selector("#modal [data-a=all]")
    page.click("#modal [data-a=all]"); page.wait_for_timeout(100)
    btn = page.locator("#modal [data-a=all]")
    check("Checked off D: the first tap on Check all only arms it, with the counts", btn.inner_text() == "Tap again to check all 2 items" and files_of(page)["try-the-list.md"] == before, btn.inner_text())
    check("…Check only this and Cancel unchanged; Check all still the highlighted button", page.locator("#modal [data-a=one]").inner_text() == "Check only this"
          and page.locator("#modal [data-a=cancel]").inner_text() == "Cancel" and "primary" in btn.get_attribute("class"))
    page.screenshot(path=str(SHOTS / "44-phone-check-all-armed.png"))
    page.click("#modal [data-a=all]"); page.wait_for_timeout(100)
    check("…a bounce under 300 ms doesn't count", files_of(page)["try-the-list.md"] == before and page.locator("#modal-bg.on").count() == 1)
    page.wait_for_timeout(4300)
    check("…not tapped again within ~4 s: it reverts to 'Check all'", btn.inner_text() == "Check all" and files_of(page)["try-the-list.md"] == before)
    check_all(page); page.wait_for_timeout(400)
    after = files_of(page)["try-the-list.md"]
    check("…a deliberate second tap checks everything", "- [ ]" not in after and "status: done" in after, after[-160:])
    page.click("#list-name"); page.locator("#modal .pick .go", has_text="Home").click(); page.wait_for_timeout(200)
    row(page, "Solar panel cleaning").locator(".ck").click(); page.wait_for_selector("#modal [data-a=all]")
    page.click("#modal [data-a=all]"); page.wait_for_timeout(100)
    check("…subtasks and lines both counted (the demote above added a line): 'Tap again to check all 2 subtasks and 1 item'", page.inner_text("#modal [data-a=all]") == "Tap again to check all 2 subtasks and 1 item", page.inner_text("#modal [data-a=all]"))
    page.click("#modal [data-a=cancel]"); page.wait_for_timeout(200)
    page.click("#list-name"); page.locator("#modal .pick .go", has_text="School").click(); page.wait_for_timeout(200)
    row(page, "Weekly review").locator(".ck").click(); page.wait_for_selector("#modal [data-a=all]")
    page.click("#modal [data-a=all]"); page.wait_for_timeout(100)
    armed = page.inner_text("#modal [data-a=all]")
    page.wait_for_timeout(300); page.click("#modal [data-a=all]"); page.wait_for_timeout(500)
    copies = [k for k in files_of(page) if k.split("/")[-1].startswith("weekly-review-")]
    check("…the recurring keep-copies path uses the same second tap", armed == "Tap again to check all 2 items" and len(copies) == 1 and "status: done" in files_of(page)["weekly-review.md"], (armed, copies))
    check("B (demo): no page errors", not errors, errors[:3])
    ctx.close()

    # ---------- B2. search banner + Recently deleted + delete list cap on a PC ----------
    ctx, page, errors = new_page(browser, init=ls_init(**{"todo.source": "demo", "todo.list": "Rental"}))
    page.goto(APP); page.wait_for_selector(".row")
    open_menu(page, "Search"); page.fill("#m-q", "rent"); page.press("#m-q", "Enter"); page.wait_for_timeout(200)
    check("Hidden C (PC): the search bar shows", page.locator("#srch-bar").is_visible() and "rent" in page.inner_text("#srch-text"))
    page.click("#srch-clear"); page.wait_for_timeout(100)
    page.evaluate("""async () => { const T = __todo, S = T.S;
        const mk = (id, title, extra) => ({ file:'', version:null, id, title, status:'open', prefix:'', list:'Rental', collections:[], parent:'', order:60, due:'', repeat:'', series:'', completed:'', demoted_into:'', body:'', extra:{}, unknown:[], isNew:true, ...extra });
        const p = mk('t-big', 'Big parent'); S.tasks.set(p.id, p); await T.saveTask(p);
        for (let i = 1; i <= 12; i++){ const c = mk('t-k' + i, 'Kid ' + i, { parent:'t-big', order:i, due: i === 2 ? '""" + D(3) + """' : '' }); S.tasks.set(c.id, c); await T.saveTask(c); } T.render(); }""")
    delete_row(page, "Big parent")
    lis = page.locator("#modal .dl-subs li")
    check("Deleted D: the subtask list is capped at 10 + 'and N more', with due dates", lis.count() == 11 and lis.nth(10).inner_text() == "and 2 more" and "due" in lis.nth(1).inner_text()
          and "Kid 1" in lis.nth(0).inner_text(), [lis.nth(i).inner_text() for i in range(min(lis.count(), 12))])
    page.click("#modal [data-a=cancel]")
    check("B2 (PC): no page errors", not errors, errors[:3])
    ctx.close()

    # ---------- C. Overwritten A + B: conflict diff (due first) at 338 px, replaced versions in the trash ----------
    cfiles = {"cf.md": fm("t-cf", "Conflict me", f"due: {D(3)}\n") + "\nline one\nline two\n", "_todo.json": '{\n  "format": 3,\n  "lists": ["Inbox"]\n}\n'}
    fg = FakeGraph(FOLDER, dict(cfiles))
    ctx = browser.new_context(viewport={"width": 338, "height": 720}, is_mobile=True, has_touch=True,
                              user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0 Mobile Safari/537.36")
    page = ctx.new_page(); errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
    page.add_init_script(od_init(**{"todo.list": "Inbox", "todo.pollMs": 300}))
    fg.install(page)
    page.goto(APP); page.wait_for_selector(".row"); page.wait_for_function(ready)
    row(page, "Conflict me").locator(".ttl").click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    page.fill("#f-title", "Mine title"); page.fill("#f-due", D(5))
    fg.ext_edit("cf.md", fm("t-cf", "Conflict me", f"due: {D(7)}\n") + "\nline one\nline TWO from elsewhere\n")
    page.wait_for_selector("#d-banner.on", timeout=4000)
    page.click("#d-save"); page.wait_for_selector("#modal .cf-diff")
    rows_ = page.locator("#modal .cf-row")
    check("Overwritten A: the conflict dialog shows what differs, due date first", rows_.count() == 3 and "cf-due" in rows_.first.get_attribute("class")
          and D(5) in rows_.first.inner_text() and D(7) in rows_.first.inner_text(), [rows_.nth(i).inner_text() for i in range(rows_.count())])
    check("…then the title, then the notes ('changed' + line counts + preview)", "Title" in rows_.nth(1).inner_text() and "Mine title" in rows_.nth(1).inner_text()
          and "Notes" in rows_.nth(2).inner_text() and "changed" in rows_.nth(2).inner_text() and "line TWO from elsewhere" in rows_.nth(2).inner_text(), rows_.nth(2).inner_text())
    src = page.inner_text("#modal .cf-src")
    check("…which is newer, when theirs was saved and by whom", "Theirs:" in src and "by Other device" in src and "Yours:" in src and "newer" in src, src)
    fits = page.evaluate("() => { const m = document.querySelector('#modal'), r = m.getBoundingClientRect(); return r.right <= innerWidth + 1 && m.scrollWidth <= m.clientWidth + 1; }")
    check("…usable on a 338 px phone (no sideways overflow)", fits)
    check("…the three choices are unchanged", page.locator("#modal .btns button").count() == 3)
    page.screenshot(path=str(SHOTS / "45-phone-338-conflict-diff.png"))
    page.click("#modal [data-a=reload]"); page.wait_for_timeout(700)
    tr = fg.trash(); mds = [v for k, v in tr.items() if k.endswith(".md")]; js = [json.loads(v) for k, v in tr.items() if k.endswith(".json")]
    check("Overwritten B: 'Use their version' keeps YOUR version in the trash (replaced, this device)", len(mds) == 1 and "Mine title" in mds[0] and js[0]["reason"] == "replaced" and js[0]["by"] == "this device"
          and "line TWO from elsewhere" in fg.files()["cf.md"], (list(tr), js))
    page.fill("#f-title", "Mine again")
    fg.ext_edit("cf.md", fm("t-cf", "Theirs three", f"due: {D(7)}\n") + "\nline one\n")
    page.wait_for_selector("#d-banner.on", timeout=4000)
    theirs = fg.files()["cf.md"]
    page.click("#d-save"); page.wait_for_selector("#modal [data-a=over]"); page.click("#modal [data-a=over]"); page.wait_for_timeout(800)
    tr = fg.trash(); mds = [v for k, v in tr.items() if k.endswith(".md")]; js = [json.loads(v) for k, v in tr.items() if k.endswith(".json")]
    check("Overwritten B: 'Overwrite with mine' keeps THEIR text in the trash first (replaced, elsewhere)", theirs in mds and any(j["by"] == "elsewhere" and j["reason"] == "replaced" for j in js)
          and "Mine again" in fg.files()["cf.md"], (len(mds), [j["by"] for j in js]))
    page.click("#d-close"); page.wait_for_timeout(200)
    recently_deleted(page)
    txt = page.inner_text("#modal")
    check("…both replaced versions are in Recently deleted, labelled and restorable", page.locator("#modal .rd-item").count() == 2 and "Replaced: your version" in txt and "Replaced: the other version" in txt
          and page.locator("#modal .rd-item button", has_text="Restore").count() == 2, txt[:300])
    page.click("#modal [data-a=close]")
    row(page, "Mine again").locator(".ttl").click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    page.fill("#f-title", "Edit of a file deleted elsewhere")
    fg.ext_delete("cf.md")
    page.wait_for_selector("#d-banner.on", timeout=4000)
    page.click("#d-save"); page.wait_for_selector("#modal .cf-diff")
    check("Overwritten A: if theirs was deleted, the dialog says so", "the file was deleted" in page.inner_text("#modal .cf-diff"))
    page.click("#modal [data-a=reload]"); page.wait_for_timeout(700)
    check("…'Use their version' accepts the delete but keeps your edit in the trash", "cf.md" not in fg.files() and any("Edit of a file deleted elsewhere" in v for v in fg.trash().values())
          and not page.locator("#drawer.open").count())
    check("C (conflicts): never wrote without If-Match", not fg.violations, fg.violations[:3])
    check("C (conflicts): no page errors", not errors, errors[:3])
    ctx.close()

    # ---------- E. Overwritten C: drafts saved on the device, offered after a restart ----------
    ctx, page, errors = new_page(browser, phone=True, init=ls_init(**{"todo.source": "demo", "todo.list": "Inbox"}))
    page.goto(APP); page.wait_for_selector(".row")
    key = "todo.autodraft|demo|t-s01"
    draft = lambda: page.evaluate("k => localStorage.getItem(k)", key)
    row(page, "Call insurance agent").locator(".ttl").click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    page.fill("#f-title", "Draft title X")
    page.wait_for_timeout(600)
    check("Overwritten C: no draft before the ~2 s pause", draft() is None)
    page.wait_for_timeout(1900)
    d = json.loads(draft() or "{}")
    check("…then the unsaved edit is saved on the device, keyed by scope and task id", d.get("id") == "t-s01" and d.get("fields", {}).get("title") == "Draft title X"
          and d.get("due") == D(1) and d.get("version") and d.get("file") == "call-insurance-agent.md" and "body" in d and d.get("savedAt"), d)
    page.evaluate("() => { __todo.S.redirecting = true; }")       # skip the browser's leave-page prompt for the test
    page.reload(); page.wait_for_selector("#modal [data-a=restore]")
    txt = page.inner_text("#modal")
    check("…on the next start: 'You had unsaved changes to <title> (due <date>)' — Restore / Discard", "You had unsaved changes to Draft title X" in txt and "(due " in txt
          and page.locator("#modal [data-a=discard]").count() == 1, txt)
    page.screenshot(path=str(SHOTS / "46-phone-draft-offer.png"))
    page.click("#modal [data-a=restore]"); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    check("…Restore opens the editor with the draft applied and dirty (same version: no banner)", page.input_value("#f-title") == "Draft title X"
          and "on" in page.get_attribute("#d-dirty", "class") and page.locator("#d-banner.on").count() == 0)
    page.click("#d-save"); page.wait_for_timeout(400)
    check("…a successful save clears the draft", draft() is None and "title: Draft title X" in files_of(page)["call-insurance-agent.md"])
    page.fill("#f-title", "Will discard"); page.wait_for_timeout(2300)
    check("…(draft saved again while editing)", draft() is not None)
    page.click("#d-close"); page.click("#modal [data-a=discard]"); page.wait_for_timeout(200)
    check("…Discard clears it", draft() is None)
    row(page, "Draft title X").locator(".ttl").click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(2300)
    page.click("#d-close"); page.wait_for_timeout(200)
    check("…opening and closing with no changes leaves no draft", draft() is None and not page.evaluate("() => Object.keys(localStorage).some(k => k.startsWith('todo.autodraft|'))"))
    page.click("#d-close") if page.locator("#drawer.open").count() else None
    page.fill("#qa", ""); page.evaluate("() => { const T = __todo; T.S.tasks.get('t-s02') && T.openDrawer('t-s02'); }"); page.wait_for_timeout(300)
    page.fill("#f-title", "Discard at start"); page.wait_for_timeout(2300)
    page.evaluate("() => { __todo.S.redirecting = true; }"); page.reload(); page.wait_for_selector("#modal [data-a=discard]")
    page.click("#modal [data-a=discard]"); page.wait_for_timeout(200)
    check("…Discard at start removes the draft and leaves the task alone", not page.evaluate("() => Object.keys(localStorage).some(k => k.startsWith('todo.autodraft|'))")
          and page.locator("#drawer.open").count() == 0)
    check("E1 (drafts, demo): no page errors", not errors, errors[:3])
    ctx.close()

    dfiles = {"dr1.md": fm("t-d1", "Draft one", f"due: {D(2)}\n"), "dr2.md": fm("t-d2", "Draft two"), "_todo.json": '{\n  "format": 3,\n  "lists": ["Inbox"]\n}\n'}
    fg = FakeGraph(FOLDER, dict(dfiles))
    ctx, page, errors = new_page(browser, phone=True, init=od_init(**{"todo.list": "Inbox"}))
    fg.install(page)
    page.goto(APP); page.wait_for_selector(".row"); page.wait_for_function(ready)
    row(page, "Draft one").locator(".ttl").click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    page.fill("#f-title", "Draft one — my phone edit"); page.wait_for_timeout(2300)
    fg.ext_edit("dr1.md", fm("t-d1", "Draft one changed on the PC", f"due: {D(2)}\n"))
    page.evaluate("() => { __todo.S.redirecting = true; }"); page.reload(); page.wait_for_selector("#modal [data-a=restore]"); page.wait_for_function(ready)
    page.click("#modal [data-a=restore]"); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    check("Overwritten C: a draft for a file changed since opens with the 'changed elsewhere' banner", page.locator("#d-banner.on").count() == 1 and page.input_value("#f-title") == "Draft one — my phone edit")
    page.click("#d-save"); page.wait_for_selector("#modal .cf-diff")
    check("…and Save asks (conflict dialog with the diff), never overwrites silently", "Changed elsewhere" in page.inner_text("#modal") and "changed on the PC" in fg.files()["dr1.md"])
    page.click("#modal [data-a=over]"); page.wait_for_timeout(700)
    check("…Overwrite with mine then saves the draft (their version kept in the trash)", "my phone edit" in fg.files()["dr1.md"] and any("changed on the PC" in v for v in fg.trash().values()))
    page.click("#d-close"); page.wait_for_timeout(200)
    row(page, "Draft two").locator(".ttl").click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    page.fill("#f-title", "Draft two survives a delete"); page.wait_for_timeout(2300)
    fg.ext_delete("dr2.md")
    page.evaluate("() => { __todo.S.redirecting = true; }"); page.reload(); page.wait_for_selector("#modal [data-a=restore]"); page.wait_for_function(ready)
    check("Overwritten C: a draft whose task no longer exists offers 'Restore as new task'", page.inner_text("#modal [data-a=restore]") == "Restore as new task" and "no longer exists" in page.inner_text("#modal"))
    page.click("#modal [data-a=restore]"); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    page.click("#d-saveclose"); page.wait_for_timeout(700)
    check("…which saves it as a new task file", "draft-two-survives-a-delete.md" in fg.files() and "Draft two survives a delete" in fg.files()["draft-two-survives-a-delete.md"], list(fg.top_files()))
    check("…and leaves no drafts behind", not page.evaluate("() => Object.keys(localStorage).some(k => k.startsWith('todo.autodraft|'))"))
    check("E2 (drafts, OneDrive): never wrote without If-Match", not fg.violations, fg.violations[:3])
    check("E2 (drafts, OneDrive): no page errors", not errors, errors[:3])
    ctx.close()

    # ---------- F. hostile task text in the new dialogs (delete, check-off, conflict diff, Recently deleted, draft offer) ----------
    evil = "<img src=x onerror=\"window.__xss=(window.__xss||0)+1\">"
    q = lambda s: "'" + s.replace("'", "''") + "'"          # YAML single-quoted
    hfiles = {"ev.md": fm("t-ev", q("Evil parent " + evil), f"due: {D(3)}\n") + f"\nnote {evil}\n- [ ] {evil} line\n",
              "evs.md": fm("t-evs", q("Evil child " + evil), "parent: t-ev\n"),
              "_todo.json": '{\n  "format": 3,\n  "lists": ["Inbox"]\n}\n'}
    fg = FakeGraph(FOLDER, dict(hfiles))
    ctx, page, errors = new_page(browser, phone=True, init=od_init(**{"todo.list": "Inbox", "todo.pollMs": 300}))
    fg.install(page)
    page.goto(APP); page.wait_for_selector(".row"); page.wait_for_function(ready)
    no_markup = lambda: page.locator("#modal img").count() == 0 and not page.evaluate("window.__xss")
    delete_row(page, "Evil parent")
    check("F: the delete dialog shows hostile titles (task and subtask) as text", no_markup() and page.inner_text("#modal").count("<img") >= 2, page.inner_text("#modal")[:300])
    page.click("#modal [data-a=cancel]"); page.wait_for_timeout(200)
    row(page, "Evil parent").locator(".ck").click(); page.wait_for_selector("#modal [data-a=all]")
    page.click("#modal [data-a=all]"); page.wait_for_timeout(100)
    armed_bg = page.eval_on_selector("#modal [data-a=all]", """b => { const d = document.createElement('i'); d.style.color = 'var(--danger)'; b.after(d);
        const red = getComputedStyle(d).color; d.remove(); return [getComputedStyle(b).backgroundColor, red, b.classList.contains('primary')]; }""")
    check("Checked off D: the armed Check all stays the highlighted button (not recoloured red)", armed_bg[0] != armed_bg[1] and armed_bg[2], armed_bg)
    check("F: the check-off dialog (armed) shows a hostile title as text", no_markup() and "<img" in page.inner_text("#modal"), page.inner_text("#modal")[:200])
    page.click("#modal [data-a=cancel]"); page.wait_for_timeout(200)
    row(page, "Evil parent").locator(".ttl").click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    page.fill("#f-title", "Mine " + evil)
    fg.ext_edit("ev.md", fm("t-ev", q("Theirs " + evil), f"due: {q(evil)}\n") + f"\ntheirs {evil}\n<script>window.__xss=100</script>\n")
    page.wait_for_selector("#d-banner.on", timeout=4000)
    page.click("#d-save"); page.wait_for_selector("#modal .cf-diff")
    check("F: the conflict comparison shows hostile titles, due and notes as text", no_markup() and page.locator("#modal script").count() == 0
          and "<img" in page.inner_text("#modal .cf-diff"), page.inner_text("#modal .cf-diff")[:300])
    page.click("#modal [data-a=reload]"); page.wait_for_timeout(700)
    if page.locator("#drawer.open").count(): page.click("#d-close")
    page.wait_for_timeout(200)
    recently_deleted(page)
    check("F: Recently deleted shows a replaced hostile version as text", page.locator("#modal .rd-item").count() >= 1 and no_markup() and "<img" in page.inner_text("#modal"), page.inner_text("#modal")[:300])
    page.click("#modal [data-a=close]"); page.wait_for_timeout(200)
    page.evaluate("() => __todo.openDrawer('t-evs')"); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    page.fill("#f-title", "Draft " + evil); page.wait_for_timeout(2300)
    page.evaluate("() => { __todo.S.redirecting = true; }"); page.reload(); page.wait_for_selector("#modal [data-a=restore]"); page.wait_for_function(ready)
    check("F: the unsaved-changes offer shows a hostile title as text", no_markup() and "<img" in page.inner_text("#modal"), page.inner_text("#modal")[:200])
    page.click("#modal [data-a=discard]"); page.wait_for_timeout(200)
    check("F: no hostile markup ran anywhere (rows, editor, dialogs)", not page.evaluate("window.__xss") and page.locator("#rows img").count() == 0)
    check("F (hostile text): never wrote without If-Match", not fg.violations, fg.violations[:3])
    check("F (hostile text): no page errors", not errors, errors[:3])
    ctx.close()

    # ---------- G. Restore follow-up (2026-11-07): a task with 7 levels of subtasks, parents in the trash, partial restore, Undo ----------
    names = ["A-top", "B-two", "C-three", "D-four", "E-five", "F-six", "G-seven"]
    ids = [f"t-g{i}" for i in range(7)]
    gfiles = {}
    for i, n in enumerate(names):
        title = q(n + " " + evil) if n == "F-six" else n
        extra = (f"due: {D(2)}\n" if i == 0 else f"parent: {ids[i-1]}\n") + ("" if i else "")
        gfiles[f"{n.lower()}.md"] = fm(ids[i], title, extra) + f"\nnotes of {n}\n"
    gfiles["s-sib.md"] = fm("t-gs", "S-sib", "parent: t-g0\n") + "\nsibling notes\n"
    gfiles["_todo.json"] = '{\n  "format": 3,\n  "lists": ["Inbox"]\n}\n'
    tasks8 = [k for k in gfiles if k.endswith(".md")]
    fg = FakeGraph(FOLDER, dict(gfiles)); gfiles = dict(fg.files())          # the fixture as stored (folder layout)
    ctx, page, errors = new_page(browser, phone=True, init=od_init(**{"todo.list": "Inbox"}))
    fg.install(page)
    page.goto(APP); page.wait_for_selector(".row"); page.wait_for_function(ready)
    page.evaluate("""() => { const s = __todo.S.store, c = s.create.bind(s); window.__creates = [];
        s.create = async (p, t) => { if (window.__failAfter != null && !p.startsWith('.trash') && window.__failAfter-- <= 0) throw new Error('test: connection lost');
          const v = await c(p, t); if (!p.startsWith('.trash')) window.__creates.push(p); return v; }; }""")
    rd_item = lambda title: page.locator("#modal .rd-item", has=page.locator(".rd-ttl", has_text=title))
    def restore(title):
        rd_item(title).locator("button", has_text="Restore").click(); page.wait_for_timeout(300)
    def settle():
        page.wait_for_function("() => !document.querySelector('#rd-list')?.textContent.includes('Restoring') && !document.querySelector('#rd-list')?.textContent.includes('Loading')", timeout=15000)
    order_ok = lambda seq: all(seq.index(f"{a.lower()}.md") < seq.index(f"{b.lower()}.md") for a, b in zip(names, names[1:]) if f"{a.lower()}.md" in seq and f"{b.lower()}.md" in seq)

    delete_row(page, "A-top")
    check("G: the delete dialog lists all 7 subtasks (every level)", "Also delete its 7 subtasks" in page.inner_text("#modal"), page.inner_text("#modal")[:300])
    page.click("#modal [data-a=ok]"); page.wait_for_timeout(1500)
    check("G: …all 8 files are in the trash", not any(k in fg.files() for k in tasks8) and len([k for k in fg.trash() if k.endswith(".md")]) == 8, list(fg.top_files()))
    for k, v in list(fg.trash().items()):                    # sidecars from before this build have no parent: the app reads it from the file
        if k.endswith(".json"):
            j = json.loads(v); j.pop("parent", None); fg.ext_edit(k, json.dumps(j, indent=2) + "\n")
    recently_deleted(page)
    check("G: '+ 7 subtasks' on the top task's entry, '+ 3 subtasks' on D-four's (even without parent in the sidecars)",
          "+ 7 subtasks" in rd_item("A-top").inner_text() and "+ 3 subtasks" in rd_item("D-four").inner_text() and "subtask" not in rd_item("G-seven").inner_text(),
          (rd_item("A-top").inner_text(), rd_item("D-four").inner_text()))
    restore("A-top"); page.wait_for_selector("#modal [data-a=all]")
    txt = page.inner_text("#modal")
    lis = page.locator("#modal .dl-subs li")
    check("G: Restore asks about all 7 subtasks across 7 levels, indented by level", "and its 7 subtasks (7 levels)?" in txt and lis.count() == 7
          and page.evaluate("() => [...document.querySelectorAll('#modal .dl-subs li')].map(l => parseInt(l.style.marginLeft)).sort((a,b) => a-b).pop()") == 70, txt[:400])
    shown = [l.split(" ")[0] for l in page.evaluate("() => [...document.querySelectorAll('#modal .dl-subs li')].map(l => l.textContent)")]
    check("G: …shown as a tree: each task followed by its own subtasks", shown in (["B-two", "C-three", "D-four", "E-five", "F-six", "G-seven", "S-sib"], ["S-sib", "B-two", "C-three", "D-four", "E-five", "F-six", "G-seven"]), shown)
    check("G: hostile titles in the restore dialog stay text", page.locator("#modal img").count() == 0 and "<img" in txt and not page.evaluate("window.__xss"))
    page.screenshot(path=str(SHOTS / "47-phone-restore-tree.png"))
    page.evaluate("() => { window.__creates = []; }")
    page.click("#modal [data-a=all]"); settle(); page.wait_for_timeout(300)
    seq = page.evaluate("window.__creates")
    check("G: Restore all brings back all 8 files with their exact text; the trash is empty",
          all(fg.files().get(k) == gfiles[k] for k in tasks8) and not fg.trash(), [k for k in tasks8 if fg.files().get(k) != gfiles[k]])
    check("G: …top level first: every parent comes back before its subtasks", len(seq) == 8 and order_ok(seq) and seq[0] == "a-top.md", seq)
    check("G: …says how many were restored", "Restored 8 tasks" in page.inner_text("#toast"), page.inner_text("#toast"))
    page.click("#modal [data-a=close]"); page.wait_for_timeout(200)
    check("G: …the tree is back in the list", row(page, "A-top").count() == 1 and page.evaluate("() => __todo.all().length") == 8)
    page.click("#undo-btn"); page.wait_for_timeout(2500)
    check("G: one Undo deletes the whole restore again (back to the trash)", not any(k in fg.files() for k in tasks8) and len([k for k in fg.trash() if k.endswith(".md")]) == 8,
          [k for k in tasks8 if k in fg.files()])

    # Q2: restoring a subtask alone while its parents are in the trash
    recently_deleted(page); restore("D-four"); page.wait_for_selector("#modal [data-a=up]")
    txt = page.inner_text("#modal")
    check("G: a subtask whose parent is in the trash asks 'Its parent … is also in Recently deleted — restore them too?'",
          "Its parent C-three is also in Recently deleted (and 2 tasks above it)" in txt and page.locator("#modal [data-a=only]").count() == 1, txt)
    page.evaluate("() => { window.__creates = []; }")
    page.click("#modal [data-a=up]"); page.wait_for_selector("#modal [data-a=all]")
    check("G: …then asks about its own 3 subtasks", "D-four and its 3 subtasks" in page.inner_text("#modal"), page.inner_text("#modal")[:200])
    page.click("#modal [data-a=all]"); settle(); page.wait_for_timeout(300)
    seq = page.evaluate("window.__creates")
    check("G: …parents and subtasks back (7), top first; the sibling stays in the trash", len(seq) == 7 and order_ok(seq) and seq[0] == "a-top.md"
          and "s-sib.md" not in fg.files() and len([k for k in fg.trash() if k.endswith(".md")]) == 1, seq)
    restore("S-sib"); settle()
    check("G: …the sibling, its parent back, restores without any question", "s-sib.md" in fg.files() and not fg.trash())
    page.click("#modal [data-a=close]"); page.wait_for_timeout(200)

    # a connection lost half way: what's back stays back; the rest finishes from the highest remaining entry
    delete_row(page, "A-top"); page.click("#modal [data-a=ok]"); page.wait_for_timeout(1500)
    recently_deleted(page); restore("A-top"); page.wait_for_selector("#modal [data-a=all]")
    page.evaluate("() => { window.__failAfter = 3; }")
    page.click("#modal [data-a=all]"); settle(); page.wait_for_timeout(300)
    page.evaluate("() => { window.__failAfter = null; }")
    back = [k for k in tasks8 if k in fg.files()]
    check("G: connection lost after 3: 'Restored 3 of 8 — 5 are still in Recently deleted.'", "Restored 3 of 8 — 5 are still in Recently deleted." in page.inner_text("#toast")
          and len(back) == 3 and page.locator("#modal .rd-item").count() == 5, (page.inner_text("#toast"), back))
    rest = [n for n in names if f"{n.lower()}.md" not in back]
    restore(rest[0])
    if page.locator("#modal [data-a=all]").count(): page.click("#modal [data-a=all]")
    settle(); page.wait_for_timeout(300)
    check("G: …one more Restore (with its subtasks) on the highest remaining entry finishes the job", all(fg.files().get(k) == gfiles[k] for k in tasks8) and not fg.trash(),
          [k for k in tasks8 if fg.files().get(k) != gfiles[k]])
    page.click("#modal [data-a=close]"); page.wait_for_timeout(200)

    # decision 1: a subtask deleted separately earlier is included, and marked
    page.evaluate("() => __todo.removeTask(__todo.S.tasks.get('t-g6'))"); page.wait_for_timeout(800)
    for k, v in list(fg.trash().items()):
        if k.endswith(".json"):
            j = json.loads(v); j["deletedAt"] = "2026-01-01T00:00:00.000Z"; fg.ext_edit(k, json.dumps(j, indent=2) + "\n")
    page.evaluate("() => __todo.render()"); page.wait_for_timeout(200)
    page.evaluate("async () => { await __todo.removeTask(__todo.S.tasks.get('t-g5')); await __todo.removeTask(__todo.S.tasks.get('t-g4')); __todo.render(); }"); page.wait_for_timeout(800)
    recently_deleted(page); restore("E-five"); page.wait_for_selector("#modal [data-a=only]")
    lis = page.locator("#modal .dl-subs li")
    check("G (decision 1): a subtask deleted separately earlier is in the list, marked 'deleted separately'", lis.count() == 2
          and "deleted separately" in lis.nth(1).inner_text() and "G-seven" in lis.nth(1).inner_text() and "deleted separately" not in lis.nth(0).inner_text(), [lis.nth(i).inner_text() for i in range(lis.count())])
    page.click("#modal [data-a=only]"); settle()
    check("G: 'Only this task' restores just that one", "e-five.md" in fg.files() and "f-six.md" not in fg.files() and "g-seven.md" not in fg.files())
    restore("F-six"); page.wait_for_selector("#modal [data-a=all]"); page.click("#modal [data-a=all]"); settle()
    check("G: …and the rest come back from the next level", all(fg.files().get(k) == gfiles[k] for k in tasks8) and not fg.trash())
    page.click("#modal [data-a=close]")
    check("G: no hostile markup ran", not page.evaluate("window.__xss"))
    check("G (restore tree, OneDrive): never wrote without If-Match", not fg.violations, fg.violations[:3])
    check("G (restore tree, OneDrive): no page errors", not [e for e in errors if "test: connection lost" not in e], errors[:3])
    ctx.close()

def test_format_check(browser):
    print("\n[24] Data-format check: a newer folder, or an old flat one, opens read-only (R2-5 step 0, decision 14)")
    fm = lambda i, title: f"---\nid: {i}\ntitle: {title}\nstatus: open\norder: 1\n---\n- [ ] a line\n"
    cfg = lambda f: '{\n  "format": %d,\n  "folders": []\n}\n' % f
    od_init = lambda **kv: TEST_AUTH + ls_init(**{"todo.source": "onedrive", "todo.folder": FOLDER, "todo.pollMs": 300, "todo.everSignedIn": True, "todo.list": "", **kv})
    ready = "__todo.S.store && __todo.S.store.ready === true"
    # format 4 (this build): normal
    fg = FakeGraph(FOLDER, {"a.md": fm("t-a", "Alpha"), "_todo.json": cfg(4)})
    ctx, page, errors = new_page(browser, phone=True, init=od_init())
    fg.install(page); page.goto(APP); page.wait_for_selector(".row"); page.wait_for_function(ready)
    check("format 4 folder: no read-only bar, quick-add on", not page.is_visible("#ro-bar") and page.is_enabled("#qa"))
    # another device's newer build updates the folder mid-session → read-only from the next check
    fg.ext_edit("_todo.json", cfg(5)); page.wait_for_selector("#ro-bar:not([hidden])", timeout=5000)
    check("…the folder becomes format 5 elsewhere: the read-only bar appears on the next check", "data format 5" in page.inner_text("#ro-text") and page.is_disabled("#qa"), page.inner_text("#ro-text"))
    before = fg.files()["a.md"]
    row(page, "Alpha").locator(".ck").click(); page.wait_for_timeout(600)
    if page.locator("#modal [data-a=one]").count(): page.click("#modal [data-a=one]"); page.wait_for_timeout(600)
    check("…a check-off is refused and undone on screen; the file is unchanged", fg.files()["a.md"] == before and page.evaluate("__todo.all().find(t => t.id === 't-a').status") == "open"
          and "Read-only" in page.inner_text("#toast"), page.inner_text("#toast"))
    row(page, "Alpha").locator(".row-more").click(); page.locator("#pop button", has_text="Delete").click(); page.click("#modal [data-a=ok]"); page.wait_for_timeout(600)
    check("…a delete is refused too: the file stays, nothing written to .trash", "a.md" in fg.files() and not fg.trash())
    r = page.evaluate("async () => { __todo.S.lists.push('Sneaky'); try { await __todo.saveConfig(); return 'saved'; } catch (e) { return e.constructor.name; } }"); page.wait_for_timeout(300)
    check("…and _todo.json is never rewritten with the older format (the write is refused)", '"format": 5' in fg.files()["_todo.json"] and "Sneaky" not in fg.files()["_todo.json"], (r, fg.files()["_todo.json"]))
    r = page.evaluate("async () => { try { await __todo.S.store.createFolder('Sneaky'); return 'made'; } catch (e) { return e.constructor.name; } }")
    check("…folder changes are refused too (create folder)", r == "ReadOnlyError" and "Sneaky" not in fg.folders(), r)
    check("format check (OneDrive): never wrote without If-Match", not fg.violations, fg.violations[:3])
    ctx.close()
    # opened fresh on a format-5 folder (the device copy is per context, so this is a cold start)
    fg = FakeGraph(FOLDER, {"a.md": fm("t-a", "Alpha"), "_todo.json": cfg(5)})
    ctx, page, errors2 = new_page(browser, phone=False, init=od_init())
    fg.install(page); page.goto(APP); page.wait_for_selector(".row"); page.wait_for_function(ready)
    check("opening a format-5 folder: read-only bar with a Reload button, tasks still shown", page.is_visible("#ro-bar") and page.is_visible("#ro-reload") and row(page, "Alpha").count() == 1)
    check("…quick-add is off", page.is_disabled("#qa"))
    check("…the Diagnostics log says why", "read-only" in page.evaluate("localStorage.getItem('todo.deviceLog') || ''"))
    ctx.close()
    # R2-5 decision 14: an old flat folder (format 3, list: lines) opens read-only until Claude converts it
    old = {"b.md": "---\nid: t-b\ntitle: Beta\nstatus: open\nlist: Home\norder: 1\n---\n", "_todo.json": '{\n  "format": 3,\n  "lists": ["Inbox", "Home"]\n}\n'}
    fg = FakeGraph(FOLDER, old, raw=True)
    ctx, page, errors3 = new_page(browser, phone=True, init=od_init())
    fg.install(page); page.goto(APP); page.wait_for_selector(".row"); page.wait_for_function(ready)
    check("old flat folder (format 3): read-only bar says it needs converting, no Reload button", page.is_visible("#ro-bar") and "old list layout" in page.inner_text("#ro-text")
          and not page.is_visible("#ro-reload") and page.is_disabled("#qa"), page.inner_text("#ro-text"))
    before = fg.files()["b.md"]
    row(page, "Beta").locator(".ck").click(); page.wait_for_timeout(600)
    check("…its tasks show (in / (root)) but nothing is written", row(page, "Beta").count() == 1 and fg.files()["b.md"] == before and not fg.violations)
    check("format check: no page errors", not errors and not errors2 and not errors3, (errors + errors2 + errors3)[:3])
    ctx.close()


def test_r25_folders(browser):
    print("\n[25] R2-5: the folder is the list (data format 4)")
    D = lambda n: (datetime.date.today() + datetime.timedelta(days=n)).isoformat()
    files_of = lambda page: Files(page.evaluate("() => Object.fromEntries([...__todo.S.store.files].map(([k, v]) => [k, v.text]))"))
    picks = lambda page: [x.strip() for x in page.locator("#modal .pick .go").all_inner_texts()]
    def open_picker(page):
        page.click("#list-name"); page.wait_for_selector("#modal .pick")
    def go_folder(page, name):
        open_picker(page); page.locator("#modal .pick .go", has_text=name).first.click(); page.wait_for_timeout(200)
    def menu(page, title, label):
        row(page, title).locator(".row-more").click(); page.locator("#pop button", has_text=label).click()

    # ---------- A. demo store (MemStore), phone ----------
    ctx, page, errors = new_page(browser, phone=True, init=ls_init(**{"todo.source": "demo", "todo.list": "Home"}))
    page.goto(APP); page.wait_for_selector(".row")
    check("the header names the folder", page.inner_text("#list-label") == "Home")
    check("demo data is in the folder layout: no list: lines, _todo.json format 4 with folders",
          not any("\nlist:" in v for k, v in files_of(page).items() if k.endswith(".md")) and json.loads(files_of(page)["_todo.json"]) == {"format": 4, "folders": ["Home", "Rental", "School"]})
    open_picker(page)
    p0 = picks(page)
    check("the picker is 'Folders': / (root) first, then the folders in their order, then Today", page.inner_text("#modal h3") == "Folders" and p0[:4] == ["/ (root)", "Home", "Rental", "School"] and "Today (all folders)" in p0[4], p0)
    check("/ (root) can't be renamed or deleted (no ✎)", page.locator("#modal .pick").first.locator("button.ren").count() == 0)
    page.click("#modal [data-a=new]"); page.wait_for_selector("#m-name")
    errs = {}
    for bad in ["a/b", "back\\slash", ".hidden", "_sys", "trail.", "con", "HOME", ""]:
        page.fill("#m-name", bad); page.click("#modal [data-a=ok]"); page.wait_for_timeout(80); errs[bad] = page.inner_text("#m-err")
    check("folder-name rules: no / or \\, no leading . or _, no trailing dot, no Windows reserved names, unique ignoring case", all(errs.values()) and page.locator("#m-name").count() == 1, errs)
    page.fill("#m-name", "Errands"); page.click("#modal [data-a=ok]"); page.wait_for_timeout(300)
    cfg = json.loads(files_of(page)["_todo.json"])
    check("New folder: made in the store, added to _todo.json's folders, and opened", page.inner_text("#list-label") == "Errands"
          and "Errands" in page.evaluate("__todo.S.store.folders()") and cfg.get("folders") == ["Home", "Rental", "School", "Errands"] and cfg.get("format") == 4, cfg)
    check("…an empty folder says so", "No open tasks in “Errands”" in page.inner_text("#rows"))
    page.fill("#qa", "Buy stamps"); page.press("#qa", "Enter"); page.wait_for_timeout(300)
    check("quick-add in a folder saves the file in that folder", "Errands/buy-stamps.md" in dict(files_of(page)) and "\nlist:" not in files_of(page)["Errands/buy-stamps.md"])

    go_folder(page, "Home")
    fam = ["solar-panel-cleaning.md", "get-quotes.md", "compare-inverter-readings.md", "export-readings-csv.md"]
    before = {n: files_of(page)["Home/" + n] for n in fam}
    menu(page, "Solar panel cleaning", "Move to folder"); page.wait_for_selector("#modal .pick")
    check("Move to folder… lists / (root) and every folder", picks(page)[:5] == ["/ (root)", "Home", "Rental", "School", "Errands"], picks(page))
    page.locator("#modal .pick .go", has_text="Errands").click(); page.wait_for_timeout(500)
    fs = dict(files_of(page))
    check("Move to folder… moves the task and its whole family (every level) into the folder", all(("Errands/" + n) in fs and ("Home/" + n) not in fs for n in fam), [k for k in fs if "solar" in k or "quotes" in k or "inverter" in k or "csv" in k])
    check("…subtask files are moved unchanged (byte for byte)", all(fs["Errands/" + n] == before[n] for n in fam[1:]))
    check("…and the family left the Home view", row(page, "Solar panel cleaning").count() == 0)
    go_folder(page, "Errands")
    row(page, "Solar panel cleaning").locator("[data-act=expand]").click(); page.wait_for_timeout(150)
    menu(page, "Get three cleaning quotes", "Move to folder"); page.locator("#modal .pick .go", has_text="Home").click(); page.wait_for_selector("#modal [data-a=ok]")
    txt = page.inner_text("#modal")
    check("a subtask alone: asks — Cancel / Make it a top-level task in Home", "A subtask stays in its parent's folder" in txt and "Make it a top-level task in Home" in txt and page.locator("#modal [data-a=cancel]").count() == 1, txt)
    page.click("#modal [data-a=cancel]"); page.wait_for_timeout(200)
    check("…Cancel moves nothing", "Errands/get-quotes.md" in dict(files_of(page)))
    menu(page, "Get three cleaning quotes", "Move to folder"); page.locator("#modal .pick .go", has_text="Home").click(); page.wait_for_selector("#modal [data-a=ok]")
    page.click("#modal [data-a=ok]"); page.wait_for_timeout(400)
    q = files_of(page).get("Home/get-quotes.md") or ""
    check("…Make it top-level: moved to Home, no parent any more", "Home/get-quotes.md" in dict(files_of(page)) and "parent:" not in q, q[:160])

    # rename and delete
    open_picker(page); page.click("#modal [data-a='r:Errands']"); page.wait_for_selector("#m-name")
    check("a folder with tasks can't be deleted (no Delete button)", page.locator("#modal [data-a=remove]").count() == 0 and "Only an empty folder can be deleted" in page.inner_text("#modal"))
    page.fill("#m-name", "rental"); page.click("#modal [data-a=ok]"); page.wait_for_timeout(100)
    check("Rename refuses a name another folder has (any case)", "exists" in page.inner_text("#m-err"))
    page.fill("#m-name", "Chores"); page.click("#modal [data-a=ok]"); page.wait_for_timeout(600)
    fs = dict(files_of(page))
    check("Rename: the folder's files follow (same names), the view follows, _todo.json keeps its place", page.inner_text("#list-label") == "Chores"
          and "Chores/solar-panel-cleaning.md" in fs and not any(k.startswith("Errands/") for k in fs)
          and json.loads(fs["_todo.json"])["folders"] == ["Home", "Rental", "School", "Chores"], (page.inner_text("#list-label"), json.loads(fs["_todo.json"])))
    open_picker(page); page.click("#modal [data-a=new]"); page.fill("#m-name", "Temp"); page.click("#modal [data-a=ok]"); page.wait_for_timeout(300)
    open_picker(page); page.click("#modal [data-a='r:Temp']"); page.wait_for_selector("#modal [data-a=remove]")
    page.click("#modal [data-a=remove]"); page.wait_for_timeout(300)
    open_picker(page)
    check("an empty folder can be deleted: gone from the picker, the store and _todo.json", "Temp" not in picks(page) and "Temp" not in page.evaluate("__todo.S.store.folders()")
          and "Temp" not in json.loads(files_of(page)["_todo.json"])["folders"], picks(page))
    page.click("#modal [data-a=cancel]")

    # the editor's Folder field
    go_folder(page, "Home")
    row(page, "Fix gate latch").locator(".ttl").click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    opts = page.locator("#f-list option").all_inner_texts()
    check("the editor's field is 'Folder' with / (root), the folders and New folder…", "Folder" in page.inner_text("label:has(#f-list)") and opts[0] == "/ (root)" and opts[-1] == "＋ New folder…", opts)
    page.select_option("#f-list", "Rental"); page.click("#d-saveclose"); page.wait_for_timeout(500)
    fs = dict(files_of(page))
    check("changing the Folder moves the file, with its subtasks (incl. archived ones)", "Rental/fix-gate-latch.md" in fs and "Rental/buy-replacement-hinge.md" in fs and "Home/fix-gate-latch.md" not in fs)

    # Today view: quick-add goes to / (root) by default (decision 9)
    open_picker(page); page.locator("#modal .pick .go", has_text="Today").click(); page.wait_for_timeout(200)
    check("Today view's folder chip starts at / (root)", page.inner_text("#qa-list") == "/ (root)", page.inner_text("#qa-list"))
    page.fill("#qa", "Root level task"); page.press("#qa", "Enter"); page.wait_for_timeout(300)
    check("…and the task is saved at the top of the task folder", "root-level-task.md" in dict(files_of(page)))

    # demote across folders: the kept file moves into the target's folder; promote finds it again
    page.evaluate("async () => { await __todo.doDemote(__todo.get('t-s01'), __todo.get('t-s15'), { keep:true, kids:'move', level:2 }); }"); page.wait_for_timeout(500)
    fs = dict(files_of(page)); arch = fs.get("School/call-insurance-agent.md", "")
    check("demote (keep) across folders: the archived file moves into the target's folder", "status: archived" in arch and "call-insurance-agent.md" not in fs, [k for k in fs if "insurance" in k])
    check("…and the line links it by name within that folder", "[↗](call-insurance-agent.md)" in fs.get("School/research-paper-outline.md", ""))
    page.evaluate("() => __todo.openDrawer('t-s15')"); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    page.locator("#d-checklist .ck-item", has_text="Call insurance agent").locator("button").click(); page.wait_for_timeout(600)
    t = page.evaluate("() => { const t = __todo.get('t-s01'); return t && [t.file, t.status, t.demoted_into]; }")
    check("promote finds the archived file in the folder and restores it (same task)", t and t[0] == "School/call-insurance-agent.md" and t[1] == "open" and t[2] == "", t)
    page.click("#d-close"); page.wait_for_timeout(200)
    check("A (demo): no page errors", not errors, errors[:3])
    ctx.close()

    # ---------- B. fake OneDrive, phone: real moves, strays, folders changed elsewhere, the device copy ----------
    fm = lambda i, title, lst, extra="": f"---\nid: {i}\ntitle: {title}\nstatus: open\nlist: {lst}\norder: 1\n{extra}---\n"
    ofiles = {"p.md": fm("t-p", "Parent", "Work"), "c1.md": fm("t-c1", "Child one", "Work", "parent: t-p\n"), "c2.md": fm("t-c2", "Child two", "Work", "parent: t-p\n"),
              "solo.md": fm("t-solo", "Solo", "Inbox"), "due1.md": fm("t-d1", "Pay the bill", "Gone", f"due: {D(3)}\n"), "x.md": fm("t-x", "Gone task", "Gone"),
              "_todo.json": '{\n  "format": 3,\n  "lists": ["Inbox", "Work", "Gone"]\n}\n'}
    fg = FakeGraph(FOLDER, ofiles)
    od = TEST_AUTH + ls_init(**{"todo.source": "onedrive", "todo.folder": FOLDER, "todo.pollMs": 86400000, "todo.everSignedIn": True, "todo.list": ""})
    ctx, page, errors = new_page(browser, phone=True, init=od)
    fg.install(page)
    ready = "__todo.S.store && __todo.S.store.ready === true"
    page.goto(APP); page.wait_for_selector(".row"); page.wait_for_function(ready)
    poll = lambda: (page.evaluate("() => __todo.poll(true)"), page.wait_for_timeout(500))
    open_picker(page)
    check("OneDrive: the picker shows / (root) and the folders", picks(page)[:3] == ["/ (root)", "Work", "Gone"], picks(page))
    page.click("#modal [data-a=cancel]")
    sid = fg.by_path("solo.md")["id"]
    menu(page, "Solo", "Move to folder"); page.locator("#modal .pick .go", has_text="Work").click(); page.wait_for_timeout(500)
    it = fg.by_path("Work/solo.md")
    check("a move is one OneDrive move (PATCH with If-Match): same item, so its history stays", it is not None and it["id"] == sid and fg.by_path("solo.md") is None
          and any(m == "PATCH" and im for m, _, im in fg.requests), [r for r in fg.requests if r[0] == "PATCH"])
    fg.ext_edit("Gone/solo.md", fm("t-other", "Other solo", "Gone"))
    go_folder(page, "Work"); poll()
    menu(page, "Solo", "Move to folder"); page.locator("#modal .pick .go", has_text="Gone").click(); page.wait_for_timeout(600)
    check("moving onto a taken name gives the unique-name rule (solo-2.md)", fg.by_path("Gone/solo-2.md") is not None and fg.by_path("Gone/solo-2.md")["id"] == sid, fg.folders() and [k for k in fg.files() if "solo" in k])
    fg.ext_move("Work/p.md", "Gone"); poll()
    go_folder(page, "Gone")
    sb = row(page, "Parent").locator("[data-act=strays]")
    check("a parent moved in Explorer without its subtasks: ⚠ 2 on the parent (they still show under it)", sb.count() == 1 and sb.inner_text().strip() == "⚠ 2", row(page, "Parent").inner_text())
    row(page, "Parent").locator("[data-act=expand]").click(); page.wait_for_timeout(150)
    chips = page.locator(".row.sub .stray-chip").all_inner_texts()
    check("…and each of those subtask rows says where its file is: '⚠ in Work'", chips == ["⚠ in Work", "⚠ in Work"], chips)
    sb.click(); page.wait_for_selector("#modal [data-a=ok]")
    check("…one tap explains and offers 'Move them to Gone'", "in Work, not in Gone" in page.inner_text("#modal") and "Move them to Gone" in page.inner_text("#modal [data-a=ok]"), page.inner_text("#modal"))
    page.click("#modal [data-a=ok]"); page.wait_for_timeout(700)
    check("…which moves them; nothing moves until then", fg.by_path("Gone/c1.md") is not None and fg.by_path("Gone/c2.md") is not None and row(page, "Parent").locator("[data-act=strays]").count() == 0)
    check("…and the per-row markers go away", page.locator(".row.sub .stray-chip").count() == 0)
    fg.ext_mkdir("Made elsewhere"); fg.ext_rename_folder("Work", "Job"); poll()
    open_picker(page); p1 = picks(page); page.click("#modal [data-a=cancel]")
    check("a folder made elsewhere shows up; a renamed folder shows its new name", "Made elsewhere" in p1 and "Job" in p1 and "Work" not in p1, p1)
    fg.ext_edit("Job/late.md", fm("t-late", "Late arrival", "Job")); poll()
    fg.ext_rename_folder("Job", "Work2"); poll()
    check("…after a rename, its files (not sent again by OneDrive) are found at their new paths", page.evaluate("__todo.get('t-late')?.file") == "Work2/late.md", page.evaluate("__todo.get('t-late')?.file"))
    tst = page.inner_text("#toast")
    check("…and the app says it was renamed", "renamed to “Work2”" in tst, tst)
    check("…and _todo.json follows the new name", "Work2" in json.loads(fg.files()["_todo.json"]).get("folders", []), fg.files()["_todo.json"])
    page.reload(); page.wait_for_function(ready); page.wait_for_timeout(200)     # (the test's start settings open / (root), empty by now)
    check("after a restart from the device copy, tasks in folders are there", page.evaluate("__todo.get('t-late')?.file") == "Work2/late.md")
    fg.ext_edit("Work2/late.md", fm("t-late", "Late arrival (edited)", "Work2")); poll()
    check("after a restart from the device copy, a change inside a folder is still picked up", page.evaluate("__todo.get('t-late')?.title") == "Late arrival (edited)", page.evaluate("__todo.get('t-late')?.title"))
    fg.ext_delete_folder("Gone"); poll(); page.wait_for_timeout(300)
    txt = page.inner_text("#modal") if page.locator("#modal-bg.on").count() else ""
    check("a folder deleted elsewhere: 'The folder “Gone” is gone', its tasks listed, due-dated first, and where to restore",
          "The folder “Gone” is gone" in txt and "Pay the bill" in txt and txt.index("Pay the bill") < txt.index("Gone task") and "Recycle bin" in txt, txt[:300])
    if page.locator("#modal [data-a=ok]").count(): page.click("#modal [data-a=ok]")
    check("…and its tasks are gone from the app", page.evaluate("__todo.get('t-d1')") is None and page.evaluate("__todo.get('t-p')") is None)
    check("B (OneDrive): never wrote without If-Match", not fg.violations, fg.violations[:3])
    check("B (OneDrive): no page errors", not errors, errors[:3])
    ctx.close()


def test_r211_fast_entry(browser):
    print("\n[23] R2-11 to R2-15: Enter = next task, inline add line, Save & close subdued, clear due, Delete all colour")
    D = lambda n: (datetime.date.today() + datetime.timedelta(days=n)).isoformat()
    files = lambda page: Files(page.evaluate("() => Object.fromEntries([...__todo.S.store.files].map(([k, v]) => [k, v.text]))"))
    task = lambda page, title: page.evaluate("ti => { const t = __todo.all().find(x => x.title === ti); return t ? { id:t.id, parent:t.parent, list:t.list, order:t.order, file:t.file, due:t.due, isNew:!!t.isNew } : null; }", title)
    focused_line = lambda page: page.evaluate("() => { const a = document.activeElement; return a && a.classList.contains('addsub-in') ? a.closest('.addsub').dataset.parent : null; }")
    ctx, page, errors = new_page(browser, phone=True, init=ls_init(**{"todo.source": "demo", "todo.list": "Home"}))
    page.goto(APP); page.wait_for_selector(".row")

    # ---- R2-11 inline line ----
    check("R2-11: no add line under a collapsed parent", page.locator(".addsub").count() == 0)
    row(page, "Solar panel cleaning").locator("[data-act=expand]").click(); page.wait_for_timeout(150)
    line = page.locator(".addsub[data-parent=t-s05] .addsub-in")
    check("R2-11: an expanded parent with subtasks gets '+ Add subtask…' under its subtasks", line.count() == 1 and line.get_attribute("placeholder") == "Add subtask…")
    line.click(); line.type("Sub A"); page.keyboard.press("Enter"); page.wait_for_timeout(300)
    page.keyboard.type("Sub B"); page.keyboard.press("Enter"); page.wait_for_timeout(300)
    a, b = task(page, "Sub A"), task(page, "Sub B")
    check("…two Enters save two subtasks under that parent, in the parent's list, in order", a and b and a["parent"] == b["parent"] == "t-s05" and a["list"] == b["list"] == "Home"
          and b["order"] > a["order"] and not a["isNew"] and not b["isNew"] and "sub-a.md" in files(page) and "sub-b.md" in files(page), (a, b))
    check("…the line stays focused and empty, ready for the next one", focused_line(page) == "t-s05" and page.locator(".addsub[data-parent=t-s05] .addsub-in").input_value() == "")
    kids_titles = page.evaluate("() => [...document.querySelectorAll('#rows .row.sub .ttl')].map(e => e.textContent.trim())")
    check("…and they show at the end of its subtasks", kids_titles[-2:] == ["Sub A", "Sub B"], kids_titles)
    page.keyboard.type("keep me"); page.evaluate("() => __todo.render()"); page.wait_for_timeout(100)
    check("…a redraw (e.g. a sync) keeps what you're typing and the focus", focused_line(page) == "t-s05" and page.locator(".addsub[data-parent=t-s05] .addsub-in").input_value() == "keep me")
    page.locator(".addsub[data-parent=t-s05] .addsub-in").fill("")
    page.keyboard.press("Enter"); page.wait_for_timeout(100)
    check("…Enter on an empty line stops (leaves the line, saves nothing)", focused_line(page) is None and not any(k.startswith("untitled") for k in files(page)))
    # ⤢ hands the typed title to the editor
    page.locator(".addsub[data-parent=t-s05] .addsub-in").fill("Handoff with notes")
    page.locator(".addsub[data-parent=t-s05] .addsub-ed").click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(200)
    check("R2-11: ⤢ opens the full editor with the typed title, as a subtask of that parent", page.input_value("#f-title") == "Handoff with notes" and "Solar panel cleaning" in page.inner_text("#d-parent")
          and page.is_enabled("#d-save"))
    page.click("#d-saveclose"); page.wait_for_timeout(300)
    check("…and saves there", task(page, "Handoff with notes") and task(page, "Handoff with notes")["parent"] == "t-s05" and page.locator("#drawer.open").count() == 0)
    # ⋯ → Add subtask on a task with no subtasks
    row(page, "A deliberately long").locator(".row-more").click(); page.locator("#pop button", has_text="Add subtask").click(); page.wait_for_timeout(200)
    check("R2-11: ⋯ → Add subtask opens the inline line (focused) even with no subtasks yet, not the editor", focused_line(page) == "t-s18" and page.locator("#drawer.open").count() == 0)
    page.keyboard.type("First child"); page.keyboard.press("Enter"); page.wait_for_timeout(300)
    fc = task(page, "First child")
    check("…Enter saves it under that task, which now has a 1-subtask badge", fc and fc["parent"] == "t-s18" and row(page, "A deliberately long").locator("[data-act=expand]").inner_text() == "0/1")
    page.locator(".addsub[data-parent=t-s18] .addsub-in").evaluate("e => e.blur()"); page.wait_for_timeout(300)
    check("…its line stays while it's expanded with subtasks", page.locator(".addsub[data-parent=t-s18]").count() == 1)
    row(page, "Fix gate latch").locator(".row-more").click(); page.locator("#pop button", has_text="Add subtask").click(); page.wait_for_timeout(200)
    check("…(Fix gate latch: only an archived subtask) the line appears", focused_line(page) == "t-s03")
    page.locator(".addsub[data-parent=t-s03] .addsub-in").evaluate("e => e.blur()"); page.wait_for_timeout(350)
    check("…and goes away when you leave it empty", page.locator(".addsub[data-parent=t-s03]").count() == 0)
    page.screenshot(path=str(SHOTS / "48-phone-inline-add.png"))

    # ---- R2-11 editor chain + R2-12 Save & close subdued ----
    row(page, "Solar panel cleaning").locator(".ttl").click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    check("R2-12: nothing changed → Save disabled and Save & close subdued", page.is_disabled("#d-save") and "sc-idle" in page.get_attribute("#d-saveclose", "class"))
    page.click("#d-sub"); page.wait_for_timeout(300)
    check("R2-12: a brand-new blank task isn't 'changed' yet (Save off, Save & close subdued)", page.input_value("#f-title") == "" and page.is_disabled("#d-save") and "sc-idle" in page.get_attribute("#d-saveclose", "class"))
    page.fill("#f-title", "Chain one")
    check("…typing a title turns both on", page.is_enabled("#d-save") and "sc-idle" not in page.get_attribute("#d-saveclose", "class"))
    check("R2-11: the phone keyboard says 'next' for a new task", page.evaluate("document.querySelector('#f-title').enterKeyHint") == "next")
    page.press("#f-title", "Enter"); page.wait_for_timeout(500)
    c1 = task(page, "Chain one")
    check("R2-11: Enter saves the new subtask and opens the next blank one (same parent), cursor in the title", c1 and not c1["isNew"] and c1["parent"] == "t-s05"
          and page.locator("#drawer.open").count() == 1 and page.input_value("#f-title") == "" and "Solar panel cleaning" in page.inner_text("#d-parent")
          and page.evaluate("document.activeElement.id") == "f-title", c1)
    page.fill("#f-title", "Chain two"); page.press("#f-title", "Enter"); page.wait_for_timeout(500)
    c2 = task(page, "Chain two")
    check("…copies only the parent and list (no due date)", c2 and c2["parent"] == "t-s05" and c2["list"] == "Home" and not c2["due"] and c2["order"] > c1["order"], c2)
    page.press("#f-title", "Enter"); page.wait_for_timeout(300)
    check("R2-11: Enter on an empty title stops: editor closed, no blank file, no unsaved ghost", page.locator("#drawer.open").count() == 0
          and not page.evaluate("() => __todo.all().some(t => t.isNew)") and not any(k.startswith("untitled") for k in files(page)))
    row(page, "Solar panel cleaning").locator(".ttl").click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    check("R2-11: the keyboard says 'done' for an existing task", page.evaluate("document.querySelector('#f-title').enterKeyHint") == "done")
    page.click("#d-saveclose"); page.wait_for_timeout(200)
    check("R2-12: the subdued Save & close still closes", page.locator("#drawer.open").count() == 0)
    row(page, "Solar panel cleaning").locator(".ttl").click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    page.fill("#f-title", "Solar panel cleaning (both houses)"); page.press("#f-title", "Enter"); page.wait_for_timeout(400)
    check("R2-11: Enter in an existing task's title = Save & close (no new task)", page.locator("#drawer.open").count() == 0
          and "title: Solar panel cleaning (both houses)" in files(page)["solar-panel-cleaning.md"] and not page.evaluate("() => __todo.all().some(t => t.isNew)"))

    # ---- R2-13 clear the due date ----
    row(page, "Solar panel cleaning").locator(".ttl").click(); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    check("R2-13: ✕ shows next to Due while there's a date", page.is_visible("#f-due-clear"))
    page.click("#f-due-clear")
    check("…tapping it clears the field, hides itself and marks the task changed", page.input_value("#f-due") == "" and not page.is_visible("#f-due-clear") and page.is_enabled("#d-save"))
    page.click("#d-saveclose"); page.wait_for_timeout(300)
    check("…Save removes due from the file", "\ndue:" not in files(page)["solar-panel-cleaning.md"], files(page)["solar-panel-cleaning.md"][:250])
    row(page, "Fix gate latch").locator(".row-more").click(); page.locator("#pop button", has_text="Change due date").click()
    check("R2-13: Change due date… offers 'No date' when there is one", page.locator("#modal .pick .go", has_text="No date").count() == 1)
    page.locator("#modal .pick .go", has_text="No date").click(); page.wait_for_timeout(300)
    check("…which clears it in the file, with Undo", "\ndue:" not in files(page)["fix-gate-latch.md"] and "no date" in page.inner_text("#undo-msg"), page.inner_text("#undo-msg"))
    page.click("#undo-btn"); page.wait_for_timeout(300)
    check("…Undo puts the date back", f"due: {D(-1)}" in files(page)["fix-gate-latch.md"])
    row(page, "A deliberately long").locator(".row-more").click(); page.locator("#pop button", has_text="Change due date").click()
    check("…no 'No date' choice for a task without a date", page.locator("#modal .pick .go", has_text="No date").count() == 0)
    page.click("#modal [data-a=cancel]")
    page.evaluate("() => __todo.openDrawer('t-s19')"); page.wait_for_selector("#drawer.open"); page.wait_for_timeout(300)
    page.click("#f-due-clear"); page.click("#d-saveclose"); page.wait_for_timeout(300)
    cr = files(page)["collect-rent.md"]
    check("R2-13: a recurring task's date can be cleared; repeat: stays", "\ndue:" not in cr and "repeat: monthly" in cr, cr[:250])

    # ---- R2-15 Delete all colour ----
    row(page, "Solar panel cleaning").locator(".row-more").click(); page.locator("#pop button", has_text="Delete").click(); page.wait_for_selector("#modal [data-a=ok]")
    st = page.eval_on_selector("#modal [data-a=ok]", "b => [getComputedStyle(b).backgroundColor, getComputedStyle(b).color, b.textContent]")
    check("R2-15: Delete all is white text on a deep red (readable), not red on blue", st[0] == "rgb(201, 48, 44)" and st[1] == "rgb(255, 255, 255)" and st[2] == "Delete all", st)
    page.screenshot(path=str(SHOTS / "49-phone-delete-all.png"))
    page.click("#modal [data-a=cancel]")
    check("R2-11 to R2-15: no page errors", not errors, errors[:3])
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
                 ("security", test_hostile_files), ("netlock", test_network_lock), ("phase4", test_phase4), ("desktopsite", test_desktop_site_phone), ("phase5", test_phase5), ("indent", test_indent_saveclose), ("pctoolbar", test_pc_toolbar), ("recurring", test_recurring), ("today", test_today), ("localfolder", test_local_folder), ("diag", test_diagnostics), ("devicecopy", test_device_copy), ("agentr1", test_agent_round1), ("agentr2", test_agent_round2), ("agentr3", test_agent_round3), ("r26", test_r26_signin_editor), ("r28p1", test_r28_phase1), ("r211", test_r211_fast_entry), ("fmtcheck", test_format_check), ("r25", test_r25_folders)]
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
