#!/usr/bin/env python3
"""Self-checks for goalrun.py. Plain asserts, stdlib only: python3 test_goalrun.py"""
import io, json, os, re, shutil, signal, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import goalrun


def make_tree(tmp):
    """A minimal working tree with one real file — no git anywhere. `--verify` clones
    whatever is on disk, so nothing here needs version control to be meaningful."""
    open(os.path.join(tmp, 'old.txt'), 'w').write('old\n')


def ledger(tmp, text):
    """Write the ledger where the CLI looks for it; return its path."""
    d = os.path.join(tmp, goalrun.GOAL_DIR)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, 'ledger.tsv')
    open(path, 'w', encoding='utf-8').write(text)
    return path


def run_cli(cwd, *args, timeout=None):
    """`timeout` only where a hang is the very thing under test: a test that hangs reports
    nothing, so the run has to be cut short and read as a failure."""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'goalrun.py')
    return subprocess.run([sys.executable, script, *args],
                          cwd=cwd, capture_output=True, text=True, timeout=timeout)


def expect_misuse(fn, *args, **kw):
    try:
        fn(*args, **kw)
    except goalrun.Misuse:
        return
    raise AssertionError('expected Misuse')


def fake_runner(tmp, output, code=0):
    """A stand-in test runner: prints `output`, exits `code`. Lets the zero-tests-matched
    gate be tested without any real framework installed."""
    path = os.path.join(tmp, 'pytest')          # the name is what makes the command a runner
    open(path, 'w').write(f'#!/bin/sh\ncat <<\'GOALRUN_EOF\'\n{output}\nGOALRUN_EOF\nexit {code}\n')
    os.chmod(path, 0o755)
    return path


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


# ---- the run lock -----------------------------------------------------------------

def _script():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'goalrun.py')


def _wait_for(path, seconds=20):
    deadline = time.time() + seconds
    while not os.path.exists(path) and time.time() < deadline:
        time.sleep(0.02)
    assert os.path.exists(path), f'{path} never appeared'


