#!/usr/bin/env python3
"""
tools/gobe_naslovi.py — ROČNO orodje (ni v nobenem workflowu): iz današnjih podatkov
sestavi kandidate za naslov + uvod objave v gobjih FB skupinah.

Skupine dobijo link (ne sliko), zato je pomemben naslov, ki ga FB izriše iz og:title,
in prvi stavek objave nad njim. Orodje:

  * zbere dejstva iz že committanih datotek (gobarska-napoved/izbirnik.json,
    indeks-zgodovina.json, trend.json, history.json) — brez omrežja, brez API-ja;
  * iz njih sestavi naslove po predlogah (vsaka ima pogoj, da velja SAMO, kadar
    številka res obstaja — nobenega izmišljenega »vrha«);
  * oceni po pravilih (številka, vrsta, dolžina, razpravljivost) in izpiše najboljše;
  * z --izberi N izpiše povezavo z UTM, ki nosi ID predloge (utm_medium=group,
    utm_campaign=gn-<id>), in vrstico doda v data/gobe-naslovi-log.csv — tako bo čez
    čas v GA4 vidno, katera vrsta naslova dejansko prinaša klike.

Pravila (iz CLAUDE.md):
  * samo ZUNANJE meritve (history.json nima notranjih; notranjih ne beri nikoli);
  * območje je najmanjša enota — imena območij so tista iz izbirnika (javna na strani),
    nikoli točne lokacije najdb;
  * vsak podatek v naslovu je izmerjen/izračunan, ne ugibanje; modelski indeks je
    »indeks«, ne »gob je toliko«.

Uporaba:
  python3 tools/gobe_naslovi.py                      # top 8 kandidatov
  python3 tools/gobe_naslovi.py --top 12 --vse       # tudi nizko ocenjeni
  python3 tools/gobe_naslovi.py --slug <slug>        # članek, na katerega vodi link
  python3 tools/gobe_naslovi.py --izberi 3           # povezava + zapis v dnevnik
"""
import argparse
import csv
import datetime
import json
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOBE = os.path.join(ROOT, "gobarska-napoved")
LOG = os.path.join(ROOT, "data", "gobe-naslovi-log.csv")
SITE = "https://meteorec.si"

# Nominativ množine za naslove (izbirnik nosi samo ednino z oklepaji).
PLURAL = {
    "boletus_edulis": "Jurčki",
    "cantharellus_cibarius": "Lisičke",
    "macrolepiota_procera": "Orjaški dežniki",
    "russula_cyanoxantha": "Modrikaste golobice",
    "leccinum_versipelle": "Brezovi turki",
}
DAYS_ACC = ["v ponedeljek", "v torek", "v sredo", "v četrtek", "v petek", "v soboto", "v nedeljo"]
# Mikorizne vrste po dežju ne rodijo prej kot po ~8 dneh (okno 8–16, glej gobe_model).
MYCORRHIZAL_LAG_MIN, MYCORRHIZAL_LAG_MAX = 8, 16
RAIN_EVENT_MM = 15.0      # vsota 5 dni, od katere govorimo o »dežju«
DRY_DAY_MM = 1.0


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dni(n):
    return "dan" if n == 1 else "dni"


def pct(v):
    return f"{int(round(v))} %"


def mm(v):
    s = f"{v:.1f}".replace(".", ",")
    return s[:-2] if s.endswith(",0") else s


# --------------------------------------------------------------------------- dejstva

