#!/usr/bin/env python3
"""
tools/generate_indeksi_page.py — /indeksi/ (21. 10. 2026)

Teleconnection indeksi, ki jih objavlja NOAA CPC/PSL: AO (Arktična oscilacija), NAO (Severnoatlantska oscilacija)
in ENSO (ONI, Niño 3.4), z zadnjimi 120 dnevi, 15-dnevno napovedjo ansambla GEFS in kratko razlago, kaj to pomeni
za nas. Ideja po polarnivrtinec.si (»Indeksi«); stran in besedilo sta naša.

Kar stran je in ni:
- SIROV INDEKS Z DRUGE POSTAJE: AO/NAO sta standardizirani višinski polji (z1000 / z500) na severni polobli,
  ENSO je temperatura Tihega oceana. Za Rečico ob Savinji nista napoved; povezava z našim vremenom je šibka in
  statistična (pozimi nekoliko močnejša). Stran to pove.
- MJO NI vključen: edini običajni prosto objavljeni indeks (RMM) pripada avstralskemu BoM, ki izrecno prepoveduje
  samodejni prenos; CPC-jev ekvivalent pa nima ustaljene razlage. Raje nič kot napačna slika.
- Brez podatkov postaje; notranjih meritev tu ni.

Usage:
  python3 tools/generate_indeksi_page.py
"""
import csv
import datetime
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atmos_common as ac  # noqa: E402

CPC = "https://ftp.cpc.ncep.noaa.gov/cwlinks/"
ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
NINO34_URL = "https://psl.noaa.gov/data/correlation/nina34.anom.data"
DATA_PATH = os.path.join(ac.ROOT, "data", "indeksi.json")
REL = "/indeksi/"
OBS_DAYS = 120
GREEN, PURPLE, AMBER = "#34d399", "#c084fc", "#fbbf24"
SEAS = ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"]  # središče = mesec 1..12

FAQ = [
    ("Kaj je Arktična oscilacija (AO)?",
     "Indeks, ki meri, kako močno je hladen zrak »zaprt« nad Arktiko. Pozitiven AO pomeni močan polarni vrtinec in "
     "pogosto milejše, zahodno vreme v srednji Evropi. Negativen AO pomeni šibek ali razmajan vrtinec in večjo "
     "možnost prodorov hladnega zraka proti jugu. Povezava je statistična in velja za povprečje, ne za posamezen dan."),
    ("Kaj je Severnoatlantska oscilacija (NAO)?",
     "Razlika tlaka med Azorskim anticiklonom in Islandskim ciklonom. Pozitiven NAO pomeni močan zahodnik čez "
     "Atlantik, mile in vlažne zime v severozahodni Evropi. Negativen NAO pomeni šibek zahodnik, blokade in "
     "pogosteje hladne zime v srednji in severni Evropi. Za Slovenijo je učinek šibkejši kot za Britanijo."),
    ("Ali indeksa napovesta, kakšno bo vreme v Rečici?",
     "Ne. To sta kazalnika velikih tokov čez celotno severno poloblo. Njuna vrednost lahko skoči za več enot v nekaj "
     "dneh, napoved za Rečico pa ostane odvisna od lokalnega vremena. Za to je /primerjava-modelov/ in poskusni "
     "model MTR. Indeksa sta dopolnilo za razumevanje sezone."),
    ("Kaj pomeni ONI in kaj je El Niño?",
     "ONI (Oceanic Niño Index) je 3-mesečno drseče povprečje odstopanja temperature morja v območju Niño 3.4 "
     "(ekvatorialni Tihi ocean). Vrednosti nad +0,5 °C nekaj zaporednih sezon so El Niño, pod −0,5 °C La Niña. "
     "Učinek na vreme v Evropi je šibek in pozimi neenoten; je pa pomemben za svetovno podnebje."),
    ("Od kod so podatki in kako sveži so?",
     "Dnevna AO in NAO (NOAA CPC, analiza iz CDAS) zaostajata nekaj dni; napoved je ansambel GEFS (31 članov) in "
     "tek GFS do 15 dni vnaprej. ONI je mesečni (zadnja vrednost je za predzadnji ali predpredzadnji mesec), Niño 3.4 "
     "je z NOAA PSL. Vsi podatki so javni."),
]


# ── Prenos in razčlenitev ────────────────────────────────────────────────────

def parse_cdas(text):
    """CPC dnevni indeks (CSV 'leto,mesec,dan,vrednost') → [(date, value)]."""
    out = []
    for line in text.splitlines():
        p = line.strip().split(",")
        if len(p) >= 4 and p[0].isdigit():
            try:
                out.append((datetime.date(int(p[0]), int(p[1]), int(p[2])), float(p[3])))
            except ValueError:
                continue
    return out


