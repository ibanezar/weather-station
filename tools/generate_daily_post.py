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
    python3 tools/generate_daily_post.py [--wire] [--dry-run] [--preview] [--choice ID]

    --preview   pokliče Claude (osnutek + lektura), izpiše obe verziji
                (pred/po lekturi) na stdout in ne zapiše/objavi ničesar --
                za preverjanje kakovosti jezika brez posega v blog.

Potrebne env spremenljivke:
    ANTHROPIC_API_KEY   -- Claude API ključ (GitHub secret)
    POST_DATE           -- (opcijsko, za testiranje) prepiše današnji datum
"""
import json, os, sys, re, shutil, time, datetime, urllib.request, urllib.error, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_monthly_post import ROOT, SITE, wire_all, fmtdate, TODAY

PROXY = "https://weatherireica1.filip-eremita.workers.dev"
LAT, LON = 46.325779, 14.921137
STATE_FILE = os.path.join(ROOT, "tools", ".daily_post_state.json")
ANTHROPIC_MODEL = "claude-sonnet-5"
# Sem (kadarkoli, pred jutranjim zagonom) vržeš svoje fotografije za naslednji
# članek -- ker se slug generira šele iz naslova, ki ga napiše Claude, ne moreš
# vnaprej vedeti pravo mapo. Skripta jih ob zagonu premakne v img/blog/<slug>/.
PENDING_PHOTOS_DIR = os.path.join(ROOT, "img", "blog-pending")
PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".webp")

# Evergreen rotacija -- ideje, ki niso vezane na trenutni dogodek. "tag" mora
# ustrezati enemu izmed tagov, ki jih Claude lahko doda v blog.json, da se
# rotacija ne ponavlja prehitro.
IDEAS = [
    {"id": "gobarska-sezona", "sezona": [6, 7, 8, 9, 10], "tag": "gobe",
     "brief": "Gobarska sezona -- kaj kažejo trenutna vlažnost tal, temperature in padavine za rast gob v dolini.",
     "seo_keywords": ["gobarska napoved Zgornja Savinjska dolina", "kdaj rastejo gobe", "gobarjenje Rečica ob Savinji"]},
    {"id": "vodna-bilanca", "sezona": list(range(1, 13)), "tag": "vodna-bilanca",
     "brief": "Vodna bilanca zadnjih dni: koliko dežja je dejansko koristilo tlom (evapotranspiracija, odtok).",
     "seo_keywords": ["vodna bilanca tal", "evapotranspiracija Savinjska dolina", "koliko dežja koristi rastlinam"]},
    {"id": "primerjava-krajev", "sezona": list(range(1, 13)), "tag": "primerjava",
     "brief": "Primerjava trenutnih razmer v Zgornji Savinjski dolini z bližnjimi kraji/ARSO postajami.",
     "seo_keywords": ["vreme Zgornja Savinjska dolina", "primerjava vremena Rečica ob Savinji", "mikroklima Savinjska dolina"]},
    {"id": "nevihtni-obeti", "sezona": [4, 5, 6, 7, 8, 9], "tag": "nevihta",
     "brief": "Nevihtni obeti za danes/jutri na podlagi CAPE, striženja vetra in vlage.",
     "seo_keywords": ["nevihtna napoved Savinjska dolina", "bo danes grmelo Rečica ob Savinji", "CAPE nestabilnost vreme"]},
    {"id": "susa-vlaga-tal", "sezona": list(range(1, 13)), "tag": "susa",
     "brief": "Trenutno stanje suše/vlage tal glede na zadnje padavine in evapotranspiracijo.",
     "seo_keywords": ["suša Zgornja Savinjska dolina", "vlaga tal Rečica ob Savinji", "koliko časa brez dežja"]},
    {"id": "temperaturni-trend", "sezona": list(range(1, 13)), "tag": "trend",
     "brief": "Kam gre temperaturni trend zadnjih dni v primerjavi s sezonskim povprečjem.",
     "seo_keywords": ["temperaturni trend Savinjska dolina", "vreme Rečica ob Savinji", "postaja IREICA1"]},
    {"id": "veter-in-tlak", "sezona": list(range(1, 13)), "tag": "pritisk",
     "brief": "Kaj gibanje zračnega tlaka in vetra zadnjih 24h pove o vremenu naslednjih dni.",
     "seo_keywords": ["zračni tlak napoved vreme", "veter Zgornja Savinjska dolina", "sprememba vremena znaki"]},
]

# Statične hub/spoke strani (glej meteorec.si) -- kandidati za interno linkanje
# glede na temo. Vsak vnos: (ujemajoči tag/i teme, url, anchor besedilo).
SPOKE_PAGES = [
    (("gobe",), "/gobarska-napoved/", "gobarsko napoved"),
    (("susa", "vodna-bilanca"), "/agrometeo/", "agrometeo stran"),
    (("nevihta",), "/nevihte/", "nevihtno napoved"),
    (("padavine", "poplave"), "/vodostaj-savinje/", "vodostaj Savinje"),
    (("zrak", "ozon"), "/kakovost-zraka/", "kakovost zraka"),
    (("padalci", "veter"), "/vreme-za-padalce/", "vreme za padalce"),
    (("trend",), "/trendi/", "dolgoročne trende"),
    (("rekord",), "/rekord/", "vremenske rekorde postaje"),
]

HEAT_C, COLD_C, RAIN_MM, WIND_KMH = 30, -5, 20, 50


def find_related_links(topic, max_posts=4):
    """Kandidati za interno linkanje: pretekli članki z ujemajočimi tagi
    (blog.json) + statične hub/spoke strani. Claude dobi SAMO te URL-je in
    jih ne sme izmišljavati -- prepreči pokvarjene/neobstoječe povezave."""
    tag = topic.get("tag", "")
    links = []

    try:
        posts = json.load(open(os.path.join(ROOT, "blog.json"), encoding="utf-8"))
    except Exception:
        posts = []
    scored = []
    for p in posts:
        p_tags = {str(t).lower() for t in p.get("tags", [])}
        score = sum(1 for t in p_tags if tag.lower() in t or t in tag.lower())
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda x: (-x[0], x[1].get("date", "")), reverse=False)
    for score, p in scored[:max_posts]:
        links.append({"title": p["title"], "url": p["url"]})

    for tags_match, url, anchor in SPOKE_PAGES:
        if any(t in tag.lower() or tag.lower() in t for t in tags_match):
            links.append({"title": anchor, "url": url})

    return links[:6]


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
    recent = state.get("recentTopics", [])
    taken = recent_tags(12) | set(recent[-6:])
    seasonal = [i for i in IDEAS if datetime.date.today().month in i["sezona"]] or IDEAS
    candidates = [i for i in seasonal if i["tag"] not in taken]
    if not candidates:
        # Vse sezonske teme so bile nedavno uporabljene -- vzemi najdlje
        # neuporabljeno, ne vedno prve s seznama (ta fallback je povzročal,
        # da se je poleti gobarska tema ponavljala dan za dnem).
        def last_used(idea):
            try:
                return len(recent) - 1 - recent[::-1].index(idea["tag"])
            except ValueError:
                return -1
        candidates = sorted(seasonal, key=last_used)
    return candidates[0]


def load_chosen_proposal(choice):
    """Prebere tools/.daily_proposals.json (commitan ob jutranjem zagonu) in
    vrne predlog z danim id -- za objavo članka, ki ga je Filip izbral po e-pošti."""
    path = os.path.join(ROOT, "tools", ".daily_proposals.json")
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        sys.exit(f"--choice {choice}: tools/.daily_proposals.json ni berljiv: {e}")
    if data.get("date") != TODAY:
        print(f"⚠ Predlogi so z dne {data.get('date')}, danes je {TODAY} -- nadaljujem vseeno.")
    for p in data.get("proposals", []):
        if p.get("id") == choice:
            return p
    ids = ", ".join(p.get("id", "?") for p in data.get("proposals", []))
    sys.exit(f"Predlog z id '{choice}' ne obstaja (na voljo: {ids}).")


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

SEO / KLJUČNE BESEDE:
- Dobiš seznam "seo_keywords" (ciljne fraze za to temo). Vpleti glavno frazo naravno v naslov,
  v prvi odstavek (lead) in v vsaj en H2 naslov -- brez keyword-stuffinga, mora zveneti naravno.
  Če fraza ne zveni naravno na danem mestu, jo preoblikuj ali izpusti raje kot da jo na silo vtakneš.
- Uporabi tudi 1-2 sorodni dolgi rep (long-tail) fraze skozi telo besedila, kjer se organsko prilegajo.

INTERNO LINKANJE:
- Dobiš seznam "interni_linki" (naslov + URL obstoječih strani na meteorec.si). Vpleti 2-4 od njih
  kot naravne inline povezave znotraj odstavkov (NE kot seznam na koncu), v obliki:
  <a href="URL" style="color:var(--blue)">smiselno sidrno besedilo</a>
- Uporabi SAMO URL-je iz podanega seznama "interni_linki" -- nikoli si ne izmišljuj lastnih URL-jev
  ali povezav na strani, ki jih nisi dobil. Če seznam nima primernih povezav za neko poved, je
  brez povezave popolnoma v redu -- ne silimo povezav tja, kjer ne sodijo vsebinsko.

Vrni SAMO veljaven JSON (brez markdown fence, brez dodatnega besedila) v tej shemi:
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
     "paragraphs": ["odstavek 1 (lahko vsebuje <a href='...'>...</a> iz interni_linki)", "odstavek 2"]}
  ],
  "callout": {"label": "...", "text": "..."} ali null,
  "sources_note": "en stavek, viri ki so bili DEJANSKO uporabljeni (postaja IREICA1, ARSO, Open-Meteo ...)"
}
Naj bo 3-5 odsekov v sections."""


