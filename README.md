[![Version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fxtieume%2Ftestcase%2Fmain%2F.claude-plugin%2Fplugin.json&query=%24.version&label=version&color=blue)](.claude-plugin/plugin.json)
[![Skills](https://img.shields.io/badge/skills-5-8957e5)](#skills)
[![Stars](https://img.shields.io/github/stars/xtieume/testcase?style=flat&color=f5a623)](https://github.com/xtieume/testcase/stargazers)
[![Last commit](https://img.shields.io/github/last-commit/xtieume/testcase)](https://github.com/xtieume/testcase/commits/main)
[![License](https://img.shields.io/github/license/xtieume/testcase?color=green)](LICENSE)

Skills for QA and documentation work — write the test cases, audit the docs, fetch the pages. Install once, use them in Claude Code, ZCode, Cursor or Antigravity.

[Tiếng Việt](README.vi.md)

## Install

**Claude Code** — marketplace install, gets every skill in the repo:

```bash
claude plugin marketplace add xtieume/testcase
claude plugin install testcase@testcase-marketplace
```

**ZCode** — same flow, reading `.zcode-plugin/`:

```bash
zcode plugin marketplace add xtieume/testcase
zcode plugin install testcase@testcase-marketplace
```

**Cursor / Antigravity** — both read `.agents/skills/` natively. Clone once, then symlink it into a project or copy it globally:

```bash
git clone https://github.com/xtieume/testcase.git

# project level (either editor)
ln -s "$(pwd)/testcase/.agents/skills" .agents/skills

# global
cp -R testcase/.agents/skills/* ~/.cursor/skills/              # Cursor
cp -R testcase/.agents/skills/* ~/.gemini/antigravity/skills/  # Antigravity
```

**Any host, one skill only** — copy the folder you want:

```bash
cp -R .agents/skills/<name> ~/.claude/skills/<name>
```

Skills trigger on natural language, or explicitly as `/<name>`.

## Skills

Each name links to its `SKILL.md`, which is the reference for that skill — triggers, workflow, flags, scripts.

### Delivery

| Skill | Does | Trigger |
| ----- | ---- | ------- |
| 🎯 [`goalrun`](.agents/skills/goalrun/SKILL.md) | Turns a goal into a ledger of checks, runs each phase through an independent subagent, and will not say done until the script exits 0 | "build X and don't stop until it's done" |

The three compose into one pipeline: **`docs-review`** says what is required, **`testcase`** says how it is proven, **`goalrun`** says whether it holds. Each still works alone.

Four diagrams of that pipeline, and of how `goalrun` decides a row and proves a check: [How these skills work](docs/how-it-works.md).

### QA

| Skill | Does | Trigger |
| ----- | ---- | ------- |
| 🧪 [`testcase`](.agents/skills/testcase/SKILL.md) | Test cases from a requirement or a Figma design, attacks its own output for missed cases, then implements the automatable ones as runnable tests and files what fails | "write test cases for…" |
| 📋 [`docs-review`](.agents/skills/docs-review/SKILL.md) | Audits docs against a spec: required vs actually written, with a citation per verdict | "review the docs against spec.md" |

### Data capture

| Skill | Does | Trigger |
| ----- | ---- | ------- |
| 📥 [`playwright-cdp`](.agents/skills/playwright-cdp/SKILL.md) | Notion pages and Slack threads → markdown through a logged-in browser: body, every comment, and the attachments downloaded | "read this Notion page", "pull this Slack thread" |

### Authoring

| Skill | Does | Trigger |
| ----- | ---- | ------- |
| ✍️ [`normalize`](.agents/skills/normalize/SKILL.md) | Rewrites a rambling everyday prompt into a compact engineering prompt — same requirements, imperative form, explicit escalation and done criteria | "rewrite this prompt for /goalrun" |

## House rules

Conventions every skill here follows, so a new one is predictable before you open it:

- **`SKILL.md` stays small.** Detail goes in `references/`, loaded only when the task needs it.
- **Review before returning.** Skills that produce a deliverable end with an independent subagent pass that re-derives the work and attacks it, repeating until a round adds nothing.
- **Scripts are stdlib.** Python or Node, no install step unless the skill says otherwise; they lint the output rather than trusting it.
- **Verdicts carry evidence.** Any claim about a document or requirement cites the line it came from.

Setup beyond cloning, where a skill needs it:

```bash
cd .agents/skills/playwright-cdp/scripts && npm install   # once
```

## Adding a skill

Drop a folder into `.agents/skills/<name>/` with a `SKILL.md` (frontmatter `name` + `description`), plus optional `references/` and `scripts/`. No manifest edit: both `plugin.json` files point at the directory, not a list. Add a row to the table above and bump the skill count in the badge. Versions are not edited by hand: merging to `main` bumps all four manifests, tags the commit and publishes a release — `feat:` gives a minor bump, `!` or `BREAKING CHANGE` a major one, anything else a patch.

## Layout

```
.agents/skills/<name>/     SKILL.md + references/ + scripts/
.claude-plugin/            Claude Code manifests
.zcode-plugin/             ZCode manifests
```

## License

MIT
