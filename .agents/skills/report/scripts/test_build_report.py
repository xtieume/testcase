"""Self-check for build_report.py. Run: python3 test_build_report.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
BUILD = HERE / "build_report.py"

CONFIG = {
    "title": "T",
    "header": "<b>scope</b>",
    "findings": ["f1"],
    "columns": [
        {"key": "id", "label": "ID", "nowrap": True},
        {"key": "req", "label": "Requirement"},
        {"key": "status", "label": "Status", "render": "status"},
        {"key": "evidence", "label": "Evidence", "render": "evidence"},
        {"key": "unit", "label": "Unit"},
        {"key": "e2e", "label": "E2E", "render": "e2e"},
        {"key": "note", "label": "Note"},
    ],
    "status": {
        "PASS": {"icon": "OK", "label": "done", "color": "#16a34a"},
        "NO_TEST": {"icon": "NT", "label": "no test", "color": "#eab308"},
        "MISSING": {"icon": "--", "label": "missing", "color": "#94a3b8"},
        "DEVIATION": {"icon": "XX", "label": "deviation", "color": "#dc2626"},
    },
    "rules": {
        "done": ["PASS"],
        "demote_pass_without_test": {"from": "PASS", "to": "NO_TEST", "when_empty": ["unit", "e2e"]},
        "e2e_fail_status": "DEVIATION",
        "attention": ["DEVIATION", "MISSING"],
    },
}

REQS = [
    {"id": "A-001", "area": "A", "req": "r1", "status": "PASS", "unit": "t.spec", "note": ""},
    {"id": "A-002", "area": "A", "req": "r2", "status": "PASS", "unit": "", "note": ""},
    {"id": "B-001", "area": "B", "req": "r3", "status": "PASS", "unit": "u.spec", "note": ""},
    {"id": "B-002", "area": "B", "req": "r4", "status": "MISSING", "unit": "", "note": ""},
]


def write(d, rel, rows):
    p = d / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def setup(tmp, config=None, reqs=None):
    d = Path(tmp)
    (d / "report.json").write_text(json.dumps(config or CONFIG, ensure_ascii=False), encoding="utf-8")
    write(d, "data/reqs-main.jsonl", reqs or REQS)
    return d


def build(d, expect_fail=False):
    r = subprocess.run([sys.executable, str(BUILD), str(d)], capture_output=True, text=True)
    if expect_fail:
        assert r.returncode != 0, f"expected failure, got:\n{r.stdout}"
        return r.stderr + r.stdout
    assert r.returncode == 0, f"build failed:\n{r.stderr}"
    return (d / "REPORT.html").read_text(encoding="utf-8")


def test_demote_pass_without_test():
    with tempfile.TemporaryDirectory() as tmp:
        d = setup(tmp)
        out = build(d)
        assert "A-002" in out
        # A-002 has no unit and no e2e -> demoted
        row = [l for l in out.splitlines() if "A-002" in l and "data-r" in l][0]
        assert "NO_TEST" in row, row
        row1 = [l for l in out.splitlines() if "A-001" in l and "data-r" in l][0]
        assert "NO_TEST" not in row1, row1


def test_missing_test_fields_are_unknown_not_demoted():
    """Absent columns (e.g. an imported flat list) must not be read as 'no test'."""
    with tempfile.TemporaryDirectory() as tmp:
        d = setup(tmp, reqs=[{"id": "A-001", "req": "r", "status": "PASS"}])
        row = [l for l in build(d).splitlines() if "A-001" in l and "data-r" in l][0]
        assert "NO_TEST" not in row, row


def test_partial_test_columns_still_demote():
    """One tracked-but-empty test column is enough: PASS with no test evidence is not PASS."""
    with tempfile.TemporaryDirectory() as tmp:
        d = setup(tmp, reqs=[{"id": "A-001", "req": "r", "status": "PASS", "unit": ""}])
        row = [l for l in build(d).splitlines() if "A-001" in l and "data-r" in l][0]
        assert "NO_TEST" in row, row


def test_rule_statuses_must_be_declared():
    """A typo in a rule's status dies with a message, not a KeyError traceback."""
    for path, value in [("e2e_fail_status", "DEVIATON"), ("done", ["PASSS"]),
                        ("attention", ["NOPE"])]:
        cfg = json.loads(json.dumps(CONFIG))
        cfg["rules"][path] = value
        with tempfile.TemporaryDirectory() as tmp:
            err = build(setup(tmp, config=cfg), expect_fail=True)
            assert "does not declare" in err, (path, err[-300:])
            assert "Traceback" not in err, (path, err[-300:])
    cfg = json.loads(json.dumps(CONFIG))
    cfg["rules"]["demote_pass_without_test"]["to"] = "NOT_A_STATUS"
    with tempfile.TemporaryDirectory() as tmp:
        assert "does not declare" in build(setup(tmp, config=cfg), expect_fail=True)