class _TransientAPIError(RuntimeError):
    """Znano prehodno stanje Anthropic API-ja (preobremenjenost, rate limit) --
    vredno ponovnega poskusa, za razliko od pravih napak (npr. max_tokens)."""


_RETRYABLE_STREAM_ERRORS = {"overloaded_error", "rate_limit_error", "api_error"}
_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 529}
_RETRY_DELAYS = [5, 15, 35, 75]  # sekund; skupno do ~2 min čakanja


def stream_claude(payload, api_key, timeout=180):
    """Kliče Claude API s stream=True. Rešuje problem, ko GitHub Actions
    (ali kak vmesni proxy) prekine navidez 'tiho' povezavo pri dolgih
    ne-streaming klicih -- pri streamingu prvi žetoni pridejo v nekaj
    sekundah, zato povezava nikoli ni tiha dovolj dolgo, da bi jo kdo prekinil.
    Timeout velja per-branje (idle timeout), ne za skupno trajanje klica.

    Ob znanih prehodnih napakah (overloaded_error, rate_limit_error, HTTP
    429/5xx/529) klic samodejno ponovi z naraščajočim zamikom -- to ni redka
    posebnost, Anthropic API se občasno preobremeni tudi sredi streama."""
    payload = dict(payload, stream=True)
    body = json.dumps(payload).encode()

    def attempt():
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
        stop_reason = None
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
                elif evt.get("type") == "message_delta":
                    stop_reason = (evt.get("delta") or {}).get("stop_reason") or stop_reason
                elif evt.get("type") == "error":
                    err = evt.get("error") or {}
                    msg = f"Claude stream napaka: {err}"
                    if err.get("type") in _RETRYABLE_STREAM_ERRORS:
                        raise _TransientAPIError(msg)
                    raise RuntimeError(msg)
        if stop_reason == "max_tokens":
            partial = "".join(text_parts)
            raise RuntimeError(
                "Claude je dosegel max_tokens limit in odgovor je bil prekinjen sredi JSON-a "
                "-- dvigni 'max_tokens' v generate_daily_post.py ali skrajšaj zahtevano dolžino članka. "
                f"[diagnostika: {len(partial)} znakov prejetih, zadnjih 400: ...{partial[-400:]!r}]"
            )
        return "".join(text_parts)

    last_err = None
    for i, delay in enumerate([*_RETRY_DELAYS, None]):
        try:
            return attempt()
        except _TransientAPIError as e:
            last_err = e
        except urllib.error.HTTPError as e:
            if e.code not in _RETRYABLE_HTTP_CODES:
                raise
            last_err = e
        if delay is None:
            break
        print(f"⚠ Claude API prehodno ni na voljo ({last_err}) -- ponovni poskus čez {delay}s "
              f"({i + 1}/{len(_RETRY_DELAYS)})...")
        time.sleep(delay)
    raise RuntimeError(f"Claude API po {len(_RETRY_DELAYS) + 1} poskusih še vedno ni na voljo: {last_err}")


