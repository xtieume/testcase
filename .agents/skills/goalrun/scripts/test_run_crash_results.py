"""Witnessed outcomes survive SIGKILL before the rest of a named run finishes."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = Path(__file__).with_name('goalrun.py')


class CrashResultTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'feature.txt').write_text('old\n')
        (self.root / 'check.py').write_text('''import os
from pathlib import Path
import sys
import time
broken = Path('feature.txt').read_text() != 'old\\n'
if sys.argv[1] != 'A' or not Path('.testcases/hollow').exists():
    assert not broken, 'planted defect detected'
if sys.argv[1] == 'A' and Path('.testcases/trigger').exists():
    raise AssertionError('observed regression')
if sys.argv[1] == 'B' and (Path('.testcases/trigger').exists() or Path('.testcases/block-only').exists()):
    Path('.testcases/blocked').write_text(str(os.getpgrp()))
    time.sleep(30)
''')
        self.cli('init', 'demo', '--goal', 'Two requirements')
        self.token = json.loads(self.cli('resume', 'demo', '--owner', 'A').stdout)['token']
        self.run = self.root / '.testcases/runs/demo'
        (self.run / 'goalrun/ledger.tsv').write_text(
            'REQ-A\tRequirement A\tpython3 check.py A\t-\tfeature.txt :: old :: broken\n'
            'REQ-B\tRequirement B\tpython3 check.py B\t-\tfeature.txt :: old :: broken\n')
        (self.run / 'goalrun/reqs.txt').write_text('REQ-A\nREQ-B\n')
        self.cli('--run', 'demo', '--token', self.token, '--verify')
        self.assertFalse(self.inspect()['proof_stale'])

    def cli(self, *arguments, code=0):
        result = subprocess.run([sys.executable, str(SCRIPT), *arguments], cwd=self.root,
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def inspect(self):
        return json.loads(self.cli('inspect', 'demo').stdout)

    def spawn(self, *arguments, patch=None):
        command = [sys.executable, str(SCRIPT), *arguments]
        if patch:
            bootstrap = (f'import sys; sys.path.insert(0, {str(SCRIPT.parent)!r})\n'
                         'import goalrun, run_cli\nfrom pathlib import Path\nimport time\n' + patch +
                         f'\nsys.argv = {[str(SCRIPT), *arguments]!r}\n'
                         'raise SystemExit(goalrun.main())\n')
            command = [sys.executable, '-c', bootstrap]
        process = subprocess.Popen(command, cwd=self.root, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
        self.addCleanup(self.stop, process)
        return process

    def stop(self, process):
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        blocked = self.root / '.testcases/blocked'
        if blocked.exists():
            try:
                os.killpg(int(blocked.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass
            blocked.unlink()

    def wait_for(self, name, process):
        marker = self.root / '.testcases' / name
        deadline = time.monotonic() + 8
        while not marker.exists() and time.monotonic() < deadline and process.poll() is None:
            time.sleep(0.02)
        self.assertTrue(marker.exists(), f'{name} not reached; process exit {process.poll()}')

    def test_failed_measurement_survives_sigkill_inspection_and_takeover(self):
        proof = self.inspect()['last_proof']['id']
        (self.root / '.testcases/trigger').touch()
        process = self.spawn('--run', 'demo', '--token', self.token)
        self.wait_for('blocked', process)
        live = self.inspect()
        self.assertTrue(live['proof_stale'])
        self.assertEqual(live['last_evidence']['state'], 'unfinished')
        self.assertIsNone(live['last_evidence']['exit_code'])
        self.assertFalse(live['last_evidence']['whole_ledger_verified'])
        self.stop(process)
        self.assertEqual(process.returncode, -signal.SIGKILL)
        files_before = {p: p.read_bytes() for p in self.run.rglob('*') if p.is_file()}
        info = self.inspect()
        self.assertTrue(info['proof_stale'], 'a witnessed production failure must stale the old proof')
        self.assertEqual(info['checkpoint']['failures'], {'REQ-A': 1})
        self.assertEqual(info['last_evidence']['rows']['REQ-A']['status'], 'FAIL')
        self.assertEqual(info['last_proof']['id'], proof)
        for _ in range(2):
            self.assertEqual(self.inspect()['checkpoint']['failures'], {'REQ-A': 1})
        self.assertEqual({p: p.read_bytes() for p in self.run.rglob('*') if p.is_file()}, files_before)
        failed = [json.loads(p.read_text()) for p in (self.run / 'evidence').glob('*-check-*.json')
                  if 'observed regression' in p.read_text()]
        self.assertEqual(len(failed), 1)
        self.assertEqual((failed[0]['row_id'], failed[0]['phase']), ('REQ-A', 'measurement'))
        next_owner = json.loads(self.cli('resume', 'demo', '--owner', 'B', '--expected-generation',
                                        str(info['checkpoint']['generation'])).stdout)
        self.assertEqual(next_owner['checkpoint']['failures'], {'REQ-A': 1})
        self.cli('--run', 'demo', '--token', self.token, code=2)
        (self.root / '.testcases/trigger').unlink()
        self.cli('--run', 'demo', '--token', next_owner['token'])
        self.assertEqual(self.inspect()['checkpoint']['failures'], {'REQ-A': 1})
        self.assertTrue(self.inspect()['proof_stale'])
        self.cli('--run', 'demo', '--token', next_owner['token'], '--verify')
        self.assertFalse(self.inspect()['proof_stale'])
        self.assertEqual(self.inspect()['checkpoint']['failures'], {'REQ-A': 1})

    def test_successful_check_before_block_preserves_existing_whole_proof(self):
        proof = self.inspect()['last_proof']['id']
        (self.root / '.testcases/block-only').touch()
        process = self.spawn('--run', 'demo', '--token', self.token)
        self.wait_for('blocked', process)
        self.stop(process)
        info = self.inspect()
        self.assertFalse(info['proof_stale'])
        self.assertEqual(info['last_proof']['id'], proof)
        self.assertEqual(info['last_evidence']['state'], 'unfinished')
        self.assertEqual(info['last_evidence']['rows']['REQ-A']['status'], 'PASS')
        self.assertEqual(info['checkpoint']['failures'], {})
        (self.root / '.testcases/block-only').unlink()
        self.cli('--run', 'demo', '--token', self.token)
        info = self.inspect()
        self.assertFalse(info['proof_stale'])
        self.assertEqual(info['last_evidence']['state'], 'completed')

    def test_blast_check_failure_counts_planted_row_once_and_not_the_sibling(self):
        # The planted row records HOLLOW and then BLAST in the same session.
        (self.root / '.testcases/hollow').touch()
        for expected in (1, 2):
            result = self.cli('--run', 'demo', '--token', self.token, '--verify', 'REQ-A', '--blast', code=1)
            self.assertIn('HOLLOW REQ-A', result.stdout)
            self.assertIn('BLAST REQ-A', result.stdout)
            info = self.inspect()
            self.assertEqual(info['checkpoint']['failures'], {'REQ-A': expected})
            self.assertEqual(info['last_evidence']['rows']['REQ-A']['status'], 'BLAST')
            self.assertEqual(info['last_evidence']['rows']['REQ-B']['status'], 'PASS')
            self.assertTrue(info['proof_stale'])
            self.cli('checkpoint', 'demo', '--token', self.token, '--phase', 'repair', '--next', 'Fix blast')
            self.assertEqual(self.inspect()['checkpoint']['failures'], {'REQ-A': expected})
        checks = [json.loads(p.read_text()) for p in (self.run / 'evidence').glob('*-check-*.json')]
        self.assertTrue(any(c['phase'] == 'blast' and c['row_id'] == 'REQ-B' and
                            c['mutation_row_id'] == 'REQ-A' and c['exit_code'] != 0 for c in checks))

    def test_raw_failed_check_stales_proof_before_row_is_finalized(self):
        (self.root / '.testcases/trigger').touch()
        patch = '''real = run_cli.Session.record_row
def pause(self, row, status, note):
    if status == 'FAIL':
        Path('.testcases/before-row').touch()
        time.sleep(30)
    return real(self, row, status, note)
run_cli.Session.record_row = pause
'''
        process = self.spawn('--run', 'demo', '--token', self.token, '--only', 'REQ-A', patch=patch)
        self.wait_for('before-row', process)
        self.stop(process)
        info = self.inspect()
        self.assertTrue(info['proof_stale'])
        self.assertEqual(info['checkpoint']['failures'], {'REQ-A': 1})
        self.assertEqual(info['last_evidence']['rows']['REQ-A']['status'], 'FAIL')
        self.cli('checkpoint', 'demo', '--token', self.token, '--phase', 'repair', '--next', 'Fix A')
        self.assertEqual(self.inspect()['checkpoint']['failures'], {'REQ-A': 1})

    def test_expected_mutation_failure_survives_sigkill_without_regression_count(self):
        patch = '''real = run_cli.Session.record_check
def pause(self, *args, **kwargs):
    result = real(self, *args, **kwargs)
    if Path('feature.txt').read_text() != 'old\\n':
        Path('.testcases/mutation-red').touch()
        time.sleep(30)
    return result
run_cli.Session.record_check = pause
'''
        process = self.spawn('--run', 'demo', '--token', self.token, '--verify', patch=patch)
        self.wait_for('mutation-red', process)
        self.stop(process)
        info = self.inspect()
        self.assertEqual(info['checkpoint']['failures'], {})
        checks = [json.loads(p.read_text()) for p in (self.run / 'evidence').glob('*-check-*.json')]
        self.assertTrue(any(c.get('phase') == 'mutation' and c['exit_code'] != 0 for c in checks))
        self.cli('checkpoint', 'demo', '--token', self.token, '--phase', 'verify', '--next', 'Retry proof')
        self.assertEqual((self.root / 'feature.txt').read_text(), 'old\n')
        self.assertEqual(self.inspect()['checkpoint']['failures'], {})
        self.assertFalse(self.inspect()['proof_stale'])
        self.cli('--run', 'demo', '--token', self.token, '--verify')
        self.assertEqual(self.inspect()['checkpoint']['failures'], {})

    def test_finish_and_repeated_restart_count_each_failed_row_once(self):
        (self.root / '.testcases/trigger').touch()
        for expected in (1, 2, 3):
            self.cli('--run', 'demo', '--token', self.token, '--only', 'REQ-A', code=1)
            self.assertEqual(self.inspect()['checkpoint']['failures'], {'REQ-A': expected})
            self.cli('checkpoint', 'demo', '--token', self.token, '--phase', 'repair', '--next', 'Fix A')
            self.assertEqual(self.inspect()['checkpoint']['failures'], {'REQ-A': expected})

    def test_zero_test_and_silent_runner_failures_survive_kill_before_finalized_row(self):
        (self.root / 'pytest').write_text('''from pathlib import Path
import sys
assert Path('feature.txt').read_text() == 'old\\n'
marker = Path('.testcases/no-tests')
sys.stdout.write(marker.read_text() if marker.exists() else '1 passed\\n')
''')
        ledger = self.run / 'goalrun/ledger.tsv'
        ledger.write_text(ledger.read_text().replace('python3 check.py', 'python3 pytest'))
        patch = '''real = run_cli.Session.record_row
def pause(self, row, status, note):
    if status == 'FAIL':
        Path('.testcases/before-row').touch()
        time.sleep(30)
    return real(self, row, status, note)
run_cli.Session.record_row = pause
'''
        for expected, output in ((1, 'collected 0 items\n'), (2, '')):
            with self.subTest(output=output):
                self.cli('--run', 'demo', '--token', self.token, '--verify')
                proof = self.inspect()['last_proof']['id']
                self.assertFalse(self.inspect()['proof_stale'])
                marker = self.root / '.testcases/no-tests'
                marker.write_text(output)
                process = self.spawn('--run', 'demo', '--token', self.token, '--only', 'REQ-A', patch=patch)
                try:
                    self.wait_for('before-row', process)
                    self.stop(process)
                    (self.root / '.testcases/before-row').unlink()
                    info = self.inspect()
                    self.assertTrue(info['proof_stale'])
                    self.assertEqual(info['last_proof']['id'], proof)
                    self.assertEqual(info['checkpoint']['failures'], {'REQ-A': expected})
                    self.assertEqual(info['last_evidence']['rows']['REQ-A']['status'], 'FAIL')
                    check = json.loads((self.run / 'evidence' /
                                        (info['last_evidence']['id'] + '-check-1.json')).read_text())
                    self.assertEqual(check['exit_code'], 0)
                    self.assertFalse(check['passed'])
                    self.cli('checkpoint', 'demo', '--token', self.token, '--phase', 'repair', '--next', 'Fix filter')
                    self.assertEqual(self.inspect()['checkpoint']['failures'], {'REQ-A': expected})
                finally:
                    self.stop(process)
                    marker.unlink()


if __name__ == '__main__':
    unittest.main()
