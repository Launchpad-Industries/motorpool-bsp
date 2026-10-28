# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Validation report: official asset cards vs. specs calculated from the
linked MegaMek units. Writes a self-contained HTML page.

The official values come from the owner's spreadsheet (exported as TSV);
the report is for private use and is not stored in this repository."""

from __future__ import annotations

import csv
import html
import json
import re
from pathlib import Path

import yaml

from .derive import derive_vehicle
from .generate import default_skill
from .cost import cost
from .match import best_match
from .megamek import load_all, load_unit

ROOT = Path(__file__).resolve().parent.parent
FIELDS = [("mp", "MP"), ("tmm", "TMM"), ("range", "Range"), ("dmg", "Dmg"),
          ("skill", "Skill"), ("check", "Check"), ("thr", "Thr"),
          ("if", "IF"), ("cost", "Cost")]


def _card(r: dict) -> dict:
    ifm = re.search(r"IF(\d+)", r["specials"])
    return {"mp": f"{r['mp']}{r['mtype']}", "tmm": r["tmm"], "range": r["range"],
            "dmg": r["dmg"], "skill": r["skill"], "check": r["check"], "thr": r["thr"],
            "if": ifm.group(1) if ifm else "0",
            "cost": f"{r['costR']} ({r['costV']})" if r["costV"].strip() else r["costR"]}


def _calc(u, weapons) -> dict:
    sp = derive_vehicle(u, weapons)
    skill = default_skill(u)
    c = cost(sp.mp, sp.tmm, sp.damage, sp.range, skill, sp.check, sp.indirect, sp.specials)
    dmg = "-" if not sp.damage else (f"{sp.damage[0]}" if sp.damage[1] == 1 else f"{sp.damage[0]}x{sp.damage[1]}")
    return {"mp": f"{sp.mp}{sp.mode}", "tmm": str(sp.tmm),
            "range": "/".join(map(str, sp.range)) if sp.range else "-",
            "dmg": dmg, "skill": str(skill), "check": str(sp.check),
            "thr": str(sp.threshold), "if": str(sp.indirect),
            "cost": f"{c['regular']} ({c['veteran']})",
            "_cost": c["regular"]}


def build(official_tsv: Path, mm_root: Path, out: Path):
    weapons = json.loads((ROOT / "cache" / "weapons.json").read_text())
    links = yaml.safe_load((ROOT / "data" / "card_links.yaml").read_text())
    pool = [u for u in load_all(mm_root, folders=("vehicles",)) if u.unit_type in ("Tank", "VTOL")]
    rows, stats = [], {k: [0, 0] for k, _ in FIELDS}
    cost_err = []
    for r in csv.DictReader(open(official_tsv, encoding="utf-8"), delimiter="\t"):
        if r["type"] != "Vehicle":
            continue
        key = f"{r['name']}|{r['variant']}"
        path = links["links"].get(key) or links["review"].get(key)
        u = load_unit(mm_root / path) if path else best_match(r, pool).unit
        if u is None or u.unit_type not in ("Tank", "VTOL"):
            continue
        card, calc = _card(r), _calc(u, weapons)
        diffs = []
        for k, _ in FIELDS:
            if card[k] in ("-", "", "N/A") and calc[k] in ("-", "0"):
                continue
            same = card[k].replace(" ", "") == calc[k].replace(" ", "")
            if k == "dmg":
                same = card[k].replace("x1", "") == calc[k]
            stats[k][1] += 1
            stats[k][0] += same
            if not same:
                diffs.append(k)
        if r["costR"].strip().isdigit():
            cost_err.append(calc["_cost"] - int(r["costR"]))
        rows.append((r, u, card, calc, diffs, key in links["review"]))
    rows.sort(key=lambda t: (-len(t[4]), t[0]["name"]))
    out.write_text(_html(rows, stats, cost_err), encoding="utf-8")
    return stats, cost_err


def _html(rows, stats, cost_err) -> str:
    e = sorted(abs(x) for x in cost_err)
    within = lambda n: round(100 * sum(1 for x in e if x <= n) / len(e))
    summary = "".join(
        f"<div class=stat><b>{round(100 * a / b) if b else 0}%</b><span>{lbl}</span><small>{a}/{b}</small></div>"
        for (k, lbl), (a, b) in ((f, stats[f[0]]) for f in FIELDS))
    trs = []
    for r, u, card, calc, diffs, review in rows:
        cells = []
        for k, _ in FIELDS:
            cls = " class=diff" if k in diffs else ""
            val = html.escape(card[k]) if k not in diffs else \
                f"{html.escape(card[k])}<em>{html.escape(calc[k])}</em>"
            cells.append(f"<td{cls}>{val}</td>")
        flag = " <span class=tag>link to review</span>" if review else ""
        trs.append(f"<tr><td class=name>{html.escape(r['name'])}<small>{html.escape(r['variant'])}"
                   f" &middot; {html.escape(u.full_name)}</small>{flag}</td>{''.join(cells)}</tr>")
    head = "".join(f"<th>{lbl}</th>" for _, lbl in FIELDS)
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Official vs Calculated</title>
<style>
:root{{--bg:#f7f6f2;--fg:#1d1d1b;--mut:#6b6a64;--line:#dddbd3;--hi:#fff1d6;--hi2:#a5520b;--card:#fff}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#151513;--fg:#ecebe6;--mut:#9a988f;--line:#33322e;--hi:#3a2a10;--hi2:#f0a659;--card:#1d1d1b}}}}
:root[data-theme=dark]{{--bg:#151513;--fg:#ecebe6;--mut:#9a988f;--line:#33322e;--hi:#3a2a10;--hi2:#f0a659;--card:#1d1d1b}}
body{{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0;padding:24px 16px}}
main{{max-width:1150px;margin:auto}} h1{{font-size:22px;margin:0 0 4px}} p{{color:var(--mut);margin:0 0 18px;max-width:70ch}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(105px,1fr));gap:8px;margin-bottom:10px}}
.stat{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px}}
.stat b{{display:block;font-size:22px;font-variant-numeric:tabular-nums}} .stat span{{display:block}} .stat small{{color:var(--mut)}}
.wrap{{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:8px}}
table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}}
th,td{{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap;vertical-align:top}}
th{{position:sticky;top:0;background:var(--card);font-weight:600}}
td.name{{white-space:normal;min-width:200px}} td.name small{{display:block;color:var(--mut)}}
td.diff{{background:var(--hi)}} td em{{display:block;font-style:normal;color:var(--hi2);font-weight:600}}
.tag{{font-size:11px;border:1px solid var(--hi2);color:var(--hi2);border-radius:4px;padding:0 4px}}
.note{{margin:10px 0 18px;color:var(--mut)}}
</style></head><body><main>
<h1>Official vs calculated asset specs</h1>
<p>Each official vehicle card compared with the spec the generator calculates from its MegaMek unit.
Highlighted cells differ: the printed value is on top, the calculated value below in orange. Rows with the most differences come first.</p>
<div class=stats>{summary}</div>
<div class=note>Cost: average error {sum(e)/len(e):.1f} points; within 1 point {within(1)}%, within 2 {within(2)}%, within 3 {within(3)}%.
Range and damage reflect judgment calls on the official cards, so they match least often.</div>
<div class=wrap><table><thead><tr><th>Card &middot; MegaMek unit</th>{head}</tr></thead><tbody>
{''.join(trs)}</tbody></table></div>
<p style="margin-top:16px">Unofficial fan tool. Calculated specs derived from MegaMek Data (CC BY-NC-SA 4.0). Official values &copy; The Topps Company, Inc.; for private comparison only.</p>
</main></body></html>"""


if __name__ == "__main__":
    import sys
    s, ce = build(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
    print({k: f"{a}/{b}" for k, (a, b) in s.items()})
