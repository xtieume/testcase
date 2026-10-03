# Installing testcase for Codex

## Plugin (Codex app and CLI)

From a local checkout:

```bash
git clone https://github.com/xtieume/testcase.git
codex plugin marketplace add ./testcase
codex plugin add testcase@testcase-marketplace
```

After this change is published, install directly from GitHub:

```bash
codex plugin marketplace add xtieume/testcase
codex plugin add testcase@testcase-marketplace
```

In the app, open Plugins and select the `testcase` marketplace to install
`testcase`. In CLI versions with the interactive plugin browser, use `/plugins`.
Start a new session after installation. This is a repository marketplace;
testcase is not listed in OpenAI's public directory.

## Native skills fallback

For a Codex version without plugin support, clone the repository to a permanent
location and link each skill into the native user skill directory:

```bash
git clone https://github.com/xtieume/testcase.git ~/.codex/testcase
mkdir -p ~/.agents/skills
for skill in ~/.codex/testcase/.agents/skills/*; do
  ln -s "$skill" ~/.agents/skills/
done
```

`ln -s` refuses to replace an existing skill of the same name. Resolve collisions
before continuing. On Windows, copy the individual skill folders into
`%USERPROFILE%\.agents\skills` instead of creating symlinks.

Restart Codex and ask `write test cases for spec.md` or invoke `$testcase`.
Keep one installation method active to avoid duplicate skill entries.

## Update and uninstall

For a Git marketplace, run `codex plugin marketplace upgrade testcase-marketplace`,
then refresh/reinstall testcase in the plugin browser. For the native fallback,
run `git -C ~/.codex/testcase pull --ff-only` and restart Codex; newly added skills
need new links.

Uninstall the plugin with `codex plugin remove testcase@testcase-marketplace`.
For the fallback, remove only the links you created from `~/.agents/skills`;
other skills in that directory belong to their own installations.

References: [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins),
[Superpowers Codex manifest](https://github.com/obra/superpowers/blob/main/.codex-plugin/plugin.json).
