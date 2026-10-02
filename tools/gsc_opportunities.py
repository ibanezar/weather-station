#!/usr/bin/env python3
"""
tools/gsc_opportunities.py — iz izvoza Google Search Console (Učinkovitost →
Izvozi → CSV/ZIP) izlušči poizvedbe, pri katerih je največ za pridobiti.

Ročno orodje (ni v workflowu — repozitorij nima dostopa do GSC). Sprejme ZIP
izvoza ali mapo z razpakiranimi CSV-ji ali sam `Queries.csv` / `Poizvedbe.csv`.
Glave so v jeziku vmesnika, zato se stolpci berejo po VRSTNEM REDU, ki je pri
GSC izvozu vedno: poizvedba, kliki, prikazi, CTR, položaj.

Tri skupine:
  - »na pragu«: položaj 4–20 in vsaj --min-impr prikazov (premik na 1. stran
    oz. v prve tri prinese največ klikov);
  - »nizek CTR«: CTR pod polovico pričakovanega za ta položaj (naslov/opis ne
    vabita — popravek naslova je poceni);
  - »brez strani«: poizvedbe, ki se ne ujemajo z nobeno ključno besedo v
    naslovih strani (kandidati za novo stran ali razdelek).

Usage:
    python3 tools/gsc_opportunities.py IZVOZ.zip [--min-impr 50] [--out docs/gsc-YYYY-MM.md]
"""
import csv
import glob
import io
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Pričakovani CTR po položaju (zaokrožena javna krivulja organskih rezultatov).
EXPECTED_CTR = {1: 0.28, 2: 0.15, 3: 0.10, 4: 0.07, 5: 0.05, 6: 0.04, 7: 0.03,
                8: 0.025, 9: 0.02, 10: 0.018}


def expected_ctr(pos):
    p = max(1, int(round(pos)))
    return EXPECTED_CTR.get(p, 0.01 if p <= 20 else 0.005)


def _num(s):
    s = (s or "").strip().replace(" ", "").replace("%", "")
    if not s:
        return 0.0
    # Slovenski izvoz: 1.234,5 → 1234.5; angleški: 1,234.5 → 1234.5
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)


def read_queries_csv(text):
    rows = []
    reader = csv.reader(io.StringIO(text))
    next(reader, None)  # glava
    for r in reader:
        if len(r) < 5 or not r[0].strip():
            continue
        q, clicks, impr, ctr, pos = r[0].strip(), _num(r[1]), _num(r[2]), _num(r[3]), _num(r[4])
        # CTR v izvozu je odstotek (»3,5 %«) — pretvori v delež.
        rows.append({"q": q, "clicks": int(clicks), "impr": int(impr),
                     "ctr": ctr / 100 if ctr > 1 or "%" in r[3] else ctr, "pos": pos})
    return rows


def load(path):
    names = ("queries.csv", "poizvedbe.csv")
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if os.path.basename(n).lower() in names:
                    return read_queries_csv(z.read(n).decode("utf-8-sig"))
        raise SystemExit("V ZIP-u ni Queries.csv / Poizvedbe.csv")
    if os.path.isdir(path):
        for n in glob.glob(os.path.join(path, "*.csv")):
            if os.path.basename(n).lower() in names:
                path = n
                break
        else:
            raise SystemExit("V mapi ni Queries.csv / Poizvedbe.csv")
    with open(path, encoding="utf-8-sig") as f:
        return read_queries_csv(f.read())


def site_titles():
    """Naslovi vseh strani (h1 + <title>) — za »brez strani«."""
    words = set()
    for p in glob.glob(os.path.join(ROOT, "**", "index.html"), recursive=True):
        if "/vreme/20" in p or "/blog/" in p or "/i/" in p:
            continue
        try:
            h = open(p, encoding="utf-8").read(6000)
        except OSError:
            continue
        for m in re.findall(r"<title>(.*?)</title>|<h1[^>]*>(.*?)</h1>", h, re.S):
            t = " ".join(m).lower()
            words.update(w for w in re.findall(r"\w+", t) if len(w) > 3)
    return words


# Besede, ki so v skoraj vsakem naslovu in ne povedo, ali tema ima stran.
GENERIC = {"vreme", "vremenska", "napoved", "rečica", "rečici", "savinji", "danes", "jutri"}


def _stem(w):
    return w[:5]


def classify(rows, min_impr, titles=None):
    near, low_ctr, orphan = [], [], []
    stems = {_stem(w) for w in (titles or ())}
    for r in rows:
        if r["impr"] < min_impr:
            continue
        if 4 <= r["pos"] <= 20:
            near.append(r)
        if r["pos"] <= 10 and r["ctr"] < expected_ctr(r["pos"]) / 2:
            low_ctr.append(r)
        if titles is not None:
            ws = [w for w in re.findall(r"\w+", r["q"].lower())
                  if len(w) > 3 and w not in GENERIC]
            if ws and not any(_stem(w) in stems for w in ws):
                orphan.append(r)
    # Potencial: dodatni kliki, če bi CTR dosegel pričakovanega za položaj 3.
    for r in near:
        r["gain"] = max(0, round(r["impr"] * expected_ctr(3) - r["clicks"]))
    near.sort(key=lambda r: -r["gain"])
    low_ctr.sort(key=lambda r: -r["impr"])
    orphan.sort(key=lambda r: -r["impr"])
    return near, low_ctr, orphan


def report(near, low_ctr, orphan, limit=25):
    def tbl(rows, extra=None):
        out = ["| Poizvedba | Prikazi | Kliki | CTR | Položaj |" + (f" {extra[0]} |" if extra else ""),
               "|---|---:|---:|---:|---:|" + ("---:|" if extra else "")]
        for r in rows[:limit]:
            out.append(f"| {r['q']} | {r['impr']} | {r['clicks']} | {r['ctr'] * 100:.1f} % | "
                       f"{r['pos']:.1f} |" + (f" {r[extra[1]]} |" if extra else ""))
        return "\n".join(out) if rows else "_ni_"
    return "\n\n".join([
        "# Priložnosti iz Search Consolea",
        "## Na pragu (položaj 4–20)\nRazvrščeno po dodatnih klikih, če bi stran prišla na 3. mesto.",
        tbl(near, ("+kliki", "gain")),
        "## Nizek CTR (prva stran, CTR pod polovico pričakovanega)\nPopravek `<title>`/opisa.",
        tbl(low_ctr),
        "## Brez ustrezne strani\nPoizvedbe, katerih ključne besede ni v nobenem naslovu.",
        tbl(orphan),
    ]) + "\n"


def main():
    args = sys.argv[1:]
    if not args or args[0].startswith("-"):
        print(__doc__)
        sys.exit(2)
    min_impr = int(args[args.index("--min-impr") + 1]) if "--min-impr" in args else 50
    rows = load(args[0])
    near, low, orphan = classify(rows, min_impr, site_titles())
    md = report(near, low, orphan)
    if "--out" in args:
        out = args[args.index("--out") + 1]
        with open(out, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"✓ {out}")
    else:
        print(md)


if __name__ == "__main__":
    main()
