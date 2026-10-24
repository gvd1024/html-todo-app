"""Stress test: how many realistic task files can HTA handle before it gets unacceptably slow?

Generates synthetic task folders in the browser (never touches real data), loads them through different stores,
and times the common actions at growing sizes.

    python tests/stress.py                       # default sweep, PC speed
    python tests/stress.py --cpu 4               # phone stand-in (Chrome CPU slowdown x4)
    python tests/stress.py --sizes 1000,5000 --stores mem,opfs,net --shape spread

Stores: mem  = files in memory (pure app cost: parsing + drawing)
        opfs = the browser's private disk through the local-folder store (FsStore), like a folder on a PC
        net  = files in memory behind a simulated network (--latency ms per request, 6 parallel, 200 items per
               listing page), the request pattern the app uses with OneDrive
Shapes: spread  = 10 lists, ~55% of tasks done (hidden), 20% subtasks, half with due dates (a realistic history)
        onelist = everything open in one list (worst case for drawing a list)
Writes a JSON + Markdown summary to tests/stress-results/.
"""
import argparse, json, pathlib, sys, threading, time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 8766
OUT = ROOT / "tests" / "stress-results"

GEN_JS = r"""
(args) => {
  const { n, shape, seed } = args;
  let s = seed >>> 0; const rnd = () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  const pick = a => a[Math.floor(rnd() * a.length)];
  const W = 'call email fix buy order check renew book clean plan review update cancel schedule pay sort file return pick drop ask send print move test water mow paint replace research compare'.split(' ');
  const N = 'insurance plumber garage filter receipts lease taxes dentist car tires gutters fence roof budget invoice report slides garden seeds groceries passport warranty router backup photos books flights hotel gift'.split(' ');
  const lists = shape === 'onelist' ? ['Inbox'] : ['Inbox','Home','Work','Errands','Rental','Garden','Finance','Health','Projects','Someday'];
  const weights = shape === 'onelist' ? [1] : [30,15,15,8,7,6,6,5,5,3];
  const wsum = weights.reduce((a, b) => a + b, 0);
  const pickList = () => { let r = rnd() * wsum; for (let i = 0; i < lists.length; i++){ r -= weights[i]; if (r < 0) return lists[i]; } return lists[0]; };
  const iso = off => { const d = new Date(); d.setDate(d.getDate() + off); return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); };
  const sentence = (a, b) => { const k = a + Math.floor(rnd() * (b - a + 1)); const w = []; for (let i = 0; i < k; i++) w.push(i % 2 ? pick(N) : pick(W)); return w.join(' '); };
  const files = {}; const tops = {}; lists.forEach(l => tops[l] = []);
  for (let i = 0; i < n; i++){
    const id = 't-20260101-' + i.toString(36).padStart(4, '0');
    const title = sentence(2, 6); const cap = title[0].toUpperCase() + title.slice(1);
    const list = pickList();
    const status = shape === 'onelist' ? 'open' : (rnd() < 0.55 ? 'done' : rnd() < 0.9 ? 'open' : 'active');
    const parent = tops[list].length && rnd() < 0.2 ? pick(tops[list]) : '';
    if (!parent) tops[list].push(id);
    const fm = ['---', 'id: ' + id, 'title: ' + cap, 'status: ' + status, 'list: ' + list];
    if (parent) fm.push('parent: ' + parent);
    fm.push('order: ' + (i + 1));
    if (rnd() < 0.5) fm.push('due: ' + iso(Math.floor(rnd() * 121) - 60));
    if (rnd() < 0.03) fm.push('repeat: ' + pick(['daily', 'weekly', 'monthly', 'weekdays', 'every 2 weeks']));
    if (status === 'done') fm.push('completed: ' + iso(-Math.floor(rnd() * 365)));
    fm.push('---');
    const r = rnd(); let body = '';
    if (r < 0.4) body = '';
    else if (r < 0.8){ const k = 1 + Math.floor(rnd() * 5); body = Array.from({ length:k }, () => sentence(4, 14)).join('\n'); }
    else if (r < 0.95){ const k = 3 + Math.floor(rnd() * 8); body = Array.from({ length:k }, () => '- [' + (rnd() < 0.4 ? 'x' : ' ') + '] ' + sentence(2, 7)).join('\n'); }
    else { const k = 30 + Math.floor(rnd() * 50); body = Array.from({ length:k }, () => (rnd() < 0.3 ? '- [ ] ' : '') + sentence(5, 16)).join('\n'); }
    files[cap.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 30) + '-' + i + '.md'] = fm.join('\n') + '\n' + (body ? '\n' + body + '\n' : '');
  }
  files['_todo.json'] = JSON.stringify({ format: 3, lists }, null, 2) + '\n';
  return files;
}
"""