def test_a_second_run_refuses_to_race_the_first_and_names_the_holder():
    """Two runs building one tree produce reds that belong to neither. The refusal names the
    holder and when it started, so a user facing a forty-minute --verify can decide whether
    to wait or to kill it."""
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        ledger(tmp, 'A\tslow\tsleep 3\t—\trm -f old.txt\n')
        first = subprocess.Popen([sys.executable, _script()], cwd=tmp,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            _wait_for(os.path.join(tmp, goalrun.LOCK))
            out = run_cli(tmp, '--only', 'A')
            assert out.returncode == 2 and 'another goalrun' in out.stderr, out
            assert re.search(r'pid \d+ since \d\d:\d\d:\d\d', out.stderr), out.stderr
        finally:
            first.wait()
        assert run_cli(tmp, '--only', 'A').returncode == 0, 'lock not released at exit'


def test_a_killed_run_leaves_no_lock_to_wedge_the_next():
    """SIGKILL: no atexit, no finally, no drop_lock. The kernel drops an flock with its holder,
    so whatever the dead run left in the file is just bytes."""
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        ledger(tmp, 'A\tslow\tsleep 30\t—\trm -f old.txt\n')
        first = subprocess.Popen([sys.executable, _script()], cwd=tmp,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _wait_for(os.path.join(tmp, goalrun.LOCK))
        first.kill(); first.wait()
        ledger(tmp, 'A\tfast\ttrue\t—\trm -f old.txt\n')
        assert run_cli(tmp, '--only', 'A').returncode == 0
        for leftover in ('', 'not-a-pid\n', 'pid 999999 since 00:00:00\n'):
            open(os.path.join(tmp, goalrun.LOCK), 'w').write(leftover)
            assert run_cli(tmp, '--only', 'A').returncode == 0, f'wedged by {leftover!r}'


def test_an_unwritable_lock_directory_is_a_refusal_not_a_hang():
    if os.geteuid() == 0:
        return                                # root writes through 0555
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        ledger(tmp, 'A\tfast\ttrue\t—\trm -f old.txt\n')
        held = os.path.join(tmp, os.path.dirname(goalrun.LOCK))
        os.chmod(held, 0o555)
        try:
            out = run_cli(tmp, '--only', 'A', timeout=30)
        finally:
            os.chmod(held, 0o755)
        assert out.returncode == 2 and 'run lock' in out.stderr, out


# ---- running checks ---------------------------------------------------------------

def test_check_passes_on_exit_zero():
    ok, note, _hung = goalrun.run_check('true')
    assert ok, note


def test_check_fails_on_nonzero_with_last_line():
    ok, note, _hung = goalrun.run_check('echo boom >&2; exit 1')
    assert not ok and 'boom' in note


def test_check_times_out_and_kills_the_group():
    t = time.time()
    ok, note, hung = goalrun.run_check('sleep 30', timeout=1)
    assert hung is True, 'a timeout is reported structurally, not by its wording'
    assert not ok and 'timed out after 1s' in note
    assert time.time() - t < 5


def test_background_child_does_not_hold_the_run_open():
    t = time.time()
    ok, _, _hung = goalrun.run_check('(sleep 5 &) ; exit 0')
    assert ok
    assert time.time() - t < 3, 'the pipe was held by the orphan; use a file, not communicate()'


def test_non_utf8_output_does_not_crash():
    ok, note, _hung = goalrun.run_check("printf '\\xff ok'")
    assert ok, note
    ok, note, _hung = goalrun.run_check("printf '\\xff'; exit 1")
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


def test_run_check_takes_a_cwd():
    with tempfile.TemporaryDirectory() as tmp:
        open(os.path.join(tmp, 'here.txt'), 'w').write('x\n')
        ok, _, _ = goalrun.run_check('test -f here.txt', cwd=tmp)
        assert ok
        ok, _, _ = goalrun.run_check('test -f here.txt')
        assert not ok, 'ran in the real process cwd, not the one passed in'


# ---- the zero-tests-matched gate ---------------------------------------------------

def test_a_check_whose_tests_were_all_skipped_is_not_a_pass():
    """`OK (skipped=1)` exits 0 and reads as PASS, having exercised nothing. A row whose only
    test is `@skip` measures exactly as much as a row whose filter matched nothing."""
    for text in ('Ran 1 test in 0.000s\n\nOK (skipped=1)\n',
                 'Ran 3 tests in 0.001s\n\nOK (skipped=3)\n',
                 '3 skipped in 0.12s\n'):
        assert goalrun._zero_tests_matched(text), text
    # a run where something actually passed is fine, skips and all
    for text in ('Ran 4 tests in 0.01s\n\nOK (skipped=1)\n', '2 passed, 1 skipped in 0.3s\n'):
        assert not goalrun._zero_tests_matched(text), text


def test_lint_flags_a_check_that_searches_text_instead_of_running_a_test():
    rows = [goalrun.Row('TAX', 'REQ-1 the base includes the inline note',
                        "grep -q 'AddedLine' src/tax.cs", '', 'rm -f x'),
            goalrun.Row('REAL', 'REQ-2 rounds half-up',
                        'python3 -m unittest -q tests.test_tax.TC_002', '', 'rm -f x')]
    problems = goalrun.lint(rows)
    assert any('rows TAX search text' in p for p in problems), problems
    assert not any('REAL' in p for p in problems), problems
    # a test runner whose command also greps its own output is still a test
    piped = [goalrun.Row('A', 'REQ-1 x', 'pytest -q tests/test_a.py | grep -q passed', '',
                         'rm -f x')]
    assert not any('search text' in p for p in goalrun.lint(piped)), goalrun.lint(piped)


def test_zero_tests_spellings_all_fail_the_check():
    with tempfile.TemporaryDirectory() as tmp:
        spellings = ('no tests ran', 'No test matches', 'collected 0 items',
                    '0 passing (2ms)', 'Test Run Successful.\nPassed: 0, Failed: 0')
        for text in spellings:
            script = fake_runner(tmp, text)
            ok, note, _ = goalrun.run_check(f'sh {script}')
            assert not ok and 'ran no test' in note, (text, note)


def test_a_check_that_is_not_a_runner_may_say_zero_tests_failed():
    """A lint or a script that reports `0 tests failed` is a pass; the gate judges only what a
    test runner printed, because that is the only output where "zero" means "nothing ran"."""
    ok, note, _ = goalrun.run_check('echo "lint ok, 0 tests failed"')
    assert ok, note


def test_a_runner_that_ran_tests_may_say_zero_failed_or_skipped():
    with tempfile.TemporaryDirectory() as tmp:
        for text in ('12 tests, 0 tests failed', 'Ran 4 tests\n0 tests skipped\nOK',
                     'Tests: 0 skipped, 5 passed', '0 errors, 3 tests'):
            script = fake_runner(tmp, text)
            ok, note, _ = goalrun.run_check(f'sh {script}')
            assert ok, (text, note)


def test_a_runner_that_prints_nothing_is_not_a_pass():
    """`cd dir \\&\\& dotnet test ...` — the escape leaked into the ledger, `sh -c` ran `cd` with two
    stray arguments and exited 0, dotnet never ran, and eight rows read DONE. A runner that ran
    anything says so; silence is the command never reaching it."""
    with tempfile.TemporaryDirectory() as tmp:
        script = fake_runner(tmp, '')                       # named pytest, prints nothing
        ok, note, _ = goalrun.run_check(f'sh {script}')
        assert not ok and 'printed nothing' in note, note
        # the shape that caused it, end to end: exit 0, no output, no test
        ok, note, _ = goalrun.run_check(f'cd {tmp} \\&\\& pytest -q')
        assert not ok, note


def test_lint_names_a_row_with_escaped_and_and():
    rows = [goalrun.Row('A', 'REQ-1 x', 'cd src \\&\\& dotnet test --filter X', '', 'rm -f x'),
            goalrun.Row('B', 'REQ-2 y', "grep -E 'a\\|b' f.txt | pytest -q", '', 'rm -f x')]
    problems = goalrun.lint(rows)
    assert any('rows A contain' in p for p in problems), problems
    assert not any('B' in p and 'contain' in p for p in problems), 'a single \\| is grep alternation'


def test_zero_tests_gate_does_not_false_positive_on_a_normal_pass():
    with tempfile.TemporaryDirectory() as tmp:
        for text in ('42 tests, 0 failures', '15 passing (300ms)', 'Ran 10 tests OK',
                    'Tests: 0 failed, 12 passed'):
            script = fake_runner(tmp, text)
            ok, note, _ = goalrun.run_check(f'sh {script}')
            assert ok, (text, note)


def test_cli_row_fails_when_its_runner_matched_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        script = fake_runner(tmp, 'collected 0 items')
        ledger(tmp, f'A\tsuite passes\tsh {script}\n')
        out = run_cli(tmp)
        assert out.returncode == 1, out.stdout
        assert 'FAIL' in out.stdout and 'ran no test' in out.stdout, out.stdout


# ---- baseline & shipping, by content -----------------------------------------------

def test_baseline_records_the_whole_tree_before_any_ledger_exists():
    """Taken at step 1, before the ledger names anything — because the moment it must be
    taken is before the first edit, and the ledger does not exist yet then."""
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, 'src'))
        os.makedirs(os.path.join(tmp, 'obj'))
        open(os.path.join(tmp, 'src/a.txt'), 'w').write('v1\n')
        open(os.path.join(tmp, 'obj/out.bin'), 'w').write('build output\n')
        out = run_cli(tmp, '--baseline')                 # no ledger anywhere
        assert out.returncode == 0, out
        data = json.load(open(os.path.join(tmp, goalrun.BASELINE)))
        assert 'src/a.txt' in data['files']
        assert 'obj/out.bin' not in data['files'], 'build output is not a deliverable'
        assert not any(k.startswith('.testcases') for k in data['files'])
        # a second one is refused: it would move every mark to now
        again = run_cli(tmp, '--baseline')
        assert again.returncode == 2 and 'already exists' in again.stderr, again
        assert run_cli(tmp, '--baseline', '--reset').returncode == 0
        assert run_cli(tmp, '--reset').returncode == 2, '--reset without --baseline is misuse'


def test_a_huge_file_is_marked_by_size_and_mtime_not_hashed():
    """A 300MB database dump under docs/ is not a deliverable, and reading it is most of the
    walk. Its mark is size+mtime; a rewrite still registers because the mtime moves."""
    with tempfile.TemporaryDirectory() as tmp:
        big = os.path.join(tmp, 'dump.mdb')
        with open(big, 'wb') as f:
            f.seek(goalrun.BIG_FILE + 1); f.write(b'x')      # sparse: no real 32MB written
        mark = goalrun._mark(big)
        assert mark.startswith('big:'), mark
        base = {'dump.mdb': mark}
        assert goalrun.not_shipped('dump.mdb', base, cwd=tmp) == 'unchanged since baseline'
        os.utime(big, (1, 1))
        assert goalrun.not_shipped('dump.mdb', base, cwd=tmp) == ''
        small = os.path.join(tmp, 'a.txt'); open(small, 'w').write('x\n')
        assert not goalrun._mark(small).startswith('big:')