def gather(today_override=None):
    pick = load(os.path.join(GOBE, "izbirnik.json"))
    idx = load(os.path.join(GOBE, "index.json"))
    hist = load(os.path.join(ROOT, "history.json"))
    try:
        trend = load(os.path.join(GOBE, "trend.json"))
    except (OSError, ValueError):
        trend = {}
    try:
        idx_hist = load(os.path.join(GOBE, "indeks-zgodovina.json"))
    except (OSError, ValueError):
        idx_hist = []

    today = datetime.date.fromisoformat(today_override or idx["date"])
    days = [datetime.date.fromisoformat(d) for d in pick["days"]]
    # Izbirnik mora vsebovati današnji dan, sicer so številke za drug datum.
    if today not in days:
        raise SystemExit(f"izbirnik.json ne vsebuje {today} (dnevi: {pick['days'][0]}..{pick['days'][-1]}) "
                         f"— zaženi gobe-forecast.yml ali podaj --datum.")
    t0 = days.index(today)
    home = next((l["name"] for l in pick["locations"] if l.get("home")), idx["location"])

    rain = {}
    low = {}
    for ds, rec in hist.items():
        try:
            d = datetime.date.fromisoformat(ds)
        except ValueError:
            continue
        if d <= today:
            if rec.get("precipTotal") is not None:
                rain[d] = rec["precipTotal"]
            if rec.get("tempLow") is not None:
                low[d] = rec["tempLow"]

    return {
        "today": today, "days": days, "t0": t0, "home": home,
        "species": pick["species"], "locations": [l["name"] for l in pick["locations"]],
        "index": pick["index"], "overall": idx["index"], "level": idx["level"],
        "rain": rain, "low": low, "trend": trend, "idx_hist": idx_hist,
        "last_obs": max(rain) if rain else None,
    }


def series(F, sid, loc):
    """Indeks vrste na območju od danes naprej (seznam, [0] = danes)."""
    return F["index"][sid][loc][F["t0"]:]


def short(F, sid):
    return PLURAL.get(sid) or next(s["name_sl"] for s in F["species"] if s["id"] == sid)


def best_location(F, sid, k=0):
    return max(F["locations"], key=lambda l: series(F, sid, l)[k])


# --------------------------------------------------------------------------- predloge
# Vsaka predloga vrne seznam kandidatov ali []. Kandidat: id, naslov, uvod, osnova
# (osnovna ocena predloge: nagnjenost k razpravi/nujnosti).

def cand(id_, title, intro, base):
    return {"id": id_, "title": title, "intro": intro, "base": base}


def t_rain_wait(F):
    """Padlo je veliko, mikorizne vrste pa še ne morejo roditi."""
    w = [F["today"] - datetime.timedelta(days=i) for i in range(1, 6)]
    vals = {d: F["rain"].get(d, 0.0) for d in w}
    total = sum(vals.values())
    if total < RAIN_EVENT_MM:
        return []
    peak = max(vals, key=vals.get)
    ds = (F["today"] - peak).days
    if ds >= MYCORRHIZAL_LAG_MIN:
        return []
    wait = MYCORRHIZAL_LAG_MIN - ds
    return [cand(
        "dez-pocakaj",
        f"Padlo je {mm(total)} mm dežja. Jurčki najprej čez {wait} {dni(wait)}.",
        f"Zadnjih 5 dni je na postaji padlo {mm(total)} mm. Mikorizne vrste (jurček, lisička) po dežju "
        f"ne rastejo takoj — pri nas se okno odpre okoli {MYCORRHIZAL_LAG_MIN}. dneva. "
        f"Kdo je tole že preizkusil in šel prezgodaj?", 8)]


def t_rain_window(F):
    w = [F["today"] - datetime.timedelta(days=i) for i in range(1, 17)]
    vals = {d: F["rain"].get(d, 0.0) for d in w}
    # največji 3-dnevni dež v zadnjih 16 dneh
    best = None
    for d in w:
        s = sum(F["rain"].get(d - datetime.timedelta(days=j), 0.0) for j in range(3))
        if best is None or s > best[1]:
            best = (d, s)
    if not best or best[1] < RAIN_EVENT_MM:
        return []
    ds = (F["today"] - best[0]).days
    if not (MYCORRHIZAL_LAG_MIN <= ds <= MYCORRHIZAL_LAG_MAX):
        return []
    return [cand(
        "dez-okno",
        f"Od {mm(best[1])} mm dežja je minilo {ds} dni. Jurčki so zdaj v oknu.",
        f"Zadnji večji dež ({mm(best[1])} mm v 3 dneh) je bil pred {ds} dnevi. "
        f"To je točno čas, ko se mikorizne vrste začnejo kazati. Pa se vam sklada s tem, kar vidite v gozdu?", 8)]


