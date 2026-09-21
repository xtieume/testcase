#!/usr/bin/env python3
"""Decide whether a goal is met. The exit code IS the answer.

Reads `.testcases/goalrun/ledger.tsv` — one row per condition, tab-separated (UTF-8, BOM tolerated):

    id<TAB>what must be true<TAB>check<TAB>deliverable<TAB>break

`id`          unique.
`check`       a shell command, or `MANUAL:<owner>` when a human must decide. Never empty.
              A MANUAL row is decided by a person and cannot also name a deliverable.
`deliverable` optional path this row must have produced; `—`, `-` or empty means none.
`break`       the command that plants the defect `check` exists to catch (`--verify`).
              A row without one has never gone red; `--lint-ledger` says so unless the
              ledger waives it with a comment line `# verify-ok: <id> — <reason>` — the
              legitimate reason being that the test was written first and its red phase
              was already witnessed by hand.
Extra columns are ignored.

Verdict per row:
  PASS  check exited 0 and (if named) the deliverable's content differs from the baseline
  FAIL  check exited non-zero, timed out, or the deliverable was not shipped
  WAIT  MANUAL row without a valid signature in `.testcases/goalrun/signoff.tsv`

Modes (mutually exclusive):
  --baseline          record the content of every file in the tree, in
                       `.testcases/goalrun/baseline.json`. Taken once, before the first
                       edit, and before the ledger exists; refused when one is present
                       (--reset replaces it). A deliverable ships when it differs from
                       this record, or was not in it
  --sign ID --who W   a human signs a MANUAL row; W must be the row's owner
  --only A,B          run a subset; prints PHASE OK / PHASE NOT OK, never DONE
  --verify [A,B]      for each row: clone the tree into a disposable temp directory, plant
                       the row's `break` inside the clone, run the row's `check` there too,
                       and demand red — then throw the clone away. The working tree is only
                       ever read
  --lint-ledger       problems with the ledger itself; with --requirements FILE it also
                       names requirements no row measures (waive: `# no-row-ok: <id> — <why>`)

Only one goalrun runs checks in a tree at a time (`.testcases/goalrun.lock`): a check racing
another build goes red for reasons that are not the code.

Exit 0 done / phase ok, 1 not done, 2 misuse or broken ledger.
"""
import argparse, collections, datetime, fcntl, hashlib, json, os, re, shutil, \
    signal, subprocess, sys, tempfile, time

GOAL_DIR = os.path.join('.testcases', 'goalrun')
LEDGER = os.path.join(GOAL_DIR, 'ledger.tsv')
SIGNOFF = os.path.join(GOAL_DIR, 'signoff.tsv')
BASELINE = os.path.join(GOAL_DIR, 'baseline.json')
# beside the ledger directory, not inside it: a lock that lived under a directory a break
# could rewrite would be a lock that blinks out from under a racing run
LOCK = os.path.join('.testcases', 'goalrun.lock')
NONE = ('', '—', '-')
SWEEP_BUDGET = 900      # seconds of sweeping (not of the run) the default proof may spend
NO_BUDGET = -2          # bare `--blast`: sweep everything. Not 0 — `--blast 0` is 0 seconds

# heavy or regenerable directories a clone skips outright — `.git` carries the whole history
# nothing in a check needs, and the rest are caches any build regenerates on its own. Build
# outputs like obj/, bin/, target/ are deliberately NOT here: a check that compiles needs
# them to stay incremental, so cloning them (not skipping them) is the point of the CoW copy
CLONE_SKIP = {'.git', 'node_modules', '__pycache__', '.venv', '.tox', '.mypy_cache'}
CLONE_PREFIX = 'goalrun-clone-'
# a check that invokes one of these is a test; the zero-tests gate and the lint's
# searches-text rule both key off it, so a lint that echoes "0 tests failed" is not a runner
# that matched nothing, and a grep piped after a runner is still a test
RUNNER_RE = re.compile(r'\b(pytest|unittest|jest|vitest|mocha|rspec|phpunit|go\s+test|'
                       r'cargo\s+test|dotnet\s+test|mvn|gradle|npm\s+test|yarn\s+test|'
                       r'pnpm\s+test)\b')

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