def test_shipping_is_content_against_the_baseline():
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, 'src'))
        path = os.path.join(tmp, 'src/a.txt')
        open(path, 'w').write('v1\n')
        base = {'src/a.txt': goalrun._digest(path)}
        assert goalrun.not_shipped('src/a.txt', base, cwd=tmp) == 'unchanged since baseline'
        os.utime(path, None)                              # touch moves mtime, not content
        assert goalrun.not_shipped('src/a.txt', base, cwd=tmp) == 'unchanged since baseline'
        open(path, 'w').write('v2\n')
        assert goalrun.not_shipped('src/a.txt', base, cwd=tmp) == ''
        assert goalrun.not_shipped('./src/a.txt', base, cwd=tmp) == '', 'normpath'


def test_a_file_the_baseline_never_saw_is_new_and_therefore_shipped():
    """The ledger is written after the baseline, so a deliverable can name a file that did
    not exist at step 1. Absent then, present now: that is this run's work."""
    with tempfile.TemporaryDirectory() as tmp:
        open(os.path.join(tmp, 'new.txt'), 'w').write('x\n')
        assert goalrun.not_shipped('new.txt', {}, cwd=tmp) == ''
        assert goalrun.not_shipped('missing.txt', {}, cwd=tmp) == 'does not exist'


def test_directory_deliverable_ships_when_anything_inside_it_changes():
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, 'out')
        os.makedirs(d)
        open(os.path.join(d, 'a.txt'), 'w').write('1\n')
        base = {'out/a.txt': goalrun._digest(os.path.join(d, 'a.txt'))}
        assert goalrun.not_shipped('out', base, cwd=tmp) == 'unchanged since baseline'
        open(os.path.join(d, 'b.txt'), 'w').write('2\n')             # added
        assert goalrun.not_shipped('out', base, cwd=tmp) == ''
        os.remove(os.path.join(d, 'b.txt'))
        os.remove(os.path.join(d, 'a.txt'))                             # removed
        assert goalrun.not_shipped('out', base, cwd=tmp) == ''


def test_work_done_before_the_baseline_reads_unchanged_end_to_end():
    """The trap two pressure runs walked into: edit first, baseline second. The script cannot
    know the edit was this run's, so it says `unchanged` — and the fix is to take the baseline
    before touching anything, never to retake it after."""
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, 'src'))
        open(os.path.join(tmp, 'src/a.py'), 'w').write('done already\n')
        run_cli(tmp, '--baseline')
        ledger(tmp, 'A\tREQ-1\ttrue\tsrc/a.py\trm -f src/a.py\n')
        out = run_cli(tmp)
        assert 'unchanged since baseline' in out.stdout, out.stdout


def test_deliverable_without_baseline_exits_before_any_check_runs():
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        ledger(tmp, 'DARK\ttoggle\ttouch ran.marker\tsrc/toggle.ts\n')
        out = run_cli(tmp)
        assert out.returncode == 2, out.stdout
        assert 'DARK' in out.stderr and 'baseline' in out.stderr, out.stderr
        assert not os.path.exists(os.path.join(tmp, 'ran.marker')), 'no check may run first'


def test_baseline_rejects_an_argument():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'A\tx\ttrue\n')
        out = run_cli(tmp, '--baseline', 'deadbeef')
        assert out.returncode == 2 and 'no argument' in out.stderr, out.stderr
        assert not os.path.exists(os.path.join(tmp, goalrun.BASELINE))


def test_passing_check_with_missing_deliverable_fails_that_row():
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        ledger(tmp, 'DARK\ttoggle\ttrue\tsrc/toggle.ts\n')
        run_cli(tmp, '--baseline')
        out = run_cli(tmp)
        assert out.returncode == 1, out.stdout
        lines = [l for l in out.stdout.splitlines() if l.startswith('DARK')]
        assert len(lines) == 1 and 'FAIL' in lines[0], out.stdout
        assert 'deliverable not shipped: src/toggle.ts' in lines[0]
        assert 'does not exist' in lines[0]


def test_missing_deliverable_is_not_shipped():
    assert goalrun.not_shipped('ghost.txt', {'ghost.txt': 'deadbeef'}) == 'does not exist'


def test_deliverable_outside_the_repo_is_not_shipped():
    assert goalrun.not_shipped('/etc/hosts', {}) != ''
    assert goalrun.not_shipped('../x', {}) != ''
    assert goalrun.not_shipped('a/../../x', {}) != ''


def test_full_baseline_run_verify_flow_needs_no_git_anywhere():
    with tempfile.TemporaryDirectory() as tmp:
        assert not os.path.isdir(os.path.join(tmp, '.git'))
        open(os.path.join(tmp, 'src.py'), 'w').write('def f(): return 1\n')
        ledger(tmp, 'BUILD\tfunction still there\tgrep -q "def f" src.py\t—\t'
                    'sed -i.bak "s/def f/def g/" src.py\n'
                    'SHIP\tartifact written\ttrue\tout.txt\t—\n')
        assert run_cli(tmp, '--baseline').returncode == 0
        open(os.path.join(tmp, 'out.txt'), 'w').write('built\n')
        out = run_cli(tmp)
        assert out.returncode == 0 and 'DONE' in out.stdout, out.stdout
        verified = run_cli(tmp, '--verify', 'BUILD')
        assert verified.returncode == 0 and 'VERIFIED BUILD' in verified.stdout, verified.stdout
        assert not os.path.isdir(os.path.join(tmp, '.git')), 'must not have needed git'
        assert open(os.path.join(tmp, 'src.py')).read() == 'def f(): return 1\n'


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


def test_manual_like_check_is_a_shell_command_not_a_manual_row():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'A\tok\tMANUALIZE thing\n')
        out = run_cli(tmp)
        assert out.returncode == 1, out.stdout
        assert 'FAIL' in out.stdout and 'WAIT' not in out.stdout, out.stdout


def test_only_empty_selection_is_misuse():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'A\tok\ttrue\n')
        out = run_cli(tmp, '--only', ',')
        assert out.returncode == 2 and 'no row ids given' in out.stderr, out.stderr
        assert run_cli(tmp, '--verify', ',').returncode == 2


