"""Build REPORT.html from report.json + data/*.jsonl.

Run: python3 build_report.py <dir>                      (<dir> holds report.json)
     python3 build_report.py <dir> --from-reqs <file>   import a flat reqs.txt first

Layout, all relative to <dir>:
  report.json            config: columns, statuses, rules, meta
  data/reqs-*.jsonl      one JSON object per requirement (merged in filename order)
  data/overrides.jsonl   {"id": ..., <fields to overwrite>}
  data/e2e-results.jsonl {"id","result","date","evidence"}
  evidence/*.manifest.jsonl  {"file","caption","check"}
  evidence/*.reqs.jsonl      {"id","verdict","evidence":[file,...],"note"}
  evidence/review-*.jsonl    {"id","finding","detail"}   independent reviewer
Rebuilding is idempotent: run it again after evidence lands and the images attach.
"""
import html
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

EV_MARK = {"SHOWN": "🟢", "SHOWN-PARTIAL": "🟡", "NOT-SHOWN": "🔴", "NONE": "⬜"}
E2E_MARK = {"PASS": "✅", "FAIL": "🔴", "BLOCKED": "⛔", "SKIP": "—"}
LABELS = {
    "progress": "Progress",
    "status": "Status",
    "evidence": "Evidence",
    "evidence_unit": "req with SHOWN evidence",
    "evidence_images": "images",
    "evidence_findings": "review findings",
    "evidence_none": "no evidence yet",
    "evidence_partial": "partial",
    "no_evidence_bucket": "not covered",
    "e2e_ran": "E2E ran on",
    "built_at": "Built at",
    "baseline": "Compared with",
    "baseline_before_after": "Before → Now",
    "total_reqs": "Total reqs",
    "group": "Group",
    "by_group": "Breakdown by group",
    "total": "Total",
    "findings": "Key findings",
    "summary": "Summary",
    "attention": "Needs action / confirmation",
    "table": "Requirements",
    "filter": "filter by Req ID, status, test file …",
    "req": "Requirement",
    "rows": "rows",
    "all": "all",
    "filter_col": "…",
    "demoted": "[auto] marked {frm} with no test.",
    "e2e_failed": "E2E FAIL",
}

# Reserved status palette (icon + label always accompany the colour; never colour alone).
STATUS_HUE = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a",
              "critical": "#d03b3b", "neutral": "#898781", "quiet": "#c3c2b7"}
FALLBACK = list(STATUS_HUE.values())