def call_claude(topic, current, hourly, forecast, stat_cards, desired_title=None):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY manjka.")

    context = {
        "tema": topic["brief"],
        "seo_keywords": topic.get("seo_keywords", []),
        "interni_linki": find_related_links(topic),
        "trenutne_razmere": current,
        "napoved_4dni": (forecast or {}).get("daily"),
        "izracunane_stat_kartice": [{"label": l, "value": v, "sub": s} for _, l, v, s in stat_cards],
        "datum": TODAY,
    }
    if desired_title:
        context["izbrani_naslov"] = desired_title
    user_prompt = "Podatki za današnji članek:\n" + json.dumps(context, ensure_ascii=False, indent=2)
    if desired_title:
        user_prompt += (
            f'\n\nFilip je iz jutranjih predlogov izbral naslov: "{desired_title}". '
            "Uporabi TOČNO ta naslov (dovoljeni so le minimalni pravopisni popravki) "
            "in napiši članek, ki naslovu vsebinsko ustreza."
        )
    user_prompt += "\n\nNapiši današnji članek za meteorec.si po sistemskih navodilih."

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 8000,
        # claude-sonnet-5 privzeto razmišlja (adaptive thinking) -- ti žetoni gredo v
        # breme max_tokens, tudi če jih stream_claude ne lovi (samo text_delta). Za to
        # nalogo (pisanje po strogi shemi, brez več-koračnega sklepanja) razmišljanje
        # ne pomaga in samo tvega, da zmanjka prostora za dejanski izpis.
        "thinking": {"type": "disabled"},
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
5. ANGLICIZMI IN KALKI -- besedilo piše jezikovni model, zato rado "diši" po
   prevodu iz angleščine, tudi če je slovnično pravilno. Poišči in popravi:
   - dobesedne prevode angleških fraz, ki v slovenščini ne zvenijo naravno
     (npr. "narediti smisel" namesto "biti smiseln", "na koncu dneva" namesto
     "navsezadnje/skratka", "igra vlogo" namesto "je pomemben/vpliva");
   - prekomerno rabo trpnika ("je bilo izmerjeno", "je bilo opaženo") tam, kjer
     bi naravna slovenščina uporabila tvornik ali povratno obliko s "se"
     ("izmerili smo", "opazili smo", "temperatura se je dvignila");
   - angleške dvojne narekovaje " " namesto slovenskih „ " (spodaj-zgoraj) in
     vezaj "-" namesto pomišljaja "–", kjer gre za pomišljaj, ne vezaj;
   - angleški besedni red (npr. prislov pred glagolom po angleškem vzorcu, ko
     bi naraven slovenski vrstni red dal drugačen poudarek).
   Ne popravljaj stavkov, ki so že naravni, le zato ker si "aktiven" -- cilj je
   odpraviti prevodni prizvok, ne preoblikovati vsak stavek.

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
        # Lektor vrne CEL popravljen članek (isto velik kot osnutek) + seznam
        # najdenih težav, zato nekoliko višji limit kot pri osnutku.
        "max_tokens": 10000,
        # Pravi vzrok, da je klic prej padal na max_tokens že pri ~2000 znakih
        # vidnega besedila, NI bil premajhen limit -- claude-sonnet-5 privzeto
        # razmišlja (adaptive thinking), ti žetoni gredo v breme max_tokens in
        # jih stream_claude ne lovi (samo text_delta, ne thinking_delta). Za
        # nalogo preverjanja po fiksnem kontrolnem seznamu razmišljanje ne
        # pomaga, zato ga izklopimo -- to je pravi popravek, ne višji limit.
        "thinking": {"type": "disabled"},
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


