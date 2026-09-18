#!/usr/bin/env python3
"""Self-checks for goalrun.py. Plain asserts, stdlib only: python3 test_goalrun.py"""
import io, os, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import goalrun


def git(tmp, *args):
    return subprocess.run(('git',) + args, cwd=tmp, capture_output=True, text=True)


def make_repo(tmp):
    git(tmp, '-c', 'init.defaultBranch=main', 'init', '-q')
    git(tmp, 'config', 'user.email', 't@example.com')
    git(tmp, 'config', 'user.name', 'test')
    git(tmp, 'config', 'core.hooksPath', os.path.join(tmp, '.nohooks'))
    # the catalog convention: .testcases/ is a working dir, excluded locally, never committed
    open(os.path.join(tmp, '.git', 'info', 'exclude'), 'a').write('.testcases/\n')
    open(os.path.join(tmp, 'old.txt'), 'w').write('old\n')
    git(tmp, 'add', '-A')
    git(tmp, 'commit', '-qm', 'base')
    return git(tmp, 'rev-parse', 'HEAD').stdout.strip()


def ledger(tmp, text):
    """Write the ledger where the CLI looks for it; return its path."""
    d = os.path.join(tmp, goalrun.GOAL_DIR)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, 'ledger.tsv')
    open(path, 'w', encoding='utf-8').write(text)
    return path


def run_cli(cwd, *args):
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'goalrun.py')
    return subprocess.run([sys.executable, script, *args],
                          cwd=cwd, capture_output=True, text=True)


def expect_misuse(fn, *args, **kw):
    try:
        fn(*args, **kw)
    except goalrun.Misuse:
        return
    raise AssertionError('expected Misuse')


# ---- ledger loading ---------------------------------------------------------------

def test_load_reads_five_columns():
    with tempfile.TemporaryDirectory() as tmp:
        rows = goalrun.load(ledger(tmp,
            '# id\twhat\tcheck\tdeliverable\tbreak\n'
            'BUILD\tsuite passes\ttrue\t—\n'
            'DARK\ttoggle works\tnpm test\tsrc/theme/toggle.ts\trm src/theme/toggle.ts\textra\n'))
    assert len(rows) == 2, rows
    assert rows[0].deliverable == '' and rows[0].brk == ''
    assert rows[1].deliverable == 'src/theme/toggle.ts'
    assert rows[1].brk == 'rm src/theme/toggle.ts', 'sixth column is ignored, fifth is break'


def test_load_accepts_three_columns_and_dash_for_none():
    with tempfile.TemporaryDirectory() as tmp:
        rows = goalrun.load(ledger(tmp, 'ASK\tno open questions\ttrue\nB\tb\ttrue\t-\t-\n'))
    assert rows[0].deliverable == '' and rows[1].deliverable == '' and rows[1].brk == ''


def test_load_rejects_two_columns():
    with tempfile.TemporaryDirectory() as tmp:
        expect_misuse(goalrun.load, ledger(tmp, 'BAD\tonly two fields\n'))


def test_load_rejects_empty_check():
    with tempfile.TemporaryDirectory() as tmp:
        expect_misuse(goalrun.load, ledger(tmp, 'A\tsays nothing\t\t—\n'))
        assert run_cli(tmp).returncode == 2, '`sh -c ""` exits 0; it must never be a check'


def test_load_rejects_duplicate_id():
    with tempfile.TemporaryDirectory() as tmp:
        expect_misuse(goalrun.load, ledger(tmp, 'A\tone\ttrue\nA\ttwo\tfalse\n'))


def test_load_tolerates_a_bom():
    with tempfile.TemporaryDirectory() as tmp:
        p = ledger(tmp, 'A\tok\ttrue\n')
        open(p, 'wb').write(b'\xef\xbb\xbfA\tok\ttrue\n')
        rows = goalrun.load(p)
    assert rows[0].id == 'A', rows


def test_missing_ledger_is_misuse():
    with tempfile.TemporaryDirectory() as tmp:
        assert run_cli(tmp).returncode == 2


def test_empty_ledger_is_misuse_not_done():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, '# header only\n')
        out = run_cli(tmp)
        assert out.returncode == 2 and 'DONE' not in out.stdout, out.stdout