def test_ctrl_c_kills_the_running_check():
    with tempfile.TemporaryDirectory() as tmp:
        # a marker unique to this run: `pgrep -f 'sleep 30'` matched any sleep on the machine,
        # so an unrelated process made the test fail and read like a leaked check
        mark = f'goalrun-ctrlc-{os.getpid()}-{int(time.time())}'
        ledger(tmp, f'A\tslow\tsleep 30 # {mark}\n')
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'goalrun.py')
        p = subprocess.Popen([sys.executable, script], cwd=tmp,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        time.sleep(1.0)
        os.kill(p.pid, signal.SIGINT)
        p.wait(timeout=10)
        time.sleep(0.5)
        r = subprocess.run(['pgrep', '-f', mark], capture_output=True)
        assert r.returncode != 0, 'the check outlived Ctrl-C'


def test_a_row_whose_own_check_hangs_under_the_break_is_not_verified():
    """A hang is not a red. Counting it as proof is the fake green this flag exists to kill —
    and the sweep already calls the same event `stuck` when it happens to a sibling."""
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        # passes at once while the file is there, hangs once the break removes it
        ledger(tmp, 'A\thangs\ttest -f old.txt || sleep 30\t—\trm -f old.txt\n')
        out = run_cli(tmp, '--verify', '--timeout', '1')
        assert out.returncode == 1, out.stdout
        assert 'STUCK A' in out.stdout and 'VERIFIED' not in out.stdout, out.stdout


def test_a_check_whose_output_says_timed_out_is_still_a_red_sibling():
    """`curl: (28) Connection timed out` is a failing check, not a hung one; classifying it by
    wording would silently downgrade a BLAST finding."""
    row = goalrun.Row('A', 'x', 'true', 'src/x.py', 'rm -f src/x.py')
    sib = goalrun.Row('SIB', 'y', 'echo "connection timed out."; exit 1', 'src/y.py', '')
    same, crossed, stuck, _, _ = goalrun.blast_radius(row, [row, sib], 5)
    assert crossed == ['SIB'] and stuck == [], (crossed, stuck)


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
        assert 'PHASE OK — 2 row(s) pass (2 of 4 in ledger)' in ok.stdout, ok.stdout
        bad = run_cli(tmp, '--only', 'BAD')
        assert bad.returncode == 1 and 'PHASE NOT OK — 1 failing (BAD)' in bad.stdout, bad.stdout


def test_modes_are_mutually_exclusive():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'A\tok\ttrue\n')
        assert run_cli(tmp, '--baseline', 'x', '--only', 'A').returncode == 2
        assert run_cli(tmp, '--lint-ledger', '--verify').returncode == 2
        assert run_cli(tmp, '--who', 'x').returncode == 2, '--who without --sign'


# ---- --verify: the tree is cloned, never mutated -----------------------------------

def test_verify_never_touches_the_real_tree_for_a_deleting_break():
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        ledger(tmp, 'A\told is old\tgrep -q old old.txt\t—\trm -f old.txt\n'
                    'B\tno break\ttrue\n')
        out = run_cli(tmp, '--verify')
        assert out.returncode == 0, out
        assert 'VERIFIED A' in out.stdout and 'skip B — no break column' in out.stdout, out.stdout
        assert open(os.path.join(tmp, 'old.txt')).read() == 'old\n', \
            'the break must have deleted the file in a clone, not the real tree'


def test_verify_never_touches_the_real_tree_for_a_creating_break():
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        ledger(tmp, 'A\tno junk file\ttest ! -f junk.txt\t—\ttouch junk.txt\n')
        out = run_cli(tmp, '--verify')
        assert out.returncode == 0 and 'VERIFIED A' in out.stdout, out.stdout
        assert not os.path.exists(os.path.join(tmp, 'junk.txt')), \
            'the break created a file in the real tree, not only the clone'


def test_verify_needs_no_clean_tree_uncommitted_work_is_safe_by_construction():
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        open(os.path.join(tmp, 'old.txt'), 'a').write('uncommitted work in progress\n')
        before = open(os.path.join(tmp, 'old.txt')).read()
        ledger(tmp, 'A\tgreps for old\tgrep -q old old.txt\t—\techo new > old.txt\n')
        out = run_cli(tmp, '--verify')
        assert out.returncode == 0 and 'VERIFIED A' in out.stdout, out.stdout
        assert open(os.path.join(tmp, 'old.txt')).read() == before, \
            'the uncommitted edit must survive --verify byte-for-byte'


def test_verify_flags_a_hollow_check():
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        ledger(tmp, 'A\tfake\ttrue\t—\techo new > old.txt\n'
                    'B\treal\tgrep -q old old.txt\t—\techo x > old.txt\n')
        out = run_cli(tmp, '--verify')
        assert out.returncode == 1, out
        assert 'HOLLOW A' in out.stdout and 'VERIFIED B' in out.stdout, out.stdout
        assert run_cli(tmp, '--verify', 'B').returncode == 0
        assert run_cli(tmp, '--verify', 'NOPE').returncode == 2


def test_break_editing_an_unrelated_file_is_still_hollow_in_the_clone():
    """The check never reads the file the break edits. If the row still went red, the
    mutation would have to have leaked out of the clone some other way than the check
    actually running against it — this is the property that pins the clone is real."""
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        open(os.path.join(tmp, 'unrelated.txt'), 'w').write('untouched\n')
        ledger(tmp, 'A\talways passes\ttrue\t—\techo mutated > unrelated.txt\n')
        out = run_cli(tmp, '--verify')
        assert out.returncode == 1 and 'HOLLOW A' in out.stdout, out.stdout
        assert open(os.path.join(tmp, 'unrelated.txt')).read() == 'untouched\n'


def test_verify_clones_the_ledger_directory_too():
    """A check may itself live under .testcases/ — `--verify` has to clone that directory
    along with everything else for such a check to even run, and never touch the real copy."""
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        chk = os.path.join(tmp, goalrun.GOAL_DIR, 'chk.sh')
        os.makedirs(os.path.dirname(chk), exist_ok=True)
        open(chk, 'w').write('grep -q old old.txt\n')
        ledger(tmp, 'A\told is old\tsh .testcases/goalrun/chk.sh\t—\trm -f old.txt\n')
        out = run_cli(tmp, '--verify')
        assert out.returncode == 0 and 'VERIFIED A' in out.stdout, out.stdout
        assert open(chk).read() == 'grep -q old old.txt\n', 'the real check script was touched'


def test_verify_reports_a_break_that_itself_fails():
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        ledger(tmp, 'A\tok\ttest -f old.txt\t—\trm no-such-file\n')
        out = run_cli(tmp, '--verify')
        assert out.returncode == 1
        assert 'BREAK FAILED A' in out.stdout, out.stdout
        assert 'HOLLOW' not in out.stdout, 'a broken break is not evidence the check is hollow'
        assert os.path.exists(os.path.join(tmp, 'old.txt')), 'real tree untouched'


