#!/usr/bin/env python3
"""
Generator dnevnega članka za blog Meteorec.
--------------------------------------------
Vsako jutro:
  1. Povleče trenutne razmere (PROXY /ecowitt-current), zadnjih 24h (PROXY
     /observations) in kratko napoved (Open-Meteo, iste koordinate kot app.js).
  2. Zazna, ali gre za "dogodek" (vročina/mraz/dež/veter nad pragom) -> če da,
     tema je retrospektiva/analiza dogodka. Sicer izbere temo iz rotacije
     evergreen idej (glej IDEAS spodaj), ki se v zadnjih 12 dneh še ni pojavila
     (glede na tags v blog.json + tools/.daily_post_state.json).
  3. Pokliče Claude API za NARATIV (lead + odseki + viri) -- številke v
     stat-gridu se izračunajo neposredno iz podatkov v Pythonu, ne iz modela,
     da se izognemo napačnim/izmišljenim vrednostim.
  4. Sestavi HTML po istem vzorcu kot obstoječi članki (stat-grid, section-label
     + h2 odseki, glave/noge/skripti identični ostalim objavam) in ga zapiše v
     blog/<slug>.html.
  5. Z --wire pokliče wire_all() (isti helper kot mesečni povzetek in nevihtni
     opazovalec) za posodobitev blog.json, blog/index.html, sitemap.xml,
     blog/rss.xml, blog/tema/*, blog/related.json + generira OG sliko.

Uporaba:
    python3 tools/generate_daily_post.py [--wire] [--dry-run]

Potrebne env spremenljivke:
    ANTHROPIC_API_KEY   -- Claude API ključ (GitHub secret)
    POST_DATE           -- (opcijsko, za testiranje) prepiše današnji datum
"""
import json, os, sys, re, datetime, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_monthly_post import ROOT, SITE, wire_all, fmtdate, TODAY

PROXY = "https://weatherireica1.filip-eremita.workers.dev"
LAT, LON = 46.325779, 14.921137
STATE_FILE = os.path.join(ROOT, "tools", ".daily_post_state.json")
ANTHROPIC_MODEL = "claude-sonnet-5"

# Evergreen rotacija -- ideje, ki niso vezane na trenutni dogodek. "tag" mora
# ustrezati enemu izmed tagov, ki jih Claude lahko doda v blog.json, da se
# rotacija ne ponavlja prehitro.
IDEAS = [
    {"id": "gobarska-sezona", "sezona": [6, 7, 8, 9, 10], "tag": "gobe",
     "brief": "Gobarska sezona -- kaj kažejo trenutna vlažnost tal, temperature in padavine za rast gob v dolini."},
    {"id": "vodna-bilanca", "sezona": list(range(1, 13)), "tag": "vodna-bilanca",
     "brief": "Vodna bilanca zadnjih dni: koliko dežja je dejansko koristilo tlom (evapotranspiracija, odtok)."},
    {"id": "primerjava-krajev", "sezona": list(range(1, 13)), "tag": "primerjava",
     "brief": "Primerjava trenutnih razmer v Zgornji Savinjski dolini z bližnjimi kraji/ARSO postajami."},
    {"id": "nevihtni-obeti", "sezona": [4, 5, 6, 7, 8, 9], "tag": "nevihta",
     "brief": "Nevihtni obeti za danes/jutri na podlagi CAPE, striženja vetra in vlage."},
    {"id": "susa-vlaga-tal", "sezona": list(range(1, 13)), "tag": "susa",
     "brief": "Trenutno stanje suše/vlage tal glede na zadnje padavine in evapotranspiracijo."},
    {"id": "temperaturni-trend", "sezona": list(range(1, 13)), "tag": "trend",
     "brief": "Kam gre temperaturni trend zadnjih dni v primerjavi s sezonskim povprečjem."},
    {"id": "veter-in-tlak", "sezona": list(range(1, 13)), "tag": "pritisk",
     "brief": "Kaj gibanje zračnega tlaka in vetra zadnjih 24h pove o vremenu naslednjih dni."},
]

HEAT_C, COLD_C, RAIN_MM, WIND_KMH = 30, -5, 20, 50


def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def fetch_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; Meteorec-DailyPost/1.0)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def fetch_current():
    try:
        return fetch_json(PROXY + "/ecowitt-current")
    except Exception as e:
        print(f"⚠ /ecowitt-current ni uspel: {e}")
        return None