# ---- running checks ---------------------------------------------------------------

def test_check_passes_on_exit_zero():
    ok, note = goalrun.run_check('true')
    assert ok, note


def test_check_fails_on_nonzero_with_last_line():
    ok, note = goalrun.run_check('echo boom >&2; exit 1')
    assert not ok and 'boom' in note


def test_check_times_out_and_kills_the_group():
    t = time.time()
    ok, note = goalrun.run_check('sleep 30', timeout=1)
    assert not ok and 'timed out after 1s' in note
    assert time.time() - t < 5


def test_background_child_does_not_hold_the_run_open():
    t = time.time()
    ok, _ = goalrun.run_check('(sleep 5 &) ; exit 0')
    assert ok
    assert time.time() - t < 3, 'the pipe was held by the orphan; use a file, not communicate()'


def test_non_utf8_output_does_not_crash():
    ok, note = goalrun.run_check("printf '\\xff ok'")
    assert ok, note
    ok, note = goalrun.run_check("printf '\\xff'; exit 1")
    assert not ok
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, "A\tbytes\tprintf '\\xff ok'\n")
        out = run_cli(tmp)
        assert out.returncode == 0 and 'Traceback' not in out.stderr, out.stderr


def test_timeout_flag_reaches_the_check():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'A\tslow\tsleep 30\n')
        t = time.time()
        out = run_cli(tmp, '--timeout', '1')
        assert out.returncode == 1 and 'timed out after 1s' in out.stdout, out.stdout
        assert time.time() - t < 5


# ---- deliverables -----------------------------------------------------------------

def test_deliverable_without_baseline_exits_before_any_check_runs():
    with tempfile.TemporaryDirectory() as tmp:
        make_repo(tmp)
        ledger(tmp, 'DARK\ttoggle\ttouch ran.marker\tsrc/toggle.ts\n')
        out = run_cli(tmp)
        assert out.returncode == 2, out.stdout
        assert 'DARK' in out.stderr and 'baseline' in out.stderr, out.stderr
        assert not os.path.exists(os.path.join(tmp, 'ran.marker')), 'no check may run first'


def test_baseline_records_full_sha_and_head_by_default():
    with tempfile.TemporaryDirectory() as tmp:
        sha = make_repo(tmp)
        assert run_cli(tmp, '--baseline').returncode == 0
        stored = open(os.path.join(tmp, goalrun.BASELINE)).read().strip()
        assert stored == sha, stored
        assert run_cli(tmp, '--baseline', sha[:7]).returncode == 0
        assert open(os.path.join(tmp, goalrun.BASELINE)).read().strip() == sha


def test_unresolvable_baseline_is_misuse():
    with tempfile.TemporaryDirectory() as tmp:
        make_repo(tmp)
        out = run_cli(tmp, '--baseline', 'deadbeef')
        assert out.returncode == 2, out
        assert not os.path.exists(os.path.join(tmp, goalrun.BASELINE))


def test_passing_check_with_missing_deliverable_fails_that_row():
    with tempfile.TemporaryDirectory() as tmp:
        make_repo(tmp)
        run_cli(tmp, '--baseline')
        ledger(tmp, 'DARK\ttoggle\ttrue\tsrc/toggle.ts\n')
        out = run_cli(tmp)
        assert out.returncode == 1, out.stdout
        lines = [l for l in out.stdout.splitlines() if l.startswith('DARK')]
        assert len(lines) == 1 and 'FAIL' in lines[0], out.stdout
        assert 'deliverable not shipped: src/toggle.ts' in lines[0]
        assert 'SHIP' not in out.stdout


def test_untracked_new_deliverable_is_shipped():
    with tempfile.TemporaryDirectory() as tmp:
        base = make_repo(tmp)
        os.makedirs(os.path.join(tmp, 'src'))
        open(os.path.join(tmp, 'src/toggle.ts'), 'w').write('export {}\n')
        touched = goalrun.changed_paths(base, cwd=tmp)
        assert goalrun.not_shipped('src/toggle.ts', touched, cwd=tmp) == ''
        assert goalrun.not_shipped('./src/toggle.ts', touched, cwd=tmp) == '', 'normpath'
        assert goalrun.not_shipped('src', touched, cwd=tmp) == '', 'directory with a change under it'


