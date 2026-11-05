#!/usr/bin/env python3
"""Izvoz dnevnih podatkov (CSV), objava na Zenodo in shema Dataset (5. 11. 2026).

1. `export_dataset.build_rows`: dnevi iz reanalize (src == era5) izpuščeni, prazna polja prazna, enote v glavi, nič notranjega;
   objavljeni CSV se ujema s history.json (vsak datum obstaja in ni iz reanalize, nobenega reanaliznega dne).
2. `zenodo_publish.publish`: brez --publish se `actions/publish` NE pokliče (osnutek), z njim se, DOI se zapiše v metapodatke;
   nova različica zamenja datoteke; CSV z notranjimi besedami ustavi objavo; manjkajoč žeton ne pošlje ničesar.
3. Shema `#dataset`: en `distribution` (seznam JSON + CSV), DOI v `identifier`/`sameAs` samo, kadar obstaja; stran /podatki/
   ima »Kako citirati«, brez izmišljenega DOI.
"""
import csv
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import export_dataset as ex  # noqa: E402
import zenodo_publish as zp  # noqa: E402

fails, checks = [], 0


def check(ok, name, detail=""):
    global checks
    checks += 1
    if not ok:
        fails.append(f"{name} {detail}")


# ---------- 1. izvoz ----------
hist = {"2026-01-01": {"tempHigh": 3.0, "tempLow": -1.5, "tempAvg": 0.7, "precipTotal": 0.0, "windspeedHigh": 12.3, "windspeedAvg": 0.0, "humidityAvg": 91.0, "src": "station"},
        "2026-01-02": {"tempHigh": 4.0, "tempLow": 1.0, "tempAvg": None, "precipTotal": 2.4, "windspeedHigh": None, "windspeedAvg": None, "humidityAvg": None, "src": "wu"},
        "2026-01-03": {"tempHigh": 9.9, "tempLow": 9.9, "tempAvg": 9.9, "precipTotal": 9.9, "windspeedHigh": 9.9, "windspeedAvg": 9.9, "humidityAvg": 99.0, "src": "era5"},
        "2026-01-04": {"tempHigh": 5.0, "tempLow": 2.0, "tempAvg": 3.5, "precipTotal": 0.0, "windspeedHigh": 1.0, "windspeedAvg": 0.5, "humidityAvg": 80.0, "indoor": {"temp": 24}, "src": "station"}}
rows = ex.build_rows(hist)
check([r[0] for r in rows] == ["2026-01-01", "2026-01-02", "2026-01-04"], "dan iz reanalize (era5) je izpuščen", str([r[0] for r in rows]))
check(rows[0] == ["2026-01-01", "3", "-1.5", "0.7", "0", "12.3", "0", "91"], "vrednosti brez nepotrebnih ničel", str(rows[0]))
check(rows[1][3] == "" and rows[1][5] == "", "manjkajoča vrednost je prazna, ne 0", str(rows[1]))
check(len(rows[2]) == len(ex.COLUMNS) and "24" not in rows[2], "notranji blok ne pride v vrstico", str(rows[2]))
check([c for c, _ in ex.COLUMNS][1:] == ["temp_max_c", "temp_min_c", "temp_avg_c", "precip_mm", "wind_max_kmh", "wind_avg_kmh", "humidity_avg_pct"], "enote so v imenih stolpcev")

H = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))
with open(ex.OUT, encoding="utf-8", newline="") as f:
    pub = list(csv.DictReader(f))
check(len(pub) >= 2500, "objavljeni CSV ima vse dni", str(len(pub)))
check(all(r["date"] in H and H[r["date"]].get("src") != "era5" for r in pub), "vsak datum v CSV je meritev postaje iz history.json")
check(not any(H[d].get("src") == "era5" for d in (r["date"] for r in pub)), "CSV nima dni iz reanalize")
raw = open(ex.OUT, encoding="utf-8").read().lower()
check("indoor" not in raw and "tempinf" not in raw, "CSV ne omenja notranjih meritev")

# ---------- 2. Zenodo (lažen odjemalec) ----------
class Resp:
    def __init__(self, obj): self.b = json.dumps(obj).encode()
    def read(self): return self.b
    def __enter__(self): return self
    def __exit__(self, *a): return False
def fake(calls, fail_on=None):
    def opener(req, timeout=0):
        url, m = req.full_url, req.get_method()
        body = req.data
        calls.append((m, url, body))
        if m == "POST" and url.endswith("/deposit/depositions"):
            return Resp({"id": 77, "links": {"bucket": "https://zenodo.test/bucket/b1", "html": "https://zenodo.test/deposit/77"}})
        if m == "POST" and url.endswith("/actions/newversion"):
            return Resp({"id": 5, "links": {"latest_draft": "https://zenodo.test/api/deposit/depositions/78"}})
        if m == "GET" and url.endswith("/depositions/78"):
            return Resp({"id": 78, "files": [{"id": "f-old"}], "links": {"bucket": "https://zenodo.test/bucket/b2", "html": "https://zenodo.test/deposit/78"}})
        if url.endswith("/actions/publish"):
            return Resp({"doi": "10.5281/zenodo.999"})
        return Resp({})
    return opener
