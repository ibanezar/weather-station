#!/usr/bin/env python3
"""
tools/generate_dolina_v_tednu.py — »Dolina v tednu«: tedenski povzetek meritev postaje IREICA1 (18. 11. 2026)

Vsak ponedeljek povzetek zadnjega popolnega tedna (pon–ned): skrajne vrednosti, odstopanje od običajnega, padavine,
zmrzal, najmočnejši sunek, novosti s postaje, članki tega tedna in napoved MTR za naslednje dni. Vse številke so izračunane
iz history.json (samo zunanja polja tempHigh/tempLow/tempAvg/precipTotal/windgustHigh; dnevi z src == "era5" izpuščeni),
nič ni vtipkano. Notranjih meritev ne bere.

- `compute()` je čista funkcija (testirana: tools/test_dolina_v_tednu.py). Zapis tedna gre v `data/dolina-v-tednu.json` (najnovejši
  prvi, en zapis na teden), stran `/dolina-v-tednu/` pokaže zadnji teden in arhiv 12 tednov ter obrazec za prijavo na e-pošto.
- E-poštni povzetek (`email_html()`) pošilja `tools/send_dolina_v_tednu.py` prek workerja (`/tedenski/poslji`); prijava je ločena od
  naročnine na nove članke (ločen seznam, dvojni opt-in, `/tedenski/prijava`).
- »Običajno« = enak koledarski teden v prejšnjih letih meritev (±3 dni okoli vsakega dne za temperaturo); primerjava samo, če so
  vsaj 3 prejšnja leta z ≥ 6 dnevi. Postaja meri od novembra 2019: pri letih je malo, besedilo ne trdi več, kot podatki dopuščajo.
- Napoved MTR (poskusni model) je izbrana po datumu, ne po `lead`; če ni današnja ali je starejša od 2 dni, je ni.

Usage:
    python3 tools/generate_dolina_v_tednu.py [--week YYYY-MM-DD(ponedeljek)] [--no-page]
"""
import datetime
import html as _html
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY = os.path.join(ROOT, "history.json")
NOVOSTI = os.path.join(ROOT, "novosti.json")
BLOG = os.path.join(ROOT, "blog.json")
MOS = os.path.join(ROOT, "napoved-modela.json")
DATA = os.path.join(ROOT, "data", "dolina-v-tednu.json")
SITE = "https://meteorec.si"
URL = "/dolina-v-tednu/"
WORKER_BASE = "https://weatherireica1.filip-eremita.workers.dev"
NBSP = " "
MES = ["", "januarja", "februarja", "marca", "aprila", "maja", "junija", "julija", "avgusta", "septembra", "oktobra",
       "novembra", "decembra"]
MIN_DAYS = 6                    # teden z manj dnevi meritev se ne objavi
MIN_PRIOR_YEARS = 3


# ───────────────────────── zapis ─────────────────────────

def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",").replace("-", "–")


def temp(x, d=1):
    return f"{num(x, d)}{NBSP}°C"


def mm(x):
    return f"{num(x, 1)}{NBSP}mm"


def dm(d):
    return f"{d.day}. {d.month}."


def dlong(d):
    return f"{d.day}. {MES[d.month]}"


def dni(n):
    n = int(n)
    return f"{n} {'dan' if n % 100 == 1 else 'dneva' if n % 100 == 2 else 'dni'}"


def v_dneh(n):
    """Mestnik: v 1 dnevu, v 2 dneh, v 6 dneh."""
    n = int(n)
    return f"{n} {'dnevu' if n % 100 == 1 else 'dneh'}"


def noci(n):
    n = int(n)
    return f"{n} {'noč' if n % 100 == 1 else 'noči'}"


def range_label(a, b):
    return f"{a.day}.–{b.day}. {b.month}. {b.year}" if a.month == b.month else f"{a.day}. {a.month}.–{b.day}. {b.month}. {b.year}"


# ───────────────────────── izračun ─────────────────────────