def test_deliverable_predating_the_baseline_is_not_shipped():
    with tempfile.TemporaryDirectory() as tmp:
        base = make_repo(tmp)
        touched = goalrun.changed_paths(base, cwd=tmp)
        assert 'unchanged' in goalrun.not_shipped('old.txt', touched, cwd=tmp)


def test_deliverable_outside_the_repo_is_not_shipped():
    touched = {'etc/hosts', 'x', '../x'}
    assert goalrun.not_shipped('/etc/hosts', touched) != ''
    assert goalrun.not_shipped('../x', touched) != ''
    assert goalrun.not_shipped('a/../../x', touched) != ''


def test_committed_deliverable_since_baseline_passes_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        make_repo(tmp)
        run_cli(tmp, '--baseline')
        os.makedirs(os.path.join(tmp, 'docs'))
        open(os.path.join(tmp, 'docs/a.md'), 'w').write('# a\n')
        git(tmp, 'add', '-A')
        git(tmp, 'commit', '-qm', 'docs')
        ledger(tmp, 'DOC\twritten\ttrue\t./docs/a.md\n')
        out = run_cli(tmp)
        assert out.returncode == 0 and 'DONE' in out.stdout, out.stdout


# ---- signatures -------------------------------------------------------------------

UX = goalrun.Row('UX', 'looks ok', 'MANUAL:tuananh', '', '')


def test_manual_without_signature_waits():
    status, note = goalrun.decide(UX, signatures={})
    assert status == 'WAIT' and 'awaiting tuananh' in note, (status, note)


def test_sign_then_pass():
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, 'signoff.tsv')
        goalrun.sign([UX], 'UX', 'tuananh', 'viewed 3 surfaces', path=p, today='2026-09-18')
        sigs = goalrun.load_signatures(p)
    status, note = goalrun.decide(UX, sigs)
    assert status == 'PASS', note
    assert 'signed by tuananh on 2026-09-18 — viewed 3 surfaces' in note


def test_changing_the_wording_voids_the_signature():
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, 'signoff.tsv')
        goalrun.sign([UX], 'UX', 'tuananh', 'ok', path=p)
        sigs = goalrun.load_signatures(p)
    reworded = UX._replace(what='looks ok on mobile too')
    status, note = goalrun.decide(reworded, sigs)
    assert status == 'WAIT' and 'older wording' in note, (status, note)


def test_sign_refuses_empty_signer():
    with tempfile.TemporaryDirectory() as tmp:
        expect_misuse(goalrun.sign, [UX], 'UX', '  ', 'note', path=os.path.join(tmp, 's.tsv'))


def test_sign_refuses_non_owner():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'UX\tlooks ok\tMANUAL:tuananh\n')
        out = run_cli(tmp, '--sign', 'UX', '--who', 'bob')
        assert out.returncode == 2
        assert 'UX is owned by tuananh; --who bob cannot sign it' in out.stderr, out.stderr
        assert not os.path.exists(os.path.join(tmp, goalrun.SIGNOFF))


def test_sign_refuses_non_manual_and_unknown_rows():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'A\tok\ttrue\n')
        assert run_cli(tmp, '--sign', 'A', '--who', 'x').returncode == 2
        assert run_cli(tmp, '--sign', 'NOPE', '--who', 'x').returncode == 2
        assert run_cli(tmp, '--sign', 'A').returncode == 2, '--sign needs --who'


def test_note_cannot_forge_a_second_signature():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'UX\tlooks ok\tMANUAL:tuananh\nSEC\tsecure\tMANUAL:tuananh\n')
        forged = 'fine\nSEC\ttuananh\t2026-01-01\t' + goalrun.what_hash('secure') + '\tpwned'
        assert run_cli(tmp, '--sign', 'UX', '--who', 'tuananh', '--note', forged).returncode == 0
        sigs = goalrun.load_signatures(os.path.join(tmp, goalrun.SIGNOFF))
        assert 'SEC' not in sigs, sigs
        assert '\n' not in sigs['UX']['note'] and '\t' not in sigs['UX']['note']
        out = run_cli(tmp)
        assert out.returncode == 1 and 'waiting on tuananh (SEC)' in out.stdout, out.stdout


