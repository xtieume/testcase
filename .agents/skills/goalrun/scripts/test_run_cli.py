"""Public CLI regressions for isolation, cross-agent continuation and recovery."""
import base64
import hashlib
import json
import signal
import time
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('goalrun.py')


class RunCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'feature.txt').write_text('old\n')

    def cli(self, *args, code=0):
        out = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.root,
                             text=True, capture_output=True, timeout=15)
        self.assertEqual(out.returncode, code, out.stdout + out.stderr)
        return out

    def init(self, run_id='export'):
        self.cli('init', run_id, '--goal', 'Export CSV')
        data = json.loads(self.cli('resume', run_id, '--owner', 'agent-A').stdout)
        return data['token']

    def folder(self, run_id='export'):
        return self.root / '.testcases/runs' / run_id

    def ledger(self, run_id='export', command='true', brk=''):
        (self.folder(run_id) / 'goalrun/ledger.tsv').write_text(
            f'REQ-A\tExports CSV\t{command}\t-\t{brk}\n')
        (self.folder(run_id) / 'goalrun/reqs.txt').write_text('REQ-A\n')

    def inspect(self, run_id='export'):
        return json.loads(self.cli('inspect', run_id).stdout)

    def test_two_goals_have_distinct_baselines_and_signatures(self):
        a = self.init('export')
        (self.root / 'feature.txt').write_text('partially implemented\n')
        b = self.init('login')
        self.ledger('export')
        self.ledger('login')
        before = (self.folder() / 'goalrun/baseline.json').read_bytes()
        self.cli('--run', 'export', '--token', a, '--only', 'REQ-A')
        self.cli('--run', 'login', '--token', b, '--only', 'REQ-A')
        self.assertEqual((self.folder() / 'goalrun/baseline.json').read_bytes(), before)
        self.assertNotEqual(before, (self.folder('login') / 'goalrun/baseline.json').read_bytes())
        self.assertFalse((self.root / '.testcases/goalrun').exists())

    def test_new_process_continues_checkpoint_after_release_and_rejects_old_token(self):
        a = self.init()
        self.ledger(command='false')
        self.cli('--run', 'export', '--token', a, '--only', 'REQ-A', code=1)
        self.cli('checkpoint', 'export', '--token', a, '--phase', 'build-2',
                 '--next', 'Implement quoted CSV cells', '--note', 'Spec amended in docs/export.md')
        self.cli('release', 'export', '--token', a, '--note', 'Continue build-2')
        b = json.loads(self.cli('resume', 'export', '--owner', 'agent-B').stdout)['token']
        info = self.inspect()
        self.assertEqual(info['checkpoint']['phase'], 'build-2')
        self.assertEqual(info['checkpoint']['failures']['REQ-A'], 1)
        self.assertEqual(info['checkpoint']['next_action'], 'Implement quoted CSV cells')
        self.assertIn('Continue build-2', info['handoff'])
        self.cli('--run', 'export', '--token', a, '--only', 'REQ-A', code=2)
        self.ledger()
        self.cli('--run', 'export', '--token', b, '--only', 'REQ-A')

    def test_takeover_is_explicit_and_generation_checked(self):
        self.init()
        info = self.inspect()
        generation = str(info['checkpoint']['generation'])
        self.cli('resume', 'export', '--owner', 'agent-B', code=2)
        self.cli('resume', 'export', '--owner', 'agent-B', '--expected-generation', '99', code=2)
        self.cli('resume', 'export', '--owner', 'agent-B', '--expected-generation', generation)
        self.cli('resume', 'export', '--owner', 'agent-C', '--expected-generation', generation, code=2)

    def test_read_only_inspection_does_not_disclose_writer_token(self):
        token = self.init()
        self.assertNotIn(token, self.cli('inspect', 'export').stdout)
        self.assertNotIn(token, self.cli('list').stdout)

    def test_evidence_becomes_stale_after_source_change(self):
        token = self.init()
        self.ledger()
        self.cli('--run', 'export', '--token', token, '--only', 'REQ-A')
        info = self.inspect()
        self.assertFalse(info['evidence_stale'])
        self.assertEqual(info['last_evidence']['exit_code'], 0)
        self.assertFalse(info['last_evidence']['whole_ledger_verified'])
        log = Path(info['last_evidence']['log'])
        self.assertIn('PHASE OK', log.read_text())
        (self.root / 'feature.txt').write_text('different source\n')
        self.assertTrue(self.inspect()['evidence_stale'])

    def test_external_symlinked_spec_content_change_stales_whole_proof(self):
        with tempfile.TemporaryDirectory() as outside:
            spec = Path(outside) / 'spec.md'
            spec.write_text('Original requirement\n')
            (self.root / 'spec.md').symlink_to(spec)
            self.cli('init', 'export', '--goal', 'Export CSV', '--spec', 'spec.md')
            token = json.loads(self.cli('resume', 'export', '--owner', 'A').stdout)['token']
            self.ledger(command="python3 -c \"assert open('feature.txt').read() == 'old\\n'\"",
                        brk='feature.txt :: old :: broken')
            self.cli('--run', 'export', '--token', token, '--verify')
            self.assertTrue(self.inspect()['last_evidence']['whole_ledger_verified'])
            self.assertFalse(self.inspect()['evidence_stale'])
            spec.write_text('Amended requirement\n')
            self.assertTrue(self.inspect()['evidence_stale'])

    def test_evidence_changes_on_requirements_and_ledger_amendment(self):
        token = self.init()
        self.ledger()
        self.cli('--run', 'export', '--token', token, '--only', 'REQ-A')
        (self.folder() / 'goalrun/reqs.txt').write_text('REQ-A\nREQ-B\n')
        self.assertTrue(self.inspect()['evidence_stale'])

    def test_named_workspace_refuses_implicit_legacy_and_reset(self):
        token = self.init()
        self.ledger()
        self.cli(code=2)
        self.cli('--run', 'export', '--only', 'REQ-A', code=2)
        baseline = (self.folder() / 'goalrun/baseline.json').read_bytes()
        self.cli('--run', 'export', '--token', token, '--baseline', '--reset', code=2)
        self.assertEqual((self.folder() / 'goalrun/baseline.json').read_bytes(), baseline)
        self.cli('--run', 'export', '--token', token, '--ledger', '/tmp/other-ledger', code=2)

    def test_schema_mismatch_refuses_mutation(self):
        token = self.init()
        path = self.folder() / 'manifest.json'
        data = json.loads(path.read_text())
        data['version'] = 999
        path.write_text(json.dumps(data))
        before = (self.folder() / 'checkpoint.json').read_bytes()
        self.cli('checkpoint', 'export', '--token', token, '--phase', 'build', '--next', 'x', code=2)
        self.assertEqual((self.folder() / 'checkpoint.json').read_bytes(), before)

    def test_migration_preserves_old_baseline_and_does_not_autoselect(self):
        old = self.root / '.testcases/goalrun'
        old.mkdir(parents=True)
        self.cli('--baseline')
        (old / 'ledger.tsv').write_text('REQ-A\tExports CSV\ttrue\n')
        (old / 'reqs.txt').write_text('REQ-A\n')
        (self.root / 'testcases.md').write_text('Existing TC-1\n')
        baseline = (old / 'baseline.json').read_bytes()
        self.cli('migrate', 'export', '--goal', 'Export CSV')
        self.assertEqual((self.folder() / 'goalrun/baseline.json').read_bytes(), baseline)
        self.assertEqual((self.root / 'docs/testcases/export/testcases.md').read_text(), 'Existing TC-1\n')
        self.assertTrue((old / 'ledger.tsv').exists())
        self.cli(code=2)

    def injected_cli(self, patch, *args, code=2):
        bootstrap = (f"import sys; sys.path.insert(0, {str(SCRIPT.parent)!r}); "
                     "import goalrun, run_cli; "
                     f"sys.argv = {[str(SCRIPT), *args]!r}\n" + patch +
                     "\nraise SystemExit(goalrun.main())\n")
        out = subprocess.run([sys.executable, '-c', bootstrap], cwd=self.root,
                             text=True, capture_output=True, timeout=15)
        self.assertEqual(out.returncode, code, out.stdout + out.stderr)
        return out

    def test_failed_init_can_retry_without_disabling_legacy(self):
        self.injected_cli("def fail(**kwargs):\n    raise OSError('baseline failed')\n"
                          "goalrun.take_baseline = fail", 'init', 'export', '--goal', 'Export CSV')
        self.assertFalse(self.folder().exists())
        self.assertEqual(json.loads(self.cli('list').stdout), [])
        self.cli('--baseline')
        self.init()

    def test_failed_migration_can_retry_and_preserves_legacy(self):
        self.cli('--baseline')
        old = self.root / '.testcases/goalrun/baseline.json'
        original = old.read_bytes()
        self.injected_cli("real_copy = run_cli.shutil.copy2\n"
                          "def fail(*args, **kwargs):\n    real_copy(*args, **kwargs)\n"
                          "    raise OSError('copy failed')\nrun_cli.shutil.copy2 = fail",
                          'migrate', 'export', '--goal', 'Export CSV')
        self.assertFalse(self.folder().exists())
        self.assertEqual(json.loads(self.cli('list').stdout), [])
        self.assertEqual(old.read_bytes(), original)
        self.cli('migrate', 'export', '--goal', 'Export CSV')

    def test_killed_init_does_not_publish_an_incomplete_run(self):
        bootstrap = (f"import sys; sys.path.insert(0, {str(SCRIPT.parent)!r}); "
                     "import goalrun; from pathlib import Path; import time\n"
                     "def pause(**kwargs):\n    Path('.testcases/initializing').touch()\n"
                     "    time.sleep(30)\ngoalrun.take_baseline = pause\n"
                     f"sys.argv = {[str(SCRIPT), 'init', 'export', '--goal', 'Export CSV']!r}\n"
                     "raise SystemExit(goalrun.main())\n")
        proc = subprocess.Popen([sys.executable, '-c', bootstrap], cwd=self.root,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 5
            while not (self.root / '.testcases/initializing').exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue((self.root / '.testcases/initializing').exists())
            self.assertEqual(json.loads(self.cli('list').stdout), [])
        finally:
            proc.kill()
            proc.wait(timeout=5)
        self.assertFalse(self.folder().exists())
        self.init()

    def test_migration_refuses_existing_tracked_testcase_table(self):
        self.cli('--baseline')
        (self.root / 'testcases.md').write_text('Legacy TC-1\n')
        destination = self.root / 'docs/testcases/export/testcases.md'
        destination.parent.mkdir(parents=True)
        destination.write_text('Tracked TC-99\n')
        self.cli('migrate', 'export', '--goal', 'Export CSV', code=2)
        self.assertEqual(destination.read_text(), 'Tracked TC-99\n')
        self.assertEqual((self.root / 'testcases.md').read_text(), 'Legacy TC-1\n')
        self.assertFalse(self.folder().exists())
        destination.unlink()
        self.cli('migrate', 'export', '--goal', 'Export CSV')
        self.assertEqual(destination.read_text(), 'Legacy TC-1\n')

    def test_migration_late_table_collision_is_not_overwritten(self):
        self.cli('--baseline')
        (self.root / 'testcases.md').write_text('Legacy TC-1\n')
        self.injected_cli("real_link = run_cli.os.link\n"
                          "def collide(source, destination):\n"
                          "    run_cli.Path(destination).write_text('Tracked TC-99\\n')\n"
                          "    real_link(source, destination)\nrun_cli.os.link = collide",
                          'migrate', 'export', '--goal', 'Export CSV')
        self.assertFalse(self.folder().exists())
        self.assertEqual((self.root / 'docs/testcases/export/testcases.md').read_text(),
                         'Tracked TC-99\n')

    def test_failed_publication_removes_only_its_migrated_table(self):
        self.cli('--baseline')
        (self.root / 'testcases.md').write_text('Legacy TC-1\n')
        self.injected_cli("def fail(*args):\n    raise OSError('publish failed')\n"
                          "run_cli.os.rename = fail", 'migrate', 'export', '--goal', 'Export CSV')
        self.assertFalse(self.folder().exists())
        self.assertFalse((self.root / 'docs/testcases/export/testcases.md').exists())
        self.assertEqual((self.root / 'testcases.md').read_text(), 'Legacy TC-1\n')
        self.cli('migrate', 'export', '--goal', 'Export CSV')

    def test_partial_verify_is_not_whole_ledger_proof(self):
        token = self.init()
        self.ledger(command="python3 -c \"assert open('feature.txt').read() == 'old\\n'\"",
                    brk='feature.txt :: old :: broken')
        with (self.folder() / 'goalrun/ledger.tsv').open('a') as f:
            f.write('REQ-B\tOther\ttrue\t-\t-\n')
        self.cli('--run', 'export', '--token', token, '--verify', 'REQ-A')
        self.assertFalse(self.inspect()['last_evidence']['whole_ledger_verified'])
        self.assertNotIn('DONE', self.cli('--run', 'export', '--token', token, '--verify', 'REQ-A').stdout)
        self.assertEqual((self.root / 'feature.txt').read_text(), 'old\n')

    def pending_undo(self, run_id='export', current=b'broken\n'):
        directory = self.folder(run_id) / 'goalrun/undo'
        directory.mkdir(exist_ok=True)
        (directory / 'fixture.json').write_text(json.dumps({
            'version': 1, 'run_id': run_id, 'row_id': 'REQ-A', 'path': 'feature.txt',
            'original': base64.b64encode(b'old\n').decode(),
            'planted_hash': hashlib.sha256(b'broken\n').hexdigest()}))
        (self.root / 'feature.txt').write_bytes(current)

    def test_other_run_recovers_pending_verify_before_ordinary_checks(self):
        self.init('export')
        token = self.init('login')
        self.ledger('login', command="python3 -c \"assert open('feature.txt').read() == 'old\\n'\"")
        self.pending_undo()
        self.cli('--run', 'login', '--token', token, '--only', 'REQ-A')
        self.assertEqual((self.root / 'feature.txt').read_bytes(), b'old\n')
        self.assertFalse(list((self.folder() / 'goalrun/undo').iterdir()))

    def test_recovery_refuses_to_overwrite_intervening_edits(self):
        token = self.init()
        self.ledger()
        self.pending_undo(current=b'user edit\n')
        self.cli('--run', 'export', '--token', token, '--only', 'REQ-A', code=2)
        self.assertEqual((self.root / 'feature.txt').read_bytes(), b'user edit\n')
        self.assertTrue(list((self.folder() / 'goalrun/undo').iterdir()))

    def test_signoff_cannot_cross_run_boundary(self):
        a, b = self.init('export'), self.init('login')
        for run in ('export', 'login'):
            self.ledger(run, command='MANUAL:alice')
        self.cli('--run', 'export', '--token', a, '--sign', 'REQ-A', '--who', 'alice', '--note', 'Accepted')
        self.cli('--run', 'export', '--token', a)
        out = self.cli('--run', 'login', '--token', b, code=1)
        self.assertIn('WAIT', out.stdout)

    def test_whole_verify_records_current_proof_and_command_exit_codes(self):
        token = self.init()
        self.ledger(command="python3 -c \"assert open('feature.txt').read() == 'old\\n'\"",
                    brk='feature.txt :: old :: broken')
        self.cli('--run', 'export', '--token', token, '--verify')
        view = self.inspect()
        self.assertTrue(view['last_evidence']['whole_ledger_verified'])
        self.assertFalse(view['evidence_stale'])
        evidence = list((self.folder() / 'evidence').glob('*-check-*.json'))
        self.assertEqual(sorted(json.loads(p.read_text())['exit_code'] for p in evidence), [0, 1])

    def test_killed_verify_is_recovered_after_its_check_stops(self):
        token = self.init()
        command = "python3 -c \"import os,time; from pathlib import Path; broken=Path('feature.txt').read_text()!='old\\n'; Path('pid').write_text(str(os.getpid())); Path('marker').write_text('planted') if broken else None; time.sleep(30) if broken else None; assert not broken\""
        self.ledger(command=command, brk='feature.txt :: old :: broken')
        proc = subprocess.Popen([sys.executable, str(SCRIPT), '--run', 'export', '--token', token,
                                 '--verify'], cwd=self.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        child_pid = None
        try:
            deadline = time.monotonic() + 10
            while not (self.root / 'marker').exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue((self.root / 'marker').exists(), 'verify never planted its defect')
            child_pid = int((self.root / 'pid').read_text())
            proc.kill()
            proc.wait(timeout=5)
            # Orphan checks still hold the workspace lock; takeover may not race them.
            self.cli('resume', 'export', '--owner', 'agent-B', '--expected-generation', '1', code=2)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
            if child_pid is not None:
                try:
                    os.killpg(os.getpgid(child_pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
        # Wait until the shell has reaped the killed check and closed its lock descriptor.
        for _ in range(100):
            out = subprocess.run([sys.executable, str(SCRIPT), 'resume', 'export', '--owner', 'agent-B',
                                  '--expected-generation', '1'], cwd=self.root, capture_output=True, text=True)
            if out.returncode == 0:
                break
            time.sleep(0.02)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual((self.root / 'feature.txt').read_bytes(), b'old\n')

    def test_checks_in_different_runs_share_workspace_lock(self):
        a, b = self.init('export'), self.init('login')
        self.ledger('export', command="python3 -c \"import time; from pathlib import Path; Path('running').touch(); time.sleep(1)\"")
        self.ledger('login')
        proc = subprocess.Popen([sys.executable, str(SCRIPT), '--run', 'export', '--token', a,
                                 '--only', 'REQ-A'], cwd=self.root,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 5
            while not (self.root / 'running').exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue((self.root / 'running').exists())
            self.cli('--run', 'login', '--token', b, '--only', 'REQ-A', code=2)
            self.assertEqual(proc.wait(timeout=5), 0)
            self.cli('--run', 'login', '--token', b, '--only', 'REQ-A')
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)

    def test_missing_baseline_blocks_resume(self):
        self.init()
        (self.folder() / 'goalrun/baseline.json').unlink()
        self.cli('resume', 'export', '--owner', 'B', '--expected-generation', '1', code=2)

    def test_local_spec_change_outside_workspace_invalidates_evidence(self):
        with tempfile.TemporaryDirectory() as other:
            spec = Path(other) / 'export.md'
            spec.write_text('CSV required')
            self.cli('init', 'export', '--goal', 'Export', '--spec', str(spec))
            token = json.loads(self.cli('resume', 'export', '--owner', 'A').stdout)['token']
            self.ledger()
            self.cli('--run', 'export', '--token', token, '--only', 'REQ-A')
            self.assertFalse(self.inspect()['evidence_stale'])
            spec.write_text('TSV required')
            self.assertTrue(self.inspect()['evidence_stale'])

    def test_source_changes_during_verify_prevent_completion(self):
        token = self.init()
        self.ledger(command="python3 -c \"from pathlib import Path; Path('new-source.txt').write_text('changed'); assert Path('feature.txt').read_text() == 'old\\n'\"",
                    brk='feature.txt :: old :: broken')
        out = self.cli('--run', 'export', '--token', token, '--verify', code=1)
        self.assertIn('inputs changed', out.stdout)
        self.assertFalse(self.inspect()['last_evidence']['whole_ledger_verified'])
        self.assertEqual(self.inspect()['last_evidence']['exit_code'], 1)

    def test_named_measurement_does_not_claim_verified_completion(self):
        token = self.init()
        self.ledger()
        out = self.cli('--run', 'export', '--token', token)
        self.assertNotIn('DONE', out.stdout)
        self.assertFalse(self.inspect()['last_evidence']['whole_ledger_verified'])

    def test_hollow_verification_is_persisted_as_failure_for_next_agent(self):
        token = self.init()
        self.ledger(command='true', brk='feature.txt :: old :: broken')
        self.cli('--run', 'export', '--token', token, '--verify', code=1)
        view = self.inspect()
        self.assertEqual(view['checkpoint']['failures']['REQ-A'], 1)
        self.assertEqual(view['last_evidence']['rows']['REQ-A']['status'], 'HOLLOW')

    def test_whole_verify_cannot_prove_a_missing_requirement(self):
        token = self.init()
        self.ledger(command="python3 -c \"assert open('feature.txt').read() == 'old\\n'\"",
                    brk='feature.txt :: old :: broken')
        (self.folder() / 'goalrun/reqs.txt').write_text('REQ-A\nREQ-B\n')
        self.cli('--run', 'export', '--token', token, '--verify', code=1)
        self.assertFalse(self.inspect()['last_evidence']['whole_ledger_verified'])

    def test_workspace_lock_symlink_cannot_truncate_source(self):
        directory = self.root / '.testcases'
        directory.mkdir()
        (directory / 'goalrun.lock').symlink_to(self.root / 'feature.txt')
        self.cli('init', 'export', '--goal', 'Export', code=2)
        self.assertEqual((self.root / 'feature.txt').read_bytes(), b'old\n')

    def test_timeout_evidence_retains_actual_exit_code_and_output(self):
        token = self.init()
        self.ledger(command="python3 -c \"import time; print('started', flush=True); time.sleep(8)\"")
        self.cli('--run', 'export', '--token', token, '--only', 'REQ-A', '--timeout', '1', code=1)
        paths = list((self.folder() / 'evidence').glob('*-check-*.json'))
        record = json.loads(paths[0].read_text())
        self.assertTrue(record['timed_out'])
        self.assertEqual(record['exit_code'], -signal.SIGKILL)
        self.assertIn('started', record['output'])

    def test_sigterm_preserves_interrupted_check_evidence(self):
        token = self.init()
        self.ledger(command="python3 -c \"import time; from pathlib import Path; print('started',flush=True); Path('running').touch(); time.sleep(30)\"")
        proc = subprocess.Popen([sys.executable, str(SCRIPT), '--run', 'export', '--token', token,
                                 '--only', 'REQ-A'], cwd=self.root,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 5
            while not (self.root / 'running').exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue((self.root / 'running').exists())
            proc.terminate()
            self.assertEqual(proc.wait(timeout=5), 130)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
        view = self.inspect()
        self.assertEqual(view['last_evidence']['exit_code'], 130)
        record = json.loads(next((self.folder() / 'evidence').glob('*-check-*.json')).read_text())
        self.assertEqual(record['exit_code'], -signal.SIGKILL)
        self.assertIn('started', record['output'])

    def test_authorized_manual_only_goal_can_complete(self):
        token = self.init()
        self.ledger(command='MANUAL:alice')
        self.cli('--run', 'export', '--token', token, '--sign', 'REQ-A', '--who', 'alice', '--note', 'Accepted')
        self.cli('--run', 'export', '--token', token, '--verify')
        self.assertTrue(self.inspect()['last_evidence']['whole_ledger_verified'])
        self.assertFalse(self.inspect()['evidence_stale'])

    def test_waived_test_first_goal_can_complete_but_unwaived_goal_cannot(self):
        token = self.init()
        self.ledger()
        self.cli('--run', 'export', '--token', token, '--verify', code=1)
        with (self.folder() / 'goalrun/ledger.tsv').open('a') as f:
            f.write('# verify-ok: REQ-A — test-first, seen red on 2026-10-03\n')
        self.cli('--run', 'export', '--token', token, '--verify')
        self.assertTrue(self.inspect()['last_evidence']['whole_ledger_verified'])

    def test_new_owner_must_obtain_fresh_proof_even_when_source_is_unchanged(self):
        token = self.init()
        self.ledger(command="python3 -c \"assert open('feature.txt').read() == 'old\\n'\"",
                    brk='feature.txt :: old :: broken')
        self.cli('--run', 'export', '--token', token, '--verify')
        self.assertFalse(self.inspect()['evidence_stale'])
        self.cli('release', 'export', '--token', token, '--note', 'Review completion')
        b = json.loads(self.cli('resume', 'export', '--owner', 'B').stdout)['token']
        self.assertTrue(self.inspect()['evidence_stale'])
        self.cli('--run', 'export', '--token', b, '--verify')
        self.assertFalse(self.inspect()['evidence_stale'])

    def test_session_logs_and_exports_do_not_invalidate_current_proof(self):
        token = self.init()
        self.ledger(command="python3 -c \"assert open('feature.txt').read() == 'old\\n'\"",
                    brk='feature.txt :: old :: broken')
        self.cli('--run', 'export', '--token', token, '--verify')
        (self.folder() / 'testcase/session.log').write_text('session wrote its completion log')
        (self.folder() / 'testcase/out.csv').write_text('TC-001,REQ-A')
        self.assertFalse(self.inspect()['evidence_stale'])
        (self.folder() / 'goalrun/reqs.txt').write_text('REQ-A\nREQ-B\n')
        self.assertTrue(self.inspect()['evidence_stale'])


if __name__ == '__main__':
    unittest.main()
