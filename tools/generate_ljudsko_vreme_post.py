#!/usr/bin/env python3
"""
tools/generate_ljudsko_vreme_post.py -- »Ali pregovori o svetnikih držijo? Deset testov na postaji« (18. 11. 2026).

Ročno napisan podatkovni članek. Pregovori so iz zbirke I. Šašelj, »Svetniki in svetnice v slovenskih pregovorih in
vremenskih prislovicah«, Etnolog 10-11 (1937-1939, Etnografski muzej); besedilo je prepis iz skeniranega dokumenta
(OCR razmaknjene črke so popravljene, pravopis izvirnika je ohranjen). Meritve: history.json (postaja IREICA1; samo
zunanja polja tempAvg/tempLow/tempHigh/precipTotal/solarHigh, dnevi z src == "era5" so izpuščeni).

Pravila preverjanja so določena PRED pogledom na rezultate (glej `TESTS`); vsak preizkus teče enkrat, poročani so vsi.
Zadetek = smer se ujema; odstopanja so merjena od povprečja istih dni v analiziranih letih (ne od uradne norme).
Verjetnost p je dvostranski binomski preizkus proti kovancu (50 %). Postaja snega ne meri, zato pregovori o snegu niso
preverjeni. Lenartov pregovor je že obdelan v blog/lenartovo-pregovor-vreme-do-bozica.html (druga definicija), zato ga
tu ni. Notranjih meritev članek ne uporablja (velja pravilo iz CLAUDE.md).

Članek je posnetek na dan objave (do Katarine, 25. 11. 2026): trditve varujejo assert-i; če se podatki osvežijo in trditev
ne drži več, generator pade -- besedilo je treba pregledati, ne zaobiti asserta. Lektura (`lektura.yml`) je izklopljena
od 2. 10. 2026: do ponovnega vklopa ostane slogovni pregled po docs/slog-pisanja.md in tools/lektura_scan.py.

Usage:
    python3 tools/generate_ljudsko_vreme_post.py [--dry-run] [--text] [--wire] [--force] [--allow-date]
"""
import datetime
import json
import os
import re
import statistics as st
import sys
from math import comb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
HISTORY = os.path.join(ROOT, "history.json")
SLUG = "pregovori-o-svetnikih-test-postaja-1118"
TEXT_OUT = os.path.join(ROOT, "docs", "lektura-ljudsko-vreme.txt")
SNAPSHOT_FIRST, SNAPSHOT_LAST = datetime.date(2026, 11, 18), datetime.date(2026, 11, 24)
NBSP = " "
D = datetime.date


# ───────────────────────── zapis ─────────────────────────

def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",").replace("-", "–")


def temp(x, d=1):
    return f"{num(x, d)}{NBSP}°C"


def sgn(x, d=1):
    return ("+" if x > 0 else "–" if x < 0 else "") + num(abs(x), d)


def dm(d):
    return f"{d.day}. {d.month}."


def nb(h):                                    # »0 °C«, »38 %« se ne smeta prelomiti čez vrstico
    return re.sub(r"(\d) (°C|%|mm|W/m²)", lambda m: m.group(1) + NBSP + m.group(2), h)


# ───────────────────────── podatki in preizkusi ─────────────────────────

def load():
    H = json.load(open(HISTORY, encoding="utf-8"))
    H = H.get("days", H)
    return {D.fromisoformat(k): v for k, v in H.items() if v.get("src") != "era5"}


def p_two(n, k):
    """Dvostranska verjetnost, da kovanec (50 %) da tako izrazit izid: min(1, 2 * min(P(X>=k), P(X<=k)))."""
    ge = sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n
    le = sum(comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * min(ge, le))


class Data:
    def __init__(self, days):
        self.d = days

    def g(self, day, f):
        v = self.d.get(day)
        return None if v is None else v.get(f)

    @staticmethod
    def rng(a, b):
        x = a
        while x <= b:
            yield x
            x += datetime.timedelta(1)

    def pmean(self, a, b, f="tempAvg", minfrac=0.8):
        L = [self.g(x, f) for x in self.rng(a, b)]
        v = [x for x in L if x is not None]
        return sum(v) / len(v) if v and len(v) >= minfrac * len(L) else None

    def calday_clim(self, m, dd, f="tempAvg", w=3, y0=2019, y1=2026):
        vals = []
        for y in range(y0, y1 + 1):
            c = D(y, m, dd)
            for x in self.rng(c - datetime.timedelta(w), c + datetime.timedelta(w)):
                v = self.g(x, f)
                if v is not None:
                    vals.append(v)
        return sum(vals) / len(vals)


def sign(x, eps=0.05):
    return 0 if abs(x) < eps else (1 if x > 0 else -1)


