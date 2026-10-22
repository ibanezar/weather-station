#!/usr/bin/env python3
"""
tools/generate_sinopticna_page.py — /sinopticna/ (21. 10. 2026)

Sinoptična karta Evrope iz ECMWF IFS (open data, 0,25°, CC BY 4.0): tlak na morski gladini z izobarami in
temperatura na 850 hPa (karta 1), geopotencialna višina 500 hPa (karta 2), za +0, +24, +48, +72 in +96 ur
od zadnjega 00 UTC teka. Ideja po polarnivrtinec.si (»Sinoptična«); karte so naše, risane iz surovih polj.

Kar stran je in ni:
- IZRISAN IZHOD MODELA (en tek, 0,25°), ne analiza in ne uradna napoved ARSO. Front NI: fronte so analiza
  sinoptika, ne polje modela — stran ne trdi, da jih prikazuje.
- Brez podatkov postaje; notranjih meritev tu ni.

Karte (WebP) se vsak dan prepišejo na isto ime (`sinopticna/karte/…`), da repozitorij ne raste z arhivom.

Usage:
  python3 tools/generate_sinopticna_page.py              # prenesi zadnji tek, nariši, zapiši stran
  python3 tools/generate_sinopticna_page.py --grib-dir D # uporabi že prenesene GRIB-e (razvoj, testi)
"""
import argparse
import datetime
import html as _html
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atmos_common as ac  # noqa: E402

STEPS = [0, 24, 48, 72, 96]
OUT_DIR = os.path.join(ac.ROOT, "sinopticna", "karte")
DATA_PATH = os.path.join(ac.ROOT, "data", "sinopticna.json")
REL = "/sinopticna/"
MAPS = [("tlak", "Tlak in T850", "tlak-t850"), ("z500", "Višina 500 hPa", "z500")]
CREDIT = "Vir: ECMWF IFS open data (CC BY 4.0) · izris: meteorec.si · ni uradna napoved"
RECICA = (14.92, 46.33)

FAQ = [
    ("Ali so to uradne sinoptične karte?",
     "Ne. To je izris enega teka modela ECMWF IFS (odprti podatki, ločljivost 0,25°), ki ga narišemo sami. Fronte "
     "na kartah niso narisane, ker jih ne računa model, ampak jih po analizi vrišejo sinoptiki. Za uradno "
     "napoved in opozorila glej ARSO."),
    ("Kaj so izobare in zakaj so pomembne?",
     "Izobare so črte enakega zračnega tlaka, preračunanega na morsko gladino. Gosto ležeče izobare pomenijo "
     "močan veter. H je središče območja visokega tlaka (običajno mirno, v hladni polovici leta z inverzijo in "
     "meglo v kotlinah), L središče ciklona (oblačno, padavine, veter)."),
    ("Kaj pomeni temperatura na 850 hPa?",
     "To je temperatura na višini približno 1500 m, kjer je zrak prost vpliva tal. Po njej se bolje primerja "
     "zračne mase kot po temperaturi pri tleh. Pozimi je T850 pod −5 °C pogosto znak, da lahko sneži tudi nizko, "
     "a to ni pravilo: odloča tudi plast pod 850 hPa."),
    ("Kaj kaže karta višine 500 hPa?",
     "Geopotencialno višino ploskve 500 hPa (približno 5,5 km). Nizke vrednosti (modro) označujejo višinske "
     "doline z mrzlim zrakom, visoke (rdeče) grebene s toplim. Hitrost zahodnika sledi gostoti črt, "
     "premiki dolin in grebenov pa napovedujejo spremembe vremena."),
    ("Kako pogosto se karte osveži?",
     "Vsak dan po izidu 00 UTC teka (okoli 8. ure po naši uri). Čas veljavnosti vsake karte je napisan nad njo, "
     "če je teka na strani več kot dan starega, to piše spodaj."),
]


def fetch(dest_dir):
    """Prenese zadnji 00 UTC tek (msl, gh500, t850 za STEPS). Vrne (datum teka, pot msl, pot pl)."""
    from ecmwf.opendata import Client
    os.makedirs(dest_dir, exist_ok=True)
    cl = Client(source="ecmwf", model="ifs", resol="0p25")
    run = cl.latest(type="fc", stream="oper", step=96, param="msl", time=0)
    day = run.date()
    sfc = os.path.join(dest_dir, "msl.grib2")
    pl = os.path.join(dest_dir, "pl.grib2")
    base = dict(date=day.strftime("%Y%m%d"), time=0, type="fc", stream="oper", step=STEPS)
    cl.retrieve(request=dict(base, param=["msl"]), target=sfc)
    cl.retrieve(request=dict(base, param=["gh", "t"], levelist=[500, 850]), target=pl)
    return day, sfc, pl


