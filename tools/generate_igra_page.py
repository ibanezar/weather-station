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

# ── Koridorji ───────────────────────────────────────────────────────────────
# Igra ne leti po eni sami osi. Vsak dan izbere smer glede na veter — tako kot
# pilot. Geometrijo (potek, mejnike, višinski profil) pripravi enkratni
# tools/build_igra_corridors.py in je committana v igra/koridorji.json; tu jo
# samo preberemo. Tam je tudi opisano, od kod višine in kje je vir nezanesljiv.
KORIDORJI_PATH = os.path.join(ROOT, "igra", "koridorji.json")

# Referenčna višina dna doline: konvekcijska plast in baza oblakov sta podani
# nad tlemi, igra pa računa v nadmorskih višinah.
DNO_DOLINE_M = 350


def nalozi_koridorje():
    with open(KORIDORJI_PATH, encoding="utf-8") as f:
        d = json.load(f)
    if not d.get("koridorji"):
        raise ValueError("igra/koridorji.json je prazen")
    return d["koridorji"]


def teren_na(kor, km):
    """Višina terena koridorja na dani kilometrini (linearna interpolacija)."""
    t = kor["teren"]
    h = t["h"]
    f = (km - t.get("od_km", 0)) / (t["korak_m"] / 1000.0)
    if f <= 0:
        return float(h[0])
    if f >= len(h) - 1:
        return float(h[-1])
    i = int(f)
    return h[i] + (h[i + 1] - h[i]) * (f - i)


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


def vzdolzna(speed_kmh, dir_from_deg, azimut):
    """Komponenta vetra vzdolž dane smeri v m/s. + je hrbtnik.

    Open-Meteo poda smer, IZ katere veter piha, zato +180°.
    Preveri: SZ veter (315°) na osi 113,8° → cos(381,2°) ≈ +0,98 → hrbtnik.
    """
    return speed_kmh * math.cos(math.radians(dir_from_deg + 180 - azimut)) / 3.6


def precna(speed_kmh, dir_from_deg, azimut):
    """Komponenta pravokotno na smer leta (m/s, brez predznaka).

    Igra je dvodimenzionalna in te komponente ne more narisati, a je NE
    zavržemo: prečni veter ob pobočjih dela rotor in nemiren zrak, zato gre v
    turbulenco. Prej je preprosto izginila, čeprav je bila v 58 % termično
    uporabnih ur večja od vzdolžne.
    """
    return abs(speed_kmh * math.sin(math.radians(dir_from_deg + 180 - azimut))) / 3.6


def hrbtnik_koridorja(kor, speed_kmh, dir_from_deg):
    """Z dolžino uteženo povprečje hrbtnika po odsekih lomljenke.

    Koridor ni ravna črta, zato en sam azimut ni pošten — dolina se zavije in
    veter je lahko na enem odseku v hrbet, na drugem čelno.
    """
    odseki = kor.get("odseki") or [{"dolzina_km": 1, "azimut": kor["azimut"]}]
    skupaj = sum(o["dolzina_km"] for o in odseki) or 1.0
    return sum(o["dolzina_km"] * vzdolzna(speed_kmh, dir_from_deg, o["azimut"])
               for o in odseki) / skupaj


def izberi_koridor(koridorji, speed_kmh, dir_from_deg):
    """Koridor dneva = tisti z največ hrbtnika po GRADIENTNEM vetru (~1500 m).

    Zakaj višinski in ne prizemni: prelet poteka med ~500 in 2500 m, dolinski
    vetrič pri tleh pa je pogosto obrnjen ravno nasproti gradientnemu (3. 9.
    2026 npr. 180 m proti ZJZ, 850 hPa proti VSV). Za izbiro smeri je
    merodajen tisti, ki te dejansko nese.
    """
    ocene = [(hrbtnik_koridorja(k, speed_kmh, dir_from_deg), k) for k in koridorji]
    ocene.sort(key=lambda x: -x[0])
    return ocene[0][1], ocene[0][0], ocene


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


