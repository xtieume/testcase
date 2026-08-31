# testcase

Three Claude Code skills — `testcase` generates manual test cases, `docs-review` audits documentation against a spec, `playwright-notion` pulls Notion pages down to markdown when the API and the Export button are both unavailable. The two QA skills end with a mandatory review pass run in an independent subagent.

## testcase

Generates comprehensive manual test cases and performs a mandatory missing-test-case review.

It systematically analyzes: positive, negative, boundary, validation, state, permission, error, data, UI, integration, and regression scenarios — then runs a second adversarial pass **in an independent subagent** to catch missed cases before returning the result. The pass runs two reviewers per round with different lenses (trace the requirement / attack the feature) and repeats until a round adds nothing, rather than accepting one round as proof.

Extras:

- **Japanese i18n coverage** — 全角/半角, surrogate pairs, Unicode normalization, byte-vs-character length limits, export/search round-trips
- **Review mode** — audit an existing test case list against the requirement, not against itself
- **Enforced risk coverage** — the lint *fails* when the table is happy-path heavy (over 40% `Positive`) or when a requirement is covered by success-path cases only. Accepting either needs a `<!-- coverage-ok: R7 — reason -->` comment in the file; no reason, or a stale one, is itself a lint error
- **Two-way traceability** — `--requirements reqs.txt` reports the requirements *nothing* traces to. That gap is invisible to any review of the table, because the table cannot show what was never written down
- **Stable IDs across re-runs** — `--diff old.md new.md` reports added, changed and newly `[OBSOLETE]` cases, and fails on an ID deleted outright, which is what silently breaks the test tools holding those IDs
- **Automation handoff** — an `Automatable` Y/N column per case, so the decision is made once during design instead of re-litigated when someone builds the suite
- **Lint + CSV export** — a script counts the cases and flags duplicate IDs, missing expected results, invalid priorities, and vague steps

## docs-review

Investigates documentation on one principle: **what the spec requires vs what the documents actually contain**.

