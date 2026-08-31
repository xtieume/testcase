#!/usr/bin/env python3
"""Count and lint a markdown test case table, and optionally export it as CSV.

Counting rows by hand is the step a model gets wrong, so it is done here instead.
So is deciding whether the table is actually risk-covering or just happy-path heavy.

    python3 summarize.py testcases.md
    python3 summarize.py testcases.md --requirements reqs.txt
    python3 summarize.py testcases.md --csv .testcases/testcase/out.csv
    python3 summarize.py --diff .testcases/testcase/previous.md testcases.md
    python3 summarize.py --selfcheck
"""

import argparse
import csv
import os
import re
import sys
import tempfile
from collections import Counter

CATEGORIES = [
    "Positive", "Negative", "Boundary", "Validation", "State", "Permission",
    "Error", "Data", "UI", "Integration", "Regression",
]
PRIORITIES = ["P0", "P1", "P2"]
AUTOMATABLE = ["Y", "N"]

# Categories that verify something other than the feature working. A requirement
# covered only by cases outside this set was tested for success alone.
RISK_CATEGORIES = {"Negative", "Boundary", "Validation", "Error", "Permission"}

# Share of Positive cases above which the table is treated as happy-path heavy.
POSITIVE_SHARE_LIMIT = 0.40
# Under this many cases the ratio says nothing, so it is not checked.
RATIO_MIN_ROWS = 10

OBSOLETE = "[OBSOLETE]"

# Phrases that mean the step has no concrete test data.
VAGUE = [
    "valid value", "invalid value", "some value", "any value", "appropriate value",
    "適切な値", "正しい値", "有効な値", "任意の値",
]

# An accepted coverage gap, with the reason on the record:
#   <!-- coverage-ok: R7 — label is display-only, there is no invalid input -->
SUPPRESS_RE = re.compile(r"<!--\s*coverage-ok:(?P<body>.*?)-->", re.DOTALL)
SUPPRESS_SPLIT = re.compile(r"\s+(?:—|–|-{1,2})\s+")


def _cells(line):
    # ponytail: naive split on "|". A literal pipe inside a cell must be written
    # as &#124;. Full markdown escaping would need a real parser.
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _blocks(text):
    """Yield each run of consecutive lines starting with '|'."""
    block = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("|"):
            block.append(line)
        elif block:
            yield block
            block = []
    if block:
        yield block


def _is_separator(line):
    return set(line.replace("|", "").replace(" ", "")) <= set("-:")


def parse_table(text):
    """Return (headers, rows) for the test case table, or (None, []) if absent.

    Picks the table whose header has a Priority column; falls back to the biggest
    table so a mis-typed header still gets counted rather than silently skipped.
    """
    best = None
    for block in _blocks(text):
        if len(block) < 3 or not _is_separator(block[1]):
            continue
        headers = _cells(block[0])
        rows = [_cells(l) for l in block[2:]]
        if "priority" in [h.lower() for h in headers]:
            return headers, rows
        if best is None or len(rows) > len(best[1]):
            best = (headers, rows)
    return best if best else (None, [])


def col(headers, *names):
    low = [h.lower() for h in headers]
    for n in names:
        if n in low:
            return low.index(n)
    return None


def get(row, idx):
    return row[idx] if idx is not None and idx < len(row) else ""


def is_obsolete(row):
    return OBSOLETE in " ".join(row)


def live_rows(rows):
    """Rows still in force. Obsolete cases stay in the file but are not counted."""
    return [r for r in rows if not is_obsolete(r)]


def suppressions(text):
    """Return ({key: reason}, problems) for the coverage-ok comments in the file."""
    found, problems = {}, []
    for m in SUPPRESS_RE.finditer(text):
        parts = SUPPRESS_SPLIT.split(m.group("body").strip(), maxsplit=1)
        key = parts[0].strip()
        reason = parts[1].strip() if len(parts) > 1 else ""
        if not key:
            problems.append("coverage-ok comment with no key")
        elif not reason:
            problems.append(f"coverage-ok: {key} — no reason given, state why the gap is accepted")
        else:
            found[key] = reason
    return found, problems