def load_days():
    H = json.load(open(HISTORY, encoding="utf-8"))
    H = H.get("days", H)
    return {datetime.date.fromisoformat(k): v for k, v in H.items() if v.get("src") != "era5"}


def last_full_week(last_day):
    """Ponedeljek zadnjega tedna, ki se je do `last_day` (vključno) že končal (nedelja <= last_day)."""
    end = last_day if last_day.weekday() == 6 else last_day - datetime.timedelta(days=last_day.weekday() + 1)
    return end - datetime.timedelta(days=6)


def _val(days, d, f):
    v = days.get(d)
    return None if v is None else v.get(f)


def _week(start):
    return [start + datetime.timedelta(i) for i in range(7)]


def _prior(days, start, f, window=0):
    """[(leto, [vrednosti])]: iste koledarske dni v prejšnjih letih (z oknom ±window dni okoli vsakega dne)."""
    out = []
    for y in range(2019, start.year):
        vals = []
        for d in _week(start):
            try:
                c = d.replace(year=y)
            except ValueError:
                continue
            for o in range(-window, window + 1):
                v = _val(days, c + datetime.timedelta(o), f)
                if v is not None:
                    vals.append(v)
        out.append((y, vals))
    return out


def compute(days, start, novosti=(), blog=(), mos=None, today=None):
    """Zapis tedna za `start` (ponedeljek) ali None, če je podatkov premalo."""
    wk = _week(start)
    have = [d for d in wk if _val(days, d, "tempHigh") is not None and _val(days, d, "tempLow") is not None]
    if len(have) < MIN_DAYS:
        return None
    hi = max(have, key=lambda d: days[d]["tempHigh"])
    lo = min(have, key=lambda d: days[d]["tempLow"])
    avgs = [days[d]["tempAvg"] for d in have if days[d].get("tempAvg") is not None]
    t_avg = statistics.mean(avgs) if avgs else None
    precs = [(d, days[d]["precipTotal"]) for d in wk if _val(days, d, "precipTotal") is not None]
    rain = sum(p for _, p in precs)
    wet_days = sum(1 for _, p in precs if p >= 0.2)
    wettest = max(precs, key=lambda x: x[1]) if precs else None
    frost = sum(1 for d in have if days[d]["tempLow"] <= 0)
    ice = sum(1 for d in have if days[d]["tempHigh"] <= 0)
    gusts = [(d, days[d]["windgustHigh"]) for d in wk if _val(days, d, "windgustHigh") is not None]
    gust = max(gusts, key=lambda x: x[1]) if gusts else None

    # običajno: ista koledarska tedna v prejšnjih letih
    t_norm = None
    pri_t = [statistics.mean(v) for y, v in _prior(days, start, "tempAvg", window=3) if len(v) >= MIN_DAYS * 3]
    if len(pri_t) >= MIN_PRIOR_YEARS and t_avg is not None:
        t_norm = statistics.mean(pri_t)
    r_norm = None
    pri_r = []
    for y in range(2019, start.year):
        yr = []
        for d in wk:
            try:
                v = _val(days, d.replace(year=y), "precipTotal")
            except ValueError:
                v = None
            if v is not None:
                yr.append(v)
        if len(yr) >= MIN_DAYS:
            pri_r.append(sum(yr) * 7 / len(yr))
    if len(pri_r) >= MIN_PRIOR_YEARS:
        r_norm = statistics.mean(pri_r)
    anom = None if t_norm is None else t_avg - t_norm

    # naslov tedna (prvo pravilo, ki velja)
    if r_norm is not None and rain >= 20 and rain >= 2 * r_norm:
        short = "moker teden"
        headline = f"Moker teden: {mm(rain)} padavin, to je {num(rain / r_norm, 1)}-krat več kot običajno."
    elif r_norm is not None and rain < 1 and r_norm >= 5:
        short = "skoraj suh teden"
        headline = f"Skoraj suh teden: {mm(rain)} padavin, običajno jih je v tem tednu okoli {mm(r_norm)}."
    elif anom is not None and abs(anom) >= 2:
        short = "toplejši teden" if anom > 0 else "hladnejši teden"
        headline = f"Teden je bil za {temp(abs(anom))} {'toplejši' if anom > 0 else 'hladnejši'} od običajnega."
    elif frost >= 4:
        short = f"{noci(frost)} z zmrzaljo"
        headline = f"{noci(frost).capitalize()} z zmrzaljo v enem tednu: najnižja {temp(days[lo]['tempLow'])}."
    elif gust and gust[1] >= 50:
        short = "vetroven teden"
        headline = f"Vetroven teden: najmočnejši sunek {num(gust[1], 0)}{NBSP}km/h ({dlong(gust[0])})."
    else:
        short = "običajen teden"
        headline = (f"Običajen teden: povprečno {temp(t_avg)}, padavin {mm(rain)}." if t_avg is not None else
                    f"Padavin {mm(rain)}.")

    lines = [f"Najvišja temperatura {temp(days[hi]['tempHigh'])} ({dlong(hi)}), najnižja {temp(days[lo]['tempLow'])} ({dlong(lo)})."]
    if t_avg is not None:
        s = f"Povprečna temperatura {temp(t_avg)}"
        s += f" (običajno za ta teden {temp(t_norm)})." if t_norm is not None else "."
        lines.append(s)
    if precs:
        s = f"Padavine {mm(rain)} v {v_dneh(wet_days)} z dežjem ali snegom (vsaj 0,2{NBSP}mm)"
        if wettest and wettest[1] >= 0.2:
            s += f", najbolj moker dan {dlong(wettest[0])} ({mm(wettest[1])})"
        s += f"; običajno {mm(r_norm)}." if r_norm is not None else "."
        lines.append(s)
    if frost or ice:
        s = f"{noci(frost).capitalize()} z najnižjo temperaturo ≤ 0{NBSP}°C"
        s += f", od tega {dni(ice)} brez odmrznitve (najvišja ≤ 0{NBSP}°C)." if ice else "."
        lines.append(s)
    if gust:
        lines.append(f"Najmočnejši sunek vetra {num(gust[1], 0)}{NBSP}km/h ({dlong(gust[0])}).")

    end = wk[-1]
    nov = [{"title": e.get("label", ""), "url": f"/novosti/{e['slug']}/", "date": e["date"]}
           for e in novosti if e.get("slug") and start.isoformat() <= e.get("date", "") <= end.isoformat()]
    posts = [{"title": p["title"], "url": p.get("url") or f"/blog/{p['slug']}.html", "date": p["date"]}
             for p in blog if start.isoformat() <= p.get("date", "") <= end.isoformat()]

    napoved = []
    today = today or datetime.date.today()
    if mos:
        gen = (mos.get("generated_at") or "")[:10]
        try:
            fresh = gen and (today - datetime.date.fromisoformat(gen)).days <= 2
        except ValueError:
            fresh = False
        if fresh:
            for r in mos.get("days") or []:
                try:
                    d = datetime.date.fromisoformat(r["date"])
                except (KeyError, ValueError):
                    continue
                if end < d <= end + datetime.timedelta(days=4) and r.get("tmax") is not None and r.get("tmin") is not None:
                    s = f"{dlong(d)}: najvišja okoli {num(r['tmax'], 0)}{NBSP}°C, najnižja okoli {num(r['tmin'], 0)}{NBSP}°C"
                    if r.get("p_frost") is not None and r["p_frost"] >= 0.3:
                        s += f", zmrzal {num(5 * round(100 * r['p_frost'] / 5), 0)}{NBSP}%"
                    napoved.append(s)

    return {"week_start": start.isoformat(), "week_end": end.isoformat(), "n_days": len(have), "headline": headline,
            "lines": lines, "novosti": nov, "blog": posts, "napoved": napoved,
            "subject": f"Dolina v tednu {range_label(start, end)}: {short}",
            "stat": {"tmax": days[hi]["tempHigh"], "tmin": days[lo]["tempLow"], "rain_mm": round(rain, 1),
                     "frost_nights": frost, "t_avg": None if t_avg is None else round(t_avg, 2),
                     "t_norm": None if t_norm is None else round(t_norm, 2), "rain_norm_mm": None if r_norm is None else round(r_norm, 1)}}