- **Gap analysis mode** — decomposes the spec into atomic requirements *before* reading the docs, then maps each one to `Covered` / `Partial` / `Missing` / `Contradict` / `Conflict` / `Stale` / `Undecided` with a mandatory citation and quote
- **Investigation mode** — no spec? the checklist comes from the question instead, and answers are marked `Stated` / `Inferred` / `Conflicting` / `Absent`
- **Review loop** — an independent subagent re-derives the checklist from the spec alone and attacks the report; repeats until a round converges — no new row, no changed verdict, no rejected citation. Rounds are not capped at a fixed number: material findings at round 4 mean round 5, an oscillating verdict is frozen as `Undecided` instead of burning rounds, and a loop still moving at round 5 is reported as unconverged rather than finished. Earlier rounds' notes are stripped before the next round, so each reviewer stays independent
- **Large sets** — over ~15 documents it switches workflow: index the documents first (their vocabulary, not the spec's), shard the audit by spec chapter, sweep for doc-vs-doc conflicts separately, and require a per-document coverage declaration before a review round counts as clean
- **`--fix`** — edits the audited document (the output artifact, never the spec) after the review loop: `Missing` / `Partial` / `Stale` rows the spec states in full, as minimal in-place edits traced to a requirement ID, then re-verifies each edited section. In a deliverable still being drafted, `Contradict` is fixed too. In documentation of a running system it is only proposed — a doc contradicting the spec may be the one describing reality
- **Lint** — a script checks every row for a valid verdict, a citation, unique IDs, a source inventory, and that the loop actually ran

```text
Review the docs in ./docs against spec.md
Review the docs in ./docs against spec.md --fix
```

## playwright-notion

For the common corporate lockout: the workspace won't issue an integration token, the Export button is greyed out by permission, and the only access you have is a browser tab you're already logged into.

The skill attaches to your **running** Brave/Chrome/Edge over the Chrome DevTools Protocol and calls Notion's own endpoints from inside that tab. Read-only — nothing in Notion is created, edited, or deleted.

- **Export first** — a greyed-out Export button is often only a client-side role check, so it enqueues Notion's native markdown export (`enqueueTask`). Where that passes, output is Notion's own markdown: person mentions resolved to real names, page mentions to titles plus URLs, embedded images downloaded alongside
- **Converter fallback** — when a workspace really did disable export server-side, it converts `loadPageChunk` / `queryCollection` block JSON itself: properties, nested lists, to-do checkboxes, callouts, code blocks with language tags, and tables with correct columns including embedded database views
- **Two dead ends it refuses to walk into** — copying the browser profile cannot carry the session (Chromium 127+ App-Bound Encryption binds the cookie key to the original profile, so a copy lands on the login screen), and DOM scraping emits every table ~3x with cells doubled while losing all page properties
- **Batch-safe** — recycles the browser tab every few pages because Notion leaks memory and crashes the renderer, retries crashed pages, and logs per-page results to grep for verification

```text
Tôi không có Notion API token, Export bị disable. Tải các trang này về markdown: <links>
```

## Install

### Option A — Plugin marketplace (recommended)

```bash
# one-time: register this repo as a marketplace
claude plugin marketplace add xtieume/testcase

# then install
claude plugin install testcase@testcase-marketplace
```

Or via the interactive UI:

```text
/plugin marketplace add xtieume/testcase
/plugin install testcase@testcase-marketplace
```

### Option B — Manual (copy the skill)

Copy the whole skill folder into your local skills folder:

```bash
cp -R skills/testcase ~/.claude/skills/testcase
cp -R skills/docs-review ~/.claude/skills/docs-review
cp -R skills/playwright-notion ~/.claude/skills/playwright-notion
```

## Usage

Ask for test cases in natural language:

```text
Write test cases for: user can change 工種コード via a dropdown, value reflected immediately in L1.
```

The skill triggers automatically on any request to write / create / generate / review test cases, or invoke it directly with `/testcase`.

Test cases are written to a file, so they can be linted and exported:

```bash
python3 skills/testcase/scripts/summarize.py testcases.md
python3 skills/testcase/scripts/summarize.py testcases.md --requirements reqs.txt
python3 skills/testcase/scripts/summarize.py testcases.md --csv out.csv
python3 skills/testcase/scripts/summarize.py --diff previous.md testcases.md
```

The CSV is UTF-8 with BOM, so Excel opens Japanese text correctly.

For `playwright-notion`, install the script deps once, then it drives the browser for you:

```bash
cd skills/playwright-notion/scripts && npm install
```

Run manually if you prefer:

```bash
# start (or verify) the browser with CDP — closes a running instance first
skills/playwright-notion/scripts/start-browser.sh brave 9222

# one URL per line, then export (preferred) or download (fallback)
node skills/playwright-notion/scripts/export.mjs   urls.txt ./notion-docs 9222
node skills/playwright-notion/scripts/download.mjs urls.txt ./notion-docs 9222

grep -c OK /tmp/notion_export.log
```

Brave commonly accepts CDP on its default profile dir where Chrome refuses.

## Layout

```text
skills/testcase/
  SKILL.md                        — workflow, output format, rules
  references/coverage-map.md      — the coverage dimensions + worked example
  references/i18n-jp.md           — Japanese charset coverage
  references/review-mode.md       — auditing an existing test case list
  scripts/summarize.py            — count, lint, requirement coverage, diff, export CSV (stdlib only)
skills/docs-review/
  SKILL.md                        — mode selection, gap workflow, review loop, rules
  references/dimensions.md        — requirement dimensions + how to make a row atomic
  references/i18n-jp.md           — Japanese term-variant + 全角/半角 checks
  references/large-sets.md        — index / shard / conflict-sweep workflow for big doc sets
  references/fix-mode.md          — what --fix may edit, and what it may only propose
  references/investigation-mode.md — auditing without a spec
  scripts/check_report.py         — lint verdicts, citations, duplicate IDs (stdlib only)
skills/playwright-notion/
  SKILL.md                        — workflow, the two dead ends, verification
  scripts/start-browser.sh        — launch Brave/Chrome/Edge with CDP on the real profile
  scripts/export.mjs              — Notion's native markdown export via enqueueTask (preferred)
  scripts/download.mjs            — block JSON → markdown converter (fallback)
  scripts/package.json            — playwright dependency
.claude-plugin/plugin.json        — Claude Code plugin manifest
.claude-plugin/marketplace.json   — plugin marketplace manifest
```

`SKILL.md` stays small on purpose — the references load only when the workflow needs them, so a session that never touches Japanese text never pays for `i18n-jp.md`. `docs-review/SKILL.md` works the same way.

## License

MIT