def lint(headers, rows):
    """Return a list of human-readable problems."""
    problems = []
    i_id = col(headers, "id")
    i_cat = col(headers, "category")
    i_pri = col(headers, "priority")
    i_exp = col(headers, "expected result", "expected")
    i_steps = col(headers, "steps")
    i_req = col(headers, "req", "requirement")
    i_auto = col(headers, "automatable")

    for name, idx in [("ID", i_id), ("Category", i_cat), ("Priority", i_pri),
                      ("Expected Result", i_exp), ("Steps", i_steps), ("Req", i_req)]:
        if idx is None:
            problems.append(f"missing column: {name}")

    seen = Counter(get(r, i_id) for r in rows if get(r, i_id))
    for tc_id, n in seen.items():
        if n > 1:
            problems.append(f"duplicate ID: {tc_id} appears {n} times")

    for n, row in enumerate(rows, 1):
        tc_id = get(row, i_id) or f"row {n}"
        if not get(row, i_id):
            problems.append(f"row {n}: empty ID")
        if is_obsolete(row):
            continue
        if not get(row, i_exp):
            problems.append(f"{tc_id}: empty Expected Result")
        if not get(row, i_req):
            problems.append(f"{tc_id}: no Req traceability (use REG for regression)")
        pri = get(row, i_pri)
        if pri and pri not in PRIORITIES:
            problems.append(f"{tc_id}: invalid Priority {pri!r} (use P0/P1/P2)")
        cat = get(row, i_cat)
        if cat and cat not in CATEGORIES:
            problems.append(f"{tc_id}: unknown Category {cat!r}")
        auto = get(row, i_auto)
        if i_auto is not None and auto and auto not in AUTOMATABLE:
            problems.append(f"{tc_id}: invalid Automatable {auto!r} (use Y/N)")
        steps = get(row, i_steps).lower()
        for phrase in VAGUE:
            if phrase in steps:
                problems.append(f"{tc_id}: vague step — {phrase!r}, use concrete data")
                break

    return problems


def coverage(headers, rows, suppressed):
    """Return (problems, notes) for happy-path bias and per-requirement risk cover.

    Rule 1 of the skill — never generate only happy paths — is checked here rather
    than left to the model's own judgement about its own output.
    """
    problems, notes = [], []
    i_cat = col(headers, "category")
    i_req = col(headers, "req", "requirement")
    live = live_rows(rows)

    if len(live) >= RATIO_MIN_ROWS:
        pos = sum(1 for r in live if get(r, i_cat) == "Positive")
        share = pos / len(live)
        over = share > POSITIVE_SHARE_LIMIT
        if over and "positive-ratio" not in suppressed:
            problems.append(
                f"happy-path heavy: {pos}/{len(live)} live cases are Positive "
                f"({share:.0%} > {POSITIVE_SHARE_LIMIT:.0%}) — add risk cases, or accept it with "
                "<!-- coverage-ok: positive-ratio — reason -->")
        elif over:
            notes.append(f"Positive share {share:.0%} accepted: {suppressed['positive-ratio']}")
        else:
            notes.append(f"Positive share: {share:.0%} of {len(live)} live cases")

    by_req = {}
    for row in live:
        req = get(row, i_req)
        if req and req.upper() != "REG":
            by_req.setdefault(req, set()).add(get(row, i_cat))

    for req, cats in by_req.items():
        if cats & RISK_CATEGORIES:
            continue
        if req in suppressed:
            notes.append(f"{req} success-path only, accepted: {suppressed[req]}")
            continue
        have = "/".join(sorted(c for c in cats if c)) or "uncategorized"
        problems.append(
            f"{req}: success-path cases only ({have}) — add a "
            f"Negative/Boundary/Validation/Error/Permission case, or accept it with "
            f"<!-- coverage-ok: {req} — reason -->")

    for key in suppressed:
        if key == "positive-ratio":
            continue
        if key not in by_req:
            problems.append(f"stale coverage-ok: {key} has no live case, remove the comment")
        elif by_req[key] & RISK_CATEGORIES:
            problems.append(f"stale coverage-ok: {key} now has risk cases, remove the comment")

    return problems, notes


