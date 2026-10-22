# Lasten WRF nad Zgornjo Savinjsko dolino (0,5 km)

Ideja po polarnivrtinec.si (WRF 0,5 km za Ljubljansko kotlino). Cilj ni stran, ampak **odgovor na vprašanje, ali lasten
model z ločljivostjo 0,5 km napove dolino bolje kot javni modeli (Open-Meteo, MTR)**. Stran nastane šele, ko to pokaže
verifikacija proti IREICA1 (glej spodaj). Do takrat je vse tu infrastruktura in meritev.

## Kaj je narejeno in preizkušeno

Cevovod je bil v peskovniku **preizkušen od začetka do konca** (22. 10. 2026, 4 jedra): GFS (pravi podatki) → ungrib → metgrid → real →
wrf z gnezdi → izvleček za Rečico, v vsebniku, zgrajenem iz `wrf/Dockerfile` (WRF se prevede v ~10 min na 4 jedrih). Preizkus je
uporabil **sintetične statične podatke** (`wrf/synthetic_geog.py`, ker WPS_GEOG ni dosegljiv — glej spodaj) in pravi Copernicus DEM za
domene ≤ 1,5 km. **Številke tega preizkusa niso napoved** in se ne smejo primerjati z meritvami; dokazuje se, da stvar teče.

| Del | Datoteka | Stanje |
|---|---|---|
| Domene in namelisti | `wrf/config.py` | `tools/test_wrf.py`; WRF jih sprejme (test profil 3 domene, prod 4 domene) |
| Robni pogoji GFS 0,25° | `wrf/fetch_gfs.py` | prenos in ungrib/metgrid/real preizkušeni na živih podatkih (~150 MB/korak) |
| Teren Copernicus 30 m | `wrf/dem_tiles.py` | geogrid ga prebere (d03: 247–1838 m, celica Rečice 405 m) |
| Omejitev naklona | `wrf/limit_slope.py` | **nujna** (glej spodaj) |
| Cevovod WPS → real → wrf | `wrf/run.sh`, `wrf/smoke.sh` | tečeta; `smoke.sh` je preizkus brez WPS_GEOG |
| Vsebnik | `wrf/Dockerfile`, `wrf-image.yml` | lokalno zgrajen; gradnja v Actions še ni zagnana |
| Izvleček za Rečico | `wrf/extract.py` | preizkušen na pravem `wrfout` in sintetičnem |
| Verifikacija | `tools/verify_wrf.py` | preizkušena; brez podatkov, dokler ni tekov |

### Kar je preizkus odkril (in je zdaj v kodi)

1. **MYNN (bl_pbl 5) se v naši sliki sesuje** (`free(): invalid pointer` takoj po začetku integracije, tudi serijsko). YSU in MYJ tečeta,
   zato je privzet YSU + MM5 (`config.py` `PBL`, `--pbl myj` za primerjavo). Vzrok ni raziskan.
2. **Strm teren sesuje d04 (0,5 km).** Copernicus 30 m, povprečen na 0,5 km, ima naklone do 45° (Kamniško-Savinjske Alpe); w je v najstrmejši celici
   zrasel na 10³ m/s v 2 sekundah (v_cfl), ne glede na časovni korak (1–2 s), `diff_opt`, `epssm`, razmik nivojev ali enakomerno glajenje
   terena. Pomagala je šele **omejitev naklona** (`wrf/limit_slope.py`: gladi samo celice nad pragom): pri 30° se je sesul po 90 s, pri **22°
   (privzeto, 9 % celic spremenjenih) je tekel 22 minut modelskega časa brez opozorila** — preizkus je bil nato prekinjen ob ponovnem zagonu
   okolja, ne zaradi napake. Prag ni umerjen; 22° pomeni, da se najstrmejša pobočja izravnajo, kar je pri 0,5 km kompromis.
3. **Časovni korak** je 4 × dx (54 s za d01, 2 s za d04), ne 6 × dx.
4. **Hitrost:** na 4 jedrih ~0,5 s računanja na sekundo modela (prod postavitev), torej 36 h ≈ 18 h; na 16 jedrih ~4–5 h, če se skalira
   dobro (ne preizkušeno). Zato je 2–3 h iz prvotne ocene **preoptimistična**; pred dnevnim tekom razmisli o manjši d04 (91 × 91 = 45 km) ali
   krajšem teku, ali o večjem strežniku.
5. WPS_GEOG je na `www2.mmm.ucar.edu` z nepopolno verigo potrdil (v peskovniku curl pade); zato sintetični podatki.

## Zasnova

- **Domene** (`python3 wrf/config.py show`): d01 13,5 km (65², 864 km) → d02 4,5 km (85², 378 km) → d03 1,5 km (91²,
  135 km) → d04 **0,5 km (121², 60 × 60 km)**; Lambertova projekcija s središčem v Rečici. Razmerje 3:1, ker ima GFS
  0,25° (28 km) preveliko razliko do 0,5 km, da bi lahko skočili neposredno; ICON-D2 (2,2 km) bi dovolil manj domen,
  a njegov Vtable ni del WPS in ga ne uporabljamo brez preizkusa.
- **Tek ob 12 UTC, 36 ur**: napoved za **jutrišnji lokalni dan** je tako 12–36 ur v teku (spin-up hladnega bazena je za
  nami). 00 UTC bi dal Tmin v 5. uri teka, ko model še ni zgradil dolinske inverzije.
