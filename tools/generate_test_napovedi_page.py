#!/usr/bin/env python3
"""
tools/generate_test_napovedi_page.py — /test-napovedi/ (Faza 4 v brief-u).

Bere data/test-napovedi.json (izračuna ga tools/compute_forecast_test_metrics.py)
in izriše:
  - test-napovedi/index.html — lestvica natančnosti, SVG grafi (client-side,
    brez zunanjih JS knjižnic — isti vzorec kot TREND_JS v generate_gobe_page.py:
    stran fetcha JSON in nariše <svg> v brskalniku), metodologija, FAQ.
  - test-napovedi/podatki.csv — javni izvoz razrešenih napovedi (samo dnevi, ki
    že imajo dejansko meritev), z licenco/viri v glavi.

Faza 4, graf "pristranskost po urah dneva" iz brief-a NI vključen: zahteval bi
urne napovedi vseh petih modelov (ne samo dnevne agregate), kar bi arhiv
povečalo za ~150x (celoten repo bi zrasel na ~200 MB) samo za en graf. Namesto
tega stran pokaže isto zgodbo (spregledana temperaturna inverzija) prek
razlike med Tmax- in Tmin-pristranskostjo pri D+1, ki je iz že izračunanih
metrik na voljo zastonj — glej build_bias_chart_data().

Usage:
  python3 tools/generate_test_napovedi_page.py
"""
import csv, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

ROOT = seo.ROOT
SITE = seo.SITE
TODAY = seo.TODAY
DATA_PATH = os.path.join(ROOT, "data", "test-napovedi.json")
ARCHIVE_PATH = os.path.join(ROOT, "data", "forecast-archive.csv")
FORWARD_LOG_PATH = os.path.join(ROOT, "data", "forecast-forward-log.csv")
HISTORY_PATH = os.path.join(ROOT, "history.json")
PAGE_DIR = os.path.join(ROOT, "test-napovedi")
CSV_OUT = os.path.join(PAGE_DIR, "podatki.csv")

MIN_SAMPLE_DAYS = 60  # brief: pod tem se ne razglaša zmagovalec