def t_dry(F):
    d = F["today"] - datetime.timedelta(days=1)
    n = 0
    while n < 40 and F["rain"].get(d, 99) < DRY_DAY_MM and d in F["rain"]:
        n += 1
        d -= datetime.timedelta(days=1)
    if n < 7:
        return []
    return [cand(
        "suša",
        f"{n} {dni(n)} brez dežja. Zakaj v gozdu ni tako, kot bi pričakovali.",
        f"Na postaji že {n} {dni(n)} ni padlo ≥ 1 mm. Gobji indeks za dolino je danes {pct(F['overall'])}. "
        f"Kje pa vi še kaj najdete?", 6)]


def t_frost(F):
    nights = [F["low"].get(F["today"] - datetime.timedelta(days=i)) for i in range(1, 4)]
    nights = [v for v in nights if v is not None]
    if not nights or min(nights) > 1.0:
        return []
    return [cand(
        "slana",
        f"Ponoči {mm(min(nights))} °C. Je s prvo slano konec gob ali šele začetek?",
        f"Najnižja nočna temperatura zadnje dni: {mm(min(nights))} °C. Različne vrste to različno prenesejo — "
        f"lisičke in jurčki pogosto še malo rastejo, šampinjoni in dežniki manj. Kaj ste opazili vi?", 7)]


def t_gap(F):
    out = []
    for s in F["species"]:
        vals = {l: series(F, s["id"], l)[0] for l in F["locations"]}
        hi = max(vals, key=vals.get)
        lo = min(vals, key=vals.get)
        if vals[hi] - vals[lo] < 20:
            continue
        out.append((vals[hi] - vals[lo], s, hi, lo, vals))
    if not out:
        return []
    gap, s, hi, lo, vals = max(out, key=lambda x: x[0])
    return [cand(
        "razlika-obmocij",
        f"{short(F, s['id'])}: {hi} {pct(vals[hi])}, {lo} le {pct(vals[lo])}.",
        f"{short(F, s['id'])} — modelski indeks je danes v dolini razpotegnjen na {int(gap)} točk: "
        f"{hi} {pct(vals[hi])}, {lo} {pct(vals[lo])}. Višina in vrsta tal naredita več kot dež. "
        f"Se strinjate z razporedom?", 8)]


def t_home_vs_best(F):
    out = []
    for s in F["species"]:
        hi = best_location(F, s["id"], 0)
        a = series(F, s["id"], hi)[0]
        b = series(F, s["id"], F["home"])[0]
        if a - b >= 15:
            out.append((a - b, s, hi, a, b))
    if not out:
        return []
    _, s, hi, a, b = max(out, key=lambda x: x[0])
    return [cand(
        "doma-proti-najboljsemu",
        f"{short(F, s['id'])}: {pct(a)} v območju {hi}, doma le {pct(b)}.",
        f"Če imate izbiro, kam gre danes pot: {short(F, s['id'])} imajo po modelu {pct(a)} ({hi}) proti "
        f"{pct(b)} v Rečici. Katero območje bi izbrali vi?", 7)]


def t_peak(F):
    out = []
    for s in F["species"]:
        # povprečje po območjih po dnevih
        n = len(series(F, s["id"], F["locations"][0]))
        avg = [sum(series(F, s["id"], l)[k] for l in F["locations"]) / len(F["locations"]) for k in range(n)]
        k = max(range(n), key=lambda i: avg[i])
        if k >= 1 and avg[k] - avg[0] >= 8:
            out.append((avg[k] - avg[0], s, k, avg[0], avg[k]))
    if not out:
        return []
    _, s, k, a0, ak = max(out, key=lambda x: x[0])
    d = F["days"][F["t0"] + k]
    kdaj = DAYS_ACC[d.weekday()]
    return [cand(
        "vrh-ne-danes",
        f"{short(F, s['id'])}: vrh bo {kdaj}, ne danes ({pct(a0)} → {pct(ak)}).",
        f"{short(F, s['id'])} — povprečni indeks v dolini: danes {pct(a0)}, {kdaj} {pct(ak)}. "
        f"Kdor gre prezgodaj, hodi zaman. Pošljite naprej tistemu, ki vas vedno vleče v gozd preveč zgodaj.", 8)]


