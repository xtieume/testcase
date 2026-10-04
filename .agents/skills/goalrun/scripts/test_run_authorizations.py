"""Authorization regressions exercise the public CLI across durable sessions."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('goalrun.py')
OLD_WAIVER = '# verify-ok: REQ-A — test-first, seen red on 2026-10-03\n'
FRESH_WAIVER = '# verify-ok: REQ-A — test-first, seen red on 2026-10-04 for revised check\n'


class RunAuthorizationTests(unittest.TestCase):
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

    def init(self, run='export'):
        self.cli('init', run, '--goal', 'Export CSV')
        return json.loads(self.cli('resume', run, '--owner', 'A').stdout)['token']

    def folder(self, run='export'):
        return self.root / '.testcases/runs' / run / 'goalrun'

    def ledger(self, folder=None, what='Exports CSV', check='true', brk='', waiver=OLD_WAIVER):
        folder = folder or self.folder()
        (folder / 'ledger.tsv').write_text(f'REQ-A\t{what}\t{check}\t-\t{brk}\n' + waiver)
        (folder / 'reqs.txt').write_text('REQ-A\n')

    def info(self, run='export'):
        return json.loads(self.cli('inspect', run).stdout)

    def verify(self, token, code=0, run='export'):
        return self.cli('--run', run, '--token', token, '--verify', code=code)

    def test_current_manual_owner_must_sign_before_whole_verification(self):
        token = self.init()
        self.ledger(check='MANUAL:alice', waiver='')
        self.cli('--run', 'export', '--token', token, '--sign', 'REQ-A', '--who', 'alice', '--note', 'Accepted')
        self.verify(token)
        self.ledger(check='MANUAL:bob', waiver='')
        self.verify(token, code=1)
        info = self.info()
        self.assertEqual(info['last_evidence']['rows']['REQ-A']['status'], 'WAIT')
        self.assertFalse(info['last_evidence']['whole_ledger_verified'])
        self.assertTrue(info['proof_stale'])
        self.cli('--run', 'export', '--token', token, '--sign', 'REQ-A', '--who', 'bob', '--note', 'Accepted')
        self.verify(token)
        self.assertFalse(self.info()['proof_stale'])

    def test_unchanged_waiver_cannot_authorize_changed_wording_or_check(self):
        for changes in ({'what': 'Exports JSON'}, {'check': 'test -f feature.txt'}):
            with self.subTest(changes=changes):
                token = self.init('wording' if 'what' in changes else 'check')
                run = 'wording' if 'what' in changes else 'check'
                self.ledger(folder=self.folder(run))
                self.verify(token, run=run)
                baseline = (self.folder(run) / 'baseline.json').read_bytes()
                self.ledger(folder=self.folder(run), **changes)
                self.verify(token, code=1, run=run)
                self.assertFalse(self.info(run)['last_evidence']['whole_ledger_verified'])
                self.assertTrue(self.info(run)['proof_stale'])
                self.assertEqual((self.folder(run) / 'baseline.json').read_bytes(), baseline)

    def test_measure_handoff_and_deleted_row_do_not_refresh_stale_waiver(self):
        token = self.init()
        self.ledger()
        self.verify(token)
        self.ledger(what='Exports JSON')
        self.cli('--run', 'export', '--token', token, '--only', 'REQ-A')
        self.verify(token, code=1)
        self.cli('release', 'export', '--token', token, '--note', 'Review authorization')
        token = json.loads(self.cli('resume', 'export', '--owner', 'B').stdout)['token']
        self.verify(token, code=1)
        self.ledger(what='Exports JSON', waiver='')
        self.verify(token, code=1)
        self.ledger(what='Exports JSON')
        self.verify(token, code=1)
        self.ledger(what='Exports JSON', waiver=FRESH_WAIVER)
        self.verify(token)
        info = self.info()
        self.assertFalse(info['proof_stale'])
        self.assertFalse(info['last_evidence']['inputs_changed'])

    def test_break_or_manual_conversion_cannot_rebind_old_waiver(self):
        token = self.init()
        self.ledger()
        self.verify(token)
        self.ledger(brk='feature.txt :: old :: broken')
        self.cli('--run', 'export', '--token', token, '--only', 'REQ-A')
        self.ledger(what='Exports JSON')
        self.verify(token, code=1)
        self.ledger(check='MANUAL:alice', waiver='')
        self.cli('--run', 'export', '--token', token, '--only', 'REQ-A', code=1)
        self.ledger(check='test -f feature.txt')
        self.verify(token, code=1)

    def test_changed_reason_requires_explicit_fresh_red_observation(self):
        token = self.init()
        self.ledger()
        self.verify(token)
        self.ledger(what='Exports JSON', waiver='# verify-ok: REQ-A — still seems fine\n')
        self.verify(token, code=1)
        self.ledger(what='Exports JSON', waiver=FRESH_WAIVER)
        self.verify(token)
        self.assertFalse(self.info()['proof_stale'])

    def test_initial_binding_and_unchanged_handoff_produce_current_proof(self):
        token = self.init()
        self.ledger()
        self.verify(token)
        self.assertFalse(self.info()['last_evidence']['inputs_changed'])
        self.assertFalse(self.info()['proof_stale'])
        self.cli('release', 'export', '--token', token)
        token = json.loads(self.cli('resume', 'export', '--owner', 'B').stdout)['token']
        self.verify(token)
        self.assertFalse(self.info()['proof_stale'])

    def test_waiver_binding_is_an_authoritative_proof_input(self):
        token = self.init()
        self.ledger()
        self.verify(token)
        (self.folder() / 'verify-waivers.json').write_text('{}\n')
        self.assertTrue(self.info()['proof_stale'])

    def test_legacy_binding_survives_migration_without_reauthorizing_changed_row(self):
        self.cli('--baseline')
        folder = self.root / '.testcases/goalrun'
        self.ledger(folder=folder)
        self.cli('--lint-ledger')
        self.ledger(folder=folder, what='Exports JSON')
        self.cli('migrate', 'export', '--goal', 'Export JSON')
        token = json.loads(self.cli('resume', 'export', '--owner', 'B').stdout)['token']
        self.verify(token, code=1)
        self.ledger(what='Exports JSON', waiver=FRESH_WAIVER)
        self.verify(token)
        self.assertFalse(self.info()['proof_stale'])

    def test_legacy_whole_verification_rejects_stale_waiver_in_mixed_ledger(self):
        self.cli('--baseline')
        folder = self.root / '.testcases/goalrun'
        self.ledger(folder=folder)
        with (folder / 'ledger.tsv').open('a') as f:
            f.write("REQ-B\tPreserves feature\tpython3 -c \"assert open('feature.txt').read() == 'old\\n'\"\t-\tfeature.txt :: old :: broken\n")
        self.cli('--verify')
        ledger = folder / 'ledger.tsv'
        ledger.write_text(ledger.read_text().replace('Exports CSV', 'Exports JSON'))
        self.cli('--verify', code=1)

    def test_removed_row_and_reused_observation_cannot_refresh_authorization(self):
        token = self.init()
        self.ledger()
        self.verify(token)
        (self.folder() / 'ledger.tsv').write_text('REQ-B\tAnother requirement\ttrue\t-\t-\n')
        (self.folder() / 'reqs.txt').write_text('REQ-B\n')
        self.cli('--run', 'export', '--token', token, '--only', 'REQ-B')
        self.ledger(what='Exports JSON')
        self.verify(token, code=1)
        self.ledger(what='Exports JSON', waiver=FRESH_WAIVER)
        self.verify(token)
        self.ledger(what='Exports XML', waiver=OLD_WAIVER)
        self.verify(token, code=1)

    def test_named_runs_bind_their_own_waivers(self):
        a = self.init('export')
        self.ledger()
        self.verify(a)
        b = self.init('login')
        self.ledger(folder=self.folder('login'), what='Logs in')
        self.verify(b, run='login')
        self.ledger(what='Exports JSON')
        self.verify(a, code=1)
        self.verify(b, run='login')
        self.assertFalse(self.info('login')['proof_stale'])


if __name__ == '__main__':
    unittest.main()
