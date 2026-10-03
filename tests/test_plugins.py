"""Packaging regressions: missing skills and stale release metadata."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PluginTests(unittest.TestCase):
    def test_hermes_registers_catalog_as_paths(self):
        path = ROOT / '.hermes-plugin' / '__init__.py'
        self.assertTrue(path.is_file(), 'Hermes adapter is missing')
        spec = importlib.util.spec_from_file_location('testcase_hermes', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        registered = {}

        class Context:
            def register_skill(self, name, path):
                if not isinstance(path, Path):
                    raise TypeError('Hermes requires pathlib.Path')
                registered[name] = path.read_text()

        module.register(Context())
        expected = {
            folder.name for folder in (ROOT / '.agents/skills').iterdir()
            if (folder / 'SKILL.md').is_file()
        }
        self.assertTrue(expected)
        self.assertEqual(set(registered), expected)
        for name, content in registered.items():
            self.assertEqual(content, (ROOT / '.agents/skills' / name / 'SKILL.md').read_text())

    def test_hermes_flattened_install_and_missing_catalog(self):
        original = ROOT / '.hermes-plugin/__init__.py'
        self.assertTrue(original.is_file())
        with tempfile.TemporaryDirectory() as tmp:
            plugin = Path(tmp) / 'plugin'
            plugin.mkdir()
            path = plugin / '__init__.py'
            shutil.copy2(original, path)
            spec = importlib.util.spec_from_file_location('testcase_flattened', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            class Context:
                def __init__(self):
                    self.skills = {}

                def register_skill(self, name, path):
                    self.skills[name] = path.read_text()

            with self.assertRaisesRegex(RuntimeError, 'catalog is missing'):
                module.register(Context())
            (plugin / 'skills/fixture').mkdir(parents=True)
            (plugin / 'skills/fixture/SKILL.md').write_text('fixture skill')
            ctx = Context()
            module.register(ctx)
            self.assertEqual(ctx.skills, {'fixture': 'fixture skill'})

    def test_release_syncs_versions_and_new_muse_skills(self):
        script = ROOT / 'scripts' / 'sync_plugins.py'
        self.assertTrue(script.is_file(), 'Release sync script is missing')
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            for directory in ROOT.glob('.*-plugin'):
                shutil.copytree(directory, repo / directory.name)
            for file in ('gemini-extension.json', 'package.json'):
                shutil.copy2(ROOT / file, repo / file)
            skills = repo / '.agents/skills'
            shutil.copytree(ROOT / '.agents/skills', skills)
            (skills / 'new-skill').mkdir()
            (skills / 'new-skill/SKILL.md').write_text('---\nname: new-skill\ndescription: New skill\n---\n')
            result = subprocess.run([
                sys.executable, str(script), '--root', str(repo), '--version', '2.3.4',
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for path in repo.glob('.*-plugin/*.json'):
                data = json.loads(path.read_text())
                if path.name == 'plugin.json':
                    self.assertEqual(data['version'], '2.3.4', str(path))
                else:
                    self.assertTrue(all(p['version'] == '2.3.4' for p in data['plugins']))
            for file in ('gemini-extension.json', 'package.json'):
                self.assertEqual(json.loads((repo / file).read_text())['version'], '2.3.4')
            self.assertIn('version: 2.3.4\n', (repo / '.hermes-plugin/plugin.yaml').read_text())
            muse = json.loads((repo / '.muse-plugin/plugin.json').read_text())
            self.assertIn({'id': 'new-skill', 'path': '.agents/skills/new-skill/SKILL.md'},
                          muse['capabilities']['skills'])
            # A stale version must fail the read-only CI check, without fixing it.
            path = repo / '.codex-plugin/plugin.json'
            data = json.loads(path.read_text())
            data['version'] = '0.0.0'
            path.write_text(json.dumps(data))
            before = path.read_bytes()
            result = subprocess.run([
                sys.executable, str(script), '--root', str(repo), '--check',
            ], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('.codex-plugin/plugin.json', result.stdout + result.stderr)
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