def fetch_hourly():
    """PROXY /hourly -- POZOR: to ni /observations (to je nekaj drugega --
    crowd-sourced uporabniške prijave vremena). /hourly vrača postajsko
    urno serijo, enako kot uporablja tools/generate_storm_watch_post.py."""
    try:
        data = fetch_json(PROXY + "/hourly")
        return data.get("observations", [])
    except Exception as e:
        print(f"⚠ /hourly ni uspel: {e}")
        return []


def fetch_forecast():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max"
        "&timezone=Europe%2FLjubljana&forecast_days=4"
    )
    try:
        return fetch_json(url)
    except Exception as e:
        print(f"⚠ Open-Meteo napoved ni uspela: {e}")
        return None


def load_state():
    try:
        return json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception:
        return {"recentTopics": [], "lastPublished": None}


def save_state(state):
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(STATE_FILE, "a", encoding="utf-8").write("\n")


def recent_tags(days=12):
    """Tagi objav iz zadnjih N dni (blog.json), da rotacija idej ne ponavlja."""
    try:
        posts = json.load(open(os.path.join(ROOT, "blog.json"), encoding="utf-8"))
    except Exception:
        return set()
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    tags = set()
    for p in posts:
        if p.get("date", "") >= cutoff:
            tags.update(str(t).lower() for t in p.get("tags", []))
    return tags


def detect_event(current, hourly, forecast):
    """Vrne opis dogodka, če trenutne razmere presegajo prag; sicer None.
    /ecowitt-current vrača surov Ecowitt v3 odgovor -- dejanski podatki so
    pod current['data'][...], ne neposredno pod current[...]."""
    d = (current or {}).get("data", {})
    if d:
        obs = d.get("outdoor", {})
        temp = (obs.get("temperature") or {}).get("value")
        rain = ((d.get("rainfall") or {}).get("daily") or {}).get("value")
        wind = (d.get("wind") or {}).get("wind_gust") or {}
        gust = wind.get("value")
        try:
            if temp is not None and float(temp) >= HEAT_C:
                return {"type": "vročina", "value": float(temp), "unit": "°C"}
            if temp is not None and float(temp) <= COLD_C:
                return {"type": "mraz", "value": float(temp), "unit": "°C"}
            if rain is not None and float(rain) >= RAIN_MM:
                return {"type": "padavine", "value": float(rain), "unit": "mm"}
            if gust is not None and float(gust) >= WIND_KMH:
                return {"type": "veter", "value": float(gust), "unit": "km/h"}
        except (TypeError, ValueError):
            pass
    d = (forecast or {}).get("daily")
    if d and d.get("temperature_2m_max"):
        tmax_today = d["temperature_2m_max"][0]
        if tmax_today is not None and tmax_today >= HEAT_C:
            return {"type": "vročina-napoved", "value": tmax_today, "unit": "°C"}
    return None


def pick_topic(event, state):
    if event:
        return {"id": "dogodek", "brief": f"Analiza dogodka: {event['type']} ({num(event['value'],1)} {event['unit']})",
                "tag": event["type"], "event": event}
    taken = recent_tags(12) | set(state.get("recentTopics", [])[-6:])
    candidates = [i for i in IDEAS if datetime.date.today().month in i["sezona"] and i["tag"] not in taken]
    if not candidates:
        candidates = [i for i in IDEAS if datetime.date.today().month in i["sezona"]] or IDEAS
    return candidates[0]


def build_stat_cards(current, hourly):
    """Zgradi stat-grid neposredno iz surovih podatkov (ne iz LLM), za točnost."""
    cards = []
    d = (current or {}).get("data", {})
    if d:
        obs = d.get("outdoor", {})
        temp = (obs.get("temperature") or {}).get("value")
        hum = (obs.get("humidity") or {}).get("value")
        rain = ((d.get("rainfall") or {}).get("daily") or {}).get("value")
        pressure = ((d.get("pressure") or {}).get("relative") or {}).get("value")
        if temp is not None:
            cards.append(("c-cool", "Trenutna temperatura", num(float(temp), 1), "°C · postaja IREICA1"))
        if rain is not None:
            cards.append(("c-rain", "Dežja danes", num(float(rain), 1), "mm"))
        if hum is not None:
            cards.append(("c-green", "Vlažnost", num(float(hum), 0), "%"))
        if pressure is not None:
            cards.append(("c-dry", "Zračni tlak", num(float(pressure), 0), "hPa"))
    return cards[:4]


