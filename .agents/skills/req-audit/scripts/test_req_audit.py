"""REQ-AUDIT built from a real named run: verify result, evidence index, staleness."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('req_audit.py')
GOALRUN = Path(__file__).resolve().parents[2] / 'goalrun' / 'scripts' / 'goalrun.py'
PNG = bytes.fromhex('89504e470d0a1a0a')

BREAK = 'feature.txt :: old :: broken'
LEDGER = '\n'.join([
    f'R1\tREQ-A1 exports CSV\tpython3 check.py\t-\t{BREAK}',
    f'R2\tREQ-A2 quotes cells\ttrue\t-\t{BREAK}',
    'R3\tREQ-A3 PM approves wording\tMANUAL:pm\t-\t',
    f'R6\tREQ-A6 has a header\tpython3 check.py\t-\t{BREAK}',
    f'R10\tREQ-A10 owns this row\ttrue\t-\t{BREAK}',
    '# no-row-ok: REQ-A4 — screenshot only',
    '# no-row-ok: REQ-A5 — not built yet',
]) + '\n'
REQS = 'REQ-A1: Export CSV\nREQ-A2\nREQ-A3\nREQ-A4: Screenshot only\nREQ-A5\nREQ-A6\nREQ-A10\n'


class ReqAuditTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'feature.txt').write_text('old\n')
        (self.root / 'check.py').write_text('import sys\nsys.exit(open("feature.txt").read() != "old\\n")\n')
        self.goalrun('init', 'demo', '--goal', 'Export CSV')
        self.token = json.loads(self.goalrun('resume', 'demo', '--owner', 'a').stdout)['token']
        self.run = self.root / '.testcases/runs/demo'
        (self.run / 'goalrun/ledger.tsv').write_text(LEDGER)
        (self.run / 'goalrun/reqs.txt').write_text(REQS)
        evidence = self.run / 'audit/evidence'
        evidence.mkdir(parents=True)
        for name in ('a1.png', 'a4.png', 'spec.png'):
            (evidence / name).write_bytes(PNG)
        (self.run / 'audit/data').mkdir()
        (self.run / 'audit/data/evidence.jsonl').write_text('\n'.join(json.dumps(x) for x in [
            {'file': 'a1.png', 'reqs': ['REQ-A1'], 'caption': 'export', 'caption_vi': 'xuất'},
            {'file': 'evidence/a4.png', 'reqs': ['REQ-A4']},
            {'file': 'spec.png', 'reqs': ['REQ-A5'], 'spec_only': True},
            {'file': '../outside.png', 'reqs': ['REQ-A5']},
        ]) + '\n')

    def goalrun(self, *args, code=None):
        out = subprocess.run([sys.executable, str(GOALRUN), *args], cwd=self.root, text=True,
                             capture_output=True, timeout=60)
        if code is not None:
            self.assertEqual(out.returncode, code, out.stdout + out.stderr)
        return out

    def audit(self, *args):
        out = subprocess.run([sys.executable, str(SCRIPT), 'demo', *args], cwd=self.root, text=True,
                             capture_output=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        return json.loads(out.stdout), (self.run / 'audit/REQ-AUDIT.html').read_text()

    def test_without_verify_every_row_is_not_run(self):
        result, page = self.audit()
        self.assertIsNone(result['verify'])
        self.assertIn('no recorded --verify', page)
        self.assertEqual(result['status_counts']['UNPROVEN'], 5)

    def test_statuses_follow_the_recorded_verify(self):
        self.goalrun('--run', 'demo', '--token', self.token, '--verify', code=1)
        result, page = self.audit()
        self.assertEqual(result['verify']['stale_because'], [])
        self.assertIsNotNone(result['verify']['whole_ledger'])
        self.assertEqual(result['verify']['subsets_after'], 0)
        self.assertEqual(result['status_counts'], {'PASS': 2, 'DEVIATION': 2, 'AWAITING_SIGN': 1,
                                                   'NO_TEST': 1, 'MISSING': 1})
        self.assertNotIn('REQ-A1', result['gaps'])
        self.assertEqual(result['gaps']['REQ-A5'], ['verified break', 'automated test', 'evidence'])
        self.assertIn("href='evidence/a1.png'", page)
        self.assertIn('vi: xuất', page)
        self.assertNotIn('outside.png', page)
        self.assertEqual(page.count('<strong>R1</strong>'), 1)  # REQ-A10's row is not REQ-A1's
        self.assertEqual((self.root / 'feature.txt').read_text(), 'old\n')

    def test_subset_verify_overlays_the_whole_ledger_one(self):
        self.goalrun('--run', 'demo', '--token', self.token, '--verify', code=1)
        (self.run / 'goalrun/ledger.tsv').write_text(LEDGER.replace('R2\tREQ-A2 quotes cells\ttrue', 'R2\tREQ-A2 quotes cells\tpython3 check.py'))
        self.goalrun('--run', 'demo', '--token', self.token, '--verify', 'R2', code=0)
        result, page = self.audit('--no-stale-check')
        self.assertEqual(result['verify']['subsets_after'], 1)
        self.assertEqual(result['verify']['latest']['subset'], 'R2')
        self.assertEqual(result['status_counts']['PASS'], 3)  # R1, R6 from the whole run, R2 from the subset
        self.assertIn('overlaid by 1 later subset run', page)

    def test_reports_stale_inputs_after_verify(self):
        self.goalrun('--run', 'demo', '--token', self.token, '--verify', code=1)
        (self.run / 'goalrun/ledger.tsv').write_text(LEDGER + 'R7\tREQ-A5 later\ttrue\t-\t\n')
        result, page = self.audit()
        self.assertIn('run-inputs', result['verify']['stale_because'])
        self.assertIn('Stale', page)
        result, page = self.audit('--no-stale-check')
        self.assertIsNone(result['verify']['stale_because'])
        self.assertIn('Not checked against the current workspace', page)

    def test_reqs_jsonl_overrides_reqs_txt(self):
        (self.run / 'audit/data/reqs.jsonl').write_text('\n'.join(json.dumps(x) for x in [
            {'id': 'REQ-A1', 'req': 'Export', 'area': 'CSV', 'proposal': 'Use commas', 'proposal_ja': 'カンマ',
             'human_owner': 'PM'},
            {'id': 'REQ-A2', 'req': 'Old', 'status': 'OBSOLETE', 'obsolete_reason': 'dropped'},
        ]) + '\n')
        result, page = self.audit()
        self.assertEqual(sum(result['status_counts'].values()), 2)
        self.assertEqual(result['status_counts']['OBSOLETE'], 1)
        self.assertIn('Awaiting a human decision (1 REQ)', page)
        self.assertIn('カンマ', page)


if __name__ == '__main__':
    unittest.main()