CSS = """:root{
  color-scheme:light;
  --plane:#fafaf8; --surface:#fff; --raise:#f2f0ea;
  --ink:#1b1b1a; --ink2:#55534e; --muted:#8a877f;
  --grid:#e3e1dc; --line:#d5d2c9; --ring:rgba(27,27,26,.10); --track:#e9e6df;
  --crit:#b3261e;
}
*{box-sizing:border-box}
.page{max-width:1440px;margin:0 auto}
body{margin:0;padding:24px 20px 64px;background:var(--plane);color:var(--ink);
  font:13px/1.55 system-ui,-apple-system,'Segoe UI','Hiragino Sans','Noto Sans JP',sans-serif;
  -webkit-font-smoothing:antialiased}
h1{font-size:20px;line-height:1.3;margin:0 0 6px;letter-spacing:-.01em}
h2{font-size:12px;margin:36px 0 12px;text-transform:uppercase;letter-spacing:.07em;
  color:var(--muted);font-weight:600}
p.src{margin:0 0 12px;color:var(--ink2);font-size:12px;max-width:110ch}
p.cap{margin:20px 0 6px;font-size:12px;font-weight:600;color:var(--ink)}
code{background:var(--raise);padding:1px 5px;border-radius:4px;font-size:.92em;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
a{color:inherit}

/* progress */
.bar{display:flex;gap:2px;height:12px;border-radius:6px;overflow:hidden;
  background:var(--track);margin:0 0 6px}
.bar span{display:block;min-width:2px}
.barlab{font-size:12px;color:var(--ink2);margin:0 0 18px;max-width:110ch}
.barlab b{color:var(--ink);font-variant-numeric:tabular-nums}
.dot{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:5px;
  vertical-align:baseline;box-shadow:0 0 0 1px var(--ring) inset}

/* layout */
/* scope text and progress share the width instead of leaving half the page empty;
   the text column keeps a readable measure rather than stretching to 180ch */
.top{display:flex;flex-wrap:wrap;gap:16px 40px;align-items:flex-start;margin:0 0 8px}
.top>div{flex:1 1 460px;min-width:0}
.top .scope{max-width:82ch}
.top h2{margin-top:0}
.row{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-start;margin:0 0 8px}
/* a card scrolls its own table sideways rather than pushing the page wider than the screen */
.row section{flex:0 1 auto;min-width:0;max-width:100%;overflow-x:auto}
.row section.find{flex:1 1 320px}
/* a long caption must not decide the card's width: width:0 keeps it out of the
   intrinsic size, min-width:100% makes it fill and wrap to the table's width */
.row .cap{margin-top:0;width:0;min-width:100%}

/* tables */
table{border-collapse:separate;border-spacing:0;width:100%;background:var(--surface);
  border:1px solid var(--grid);border-radius:8px;overflow:hidden;margin:0 0 28px}
table:last-child{margin-bottom:0}
th,td{border-bottom:1px solid var(--grid);padding:7px 10px;text-align:left;vertical-align:top}
/* file paths and ids offer no break opportunities -- without this a column never wraps */
td{overflow-wrap:anywhere}
tr:last-child th,tr:last-child td{border-bottom:0}
th{background:var(--raise);font-weight:600;font-size:11px;letter-spacing:.03em;
  text-transform:uppercase;color:var(--ink2);position:sticky;top:0;z-index:2;
  border-bottom:1px solid var(--line)}
/* per-column filters ride just under the header, both pinned while the box scrolls */
tr.f td{position:sticky;top:30px;z-index:2;background:var(--raise);padding:4px 6px;
  border-bottom:1px solid var(--line)}
tr.f input,tr.f select{width:100%;margin:0;padding:3px 5px;font-size:11px;border-radius:5px}
/* touch: 11px inputs are both hard to hit and trigger focus-zoom on iOS */
@media (pointer:coarse){
  tr.f input,tr.f select,#q{font-size:16px;min-height:36px;padding:6px 8px}
}
tr.f select{background:var(--surface)}
td{color:var(--ink2)}
/* indicator columns (ids, status) read as one token -- wrapping them mid-word is noise;
   content columns keep wrapping */
td.nw{color:var(--ink);white-space:nowrap}
th{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
/* the requirement table scrolls inside its own box -- 700+ rows must not turn the
   page into an endless scroll, and the sticky header only works against this container */
.tw{max-height:__TH__;overflow:auto;border:1px solid var(--grid);border-radius:8px;
  margin:0 0 28px;background:var(--surface)}
.tw table{border:0;border-radius:0;margin:0}
table#t{table-layout:fixed;min-width:1240px}
.count{font-size:12px;color:var(--muted);margin-left:10px;font-variant-numeric:tabular-nums}
table.sum{width:auto;max-width:100%;font-variant-numeric:tabular-nums}
table.sum td,table.sum th{white-space:nowrap}
table.sum td{text-align:right;color:var(--ink)}
table.sum td:first-child,table.sum th:first-child{text-align:left}
table.sum th{text-align:right}
table.sum th,table.sum td{padding:6px 9px}
/* status headers stack the icon over the label so the column is only as wide as the word */
table.sum th i{display:block;font-style:normal;line-height:1.2;margin-bottom:1px}

/* filter */
input{margin:0 0 12px;padding:7px 11px;width:340px;max-width:100%;font:inherit;
  color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:7px}
input:focus{outline:2px solid var(--ink2);outline-offset:1px}

/* evidence */
img.ev{width:100%;max-width:150px;border:1px solid var(--grid);border-radius:6px;display:block;margin-top:5px}
.evc{font-size:11px;line-height:1.45;color:var(--muted);max-width:220px}
.evr{font-size:11px;line-height:1.45;color:var(--crit);max-width:220px;margin-top:3px}
td.evt{min-width:200px}
ul{margin:0 0 4px;padding-left:18px;color:var(--ink2);max-width:110ch}
/* same for the stand-alone tables outside the card row */
.scroll{overflow-x:auto;margin:0 0 28px}
.scroll table{margin:0}
li{margin-bottom:4px}

/* last: these must win over the rules above */
@media (max-width:700px){.tw{max-height:80vh}}"""