def test_break_that_changes_nothing_in_the_clone_is_break_failed():
    """A break that exits 0 but never actually touches the clone — e.g. because it names an
    absolute path back to the original tree — must not read as VERIFIED against unmutated
    code. `true` is exactly that: a break which always exits 0 and changes nothing."""
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        ledger(tmp, 'A\told is old\tgrep -q old old.txt\t—\ttrue\n')
        out = run_cli(tmp, '--verify')
        assert out.returncode == 1, out.stdout
        assert 'BREAK FAILED A' in out.stdout, out.stdout
        assert 'changed nothing in the clone' in out.stdout, out.stdout


# ---- --lint-ledger ----------------------------------------------------------------

def test_lint_empty_ledger():
    assert goalrun.lint([]) != []


def test_lint_catches_unowned_manual():
    problems = goalrun.lint([goalrun.Row('UX', 'looks ok', 'MANUAL:', '', '')])
    assert any('owner' in p for p in problems)


def test_load_rejects_manual_row_naming_a_deliverable():
    with tempfile.TemporaryDirectory() as tmp:
        expect_misuse(goalrun.load, ledger(tmp, 'UX\tlooks ok\tMANUAL:t\tsrc/x\n'))
        out = run_cli(tmp, '--lint-ledger')
        assert out.returncode == 2 and 'not both' in out.stderr, out.stderr


def test_load_rejects_manual_without_colon():
    with tempfile.TemporaryDirectory() as tmp:
        expect_misuse(goalrun.load, ledger(tmp, 'UX\tlooks ok\tMANUAL\n'))
        assert 'owner' in run_cli(tmp).stderr


def test_lint_warns_when_mostly_manual_but_allows_one():
    r = lambda i, c: goalrun.Row(i, 'x', c, '', '' if c.startswith('MANUAL:') else 'rm -f x')
    assert any('30%' in p for p in goalrun.lint([r('A', 'MANUAL:me'), r('B', 'MANUAL:me'),
                                                 r('C', 'npm test')]))
    assert goalrun.lint([r('A', 'npm test'), r('B', 'npm run lint'), r('UX', 'MANUAL:t')]) == []


def test_lint_deliverables_need_a_baseline():
    row = goalrun.Row('DARK', 'x', 'npm test', 'src/t.ts', 'rm src/t.ts')
    assert any('baseline' in p for p in goalrun.lint([row], has_baseline=False))
    assert goalrun.lint([row], has_baseline=True) == []


def test_lint_flags_a_row_that_can_never_go_red():
    """A missing break is the cheapest way to fake a green ledger — lint has to say so."""
    rows = [goalrun.Row('A', 'suite passes', 'true', '', ''),
            goalrun.Row('UX', 'looks ok', 'MANUAL:t', '', '')]
    problems = goalrun.lint(rows)
    assert any('no break' in p and 'A' in p for p in problems), problems
    assert any('test-first' in p for p in problems), 'legitimate waiver reason not named'
    assert not any('UX' in p for p in problems), 'a MANUAL row has nothing to break'


def test_lint_honours_a_verify_ok_waiver():
    rows = [goalrun.Row('A', 'suite passes', 'true', '', '')]
    waived = {'verify-ok': {'A': 'smoke row'}, 'no-row-ok': {}}
    assert goalrun.lint(rows, waived=waived) == []


def test_waivers_need_a_reason():
    with tempfile.TemporaryDirectory() as tmp:
        path = ledger(tmp, '# verify-ok: A\n# verify-ok: B — measured upstream\n'
                           '# no-row-ok: REQ-1 — out of scope\nA\tx\ttrue\n')
        w = goalrun.waivers(path)
        assert w['verify-ok'] == {'B': 'measured upstream'}, w
        assert w['no-row-ok'] == {'REQ-1': 'out of scope'}, w


def test_a_reasonless_waiver_cannot_eat_its_own_id():
    """`# verify-ok: REQ-A-001` must not parse as id REQ-A with reason 001 — that waives
    a different row than the one written, and waives it without a reason at all."""
    with tempfile.TemporaryDirectory() as tmp:
        path = ledger(tmp, '# verify-ok: REQ-A-001\n'
                           '# verify-ok: REQ-A-010 - \n'
                           '# no-row-ok: REQ-B-002 — ships from the docs repo\n'
                           'A\tx\ttrue\n')
        w = goalrun.waivers(path)
        assert w['verify-ok'] == {}, w
        assert w['no-row-ok'] == {'REQ-B-002': 'ships from the docs repo'}, w
        rows = [goalrun.Row('REQ-A-1', 'x', 'true', '', ''),
                goalrun.Row('REQ-A-10', 'y', 'true', '', '')]
        assert len(goalrun.lint(rows, waived=w)) == 1, 'neither row is waived'


def test_an_empty_requirements_file_is_misuse():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'A\tx\ttrue\t\trm -f x\n')
        open(os.path.join(tmp, 'reqs.txt'), 'w').write('# only a comment\n\n')
        out = run_cli(tmp, '--lint-ledger', '--requirements', 'reqs.txt')
        assert out.returncode == 2 and 'no requirement ids' in out.stderr, out.stderr


def test_lint_says_when_coverage_was_not_checked():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'A\tx\ttrue\t\trm -f x\n')
        out = run_cli(tmp, '--lint-ledger')
        assert out.returncode == 0 and 'coverage not checked' in out.stdout, out.stdout


def test_blast_separates_shared_deliverables_from_crossed_ones():
    """Two rows shipping one file go red together on purpose; a row shipping something else
    going red means its check cannot tell this defect from its own."""
    with tempfile.TemporaryDirectory() as tmp:
        open(os.path.join(tmp, 'a.txt'), 'w').write('a\n')
        open(os.path.join(tmp, 'b.txt'), 'w').write('b\n')
        # SIB ships a.txt like A does; WIDE greps both files, so it reddens on A's break too
        ledger(tmp, 'A\tx\ttest -f a.txt\ta.txt\trm -f a.txt\n'
                    'SIB\ty\tgrep -q a a.txt\ta.txt\t—\n'
                    'WIDE\tz\tcat a.txt b.txt\tb.txt\t—\n')
        out = run_cli(tmp, '--verify', 'A', '--blast')
        assert 'shared A — SIB' in out.stdout, out.stdout
        assert 'BLAST A' in out.stdout and 'WIDE' in out.stdout, out.stdout
        assert out.returncode == 1, out.stdout
        # a row waived from needing a break is undiscriminating on purpose: not its fault
        ledger(tmp, '# verify-ok: WIDE — reads every file; it reddens on any defect\n'
                    'A\tx\ttest -f a.txt\ta.txt\trm -f a.txt\n'
                    'WIDE\tz\tcat a.txt b.txt\tb.txt\t—\n')
        quiet = run_cli(tmp, '--verify', 'A', '--blast')
        assert 'BLAST' not in quiet.stdout and quiet.returncode == 0, quiet.stdout