def t_drop(F):
    cur, nxt = F["overall"], None
    vals = []
    for s in F["species"]:
        for l in F["locations"]:
            ser = series(F, s["id"], l)
            if len(ser) > 1:
                vals.append((ser[0], ser[1]))
    if not vals:
        return []
    a = sum(v[0] for v in vals) / len(vals)
    b = sum(v[1] for v in vals) / len(vals)
    if a - b < 5:
        return []
    return [cand(
        "jutri-pade",
        f"Jutri gobji indeks pade: {pct(a)} → {pct(b)}. Če greste, greste danes.",
        f"Povprečje petih največjih vrst čez 97 območij: danes {pct(a)}, jutri {pct(b)}. "
        f"Kdo gre še danes?", 7)]


def t_weekend(F):
    sat = next((d for d in F["days"][F["t0"]:] if d.weekday() == 5), None)
    if not sat:
        return []
    k = F["days"][F["t0"]:].index(sat)
    best = None
    for s in F["species"]:
        for l in F["locations"]:
            ser = series(F, s["id"], l)
            if k < len(ser) and (best is None or ser[k] > best[0]):
                best = (ser[k], s, l)
    if not best or best[0] < 45:
        return []
    v, s, l = best
    hv = series(F, s["id"], F["home"])[k]
    return [cand(
        "vikend",
        f"Vikend v gozd? {short(F, s['id'])} v soboto: {pct(v)} ({l}), doma {pct(hv)}.",
        f"Najboljša kombinacija za soboto po modelu: {short(F, s['id'])}, {l}, {pct(v)} "
        f"(v Rečici {pct(hv)}). Kam gre vaša pot?", 7)]


def t_year_compare(F):
    months = {}
    for y, rec in (F["trend"].get("years") or {}).items():
        m = rec.get("monthly_avg", {}).get(f"{F['today'].month:02d}")
        if m is not None and y != str(F["today"].year):
            months[y] = m
    if len(months) < 3:
        return []
    avg = sum(months.values()) / len(months)
    mon = ["", "januar", "februar", "marec", "april", "maj", "junij", "julij", "avgust",
           "september", "oktober", "november", "december"][F["today"].month]
    # povprečje letošnjih dni v tem mesecu
    cur = [r["index"] for r in F["idx_hist"]
           if r["date"][:7] == F["today"].strftime("%Y-%m")]
    if len(cur) < 3:
        return []
    c = sum(cur) / len(cur)
    diff = c - avg
    verdict = "boljši" if diff > 0 else "slabši"
    return [cand(
        "leto-primerjava",
        f"{mon.capitalize()} {F['today'].year}: indeks {pct(c)}, v {len(months)} letih {pct(avg)}. Boljše ali slabše?",
        f"Letošnji {mon} ima za zdaj povprečni gobji indeks {pct(c)}, v prejšnjih {len(months)} letih je bil "
        f"{pct(avg)} (letos {verdict} za {abs(int(round(diff)))} točk). "
        f"Se vam zdi, da drži?", 6)]


def t_evergreen(F):
    years = [y for y in (F["trend"].get("years") or {})]
    n = len(years)
    out = []
    if n >= 3:
        out.append(cand(
            "mit-dez",
            f"{n} let podatkov, ena ugotovitev: po dežju ne hitite v gozd.",
            f"Primerjal sem {n} sezon z meritvami postaje. Za mikorizne vrste (jurček, lisička) se okno odpre "
            f"šele {MYCORRHIZAL_LAG_MIN}–{MYCORRHIZAL_LAG_MAX} dni po dežju. Se strinjate ali imate drugačno izkušnjo?", 4))
    out.append(cand(
        "vprasanje",
        "Kje ste letos našli prvega jurčka? In kolikšen dež je prej padel?",
        "Primerjam izkušnje z meritvami postaje. Napišite približno območje (ne točne lokacije!) in datum, "
        "jaz pa dodam, koliko dežja je prej padlo.", 3))
    return out


