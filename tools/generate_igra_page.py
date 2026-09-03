#!/usr/bin/env python3
"""
tools/generate_igra_page.py — »Termika«, igra jadralnega padalca (/igra/)

Sestavi NIVO DNEVA iz dejanske vremenske napovedi in ga zapiše na dva načina:
  igra/nivo.json      — bere ga igra v brskalniku (osveži se, če je svežji)
  igra/index.html     — nivo vdelan v stran (#pg-level) + strežniško izrisan
                        opis današnjih razmer, razlaga, tabela in FAQ

Zakaj nivo računa Python in ne brskalnik: modelski teki Open-Meteo se čez dan
menjajo, zato bi klic iz brskalnika ob 7:00 in ob 20:00 dal drugačen strop in
drugačno moč termike. Obljuba »isti dan, isti nivo za vse« bi bila laž,
deljeni rezultati pa neprimerljivi. Vrednosti so zato tudi KVANTIZIRANE
(strop na 25 m, dvigi na 0,1 m/s) — drobna sprememba med tekoma ne sme
premakniti nivoja pod nogami igralcev, ki so ga že igrali.

Napoved zajame fetch_forecast() iz generate_padalci_page — UVOŽENA, ne
podvojena (isto načelo kot storm_threat_score() pri nevihtni karti in
fetch_arso_stations() pri gasilskih vodotokih). Tam je tudi fly_score(), ki
ostaja edini vir ocene priletnosti; ta skript je ne računa na novo.

Uporaba:
  python3 tools/generate_igra_page.py [--offline]
"""
import datetime, html, json, math, os, sys, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — skupni ovoj strani
from asset_version import asset_href  # noqa: E402
# Zajem napovedi in ocena priletnosti sta pri starševski strani; tu ju samo
# uporabimo. Če dodaš spremenljivko, jo dodaj v HOURLY_VARS TAM, ne tu.
from generate_padalci_page import fetch_forecast, fly_score  # noqa: E402

ROOT = seo.ROOT
SITE = seo.SITE
TODAY = seo.TODAY

URL = "/igra/"
TITLE = "Termika — igra jadralnega padalca nad Savinjsko dolino"
SEZNAM_URE = range(9, 19)          # ure, med katerimi iščemo vrhunec termike

# ── Pot preleta ─────────────────────────────────────────────────────────────
# Lomljenka skozi prave kraje (dolina se zavije, zato ravna črta ne gre).
# Razdalje so kumulativne po tej poti, višine so dejanske.
#
# ZAKAJ NI ZAJETO IZ Open-Meteo Elevation API: preverjeno ob gradnji — tisti
# vir je v dolini točen (Rečica 374 m, Mozirje 338 m, Celje 241 m), gorski
# svet pa močno splošči (vzletišče Golte ~1400 m vrne kot ~600 m, Menina
# planina 1500 m kot 1077 m). Za igro, ki se začne s spustom z Golt, je to
# neuporabno. Profil je zato ročen: dolinske višine iz tistega vira, vrhovi in
# vzletišče po objavljenih podatkih. NE zamenjuj tega s klicem Elevation API.
POT = [
    # (km po poti, nadmorska višina v m)
    (0.0, 1400), (0.6, 1300), (1.2, 1150), (2.0, 950), (3.0, 760),
    (4.0, 620), (5.5, 500), (7.0, 430), (8.5, 395), (10.3, 374),
    (12.0, 355), (13.6, 338), (15.0, 380), (16.5, 470), (17.8, 400),
    (19.1, 320), (21.0, 360), (23.4, 290), (25.7, 280), (28.0, 320),
    (30.5, 300), (33.5, 250), (36.0, 285), (38.5, 320), (41.7, 241),
    (44.0, 260),
]
MEJNIKI = [
    (0.0, "Golte"), (10.3, "Rečica"), (13.6, "Mozirje"), (19.1, "Letuš"),
    (23.4, "Braslovče"), (25.7, "Polzela"), (33.5, "Žalec"), (41.7, "Celje"),
]
KONEC_KM = 44.0
TEREN_KORAK_M = 250