def collect_local_photos(slug):
    """Če so v img/blog-pending/ kake fotografije (Filip jih je ročno naložil
    pred zagonom), jih premakne v img/blog/<slug>/ in vrne seznam za galerijo.
    Prazen nabiralnik -> prazen seznam (brez napake)."""
    if not os.path.isdir(PENDING_PHOTOS_DIR):
        return []
    files = sorted(f for f in os.listdir(PENDING_PHOTOS_DIR) if f.lower().endswith(PHOTO_EXTS))
    if not files:
        return []
    dest_dir = os.path.join(ROOT, "img", "blog", slug)
    os.makedirs(dest_dir, exist_ok=True)
    photos = []
    for i, fname in enumerate(files, 1):
        ext = os.path.splitext(fname)[1].lower()
        new_name = f"foto-{i}{ext}"
        shutil.move(os.path.join(PENDING_PHOTOS_DIR, fname), os.path.join(dest_dir, new_name))
        photos.append({
            "filename": new_name,
            "caption": f"Rečica ob Savinji, {fmtdate(TODAY)}. Foto: Filip Eremita.",
        })
    print(f"✓ {len(photos)} fotografij iz nabiralnika premaknjenih v img/blog/{slug}/")
    return photos


def fetch_stock_photo(query, slug):
    """Poišče prosto licenčno fotografijo prek Openverse (CC0/CC-BY/CC-BY-SA,
    filtrirano na dovoljeno komercialno rabo, brez potrebnega API ključa) in
    jo prenese lokalno z ustrezno navedbo avtorja. Vrne [] če nič ne najde --
    članek se v tem primeru objavi brez fotografij, brez napake."""
    try:
        q = urllib.parse.quote(query)
        url = f"https://api.openverse.org/v1/images/?q={q}&license_type=commercial,modification&page_size=5&mature=false"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; Meteorec-DailyPost/1.0)"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    except Exception as e:
        print(f"⚠ Openverse iskanje ni uspelo, nadaljujem brez fotografij: {e}")
        return []

    for result in data.get("results", []):
        img_url = result.get("url")
        if not img_url:
            continue
        try:
            req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0 (compatible; Meteorec-DailyPost/1.0)"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                content = resp.read()
            dest_dir = os.path.join(ROOT, "img", "blog", slug)
            os.makedirs(dest_dir, exist_ok=True)
            filename = "stock-1.jpg"
            with open(os.path.join(dest_dir, filename), "wb") as f:
                f.write(content)
            creator = result.get("creator") or "neznan avtor"
            license_name = (result.get("license") or "").upper()
            caption = f"Ilustrativna fotografija. Foto: {creator} (Openverse, licenca {license_name})."
            print(f"✓ Prosto licenčna fotografija najdena in prenesena (licenca {license_name}, avtor {creator})")
            return [{"filename": filename, "caption": caption}]
        except Exception as e:
            print(f"⚠ Prenos fotografije ni uspel, poskušam naslednjo: {e}")
            continue
    print("   Openverse ni vrnil uporabne fotografije -- članek brez fotografij.")
    return []