def parse_forecast(text, col):
    """CSV napovedi (lead,[member,]time,<col>,valid_time) → {'init': date, 'gefs': {valid: [vrednosti]},
    'gfs': {valid: v}} za zadnji čas izdaje."""
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        return None
    init = max(r["time"] for r in rows)
    by = {}
    for r in rows:
        if r["time"] != init:
            continue
        try:
            by.setdefault(r["valid_time"], []).append(float(r[col]))
        except (ValueError, KeyError):
            continue
    return {"init": init, "by_valid": by}


def percentile(vals, p):
    s = sorted(vals)
    if not s:
        return None
    k = (len(s) - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def parse_oni(text):
    """ONI (SEAS YR TOTAL ANOM) → [(date središčnega meseca, anomalija, oznaka sezone)]."""
    out = []
    for line in text.splitlines():
        p = line.split()
        if len(p) >= 4 and p[0] in SEAS and p[1].isdigit():
            try:
                m = SEAS.index(p[0]) + 1
                y = int(p[1])
                out.append((datetime.date(y, m, 1), float(p[3]), f"{p[0]} {y}"))
            except ValueError:
                continue
    return out


def parse_nino34(text):
    """PSL (vrstica 'leto v1..v12', manjkajoče −99.99) → [(date, anomalija)]."""
    out = []
    for line in text.splitlines():
        p = line.split()
        if len(p) == 13 and p[0].isdigit() and 1800 < int(p[0]) < 2200:
            for m, v in enumerate(p[1:], 1):
                try:
                    val = float(v)
                except ValueError:
                    continue
                if val > -90:
                    out.append((datetime.date(int(p[0]), m, 1), val))
    return out


def fetch_all():
    ao_obs = parse_cdas(ac.http_get(CPC + "norm.daily.ao.cdas.z1000.19500101_current.csv").decode("utf-8", "replace"))
    nao_obs = parse_cdas(ac.http_get(CPC + "norm.daily.nao.cdas.z500.19500101_current.csv").decode("utf-8", "replace"))
    ao_fc = parse_forecast(ac.http_get(CPC + "norm.daily.ao.gefs.z1000.120days.csv").decode(), "ao_index")
    nao_fc = parse_forecast(ac.http_get(CPC + "norm.daily.nao.gefs.z500.120days.csv").decode(), "nao_index")
    ao_gfs = parse_forecast(ac.http_get(CPC + "norm.daily.ao.gfs.z1000.120days.csv").decode(), "ao_index")
    nao_gfs = parse_forecast(ac.http_get(CPC + "norm.daily.nao.gfs.z500.120days.csv").decode(), "nao_index")
    oni = parse_oni(ac.http_get(ONI_URL).decode("utf-8", "replace"))
    nino = parse_nino34(ac.http_get(NINO34_URL).decode("utf-8", "replace"))
    if not (ao_obs and nao_obs and ao_fc and nao_fc and oni):
        raise RuntimeError("manjkajo podatki NOAA (prazen odgovor)")
    cut = ao_obs[-1][0] - datetime.timedelta(days=OBS_DAYS)

    def pack(obs, fc, gfs):
        by = fc["by_valid"]
        steps = []
        for valid in sorted(by):
            v = by[valid]
            g = (gfs or {}).get("by_valid", {}).get(valid)
            steps.append({"date": valid, "mean": sum(v) / len(v), "p10": percentile(v, 10), "p90": percentile(v, 90),
                          "n": len(v), "gfs": g[0] if g else None})
        return {"obs": [[d.isoformat(), round(x, 3)] for d, x in obs if d >= cut],
                "fc_init": fc["init"], "fc": steps}

    return {"generated_at": ac.now_utc_iso(),
            "ao": pack(ao_obs, ao_fc, ao_gfs), "nao": pack(nao_obs, nao_fc, nao_gfs),
            "oni": [[d.isoformat(), v, lab] for d, v, lab in oni[-48:]],
            "nino34": [[d.isoformat(), v] for d, v in nino[-48:]]}


# ── Razlaga (iz števil, ne ročno) ────────────────────────────────────────────

def phase(v, pos, neg):
    if v >= 1.0:
        return f"izrazito {pos}"
    if v >= 0.5:
        return pos
    if v <= -1.0:
        return f"izrazito {neg}"
    if v <= -0.5:
        return neg
    return "blizu nevtralnega"


def enso_state(v):
    """Običajna delitev po moči (NOAA CPC jo uporablja pri opisih; meje so konvencija, ne uradno pravilo)."""
    a = abs(v)
    if a < 0.5:
        return "nevtralno"
    kind = "El Niño" if v > 0 else "La Niña"
    if a < 1.0:
        return f"šibek {kind}"
    if a < 1.5:
        return f"zmeren {kind}"
    if a < 2.0:
        return f"močan {kind}"
    return f"zelo močan {kind}"


def index_summary(name, block, pos, neg, hint_pos, hint_neg):
    obs = block["obs"]
    last_d, last_v = datetime.date.fromisoformat(obs[-1][0]), obs[-1][1]
    wk = [v for d, v in obs[-7:]]
    wk_mean = sum(wk) / len(wk)
    fc = block["fc"]
    today = last_d
    future = [s for s in fc if datetime.date.fromisoformat(s["date"]) > today]
    txt = (f"{name} je bil {ac.fmt_date(last_d)} {ac.num(last_v, 1, True)} ({phase(last_v, pos, neg)}), "
           f"povprečje zadnjih sedmih dni {ac.num(wk_mean, 1, True)}.")
    if future:
        end = future[-1]
        txt += (f" Ansambel GEFS za {ac.fmt_date(end['date'])} kaže povprečje {ac.num(end['mean'], 1, True)} "
                f"(razpon 10.–90. percentila {ac.num(end['p10'], 1, True)} do {ac.num(end['p90'], 1, True)}) — "
                f"razpon je velik, zato je napoved za 2 tedna le smer, ne podatek.")
    hint = hint_pos if wk_mean >= 0.5 else hint_neg if wk_mean <= -0.5 else ""
    return txt, hint


def build_charts(d):
    def idx_chart(block, label):
        obs = [(datetime.date.fromisoformat(a), b) for a, b in block["obs"]]
        last = obs[-1][0]
        fc = [s for s in block["fc"] if datetime.date.fromisoformat(s["date"]) >= last]
        mean = [(datetime.date.fromisoformat(s["date"]), s["mean"]) for s in fc]
        band = [(datetime.date.fromisoformat(s["date"]), s["p10"], s["p90"]) for s in fc]
        gfs = [(datetime.date.fromisoformat(s["date"]), s["gfs"]) for s in fc if s["gfs"] is not None]
        series = [{"name": "analiza", "color": GREEN, "pts": obs, "width": 2},
                  {"name": "GEFS", "color": PURPLE, "pts": mean, "width": 2, "band": band}]
        if gfs:
            series.append({"name": "GFS", "color": AMBER, "pts": gfs, "width": 1.5, "dash": "4 3"})
        aria = (f"Graf indeksa {label}: dnevna analiza zadnjih {OBS_DAYS} dni in napoved ansambla GEFS "
                f"do {ac.fmt_date(fc[-1]['date'])}.") if fc else f"Graf indeksa {label}."
        leg = ac.legend([(GREEN, "analiza (CDAS)", False), (PURPLE, "povprečje GEFS in razpon 10.–90. perc.", False)]
                        + ([(AMBER, "GFS", True)] if gfs else []))
        return leg + ac.line_chart(series, marker=(last, "zadnja analiza"), aria=aria, yfmt=lambda v: ac.num(v, 0))

    def enso_chart():
        oni = [(datetime.date.fromisoformat(a), b) for a, b, _ in d["oni"]]
        nino = [(datetime.date.fromisoformat(a), b) for a, b in d["nino34"]]
        series = [{"name": "ONI", "color": GREEN, "pts": oni, "width": 2.5}]
        if nino:
            series.append({"name": "Niño 3.4", "color": PURPLE, "pts": nino, "width": 1.5, "dash": "4 3"})
        leg = ac.legend([(GREEN, "ONI (3-mesečno povprečje)", False)] + ([(PURPLE, "Niño 3.4 (mesečno)", True)]
                                                                       if nino else []))
        return leg + ac.line_chart(series, hlines=[(0.5, "El Niño ≥ +0,5"), (-0.5, "La Niña ≤ −0,5")], unit="°C",
                                   aria="Graf ONI in temperature morja Niño 3.4 za zadnja štiri leta.",
                                   width=720, height=280, x_every=None)
    return idx_chart(d["ao"], "AO"), idx_chart(d["nao"], "NAO"), enso_chart()


def build_body(d, stale_note=""):
    ao_txt, ao_hint = index_summary("AO", d["ao"], "pozitiven", "negativen",
                                    " Pozitiven AO pomeni, da je polarni vrtinec močan in hladen zrak ostaja nad "
                                    "Arktiko; v srednji Evropi to običajno pomeni milejše vreme.",
                                    " Negativen AO pomeni šibkejši polarni vrtinec in večjo možnost prodorov "
                                    "hladnega zraka proti jugu (pozimi).")
    nao_txt, nao_hint = index_summary("NAO", d["nao"], "pozitiven", "negativen",
                                      " Pozitiven NAO pomeni hiter zahodnik čez Atlantik: milo in vlažno na "
                                      "severozahodu Evrope.",
                                      " Negativen NAO pomeni šibek zahodnik in več blokad: hladneje in suho v "
                                      "srednji in severni Evropi.")
    oni_d, oni_v, oni_lab = d["oni"][-1]
    enso_txt = (f"Zadnja vrednost ONI je {ac.num(oni_v, 2, True)} °C za sezono {oni_lab}: po običajni delitvi je to "
                f"{enso_state(oni_v)}.")
    aoc, naoc, ensoc = build_charts(d)
    ao_last = d["ao"]["obs"][-1]
    nao_last = d["nao"]["obs"][-1]
    cards = (
        f'  <div class="callout"><strong>AO {ac.num(ao_last[1], 1, True)}</strong> · '
        f'<strong>NAO {ac.num(nao_last[1], 1, True)}</strong> · '
        f'<strong>ONI {ac.num(oni_v, 2, True)} °C</strong> ({_esc(enso_state(oni_v))})'
        f'<br><span class="muted-note">Zadnji podatki: AO in NAO za {ac.fmt_date(ao_last[0])}, ONI za sezono '
        f'{_esc(oni_lab)}. Stran osvežena {_esc(ac.fmt_dt_local(d["generated_at"]))}.</span></div>')
    return f'''  <h1 class="page-title">Indeksi AO, NAO in ENSO: kaj velika ozračja pravijo o sezoni</h1>
  <p class="archive-intro">Trije kazalniki, ki jih meteorologi spremljajo ob sezonskem pregledu: Arktična oscilacija
  (polarni vrtinec), Severnoatlantska oscilacija (zahodnik čez Atlantik) in ENSO (El Niño, La Niña). Podatki
  so iz NOAA, napoved indeksov iz ansambla GEFS. To <b>ni napoved vremena za Rečico</b>: povezava s
  slovenskim vremenom je statistična in šibka. Za polarni vrtinec glej tudi
  <a href="/stratosfera/">stratosfero</a>, za razmere nad Evropo <a href="/sinopticna/">sinoptično karto</a>.</p>
{stale_note}{cards}
  <h2>Arktična oscilacija (AO)</h2>
  <p class="archive-intro">{_esc(ao_txt)}{_esc(ao_hint)}</p>
{aoc}
  <h2>Severnoatlantska oscilacija (NAO)</h2>
  <p class="archive-intro">{_esc(nao_txt)}{_esc(nao_hint)}</p>
{naoc}
  <h2>El Niño in La Niña (ENSO)</h2>
  <p class="archive-intro">{_esc(enso_txt)} Učinek na evropsko vreme je šibek in pozimi neenoten; sezonski signal je
  veliko izrazitejši v tropih in Severni Ameriki.</p>
{ensoc}
  <h2>Kako uporabljati te indekse</h2>
  <p class="archive-intro">Indeksi so zanimivi predvsem pozimi, ko je polarni vrtinec najmočnejši in je vpliv na srednjo
  Evropo največji. Poleti so skoraj brez vrednosti za napoved. Nobeden od indeksov ni jamstvo: negativen AO v
  zimskem mesecu poveča verjetnost hladnega obdobja, ne obljubi ga. Uradna napoved je ARSO; razlago vrednosti
  zimskih mesecev za dolino lahko primerjaš z <a href="/klima/">klimo Rečice</a>.</p>
  <p class="muted-note">Viri: NOAA CPC (AO, NAO, GEFS, GFS, ONI), NOAA PSL (Niño 3.4). Standardizirano glede na
  referenčno obdobje NOAA. Indeksa MJO nimamo, ker njegov običajni vir (BoM) samodejnega prenosa ne dovoljuje.</p>'''


def _esc(s):
    import html
    return html.escape(s)


def main():
    stale = ""
    try:
        d = fetch_all()
        ac.write_json(DATA_PATH, d)
    except Exception as e:  # noqa: BLE001
        print(f"✗ prenos NOAA: {e} — uporabim shranjeni posnetek", file=sys.stderr)
        d = ac.read_json(DATA_PATH)
        if not d:
            return 1
        stale = (f'  <p class="callout"><strong>Podatki niso sveži:</strong> NOAA ob zadnjem teku ni bil '
                 f'dosegljiv, prikazan je posnetek z {_esc(ac.fmt_dt_local(d["generated_at"]))}.</p>\n')
    title = "Indeksi AO, NAO in ENSO: polarni vrtinec in sezona"
    desc = ("AO, NAO in ENSO iz NOAA: zadnjih 120 dni, 15-dnevna napoved ansambla GEFS in razlaga. Kazalniki sezone, "
            "ne napoved za Rečico.")
    ac.write_site_page(REL + "index.html", REL, title, desc, build_body(d, stale), FAQ, "Indeksi AO, NAO, ENSO",
                       "2026-10-22", modified=d["generated_at"][:10])
    return 0


if __name__ == "__main__":
    sys.exit(main())
