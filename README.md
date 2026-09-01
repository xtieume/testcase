# testcase

Three Claude Code skills. The two QA skills end with a mandatory review pass in an independent subagent.

[Tiếng Việt](README.vi.md)

| Skill | Does | Trigger |
| ----- | ---- | ------- |
| 🧪 `testcase` | Manual test cases from a requirement, then attacks its own output for missed cases | "write test cases for…" |
| 📋 `docs-review` | Audits docs against a spec: required vs actually written | "review the docs against spec.md" |
| 📥 `playwright-notion` | Notion → markdown through a logged-in browser, when API token and Export are both unavailable | "download these Notion pages" |

## 🧪 testcase

Coverage map first (positive / negative / boundary / validation / state / permission / error / data / UI / integration / regression, plus Japanese 全角/半角 when relevant) → cases → independent second pass: two reviewer subagents per round (trace the requirement / attack the feature), repeated until a round adds nothing.

The lint script enforces the rules:

| Check | Fails when |
| ----- | ---------- |
| Happy-path ratio | >40% `Positive` live cases |
| Risk cover | A requirement has success-path cases only |
| Suppression | `<!-- coverage-ok: R7 — reason -->` missing a reason, or stale |
| `--requirements reqs.txt` | A requirement has **no** case at all |
| `--diff old.md new.md` | An ID was deleted instead of marked `[OBSOLETE]` |
| Row lint | Duplicate ID, empty expected result, invalid priority, vague steps |

Plus: `Automatable` Y/N per case, CSV export (UTF-8 BOM, Excel-safe for Japanese), review mode for auditing an existing case list against the requirement.

## 📋 docs-review

Decomposes the spec into atomic requirements *before* reading the docs; each maps to `Covered` / `Partial` / `Missing` / `Contradict` / `Conflict` / `Stale` / `Undecided` with a mandatory citation. No spec → investigation mode derives the checklist from your question.

An independent subagent re-derives the checklist and attacks the report until a round converges (still moving at round 5 → reported unconverged). Over ~15 docs it switches to index/shard. `--fix` applies `Missing`/`Partial`/`Stale` rows to the audited document — never the spec. A lint script checks verdicts, citations, and that the loop ran.

## 📥 playwright-notion

Attaches to your **running** Brave/Chrome/Edge over CDP, calls Notion's endpoints from inside the logged-in tab. Read-only. Native markdown export first (greyed-out Export is often a client-side check only), block-JSON conversion as fallback. Batch-safe: recycles tabs, retries crashes, logs per page. Refuses two dead ends: profile copying (Chromium 127+ App-Bound Encryption drops the session) and DOM scraping (tripled tables, lost properties).

## Install & use

```bash
claude plugin marketplace add xtieume/testcase
claude plugin install testcase@testcase-marketplace
```

Or copy manually: `cp -R .agents/skills/<name> ~/.claude/skills/<name>`. Skills trigger on natural language or `/testcase`, `/docs-review`, `/playwright-notion`.

**Cursor & Antigravity** — skills live in the standard `.agents/skills/` directory, which both editors read natively. Clone this repo into your project (or symlink it):

```bash
git clone https://github.com/xtieume/testcase.git
ln -s $(pwd)/testcase/.agents/skills .agents/skills   # project-level
# or global: cp -R testcase/.agents/skills/* ~/.gemini/antigravity/skills/
```

```bash
python3 .agents/skills/testcase/scripts/summarize.py testcases.md [--requirements reqs.txt] [--csv out.csv]
python3 .agents/skills/testcase/scripts/summarize.py --diff previous.md testcases.md
```

`playwright-notion` needs `cd .agents/skills/playwright-notion/scripts && npm install` once; manual commands in its `SKILL.md`.

## Layout

Each skill: `SKILL.md` (small on purpose) + `references/` loaded only when needed + `scripts/` (stdlib Python / Node). `.claude-plugin/` holds the manifests.

## License

MIT
