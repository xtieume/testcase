#!/usr/bin/env python3
"""Lint a docs-review report: verdict validity, duplicate IDs, missing citations."""
import re
import sys
from collections import Counter

VERDICTS_A = {"Covered", "Partial", "Missing", "Contradict", "Conflict", "Stale",
              "Unspecified", "Undecided"}
VERDICTS_B = {"Stated", "Inferred", "Conflicting", "Absent"}
NO_EVIDENCE_NEEDED = {"Missing", "Undecided", "Absent"}
ID_RE = re.compile(r"^(REQ|DOC|Q)-[A-Z0-9]+-\d{3}$|^Q-?\d+$", re.I)


VERDICT_HEADERS = {"verdict", "answer", "confidence"}


def rows(path):
    """Yield (line number, cells) for data rows of tables that have a verdict column.

    The report also contains the requirement checklist and the round log, whose rows carry
    IDs but no verdict. Linting those reports every checklist row as a duplicate with a
    missing verdict, so tables are selected by their header.
    """
    header = None
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.strip()
        if not line.startswith("|"):
            header = None
            continue
        if set(line) <= set("|- :"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if header is None:
            header = {c.lower() for c in cells}
            continue
        if header & VERDICT_HEADERS:
            yield n, cells


def selfcheck():
    """Every problem the linter can report, plus the clean case, checked against a report
    written in the exact format SKILL.md prescribes."""
    import os
    import tempfile

    report = """## Source inventory

| Doc ID | Path | What it is |
| ------ | ---- | ---------- |
| D1 | a.md | a document |

## Requirement checklist

| Req ID | Requirement | Dimension | Source |
| ------ | ----------- | --------- | ------ |
| REQ-A-001 | first | Behavior | spec |
| REQ-A-002 | second | Behavior | spec |
| REQ-A-003 | third | Behavior | spec |

## Traceability

| Req ID | Requirement | Verdict | Evidence | Quote |
| ------ | ----------- | ------- | -------- | ----- |
| REQ-A-001 | first | Covered | D1:1 | "x" |
| REQ-A-002 | second | Missing | searched: x, y | |
| REQ-A-003 | third | Undecided | | |
| DOC-A-001 | doc says fourth | Unspecified | D1:2 | "y" |

## Round findings

## Round log

| Round | New rows | Verdict changes | Citations rejected | Nits |
| ----- | -------- | --------------- | ------------------ | ---- |
| 1 | 0 | 0 | 0 | 0 |
"""

    def run(text, verdicts=VERDICTS_A):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(text)
        try:
            return lint(f.name, verdicts)
        finally:
            os.unlink(f.name)

    def fires(text, needle, case):
        problems, _ = run(text)
        assert any(needle in p for p in problems), f"{case}: expected {needle!r}, got {problems}"

    problems, counts = run(report)
    assert problems == [], f"clean report should lint clean, got {problems}"
    assert counts == Counter({"Covered": 1, "Missing": 1, "Undecided": 1,
                              "Unspecified": 1}), counts

    # The checklist and the round log carry IDs and numbers but no verdict column.
    # Counting their rows is the bug this header selection exists to prevent.
    assert sum(counts.values()) == 4, "non-verdict tables were linted"

    fires(report.replace("| REQ-A-001 | first | Covered | D1:1 | \"x\" |",
                         "| REQ-A-001 | first | Coverd | D1:1 | \"x\" |"),
          "has no valid verdict", "typo in verdict")
    fires(report.replace("| REQ-A-001 | first | Covered | D1:1 | \"x\" |",
                         "| REQ-A-001 | first | Covered | | |"),
          "with no evidence or quote", "Covered without a citation")
    fires(report.replace("| REQ-A-002 | second | Missing | searched: x, y | |",
                         "| REQ-A-002 | second | Missing | | |"),
          "without the search terms", "Missing without search terms")
    fires(report.replace("| REQ-A-003 | third | Undecided | | |",
                         "| REQ-A-001 | third | Undecided | | |"),
          "duplicate ID REQ-A-001", "duplicate ID")
    fires(report.replace('| DOC-A-001 | doc says fourth | Unspecified | D1:2 | "y" |',
                         "| DOC-A-001 | doc says fourth | Unspecified | | |"),
          "with no evidence or quote", "Unspecified without a citation")
    fires(report.replace("## Round findings", "## Nothing"), "no '## Round findings'", "no round findings")
    fires(report.replace("## Round log", "## Nothing"), "no '## Round log'", "no round log")
    fires(report.replace("## Source inventory", "## Nothing"), "no source inventory", "no inventory")
    fires("# empty\n", "no verdict rows found", "no table at all")
    fires(report + "\nThis audit was sharded across subagents.\n",
          "sharded audit with no coverage declaration", "shard without coverage")

    # Undecided needs neither citation nor search terms; Missing needs search terms only.
    problems, _ = run(report.replace("| REQ-A-003 | third | Undecided | | |",
                                     "| REQ-A-003 | third | Undecided | | |"))
    assert problems == [], problems

    mode_b = report.replace("| Req ID | Requirement | Verdict | Evidence | Quote |",
                            "| Q ID | Sub-question | Answer | Evidence | Quote |")
    mode_b = mode_b.replace("| REQ-A-001 | first | Covered | D1:1 | \"x\" |",
                            "| Q-1 | first | Stated | D1:1 | \"x\" |")
    mode_b = mode_b.replace("| REQ-A-002 | second | Missing | searched: x, y | |",
                            "| Q-2 | second | Absent | searched: x, y | |")
    mode_b = mode_b.replace("| REQ-A-003 | third | Undecided | | |",
                            "| Q-3 | third | Inferred | D1:2 | \"y\" |")
    mode_b = mode_b.replace('| DOC-A-001 | doc says fourth | Unspecified | D1:2 | "y" |\n', "")
    problems, counts = run(mode_b, VERDICTS_B)
    assert problems == [], f"clean mode B report should lint clean, got {problems}"
    assert sum(counts.values()) == 3, counts

    print("selfcheck ok")


def lint(path, verdicts=VERDICTS_A):
    problems, seen, counts = [], Counter(), Counter()

    for n, cells in rows(path):
        if len(cells) < 3 or not ID_RE.match(cells[0]):
            continue
        rid, verdict = cells[0], next((c for c in cells if c in verdicts), None)
        seen[rid] += 1
        if verdict is None:
            problems.append(f"{path}:{n}: {rid} has no valid verdict (one of {sorted(verdicts)})")
            continue
        counts[verdict] += 1
        rest = " ".join(cells[cells.index(verdict) + 1:])
        if verdict not in NO_EVIDENCE_NEEDED and not rest.strip():
            problems.append(f"{path}:{n}: {rid} is '{verdict}' with no evidence or quote")
        if verdict in NO_EVIDENCE_NEEDED and verdict != "Undecided" and not rest.strip():
            problems.append(f"{path}:{n}: {rid} is '{verdict}' without the search terms you checked")

    problems += [f"{path}: duplicate ID {rid} ({c} rows)" for rid, c in seen.items() if c > 1]

    if not counts:
        problems.append(f"{path}: no verdict rows found — is this the right file?")
    text = open(path, encoding="utf-8").read()
    if "## Round findings" not in text:
        problems.append(f"{path}: no '## Round findings' section — was the review loop run?")
    if "## Round log" not in text:
        problems.append(f"{path}: no '## Round log' table — convergence is asserted, not shown")
    if not re.search(r"^#+ .*(Source inventory|Inventory)", text, re.M | re.I):
        problems.append(f"{path}: no source inventory — which documents were read, and which were not?")
    if re.search(r"\bshard|not-accessed\b", text, re.I) and "coverage" not in text.lower():
        problems.append(f"{path}: sharded audit with no coverage declaration")

    return problems, counts


def main():
    if "--selfcheck" in sys.argv:
        selfcheck()
        return 0
    path = sys.argv[1]
    verdicts = VERDICTS_B if "--mode" in sys.argv and "b" in sys.argv[-1].lower() else VERDICTS_A
    problems, counts = lint(path, verdicts)

    print(f"{sum(counts.values())} rows: " + ", ".join(f"{v}={c}" for v, c in counts.most_common()))
    for p in problems:
        print("  " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