def test_e2e_fail_forces_deviation():
    with tempfile.TemporaryDirectory() as tmp:
        d = setup(tmp)
        write(d, "data/e2e-results.jsonl",
              [{"id": "A-001", "result": "FAIL", "date": "2026-01-01", "evidence": "run#3"}])
        out = build(d)
        row = [l for l in out.splitlines() if "A-001" in l and "data-r" in l][0]
        assert "DEVIATION" in row, row
        assert "run#3" in row, row


def test_overrides_apply():
    with tempfile.TemporaryDirectory() as tmp:
        d = setup(tmp)
        write(d, "data/overrides.jsonl", [{"id": "B-002", "status": "PASS", "unit": "fixed.spec"}])
        out = build(d)
        row = [l for l in out.splitlines() if "B-002" in l and "data-r" in l][0]
        assert "fixed.spec" in row and "MISSING" not in row, row


def test_validation_errors():
    checks = [
        ("duplicate", REQS + [dict(REQS[0])], None, "duplicate"),
        ("bad status", [dict(REQS[0], status="WAT")], None, "unknown status"),
    ]
    for name, reqs, _, needle in checks:
        with tempfile.TemporaryDirectory() as tmp:
            d = setup(tmp, reqs=reqs)
            assert needle in build(d, expect_fail=True).lower(), name
    with tempfile.TemporaryDirectory() as tmp:  # e2e for unknown id
        d = setup(tmp)
        write(d, "data/e2e-results.jsonl",
              [{"id": "ZZ-9", "result": "PASS", "date": "x", "evidence": "y"}])
        assert "unknown" in build(d, expect_fail=True).lower()
    with tempfile.TemporaryDirectory() as tmp:  # override for unknown id
        d = setup(tmp)
        write(d, "data/overrides.jsonl", [{"id": "ZZ-9", "status": "PASS"}])
        assert "unknown" in build(d, expect_fail=True).lower()


def test_progress_bars():
    with tempfile.TemporaryDirectory() as tmp:
        d = setup(tmp)
        out = build(d)
        # 4 reqs: A-001 PASS, A-002 -> NO_TEST, B-001 PASS, B-002 MISSING => 50% done
        assert 'class="bar"' in out
        assert "50%" in out, "status progress percent missing"
        assert "0%" in out, "evidence progress percent missing"


def test_evidence_attaches_and_review_warns():
    with tempfile.TemporaryDirectory() as tmp:
        d = setup(tmp)
        (d / "evidence").mkdir()
        write(d, "evidence/s01.manifest.jsonl",
              [{"file": "EV-1.png", "caption": "login empty", "check": "PASS"}])
        write(d, "evidence/s01.reqs.jsonl",
              [{"id": "A-001", "verdict": "SHOWN", "evidence": ["EV-1.png"]}])
        write(d, "evidence/review-s01.jsonl",
              [{"id": "A-001", "finding": "caption-mismatch", "detail": "other screen"}])
        out = build(d)
        row = [l for l in out.splitlines() if "A-001" in l and "data-r" in l][0]
        assert "evidence/EV-1.png" in row and "login empty" in row, row
        assert "caption-mismatch" in row, "review finding not surfaced"
        assert "25%" in out, "evidence bar should be 1/4"


def test_baseline_delta():
    cfg = dict(CONFIG, baseline={"label": "prev", "total": 3, "status": {"PASS": 3}})
    with tempfile.TemporaryDirectory() as tmp:
        d = setup(tmp, config=cfg)
        out = build(d)
        assert "prev" in out and "3 →" in out
        # both summary tables must sit inside the one flex row, each in its own section
        row = out[out.index("<div class='row'>"):out.index("<table id='t'")]
        assert row.count("<section>") == 2, row[:200]
        assert row.count("<table class='sum'>") == 2, "a summary table escaped the row"
        assert "<table class='sum'>" not in out[:out.index("<div class='row'>")]