# ───────────────────────── e-pošta in stran ─────────────────────────

def _li(items):
    return "".join(f'<li style="margin:.25rem 0">{_html.escape(x).replace("&nbsp;", NBSP)}</li>' for x in items)


def email_html(rec):
    """HTML e-pošte; {{ODJAVA}} nadomesti worker z osebno povezavo za odjavo."""
    a, b = datetime.date.fromisoformat(rec["week_start"]), datetime.date.fromisoformat(rec["week_end"])
    link = lambda t: f'<a href="{SITE}{t["url"]}" style="color:#2563eb">{_html.escape(t["title"])}</a>'
    parts = [f'<h2 style="margin:0 0 .3rem">Dolina v tednu</h2><p style="margin:0 0 1rem;color:#555">{range_label(a, b)} · postaja IREICA1, Rečica ob Savinji</p>',
             f'<p style="font-size:1.1rem;font-weight:600;margin:.2rem 0 .8rem">{_html.escape(rec["headline"])}</p>',
             f'<ul style="padding-left:1.2rem;margin:0 0 1rem">{_li(rec["lines"])}</ul>']
    if rec["novosti"]:
        parts.append('<h3 style="margin:1rem 0 .3rem;font-size:1rem">Novosti s postaje</h3><ul style="padding-left:1.2rem;margin:0">' +
                     "".join(f'<li style="margin:.25rem 0">{link(n)}</li>' for n in rec["novosti"]) + "</ul>")
    if rec["blog"]:
        parts.append('<h3 style="margin:1rem 0 .3rem;font-size:1rem">Na blogu</h3><ul style="padding-left:1.2rem;margin:0">' +
                     "".join(f'<li style="margin:.25rem 0">{link(n)}</li>' for n in rec["blog"]) + "</ul>")
    if rec["napoved"]:
        parts.append('<h3 style="margin:1rem 0 .3rem;font-size:1rem">Kaj prihaja (poskusni model MTR)</h3><ul style="padding-left:1.2rem;margin:0">' +
                     _li(rec["napoved"]) + '</ul><p style="color:#777;font-size:.85rem">Napoved je modelska, ne uradna. Za opozorila velja ARSO.</p>')
    parts.append(f'<p style="margin:1.2rem 0"><a href="{SITE}{URL}" style="display:inline-block;background:#2563eb;color:#fff;padding:.6rem 1.2rem;'
                 'border-radius:8px;text-decoration:none;font-weight:600">Povzetek na spletu →</a></p>'
                 '<hr style="border:none;border-top:1px solid #eee;margin:1.5rem 0">'
                 '<p style="color:#999;font-size:.8rem">Prejemate, ker ste se prijavili na tedenski povzetek »Dolina v tednu«. '
                 'Podatki so s postaje IREICA1 (zunanji senzor). <a href="{{ODJAVA}}" style="color:#999">Odjava z enim klikom</a>.</p>')
    return '<div style="font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:560px;color:#111;line-height:1.5">' + "".join(parts) + "</div>"