def test_blast_normalises_the_deliverable_before_comparing():
    """`./src/x` and `src/x` are one file; comparing raw strings flips shared into BLAST."""
    a = goalrun.Row('A', 'x', 'true', 'src/x.py', 'rm -f src/x.py')
    b = goalrun.Row('B', 'y', 'false', './src/x.py', '')
    c = goalrun.Row('C', 'z', 'exit 1', 'src/other.py', '')
    same, crossed, stuck, swept, _ = goalrun.blast_radius(a, [a, b, c], 5)
    assert same == ['B'] and crossed == ['C'] and stuck == [], (same, crossed, stuck)
    assert swept == 2, swept


def test_blast_separates_a_hung_check_from_a_confused_one():
    slow = goalrun.Row('SLOW', 'y', 'sleep 5', 'src/other.py', '')
    row = goalrun.Row('A', 'x', 'true', 'src/x.py', 'rm -f src/x.py')
    same, crossed, stuck, _, _ = goalrun.blast_radius(row, [row, slow], 1)
    assert stuck == ['SLOW'] and crossed == [] and same == [], (same, crossed, stuck)


def test_blast_runs_one_identical_check_once():
    """Rows sharing a command share its result — the pathological ledger is also the
    expensive one, so the sweep must not pay for it twice."""
    row = goalrun.Row('A', 'x', 'true', 'src/x.py', 'rm -f src/x.py')
    twins = [goalrun.Row(i, 'y', 'sleep 0.4; false', 'src/y.py', '') for i in ('B', 'C', 'D')]
    start = time.time()
    same, crossed, stuck, swept, _ = goalrun.blast_radius(row, [row] + twins, 5)
    assert swept == 1, swept
    assert crossed == ['B', 'C', 'D'], crossed
    assert time.time() - start < 1.2, 'the shared command ran more than once'


def test_lint_flags_a_waiver_pointing_at_nothing():
    rows = [goalrun.Row('A', 'REQ-1 x', 'true', '', 'rm -f x')]
    waived = {'verify-ok': {'GONE': 'stale'}, 'no-row-ok': {'REQ-9': 'stale'}}
    problems = goalrun.lint(rows, waived=waived, requirements=['REQ-1'])
    assert any('verify-ok: GONE' in p for p in problems), problems
    assert any('no-row-ok: REQ-9' in p for p in problems), problems
    # without a requirement list there is nothing to check coverage waivers against
    assert not any('REQ-9' in p for p in goalrun.lint(rows, waived=waived))


def test_lint_refuses_a_ledger_that_waives_most_of_the_list():
    rows = [goalrun.Row('A', 'REQ-1 x', 'true', '', 'rm -f x')]
    reqs = [f'REQ-{n}' for n in range(1, 11)]
    # nine ids waived one by one, each with its own reason — the shape that passed before
    waived = {'verify-ok': {}, 'no-row-ok': {r: f'reason {r}' for r in reqs[1:]}}
    problems = goalrun.lint(rows, waived=waived, requirements=reqs)
    assert any('9 of 10 requirements are waived' in p for p in problems), problems
    # a third of the list is still a gate
    ok = {'verify-ok': {}, 'no-row-ok': {r: 'ships elsewhere' for r in reqs[:2]}}
    rows = [goalrun.Row(r, f'{r} holds', 'true', '', 'rm -f x') for r in reqs[2:]]
    assert not goalrun.lint(rows, waived=ok, requirements=reqs), goalrun.lint(
        rows, waived=ok, requirements=reqs)


def test_lint_prints_the_coverage_ratio():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, '# no-row-ok: REQ-2 — ships in the other repo\n'
                    'A\tREQ-1 holds\ttrue\t—\trm -f old.txt\n')
        open(os.path.join(tmp, 'reqs.txt'), 'w').write('REQ-1\nREQ-2\n')
        out = run_cli(tmp, '--lint-ledger', '--requirements', 'reqs.txt')
        assert 'coverage: 2 requirement(s) · 1 carried by rows · 1 waived (50%)' in out.stdout, \
            out.stdout


def test_requirements_file_rejects_a_line_that_is_not_an_id():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'reqs.txt')
        open(path, 'w').write('REQ-A-001: fine\n1. pasted from the spec\n')
        expect_misuse(goalrun.read_requirements, path)


def test_a_sibling_starved_by_the_deadline_is_unswept_not_stuck():
    """A slow check the sweep ran out of time for has not hung — filing it as `stuck` would
    turn a real BLAST into a footnote and let verify exit 0."""
    row = goalrun.Row('A', 'x', 'true', 'src/x.py', 'rm -f src/x.py')
    slow_red = goalrun.Row('SLOW-RED', 'y', 'sleep 3; exit 1', 'src/y.py', '')
    same, crossed, stuck, swept, unswept = goalrun.blast_radius(
        row, [row, slow_red], 60, allowance=1)
    assert unswept == ['SLOW-RED'], unswept
    assert stuck == [] and crossed == [] and swept == 0, (stuck, crossed, swept)


def test_the_allowance_bounds_the_whole_sweep_not_each_check():
    """Distinct slow commands inside one sweep must not each get the full budget."""
    row = goalrun.Row('A', 'x', 'true', 'src/x.py', 'rm -f src/x.py')
    slow = [goalrun.Row(f'S{i}', 'y', f'sleep 4; exit {i}', 'src/y.py', '') for i in range(1, 4)]
    began = time.monotonic()
    *_, unswept = goalrun.blast_radius(row, [row] + slow, 60, allowance=2)
    assert time.monotonic() - began < 6, 'one sweep spent more than the whole budget'
    assert len(unswept) >= 2, unswept


