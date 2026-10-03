"""Keep release versions and Muse's explicit skill catalog in sync (stdlib only)."""
import argparse
import json
from pathlib import Path
import re
import sys


def sync(root, version=None, check=False):
    current = json.loads((root / '.claude-plugin/plugin.json').read_text())['version']
    version = version or current
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError(f'Invalid release version: {version}')
    stale = []

    def update(path, content):
        if path.read_text() != content:
            stale.append(str(path.relative_to(root)))
            if not check:
                path.write_text(content)

    for path in sorted(root.glob('.*-plugin/*.json')) + [
        root / 'gemini-extension.json', root / 'package.json',
    ]:
        data = json.loads(path.read_text())
        if path.name == 'marketplace.json':
            for plugin in data['plugins']:
                plugin['version'] = version
        else:
            data['version'] = version
        if path.parent.name == '.muse-plugin' and path.name == 'plugin.json':
            data['capabilities']['skills'] = [
                {'id': p.parent.name, 'path': p.relative_to(root).as_posix()}
                for p in sorted(root.glob('.agents/skills/*/SKILL.md'))
            ]
        update(path, json.dumps(data, indent=2, ensure_ascii=False) + '\n')

    path = root / '.hermes-plugin/plugin.yaml'
    content, count = re.subn(r'^version: .*$', f'version: {version}', path.read_text(), flags=re.M)
    if count != 1:
        raise ValueError('Hermes manifest must contain exactly one version field')
    update(path, content)
    return stale


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--version', help='Release version; defaults to the Claude manifest version')
    parser.add_argument('--check', action='store_true', help='Report drift without writing files')
    args = parser.parse_args()
    stale = sync(args.root.resolve(), args.version, args.check)
    if args.check and stale:
        print('Out of sync: ' + ', '.join(stale), file=sys.stderr)
        return 1
    print('Plugin metadata is in sync.' if args.check else 'Plugin metadata synchronized.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