def update_data(rec, path=DATA):
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        data = []
    data = [r for r in data if r["week_start"] != rec["week_start"]]
    data.insert(0, rec)
    data.sort(key=lambda r: r["week_start"], reverse=True)
    data = data[:60]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return data


def build_page(data):
    import generate_seo_pages as seo
    latest = data[0]
    a, b = datetime.date.fromisoformat(latest["week_start"]), datetime.date.fromisoformat(latest["week_end"])

    def card(r, big=False):
        sa, sb = datetime.date.fromisoformat(r["week_start"]), datetime.date.fromisoformat(r["week_end"])
        lis = "".join(f"<li>{_html.escape(x)}</li>" for x in r["lines"])
        extra = ""
        if big and r["novosti"]:
            extra += "<h3>Novosti s postaje</h3><ul>" + "".join(f'<li><a href="{n["url"]}">{_html.escape(n["title"])}</a></li>' for n in r["novosti"]) + "</ul>"
        if big and r["blog"]:
            extra += "<h3>Na blogu</h3><ul>" + "".join(f'<li><a href="{n["url"]}">{_html.escape(n["title"])}</a></li>' for n in r["blog"]) + "</ul>"
        if big and r["napoved"]:
            extra += "<h3>Kaj je prihajalo (poskusni model MTR)</h3><ul>" + "".join(f"<li>{_html.escape(x)}</li>" for x in r["napoved"]) + "</ul>"
        return (f'<div class="card dt-card"><div class="clabel">{range_label(sa, sb)}</div><p class="dt-head">{_html.escape(r["headline"])}</p>'
                f'<ul class="dt-list">{lis}</ul>{extra}</div>')
    archive = "".join(card(r) for r in data[1:12])
    faq = [("Kaj dobim v e-pošti?", "Vsak ponedeljek en kratek povzetek preteklega tedna na postaji IREICA1: najvišja in najnižja temperatura, odstopanje od običajnega, padavine, zmrzal, "
            "novosti s postaje, članki tega tedna in napoved poskusnega modela MTR za nekaj dni naprej."),
           ("Kaj pomeni »običajno«?", "Povprečje istega koledarskega tedna v prejšnjih letih meritev (postaja meri od novembra 2019). Primerjava se izpiše samo, če so vsaj tri prejšnja leta s podatki; "
            "ob tako kratkem nizu je to orientacija, ne klimatološka norma."),
           ("Kako se prijavim in odjavim?", "Vpišete e-naslov, nato potrdite prijavo v sporočilu, ki ga prejmete (dvojni opt-in). Vsako sporočilo ima povezavo za odjavo z enim klikom. "
            "E-naslov uporabljamo samo za ta povzetek in ga ne združujemo z naročnino na nove blog članke."),
           ("Koliko je to v e-pošti uradno?", "Nič: so meritve amaterske postaje in modelska napoved. Uradna opozorila izdaja ARSO.")]
    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Dolina v tednu", None)])}
  <h1 class="page-title">Dolina v tednu: tedenski povzetek vremena v Rečici</h1>
  <p class="post-meta">Vsak ponedeljek · meritve postaje IREICA1 · po želji tudi v e-pošti</p>
  <p class="archive-intro">Kaj se je zgodilo v dolini prejšnji teden: skrajne vrednosti, odstopanje od običajnega, padavine in zmrzal, novosti s postaje in kratka napoved poskusnega modela MTR.
  Spodaj je zadnji teden; povzetek lahko prejemate tudi po e-pošti.</p>
  <style>
  .dt-card{{margin-bottom:1rem}} .dt-head{{font-weight:600;font-size:1.05rem;margin:.3rem 0 .6rem}} .dt-list{{padding-left:1.2rem;display:grid;gap:.3rem}}
  .dt-card h3{{font-size:.95rem;margin:1rem 0 .3rem}} .dt-form{{display:flex;flex-wrap:wrap;gap:.6rem;margin-top:.6rem}}
  .dt-form input[type=email]{{flex:1 1 14rem;min-height:44px;padding:.4rem .7rem;border-radius:10px;border:1px solid var(--card-border,var(--border));background:var(--card-bg);color:var(--text);font-size:1rem}}
  .dt-hp{{position:absolute;left:-9999px}} .dt-msg{{min-height:1.3em;font-size:.9rem;margin-top:.4rem}}
  </style>
  <div class="card dt-card"><div class="clabel">Prejemajte povzetek po e-pošti</div>
    <form class="dt-form" id="dt-form" autocomplete="off"><input type="email" id="dt-email" required maxlength="120" placeholder="vas@email.si" aria-label="E-naslov">
      <input class="dt-hp" type="text" id="dt-hp" tabindex="-1" autocomplete="off" aria-hidden="true"><button type="submit" class="mtn-avk-link" id="dt-btn">Prijava</button></form>
    <div class="dt-msg" id="dt-msg" aria-live="polite"></div>
    <p class="vs-note" style="color:var(--muted);font-size:.82rem">Z dvojno potrditvijo, odjava z enim klikom. E-naslov uporabimo samo za ta povzetek.</p></div>
  <h2>Zadnji teden</h2>
  {card(latest, True)}
  <h2>Prejšnji tedni</h2>
  {archive or '<p class="archive-intro">Arhiv se začne s prvim objavljenim tednom.</p>'}
  <h2>Pogosta vprašanja</h2>
  <div class="faq">{"".join(f"<details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>" for q, a in faq)}</div>
  <p class="vs-note" style="color:var(--muted);font-size:.82rem">Vir: postaja IREICA1, Rečica ob Savinji (366 m), zunanji senzor. Napoved MTR je poskusni statistični model, ne uradna napoved.</p>
  <a class="back-link" href="/">← Vreme v Rečici</a>