def waivers(path):
    """`# verify-ok: ID — reason` / `# no-row-ok: ID — reason` comment lines in the ledger.

    A gap the author accepted on purpose, with the reason written down. Silence is not a
    waiver, and a waiver with no reason is silence with a prefix — here that line is ignored,
    so the gap it meant to excuse is reported.

    `no-row-ok:` is deliberately not spelled `coverage-ok:`, which `testcase` uses for a
    different thing: there it excuses a requirement whose cases are all success-path, and it
    refuses to excuse a requirement with no case at all. Here it excuses a requirement with no
    row. One marker with opposite preconditions in two halves of one pipeline is a trap."""
    out = {'verify-ok': {}, 'no-row-ok': {}}
    if not os.path.exists(path):
        return out
    # the separator must be surrounded by spaces: ids contain `-` (REQ-A-001), so a looser
    # pattern lets a reasonless waiver split its own id and pass `001` off as the reason
    pat = re.compile(r'\s*#\s*(verify-ok|no-row-ok)\s*:\s*(\S+)\s+[—-]\s+(\S.*?)\s*$')
    with open(path, encoding='utf-8-sig') as f:
        for raw in f:
            m = pat.match(raw)
            if m:
                out[m.group(1)][m.group(2)] = m.group(3)
    return out


