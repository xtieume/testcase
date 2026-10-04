"""Regressions for complete workspace inputs and durable migration publication."""
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import time
import unittest

import test_run_cli as helpers

SCRIPT = helpers.SCRIPT


class InputProvenanceTests(unittest.TestCase):
    setUp = helpers.RunCliTests.setUp
    cli = helpers.RunCliTests.cli
    init = helpers.RunCliTests.init
    folder = helpers.RunCliTests.folder
    ledger = helpers.RunCliTests.ledger
    inspect = helpers.RunCliTests.inspect
    injected_cli = helpers.RunCliTests.injected_cli

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, text=True)

    def repository(self):
        self.git('init', '-q')
        (self.root / '.gitignore').write_text('.testcases/\n.env\nschema.json\nbuild/\n')
        self.git('add', 'feature.txt', '.gitignore')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-qm', 'Initial')

    def prove(self, extra=''):
        token = self.init()
        self.ledger(command='python3 -c "assert open(\'feature.txt\').read() == \'old\\n\'; ' +
                    (extra or 'assert True') + '"', brk='feature.txt :: old :: broken')
        self.cli('--run', 'export', '--token', token, '--verify')
        self.assertFalse(self.inspect()['proof_stale'])
        return token

    def test_ignored_check_input_change_invalidates_whole_proof(self):
        self.repository()
        (self.root / '.env').write_text('accepted')
        self.prove("assert open('.env').read() == 'accepted'")
        (self.root / '.env').write_text('changed')
        self.assertTrue(self.inspect()['proof_stale'])

    def test_ignored_file_named_build_remains_an_ordinary_input(self):
        self.repository()
        (self.root / '.gitignore').write_text('.testcases/\nbuild\n')
        (self.root / 'build').write_text('accepted')
        self.prove("assert open('build').read() == 'accepted'")
        (self.root / 'build').write_text('changed')
        self.assertTrue(self.inspect()['proof_stale'])

    def test_preexisting_ignored_file_deliverable_cannot_pass_unchanged(self):
        self.repository()
        (self.root / 'schema.json').write_text('{"version": 1}')
        token = self.init()
        self.ledger()
        ledger = self.folder() / 'goalrun/ledger.tsv'
        ledger.write_text(ledger.read_text().replace('\t-\t', '\tschema.json\t'))
        out = self.cli('--run', 'export', '--token', token, '--only', 'REQ-A', code=1)
        self.assertIn('unchanged since baseline', out.stdout)
        (self.root / 'schema.json').write_text('{"version": 2}')
        self.cli('--run', 'export', '--token', token, '--only', 'REQ-A')

    def test_staging_existing_worktree_bytes_invalidates_whole_proof(self):
        self.repository()
        (self.root / 'staged.txt').write_text('baseline')
        self.git('add', 'staged.txt')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-qm', 'Staged fixture')
        (self.root / 'staged.txt').write_text('worktree change')
        self.prove("import subprocess; assert not subprocess.check_output(['git', 'diff', '--cached'])")
        self.git('add', 'staged.txt')
        self.assertTrue(self.inspect()['proof_stale'])

    def test_index_refresh_during_checks_preserves_current_proof(self):
        self.repository()
        self.prove("import subprocess; subprocess.run(['git', 'status', '--porcelain'], check=True)")
        os.utime(self.root / 'feature.txt', None)
        self.git('update-index', '--refresh')
        self.assertFalse(self.inspect()['proof_stale'])

    def test_index_flags_invalidate_proof_without_changing_source(self):
        self.repository()
        self.prove()
        self.git('update-index', '--assume-unchanged', 'feature.txt')
        self.assertTrue(self.inspect()['proof_stale'])

    def test_removed_empty_ignored_directory_invalidates_whole_proof(self):
        self.repository()
        (self.root / '.gitignore').write_text((self.root / '.gitignore').read_text() + 'required/\n')
        (self.root / 'required').mkdir()
        self.prove("import os; assert os.path.isdir('required')")
        (self.root / 'required').rmdir()
        self.assertTrue(self.inspect()['proof_stale'])

    def test_generated_outputs_and_private_caches_do_not_invalidate_proof(self):
        self.repository()
        self.prove()
        for directory in ('build', '__pycache__', '.cache'):
            path = self.root / directory
            path.mkdir()
            (path / 'generated').write_text('output')
        self.assertFalse(self.inspect()['proof_stale'])

    def test_tracked_cache_file_overrides_exclusion(self):
        self.repository()
        path = self.root / '.cache/input.txt'
        path.parent.mkdir()
        path.write_text('original')
        self.git('add', '-f', '.cache/input.txt')
        self.prove()
        path.write_text('changed')
        self.assertTrue(self.inspect()['proof_stale'])

    def test_tracked_output_file_does_not_admit_untracked_sibling_outputs(self):
        self.repository()
        path = self.root / 'build/source.txt'
        path.parent.mkdir()
        path.write_text('tracked source')
        self.git('add', '-f', 'build/source.txt')
        self.prove()
        (path.parent / 'generated.txt').write_text('derived output')
        self.assertFalse(self.inspect()['proof_stale'])
        path.write_text('changed source')
        self.assertTrue(self.inspect()['proof_stale'])

    def test_staged_mode_and_conflict_entries_invalidate_proof(self):
        self.repository()
        self.prove()
        original = self.git('rev-parse', 'HEAD:feature.txt').strip()
        self.git('update-index', '--chmod=+x', 'feature.txt')
        self.assertEqual((self.root / 'feature.txt').stat().st_mode & 0o111, 0)
        self.assertTrue(self.inspect()['proof_stale'])
        self.git('reset', '-q', 'HEAD', '--', 'feature.txt')
        self.assertFalse(self.inspect()['proof_stale'])
        entries = ('0 ' + '0' * len(original) + '\tfeature.txt\n' +
                   ''.join(f'100644 {original} {stage}\tfeature.txt\n' for stage in (1, 2, 3)))
        subprocess.run(['git', 'update-index', '--index-info'], cwd=self.root,
                       input=entries, text=True, check=True)
        self.assertTrue(self.inspect()['proof_stale'])

    def test_intent_to_add_and_skip_worktree_flags_invalidate_proof(self):
        self.repository()
        (self.root / 'new.txt').write_text('new source')
        self.prove()
        self.git('update-index', '--skip-worktree', 'feature.txt')
        self.assertTrue(self.inspect()['proof_stale'])
        self.git('update-index', '--no-skip-worktree', 'feature.txt')
        self.assertFalse(self.inspect()['proof_stale'])
        self.git('add', '-N', 'new.txt')
        self.assertTrue(self.inspect()['proof_stale'])

    def test_index_refresh_with_newline_path_preserves_proof(self):
        self.repository()
        (self.root / 'odd\nname.txt').write_text('source')
        self.git('add', 'odd\nname.txt')
        self.prove()
        self.git('status', '--porcelain')
        self.assertFalse(self.inspect()['proof_stale'])

    def test_non_git_common_output_names_can_contain_source(self):
        for directory in ('bin', 'obj', 'target', 'dist', 'build'):
            path = self.root / directory / 'source.txt'
            path.parent.mkdir()
            path.write_text('original')
        self.prove()
        (self.root / 'build/source.txt').write_text('changed')
        self.assertTrue(self.inspect()['proof_stale'])

    def kill_after_publication(self):
        (self.root / '.testcases/migration-published').unlink(missing_ok=True)
        if not (self.root / '.testcases/goalrun/baseline.json').exists():
            self.cli('--baseline')
        (self.root / 'testcases.md').write_text('Legacy TC-1\n')
        bootstrap = (f"import sys; sys.path.insert(0, {str(SCRIPT.parent)!r}); "
                     "import goalrun, run_cli, time; from pathlib import Path\n"
                     "real_rename = run_cli.os.rename\n"
                     "def pause(*args):\n    real_rename(*args)\n"
                     "    Path('.testcases/migration-published').touch()\n    time.sleep(30)\n"
                     "run_cli.os.rename = pause\n"
                     f"sys.argv = {[str(SCRIPT), 'migrate', 'export', '--goal', 'Export CSV']!r}\n"
                     "raise SystemExit(goalrun.main())\n")
        proc = subprocess.Popen([sys.executable, '-c', bootstrap], cwd=self.root,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 5
            while not (self.root / '.testcases/migration-published').exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue((self.root / '.testcases/migration-published').exists())
        finally:
            proc.kill()
            proc.wait(timeout=5)
        self.assertTrue(self.folder().exists())
        return self.root / 'docs/testcases/export/testcases.md'

    def test_published_migration_restores_deleted_destination_before_cleanup(self):
        destination = self.kill_after_publication()
        destination.unlink()
        self.cli('resume', 'export', '--owner', 'A')
        self.assertTrue(destination.exists(), 'recovery deleted the remaining table copy')
        self.assertEqual(destination.read_text(), 'Legacy TC-1\n')
        self.assertFalse((self.folder() / 'migrated-testcases.md').exists())
        self.assertFalse(list((self.root / '.testcases/runs').glob('.*-publication.json')))

    def test_published_migration_preserves_conflicting_destination_and_recovery_copy(self):
        destination = self.kill_after_publication()
        destination.unlink()
        destination.write_text('User TC-99\n')
        out = self.cli('resume', 'export', '--owner', 'A', code=2)
        self.assertIn('conflict', out.stderr)
        self.assertEqual(destination.read_text(), 'User TC-99\n')
        self.assertEqual((self.folder() / 'migrated-testcases.md').read_text(), 'Legacy TC-1\n')
        self.assertTrue(list((self.root / '.testcases/runs').glob('.*-publication.json')))

    def test_destination_created_during_recovery_is_preserved_exclusively(self):
        destination = self.kill_after_publication()
        destination.unlink()
        self.injected_cli("real_link = run_cli.os.link\n"
                          "def collide(source, destination):\n"
                          "    run_cli.Path(destination).write_text('User TC-99\\n')\n"
                          "    real_link(source, destination)\nrun_cli.os.link = collide",
                          'resume', 'export', '--owner', 'A')
        self.assertEqual(destination.read_text(), 'User TC-99\n')
        self.assertEqual((self.folder() / 'migrated-testcases.md').read_text(), 'Legacy TC-1\n')
        self.assertTrue(list((self.root / '.testcases/runs').glob('.*-publication.json')))

    def test_recovery_after_copy_or_journal_cleanup_is_idempotent(self):
        for boundary in ('migrated-testcases.md', '.export-publication.json'):
            with self.subTest(boundary=boundary):
                # Each cleanup boundary gets an independent published migration.
                if self.folder().exists():
                    shutil.rmtree(self.folder())
                    (self.root / 'docs/testcases/export/testcases.md').unlink()
                destination = self.kill_after_publication()
                destination.unlink()
                patch = ("real_unlink = run_cli.Path.unlink\n"
                         "def stop(path, *args, **kwargs):\n"
                         "    result = real_unlink(path, *args, **kwargs)\n"
                         f"    if path.name == {boundary!r}: run_cli.os._exit(91)\n"
                         "    return result\nrun_cli.Path.unlink = stop")
                self.injected_cli(patch, 'resume', 'export', '--owner', 'A', code=91)
                self.assertEqual(destination.read_text(), 'Legacy TC-1\n')
                self.cli('resume', 'export', '--owner', 'A')
                self.assertEqual(destination.read_text(), 'Legacy TC-1\n')
                self.assertFalse((self.folder() / 'migrated-testcases.md').exists())
                self.assertFalse(list((self.root / '.testcases/runs').glob('.*-publication.json')))


if __name__ == '__main__':
    unittest.main()
