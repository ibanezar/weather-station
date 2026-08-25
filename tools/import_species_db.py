#!/usr/bin/env python3
"""
tools/import_species_db.py — build species_rules.yaml from the species database

Two sources, in this order:
  * data/baza_gob.xlsx        — the hand-curated Zgornja Savinjska core,
                                emitted with verified: true;
  * data/baza_gob_dodatek.csv — the compiled extension (species chosen by GBIF
                                occurrence counts for Slovenia, fields written
                                from literature), emitted with verified: false
                                and indexed only where its "Indeks" column says
                                so. A duplicate of a workbook species is dropped.

Together they build species_rules.yaml, the source of truth the model reads.
Run manually whenever either source changes — NOT in the daily CI workflow.

Everything the script *derives* (soil-temp window from the air-temp threshold,
rain thresholds, elevation band, geology affinity, temp-drop requirement,
ecological group and the fruiting lag that follows from it) is emitted with a
"# TODO: kalibriraj" marker, so calibration targets stay visible.
Directly-sourced fields (season, air temp, mycorrhiza, doubles, edibility) are not
marked.

Usage:
  python3 tools/import_species_db.py            # regenerate species_rules.yaml
  python3 tools/import_species_db.py --stdout   # print YAML, don't write
"""
import argparse
import csv
import datetime as dt
import os
import re
import sys
import unicodedata

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.path.join(ROOT, "data", "baza_gob.xlsx")
EXTRA_CSV = os.path.join(ROOT, "data", "baza_gob_dodatek.csv")
OUT = os.path.join(ROOT, "species_rules.yaml")

# Column indices in the "Baza Gob" sheet (0-based), from the workbook header.
C_NAME_SL, C_NAME_LAT, C_EDIB, C_SEASON, C_AIRTEMP = 0, 1, 2, 3, 4
C_MYCO, C_SUBSTRATE, C_SOILPH, C_DOUBLES = 5, 6, 7, 8
C_ELEV, C_FREQ, C_GEOLOGY = 12, 13, 14
C_MOIST7, C_OPTTEMP = 15, 16

# The extension CSV carries the same columns under the same headings, so one
# record builder serves both sources. Index positions must match the C_* map.
CSV_COLUMNS = [
    "Slovensko ime", "Znanstveno ime", "Užitnost", "Čas rasti", "Temp. prag (zrak)",
    "Mikorizni partner", "Tip rastišča (Prehranjevanje)", "Tip tal (pH vrednost)",
    "Nevarnost zamenjave (Dvojnice)", "Vonj in okus", "Sprememba barve mesa ob poškodbi",
    "Shranjevanje in priprava", "Višinski pas in značilna območja",
    "Pogostost v Zgornji savinjski", "Geološki mikro-teren (Zg. Savinjska)",
    "Minimalna kumulativna vlaga (7 dni, mm)", "Optimalni temperaturni pas (°C)",
    "Vpliv vetra/izsušitve", "Gobarski indeks (Izračun)",
]

SL_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6,
             "jul": 7, "avg": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12}
MONTH_LAST = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
              7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}

# Edibility categories that get a foraging index (everything else is reference /
# dangerous-double material only).
INDEXED_EDIBILITY = {"užitna", "pogojno užitna"}

# Air→soil derivation calibration (2026-07-17, per uporabnikova opomba v
# UI_Arhitektura_in_Logika: "nižji prag 6-8 °C, višji prag 18-22 °C").
# Tuned so a mid-range species (air_temp ~12-20 °C, the most common band in
# the workbook) lands with trapezoid min≈7-8 °C and max≈20-22 °C. Genuinely
# cold-fruiting (e.g. Jurček, air 8-15) or warm-fruiting (e.g. Poletni goban,
# air 18-24) species still land outside this band on one side — that's
# correct, not a bug: their real air-temp ecology differs from the "typical"
# mid-season species this note was calibrated against.
# TODO: kalibriraj — prej: offset=-2.0, shoulder=4.0
SOIL_TEMP_OFFSET_C = -1.5
SOIL_TEMP_SHOULDER_C = 3.0

# Ecological groups. The lag between the trigger rain and a fruit body differs
# by an order of days between them, and that is what the model's rain windows
# are shifted by — a litter saprotroph answers a shower within days, a
# mycorrhizal species only after a week and a half.
# TODO: kalibriraj — vrednosti so iz literature/izkušenj, ne iz meritev.
ECOLOGIES = [
    ("razkrojevalka", "Razkrojevalka stelje in travinja", (2, 8),
     "Kukmaki, tintnice, plešivke, marela. Trosnjak sledi dežju v nekaj dneh."),
    ("lesna", "Lesna razkrojevalka / parazit na lesu", (3, 10),
     "Ostrigar, panjevka, štorovka, uhljevka. Les zadržuje vlago, odziv je nekaj dni daljši."),
    ("mikorizna", "Mikorizna vrsta", (8, 16),
     "Gobani, lisičke, golobice. Trosnjak pride šele teden in pol do dva po sprožilnem dežju."),
]
DEFAULT_ECOLOGY = "mikorizna"

# Substrate keywords → ecological group. "Razkrajalka" on its own says only
# "decomposer", and where it decomposes usually sits in the tail of the cell —
# so a plain decomposer growing on stumps must read as a wood one. Only an
# explicit litter/grassland head ("Razkrajalka organskih ostankov; …") keeps a
# passing mention of wood from claiming the species.
ECOLOGY_MYCO_KEYS = ("mikoriz",)
ECOLOGY_LITTER_HEAD_KEYS = ("organsk", "stelj", "humus", "travnik", "pašnik", "gnoj")
ECOLOGY_WOOD_KEYS = ("les", "debl", "štor", "panj", "lubj", "veje", "korenin")
ECOLOGY_DECAY_KEYS = ("razkraj", "saprofit", "saprob")