tmp = tempfile.mkdtemp()
csvp = os.path.join(tmp, "podatki.csv"); open(csvp, "w", encoding="utf-8").write("date,temp_max_c\n2019-11-07,1\n2026-11-04,2\n")
metap = os.path.join(tmp, "meta.json"); json.dump({"title": "T", "upload_type": "dataset", "doi": None}, open(metap, "w"))
calls = []
out = zp.publish("tok", "https://zenodo.test/api", None, False, fake(calls), csvp, metap)
check(out["published"] is False and not any(u.endswith("/actions/publish") for _, u, _ in calls), "brez --publish je samo osnutek (publish se ne pokliče)", str([u for _, u, _ in calls]))
puts = [c for c in calls if c[0] == "PUT"]
check(len(puts) == 2 and puts[0][1].endswith("/b1/podatki.csv") and puts[0][2].startswith(b"date,"), "CSV se naloži v bucket", str([p[1] for p in puts]))
md = json.loads(puts[1][2])["metadata"]
check(md["version"] == "2026-11-04" and md["dates"][0]["start"] == "2019-11-07" and "doi" not in md, "metapodatki: različica = zadnji dan, obdobje, brez doi", str(md))
calls = []
out = zp.publish("tok", "https://zenodo.test/api", None, True, fake(calls), csvp, metap)
check(out["published"] and out["doi"] == "10.5281/zenodo.999" and json.load(open(metap))["doi"] == "10.5281/zenodo.999", "--publish pokliče publish in zapiše DOI v metapodatke", str(out))
calls = []
zp.publish("tok", "https://zenodo.test/api", "5", False, fake(calls), csvp, metap)
check(any(m == "DELETE" and u.endswith("/files/f-old") for m, u, _ in calls) and any(m == "POST" and u.endswith("/actions/newversion") for m, u, _ in calls), "nova različica: stare datoteke se zamenjajo", str([(m, u[-30:]) for m, u, _ in calls]))
open(csvp, "w", encoding="utf-8").write("date,indoor_temp\n2019-11-07,1\n2026-11-04,2\n")
try:
    zp.publish("tok", "https://zenodo.test/api", None, True, fake([]), csvp, metap); stopped = False
except SystemExit:
    stopped = True
check(stopped, "CSV z notranjimi besedami ustavi objavo")
os.environ.pop("ZENODO_TOKEN", None)
check(zp.main([]) == 2, "brez žetona se ne pošlje nič")

# ---------- 3. shema in stran ----------
import generate_seo_pages as seo  # noqa: E402
def schema():
    t = seo.archive_dataset_schema("2019-11-07", "2026-11-04")
    return json.loads(t.split("\n", 1)[1].rsplit("\n</script>", 1)[0])
seo._DATASET_DOI_URL = None
d = schema()
check(d["identifier"] == ["IREICA1"] and "sameAs" not in d, "brez DOI ga shema ne izmišlja", str(d["identifier"]))
check([x["encodingFormat"] for x in d["distribution"]] == ["application/json", "text/csv"], "distribution je seznam JSON + CSV")
seo._DATASET_DOI_URL = "https://doi.org/10.5281/zenodo.999"
d = schema()
check(d["identifier"][-1] == "https://doi.org/10.5281/zenodo.999" and d["sameAs"].endswith("zenodo.999"), "z DOI ga shema navede")
src = open(os.path.join(HERE, "generate_seo_pages.py"), encoding="utf-8").read()
fn = src[src.index("def archive_dataset_schema"):src.index("def stn_badge")]
check(fn.count('"distribution"') == 1, "ključ distribution je v shemi enkrat (prej dvakrat)")
page = open(os.path.join(ROOT, "podatki", "index.html"), encoding="utf-8").read()
check("Kako citirati" in page and "ireica1-dnevni-podatki.csv" in page, "stran /podatki/ ima navodilo za citiranje in CSV")
check("doi.org/10.5281/zenodo.XXXX" not in page and "10.5281" not in page or json.load(open(os.path.join(ROOT, "data", "dataset-metadata.json")))["doi"], "stran nima izmišljenega DOI")

print(f"{checks} preverjanj, {len(fails)} napak")
for f in fails:
    print("  ✗", f)
sys.exit(1 if fails else 0)