def test_the_budget_is_spent_on_sweeping_not_on_the_rows_own_checks():
    """A row's break and check are the proof, not the sweep. Charging them to the sweep's
    budget stopped it before it had run a single sibling."""
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        # slow breaks, fast checks: the sweep itself needs almost no time. Both ship the same
        # file, so under the other's break they are expected `shared` collateral, not BLAST
        ledger(tmp, 'A\tx\ttest -f old.txt\told.txt\tsleep 2; rm -f old.txt\n'
                    'B\ty\ttest -f old.txt\told.txt\tsleep 2; rm -f old.txt\n')
        out = run_cli(tmp, '--verify', '--blast', '3')
        assert 'SWEEP STOPPED' not in out.stdout, out.stdout
        assert out.returncode == 0, out.stdout


def test_sweep_stopped_names_the_rows_it_could_not_finish():
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        ledger(tmp, 'A\tx\ttest -f old.txt\t—\trm -f old.txt\n'
                    'B\ty\tsleep 4; test -f old.txt\t—\t—\n')
        here = os.getcwd()
        os.chdir(tmp)
        try:
            rows = goalrun.load(os.path.join(tmp, goalrun.GOAL_DIR, 'ledger.tsv'))
            import contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                ok = goalrun.verify(rows, '', 60, blast=True, budget=1)
        finally:
            os.chdir(here)
        out = buf.getvalue()
        assert ok is False, out
        assert 'SWEEP STOPPED' in out and 'the sweeps for A are incomplete' in out, out


def test_a_row_already_red_is_not_verified_and_is_kept_out_of_the_sweep():
    """An honest row for unbuilt work is red before anything is planted. Its break proves
    nothing, and letting it into the sweep makes every other row report BLAST."""
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        ledger(tmp, 'GOOD\tx\ttest -f old.txt\t—\trm -f old.txt\n'
                    'UNBUILT\ty\ttest -f src/cli.py\t—\trm -f src/cli.py\n')
        out = run_cli(tmp, '--verify')
        assert 'already red before any break: UNBUILT' in out.stdout, out.stdout
        assert 'ALREADY RED UNBUILT' in out.stdout, out.stdout
        assert 'VERIFIED GOOD' in out.stdout, out.stdout
        assert 'BLAST' not in out.stdout, 'a row red for its own reasons is not collateral'
        assert out.returncode == 1, out.stdout


def test_verify_survives_a_check_that_litters():
    """A check that writes an artifact runs inside the clone, so the litter never reaches the
    real tree — there is no clean-tree gate left for it to trip anyway."""
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        ledger(tmp, 'A\tx\ttouch junk.junk && test -f old.txt\t—\trm -f old.txt\n')
        out = run_cli(tmp, '--verify', '--no-blast')
        assert out.returncode == 0 and 'VERIFIED A' in out.stdout, out.stdout + out.stderr
        assert not os.path.exists(os.path.join(tmp, 'junk.junk')), \
            'the litter landed in the real tree, not just the clone'


def test_verify_works_in_a_directory_with_nothing_tracked_at_all():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'A\tx\ttrue\n')
        out = run_cli(tmp, '--verify')
        assert out.returncode == 1 and 'NOTHING VERIFIED' in out.stdout, out.stdout + out.stderr


