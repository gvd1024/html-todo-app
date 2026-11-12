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

    // R2-8 Deleted A: files in the hidden .trash folder are never tasks — not in list(), not in changes()
    const tp = '.trash/20261101-120000-abc123-alpha.md';
    const tv = await s.create(tp, '---\nid: t-a\ntitle: Alpha (trashed)\nstatus: open\nlist: Inbox\norder: 1\n---\n');
    await s.create(tp.replace(/\.md$/, '.json'), '{"format":1,"path":"alpha.md"}\n');
    check('a file created in .trash is never listed as a task', !(await s.list()).some(e => e.path.includes('.trash')), JSON.stringify(await s.list()));
    const tl = await s.trashList();
    check('trashList() lists the trash entry (text + sidecar)', tl.some(e => e.path === tp && e.version === tv) && tl.some(e => e.path === tp.replace(/\.md$/, '.json')), JSON.stringify(tl));
    const ch3 = await s.changes();
    check('changes() never reports a .trash file', !ch3.some(c => String(c.path).includes('.trash') || c.path === 'alpha.md' && c.deleted), JSON.stringify(ch3));
    check('a trash entry reads back exactly', (await s.read(tp)).text.includes('Alpha (trashed)'));
    await s.remove(tp, tv);
    check('a trash entry can be removed', !(await s.trashList()).some(e => e.path === tp));

    // R2-5 folders: files in a folder are listed by path; a move keeps the text; folders are listed and managed
    const fv = await s.create('Work/gamma.md', '---\nid: t-g\ntitle: Gamma\nstatus: open\norder: 1\n---\ngamma body\n');
    await s.create('Deep/deeper/delta.md', '---\nid: t-d\ntitle: Delta\nstatus: open\norder: 1\n---\n');
    const l2 = await s.list();
    check('a file in a folder is listed with its path', l2.some(e => e.path === 'Work/gamma.md' && e.version === fv), JSON.stringify(l2));
    check('a file two folders down is not listed (one level of folders for now)', !l2.some(e => e.path.includes('deeper')), JSON.stringify(l2));
    check('folders() lists the folders (not hidden ones like .trash)', (s.folders() || []).includes('Work') && !(s.folders() || []).some(f => f.startsWith('.')), JSON.stringify(s.folders()));
    const mv = await s.move('Work/gamma.md', 'gamma.md', fv);
    check('move() puts the file at its new path with the same text and a version', !!mv && (await s.read('gamma.md')).text.includes('gamma body'), mv);
    check('…and it is gone from the old path', !(await s.list()).some(e => e.path === 'Work/gamma.md'));
    await expectErr('move() with a version that is not the current one → ConflictError', () => s.move('gamma.md', 'Work/gamma.md', 'not-the-version'), T.ConflictError);
    await expectErr('move() onto a taken name → ExistsError', () => s.move('gamma.md', 'alpha.md', mv), T.ExistsError);
    const mv2 = await s.move('gamma.md', 'Work/gamma.md', mv);
    check('move() into a folder', (await s.read('Work/gamma.md')).text.includes('gamma body') && !!mv2);
    await s.createFolder('Empty'); await s.list();
    check('createFolder() makes a folder that is listed', (s.folders() || []).includes('Empty'), JSON.stringify(s.folders()));
    await expectErr('createFolder() refuses an existing name, any case', () => s.createFolder('empty'), T.ExistsError);
    await s.renameFolder('Work', 'Job'); const l3 = await s.list();
    check('renameFolder(): its files follow, with their text', l3.some(e => e.path === 'Job/gamma.md') && !l3.some(e => e.path.startsWith('Work/')) && (await s.read('Job/gamma.md')).text.includes('gamma body'), JSON.stringify(l3));
    check('…and folders() has the new name only', (s.folders() || []).includes('Job') && !(s.folders() || []).includes('Work'), JSON.stringify(s.folders()));
    await expectErr('removeFolder() refuses a folder with files', () => s.removeFolder('Job'), T.FolderError);
    await s.removeFolder('Empty'); await s.list();
    check('removeFolder() removes an empty folder', !(s.folders() || []).includes('Empty'), JSON.stringify(s.folders()));
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
