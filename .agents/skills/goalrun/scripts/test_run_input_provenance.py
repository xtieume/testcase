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

    def test_excluded_file_deliverables_are_rejected_instead_of_counted_as_new(self):
        self.repository()
        for run_id, deliverable in (('built', 'build/schema.json'), ('cache', '.coverage')):
            with self.subTest(deliverable=deliverable):
                path = self.root / deliverable
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('preexisting output')
                token = self.init(run_id)
                self.ledger(run_id)
                ledger = self.folder(run_id) / 'goalrun/ledger.tsv'
                ledger.write_text(ledger.read_text().replace('\t-\t', f'\t{deliverable}\t'))
                out = self.cli('--run', run_id, '--token', token, '--only', 'REQ-A', code=1)
                self.assertIn('excluded', out.stdout)
                path.write_text('changed output')
                self.cli('--run', run_id, '--token', token, '--only', 'REQ-A', code=1)

    def test_excluded_directory_deliverable_is_rejected_instead_of_counted_as_new(self):
        self.repository()
        path = self.root / 'build/schema.json'
        path.parent.mkdir()
        path.write_text('preexisting output')
        token = self.init()
        self.ledger()
        ledger = self.folder() / 'goalrun/ledger.tsv'
        ledger.write_text(ledger.read_text().replace('\t-\t', '\tbuild\t'))
        out = self.cli('--run', 'export', '--token', token, '--only', 'REQ-A', code=1)
        self.assertIn('excluded', out.stdout)

    def test_tracked_output_directory_ignores_untracked_generated_siblings_when_shipping(self):
        self.repository()
        path = self.root / 'build/source.txt'
        path.parent.mkdir()
        path.write_text('tracked source')
        self.git('add', '-f', 'build/source.txt')
        (path.parent / 'schema.json').write_text('preexisting output')
        token = self.init()
        self.ledger()
        ledger = self.folder() / 'goalrun/ledger.tsv'
        ledger.write_text(ledger.read_text().replace('\t-\t', '\tbuild\t'))
        out = self.cli('--run', 'export', '--token', token, '--only', 'REQ-A', code=1)
        self.assertIn('unchanged since baseline', out.stdout)
        self.git('add', '-f', 'build/schema.json')
        self.cli('--run', 'export', '--token', token, '--only', 'REQ-A', code=1)
        (path.parent / 'schema.json').write_text('changed output')
        self.cli('--run', 'export', '--token', token, '--only', 'REQ-A', code=1)
        path.write_text('changed source')
        self.cli('--run', 'export', '--token', token, '--only', 'REQ-A')

    def exclusion_ledger(self, deliverable, run_id='export'):
        token = self.init(run_id)
        self.ledger(run_id, command="python3 -c \"assert open('feature.txt').read() == 'old\\n'\"",
                    brk='feature.txt :: old :: broken')
        ledger = self.folder(run_id) / 'goalrun/ledger.tsv'
        ledger.write_text(ledger.read_text().replace('\t-\t', f'\t{deliverable}\t'))
        return token

    def test_late_tracking_cannot_ship_preexisting_excluded_files_or_directories(self):
        self.repository()
        for run_id, deliverable, tracked in (('schema', 'build/schema.json', 'build/schema.json'),
                                              ('cache', '.coverage', '.coverage'),
                                              ('folder', 'dist', 'dist/schema.json')):
            with self.subTest(deliverable=deliverable):
                if deliverable == 'dist':
                    (self.root / '.gitignore').write_text((self.root / '.gitignore').read_text() + 'dist/\n')
                path = self.root / tracked
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('preexisting output')
                token = self.exclusion_ledger(deliverable, run_id)
                self.cli('--run', run_id, '--token', token, '--only', 'REQ-A', code=1)
                self.git('add', '-f', tracked)
                out = self.cli('--run', run_id, '--token', token, '--verify', code=1)
                self.assertIn('excluded', out.stdout)
                self.assertTrue(self.inspect(run_id)['proof_stale'])

    def test_ignore_rule_change_cannot_ship_preexisting_excluded_file(self):
        self.repository()
        path = self.root / 'build/schema.json'
        path.parent.mkdir()
        path.write_text('preexisting output')
        token = self.exclusion_ledger('build/schema.json')
        (self.root / '.gitignore').write_text('.testcases/\n')
        self.cli('--run', 'export', '--token', token, '--verify', code=1)
        self.assertTrue(self.inspect()['proof_stale'])

    def test_legacy_baseline_cannot_reclassify_unrecorded_generated_target_by_staging(self):
        self.repository()
        path = self.root / 'build/schema.json'
        path.parent.mkdir()
        path.write_text('preexisting output')
        token = self.exclusion_ledger('build/schema.json')
        baseline = self.folder() / 'goalrun/baseline.json'
        data = json.loads(baseline.read_text())
        data.pop('excluded', None)  # A saved baseline from before exclusion provenance existed.
        baseline.write_text(json.dumps(data))
        self.git('add', '-f', 'build/schema.json')
        self.cli('--run', 'export', '--token', token, '--verify', code=1)
        self.assertTrue(self.inspect()['proof_stale'])

    def test_legacy_directory_with_original_tracked_source_remains_deliverable(self):
        self.repository()
        path = self.root / 'build/source.txt'
        path.parent.mkdir()
        path.write_text('original tracked source')
        self.git('add', '-f', 'build/source.txt')
        token = self.exclusion_ledger('build')
        baseline = self.folder() / 'goalrun/baseline.json'
        data = json.loads(baseline.read_text())
        data.pop('excluded', None)
        baseline.write_text(json.dumps(data))
        path.write_text('changed tracked source')
        self.cli('--run', 'export', '--token', token, '--verify')
        self.assertFalse(self.inspect()['proof_stale'])

    def test_legacy_baseline_in_git_subdirectory_rejects_late_tracked_outputs(self):
        self.repository()
        repository = self.root
        for name, deliverable in (('schema', 'build/schema.json'), ('folder', 'build')):
            with self.subTest(deliverable=deliverable):
                self.root = repository / ('app-' + name)
                self.root.mkdir()
                (self.root / 'feature.txt').write_text('old\n')
                self.git('add', 'feature.txt')
                self.assertFalse((self.root / '.git').exists())
                self.assertEqual(self.git('rev-parse', '--is-inside-work-tree').strip(), 'true')
                path = self.root / 'build/schema.json'
                path.parent.mkdir()
                path.write_text('preexisting output')
                token = self.exclusion_ledger(deliverable)
                baseline = self.folder() / 'goalrun/baseline.json'
                data = json.loads(baseline.read_text())
                self.assertNotIn('build/schema.json', data['files'])
                self.assertIn('build', data['excluded'])
                data.pop('excluded')  # Exercise an existing baseline in the older format.
                baseline.write_text(json.dumps(data))
                original_baseline = baseline.read_bytes()
                self.git('add', '-f', 'build/schema.json')
                self.cli('--run', 'export', '--token', token, '--verify', code=1)
                self.assertTrue(self.inspect()['proof_stale'])
                self.assertEqual(path.read_text(), 'preexisting output')
                self.assertEqual(baseline.read_bytes(), original_baseline)

    def test_legacy_non_git_workspace_accepts_new_build_named_source(self):
        token = self.exclusion_ledger('build/schema.json')
        baseline = self.folder() / 'goalrun/baseline.json'
        data = json.loads(baseline.read_text())
        data.pop('excluded')
        baseline.write_text(json.dumps(data))
        original_baseline = baseline.read_bytes()
        path = self.root / 'build/schema.json'
        path.parent.mkdir()
        path.write_text('new ordinary source')
        self.cli('--run', 'export', '--token', token, '--verify')
        self.assertFalse(self.inspect()['proof_stale'])
        self.assertEqual(baseline.read_bytes(), original_baseline)

    def test_new_ordinary_source_and_original_tracked_output_remain_deliverable(self):
        self.repository()
        path = self.root / 'build/source.txt'
        path.parent.mkdir()
        path.write_text('original tracked source')
        self.git('add', '-f', 'build/source.txt')
        token = self.exclusion_ledger('build/source.txt')
        path.write_text('changed tracked source')
        self.cli('--run', 'export', '--token', token, '--verify')
        ledger = self.folder() / 'goalrun/ledger.tsv'
        ledger.write_text(ledger.read_text().replace('build/source.txt', 'src/new.py'))
        source = self.root / 'src/new.py'
        source.parent.mkdir()
        source.write_text('new source')
        self.cli('--run', 'export', '--token', token, '--verify')
        self.assertFalse(self.inspect()['proof_stale'])

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