def build_level(data, date, koridorji):
    """Napoved → nivo dneva. Čista funkcija: isti (data, date, koridorji) → isti nivo."""
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
    # Jedro termike je hitrejše od povprečja stolpca. Literatura daje vršni
    # dvig v jedru ~1,5–2× w*; s količnikom 1,35 je igra dajala dvige, šibkejše
    # od spuščanja padala med kroženjem (1,28 m/s), zato kroženje sploh ni
    # dvigalo. Pri 1,6 aprilski dan (w* 1,7) da ~1,4 m/s vzpona na variu, kar
    # ustreza temu, kar pilot tak dan res vidi.
    # Nizka oblačnost gasi sevanje pri tleh in s tem termiko.
    termika = 1.6 * ws * (1 - min(90.0, low_cloud) / 140.0)

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
    # Gradientni veter na ~1500 m — po njem izberemo koridor in po njem se
    # ravna zgornji del vetrovnega profila v igri.
    w850 = _hv(h, "wind_speed_850hPa", best, w180 * 1.4)
    d850 = _hv(h, "wind_direction_850hPa", best, d180)
    gust = _hv(h, "wind_gusts_10m", best, w10)
    rain = max(0.0, _hv(h, "precipitation", best))
    code = int(_hv(h, "weather_code", best, 0))
    cape = _hv(h, "cape", best)

    kor, hrbtnik, lestvica = izberi_koridor(koridorji, w850, d850)
    az = kor["azimut"]

    # Prečni veter ni več zavržen: ob pobočjih dela rotor in nemiren zrak.
    prec = precna(w850, d850, az)

    # Turbulenca: sunkovitost pri tleh + strig med nivoji + prečna komponenta.
    # (Ne iz višine ničelne izoterme — ta z nemirnostjo zraka nima zveze.)
    strig = abs(w180 - w10)
    turb = min(1.0, max(0.0, (gust - w10) / 25.0)) * 0.5 \
        + min(1.0, max(0.0, strig / 20.0)) * 0.3 \
        + min(1.0, max(0.0, prec / 5.5)) * 0.2

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

    lvl = {
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
        "veter_tla_ms": q(vzdolzna(w10, d10, az), 0.1),
        "veter_180_ms": q(vzdolzna(w180, d180, az), 0.1),
        "veter_visoko_ms": q(vzdolzna(w850, d850, az), 0.1),
        "veter_precno_ms": q(prec, 0.1),
        "veter_kmh": q(w850, 1),
        "veter_smer": q(d850, 10),
        "veter_tla_kmh": q(w180, 1),
        "veter_tla_smer": q(d180, 10),
        "sunki_kmh": q(gust, 1),
        "turbulenca": q(turb, 0.05),
        "padavine_mm": q(rain, 0.1),
        "koda_vremena": code,
        "cape": q(cape, 25),
        "ocena": ocena,
    }
    return vstavi_koridor(lvl, kor, hrbtnik, lestvica)


def vstavi_koridor(lvl, kor, hrbtnik=None, lestvica=None):
    """Doda geometrijo koridorja v nivo. Teren in mejniki gredo VEDNO od tu,
    tudi pri zastarelem nivoju — pot se z vremenom ne spreminja in stara kopija
    bi po spremembi profila obtičala."""
    lvl["koridor"] = {
        "id": kor["id"], "ime": kor["ime"], "kratko": kor["kratko"],
        "opis": kor["opis"], "azimut": kor["azimut"],
        "dolzina_km": kor["dolzina_km"],
        "hrbtnik_kmh": q(hrbtnik * 3.6, 1) if hrbtnik is not None else None,
        "izbira": [{"id": k["id"], "kratko": k["kratko"], "hrbtnik_kmh": q(v * 3.6, 1)}
                   for v, k in (lestvica or [])],
    }
    lvl["konec_km"] = kor["konec_km"]
    lvl["mejniki"] = kor["mejniki"]
    lvl["teren"] = kor["teren"]
    return lvl