def analyse(days):
    A = Data(days)
    R = {}
    # zime (dec-feb), ki se začnejo decembra 2019 ... 2025
    W = {y: A.pmean(D(y, 12, 1), D(y + 1, 2, 28 if (y + 1) % 4 else 29)) for y in range(2019, 2026)}
    assert all(v is not None for v in W.values())
    Wm = st.mean(W.values())
    R["W"], R["Wm"] = W, Wm

    # mediana sevanja 1.-20. 11. (merilo »sončno«); sevanje je v podatkih od 2021
    sol = [A.g(x, "solarHigh") for y in range(2019, 2026) for x in A.rng(D(y, 11, 1), D(y, 11, 20))]
    med_nov = st.median([v for v in sol if v is not None])
    R["med_nov"] = med_nov

    # S1 Martin: sončen => huda zima; oblačen => lepa zima
    rows = []
    for y in range(2019, 2026):
        s = A.g(D(y, 11, 11), "solarHigh")
        if s is None:
            continue
        sunny = s >= med_nov
        dev = W[y] - Wm
        hit = (sunny and dev < 0) or ((not sunny) and dev > 0)
        rows.append(dict(y=y, sun=s, sunny=sunny, dev=dev, hit=hit))
    R["S1"] = rows

    # S2 Martin lepo => v treh dneh grdo; osnova = vsi lepi dnevi 1.-27. 11.
    def lep(x):
        p, s = A.g(x, "precipTotal"), A.g(x, "solarHigh")
        return p is not None and s is not None and p < 0.2 and s >= med_nov

    def grdo3(x):
        L = [A.g(x + datetime.timedelta(i), "precipTotal") for i in (1, 2, 3)]
        return None if any(l is None for l in L) else any(l >= 0.2 for l in L)
    base = [grdo3(x) for y in range(2019, 2026) for x in A.rng(D(y, 11, 1), D(y, 11, 27)) if lep(x) and x != D(y, 11, 11)]
    base = [b for b in base if b is not None]
    R["S2"] = dict(base_n=len(base), base_k=sum(base),
                   martin=[(y, grdo3(D(y, 11, 11))) for y in range(2019, 2026) if lep(D(y, 11, 11))])

    # S3 vsi sveti: mraz 1. 11. => toplo Martinovo
    lows = {y: A.g(D(y, 11, 1), "tempLow") for y in range(2019, 2026)}
    lows = {y: v for y, v in lows.items() if v is not None}
    R["S3"] = dict(lows=lows, frost=[y for y, v in lows.items() if v <= 0])

    # S4 zmrzal pred Martinom (1.-10. 11., najnižja <= 0 °C) => povodenj pred božičem (padavine 1.-24. 12. nad mediano let)
    rain = {}
    for y in range(2019, 2026):
        v = A.pmean(D(y, 12, 1), D(y, 12, 24), "precipTotal", minfrac=0.9)
        rain[y] = None if v is None else v * 24
    rows = []
    for y in range(2020, 2026):
        lw = [A.g(x, "tempLow") for x in A.rng(D(y, 11, 1), D(y, 11, 10))]
        lw = [l for l in lw if l is not None]
        assert len(lw) >= 8, y
        rows.append(dict(y=y, minlow=min(lw), frost=min(lw) <= 0, rain=rain[y]))
    med_rain = st.median(r["rain"] for r in rows)
    for r in rows:
        r["wet"] = r["rain"] > med_rain
        r["hit"] = (r["frost"] and r["wet"]) or ((not r["frost"]) and (not r["wet"]))
    R["S4"], R["S4_med"] = rows, med_rain

    # S5 led na Martina (najnižja <= 0 °C) => blato o božiču (24.-26. 12.: povprečje > 0 °C in padavine >= 0,2 mm)
    rows = []
    for y in range(2019, 2026):
        lo = A.g(D(y, 11, 11), "tempLow")
        L = [(A.g(x, "tempAvg"), A.g(x, "precipTotal")) for x in A.rng(D(y, 12, 24), D(y, 12, 26))]
        if lo is None or any(a is None or b is None for a, b in L):
            continue
        rows.append(dict(y=y, low=lo, ice=lo <= 0, mud=any(a > 0 and b >= 0.2 for a, b in L)))
    R["S5"] = rows

    # S7 Katarina (25. 11.) => januar: predznak odstopanja povprečne temperature dneva = predznak odstopanja januarja
    jan = {y: A.pmean(D(y + 1, 1, 1), D(y + 1, 1, 31)) for y in range(2019, 2026)}
    jm = st.mean(jan.values())
    cl = A.calday_clim(11, 25)
    rows = []
    for y in range(2019, 2026):
        a = A.g(D(y, 11, 25), "tempAvg")
        da, dj = a - cl, jan[y] - jm
        rows.append(dict(y=y, da=da, dj=dj, hit=sign(da) == sign(dj) and sign(da) != 0))
    R["S7"] = rows

    # S8 Andrejev mraz (najnižja 30. 11. <= 0 °C) => zima hladnejša od povprečja; brez mraza => toplejša
    rows = []
    for y in range(2019, 2026):
        lo = A.g(D(y, 11, 30), "tempLow")
        dev = W[y] - Wm
        frost = lo <= 0
        rows.append(dict(y=y, low=lo, frost=frost, dev=dev, w=W[y], hit=(frost and dev < 0) or ((not frost) and dev >= 0)))
    R["S8"] = rows

    # S9 Lucija: 13.-24. 12. => meseci naslednjega leta (13. -> januar ... 24. -> december)
    Ym = {}
    for y in range(2020, 2027):
        for m in range(1, 13):
            a = D(y, m, 1)
            b = D(y + (m == 12), (m % 12) + 1, 1) - datetime.timedelta(1)
            if b > max(days):
                continue
            Ym[(y, m)] = A.pmean(a, b)
    mclim = {m: st.mean(Ym[(y, m)] for y in range(2020, 2027) if Ym.get((y, m)) is not None) for m in range(1, 13)}
    n = k = total = 0
    for y in range(2019, 2026):
        for i in range(12):
            day = D(y, 12, 13 + i)
            a, mm = A.g(day, "tempAvg"), Ym.get((y + 1, i + 1))
            if a is None or mm is None:
                continue
            da, dmo = a - A.calday_clim(12, 13 + i), mm - mclim[i + 1]
            total += 1
            if sign(da) == 0 or sign(dmo) == 0:          # odstopanje pod 0,05 °C: ni razlike, primer se ne šteje
                continue
            n += 1
            k += sign(da) == sign(dmo)
    R["S9"] = dict(n=n, k=k, total=total)

    # S10 svečnica (2. 2.) jasna (sevanje >= mediana 1.-20. 2.) => zima še dolgo trpi (3. 2.-15. 3. hladnejše); S11 topla svečnica => mraz po njej
    sf = [A.g(x, "solarHigh") for y in range(2020, 2027) for x in A.rng(D(y, 2, 1), D(y, 2, 20))]
    med_feb = st.median([v for v in sf if v is not None])
    after = {y: A.pmean(D(y, 2, 3), D(y, 3, 15)) for y in range(2020, 2027)}
    am = st.mean(v for v in after.values() if v is not None)
    clc = A.calday_clim(2, 2)
    rows10, rows11 = [], []
    for y in range(2020, 2027):
        s, a = A.g(D(y, 2, 2), "solarHigh"), A.g(D(y, 2, 2), "tempAvg")
        dev = after[y] - am
        if s is not None:
            rows10.append(dict(y=y, sun=s, clear=s >= med_feb, dev=dev))
        da = a - clc
        rows11.append(dict(y=y, da=da, dev=dev, hit=sign(da) == -sign(dev) and sign(da) != 0, skip=sign(da) == 0 or sign(dev) == 0))
    R["S10"], R["S11"], R["med_feb"] = rows10, rows11, med_feb
    return R