def load_data():
    try:
        with open(DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


# ── CSV izvoz ────────────────────────────────────────────────────────────────

def write_csv():
    hist = json.load(open(HISTORY_PATH, encoding="utf-8"))
    rows_out = []
    for path in (ARCHIVE_PATH, FORWARD_LOG_PATH):
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                actual = hist.get(r["valid_at"])
                if not actual or actual.get("src") not in ("station", "wu"):
                    continue  # samo razrešeni dnevi z veljavno postajno meritvijo
                a_tmax, a_tmin, a_precip = actual.get("tempHigh"), actual.get("tempLow"), actual.get("precipTotal")
                p_tmax = float(r["tmax_c"]) if r["tmax_c"] else None
                p_tmin = float(r["tmin_c"]) if r["tmin_c"] else None
                rows_out.append({
                    "source": r["model"], "issued_at": r["issued_at"], "valid_at": r["valid_at"],
                    "lead_days": r["lead_days"],
                    "predicted_tmax_c": r["tmax_c"], "predicted_tmin_c": r["tmin_c"],
                    "predicted_precip_mm": r["precip_mm"],
                    "actual_tmax_c": a_tmax, "actual_tmin_c": a_tmin, "actual_precip_mm": a_precip,
                    "err_tmax_c": round(p_tmax - a_tmax, 2) if p_tmax is not None and a_tmax is not None else "",
                    "err_tmin_c": round(p_tmin - a_tmin, 2) if p_tmin is not None and a_tmin is not None else "",
                })
    rows_out.sort(key=lambda r: (r["source"], int(r["lead_days"]), r["valid_at"]))

    os.makedirs(PAGE_DIR, exist_ok=True)
    fields = ["source", "issued_at", "valid_at", "lead_days", "predicted_tmax_c", "predicted_tmin_c",
              "predicted_precip_mm", "actual_tmax_c", "actual_tmin_c", "actual_precip_mm",
              "err_tmax_c", "err_tmin_c"]
    with open(CSV_OUT, "w", encoding="utf-8", newline="") as f:
        f.write(
            "# Meteorec test-napovedi -- primerjava vremenskih napovedi z meritvami postaje IREICA1 "
            "(Recica ob Savinji, Zgornja Savinjska dolina)\n"
            f"# Vir napovedi: Open-Meteo Previous Runs API (ecmwf_ifs025, icon_seamless, gfs_seamless, "
            f"meteofrance_arpege_europe, best_match), ARSO (vreme.arso.gov.si), Yr/MET Norway (api.met.no)\n"
            "# Vir meritev: postaja IREICA1 (Ecowitt), src=station/wu v history.json\n"
            f"# Licenca podatkov Meteorec: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/) -- "
            f"navedi vir: {SITE}/test-napovedi/\n"
            f"# Posodobljeno: {TODAY.isoformat()} -- {len(rows_out)} vrstic\n"
            "# lead_days = koliko dni vnaprej je bila napoved izdana; err_* = napoved - dejansko (predznak "
            "pove smer: + precenjuje, - podcenjuje)\n"
        )
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows_out:
            w.writerow(r)
    return len(rows_out)


# ── SVG grafi (client-side, brez zunanjih JS knjižnic) ────────────────────────

CHART_JS = """<script>
(function(){
  var wrap = document.getElementById("tnp-charts");
  if (!wrap) return;
  var COLORS = ["#38bdf8", "#f59e0b", "#34d399", "#f472b6", "#a78bfa"];

  function esc(s){ return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

  function maeChart(data){
    var models = Object.keys(data.models);
    var leads = [1,2,3,4,5,6,7];
    var W=680,H=280,padL=38,padR=14,padT=14,padB=28;
    var plotW=W-padL-padR, plotH=H-padT-padB;
    var maxMae = data.climatology.tmax.mae || 4;
    models.forEach(function(m){ leads.forEach(function(l){
      var r=(data.results[m]||{})[l];
      if(r && r.tmax && r.tmax.mae!=null) maxMae=Math.max(maxMae, r.tmax.mae);
    }); });
    maxMae = Math.ceil(maxMae*1.1*10)/10;
    function x(l){ return padL+plotW*((l-1)/(leads.length-1)); }
    function y(v){ return padT+plotH*(1-Math.max(0,v)/maxMae); }

    var svg='<svg viewBox="0 0 '+W+' '+H+'" class="tnp-svg" preserveAspectRatio="xMidYMid meet">';
    [0,1,2,3,4].forEach(function(i){
      var v = maxMae*i/4;
      svg += '<line x1="'+padL+'" y1="'+y(v)+'" x2="'+(W-padR)+'" y2="'+y(v)+'" stroke="rgba(255,255,255,.08)"/>';
      svg += '<text x="'+(padL-6)+'" y="'+(y(v)+3)+'" text-anchor="end" font-size="9" fill="var(--muted)">'+v.toFixed(1)+'</text>';
    });
    leads.forEach(function(l){
      svg += '<text x="'+x(l)+'" y="'+(H-8)+'" text-anchor="middle" font-size="9" fill="var(--muted)">D+'+l+'</text>';
    });
    // klimatologija -- vodoravna referencna crta
    var climoMae = data.climatology.tmax.mae;
    if (climoMae != null){
      svg += '<line x1="'+padL+'" y1="'+y(climoMae)+'" x2="'+(W-padR)+'" y2="'+y(climoMae)+
        '" stroke="#f87171" stroke-width="1.5" stroke-dasharray="5,4"/>';
      svg += '<text x="'+(W-padR)+'" y="'+(y(climoMae)-4)+'" text-anchor="end" font-size="9" fill="#f87171">klimatologija ('+climoMae.toFixed(1)+')</text>';
    }
    models.forEach(function(m,mi){
      var pts=[];
      leads.forEach(function(l){
        var r=(data.results[m]||{})[l];
        if(r && r.tmax && r.tmax.mae!=null) pts.push(x(l)+","+y(r.tmax.mae));
      });
      if(pts.length<2) return;
      var col=COLORS[mi%COLORS.length];
      svg += '<polyline points="'+pts.join(" ")+'" fill="none" stroke="'+col+'" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>';
      leads.forEach(function(l){
        var r=(data.results[m]||{})[l];
        if(r && r.tmax && r.tmax.mae!=null) svg += '<circle cx="'+x(l)+'" cy="'+y(r.tmax.mae)+'" r="2.6" fill="'+col+'"/>';
      });
    });
    svg += '</svg>';
    var legend = '<div class="tnp-legend">';
    models.forEach(function(m,mi){ legend += '<span><i style="background:'+COLORS[mi%COLORS.length]+'"></i>'+esc(data.models[m])+'</span>'; });
    legend += '<span><i style="background:#f87171"></i>klimatologija (izhodišče)</span></div>';
    return '<div class="tnp-chart-title">MAE najvišje temperature glede na vodilni čas</div>' + svg + legend;
  }

  function biasChart(data){
    var models = Object.keys(data.models);
    var W=680,H=240,padL=38,padR=14,padT=14,padB=44;
    var plotW=W-padL-padR, plotH=H-padT-padB;
    var vals=[];
    models.forEach(function(m){
      var r=(data.results[m]||{})[1];
      if(r){ if(r.tmax&&r.tmax.bias!=null) vals.push(r.tmax.bias); if(r.tmin&&r.tmin.bias!=null) vals.push(r.tmin.bias); }
    });
    var maxAbs = Math.max(1, Math.ceil(Math.max.apply(null, vals.map(Math.abs).concat([1]))*10)/10);
    function y(v){ return padT + plotH*(1 - (v+maxAbs)/(2*maxAbs)); }
    var zero = y(0);
    var groupW = plotW/models.length;
    var svg='<svg viewBox="0 0 '+W+' '+H+'" class="tnp-svg" preserveAspectRatio="xMidYMid meet">';
    svg += '<line x1="'+padL+'" y1="'+zero+'" x2="'+(W-padR)+'" y2="'+zero+'" stroke="rgba(255,255,255,.25)"/>';
    svg += '<text x="'+(padL-6)+'" y="'+(zero+3)+'" text-anchor="end" font-size="9" fill="var(--muted)">0</text>';
    svg += '<text x="'+(padL-6)+'" y="'+(y(maxAbs)+3)+'" text-anchor="end" font-size="9" fill="var(--muted)">+'+maxAbs.toFixed(1)+'</text>';
    svg += '<text x="'+(padL-6)+'" y="'+(y(-maxAbs)+3)+'" text-anchor="end" font-size="9" fill="var(--muted)">-'+maxAbs.toFixed(1)+'</text>';
    models.forEach(function(m,mi){
      var r=(data.results[m]||{})[1];
      var gx = padL + groupW*mi;
      var bw = groupW*0.32;
      ["tmax","tmin"].forEach(function(k,ki){
        var b = r && r[k] ? r[k].bias : null;
        if(b==null) return;
        var bx = gx + groupW*0.18 + ki*bw*1.15;
        var by0 = zero, by1 = y(b);
        var top = Math.min(by0,by1), h = Math.abs(by1-by0);
        var col = ki===0 ? "#38bdf8" : "#f59e0b";
        svg += '<rect x="'+bx+'" y="'+top+'" width="'+bw+'" height="'+Math.max(h,1)+'" fill="'+col+'" fill-opacity="'+(ki===0?0.9:0.9)+'"/>';
      });
      svg += '<text x="'+(gx+groupW/2)+'" y="'+(H-26)+'" text-anchor="middle" font-size="9" fill="var(--muted)">'+esc(data.models[m])+'</text>';
    });
    svg += '</svg>';
    var legend = '<div class="tnp-legend"><span><i style="background:#38bdf8"></i>Tmax pristranskost</span>'+
      '<span><i style="background:#f59e0b"></i>Tmin pristranskost</span></div>';
    return '<div class="tnp-chart-title">Pristranskost pri D+1: precenjuje (+) / podcenjuje (-), °C</div>'
      + '<p class="tnp-chart-note">Model, ki precenjuje Tmin (topel steber čez noč) in podcenjuje Tmax (hladen podnevi), '
      + 'ni ujel temperaturne inverzije na dnu doline — točno signatura, ki jo lokalna postaja lovi, model na mreži pa ne.</p>'
      + svg + legend;
  }

  function farChart(data){
    var models = Object.keys(data.models);
    var W=680,H=220,padL=38,padR=14,padT=14,padB=40;
    var plotW=W-padL-padR, plotH=H-padT-padB;
    var barW = plotW/models.length*0.55;
    function y(v){ return padT + plotH*(1-Math.max(0,Math.min(1,v))); }
    var svg='<svg viewBox="0 0 '+W+' '+H+'" class="tnp-svg" preserveAspectRatio="xMidYMid meet">';
    [0,.25,.5,.75,1].forEach(function(v){
      svg += '<line x1="'+padL+'" y1="'+y(v)+'" x2="'+(W-padR)+'" y2="'+y(v)+'" stroke="rgba(255,255,255,.08)"/>';
      svg += '<text x="'+(padL-6)+'" y="'+(y(v)+3)+'" text-anchor="end" font-size="9" fill="var(--muted)">'+Math.round(v*100)+'%</text>';
    });
    var groupW = plotW/models.length;
    models.forEach(function(m,mi){
      var r=(data.results[m]||{})[1];
      var ct = r && r.precip_contingency ? r.precip_contingency["0.2"] : null;
      var far = ct ? ct.far : null;
      var gx = padL + groupW*mi + (groupW-barW)/2;
      if (far!=null){
        svg += '<rect x="'+gx+'" y="'+y(far)+'" width="'+barW+'" height="'+(y(0)-y(far))+'" fill="'+COLORS[mi%COLORS.length]+'"/>';
        svg += '<text x="'+(gx+barW/2)+'" y="'+(y(far)-4)+'" text-anchor="middle" font-size="9" fill="var(--muted)">'+Math.round(far*100)+'%</text>';
      }
      svg += '<text x="'+(gx+barW/2)+'" y="'+(H-24)+'" text-anchor="middle" font-size="9" fill="var(--muted)">'+esc(data.models[m])+'</text>';
    });
    svg += '</svg>';
    return '<div class="tnp-chart-title">Delež lažnih alarmov za dež pri D+1 (prag ≥ 0,2 mm)</div>'
      + '<p class="tnp-chart-note">Kolikokrat je vir napovedal dež, pa ga ni bilo — od vseh primerov, ko je napovedal dež.</p>'
      + svg;
  }

  fetch("/data/test-napovedi.json")
    .then(function(r){ if(!r.ok) throw 0; return r.json(); })
    .then(function(data){
      wrap.innerHTML = '<div class="tnp-chart-block">'+maeChart(data)+'</div>'
        + '<div class="tnp-chart-block">'+biasChart(data)+'</div>'
        + '<div class="tnp-chart-block">'+farChart(data)+'</div>';
    })
    .catch(function(){ wrap.innerHTML = '<div class="gp-msg">Grafi trenutno niso na voljo.</div>'; });
})();
</script>"""

CHART_CSS = """<style>
.tnp-chart-block{margin:1.6rem 0}
.tnp-chart-title{font-family:'JetBrains Mono',monospace;font-size:.7rem;letter-spacing:.06em;
  text-transform:uppercase;color:var(--cyan,#38bdf8);opacity:.85;margin-bottom:.3rem}
.tnp-chart-note{font-size:.85rem;color:var(--muted);margin:.2rem 0 .5rem}
.tnp-svg{width:100%;height:auto;display:block}
.tnp-legend{display:flex;flex-wrap:wrap;gap:.9rem;margin-top:.4rem;font-size:.8rem;color:var(--muted)}
.tnp-legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:.3rem;vertical-align:middle}
</style>"""


# ── Stran ──────────────────────────────────────────────────────────────────

def num(x, d=1):
    return seo.num(x, d)


def build_body(data, n_csv_rows):
    models = data["models"]
    results = data["results"]
    climo = data["climatology"]
    pers = data["persistence"]
    n_obs = data.get("n_compared_days") or data["n_obs_days"]
    zero_crossing = data.get("zero_crossing_lead_days") or {}
    forward_labels = data.get("forward_models") or {}
    forward_n = data.get("forward_n") or {}

    # D+1 lestvica
    d1_rows = []
    for m, label in models.items():
        r = (results.get(m) or {}).get("1") or (results.get(m) or {}).get(1)
        if r and r["tmax"].get("mae") is not None:
            d1_rows.append((label, r["tmax"]["mae"], r["tmin"]["mae"]))
    d1_rows.sort(key=lambda x: x[1])

    sample_warning = ""
    if n_obs < MIN_SAMPLE_DAYS:
        sample_warning = (
            f'  <div class="warn-banner lvl-none">Vzorec ({n_obs} dni) je manjši od {MIN_SAMPLE_DAYS} dni — '
            'razlike med viri so lahko statistično naključne. Zmagovalca še ne razglašamo.</div>\n')

    winner_html = ""
    if not sample_warning and d1_rows:
        best = d1_rows[0]
        worst_tmin = max(
            ((label, r["tmin"]["bias"]) for m, label in models.items()
             for r in [(results.get(m) or {}).get("1") or (results.get(m) or {}).get(1)]
             if r and r["tmin"].get("bias") is not None),
            key=lambda x: x[1], default=None)
        winner_html = (
            f'  <p class="archive-intro"><strong>{best[0]}</strong> ima pri napovedi za jutri (D+1) najmanjšo '
            f'povprečno napako najvišje temperature: ±{num(best[1])} °C. '
            + (f'Največjo pristranskost pri jutranjem minimumu ima {worst_tmin[0]} '
               f'({"precenjuje" if worst_tmin[1] > 0 else "podcenjuje"} za {num(abs(worst_tmin[1]))} °C v povprečju) — '
               'znak, da model ne ujame nočnega hladnega zraka na dnu doline.'
               if worst_tmin else '') + '</p>\n')

    cards = '  <div class="stat-grid">\n'
    for label, mae_tx, mae_tn in d1_rows:
        cards += (f'    <div class="stat-card c-temp"><div class="sc-label">{label}</div>'
                   f'<div class="sc-val">±{num(mae_tx)}</div><div class="sc-sub">°C, D+1 Tmax MAE · Tmin ±{num(mae_tn)} °C</div></div>\n')
    cards += '  </div>'

    # Zero-crossing / skill besedilo
    crossing_lines = []
    for m, label in models.items():
        lead = zero_crossing.get(m)
        if lead:
            crossing_lines.append(f'{label} pade na raven klimatologije pri D+{lead}')
        else:
            crossing_lines.append(f'{label} ostane boljši od klimatologije skozi ves D+1..D+7 vzorec')
    crossing_html = ('  <h2 id="prelom">Po katerem dnevu napoved ni več boljša od klimatologije?</h2>\n'
                      '  <p class="archive-intro">Skill = 1 − MAE<sub>model</sub> / MAE<sub>klimatologija</sub>. '
                      'Vrednost 0 pomeni, da je napoved enakovredna ugibanju dolgoletnega povprečja za ta koledarski dan '
                      f'(±{num(climo["tmax"]["mae"])} °C za Tmax, izračunano iz cele postajne zgodovine). '
                      + ("V tem vzorcu (D+1..D+7) noben od petih virov te meje ne doseže — vsi ostanejo pred "
                         "klimatologijo tudi teden vnaprej, čeprav razlika pada z vsakim dnem." if not zero_crossing else
                         "; ".join(crossing_lines) + ".") + '</p>')

    # Persistenca
    pers_html = (f'  <p class="archive-intro"><strong>Persistenca</strong> ("jutri bo tako kot danes") doseže '
                 f'Tmax MAE ±{num(pers["tmax"].get("mae"))} °C, Tmin ±{num(pers["tmin"].get("mae"))} °C — '
                 'preprosta primerjava poleg klimatologije, brez modela.</p>')

    # ── Mesečna tabela po viru/vodilnem času ──────────────────────────────
    lead_table_rows = []
    for lead in range(1, 8):
        cells = []
        any_data = False
        for m in models:
            r = (results.get(m) or {}).get(str(lead)) or (results.get(m) or {}).get(lead)
            if r and r["tmax"].get("mae") is not None:
                cells.append(f'<td>±{num(r["tmax"]["mae"])} °C</td>')
                any_data = True
            else:
                cells.append('<td>—</td>')
        if any_data:
            lead_table_rows.append(f'    <tr><th>D+{lead}</th>' + "".join(cells) + '</tr>')
    lead_table = ('  <table class="table-scroll stats">\n    <tr><th>Vodilni čas</th>'
                  + "".join(f'<th>{l}</th>' for l in models.values()) + '</tr>\n'
                  + "\n".join(lead_table_rows) + '\n  </table>')

    # ── ARSO/Yr sprotno beleženje ──────────────────────────────────────────
    forward_html = ""
    if forward_labels:
        total_forward = sum(forward_n.values())
        names = ", ".join(forward_labels.values())
        if total_forward == 0:
            forward_html = (
                f'  <h2>Kmalu tudi: {names}</h2>\n'
                f'  <p class="archive-intro">{names} nimata javnega arhiva preteklih napovedi, zato ju beležimo '
                'sproti od danes naprej — vsak dan zabeležimo napoved za naslednjih 7 dni in jo primerjamo z '
                'dejansko meritvijo, ko dan mine. Zbiranje se je začelo danes; prve primerjave bodo na voljo v '
                'naslednjih tednih.</p>')
        else:
            forward_html = (
                f'  <h2>{names} — sprotno beleženi viri</h2>\n'
                f'  <p class="archive-intro">Brez arhiva za nazaj, zato krajša zgodovina: '
                + "; ".join(f'{forward_labels[m]}: {forward_n[m]} razrešenih napovedi' for m in forward_labels)
                + '.</p>')

    # ── Metodologija (obvezne opombe iz brief-a) ────────────────────────────
    methodology = f'''  <h2>Metodologija</h2>
  <p class="archive-intro">Rezultat velja <strong>izključno za Zgornjo Savinjsko dolino</strong> (postaja IREICA1,
  Rečica ob Savinji) — dno ozke alpske doline, kjer se ponoči nabira hladen zrak in podnevi sonce dolino hitro
  segreje. To ni splošna ocena teh modelov za Slovenijo ali kjerkoli drugje.</p>
  <p class="archive-intro">ARSO napoveduje po <strong>regijah</strong>, ne po točkah — za Rečico ob Savinji nima
  krajevne napovedi, zato jemljemo najbližji kraj z njihovega seznama (Ljubno ob Savinji, ~9 km gorvodno).
  Modeli Open-Meteo delujejo na mreži: ECMWF IFS ima ločljivost ~25 km, GFS ~25 km, ARPEGE ~10 km, ICON (prek
  best_match) ~2 km (ICON-D2) — noben od njih ozke doline v resnici ne razloči. To ni opravičilo, ampak glavna
  poanta: napaka izvira (tudi) iz ločljivosti mreže, zato ima lokalna postaja sploh smisel.</p>
  <p class="archive-intro"><strong>Klimatologija</strong>: povprečni Tmax/Tmin za ta koledarski dan ±7 dni, iz cele
  postajne zgodovine (2019–danes). <strong>Persistenca</strong>: "jutri bo tako kot danes" (dejanska včerajšnja
  vrednost). Obe izhodišči merita, koliko modeli dejansko prispevajo nad preprosto ugibanje.</p>
  <p class="archive-intro">Kontrola kakovosti meritev: uporabljeni so samo dnevi z veljavno meritvijo prave
  postaje (ne modelska rezerva), fizikalno smiselno vrednostjo (Tmax≥Tmin, -25..45 °C). Urno preverjanje
  "&gt;10 % manjkajočih ur" in "zataknjen senzor &gt;6h" na tem arhivu ni izvedljivo — Ecowitt API vrne polno
  urno ločljivost le za zadnjih ~90 dni, starejši dnevi so na strežniku že podvzorčeni. Graf "pristranskost po
  urah dneva" iz prvotnega načrta zato nadomešča primerjava Tmax- in Tmin-pristranskosti zgoraj, ki isto zgodbo
  (spregledana nočna inverzija) pove brez potrebe po urnem arhivu napovedi vseh petih virov.</p>
  <p class="archive-intro">V besedilu namenoma ne uporabljamo besede "laže" — modeli se motijo, precenjujejo ali
  podcenjujejo, ne lažejo; napaka izvira iz fizike in ločljivosti, ne iz namena.</p>'''

    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in [
            ("Kateri vremenski model je najbolj natančen za Zgornjo Savinjsko dolino?",
             f'Pri napovedi za jutri (D+1) ima v tem vzorcu ({n_obs} dni) najnižjo povprečno napako '
             f'{d1_rows[0][0] if d1_rows else "—"}. Razlike med viri se z vodilnim časom (D+2, D+3, …) spreminjajo — '
             'glej tabelo po vodilnem času zgoraj.'),
            ("Kaj pomeni skill score?",
             "1 minus razmerje med povprečno napako modela in povprečno napako klimatologije (dolgoletnega "
             "povprečja za ta koledarski dan). 0 pomeni, da napoved ni boljša od ugibanja povprečja; 1 bi "
             "pomenil popolno napoved."),
            ("Zakaj moja vremenska aplikacija kaže drugo številko kot postaja?",
             "Večina aplikacij uporablja model best_match ali podoben globalni model na mreži, ki naše ozke "
             "doline ne razloči — mreža vidi pobočje, ne dna doline. Ta stran meri prav to razliko."),
            ("Od kdaj tečejo podatki?",
             f'Napovedi Open-Meteo (pet modelov) so na voljo za nazaj vse od {seo.fmtd("2024-05-26")} '
             '(Open-Meteo Previous Runs API arhivira toliko nazaj). ARSO in Yr/MET Norway nimata arhiva preteklih '
             'napovedi, zato ju beležimo sproti od dneva, ko je ta stran nastala.'),
        ]
    ) + "\n  </div>"

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Test napovedi", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Test napovedi — kateri model najbolje napove vreme v Zgornji Savinjski dolini?</h1>
  <p class="post-meta">Pet virov vs. dejanska meritev IREICA1 · {n_obs} razrešenih dni · {TODAY.isoformat()}</p>
{sample_warning}{winner_html}
{cards}
  <div id="tnp-charts">Grafi se nalagajo …</div>
{crossing_html}
{pers_html}
  <h2>Natančnost po vodilnem času (Tmax MAE, °C)</h2>
{lead_table}
{forward_html}
{methodology}
  <h2>Surovi podatki</h2>
  <p class="archive-intro">Celoten podatkovni niz (napoved vsakega vira, dejanska meritev, napaka) je javno na
  voljo za prenos: <a href="/test-napovedi/podatki.csv" style="color:var(--blue)">podatki.csv</a>
  ({n_csv_rows} vrstic, licenca CC BY 4.0 — pri uporabi navedi vir). Viri: Open-Meteo (previous-runs-api.open-meteo.com),
  ARSO (vreme.arso.gov.si), Yr/MET Norway (api.met.no), meritve postaje IREICA1.</p>
{faq_html}
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''
    return body


