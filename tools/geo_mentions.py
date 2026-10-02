#!/usr/bin/env python3
"""
tools/geo_mentions.py — mesečni dnevnik omemb meteorec.si pri AI asistentih.

Pomočnik za ročni postopek iz docs/geo-prompt-panel.md (odgovorov asistentov ni
mogoče brati prek ključa-prostega API-ja, zato vprašanja postaviš sam):

  plan   [--month 2026-10]   katera vprašanja ta mesec (rotacija — v treh mesecih
                             pride na vrsto ves panel; isti id se ponavlja, da so
                             meseci primerljivi) in kontrolni seznam za vpis
  add    --assistant chatgpt --prompt vreme-recica-jutri --mentioned da
         [--competitors "ARSO,Windy"] [--context "…"] [--note "…"] [--date 2026-10-03]
                             doda vnos v data/geo-mentions.json (preveri id in asistenta)
  report                     delež omemb po mesecu in asistentu ter delež glasu
                             (share of voice) proti konkurenci

Panel (id-ji) se bere iz tabele v docs/geo-prompt-panel.md — en vir, ne kopija.
"""
import datetime
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL_MD = os.path.join(ROOT, "docs", "geo-prompt-panel.md")
DATA = os.path.join(ROOT, "data", "geo-mentions.json")
ASSISTANTS = ("chatgpt", "perplexity", "google-ai-overview", "claude")
CORE_ASSISTANTS = ASSISTANTS[:3]
PER_MONTH = 7
YES = {"da", "yes", "true", "1", "y"}
NO = {"ne", "no", "false", "0", "n"}


def panel():
    """[(id, vprašanje)] iz tabele v docs/geo-prompt-panel.md."""
    out = []
    for line in open(PANEL_MD, encoding="utf-8"):
        m = re.match(r"\|\s*`([a-z0-9-]+)`\s*\|\s*([^|]+?)\s*\|", line)
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def month_plan(month, items=None):
    """Rotacija: zaporedni bloki po PER_MONTH id-jev, ciklično po mesecih."""
    items = items or panel()
    y, m = int(month[:4]), int(month[5:7])
    k = (y * 12 + m) % max(1, -(-len(items) // PER_MONTH))
    start = k * PER_MONTH
    block = items[start:start + PER_MONTH]
    if len(block) < PER_MONTH:
        block += items[:PER_MONTH - len(block)]
    return block


def load():
    try:
        return json.load(open(DATA, encoding="utf-8"))
    except (OSError, ValueError):
        return []


def save(rows):
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
        f.write("\n")


def make_entry(assistant, prompt_id, mentioned, competitors="", context="", note="", date=None, ids=None):
    ids = ids if ids is not None else {i for i, _ in panel()}
    if assistant not in ASSISTANTS:
        raise ValueError(f"asistent mora biti eden od {', '.join(ASSISTANTS)}")
    if prompt_id not in ids:
        raise ValueError(f"neznan prompt_id {prompt_id!r} — glej docs/geo-prompt-panel.md")
    mv = str(mentioned).strip().lower()
    if mv not in YES | NO:
        raise ValueError("--mentioned mora biti da/ne")
    date = date or datetime.date.today().isoformat()
    datetime.date.fromisoformat(date)
    comps = [c.strip() for c in (competitors or "").split(",") if c.strip()]
    return {"date": date, "assistant": assistant, "prompt_id": prompt_id,
            "mentioned": mv in YES, "context": context, "competitors_mentioned": comps,
            "note": note}


def summarize(rows):
    """{mesec: {asistent: (omenjen, vseh)}}, Counter konkurence, delež glasu."""
    by = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    comp = Counter()
    for r in rows:
        cell = by[r["date"][:7]][r["assistant"]]
        cell[1] += 1
        cell[0] += 1 if r["mentioned"] else 0
        comp.update(r.get("competitors_mentioned") or [])
    ours = sum(1 for r in rows if r["mentioned"])
    total = ours + sum(comp.values())
    sov = ours / total if total else None
    return by, comp, sov


def cmd_plan(args):
    month = _arg(args, "--month") or datetime.date.today().strftime("%Y-%m")
    done = {(r["assistant"], r["prompt_id"]) for r in load() if r["date"].startswith(month)}
    print(f"# GEO panel — {month}\n")
    for pid, q in month_plan(month):
        marks = " ".join(f"[{'x' if (a, pid) in done else ' '}] {a}" for a in CORE_ASSISTANTS)
        print(f"- `{pid}` — {q}\n    {marks}")
    print("\nVpis: python3 tools/geo_mentions.py add --assistant chatgpt --prompt <id> --mentioned da|ne "
          "[--competitors \"ARSO,Windy\"] [--context \"…\"]")


def cmd_add(args):
    try:
        e = make_entry(_arg(args, "--assistant"), _arg(args, "--prompt"), _arg(args, "--mentioned"),
                       _arg(args, "--competitors") or "", _arg(args, "--context") or "",
                       _arg(args, "--note") or "", _arg(args, "--date"))
    except (ValueError, TypeError) as ex:
        sys.exit(f"✗ {ex}")
    rows = load()
    rows = [r for r in rows if not (r["date"] == e["date"] and r["assistant"] == e["assistant"]
                                    and r["prompt_id"] == e["prompt_id"])]
    rows.append(e)
    rows.sort(key=lambda r: (r["date"], r["assistant"], r["prompt_id"]))
    save(rows)
    print(f"✓ {e['date']} {e['assistant']} {e['prompt_id']}: {'omenjen' if e['mentioned'] else 'ni omenjen'}")


def cmd_report(_args):
    rows = load()
    if not rows:
        print("Ni še vnosov (data/geo-mentions.json je prazen) — začni s `plan`.")
        return
    by, comp, sov = summarize(rows)
    print("| Mesec | " + " | ".join(ASSISTANTS) + " |")
    print("|---|" + "---:|" * len(ASSISTANTS))
    for month in sorted(by):
        cells = []
        for a in ASSISTANTS:
            m, n = by[month].get(a, (0, 0))
            cells.append(f"{m}/{n}" if n else "—")
        print(f"| {month} | " + " | ".join(cells) + " |")
    if comp:
        print("\nKonkurenca: " + ", ".join(f"{c} {n}×" for c, n in comp.most_common()))
    if sov is not None:
        print(f"Delež glasu meteorec.si: {sov * 100:.0f} %")


def _arg(args, name):
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else ""
    {"plan": cmd_plan, "add": cmd_add, "report": cmd_report}.get(cmd, lambda _a: print(__doc__))(args[1:])


if __name__ == "__main__":
    main()
