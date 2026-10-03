# Installing testcase for OpenCode

testcase uses OpenCode's native skill discovery; no JavaScript plugin or package
dependency is needed.

## Global installation

Clone to a permanent location and link each skill into OpenCode's skill directory:

```bash
git clone https://github.com/xtieume/testcase.git ~/.config/opencode/testcase
mkdir -p ~/.config/opencode/skills
for skill in ~/.config/opencode/testcase/.agents/skills/*; do
  ln -s "$skill" ~/.config/opencode/skills/
done
```

`ln -s` refuses to replace existing entries. Resolve any same-name collisions
before continuing. On Windows, copy the individual folders into
`%USERPROFILE%\.config\opencode\skills` instead.

## Project installation

From the target project, with the clone outside that project:

```bash
mkdir -p .agents/skills
for skill in /absolute/path/to/testcase/.agents/skills/*; do
  ln -s "$skill" .agents/skills/
done
```

OpenCode also discovers `.agents/skills/` directly when working in this repo.
Restart the session, ask the agent to list skills with its `skill` tool, then
load `testcase` or ask `write test cases for spec.md`.

## Update and uninstall

Run `git -C ~/.config/opencode/testcase pull --ff-only` and restart OpenCode.
Link any newly added skill folders. To uninstall, remove only the testcase links
you created in the skill directory.

Reference: [OpenCode Agent Skills](https://opencode.ai/docs/skills/).