# ───────────────────────── besedilo ─────────────────────────

STYLE = """<style>
.vs-tbl{overflow-x:auto;max-width:100%;margin:1rem 0}
.vs-tbl table{border-collapse:collapse;width:100%;font-size:.86rem}
.vs-tbl th,.vs-tbl td{padding:.42rem .5rem;text-align:right;border-bottom:1px solid var(--border)}
.vs-tbl td{white-space:nowrap}
.vs-tbl th{vertical-align:bottom;line-height:1.3;color:var(--muted);font-weight:600;font-size:.76rem}
.vs-tbl th:first-child,.vs-tbl td:first-child{text-align:left}
.vs-tbl td.pz,.vs-tbl th.pz{text-align:left;white-space:normal;min-width:15rem}
.vs-note{color:var(--muted);font-size:.82rem;line-height:1.5;margin:-.4rem 0 1.2rem}
.pz-q{font-style:italic}
.post-body h3{font-family:'Space Grotesk',sans-serif;font-size:1.05rem;margin:1.6rem 0 .4rem}
</style>"""


def table(head, rows, cap="", note="", pzcol=None):
    th = "".join(f'<th{" class=pz" if i == pzcol else ""}>{h}</th>' for i, h in enumerate(head))
    body = "".join("<tr>" + "".join(f'<td{" class=pz" if i == pzcol else ""}>{c}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
    return (f'<div class="vs-tbl" tabindex="0" role="region" aria-label="{cap}"><table><thead><tr>{th}</tr></thead>'
            f'<tbody>{body}</tbody></table></div>' + (f'<p class="vs-note">{note}</p>' if note else ""))


def yes(b):
    return "da" if b else "ne"


def build_article(days, R):
    last = max(days)
    assert SNAPSHOT_FIRST - datetime.timedelta(3) <= last < D(2026, 11, 25), last   # posnetek pred Katarino

    # --- trditve članka: če podatki tega ne kažejo več, generator pade ---
    s1, s4, s7, s8, s9 = R["S1"], R["S4"], R["S7"], R["S8"], R["S9"]
    assert [r["y"] for r in s1] == [2021, 2022, 2023, 2024, 2025] and sum(r["hit"] for r in s1) == 2
    assert len(s7) == 7 and sum(r["hit"] for r in s7) == 4
    assert len(s8) == 7 and sum(r["hit"] for r in s8) == 6 and [r["y"] for r in s8 if r["frost"]] == [2020, 2021, 2023, 2024, 2025]
    assert (s9["n"], s9["k"], s9["total"]) == (77, 33, 82), s9
    assert [r["y"] for r in s4 if r["frost"]] == [2020, 2021, 2024, 2025]
    assert sum(r["hit"] for r in s4) == 1 and [r["y"] for r in s4 if r["hit"]] == [2020]
    assert max(r["rain"] for r in s4 if r["frost"]) < min(r["rain"] for r in s4 if not r["frost"])
    assert R["S2"]["base_n"] == 20 and R["S2"]["base_k"] == 18 and len(R["S2"]["martin"]) == 1
    assert R["S3"]["frost"] == [] and len(R["S3"]["lows"]) == 6 and min(R["S3"]["lows"].values()) == 3.5
    s5 = R["S5"]
    assert [r["y"] for r in s5 if r["ice"]] == [2021, 2025] and all(r["mud"] for r in s5 if r["ice"]) and sum(r["mud"] for r in s5) == 4
    s10 = R["S10"]
    assert [r["y"] for r in s10 if r["clear"]] == [2024] and len(s10) == 5 and s10[2]["y"] == 2024 and s10[2]["dev"] == max(r["dev"] for r in s10)
    s11 = [r for r in R["S11"] if not r["skip"]]
    assert len(s11) == 6 and sum(r["hit"] for r in s11) == 2, (len(s11), sum(r["hit"] for r in s11))

    # --- letošnje stanje (samo meritve do `last`) ---
    t26 = days
    mart = t26[D(2026, 11, 11)]
    assert mart["solarHigh"] < R["med_nov"] and mart["tempLow"] > 0
    pre = [(t26[x]["tempLow"], x) for x in Data.rng(D(2026, 11, 1), D(2026, 11, 10))]
    pre_min = min(pre)
    assert pre_min == (-1.7, D(2026, 11, 9)), pre_min
    allsaints = t26[D(2026, 11, 1)]["tempLow"]
    assert allsaints == 4.8

    # verjetnost, da vsaj en od šestih preizkusov po naključju doseže p kot najboljši (S4/S8 sta enaka ali slabša)
    p4, p8 = p_two(len(s4), sum(r["hit"] for r in s4)), p_two(len(s8), sum(r["hit"] for r in s8))
    p_any = 1 - (1 - min(p4, p8)) ** 6

    # ---------- tabele ----------
    def tb_overview():
        n1, k1 = len(s1), sum(r["hit"] for r in s1)
        n7, k7 = len(s7), sum(r["hit"] for r in s7)
        n8, k8 = len(s8), sum(r["hit"] for r in s8)
        n4, k4 = len(s4), sum(r["hit"] for r in s4)
        n11, k11 = len(s11), sum(r["hit"] for r in s11)
        rows = [
            ('<span class="pz-q">»Andreja mraz – zima železna rebra.«</span> (30. 11.)', f"{k8} od {n8}", f"se je ujel, razlika majhna (p = {num(p8, 2)})"),
            ('<span class="pz-q">»Če pred Martinom zmrzuje, je pred božičem povodenj.«</span>', f"{k4} od {n4}", "brez zveze, če kaj, obratno"),
            ('<span class="pz-q">»Kakršni so dnevi od Lucije do božiča, taki bodo meseci v prihodnjem letu.«</span>', f"{s9['k']} od {s9['n']}", f"brez zveze (p = {num(p_two(s9['n'], s9['k']), 2)})"),
            ('<span class="pz-q">»Sv. Katarine dan ne laže, če po sebi prosincu vreme kaže.«</span>', f"{k7} od {n7}", f"brez zveze (p = {num(p_two(n7, k7), 2)})"),
            ('<span class="pz-q">»Če Martin sonce ima, pride rada huda zima.«</span> in obratno za oblačen dan', f"{k1} od {n1}", f"brez zveze (p = {num(p_two(n1, k1), 2)})"),
            ('<span class="pz-q">»Topla svečnica sneg in mraz prinese, mrzla pa oba odžene.«</span>', f"{k11} od {n11}", f"brez zveze (p = {num(p_two(n11, k11), 2)})"),
            ('<span class="pz-q">»Ako je na Martinje lepo, bo za tri dni grdo.«</span>', "–", "ni mogoče preveriti: po lepem dnevu pride dež tako ali tako"),
            ('<span class="pz-q">»Vseh svetnikov mraz – o Martinju topel čas.«</span>', "–", "ni mogoče preveriti: na vse svete mraza še ni bilo"),
            ('<span class="pz-q">»Če Martinova gos po ledu plazi, o božiču navadno po blatu gazi.«</span>', "–", "ni mogoče preveriti: led na Martinovo samo dvakrat"),
            ('<span class="pz-q">»Če svečnica jasno zdani, zima še dolgo trpi.«</span>', "–", "ni mogoče preveriti: samo ena jasna svečnica"),
        ]
        return table(["Pregovor", "Zadetkov", "Sklep"], rows, cap="Pregled desetih pregovorov", pzcol=0,
                     note="Zadetek pomeni, da se smer napovedi ujema z meritvijo. Verjetnost p pove, kako pogosto bi tako izrazit izid v katero koli smer dal navaden kovanec.")

    def tb_andrej():
        rows = [(str(r["y"]) + "/" + str((r["y"] + 1) % 100).zfill(2), num(r["low"]), "mraz" if r["frost"] else "brez mraza", num(r["w"]), sgn(r["dev"]),
                 "da" if r["hit"] else "ne") for r in s8]
        return table(["Zima", "Najnižja 30. 11. (°C)", "Andrej", "Povprečje dec–feb (°C)", "Odstopanje (°C)", "Zadetek"], rows,
                     cap="Andrejev mraz in zima po njem",
                     note="Zima je od 1. decembra do konca februarja. Odstopanje je od povprečja vseh sedmih zim.")

    def tb_martin_zmrzal():
        rows = [(str(r["y"]), num(r["minlow"]), "da" if r["frost"] else "ne", num(r["rain"], 0), "da" if r["wet"] else "ne") for r in s4]
        return table(["Leto", "Najnižja 1.–10. 11. (°C)", "Zmrzal pred Martinom", "Padavine 1.–24. 12. (mm)", "Nad mediano"], rows,
                     cap="Zmrzal pred Martinom in padavine pred božičem",
                     note=f"Mediana šestih let je {num(R['S4_med'], 0)} mm. Za leto 2019 podatkov za prvih deset dni novembra ni dovolj.")

    def tb_martin_sonce():
        rows = [(str(r["y"]), num(r["sun"], 0), "sončen" if r["sunny"] else "oblačen", sgn(r["dev"]), "da" if r["hit"] else "ne") for r in s1]
        return table(["Leto", "Največje sevanje 11. 11. (W/m²)", "Martin", "Zima, odstopanje (°C)", "Zadetek"], rows,
                     cap="Martinovo vreme in zima po njem",
                     note=f"»Sončen« je dan z največjim sevanjem nad mediano 1.–20. novembra ({num(R['med_nov'], 0)} W/m²). Sevanje postaja meri od leta 2021.")

    def tb_katarina():
        rows = [(str(r["y"]), sgn(r["da"]), sgn(r["dj"]), "da" if r["hit"] else "ne") for r in s7]
        return table(["Leto", "Katarina, odstopanje (°C)", "Januar, odstopanje (°C)", "Zadetek"], rows, cap="Katarina in januar",
                     note="Odstopanje dneva je od povprečja istega dne (±3 dni) v vseh letih, odstopanje januarja od povprečja sedmih januarjev.")

    # ---------- besedilo ----------
    n8, k8 = len(s8), sum(r["hit"] for r in s8)
    frost8 = [r for r in s8 if r["frost"]]
    nofrost8 = [r for r in s8 if not r["frost"]]
    wf = st.mean(r["w"] for r in frost8)
    wn = st.mean(r["w"] for r in nofrost8)
    cold_after_frost = sum(1 for r in frost8 if r["dev"] < 0)
    lows8 = sorted(r["low"] for r in frost8)
    rain_frost = sorted(r["rain"] for r in s4 if r["frost"])
    rain_free = sorted(r["rain"] for r in s4 if not r["frost"])

    lead = (
        "Kratek odgovor: večinoma ne. Deset pregovorov o svetnikih iz zbirke, objavljene v letih 1937–1939, sem primerjal z meritvami postaje "
        f"IREICA1 iz sedmih zim. Štirih ni bilo mogoče preveriti, štirje ne kažejo nobene zveze, eden se je ujel v {k8} od {n8} let, "
        "eden pa kaže, če kaj, obratno. Lucijin pregovor, po katerem 12 dni pred božičem napove 12 mesecev prihodnjega leta, je od "
        f"{s9['n']} primerov zadel {s9['k']} ({num(100 * s9['k'] / s9['n'], 0)} %)."
    )

    p1 = [
        "Katarina in Andrej sta pred vrati, zato sem pred začetkom zime preveril, kaj pregovori trdijo in kaj kažejo meritve. "
        "Pregovori so iz zbirke I. Šašelja iz Št. Lovrenca ob Temenici (Etnolog 10–11, 1937–1939). Izbral sem tiste, ki jih je mogoče "
        "primerjati s temperaturo, padavinami ali sevanjem, in to storil, preden sem videl rezultate.",
        tb_overview(),
        "Prvi pregovor je najboljši izid od desetih, ne dokaz. Pri šestih preizkusih, ki jih je bilo mogoče izračunati, bi po naključju "
        f"vsaj en izid, enako izrazit kot najboljši, dobili v {num(100 * p_any, 0)} % primerov.",
    ]
    p2 = [
        "Vsak pregovor sem pred branjem rezultatov prevedel v preizkus: dan svetnika, merilo (npr. najnižja temperatura ≤ 0 °C) in obdobje, ki ga "
        "napoveduje. Zadetek je, če se smer ujema. Odstopanja so od povprečja istih dni v analiziranih letih, ne od uradne norme.",
        "Zimo štejem od 1. decembra do konca februarja. Postaja snega ne meri, zato pregovori o snegu (Katarina »grušta«, Andrej »pokriva«, Barbara in "
        "strnišče) niso preverjeni. Lenartov pregovor sem obdelal že prej ([članek o Lenartovem](/blog/lenartovo-pregovor-vreme-do-bozica.html)), "
        "po drugačni definiciji, zato ga tu ne ponavljam.",
        "Besedila pregovorov so prepis iz skeniranega dokumenta; razmaknjene črke sem popravil, pravopis izvirnika pa pustil. "
        "Pregovori se po krajih razlikujejo, to je zapis iz ene vasi.",
    ]
    p3 = [
        "»Andreja mraz – zima železna rebra.« Če je 30. novembra mraz, bo zima huda. "
        f"Mraz (najnižja temperatura ≤ 0 °C) je bil v {len(frost8)} od {n8} let, od {num(lows8[0])} do {num(lows8[-1])} °C. "
        f"V {cold_after_frost} od teh petih let je bila zima hladnejša od povprečja, v obeh letih brez mraza (2019 in 2022) toplejša.",
        tb_andrej(),
        f"Razlika je majhna: zime po Andrejevem mrazu so imele povprečje {num(wf)} °C, po toplem Andreju {num(wn)} °C. "
        f"Leto 2023 (mraz, a najtoplejša zima, {num(R['W'][2023])} °C) kaže, da pregovor ni pravilo. Pri sedmih zimah tega ne moremo ločiti od naključja (p = {num(p8, 2)}).",
    ]
    p4 = [
        "»Če pred Martinom zmrzuje, je pred božičem povodenj.« Zmrzovalo (najnižja temperatura ≤ 0 °C med 1. in 10. novembrom) je v štirih od šestih let, "
        f"in v teh letih je bil december suhejši: od 1. do 24. decembra je padlo od {num(rain_frost[0], 0)} do {num(rain_frost[-1], 0)} mm. "
        f"V obeh letih brez zmrzali (2022 in 2023) je padlo {num(rain_free[0], 0)} in {num(rain_free[1], 0)} mm.",
        tb_martin_zmrzal(),
        f"Po merilu »nad mediano« se je pregovor ujel enkrat od šestkrat (p = {num(p4, 2)}). Šest let ne dokazuje obratne zveze, "
        "a podpore za pregovor tu ni. Ker je bila v letih 2022 in 2023 najnižja temperatura 0,2 °C, sta tik ob meji: če bi ju šteli med zmrzal, "
        "bi imela zmrzal vsa leta in preizkusa ne bi bilo.",
    ]
    p5 = [
        "»Kakršni so dnevi od Lucije do božiča, taki bodo meseci v prihodnjem letu.« Dvanajst dni od 13. do 24. decembra naj bi napovedalo dvanajst "
        "mesecev od januarja do decembra. Dan sem primerjal z odgovarjajočim mesecem po smeri odstopanja temperature (13. december – januar, "
        "14. december – februar in tako naprej).",
        f"Možnih primerov je {s9['total']} (šest let po 12 mesecev in še 10 mesecev letošnjega leta). Pri {s9['total'] - s9['n']} je bilo odstopanje dneva ali meseca "
        f"pod 0,05 °C in jih nisem štel. Od preostalih {s9['n']} se je smer ujela {s9['k']}-krat ({num(100 * s9['k'] / s9['n'], 0)} %), kovanec pa bi dal okoli {num(s9['n'] / 2, 0)} zadetkov. "
        f"Najbolj znan decembrski pregovor torej ni boljši od meta kovanca (p = {num(p_two(s9['n'], s9['k']), 2)}).",
    ]
    p6 = [
        '<h3>Martin: sonce in zima</h3>',
        "»Če je na sv. Martina dan grdo in oblačno vreme, bo potem lepa zima; če je pa sončno in toplo, se je kmalu hude zime nadejati.« "
        "V zbirki je o Martinovem vremenu več zapisov in ne govorijo vsi isto; preizkusil sem ta, ki je najjasnejši.",
        tb_martin_sonce(),
        f"Dvakrat od petkrat se je ujelo. Razlike med zimami so majhne in ne kažejo smeri.",
        '<h3>Katarina: januar</h3>',
        "»Sv. Katarine dan ne laže, če po sebi prosincu vreme kaže.« Prosinec je januar: vreme na Katarino naj bi pokazalo vreme januarja.",
        tb_katarina(),
        f"Štirikrat od sedemkrat, kar ni nič posebnega. Letošnja Katarina je 25. novembra.",
        '<h3>Svečnica: mraz po njej</h3>',
        "»Topla svečnica sneg in mraz prinese, mrzla pa oba odžene.« Če je 2. februarja toplo, naj bi bilo po njem hladneje, in obratno. "
        f"Predznak odstopanja se je ujel {sum(r['hit'] for r in s11)}-krat od {len(s11)} (leta, ko je bilo odstopanje dneva ali obdobja zanemarljivo, sem izpustil).",
    ]
    base = R["S2"]
    p7 = [
        '<h3>Martinovo lepo, nato grdo</h3>',
        "»Ako je na Martinje lepo, bo za tri dni grdo.« V novembru je po lepem dnevu (brez padavin in z nadpovprečnim sevanjem) "
        f"v naslednjih treh dneh padlo vsaj 0,2 mm v {base['base_k']} od {base['base_n']} primerov ({num(100 * base['base_k'] / base['base_n'], 0)} %). "
        "Kdor po lepem dnevu čaka dež, ga skoraj vedno dobi, ne glede na svetnika. Martinov dan je bil lep samo v enem od petih let z meritvijo sevanja.",
        '<h3>Vseh svetnikov mraz</h3>',
        f"»Vseh svetnikov mraz – o Martinju topel čas.« Na vse svete (1. novembra) je bila najnižja temperatura v šestih letih od {num(min(R['S3']['lows'].values()))} do "
        f"{num(max(R['S3']['lows'].values()))} °C. Mraza ni bilo nikoli, zato pregovor nima kaj napovedati.",
        '<h3>Martinova gos</h3>',
        "»Če Martinova gos po ledu plazi, o božiču navadno po blatu gazi.« Najnižja temperatura na Martinovo je bila ≤ 0 °C v letih 2021 in 2025 in v obeh "
        "je bil božič razmočen (nad 0 °C in padavine med 24. in 26. decembrom). A razmočen je bil božič tudi v dveh letih brez ledu: v štirih od sedmih let skupaj. "
        "Dva primera ne zadoščata.",
        '<h3>Jasna svečnica</h3>',
        "»Če svečnica jasno zdani, zima še dolgo trpi.« Jasna svečnica (sevanje nad mediano 1.–20. februarja, "
        f"{num(R['med_feb'], 0)} W/m²) je bila v petih letih z meritvijo sevanja samo 2024, in obdobje od 3. 2. do 15. 3. je bilo po njej "
        f"najtoplejše od sedmih ({sgn(s10[2]['dev'])} °C od povprečja). En primer ne pove ničesar.",
    ]
    p8 = [
        f"Martinovo 2026 je bilo oblačno (največje sevanje {num(mart['solarHigh'], 0)} W/m², mediana je {num(R['med_nov'], 0)} W/m²): po prvem pregovoru lepa zima. "
        f"Pred Martinom je zmrzovalo ({sgn(pre_min[0])} °C 9. 11.): po pregovoru sledi povodenj pred božičem, po moji analizi pa ne vidim podpore. "
        f"Na vse svete je bila najnižja {num(allsaints)} °C, zato pregovor o mrazu ni imel kaj povedati.",
        "Katarina (25. 11.) in Andrej (30. 11.) še prideta. Če bo na Andreja mraz, pregovor napoveduje hudo zimo. Andrejev mraz je edini od desetih pregovorov, ki se je v preizkusu ujel, "
        "zato ga bo letos zanimivo spremljati. Rezultat za zimo 2026/27 bo znan spomladi.",
    ]
    omejitve = [
        "<ul>"
        "<li><strong>Sedem zim je malo.</strong> Postaja meri od novembra 2019, sevanje od leta 2021. Pri petih ali šestih primerih eno leto spremeni vse.</li>"
        "<li><strong>Preizkusov je več.</strong> Ob več preizkusih se po naključju vedno kaj ujame; zato vsak p navajam in ga ne štejem za dokaz.</li>"
        "<li><strong>Definicije so moje.</strong> »Sončno«, »mraz«, »povodenj« in »blato« sem določil vnaprej, a pregovori so dvoumni. Drugačno merilo lahko da drugačen izid.</li>"
        "<li><strong>Postaja je ena točka v dolini.</strong> Pregovori so nastali v drugih krajih in časih, ko je bilo podnebje drugačno.</li>"
        "<li><strong>Snega postaja ne meri.</strong> Pregovori o snegu so zato izven preizkusa.</li>"
        "<li><strong>Pregovor ni napoved.</strong> Služi spominu in pogovoru, ne odločanju o kurjavi ali gumah.</li>"
        "</ul>",
    ]
    p10 = [
        "Za napoved za naslednje dni poglejte <a href=\"" + SITE + "/zima/\" style=\"color:var(--blue)\">zimske strani</a> in "
        "<a href=\"" + SITE + "/tocnost-napovedi/\" style=\"color:var(--blue)\">natančnost napovedi za Rečico</a>. "
        "O vremenu ob Martinovem sem pisal tudi <a href=\"/blog/martinovo-vreme-recica-sest-let-1111.html\" style=\"color:var(--blue)\">v članku z dne 11. novembra</a>.",
        '<p class="vs-note" style="margin-top:1.5rem"><strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko povzemate le z '
        'navedbo avtorja (Filip Eremita, Meteorec) in neposredno povezavo na ta članek. Za prepis ali vdelavo grafov in izračunov se '
        'predhodno dogovorite z avtorjem.</p>',
    ]
    title = "Ali pregovori o svetnikih držijo? Deset testov"
    assert len(title) <= 60, len(title)
    desc = ("Deset vremenskih pregovorov iz zbirke 1937–1939 proti sedmim zimam meritev v Rečici: Andrejev mraz se je ujel, Lucija ni boljša od kovanca.")
    assert len(desc) <= 160, len(desc)
    sections = [
        {"label": "01 — odgovor", "heading": "Večina pregovorov ne zdrži preizkusa", "id": "odgovor", "paragraphs": p1},
        {"label": "02 — preizkus", "heading": "Kako sem preverjal", "id": "preizkus", "paragraphs": p2},
        {"label": "03 — Andrej", "heading": "Andrejev mraz se je ujel, a malo", "id": "andrej", "paragraphs": p3},
        {"label": "04 — Martin", "heading": "Zmrzal pred Martinom: obratno", "id": "zmrzal", "paragraphs": p4},
        {"label": "05 — Lucija", "heading": "Lucija ni boljša od kovanca", "id": "lucija", "paragraphs": p5},
        {"label": "06 — brez zveze", "heading": "Martin, Katarina in svečnica", "id": "brez-zveze", "paragraphs": p6},
        {"label": "07 — ni preverljivo", "heading": "Kar se ne da preveriti", "id": "ni-preverljivo", "paragraphs": p7},
        {"label": "08 — letos", "heading": "Kaj pregovori napovedujejo letos?", "id": "letos", "paragraphs": p8},
        {"label": "09 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": omejitve},
        {"label": "10 — kaj naprej", "heading": "Kaj narediti s pregovori", "id": "kaj-naprej", "paragraphs": p10},
    ]
    lead = nb(lead)
    for sec in sections:
        sec["paragraphs"] = [nb(x) for x in sec["paragraphs"]]
    return {
        "title": title, "meta_description": desc,
        "tags": ["pregovori", "zima", "podatki", "november"],
        "section_label": "Podatkovna analiza", "og_photo": "misty-valley", "og_accent_hex": "#22d3ee",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": ("Viri: I. Šašelj, »Svetniki in svetnice v slovenskih pregovorih in vremenskih prislovicah«, Etnolog 10–11 (1937–1939), "
                         "Etnografski muzej (prepis iz skeniranega dokumenta); postaja IREICA1 (zunanji senzor, od 7. 11. 2019, sevanje od 2021). "
                         f"Podatki do {last.day}. {last.month}. {last.year}. Izračuni: tools/generate_ljudsko_vreme_post.py."),
    }


def md_links(h):
    """Markdown povezave [besedilo](url) v odstavkih -> <a>."""
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" style="color:var(--blue)">\1</a>', h)


def plain_text(article):
    def clean(h):
        h = re.sub(r"<svg.*?</svg>", "", h, flags=re.S)
        h = re.sub(r"<style.*?</style>", "", h, flags=re.S)
        h = re.sub(r"</tr>", "\n", h)
        h = re.sub(r"</t[hd]>", " | ", h)
        h = re.sub(r"</?(h3|figcaption|li|p)[^>]*>", "\n", h)
        h = re.sub(r"<[^>]+>", "", h)
        h = h.replace(NBSP, " ")
        h = re.sub(r"[ \t]+\n", "\n", h)
        return re.sub(r"\n{3,}", "\n\n", h).strip()
    out = [article["title"], "", "META OPIS: " + article["meta_description"], "", "UVOD", clean(article["lead"]), ""]
    for s in article["sections"]:
        out += [f'{s["label"].upper()} -- {s["heading"]}', ""]
        for p in s["paragraphs"]:
            out += [clean(p), ""]
    out += ["VIRI", clean(article["sources_note"])]
    return "\n".join(out) + "\n"


def main():
    dry, wire, force = "--dry-run" in sys.argv, "--wire" in sys.argv, "--force" in sys.argv
    if not ("--allow-date" in sys.argv or dry or "--text" in sys.argv):
        assert SNAPSHOT_FIRST <= datetime.date.today() <= SNAPSHOT_LAST, "posnetek je vezan na datum (--allow-date)"
    days = load()
    R = analyse(days)
    article = build_article(days, R)
    for s in article["sections"]:
        s["paragraphs"] = [md_links(p) for p in s["paragraphs"]]
    if "--text" in sys.argv:
        open(TEXT_OUT, "w", encoding="utf-8").write(plain_text(article))
        print("✓ besedilo za lekturo:", os.path.relpath(TEXT_OUT, ROOT))
    if dry:
        print(plain_text(article))
        return
    path = os.path.join(ROOT, "blog", f"{SLUG}.html")
    if os.path.exists(path) and not force:
        print(f"blog/{SLUG}.html že obstaja -- brez ponovne objave (--force za prepis).")
        return
    import generate_forecast_test_post as ftp
    today = datetime.date.today()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    ftp.TODAY = today.isoformat()
    slug, html, entry, og_meta = ftp.build_html(
        article, today.year, today.month, now_utc, slug=SLUG, back=("/blog/", "← Vsi članki"),
        og_title="Pregovori o\nsvetnikih: držijo?", meta_note="podatkovna analiza",
        nav_label="O postaji", nav_href="/o-postaji.html")
    lead = f'<p class="lead">{article["lead"]}</p>'
    assert html.count(lead) == 1, "uvoda ni mogoče najti za vstavitev sloga"
    html = html.replace(lead, STYLE + "\n" + lead, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ zapisano: blog/{slug}.html")
    if wire or "--og" in sys.argv:
        try:
            from generate_og_images import make_og
            make_og({"slug": slug, **og_meta})
            print(f"✓ OG slika: og/{slug}.jpg")
        except Exception as e:  # noqa: BLE001
            print(f"⚠ OG slika preskočena: {e}")
    if wire:
        from generate_monthly_post import wire_all
        wire_all(entry, entry["url"])
        print("✓ blog.json, blog/index.html, sitemap.xml, blog/rss.xml, teme in sorodni članki osveženi.")


if __name__ == "__main__":
    main()
