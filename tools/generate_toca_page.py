#!/usr/bin/env python3
"""
tools/generate_toca_page.py — /toca/ pillar page (toča-tracker)

Generates /toca/index.html: static ARSO hail-warning status, a crowdsourced
photo archive (community reports pulled from the R2-backed gallery,
category=toca) and a station-based proxy signal for convective days from
history.json. Targets local hail searches ("toča danes Savinjska dolina",
"je bila toča v Mozirju", "škoda toča hmelj").

The community archive and the upload form are the actual crowdsourcing
mechanism: the page ships the last known reports baked into static HTML
(crawlable, no JS required), and a small inline script re-fetches
/gallery?category=toca on load to hydrate it with anything submitted since
the last build — same "static shell + JS hydration" pattern used for the
homepage's live measurement.

Sources:
  - ARSO warnings via the Cloudflare Worker (/arso-warning) — ARSO blocks
    direct requests from cloud IPs, so we proxy through the same Worker
    .github/workflows/arso-alerts.yml already uses.
  - Community photo reports via the Worker's R2-backed gallery
    (/gallery?category=toca).
  - history.json — heavy-rain + high-gust warm-season days as a
    supplementary, station-based proxy signal. Clearly labelled as
    inferred, not a confirmed hail measurement — the station has no
    dedicated hail sensor.

Usage:
  python3 tools/generate_toca_page.py
"""
import html, json, os, sys, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers

ROOT = seo.ROOT
SITE = seo.SITE
TODAY = seo.TODAY
WORKER = "https://weatherireica1.filip-eremita.workers.dev"
UA = {"User-Agent": "Mozilla/5.0 (compatible; Meteorec-Toca/1.0; +https://meteorec.si)"}


def fetch_json(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def fetch_arso_alerts():
    try:
        data = fetch_json(f"{WORKER}/arso-warning?region=SLOVENIA_NORTH-EAST")
        return data.get("alerts", [])
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"⚠ ARSO opozorila nedosegljiva: {e}", file=sys.stderr)
        return []


def fetch_toca_reports():
    try:
        data = fetch_json(f"{WORKER}/gallery?category=toca")
        return data.get("photos", [])
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"⚠ Skupnostna galerija nedosegljiva: {e}", file=sys.stderr)
        return []


def hail_alert():
    """Najhujše aktivno opozorilo, ki izrecno omenja točo (WarningTS besedilo)."""
    best = None
    rank = {"yellow": 1, "orange": 2, "red": 3}
    for a in fetch_arso_alerts():
        blob = f"{a.get('text','')} {a.get('desc','')} {a.get('more','')}".lower()
        if "toč" not in blob:
            continue
        if best is None or rank.get(a.get("level"), 0) > rank.get(best.get("level"), 0):
            best = a
    return best


def convective_candidates(hist, n=8):
    """Topli-del-leta dnevi z izrazitim nalivom + sunki vetra — orientacijski
    signal za pogoje, v katerih je toča verjetna. Postaja nima senzorja za
    točo, zato tega NE prikazujemo kot potrjeno točo."""
    cands = []
    for d, v in hist.items():
        try:
            month = int(d[5:7])
        except (ValueError, IndexError):
            continue
        if month not in (5, 6, 7, 8, 9):
            continue
        precip = v.get("precipTotal") or 0
        gust = v.get("windgustHigh")
        if gust is None or precip < 10 or gust < 30:
            continue
        cands.append((d, precip, gust))
    cands.sort(key=lambda x: (x[1] + x[2]), reverse=True)
    return cands[:n]


def esc(s):
    return html.escape(str(s or ""), quote=True)


def fmtd_short(iso):
    try:
        y, m, d = int(iso[:4]), int(iso[5:7]), int(iso[8:10])
        return f"{d}. {seo.MES_GEN[m]} {y}"
    except (ValueError, IndexError, KeyError):
        return iso


def build_report_card(p):
    key = p.get("key", "")
    img_url = f"{WORKER}/gallery/img/{urllib.parse.quote(key, safe='')}"
    loc = esc(p.get("location") or "Lokacija ni navedena")
    caption = esc(p.get("caption") or "")
    uploaded = p.get("uploadedAt") or p.get("uploaded") or ""
    date_txt = fmtd_short(uploaded[:10]) if len(uploaded) >= 10 else ""
    meta = date_txt + (f" · {caption}" if caption else "")
    return (f'    <div class="toca-photo-card">\n'
            f'      <img src="{esc(img_url)}" alt="{loc}" loading="lazy" width="190" height="143">\n'
            f'      <div class="tp-overlay"><div class="tp-loc">📍 {loc}</div>'
            f'<div class="tp-meta">{esc(meta)}</div></div>\n'
            f'    </div>')