# Os doline Golte→Celje; nanjo projiciramo veter, ker je igra dvodimenzionalna.
OS_AZIMUT = 113.8
# Referenčna višina dna doline: konvekcijska plast in baza oblakov sta podani
# nad tlemi, igra pa računa v nadmorskih višinah.
DNO_DOLINE_M = 350


def q(x, step):
    """Kvantizacija na korak — brez nje bi vsak modelski tek premaknil nivo."""
    if x is None:
        return None
    return round(round(x / step) * step, 6)


def fnv1a(s):
    h = 2166136261
    for ch in s.encode("utf-8"):
        h ^= ch
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def teren_vzorci():
    """Profil poti, prevzorčen na enakomeren korak (igra vmes interpolira)."""
    out, km, korak = [], 0.0, TEREN_KORAK_M / 1000.0
    while km <= KONEC_KM + 1e-9:
        out.append(round(_lerp(POT, km)))
        km += korak
    return out


def _lerp(pairs, km):
    if km <= pairs[0][0]:
        return float(pairs[0][1])
    if km >= pairs[-1][0]:
        return float(pairs[-1][1])
    for i in range(1, len(pairs)):
        if km <= pairs[i][0]:
            (x0, y0), (x1, y1) = pairs[i - 1], pairs[i]
            return y0 + (y1 - y0) * (km - x0) / (x1 - x0)
    return float(pairs[-1][1])


def vzdolzna(speed_kmh, dir_from_deg):
    """Komponenta vetra vzdolž osi doline v m/s. + je hrbtnik (proti Celju).

    Open-Meteo poda smer, IZ katere veter piha, zato +180°.
    Preveri: SZ veter (315°) → cos(315+180−113,8) = cos(381,2°) ≈ +0,98 → hrbtnik.
    """
    return speed_kmh * math.cos(math.radians(dir_from_deg + 180 - OS_AZIMUT)) / 3.6


def _hv(h, key, i, dflt=0.0):
    arr = h.get(key) or []
    v = arr[i] if i < len(arr) else None
    return dflt if v is None else v


def w_star(direct_rad, z_i):
    """Deardorffova konvekcijska hitrostna lestvica (m/s).

    w* = (g/θ · H/(ρ·cp) · z_i)^(1/3); g/θ ≈ 9,81/288, ρ·cp ≈ 1200 J m⁻³ K⁻¹,
    turbulentni tok toplote H ≈ 0,35 · sevanje (groba Bowenova delitev nad
    zaraslim terenom).

    NAMENOMA ne uporabljamo CAPE za moč termike: CAPE meri potencial globoke
    vlažne konvekcije, ne suhe termike. Na najlepšem »modrem« dnevu je CAPE
    lahko 0, termika pa 3 m/s — po CAPE bi igra nagrajevala nevihtne dni in
    kaznovala idealne, torej učila ravno narobe. CAPE ostane tam, kjer je
    smiseln: v fly_score() kot mera nevarnosti.
    """
    H = 0.35 * max(0.0, direct_rad)
    val = 0.03406 * (H / 1200.0) * max(0.0, z_i)
    return val ** (1.0 / 3.0) if val > 0 else 0.0


