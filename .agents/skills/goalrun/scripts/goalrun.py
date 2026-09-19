#!/usr/bin/env python3
"""Decide whether a goal is met. The exit code IS the answer.

Reads `.testcases/goalrun/ledger.tsv` — one row per condition, tab-separated (UTF-8, BOM tolerated):

    id<TAB>what must be true<TAB>check<TAB>deliverable<TAB>break

`id`          unique.
`check`       a shell command, or `MANUAL:<owner>` when a human must decide. Never empty.
              A MANUAL row is decided by a person and cannot also name a deliverable.
`deliverable` optional path this row must have produced; `—`, `-` or empty means none.
              A gitignored one is measured by mtime against the baseline commit, since git
              sees neither its content nor its history.
`break`       the command that plants the defect `check` exists to catch (`--verify`).
              A row without one has never gone red; `--lint-ledger` says so unless the
              ledger waives it with a comment line `# verify-ok: <id> — <reason>`.
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
                     (databases, services, $HOME) are NOT undone, and a break naming a
                     gitignored path is refused (UNRESTORABLE) rather than planted — git
                     restores neither its content nor its existence.
  --lint-ledger      problems with the ledger itself; with --requirements FILE it also
                     names requirements no row measures (waive: `# no-row-ok: <id> — <why>`)

Only one goalrun runs checks in a tree at a time (`.testcases/goalrun/lock`): a check racing
another build goes red for reasons that are not the code.

Exit 0 done / phase ok, 1 not done, 2 misuse or broken ledger.
"""
import argparse, collections, datetime, hashlib, os, re, shlex, shutil, signal, subprocess, \
    sys, tempfile, time

GOAL_DIR = os.path.join('.testcases', 'goalrun')
LEDGER = os.path.join(GOAL_DIR, 'ledger.tsv')
SIGNOFF = os.path.join(GOAL_DIR, 'signoff.tsv')
BASELINE = os.path.join(GOAL_DIR, 'baseline')
NONE = ('', '—', '-')
SWEEP_BUDGET = 900      # seconds of sweeping (not of the run) the default proof may spend
NO_BUDGET = -2          # bare `--blast`: sweep everything. Not 0 — `--blast 0` is 0 seconds

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


def run_check(cmd, timeout=1800):
    """Return (ok, one-line summary, timed_out). A check passes only on exit 0.

    Timeout is reported structurally, not as text: a check that hangs says nothing either way,
    and a check's own output may legitimately end in the words "timed out".

    Output goes to a tempfile, not a pipe, so a backgrounded child that inherits stdout
    cannot hold the run open; the whole session is killed on timeout."""
    with tempfile.TemporaryFile() as out:
        p = subprocess.Popen(cmd, shell=True, stdin=subprocess.DEVNULL, stdout=out,
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
    tail = [l.strip() for l in text.splitlines() if l.strip()]
    return code == 0, (tail[-1][:96] if tail else f'exit {code}'), False


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


def baseline_time(baseline, cwd=None):
    """Unix time of the baseline commit — what an ignored deliverable's mtime is read against."""
    out = _git('show', '-s', '--format=%ct', baseline, cwd=cwd) if baseline else None
    return int(out[0]) if out else None


def not_shipped(path, touched, cwd=None, since=None):
    """'' when the deliverable exists and changed since baseline, else the reason.

    An ignored file is invisible to `git diff` and to `ls-files --others --exclude-standard`,
    so it can never appear in `touched` — the row would read `unchanged since baseline`
    forever, and dropping the deliverable column to escape that quietly switches rule 6 off
    for the one artifact the run exists to produce. Shipping is therefore measured by mtime
    there, which `--lint-ledger` names as the weaker standard it is."""
    norm = os.path.normpath(path)
    if os.path.isabs(norm) or norm.split(os.sep)[0] == '..':
        return 'path leaves the repository'
    full = os.path.join(cwd or '.', norm)
    if not os.path.lexists(full):
        return 'does not exist'
    if norm in touched or any(t.startswith(norm + '/') for t in touched):
        return ''
    if _is_ignored(norm, cwd):
        if since is None:
            return 'git ignores it and no baseline time is known — shipping cannot be measured'
        newest = os.path.getmtime(full)
        for base, _dirs, files in os.walk(full):     # a directory ships when anything in it does
            newest = max([newest] + [os.path.getmtime(os.path.join(base, f)) for f in files])
        return '' if newest > since else 'not written since baseline (mtime; git ignores it)'
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


def decide(row, signatures, touched=frozenset(), timeout=1800, cwd=None, since=None):
    """Resolve one row to (status, note); status is PASS, FAIL or WAIT."""
    if row.check.startswith('MANUAL:'):
        owner = owner_of(row) or 'unassigned'
        sig = signatures.get(row.id)
        if not sig:
            return 'WAIT', f'awaiting {owner}'
        if sig['what_hash'] != what_hash(row.what):
            return 'WAIT', f'awaiting {owner} — signature is for an older wording'
        return 'PASS', f'signed by {sig["who"]} on {sig["date"]} — {sig["note"]}'
    ok, note, _ = run_check(row.check, timeout)
    if not ok:
        return 'FAIL', note
    if row.deliverable:
        why = not_shipped(row.deliverable, touched, cwd, since)
        if why:
            return 'FAIL', f'deliverable not shipped: {row.deliverable} — {why}'
    return 'PASS', note


def report(rows, signatures, touched, timeout, since=None):
    """Print the table. Return [(status, row)]."""
    width = max(len(r.id) for r in rows)
    results = []
    for row in rows:
        status, note = decide(row, signatures, touched, timeout, since=since)
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
                        f'`# verify-ok: <id> — <reason>`')
    # found at the gate rather than at --verify: the break that names an ignored path is
    # written at plan time, and waiting until the proof to say so costs a round trip on a
    # ledger nobody can prove — `.testcases/` is ignored by design, so a break reaching in
    # there is the common form
    for row in rows:
        doomed = unrestorable(row.brk) if row.brk else []
        if doomed:
            problems.append(f'{row.id}: its break names {", ".join(doomed)}, which git ignores '
                            f'— `--verify` restores with git, so that break cannot be undone '
                            f'and is refused; point it at a tracked file')
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
        if len(skipped) > 3 and len(skipped) / len(requirements) > 0.30:
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


