"""Writes tests/fixtures/frontmatter/: the shared task-file fixtures (R2-22, rule 13). The expected outputs are written by hand
here (they are the contract); HTA (tests/run_tests.py r222) and HTA Alarms (android/core tests) must both reproduce them."""
import json, pathlib
D = pathlib.Path(__file__).resolve().parent / 'frontmatter'   # run: python tests/fixtures/make_frontmatter_fixtures.py
cases = []
def case(name, text, parsed, edits):
    (D / f'{name}.md').write_bytes(text.encode('utf-8'))
    out = []
    for i, (op, exp) in enumerate(edits, 1):
        e = dict(op)
        if exp is None: e['expect'] = None
        elif exp == 'GONE': e['expect'] = 'gone'
        else:
            fn = f'{name}.{i}.md'; (D / 'expected' / fn).write_bytes(exp.encode('utf-8')); e['expect'] = fn
        out.append(e)
    cases.append({'name': name, 'file': f'{name}.md', 'parsed': parsed, 'edits': out})

def P(id, title, status='open', due='', remind=(), text='', repeat=''):
    return {'id': id, 'title': title, 'status': status, 'due': due, 'remind': list(remind), 'remind_text': text, 'repeat': repeat}

# 1 CRLF, scalar remind, unknown key
base = "---\r\nid: t-20261114-crlf\r\ntitle: Pay rent\r\nstatus: open\r\norder: 2\r\ndue: 2026-11-14\r\nremind: 2026-11-14 17:00\r\nflavor: mint\r\n---\r\nNotes line 1\r\n- [ ] item\r\n"
case('crlf-scalar', base, P('t-20261114-crlf', 'Pay rent', due='2026-11-14', remind=['2026-11-14 17:00']), [
  ({'op': 'remove', 'entry': '2026-11-14 17:00'}, base.replace("remind: 2026-11-14 17:00\r\n", "")),
  ({'op': 'replace', 'entry': '2026-11-14 17:00', 'to': '2026-11-14 17:10'}, base.replace("17:00", "17:10")),
  ({'op': 'add', 'to': '2026-11-14 09:00'}, base.replace("remind: 2026-11-14 17:00", "remind: [2026-11-14 09:00, 2026-11-14 17:00]")),
])
# 2 LF, odd key order, unknown keys in between, flow list
base = "---\nstatus: active\nid: t-20261114-odd\nx-source: claude\ntitle: Water the plants\nremind: [2026-11-15 08:00, 2026-11-14 18:30]\norder: 1.5\ndue: 2026-11-15\ncustom:\n  nested: true\n---\n\nBody.\n"
case('odd-order-list', base, P('t-20261114-odd', 'Water the plants', status='active', due='2026-11-15', remind=['2026-11-15 08:00', '2026-11-14 18:30']), [
  ({'op': 'remove', 'entry': '2026-11-14 18:30'}, base.replace("remind: [2026-11-15 08:00, 2026-11-14 18:30]", "remind: 2026-11-15 08:00")),
  ({'op': 'replace', 'entry': '2026-11-15 08:00', 'to': '2026-11-14 08:00'}, base.replace("remind: [2026-11-15 08:00, 2026-11-14 18:30]", "remind: [2026-11-14 08:00, 2026-11-14 18:30]")),
  ({'op': 'add', 'to': '2026-11-16 08:00'}, base.replace("remind: [2026-11-15 08:00, 2026-11-14 18:30]", "remind: [2026-11-14 18:30, 2026-11-15 08:00, 2026-11-16 08:00]")),
])
# 3 quoted title, quoted remind entry, remind_text after
base = "---\nid: t-20261114-quo\ntitle: 'Call: the dentist'\nstatus: open\norder: 1\ndue: 2026-11-20\nremind: \"2026-11-19 09:00\"\nremind_text: \"Call the dentist, it's about the crown\"\nrepeat: yearly\n---\n"
case('quoted', base, P('t-20261114-quo', 'Call: the dentist', due='2026-11-20', remind=['2026-11-19 09:00'], text="Call the dentist, it's about the crown", repeat='yearly'), [
  ({'op': 'remove', 'entry': '2026-11-19 09:00'}, base.replace('remind: "2026-11-19 09:00"\n', '')),
  ({'op': 'add', 'to': '2026-11-20 08:00'}, base.replace('remind: "2026-11-19 09:00"', 'remind: ["2026-11-19 09:00", 2026-11-20 08:00]')),
  ({'op': 'replace', 'entry': '2026-11-19 09:00', 'to': '2026-11-19 10:00'}, base.replace('remind: "2026-11-19 09:00"', 'remind: 2026-11-19 10:00')),
])
# 4 BOM, no remind: add after due
base = "﻿---\nid: t-20261114-bom\ntitle: Notepad file\nstatus: open\norder: 3\ndue: 2026-12-01\nrepeat: monthly\n---\nbody\n"
case('bom', base, P('t-20261114-bom', 'Notepad file', due='2026-12-01', repeat='monthly'), [
  ({'op': 'add', 'to': '2026-12-01 07:45'}, base.replace("due: 2026-12-01\n", "due: 2026-12-01\nremind: 2026-12-01 07:45\n")),
  ({'op': 'remove', 'entry': '2026-12-01 07:45'}, 'GONE'),
])
# 5 no trailing newline, no due: add after the last of id..order
base = "---\nid: t-20261114-nonl\ntitle: No newline\nstatus: open\norder: 1\nseries: t-x\ncompleted: 2026-11-01\n---"
case('no-trailing-newline', base, P('t-20261114-nonl', 'No newline'), [
  ({'op': 'add', 'to': '2026-11-14 12:00'}, base.replace("order: 1\n", "order: 1\nremind: 2026-11-14 12:00\n")),
])
# 6 invalid entry kept
base = "---\nid: t-20261114-bad\ntitle: Half bad\nstatus: open\nremind: [2026-11-14 17:00, next tuesday]\n---\n"
case('invalid-entry', base, P('t-20261114-bad', 'Half bad', remind=['2026-11-14 17:00', 'next tuesday']), [
  ({'op': 'remove', 'entry': '2026-11-14 17:00'}, base.replace("[2026-11-14 17:00, next tuesday]", "next tuesday")),
  ({'op': 'replace', 'entry': '2026-11-14 17:00', 'to': '2026-11-15 17:00'}, base.replace("[2026-11-14 17:00, next tuesday]", "[2026-11-15 17:00, next tuesday]")),
])
# 7 a whole invalid scalar
base = "---\nid: t-20261114-bad2\ntitle: All bad\nstatus: open\nremind: 2026-02-30 25:00\n---\n"
case('invalid-scalar', base, P('t-20261114-bad2', 'All bad', remind=['2026-02-30 25:00']), [
  ({'op': 'add', 'to': '2026-11-14 08:00'}, base.replace("remind: 2026-02-30 25:00", "remind: [2026-02-30 25:00, 2026-11-14 08:00]")),
])
# 8 body containing --- and a remind: line; block list in the frontmatter
base = "---\nid: t-20261114-body\ntitle: Dashes in the body\nstatus: open\nremind:\n  - 2026-11-20 08:00\n  - 2026-11-21 08:00\nzeta: last\n---\nIntro\n\n---\n\nremind: 2020-01-01 10:00\n---\n"
case('body-dashes-block-list', base, P('t-20261114-body', 'Dashes in the body', remind=['2026-11-20 08:00', '2026-11-21 08:00']), [
  ({'op': 'remove', 'entry': '2026-11-20 08:00'}, base.replace("remind:\n  - 2026-11-20 08:00\n  - 2026-11-21 08:00\n", "remind: 2026-11-21 08:00\n")),
  ({'op': 'remove', 'entry': '2026-11-21 08:00'}, base.replace("remind:\n  - 2026-11-20 08:00\n  - 2026-11-21 08:00\n", "remind: 2026-11-20 08:00\n")),
])
# 9 block list at column 0, CRLF, comment on a key line
base = "---\r\nid: t-20261114-col0\r\ntitle: Column zero\r\nstatus: open # a comment\r\nremind:\r\n- 2026-11-22 06:30\r\nrepeat: daily\r\ndue: 2026-11-22\r\n---\r\n"
case('crlf-col0-list', base, P('t-20261114-col0', 'Column zero', due='2026-11-22', remind=['2026-11-22 06:30'], repeat='daily'), [
  ({'op': 'replace', 'entry': '2026-11-22 06:30', 'to': '2026-11-22 06:45'}, base.replace("remind:\r\n- 2026-11-22 06:30\r\n", "remind: 2026-11-22 06:45\r\n")),
])
# 10 comment after the remind value
base = "---\nid: t-20261114-cmt\ntitle: Comment\nstatus: open\nremind: 2026-11-14 17:00 # ask Geoff\n---\n"
case('remind-comment', base, P('t-20261114-cmt', 'Comment', remind=['2026-11-14 17:00']), [
  ({'op': 'replace', 'entry': '2026-11-14 17:00', 'to': '2026-11-14 18:00'}, base.replace("remind: 2026-11-14 17:00 # ask Geoff", "remind: 2026-11-14 18:00")),
])
# 11 no frontmatter → refused
base = "Just a note\n\n- [ ] no frontmatter\n"
case('no-frontmatter', base, {'noFrontmatter': True}, [({'op': 'add', 'to': '2026-11-14 08:00'}, None)])
# 12 two remind keys → refused
base = "---\nid: t-20261114-dup\ntitle: Twice\nremind: 2026-11-14 08:00\nremind: 2026-11-14 09:00\n---\n"
case('duplicate-remind', base, {'unreadable': True}, [({'op': 'remove', 'entry': '2026-11-14 08:00'}, None)])
# 13 done task with reminder (never rings) and a map value for remind
base = "---\nid: t-20261114-done\ntitle: Finished\nstatus: done\nremind: 2026-11-14 08:00\ncompleted: 2026-11-13\n---\n"
case('done-task', base, P('t-20261114-done', 'Finished', status='done', remind=['2026-11-14 08:00']), [
  ({'op': 'remove', 'entry': '2026-11-14 08:00'}, base.replace("remind: 2026-11-14 08:00\n", "")),
])
base = "---\nid: t-20261114-map\ntitle: Map value\nstatus: open\nremind: {at: 2026-11-14 08:00}\n---\n"
case('map-value', base, {**P('t-20261114-map', 'Map value', remind=['{"at":"2026-11-14 08:00"}']), 'remindLine': None}, [({'op': 'add', 'to': '2026-11-14 09:00'}, None)])
# 14 empty remind key: remind: [] and add
base = "---\nid: t-20261114-empty\ntitle: Empty list\nstatus: open\ndue: 2026-11-30\nremind: []\nremind_text: Bring the forms\n---\n"
case('empty-list', base, P('t-20261114-empty', 'Empty list', due='2026-11-30', text='Bring the forms'), [
  ({'op': 'add', 'to': '2026-11-30 08:00'}, base.replace("remind: []", "remind: 2026-11-30 08:00")),
])
(D / 'cases.json').write_text(json.dumps({'about': 'Shared task-file contract fixtures (R2-22, rule 13). Run by tests/run_tests.py (group r222) and android/core unit tests; both must produce byte-identical output.', 'rules': ['Each edit applies to the original file on its own (not chained).', 'remove/replace an entry the file does not have → "gone" (nothing written).', 'expect null → the line-level edit refuses (no frontmatter, two remind keys, a value it cannot read); the caller must not write. For parsed.unreadable / parsed.noFrontmatter cases, apply the op to an empty list.', 'parsed.remindLine (when present) is what the line-level reader gives where it differs from YAML (null = unreadable value).'], 'cases': cases}, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
print(len(cases))