def test_import_reqs_txt():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "report.json").write_text(json.dumps(CONFIG, ensure_ascii=False), encoding="utf-8")
        flat = d / "reqs.txt"
        flat.write_text("A-001: [PASS] does a thing (src: spec.md:12)\n"
                        "A-002: [MISSING] does another\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(BUILD), str(d), "--from-reqs", str(flat)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        rows = [json.loads(l) for l in
                (d / "data" / "reqs-00-imported.jsonl").read_text(encoding="utf-8").splitlines()]
        assert rows[0] == {"id": "A-001", "status": "PASS", "req": "does a thing", "src": "spec.md:12"}
        assert rows[1] == {"id": "A-002", "status": "MISSING", "req": "does another"}
        out = (d / "REPORT.html").read_text(encoding="utf-8")
        assert "does a thing" in out
        # re-import must refuse rather than clobber
        r2 = subprocess.run([sys.executable, str(BUILD), str(d), "--from-reqs", str(flat)],
                            capture_output=True, text=True)
        assert r2.returncode != 0 and "already exists" in r2.stderr + r2.stdout


def test_table_scrolls_in_its_own_box():
    with tempfile.TemporaryDirectory() as tmp:
        out = build(setup(tmp))
        assert "<div class='tw'><table id='t'>" in out
        assert out.rstrip().endswith("</table></div></main>")
        assert "max-height:72vh;overflow:auto" in out
        cfg = dict(CONFIG, table_height="1800px")
        with tempfile.TemporaryDirectory() as t2:
            assert "max-height:1800px" in build(setup(t2, config=cfg))
        assert ">4</b> rows" in out, "row counter missing"


def test_scope_and_progress_share_the_width():
    with tempfile.TemporaryDirectory() as tmp:
        out = build(setup(tmp))
        top = out[out.index("<div class='top'>"):out.index("<div class='row'>")]
        assert top.count("<div") - top.count("</div>") == 0, "unbalanced top row"
        assert "scope" in top and "Progress" in top


def test_column_filters():
    """Categorical columns get a dropdown; id-like columns stay a text box."""
    with tempfile.TemporaryDirectory() as tmp:
        out = build(setup(tmp))
        frow = out[out.index("<tr class='f'>"):out.index("</tr>", out.index("<tr class='f'>"))]
        assert frow.count("<select") == 2, "status and unit repeat values -> dropdowns"
        assert "<option>PASS</option>" in frow and "<option>NO_TEST</option>" in frow
        assert "data-i='0'" in frow and "<select data-i='0'" not in frow, "ids must not be a dropdown"
        assert "<td></td>" in frow, "evidence column takes no filter"
        assert "function F()" in out and "tr.cells[i].textContent" in out


def test_long_status_keys_are_abbreviated():
    """A long OVER_LONG_KEY collapses to its initials on its own; `short` can override."""
    cfg = json.loads(json.dumps(CONFIG))
    cfg["status"]["OUT_OF_SCOPE"] = {"icon": "o", "label": "out", "color": "#cbd5e1"}
    cfg["status"]["DEVIATION"]["short"] = "DEV"
    reqs = REQS + [{"id": "C-001", "req": "r5", "status": "OUT_OF_SCOPE"}]
    with tempfile.TemporaryDirectory() as tmp:
        out = build(setup(tmp, config=cfg, reqs=reqs))
        head = out[out.index("<div class='row'>"):out.index("<table id='t'")]
        assert "title='OUT_OF_SCOPE'" in head and ">OOS</th>" in head, "not abbreviated"
        assert ">DEV</th>" in head, "explicit short ignored"
        assert ">PASS</th>" in head, "short keys must stay intact"
        # the full name still appears where there is room
        assert "OUT_OF_SCOPE" in out[:out.index("<div class='row'>")]


def test_labels_override():
    cfg = dict(CONFIG, labels={"progress": "Tiến độ", "evidence": "Bằng chứng"})
    with tempfile.TemporaryDirectory() as tmp:
        out = build(setup(tmp, config=cfg))
        assert "Tiến độ" in out and "Bằng chứng" in out


def test_goalrun_emit():
    cfg = dict(CONFIG, emit={"goalrun_reqs": True})
    with tempfile.TemporaryDirectory() as tmp:
        d = setup(tmp, config=cfg)
        build(d)
        txt = (d / "reqs.txt").read_text(encoding="utf-8")
        assert "A-001: [PASS] r1" in txt, txt


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
    print("all passed")