def load(sfc, pl):
    """GRIB-i → slovar {(spremenljivka, korak): (lats, lons, vrednosti)} samo za zahtevane nivoje."""
    out = {}
    for short, level, step, lats, lons, vals in ac.grib_messages(sfc):
        if short == "msl":
            out[("msl", step)] = ac.crop_grid(lats, lons, vals / 100.0)  # Pa → hPa
    for short, level, step, lats, lons, vals in ac.grib_messages(pl):
        if short == "gh" and level == 500:
            out[("z500", step)] = ac.crop_grid(lats, lons, vals / 10.0)  # gpm → gpdam
        elif short == "t" and level == 850:
            out[("t850", step)] = ac.crop_grid(lats, lons, vals - 273.15)
    return out


def _mark_recica(ax):
    x, y = ac.LCC.xy(RECICA[0], RECICA[1])
    ax.plot([x], [y], marker="o", ms=5, mfc="#e11d48", mec="white", mew=1.2, zorder=12)
    ax.text(x + 40, y - 70, "Rečica", fontsize=8, color="#be123c", zorder=12, fontweight="bold")


def _valid_text(run_dt, step):
    v = run_dt + datetime.timedelta(hours=step)
    return f"{v.day}. {v.month}. {v.year} ob {v.hour:02d}:00 UTC"


def draw_pressure(data, run_dt, step, path):
    import matplotlib.pyplot as plt
    import numpy as np
    lats, lons, msl = data[("msl", step)]
    _, _, t850 = data[("t850", step)]
    LON, LAT = np.meshgrid(lons, lats)
    X, Y = ac.LCC.xy(LON, LAT)
    fig, ax = ac.new_map(f"Tlak na morski gladini (hPa) in temperatura na 850 hPa (°C) · +{step} h",
                         f"ECMWF IFS, tek {run_dt:%d. %m. %Y} {run_dt:%H} UTC · veljavno {_valid_text(run_dt, step)}",
                         CREDIT)
    levels = list(range(-28, 33, 4))
    cf = ax.contourf(X, Y, t850, levels=levels, cmap="RdYlBu_r", extend="both", alpha=0.82, zorder=2)
    lv = np.arange(940, 1066, 4)
    cs = ax.contour(X, Y, msl, levels=lv, colors="#1b2735", linewidths=0.8, zorder=7)
    ax.clabel(cs, fmt="%d", fontsize=7, inline=True, inline_spacing=3)
    cs2 = ax.contour(X, Y, msl, levels=[1000, 1020], colors="#1b2735", linewidths=1.5, zorder=7)
    hi, lo = ac.local_extrema(msl, size=41, prominence=3.0, min_dist=44)
    for (j, i), kind, color in [(p, "H", "#1d4ed8") for p in hi] + [(p, "L", "#b91c1c") for p in lo]:
        x, y = X[j, i], Y[j, i]
        if not (ac.MAP_X[0] + 120 < x < ac.MAP_X[1] - 120 and ac.MAP_Y[0] + 120 < y < ac.MAP_Y[1] - 120):
            continue
        ax.text(x, y, kind, fontsize=17, fontweight="bold", color=color, ha="center", va="center", zorder=10)
        ax.text(x, y - 95, f"{msl[j, i]:.0f}", fontsize=8, color=color, ha="center", va="center", zorder=10)
    _mark_recica(ax)
    cax = fig.add_axes([0.62, 0.035, 0.36, 0.014])
    cb = fig.colorbar(cf, cax=cax, orientation="horizontal", ticks=list(range(-28, 33, 8)))
    cb.ax.tick_params(labelsize=7, length=2)
    cb.outline.set_linewidth(0.4)
    ac.save_webp(fig, path)


def draw_z500(data, run_dt, step, path):
    import numpy as np
    lats, lons, z = data[("z500", step)]
    LON, LAT = np.meshgrid(lons, lats)
    X, Y = ac.LCC.xy(LON, LAT)
    fig, ax = ac.new_map(f"Geopotencialna višina 500 hPa (gpdam) · +{step} h",
                         f"ECMWF IFS, tek {run_dt:%d. %m. %Y} {run_dt:%H} UTC · veljavno {_valid_text(run_dt, step)}",
                         CREDIT)
    levels = list(range(504, 600, 6))
    cf = ax.contourf(X, Y, z, levels=levels, cmap="RdYlBu_r", extend="both", alpha=0.85, zorder=2)
    cs = ax.contour(X, Y, z, levels=levels, colors="#1b2735", linewidths=0.8, zorder=7)
    ax.clabel(cs, fmt="%d", fontsize=7, inline=True, inline_spacing=3)
    _mark_recica(ax)
    cax = fig.add_axes([0.62, 0.035, 0.36, 0.014])
    cb = fig.colorbar(cf, cax=cax, orientation="horizontal", ticks=list(range(504, 600, 24)))
    cb.ax.tick_params(labelsize=7, length=2)
    cb.outline.set_linewidth(0.4)
    ac.save_webp(fig, path)