# Ročne kalibracije posameznih vrst. Baza pove, kaj vrsta potrebuje, ne pa,
# kako se njene zahteve primerjajo z drugimi — indeks je delež izpolnjenih
# zahtev vrste, zato vrsta z ohlapnimi pragovi zasede vrh, še preden je v
# gozdu karkoli za nabrat. Vsak vnos tu potrebuje razlog; ne dodajaj jih, da bi
# popravil vtis, ampak kadar je primerjava med vrstami dokazljivo popačena.
CALIBRATION = {
    "auricularia_auricula_judae": {
        "rain_7d_min": 35, "rain_14d_min": 70,
        # Edina vrsta v bazi s celoletno sezono, hkrati pa z najnižjimi
        # padavinskimi pragovi in 10 °C širokim temperaturnim oknom. V
        # petletnem backtestu je bila zato najboljši dan vsakega leta prav ona,
        # s 100 %. Želatinast trosnjak na veji potrebuje res premočen les, ne
        # 20 mm v tednu — višja pragova jo vrneta med druge vrste.
        "razlog": "celoletna vrsta z najnižjimi pragovi je monopolizirala vrh",
    },
}

# Terrain definitions — three productive geological terrains of the valley,
# plus the strictly-protected zones (no foraging).
TERRAINS = [
    ("kisla", "Kislo/vulkansko pogorje (Smrekovec)",
     "Silikatna kisla tla; dobro zadržujejo vlago. Kraljestvo jurčka in žametastega gobana."),
    ("bazicna", "Karbonatni masivi (Golte, Menina, Raduha)",
     "Apnenčasta bazična tla; hitreje se sušijo. Kraljestvo marele in poletnega gobana."),
    ("vlazna", "Rečni logi in dolinske terase",
     "Stalno vlažna tla ob Savinji in Dreti. Kraljestvo smrčkov in uhljevk."),
]