def build_photos_html(photos, slug):
    if not photos:
        return ""
    parts = []
    for p in photos:
        cap = p["caption"]
        parts.append(
            f'    <figure class="post-photo">\n'
            f'      <img src="/img/blog/{slug}/{p["filename"]}" alt="{cap[:120]}" loading="lazy">\n'
            f'      <figcaption>{cap}</figcaption>\n'
            f'    </figure>'
        )
    return "\n" + "\n".join(parts) + "\n"


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


def build_html(article, stat_cards, slug, now_utc, forecast=None, photos=None):
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
    photos_html = build_photos_html(photos, slug)
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
{photos_html}
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
    preview = "--preview" in sys.argv
    choice = None
    if "--choice" in sys.argv:
        i = sys.argv.index("--choice")
        if i + 1 >= len(sys.argv):
            sys.exit("--choice zahteva ID predloga.")
        choice = sys.argv[i + 1]

    print("1/6 Pridobivam podatke...")
    current = fetch_current()
    hourly = fetch_hourly()
    forecast = fetch_forecast()

    print("2/6 Izbiram temo...")
    state = load_state()
    desired_title = None
    if choice:
        if not preview and (state.get("lastPublished") or "").startswith(TODAY):
            sys.exit("Današnji dnevni članek je že objavljen -- ne objavljam drugič.")
        prop = load_chosen_proposal(choice)
        topic = prop["topic"]
        desired_title = prop.get("title")
        print(f"   izbran predlog: {choice} ({desired_title})")
    else:
        event = detect_event(current, hourly, forecast)
        topic = pick_topic(event, state)
        print(f"   tema: {topic['id']} ({topic['brief'][:70]}...)")

    stat_cards = build_stat_cards(current, hourly)

    print("3/6 Kličem Claude API (osnutek)...")
    if dry_run:
        print("   (--dry-run: preskačem klic Claude API)")
        return
    draft = call_claude(topic, current, hourly, forecast, stat_cards, desired_title)

    print("4/6 Lektura...")
    lektor_context = {
        "trenutne_razmere": current,
        "napoved_4dni": (forecast or {}).get("daily"),
        "izracunane_stat_kartice": [{"label": l, "value": v, "sub": s} for _, l, v, s in stat_cards],
    }
    review = call_lektor(draft, lektor_context)
    if review.get("issues"):
        print("   popravki/opombe lektorja:")
        for i in review["issues"]:
            print(f"   - {i}")
    article = review.get("corrected") or draft

    if preview:
        def render(a):
            out = [f"NASLOV: {a['title']}", f"META: {a.get('meta_description','')}",
                   f"TAGI: {', '.join(a.get('tags', []))}", "", "LEAD:", a.get("lead", "")]
            for s in a.get("sections", []):
                out.append(f"\n## {s.get('heading','')}")
                out.extend(s.get("paragraphs", []))
            if a.get("callout"):
                out.append(f"\nCALLOUT ({a['callout'].get('label','')}): {a['callout'].get('text','')}")
            out.append(f"\nVIRI: {a.get('sources_note','')}")
            return "\n".join(out)

        print("\n" + "=" * 70)
        print("PREVIEW -- OSNUTEK (pred lekturo)")
        print("=" * 70)
        print(render(draft))
        print("\n" + "=" * 70)
        print("PREVIEW -- PO LEKTURI (to bi bilo objavljeno)")
        print("=" * 70)
        print(render(article))
        print(f"\nlektor blocking: {review.get('blocking', False)}")
        print("\n(--preview: nič ni zapisano na disk, nič ni objavljeno)")
        return

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
    photos = collect_local_photos(slug)
    if not photos:
        photos = fetch_stock_photo(article.get("og_photo", "weather station"), slug)
    html, entry, og_meta = build_html(article, stat_cards, slug, now, forecast, photos)

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