def main():
    data = load_data()
    if not data:
        sys.exit("data/test-napovedi.json manjka — najprej poženi compute_forecast_test_metrics.py")

    n_csv_rows = write_csv()
    body = build_body(data, n_csv_rows) + "\n" + CHART_JS

    url = "/test-napovedi/"
    title = "Test napovedi — Zgornja Savinjska dolina"
    n = data.get("n_compared_days") or data.get("n_obs_days", 0)
    desc = (f"Kateri vremenski model najbolje napove vreme v Zgornji Savinjski dolini? Primerjava petih virov "
            f"(ECMWF, ICON, GFS, ARPEGE, ARSO) z dejansko meritvijo postaje IREICA1 po dnevih vnaprej — "
            f"{n} razrešenih dni, javni podatki.")

    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published=TODAY.isoformat()),
        seo.crumbs_schema([("Meteorec", "/"), ("Test napovedi", None)]),
        seo.named_dataset_schema(
            url, "Test napovedi — primerjava modelov proti postaji IREICA1",
            "Dnevna primerjava napovedi ECMWF, ICON, GFS, ARPEGE, best_match, ARSO in Yr/MET Norway z "
            "dejansko meritvijo postaje IREICA1, po vodilnem času D+1..D+7.",
            variable_measured=[{"@type": "PropertyValue", "name": "Razrešeni dnevi", "value": n, "unitText": "dni"}],
            distribution={"@type": "DataDownload", "encodingFormat": "text/csv",
                          "contentUrl": f"{seo.SITE}/test-napovedi/podatki.csv"},
        ),
    ]) + "\n" + CHART_CSS

    html_out = seo.page_shell(title, desc, url, schema, body)
    seo.write_page("test-napovedi/index.html", html_out, force=True)
    print(f"  → test-napovedi/index.html ({n} razrešenih dni)")
    print(f"  → test-napovedi/podatki.csv ({n_csv_rows} vrstic)")


if __name__ == "__main__":
    main()