# Forecast spots, each tagged with a terrain. Protected areas (Logarska
# dolina, Robanov kot, Komen) are kept for display but flagged so the model
# never ranks them as a picking spot.
#
# Koordinate spodnjih vrstic (razen prvih 7 in treh zavarovanih) izvorno
# temeljijo na Filipovem 27. 8. 2026 prečiščenem krogu (49 mikro-območij po
# 4 poteh). 29. 8. 2026 je Filip poslal pravi geološki vir —
# zgornja_savinjska_geo_glivna_mreza_96_OGK100_2_0.csv, 96 točk iz OGK100
# (Osnovna geološka karta 1:100.000), ZGS gozdnogospodarskih načrtov in
# enega lokalitetnega članka — ki je terrain popravil pri 29 vrsticah in
# dodal 37 novih. Elevacija ostaja sredina/ocena iz prejšnjega kroga, kjer
# CSV ni dal natančnejše.
#
# terrain je lahko tudi None (namesto niza) — POMEMBNO, ne "nevtralna" vrsta
# terena, ampak DEJANSKO MANJKAJOČ podatek: CSV razkrije, da je velik del
# doline (~40 % od 96 točk) geološka STIČNA/MOZAIČNA cona (oznake z ↔, →, +,
# npr. "TUF↔VOL") ali lapor/glinovec/meljevec (koda MAR) — nobenega od teh
# baza vrst (145 terensko preverjenih vrst) NE navaja kot prednost nobene
# vrste, zato bi prisilna uvrstitev v kisla/bazicna/vlazna vsaki vrsti s
# to ali drugo afiniteto dala napačno kazen. gobe_model.eval_species() že
# ima za to pravilo ("elif affinity == 'nevtralna' or not terrain: pass") —
# terrain=None torej pomeni "ne kaznuj tu nikogar", ne napako. build_yaml()
# spodaj zato izpusti "terrain:" vrstico, kadar je terrain None/prazen —
# GLEJ TUDI generate_gobe_page.py, kjer mora vsako `terrain`-branje ostati
# null-varno (`loc.get("terrain") or ""`, ne `loc.get("terrain", "")`).
LOCATIONS = [
    # (name, lat, lon, elev_m, terrain, home, protected, picking_restriction)
    # picking_restriction (samo pri protected=true): "unknown" | "prohibited" —
    # glej pravilo tik pod tabelo.
    ("Rečica ob Savinji",         46.326, 14.921, 400,  "vlazna",  True,  False, None),
    ("Gozdovi nad Ljubnim",       46.348, 14.834, 700,  "kisla",   False, False, None),
    # Predstavlja nižja pobočja pogorja, NE grebena Smrekovec–Komen (glej
    # opombo pri "Komen" spodaj) — Filip: "za gobarjenje bi izbiral nižja
    # gozdnata pobočja zunaj občutljivega grebenskega območja".
    ("Smrekovško pogorje",        46.430, 14.860, 1300, "kisla",   False, False, None),
    ("Golte",                     46.348, 14.840, 1300, "bazicna", False, False, None),
    ("Dobrovlje – Čreta",         46.300, 14.860, 900,  "bazicna", False, False, None),
    ("Menina planina",            46.262, 14.819, 1453, "bazicna", False, False, None),
    ("Dleskovška planota",        46.357, 14.698, 1500, "bazicna", False, False, None),

    # ── Zavarovana območja (prikaz, nikoli predlog za nabiranje) ────────────
    ("Logarska dolina",           46.392, 14.628, 750,  "vlazna",  False, True,  "unknown"),
    ("Robanov kot",               46.397, 14.710, 700,  "vlazna",  False, True,  "unknown"),
    # Greben Smrekovec–Komen je po Filipovi navedbi zavarovan kot geološko-
    # botanični rezervat — prej pomotoma vodeno kot navadno nabiralno točko.
    ("Komen (Smrekovec)",         46.415, 14.845, 1600, "kisla",   False, True,  "unknown"),

    # ── 1) Mozirje – Radegunda – Golte, ~450–1200 m ─────────────────────────
    # Pozor (Filip): blizu je gozdni rezervat Mozirska požganija — spodnje
    # koordinate niso dovoljenje za nabiranje, pred odmikom globlje v gozd
    # preveri plast "Gozdni rezervati" v ZGS Pregledovalniku.
    # OGK100: andezitni tuf (TUF) → kisla.
    ("Radegunda spodaj",                    46.35854, 14.93136, 495,  "kisla",   False, False, None),
    # OGK100: TUF↔LIM/DOL, stik dveh podlag — brez terena (glej opombo zgoraj).
    ("Žekovec",                             46.35509, 14.93338, 525,  None,      False, False, None),
    ("Radegunda višje",                     46.36608, 14.93296, 700,  "bazicna", False, False, None),
    ("Radegunda → Golte, spodnji pas",      46.365,   14.925,   750,  None,      False, False, None),
    ("Počivavnik–Korte",                    46.370,   14.920,   900,  "bazicna", False, False, None),
    ("Golte, vzhodni gozdni pas",           46.370,   14.913,   1100, "bazicna", False, False, None),
    # Filip je to prej označil kot "samo orientacija" (koča je pri 1405 m),
    # zdaj pa jo je vključil z opombo "gozd precej nižje" — elevacija tu je
    # zato precej pod višino same koče.
    ("Mozirska koča – gozd precej nižje",   46.37139, 14.90470, 1100, "bazicna", False, False, None),
    # OGK100: TUF → kisla.
    ("Pahtin",                              46.330,   14.944,   600,  "kisla",   False, False, None),
    # OGK100: lapor/glinovec/meljevec (MAR) — baza vrst tega substrata ne
    # pozna kot prednost nobene vrste, zato brez terena (ne "bazicna").
    ("Mali lazi",                           46.313,   14.931,   575,  None,      False, False, None),
    ("Veliki lazi / Kokarca",               46.304,   14.927,   600,  None,      False, False, None),
    ("Spodnja Kokarca",                     46.293,   14.922,   550,  None,      False, False, None),
    ("Pusto Polje – rob gričevja",          46.29266, 14.91849, 430,  None,      False, False, None),
    ("Prihova – gozdni rob",                46.3238,  14.94388, 485,  None,      False, False, None),
    ("Kokarje – severni gozdni rob",        46.30272, 14.93893, 525,  "kisla",   False, False, None),

    # ── Nazarje/Rečica – obrečni pas Savinje in Drete, ~340–360 m ───────────
    # OGK100: ALL (rečni prod/pesek/melj) — sodi v "vlazna" (rečni logi in
    # dolinske terase), enako kot obstoječa Rečica ob Savinji.
    ("Nazarje – sotočje Drete in Savinje",  46.3188,  14.9489,  340,  "vlazna",  False, False, None),
    ("Spodnje Pobrežje – ob Savinji",       46.329,   14.927,   350,  "vlazna",  False, False, None),
    ("Trnovec / Nizka – obrečni pas",       46.334,   14.912,   360,  "vlazna",  False, False, None),

    # ── Dobrovlje–Čreta, dodatek ─────────────────────────────────────────────
    ("Čreta pri Kokarjah",                  46.2891,  14.95628, 636,  None,      False, False, None),
    ("Dom na Čreti – gozdni rob",           46.27695, 14.95924, 876,  "bazicna", False, False, None),
    ("Čreta – keratofirni pas",             46.28333, 14.96667, 900,  "kisla",   False, False, None),

    # ── Gornji Grad – Menina – Črnivec, ~430–1400 m (nova podregija) ────────
    # OGK100 pokriva tudi občino Gornji Grad, doslej v LOCATIONS ne pokrito.
    ("Bočna – dolinski rob",                46.28889, 14.85389, 440,  "vlazna",  False, False, None),
    ("Bočna – spodnji gozd proti Menini",   46.28,    14.844,   650,  "bazicna", False, False, None),
    ("Bočka trata – orientacijski gozdni pas", 46.27, 14.839,   900,  "bazicna", False, False, None),
    ("Rovt pod Menino",                     46.296,   14.895,   600,  None,      False, False, None),
    ("Črnivec – severna stran prelaza",     46.26059, 14.70212, 902,  "kisla",   False, False, None),
    ("Kašni vrh – gozd pod vrhom",          46.29697, 14.71769, 1175, "kisla",   False, False, None),
    ("Lepenatka – gozd pod vrhom",          46.30991, 14.74055, 1290, "kisla",   False, False, None),
    ("Menina – severni srednji pas",        46.278,   14.828,   1025, None,      False, False, None),
    ("Menina – visoki gozd pod domom",      46.265,   14.821,   1325, "bazicna", False, False, None),
    ("Biba planina – spodnji gozd",         46.245,   14.845,   1225, None,      False, False, None),
    ("Dreta pri Gornjem Gradu",             46.295,   14.806,   430,  "vlazna",  False, False, None),
    ("Hom / severno gričevje",              46.317,   14.855,   575,  "kisla",   False, False, None),

    # ── 2) Ljubno – Rastke – Primož – Smrekovec, ~550–1330 m ────────────────
    # Brezovci/Kramarica/Mrzle vode/Kugovnik/Ramšak/Kolarica/Vrtačnikov potok/
    # Bistra/Črni vrh so dodane 27. 8. 2026 (isti dan, sledeč krog) — Filip
    # jih je našel na severnih/vzhodnih pobočjih Smrekovca/Komna/Krnesa, z
    # nadm. višinami, preverjenimi na hribi.net. Ramšak, Kolarica in Črni vrh
    # ležijo tik ob grebenu Smrekovec–Komen (glej "Komen (Smrekovec)" zgoraj)
    # — Filip: pred nabiranjem preveri mejo rezervata v ZGS Pregledovalniku.
    ("Brezovci – severno pobočje Smrekovca", 46.42976, 14.89060, 1130, "kisla", False, False, None),
    ("Kramarica – vzhodno pobočje Smrekovca", 46.42600, 14.90350, 1140, "kisla", False, False, None),
    ("Mrzle vode – severna stran Komna",    46.41582, 14.83113, 1226, "kisla", False, False, None),
    ("Kugovnik",                            46.41274, 14.87742, 1233, "kisla", False, False, None),
    ("Ramšak pod Krnesom",                  46.416,   14.869,   1300, "kisla", False, False, None),
    ("Kolarica – gozdni pas proti Komnu",   46.41100, 14.81190, 1328, "kisla", False, False, None),
    # OGK100: COL/VOL (koluvij nad andezitom), reakcija "spremenljivo" —
    # brez terena.
    ("Vrtačnikov potok / Pudgarsko",        46.438,   14.865,   1150, None,      False, False, None),
    ("Bistra – pod Petelinjekom",           46.44440, 14.80720, 1100, "kisla", False, False, None),
    # Filip: "gozd nižje od vrha" — koordinata je bližina vrha.
    ("Črni vrh pri Smrekovcu – gozd nižje", 46.40946, 14.89846, 1150, "kisla", False, False, None),
    ("Ljubenske Rastke",                    46.38529, 14.84697, 554,  "kisla", False, False, None),
    ("Rastočnik",                           46.388,   14.850,   675,  "kisla", False, False, None),
    ("Retkovo",                             46.392,   14.857,   800,  "kisla", False, False, None),
    # OGK100: TUF↔VOL, stik tufa in strjenega vulkanita — brez terena.
    ("Kumprej",                             46.39930, 14.87290, 782,  None,      False, False, None),
    ("Atelšek",                             46.39915, 14.88119, 950,  None,      False, False, None),
    ("Vrnivšek",                            46.40520, 14.88160, 875,  None,      False, False, None),
    # Filip: "cilja nižji gozdovi" — koordinata je sedlo (1317 m), zato je
    # elevacija tu namenoma nižja. OGK100 tu (VOL, kislo) je čisti kisli
    # vulkanit, ne stik — ostane "kisla".
    ("Atelsko sedlo",                       46.40329, 14.89713, 1150, "kisla", False, False, None),
    ("Kozlova planina – gozd spodaj",       46.399,   14.850,   1025, "kisla", False, False, None),
    ("Tračka planina – gozdni rob",         46.41432, 14.82479, 1200, "kisla", False, False, None),
    ("Počka / Robnikova planina",           46.40421, 14.81777, 1100, "kisla", False, False, None),
    ("Travnik – P1",                        46.411113,14.812025,1200, "kisla", False, False, None),
    # OGK100: TUF↔VOL — brez terena.
    ("Travnik – P2",                        46.418383,14.817943,1300, None,      False, False, None),
    ("Bukovnik (Primož)",                   46.360,   14.811,   750,  "kisla", False, False, None),
    ("Lenko–Frgelj",                        46.376,   14.821,   850,  "kisla", False, False, None),
    # Filip: "ne uporabljaj vršnega grebena kot nabiralnega območja" — greben
    # Smrekovec–Komen je zavarovan (glej "Komen (Smrekovec)" zgoraj); ta
    # točka predstavlja južni gozd POD grebenom. OGK100: TUF↔VOL — brez terena.
    ("Pod Smrekovcem, južni gozd",          46.410,   14.889,   1225, None,      False, False, None),

    # ── 3) Luče – Krnica – Podvolovljek – Podveža, ~600–1500 m ──────────────
    # Pozor (Filip): Dleskovška planota ima rezervatna območja — pri višjih
    # točkah tega bloka (Planina Ravne, pod Podvežakom, Gozdarska koča,
    # Plahojca–Šibje) preveri ZGS sloje, preden greš izven gospodarskega
    # gozda; ti štirje so tudi bolj rezerva za vroče/suho obdobje.
    # OGK100: ALL (rečni nanos Savinje/Lučnice pri Lučah) → vlazna.
    ("Luče (nad dolino)",                   46.356413,14.743139,600,  "vlazna",  False, False, None),
    # OGK100: DOL (dolomit), reakcija "spremenljivo" — brez terena.
    ("Zgornji Jerovčnik",                   46.34953, 14.74480, 650,  None,      False, False, None),
    # OGK100: TUF, reakcija "spremenljivo" (ne izrazito kislo) — brez terena.
    ("Podvolovljek – Mlinar",               46.302045,14.693477,650,  None,      False, False, None),
    ("Krnica – Metulj",                     46.340,   14.740,   650,  None,      False, False, None),
    ("Mlakar–Majk",                         46.335,   14.735,   675,  None,      False, False, None),
    ("Škomen",                              46.339,   14.747,   675,  None,      False, False, None),
    ("Kogel",                               46.321,   14.756,   850,  "bazicna", False, False, None),
    ("Riher",                               46.328,   14.722,   800,  None,      False, False, None),
    ("Vavdnovo",                            46.354,   14.720,   850,  "bazicna", False, False, None),
    ("Navršnik–Pečovsko",                   46.361,   14.728,   900,  "bazicna", False, False, None),
    ("Podveža – srednji pas",               46.343,   14.717,   825,  "bazicna", False, False, None),
    ("Planina Ravne – gozd pod planino",    46.35006, 14.69912, 1350, "bazicna", False, False, None),
    ("Pod planino Podvežak",                46.3320,  14.6721,  1350, "bazicna", False, False, None),
    ("Gozdarska koča – širši blok",         46.324,   14.681,   1350, "bazicna", False, False, None),
    ("Plahojca–Šibje",                      46.307,   14.656,   1050, "bazicna", False, False, None),

    # ── Lučka Bela / Dleskovška planota, dodatek ────────────────────────────
    # OGK100: MOR→LIM/DOL / MOR↔LIM/DOL (morenski nanos nad karbonatom) —
    # brez terena, morena zakrije pravo podlago.
    ("Lučka Bela – spodnja dolina",         46.315,   14.676,   800,  None,      False, False, None),
    ("Lučka Bela – zgornji morenski rob",   46.302,   14.648,   1025, None,      False, False, None),
    ("Ravne–Dleskovec kontaktni rob",       46.345,   14.685,   1325, None,      False, False, None),

    # ── 4) Raduha – Solčava – Podolševa, ~640–1350 m ────────────────────────
    # OGK100: WER (werfenske plasti), reakcija "nevtralno–bazično" — ne
    # čisto bazično, zato brez terena (razen kjer je posebej označeno).
    ("Zavratnik–Tratnik",                   46.383,   14.740,   875,  None,      False, False, None),
    # Filip: "gozd nižje" — koordinata je visoka referenčna točka (~1420 m).
    ("Pod Loko / južna Raduha",             46.4035,  14.7575,  1250, "bazicna", False, False, None),
    ("Sedelce",                             46.390,   14.759,   1000, None,      False, False, None),
    ("Vodole",                              46.397,   14.773,   1050, None,      False, False, None),
    ("Dešman–Smrečnik",                     46.375,   14.775,   925,  None,      False, False, None),
    # Filip: "gozd pod vrhom" — koordinata je vrh Rožni vrh (1478 m). OGK100:
    # MAR/LIM↔LIM/DOL, stik — brez terena.
    ("Rožni vrh – gozd pod vrhom",          46.4014136,14.6691938,1300,None,      False, False, None),
    ("Huda goša / spodnji Rožni vrh",       46.399,   14.681,   1125, None,      False, False, None),
    ("Tolstovršnik",                        46.41379, 14.70864, 900,  None,      False, False, None),
    # OGK100: SIL (paleozojski silikatni klastiti), reakcija "kislo" → kisla
    # (prej bazicna po napačni oceni).
    ("Podolševa – Sv. Duh",                 46.435528,14.659476,1200, "kisla",   False, False, None),
    ("Podolševa – vzhodni gozd",            46.431,   14.674,   1125, None,      False, False, None),
    ("Podolševa – zahodni gozd",            46.434,   14.646,   1175, "kisla",   False, False, None),
    # Filip: "gozd pod domačijo" — koordinata je pri domačiji (1327 m). OGK100:
    # MAR/LIM, reakcija "nevtralno–bazično" — brez terena.
    ("Bukovnik (Grohat)",                   46.43400, 14.73710, 1200, None,      False, False, None),
    ("Grohat – spodnji gozd",               46.417,   14.735,   1250, None,      False, False, None),
    ("Grohat – vulkanski kontakt",          46.4215,  14.7405,  1375, None,      False, False, None),
    ("Lipni plaz – vulkanski kontakt",      46.415,   14.728,   1300, None,      False, False, None),
    ("Solčava – ob Savinji",                46.419,   14.693,   640,  "vlazna",  False, False, None),

    # ── Matkov kot — nov, doslej nepokrit stranski dolinski krak ────────────
    # Previdnostno zaščiteno, enako kot Logarska dolina/Robanov kot — v PR
    # #770 je Matkov kot že bil naveden skupaj z njima za enako nevtralno
    # pravno formulacijo (glej opombo pri picking_restriction spodaj).
    ("Odcep Matkov kot",                    46.41967, 14.6275,  800,  None,      False, True,  "unknown"),
    ("Matkov kot – notranji dolinski rob",  46.425,   14.61,    925,  None,      False, True,  "unknown"),

    # ── Notranjost Logarske doline / Robanovega kota — previdnostno
    #    zaščiteno, enako kot obstoječi vrhnji vnos za vsako dolino ─────────
    ("Začetek Logarske doline",             46.41,    14.63711, 730,  "vlazna",  False, True,  "unknown"),
    ("Srednja Logarska dolina",             46.3995,  14.6305,  800,  "vlazna",  False, True,  "unknown"),
    ("Začetek Robanovega kota",             46.39409, 14.69556, 675,  None,      False, True,  "unknown"),
    ("Srednji Robanov kot",                 46.3951,  14.71215, 775,  None,      False, True,  "unknown"),
]
# picking_restriction (samo pri protected=true): "unknown" | "prohibited". UI sme
# pisati "nabiranje prepovedano" SAMO pri "prohibited" IN obstoječem restriction_source
# (preverjen pravni vir za TO območje) — sicer nevtralno "preveri omejitve". Trenutno za
# nobeno območje ni preverjenega vira za splošno prepoved gobarjenja, zato so vsa
# zavarovana območja na "unknown". Ne spreminjaj v "prohibited" brez konkretnega vira.
# TODO: kalibriraj — koordinate poti so od Filipa (27. 8. 2026 mikro-lokacije,
# 29. 8. 2026 geološki popravek/dodatek iz OGK100), a še vedno ne pomenijo
# GPS-izmerjene meje parcele.
# Filipovih 12 najljubših za "prvi resen scan" (razpon ~650–1250 m, veliko
# ekspozicij): Radegunda višje, Počivavnik–Korte, Retkovo, Kumprej, Atelšek,
# Vrnivšek, Pod Smrekovcem (južni gozd), Mlakar–Majk, Riher, Navršnik–
# Pečovsko, Vodole, Huda goša / spodnji Rožni vrh.