def read_requirements(path):
    """Requirement ids, one per line. `#` comments and `ID: description` both fine."""
    ids, seen = [], set()
    with open(path, encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                head, sep, desc = line.partition(':')
                # `REQ-A-001 REQ-A-002` — with or without a trailing description — would
                # silently measure only the first, and a requirement missing from this file
                # is the blind spot the gate has
                if len(head.split()) > 1:
                    raise Misuse(f'{path}: {line!r} holds more than one id — one per line, or '
                                 f'`REQ-A-001: description`')
                rid = head.strip()
                if not re.match(r'^[A-Za-z0-9][\w.-]*$', rid) or not re.search(r'[A-Za-z]', rid):
                    raise Misuse(f'{path}: {rid!r} is not a requirement id — one id per line, '
                                 f'`REQ-A-001: description` or bare')
                if rid not in seen:
                    seen.add(rid)
                    ids.append(rid)
    if not ids:
        raise Misuse(f'no requirement ids in {path} — an empty list gates nothing')
    return ids


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


def _zero_tests_matched(text):
    """Common test-runner spellings for 'ran, but matched nothing'. A check that invokes a
    runner with a filter matching zero tests exits 0 and reads as PASS unless caught here —
    not exhaustive, add a spelling when a runner's own phrasing isn't one of these.

    The numeric ones guard against a digit right before the `0` (`10 tests` must not match
    `0 tests`), since a plain substring search would."""
    low = text.lower()
    for marker in ('no tests ran', 'no test matches', 'collected 0 items'):
        if marker in low:
            return marker
    # `0 tests ran/collected/found`, never `0 tests failed`: the second is a suite that passed
    if re.search(r'(?<!\d)0\s+tests?\b(?!\s+(failed|failing|skipped|errored|errors?|pending))', low):
        return '0 tests'
    if re.search(r'(?<!\d)0\s+passing\b', low):
        return '0 passing'
    if 'test run successful' in low and re.search(r'passed:\s*0\b', low):
        return 'Test Run Successful … Passed: 0'
    # every test the check ran was skipped: the runner is happy, nothing was exercised, and a
    # row whose only test is `@skip` reads as PASS while measuring exactly nothing
    if re.search(r'\bok\b\s*\(skipped=\d+\)', low) and not re.search(r'(?<!\d)[1-9]\d*\s+passed', low):
        ran = re.search(r'ran\s+(\d+)\s+tests?', low)
        skip = re.search(r'skipped=(\d+)', low)
        if ran and skip and ran.group(1) == skip.group(1):
            return 'every test skipped'
    if re.search(r'(?<!\d)[1-9]\d*\s+skipped', low) and not re.search(r'(?<!\d)[1-9]\d*\s+passed', low):
        return 'every test skipped'
    return None


def run_check(cmd, timeout=1800, cwd=None):
    """Return (ok, one-line summary, timed_out). A check passes only on exit 0 and, if it
    looks like a test runner, only when it actually matched something to run.

    Timeout is reported structurally, not as text: a check that hangs says nothing either way,
    and a check's own output may legitimately end in the words "timed out".

    Output goes to a tempfile, not a pipe, so a backgrounded child that inherits stdout
    cannot hold the run open; the whole session is killed on timeout."""
    with tempfile.TemporaryFile() as out:
        p = subprocess.Popen(cmd, shell=True, cwd=cwd, stdin=subprocess.DEVNULL, stdout=out,
                             stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = p.wait(timeout)
        except subprocess.TimeoutExpired:
            _kill_group(p)
            return False, f'timed out after {timeout}s', True
        except KeyboardInterrupt:
            _kill_group(p)
            raise
        out.seek(0)
        text = out.read().decode('utf-8', errors='replace')
    if code == 0 and RUNNER_RE.search(cmd):
        marker = _zero_tests_matched(text)
        if marker:
            return False, (f'ran no test ({marker}) — the filter matched nothing, or every '
                           f'test it matched was skipped'), False
    tail = [l.strip() for l in text.splitlines() if l.strip()]
    return code == 0, (tail[-1][:96] if tail else f'exit {code}'), False


def _digest(path):
    """Content id of one path. A symlink is its target, not what the target holds — reading
    through it compares the wrong file, and a relative link dangles from inside a clone."""
    try:
        if os.path.islink(path):
            return 'link:' + os.readlink(path)
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for block in iter(lambda: f.read(1 << 20), b''):   # an artifact can be large
                h.update(block)
        return h.hexdigest()
    except OSError:
        return 'unreadable'


def _tree_stat(root):
    """(mtime_ns, size) per path — whether anything moved, not what it now holds. Reading every
    byte of a clone twice per row costs minutes on a build tree; a stat walk costs nothing."""
    out = {}
    for base, dirs, files in os.walk(root):
        for name in files + [d for d in dirs if os.path.islink(os.path.join(base, d))]:
            path = os.path.join(base, name)
            try:
                st = os.lstat(path)
                out[os.path.relpath(path, root)] = (st.st_mtime_ns, st.st_size)
            except OSError:
                out[os.path.relpath(path, root)] = None
    return out


def _tree_hashes(root):
    out = {}
    for base, dirs, files in os.walk(root):
        # a symlinked directory is an entry, not a directory to walk into: os.walk lists it
        # under `dirs` and never yields its contents, so without this it is invisible
        for name in files + [d for d in dirs if os.path.islink(os.path.join(base, d))]:
            path = os.path.join(base, name)
            out[os.path.relpath(path, root)] = _digest(path)
    return out


BASELINE_SKIP = CLONE_SKIP | {'obj', 'bin', 'target', 'dist', 'build', '.next', '.testcases'}


def take_baseline(cwd=None, path=BASELINE, reset=False):
    """Record the content id of every file in the tree — the mark this run's work is measured
    against — and return (data, count).

    The whole tree, not the ledger's deliverables: the ledger does not exist yet at the moment
    this must be taken, which is before the first edit. A baseline taken after the work began
    reads every deliverable as `unchanged` for ever, and the only cure is to undo the work by
    hand. Build outputs are skipped — no requirement ships one — which also keeps the walk short.

    A second baseline is refused unless `reset`: retaking it mid-run moves every mark to now and
    erases the evidence that anything shipped."""
    full = os.path.join(cwd or '.', path)
    if os.path.exists(full) and not reset:
        raise Misuse(f'a baseline already exists at {path} — the marks this run is measured '
                     f'against. Retaking it would read every deliverable as unchanged; '
                     f'`--baseline --reset` if that is really what you want')
    root = cwd or '.'
    files = {}
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in BASELINE_SKIP]
        for name in names + [d for d in dirs if os.path.islink(os.path.join(base, d))]:
            p = os.path.join(base, name)
            files[os.path.normpath(os.path.relpath(p, root))] = _digest(p)
    data = {'taken': int(time.time()), 'files': files}
    os.makedirs(os.path.dirname(full) or '.', exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, sort_keys=True)
        f.write('\n')
    return data, len(files)


def read_baseline(path=BASELINE, cwd=None):
    full = os.path.join(cwd or '.', path)
    if not os.path.exists(full):
        return None
    with open(full, encoding='utf-8') as f:
        return json.load(f)


def not_shipped(path, baseline_files, cwd=None):
    """'' when the deliverable exists and differs from the baseline, else the reason.

    A file the baseline never saw is new since then, so it shipped. A directory shipped when
    anything under it was added, removed or changed."""
    norm = os.path.normpath(path)
    if os.path.isabs(norm) or norm.split(os.sep)[0] == '..':
        return 'path leaves the repository'
    full = os.path.join(cwd or '.', norm)
    if not os.path.lexists(full):
        return 'does not exist'
    if os.path.isdir(full) and not os.path.islink(full):
        now = {os.path.normpath(os.path.join(norm, rel)): h for rel, h in _tree_hashes(full).items()}
        then = {k: v for k, v in baseline_files.items()
                if k == norm or k.startswith(norm + os.sep)}
        return '' if now != then else 'unchanged since baseline'
    return '' if _digest(full) != baseline_files.get(norm) else 'unchanged since baseline'


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


def decide(row, signatures, baseline_files=None, timeout=1800, cwd=None):
    """Resolve one row to (status, note); status is PASS, FAIL or WAIT."""
    if row.check.startswith('MANUAL:'):
        owner = owner_of(row) or 'unassigned'
        sig = signatures.get(row.id)
        if not sig:
            return 'WAIT', f'awaiting {owner}'
        if sig['what_hash'] != what_hash(row.what):
            return 'WAIT', f'awaiting {owner} — signature is for an older wording'
        return 'PASS', f'signed by {sig["who"]} on {sig["date"]} — {sig["note"]}'
    ok, note, _ = run_check(row.check, timeout, cwd)
    if not ok:
        return 'FAIL', note
    if row.deliverable:
        why = not_shipped(row.deliverable, baseline_files or {}, cwd)
        if why:
            return 'FAIL', f'deliverable not shipped: {row.deliverable} — {why}'
    return 'PASS', note


def report(rows, signatures, baseline_files, timeout):
    """Print the table. Return [(status, row)]."""
    width = max(len(r.id) for r in rows)
    results = []
    for row in rows:
        status, note = decide(row, signatures, baseline_files, timeout)
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


def lint(rows, signatures=None, has_baseline=True, waived=None, requirements=None):
    """Problems with the ledger itself. Empty list means the ledger measures something.

    Two gaps a ledger closes by omission, so both are checked here rather than trusted to
    prose: a row with no `break` (nothing proves its check can fail) and a requirement with
    no row (nothing measures it at all). Either can be waived in the ledger with a reason."""
    problems = []
    if waived is None:
        waived = {'verify-ok': {}, 'no-row-ok': {}}
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
    unbreakable = [r.id for r in rows
                   if not r.brk and not r.check.startswith('MANUAL:')
                   and r.id not in waived['verify-ok']]
    if unbreakable:
        problems.append(f'rows {", ".join(unbreakable)} have no break — nothing proves their '
                        f'check can fail; add one, or waive it in the ledger with '
                        f'`# verify-ok: <id> — <reason>` — legitimate when this is test-first '
                        f'and its red phase was already witnessed by hand')
    # the contract is `check` runs the test implementing this requirement's TC. A search over
    # text is the shape that slips past `--verify` too: pair it with a break that edits the
    # same string and the two agree with each other while measuring nothing
    searching = [r.id for r in rows
                 if not r.check.startswith('MANUAL:')
                 and re.search(r'\b(grep|rg|ag|ack)\b', r.check)
                 and not RUNNER_RE.search(r.check)]
    if searching:
        problems.append(f'rows {", ".join(searching)} search text instead of running a test — a '
                        f'search proves the word is present, which survives every defect the '
                        f'requirement is about; give the claim a test in the repo, or say in '
                        f'the ledger why this row is hygiene rather than a requirement '
                        f'(`# verify-ok: <id> — <reason>`)')
    ids = {r.id for r in rows}
    for sid in (signatures or {}):
        if sid not in ids:
            problems.append(f'signature for {sid!r} but no such row — stale signoff.tsv')
    manual_ids = {r.id for r in manual}
    broken = {r.id for r in rows if r.brk}
    for wid in waived['verify-ok']:
        if wid in broken and wid not in manual_ids:
            problems.append(f'`# verify-ok: {wid}` waives a row that has a break — the waiver '
                            f'silently removes it from every sweep; delete one of the two')
        elif wid in manual_ids:
            problems.append(f'`# verify-ok: {wid}` waives a break on a MANUAL row, which never '
                            f'needs one — delete the line')
        elif wid not in ids:
            problems.append(f'`# verify-ok: {wid}` but no such row — a waiver for nothing reads '
                            f'as a gap someone accepted; delete the line or fix the id')
    if requirements is not None:
        for wid in waived['no-row-ok']:
            if wid not in requirements:
                problems.append(f'`# no-row-ok: {wid}` but no such requirement — delete the '
                                f'line or fix the id')
    if requirements:
        # a waiver excuses a gap someone looked at; past a third of the list it is a bulk pass
        # wearing per-id clothes, and the gate it defeats is the only one that sees a
        # requirement no row measures. Varying the wording does not make it smaller
        skipped = [r for r in requirements if r in waived['no-row-ok']]
        if len(skipped) > 1 and len(skipped) / len(requirements) > 0.30:
            problems.append(
                f'{len(skipped)} of {len(requirements)} requirements are waived with '
                f'`# no-row-ok:` (>30%) — a ledger measuring {len(requirements) - len(skipped)} '
                f'of them is not gated by this list; add rows, or cut the list down to what '
                f'this run is about')
    for req in (requirements or []):
        if req in waived['no-row-ok']:
            continue
        # whole-token match, so REQ-1 is not satisfied by a row that names REQ-10
        pat = re.compile(rf'(?<![\w-]){re.escape(req)}(?![\w-])')
        if not any(pat.search(r.id) or pat.search(r.what) for r in rows):
            problems.append(f'{req}: no row measures it — a requirement with no row is a '
                            f'permanent pass; add a row, or waive it in the ledger with '
                            f'`# no-row-ok: {req} — <reason>`')
    return problems


def blast_radius(row, rows, timeout, waived=(), allowance=None, cwd=None):
    """Other rows whose check also goes red under this row's planted break, run inside the
    same clone the break was planted in.

    Returns (same-deliverable siblings, crossed rows, rows that hung, checks run, rows the
    sweep had no time left for).

    `waived` names rows the sweep must ignore: ones waived from needing a break, and ones
    already red before anything was planted.

    A sibling delivering the same file is expected collateral — `rm -f src/export.py` reddens
    every row that ships it. A row delivering something else going red means its check cannot
    tell this defect from its own, so neither row proves what it claims. A row waived from
    needing a break has already declared itself undiscriminating (a whole-suite row reddens on
    every defect, which is its job) and is not counted.
    """
    # ponytail: O(rows²) checks. On by default for the whole-ledger proof, bounded by an
    # absolute deadline; --no-blast opts out, a --verify subset never sweeps
    ships = lambda r: os.path.normpath(r.deliverable) if r.deliverable else ''
    hit, stuck, unswept, seen = [], [], [], {}
    # the clock starts when the sweeping does — a row's own break and check are the proof,
    # not the sweep, and charging them to the sweep's budget stops it before it begins
    deadline = time.monotonic() + allowance if allowance is not None else None
    for other in rows:
        if other.id == row.id or other.check.startswith('MANUAL:') or other.id in waived:
            continue
        # rows running the identical command share one result under this break; that is the
        # ledger shape the sweep exists to catch, and also the one that would cost the most
        if other.check not in seen:
            left = deadline - time.monotonic() if deadline else None
            if left is not None and left < 1:
                seen[other.check] = 'unswept'
            else:
                lim = timeout if left is None else min(timeout, int(left))
                ok, _, hung = run_check(other.check, lim, cwd)
                # hitting the sweep's own cap is the sweep running out of time, not the check
                # hanging — calling that `stuck` would file a real BLAST as a footnote
                seen[other.check] = ('unswept' if hung and lim < timeout else
                                     'ok' if ok else 'stuck' if hung else 'red')
        verdict = seen[other.check]
        if verdict == 'unswept':
            unswept.append(other.id)
        elif verdict == 'stuck':
            stuck.append(other)
        elif verdict == 'red':
            hit.append(other)
    same = [o.id for o in hit if ships(o) and ships(o) == ships(row)]
    crossed = [o.id for o in hit if o.id not in same]
    swept = sum(1 for v in seen.values() if v != 'unswept')
    return same, crossed, [o.id for o in stuck], swept, unswept


def hold_lock(path=LOCK):
    """One goalrun runs checks in a tree at a time. Returns the open lock, or raises Misuse.

    Two runs building the same tree — or two clones of it racing over an external resource
    such as a port or a database — produce reds that belong to neither: such a red is
    indistinguishable from a real one in the table, so the second run is refused instead.

    `flock` rather than a pid file: the kernel drops the lock when the holder dies, however it
    dies, so a crashed run cannot wedge the next one and there is no stale entry to detect, to
    race over, or to fail to delete. The pid written inside is only there to name the holder."""
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    try:
        # `a+`, never `w`: `w` truncates before the lock is taken, wiping the pid of whoever
        # is holding it. The truncate below happens after the lock is ours
        fd = open(path, 'a+', encoding='utf-8')
    except OSError as e:
        raise Misuse(f'cannot open the run lock {path}: {e}')
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fd.seek(0)
        who = fd.read().strip() or 'unknown pid'
        fd.close()
        raise Misuse(f'another goalrun is running checks here ({who}) — a check racing another '
                     f'build goes red for reasons that are not the code; wait for it to finish')
    fd.seek(0)
    fd.truncate()
    fd.write(f'pid {os.getpid()}\n')
    fd.flush()
    return fd


def drop_lock(fd):
    """Release it. The file stays: unlinking a flocked path races the next run onto a lock
    nobody else can see."""
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
    except OSError:
        pass


def _prune_skip(root):
    """Remove CLONE_SKIP directories from an already-made clone — needed unconditionally so
    the plain-copy fallback doesn't pay to copy them first, and harmless when `cp` already
    pruned nothing (they just aren't there to remove)."""
    for base, dirs, files in os.walk(root, topdown=True):
        for d in list(dirs):
            if d in CLONE_SKIP:
                shutil.rmtree(os.path.join(base, d), ignore_errors=True)
                dirs.remove(d)


def clone_tree(src):
    """Copy the tree into a disposable directory so `--verify` can plant a break without ever
    writing to the caller's own working tree. Tries `cp -c` (APFS copy-on-write, macOS), then
    `cp --reflink=auto` (Linux CoW filesystems), then falls back to a plain recursive copy —
    whichever the filesystem actually supports. The caller deletes the result when done."""
    dst = tempfile.mkdtemp(prefix=CLONE_PREFIX)
    for cmd in (['cp', '-c', '-R', src, dst], ['cp', '-R', '--reflink=auto', src, dst]):
        shutil.rmtree(dst, ignore_errors=True)    # `cp -R src emptydst` fills dst; an
        if subprocess.run(cmd, capture_output=True).returncode == 0:  # existing one nests
            break
    else:
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst, symlinks=True,
                        ignore=lambda _d, names: [n for n in names if n in CLONE_SKIP])
    _prune_skip(dst)        # `cp` has no exclude list; the CoW copy of a skip dir is cheap
    return dst


