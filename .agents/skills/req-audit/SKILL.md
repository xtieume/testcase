---
name: req-audit
description: Use when the user wants a requirement audit page from a goalrun run — "build REQ-AUDIT", "requirement audit report", "which requirements are proven, which await sign-off", "tạo report audit từ goalrun", 「要件監査レポート」 — a REQ-AUDIT.html with a status per requirement, its ledger rows and their verify verdicts, screenshot/video evidence with hover preview, and the items waiting on a human decision. Requires the goalrun skill installed alongside.
allowed-tools: Read, Write, Edit, Grep, Glob, Bash
---

# REQ-AUDIT from a goalrun run

`scripts/req_audit.py` (stdlib + the sibling `../goalrun/scripts`) renders what goalrun already
recorded. It never runs a check: statuses come from the run's newest recorded `--verify`
(`<run_dir>/evidence/<uuid>.json`), and the page says when that result no longer matches the
workspace.

## Steps

1. Select the run explicitly (see `../goalrun/references/run-context.md`); never guess the newest.
   `python3 "$GOALRUN" inspect "$RUN"` gives `paths.run_dir`.
2. Whole-ledger proof first, if the last one is missing or stale:
   `python3 "$GOALRUN" --run "$RUN" --token "$TOKEN" --verify`. A failing verify is still
   recorded and still reportable — the page shows which rows broke.
3. Build, from the workspace root:
   ```sh
   python3 <skills>/req-audit/scripts/req_audit.py "$RUN" [--audit-dir DIR] [--fresh YYYY-MM-DD] [--title T] [--out FILE]
   ```
4. Read the JSON it prints. `verify` null → no verify recorded; `verify.stale_because` non-empty
   → source, run inputs or spec changed since: rerun step 2 before reporting; `verify.subset` set
   → only those rows were proven. `gaps` lists each requirement missing a verified break, an
   automated test or evidence.
5. Report `status_counts` and the gaps, and give the page path. Never call the work done while a
   status other than PASS, SIGNED or OBSOLETE remains.

## Audit folder

Default `<run_dir>/audit/`; `--audit-dir` points elsewhere (keep the page next to its `evidence/`,
links are relative). Everything in it is optional.

| Path | Content |
| --- | --- |
| `data/reqs.jsonl` | one requirement per line; absent → the run's `goalrun/reqs.txt` (`ID: text`, or text from the ledger row) |
| `data/evidence*.jsonl` | one evidence file per line |
| `data/adequacy.json` | `{"REQ-1": {"yes": bool, "blockers": [..]}}` — a reviewer's judgement whether the evidence suffices |
| `evidence/` | the screenshots / videos (`.png .jpg .jpeg .webp .gif .webm .mp4`) |

`reqs.jsonl` fields: `id` (required), `req`, `area` (groups tables), `src`, `status`
(`OBSOLETE` / `CONFIRM`), `obsolete_reason`, `human_check`, `dev_decision`; a decision awaiting a
person: `proposal`, `human_owner`, `decided_by` (empty → still a proposal), `decision_source`,
`proposal_evidence` (path under `evidence/`).

Evidence line: `{"file": "<path under evidence/>", "reqs": ["REQ-1"], "caption": "...",
"captured": "YYYY-MM-DD", "spec_only": bool, "stale": bool}`. `spec_only` or `stale` shows the file
but does not count it as proof.

Any text field `caption`, `proposal`, `dev_decision` may carry translations as `<field>_<lang>`
(`caption_vi`, `proposal_ja`); each is shown with its language code.

A ledger row belongs to a requirement when its id or `what` names the id as a whole token —
goalrun's own coverage rule, so `REQ-1` does not claim `REQ-10`'s row.

## Statuses

From goalrun's recorded row outcome, first match wins:

| Status | When |
| --- | --- |
| OBSOLETE / CONFIRM | `status` in reqs.jsonl |
| DEVIATION | a row FAIL, HOLLOW, BREAK FAILED, STUCK or BLAST |
| PASS | every row VERIFIED, at least one automated |
| SIGNED | every row VERIFIED, all `MANUAL:` (signed) |
| AWAITING_SIGN | a `MANUAL:` row still WAIT |
| UNPROVEN | rows exist but not all proven (no break, outside a subset verify, not run) |
| NO_TEST | no row, but evidence |
| MISSING | nothing |