# ── parsing helpers ──────────────────────────────────────────────────────────

def slugify(name_lat):
    s = unicodedata.normalize("NFKD", name_lat).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s or "vrsta"


def parse_season(text):
    """'Sep – Nov' → ('09.01', '11.30'); 'Celotno leto' → whole year."""
    t = (text or "").strip().lower()
    if "celotno" in t or "vse leto" in t:
        return "01.01", "12.31"
    months = [SL_MONTHS[m] for m in re.findall(r"[a-zčšž]+", t) if m in SL_MONTHS]
    if len(months) >= 2:
        a, b = months[0], months[-1]
    elif len(months) == 1:
        a = b = months[0]
    else:
        return None, None
    return f"{a:02d}.01", f"{b:02d}.{MONTH_LAST[b]:02d}"


def parse_temp_range(text):
    """'8 – 15 °C' / '-2 do 8 °C' → (min, max)."""
    nums = [int(n) for n in re.findall(r"-?\d+", text or "")]
    if len(nums) >= 2:
        return min(nums[0], nums[1]), max(nums[0], nums[1])
    if len(nums) == 1:
        return nums[0], nums[0]
    return None, None


def parse_moisture(text):
    """'25-35' → low end 25 (mm, 7-day cumulative trigger)."""
    nums = [int(n) for n in re.findall(r"\d+", text or "")]
    return nums[0] if nums else 20