def build_level(data, date):
    """Napoved → nivo dneva. Čista funkcija: isti (data, date) → isti nivo."""
    h = data.get("hourly") or {}
    times = h.get("time") or []
    if not times:
        raise ValueError("Open-Meteo brez urnih podatkov")

    ds = date.isoformat()
    idxs = [i for i, t in enumerate(times)
            if t.startswith(ds) and int(t[11:13]) in SEZNAM_URE]
    if not idxs:
        raise ValueError(f"ni urnih vrednosti za {ds}")

    def rad(i):
        # direct_radiation je pravi vhod za termiko; če ga ni, pade na globalno.
        return _hv(h, "direct_radiation", i, _hv(h, "shortwave_radiation", i))

    # Vrhunec dneva = ura z najvišjim w*. Vse ostalo beremo iz TE ure, da je
    # nivo en sam skladen posnetek, ne mešanica različnih ur.
    best = max(idxs, key=lambda i: w_star(rad(i), _hv(h, "boundary_layer_height", i)))

    z_i = max(0.0, _hv(h, "boundary_layer_height", best))
    ws = w_star(rad(best), z_i)
    low_cloud = min(100.0, max(0.0, _hv(h, "cloud_cover_low", best)))
    # Jedro termike je hitrejše od povprečja stolpca (~1,35×); nizka oblačnost
    # gasi sevanje pri tleh in s tem termiko.
    termika = 1.35 * ws * (1 - min(90.0, low_cloud) / 140.0)

    t2, td = _hv(h, "temperature_2m", best, 15.0), _hv(h, "dew_point_2m", best, 8.0)
    baza_agl = 125.0 * max(0.0, t2 - td)          # Espy
    strop_bl = z_i + DNO_DOLINE_M
    baza_asl = baza_agl + DNO_DOLINE_M
    # Kumulusi nastanejo le, če je baza POD vrhom konvekcije. Če je nad njim,
    # je »moder dan« — termika je, oblakov ni in stebrov ne vidiš.
    kumulusi = baza_asl < strop_bl - 100
    strop = min(strop_bl, baza_asl)

    w10 = _hv(h, "wind_speed_10m", best)
    w180 = _hv(h, "wind_speed_180m", best, w10 * 1.6)
    d10 = _hv(h, "wind_direction_10m", best, 270.0)
    d180 = _hv(h, "wind_direction_180m", best, d10)
    gust = _hv(h, "wind_gusts_10m", best, w10)
    rain = max(0.0, _hv(h, "precipitation", best))
    code = int(_hv(h, "weather_code", best, 0))
    cape = _hv(h, "cape", best)

    # Turbulenca: sunkovitost pri tleh + strig med nivoji. (Ne iz višine
    # ničelne izoterme — ta z nemirnostjo zraka nima zveze.)
    strig = abs(w180 - w10)
    turb = min(1.0, max(0.0, (gust - w10) / 25.0)) * 0.6 \
        + min(1.0, max(0.0, strig / 20.0)) * 0.4

    # Megla in padavine termiko zbijejo; strop pade.
    if code in (45, 48):
        termika *= 0.2
        strop = min(strop, DNO_DOLINE_M + 250)
    if rain > 0.1:
        termika *= max(0.3, 1 - 0.55 * min(1.0, rain / 2.5))

    # Masovni spust med stebri: kar gre gor, se mora nekje spustiti — in
    # močnejši ko je dan, hujši je spust vmes.
    sink = 0.25 + 0.38 * (termika / 3.0)

    # Razmik med stebri je ~1,5–3× višine konvekcijske plasti; jemljemo spodnji
    # del tega razpona, ker mora biti dan igralen tudi pri nizkem stropu.
    gostota = min(3.8, max(0.9, 1.6 * z_i / 1000.0))

    ocena = fly_score(w10, _hv(h, "precipitation_probability", best), cape, z_i, 1)

    return {
        "datum": ds,
        "generated": datetime.datetime.now(datetime.timezone.utc)
                     .isoformat(timespec="seconds").replace("+00:00", "Z"),
        "vir": "open-meteo",
        "seme": fnv1a(ds),
        "ura": times[best][11:16],
        "strop_m": q(strop, 25),
        "strop_bl_m": q(strop_bl, 25),
        "baza_m": q(baza_asl, 25) if kumulusi else None,
        "termika_ms": q(termika, 0.1),
        "w_star": q(ws, 0.1),
        "sink_ms": q(sink, 0.05),
        "gostota_km": q(gostota, 0.1),
        "z_i_m": q(z_i, 25),
        "veter_tla_ms": q(vzdolzna(w10, d10), 0.1),
        "veter_180_ms": q(vzdolzna(w180, d180), 0.1),
        "veter_kmh": q(w180, 1),
        "veter_smer": q(d180, 10),
        "sunki_kmh": q(gust, 1),
        "turbulenca": q(turb, 0.05),
        "padavine_mm": q(rain, 0.1),
        "koda_vremena": code,
        "cape": q(cape, 25),
        "ocena": ocena,
        "konec_km": KONEC_KM,
        "mejniki": [{"km": km, "ime": ime} for km, ime in MEJNIKI],
        "teren": {"korak_m": TEREN_KORAK_M, "od_km": 0, "h": teren_vzorci()},
    }