def read_requirements(path):
    """Requirement IDs, one per line. '#' comments and 'ID: description' both fine."""
    ids = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                ids.append(re.split(r"[:\s]", line, maxsplit=1)[0])
    return ids


def requirement_coverage(headers, rows, req_ids):
    """Return (problems, report) mapping the requirement list onto the table.

    The table only proves case -> requirement. This is the other direction: a
    requirement nothing traces to is the gap a second pass over the table cannot see.
    """
    i_req = col(headers, "req", "requirement")
    counts = Counter(get(r, i_req) for r in live_rows(rows))

    problems, out = [], ["## Requirement Coverage", ""]
    for rid in req_ids:
        n = counts.get(rid, 0)
        out.append(f"{rid}: {n} case(s)" if n else f"{rid}: 0  <- no test case traces here")
        if not n:
            problems.append(f"requirement {rid}: no test case traces to it")

    for req in sorted(r for r in counts if r and r.upper() != "REG" and r not in req_ids):
        problems.append(f"Req {req!r} is not in the requirement list — typo, or the list is stale")

    return problems, "\n".join(out)


def diff_tables(old_text, new_text):
    """Return (report, problems) comparing two test case tables by ID."""
    o_head, o_rows = parse_table(old_text)
    n_head, n_rows = parse_table(new_text)
    if not o_head or not n_head:
        return "", ["--diff needs a markdown test case table in both files"]

    def index(headers, rows):
        i = col(headers, "id")
        return {get(r, i): r for r in rows if get(r, i)}

    old, new = index(o_head, o_rows), index(n_head, n_rows)
    added = [k for k in new if k not in old]
    removed = [k for k in old if k not in new]

    obsoleted, changed = [], []
    for tc_id in (k for k in new if k in old):
        fields = [h for h in n_head
                  if get(old[tc_id], col(o_head, h.lower())) != get(new[tc_id], col(n_head, h.lower()))]
        if not fields:
            continue
        if is_obsolete(new[tc_id]) and not is_obsolete(old[tc_id]):
            obsoleted.append(tc_id)
        else:
            changed.append((tc_id, fields))

    out = ["## Diff", "",
           f"added: {len(added)}   changed: {len(changed)}   "
           f"marked obsolete: {len(obsoleted)}   deleted: {len(removed)}", ""]
    for tc_id in added:
        out.append(f"+ {tc_id}")
    for tc_id in obsoleted:
        out.append(f"~ {tc_id} [OBSOLETE]")
    for tc_id, fields in changed:
        out.append(f"* {tc_id}: {', '.join(fields)}")
    for tc_id in removed:
        out.append(f"- {tc_id}")

    problems = [f"{tc_id} was deleted — IDs are permanent, mark it {OBSOLETE} instead"
                for tc_id in removed]
    return "\n".join(out), problems


def summary(headers, rows):
    i_cat = col(headers, "category")
    i_pri = col(headers, "priority")
    i_auto = col(headers, "automatable")
    live = live_rows(rows)
    cats = Counter(get(r, i_cat) for r in live)
    pris = Counter(get(r, i_pri) for r in live)

    out = ["## Coverage Summary", "", f"Total test cases: {len(live)}"]
    obsolete = len(rows) - len(live)
    if obsolete:
        out.append(f"Obsolete, not counted: {obsolete}")
    out.append("")
    for p in PRIORITIES:
        out.append(f"{p}: {pris.get(p, 0)}")
    out.append("")
    for c in CATEGORIES:
        n = cats.get(c, 0)
        out.append(f"{c}: {n}" if n else f"{c}: 0  <- none, confirm N/A or add cases")
    extra = set(cats) - set(CATEGORIES) - {""}
    for c in sorted(extra):
        out.append(f"{c} (unrecognized): {cats[c]}")
    if i_auto is not None:
        autos = Counter(get(r, i_auto) for r in live)
        out += ["", f"Automatable Y: {autos.get('Y', 0)}   N: {autos.get('N', 0)}"]
    return "\n".join(out)