TEMPLATES = [t_rain_wait, t_rain_window, t_dry, t_frost, t_gap, t_home_vs_best, t_peak,
             t_drop, t_weekend, t_year_compare, t_evergreen]


# --------------------------------------------------------------------------- ocena

def score(c, F):
    t = c["title"]
    s = float(c["base"])
    has_num = any(ch.isdigit() for ch in t)
    s += 2.0 if has_num else -2.0
    if any(sh.lower() in t.lower() for sh in PLURAL.values()):
        s += 1.0
    if "?" in t:
        s += 0.5
    n = len(t)
    if n > 90:
        s -= 4.0
    elif n > 75:
        s -= 2.0
    return round(s, 1)


def build(F):
    out = []
    for tpl in TEMPLATES:
        for c in tpl(F):
            c["score"] = score(c, F)
            c["len"] = len(c["title"])
            out.append(c)
    out.sort(key=lambda c: -c["score"])
    return out


# --------------------------------------------------------------------------- izhod

def latest_gobe_slug():
    posts = load(os.path.join(ROOT, "blog.json"))
    posts = posts if isinstance(posts, list) else posts.get("posts", [])
    for p in posts:
        if "gob" in p.get("slug", "").lower():
            return p
    return posts[0]


def link_for(post, cid):
    q = urllib.parse.urlencode({"utm_source": "facebook", "utm_medium": "group", "utm_campaign": f"gn-{cid}"})
    return f"{SITE}{post['url']}?{q}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datum", help="YYYY-MM-DD (privzeto: datum iz index.json)")
    ap.add_argument("--slug", help="slug članka za link (privzeto: zadnji gobji članek)")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--vse", action="store_true", help="tudi kandidati z oceno < 7")
    ap.add_argument("--izberi", type=int, metavar="N", help="izberi kandidata N: izpiši link + zapiši v dnevnik")
    a = ap.parse_args(argv)

    F = gather(a.datum)
    cands = build(F)
    if not a.vse:
        cands = [c for c in cands if c["score"] >= 7] or cands[:3]
    cands = cands[: a.top]

    posts = load(os.path.join(ROOT, "blog.json"))
    posts = posts if isinstance(posts, list) else posts.get("posts", [])
    post = next((p for p in posts if p.get("slug") == a.slug), None) if a.slug else latest_gobe_slug()
    if not post:
        raise SystemExit(f"slug {a.slug!r} ni v blog.json")

    if a.izberi:
        if not (1 <= a.izberi <= len(cands)):
            raise SystemExit(f"izberi 1..{len(cands)}")
        c = cands[a.izberi - 1]
        url = link_for(post, c["id"])
        print(f"{c['intro']}\n\n{url}\n")
        print(f"Naslov (če ga FB ne vzame iz članka, ga napiši ročno): {c['title']}")
        print(f"Članek: {post['title']}  [{post['slug']}]")
        print("Povezava v prvem komentarju, če skupina skriva zunanje linke.")
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        new = not os.path.exists(LOG)
        with open(LOG, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["datum", "id", "naslov", "slug", "utm_campaign"])
            w.writerow([F["today"].isoformat(), c["id"], c["title"], post["slug"], f"gn-{c['id']}"])
        return 0

    print(f"Datum: {F['today']}  ·  dolina {pct(F['overall'])} ({F['level']})  ·  članek: {post['slug']}")
    if F["last_obs"] and (F["today"] - F["last_obs"]).days > 2:
        print(f"⚠ history.json zaostaja ({F['last_obs']}) — številke o dežju so lahko zastarele.")
    print()
    for i, c in enumerate(cands, 1):
        print(f"{i}. [{c['score']}] {c['title']}   ({c['len']} znakov, {c['id']})")
        print(f"     uvod: {c['intro']}")
        print()
    print("Izbiro: python3 tools/gobe_naslovi.py --izberi N  (izpiše link z UTM in zapiše v dnevnik)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