def rezervni_level(prejsnji):
    """Raje star podatek kot prazna stran (isto načelo kot inject_forecast.py).

    Če imamo včerajšnji nivo, ga obdržimo — igra ga označi kot nesvežega prek
    `generated`. Če nimamo niti tega, sestavimo povprečen dan in ga izrecno
    označimo kot rezervo, nikoli kot »današnjega«.
    """
    if prejsnji:
        return dict(prejsnji, vir="zastarel")
    ds = TODAY.isoformat()
    return {
        "datum": ds, "generated": None, "vir": "rezerva", "seme": fnv1a(ds),
        "ura": None, "strop_m": 1600, "strop_bl_m": 1650, "baza_m": 1575,
        "termika_ms": 2.1, "w_star": 1.6, "sink_ms": 0.52, "gostota_km": 1.9,
        "z_i_m": 1250, "veter_tla_ms": 1.0, "veter_180_ms": 2.4,
        "veter_kmh": 9, "veter_smer": 290, "sunki_kmh": 15, "turbulenca": 0.3,
        "padavine_mm": 0.0, "koda_vremena": 2, "cape": 0, "ocena": None,
        "konec_km": KONEC_KM,
        "mejniki": [{"km": km, "ime": ime} for km, ime in MEJNIKI],
        "teren": {"korak_m": TEREN_KORAK_M, "od_km": 0, "h": teren_vzorci()},
    }


# ── Besedilo ────────────────────────────────────────────────────────────────

def num(v, d=0):
    if v is None:
        return "—"
    return f"{v:.{d}f}".replace(".", ",")


def opis_dneva(l):
    """Besedilo, ki se vsak dan spremeni — to je vsebina strani, ne okras."""
    dvig = (l["termika_ms"] or 0) - 1.28   # spust padala med kroženjem
    strop = l["strop_m"] or 0
    # Te veje morajo ostati usklajene z dayRating() v igra/igra.js — igralec
    # ne sme tu prebrati »soliden dan«, igra pa mu takoj zatem javiti »nizek
    # strop«. Namerna podvojitev (Python piše stran, JS teče v igri).
    if l["koda_vremena"] in (45, 48):
        znacaj = ("Megla. Sonce ne pride do tal, termike praktično ni — z Golt "
                  "lahko samo zdrsneš v sivino.")
    elif strop and strop < 1400:
        znacaj = (f"Konvekcija seže le do {num(strop)} m, to je pod vzletiščem na Goltah "
                  f"({num(POT[0][1])} m). Z Golt boš najprej samo padal; loviti se začne "
                  f"šele nižje v dolini, kjer je zrak sploh premešan.")
    elif (l["padavine_mm"] or 0) > 1.2:
        znacaj = ("Dežuje. Termika je zbita, zrak med stebri pada hitreje kot "
                  "običajno. Danes gre za preživetje prvih kilometrov.")
    elif dvig < 0.3:
        znacaj = ("Mrtev zrak — dvigov skoraj ni. Vprašanje ni, kako visoko, "
                  "ampak kako daleč prideš z eno samo višino z vzletišča.")
    elif dvig < 1.0:
        znacaj = ("Šibek dan. Vsak steber šteje in nobene višine ne smeš "
                  "zapraviti — do Rečice je z Golt 10,3 km.")
    elif dvig < 2.0:
        znacaj = "Soliden dan. Dolina je odprta, Letuš je realen cilj."
    elif dvig < 3.0:
        znacaj = ("Dober dan. Do Žalca je dovolj — če ne zgrešiš stebrov in "
                  "znaš izkoristiti zanos.")
    else:
        znacaj = "Odličen dan. Danes je Celje na dosegu."

    nebo = ("Baza kumulusov je na %s m, zato oblaki kažejo, kje so dvigi."
            % num(l["baza_m"])) if l["baza_m"] else \
           ("Baza oblakov je nad vrhom konvekcije, zato je danes »moder dan« — "
            "termika je, kumulusov nad njo pa ne. Stebre moraš iskati po variu "
            "in po terenu, ne po nebu.")

    veter = l["veter_180_ms"] or 0
    if veter > 1.0:
        vet = (f"Veter na višini nosi po dolini navzdol ({num(abs(veter) * 3.6, 0)} km/h "
               f"v hrbet) — med kroženjem te zanaša proti Celju, kar je zastonj razdalja, "
               f"a stebri se pri tem nagnejo in jih je težje zadržati.")
    elif veter < -1.0:
        vet = (f"Veter na višini piha po dolini navzgor ({num(abs(veter) * 3.6, 0)} km/h "
               f"čelno) — vsak kilometer boš moral izleteti, med kroženjem pa te nosi nazaj.")
    else:
        vet = "Veter vzdolž doline je šibek, zato stebri stojijo skoraj pokonci."

    return f"{znacaj} {nebo} {vet}"