BENCH_JS = r"""
async (args) => {
  const { store: kind, latency, coldLatency, n } = args; window.__lat = coldLatency ?? latency;
  const T = window.__todo; const files = window.__files;
  const frame = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));   // let the browser paint
  const longs = []; new PerformanceObserver(l => l.getEntries().forEach(e => longs.push(e))).observe({ type:'longtask', buffered:false });
  const since = t0 => longs.filter(e => e.startTime >= t0);
  const gc = () => { try { window.gc && window.gc(); } catch {} };
  let calls = 0;
  let store, makeSource;
  if (kind === 'mem'){ makeSource = () => new T.MemStore(files); }
  else if (kind === 'net'){
    const inner = new T.MemStore(files); const wait = () => new Promise(r => setTimeout(r, window.__lat)); const PAGE = 200;
    makeSource = () => { const s = Object.create(inner);
      s.kind = 'onedrive'; s.demo = false; s.folder = 'stress'; s.name = 'OneDrive · stress';
      s.list = async () => { const e = await inner.list(); for (let i = 0; i < Math.max(1, Math.ceil(e.length / PAGE)); i++){ calls++; await wait(); } return e; };
      s.read = async (p, o) => { calls++; await wait(); return inner.read(p, o); };
      s.write = async (...a) => { calls++; await wait(); return inner.write(...a); };
      s.create = async (...a) => { calls++; await wait(); return inner.create(...a); };
      s.changes = async () => { calls++; await wait(); return []; };            // OneDrive delta: one call, no changes
      if (window.__deviceCopy){                                                   // the source abilities the device copy uses
        s.snapshot = async () => ({ entries: await s.list(), token: 'bookmark' });
        s.changesSince = async tok => { calls++; await wait(); return { changes: [], token: tok }; };
      }
      return s; };
  } else {
    const root = await navigator.storage.getDirectory();
    try { await root.removeEntry('stress', { recursive:true }); } catch {}
    const dir = await root.getDirectoryHandle('stress', { create:true });
    const names = Object.keys(files); let i = 0;
    await Promise.all(Array.from({ length:8 }, async () => { while (i < names.length){ const nm = names[i++];
      const w = await (await dir.getFileHandle(nm, { create:true })).createWritable(); await w.write(files[nm]); await w.close(); } }));
    makeSource = () => new T.FsStore(dir);
  }
  store = makeSource();
  const R = {};
  gc(); await frame();
  // startup: read every file + draw the first list
  let t0 = performance.now(); calls = 0;
  await T.useStore(store); await frame();
  R.startupMs = performance.now() - t0; R.startupCalls = calls; R.startupLongest = Math.max(0, ...since(t0).map(e => e.duration));
  R.tasks = T.S.tasks.size; window.__lat = latency;
  clearTimeout(window.__noop);
  // the biggest list
  const counts = {}; T.all().forEach(t => { if (!t.parent && t.status !== 'done' && t.status !== 'archived') counts[t.list] = (counts[t.list] || 0) + 1; });
  const big = Object.entries(counts).sort((a, b) => b[1] - a[1])[0] || ['Inbox', 0];
  R.biggestList = big[0]; R.biggestListOpenTop = big[1];
  const act = async (name, fn) => { await frame(); const a = performance.now(); await fn(); await frame(); const ms = performance.now() - a;
    R[name] = Math.round(ms); R[name + 'Longest'] = Math.round(Math.max(0, ...since(a).map(e => e.duration))); };
  await act('switchList', async () => { T.S.view = 'list'; T.S.list = big[0]; T.render(); });
  R.rowsDrawn = document.querySelectorAll('#rows .row').length;
  // scrolling the biggest list: frames slower than 50 ms are visible stutter
  { const sc = document.querySelector('#scroller'); sc.scrollTop = 0; await frame(); const dts = []; let last = performance.now();
    for (let i = 0; i < 90; i++){ sc.scrollTop += 120; await new Promise(r => requestAnimationFrame(r)); const now = performance.now(); dts.push(now - last); last = now; }
    dts.sort((a, b) => a - b); R.scrollP95FrameMs = Math.round(dts[Math.floor(dts.length * 0.95)]); R.scrollJankFrames = dts.filter(d => d > 50).length; sc.scrollTop = 0; }
  await act('todayView', async () => { T.S.view = 'due'; T.render(); });
  await act('backToList', async () => { T.S.view = 'list'; T.render(); });
  await act('search', async () => { T.S.q = 'plumber'; T.render(); });
  await act('clearSearch', async () => { T.S.q = ''; T.render(); });
  const victim = T.all().find(t => t.list === big[0] && !t.parent && t.status === 'open' && !T.all().some(c => c.parent === t.id) && !t.repeat && !/\[ \]/.test(t.body));
  if (victim){
    await act('checkOff', async () => { await T.setDone([victim], true); });
    await act('uncheck', async () => { await T.setDone([victim], false); });
  }
  await act('quickAdd', async () => { const qa = document.querySelector('#qa'); qa.value = 'Stress quick add';
    qa.dispatchEvent(new KeyboardEvent('keydown', { key:'Enter', bubbles:true })); });
  await new Promise(r => setTimeout(r, Math.max(50, latency * 2)));
  const ed = T.all().find(t => t.list === big[0] && t.body && t.body.length > 200) || victim;
  if (ed){
    await act('openEditor', async () => { T.openDrawer(ed.id); await new Promise(r => setTimeout(r, 30)); });
    await act('closeEditor', async () => { T.closeDrawer(true); });
  }
  // background sync check while idle (what runs every 5 s on a PC, 10 s on a phone)
  { const pa = performance.now(); const runs = []; let gap = 0, on = true, lastF = performance.now();
    const probe = () => { const now = performance.now(); gap = Math.max(gap, now - lastF); lastF = now; if (on) requestAnimationFrame(probe); }; requestAnimationFrame(probe);
    for (let i = 0; i < 3; i++){ calls = 0; const a = performance.now(); await T.poll(true); runs.push(performance.now() - a); }
    on = false; R.idlePollMaxFrameGap = Math.round(gap);
    runs.sort((a, b) => a - b); R.idlePollMs = Math.round(runs[1]); R.idlePollCalls = calls; R.idlePollLongest = Math.round(Math.max(0, ...since(pa).map(e => e.duration))); }
  // second launch: the everyday case (with the device copy, it starts from the copy on this device)
  { T.S.tasks = new Map(); const rows = document.querySelector('#rows'); rows.innerHTML = ''; let painted = null; const a = performance.now();
    const mo = new MutationObserver(() => { if (painted == null && rows.querySelector('.row')) painted = performance.now() - a; }); mo.observe(rows, { childList:true, subtree:true });
    calls = 0; await T.useStore(makeSource()); await frame(); mo.disconnect();
    R.restartMs = Math.round(performance.now() - a); R.restartFirstPaintMs = Math.round(painted ?? R.restartMs); R.restartCalls = calls; }
  gc(); await frame();
  R.heapMB = performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null;
  R.domNodes = document.getElementsByTagName('*').length;
  R.startupMs = Math.round(R.startupMs); R.startupLongest = Math.round(R.startupLongest);
  return R;
}
"""