def test_cli_sign_turns_a_manual_row_green():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'UX\tlooks ok\tMANUAL:tuananh\n')
        assert run_cli(tmp).returncode == 1
        assert run_cli(tmp, '--sign', 'UX', '--who', ' tuananh ', '--note', 'ok').returncode == 0
        out = run_cli(tmp)
        assert out.returncode == 0 and 'DONE' in out.stdout, out.stdout


# ---- verdict and summary ----------------------------------------------------------

def test_summary_separates_failing_from_waiting():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'DARK\ttoggle\tfalse\nUX\tlooks ok\tMANUAL:tuananh\nOK\tfine\ttrue\n')
        out = run_cli(tmp)
        assert out.returncode == 1
        assert 'NOT DONE — 1 failing (DARK), 1 waiting on tuananh (UX)' in out.stdout, out.stdout


def test_only_waiting_rows_is_still_not_done():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'UX\tlooks ok\tMANUAL:tuananh\nOK\tfine\ttrue\n')
        out = run_cli(tmp)
        assert out.returncode == 1
        assert 'NOT DONE — 1 waiting on tuananh (UX)' in out.stdout, out.stdout
        assert 'failing' not in out.stdout


def test_only_unknown_id_is_misuse():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'EVEN\tok\ttrue\n')
        out = run_cli(tmp, '--only', 'EVN,EVEN')
        assert out.returncode == 2 and 'EVN' in out.stderr, out


def test_only_subset_never_says_done():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'GOOD\tpasses\ttrue\nBAD\tfails\tfalse\nC\tc\ttrue\nD\td\ttrue\n')
        ok = run_cli(tmp, '--only', 'GOOD,C')
        assert ok.returncode == 0 and 'DONE' not in ok.stdout, ok.stdout
        assert 'PHASE OK — 2 rows pass (2 of 4 in ledger)' in ok.stdout, ok.stdout
        bad = run_cli(tmp, '--only', 'BAD')
        assert bad.returncode == 1 and 'PHASE NOT OK — 1 failing (BAD)' in bad.stdout, bad.stdout


def test_modes_are_mutually_exclusive():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'A\tok\ttrue\n')
        assert run_cli(tmp, '--baseline', 'x', '--only', 'A').returncode == 2
        assert run_cli(tmp, '--lint-ledger', '--verify').returncode == 2
        assert run_cli(tmp, '--who', 'x').returncode == 2, '--who without --sign'


# ---- --verify ---------------------------------------------------------------------

def test_verify_needs_a_clean_tree():
    with tempfile.TemporaryDirectory() as tmp:
        make_repo(tmp)
        ledger(tmp, 'A\told is old\tgrep -q old old.txt\t—\techo new > old.txt\n')
        open(os.path.join(tmp, 'old.txt'), 'a').write('dirty\n')
        out = run_cli(tmp, '--verify')
        assert out.returncode == 2 and 'clean working tree' in out.stderr, out


def test_verify_proves_a_check_can_go_red_and_restores():
    with tempfile.TemporaryDirectory() as tmp:
        make_repo(tmp)
        ledger(tmp, 'A\told is old\tgrep -q old old.txt\t—\techo new > old.txt; touch junk\n'
                    'B\tno break\ttrue\n')
        out = run_cli(tmp, '--verify')
        assert out.returncode == 0, out
        assert 'VERIFIED A' in out.stdout and 'skip B — no break column' in out.stdout, out.stdout
        assert open(os.path.join(tmp, 'old.txt')).read() == 'old\n', 'planted change not undone'
        assert not os.path.exists(os.path.join(tmp, 'junk'))
        assert os.path.exists(os.path.join(tmp, goalrun.LEDGER)), 'git clean must spare .testcases/'


def test_verify_flags_a_hollow_check():
    with tempfile.TemporaryDirectory() as tmp:
        make_repo(tmp)
        ledger(tmp, 'A\tfake\ttrue\t—\techo new > old.txt\nB\treal\tgrep -q old old.txt\t—\techo x > old.txt\n')
        out = run_cli(tmp, '--verify')
        assert out.returncode == 1, out
        assert 'HOLLOW A' in out.stdout and 'VERIFIED B' in out.stdout, out.stdout
        assert run_cli(tmp, '--verify', 'B').returncode == 0
        assert run_cli(tmp, '--verify', 'NOPE').returncode == 2


