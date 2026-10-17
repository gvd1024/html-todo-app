// Shared store test suite (storage-spec S-2 acceptance): every connector must behave the same.
// Usage in a page: await storeSuite(label, store, ext) → [{name, ok, detail}]
//   ext.edit(path, text) / ext.del(path) simulate a change made by another device or Claude.
window.storeSuite = async function (label, s, ext) {
  const T = window.__todo, out = [];
  const check = (name, ok, detail = '') => out.push({ name: `${label}: ${name}`, ok: !!ok, detail: String(detail) });
  const expectErr = async (name, fn, Cls) => {
    try { await fn(); check(name, false, 'no error thrown'); }
    catch (e) { check(name, e instanceof Cls, e.constructor.name + ' ' + e.message); }
  };
  try {
    const list = await s.list();
    const paths = list.map(e => e.path).sort();
    check('list returns task files and _todo.json only', JSON.stringify(paths) === JSON.stringify(['_todo.json', 'alpha.md', 'beta.md']), paths.join(','));
    const a = await s.read('alpha.md');
    check('read returns text', a.text.includes('title: Alpha'), a.text.slice(0, 40));
    check('read version matches list version', a.version === list.find(e => e.path === 'alpha.md').version, a.version);
    const v2 = await s.write('alpha.md', a.text + '\nedited once', a.version);
    check('write with the loaded version succeeds and changes the version', v2 && v2 !== a.version, v2);
    await expectErr('write with a stale version → ConflictError', () => s.write('alpha.md', a.text + '\nstale write!!', a.version), T.ConflictError);
    const v3 = await s.create('gamma.md', '---\nid: t-g\ntitle: Gamma\nstatus: open\nlist: Inbox\norder: 3\n---\n');
    check('create a new file', !!v3, v3);
    await expectErr('create an existing name → ExistsError', () => s.create('gamma.md', 'x'), T.ExistsError);
    await expectErr('write to a missing file → ConflictError', () => s.write('missing.md', 'x', 'v'), T.ConflictError);
    await expectErr('read a missing file → NotFoundError', () => s.read('missing.md'), T.NotFoundError);
    const g = await s.read('gamma.md');
    await expectErr('remove with a stale version → ConflictError', () => s.remove('gamma.md', 'not-the-version'), T.ConflictError);
    await s.remove('gamma.md', g.version);
    await expectErr('removed file is gone', () => s.read('gamma.md'), T.NotFoundError);
    await s.remove('gamma.md', g.version);
    check('removing an already-removed file is a no-op', true);

    // change feed: first call = baseline, then only real changes
    await s.changes();
    const quiet = await s.changes();
    check('changes() is empty when nothing changed', quiet.length === 0, JSON.stringify(quiet));
    const b = await s.read('beta.md');
    const own = await s.write('beta.md', b.text + '\nown write', b.version);
    const afterOwn = await s.changes();
    const ownReported = afterOwn.find(c => c.path === 'beta.md');
    check('own write is reported with the version we already hold (app ignores it)', !ownReported || ownReported.version === own, JSON.stringify(afterOwn));
    await ext.edit('alpha.md', '---\nid: t-a\ntitle: Alpha edited elsewhere\nstatus: open\nlist: Inbox\norder: 1\n---\nchanged by another device, longer text\n');
    const ch1 = await s.changes();
    const hit = ch1.find(c => c.path === 'alpha.md' && !c.deleted);
    check('an outside edit is reported by changes()', !!hit, JSON.stringify(ch1));
    const fresh = await s.read('alpha.md');
    check('outside edit readable with a new version', fresh.text.includes('Alpha edited elsewhere') && (!hit || fresh.version === hit.version), fresh.version);
    await ext.del('beta.md');
    const ch2 = await s.changes();
    check('an outside delete is reported by changes()', ch2.some(c => c.path === 'beta.md' && c.deleted), JSON.stringify(ch2));
  } catch (e) {
    check('suite crashed', false, e.stack || e.message);
  }
  return out;
};
window.storeSeed = {
  'alpha.md': '---\nid: t-a\ntitle: Alpha\nstatus: open\nlist: Inbox\norder: 1\n---\nalpha body\n',
  'beta.md': '---\nid: t-b\ntitle: Beta\nstatus: open\nlist: Inbox\norder: 2\n---\nbeta body\n',
  '_todo.json': '{\n  "format": 2,\n  "lists": ["Inbox"]\n}\n',
  '_notes.md': 'not a task (leading underscore)',
  'README.md': 'not a task',
};