def to_csv(headers, rows, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


SAMPLE = """
Intro text.

| ID | Req | Category | Test Case | Preconditions | Steps | Expected Result | Priority | Automatable |
| -- | --- | -------- | --------- | ------------- | ----- | --------------- | -------- | ----------- |
| TC-A-001 | R1 | Positive | happy | none | enter `100` | saved | P0 | Y |
| TC-A-001 | R1 | Boundary | dup id | none | enter `0` | saved | P1 | N |
| TC-A-003 | | Nonsense | no req | none | enter a valid value | | P5 | maybe |
| TC-A-004 | R2 | Positive | gone | none | enter `1` | saved | P2 | Y |
"""

# 11 live cases, 9 of them Positive. R3 is covered by Positive only, R4 by Boundary.
RATIO_SAMPLE = """
| ID | Req | Category | Steps | Expected Result | Priority |
| -- | --- | -------- | ----- | --------------- | -------- |
""" + "".join(
    f"| TC-B-{n:03d} | R3 | Positive | enter `{n}` | saved | P1 |\n" for n in range(1, 9)
) + """| TC-B-009 | R4 | Boundary | enter `0` | rejected | P0 |
| TC-B-010 | R4 | Positive | enter `1` | saved | P1 |
| TC-B-011 | REG | Regression | reopen | unchanged | P2 |
| TC-B-012 | R5 | Positive | old | saved | P2 [OBSOLETE] |
"""


def selfcheck():
    headers, rows = parse_table(SAMPLE)
    assert headers[0] == "ID", headers
    assert len(rows) == 4, rows

    problems = "\n".join(lint(headers, rows))
    for expected in ["duplicate ID: TC-A-001", "TC-A-003: empty Expected Result",
                     "TC-A-003: no Req traceability", "invalid Priority 'P5'",
                     "unknown Category 'Nonsense'", "vague step",
                     "TC-A-003: invalid Automatable 'maybe'"]:
        assert expected in problems, f"missing {expected!r} in:\n{problems}"
    assert "missing column" not in problems, problems
    assert "\n".join(lint(["Test Case"], [["x"]])).count("missing column") == 6

    text = summary(headers, rows)
    assert "Total test cases: 4" in text
    assert "P0: 1" in text and "P1: 1" in text and "P2: 1" in text
    assert "Permission: 0  <- none" in text
    assert "Nonsense (unrecognized): 1" in text
    assert "Automatable Y: 2   N: 1" in text
    assert "Obsolete" not in text

    # Ratio and per-requirement risk cover.
    r_head, r_rows = parse_table(RATIO_SAMPLE)
    assert len(live_rows(r_rows)) == 11, r_rows
    assert "Obsolete, not counted: 1" in summary(r_head, r_rows)
    cov, notes = coverage(r_head, r_rows, {})
    joined = "\n".join(cov)
    assert "happy-path heavy: 9/11" in joined, joined
    assert "R3: success-path cases only (Positive)" in joined, joined
    assert "R4" not in joined and "REG" not in joined, joined

    cov, notes = coverage(r_head, r_rows, {"positive-ratio": "read-only screen", "R3": "no invalid input"})
    assert cov == [], cov
    assert any("Positive share 82% accepted" in n for n in notes), notes
    assert any("R3 success-path only, accepted" in n for n in notes), notes

    cov, _ = coverage(r_head, r_rows, {"R4": "why", "R9": "why"})
    joined = "\n".join(cov)
    assert "stale coverage-ok: R4 now has risk cases" in joined, joined
    assert "stale coverage-ok: R9 has no live case" in joined, joined

    # Under RATIO_MIN_ROWS the ratio is not checked at all.
    cov, notes = coverage(headers, rows, {})
    assert not any("happy-path heavy" in p for p in cov), cov
    assert not any("Positive share" in n for n in notes), notes

    found, sup_problems = suppressions(
        "<!-- coverage-ok: R7 — display only -->\n"
        "<!-- coverage-ok: R8 -->\n"
        "<!-- coverage-ok:  -->\n")
    assert found == {"R7": "display only"}, found
    assert "coverage-ok: R8 — no reason given" in "\n".join(sup_problems), sup_problems
    assert "coverage-ok comment with no key" in "\n".join(sup_problems), sup_problems

    # Two-way traceability.
    req_problems, report = requirement_coverage(r_head, r_rows, ["R3", "R4", "R6"])
    assert "R6: 0  <- no test case traces here" in report, report
    joined = "\n".join(req_problems)
    assert "requirement R6: no test case traces to it" in joined, joined
    assert "Req 'R5' is not in the requirement list" not in joined, joined  # obsolete row
    req_problems, _ = requirement_coverage(r_head, r_rows, ["R3"])
    assert "Req 'R4' is not in the requirement list" in "\n".join(req_problems), req_problems

    # Diff by ID.
    older = SAMPLE.replace("| TC-A-004 | R2 | Positive | gone | none | enter `1` | saved | P2 | Y |\n", "")
    report, diff_problems = diff_tables(SAMPLE, older)
    assert "+ " not in report and "- TC-A-004" in report, report
    assert "TC-A-004 was deleted" in "\n".join(diff_problems), diff_problems
    report, diff_problems = diff_tables(older, SAMPLE)
    assert "+ TC-A-004" in report and diff_problems == [], report
    marked = SAMPLE.replace("| TC-A-004 | R2 | Positive | gone |", "| TC-A-004 | R2 | Positive | gone [OBSOLETE] |")
    report, diff_problems = diff_tables(SAMPLE, marked)
    assert "~ TC-A-004 [OBSOLETE]" in report and diff_problems == [], report
    edited = SAMPLE.replace("| saved | P2 | Y |", "| saved and logged | P0 | Y |")
    report, _ = diff_tables(SAMPLE, edited)
    assert "* TC-A-004: Expected Result, Priority" in report, report
    assert diff_tables("nope", SAMPLE)[1] == ["--diff needs a markdown test case table in both files"]

    with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as f:
        f.write("# comment\n\nR1: dropdown reflects in L1\nR2\n")
        req_file = f.name
    assert read_requirements(req_file) == ["R1", "R2"], read_requirements(req_file)
    os.unlink(req_file)

    assert parse_table("no table here") == (None, [])
    print("selfcheck ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", help="markdown file containing the test case table")
    ap.add_argument("--csv", metavar="PATH", help="also export the table as CSV")
    ap.add_argument("--requirements", metavar="PATH",
                    help="file of requirement IDs, one per line; reports which have no case")
    ap.add_argument("--diff", nargs=2, metavar=("OLD", "NEW"),
                    help="compare two test case tables by ID and exit")
    ap.add_argument("--selfcheck", action="store_true", help="run built-in tests and exit")
    args = ap.parse_args()

    if args.selfcheck:
        selfcheck()
        return 0

    if args.diff:
        old, new = args.diff
        with open(old, encoding="utf-8") as f:
            old_text = f.read()
        with open(new, encoding="utf-8") as f:
            new_text = f.read()
        report, problems = diff_tables(old_text, new_text)
        if report:
            print(report)
        if problems:
            print("\n## Lint\n")
            for p in problems:
                print(f"- {p}")
        return 1 if problems else 0

    if not args.file:
        ap.error("file is required (or use --selfcheck / --diff)")

    with open(args.file, encoding="utf-8") as f:
        text = f.read()
    headers, rows = parse_table(text)

    if not headers:
        print(f"no markdown table found in {args.file}", file=sys.stderr)
        return 1

    print(summary(headers, rows))

    suppressed, problems = suppressions(text)
    cov_problems, notes = coverage(headers, rows, suppressed)
    problems += lint(headers, rows) + cov_problems

    if args.requirements:
        req_problems, report = requirement_coverage(headers, rows, read_requirements(args.requirements))
        print()
        print(report)
        problems += req_problems

    if notes:
        print("\n## Accepted\n")
        for n in notes:
            print(f"- {n}")

    print("\n## Lint\n")
    if problems:
        for p in problems:
            print(f"- {p}")
    else:
        print("clean")

    if args.csv:
        to_csv(headers, rows, args.csv)
        print(f"\nCSV written: {args.csv}")

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