# ---- --lint-ledger ----------------------------------------------------------------

def test_lint_empty_ledger():
    assert goalrun.lint([]) != []


def test_lint_catches_unowned_manual():
    problems = goalrun.lint([goalrun.Row('UX', 'looks ok', 'MANUAL', '', '')])
    assert any('owner' in p for p in problems)


def test_lint_warns_when_mostly_manual_but_allows_one():
    r = lambda i, c: goalrun.Row(i, 'x', c, '', '')
    assert any('30%' in p for p in goalrun.lint([r('A', 'MANUAL:me'), r('B', 'MANUAL:me'),
                                                 r('C', 'npm test')]))
    assert goalrun.lint([r('A', 'npm test'), r('B', 'npm run lint'), r('UX', 'MANUAL:t')]) == []


def test_lint_deliverables_need_a_baseline_but_not_a_break():
    row = goalrun.Row('DARK', 'x', 'npm test', 'src/t.ts', '')
    assert any('baseline' in p for p in goalrun.lint([row], has_baseline=False))
    assert goalrun.lint([row], has_baseline=True) == [], 'no break column is not a problem'


def test_lint_flags_stale_signatures():
    rows = [goalrun.Row('A', 'x', 'npm test', '', '')]
    sigs = {'GONE': {'who': 'x', 'date': 'd', 'what_hash': 'h', 'note': ''}}
    assert any('GONE' in p for p in goalrun.lint(rows, sigs))


def test_cli_lint_ledger_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        make_repo(tmp)
        ledger(tmp, 'A\tunowned\tMANUAL\nD\tship\ttrue\tsrc/x\n')
        bad = run_cli(tmp, '--lint-ledger')
        assert bad.returncode == 1 and 'no owner' in bad.stdout and 'baseline' in bad.stdout, bad.stdout
        run_cli(tmp, '--baseline')
        ledger(tmp, 'A\tsuite\tnpm test\nB\tlint\tnpm run lint\nUX\tok\tMANUAL:t\tsrc/x\n')
        good = run_cli(tmp, '--lint-ledger')
        assert good.returncode == 0, good.stdout
        ledger(tmp, '# nothing\n')
        assert run_cli(tmp, '--lint-ledger').returncode == 1


def test_verify_names_the_exclude_when_only_testcases_is_dirty():
    with tempfile.TemporaryDirectory() as tmp:
        make_repo(tmp)
        # undo the exclude make_repo wrote, so the ledger itself dirties the tree
        open(os.path.join(tmp, '.git', 'info', 'exclude'), 'w').write('')
        ledger(tmp, 'A\tok\ttest -f old.txt\t—\trm old.txt\n')
        out = run_cli(tmp, '--verify')
        assert out.returncode == 2
        assert 'info/exclude' in out.stderr, out.stderr
        assert 'stash' not in out.stderr, 'wrong advice for an unexcluded working dir'


def test_verify_reports_a_break_that_itself_fails():
    with tempfile.TemporaryDirectory() as tmp:
        make_repo(tmp)
        ledger(tmp, 'A\tok\ttest -f old.txt\t—\trm no-such-file\n')
        out = run_cli(tmp, '--verify')
        assert out.returncode == 1
        assert 'BREAK FAILED A' in out.stdout, out.stdout
        assert 'HOLLOW' not in out.stdout, 'a broken break is not evidence the check is hollow'
        assert os.path.exists(os.path.join(tmp, 'old.txt')), 'tree restored'


if __name__ == '__main__':
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            # several tests exercise exit-2 paths that write to stderr on purpose;
            # hold that output and only show it when the test actually fails.
            real, sys.stderr = sys.stderr, io.StringIO()
            try:
                fn()
                noise = sys.stderr.getvalue()
                sys.stderr = real
                print(f'PASS {name}')
            except BaseException as e:
                noise = sys.stderr.getvalue()
                sys.stderr = real
                failures += 1
                print(f'FAIL {name}: {e}')
                for line in noise.splitlines():
                    print(f'    {line}')
    print()
    print(f'{failures} failure(s)' if failures else 'all green')
    sys.exit(1 if failures else 0)