def build_body(l, svez_opomba):
    esc = html.escape
    crumbs = [("Meteorec", "/"), ("Vreme za padalce", "/vreme-za-padalce/"), ("Termika", None)]
    dvig = (l["termika_ms"] or 0) - 1.28

    pogoji = f'''  <ul class="pg-cond">
    <li><b>Strop</b><span>{num(l["strop_m"])} m</span><em>{"baza oblakov" if l["baza_m"] else "vrh termike"}</em></li>
    <li><b>Dvigi v jedru</b><span>{num(l["termika_ms"], 1)} m/s</span><em>vzpon padala ~{num(max(0, dvig), 1)} m/s</em></li>
    <li><b>Razmik stebrov</b><span>{num(l["gostota_km"], 1)} km</span><em>toliko preletiš med njimi</em></li>
    <li><b>Veter na 180 m</b><span>{num(l["veter_kmh"])} km/h</span><em>{"v hrbet" if (l["veter_180_ms"] or 0) > 0 else "čelno"} vzdolž doline</em></li>
    <li><b>Konvekcijska plast</b><span>{num(l["z_i_m"])} m</span><em>nad tlemi (z<sub>i</sub>)</em></li>
    <li><b>Turbulenca</b><span>{num(l["turbulenca"], 2)}</span><em>iz sunkov in striženja</em></li>
  </ul>'''

    mejnik_vrstice = "\n".join(
        f'      <tr><th>{esc(ime)}</th><td>{num(km, 1)} km · tla {num(_lerp(POT, km))} m</td></tr>'
        for km, ime in MEJNIKI)

    faq = [
        ("Ali je igra realistična?",
         "Fizika je poenostavljena, a ni izmišljena: polara jadralnega padala (najmanjši "
         "spust 0,95 m/s, najboljše drsenje ~9,9 : 1), dvigi kot navpična hitrost zraka, "
         "masovni spust med stebri, zanos med kroženjem in strop na bazi oblakov. Moč "
         "termike je izračunana po Deardorffovi konvekcijski hitrostni lestvici iz "
         "sončnega sevanja in globine konvekcijske plasti. Navpično merilo na sliki je "
         "raztegnjeno približno 1,6-krat, sicer bi bila dolina en tanek pas."),
        ("Zakaj danes ne pridem daleč?",
         "Ker danes ni dan za to. Nivo ni naključen — sestavljen je iz današnje napovedi. "
         "Nizek strop, šibko sevanje, megla ali čelni veter razdaljo omejijo enako kot v "
         "resnici. Poskusi spet čez nekaj dni; poleti bo drugače kot novembra."),
        ("Ali imamo vsi isti nivo?",
         "Da. Nivo sestavi strežnik enkrat na dan in ga vsem postreže enakega, vrednosti "
         "pa so zaokrožene, da ga osveževanje napovedi med dnevom ne premakne. Zato so "
         "deljeni rezultati istega dne primerljivi."),
        ("Ali lahko po tej igri sklepam, ali danes letim?",
         "Ne. To je igra, ne pripomoček za odločanje o letu. Za oceno primernosti letenja "
         "je tu <a href=\"/vreme-za-padalce/\">Vreme za padalce</a>, odločitev pa je vedno "
         "pilotova in odvisna od izkušenj, opreme, terena in razmer na kraju samem."),
        ("Kje je pot, po kateri letim?",
         "Po Zgornji Savinjski dolini: z vzletišča na Goltah (~1400 m) mimo Rečice ob "
         "Savinji, Mozirja, Letuša, Braslovč in Žalca do Celja — 41,7 km po dejanski poti "
         "skozi te kraje. Višinski profil je poenostavljen."),
    ]
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f"    <details><summary>{esc(q_)}</summary><p>{a}</p></details>" for q_, a in faq
    ) + "\n  </div>"

    level_json = json.dumps(l, ensure_ascii=False, separators=(",", ":"))

    return f'''{seo.crumbs_html(crumbs)}
{seo.stn_badge()}
  <h1 class="page-title">Termika — igra jadralnega padalca</h1>
  <p class="post-meta">Vzleti z Golt in preleti Savinjsko dolino. Nivo se vsak dan
  sestavi iz dejanske vremenske napovedi · {TODAY.isoformat()}</p>
  <p class="archive-intro">{opis_dneva(l)}</p>

  <div class="pg-bleed">
    <div id="pg-game" tabindex="0" role="application"
         aria-label="Termika — igra jadralnega padalca nad Savinjsko dolino">
      <div class="pg-hud">
        <p class="pg-hero"><span id="pg-km">0,2</span><small>km</small></p>
        <div class="pg-stats">
          <div><span class="pg-lbl">Višina</span><span class="pg-val"><span id="pg-alt">1440</span> m</span></div>
          <div><span class="pg-lbl">Nad tlemi</span><span class="pg-val"><span id="pg-agl">40</span> m</span></div>
          <div><span class="pg-lbl">Vario</span><span class="pg-val"><span id="pg-vario" class="pg-v">0,0</span> m/s</span></div>
          <div><span class="pg-lbl">Čas leta</span><span class="pg-val" id="pg-time">0 min</span></div>
          <div><span class="pg-lbl">Rekord</span><span class="pg-val" id="pg-best">—</span></div>
        </div>
      </div>
      <div class="pg-route" aria-hidden="true">
        <span>Golte</span>
        <div class="pg-route-bar" id="pg-route-bar">
          <i class="pg-route-fill" id="pg-route-fill"></i>
          <i class="pg-route-mark" id="pg-route-mark"></i>
        </div>
        <span>Celje</span>
      </div>
      <canvas id="pg-canvas" width="900" height="506"
              aria-label="Stranski pogled na dolino: padalo, termični stebri, oblaki in teren"></canvas>
      <div class="pg-overlay" id="pg-overlay">
        <div class="pg-ov-in">
          <p class="pg-ov-kicker">Nivo dneva · {TODAY.isoformat()}</p>
          <h2 class="pg-ov-title">Termika</h2>
          <p class="pg-ov-sub">Igra se naloži … Če se ne, potrebuje JavaScript —
          današnje razmere so opisane zgoraj in v tabeli pod igro.</p>
        </div>
      </div>
      <div class="pg-controls">
        <button class="pg-btn pg-circle" id="pg-btn-circle" type="button">
          Kroži<small>drži · levo/desno loviš jedro</small></button>
        <button class="pg-btn" id="pg-btn-speed" type="button">
          Pospeši<small>drži · proti vetru</small></button>
        <button class="pg-btn pg-sound" id="pg-btn-sound" type="button" aria-pressed="false">🔇 Vario</button>
      </div>
      <p class="pg-live" id="pg-live" role="status" aria-live="polite"></p>
    </div>
    <p class="pg-source" id="pg-source">{esc(svez_opomba)}</p>
  </div>

  <h2>Današnje razmere v igri</h2>
{pogoji}
  <p class="muted-note">Iste vrednosti poganjajo nivo. Ocena primernosti za letenje
  ({num(l["ocena"])}{"" if l["ocena"] is None else " %"}) je izračunana z istim modelom kot na strani
  <a href="/vreme-za-padalce/">Vreme za padalce</a> — tam je tudi razlaga.</p>

  <h2>Kako se igra</h2>
  <p class="archive-intro">Ena poteza: <strong>drži</strong>, ko te dviga, in <strong>spusti</strong>,
  ko te ne. Med držanjem krožiš — po zraku ne napreduješ, zato pa se dvigaš in te zanaša veter.
  Ko spustiš, drsiš naprej z okoli 38 km/h in počasi izgubljaš višino. Gumb <strong>Pospeši</strong>
  te požene na 52 km/h: uporaben proti čelnemu vetru in skozi območja spuščanja, a te stane višino.
  Na tipkovnici: <kbd>preslednica</kbd> kroženje, <kbd>D</kbd> pospeševalnik,
  <kbd>←</kbd>/<kbd>→</kbd> lovljenje jedra. Ko se dotakneš tal, je leta konec.</p>
  <p class="archive-intro">Glavni inštrument je <strong>vario</strong> — stolpič ob desnem robu.
  Zelen pomeni dvig, rdeč spust. Pravi pilot leti po njem, ker se termike ne vidi.</p>

  <h2>Kaj te igra nauči o vremenu</h2>
  <p class="archive-intro">Vse, kar v igri odloča, odloča tudi v resnici:</p>
  <table class="stats">
    <tr><th>Sonce</th><td>Sevanje segreje tla, tla segrejejo zrak — <a href="/slovar/termika/">termika</a>
      je posledica sončnega sevanja, ne temperature. Zato je marčevsko sonce boljše od toplega,
      a oblačnega julijskega popoldneva.</td></tr>
    <tr><th>Globina premešanja</th><td>Konvekcijska plast (z<sub>i</sub>) pove, kako globoko se zrak
      premeša. Plitva plast pomeni nizek strop in šibke dvige, tudi ob soncu.</td></tr>
    <tr><th><a href="/slovar/kumulus/">Kumulusi</a></th><td>Baza oblakov je tam, kjer se dvigajoči zrak
      ohladi do <a href="/slovar/rosisce/">rosišča</a> — približno 125 m na vsako stopinjo razlike med
      temperaturo in rosiščem. Kumulus torej stoji nad termiko in ti jo pokaže. Če je baza višja od vrha
      konvekcije, kumulusov ni: »moder dan«, ko letiš na slepo.</td></tr>
    <tr><th><a href="/slovar/temperaturna-inverzija/">Inverzija</a></th><td>Nad stropom dvig preneha.
      V igri to vidiš kot črtkano črto — nad njo ne gre, ne glede na to, kako dolgo krožiš.</td></tr>
    <tr><th>Masovni spust</th><td>Zrak, ki se dviga v stebrih, se mora med njimi spuščati. Močnejši ko
      je dan, hujši je spust vmes — zato dober dan ni samo lažji, ampak tudi bolj neizprosen do napak.</td></tr>
    <tr><th>Veter in zanos</th><td>Med kroženjem te veter nosi s seboj. V hrbet je to zastonj razdalja,
      čelno pa te vrača. Stebri se ob vetru nagnejo, zato je termika na višini drugje kot pri tleh —
      <a href="/slovar/strizenje-vetra/">striženje vetra</a> to še poudari.</td></tr>
  </table>

  <h2>Pot preleta</h2>
  <table class="stats">
{mejnik_vrstice}
  </table>
  <p class="muted-note">Razdalje so kumulativne po dejanski poti skozi te kraje (dolina se zavije,
  zato ni ravna črta). Višinski profil je poenostavljen; navpično merilo na sliki je raztegnjeno.</p>

{faq_html}
  <p class="muted-note">Igra ni pripomoček za odločanje o letenju in ne nadomešča napovedi, presoje
  pilota ali predpisov. Za oceno razmer glej <a href="/vreme-za-padalce/">Vreme za padalce</a>.</p>
  <a class="back-link" href="/vreme-za-padalce/">← Vreme za padalce</a>

  <script type="application/json" id="pg-level">{level_json}</script>
  <script src="{asset_href("igra/igra.js")}" defer></script>'''


