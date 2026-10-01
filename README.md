<p align="center">
  <a href="README.md"><img alt="English" src="https://img.shields.io/badge/EN-English-blue?style=flat-square"></a>
  <a href="README.vi.md"><img alt="Tiếng Việt" src="https://img.shields.io/badge/VI-Tiếng_Việt-cc6699?style=flat-square"></a>
</p>

<h1 align="center">testcase</h1>

<p align="center"><strong>Your agent says done. Make it prove it.</strong></p>

<p align="center">
  <a href=".claude-plugin/plugin.json"><img alt="Version" src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fxtieume%2Ftestcase%2Fmain%2F.claude-plugin%2Fplugin.json&query=%24.version&label=version&color=6c63ff&style=flat-square"></a>
  <img alt="Claude Code" src="https://img.shields.io/badge/Claude_Code-ready-d97757?style=flat-square">
  <img alt="ZCode" src="https://img.shields.io/badge/ZCode-ready-informational?style=flat-square">
  <img alt="Cursor" src="https://img.shields.io/badge/Cursor-ready-black?style=flat-square">
  <img alt="Antigravity" src="https://img.shields.io/badge/Antigravity-ready-4285F4?style=flat-square">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/github/license/xtieume/testcase?color=green&style=flat-square"></a>
  <a href="https://github.com/xtieume/testcase/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/xtieume/testcase?color=f5a623&style=flat-square"></a>
</p>

<p align="center">
  <a href="#get-started"><img alt="Get started" src="https://img.shields.io/badge/Get_started-2EA043?style=for-the-badge"></a>
  <a href="docs/how-it-works.md"><img alt="How it works" src="https://img.shields.io/badge/How_it_works-1F6FEB?style=for-the-badge&logo=mermaid&logoColor=white"></a>
  <a href="../../releases"><img alt="Releases" src="https://img.shields.io/badge/Releases-6E7681?style=for-the-badge&logo=github&logoColor=white"></a>
</p>

<p align="center">
  <a href="docs/how-it-works.md#1-the-pipeline"><img alt="The pipeline" src="https://img.shields.io/badge/1-The_pipeline-8957e5?style=flat-square"></a>
  <a href="docs/how-it-works.md#2-what-changes"><img alt="What changes" src="https://img.shields.io/badge/2-What_changes-1f6feb?style=flat-square"></a>
  <a href="docs/how-it-works.md#3-how-one-row-is-decided"><img alt="How a row is decided" src="https://img.shields.io/badge/3-How_a_row_is_decided-2ea043?style=flat-square"></a>
  <a href="docs/how-it-works.md#4-proving-the-checks-themselves"><img alt="Proving the checks" src="https://img.shields.io/badge/4-Proving_the_checks-d97757?style=flat-square"></a>
</p>

testcase is a set of agent skills that take a requirement all the way to code that ships: pin down what the spec asks for, turn it into real tests, then build until every check passes. Every step leaves proof you can rerun.

## Done should mean done

You ask an AI agent to build a feature. It says done. You check — a requirement is missing, a test was never written, the edge case from the third comment on the ticket got ignored. You ask again. It finds more. Repeat.

testcase ends that loop.

**Every requirement counted.** Each one gets an id, a yes/no question and the line it came from. A requirement can't quietly drop out.

**Tests before trust.** Requirements become test cases, and the test cases become real tests in your repo's own framework — not a checklist in a chat window.

**Done means exit 0.** `goalrun` builds phase by phase and won't say done until the script passes on the whole ledger. Not "done pending X". Not "I checked by hand".

## From ticket to shipped

The core pipeline, one handoff per stage. Use any stage alone, or chain them and hand off the whole job:

| Step | Skill | You get |
| ---- | ----- | ------- |
| 1. Require | `docs-review` | Atomic `REQ-` ids, each a yes/no, each citing its source line |
| 2. Prove | `testcase` | `TC-` ids traced to a `REQ-`, implemented as tests in the repo's own framework |
| 3. Build | `goalrun` | The implementation, phase by phase, until the ledger of checks exits 0 |

Four diagrams of the pipeline, and of how `goalrun` decides a row and proves a check: [How these skills work](docs/how-it-works.md).

## Get started

1. Install the plugin (Claude Code shown; [other hosts below](#install)):
   ```bash
   claude plugin marketplace add xtieume/testcase
   claude plugin install testcase@testcase-marketplace
   ```
2. Point it at a spec: *"write test cases for spec.md"*.
3. Hand off the build: *"/goalrun build the export feature and don't stop until it's done"*.

> [!TIP]
> **On Claude Code, start with `/goal`.** `/goal` sets a condition that is checked after every turn, and Claude keeps working until it holds — so the run doesn't stop halfway to ask whether to continue:
> ```
> /goal /goalrun build the export feature — done when goalrun.py exits 0 on the whole ledger
> ```

> [!TIP]
> **Already think it's finished?** Ask *"is this actually done?"* — `goalrun` audits the work against its ledger and tells you what's still red.

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

### Build

| Skill | Does | Trigger |
| ----- | ---- | ------- |
| 🎯 [`goalrun`](.agents/skills/goalrun/SKILL.md) | Turns a goal into a ledger of checks, builds each phase through an independent subagent, and will not say done until the script exits 0. Also audits work someone else called finished | "build X and don't stop until it's done", "is this actually done?" |
| ✍️ [`normalize`](.agents/skills/normalize/SKILL.md) | Rewrites a rambling everyday prompt into a compact engineering prompt — same requirements, imperative form, explicit escalation and done criteria | "rewrite this prompt for /goalrun" |

### Verify

| Skill | Does | Trigger |
| ----- | ---- | ------- |
| 🧪 [`testcase`](.agents/skills/testcase/SKILL.md) | Test cases from a requirement or a Figma design, attacks its own output for missed cases, then implements the automatable ones as runnable tests and files what fails | "write test cases for…" |
| 📋 [`docs-review`](.agents/skills/docs-review/SKILL.md) | Audits docs against a spec: required vs actually written, with a citation per verdict | "review the docs against spec.md" |

### Capture

| Skill | Does | Trigger |
| ----- | ---- | ------- |
| 📥 [`playwright-cdp`](.agents/skills/playwright-cdp/SKILL.md) | Notion pages and Slack threads → markdown through a logged-in browser: body, every comment, and the attachments downloaded | "read this Notion page", "pull this Slack thread" |

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

Drop a folder into `.agents/skills/<name>/` with a `SKILL.md` (frontmatter `name` + `description`), plus optional `references/` and `scripts/`. No manifest edit: both `plugin.json` files point at the directory, not a list. Add a row to the table above. Versions are not edited by hand: merging to `main` bumps all four manifests, tags the commit and publishes a release — `feat:` gives a minor bump, `!` or `BREAKING CHANGE` a major one, anything else a patch.

## Layout

```
.agents/skills/<name>/     SKILL.md + references/ + scripts/
.claude-plugin/            Claude Code manifests
.zcode-plugin/             ZCode manifests
```

## License

MIT