def verify(rows, ids, timeout, cwd=None, blast=False, waived=(), budget=SWEEP_BUDGET):
    """Plant each row's break inside a disposable clone of the tree, prove its check goes red
    there, then throw the clone away. Return True if all did.

    The caller's own tree is only ever read."""
    everything = rows                       # --blast scans the whole ledger, not the selection
    if ids:
        rows = select(rows, ids)
    # one pass over a fresh clone first: a row whose check already fails proves nothing when
    # its break makes it fail again, and it reddens every other row's sweep for reasons that
    # have nothing to do with the planted defect. Run in a clone like everything else here, so
    # even a check with side effects (one that litters an artifact) never touches the real tree
    scan = everything if blast else rows
    pre = clone_tree(cwd or '.')
    try:
        already = {r.id for r in scan
                  if not r.check.startswith('MANUAL:') and not run_check(r.check, timeout, pre)[0]}
    finally:
        shutil.rmtree(pre, ignore_errors=True)
    if already:
        print(f'already red before any break: {", ".join(sorted(already))} — those rows prove '
              f'nothing until they pass, and the sweep ignores them')
    all_ok, ran, sweeps, spent = True, 0, 0, 0.0
    incomplete = []
    for row in rows:
        if not row.brk:
            print(f'skip {row.id} — no break column')
            continue
        if row.check.startswith('MANUAL:'):
            print(f'skip {row.id} — MANUAL row')
            continue
        if row.id in already:
            all_ok = False
            print(f'ALREADY RED {row.id} — its check fails before the break is planted, so '
                  f'the break proves nothing; fix the row, then verify it')
            continue
        clone = clone_tree(cwd or '.')
        try:
            before = _tree_stat(clone)
            planted, why, _ = run_check(row.brk, timeout, clone)
            after = _tree_stat(clone)
            if not planted:
                all_ok, ran = False, ran + 1
                print(f'BREAK FAILED {row.id} — the break command itself failed: {why}')
                continue
            if before == after:
                # the break exited 0 but nothing in the clone moved — the common cause is a
                # break or check written against an absolute path to the original tree, which
                # would otherwise silently test the unmutated code and read as VERIFIED
                all_ok, ran = False, ran + 1
                print(f'BREAK FAILED {row.id} — the break ran but changed nothing in the '
                      f'clone; does it (or the check) use an absolute path to the original '
                      f'tree instead of a relative one?')
                continue
            ok, note, hung = run_check(row.check, timeout, clone)
            if blast:
                began = time.monotonic()
                left = None if budget is None else max(0.0, budget - spent)
                same, crossed, stuck, swept, unswept = blast_radius(
                    row, everything, timeout, set(waived) | already, left, cwd=clone)
                spent, sweeps = spent + time.monotonic() - began, sweeps + swept
                if unswept:
                    incomplete.append(row.id)
            else:
                same, crossed, stuck = [], [], []
            # the row's own verdict first, its sweep footnotes after — printed the other way
            # round, `shared` reads as the previous row's fallout
            if hung:
                all_ok, ran = False, ran + 1
                print(f'STUCK {row.id} — its check timed out under the break rather than '
                      f'failing; a check that hangs proves nothing about the defect')
            elif ok:
                all_ok, ran = False, ran + 1
                print(f'HOLLOW {row.id} — check still passed after break; it does not test '
                      f'what it claims')
            else:
                ran += 1
                print(f'VERIFIED {row.id} — {note}')
            if crossed:
                all_ok = False
                print(f'BLAST {row.id} — its break also reddens {", ".join(crossed)}, which '
                      f'ship elsewhere; those checks cannot tell this defect from their own')
            if stuck:
                print(f'stuck {row.id} — {", ".join(stuck)} timed out under its break; those '
                      f'checks hang rather than fail, which the sweep cannot read either way')
            if same:
                print(f'shared {row.id} — {", ".join(same)} went red too, as rows delivering '
                      f'the same file do')
        finally:
            shutil.rmtree(clone, ignore_errors=True)
    if not ran:
        # rule 2, turned on the script itself: a run that proved nothing is not a pass
        where = 'no row in this selection' if ids else 'no row'
        print(f'NOTHING VERIFIED — {where} ran a break; --verify proved nothing')
        return False
    if not blast and not ids:
        # the docs promise --no-blast names the blind spot; silence here would be the same
        # failure mode the rest of the script refuses
        print('sweep skipped (--no-blast) — rows are not proven against each other\'s defects')
    if blast and incomplete:
        # not 'spent the budget': a budget under a check's runtime buys no sweep at all,
        # and 0 check(s) in 0s having spent 1s reads as a bug in the accounting
        print(f'SWEEP STOPPED — a {budget:g}s sweep budget was not enough; {sweeps} sibling '
              f'check(s) ran in {spent:.1f}s and the sweeps for {", ".join(incomplete)} '
              f'are incomplete, '
              f'so those rows are unproven against the rest. Rerun with `--blast SECONDS` for '
              f'a bigger budget, `--blast` for none at all, or `--no-blast` to accept the '
              f'proof without the sweep')
        all_ok = False
    elif blast:
        print(f'swept {sweeps} sibling check(s) across {ran} break(s) in {spent:.0f}s')
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
    ap.add_argument('--requirements', metavar='PATH',
                    help='file of requirement ids, one per line; with --lint-ledger, names '
                         'the ones no row measures')
    ap.add_argument('--who')
    ap.add_argument('--note', default='')
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--only', metavar='A,B', help='run a subset of rows')
    mode.add_argument('--sign', metavar='ID')
    mode.add_argument('--baseline', nargs='?', const='', default=None, metavar='(no argument)',
                      help='record the tree before any work: what every deliverable is later '
                           'measured against. Refused when one exists')
    ap.add_argument('--reset', action='store_true',
                    help='with --baseline: replace the existing baseline')
    mode.add_argument('--lint-ledger', action='store_true')
    mode.add_argument('--verify', nargs='?', const='', metavar='A,B')
    blast = ap.add_mutually_exclusive_group()
    def _seconds(v):
        n = int(v)
        if n < 0:
            raise argparse.ArgumentTypeError('seconds (or nothing for no budget); '
                                             '--no-blast skips the sweep')
        return n

    blast.add_argument('--blast', dest='blast', nargs='?', const=NO_BUDGET, type=_seconds,
                       default=None,
                       metavar='SECONDS',
                       help='with --verify: also run every other row under each planted break, '
                            'to find rows whose checks cannot tell one defect from another. On '
                            f'by default for a whole-ledger --verify with a {SWEEP_BUDGET}s '
                            'budget, off for a subset; SECONDS sets a different budget (0 '
                            'sweeps nothing), bare --blast removes it')
    blast.add_argument('--no-blast', dest='blast', action='store_const', const=-1,
                       help='skip that sweep; the proof is then blind to rows measuring each '
                            "other's defects")
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
    if a.reset and a.baseline is None:
        raise Misuse('--reset is read by --baseline')
    if a.requirements and not a.lint_ledger:
        raise Misuse('--requirements is read by --lint-ledger')
    if a.blast is not None and a.verify is None:
        raise Misuse('--blast/--no-blast is read by --verify')

    if a.requirements and not os.path.exists(a.requirements):
        raise Misuse(f'no requirements file at {a.requirements}')

    if a.baseline is not None:
        if a.baseline:
            raise Misuse(f'--baseline takes no argument — it records the tree as it is; '
                         f'drop {a.baseline!r}')
        # under the lock like the checks: two writers to the baseline file at once could
        # interleave and leave it holding neither write
        lock = hold_lock()
        try:
            _, count = take_baseline(reset=a.reset)
        finally:
            drop_lock(lock)
        print(f'baseline: {count} file(s) recorded -> {BASELINE}')
        return 0

    rows = load(a.ledger)

    if a.sign:
        lock = hold_lock()
        try:
            date = sign(rows, a.sign, a.who, a.note)
        finally:
            drop_lock(lock)
        print(f'{a.sign} signed by {" ".join(a.who.split())} on {date}')
        return 0

    baseline = read_baseline()

    if a.lint_ledger:
        waived = waivers(a.ledger)
        reqs = read_requirements(a.requirements) if a.requirements else None
        problems = lint(rows, load_signatures(), has_baseline=baseline is not None,
                        waived=waived, requirements=reqs)
        for p in problems:
            print(p)
        if reqs:
            skipped = sum(1 for r in reqs if r in waived['no-row-ok'])
            print(f'coverage: {len(reqs)} requirement(s) · {len(reqs) - skipped} carried by '
                  f'rows · {skipped} waived ({skipped * 100 // len(reqs)}%)')
        if not a.requirements:
            print('coverage not checked — no --requirements file; only the rows that exist '
                  'were linted')
        print('ledger measures something' if not problems else
              f'{len(problems)} problem(s) with the ledger itself')
        return 1 if problems else 0

    if not rows:
        raise Misuse('ledger has no rows')

    lock = hold_lock()      # from here on the modes that run checks; nothing else builds
    try:
        return _run_checks(a, rows, baseline)
    finally:
        drop_lock(lock)