def render_all(data, run_dt):
    files = {}
    for step in STEPS:
        for key, _label, stem in MAPS:
            name = f"{stem}-{step:03d}.webp"
            path = os.path.join(OUT_DIR, name)
            (draw_pressure if key == "tlak" else draw_z500)(data, run_dt, step, path)
            files[(key, step)] = name
            print(f"  → sinopticna/karte/{name} ({os.path.getsize(path) // 1024} KB)")
    return files


def build_body(run_dt, generated_utc):
    valid = {s: _valid_text(run_dt, s) for s in STEPS}
    btns = "".join(
        f'<button type="button" class="sy-step{" on" if s == 0 else ""}" data-step="{s}">+{s} h</button>'
        for s in STEPS)
    tabs = "".join(
        f'<button type="button" class="sy-tab{" on" if i == 0 else ""}" data-map="{k}">{_html.escape(lbl)}</button>'
        for i, (k, lbl, _) in enumerate(MAPS))
    stems = {k: stem for k, _l, stem in MAPS}
    first = f"/sinopticna/karte/{stems['tlak']}-000.webp"
    age_note = ""
    try:
        age_h = (datetime.datetime.now(datetime.timezone.utc) - run_dt).total_seconds() / 3600
        if age_h > 36:
            age_note = (f'  <p class="callout"><strong>Podatki niso sveži:</strong> zadnji tek je star '
                        f'{age_h / 24:.0f} dni. Karte ostajajo, dokler se ne osveži (glej opombo spodaj).</p>\n')
    except Exception:
        pass
    run_local = ac.fmt_dt_local(run_dt.strftime("%Y-%m-%dT%H:%M:%SZ"))
    return f'''  <h1 class="page-title">Sinoptična karta Evrope: tlak, T850 in višina 500 hPa</h1>
  <p class="post-meta">ECMWF IFS, tek {run_dt:%-d. %-m. %Y} ob {run_dt:%H} UTC · stran osvežena {_html.escape(ac.fmt_dt_local(generated_utc))}</p>
  <p class="archive-intro">Izobare, območja visokega in nizkega tlaka, temperatura na višini 1500 m in višinske
  doline in grebeni nad Evropo za naslednje štiri dni. To je <b>izris enega teka modela</b> (odprti podatki ECMWF,
  0,25°), ne analiza in ne uradna napoved. Rdeča pika je Rečica ob Savinji. Za Slovenijo glej
  <a href="/primerjava-modelov/">primerjavo modelov za Rečico</a> in <a href="/nevihte/">nevihtno karto</a>.</p>
{age_note}  <div class="sy" id="sy">
    <div class="sy-bar" role="tablist" aria-label="Vrsta karte">{tabs}</div>
    <div class="sy-bar" role="group" aria-label="Čas napovedi">{btns}</div>
    <p class="muted-note" id="sy-valid">Veljavno: {_html.escape(valid[0])}</p>
    <img id="sy-img" src="{first}" width="960" height="740" alt="Sinoptična karta Evrope: tlak na morski gladini
 in temperatura na 850 hPa, ECMWF IFS, +0 h" style="width:100%;height:auto;border-radius:12px">
    <noscript><p class="muted-note">Za preklop časa in karte je potreben JavaScript. Karte so tudi neposredno:
    {" · ".join(f'<a href="/sinopticna/karte/{stems[k]}-{s:03d}.webp">{_html.escape(l)} +{s} h</a>' for k, l, _ in MAPS for s in STEPS)}.</p></noscript>
  </div>
  <h2>Kako brati karti</h2>
  <p class="archive-intro"><strong>Črne črte (izobare)</strong> so tlak v hPa na vsake 4 hPa, debelejši sta 1000 in
  1020. <strong>H</strong> in <strong>L</strong> sta središči visokega in nizkega tlaka z vrednostjo.
  <strong>Barve</strong> na prvi karti so temperatura na 850 hPa (okoli 1500 m), na drugi geopotencialna višina
  ploskve 500 hPa v dekametrih. Na višinski karti hladne doline (modro) pogosto spremljajo dež, sneg in veter.</p>
  <h2>Kar karte niso</h2>
  <p class="archive-intro">Fronte niso narisane: model jih ne računa, sinoptiki jih vrišejo po analizi. Ločljivost
  0,25° (okoli 20 km) ne razloči doline, zato za Rečico uporabi napoved za točko. Zadnja osvežitev: tek {run_local} (naša ura).
  Podatke je pripravil ECMWF in jih objavlja pod licenco <a href="https://creativecommons.org/licenses/by/4.0/"
  rel="noopener" target="_blank">CC BY 4.0</a>; izris je naš.</p>'''