- **Fizika** (`namelist_input`): Thompson (8), RRTMG, YSU (1) s pritlično plastjo MM5 (1), Noah (2), Grell–Freitas (3)
  samo na d01/d02, pobočno sevanje in senčenje terena na d03/d04, 51 nivojev z najnižjim ~25 m. To je razumna izhodiščna
  izbira za dolino, **ne umerjena**: pri 0,5 km je turbulenca v »sivi coni« in je brez preverjanja ne smemo imeti za boljšo.
- **Teren**: privzeti teren WPS (GMTED2010, 30″) doline ne razloči. `wrf/dem_tiles.py build` pretvori Copernicus GLO-30
  v ploščice WPS (`$GEOG/cop30m`), `run.sh` jih zazna in jih uporabi za domene ≤ 1,5 km. Brez tega 0,5 km ne pomeni nič.
- **Izhod** je JSON za eno celico (`data/wrf/recica-<tek>.json`: 30-minutne vrednosti in dnevni povzetek po lokalnem
  dnevu). Višina celice modela je zapisana, ker se od postaje razlikuje. Veter je trenutna vrednost, ne sunek.

## Cena in strojna oprema

Za prod postavitev je glavni strošek d04 (14,6 tisoč celic × 51 nivojev, korak 2 s). Izmerjeno: ~0,5 s računanja na sekundo modela
na 4 jedrih, torej **~4–5 h na 16 jedrih** za 36 h napovedi, če se skalira (ni preizkušeno). GitHub Actions z 4 jedri tega ne zmore v razumnem času,
zato potrebuješ strežnik. Hetznerjev CCX43 (16 dedicated vCPU) po uri je glede na objavljene cene okoli 0,2–0,3 €/h,
torej ~1–2 € na tek; prepričaj se o aktualni ceni. Statika (WPS_GEOG ~29 GB + DEM) se hrani na pomnilniškem disku (volume),
da je ni treba vsak dan snemati.

### Ročni tek (runbook)

```bash
# 1. enkrat: strežnik z Dockerjem in diskom ≥ 60 GB (npr. /data)
docker pull ghcr.io/ibanezar/weather-station-wrf:latest        # slika iz wrf-image.yml

# 2. enkrat: geografski podatki (~2,6 GB prenos, ~29 GB razpakirano) in teren
mkdir -p /data/geog && cd /data/geog
curl -fLO https://www2.mmm.ucar.edu/wrf/src/wps_files/geog_high_res_mandatory.tar.gz && tar xzf geog_high_res_mandatory.tar.gz
pip install numpy tifffile imagecodecs && python3 /work/wrf/dem_tiles.py build /data/geog/WPS_GEOG

# 3. tek (init = 12 UTC včeraj → napoved za jutrišnji dan; traja 2–3 h)
git clone https://github.com/ibanezar/weather-station /work && cd /work
docker run --rm -v /work:/work -v /data/geog:/geog -e INIT=2026102212 -e HOURS=36 -e PROFILE=prod \
  ghcr.io/ibanezar/weather-station-wrf:latest bash /work/wrf/run.sh
# → /work/out/recica-2026102212.json; kopiraj v data/wrf/ in commitaj, potem: python3 tools/verify_wrf.py
```

**Pozor:** `www2.mmm.ucar.edu` (edini vir WPS_GEOG) pošilja verigo potrdil, ki ni v vseh trust storih (v peskovniku, v
katerem je nastajal ta cevovod, curl pade s »unable to get local issuer certificate«). Če se to zgodi tudi na
strežniku, podatke prenesi drugje in jih naloži na disk; TLS preverjanja ne izklapljaj.

## Preverjanje, preden pride kaj na stran

`tools/verify_wrf.py` primerja vsak tek z IREICA1 (`history.json`) in z napovedmi Open-Meteo, **izdanimi isti dan**
(`data/forecast-archive.csv`, lead 1: best_match, ECMWF IFS, ICON, GFS), na skupnih dnevih. Rezultat:
`data/wrf-verification.json` (MAE in pristranskost Tmax/Tmin, zadetek mokrega dne, zmage WRF po spremenljivkah).
Pravila: **IREICA1 je edina referenca**; do 30 skupnih dni je rezultat »zgoden«; negativen rezultat se objavi enako.
Šele če WRF dosledno zmaga (zlasti pri Tmin ob jasnih mirnih nočeh, kjer pričakujemo korist), ima smisel stran, kartica
na naslovni ali tema za zgodbo.

## Kaj še manjka

- Samodejen dnevni tek (Hetzner prek `hcloud` ali drug najem): ni narejen, ker ga brez prvega uspešnega ročnega teka
  ni mogoče preizkusiti. Ko bo, naj ustvari strežnik, požene `run.sh`, commitne izvleček in strežnik izbriše.
- Vrednosti fizike niso umerjene; prvi meseci verifikacije so tudi umerjanje (npr. MYNN proti YSU).
- Ni ansambla ali verjetnosti, samo en determinističen tek.
- Notranjih meritev ta cevovod ne bere (model ne vidi postaje; verifikacija bere samo zunanje polje `history.json`).

## Viri in licence

NOAA GFS (javna domena, AWS Open Data), Copernicus GLO-30 DEM (prosta uporaba z navedbo: © DLR 2010–2014, © Airbus Defence
and Space 2014–2018, ESA), WPS_GEOG (NCAR/UCAR, javno), WRF in WPS (javna domena, NCAR).

## Lokalna gradnja slike v okolju s posrednikom

```bash
docker build --network host --build-context ca=/root/.ccr --build-context wpssrc=<klon wrf-model/WPS v4.6.0> \
  --build-arg BASE_IMAGE=mirror.gcr.io/library/ubuntu:20.04 --build-arg HTTPS_PROXY=$HTTPS_PROXY -t meteorec-wrf -f wrf/Dockerfile wrf/
```
