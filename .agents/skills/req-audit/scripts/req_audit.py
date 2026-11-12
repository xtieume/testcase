#!/usr/bin/env python3
"""Render REQ-AUDIT.html for one named goalrun run: a status per requirement from the run's
ledger, its newest recorded `--verify` result and the audit folder's evidence index.

It never runs a check. Statuses are only as fresh as the last `--verify`; the JSON it prints
says when that result no longer matches the workspace."""
import argparse
import html
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

GOALRUN_SCRIPTS = Path(__file__).resolve().parents[2] / 'goalrun' / 'scripts'
sys.path.insert(0, str(GOALRUN_SCRIPTS))
import goalrun  # noqa: E402
import run_cli  # noqa: E402
from run_store import Store  # noqa: E402

MEDIA = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.webm', '.mp4')
BROKEN = ('FAIL', 'HOLLOW', 'BREAK FAILED', 'STUCK', 'BLAST')
LABELS = {'PASS': '✅ PASS', 'SIGNED': '✍️ SIGNED (manual)', 'AWAITING_SIGN': '⏳ AWAITING SIGN-OFF',
          'DEVIATION': '🔴 DEVIATION', 'UNPROVEN': '🟠 UNPROVEN', 'CONFIRM': '❓ CONFIRM',
          'NO_TEST': '🟡 NO_TEST', 'MISSING': '⬜ MISSING', 'OBSOLETE': '⚪ OBSOLETE'}


def esc(value):
    return html.escape(str(value if value not in (None, '') else '—'), quote=True)