JS = '''<script>
(function(){
  var root=document.getElementById("sy"); if(!root) return;
  var img=document.getElementById("sy-img"), valid=document.getElementById("sy-valid");
  var stems={tlak:"tlak-t850",z500:"z500"}, state={map:"tlak",step:0};
  var VALID=__VALID__, ALT={tlak:"Sinoptična karta Evrope: tlak na morski gladini in temperatura na 850 hPa, ECMWF IFS, +",
    z500:"Višinska karta Evrope: geopotencialna višina 500 hPa, ECMWF IFS, +"};
  function pad(n){return ("00"+n).slice(-3);}
  function show(){
    img.src="/sinopticna/karte/"+stems[state.map]+"-"+pad(state.step)+".webp?v=__V__";
    img.alt=ALT[state.map]+state.step+" h";
    valid.textContent="Veljavno: "+VALID[state.step];
    [].forEach.call(root.querySelectorAll(".sy-tab"),function(b){b.classList.toggle("on",b.dataset.map===state.map);});
    [].forEach.call(root.querySelectorAll(".sy-step"),function(b){b.classList.toggle("on",+b.dataset.step===state.step);});
  }
  root.addEventListener("click",function(e){
    var t=e.target.closest("button"); if(!t) return;
    if(t.dataset.map) state.map=t.dataset.map;
    if(t.dataset.step) state.step=+t.dataset.step;
    show();
  });
})();
</script>'''

CSS = '''<style>
.sy-bar{display:flex;flex-wrap:wrap;gap:.45rem;margin:.5rem 0}
.sy-tab,.sy-step{font:inherit;font-size:.92rem;padding:.55rem .9rem;min-height:44px;border-radius:999px;cursor:pointer;
 background:var(--card-bg);color:var(--text);border:1px solid var(--card-border)}
.sy-tab.on,.sy-step.on{background:#0f766e;border-color:#14b8a6;color:#fff}
.sy-tab:focus-visible,.sy-step:focus-visible{outline:2px solid #5eead4;outline-offset:2px}
</style>'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grib-dir", help="že preneseni msl.grib2 in pl.grib2 (brez prenosa)")
    ap.add_argument("--force", action="store_true", help="nariši znova, tudi če je tek že obdelan")
    ap.add_argument("--run", help="ISO datum teka (YYYY-MM-DD) ob --grib-dir; privzeto iz data/sinopticna.json")
    args = ap.parse_args()
    try:
        if args.grib_dir:
            day = datetime.datetime.fromisoformat(args.run) if args.run else datetime.datetime.now()
            sfc, pl = os.path.join(args.grib_dir, "msl.grib2"), os.path.join(args.grib_dir, "pl.grib2")
        else:
            import tempfile
            day, sfc, pl = fetch(tempfile.mkdtemp(prefix="ecmwf-"))
    except Exception as e:  # noqa: BLE001
        # Brez novega teka ostane stran z zadnjimi kartami; napaka se vidi kot rdeč tek.
        print(f"✗ prenos ECMWF: {e}", file=sys.stderr)
        return 1
    run_dt = datetime.datetime(day.year, day.month, day.day, 0, tzinfo=datetime.timezone.utc)
    meta = ac.read_json(DATA_PATH, {})
    if meta.get("run") == run_dt.strftime("%Y-%m-%dT%H:%MZ") and not (args.grib_dir or args.force):
        print("  tek že obdelan, brez sprememb")
        return 0
    data = load(sfc, pl)
    missing = [(k, s) for k in ("msl", "z500", "t850") for s in STEPS if (k, s) not in data]
    if missing:
        print(f"✗ manjkajo polja: {missing}", file=sys.stderr)
        return 1
    files = render_all(data, run_dt)
    generated = ac.now_utc_iso()
    ac.write_json(DATA_PATH, {"run": run_dt.strftime("%Y-%m-%dT%H:%MZ"), "generated_at": generated,
                              "steps": STEPS, "files": {f"{k}:{s}": v for (k, s), v in files.items()},
                              "source": "ECMWF IFS open data 0.25 deg, CC BY 4.0"})
    valid_js = "{" + ",".join(f'{s}:"{_valid_text(run_dt, s)}"' for s in STEPS) + "}"
    js = JS.replace("__VALID__", valid_js).replace("__V__", run_dt.strftime("%Y%m%d%H"))
    body = build_body(run_dt, generated) + "\n" + js
    title = "Sinoptična karta Evrope: tlak, T850, višina 500 hPa"
    desc = ("Izobare, tlak, T850 in višina 500 hPa nad Evropo za 4 dni iz ECMWF IFS. Izris enega teka, "
            "ne uradna napoved.")
    ac.write_site_page(REL + "index.html", REL, title, desc, body, FAQ, "Sinoptična karta", "2026-10-22",
                       modified=generated[:10],
                       extra_head=CSS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
