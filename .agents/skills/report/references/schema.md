# Schema

Every path is relative to the directory holding `report.json`.
Build: `python3 scripts/build_report.py <dir>`.

```
<dir>/report.json            config + meta
<dir>/data/reqs-*.jsonl      requirements, merged in filename order
<dir>/data/overrides.jsonl   post-verification corrections (optional)
<dir>/data/e2e-results.jsonl E2E outcomes (optional)
<dir>/evidence/…             see references/evidence.md
<dir>/REPORT.html            generated
```

Rendering is plain Python — deterministic, no network, no model. The judgement lives in the data.

## reqs-*.jsonl

One object per line. Required: `id` (unique across all files) and `status` (must be declared in
`report.json.status`). Every other key is free-form: a key shows up only if a column declares it.

```json
{"id":"AUTH-001","area":"Login","req":"5 wrong passwords -> lock for 15 min","src":"spec.md:88-94","acc":"T-12","impl":"src/auth/lockout.ts:30-61","unit":"src/auth/__tests__/lockout.test.ts","e2e":"tests-e2e/auth-lockout.spec.ts","status":"PASS","qa":"—","note":""}
```

Name ids `<GROUP>-<number>`: the default `group_by: "id_prefix"` cuts at the last `-` to group rows.
To group by a field instead, set `"group_by": "area"`.

### Importing an existing flat list

If the project already has a flat `reqs.txt` in the
`ID: [STATUS] requirement (src: file:line)` shape (what `emit.goalrun_reqs` writes, and what the
`goalrun` skill keeps), import it instead of retyping — no model involved:

```bash
python3 scripts/build_report.py <dir> --from-reqs <path>/reqs.txt
```

It writes `data/reqs-00-imported.jsonl` and builds. It refuses to overwrite an existing import,
so re-running never silently discards hand edits — delete the file or import into a fresh directory.

## overrides.jsonl

`{"id": "...", <fields to overwrite>}`, merged onto the requirement with that id. Unknown id fails
the build. This is where a human reviewer records corrections — **do not edit `reqs-*.jsonl`** for
them, or the next run loses the boundary between what was derived and what a person concluded.

## e2e-results.jsonl

`{"id":"AUTH-001","result":"PASS|FAIL|BLOCKED|SKIP","date":"2026-01-20","evidence":"run #312"}`
Feeds any column with `"render": "e2e"`. Unknown id fails the build.

## Column widths

The main table uses `table-layout: fixed`, so every cell wraps instead of forcing the table
sideways — file paths break mid-token rather than stretching one column to 800px. Give the columns
that carry long text a larger `"width"` (any CSS length or percentage); columns without one share
what is left.

Widths are a density budget: thirteen columns on a 1240px table leaves ~95px each, which is tight
for prose. If a column is not read in practice, drop it from `columns` — the JSONL keeps the field
either way, and fewer columns is the only real fix for a cramped table.

## report.json

| Key | Required | Meaning |
| --- | --- | --- |
| `title` | ✔ | `<h1>` and `<title>` |
| `header` | | one HTML paragraph: scope, spec sources, method |
| `columns` | ✔ | column order. `{"key","label","width"?,"nowrap"?,"render"?}` — `render` is `status`, `evidence` or `e2e`; omitted means plain text |
| `status` | ✔ | `{"KEY": {"icon","label","color"}}`. Declaration order drives the summary columns and the progress-bar segments |
| `group_by` | | `"id_prefix"` (default) or a field name |
| `findings` | | list of HTML strings for the "Key findings" section |
| `baseline` | | `{"label","total","status":{},"e2e":{}}` → the "Before → Now" table |
| `table_height` | | height of the requirement table's scroll box (default `72vh`). The table scrolls inside it so 700 rows do not turn the page into an endless scroll |
| `labels` | | override any UI string, e.g. `{"progress":"Tiến độ","evidence":"Bằng chứng"}`. Report language is config, not code |
| `rules.done` | | which statuses count as done for the headline percentage (default: first status) |
| `rules.demote_pass_without_test` | | `{"from","to","when_empty":[field,…]}` — demote when the row tracks tests at all (at least one listed field is present) and none of them holds a value. An empty field means "looked, found none" and counts toward the demotion; a row carrying none of the fields says nothing about tests, so an imported flat list keeps its statuses |
| `rules.e2e_fail_status` | | an E2E FAIL forces this status and records why in `note` |
| `rules.attention` | | statuses listed in "Needs action / confirmation" |
| `rules.attention_columns` | | extra columns for that section (default `["qa","note"]`) |
| `emit.goalrun_reqs` | | also write a flat `reqs.txt` for the `goalrun` skill |

## Filtering

The requirement table carries a free-text box plus one control per column, pinned under the header
while the box scrolls. A column gets a dropdown when its values are categorical — at most 25 distinct
*and* fewer distinct values than rows, so an id column (one value per row) stays a text box. The
evidence column takes no filter. All active filters combine with AND, and the counter beside the
free-text box reports how many rows survived.

## Responsive behaviour

One stylesheet, no breakpoints to configure. Wide screens put the scope text beside the progress
bars and the summary cards in one row; narrow screens stack them. Every table that is wider than the
screen scrolls inside its own card or box rather than widening the page, so there is no horizontal
page scroll at any width. Below 700px the requirement box is capped at `80vh` whatever
`table_height` says, and on touch screens the filter controls grow to 36px with 16px text (smaller
text makes iOS zoom on focus).

## The build fails on

duplicate Req ID · a status not declared in config · a status named by a rule (`done`, `attention`,
`e2e_fail_status`, `demote_pass_without_test.from`/`.to`) that `status` does not declare · an
override, E2E result or evidence row pointing at an unknown id · malformed JSONL.

Loudly, never silently: a wrong report is worse than no report.
