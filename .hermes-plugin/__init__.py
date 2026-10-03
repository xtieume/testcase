"""Expose the shared skill catalog to Hermes' native skill loader."""
from pathlib import Path


def register(ctx):
    here = Path(__file__).resolve().parent
    # Git-clone installs keep this module in .hermes-plugin/. A flattened
    # install places the module beside the catalog instead.
    for skills in (here.parent / '.agents/skills', here / '.agents/skills', here / 'skills'):
        paths = sorted(skills.glob('*/SKILL.md'))
        if paths:
            for path in paths:
                ctx.register_skill(path.parent.name, path)
            return
    raise RuntimeError('testcase: skill catalog is missing; reinstall the plugin')