def serve():
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), partial(type("Q", (SimpleHTTPRequestHandler,), {"log_message": lambda *a: None}), directory=str(ROOT)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def run_one(browser, n, store, shape, cpu, latency, phone, device_copy=True, cold_latency=None):
    vp = {"viewport": {"width": 412, "height": 860}, "is_mobile": True, "has_touch": True} if phone else {"viewport": {"width": 1280, "height": 860}}
    ctx = browser.new_context(**vp)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script("window.__TEST_NO_BOOT__ = true; localStorage.setItem('todo.pollMs', '86400000'); localStorage.setItem('todo.showDone', 'false');"
                         + f"window.__deviceCopy = {'true' if device_copy else 'false'}; localStorage.setItem('todo.deviceCopy', '{'true' if device_copy else 'false'}');")
    page.goto(f"http://127.0.0.1:{PORT}/app/")
    page.wait_for_function("window.__todo")
    page.evaluate("f => { window.__files = f; }", page.evaluate(GEN_JS, {"n": n, "shape": shape, "seed": 1234}))
    if cpu > 1:
        ctx.new_cdp_session(page).send("Emulation.setCPUThrottlingRate", {"rate": cpu})
    t = time.time()
    try:
        r = page.evaluate(BENCH_JS, {"store": store, "latency": latency, "coldLatency": cold_latency, "n": n})
    except Exception as e:  # report crashes / timeouts as a result
        r = {"error": str(e)[:300]}
    r.update(n=n, store=store, shape=shape, cpu=cpu, wall=round(time.time() - t, 1), errors=errors[:3])
    ctx.close()
    return r


GOOD, POOR = 200, 500          # INP thresholds (ms) for a user action
START_GOOD, START_POOR = 2500, 4000


def verdict(r):
    if "error" in r:
        return "CRASH"
    acts = [r.get(k, 0) for k in ("switchList", "todayView", "search", "checkOff", "quickAdd", "openEditor")]
    worst = max(acts)
    duty = r["idlePollMs"] / 5000                     # share of each 5 s sync cycle spent checking (PC interval)
    if worst > POOR or r["startupMs"] > START_POOR or r["scrollJankFrames"] > 5 or duty > 0.2 or r.get("idlePollMaxFrameGap", 0) > 100:
        return "POOR"
    if worst > GOOD or r["startupMs"] > START_GOOD or r["scrollJankFrames"] > 0 or duty > 0.05:
        return "OK"
    return "GOOD"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default="250,500,1000,2000,5000,10000,20000")
    ap.add_argument("--stores", default="mem,opfs,net")
    ap.add_argument("--shape", default="spread")
    ap.add_argument("--cpu", type=float, default=1)
    ap.add_argument("--latency", type=int, default=120)
    ap.add_argument("--net-max", type=int, default=5000, help="largest size to run on the simulated network (it's linear)")
    ap.add_argument("--phone", action="store_true")
    ap.add_argument("--tag", default="")
    ap.add_argument("--cold-latency", type=int, default=None, help="network delay for the first (filling) launch only; 0 = fast")
    ap.add_argument("--no-device-copy", action="store_true", help="measure without the R2-7 A device copy (the old behaviour)")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    httpd = serve()
    results = []
    cols = ["n", "store", "startupMs", "startupCalls", "restartFirstPaintMs", "restartMs", "restartCalls", "switchList", "todayView", "search", "checkOff", "quickAdd", "openEditor",
            "scrollP95FrameMs", "scrollJankFrames", "idlePollMs", "idlePollMaxFrameGap", "heapMB", "rowsDrawn", "verdict"]
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--enable-precise-memory-info", "--js-flags=--expose-gc"])
        for store in a.stores.split(","):
            for n in map(int, a.sizes.split(",")):
                if store == "net" and n > a.net_max:
                    continue
                r = run_one(browser, n, store, a.shape, a.cpu, a.latency, a.phone, not a.no_device_copy, a.cold_latency)
                r["verdict"] = verdict(r)
                results.append(r)
                print(" | ".join(f"{c}={r.get(c)}" for c in cols) + (f" | ERR {r.get('error') or r.get('errors')}" if r.get("error") or r.get("errors") else ""), flush=True)
        browser.close()
    httpd.shutdown()
    tag = a.tag or f"{a.shape}-cpu{int(a.cpu)}{'-phone' if a.phone else ''}"
    (OUT / f"{tag}.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    md = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    md += ["| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in results]
    (OUT / f"{tag}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT / (tag + '.md')}")


if __name__ == "__main__":
    main()
