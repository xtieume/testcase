# testcase

Three Claude Code skills. The two QA skills end with a mandatory review pass in an independent subagent.

| Skill | Does |
| ----- | ---- |
| `testcase` | Generates manual test cases from a requirement, then attacks its own output for missed cases |
| `docs-review` | Audits documentation against a spec: what it requires vs what the docs actually say |
| `playwright-notion` | Pulls Notion pages to markdown through a logged-in browser when the API token and Export button are both unavailable |

## testcase

Builds a coverage map (positive, negative, boundary, validation, state, permission, error, data, UI, integration, regression — plus Japanese 全角/半角 and Unicode when relevant), writes the cases, then runs an independent second pass: two reviewer subagents per round with different lenses (trace the requirement / attack the feature), repeated until a round adds nothing.

The lint script enforces what the rules only used to say:

- **fails** on happy-path-heavy tables (>40% `Positive`) and on requirements covered by success-path cases only — accepting a gap requires `<!-- coverage-ok: R7 — reason -->`, and a missing or stale reason is itself an error
- `--requirements reqs.txt` reports requirements *nothing* traces to — the gap no review of the table can see
- `--diff old.md new.md` fails on a deleted ID (mark cases `[OBSOLETE]` instead; downstream tools hold those IDs)
- flags duplicate IDs, empty expected results, invalid priorities, vague steps; exports CSV (UTF-8 BOM, Excel-safe for Japanese)
- `Automatable` Y/N column per case, so the manual/automated split is decided once, during design

Review mode audits an existing case list against the requirement, not against itself.

## docs-review

Decomposes the spec into atomic requirements *before* reading the docs, then maps each to `Covered` / `Partial` / `Missing` / `Contradict` / `Conflict` / `Stale` / `Undecided` with a mandatory citation. No spec? Investigation mode derives the checklist from your question instead.

An independent subagent re-derives the checklist from the spec alone and attacks the report, repeating until a round converges; a loop still moving at round 5 is reported as unconverged, not finished. Over ~15 documents it switches to an index/shard workflow. `--fix` applies `Missing`/`Partial`/`Stale` rows to the audited document as minimal traced edits — never to the spec. A lint script checks verdicts, citations, and that the loop actually ran.

```text
Review the docs in ./docs against spec.md
Review the docs in ./docs against spec.md --fix
```

## playwright-notion

Attaches to your **running** Brave/Chrome/Edge over CDP and calls Notion's own endpoints from inside the logged-in tab. Read-only. Tries Notion's native markdown export first (a greyed-out Export button is often just a client-side role check); falls back to converting block JSON itself — nested lists, callouts, code blocks, tables, embedded database views. Batch-safe: recycles the tab (Notion leaks memory), retries crashed pages, logs per-page results.

It deliberately avoids two dead ends: copying the browser profile (Chromium 127+ App-Bound Encryption drops the session) and DOM scraping (tables tripled, page properties lost).

```text
Tôi không có Notion API token, Export bị disable. Tải các trang này về markdown: <links>
```

## Install

```bash
claude plugin marketplace add xtieume/testcase
claude plugin install testcase@testcase-marketplace
```

Or copy manually: `cp -R skills/<name> ~/.claude/skills/<name>`.

## Usage

Skills trigger on natural language ("write test cases for…", "review the docs against…") or directly via `/testcase`, `/docs-review`, `/playwright-notion`.

```bash
python3 skills/testcase/scripts/summarize.py testcases.md                     # count + lint
python3 skills/testcase/scripts/summarize.py testcases.md --requirements reqs.txt
python3 skills/testcase/scripts/summarize.py testcases.md --csv out.csv
python3 skills/testcase/scripts/summarize.py --diff previous.md testcases.md
```

For `playwright-notion`: `cd skills/playwright-notion/scripts && npm install` once, then the skill drives the browser itself (or run `start-browser.sh` / `export.mjs` / `download.mjs` by hand — see `skills/playwright-notion/SKILL.md`).

## Layout

Each skill is `SKILL.md` (small on purpose) + `references/` loaded only when the workflow needs them + `scripts/` (stdlib-only Python, or Node for playwright-notion). `.claude-plugin/` holds the plugin and marketplace manifests.

## License

MIT
