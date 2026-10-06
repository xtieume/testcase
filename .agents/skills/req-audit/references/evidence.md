# Evidence pass

Only run this after the user answers **yes**. The report already exists by then — this pass only
*adds* images. It never touches `data/`, and rebuilding is safe at any point.

## File contract

Agents write into `evidence/` only, each agent under its own `<batch>` so no two agents write the
same file:

```
evidence/<image>.png
evidence/<batch>.manifest.jsonl   {"file":"EV-A01-login-locked.png","caption":"After 5 failures: 15-minute lock banner","check":"PASS"}
evidence/<batch>.reqs.jsonl       {"id":"AUTH-001","verdict":"SHOWN","evidence":["EV-A01-login-locked.png"],"note":""}
evidence/review-<batch>.jsonl     {"id":"AUTH-001","finding":"caption-mismatch","detail":"screenshot shows the signup screen"}
```

- `check`: `PASS` when the image really shows what the caption claims; anything else renders as ✖.
- `verdict`: `SHOWN` (proves the requirement) · `SHOWN-PARTIAL` (covers part of it) ·
  `NOT-SHOWN` (captured, but does not prove it).
- Image names: `EV-<batch>-<short-description>.png` — readable without opening the file.
- An id absent from `data/` fails the build. Only capture for requirements that exist.

## Splitting the work

Split by requirement group (`group_by`), one agent per group, run in parallel via
`superpowers:dispatching-parallel-agents`. Each agent receives: its requirements (id, requirement
text, acceptance criteria), the `evidence/` path, its `<batch>` name, and how to reach the app.

The capture tool is **not fixed**: `playwright-cdp` is the best option when the app is a web app and
the user's machine can run it, because it can reproduce the exact state. Otherwise manual
screenshots, CI artifacts, or anything else works. The contract is the three files, not the tool.

## Independent review — do not skip

An agent that captures its own screenshots and then marks its own `check: PASS` is the single most
likely source of fake evidence: wrong screen, right screen in the wrong state, or a stale image taken
before the fix. Once capture finishes, **a different agent** opens every image, compares it against
`req` and `caption`, and records every mismatch in `review-<batch>.jsonl`. The report shows those as
red warnings inside the evidence cell and counts them on the progress bar.

The reviewing agent must not be the agent that captured that group.

## Finish

Re-run `python3 scripts/build_report.py <dir>` and the Evidence bar moves. Running it mid-flight is
fine — whatever has landed shows up.