def main():
    offline = "--offline" in sys.argv
    path_json = os.path.join(ROOT, "igra", "nivo.json")
    prejsnji = None
    if os.path.exists(path_json):
        try:
            with open(path_json, encoding="utf-8") as f:
                prejsnji = json.load(f)
        except (OSError, json.JSONDecodeError):
            prejsnji = None

    level = None
    if not offline:
        try:
            print(f"[{TODAY}] Pridobivam napoved Open-Meteo …")
            level = build_level(fetch_forecast(), TODAY)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"! Napoved ni dosegljiva ({e}) — obdržim prejšnji nivo.", file=sys.stderr)
    if level is None:
        level = rezervni_level(prejsnji)

    # Teren in mejnike vedno osvežimo iz te datoteke, tudi pri zastarelem nivoju —
    # pot se ne spreminja z vremenom in stara kopija bi po morebitni spremembi
    # profila obtičala.
    level["mejniki"] = [{"km": km, "ime": ime} for km, ime in MEJNIKI]
    level["teren"] = {"korak_m": TEREN_KORAK_M, "od_km": 0, "h": teren_vzorci()}
    level["konec_km"] = KONEC_KM

    os.makedirs(os.path.join(ROOT, "igra"), exist_ok=True)
    with open(path_json, "w", encoding="utf-8") as f:
        json.dump(level, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")

    if level["vir"] == "open-meteo":
        svez = (f"🟢 Nivo dneva {level['datum']}"
                + (f" · vrhunec termike ob {level['ura']}" if level["ura"] else "")
                + " · iz napovedi Open-Meteo")
    elif level["vir"] == "zastarel":
        svez = (f"🟡 Nivo z dne {level['datum']} — današnja napoved ni bila dosegljiva, "
                f"zato je prikazan zadnji znani.")
    else:
        svez = ("🔴 Nivo iz povprečnih razmer — napovedi ni bilo mogoče pridobiti. "
                "Igra deluje, a ni današnja.")

    desc = (f"Igra jadralnega padalca nad Zgornjo Savinjsko dolino: vzleti z Golt in preleti "
            f"čim več. Nivo se vsak dan sestavi iz dejanske napovedi — danes strop "
            f"{num(level['strop_m'])} m, dvigi {num(level['termika_ms'], 1)} m/s.")

    schema = "\n".join([
        seo.webpage_schema(URL, TITLE, desc, date_published="2026-09-02"),
        seo.crumbs_schema([("Meteorec", "/"), ("Vreme za padalce", "/vreme-za-padalce/"),
                           ("Termika", None)]),
    ])
    head = schema + f'\n<link rel="stylesheet" href="{asset_href("igra/igra.css")}">'

    html_out = seo.page_shell(TITLE, desc, URL, head, build_body(level, svez))
    seo.write_page("igra/index.html", html_out, force=True)
    print(f"  → igra/index.html + igra/nivo.json ({level['vir']}, strop {num(level['strop_m'])} m, "
          f"dvigi {num(level['termika_ms'], 1)} m/s, razmik {num(level['gostota_km'], 1)} km)")


if __name__ == "__main__":
    main()
