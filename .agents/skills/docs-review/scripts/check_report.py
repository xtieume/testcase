#!/usr/bin/env python3
"""Lint a docs-review report: verdict validity, duplicate IDs, missing citations."""
import os
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
    import shutil
    import tempfile

    report = """## Source inventory

| Doc ID | Path | What it is |
| ------ | ---- | ---------- |
| D1 | a.md | a document |

Searched the tree for: first, second, third — nothing outside the set.

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
| REQ-A-002 | second | Missing | searched: x, y in D1 | |
| REQ-A-003 | third | Undecided | | |
| DOC-A-001 | doc says fourth | Unspecified | D1:6 | "y" |

## Round findings

## Round log

| Round | Status | New rows | Verdict changes | Citations rejected | Nits |
| ----- | ------ | -------- | --------------- | ------------------ | ---- |
| 1 | merged | 0 | 0 | 0 | 0 |
"""

    work = tempfile.mkdtemp()
    open(os.path.join(work, "a.md"), "w").write("x\n\n\n\n\ny\n")   # "x" at line 1, "y" at line 6
    here = os.getcwd()
    os.chdir(work)

    def run(text, verdicts=VERDICTS_A):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, dir=work) as f:
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
    fires(report.replace("| REQ-A-002 | second | Missing | searched: x, y in D1 | |",
                         "| REQ-A-002 | second | Missing | | |"),
          "without a checkable search", "Missing without search terms")
    fires(report.replace("| REQ-A-002 | second | Missing | searched: x, y in D1 | |",
                         "| REQ-A-002 | second | Missing | searched: x in D1 | |"),
          "without a checkable search", "Missing with one spelling")
    fires(report.replace("| REQ-A-002 | second | Missing | searched: x, y in D1 | |",
                         "| REQ-A-002 | second | Missing | searched: x, y | |"),
          "without a checkable search", "Missing without the documents searched")
    fires(report.replace("| REQ-A-001 | first | Covered | D1:1 | \"x\" |",
                         "| REQ-A-001 | first | Covered | D1 | \"x\" |"),
          "citing no line or section", "Covered on a file name")
    fires(report.replace("Searched the tree for: first, second, third — nothing outside the set.\n", ""),
          "never checked against the tree", "inventory not checked against the tree")
    fires(report.replace("| 1 | merged | 0 | 0 | 0 | 0 |",
                         "| 1 | merged | 4 | 1 | 0 | 0 |\n| 2 | merged | 3 | 2 | 0 | 0 |"),
          "discovering the checklist", "new rows two rounds running")
    # a rebuilt round resets the streak: the set was fixed, the loop starts over
    problems, _ = run(report.replace("| 1 | merged | 0 | 0 | 0 | 0 |",
                                     "| 1 | merged | 4 | 1 | 0 | 0 |\n| 2 | rebuilt | | | | |\n"
                                     "| 1 | merged | 3 | 2 | 0 | 0 |\n| 2 | merged | 0 | 0 | 0 | 0 |"))
    assert problems == [], problems
    fires(report.replace("| 1 | merged | 0 | 0 | 0 | 0 |",
                         "| 1 | merged | 0 | 15 | 0 | 0 |"),
          "a flip is a new claim", "mass flip as the last round")
    # the quote is checked against the cited line: a rule number written as a line number
    fires(report.replace('| REQ-A-001 | first | Covered | D1:1 | "x" |',
                         '| REQ-A-001 | first | Covered | D1:6 | "x" |'),
          "the quote is not within two lines", "quote not at the cited line")
    fires(report.replace('| REQ-A-001 | first | Covered | D1:1 | "x" |',
                         '| REQ-A-001 | first | Covered | D1:40 | "x" |'),
          "has 6 lines", "cited line past the end of the file")
    # a retired row keeps its id and carries no verdict; the lint lets it stand
    problems, _ = run(report.replace("| REQ-A-003 | third | Undecided | | |",
                                     "| REQ-A-003 [OBSOLETE — split into 004/005] | third | | | |"))
    assert problems == [], problems
    fires(report.replace("| REQ-A-003 | third | Undecided | | |",
                         "| REQ-A-001 | third | Undecided | | |"),
          "duplicate ID REQ-A-001", "duplicate ID")
    fires(report.replace('| DOC-A-001 | doc says fourth | Unspecified | D1:6 | "y" |',
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
    mode_b = mode_b.replace("| REQ-A-002 | second | Missing | searched: x, y in D1 | |",
                            "| Q-2 | second | Absent | searched: x, y in D1 | |")
    mode_b = mode_b.replace("| REQ-A-003 | third | Undecided | | |",
                            "| Q-3 | third | Inferred | D1:6 | \"y\" |")
    mode_b = mode_b.replace('| DOC-A-001 | doc says fourth | Unspecified | D1:6 | "y" |\n', "")
    problems, counts = run(mode_b, VERDICTS_B)
    assert problems == [], f"clean mode B report should lint clean, got {problems}"
    assert sum(counts.values()) == 3, counts

    os.chdir(here)
    shutil.rmtree(work, ignore_errors=True)
    print("selfcheck ok")


# `D1:12`, `D3 §2.4`, `DOC-A-001#L40` — a place inside a document, not the document
LOCATED = re.compile(r"\b[A-Za-z]+-?[A-Za-z0-9]*-?\d+\s*[:§#]\s*\S")
# `searched: <term>, <variant> in D1, D3` — the spellings tried, then where
SEARCHED = re.compile(r"searched:\s*(.+?)\s+in\s+(\S.*)$", re.I)


def lint_round_log(path, text):
    """Read the round log the way step 4 says to: the columns are the stop rule.

    `New rows` staying at or above `Verdict changes` for two rounds means the loop is finding
    the checklist, not refining an audit — the set or the decomposition is wrong, and only a
    `rebuilt` round answers that. A last round that changed more than five verdicts is itself
    unreviewed: a flip is a new claim, and the round after it is what checks it."""
    problems, header, rounds, in_log = [], None, [], False
    for line in text.splitlines():
        if line.startswith("#"):
            in_log, header = "round log" in line.lower(), None
            continue
        if not in_log or not line.strip().startswith("|") or set(line.strip()) <= set("|- :"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        row = dict(zip(header, cells))
        if row.get("round", "").strip():
            rounds.append(row)

    def num(row, key):
        try:
            return int(row.get(key, "") or 0)
        except ValueError:
            return 0

    streak = 0
    for row in rounds:
        if "rebuilt" in row.get("status", "").lower():
            streak = 0
            continue
        new, changed = num(row, "new rows"), num(row, "verdict changes")
        streak = streak + 1 if new and new >= changed else 0
        if streak == 2:
            problems.append(f"{path}: round {row['round']} is the second running where `New rows` "
                            f"({new}) is at least `Verdict changes` ({changed}) — the loop is "
                            f"discovering the checklist, not refining it. Stop, redo steps 1–2, "
                            f"log the round as `rebuilt`, restart at round 1")
    if rounds and num(rounds[-1], "verdict changes") > 5:
        problems.append(f"{path}: the last round changed {num(rounds[-1], 'verdict changes')} "
                        f"verdicts and nothing reviewed them — a flip is a new claim; run the "
                        f"round after")
    return problems


CITE = re.compile(r"\b([A-Za-z][\w.-]*?)\s*:\s*(\d+)(?:\s*[-–]\s*(\d+))?")


def inventory(text):
    """Doc ID -> path, from the source inventory table, so a citation can be opened."""
    docs, header, in_inv = {}, None, False
    for line in text.splitlines():
        if line.startswith("#"):
            in_inv, header = "inventory" in line.lower(), None
            continue
        if not in_inv or not line.strip().startswith("|") or set(line.strip()) <= set("|- :"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        row = dict(zip(header, cells))
        did, dpath = row.get("doc id", ""), row.get("path", row.get("path / url", ""))
        if did and dpath:
            docs[did.lower()] = dpath.strip("`")
    return docs


def check_citation(rid, evidence, quote, docs, base):
    """'' when the quote sits at the cited line (±2), else why not. A line number that is
    really a rule number, or a quote copied from a different line, passes every format check
    and costs a review round each — this is the check the reviewer was doing by hand."""
    m = CITE.search(evidence)
    if not m or not quote.strip():
        return ""
    doc, start, end = m.group(1).lower(), int(m.group(2)), int(m.group(3) or m.group(2))
    fpath = docs.get(doc) or (doc if os.path.exists(os.path.join(base, doc)) else None)
    if not fpath:
        return ""                                           # a section, or a doc not on disk
    fpath = os.path.join(base, fpath)
    if not os.path.isfile(fpath):
        return ""
    lines = open(fpath, encoding="utf-8", errors="replace").read().splitlines()
    if start > len(lines):
        return f"{rid} cites {m.group(0)} but {fpath} has {len(lines)} lines"
    needle = re.sub(r"\s+", " ", quote.strip().strip('"“”\'`…').strip())[:24].lower()
    window = " ".join(lines[max(0, start - 3):min(len(lines), end + 2)])
    if needle and needle not in re.sub(r"\s+", " ", window).lower():
        return (f"{rid} cites {m.group(0)} but the quote is not within two lines of it — a rule "
                f"number written as a line number, or a quote from another line?")
    return ""


def lint(path, verdicts=VERDICTS_A):
    problems, seen, counts = [], Counter(), Counter()
    text_all = open(path, encoding="utf-8").read()
    docs, base = inventory(text_all), os.getcwd()

    for n, cells in rows(path):
        if len(cells) < 3 or not ID_RE.match(cells[0]):
            continue
        # a retired row keeps its id and says so; it has no verdict to lint
        if "[OBSOLETE" in cells[0].upper() or (len(cells) > 1 and "[OBSOLETE" in cells[1].upper()):
            seen[cells[0].split()[0]] += 1
            continue
        rid, verdict = cells[0], next((c for c in cells if c in verdicts), None)
        seen[rid] += 1
        if verdict is None:
            problems.append(f"{path}:{n}: {rid} has no valid verdict (one of {sorted(verdicts)})")
            continue
        counts[verdict] += 1
        rest = " ".join(cells[cells.index(verdict) + 1:])
        if verdict not in NO_EVIDENCE_NEEDED:
            if not rest.strip():
                problems.append(f"{path}:{n}: {rid} is '{verdict}' with no evidence or quote")
            elif not LOCATED.search(rest):
                # a file name says where to look, not what it says: a verdict flipped to
                # Covered on "the file contains the word" is a grep, and the line is the proof
                problems.append(f"{path}:{n}: {rid} is '{verdict}' citing no line or section "
                                f"(D1:12, D1 §2.3) — a file name is not a citation")
            else:
                after = cells[cells.index(verdict) + 1:]
                why = check_citation(rid, after[0] if after else "",
                                     after[1] if len(after) > 1 else "", docs, base)
                if why:
                    problems.append(f"{path}:{n}: {why}")
        elif verdict != "Undecided":
            m = SEARCHED.search(rest)
            terms = [t for t in re.split(r"[,、，]", m.group(1)) if t.strip()] if m else []
            if not m or len(terms) < 2 or not m.group(2).strip():
                problems.append(f"{path}:{n}: {rid} is '{verdict}' without a checkable search — "
                                f"write `searched: <term>, <variant> in <Doc IDs>`; one spelling "
                                f"of the spec's own word is how a search failure becomes a gap")

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
    elif "searched the tree for" not in text.lower():
        problems.append(f"{path}: the inventory was never checked against the tree — list the "
                        f"terms you searched the whole tree for (`Searched the tree for: …`); a "
                        f"set nobody checked is what a review loop then rediscovers one row per "
                        f"round")
    problems += lint_round_log(path, text)
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