def test_requirements_file_rejects_two_ids_before_a_colon():
    """`REQ-A-001 REQ-A-002: shared description` escaped the no-colon guard and silently
    dropped the second id — the exact blind spot the gate exists to close."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'reqs.txt')
        open(path, 'w').write('REQ-A-001 REQ-A-002: shared description\n')
        expect_misuse(goalrun.read_requirements, path)


def test_lint_flags_a_verify_ok_on_a_row_that_has_a_break():
    """A verify-ok on a row that carries a break silently removes it from every sweep —
    the waiver turns off the detector."""
    rows = [goalrun.Row('A', 'x', 'true', '', 'rm -f x')]
    waived = {'verify-ok': {'A': 'why'}, 'no-row-ok': {}}
    assert any('has a break' in p for p in goalrun.lint(rows, waived=waived))


def test_lint_flags_a_verify_ok_on_a_manual_row():
    rows = [goalrun.Row('UX', 'looks ok', 'MANUAL:t', '', ''),
            goalrun.Row('A', 'x', 'true', '', 'rm -f x')]
    waived = {'verify-ok': {'UX': 'no break needed'}, 'no-row-ok': {}}
    assert any('MANUAL row' in p and 'UX' in p for p in goalrun.lint(rows, waived=waived))


def test_requirements_file_rejects_two_ids_on_one_line():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'reqs.txt')
        open(path, 'w').write('REQ-A-001 REQ-A-002\n')
        expect_misuse(goalrun.read_requirements, path)
        open(path, 'w').write('REQ-A-001: one id, then a description\n')
        assert goalrun.read_requirements(path) == ['REQ-A-001']


def test_blast_takes_a_budget_in_seconds():
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        ledger(tmp, 'A\tx\ttest -f old.txt\t—\trm -f old.txt\n'
                    'B\ty\tsleep 4; test -f old.txt\t—\trm -f old.txt\n')
        tight = run_cli(tmp, '--verify', '--blast', '1')
        assert 'SWEEP STOPPED' in tight.stdout and tight.returncode == 1, tight.stdout
        assert run_cli(tmp, '--blast', '30').returncode == 2, 'still needs --verify'


def test_the_sweep_stops_on_its_budget_and_says_so():
    """An O(rows²) sweep on a slow suite can run for hours; silence there would be the same
    lie as a proof that never ran."""
    with tempfile.TemporaryDirectory() as tmp:
        make_tree(tmp)
        rows = [goalrun.Row(f'R{i}', 'x', 'sleep 0.3; test -f old.txt', '',
                            f'rm -f old.txt; : {i}') for i in range(4)]
        here = os.getcwd()
        os.chdir(tmp)
        try:
            ok = goalrun.verify(rows, '', 5, blast=True, budget=0.2)
        finally:
            os.chdir(here)
        assert ok is False, 'a partly-swept proof is not a pass'


def test_an_empty_only_is_misuse_not_a_whole_ledger_done():
    """`--only` may never print `DONE` — that is the whole point of a phase run. An empty
    selection falling through to the whole ledger printed exactly that."""
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'A\tone\ttrue\t—\tfalse\nB\ttwo\ttrue\t—\tfalse\n')
        out = run_cli(tmp, '--only', '')
        assert out.returncode == 2, out.stdout + out.stderr
        assert 'DONE' not in out.stdout, out.stdout
        assert 'no row ids given' in out.stderr, out.stderr


def test_blast_zero_is_a_zero_second_budget_not_an_unlimited_one():
    """`--blast 0` reads as the smallest budget, so it must not mean the largest. The sweep
    is the part that runs for hours; a flag that silently removes its bound is the one
    mistake the budget exists to prevent."""
    with tempfile.TemporaryDirectory() as tmp:
        open(os.path.join(tmp, 'a.txt'), 'w').write('a\n')
        open(os.path.join(tmp, 'b.txt'), 'w').write('b\n')
        ledger(tmp, 'A\tx\tcat a.txt b.txt\ta.txt\trm -f a.txt\n'
                    'B\ty\tcat a.txt b.txt\tb.txt\trm -f b.txt\n')
        zero = run_cli(tmp, '--verify', '--blast', '0')
        assert 'SWEEP STOPPED' in zero.stdout and zero.returncode == 1, zero.stdout
        # ...while bare --blast still means no bound at all, and finds what the sweep is for
        bare = run_cli(tmp, '--verify', '--blast')
        assert 'BLAST' in bare.stdout and 'SWEEP STOPPED' not in bare.stdout, bare.stdout


def test_a_whole_ledger_verify_blasts_by_default():
    """Knowing whether rows tell defects apart requires the sweep, so the proof run does it."""
    with tempfile.TemporaryDirectory() as tmp:
        open(os.path.join(tmp, 'a.txt'), 'w').write('a\n')
        open(os.path.join(tmp, 'b.txt'), 'w').write('b\n')
        ledger(tmp, 'A\tx\tcat a.txt b.txt\ta.txt\trm -f a.txt\n'
                    'B\ty\tcat a.txt b.txt\tb.txt\trm -f b.txt\n')
        whole = run_cli(tmp, '--verify')
        assert 'BLAST' in whole.stdout and whole.returncode == 1, whole.stdout
        subset = run_cli(tmp, '--verify', 'A')
        assert 'BLAST' not in subset.stdout and subset.returncode == 0, subset.stdout
        off = run_cli(tmp, '--verify', '--no-blast')
        assert 'BLAST' not in off.stdout and off.returncode == 0, off.stdout
        assert 'sweep skipped' in off.stdout, 'the docs promise --no-blast names the blind spot'
        assert run_cli(tmp, '--no-blast').returncode == 2
        assert run_cli(tmp, '--blast').returncode == 2


def test_verify_says_the_selection_ran_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'A\tx\ttrue\nB\ty\ttrue\t\trm -f old.txt\n')
        out = run_cli(tmp, '--verify', 'A')
        assert out.returncode == 1 and 'no row in this selection' in out.stdout, out.stdout


def test_waived_shape_survives_a_requirements_call():
    rows = [goalrun.Row('A', 'REQ-1 x', 'true', '', 'rm -f x')]
    with tempfile.TemporaryDirectory() as tmp:
        path = ledger(tmp, '# no-row-ok: REQ-2 — out of scope\nA\tREQ-1 x\ttrue\t\trm -f x\n')
        problems = goalrun.lint(rows, waived=goalrun.waivers(path),
                                requirements=['REQ-1', 'REQ-2'])
        assert problems == [], problems


def test_lint_names_requirements_no_row_measures():
    rows = [goalrun.Row('EXPORT', 'REQ-EXP-001 csv export', 'true', '', 'rm -f x')]
    problems = goalrun.lint(rows, requirements=['REQ-EXP-001', 'REQ-DOC-002'])
    assert any('REQ-DOC-002' in p for p in problems), problems
    assert not any('REQ-EXP-001' in p for p in problems), problems
    waived = {'verify-ok': {}, 'no-row-ok': {'REQ-DOC-002': 'ships elsewhere'}}
    assert goalrun.lint(rows, requirements=['REQ-DOC-002'], waived=waived) == []


def test_lint_does_not_let_req_10_satisfy_req_1():
    rows = [goalrun.Row('A', 'REQ-10 done', 'true', '', 'rm -f x')]
    assert any('REQ-1:' in p for p in goalrun.lint(rows, requirements=['REQ-1']))
    assert goalrun.lint(rows, requirements=['REQ-10']) == []


def test_read_requirements_takes_ids_or_id_plus_description():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'reqs.txt')
        open(path, 'w').write('# comment\nREQ-A-001: amount rejects 0\nREQ-A-002\nREQ-A-001\n')
        assert goalrun.read_requirements(path) == ['REQ-A-001', 'REQ-A-002']


def test_cli_requirements_only_reads_with_lint():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'A\tx\ttrue\t\trm -f x\n')
        open(os.path.join(tmp, 'reqs.txt'), 'w').write('REQ-1\n')
        assert run_cli(tmp, '--requirements', 'reqs.txt').returncode == 2
        missing = run_cli(tmp, '--lint-ledger', '--requirements', 'nope.txt')
        assert missing.returncode == 2 and 'no requirements file' in missing.stderr
        out = run_cli(tmp, '--lint-ledger', '--requirements', 'reqs.txt')
        assert out.returncode == 1 and 'REQ-1' in out.stdout, out.stdout


def test_verify_that_ran_no_break_is_not_a_pass():
    """Exit 0 from a --verify that skipped every row is the fake green this flag exists to kill."""
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'A\tsuite passes\ttrue\n')
        out = run_cli(tmp, '--verify')
        assert out.returncode == 1, out.stdout
        assert 'NOTHING VERIFIED' in out.stdout, out.stdout


def test_lint_flags_stale_signatures():
    rows = [goalrun.Row('A', 'x', 'npm test', '', '')]
    sigs = {'GONE': {'who': 'x', 'date': 'd', 'what_hash': 'h', 'note': ''}}
    assert any('GONE' in p for p in goalrun.lint(rows, sigs))


def test_cli_lint_ledger_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        ledger(tmp, 'A\tunowned\tMANUAL:\nD\tship\ttrue\tsrc/x\n')
        bad = run_cli(tmp, '--lint-ledger')
        assert bad.returncode == 1 and 'no owner' in bad.stdout and 'baseline' in bad.stdout, bad.stdout
        run_cli(tmp, '--baseline')
        ledger(tmp, 'A\tsuite\tnpm test\t—\trm -rf src\n'
                    'B\tlint\tnpm run lint\t—\tprintf "x" >> src/a.js\n'
                    'UX\tok\tMANUAL:t\t—\n')
        good = run_cli(tmp, '--lint-ledger')
        assert good.returncode == 0, good.stdout
        ledger(tmp, '# nothing\n')
        assert run_cli(tmp, '--lint-ledger').returncode == 1


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
                if isinstance(e, KeyboardInterrupt):
                    raise
                failures += 1
                print(f'FAIL {name}: {e}')
                for line in noise.splitlines():
                    print(f'    {line}')
    print()
    print(f'{failures} failure(s)' if failures else 'all green')
    sys.exit(1 if failures else 0)