SYSTEM_PROMPT = """Si urednik vremenskega bloga meteorec.si (osebna meteorološka postaja IREICA1,
Rečica ob Savinji, Zgornja Savinjska dolina, Slovenija, 46.326°N 14.921°E, 366 m).

STROGA PRAVILA:
- Piši SAMO na podlagi številk, ki so ti podane v uporabniškem sporočilu. Nič ne izmišljuj
  (ne rekordov, ne citatov, ne natančnih zgodovinskih vrednosti, ki jih nisi dobil). Če je
  smiselno omeniti nekaj, česar nimaš, formuliraj splošno ali izpusti.
- Naravni uredniški slovenski ton, ne pretirano formalen, tak kot ga uporabljajo obstoječi
  članki (kratke, jasne povedi, občasno "mi"/nagovor bralca, brez klišejev).
- 700-900 besed skupaj v paragraphs poljih.
- Vrni SAMO veljaven JSON (brez markdown fence, brez dodatnega besedila) v tej shemi:
{
  "title": "...",
  "meta_description": "150-160 znakov",
  "tags": ["...", "IREICA1", "Savinja"],
  "section_label": "Napoved" | "Analiza" | "Rekord" | "Sezona",
  "og_photo": eno izmed: drought, dusk-storm, flood-river, misty-valley, night-fog-valley,
              ocean-storm, rain-overcast, spring, spring-landscape, storm-clouds, weather-station,
  "og_accent_hex": "#rrggbb",
  "lead": "uvodni odstavek (2-4 povedi), lahko <strong>poudarki</strong>",
  "sections": [
    {"label": "01 — kratek naslov odseka", "heading": "H2 naslov", "id": "kebab-case-id",
     "paragraphs": ["odstavek 1", "odstavek 2"]}
  ],
  "callout": {"label": "...", "text": "..."} ali null,
  "sources_note": "en stavek, viri ki so bili DEJANSKO uporabljeni (postaja IREICA1, ARSO, Open-Meteo ...)"
}
Naj bo 3-5 odsekov v sections."""


def stream_claude(payload, api_key, timeout=180):
    """Kliče Claude API s stream=True. Rešuje problem, ko GitHub Actions
    (ali kak vmesni proxy) prekine navidez 'tiho' povezavo pri dolgih
    ne-streaming klicih -- pri streamingu prvi žetoni pridejo v nekaj
    sekundah, zato povezava nikoli ni tiha dovolj dolgo, da bi jo kdo prekinil.
    Timeout velja per-branje (idle timeout), ne za skupno trajanje klica."""
    payload = dict(payload, stream=True)
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    text_parts = []
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw_line in r:
            line = raw_line.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            chunk = line[len("data:"):].strip()
            if not chunk:
                continue
            try:
                evt = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if evt.get("type") == "content_block_delta":
                delta = evt.get("delta", {})
                if delta.get("type") == "text_delta":
                    text_parts.append(delta.get("text", ""))
            elif evt.get("type") == "error":
                raise RuntimeError(f"Claude stream napaka: {evt.get('error')}")
    return "".join(text_parts)


