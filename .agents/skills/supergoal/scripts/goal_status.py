#!/usr/bin/env python3
"""Decide whether a standing goal is met. The exit code IS the answer.

Reads `.goal/ledger.tsv` — one row per condition, tab-separated:

    id<TAB>what must be true<TAB>shell command that decides it

A row whose command is `MANUAL:<owner>` is blocked on someone else. It stays RED and
names the owner; it never counts as passed.

    python3 goal_status.py                 # run every check, print the table
    python3 goal_status.py --only BUILD    # run one row
    python3 goal_status.py --init          # write a starter ledger

Exit 0 only when every row passed. Anything else is "not done".
"""
import argparse, os, subprocess, sys

LEDGER = os.path.join('.goal', 'ledger.tsv')
STARTER = """\
# id\twhat must be true\tcheck (shell; MANUAL:<owner> when someone else must decide)
BUILD\tthe test suite passes\techo 'replace me' && false
SCOPE\tthe scope list is non-empty and proven by a control\tpython3 scripts/goal_status.py --scope-control
"""


def load(path):
    if not os.path.exists(path):
        sys.stderr.write(f'no ledger at {path} — run --init\n')
        sys.exit(2)
    rows = []
    for raw in open(path, encoding='utf-8'):
        line = raw.rstrip('\n')
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) < 3:
            sys.stderr.write(f'malformed row (need 3 tab-separated fields): {line!r}\n')
            sys.exit(2)
        rows.append((parts[0].strip(), parts[1].strip(), '\t'.join(parts[2:]).strip()))
    return rows


def run(cmd):
    """Return (ok, one-line summary). A check passes only on exit 0."""
    if cmd.startswith('MANUAL'):
        owner = cmd.partition(':')[2].strip() or 'unassigned'
        return False, f'blocked — {owner} must decide'
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        return False, 'timed out after 1800s'
    out = (p.stdout or '') + (p.stderr or '')
    tail = [l.strip() for l in out.splitlines() if l.strip()]
    return p.returncode == 0, (tail[-1][:96] if tail else f'exit {p.returncode}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ledger', default=LEDGER)
    ap.add_argument('--only')
    ap.add_argument('--init', action='store_true')
    a = ap.parse_args()

    if a.init:
        os.makedirs(os.path.dirname(a.ledger) or '.', exist_ok=True)
        if os.path.exists(a.ledger):
            sys.stderr.write(f'{a.ledger} already exists — not overwriting\n')
            return 2
        open(a.ledger, 'w', encoding='utf-8').write(STARTER)
        print(f'wrote {a.ledger} — replace the placeholder checks')
        return 0

    rows = [r for r in load(a.ledger) if not a.only or r[0] == a.only]
    if not rows:
        sys.stderr.write('no matching rows\n')
        return 2

    width = max(len(r[0]) for r in rows)
    failed = []
    for rid, what, cmd in rows:
        ok, note = run(cmd)
        print(f'{rid:<{width}}  {"PASS" if ok else "FAIL"}  {what} — {note}')
        if not ok:
            failed.append(rid)

    print()
    if failed:
        print(f'NOT DONE — {len(failed)} of {len(rows)} check(s) failing: {", ".join(failed)}')
        return 1
    print(f'DONE — all {len(rows)} checks pass')
    return 0


if __name__ == '__main__':
    sys.exit(main())