def die(msg):
    raise SystemExit(f"build_report: {msg}")


def esc(v):
    return html.escape(str(v if v not in (None, "") else "—"))


def load_jsonl(path):
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as e:
            die(f"{path.name}:{n}: {e}")
    return rows


def pct(part, total):
    return 100.0 * part / total if total else 0.0


def bar(segments, label):
    """segments: [(count, color, name)] -> stacked progress bar."""
    total = sum(c for c, _, _ in segments) or 1
    cells = "".join(
        f"<span style='width:{pct(c, total):.4f}%;background:{col}' title='{esc(n)}: {c}'></span>"
        for c, col, n in segments if c and col)
    return f"<div class=\"bar\">{cells}</div><div class='barlab'>{label}</div>"


class Report:
    def __init__(self, root):
        self.root = root
        cfg_file = root / "report.json"
        if not cfg_file.exists():
            die(f"no report.json in {root}")
        self.cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        self.status = self.cfg["status"]
        self.columns = self.cfg["columns"]
        self.rules = self.cfg.get("rules", {})
        self.data = root / "data"
        self.ev_dir = root / "evidence"
        self.lab = dict(LABELS, **self.cfg.get("labels", {}))
        self.color = {k: v.get("color", FALLBACK[i % len(FALLBACK)])
                      for i, (k, v) in enumerate(self.status.items())}
        self.check_rule_statuses()

    def check_rule_statuses(self):
        """Rules can assign a status; a typo there must die here, not as a KeyError mid-render."""
        named = [("rules.e2e_fail_status", [self.rules.get("e2e_fail_status")]),
                 ("rules.done", self.rules.get("done") or []),
                 ("rules.attention", self.rules.get("attention") or [])]
        dem = self.rules.get("demote_pass_without_test") or {}
        named += [("rules.demote_pass_without_test.%s" % k, [dem.get(k)]) for k in ("from", "to")]
        bad = {where: v for where, vals in named for v in vals if v and v not in self.status}
        if bad:
            die("rules name statuses that report.json does not declare: %s (declared: %s)"
                % (bad, ", ".join(self.status)))

    # ---------- load ----------

    def load_reqs(self):
        reqs = []
        for f in sorted(self.data.glob("reqs-*.jsonl")):
            reqs += load_jsonl(f)
        if not reqs:
            die(f"no requirements found in {self.data}/reqs-*.jsonl")
        by_id = {}
        for r in reqs:
            if "id" not in r:
                die(f"requirement without id: {r}")
            if r["id"] in by_id:
                die(f"duplicate Req ID: {r['id']}")
            by_id[r["id"]] = r
        ov = self.data / "overrides.jsonl"
        if ov.exists():
            for o in load_jsonl(ov):
                if o.get("id") not in by_id:
                    die(f"override for unknown Req ID: {o.get('id')}")
                by_id[o["id"]].update(o)
        bad = {r["id"]: r.get("status") for r in reqs if r.get("status") not in self.status}
        if bad:
            die(f"unknown status: {bad}")
        return reqs, by_id

    def load_e2e(self, by_id):
        f = self.data / "e2e-results.jsonl"
        if not f.exists():
            return {}
        res = {}
        for r in load_jsonl(f):
            if r.get("id") not in by_id:
                die(f"e2e result for unknown Req ID: {r.get('id')}")
            res[r["id"]] = r
        return res

    def load_evidence(self, by_id):
        by_req, caption, findings = {}, {}, {}
        if not self.ev_dir.exists():
            return by_req, caption, findings
        for f in sorted(self.ev_dir.glob("*.manifest.jsonl")):
            for m in load_jsonl(f):
                caption[m["file"]] = m
        for f in sorted(self.ev_dir.glob("*.reqs.jsonl")):
            for r in load_jsonl(f):
                if r.get("id") not in by_id:
                    die(f"evidence for unknown Req ID: {r.get('id')} ({f.name})")
                by_req[r["id"]] = r
        for f in sorted(self.ev_dir.glob("review-*.jsonl")):
            for x in load_jsonl(f):
                findings.setdefault(x["id"], []).append(x)
        return by_req, caption, findings

    # ---------- rules ----------

    def apply_rules(self, reqs, e2e):
        fail_to = self.rules.get("e2e_fail_status")
        for r in reqs:
            res = e2e.get(r["id"])
            if not res:
                continue
            r["_e2e"] = (f"{E2E_MARK.get(res['result'], '?')} {res['result']}"
                         f" ({res.get('date', '—')}): {res.get('evidence', '—')}")
            if res["result"] == "FAIL" and fail_to and r["status"] != fail_to:
                r["note"] = (f"{self.lab['e2e_failed']} → {res.get('evidence', '')}. "
                             + (r.get("note") or ""))
                r["status"] = fail_to
        dem = self.rules.get("demote_pass_without_test")
        if dem:
            keys = dem.get("when_empty", [])
            for r in reqs:
                if r["status"] != dem["from"]:
                    continue
                # Demote only when this dataset tracks tests at all: at least one of the
                # fields is present (an empty one means "looked, found none") and none of
                # them holds a value. A row carrying none of them -- an imported flat list --
                # says nothing about tests, so it keeps its status.
                if not any(k in r or (k == "e2e" and "_e2e" in r) for k in keys):
                    continue
                vals = [r.get("_e2e") if k == "e2e" else r.get(k) for k in keys]
                if all(str(v or "—").strip() in ("—", "-", "") for v in vals):
                    r["status"] = dem["to"]
                    r["note"] = (self.lab["demoted"].format(frm=dem["from"]) + " "
                                 + (r.get("note") or ""))

    # ---------- render ----------

    def evidence_cell(self, ev, caption, findings):
        if not ev and not findings:
            return f"<td class='evt'>⬜ {esc(self.lab['evidence_none'])}</td>"
        ev = ev or {"verdict": "NONE", "evidence": []}
        parts = [f"{EV_MARK.get(ev['verdict'], '?')} <b>{esc(ev['verdict'])}</b>"]
        for f in ev.get("evidence", []):
            m = caption.get(f, {})
            ok = "✔" if m.get("check") == "PASS" else "✖"
            parts.append(
                f"<a href='evidence/{html.escape(f)}' target='_blank' title='{esc(m.get('caption'))}'>"
                f"<img src='evidence/{html.escape(f)}' loading='lazy' class='ev'></a>"
                f"<div class='evc'>{ok} {esc(f)}<br>{esc(m.get('caption'))}</div>")
        if ev.get("note"):
            parts.append(f"<div class='evc'>{esc(ev['note'])}</div>")
        for x in findings or []:
            parts.append(f"<div class='evr'>⚠ review {esc(x.get('finding'))}: {esc(x.get('detail'))}</div>")
        return "<td class='evt'>" + "".join(parts) + "</td>"

    def cell(self, r, col, ev_by_req, ev_caption, ev_findings):
        key, render = col["key"], col.get("render")
        if render == "evidence":
            return self.evidence_cell(ev_by_req.get(r["id"]), ev_caption, ev_findings.get(r["id"]))
        if render == "status":
            st = r["status"]
            return (f"<td class='nw'><span class='dot' style='background:{self.color[st]}'></span>"
                    f"{esc(self.status[st]['icon'])} {esc(st)}</td>")
        elif render == "e2e":
            v = r.get("_e2e") or r.get(key)
        else:
            v = r.get(key)
        cls = " class='nw'" if col.get("nowrap") else ""
        return f"<td{cls}>{esc(v)}</td>"

    FILTER_MAX_OPTIONS = 25
    SHORT_AT = 10

    def short_label(self, key):
        """Compact header label: an explicit `short`, else initials of an OVER_LONG_KEY."""
        cfg = self.status[key].get("short")
        if cfg:
            return cfg
        if len(key) <= self.SHORT_AT:
            return key
        parts = [p for p in key.split("_") if p]
        return "".join(p[0] for p in parts) if len(parts) > 1 else key[:self.SHORT_AT - 1] + "."


    def filter_row(self, reqs):
        """A text box per column, or a dropdown when the column holds few distinct values."""
        cells = []
        for i, c in enumerate(self.columns):
            key, render = c["key"], c.get("render")
            if render == "evidence":
                cells.append("<td></td>")
                continue
            if render == "status":
                vals = list(self.status)
            else:
                seen = {str(r.get(key)).strip() for r in reqs if str(r.get(key) or "").strip()}
                # a dropdown only helps for categorical columns: few values, and repeated.
                # an id column has one value per row, so it stays a text box.
                vals = (sorted(seen) if 1 < len(seen) <= self.FILTER_MAX_OPTIONS
                        and len(seen) < len(reqs) else None)
            if vals:
                opts = "".join("<option>%s</option>" % esc(v) for v in vals)
                cells.append("<td><select data-i='%d' onchange='F()'><option value=''>%s</option>%s"
                             "</select></td>" % (i, esc(self.lab["all"]), opts))
            else:
                cells.append("<td><input data-i='%d' oninput='F()' placeholder='%s'></td>"
                             % (i, esc(self.lab["filter_col"])))
        return "<tr class='f'>" + "".join(cells) + "</tr>"

    def sec(self):
        self._sec += 1
        return f"{self._sec}."

    def group_of(self, r):
        gb = self.cfg.get("group_by", "id_prefix")
        return r["id"].rsplit("-", 1)[0] if gb == "id_prefix" else str(r.get(gb, "—"))

    def build(self):
        reqs, by_id = self.load_reqs()
        e2e = self.load_e2e(by_id)
        self.apply_rules(reqs, e2e)
        ev_by_req, ev_caption, ev_findings = self.load_evidence(by_id)

        n = len(reqs)
        by_status = Counter(r["status"] for r in reqs)
        e2e_count = Counter(v["result"] for v in e2e.values())
        ev_count = Counter(ev_by_req[r["id"]]["verdict"] if r["id"] in ev_by_req else "NONE" for r in reqs)
        done = self.rules.get("done") or [next(iter(self.status))]
        done_n = sum(by_status.get(s, 0) for s in done)
        shown, partial = ev_count.get("SHOWN", 0), ev_count.get("SHOWN-PARTIAL", 0)

        o = [f"<!doctype html><meta charset='utf-8'><title>{esc(self.cfg['title'])}</title>",
             "<meta name='viewport' content='width=device-width,initial-scale=1'>",
             "<style>%s</style>" % CSS.replace("__TH__", self.cfg.get("table_height", "72vh")),
             "<main class='page'>",
             f"<h1>{self.cfg['title']}</h1>"]
        o.append("<div class='top'><div class='scope'>")
        if self.cfg.get("header"):
            o.append(f"<p class='src'>{self.cfg['header']}</p>")
        o.append("</div><div>")

        L = self.lab
        self._sec = 0
        o.append(f"<h2>{self.sec()} {esc(L['progress'])}</h2>")
        o.append(bar([(by_status.get(s, 0), self.color[s], s) for s in self.status],
                     f"{esc(L['status'])} — <b>{pct(done_n, n):.0f}%</b> {'/'.join(done)} ({done_n}/{n}) · "
                     + " · ".join(
                         f"<span class='dot' style='background:{self.color[s]}'></span>"
                         f"{esc(self.status[s]['icon'])} {esc(s)}: <b>{by_status.get(s, 0)}</b>"
                         for s in self.status)))
        o.append(bar([(shown, STATUS_HUE["good"], "SHOWN"),
                      (partial, STATUS_HUE["warning"], "SHOWN-PARTIAL"),
                      (n - shown - partial, "", L["no_evidence_bucket"])],
                     f"{esc(L['evidence'])} — <b>{pct(shown, n):.0f}%</b> "
                     f"({shown}/{n} {esc(L['evidence_unit'])}"
                     + (f", {partial} {esc(L['evidence_partial'])}" if partial else "")
                     + f") · {len(ev_caption)} {esc(L['evidence_images'])}"
                     + (f" · ⚠ {sum(len(v) for v in ev_findings.values())} {esc(L['evidence_findings'])}"
                        if ev_findings else "")))
        if e2e:
            o.append(f"<p class='src'>{esc(L['e2e_ran'])} <b>{len(e2e)}</b> reqs: "
                     + " · ".join(f"{E2E_MARK.get(k, '?')} {k}: <b>{v}</b>"
                                  for k, v in sorted(e2e_count.items())) + ".</p>")
        o.append(f"<p class='src'>{esc(L['built_at'])} <b>{datetime.now():%Y-%m-%d %H:%M}</b>.</p>")
        o.append("</div></div>")

        cards = []
        base = self.cfg.get("baseline")
        if base:
            def delta(now, before):
                d = now - before
                return f"{before} → <b>{now}</b>" + (f" ({'+' if d > 0 else ''}{d})" if d else "")
            cards.append(f"<p class='cap'>{esc(L['baseline'])} {esc(base['label'])}</p>")
            cards.append(f"<table class='sum'><tr><th>{esc(L['status'])}</th>"
                     f"<th>{esc(L['baseline_before_after'])}</th></tr>"
                     + f"<tr><td>{esc(L['total_reqs'])}</td><td>{delta(n, base.get('total', 0))}</td></tr>"
                     + "".join(f"<tr><td>{esc(self.status[s]['icon'])} {esc(s)}</td>"
                               f"<td>{delta(by_status.get(s, 0), base.get('status', {}).get(s, 0))}</td></tr>"
                               for s in self.status)
                     + "".join(f"<tr><td>E2E {E2E_MARK.get(k, '?')} {k}</td>"
                               f"<td>{delta(e2e_count.get(k, 0), base.get('e2e', {}).get(k, 0))}</td></tr>"
                               for k in sorted(base.get("e2e", {})))
                     + "</table>")

        cards = ["<section>" + "".join(cards) + "</section>"] if cards else []
        groups = sorted({self.group_of(r) for r in reqs})
        g = [f"<p class='cap'>{esc(L['by_group'])}</p>"]
        g.append(f"<table class='sum'><tr><th>{esc(L['group'])}</th><th>{esc(L['total'])}</th>"
                 + "".join("<th title='%s'><i>%s</i>%s</th>"
                             % (esc(s), esc(self.status[s]["icon"]), esc(self.short_label(s)))
                             for s in self.status)
                 + "</tr>")
        for name in groups:
            c = Counter(r["status"] for r in reqs if self.group_of(r) == name)
            g.append(f"<tr><td>{esc(name)}</td><td>{sum(c.values())}</td>"
                     + "".join(f"<td>{c.get(s, 0)}</td>" for s in self.status) + "</tr>")
        g.append(f"<tr><th>{esc(L['total'])}</th><th>{n}</th>"
                 + "".join(f"<th>{by_status.get(s, 0)}</th>" for s in self.status) + "</tr></table>")
        cards.append("<section>" + "".join(g) + "</section>")
        if self.cfg.get("findings"):
            cards.append("<section class='find'><p class='cap'>" + esc(L["findings"]) + "</p><ul>"
                         + "".join(f"<li>{f}</li>" for f in self.cfg["findings"]) + "</ul></section>")
        o.append(f"<h2>{self.sec()} {esc(L['summary'])}</h2>")
        o.append("<div class='row'>" + "".join(cards) + "</div>")

        attention = self.rules.get("attention", [])
        if attention:
            extra = [c for c in self.columns
                     if c["key"] in self.rules.get("attention_columns", ["qa", "note"])]
            o.append(f"<h2>{self.sec()} {esc(L['attention'])}</h2>"
                     "<div class='scroll'><table><tr><th>Req ID</th>"
                     f"<th>{esc(L['status'])}</th><th>{esc(L['req'])}</th>" + "".join(f"<th>{esc(c['label'])}</th>" for c in extra) + "</tr>")
            for r in reqs:
                if r["status"] in attention:
                    o.append(f"<tr><td class='nw'>{esc(r['id'])}</td>"
                             f"<td class='nw'>{esc(self.status[r['status']]['icon'])} {esc(r['status'])}</td>"
                             f"<td>{esc(r.get('req'))}</td>"
                             + "".join(f"<td>{esc(r.get(c['key']))}</td>" for c in extra) + "</tr>")
            o.append("</table></div>")

        o.append(f"<h2>{self.sec()} {esc(L['table'])}</h2>"
                 f"<input id='q' placeholder='{esc(L['filter'])}' oninput='F()'>"
                 "<span class='count'><b id='n'>%d</b> %s</span>"
                 "<script>const TOTAL=%d;function F(){"
                 "const q=document.getElementById('q').value.toLowerCase();"
                 "const fs=[...document.querySelectorAll('#t tr.f [data-i]')]"
                 ".map(e=>[+e.dataset.i,e.value.trim().toLowerCase()]).filter(x=>x[1]);"
                 "let n=0;for(const tr of document.querySelectorAll('#t tr[data-r]')){"
                 "let m=tr.dataset.r.toLowerCase().includes(q);"
                 "if(m)for(const[i,v]of fs){"
                 "if(!tr.cells[i].textContent.toLowerCase().includes(v)){m=false;break}}"
                 "tr.style.display=m?'':'none';n+=m}"
                 "document.getElementById('n').textContent=n+'/'+TOTAL;"
                 "document.querySelector('.tw').scrollTop=0}</script>" % (n, esc(L["rows"]), n))
        head = []
        for c in self.columns:
            cw = c.get("width")
            style = " style='width:%s'" % cw if cw else ""
            head.append("<th%s>%s</th>" % (style, esc(c["label"])))
        o.append("<div class='tw'><table id='t'><tr>" + "".join(head) + "</tr>"
                 + self.filter_row(reqs))
        for r in reqs:
            cells = "".join(self.cell(r, c, ev_by_req, ev_caption, ev_findings) for c in self.columns)
            blob = html.escape(" ".join(str(r.get(c["key"], "") or "") for c in self.columns)
                               + " " + r["status"] + " " + (r.get("_e2e") or ""), quote=True)
            o.append(f'<tr data-r="{blob}">{cells}</tr>')
        o.append("</table></div></main>")

        (self.root / "REPORT.html").write_text("\n".join(o), encoding="utf-8")
        if self.cfg.get("emit", {}).get("goalrun_reqs"):
            (self.root / "reqs.txt").write_text(
                "".join(f"{r['id']}: [{r['status']}] {r.get('req', '')}"
                        + (f" (src: {r['src']})" if r.get("src") else "") + "\n" for r in reqs),
                encoding="utf-8")
        print(f"{n} reqs · status={dict(by_status)} · evidence={shown}/{n} SHOWN"
              + (f" · e2e={dict(e2e_count)}" if e2e else ""))


REQ_LINE = re.compile(r"^(?P<id>\S+):\s*\[(?P<status>[A-Z_]+)\]\s*(?P<req>.*?)"
                      r"(?:\s*\(src:\s*(?P<src>.*)\))?\s*$")


def import_reqs_txt(src, out):
    """Flat 'ID: [STATUS] requirement (src: ...)' lines -> reqs jsonl. No AI needed."""
    if out.exists():
        die(f"{out} already exists — delete it first or import into a fresh dir")
    rows = []
    for n, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        m = REQ_LINE.match(line.strip())
        if not m:
            die(f"{src.name}:{n}: cannot parse: {line.strip()[:80]}")
        rows.append({k: v for k, v in m.groupdict().items() if v})
    if not rows:
        die(f"{src}: no requirements found")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"imported {len(rows)} reqs from {src} -> {out}")


def main():
    args = sys.argv[1:]
    root = Path(args[0] if args and not args[0].startswith("-") else ".").resolve()
    if "--from-reqs" in args:
        src = Path(args[args.index("--from-reqs") + 1]).resolve()
        import_reqs_txt(src, root / "data" / "reqs-00-imported.jsonl")
    Report(root).build()


if __name__ == "__main__":
    main()