def call_claude(topic, current, hourly, forecast, stat_cards):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY manjka.")

    context = {
        "tema": topic["brief"],
        "trenutne_razmere": current,
        "napoved_4dni": (forecast or {}).get("daily"),
        "izracunane_stat_kartice": [{"label": l, "value": v, "sub": s} for _, l, v, s in stat_cards],
        "datum": TODAY,
    }
    user_prompt = "Podatki za današnji članek:\n" + json.dumps(context, ensure_ascii=False, indent=2)
    user_prompt += "\n\nNapiši današnji članek za meteorec.si po sistemskih navodilih."

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 4000,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    try:
        text = stream_claude(payload, api_key)
    except urllib.error.HTTPError as e:
        sys.exit(f"Claude API napaka {e.code}: {e.read().decode('utf-8','replace')[:500]}")
    except (TimeoutError, urllib.error.URLError) as e:
        sys.exit(f"Claude API klic ni uspel (timeout/omrežje): {e}")
    except RuntimeError as e:
        sys.exit(str(e))

    if not text:
        sys.exit("Claude ni vrnil besedila.")
    cleaned = re.sub(r"^```json|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(cleaned)


LEKTOR_PROMPT = """Si natančen slovenski lektor in urednik-preverjevalec za blog meteorec.si.
Dobiš osnutek članka (JSON) in surove podatke, iz katerih je bil napisan.

Preveri:
1. SLOVNICA IN PRAVOPIS -- sklanjanje, vejice, ločila, raba velike/male začetnice
   pri strokovnih izrazih (npr. "arso" -> "ARSO").
2. DEJSTVA -- ali se VSAKA številka, omenjena v lead/sections/callout, dejansko
   pojavi (ali je neposredno izpeljiva) v podanih surovih podatkih. Če je
   izmišljena, nenatančna ali je model dodal podatek, ki ga v virih ni
   (rekord, datum, primerjava, citat) -- to je napaka, ki jo je treba popraviti
   ali odstraniti.
3. SLOG -- ali se ujema z ustaljenim tonom bloga (naraven uredniški slovenski
   ton, kratke jasne povedi, brez klišejev in praznega besedičenja, brez
   pretirane formalnosti). Ponavljajoče se fraze med odseki popravi.
4. INTERNA KONSISTENTNOST -- naslov, meta_description in lead se morajo ujemati
   z vsebino odsekov.

Manjše napake (slovnica, slog, drobne nedoslednosti) POPRAVI SAM in vrni popravljen
članek. Če najdeš izmišljen/neutemeljen podatek, ki ga ne moreš preprosto
odstraniti brez izgube smisla odstavka, PREOBLIKUJ poved v splošnejšo trditev
namesto konkretne (izmišljene) številke -- ne izmišljuj nadomestne vrednosti.

Vrni SAMO veljaven JSON (brez markdown fence) v tej shemi:
{
  "ok": true ali false,
  "issues": ["kratek opis vsake najdene in popravljene/preoblikovane težave"],
  "blocking": false ali true,
  "corrected": { ... enaka shema kot vhodni članek (title, meta_description, tags,
                  section_label, og_photo, og_accent_hex, lead, sections, callout,
                  sources_note) ... }
}

"blocking": true nastavi SAMO, če je članek tako pomanjkljiv (npr. bistven del
teme ni podprt s podatki, ali bi popravek zahteval, da si izmisliš vsebino), da
ga ni mogoče objaviti niti po tvojih popravkih -- v tem primeru naj bo
"corrected" enak najboljši možni popravljeni verziji, ki jo je človek lahko
hitro dokonča ročno."""


def call_lektor(article, context):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    user_prompt = (
        "Surovi podatki, uporabljeni za članek:\n" + json.dumps(context, ensure_ascii=False, indent=2)
        + "\n\nOsnutek članka za lekturo:\n" + json.dumps(article, ensure_ascii=False, indent=2)
    )
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 4000,
        "system": LEKTOR_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    try:
        text = stream_claude(payload, api_key)
    except urllib.error.HTTPError as e:
        print(f"⚠ Lektor API napaka {e.code}, nadaljujem brez lekture: {e.read().decode('utf-8','replace')[:300]}")
        return {"ok": True, "issues": ["lektura preskočena -- API napaka"], "blocking": False, "corrected": article}
    except (TimeoutError, urllib.error.URLError) as e:
        print(f"⚠ Lektor API timeout/omrežje, nadaljujem brez lekture: {e}")
        return {"ok": True, "issues": ["lektura preskočena -- timeout"], "blocking": False, "corrected": article}
    except RuntimeError as e:
        print(f"⚠ Lektor API stream napaka, nadaljujem brez lekture: {e}")
        return {"ok": True, "issues": ["lektura preskočena -- stream napaka"], "blocking": False, "corrected": article}

    if not text:
        return {"ok": True, "issues": ["lektura preskočena -- prazen odgovor"], "blocking": False, "corrected": article}
    cleaned = re.sub(r"^```json|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        return {"ok": True, "issues": ["lektura preskočena -- neveljaven JSON"], "blocking": False, "corrected": article}


def open_review_issue(article, slug, issues):
    """Odpre GitHub Issue z osnutkom, ko lektor oceni članek kot blokirajoč.
    Uporablja GITHUB_TOKEN, ki je v Actions samodejno na voljo -- brez novega secreta."""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")  # "ibanezar/weather-station"
    if not token or not repo:
        print("⚠ GITHUB_TOKEN/GITHUB_REPOSITORY ni na voljo -- issue ni bil odprt.")
        return
    issues_md = "\n".join(f"- {i}" for i in issues) or "(lektor ni navedel razloga)"
    body = (
        f"Samodejno generiran dnevni članek **ni bil objavljen** -- lektor ga je označil "
        f"kot blokirajočega.\n\n### Najdene težave\n{issues_md}\n\n"
        f"### Osnutek (po popravkih lektorja)\n\n```json\n{json.dumps(article, ensure_ascii=False, indent=2)}\n```\n\n"
        f"Slug: `{slug}`. Če ga po ročnem pregledu/popravku želiš objaviti, ga ročno dodaj "
        f"v `blog/{slug}.html` in poženi `wire_all` (ali ponovno zaženi workflow z ročnim popravkom)."
    )
    payload = json.dumps({
        "title": f"Dnevni članek za pregled: {article.get('title', slug)}",
        "body": body,
        "labels": ["dnevni-clanek", "potrebna-lektura"],
    }).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.load(r)
            print(f"✓ Issue odprt za ročni pregled: {resp.get('html_url')}")
    except urllib.error.HTTPError as e:
        print(f"⚠ Issue ni bil odprt: {e.code} {e.read().decode('utf-8','replace')[:300]}")


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def slugify(title):
    t = title.lower()
    for a, b in (("č", "c"), ("š", "s"), ("ž", "z"), ("ć", "c"), ("đ", "d")):
        t = t.replace(a, b)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:60].rstrip("-")


EXTRA_STYLE = """
.section-label{font-family:'JetBrains Mono',monospace;font-size:.65rem;letter-spacing:.15em;
  text-transform:uppercase;color:var(--cyan);opacity:.75}
.stat-card.c-cool .sc-val{color:#22d3ee}
.stat-card.c-green .sc-val{color:#34d399}
.stat-card.c-dry .sc-val{color:#f59e0b}
.stat-card.c-rain .sc-val{color:#60a5fa}
"""


def build_forecast_chart(forecast):
    """Zgradi chart-card + Chart.js kodo iz DEJANSKIH napovednih podatkov
    (Open-Meteo daily), ne iz LLM-ja -- isti CHART_DEFAULTS vzorec in
    temna paleta kot obstoječi članki (glej npr. junijski-rekord-*.html)."""
    d = (forecast or {}).get("daily")
    if not d or not d.get("time"):
        return "", ""

    labels = d["time"]
    tmax = d.get("temperature_2m_max", [])
    tmin = d.get("temperature_2m_min", [])
    rain = d.get("precipitation_sum", [])
    if not tmax or not tmin:
        return "", ""

    day_labels_js = json.dumps([f"{x[8:10]}.{x[5:7]}." for x in labels], ensure_ascii=False)
    tmax_js = json.dumps(tmax)
    tmin_js = json.dumps(tmin)
    rain_js = json.dumps(rain)

    card = (
        '\n    <div class="chart-card">\n'
        '      <h3>IREICA1 · napoved naslednjih dni (Open-Meteo)</h3>\n'
        '      <canvas id="chartForecast"></canvas>\n'
        '      <p style="font-size:.75rem;color:var(--muted);margin-top:.7rem">'
        'Najvišje/najnižje dnevne temperature in pričakovane padavine za Rečico ob Savinji.</p>\n'
        '    </div>\n'
    )

    js = f'''
  const CHART_DEFAULTS = {{
    responsive: true,
    maintainAspectRatio: true,
    interaction: {{ mode: 'index', intersect: false }},
    animation: {{ duration: 700, easing: 'easeOutQuart' }},
    plugins: {{
      legend: {{ display: true, position: 'top',
        labels: {{ color: '#adc0d8', font: {{ size: 11, family: 'JetBrains Mono' }}, boxWidth: 10, padding: 14 }} }},
      tooltip: {{ backgroundColor: 'rgba(4,7,14,.96)', borderColor: 'rgba(255,255,255,.1)', borderWidth: 1,
        titleColor: '#adc0d8', bodyColor: '#e8edf8', padding: 10 }}
    }}
  }};
  new Chart(document.getElementById('chartForecast'), {{
    data: {{
      labels: {day_labels_js},
      datasets: [
        {{ type: 'bar', label: 'Padavine (mm)', data: {rain_js}, backgroundColor: 'rgba(96,165,250,.55)',
           borderRadius: 5, yAxisID: 'y1', order: 3 }},
        {{ type: 'line', label: 'Tmax (°C)', data: {tmax_js}, borderColor: '#f97316',
           backgroundColor: 'rgba(249,115,22,.12)', borderWidth: 2, pointRadius: 3,
           pointBackgroundColor: '#f97316', fill: true, tension: .35, order: 1 }},
        {{ type: 'line', label: 'Tmin (°C)', data: {tmin_js}, borderColor: '#22d3ee',
           backgroundColor: 'rgba(34,211,238,.08)', borderWidth: 2, pointRadius: 3,
           pointBackgroundColor: '#22d3ee', fill: true, tension: .35, order: 2 }}
      ]
    }},
    options: {{
      ...CHART_DEFAULTS,
      scales: {{
        x: {{ grid: {{ color: 'rgba(255,255,255,.04)' }}, ticks: {{ color: '#adc0d8', font: {{ size: 10 }} }} }},
        y: {{ position: 'left', grid: {{ color: 'rgba(255,255,255,.05)' }},
             ticks: {{ color: '#f97316', font: {{ size: 10 }}, callback: v => v + ' °C' }} }},
        y1: {{ position: 'right', min: 0, grid: {{ display: false }},
              ticks: {{ color: '#60a5fa', font: {{ size: 10 }}, callback: v => v + ' mm' }} }}
      }}
    }}
  }});
'''
    return card, js


def build_html(article, stat_cards, slug, now_utc, forecast=None):
    date_str = fmtdate(TODAY)
    url = f"{SITE}/blog/{slug}.html"
    title = article["title"]
    desc = article["meta_description"]

    cards_html = "\n".join(
        f'      <div class="stat-card {cls}">\n'
        f'        <div class="sc-label">{label}</div>\n'
        f'        <div class="sc-val">{val}</div>\n'
        f'        <div class="sc-sub">{sub}</div>\n'
        f'      </div>' for cls, label, val, sub in stat_cards
    )

    chart_card_html, chart_js = build_forecast_chart(forecast)
    chart_scripts_html = ""
    if chart_js:
        chart_scripts_html = (
            '<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>\n'
            f'<script>\n{chart_js}\n</script>'
        )

    sec_parts = []
    for s in article["sections"]:
        paras = "\n".join(f"    <p>{p}</p>" for p in s["paragraphs"])
        sec_parts.append(
            f'    <span class="section-label">{s["label"]}</span>\n'
            f'    <h2 id="{s["id"]}">{s["heading"]}</h2>\n{paras}'
        )
    sections_html = "\n\n".join(sec_parts)

    callout_html = ""
    if article.get("callout"):
        c = article["callout"]
        callout_html = (
            f'\n    <div class="callout">\n      <p><strong>{c["label"]}:</strong> {c["text"]}</p>\n    </div>\n'
        )

    tags = article.get("tags", [])
    keywords = ", ".join(tags)
    section_label = article.get("section_label", "Analiza")

    html = f'''<!DOCTYPE html>
<html lang="sl">
<head>
<meta charset="UTF-8">
<script async src="https://www.googletagmanager.com/gtag/js?id=G-LE8PJ1HR8B"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-LE8PJ1HR8B');
</script>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} | Meteorec</title>
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="sl" href="{url}">
<link rel="alternate" hreflang="x-default" href="{url}">
<meta name="description" content="{desc}">
<meta name="keywords" content="{keywords}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="author" content="Filip Eremita">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:site_name" content="Meteorec">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{SITE}/og/{slug}.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="sl_SI">
<meta property="article:published_time" content="{TODAY}">
<meta property="article:author" content="Filip Eremita">
<meta property="article:section" content="{section_label}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{SITE}/og/{slug}.jpg">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "{title}",
  "description": "{desc}",
  "image": {{ "@type": "ImageObject", "url": "{SITE}/og/{slug}.jpg", "width": 1200, "height": 630 }},
  "datePublished": "{TODAY}",
  "dateModified": "{TODAY}",
  "inLanguage": "sl",
  "author": {{ "@type": "Person", "name": "Filip Eremita" }},
  "publisher": {{ "@type": "Organization", "name": "Meteorec", "logo": {{ "@type": "ImageObject", "url": "{SITE}/icon-512.png" }} }},
  "mainEntityOfPage": {{ "@type": "WebPage", "@id": "{url}" }},
  "about": {{ "@type": "Place", "name": "Zgornja Savinjska dolina", "sameAs": ["https://sl.wikipedia.org/wiki/Zgornja_Savinjska_dolina"], "geo": {{ "@type": "GeoCoordinates", "latitude": {LAT}, "longitude": {LON} }} }},
  "keywords": "{keywords}"
}}
</script>
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{ "@type": "ListItem", "position": 1, "name": "Meteorec", "item": "{SITE}/" }},
    {{ "@type": "ListItem", "position": 2, "name": "Blog", "item": "{SITE}/blog/" }},
    {{ "@type": "ListItem", "position": 3, "name": "{title}" }}
  ]
}}
</script>
<link rel="stylesheet" href="/fonts/fonts.css">
<link rel="alternate" type="application/rss+xml" title="Meteorec — blog" href="/blog/rss.xml">
<link rel="stylesheet" href="blog.css">
<style>{EXTRA_STYLE}</style>
</head>
<body>
<div id="bg" aria-hidden="true"><div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div><div class="blob b4"></div><div class="blob b5"></div></div>
<div class="wrap">

  <header class="site-head">
    <a class="brand" href="/">
      <img class="brand-logo" src="/logo.svg" alt="" width="42" height="42">
      <span class="brand-name">Meteo<em>rec</em></span>
    </a>
    <nav class="site-nav"><a href="/">Vreme v živo</a><a href="/blog/">Blog</a><a href="/o-postaji.html">O postaji</a></nav>
  </header>

  <nav class="crumbs" aria-label="Drobtine">
    <a href="/">Meteorec</a> › <a href="/blog/">Blog</a> › {title}
  </nav>

  <article>
    <div class="stn-badge"><span></span> IREICA1 · Rečica ob Savinji · {section_label}</div>
    <h1>{title}</h1>
    <p class="post-meta">{date_str} · Filip Eremita</p>

    <p class="lead">{article["lead"]}</p>

    <div class="stat-grid">
{cards_html}
    </div>
{chart_card_html}
{sections_html}
{callout_html}
    <p style="color:var(--muted);font-size:.9rem;margin-top:2rem">{article["sources_note"]}</p>

    <div class="share-bar" id="share-bar">
      <span class="share-label">Deli</span>
      <a class="share-btn wa" id="btn-wa" href="#" target="_blank" rel="noopener" aria-label="Deli na WhatsApp">WhatsApp</a>
      <a class="share-btn x" id="btn-x" href="#" target="_blank" rel="noopener" aria-label="Deli na X">X</a>
      <a class="share-btn fb" id="btn-fb" href="#" target="_blank" rel="noopener" aria-label="Deli na Facebooku">Facebook</a>
      <button class="share-btn copy" id="btn-copy" aria-label="Kopiraj povezavo"><span id="copy-label">Kopiraj</span></button>
      <button class="share-btn native" id="btn-native" aria-label="Deli" style="display:none">Deli</button>
    </div>

    <a class="back-link" href="/blog/">← Nazaj na blog</a>
  </article>

  <footer class="site-foot">
    <span>© {now_utc.year} Meteorec · Rečica ob Savinji</span>
    <span><a href="/">Vreme v živo</a> · <a href="/blog/">Blog</a></span>
  </footer>

</div>

<script data-goatcounter="https://ibanezar.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
<script>
(function () {{
  const PAGE_URL   = "{url}";
  const PAGE_TITLE = "{title} | Meteorec";
  const PAGE_TEXT  = "{desc}";
  const enc = encodeURIComponent;
  document.getElementById('btn-wa').href = 'https://wa.me/?text=' + enc(PAGE_TEXT + ' ' + PAGE_URL);
  document.getElementById('btn-x').href = 'https://x.com/intent/tweet?text=' + enc(PAGE_TEXT) + '&url=' + enc(PAGE_URL);
  document.getElementById('btn-fb').href = 'https://www.facebook.com/sharer/sharer.php?u=' + enc(PAGE_URL);
  document.getElementById('btn-copy').addEventListener('click', function () {{
    var label = document.getElementById('copy-label');
    if (navigator.clipboard) {{
      navigator.clipboard.writeText(PAGE_URL).then(function () {{ label.textContent = 'Kopirano!'; setTimeout(function () {{ label.textContent = 'Kopiraj'; }}, 2000); }});
    }}
  }});
  if (navigator.share) {{
    var nb = document.getElementById('btn-native'); nb.style.display = 'inline-flex';
    nb.addEventListener('click', function () {{ navigator.share({{ title: PAGE_TITLE, text: PAGE_TEXT, url: PAGE_URL }}).catch(function () {{}}); }});
  }}
}})();
</script>
<script src="likes.js" defer></script>
<script src="/blog/comments.js" defer></script>
<script src="/blog/article-enhance.js" defer></script>
<script src="/blog/subscribe.js" defer></script>
{chart_scripts_html}
</body>
</html>
'''
    entry = {
        "title": title, "slug": slug, "url": f"/blog/{slug}.html",
        "date": TODAY, "summary": desc, "tags": tags,
    }
    og_meta = {
        "title": title.split(":")[0][:40],
        "subtitle": f"Rečica ob Savinji · {date_str}",
        "section": section_label,
        "accent": hexrgb(article.get("og_accent_hex", "#38bdf8")),
        "photo": article.get("og_photo", "weather-station"),
    }
    return html, entry, og_meta


def main():
    wire = "--wire" in sys.argv
    dry_run = "--dry-run" in sys.argv

    print("1/6 Pridobivam podatke...")
    current = fetch_current()
    hourly = fetch_hourly()
    forecast = fetch_forecast()

    print("2/6 Izbiram temo...")
    state = load_state()
    event = detect_event(current, hourly, forecast)
    topic = pick_topic(event, state)
    print(f"   tema: {topic['id']} ({topic['brief'][:70]}...)")

    stat_cards = build_stat_cards(current, hourly)

    print("3/6 Kličem Claude API (osnutek)...")
    if dry_run:
        print("   (--dry-run: preskačem klic Claude API)")
        return
    article = call_claude(topic, current, hourly, forecast, stat_cards)

    print("4/6 Lektura...")
    lektor_context = {
        "trenutne_razmere": current,
        "napoved_4dni": (forecast or {}).get("daily"),
        "izracunane_stat_kartice": [{"label": l, "value": v, "sub": s} for _, l, v, s in stat_cards],
    }
    review = call_lektor(article, lektor_context)
    if review.get("issues"):
        print("   popravki/opombe lektorja:")
        for i in review["issues"]:
            print(f"   - {i}")
    article = review.get("corrected") or article

    slug = slugify(article["title"]) + f"-{TODAY[-5:].replace('-','')}"
    now = datetime.datetime.now(datetime.timezone.utc)

    if review.get("blocking"):
        print("⚠ Lektor je članek označil kot BLOKIRAJOČ -- ne objavljam samodejno.")
        if wire:
            open_review_issue(article, slug, review.get("issues", []))
        else:
            print(json.dumps(article, ensure_ascii=False, indent=2))
        return

    print("5/6 Sestavljam HTML...")
    html, entry, og_meta = build_html(article, stat_cards, slug, now, forecast)

    out = os.path.join(ROOT, "blog", f"{slug}.html")
    open(out, "w", encoding="utf-8").write(html)
    print(f"✓ zapisano: blog/{slug}.html")

    state.setdefault("recentTopics", []).append(topic.get("tag", topic["id"]))
    state["recentTopics"] = state["recentTopics"][-20:]
    state["lastPublished"] = now.isoformat()
    save_state(state)

    if not wire:
        print("\n— Za blog.json dodaj:\n" + json.dumps(entry, ensure_ascii=False, indent=2))
        print("\n(poženi z --wire za samodejno vpisovanje in OG sliko)")
        return

    print("6/6 Posodabljam blog.json, sitemap, RSS, OG sliko...")
    wire_all(entry, entry["url"])
    try:
        from generate_og_images import make_og
        make_og({"slug": slug, **og_meta})
        print(f"✓ OG slika: og/{slug}.jpg")
    except Exception as e:
        print(f"⚠ OG slika (Pillow) preskočena: {e}")
    print("✓ blog.json, blog/index.html, sitemap.xml, blog/rss.xml osveženi.")


if __name__ == "__main__":
    main()
