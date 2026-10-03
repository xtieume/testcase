"""Persistent ownership, confinement and atomic run state tests."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from run_store import RunError, Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root)

    def create(self, rid='one'):
        with self.store.lock(rid):
            return self.store.create(rid, 'Finish the goal', 'spec.md')

    def resume(self, store=None, rid='one', owner='A', generation=None):
        store = store or self.store
        with store.lock(rid):
            return store.resume(rid, owner, generation)

    def test_create_and_inspect(self):
        manifest = self.create()
        view = self.store.inspect('one')
        self.assertEqual(manifest, view['manifest'])
        self.assertEqual(manifest['version'], 1)
        self.assertEqual(manifest['workspace'], str(self.root.resolve()))
        self.assertEqual(manifest['goal'], 'Finish the goal')
        self.assertEqual(view['checkpoint']['phase'], 'plan')
        self.assertEqual(view['checkpoint']['generation'], 0)
        self.assertIsNone(view['checkpoint']['token'])
        self.assertEqual(view['handoff'], '')
        self.assertEqual(view['paths']['testcases'], str(self.root.resolve() / 'docs/testcases/one/testcases.md'))
        for key in ('goalrun_dir', 'docs_review_dir', 'testcase_dir'):
            self.assertTrue(Path(view['paths'][key]).is_dir())

    def test_release_and_new_store_resume_preserve_state_revoke_tokens(self):
        self.create()
        first = self.resume()
        token = first['checkpoint']['token']
        with self.store.lock('one'):
            self.store.checkpoint('one', token, 'build', 'Write tests', 'Tests red', failure='lint')
            self.store.release('one', token, 'Continue tests')
        second_store = Store(self.root)
        second = self.resume(second_store, owner='B')
        next_token = second['checkpoint']['token']
        self.assertNotEqual(next_token, token)
        self.assertEqual(second['checkpoint']['phase'], 'build')
        self.assertEqual(second['handoff'], 'Continue tests')
        with second_store.lock('one'):
            second_store.checkpoint('one', next_token, 'review', 'Review work', 'Tests green')
            with self.assertRaises(RunError):
                second_store.require('one', token)
        final = Store(self.root).inspect('one')
        self.assertEqual(final['checkpoint']['phase'], 'review')
        self.assertEqual(final['checkpoint']['failures'], {'lint': 1})
        self.assertEqual(final['handoff'], 'Tests green')
        self.assertEqual(final['checkpoint']['generation'], 5)

    def test_owned_collision_and_explicit_generation_takeover(self):
        self.create()
        first = self.resume()
        with self.assertRaises(RunError):
            self.resume(owner='B')
        with self.assertRaises(RunError):
            self.resume(owner='B', generation=0)
        second = self.resume(owner='B', generation=first['checkpoint']['generation'])
        self.assertEqual(second['checkpoint']['owner'], 'B')
        with self.assertRaises(RunError):
            self.store.require('one', first['checkpoint']['token'])
        with self.assertRaises(RunError):
            self.resume(owner='C', generation=first['checkpoint']['generation'])

    def test_schema_and_workspace_rejection(self):
        self.create()
        path = Path(self.store.inspect('one')['paths']['manifest'])
        original = json.loads(path.read_text())
        for field, value in [('version', 2), ('workspace', '/different-workspace')]:
            modified = dict(original, **{field: value})
            path.write_text(json.dumps(modified))
            with self.assertRaises(RunError):
                self.store.inspect('one')
        path.write_text(json.dumps(original))
        checkpoint = Path(self.store.inspect('one')['paths']['checkpoint'])
        checkpoint.write_text('{bad JSON')
        with self.assertRaises(RunError):
            self.store.inspect('one')

    def test_two_runs_list_independent_and_duplicate_creation(self):
        self.create('z')
        self.create('a')
        self.resume(rid='z')
        self.assertEqual([row['run_id'] for row in self.store.list()], ['a', 'z'])
        self.assertIsNone(self.store.inspect('a')['checkpoint']['owner'])
        with self.assertRaises(RunError):
            self.create('a')
        self.assertEqual(self.store.inspect('a')['checkpoint']['generation'], 0)

    def test_malicious_ids(self):
        for rid in ('', '../outside', '/tmp/x', 'a/b', '.hidden', 'a.b', 'a' * 81, 'x\n'):
            with self.subTest(rid=rid), self.assertRaises(RunError):
                with self.store.lock(rid):
                    self.store.create(rid, 'goal')

    def test_outside_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.root / '.testcases').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(RunError):
                self.create()

    def test_artifact_and_run_symlinks_rejected(self):
        self.create()
        paths = self.store.inspect('one')['paths']
        with tempfile.TemporaryDirectory() as outside:
            artifact = Path(paths['docs_review_dir'])
            artifact.rmdir()
            artifact.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(RunError):
                self.store.inspect('one')
            artifact.unlink()
            artifact.mkdir()
            run = Path(paths['run_dir'])
            run.rename(run.with_name('saved'))
            run.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(RunError):
                self.store.inspect('one')

    def test_nonblocking_lock_between_processes(self):
        script = ('from run_store import Store, RunError\n'
                  'import sys\n'
                  'try:\n'
                  ' with Store(sys.argv[1]).lock("one"): pass\n'
                  'except RunError: sys.exit(7)\n')
        with self.store.lock('one'):
            result = subprocess.run([sys.executable, '-c', script, str(self.root)],
                                    cwd=Path(__file__).parent, capture_output=True, text=True)
        self.assertEqual(result.returncode, 7, result.stderr)
        with self.store.lock('one'):
            pass

    def test_checkpoint_failed_replace_keeps_previous_complete_state(self):
        self.create()
        token = self.resume()['checkpoint']['token']
        before = self.store.inspect('one')
        with self.store.lock('one'), mock.patch('run_store.os.replace', side_effect=OSError('disk')):
            with self.assertRaises(RunError):
                self.store.checkpoint('one', token, 'build', 'next', 'new handoff')
        self.assertEqual(self.store.inspect('one'), before)
        self.assertFalse(list(Path(before['paths']['run_dir']).glob('*.tmp')))

    def test_restart_in_new_interpreter_continues_released_checkpoint(self):
        self.create()
        token = self.resume()['checkpoint']['token']
        with self.store.lock('one'):
            self.store.checkpoint('one', token, 'build', 'Finish tests', 'A stopped')
            self.store.release('one', token, 'B should finish tests')
        script = ('from run_store import Store\n'
                  'import sys\n'
                  'store = Store(sys.argv[1])\n'
                  'with store.lock("one"):\n'
                  ' view = store.resume("one", "B")\n'
                  ' assert view["handoff"] == "B should finish tests"\n'
                  ' store.checkpoint("one", view["checkpoint"]["token"], '
                  '"review", "Inspect proof", "B finished")\n')
        result = subprocess.run([sys.executable, '-c', script, str(self.root)],
                                cwd=Path(__file__).parent, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        view = self.store.inspect('one')
        self.assertEqual(view['checkpoint']['owner'], 'B')
        self.assertEqual(view['handoff'], 'B finished')
        with self.assertRaises(RunError):
            self.store.require('one', token)

    def test_tracked_artifact_parent_symlink_rejected(self):
        self.create()
        with tempfile.TemporaryDirectory() as outside:
            (self.root / 'docs').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(RunError):
                self.store.inspect('one')

    def test_none_token_and_empty_owner_refused(self):
        self.create()
        with self.assertRaises(RunError):
            self.store.require('one', None)
        with self.assertRaises(RunError):
            self.resume(owner=' ')

    def test_symlink_to_another_run_is_refused_even_inside_workspace(self):
        self.create('one')
        self.create('two')
        paths = self.store.inspect('one')['paths']
        other = self.store.inspect('two')['paths']
        directory = Path(paths['goalrun_dir'])
        directory.rmdir()
        directory.symlink_to(other['goalrun_dir'], target_is_directory=True)
        with self.assertRaises(RunError):
            self.store.inspect('one')

    def test_malformed_evidence_and_manifest_cannot_revoke_previous_owner(self):
        self.create()
        view = self.resume()
        original_token = view['checkpoint']['token']
        path = Path(view['paths']['checkpoint'])
        cp = json.loads(path.read_text())
        cp['last_evidence'] = 5
        path.write_text(json.dumps(cp))
        before = path.read_bytes()
        with self.assertRaises(RunError):
            self.resume(owner='B', generation=1)
        self.assertEqual(path.read_bytes(), before)
        cp.pop('last_evidence')
        path.write_text(json.dumps(cp))
        manifest_path = Path(view['paths']['manifest'])
        manifest = json.loads(manifest_path.read_text())
        manifest['spec'] = 5
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(RunError):
            self.resume(owner='B', generation=1)
        self.assertEqual(json.loads(path.read_text())['token'], original_token)


if __name__ == '__main__':
    unittest.main()