def derive_soil_temp(air_lo, air_hi, offset, shoulder):
    """Soil-temp trapezoid derived from the air-temp favourable band.
    Soil at 6-18 cm is cooler and more damped than air; offset/shoulder are
    calibration knobs. Clamped to a non-negative, monotonic trapezoid."""
    opt_low = air_lo + offset
    opt_high = air_hi + offset
    tmin = opt_low - shoulder
    tmax = opt_high + shoulder
    vals = [max(0.0, v) for v in (tmin, opt_low, opt_high, tmax)]
    # enforce min <= opt_low <= opt_high <= max after clamping
    for i in range(1, 4):
        vals[i] = max(vals[i], vals[i - 1])
    return [round(v, 1) for v in vals]


def derive_elevation(text):
    """Rough elevation band (m) from the free-text zone description."""
    t = (text or "").lower()
    if "vse viš" in t or "od ravnin" in t or "povsod" in t:
        return 300, 1600
    if any(k in t for k in ("gorsk", "alpsk", "višj", "hribovit", "predalpsk")):
        return 600, 1600
    if any(k in t for k in ("nižin", "ravnin", "dolin", "nižje", "log")):
        return 250, 900
    return 300, 1400


def derive_geology(geology, soil_ph):
    """Categorical terrain affinity from geology + soil-pH keywords."""
    t = f"{geology or ''} {soil_ph or ''}".lower()
    scores = {
        "kisla":   sum(k in t for k in ("kisl", "silikat", "vulkan", "igličev", "borovnic")),
        "bazicna": sum(k in t for k in ("apnen", "bazičn", "karbonat", "dolomit")),
        "vlazna":  sum(k in t for k in ("vlažn", "mokrot", "šotn", "barjansk", "ob rek", "log", "obrežj")),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "nevtralna"


def derive_frequency_factor(text):
    """Local-presence prior from the 'Pogostost v Zg. Savinjski' text. Keeps a
    weather-favourable but locally absent/rare species from topping the list.
    Calibration values — flagged TODO in the YAML."""
    t = (text or "").lower()
    if any(k in t for k in ("odsot", "praktično odsot", "povsem odsot")):
        return 0.2
    if "redk" in t or "redek" in t or "redka" in t:
        return 0.4
    if "manj pogost" in t:
        return 0.7
    if any(k in t for k in ("izjemno pogost", "zelo pogost", "množično", "obilno", "neizogibn")):
        return 1.0
    if "pogost" in t or "prisot" in t or "najdem" in t:
        return 0.9
    return 0.8


def derive_ecology(substrate, mycorrhiza):
    """Ecological group from the substrate description.

    The leading clause of the substrate cell carries the trophic mode
    ("Mikoriza; v tleh …", "Razkrajalka organskih ostankov; … ali lesu"); the
    substrate it lives on can sit anywhere in the cell. The mycorrhiza column
    settles what the text leaves open; it marks saprotrophs as "(saprofit)"."""
    t = (substrate or "").lower()
    head = t.split(";", 1)[0]
    if any(k in head for k in ECOLOGY_MYCO_KEYS):
        return "mikorizna"
    if any(k in head for k in ECOLOGY_LITTER_HEAD_KEYS):
        return "razkrojevalka"
    if any(k in t for k in ECOLOGY_WOOD_KEYS):
        return "lesna"
    if any(k in t for k in ECOLOGY_DECAY_KEYS):
        return "razkrojevalka"
    m = (mycorrhiza or "").lower()
    if any(k in m for k in ECOLOGY_DECAY_KEYS + ("parazit",)):
        return "razkrojevalka"
    return "mikorizna" if m.strip() else DEFAULT_ECOLOGY


ECOLOGY_LAGS = {gid: lag for gid, _name, lag, _note in ECOLOGIES}


def ecology_lag(group):
    """Fruiting lag (days) of the group — the seed for the species' own value."""
    return ECOLOGY_LAGS.get(group) or ECOLOGY_LAGS[DEFAULT_ECOLOGY]


def derive_requires_temp_drop(season_start):
    """Late-season species (fruiting from August onward) treat night cooling
    as a trigger; earlier species do not. Heuristic — flagged for calibration."""
    try:
        return int(season_start.split(".")[0]) >= 8
    except (AttributeError, ValueError):
        return False


def split_list(text):
    """'Smreka, bukev, bor, hrast' → ['smreka','bukev','bor','hrast']."""
    if not text:
        return []
    return [p.strip().lower() for p in re.split(r"[,;/]| in ", text) if p.strip()]


# ── YAML emitter (hand-rendered to keep inline TODO comments) ─────────────────

def q(s):
    """Double-quoted YAML scalar with escaping."""
    s = "" if s is None else str(s).replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\n", " ").strip()
    return f'"{s}"'


def yaml_list(items):
    return "[" + ", ".join(q(i) for i in items) + "]"


def build_yaml(species):
    L = []
    L.append("# species_rules.yaml — pravila gobarskega modela po vrstah")
    L.append("#")
    L.append("# AVTOMATSKO GENERIRANO iz data/baza_gob.xlsx prek")
    L.append("# tools/import_species_db.py. To datoteko lahko ročno urejaš in kalibriraš —")
    L.append("# regeneracija jo prepiše, zato spremembe pomeni prenesti tudi v bazo ali skript.")
    L.append("#")
    L.append("# Izpeljane vrednosti (talno-temp. okno, padavinski pragovi, višina, geološka")
    L.append("# afiniteta, nočna ohladitev, ekološka skupina in rastni zamik) so označene")
    L.append("# '# TODO: kalibriraj'. Neposredno iz baze (sezona, zračni prag, mikoriza,")
    L.append("# dvojnice, užitnost) niso.")
    L.append(f"# Zadnja regeneracija: {dt.date.today().isoformat()} · {len(species)} vrst.")
    L.append("")

    # Global weights
    L.append("# Globalne uteži za izračun indeksa (0–100)")
    L.append("weights:")
    L.append("  temperature: 0.35      # ujemanje temperature z optimalnim oknom vrste")
    L.append("                         # (talna pri mikoriznih in razkrojevalkah, zračna pri lesnih)")
    L.append("  rain_trigger: 0.25     # sprožilni dež v zamiku vrste (fruiting_lag_days)")
    L.append("  rain_base: 0.15        # zaloga vode v tleh 14 dni pred zamikom")
    L.append("  soil_moisture: 0.10")
    L.append("  humidity: 0.08")
    L.append("  temp_drop: 0.07        # nočna ohladitev kot sprožilec")
    L.append("")

    # Scoring knobs
    L.append("# Globalni kalibracijski parametri točkovanja (veljajo za vse vrste).")
    L.append("scoring:")
    L.append("  rain:")
    L.append("    oversat_ratio: 3.0       # TODO: kalibriraj — večkratnik praga, kjer se začne prenamočenost")
    L.append("    oversat_max_ratio: 6.0   # TODO: kalibriraj — večkratnik praga, kjer je upad največji")
    L.append("    oversat_factor: 0.5      # TODO: kalibriraj — minimalni prispevek ob ekstremni namočenosti")
    L.append("  soil_moisture:")
    L.append("    dry: 0.12                # TODO: kalibriraj — pod tem prispevek 0")
    L.append("    full: 0.28               # TODO: kalibriraj — nad tem polni prispevek")
    L.append("  humidity:")
    L.append("    rh_low: 60               # TODO: kalibriraj")
    L.append("    rh_full: 85              # TODO: kalibriraj")
    L.append("    dewpoint_spread_full: 2.0  # TODO: kalibriraj")
    L.append("  temp_drop:")
    L.append("    window_days: 5           # TODO: kalibriraj")
    L.append("    min_drop_c: 3.0          # TODO: kalibriraj")
    L.append("    persist_days: 4          # TODO: kalibriraj")
    L.append("  # Pri lesnih vrstah odloča zračna temperatura (rastejo na lesu nad tlemi),")
    L.append("  # zato njihov trapez nastane iz air_temp s temi rameni.")
    L.append("  temperature:")
    L.append("    air_shoulder_c: 3.0      # TODO: kalibriraj — širina ramen pri zračni temp.")
    L.append("  elevation:")
    L.append("    out_of_range_factor: 0.7  # TODO: kalibriraj")
    L.append("  # Izpeljava talno-temp. okna iz zračnega praga (soil hladnejši/dušen od zraka).")
    L.append("  soil_temp_from_air:")
    L.append(f"    offset_c: {SOIL_TEMP_OFFSET_C}           # TODO: kalibriraj — zamik zrak→tla")
    L.append(f"    shoulder_c: {SOIL_TEMP_SHOULDER_C}          # TODO: kalibriraj — širina ramen trapeza")
    L.append("  # Ujemanje geološke afinitete vrste s terenom lokacije.")
    L.append("  geology:")
    L.append("    match_factor: 1.15       # TODO: kalibriraj — afiniteta se ujema s terenom")
    L.append("    mismatch_factor: 0.75    # TODO: kalibriraj — afiniteta se NE ujema")
    L.append("    neutral_factor: 1.0      # vrsta brez izrazite geološke preference")
    L.append("")

    # Ecological groups
    L.append("# Ekološke skupine. fruiting_lag_days je zamik med sprožilnim dežjem in")
    L.append("# trosnjakom; model za ta zamik premakne obe padavinski okni, tako da ista")
    L.append("# ploha pri razkrojevalki in pri mikorizni vrsti ne šteje isti dan.")
    L.append("# Vrednost tu je izhodišče, iz katerega import_species_db.py napolni")
    L.append("# fruiting_lag_days pri vrsti — model bere vrednost PRI VRSTI, zato jo lahko")
    L.append("# za posamezno vrsto ročno prepišeš, ne da bi premaknil celo skupino.")
    L.append("ecologies:")
    for eid, name, lag, note in ECOLOGIES:
        L.append(f"  - id: {eid}")
        L.append(f"    name_sl: {q(name)}")
        L.append(f"    fruiting_lag_days: {{ min: {lag[0]}, max: {lag[1]} }}  # TODO: kalibriraj")
        L.append(f"    note: {q(note)}")
    L.append("")

    # Terrains
    L.append("# Geološki tereni doline (za geo-afiniteto v izračunu po lokaciji).")
    L.append("terrains:")
    for tid, name, note in TERRAINS:
        L.append(f"  - id: {tid}")
        L.append(f"    name_sl: {q(name)}")
        L.append(f"    note: {q(note)}")
    L.append("")

    # Locations
    L.append("# Napovedne točke. protected=true → zaščiteno območje, ne prikazuj kot nabiralno mesto.")
    L.append("# picking_restriction (samo pri protected=true): \"unknown\" | \"prohibited\". UI sme")
    L.append("# pisati \"nabiranje prepovedano\" SAMO pri \"prohibited\" IN obstoječem restriction_source")
    L.append("# (preverjen pravni vir za TO območje) — sicer nevtralno \"preveri omejitve\". Trenutno za")
    L.append("# nobeno območje ni preverjenega vira za splošno prepoved gobarjenja, zato so vsa")
    L.append("# zavarovana območja na \"unknown\". Ne spreminjaj v \"prohibited\" brez konkretnega vira.")
    L.append("locations:")
    for name, lat, lon, elev, terr, home, prot, restriction in LOCATIONS:
        L.append(f"  - name: {q(name)}")
        L.append(f"    lat: {lat}")
        L.append(f"    lon: {lon}")
        L.append(f"    elev_m: {elev}")
        if terr:
            L.append(f"    terrain: {terr}")
        L.append(f"    home: {'true' if home else 'false'}")
        L.append(f"    protected: {'true' if prot else 'false'}")
        if prot and restriction:
            L.append(f"    picking_restriction: {restriction}")
    L.append("")

    # Species
    L.append("# Vrste. gets_index=true dobijo gobarski indeks; ostale so referenca / dvojnice.")
    L.append("species:")
    for s in species:
        L.append(f"  - id: {s['id']}")
        L.append(f"    name_sl: {q(s['name_sl'])}")
        L.append(f"    name_lat: {q(s['name_lat'])}")
        L.append(f"    edibility: {q(s['edibility'])}")
        L.append(f"    gets_index: {'true' if s['gets_index'] else 'false'}")
        L.append(f"    verified: {'true' if s['verified'] else 'false'}"
                 f"{'' if s['verified'] else '   # iz dodatka, ni terensko preverjeno'}")
        L.append(f"    frequency: {q(s['frequency'])}")
        L.append(f"    frequency_factor: {s['frequency_factor']}   # TODO: kalibriraj (lokalna prisotnost)")
        st = s["season"]
        L.append(f'    season: {{ start: "{st[0]}", end: "{st[1]}" }}')
        at = s["air_temp"]
        L.append(f"    air_temp: {{ min: {at[0]}, max: {at[1]} }}  # zračni prag iz baze")
        so = s["soil_temp"]
        L.append(f"    soil_temp: {{ min: {so[0]}, opt_low: {so[1]}, opt_high: {so[2]}, max: {so[3]} }}  # TODO: kalibriraj (izpeljano iz air_temp)")
        cal_note = f"  # ROČNO UMERJENO: {s['calibrated']}" if s.get("calibrated") else ""
        L.append(f"    rain_7d_min: {s['rain_7d_min']}        # TODO: kalibriraj (baza: vlaga 7d; prag kot 7-dnevna kumulativa){cal_note}")
        L.append(f"    rain_14d_min: {s['rain_14d_min']}       # TODO: kalibriraj (prag kot 14-dnevna kumulativa)")
        L.append(f"    ecology: {s['ecology']}   # TODO: kalibriraj (izpeljano iz substrata)")
        fl = s["fruiting_lag_days"]
        L.append(f"    fruiting_lag_days: {{ min: {fl[0]}, max: {fl[1]} }}  # TODO: kalibriraj (iz skupine {s['ecology']})")
        L.append(f"    mycorrhiza: {yaml_list(s['mycorrhiza'])}")
        L.append(f"    substrate: {q(s['substrate'])}")
        L.append(f"    soil_ph: {q(s['soil_ph'])}")
        L.append(f"    geology_affinity: {s['geology_affinity']}   # TODO: kalibriraj")
        L.append(f"    elevation_zone: {q(s['elevation_zone'])}")
        ep = s["elevation_pref_m"]
        L.append(f"    elevation_pref_m: {{ min: {ep[0]}, max: {ep[1]} }}  # TODO: kalibriraj")
        L.append(f"    requires_temp_drop: {'true' if s['requires_temp_drop'] else 'false'}   # TODO: kalibriraj")
        L.append(f"    doubles: {q(s['doubles'])}")
    L.append("")
    return "\n".join(L)


# ── main ─────────────────────────────────────────────────────────────────────

def build_record(r, verified, index_flag=None):
    """One species record from a row of cells, indexed by the C_* constants.
    `index_flag` overrides the edibility rule for gets_index (the extension CSV
    decides per species; the workbook lets edibility decide)."""
    edib = (r[C_EDIB] or "").strip()
    season = parse_season(r[C_SEASON])
    air_lo, air_hi = parse_temp_range(r[C_AIRTEMP])
    if air_lo is None:
        air_lo, air_hi = 10, 18  # fallback, unlikely
    soil = derive_soil_temp(air_lo, air_hi, offset=SOIL_TEMP_OFFSET_C, shoulder=SOIL_TEMP_SHOULDER_C)
    rain7 = parse_moisture(r[C_MOIST7])
    elev_min, elev_max = derive_elevation(r[C_ELEV])
    ecology = derive_ecology(r[C_SUBSTRATE], r[C_MYCO])
    gets_index = (edib.lower() in INDEXED_EDIBILITY) if index_flag is None else bool(index_flag)
    sid = slugify(r[C_NAME_LAT])
    cal = CALIBRATION.get(sid, {})
    rec = {
        "id": sid,
        "name_sl": r[C_NAME_SL],
        "name_lat": r[C_NAME_LAT],
        "edibility": edib,
        "gets_index": gets_index,
        "verified": verified,
        "frequency": r[C_FREQ],
        "frequency_factor": derive_frequency_factor(r[C_FREQ]),
        "season": season if season[0] else ("01.01", "12.31"),
        "air_temp": (air_lo, air_hi),
        "soil_temp": soil,
        "rain_7d_min": rain7,
        "rain_14d_min": rain7 * 2,
        "ecology": ecology,
        "fruiting_lag_days": ecology_lag(ecology),
        "mycorrhiza": split_list(r[C_MYCO]),
        "substrate": r[C_SUBSTRATE],
        "soil_ph": r[C_SOILPH],
        "geology_affinity": derive_geology(r[C_GEOLOGY], r[C_SOILPH]),
        "elevation_zone": r[C_ELEV],
        "elevation_pref_m": (elev_min, elev_max),
        "requires_temp_drop": derive_requires_temp_drop(season[0]),
        "doubles": r[C_DOUBLES],
    }
    rec.update({k: v for k, v in cal.items() if k != "razlog"})
    if cal:
        rec["calibrated"] = cal["razlog"]
    return rec


def read_workbook():
    """The hand-curated core: data/baza_gob.xlsx, verified species."""
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb["Baza Gob"]
    rows = list(ws.iter_rows(values_only=True))
    return [build_record(r, verified=True)
            for r in rows[1:] if r[C_NAME_SL] and r[C_NAME_LAT]]


def read_extension():
    """The extension list: data/baza_gob_dodatek.csv.

    Kept as CSV, not merged into the workbook, because these rows are compiled
    (species picked by GBIF occurrence counts for Slovenia, fields written from
    literature) rather than checked in the field like the workbook is — a text
    file is reviewable in a diff, an .xlsx blob is not. They land in the YAML
    with verified: false, and only take a foraging index where the "Indeks"
    column says so."""
    if not os.path.exists(EXTRA_CSV):
        return []
    with open(EXTRA_CSV, encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        missing = [c for c in CSV_COLUMNS if c not in (rdr.fieldnames or [])]
        if missing:
            print(f"✗ {os.path.basename(EXTRA_CSV)}: manjkajo stolpci {missing}", file=sys.stderr)
            sys.exit(1)
        out = []
        for row in rdr:
            if not row.get(CSV_COLUMNS[C_NAME_SL]) or not row.get(CSV_COLUMNS[C_NAME_LAT]):
                continue
            cells = [row.get(name) for name in CSV_COLUMNS]
            index_flag = (row.get("Indeks") or "").strip().lower() in ("da", "1", "true")
            out.append(build_record(cells, verified=False, index_flag=index_flag))
    return out


def read_species():
    """Workbook first, extension after; a duplicate id in the extension is
    dropped, so the hand-checked row always wins."""
    core = read_workbook()
    seen = {s["id"] for s in core}
    extra = []
    for s in read_extension():
        if s["id"] in seen:
            print(f"  ⚠ podvojena vrsta v dodatku, preskočena: {s['name_lat']}", file=sys.stderr)
            continue
        seen.add(s["id"])
        extra.append(s)
    return core + extra


def main():
    ap = argparse.ArgumentParser(description="Build species_rules.yaml from data/baza_gob.xlsx")
    ap.add_argument("--stdout", action="store_true", help="print YAML, don't write file")
    args = ap.parse_args()

    if not os.path.exists(XLSX):
        print(f"✗ Baza ni najdena: {XLSX}", file=sys.stderr)
        sys.exit(1)

    species = read_species()
    indexed = sum(1 for s in species if s["gets_index"])
    yaml_text = build_yaml(species)

    if args.stdout:
        print(yaml_text)
        return
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(yaml_text)
    print(f"→ {OUT}")
    print(f"  {len(species)} vrst · {indexed} z indeksom · {len(species) - indexed} referenca/dvojnice")


if __name__ == "__main__":
    main()