<script>
(function(){{var API="{WORKER_BASE}",f=document.getElementById("dt-form");if(!f)return;var m=document.getElementById("dt-msg"),b=document.getElementById("dt-btn");
f.addEventListener("submit",function(e){{e.preventDefault();if(document.getElementById("dt-hp").value)return;var v=document.getElementById("dt-email").value.trim();
if(!v){{m.textContent="Vpišite e-naslov.";return;}}b.disabled=true;m.textContent="Pošiljam …";
fetch(API+"/tedenski/prijava",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{email:v,website:""}})}})
.then(function(r){{return r.json().then(function(j){{return {{ok:r.ok,j:j}};}});}})
.then(function(x){{b.disabled=false;if(!x.ok||x.j.error){{m.textContent=x.j.error||"Napaka pri prijavi.";return;}}
m.textContent=x.j.already?"Ta e-naslov je že prijavljen.":"Skoraj gotovo: v e-pošti potrdite prijavo.";if(!x.j.already)f.reset();}})
.catch(function(){{b.disabled=false;m.textContent="Napaka v povezavi, poskusite znova.";}});}});}})();
</script>'''
    title = "Dolina v tednu: tedenski povzetek vremena v Rečici"
    desc = f"Tedenski povzetek meritev postaje v Rečici ob Savinji: skrajne vrednosti, padavine, zmrzal, novosti in napoved. Zadnji teden: {range_label(a, b)}."
    if len(desc) > 160:
        desc = "Tedenski povzetek meritev postaje v Rečici ob Savinji: skrajne vrednosti, padavine, zmrzal in novosti. Tudi po e-pošti."
    assert len(title) <= 60 and len(desc) <= 160, (len(title), len(desc))
    schema = "\n".join([seo.webpage_schema(URL, title, desc, date_published="2026-11-18", ), seo.crumbs_schema([("Meteorec", "/"), ("Dolina v tednu", None)]),
                        seo.faq_schema(faq)])
    seo.write_page("dolina-v-tednu/index.html", seo.page_shell(title, desc, URL, schema, body), force=True)
    print("  → dolina-v-tednu/index.html")


def main():
    days = load_days()
    last = max(days)
    start = datetime.date.fromisoformat(sys.argv[sys.argv.index("--week") + 1]) if "--week" in sys.argv else last_full_week(last)
    assert start.weekday() == 0, "teden se začne v ponedeljek"
    novosti = json.load(open(NOVOSTI, encoding="utf-8"))
    blog = json.load(open(BLOG, encoding="utf-8"))
    try:
        mos = json.load(open(MOS, encoding="utf-8"))
    except (OSError, ValueError):
        mos = None
    rec = compute(days, start, novosti, blog, mos)
    if rec is None:
        print(f"Teden {start}: premalo podatkov (< {MIN_DAYS} dni); nič zapisano.")
        return 0
    data = update_data(rec)
    print(f"✓ {os.path.relpath(DATA, ROOT)}: {rec['week_start']}… {rec['headline']}")
    if "--no-page" not in sys.argv:
        build_page(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