def rezervni_level(prejsnji, koridorji):
    """Raje star podatek kot prazna stran (isto načelo kot inject_forecast.py).

    Če imamo včerajšnji nivo, ga obdržimo — igra ga označi kot nesvežega prek
    `generated`. Če nimamo niti tega, sestavimo povprečen dan in ga izrecno
    označimo kot rezervo, nikoli kot »današnjega«.

    Koridor: pri zastarelem nivoju obdržimo tistega, ki je bil izbran takrat
    (smer je del tistega dne), pri čisti rezervi pa privzamemo prvega.
    """
    po_id = {k["id"]: k for k in koridorji}
    if prejsnji:
        prej_kor = prejsnji.get("koridor") or {}
        kor = po_id.get(prej_kor.get("id"), koridorji[0])
        # Če je prejšnji nivo ŽE današnji (jutranji tek je uspel, poznejši pa
        # je našel Open-Meteo nedosegljiv), ni zastarel in ga ne smemo tako
        # označiti -- stran bi po nepotrebnem javila 🟡, hrbtnik in lestvica
        # smeri pa bi izpadla, čeprav sta bila izračunana iz žive napovedi.
        if prejsnji.get("datum") == TODAY.isoformat():
            lvl = vstavi_koridor(dict(prejsnji), kor)
            lvl["koridor"]["hrbtnik_kmh"] = prej_kor.get("hrbtnik_kmh")
            lvl["koridor"]["izbira"] = prej_kor.get("izbira") or []
            return lvl
        return vstavi_koridor(dict(prejsnji, vir="zastarel"), kor)
    ds = TODAY.isoformat()
    lvl = {
        "datum": ds, "generated": None, "vir": "rezerva", "seme": fnv1a(ds),
        "ura": None, "strop_m": 1600, "strop_bl_m": 1650, "baza_m": 1575,
        "termika_ms": 2.1, "w_star": 1.6, "sink_ms": 0.52, "gostota_km": 1.9,
        "z_i_m": 1250, "veter_tla_ms": 1.0, "veter_180_ms": 2.4,
        "veter_visoko_ms": 3.2, "veter_precno_ms": 1.0,
        "veter_kmh": 12, "veter_smer": 290, "veter_tla_kmh": 9,
        "veter_tla_smer": 290, "sunki_kmh": 15, "turbulenca": 0.3,
        "padavine_mm": 0.0, "koda_vremena": 2, "cape": 0, "ocena": None,
    }
    return vstavi_koridor(lvl, koridorji[0])


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
                  f"({num(teren_na(l, 0))} m). Z Golt boš najprej samo padal; loviti se "
                  f"začne šele nižje, kjer je zrak sploh premešan.")
    elif (l["padavine_mm"] or 0) > 1.2:
        znacaj = ("Dežuje. Termika je zbita, zrak med stebri pada hitreje kot "
                  "običajno. Danes gre za preživetje prvih kilometrov.")
    elif dvig < 0.3:
        znacaj = ("Mrtev zrak — dvigov skoraj ni. Vprašanje ni, kako visoko, "
                  "ampak kako daleč prideš z eno samo višino z vzletišča.")
    elif dvig < 1.0:
        prvi = (l.get("mejniki") or [{}, {}])[1]
        znacaj = ("Šibek dan. Vsak steber šteje in nobene višine ne smeš zapraviti — "
                  f"že do prvega mejnika ({prvi.get('ime','?')}) je "
                  f"{num(prvi.get('km', 0), 1)} km.")
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
    kor = l.get("koridor") or {}
    mejniki = l.get("mejniki") or []

    # id-ji so tu zato, da lahko igra kartico osveži, če je nivo.json svežji od
    # (morda predpomnjenega) HTML-a — sicer bi kartica in igra kazali različne
    # številke istega dne.
    pogoji = f'''  <ul class="pg-cond">
    <li><b>Smer dneva</b><span id="pg-c-korridor">{esc(kor.get("ime", "—"))}</span><em>izbral jo je veter na 1500 m</em></li>
    <li><b>Strop</b><span id="pg-c-ceiling">{num(l["strop_m"])} m</span><em>{"baza oblakov" if l["baza_m"] else "vrh termike"}</em></li>
    <li><b>Dvigi v jedru</b><span id="pg-c-lift">{num(l["termika_ms"], 1)} m/s</span><em>vzpon padala ~{num(max(0, dvig), 1)} m/s</em></li>
    <li><b>Razmik stebrov</b><span id="pg-c-spacing">{num(l["gostota_km"], 1)} km</span><em>toliko preletiš med njimi</em></li>
    <li><b>Veter na 1500 m</b><span id="pg-c-wind">{num(l["veter_kmh"])} km/h</span><em>{"v hrbet" if (l.get("veter_visoko_ms") or 0) > 0 else "čelno"} po koridorju</em></li>
    <li><b>Prečni veter</b><span id="pg-c-cross">{num((l.get("veter_precno_ms") or 0) * 3.6)} km/h</span><em>ne nese naprej, dela nemir</em></li>
    <li><b>Konvekcijska plast</b><span id="pg-c-zi">{num(l["z_i_m"])} m</span><em>nad tlemi (z<sub>i</sub>)</em></li>
    <li><b>Turbulenca</b><span id="pg-c-turb">{num(l["turbulenca"], 2)}</span><em>sunki, strig, prečni veter</em></li>
  </ul>'''

    mejnik_vrstice = "\n".join(
        f'      <tr><th>{esc(m["ime"])}</th><td>{num(m["km"], 1)} km · '
        f'tla {num(teren_na(l, m["km"]))} m</td></tr>'
        for m in (l.get("mejniki") or []))

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
        ("Zakaj letim danes prav v to smer?",
         "Ker te tja nese veter. Igra ima štiri koridorje z Golt — po Savinjski dolini "
         "proti Celju, navzgor proti Solčavi, čez Gornji Grad proti Kamniku in čez Raduho "
         "na Koroško — in vsako jutro izbere tistega z največ vetra v hrbet. Enako se "
         "odloči pilot: smeri preleta ne izbereš ti, izbere jo veter."),
        ("Kateri veter odloča o smeri?",
         "Gradientni na približno 1500 m (850 hPa), ne tisti pri tleh. Prelet poteka v tem "
         "pasu, dolinski vetrič pri tleh pa je podnevi pogosto obrnjen ravno nasproti — "
         "3. septembra 2026 je pri tleh pihalo proti zahodu, na 1500 m pa proti vzhodu. "
         "V igri to čutiš: nizko te veter zavira, visoko te nese."),
        ("Kje je pot, po kateri letim?",
         "Po lomljenki skozi prave kraje, ker se doline zavijejo in ravna črta reže čez "
         "pobočja. Višine dna doline so iz javnega višinskega modela, vzletišče Golte "
         "(~1400 m) pa po objavljeni višini — tisti model gore močno splošči. Zato so "
         "koridorji, ki prečkajo visokogorje, v igri lažji od resničnosti."),
        ("Zakaj so rekordi ločeni po smereh?",
         "Ker so koridorji različno dolgi: proti Celju jih je 42 km, čez Raduho na Koroško "
         "pa 11,5. Dvajset kilometrov čez gorsko pregrado ni isto kot dvajset po ravni "
         "dolini, zato bi skupen rekord pomenil malo."),
        ("Ali je javna lestvica preverjena, kot pri »Prehiti model«?",
         "Ne enako. Pri igri »Prehiti model« strežnik napoved sam oceni proti izmerjenemu "
         "dnevu, zato je rezultat neprepisljiv. Tu je »Termika« fizikalna simulacija, ki teče "
         "v celoti v tvojem brskalniku — ni resničnega dogodka, proti kateremu bi strežnik "
         "prelet lahko preveril. Preveri samo, da prijavljena razdalja ne presega dolžine "
         "koridorja; kdor si priredi odjemalca, lahko prijavi poljubno število do te meje. "
         "Za pošteno igro se torej zanašamo nate."),
    ]
    izbira = kor.get("izbira") or []
    lestvica_html = ("  <table class=\"stats\">\n" + "\n".join(
        f'      <tr><th>{esc(i["kratko"])}</th><td>'
        f'{"+" if (i["hrbtnik_kmh"] or 0) >= 0 else ""}{num(i["hrbtnik_kmh"], 0)} km/h '
        f'{"v hrbet" if (i["hrbtnik_kmh"] or 0) >= 0 else "čelno"}'
        f'{" · izbrana" if i["id"] == kor.get("id") else ""}</td></tr>'
        for i in izbira) + "\n  </table>") if izbira else ""

    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f"    <details><summary>{esc(q_)}</summary><p>{a}</p></details>" for q_, a in faq
    ) + "\n  </div>"

    level_json = json.dumps(l, ensure_ascii=False, separators=(",", ":"))

    # Igra se odpre na ves zaslon, kot igra — brez glave, noge in mobilnega
    # spodnjega traku (skriti v igra.css, samo za to stran). Namesto glave je
    # .pg-topbar: pot nazaj + ime igre, oboje del igralnega vmesnika, ne
    # uredniške strani. Uvod (h1, datum, opis dneva) in preostala vsebina
    # (razlaga, koridor, FAQ) sledijo POD igro — dosegljivi z drsenjem, ne
    # nekaj, kar bi bralec moral prebrati, preden sploh vidi igro.
    return f'''  <div id="pg-game" tabindex="0" role="application"
       aria-label="Termika — igra jadralnega padalca nad Savinjsko dolino">
    <div class="pg-topbar">
      <a class="pg-topbar-back" href="/vreme-za-padalce/">← Vreme za padalce</a>
      <span class="pg-topbar-word">🪂 Termika</span>
    </div>
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
      <span id="pg-route-a">{esc(mejniki[0]["ime"]) if mejniki else "Golte"}</span>
      <div class="pg-route-bar" id="pg-route-bar">
        <i class="pg-route-fill" id="pg-route-fill"></i>
        <i class="pg-route-mark" id="pg-route-mark"></i>
      </div>
      <span id="pg-route-b">{esc(mejniki[-1]["ime"]) if mejniki else ""}</span>
    </div>
    <canvas id="pg-canvas" width="900" height="506"
            aria-label="Stranski pogled na dolino: padalo, termični stebri, oblaki in teren"></canvas>
    <div class="pg-overlay" id="pg-overlay">
      <div class="pg-ov-in">
        <p class="pg-ov-kicker">Nivo dneva · {TODAY.isoformat()}</p>
        <h2 class="pg-ov-title">Termika</h2>
        <p class="pg-ov-sub">Igra se naloži … Če se ne, potrebuje JavaScript —
        današnje razmere so opisane spodaj, pod igro.</p>
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

  <div class="pg-lb" id="pg-lb">
    <h2 class="pg-lb-h2">Lestvica</h2>
    <p class="muted-note">Vzdevek za lestvico (neobvezno):
      <input id="pg-lb-ime" type="text" maxlength="24" placeholder="Anonimni" autocomplete="nickname">
      — prikazan je samo tvoj najboljši prelet, ne vsak poskus.</p>
    <div class="pg-lb-tabs" role="tablist">
      <button type="button" class="pg-lb-tab" data-obdobje="dan" aria-pressed="true">Danes</button>
      <button type="button" class="pg-lb-tab" data-obdobje="{esc(kor.get("id", "celje"))}" aria-pressed="false">
        Rekord — {esc(kor.get("kratko", "ta koridor"))}</button>
    </div>
    <div id="pg-lb-body"><p class="muted-note">Nalagam …</p></div>
  </div>

{seo.crumbs_html(crumbs)}
{seo.stn_badge()}
  <h1 class="page-title">Termika — igra jadralnega padalca</h1>
  <p class="post-meta">Vzleti z Golt in preleti Savinjsko dolino. Nivo se vsak dan
  sestavi iz dejanske vremenske napovedi · {TODAY.isoformat()}</p>
  <p class="archive-intro">{opis_dneva(l)}</p>

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

  <h2>Koridor dneva: {esc(kor.get("ime", "—"))}</h2>
  <p class="archive-intro">{esc(kor.get("opis", ""))}
  {("Veter na 1500 m ti danes doda " + num(kor["hrbtnik_kmh"], 0) + " km/h v hrbet."
    if (kor.get("hrbtnik_kmh") or 0) > 3 else
    ("Vse smeri so danes proti vetru; ta je najmanj slaba."
     if (kor.get("hrbtnik_kmh") or 0) < -1 else
     "Veter danes ne pomaga in ne ovira — šteje samo termika."))}</p>
{lestvica_html}
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
    koridorji = nalozi_koridorje()
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
            level = build_level(fetch_forecast(), TODAY, koridorji)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"! Napoved ni dosegljiva ({e}) — obdržim prejšnji nivo.", file=sys.stderr)
    if level is None:
        level = rezervni_level(prejsnji, koridorji)

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

    # Dnevna OG kartica: profil današnjega koridorja, strop in dvigi. Riše se
    # tu (in ne v svojem koraku delavnega toka), da slika in `og:image` na
    # strani nikoli ne moreta biti iz različnih dni. Če Pillow manjka ali
    # risanje odpove, ostane splošna og-image.jpg — slika ni vredna tega, da
    # bi zaradi nje izostal nivo dneva. Nariše se PRED shemo, ker isti URL
    # potrebujeta oba (og:image in `image` v JSON-LD) — razhajanje med njima
    # javi geo_audit.py.
    og_slika = None
    try:
        import generate_igra_og  # noqa: PLC0415 — lokalno, da manjkajoč Pillow ne podre teka
        og_slika = generate_igra_og.zapisi(level, datetime.datetime.now())
        print(f"  → OG kartica: {og_slika}")
    except Exception as e:  # noqa: BLE001 — namenoma široko, glej opombo zgoraj
        print(f"! OG kartica ni nastala ({e}) — ostane splošna og-image.jpg", file=sys.stderr)

    schema = "\n".join([
        seo.webpage_schema(URL, TITLE, desc, date_published="2026-09-02", image=og_slika),
        seo.crumbs_schema([("Meteorec", "/"), ("Vreme za padalce", "/vreme-za-padalce/"),
                           ("Termika", None)]),
    ])
    head = schema + f'\n<link rel="stylesheet" href="{asset_href("igra/igra.css")}">'

    html_out = seo.page_shell(TITLE, desc, URL, head, build_body(level, svez),
                              og_image=og_slika)
    seo.write_page("igra/index.html", html_out, force=True)
    print(f"  → igra/index.html + igra/nivo.json ({level['vir']}, strop {num(level['strop_m'])} m, "
          f"dvigi {num(level['termika_ms'], 1)} m/s, razmik {num(level['gostota_km'], 1)} km)")


if __name__ == "__main__":
    main()
