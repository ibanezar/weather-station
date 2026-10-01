#!/usr/bin/env python3
"""
tools/measure_cron_throughput.py — koliko cron tekov GitHub res dostavi?

1. 10. 2026: pogosti workflowi (cron */15, */20, vsako uro) so dobili le ~6 tekov na
dan namesto 96/72/24 (toča-tracker 6,1/dan, retry-pages-deploy 5,9/dan,
prerender-current 5/dan), dnevni pa zamujajo 5-7 ur — GitHub je cron dogodke
očitno združeval v pakete na ~4 ure. To razloži, zakaj časovna vrata (6:00–8:00)
tiho zavračajo vsak tek. Skript to meri vsak dan, da je trend viden (ali se je
stanje popravilo, ko smo redčili urnike ali nastavili GH_DISPATCH_TOKEN).

Primerja pričakovano število tekov na dan (iz `schedule:` v workflowu) z dejanskim
(`gh api .../runs?event=schedule`) v zadnjih DAYS dneh in izpiše tabelo v
$GITHUB_STEP_SUMMARY (brez issue-ja: to je podatek za odločanje, ne alarm).

Usage:  python3 tools/measure_cron_throughput.py [--days 3]
Zahteva `gh` in GH_TOKEN (v workflowu je).
"""
import datetime
import glob
import json
import os
import re
import subprocess
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.environ.get("GITHUB_REPOSITORY", "ibanezar/weather-station")


def runs_per_day(cron):
    """Približno število sprožitev na dan za 5-poljni cron (dan v tednu/mesecu: povprečje)."""
    m, h, dom, mon, dow = cron.split()

    def count(field, lo, hi):
        total = 0
        for part in field.split(","):
            step = 1
            if "/" in part:
                part, st = part.split("/")
                step = int(st)
            if part == "*":
                a, b = lo, hi
            elif "-" in part:
                a, b = map(int, part.split("-"))
            else:
                a = b = int(part)
                if step != 1:
                    b = hi
            total += len(range(a, b + 1, step))
        return total

    n = count(m, 0, 59) * count(h, 0, 23)
    if dow != "*":
        n *= count(dow, 0, 6) / 7
    if dom != "*":
        n *= count(dom, 1, 31) / 30.4
    if mon != "*":
        n *= count(mon, 1, 12) / 12
    return n


def scheduled_workflows():
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml"))):
        d = yaml.safe_load(open(f, encoding="utf-8"))
        on = d.get(True) or d.get("on") or {}
        crons = [x["cron"] for x in (on.get("schedule") or [])] if isinstance(on, dict) else []
        if crons:
            out[os.path.basename(f)] = crons
    return out


def actual_runs(workflow, since):
    p = subprocess.run(
        ["gh", "api", "--paginate", f"repos/{REPO}/actions/workflows/{workflow}/runs?event=schedule&created=>={since}&per_page=100",
         "--jq", ".workflow_runs[].created_at"],
        capture_output=True, text=True)
    if p.returncode != 0:
        return None
    return len([l for l in p.stdout.split() if l])


def main():
    days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 3
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for wf, crons in scheduled_workflows().items():
        exp = sum(runs_per_day(c) for c in crons)
        act = actual_runs(wf, since)
        per_day = None if act is None else act / days
        rows.append((wf, exp, per_day))
    lines = [f"### Dostava GitHub cron tekov (zadnjih {days} dni)\n",
             "| Workflow | Pričakovano/dan | Dejansko/dan | Delež |", "|---|---|---|---|"]
    for wf, exp, act in sorted(rows, key=lambda r: -(r[1] - (r[2] or 0))):
        share = "—" if act is None or not exp else f"{round(100 * act / exp)} %"
        lines.append(f"| `{wf}` | {exp:.1f} | {'—' if act is None else f'{act:.1f}'} | {share} |")
    text = "\n".join(lines) + "\n"
    print(text)
    p = os.environ.get("GITHUB_STEP_SUMMARY")
    if p:
        with open(p, "a", encoding="utf-8") as f:
            f.write("\n" + text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
