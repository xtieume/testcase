#!/usr/bin/env python3
"""Decide whether a goal is met. The exit code IS the answer.

Reads `.testcases/goalrun/ledger.tsv` — one row per condition, tab-separated (UTF-8, BOM tolerated):

    id<TAB>what must be true<TAB>check<TAB>deliverable<TAB>break

`id`          unique.
`check`       a shell command, or `MANUAL:<owner>` when a human must decide. Never empty.
              A MANUAL row is decided by a person and cannot also name a deliverable.
`deliverable` optional path this row must have produced; `—`, `-` or empty means none.
`break`       optional command that plants the defect `check` exists to catch (`--verify`).
Extra columns are ignored.

Verdict per row:
  PASS  check exited 0 and (if named) the deliverable exists and changed since `.testcases/goalrun/baseline`
  FAIL  check exited non-zero, timed out, or the deliverable was not shipped
  WAIT  MANUAL row without a valid signature in `.testcases/goalrun/signoff.tsv`

Modes (mutually exclusive):
  --baseline [SHA]   record the commit this run is measured against (`.testcases/goalrun/baseline`)
  --sign ID --who W  a human signs a MANUAL row; W must be the row's owner
  --only A,B         run a subset; prints PHASE OK / PHASE NOT OK, never DONE
  --verify [A,B]     run each row's `break`, then its `check`, which must go red; restores
                     the tree with `git checkout -- . && git clean -fdq`, so it demands a
                     clean tree first. Break commands that touch state outside the repo
                     (databases, services, $HOME) are NOT undone.
  --lint-ledger      problems with the ledger itself

Exit 0 done / phase ok, 1 not done, 2 misuse or broken ledger.
"""
import argparse, collections, datetime, hashlib, os, signal, subprocess, sys, tempfile

GOAL_DIR = os.path.join('.testcases', 'goalrun')
LEDGER = os.path.join(GOAL_DIR, 'ledger.tsv')
SIGNOFF = os.path.join(GOAL_DIR, 'signoff.tsv')
BASELINE = os.path.join(GOAL_DIR, 'baseline')
NONE = ('', '—', '-')

Row = collections.namedtuple('Row', 'id what check deliverable brk')


class Misuse(Exception):
    """Wrong invocation or a broken ledger. main() turns it into exit 2."""


def load(path):
    if not os.path.exists(path):
        raise Misuse(f'no ledger at {path}')
    rows, seen = [], set()
    for raw in open(path, encoding='utf-8-sig'):
        line = raw.rstrip('\n')
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        parts = [p.strip() for p in line.split('\t')] + ['', '']
        if len(parts) < 5:
            raise Misuse(f'malformed row (need at least 3 tab-separated fields): {line!r}')
        rid, what, check, deliverable, brk = parts[:5]
        if not rid:
            raise Misuse(f'row with empty id: {line!r}')
        if rid in seen:
            raise Misuse(f'duplicate id {rid!r} — every row needs its own name')
        if not check:
            raise Misuse(f'{rid}: empty check — `sh -c ""` exits 0 and decides nothing')
        if check == 'MANUAL' or check.startswith('MANUAL '):
            raise Misuse(f'{rid}: MANUAL row needs an owner — write MANUAL:<owner>')
        deliverable = '' if deliverable in NONE else deliverable
        if check.startswith('MANUAL:') and deliverable:
            raise Misuse(f'{rid}: a MANUAL row is decided by a person and cannot also name '
                         f'a deliverable — a row belongs to a decider or a file, not both')
        seen.add(rid)
        rows.append(Row(rid, what, check, deliverable, '' if brk in NONE else brk))
    return rows


def owner_of(row):
    return ' '.join(row.check.partition(':')[2].split())


def what_hash(what):
    return hashlib.sha256(what.strip().encode()).hexdigest()[:12]


def _kill_group(p):
    """Kill the check's whole session; the race with its own exit is not an error."""
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    p.wait()


