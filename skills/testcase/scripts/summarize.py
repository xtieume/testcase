#!/usr/bin/env python3
"""Count and lint a markdown test case table, and optionally export it as CSV.

Counting rows by hand is the step a model gets wrong, so it is done here instead.

    python3 summarize.py testcases.md
    python3 summarize.py testcases.md --csv .testcases/testcase/out.csv
    python3 summarize.py --selfcheck
"""

import argparse
import csv
import sys
from collections import Counter

CATEGORIES = [
    "Positive", "Negative", "Boundary", "Validation", "State", "Permission",
    "Error", "Data", "UI", "Integration", "Regression",
]
PRIORITIES = ["P0", "P1", "P2"]

# Phrases that mean the step has no concrete test data.
VAGUE = [
    "valid value", "invalid value", "some value", "any value", "appropriate value",
    "適切な値", "正しい値", "有効な値", "任意の値",
]


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


def lint(headers, rows):
    """Return a list of human-readable problems."""
    problems = []
    i_id = col(headers, "id")
    i_cat = col(headers, "category")
    i_pri = col(headers, "priority")
    i_exp = col(headers, "expected result", "expected")
    i_steps = col(headers, "steps")
    i_req = col(headers, "req", "requirement")

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
        steps = get(row, i_steps).lower()
        for phrase in VAGUE:
            if phrase in steps:
                problems.append(f"{tc_id}: vague step — {phrase!r}, use concrete data")
                break

    return problems


def summary(headers, rows):
    i_cat = col(headers, "category")
    i_pri = col(headers, "priority")
    cats = Counter(get(r, i_cat) for r in rows)
    pris = Counter(get(r, i_pri) for r in rows)

    out = ["## Coverage Summary", "", f"Total test cases: {len(rows)}", ""]
    for p in PRIORITIES:
        out.append(f"{p}: {pris.get(p, 0)}")
    out.append("")
    for c in CATEGORIES:
        n = cats.get(c, 0)
        out.append(f"{c}: {n}" if n else f"{c}: 0  <- none, confirm N/A or add cases")
    extra = set(cats) - set(CATEGORIES) - {""}
    for c in sorted(extra):
        out.append(f"{c} (unrecognized): {cats[c]}")
    return "\n".join(out)


def to_csv(headers, rows, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


SAMPLE = """
Intro text.

| ID | Req | Category | Test Case | Preconditions | Steps | Expected Result | Priority |
| -- | --- | -------- | --------- | ------------- | ----- | --------------- | -------- |
| TC-A-001 | R1 | Positive | happy | none | enter `100` | saved | P0 |
| TC-A-001 | R1 | Boundary | dup id | none | enter `0` | saved | P1 |
| TC-A-003 | | Nonsense | no req | none | enter a valid value | | P5 |
"""


def selfcheck():
    headers, rows = parse_table(SAMPLE)
    assert headers[0] == "ID", headers
    assert len(rows) == 3, rows

    problems = "\n".join(lint(headers, rows))
    for expected in ["duplicate ID: TC-A-001", "TC-A-003: empty Expected Result",
                     "TC-A-003: no Req traceability", "invalid Priority 'P5'",
                     "unknown Category 'Nonsense'", "vague step"]:
        assert expected in problems, f"missing {expected!r} in:\n{problems}"

    text = summary(headers, rows)
    assert "Total test cases: 3" in text
    assert "P0: 1" in text and "P1: 1" in text and "P2: 0" in text
    assert "Permission: 0  <- none" in text

    assert parse_table("no table here") == (None, [])
    print("selfcheck ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", help="markdown file containing the test case table")
    ap.add_argument("--csv", metavar="PATH", help="also export the table as CSV")
    ap.add_argument("--selfcheck", action="store_true", help="run built-in tests and exit")
    args = ap.parse_args()

    if args.selfcheck:
        selfcheck()
        return 0
    if not args.file:
        ap.error("file is required (or use --selfcheck)")

    with open(args.file, encoding="utf-8") as f:
        headers, rows = parse_table(f.read())

    if not headers:
        print(f"no markdown table found in {args.file}", file=sys.stderr)
        return 1

    print(summary(headers, rows))

    problems = lint(headers, rows)
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