def _run_checks(a, rows, baseline):
    if a.verify is not None:
        # the condition for wanting the sweep is only knowable by running it, so the whole-ledger
        # proof runs it unless told not to; a subset run is iterative work, not the proof
        # bare --blast means no budget; --blast N sets one, and N=0 sweeps nothing rather
        # than everything; --no-blast (-1) skips the
        # sweep; left alone, the whole-ledger proof sweeps under the default budget
        blast = (a.blast != -1) if a.blast is not None else not a.verify
        budget = (SWEEP_BUDGET if a.blast is None else
                  None if a.blast == NO_BUDGET else max(0, a.blast))
        return 0 if verify(rows, a.verify, a.timeout, blast=blast,
                           waived=waivers(a.ledger)['verify-ok'], budget=budget) else 1

    # `is not None`, not truthiness: `--only ''` names no row, and falling through to the
    # whole ledger turns a phase run into a `DONE` — the one verdict --only may never print
    chosen = select(rows, a.only) if a.only is not None else rows
    shipping = [r.id for r in chosen if r.deliverable]
    if shipping and baseline is None:
        raise Misuse(f'rows {", ".join(shipping)} name deliverables but no baseline is '
                     f'recorded — run --baseline first')

    results = report(chosen, load_signatures(), baseline['files'] if baseline else {}, a.timeout)
    passed = sum(1 for s, _ in results if s == 'PASS')
    print()
    if a.only is not None:
        tail = f'({len(chosen)} of {len(rows)} in ledger)'
        if passed == len(chosen):
            print(f'PHASE OK — {passed} row(s) pass {tail}')
            return 0
        print(f'PHASE NOT OK — {summary(results)} {tail}')
        return 1
    if passed == len(chosen):
        print(f'DONE — all {passed} check(s) pass')
        return 0
    print(f'NOT DONE — {summary(results)}')
    return 1


if __name__ == '__main__':
    sys.exit(main())