def run_check(cmd, timeout=1800):
    """Return (ok, one-line summary). A check passes only on exit 0.

    Output goes to a tempfile, not a pipe, so a backgrounded child that inherits stdout
    cannot hold the run open; the whole session is killed on timeout."""
    with tempfile.TemporaryFile() as out:
        p = subprocess.Popen(cmd, shell=True, stdin=subprocess.DEVNULL, stdout=out,
                             stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = p.wait(timeout)
        except subprocess.TimeoutExpired:
            _kill_group(p)
            return False, f'timed out after {timeout}s'
        except KeyboardInterrupt:
            _kill_group(p)
            raise
        out.seek(0)
        text = out.read().decode('utf-8', errors='replace')
    tail = [l.strip() for l in text.splitlines() if l.strip()]
    return code == 0, (tail[-1][:96] if tail else f'exit {code}')


def _git(*args, cwd=None):
    p = subprocess.run(('git',) + args, cwd=cwd, capture_output=True, text=True)
    return p.stdout.splitlines() if p.returncode == 0 else None


def resolve_commit(sha, cwd=None):
    out = _git('rev-parse', '--verify', '--quiet', f'{sha}^{{commit}}', cwd=cwd)
    if not out:
        raise Misuse(f'{sha!r} is not a commit in this repository')
    return out[0].strip()


def read_baseline(path=BASELINE, cwd=None):
    if not os.path.exists(path):
        return None
    sha = open(path, encoding='utf-8').read().strip()
    return resolve_commit(sha, cwd) if sha else None


def changed_paths(baseline, cwd=None):
    """Every path touched since baseline across the COMPLETE working tree."""
    q = ('-c', 'core.quotePath=false')
    paths = set()
    for args in (('diff', '--name-only', baseline), ('diff', '--name-only', '--cached'),
                 ('diff', '--name-only'), ('ls-files', '--others', '--exclude-standard')):
        paths.update(_git(*q, *args, cwd=cwd) or [])
    return {p.strip() for p in paths if p.strip()}


def not_shipped(path, touched, cwd=None):
    """'' when the deliverable exists and changed since baseline, else the reason."""
    norm = os.path.normpath(path)
    if os.path.isabs(norm) or norm.split(os.sep)[0] == '..':
        return 'path leaves the repository'
    if not os.path.lexists(os.path.join(cwd or '.', norm)):
        return 'does not exist'
    if norm in touched or any(t.startswith(norm + '/') for t in touched):
        return ''
    return 'unchanged since baseline'


def load_signatures(path=SIGNOFF):
    """id -> {who, date, what_hash, note}. Last line for an id wins."""
    sigs = {}
    if not os.path.exists(path):
        return sigs
    for raw in open(path, encoding='utf-8-sig'):
        line = raw.rstrip('\n')
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        parts = [p.strip() for p in line.split('\t')] + ['']
        if len(parts) < 5:
            continue
        sigs[parts[0]] = dict(zip(('who', 'date', 'what_hash', 'note'), parts[1:5]))
    return sigs


def decide(row, signatures, touched=frozenset(), timeout=1800, cwd=None):
    """Resolve one row to (status, note); status is PASS, FAIL or WAIT."""
    if row.check.startswith('MANUAL:'):
        owner = owner_of(row) or 'unassigned'
        sig = signatures.get(row.id)
        if not sig:
            return 'WAIT', f'awaiting {owner}'
        if sig['what_hash'] != what_hash(row.what):
            return 'WAIT', f'awaiting {owner} — signature is for an older wording'
        return 'PASS', f'signed by {sig["who"]} on {sig["date"]} — {sig["note"]}'
    ok, note = run_check(row.check, timeout)
    if not ok:
        return 'FAIL', note
    if row.deliverable:
        why = not_shipped(row.deliverable, touched, cwd)
        if why:
            return 'FAIL', f'deliverable not shipped: {row.deliverable} — {why}'
    return 'PASS', note


def report(rows, signatures, touched, timeout):
    """Print the table. Return [(status, row)]."""
    width = max(len(r.id) for r in rows)
    results = []
    for row in rows:
        status, note = decide(row, signatures, touched, timeout)
        print(f'{row.id:<{width}}  {status}  {row.what} — {note}')
        results.append((status, row))
    return results


def summary(results):
    failing = [r.id for s, r in results if s == 'FAIL']
    waiting = collections.OrderedDict()
    for s, r in results:
        if s == 'WAIT':
            waiting.setdefault(owner_of(r) or 'unassigned', []).append(r.id)
    parts = [f'{len(failing)} failing ({", ".join(failing)})'] if failing else []
    parts += [f'{len(ids)} waiting on {who} ({", ".join(ids)})' for who, ids in waiting.items()]
    return ', '.join(parts)


def sign(rows, row_id, who, note, path=SIGNOFF, today=None):
    """Append a human signature. The signer must be the row's owner."""
    row = next((r for r in rows if r.id == row_id), None)
    if row is None:
        raise Misuse(f'no row {row_id!r} in the ledger')
    if not row.check.startswith('MANUAL:'):
        raise Misuse(f'{row_id} is decided by its check, not by a signature')
    who = ' '.join((who or '').split())
    if not who:
        raise Misuse('--sign needs --who <person>; an unsigned approval is not one')
    owner = owner_of(row)
    if who != owner:
        raise Misuse(f'{row_id} is owned by {owner or "nobody"}; --who {who} cannot sign it')
    note = ' '.join((note or '').split())
    today = today or datetime.date.today().isoformat()
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    new = not os.path.exists(path)
    with open(path, 'a', encoding='utf-8') as f:
        if new:
            f.write('# id\twho\tdate\twhat_hash\tnote\n')
        f.write(f'{row_id}\t{who}\t{today}\t{what_hash(row.what)}\t{note}\n')
    return today


def lint(rows, signatures=None, has_baseline=True):
    """Problems with the ledger itself. Empty list means the ledger measures something."""
    problems = []
    if not rows:
        return ['ledger has no rows — nothing is being measured']
    manual = [r for r in rows if r.check.startswith('MANUAL:')]
    for row in manual:
        if not owner_of(row):
            problems.append(f'{row.id}: MANUAL with no owner — name who decides')
    # one subjective row is normal — there is usually something a human must eyeball.
    # more than one is worth a second look, and past 30% of rows the ledger is a
    # list of promises — hence both conditions below.
    if len(manual) > 1 and len(manual) / len(rows) > 0.30:
        problems.append(f'{len(manual)} of {len(rows)} rows are MANUAL (>30%) — this ledger '
                        f'is mostly promises, not checks')
    shipping = [r.id for r in rows if r.deliverable]
    if shipping and not has_baseline:
        problems.append(f'rows {", ".join(shipping)} name deliverables but no baseline is '
                        f'recorded — run --baseline first')
    ids = {r.id for r in rows}
    for sid in (signatures or {}):
        if sid not in ids:
            problems.append(f'signature for {sid!r} but no such row — stale signoff.tsv')
    return problems


def verify(rows, ids, timeout, cwd=None):
    """Plant each row's break, prove its check goes red, restore. Return True if all did."""
    if ids:
        rows = select(rows, ids)
    all_ok = True
    for row in rows:
        if not row.brk:
            print(f'skip {row.id} — no break column')
            continue
        if row.check.startswith('MANUAL:'):
            print(f'skip {row.id} — MANUAL row')
            continue
        dirty = _git('status', '--porcelain', cwd=cwd)
        if dirty:
            top = GOAL_DIR.split(os.sep)[0] + '/'   # git lists an untracked dir as `?? .testcases/`
            hint = ('commit or stash first' if not all(top in l for l in dirty) else
                    f'add `/{top}` to .git/info/exclude — {GOAL_DIR} is what is dirty')
            raise Misuse(f'--verify needs a clean working tree; {hint}')
        planted, why = run_check(row.brk, timeout)
        if not planted:
            subprocess.run('git -c core.quotePath=false checkout -- . && git clean -fdq',
                           shell=True, cwd=cwd, check=True)
            all_ok = False
            print(f'BREAK FAILED {row.id} — the break command itself failed: {why}')
            continue
        ok, note = run_check(row.check, timeout)
        subprocess.run('git -c core.quotePath=false checkout -- . && git clean -fdq',
                       shell=True, cwd=cwd, check=True)
        if ok:
            all_ok = False
            print(f'HOLLOW {row.id} — check still passed after break; it does not test what '
                  f'it claims')
        else:
            print(f'VERIFIED {row.id} — {note}')
    return all_ok


def select(rows, ids):
    wanted = [s.strip() for s in ids.split(',') if s.strip()]
    if not wanted:
        raise Misuse('no row ids given — name at least one id from the ledger')
    known = {r.id for r in rows}
    unknown = [w for w in wanted if w not in known]
    if unknown:
        raise Misuse(f'no such row(s) in the ledger: {", ".join(unknown)}')
    return [r for r in rows if r.id in wanted]


def main():
    signal.signal(signal.SIGTERM, signal.default_int_handler)  # so SIGTERM kills the check too
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--ledger', default=LEDGER)
    ap.add_argument('--timeout', type=int, default=1800, help='seconds per check')
    ap.add_argument('--who')
    ap.add_argument('--note', default='')
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--only', metavar='A,B', help='run a subset of rows')
    mode.add_argument('--sign', metavar='ID')
    mode.add_argument('--baseline', nargs='?', const='HEAD', metavar='SHA')
    mode.add_argument('--lint-ledger', action='store_true')
    mode.add_argument('--verify', nargs='?', const='', metavar='A,B')
    a = ap.parse_args()
    try:
        return run(a)
    except Misuse as e:
        sys.stderr.write(f'{e}\n')
        return 2
    except Exception as e:  # ponytail: any crash is a broken ledger or setup, never a verdict
        sys.stderr.write(f'{type(e).__name__}: {e}\n')
        return 2


def run(a):
    if (a.who or a.note) and not a.sign:
        raise Misuse('--who/--note only mean something with --sign')

    if a.baseline:
        sha = resolve_commit(a.baseline)
        os.makedirs(GOAL_DIR, exist_ok=True)
        open(BASELINE, 'w', encoding='utf-8').write(sha + '\n')
        print(f'baseline {sha} -> {BASELINE}')
        return 0

    rows = load(a.ledger)

    if a.sign:
        date = sign(rows, a.sign, a.who, a.note)
        print(f'{a.sign} signed by {" ".join(a.who.split())} on {date}')
        return 0

    baseline = read_baseline()

    if a.lint_ledger:
        problems = lint(rows, load_signatures(), has_baseline=baseline is not None)
        for p in problems:
            print(p)
        print('ledger measures something' if not problems else
              f'{len(problems)} problem(s) with the ledger itself')
        return 1 if problems else 0

    if not rows:
        raise Misuse('ledger has no rows')

    if a.verify is not None:
        return 0 if verify(rows, a.verify, a.timeout) else 1

    chosen = select(rows, a.only) if a.only else rows
    shipping = [r.id for r in chosen if r.deliverable]
    if shipping and baseline is None:
        raise Misuse(f'rows {", ".join(shipping)} name deliverables but no baseline is '
                     f'recorded — run --baseline first')
    touched = changed_paths(baseline) if baseline else frozenset()

    results = report(chosen, load_signatures(), touched, a.timeout)
    passed = sum(1 for s, _ in results if s == 'PASS')
    print()
    if a.only:
        tail = f'({len(chosen)} of {len(rows)} in ledger)'
        if passed == len(chosen):
            print(f'PHASE OK — {passed} rows pass {tail}')
            return 0
        print(f'PHASE NOT OK — {summary(results)} {tail}')
        return 1
    if passed == len(chosen):
        print(f'DONE — all {passed} checks pass')
        return 0
    print(f'NOT DONE — {summary(results)}')
    return 1


if __name__ == '__main__':
    sys.exit(main())