def jsonl(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def localized(record, key):
    """`key` plus every `key_<lang>` translation, e.g. caption, caption_vi, caption_ja."""
    out = [('', record[key])] if record.get(key) else []
    return out + [(k[-2:], v) for k, v in sorted(record.items()) if re.fullmatch(re.escape(key) + r'_[a-z]{2}', k) and v]


def requirements(audit, goal_dir, rows):
    reqs = jsonl(audit / 'data' / 'reqs.jsonl')
    if not reqs:
        text = {}
        reqs_txt = goal_dir / 'reqs.txt'
        for line in reqs_txt.read_text(encoding='utf-8-sig').splitlines():
            head, _, desc = line.partition(':')
            text.setdefault(head.strip(), desc.strip())
        reqs = [{'id': rid, 'req': text.get(rid) or next((r.what for r in rows if r.id == rid), ''), 'src': 'reqs.txt'}
                for rid in goalrun.read_requirements(str(reqs_txt))]
    ids = [r.get('id') for r in reqs]
    if not ids or None in ids or len(set(ids)) != len(ids):
        raise SystemExit('requirement list is empty, has a record without id, or repeats an id')
    return reqs


def verify_subset(argv):
    """None for a whole-ledger --verify, the row list for a subset."""
    for i, arg in enumerate(argv):
        if arg.startswith('--verify='):
            return arg.split('=', 1)[1] or None
        if arg == '--verify':
            following = argv[i + 1] if i + 1 < len(argv) else ''
            return None if not following or following.startswith('-') else following
    return None


def latest_verify(store, view):
    results = []
    for path in Path(view['paths']['run_dir'], 'evidence').glob('*.json'):
        if '-check-' not in path.name:
            result = json.loads(path.read_text(encoding='utf-8'))
            if any(a == '--verify' or a.startswith('--verify=') for a in result.get('argv', [])):
                results.append(result)
    if not results:
        return None
    result = max(results, key=lambda r: r.get('at', 0))
    if result.get('state') != 'completed':
        stale = ['unfinished']
    else:
        current = run_cli.fingerprint(store, view, goalrun)
        # runtime digests this process's environment, which differs from the shell that ran --verify
        stale = [g for g in current if g != 'runtime' and result['fingerprint'].get(g) != current[g]]
    return {'id': result['id'], 'at': result.get('at'), 'exit_code': result.get('exit_code'),
            'subset': verify_subset(result.get('argv', [])), 'rows': result.get('rows', {}), 'stale_because': stale}


def evidence_index(audit):
    by_req = defaultdict(dict)
    for index in sorted((audit / 'data').glob('evidence*.jsonl')):
        for item in jsonl(index):
            for rid in item.get('reqs', []):
                by_req[rid][item.get('file', '')] = item
    return by_req


def media_links(audit, items, fresh):
    def is_fresh(m):
        return bool(fresh) and str(m.get('captured', '')).startswith(fresh)
    has_fresh = any(is_fresh(m) and not m.get('stale') for m in items.values())
    links, real, first = [], False, None
    for name, meta in items.items():
        if has_fresh and not is_fresh(meta):
            continue
        rel = Path(name)
        if rel.parts[:1] == ('evidence',):
            rel = Path(*rel.parts[1:])
        path = audit / 'evidence' / rel
        if rel.is_absolute() or '..' in rel.parts or path.suffix.lower() not in MEDIA or not path.is_file():
            continue
        proof = not (meta.get('spec_only') or meta.get('stale'))
        real |= proof
        href = 'evidence/' + rel.as_posix()
        first = first or (href if proof else None)
        lines = [f'{lang + ": " if lang else ""}{text}' for lang, text in localized(meta, 'caption')]
        lines.append(('proof' if proof else 'not proof (spec excerpt or stale)') + f' · {meta.get("captured", "")} · {name}')
        links.append(f"<a href='{esc(href)}' title='{esc(chr(10).join(lines))}'>{esc(rel.name)}</a>")
    return links, real, first


def classify(record, entries, real_media):
    if str(record.get('status', '')).upper() == 'OBSOLETE':
        return 'OBSOLETE'
    if str(record.get('status', '')).upper() == 'CONFIRM':
        return 'CONFIRM'
    states = [e['status'] for e in entries]
    if any(s in BROKEN for s in states):
        return 'DEVIATION'
    if entries and all(s == 'VERIFIED' for s in states):
        return 'PASS' if any(not e['check'].startswith('MANUAL:') for e in entries) else 'SIGNED'
    if 'WAIT' in states:
        return 'AWAITING_SIGN'
    if entries:
        return 'UNPROVEN'
    return 'NO_TEST' if real_media else 'MISSING'


def texts(record, key, cls=''):
    return ''.join(f"<div class='{cls}'>{esc((lang + ': ') if lang else '')}{esc(t)}</div>" for lang, t in localized(record, key))


def build(root, run_id, audit=None, out=None, title=None, fresh=None):
    store = Store(root)
    view = store.inspect(run_id)
    goal_dir = Path(view['paths']['goalrun_dir'])
    audit = Path(audit).resolve() if audit else Path(view['paths']['run_dir']) / 'audit'
    out = Path(out).resolve() if out else audit / 'REQ-AUDIT.html'
    title = title or f'Requirement audit · {run_id}'
    rows = goalrun.load(str(goal_dir / 'ledger.tsv'))
    reqs = requirements(audit, goal_dir, rows)
    verify = latest_verify(store, view)
    outcome = verify['rows'] if verify else {}
    by_req = evidence_index(audit)
    adequacy_path = audit / 'data' / 'adequacy.json'
    adequacy = json.loads(adequacy_path.read_text(encoding='utf-8')) if adequacy_path.is_file() else {}

    status_counts, gaps, groups, proposals = Counter(), {}, defaultdict(list), []
    for r in reqs:
        rid = r['id']
        token = re.compile(rf'(?<![\w.-]){re.escape(rid)}(?![\w.-])')  # goalrun's own row ↔ requirement match
        entries = [{'id': row.id, 'check': row.check, 'brk': row.brk, **outcome.get(row.id, {'status': 'not run', 'note': ''})}
                   for row in rows if token.search(row.id) or token.search(row.what)]
        links, real_media, first = media_links(audit, by_req.get(rid, {}), fresh)
        status = classify(r, entries, real_media)
        status_counts[status] += 1
        missing = [name for name, ok in (('verified break', entries and all(e['status'] == 'VERIFIED' for e in entries)),
                                         ('automated test', any(not e['check'].startswith('MANUAL:') for e in entries)),
                                         ('evidence', real_media)) if not ok]
        if missing and status != 'OBSOLETE':
            gaps[rid] = missing
        decision = ''
        if r.get('proposal'):
            kind = 'decided' if r.get('decided_by') else 'draft'
            badge = f"Decided by {esc(r['decided_by'])}" if kind == 'decided' else 'Proposal · not yet decided'
            href = 'evidence/' + r['proposal_evidence'] if r.get('proposal_evidence') else first
            proposals.append((r.get('human_owner') or 'unassigned', rid, r.get('req'), localized(r, 'proposal'), href, kind))
            decision = (f"<div class='decision {kind}'><span class='tag'>{badge}</span><div><strong>Confirmer:</strong> {esc(r.get('human_owner'))}</div>"
                        f"{texts(r, 'proposal')}<small>Source: {esc(r.get('decision_source'))}</small></div>")
        elif r.get('dev_decision'):
            decision = f"<div class='decision draft'><span class='tag'>Developer decision · not yet confirmed</span>{texts(r, 'dev_decision')}</div>"
        human = f"<div class='human'><span class='tag'>Needs a human check</span><div>{esc(r['human_check'])}</div></div>" if r.get('human_check') else ''
        ad = adequacy.get(rid)
        enough = '' if status == 'OBSOLETE' else (
            '<small>Evidence adequate</small>' if ad and ad.get('yes') else
            '<small>Evidence not adequate</small>' + ''.join(f'<small>{esc(b)}</small>' for b in (ad or {}).get('blockers', [])[:2]))
        checks = ''.join(f"<div title='{esc(e['check'])}'><strong>{esc(e['id'])}</strong> {esc(e['check'][:100])}"
                         f"<small>goalrun: {esc(e['status'])}{' — ' + esc(e['note']) if e.get('note') else ''}</small></div>"
                         for e in entries) or 'No ledger row'
        reason = f"<small>Obsolete: {esc(r.get('obsolete_reason'))}</small>" if status == 'OBSOLETE' else ''
        group = 'Obsolete' if status == 'OBSOLETE' else (r.get('area') or 'Other')
        groups[group].append(
            f"<tr class='{'obsolete' if status == 'OBSOLETE' else ''}'><td><strong>{esc(rid)}</strong><div>{esc(r.get('req'))}</div>"
            f"{decision}{human}<small>{esc(r.get('src'))}</small>{reason}</td><td><strong>{esc(LABELS[status])}</strong>{enough}</td>"
            f"<td>{checks}</td><td>{' '.join(links) or 'No screenshot or video'}</td></tr>")

    summary = ''.join(f"<tr><td>{esc(label)}</td><td class='n'>{status_counts[key]}</td></tr>" for key, label in LABELS.items())
    owners = defaultdict(list)
    for owner, rid, item, proposal, href, kind in proposals:
        owners[owner].append(f"<tr><td><strong>{esc(rid)}</strong></td><td>{esc(item)}</td><td>{''.join(f'<div>{esc(t)}</div>' for _, t in proposal)}</td>"
                             f"<td>{f'<a href={chr(39)}{esc(href)}{chr(39)}>evidence</a>' if href else '—'}</td><td>{'decided, sign only' if kind == 'decided' else 'proposal'}</td></tr>")
    needs = ''.join(f"<details open><summary>{esc(owner)} · {len(items)} REQ</summary><table><thead><tr><th>REQ</th><th>Item</th><th>Proposal</th><th>Evidence</th><th>Kind</th></tr></thead><tbody>{''.join(items)}</tbody></table></details>"
                    for owner, items in sorted(owners.items()))
    needs = f'<h2>Awaiting a human decision ({len(proposals)} REQ)</h2>{needs}' if proposals else ''
    order = sorted((g for g in groups if g != 'Obsolete'), key=str.casefold) + (['Obsolete'] if 'Obsolete' in groups else [])
    tables = ''.join(f"<details{'' if g == 'Obsolete' else ' open'}><summary>{esc(g)} · {len(groups[g])} REQ</summary><table><thead><tr>"
                     f"<th>Requirement</th><th>Status</th><th>Ledger rows</th><th>Evidence</th></tr></thead><tbody>{''.join(groups[g])}</tbody></table></details>"
                     for g in order)
    if verify:
        when = datetime.fromtimestamp(verify['at']).strftime('%Y-%m-%d %H:%M') if verify.get('at') else '?'
        scope = f"rows {verify['subset']}" if verify['subset'] else 'whole ledger'
        source = f"Statuses from goalrun --verify ({scope}) at {esc(when)}, exit {esc(verify['exit_code'])}."
        if verify['stale_because']:
            source += f" <strong>⚠ Stale: {esc(', '.join(verify['stale_because']))} changed since — rerun --verify.</strong>"
    else:
        source = '<strong>⚠ This run has no recorded --verify: every ledger row shows "not run".</strong>'
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>
body{{margin:0;background:#f4f6f4;color:#22302b;font:13px/1.45 system-ui,sans-serif}}main{{max-width:1800px;margin:auto;padding:16px}}h1{{font-size:20px;margin:0 0 8px}}h2{{font-size:16px}}
details{{margin:0 0 10px;overflow:auto}}summary{{font-weight:700;cursor:pointer;padding:6px;background:#e5eee9}}table{{border-collapse:collapse;width:100%;background:#fff}}
th,td{{border:1px solid #dbe3de;padding:4px 6px;font-size:12px;vertical-align:top;text-align:left;overflow-wrap:anywhere}}th{{background:#eef4f0}}table.sum{{width:auto;min-width:320px}}td.n{{text-align:right;font-variant-numeric:tabular-nums}}
small{{display:block;color:#66726c;font-size:11px}}.obsolete{{color:#858b87;background:#ededed}}.tag{{font-size:11px;font-weight:700;padding:1px 5px;border-radius:3px;background:#fce3a1;color:#704700}}
.decision,.human{{padding:5px;margin-top:4px;background:#fff8e6}}.decision.decided{{background:#eaf5ec}}.decision.decided .tag{{background:#bfe3c6;color:#1d5a2a}}.human{{background:#f0f1f1}}.human .tag{{background:#dfe2e1;color:#444}}
a.thumb{{display:inline-block;position:relative;margin:2px;line-height:0}}a.thumb img,a.thumb video{{height:64px;width:96px;object-fit:cover;object-position:top left;border:1px solid #c5d0cb;border-radius:4px;background:#fff}}
.play{{position:absolute;left:4px;bottom:4px;font-size:11px;line-height:1;color:#fff;background:rgba(0,0,0,.55);padding:2px 4px;border-radius:3px}}
#pop{{display:none;position:fixed;z-index:9;pointer-events:none;background:#fff;border:1px solid #9aa;box-shadow:0 6px 24px rgba(0,0,0,.35);padding:4px;border-radius:4px}}#pop>*{{display:block;max-width:min(1100px,70vw);max-height:85vh}}
</style></head><body><main><h1>{esc(title)}</h1><p>{source}</p><table class="sum"><thead><tr><th>Status</th><th>REQ</th></tr></thead><tbody>{summary}</tbody></table>
{needs}{tables}<div id="pop"></div><script>
(function(){{
  var pop=document.getElementById('pop'),IMG=/[.](png|jpe?g|gif|webp)$/i,VID=/[.](webm|mp4)$/i;
  function media(href,thumb){{
    var el=document.createElement(IMG.test(href)?'img':'video');
    el.src=href+(thumb&&el.tagName==='VIDEO'?'#t=0.5':'');
    if(el.tagName==='VIDEO'){{el.muted=true;if(thumb)el.preload='metadata';else{{el.autoplay=true;el.loop=true;}}}}else if(thumb)el.loading='lazy';
    return el;
  }}
  function place(e){{
    var x=e.clientX+18,y=e.clientY+18;
    if(x+pop.offsetWidth>innerWidth-8)x=Math.max(8,e.clientX-pop.offsetWidth-18);
    if(y+pop.offsetHeight>innerHeight-8)y=Math.max(8,innerHeight-pop.offsetHeight-8);
    pop.style.left=x+'px';pop.style.top=y+'px';
  }}
  document.querySelectorAll('a[href]').forEach(function(a){{
    var href=a.getAttribute('href');
    if(!IMG.test(href)&&!VID.test(href))return;
    a.classList.add('thumb');a.textContent='';a.appendChild(media(href,true));
    if(VID.test(href)){{var p=document.createElement('span');p.className='play';p.textContent='▶';a.appendChild(p);}}
    a.addEventListener('mouseenter',function(e){{
      pop.replaceChildren(media(href,false));pop.style.display='block';place(e);
      pop.firstChild.addEventListener('load',function(){{place(e);}});pop.firstChild.addEventListener('loadedmetadata',function(){{place(e);}});
    }});
    a.addEventListener('mousemove',place);
    a.addEventListener('mouseleave',function(){{pop.style.display='none';pop.replaceChildren();}});
  }});
}})();
</script></main></body></html>'''
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding='utf-8')
    return {'out': str(out), 'status_counts': dict(status_counts), 'gaps': gaps,
            'verify': None if not verify else {k: v for k, v in verify.items() if k != 'rows'}}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('run', help='named goalrun run id')
    ap.add_argument('--root', default='.', help='workspace root holding .testcases/ (default: cwd)')
    ap.add_argument('--audit-dir', help='folder with data/ and evidence/ (default: <run_dir>/audit)')
    ap.add_argument('--out', help='output HTML (default: <audit-dir>/REQ-AUDIT.html)')
    ap.add_argument('--title')
    ap.add_argument('--fresh', metavar='YYYY-MM-DD', help='once a REQ has captures from this date, hide its older ones')
    a = ap.parse_args()
    print(json.dumps(build(a.root, a.run, a.audit_dir, a.out, a.title, a.fresh), ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