def build_body(alert, reports, hist):
    now_txt = seo.TODAY.isoformat()

    # ── Opozorilni pas ────────────────────────────────────────────────────
    if alert:
        level = alert.get("level", "yellow")
        desc = alert.get("desc") or alert.get("text") or "Opozorilo pred nevihtami s točo."
        time_str = alert.get("timeStr", "")
        warn = (f'  <div class="warn-banner lvl-{level}">⚠️ <strong>ARSO opozorilo '
                f'({level.upper()})</strong> — {esc(desc)}'
                + (f' <span style="opacity:.8">({esc(time_str)})</span>' if time_str else "")
                + '</div>')
        lede = (f'Danes velja ARSO opozorilo pred nevihtami s točo (stopnja <strong>{level}</strong>) '
                f'za širšo regijo — v Zgornji Savinjski dolini spremljaj lokalno napoved na '
                f'<a href="/#tab-storm">domači strani (zavihek Nevihte)</a>, kjer je urna verjetnost '
                f'toče za naslednjih 12 ur.')
    else:
        warn = ('  <div class="warn-banner lvl-none">Trenutno ni izdanega uradnega ARSO opozorila '
                'pred točo za severovzhodno Slovenijo / Savinjsko regijo.</div>')
        lede = ('Trenutno ni aktivnega uradnega opozorila pred točo, a nevihtna sezona (maj–september) '
                'v Zgornji Savinjski dolini vsako leto prinese nekaj epizod toče. Urno napoved tveganja '
                'za naslednjih 12 ur najdeš na <a href="/#tab-storm">domači strani (zavihek Nevihte)</a>.')

    intro = (f'  <p class="archive-intro">{lede} Spodaj je arhiv prijav uporabnikov iz doline '
              f'(fotografija + lokacija) in orientacijski pregled dni z izrazito nevihtno aktivnostjo '
              f'po meritvah postaje IREICA1. Zadnja osvežitev: {now_txt}.</p>')

    # ── Skupnostni arhiv (crowdsourcing) ───────────────────────────────────
    if reports:
        cards = "\n".join(build_report_card(p) for p in reports[:60])
        gallery_html = f'  <div class="toca-photo-grid" id="toca-grid">\n{cards}\n  </div>'
        count_txt = f'{len(reports)} prijav skupnosti'
    else:
        gallery_html = ('  <div class="toca-photo-empty" id="toca-grid">Še ni prijav — bodi prvi, ki '
                         'javi točo v svojem kraju. 👇</div>')
        count_txt = "še ni prijav"

    # ── Postajni proxy-signal ───────────────────────────────────────────────
    cands = convective_candidates(hist)
    if cands:
        rows = "\n".join(
            f'      <tr><th><a href="/vreme/{d[:4]}/{d[5:7]}/{d[8:10]}/">{fmtd_short(d)}</a></th>'
            f'<td>{seo.num(p, 1)} mm padavin · sunki do {seo.num(g, 1)} km/h</td></tr>'
            for d, p, g in cands
        )
        conv_table = f'  <table class="stats">\n{rows}\n  </table>'
    else:
        conv_table = '  <p class="muted-note">Trenutno ni zabeleženih dni, ki bi ustrezali pragu.</p>'

    # ── Sorodni članki ───────────────────────────────────────────────────
    try:
        posts = json.load(open(os.path.join(ROOT, "blog.json"), encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        posts = []
    related = [p for p in posts if any("toč" in t.lower() for t in p.get("tags", []))
               or "toč" in p.get("title", "").lower()][:5]
    if related:
        rel_html = "  <ul class=\"muted-note\" style=\"list-style:disc;padding-left:1.2rem\">\n" + "\n".join(
            f'    <li><a href="{esc(p["url"])}">{esc(p["title"])}</a> — {esc(p["date"])}</li>' for p in related
        ) + "\n  </ul>"
    else:
        rel_html = ""

    # ── Prijavni obrazec ─────────────────────────────────────────────────
    form_html = '''  <div class="card">
    <div class="clabel">📷 Prijavi točo v svojem kraju</div>
    <form class="toca-form" id="toca-form" onsubmit="return tocaSubmit(event)">
      <div>
        <label for="toca-loc">Kraj (npr. Mozirje, Nazarje, Ljubno ob Savinji) *</label>
        <input type="text" id="toca-loc" maxlength="120" required placeholder="Kraj dogodka">
      </div>
      <div>
        <label for="toca-caption">Opis (velikost zrn, škoda na pridelku/hmelju …)</label>
        <textarea id="toca-caption" maxlength="500" placeholder="Kaj se je zgodilo?"></textarea>
      </div>
      <div>
        <label for="toca-author">Ime (neobvezno)</label>
        <input type="text" id="toca-author" maxlength="60" placeholder="Anonimno">
      </div>
      <div>
        <label for="toca-photo">Fotografija *</label>
        <input type="file" id="toca-photo" accept="image/jpeg,image/png,image/webp" required>
      </div>
      <button type="submit" class="toca-form-btn" id="toca-submit-btn">Objavi prijavo</button>
      <div class="toca-form-msg" id="toca-form-msg"></div>
    </form>
    <div class="muted-note" style="margin-top:.8rem">Fotografija in kraj bosta javno objavljena na tej strani. Pošiljaj le lastne fotografije.</div>
  </div>'''

    # ── FAQ ─────────────────────────────────────────────────────────────
    qa = [
        ("Je bila danes toča v Zgornji Savinjski dolini?",
         "Preveri opozorilni pas na vrhu te strani — prikazuje trenutno aktivna uradna ARSO opozorila "
         "pred nevihtami s točo. Za potrjene dogodke v posameznih krajih poglej skupnostni arhiv fotografij "
         "spodaj, ki ga sproti dopolnjujejo prebivalci doline."),
        ("Je bila toča v Mozirju, Ljubnem, Nazarjah ali Rečici ob Savinji?",
         "Ta stran zbira prijave iz celotne Zgornje Savinjske doline s fotografijo in navedbo kraja. "
         "Če je v tvojem kraju padla toča, jo prijavi spodaj — tako nastaja skupni pregled po naseljih."),
        ("Kakšna je škoda toče na hmelju v Savinjski dolini?",
         "Debela toča lahko v nekaj minutah uniči velik del pridelka hmelja in poškoduje mreže proti toči. "
         "Za uradno oceno škode se obrni na Kmetijsko gozdarski zavod Celje ali svoje zavarovalnico; na tej "
         "strani lahko škodo dokumentiraš s fotografijo za skupno sliko razsežnosti dogodka v dolini."),
        ("Kako postaja IREICA1 zaznava točo?",
         "Postaja nima namenskega senzorja za točo. Kot orientacijski signal uporabljamo kombinacijo "
         "intenzivnega naliva in visokih sunkov vetra v toplem delu leta (glej razpredelnico spodaj) — to "
         "NI potrditev toče, temveč pogoji, v katerih je bila verjetna. Za potrjene dogodke je najbolj "
         "zanesljiv skupnostni arhiv fotografij."),
        ("Kje najdem uro-natančno napoved tveganja za točo?",
         "Na naslovni strani meteorec.si, zavihek »Nevihte«, je živ pripomoček z verjetnostjo toče za "
         "naslednjih 12 ur na podlagi CAPE, striženja vetra in drugih konvektivnih indeksov."),
    ]
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in qa
    ) + "\n  </div>"

    related_section = f'  <h2>Sorodno na blogu</h2>\n{rel_html}' if rel_html else ""

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Toča", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Toča v Zgornji Savinjski dolini — sledilnik in arhiv</h1>
  <p class="post-meta">ARSO opozorila v živo · skupnostne prijave s fotografijo · {count_txt} · {now_txt}</p>
{warn}
{intro}
  <h2>Arhiv prijav skupnosti</h2>
{gallery_html}
{form_html}
  <h2>Dnevi z izrazito nevihtno aktivnostjo (postaja IREICA1)</h2>
  <p class="archive-intro">Orientacijski seznam toplih dni z močnim nalivom in visokimi sunki vetra — pogoji,
  v katerih je bila toča v dolini verjetna. Postaja nima senzorja za točo, zato to ni potrditev dogodka.</p>
{conv_table}
{related_section}
{faq_html}
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>
  <script>
  (function(){{
    var WORKER = {json.dumps(WORKER)};
    function esc(s){{ var d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }}
    function fmtDate(iso){{
      if(!iso || iso.length<10) return '';
      var p = iso.slice(0,10).split('-');
      var MES=['','jan.','feb.','mar.','apr.','maj','jun.','jul.','avg.','sep.','okt.','nov.','dec.'];
      return p[2]+'. '+MES[parseInt(p[1],10)]+' '+p[0];
    }}
    function renderReports(photos){{
      var grid = document.getElementById('toca-grid');
      if(!grid) return;
      if(!photos.length){{
        grid.className = 'toca-photo-empty';
        grid.textContent = 'Še ni prijav — bodi prvi, ki javi točo v svojem kraju. 👇';
        return;
      }}
      grid.className = 'toca-photo-grid';
      grid.innerHTML = photos.slice(0,60).map(function(p){{
        var img = WORKER + '/gallery/img/' + encodeURIComponent(p.key);
        var loc = esc(p.location || 'Lokacija ni navedena');
        var meta = fmtDate(p.uploadedAt || p.uploaded) + (p.caption ? ' · ' + esc(p.caption) : '');
        return '<div class="toca-photo-card"><img src="'+img+'" alt="'+loc+'" loading="lazy" width="190" height="143">'
          +'<div class="tp-overlay"><div class="tp-loc">📍 '+loc+'</div><div class="tp-meta">'+meta+'</div></div></div>';
      }}).join('');
    }}
    fetch(WORKER + '/gallery?category=toca', {{cache:'no-cache'}})
      .then(function(r){{ return r.json(); }})
      .then(function(d){{ renderReports(d.photos || []); }})
      .catch(function(){{}});

    window.tocaSubmit = function(ev){{
      ev.preventDefault();
      var fileInp = document.getElementById('toca-photo');
      var loc = document.getElementById('toca-loc').value.trim();
      var msg = document.getElementById('toca-form-msg');
      var btn = document.getElementById('toca-submit-btn');
      if(!fileInp.files[0] || !loc){{
        msg.className = 'toca-form-msg err'; msg.textContent = 'Izpolni kraj in izberi fotografijo.';
        return false;
      }}
      var fd = new FormData();
      fd.append('photo', fileInp.files[0]);
      fd.append('category', 'toca');
      fd.append('location', loc);
      fd.append('caption', document.getElementById('toca-caption').value.trim());
      fd.append('author', document.getElementById('toca-author').value.trim() || 'Anonimno');
      btn.disabled = true; btn.textContent = 'Nalagam …';
      msg.className = 'toca-form-msg'; msg.textContent = '';
      fetch(WORKER + '/gallery/upload', {{ method:'POST', body: fd }})
        .then(function(r){{ return r.json(); }})
        .then(function(d){{
          if(!d.ok) throw new Error(d.error || 'Napaka pri nalaganju');
          msg.className = 'toca-form-msg ok'; msg.textContent = 'Hvala! Prijava je objavljena.';
          document.getElementById('toca-form').reset();
          return fetch(WORKER + '/gallery?category=toca', {{cache:'no-cache'}}).then(function(r){{return r.json();}});
        }})
        .then(function(d){{ if(d) renderReports(d.photos || []); }})
        .catch(function(e){{ msg.className = 'toca-form-msg err'; msg.textContent = e.message || 'Napaka pri nalaganju.'; }})
        .finally(function(){{ btn.disabled = false; btn.textContent = 'Objavi prijavo'; }});
      return false;
    }};
  }})();
  </script>'''

    return body


def main():
    print(f"[{TODAY}] Pridobivam ARSO opozorila in skupnostne prijave …")
    alert = hail_alert()
    reports = fetch_toca_reports()
    hist = seo.load_history()

    body = build_body(alert, reports, hist)

    url = "/toca/"
    title = "Toča v Zgornji Savinjski dolini — sledilnik in arhiv"
    desc = ("Toča danes v Savinjski dolini: ARSO opozorila v živo, skupnostni arhiv prijav s fotografijo "
            "po krajih (Mozirje, Nazarje, Ljubno, Rečica ob Savinji) in dnevi z izrazito nevihtno aktivnostjo.")

    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-07-14"),
        seo.crumbs_schema([("Meteorec", "/"), ("Toča", None)]),
    ])

    html_out = seo.page_shell(title, desc, url, schema, body)
    seo.write_page("toca/index.html", html_out, force=True)
    status = f"opozorilo {alert.get('level')}" if alert else "brez opozorila"
    print(f"  → toca/index.html ({status}, {len(reports)} prijav)")


if __name__ == "__main__":
    main()