def blast_radius(row, rows, timeout, waived=(), allowance=None):
    """Other rows whose check also goes red under this row's planted break.

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
                ok, _, hung = run_check(other.check, lim)
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


def hold_lock(path=os.path.join(GOAL_DIR, 'lock')):
    """One goalrun runs checks in a tree at a time. Returns the path, or raises Misuse.

    Two runs building the same tree produce reds that belong to neither: a compiler lock, a
    half-written artifact, a port already bound. Such a red is indistinguishable from a real
    one in the table, so the second run is refused instead. A lock whose process is gone is
    stale and taken over — a crashed run must not wedge the next one."""
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f'{os.getpid()}\n'.encode())
            os.close(fd)
            return path
        except FileExistsError:
            try:
                pid = int(open(path, encoding='utf-8').read().strip() or 0)
            except (OSError, ValueError):
                pid = 0
            if pid <= 0:            # crashed between create and write, or truncated; `os.kill(0,
                os.unlink(path)     # 0)` signals our own process group and would read as alive
                continue
            try:
                os.kill(pid, 0)
            except (ProcessLookupError, ValueError, PermissionError) as e:
                if isinstance(e, PermissionError):     # alive, owned by someone else
                    raise Misuse(f'another goalrun is running checks here (pid {pid}); wait for '
                                 f'it, or delete {path} if you know it is gone')
                os.unlink(path)                        # stale: its process is gone
                continue
            raise Misuse(f'another goalrun is running checks here (pid {pid}) — a check racing '
                         f'another build goes red for reasons that are not the code. Wait for '
                         f'it, or delete {path} if you know it is gone')


def drop_lock(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def _is_ignored(path, cwd=None):
    """True when git ignores this path, so `checkout`/`clean` can neither restore nor delete it."""
    return subprocess.run(('git', 'check-ignore', '-q', '--', path),
                          cwd=cwd, capture_output=True).returncode == 0


def unrestorable(cmd, cwd=None):
    """Existing gitignored paths a break command names — the ones restore cannot undo.

    `--verify` restores with `git checkout -- . && git clean -fdq`: tracked files come back,
    untracked ones are deleted, and an ignored file is outside both. A break that deletes one
    destroys it for good, and a break that rewrites one (a check script under .testcases/) is
    worse — it leaves the row measuring less than the ledger says, silently, past the end of
    the run. Both happen with the plan-time default `rm -f <deliverable>` the moment the
    deliverable is ignored, so the break is refused rather than planted.

    Reads the literal path tokens only: a break that hides its target behind a variable or a
    subshell is beyond this, which is why the ledger, its checks and its signatures are
    snapshotted separately."""
    try:
        tokens = shlex.split(cmd, comments=True)
    except ValueError:                      # unbalanced quotes; the shell will complain too
        tokens = cmd.split()
    hits = {t for t in tokens
            if t and not t.startswith('-')
            and os.path.lexists(os.path.join(cwd or '.', t)) and _is_ignored(t, cwd)}
    return sorted(hits)


def _tree_hashes(root):
    out = {}
    for base, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(base, name)
            try:
                with open(path, 'rb') as f:
                    digest = hashlib.sha256(f.read()).hexdigest()
            except OSError:
                digest = 'unreadable'
            out[os.path.relpath(path, root)] = digest
    return out


def snapshot(src, cwd=None):
    """Copy a gitignored directory aside so a break cannot make it a one-way door."""
    root = os.path.join(cwd or '.', src)
    if not os.path.isdir(root):
        return None
    held = tempfile.mkdtemp(prefix='goalrun-snap-')
    shutil.copytree(root, os.path.join(held, 'tree'), symlinks=True)
    return held


def restore_snapshot(held, src, cwd=None):
    """Put it back exactly; return the paths a break had changed (empty when it behaved)."""
    if not held:
        return []
    root, keep = os.path.join(cwd or '.', src), os.path.join(held, 'tree')
    before, after = _tree_hashes(keep), _tree_hashes(root)
    changed = sorted(set(before) ^ set(after)
                     | {p for p in set(before) & set(after) if before[p] != after[p]})
    if changed:
        shutil.rmtree(root, ignore_errors=True)
        shutil.copytree(keep, root, symlinks=True)
    shutil.rmtree(held, ignore_errors=True)
    return changed


def _demand_clean_tree(cwd=None):
    """--verify restores with git checkout/clean, so it refuses to start from a dirty one."""
    dirty = _git('status', '--porcelain', cwd=cwd)
    if dirty:
        top = GOAL_DIR.split(os.sep)[0] + '/'   # git lists an untracked dir as `?? .testcases/`
        hint = ('commit or stash first' if not all(top in l for l in dirty) else
                f'add `/{top}` to .git/info/exclude — {GOAL_DIR} is what is dirty')
        raise Misuse(f'--verify needs a clean working tree; {hint}')


def verify(rows, ids, timeout, cwd=None, blast=False, waived=(), budget=SWEEP_BUDGET):
    """Plant each row's break, prove its check goes red, restore. Return True if all did."""
    everything = rows                       # --blast scans the whole ledger, not the selection
    if ids:
        rows = select(rows, ids)
    # the clean-tree gate comes first: the pre-pass below runs checks, and a check that writes
    # an unignored artifact would otherwise fail this gate for dirt the script itself made
    _demand_clean_tree(cwd)
    # One pass over the clean tree first: a row whose check already fails proves nothing when
    # its break makes it fail again, and it reddens every other row's sweep for reasons that
    # have nothing to do with the planted defect. Costs one run per row, not one per pair —
    # and only the selection when no sweep will read the rest.
    scan = everything if blast else rows
    already = {r.id for r in scan
               if not r.check.startswith('MANUAL:') and not run_check(r.check, timeout)[0]}
    if _git('status', '--porcelain', cwd=cwd):
        subprocess.run('git -c core.quotePath=false checkout -- . && git clean -fdq',
                       shell=True, cwd=cwd, check=True)
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
        _demand_clean_tree(cwd)
        if row.id in already:
            all_ok = False
            print(f'ALREADY RED {row.id} — its check fails before the break is planted, so '
                  f'the break proves nothing; fix the row, then verify it')
            continue
        doomed = unrestorable(row.brk, cwd)
        if doomed:
            all_ok = False
            print(f'UNRESTORABLE {row.id} — its break names {", ".join(doomed)}, which git '
                  f'ignores, so the restore afterwards cannot bring it back; nothing was '
                  f'planted. Track the file, point the break at a tracked one, or verify this '
                  f'row by hand and waive it with `# verify-ok: {row.id} — <reason>`')
            continue
        # the ledger and its check scripts live in a gitignored directory, so a break that
        # edits one outlives the restore and leaves the row measuring less than it claims
        held = snapshot(GOAL_DIR, cwd)
        planted, why, _ = run_check(row.brk, timeout)
        if not planted:
            subprocess.run('git -c core.quotePath=false checkout -- . && git clean -fdq',
                           shell=True, cwd=cwd, check=True)
            clobbered = restore_snapshot(held, GOAL_DIR, cwd)
            all_ok, ran = False, ran + 1   # it ran; `ran` counts attempts, not successes
            print(f'BREAK FAILED {row.id} — the break command itself failed: {why}')
            if clobbered:
                print(f'  and it had already changed {", ".join(clobbered[:3])} under '
                      f'{GOAL_DIR}; restored from a snapshot')
            continue
        ok, note, hung = run_check(row.check, timeout)
        if blast:
            began = time.monotonic()
            left = None if budget is None else max(0.0, budget - spent)
            same, crossed, stuck, swept, unswept = blast_radius(
                row, everything, timeout, set(waived) | already, left)
            spent, sweeps = spent + time.monotonic() - began, sweeps + swept
            if unswept:
                incomplete.append(row.id)
        else:
            same, crossed, stuck = [], [], []
        subprocess.run('git -c core.quotePath=false checkout -- . && git clean -fdq',
                       shell=True, cwd=cwd, check=True)
        clobbered = restore_snapshot(held, GOAL_DIR, cwd)
        if crossed:
            all_ok = False
            print(f'BLAST {row.id} — its break also reddens {", ".join(crossed)}, which ship '
                  f'elsewhere; those checks cannot tell this defect from their own')
        if stuck:
            print(f'stuck {row.id} — {", ".join(stuck)} timed out under its break; those checks '
                  f'hang rather than fail, which the sweep cannot read either way')
        if same:
            print(f'shared {row.id} — {", ".join(same)} went red too, as rows delivering the '
                  f'same file do')
        if clobbered:
            all_ok, ran = False, ran + 1
            print(f'UNRESTORABLE {row.id} — its break changed {", ".join(clobbered[:3])} under '
                  f'{GOAL_DIR}, which git cannot restore; goalrun put it back from a snapshot. '
                  f'A break that rewrites a check measures less than the ledger claims, so '
                  f'this row is unproven until the break points at a tracked file')
        elif hung:
            all_ok, ran = False, ran + 1
            print(f'STUCK {row.id} — its check timed out under the break rather than failing; '
                  f'a check that hangs proves nothing about the defect')
        elif ok:
            all_ok, ran = False, ran + 1
            print(f'HOLLOW {row.id} — check still passed after break; it does not test what '
                  f'it claims')
        else:
            ran += 1
            print(f'VERIFIED {row.id} — {note}')
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
    mode.add_argument('--baseline', nargs='?', const='HEAD', metavar='SHA')
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
    if a.requirements and not a.lint_ledger:
        raise Misuse('--requirements is read by --lint-ledger')
    if a.blast is not None and a.verify is None:
        raise Misuse('--blast/--no-blast is read by --verify')

    if a.requirements and not os.path.exists(a.requirements):
        raise Misuse(f'no requirements file at {a.requirements}')

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
        waived = waivers(a.ledger)
        problems = lint(rows, load_signatures(), has_baseline=baseline is not None,
                        waived=waived,
                        requirements=read_requirements(a.requirements) if a.requirements else None)
        for p in problems:
            print(p)
        # not a problem — a weaker standard, said out loud. git sees neither the content nor
        # the history of an ignored file, so `--verify` cannot break one and only its mtime
        # says the run wrote it
        for row in rows:
            if row.deliverable and _is_ignored(row.deliverable):
                print(f'{row.id}: git ignores {row.deliverable}, so shipping is measured by '
                      f'mtime and no break may touch it — track the file to measure it '
                      f'properly')
        if a.requirements:
            reqs = read_requirements(a.requirements)
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
    touched = changed_paths(baseline) if baseline else frozenset()

    results = report(chosen, load_signatures(), touched, a.timeout,
                     since=baseline_time(baseline))
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
