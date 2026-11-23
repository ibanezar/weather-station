#!/usr/bin/env python3
"""tools/test_snegofili.py — /snegofili/: seznam točk, izračun snega po oknih, izris, vdelava kamer.
Zaženi: python3 tools/test_snegofili.py"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import snegofili_data as d  # noqa: E402
import generate_snegofili_page as g  # noqa: E402

fails = 0


def check(ok, name):
    global fails
    if not ok:
        fails += 1
        print("  ✗", name)


# ── seznam točk ──
pts = d.load_points()
ids = [p["id"] for p in pts]
check(len(ids) == len(set(ids)), "id točk so enolični")
check(len(pts) >= 30, "vsaj 30 točk")
for p in pts:
    check(p["drzava"] in g.COUNTRIES, f"država {p['id']}")
    check(43 <= p["lat"] <= 48.5 and 5 <= p["lon"] <= 17, f"koordinate v alpskem loku {p['id']}")
    check(300 <= p["elevation_m"] <= 4200, f"višina {p['id']}")
    for c in p.get("kamere") or []:
        check(c["url"].startswith("https://"), f"povezava kamere https {p['id']}")
        if c.get("embed"):
            check(c["embed"].startswith("https://") and c.get("embed_terms") and c.get("checked"),
                  f"vdelava brez embed_terms/checked {p['id']}")

# ── izračun po oknih ──
N = 168
IDX = 80  # 72 nazaj + 8 ur


def series(fl, precip_at):
    times = [(datetime.datetime(2026, 11, 10) + datetime.timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(N)]
    pr = [precip_at.get(i, 0.0) for i in range(N)]
    return {"time": times, "temperature_2m": [-3.0] * N, "precipitation": pr, "freezing_level_height": [fl] * N}


cold = series(0, {i: 1.0 for i in range(N)})
c = d.compute_point(cold, IDX, 1000)
check(c["past24_cm"] == 24.0 and c["past72_cm"] == 72.0, "mraz: 1 mm/h = 1 cm/h nazaj")
check(c["next24_cm"] == 24.0 and c["next72_cm"] == 72.0, "mraz: naprej")
check(c["snow_line_m"] == -250, "meja sneženja = ničta izoterma − 250 m")
warm = series(3000, {i: 1.0 for i in range(N)})
w = d.compute_point(warm, IDX, 1000)
check(w["past24_cm"] == 0 and w["past24_mm"] == 24.0, "topli sloj: dež, ne sneg")
# meje oken: padavina ob idx+1 šteje samo naprej, ob idx samo nazaj
edge = series(0, {IDX: 5.0, IDX + 1: 7.0, IDX - 24: 3.0, IDX - 23: 2.0})
e = d.compute_point(edge, IDX, 1000)
check(e["past24_cm"] == 7.0, "nazaj (idx-24, idx]: 5+2, brez idx-24 in idx+1")
check(e["next24_cm"] == 7.0, "naprej začne pri idx+1")
check(d.compute_point(cold, 10, 1000) is None, "premalo ur nazaj → None")
check(d.compute_point(cold, N - 5, 1000) is None, "premalo ur naprej → None")
check(d.compute_point(cold, 60, 1000) is None, "70 ur nazaj ne zadošča za okno 72 h → None")
check(d.compute_point(cold, 71, 1000) is not None, "točno 72 ur nazaj zadošča")

# ── izris ──
rows = [{"id": "a", "ime": "Točka <A>", "drzava": "SI", "regija": "R", "lat": 46, "lon": 14, "elevation_m": 1500,
         "elev_opis": "x", "km_od_recice": 20, "temp_c": -2.0, "snow_line_m": 900, "snow_now_possible": True,
         "past24_cm": 12.0, "past72_cm": 30.0, "next24_cm": 4.0, "next72_cm": 6.0,
         "izmerjeno": {"depth_cm": 5, "valid_utc": "2026-11-13T06:00Z", "age_h": 3.0}},
        {"id": "b", "ime": "Daleč", "drzava": "CH", "regija": "R", "lat": 46, "lon": 7, "elevation_m": 3000,
         "elev_opis": "x", "km_od_recice": 700, "temp_c": -9.0, "snow_line_m": 1500, "snow_now_possible": True,
         "past24_cm": 0.2, "past72_cm": 0.4, "next24_cm": 50.0, "next72_cm": 60.0}]
data = {"generated_at": "2026-11-13T06:00:00Z", "generated_at_local": "13. 11. 2026 ob 7.00", "tocke": rows}
cams = {"a": {"id": "a", "ime": "A", "arso_cam": "Krvavec", "kamere": []}, "b": {"id": "b", "ime": "B", "kamere": [
    {"naslov": "k", "url": "https://x.example/cam", "ponudnik": "P"}]}}
body = g.build_body(data, cams)
check("Točka &lt;A&gt;" in body and "Točka <A>" not in body, "ime točke je ubežano")
hs = g.hero_sentence(rows)
check("Točka &lt;A&gt;" in hs and "(12 cm)" in hs.replace(" ", " "), "stavek: najbolj zasnežilo")
check("Daleč" not in hs, "stavek: točka čez 200 km ni v dnevnem izletu")
check("indoor" not in body.lower() and "tempinf" not in body.lower(), "brez notranjih meritev")
check(g.cm_cell(0.4) == "<1 cm" and g.cm_cell(3.26).startswith("3,3"), "oblika centimetrov (vejica, pod 1 cm »<1 cm«)")
good = {"embed_kind": "windy", "embed": "https://webcams.windy.com/webcams/public/embed/player/1/day", "embed_terms": "https://api.windy.com/webcams/terms", "checked": "2026-11-13", "ponudnik": "Windy"}
_alp = body.split('<section id="po-svetu"')[0]  # rubrika »Po svetu« ima lastne kamere (s pravimi podatki)
check('class="sg-camslot"' not in _alp, "brez vdelave ni slota")
check(g.valid_embed(good) == ("windy", good["embed"]), "windy vdelava z gostiteljem, pogoji in datumom je dovoljena")
check(g.valid_embed({**good, "checked": None}) is None, "vdelava brez checked ni dovoljena")
check(g.valid_embed({**good, "embed_terms": ""}) is None, "vdelava brez embed_terms ni dovoljena")
check(g.valid_embed({**good, "embed": "http://webcams.windy.com/x"}) is None, "http ni dovoljen")
check(g.valid_embed({**good, "embed": "https://evil.example/x"}) is None, "tuj gostitelj ni dovoljen")
check(g.valid_embed({**good, "embed_kind": "whatsupcams", "embed": "https://www.whatsupcams.com/en/x"}) is None, "WhatsUpCams ni na seznamu (pogoji prepovedujejo framing)")
check(g.valid_embed({**good, "embed": "https://webcams.windy.com.evil.example/x"}) is None, "podomena trik ni dovoljen")
slot = g.cam_slot("Vogel <b>", {"kamere": [good]})
check("Odpri kamero Windy" in slot and "windy.com" in slot and "add a webcam" in slot, "windy slot ima gumb in navedbo")
check("<b>" not in slot, "ime v slotu je ubežano")
yt = {"embed_kind": "youtube", "embed": "https://www.youtube-nocookie.com/embed/abc", "embed_terms": "Share → Embed", "checked": "2026-11-13", "ponudnik": "YT"}
check(g.valid_embed(yt) is not None and "add a webcam" not in g.cam_slot("X", {"kamere": [yt]}), "youtube slot brez Windy navedbe")
check(len(g.TITLE) <= 60, "naslov ≤ 60 znakov")


# ── usklajenost Python ↔ snegofili.js (namerna podvojitev) ──
import subprocess  # noqa: E402

CASES = [0, 0.4, 0.99, 1, 4.9, 5, 14.9, 15, 29.9, 30, 59.9, 60, 120]
js = ("const m=require('./snegofili/snegofili.js');const c=" + json.dumps(CASES) +
      ";console.log(JSON.stringify(c.map(x=>[m.step(x),+m.radius(x).toFixed(3),+m.barPct(x).toFixed(3)])))")
try:
    out = json.loads(subprocess.run(["node", "-e", js], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    capture_output=True, text=True, timeout=30, check=True).stdout)
    for x, (st, rad, bp) in zip(CASES, out):
        check(st == g.step(x) and abs(rad - g.radius(x)) < 1e-3 and abs(bp - g.bar_pct(x)) < 1e-3, f"JS↔Python step/radius/barPct pri {x}")
    jp = ("const m=require('./snegofili/snegofili.js');console.log(JSON.stringify([[1000,null],[1000,800],[1000,900],[1000,901],[1000,1100],[1000,1101],[1000,1500]]"
          ".map(a=>m.phase(a[0],a[1]))))")
    ph = json.loads(subprocess.run(["node", "-e", jp], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   capture_output=True, text=True, timeout=30, check=True).stdout)
    check(ph == [g.phase(a, b) for a, b in [(1000, None), (1000, 800), (1000, 900), (1000, 901), (1000, 1100), (1000, 1101), (1000, 1500)]],
          "JS↔Python phase (meje ±100 m)")
except (OSError, subprocess.SubprocessError) as e:
    check(False, f"node ni dosegljiv: {e}")

# ── urna serija: okno v JS pri »zdaj« = okno v Pythonu ──
hs = d.hourly_series(cold, 1000, IDX)
check(len(hs["sn"]) == 144 and len(hs["sl"]) == 144 and len(hs["t"]) == 144, "urna serija ima 144 ur")
check(len(hs["p"]) == 144 and hs["p"][0] == 10 and all(isinstance(x, int) for x in hs["p"]), "urna serija ima padavine v desetinkah mm")
jw = ("const m=require('./snegofili/snegofili.js');const s=" + json.dumps(hs["sn"]) +
      ";console.log(JSON.stringify(m.windows(s,m.NOW)))")
w2 = json.loads(subprocess.run(["node", "-e", jw], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               capture_output=True, text=True, timeout=30, check=True).stdout)
pp = d.compute_point(cold, IDX, 1000)
check(abs(w2["past"] - pp["past24_cm"]) < 1e-6 and abs(w2["next"] - pp["next24_cm"]) < 1e-6, "JS okno pri zdaj = Python past24/next24")
cw = d.compute_point(edge, IDX, 1000)
hs2 = d.hourly_series(edge, 1000, IDX)
w3 = json.loads(subprocess.run(["node", "-e", "const m=require('./snegofili/snegofili.js');console.log(JSON.stringify(m.windows(" + json.dumps(hs2["sn"]) + ",m.NOW)))"],
                               cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), capture_output=True, text=True, timeout=30, check=True).stdout)
check(abs(w3["past"] - cw["past24_cm"]) < 1e-6 and abs(w3["next"] - cw["next24_cm"]) < 1e-6, "JS↔Python okna na mejah (idx, idx+1)")

# ── izris: karta, prerez, kartice ──
check("sg-map" in body and "sg-prof" in body and 'class="sg-card"' in body, "hero ima karto, prerez in kartice")
check("sg-line" not in body, "prerez nima več polilinije")
check(g.ZOOM_VB.count(" ") == 3, "zoom viewBox ima 4 števila")

# ── ARSO: stara meritev se ne prikaže ──
now = datetime.datetime(2026, 11, 13, 12, 0, tzinfo=datetime.timezone.utc)
a = d.load_arso(now)
check(all(v["age_h"] <= d.ARSO_MAX_AGE_H for v in a.values()), "ARSO meritve ≤ 24 h")
# sintetični CSV: sveža se prikaže, 30 h stara ne, prihodnja ne, brez višine ne
import tempfile  # noqa: E402
with tempfile.TemporaryDirectory() as tmp:
    old_csv = d.ARSO_CSV
    d.ARSO_CSV = os.path.join(tmp, "snow.csv")
    with open(d.ARSO_CSV, "w", encoding="utf-8") as f:
        f.write("id,valid_utc,snow_cm\nsveza,2026-11-13T06:00Z,12\nstara,2026-11-12T06:00Z,40\n"
                "prihodnja,2026-11-13T20:00Z,5\nprazna,2026-11-13T06:00Z,\n")
    try:
        syn = d.load_arso(now)
    finally:
        d.ARSO_CSV = old_csv
check(set(syn) == {"sveza"} and syn["sveza"]["depth_cm"] == 12 and syn["sveza"]["age_h"] == 6.0,
      "ARSO: samo sveža meritev z višino (stara, prihodnja in prazna odpadejo)")

# ── status pod mejo sneženja: dež, brez padavin ali (brez podatka) splošna oznaka ──
check([g.phase_text("rain", {"precip_now_mm": 0.3}), g.phase_text("rain", {"precip_now_mm": 0.0}), g.phase_text("rain", {"precip_now_mm": 0.09}),
       g.phase_text("rain", {}), g.phase_text("rain"), g.phase_text("snow", {"precip_now_mm": 0.0}), g.phase_text("mix", {"precip_now_mm": 2.0})]
      == ["Dež", "Brez padavin", "Brez padavin", "Dež ali suho", "Dež ali suho", "Sneg", "Moker sneg"],
      "phase_text: prag 0,1 mm/h, brez podatka splošna oznaka, sneg in moker sneg ostaneta")
check(w["precip_now_mm"] == 1.0 and c["precip_now_mm"] == 1.0, "compute_point: padavine v tekoči uri")

# ── povezave kamer: samo https ──
links = g.cam_links({"kamere": [{"url": "http://x.example/a", "ponudnik": "Nevarna"},
                                {"url": "https://x.example/b", "ponudnik": "Varna"}]})
check("Varna" in links and "Nevarna" not in links, "cam_links: http povezava se ne izpiše")
check(g.cam_links({}) == "ni kamere", "cam_links: brez kamer besedilo")
both = g.cam_links({"arso_cam": "kredarica", "kamere": [{**good, "ponudnik": "Windy"}]})
check("ARSO: aktualna slika" in both and "Windy: časovni zdrs" in both and both.count("#kamere") == 1,
      "cam_links: vsak vir ima svojo oznako (ARSO slika, Windy zdrs), brez podvojene povezave")
wonly = g.cam_links({"kamere": [{**good, "ponudnik": "Windy"}]})
check("#kamere" not in wonly and "Windy: časovni zdrs" in wonly, "cam_links: samo Windy ne vodi na razdelek ARSO kamer")

# ── opozorilo na telefon: konstante gradnika ↔ worker.js (SG_CM_ALLOWED, SG_MAX_RULES), vse točke v izbirniku ──
import re  # noqa: E402
wsrc = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "worker.js"), encoding="utf-8").read()
m_cm = re.search(r"const SG_CM_ALLOWED = \[([\d, ]+)\];", wsrc)
m_max = re.search(r"const SG_MAX_RULES = (\d+);", wsrc)
check(m_cm and tuple(int(x) for x in m_cm.group(1).split(",")) == g.ALARM_CM, "alarm: pragovi gradnika = SG_CM_ALLOWED v workerju")
check(m_max and int(m_max.group(1)) == g.ALARM_MAX_RULES, "alarm: največ pravil gradnika = SG_MAX_RULES v workerju")
ah = g.alarm_html([{"id": "a", "ime": "A <b>", "drzava": "SI", "elevation_m": 1500}, {"id": "b", "ime": "B", "drzava": "AT", "elevation_m": 2000}])
check('value="a"' in ah and 'value="b"' in ah and "A &lt;b&gt;" in ah, "alarm: točke v izbirniku, ime ubežano")
check(ah.index('value="a"') < ah.index('value="b"'), "alarm: razvrščeno po državi (SI pred AT) in imenu")
check("ni plazovni bilten" in ah and "ne meritev" in ah, "alarm: opozorilo, da je modelska ocena in ni plazovni bilten")
check("hidden" in ah.split(">")[0], "alarm: brez JS skrit (nikoli gumb, ki ne dela)")
check(all(f'value="{c}"' in ah for c in g.ALARM_CM), "alarm: vsi pragovi v izbirniku")

# ── nove komponente (19. 11. 2026): model v JS (snowing, hstep, plan) in struktura strani ──
CWD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def node_json(code):
    return json.loads(subprocess.run(["node", "-e", "const m=require('./snegofili/snegofili.js');" + code], cwd=CWD,
                                     capture_output=True, text=True, timeout=30, check=True).stdout)


try:
    check(node_json("console.log(JSON.stringify([m.ptxt('rain',{p:[0,1,5]},0),m.ptxt('rain',{p:[0,1,5]},1),m.ptxt('rain',{p:[0,1,5]},2),m.ptxt('rain',{},1),m.ptxt('rain',null,0),m.ptxt('snow',{p:[0]},0),m.ptxt('mix',{p:[9]},0)]))")
          == ["Brez padavin", "Dež", "Dež", "Dež ali suho", "Dež ali suho", "Sneg", "Moker sneg"],
          "JS ptxt: prag 0,1 mm/h, brez serije padavin splošna oznaka")
except (OSError, subprocess.SubprocessError, ValueError) as e:
    check(False, f"node (ptxt): {e}")
try:
    check(node_json("console.log(JSON.stringify([m.snowing({sn:[0,1,0]},1),m.snowing({sn:[0,0,0]},1),m.snowing(null,0),m.snowing({sn:[]},5)]))") == [True, False, False, False],
          "JS snowing: prag 0,1 cm/h, brez podatka ni snega")
    check(node_json("console.log(JSON.stringify([0,0.9,1,4.9,5,9.9,10,19.9,20,39.9,40,80].map(m.hstep)))") == [-1, -1, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4],
          "JS hstep: pragovi 0,1 / 0,5 / 1 / 2 / 4 cm/h")
    plan_js = r"""
const hs=(f)=>{const a=new Array(144).fill(0);f(a);return {sn:a,t:[],sl:[]}};
const hours={a:hs(a=>{a[71]=7;for(let i=72;i<=95;i++)a[i]=10}),   // 24 cm v naslednjih 24 h (ura 71 = »zdaj«, šteje samo nazaj)
             b:hs(a=>{for(let i=72;i<=95;i++)a[i]=5}),             // 12 cm
             c:hs(a=>{for(let i=96;i<=119;i++)a[i]=30}),           // 72 cm šele 24-48 h
             d:hs(a=>{for(let i=72;i<=95;i++)a[i]=10}),            // 24 cm, a daleč
             e:hs(a=>{a[72]=2})};                                  // 0,2 cm: pod pragom
const pts=[{id:'d',e:2500,k:500},{id:'a',e:1500,k:50},{id:'b',e:900,k:10},{id:'c',e:2000,k:30},{id:'e',e:1800,k:5}];
const r=(o)=>m.plan(pts,hours,o).map(x=>x.p.id+':'+x.cm);
console.log(JSON.stringify([r({win:'n24',km:200,minCm:1}), r({win:'n24',km:0,minCm:1}), r({win:'n48',km:0,minCm:1}),
  r({win:'n24',km:0,minCm:1,minE:1000}), r({win:'n24',km:0,minCm:15}), r({win:'p24',km:0,minCm:1}), r({win:'n24',km:0,minCm:1,top:1}), r({win:'p24',km:0,minCm:0})]))
"""
    got = node_json(plan_js)
    check(got[0] == ["a:24", "b:12"], "plan: razdalja 200 km izloči d, pod 1 cm izloči e")
    check(got[1] == ["a:24", "d:24", "b:12"], "plan: ob izenačenju prej bližja točka (d je v seznamu prvi)")
    check(got[2] == ["c:72"], "plan: okno 24–48 h od zdaj")
    check(got[3] == ["a:24", "d:24"], "plan: najmanjša višina točke")
    check(got[4] == ["a:24", "d:24"], "plan: prag 15 cm")
    check(got[5] == [], "plan: okno nazaj brez snega")
    check(got[6] == ["a:24"], "plan: top")
    check(got[7] == ["a:0.7"], "plan: ura »zdaj« šteje samo v oknu nazaj")
except (OSError, subprocess.SubprocessError, ValueError) as e:
    check(False, f"node (nove komponente): {e}")

try:
    slo_js = r"""
const H=3600000, NOW=Date.UTC(2026,11,3,8,0), SLO=[290,291,292,293], OUT=[280,281,282,283];
const K=(fill)=>{const sn=Array.from({length:48},()=>new Array(560).fill(0));const z=new Array(560).fill(null);SLO.concat(OUT).forEach((i,n)=>{z[i]=500+100*n});fill(sn);return {generated:NOW,t0:NOW,nx:35,ny:16,sn,z}};
const S=(f,now)=>m.sloSummary(K(f),now==null?NOW:now);
const a=S(sn=>{SLO.forEach(i=>{sn[0][i]=5});sn[0][SLO[0]]=12});
console.log(JSON.stringify([a.active,a.cells,a.maxCmH,a.lowM,a.hours,
  S(sn=>{OUT.forEach(i=>{sn[0][i]=30})}).active,
  S(sn=>{SLO.slice(0,2).forEach(i=>{sn[0][i]=30})}).active,
  S(sn=>{SLO.slice(0,3).forEach(i=>{sn[0][i]=1})}).active,
  S(sn=>{SLO.forEach(i=>{sn[5][i]=9})}).active,
  S(sn=>{SLO.forEach(i=>{sn[2][i]=9})}).active,
  S(sn=>{SLO.forEach(i=>{sn[0][i]=9})},NOW+2*H).active,
  m.sloSummary(null,NOW).active,m.sloSummary({sn:'x'},NOW).active,
  m.SLO_MASK.length,m.SLO_MASK.every(r=>r.length===35)]))
"""
    sl = node_json(slo_js)
    check(sl[:5] == [True, 4, 1.2, 500, 1], "okno Slovenija: povzetek karte (4 celice, največ 1,2 cm/h, najnižja celica 500 m, 1 ura)")
    check(sl[5] is False, "okno Slovenija: sneženje zunaj Slovenije ne šteje (maska)")
    check(sl[6] is False and sl[7] is True, "okno Slovenija: 2 celici sta šum, 3 celice po 0,1 cm/h so prag")
    check(sl[8] is False and sl[9] is True, "okno Slovenija: ura čez okno ne šteje, zadnja ura okna šteje")
    check(sl[10] is False, "okno Slovenija: ura, ki je že mimo, ne šteje (po žigu, ne po indeksu)")
    check(sl[11] is False and sl[12] is False, "okno Slovenija: brez karte ali s pokvarjeno karto ni sneženja")
    check(sl[13] == 16 and sl[14] is True, "okno Slovenija: maska ima 16 vrstic po 35 celic")
    pl_js = r"""
const H=3600000, NOW=Date.UTC(2026,11,3,8,0);
const K=(cells,lat0,lon0)=>{const sn=Array.from({length:48},()=>new Array(560).fill(0));Object.keys(cells).forEach(i=>{sn[0][i]=cells[i];sn[1][i]=Math.round(cells[i]/2)});return {generated:NOW,t0:NOW,nx:35,ny:16,sn,z:new Array(560).fill(900),lat0,lon0,d:0.1}};
// 390 = vrstica 11, stolpec 5 (46,5 N, 13,8 E: Kranjska Gora); 291.. = vrstica 8, stolpci 11-13 (46,2 N, 14,4-14,6 E: Kamnik); 560-vrstica 15 je zunaj maske
const k1=K({390:18,391:6,392:3,291:7,292:7,293:7});
const p=m.sloPlaces(k1,NOW), h=m.sloHits(k1,NOW), s=m.sloSummary(k1,NOW);
const p0=m.sloPlaces(K({0:30,1:30,2:30}),NOW), p1=m.sloPlaces(null,NOW), p2=m.sloPlaces(K({}),NOW);
const dflt=m.sloPlaces({generated:NOW,t0:NOW,nx:35,ny:16,sn:k1.sn,z:k1.z},NOW);
console.log(JSON.stringify([p.map(x=>x.name+':'+x.cmH+':'+x.n), h.hours, Object.keys(h.cells).length, s.cells, s.maxCmH, p0.length, p1.length, p2.length, dflt.length, m.SLO_PLACES.length>=40]))
"""
    pl = node_json(pl_js)
    check(pl[0][0].startswith("Kranjska Gora:1.8:") and len(pl[0]) >= 2, "kraji: najmočnejše sneženje prvo, celica pri Kranjski Gori da Kranjsko Goro (največ 1,8 cm/h)")
    check(pl[1] == 2 and pl[2] == 5 and pl[3] == 5 and pl[4] == 1.8, "kraji: sloHits in sloSummary štejeta iste celice (celica 392 je zunaj maske, 5 znotraj)")
    check(pl[5] == 0 and pl[6] == 0 and pl[7] == 0, "kraji: celice zunaj Slovenije, brez karte in brez snega ne dajo krajev")
    check(pl[8] >= 1, "kraji: brez lat0/lon0/d v karti veljajo konstante snežne karte")
    check(pl[9] is True, "kraji: seznam ima vsaj 40 krajev")
except (OSError, subprocess.SubprocessError, ValueError) as e:
    check(False, f"node (okno Slovenija): {e}")

check('id="sg-slo"' in body and 'id="sg-slo-l"' in body and 'id="sg-slo-x"' in body and 'id="sg-slo-s"' in body and 'id="sg-slo-t"' in body,
      "stran ima okno »Sneži v Sloveniji« (skrito do JS) z vsemi elementi, ki jih polni sloPaint()")
check(re.search(r'<aside class="sg-slo"[^>]*\bhidden\b', body) is not None, "okno Slovenija je privzeto skrito (brez JS statičen posnetek ne trdi nič)")
# ── merila na karticah v herou (22. 11. 2026) ──
try:
    vs = [0, 0.4, 1, 3, 10, 32, 59, 60, 120, 400]
    js = node_json("console.log(JSON.stringify(%s.map(v=>m.gaugePos(v))))" % json.dumps(vs))
    check(js == [g.gauge_pos(v) for v in vs], "gauge_pos (Python) = gaugePos (JS) na 10 vrednostih, nad 60 cm je lata polna")
    check(g.gauge_pos(0) == 0 and g.gauge_pos(60) == 100 and 0 < g.gauge_pos(3) < g.gauge_pos(10) < g.gauge_pos(32) < 100, "lata je korenska in monotona")
    check(node_json("console.log(JSON.stringify([m.GAUGE_MAX,m.GAUGE_SEGS]))") == [g.GAUGE_MAX, g.GAUGE_SEGS], "konstante late in segmentov so v obeh jezikih enake")
except (OSError, subprocess.SubprocessError, ValueError) as e:
    check(False, f"node (gauge): {e}")
check('id="sg-st-past-g"' in body and 'id="sg-st-next-g"' in body and 'id="sg-st-fresh-g"' in body and 'class="sg-sbars"' in body and 'id="sg-st-rec-g"' in body,
      "kartice v herou imajo merila: lata (nazaj, naprej), segmenti, stolpci postaj in mesto za Rečico")
check(body.count('class="sg-segs"') == 1 and body.count('<i class=on>') <= g.GAUGE_SEGS, "segmentov je 20, vklopljenih ne več")
z = g.gauge_rule("x", 0, "0 cm", meas=True)
check('sg-rule meas zero' in z and 'width:0.0%' in z, "izmerjena ničla je krožec (zero), ne prazna proga")
check('&amp;lt;' not in g.gauge_rule("x", 0.2, "<1 cm"), "oznaka late ni dvakrat escapirana")
check('id="sg-stats"' in body and 'id="zdaj-snezi"' in body and 'id="kam-peljem"' in body and 'id="toplotna-karta"' in body,
      "stran ima povzetek, pas »Kjer zdaj sneži«, izbirnik in toplotno karto")
check(body.count('class="sg-spark"') == 2, "vsaka kartica ima rezerviran sparkline")
check('data-f="fav"' in body, "filter »Moje točke«")
check("<script>" not in body.replace('<script type="application/json"', ""), "brez inline JS (kamere so v snegofili.js)")
check('class="sg-cam"' in body and 'data-id="a"' in body and 'data-kind="arso"' in body, "kamerni zid: ploščica za točko s kamero ARSO")
check(body.count('class="sg-cam"') == 1, "kamerni zid: točka samo s tujo povezavo nima ploščice")
check('href="https://x.example/cam"' in body and "Kamere pri ponudnikih" in body, "tuja kamera je v seznamu povezav")
pj = json.loads(body.split('id="sg-pts">')[1].split("</script>")[0])
pa = next(x for x in pj if x["id"] == "a"); pb = next(x for x in pj if x["id"] == "b")
check(pa.get("ca") == "Krvavec" and pa["k"] == 20 and pa["c"] == "SI" and pa["m"] == {"d": 5, "a": 3.0}, "sg-pts: kamera, razdalja, država, izmerjeno")
check(pb.get("cl") == [{"u": "https://x.example/cam", "p": "P"}] and "ca" not in pb and "m" not in pb, "sg-pts: samo https povezave, brez izmišljenih polj")
emb = g.cam_info({"kamere": [good]})
check(len(emb.get("ce", [])) == 1 and emb["ce"][0]["k"] == "windy" and emb["ce"][0]["s"] == good["embed"], "cam_info: dovoljena vdelava gre v sg-pts (seznam)")
check("cl" not in emb, "cam_info: vdelana kamera ni še enkrat med povezavami")
check("ce" not in g.cam_info({"kamere": [{**good, "checked": None}]}), "cam_info: vdelava brez potrdila ne gre v sg-pts")
check('data-proxy="' in body and "data-drsi" in body, "kamerni zid nosi naslov workerja in DRSI")
check("Izmerjena snežna odeja" in body and "Agencija Republike Slovenije za okolje" in body, "izmerjeno: razdelek z navedbo vira ARSO")
check("Videa v živo tu ni" in body and "Oglej si aktualno sliko" in body, "kamere: iskreno pove, da ni videa v živo")
check(g.measured_html([r for r in rows if "izmerjeno" not in r]) == "", "izmerjeno: brez meritev razdelka ni")

check('id="windy"' in body and "<iframe" not in body, "Windy karta: razdelek je, iframe šele po kliku")
check(g.WINDY_MAP.startswith("https://embed.windy.com/") and "{overlay}" in g.WINDY_MAP and all("overlay=" + o + "&" in g.WINDY_MAP.replace("{overlay}", o) for o, _ in g.WINDY_OVERLAYS),
      "Windy karta: gostitelj embed.windy.com, plast je parameter")
check("windy.com" in body and "ne naša ocena" in body, "Windy karta: navedba ponudnika in pojasnilo, da ni naša ocena")

# ── add_windy_cam.py: sidra Windy → iframe (skripta player.js se ne izvaja) ──
import add_windy_cam as aw  # noqa: E402
A = ('<a name="windy-webcam-timelapse-player" data-id="1385535601" data-play="day" href="https://www.windy.com/webcams/1385535601" target="_blank">Kredarica</a>\n'
     '<a name="windy-webcam-timelapse-player" data-id="1010220186" data-play="day" href="x" target="_blank">Jungfraujoch &amp; Top</a>\n'
     '<script async src="https://webcams.windy.com/webcams/public/embed/v2/script/player.js"></script>')
pa = aw.parse(A)
check([c["id"] for c in pa] == ["1385535601", "1010220186"], "windy: dve sidri razpoznani, skripta ne šteje")
check(pa[0]["src"] == "https://webcams.windy.com/webcams/public/embed/player/1385535601/day" and pa[1]["naslov"] == "Jungfraujoch & Top", "windy: src iz id in play, naslov brez entitet")
check(aw.parse('<iframe src="https://webcams.windy.com/x"></iframe>')[0]["src"] == "https://webcams.windy.com/x", "windy: iframe src")
chk = {"tocke": [{"id": "t", "ime": "T", "kamere": []}]}
aw.add(chk, "t", pa[0], today="2026-11-19")
e0 = chk["tocke"][0]["kamere"][0]
check(g.valid_embed(e0) == ("windy", pa[0]["src"]) and e0["checked"] == "2026-11-19", "windy: vnos prestane valid_embed")
aw.add(chk, "t", pa[0], today="2026-11-20")
check(len(chk["tocke"][0]["kamere"]) == 1, "windy: ponovni vnos iste kamere zamenja, ne podvoji")
for bad in ({"src": "https://evil.example/x"}, {"src": "http://webcams.windy.com/x"}, {"src": "https://webcams.windy.com.evil.example/x"}):
    try:
        aw.add(chk, "t", {**bad, "url": "u"}); check(False, f"windy: {bad['src']} bi moral biti zavrnjen")
    except ValueError:
        pass
try:
    aw.add(chk, "ni-take", pa[0]); check(False, "windy: neznana točka")
except ValueError:
    pass
check("1010220186" not in json.dumps(aw.parse('<a name="windy-webcam-timelapse-player" data-id="abc" data-play="day">x</a>')), "windy: neveljaven id se ne sprejme")
# ob več vdelavah na točko gredo vse v sg-pts, ob več kot eni je ena ploščica
good2 = {**good, "embed": "https://webcams.windy.com/webcams/public/embed/player/2/day", "naslov": "Druga"}
two = g.cam_info({"kamere": [good, good2]})
check(len(two["ce"]) == 2 and two["ce"][1]["t"] == "Druga", "cam_info: več vdelav na točko")

# ── ročna meritev snega v Rečici ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import snegofili_recica as rec
from datetime import datetime as _dt, timedelta as _td, timezone as _tz
try:
    now_ms = int(_dt(2026, 11, 20, 12, 0, tzinfo=_tz.utc).timestamp() * 1000)
    L = [{"cas": "2026-11-20T07:00:00Z", "cm": 3, "novi": 1}, {"cas": "2026-11-19T07:00:00Z", "cm": 8},
         {"cas": "2026-11-21T07:00:00Z", "cm": 99}, {"cas": "nesmisel", "cm": 5}, {"cas": "2026-11-20T08:00:00Z", "cm": -1},
         {"cas": "2026-11-20T09:00:00Z", "cm": "5"}]
    r = node_json(f"console.log(JSON.stringify(m.recicaState({json.dumps(L)},{now_ms})))")
    check(r and r["cm"] == 3 and r["novi"] == 1 and abs(r["ageH"] - 5) < 0.01 and r["stale"] is False,
          "Rečica: izbere najnovejšo veljavno meritev (prihodnost, nesmisel, negativna in nizi so zavrnjeni)")
    check(node_json(f"console.log(JSON.stringify([m.recicaState([],{now_ms}),m.recicaState(null,{now_ms})]))") == [None, None],
          "Rečica: brez meritev ni ploščice")
    st = node_json(f"console.log(JSON.stringify([m.recicaState([{{cas:'2026-11-17T11:00:00Z',cm:2}}],{now_ms}),m.recicaState([{{cas:'2026-11-17T13:00:00Z',cm:2}}],{now_ms}),m.recicaState([{{cas:'2026-10-20T11:00:00Z',cm:2}}],{now_ms}),m.recicaState([{{cas:'2026-10-22T11:00:00Z',cm:0}}],{now_ms})]))")
    check([x is not None and x["stale"] for x in st[:2]] == [True, False] and st[2] is None and st[3] is not None and st[3]["cm"] == 0,
          "Rečica: starejša od 72 h je označena kot stara, starejša od 30 dni se skrije, ničla je veljavna meritev")
    check(node_json("console.log(JSON.stringify([m.recicaCm(0),m.recicaCm(3),m.recicaCm(2.5),m.recicaCm(12.4),m.recicaAge(0.4),m.recicaAge(5.2),m.recicaAge(30),m.recicaAge(72)]))")
          == ["0 cm", "3 cm", "2,5 cm", "12 cm", "pred manj kot uro", "pred 5 h", "pred 30 h", "pred 3 dnevi"],
          "Rečica: besedila (decimalna vejica, ura/dnevi)")
except (OSError, subprocess.SubprocessError, ValueError) as e:
    check(False, f"node (Rečica): {e}")

d0 = {"meritve": []}
d1 = rec.add(d0, 3, 1, _dt(2026, 11, 19, 8, 30))
check(d1["meritve"] == [{"cas": "2026-11-19T07:30:00Z", "cm": 3, "novi": 1}], "Rečica CLI: čas po naši uri se zapiše v UTC (zima +1 h)")
d2 = rec.add(rec.add(d1, 0, None, _dt(2026, 11, 19, 20, 0)), 4, None, _dt(2026, 11, 18, 8, 0))
check([m["cas"][:10] for m in d2["meritve"]] == ["2026-11-18", "2026-11-19", "2026-11-19"] and d2["meritve"][2]["cm"] == 0,
      "Rečica CLI: vnosi so urejeni po času, ničla je veljaven vnos")
check(rec.add(d1, 7, None, _dt(2026, 11, 19, 8, 30))["meritve"] == [{"cas": "2026-11-19T07:30:00Z", "cm": 7}], "Rečica CLI: ista minuta prepiše vnos")
for bad in ((-1, None, None), (501, None, None), (3, -2, None), (3, None, _dt.now() + _td(days=2))):
    try:
        rec.add(d0, *bad)
        check(False, f"Rečica CLI: zavrne {bad}")
    except ValueError:
        check(True, "Rečica CLI: zavrne neveljaven vnos")
dj = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "snegofili-recica.json"), encoding="utf-8"))
ts = [m["cas"] for m in dj["meritve"]]
check(isinstance(dj["meritve"], list) and ts == sorted(ts) and all(isinstance(m["cm"], (int, float)) and 0 <= m["cm"] <= 500 and m["cas"].endswith("Z") for m in dj["meritve"]),
      "data/snegofili-recica.json: veljavna oblika, urejeno po času")
check('id="sg-st-rec-w"' in body and 'id="sg-rec-lbl"' in body, "stran ima skrito ploščico Rečica in oznako na zemljevidu")

# ── rubrika »Po svetu« ──
wpts = json.load(open(d.WORLD_POINTS_PATH, encoding="utf-8"))["tocke"]
wids = [p["id"] for p in wpts]
check(len(wids) == len(set(wids)) and not set(wids) & set(ids), "svet: id so enolični in ne trčijo z alpskimi")
for p in wpts:
    check(p["drzava"] in g.COUNTRIES_WORLD, f"svet: država {p['id']}")
    check(-180 <= p["lon"] <= 180 and -60 <= p["lat"] <= 70 and 0 < p["elevation_m"] <= 4500, f"svet: koordinate in višina {p['id']}")
    check(all(k in p for k in ("ime", "regija", "elev_opis")), f"svet: polja {p['id']}")
check({p["drzava"] for p in wpts} == {"JP", "CA", "US", "CL", "AR", "NZ", "AU"}, "svet: Japonska, Severna Amerika in južna polobla")
check(all(p["lat"] < 0 for p in wpts if p["drzava"] in g.SOUTH_CODES) and all(p["lat"] > 0 for p in wpts if p["drzava"] not in g.SOUTH_CODES), "svet: južna polobla ima negativno širino")
# nadomestek ob manjkajoči ničti izotermi: ura ne sme šteti za »nič snega«
check(d.snow_frac(1000, None, -3) == 1.0 and d.snow_frac(1000, None, 1) == 0.5 and d.snow_frac(1000, None, 5) == 0.0, "svet: sneg iz temperature, kadar ni ničte izoterme")
check(d.snow_frac(1000, None, None) == 0.0 and d.snow_frac(1000, 3000, 5) == d.we.snow_fraction(1000, 3000), "ničta izoterma ima prednost; brez obojega ni snega")
_tm = [f"2026-11-20T{h:02d}:00" for h in range(24)] * 7
_n = len(_tm)
_h = {"time": _tm, "temperature_2m": [-4.0] * _n, "precipitation": [1.0] * _n, "freezing_level_height": [None] * _n}
check(d.window_snow(_h, 1500, range(10, 34))[0] == 24.0, "svet: 24 ur po 1 mm pri −4 °C brez ničte izoterme = 24 cm")
_ser = d.hourly_series(_h, 1500, 71)
check(len(_ser["sn"]) == 144 and _ser["sn"][0] == 10, "svet: urna serija ima 144 vrednosti, 1 cm/h = 10")
_sp = g.spark_svg(_ser["sn"])
check(_sp.count("<rect") == 96 and "<line" in _sp and 'role="img"' in _sp, "svet: sličica poteka ima 96 stolpcev in črto »zdaj«")
check(g.spark_svg(None) == "" and g.spark_svg([0] * 50) == "", "svet: brez serije ni sličice")
check(g.world_phase({"elevation_m": 1500, "snow_line_m": None, "temp_c": -2}) == "snow" and g.world_phase({"elevation_m": 1500, "snow_line_m": None, "temp_c": 5}) == "rain"
      and g.world_phase({"elevation_m": 1500, "snow_line_m": None, "temp_c": None}) == "rain", "svet: stanje iz temperature, kadar ni meje sneženja")
_wr = [dict(id="a", ime="Test A", drzava="JP", regija="Hokkaido", lat=1, lon=1, elevation_m=1100, elev_opis="x", past24_cm=12.0, next24_cm=3.0, past72_cm=30.0,
            next72_cm=8.0, temp_c=-4.0, snow_line_m=None, precip_now_mm=0.3, sn=_ser["sn"]),
       dict(id="b", ime="Test B", drzava="US", regija="Utah", lat=1, lon=1, elevation_m=2900, elev_opis="x", past24_cm=0.0, next24_cm=0.0, past72_cm=0.0,
            next72_cm=0.0, temp_c=1.0, snow_line_m=1500, precip_now_mm=0.0, sn=_ser["sn"])]
_html_w = g.svet_html({"rows": _wr, "when": ""})
check('id="po-svetu"' in _html_w and "Japonska</h3>" in _html_w and "Severna Amerika</h3>" in _html_w and _html_w.count('class="sg-wc"') == 2, "svet: razdelek z obema skupinama in karticama")
check("Test A" in _html_w and "12 cm" in _html_w and "ni podatka" in _html_w and "&lt;1 cm" in _html_w, "svet: številke in »ni podatka« za manjkajočo mejo, <1 cm za ničlo")
check("suh in lahek" in _html_w and "merjene višine odeje" in _html_w, "svet: opozorilo, da je modelska ocena in da je japonski sneg lahko težji od ocene")
check(g.load_world.__doc__ and g.world_card_html(_wr[0]).count("<article") == 1, "svet: ena kartica = en članek")
_old = g.WORLD_PATH
g.WORLD_PATH = os.path.join(tempfile.mkdtemp(), "ni.json")
check(g.load_world() is None, "svet: brez datoteke rubrike ni")
g.WORLD_PATH = _old

# kamere na karticah »Po svetu« (isti zapis kot pri alpskih točkah; vdelava samo prek valid_embed())
_wcam = {"kamere": [{"naslov": "Hanazono", "url": "https://www.windy.com/webcams/1697599566", "ponudnik": "Windy", "embed_kind": "windy",
                     "embed": "https://webcams.windy.com/webcams/public/embed/player/1697599566/day", "embed_terms": "https://api.windy.com/webcams/terms", "checked": "2026-11-20"}]}
_wlink = {"kamere": [{"naslov": "Kamere", "url": "https://www.whistler.com/webcams/", "ponudnik": "Tourism Whistler"}]}
_wbad = {"kamere": [{"naslov": "x", "url": "https://evil.example/", "ponudnik": "Windy", "embed_kind": "windy", "embed": "https://evil.example/player/12345/day",
                     "embed_terms": "https://api.windy.com/webcams/terms", "checked": "2026-11-20"}]}
_c1, _c2, _c3, _c0 = (g.world_card_html(_wr[0], x) for x in (_wcam, _wlink, _wbad, None))
check('class="sg-wc-cam" data-wid="1697599566"' in _c1 and 'class="sg-camslot"' in _c1 and "Webcams provided by" in _c1 and "Windy: časovni zdrs" in _c1,
      "svet kamere: Windy vdelava da sličico, gumb s pogoji in navedbo")
check("sg-wc-cam" not in _c2 and "sg-camslot" not in _c2 and 'href="https://www.whistler.com/webcams/"' in _c2 and "Tourism Whistler: odpri kamero" in _c2,
      "svet kamere: povezava ponudnika brez vdelave in brez sličice")
check("sg-wc-cam" not in _c3 and "sg-camslot" not in _c3 and "player/12345" not in _c3, "svet kamere: vdelava z napačne domene se ne prikaže")
check("ni kamere" in _c0 and "#kamere" not in _c0, "svet kamere: točka brez kamere piše »ni kamere« in ne vodi na razdelek ARSO")
_wp = g.load_world_cams()
check({"niseko", "whistler", "alta", "zao"} <= set(_wp) and all(g.valid_embed(c) is None for p in _wp.values() for c in p.get("kamere") or [] if not c.get("embed_kind")),
      "svet kamere: seznam točk se naloži, povezave brez vdelave niso vdelave")
check(all(str(c.get("url", "")).startswith("https://") and c.get("ponudnik") for p in _wp.values() for c in p.get("kamere") or []), "svet kamere: vsaka kamera ima https povezavo in ponudnika")
_ref = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "snegofili", "snegofili.js"), encoding="utf-8").read()
check("sg-wc-cam[data-wid]" in _ref and "/windy-thumb?id=" in _ref and "windy\\.com" in _ref, "svet kamere: JS nalaga sličice prek workerja in sprejme samo windy.com")

# ── Powder Tracker: kategorije, vrstni red, veter, izris ──
def _r(**k):
    base = {"id": "x", "ime": "X", "drzava": "AT", "regija": "R", "elevation_m": 2000, "temp_c": -5.0, "past24_cm": 0.0, "past72_cm": 0.0,
            "next24_cm": 0.0, "next72_cm": 0.0, "snow_line_m": 1000}
    base.update(k)
    return base


pc = g.powder_category
check(pc(_r(past24_cm=g.PW_POWDER_CM)) == "powder", "powder: točno na meji")
check(pc(_r(past24_cm=g.PW_POWDER_CM - 0.1)) == "fresh", "powder: tik pod mejo je svež sneg")
check(pc(_r(past24_cm=30, temp_c=0.1)) == "fresh", "powder: nad 0 °C ni powder alert")
check(pc(_r(past24_cm=30, temp_c=g.PW_POWDER_T)) == "powder", "powder: temperatura točno 0 °C velja")
check(pc(_r(past24_cm=30, temp_c=None)) == "fresh", "powder: brez temperature ni powder alert")
check(pc(_r(past24_cm=30, gust_kmh=g.PW_GUST_KMH)) == "fresh", "powder: močni sunki znižajo na svež sneg")
check(pc(_r(past24_cm=30, gust_kmh=g.PW_GUST_KMH - 1)) == "powder", "powder: sunek pod mejo ne šteje")
check(pc(_r(past24_cm=30, gust_kmh=None)) == "powder", "powder: neznan veter ne blokira (stari posnetek brez vetra)")
check(pc(_r(past24_cm=g.PW_FRESH_CM)) == "fresh" and pc(_r(past72_cm=g.PW_FRESH72_CM)) == "fresh", "svež sneg: meji 24 h in 72 h")
check(pc(_r(next24_cm=g.PW_WAIT24_CM)) == "waiting" and pc(_r(next72_cm=g.PW_WAIT72_CM)) == "waiting", "sneg prihaja: meji 24 h in 72 h")
check(pc(_r(past24_cm=g.PW_FRESH_CM, next24_cm=40)) == "fresh", "svež sneg ima prednost pred »sneg prihaja«")
check(pc(_r(past72_cm=g.PW_SNOWY_CM)) == "snowy" and pc(_r(next72_cm=g.PW_SNOWY_CM)) == "snowy", "nekaj snega: nazaj in naprej")
check(pc(_r()) is None and pc(_r(past72_cm=g.PW_SNOWY_CM - 0.1)) is None, "brez snega ni kategorije")
check(pc({"id": "y"}) is None, "manjkajoča polja ne podrejo razvrstitve")
check(g.powder_quality(-3) == "suh, lahek sneg" and g.powder_quality(-2.9).startswith("običajen") and g.powder_quality(0.1).startswith("moker")
      and g.powder_quality(None) == "", "kakovost po temperaturi")
check(g.powder_sort_key(_r(past24_cm=20), "powder") < g.powder_sort_key(_r(past24_cm=40), "fresh"), "razvrstitev: kategorija pred količino")
check(g.powder_sort_key(_r(past24_cm=40), "powder") < g.powder_sort_key(_r(past24_cm=20), "powder"), "razvrstitev: v kategoriji več snega prej")
check(g.powder_sort_key(_r(next24_cm=30), "waiting") < g.powder_sort_key(_r(next24_cm=12), "waiting"), "razvrstitev: pri »sneg prihaja« po napovedanem")
check(g.powder_groups(_r(drzava="SI"), False) == "alpe si" and g.powder_groups(_r(drzava="AT"), False) == "alpe"
      and g.powder_groups(_r(drzava="JP"), True) == "japonska" and g.powder_groups(_r(drzava="US"), True) == "amerika", "skupine območij")
check(g.powder_wind(_r(wind_kmh=20, gust_kmh=45)) == "veter 20 km/h (sunki 45)" and g.powder_wind(_r()) == "", "izpis vetra")

_pa = [_r(id="a", ime="Alfa", past24_cm=40), _r(id="b", ime="Beta", past24_cm=6, temp_c=1.0), _r(id="c", ime="Ceta"), _r(id="d", ime="Deta", next24_cm=12, drzava="SI")]
_pw = [_r(id="w1", ime="Wuno", drzava="JP", past24_cm=60, past72_cm=100)]
_ph = g.powder_html(_pa, _pw)
check(_ph.index("Wuno") < _ph.index("Alfa") < _ph.index("Beta") < _ph.index("Deta"), "izris: vrstni red Wuno (60), Alfa (40), Beta (6), Deta (prihaja)")
check("Ceta" not in _ph, "izris: točka brez snega ni na seznamu")
check('href="#w-w1"' in _ph and 'href="#t-a"' in _ph, "izris: povezave na kartice (alpske #t-, svetovne #w-)")
check("Vse (4)" in _ph and "Powder alert (2)" in _ph and "Sneg prihaja (1)" in _ph and 'data-pg="japonska"' in _ph and 'data-pg="si"' in _ph
      and 'data-pg="amerika"' not in _ph, "izris: števila v filtrih in samo prisotna območja")
check("modelski potencial" in _ph.lower() and "ne izmerjena kakovost" in _ph, "izris: pove, da je modelski potencial")
check(f"{g.PW_POWDER_CM} cm" in _ph and f"{g.PW_GUST_KMH} km/h" in _ph, "izris: »Kako razvrščamo« navaja meje iz konstant")
check("ni dovolj novega snega" in g.powder_html([_r()], None), "izris: brez uvrščenih točk je stavek brez trditve o snegu")
check(g.powder_html([_r()], None).count("<li class=\"sg-pw-i\"") == 0, "izris: brez točk ni vrstic")
_faq = " ".join(a for q, a in g.FAQ if "Powder Tracker" in q)
check(f"{g.PW_POWDER_CM} cm" in _faq and f"{g.PW_FRESH72_CM} cm" in _faq and f"{g.PW_WAIT72_CM} cm" in _faq, "FAQ Powder Tracker navaja iste meje kot razvrstitev")

# veter v podatkih (iz Open-Meteo hourly; brez polja ostane None)
_h = series(1500, {})
_h["wind_speed_10m"] = [12.4] * N
_h["wind_gusts_10m"] = [None] * N
_cp = d.compute_point(_h, IDX, 1400)
check(_cp["wind_kmh"] == 12 and _cp["gust_kmh"] is None, "podatki: veter se zaokroži, manjkajoč sunek je None")
check("wind_speed_10m" in d.HOURLY and "wind_gusts_10m" in d.HOURLY, "podatki: veter je v zahtevi Open-Meteo")
_h2 = series(1500, {})
_cp2 = d.compute_point(_h2, IDX, 1400)
check(_cp2["wind_kmh"] is None and _cp2["gust_kmh"] is None, "podatki: brez polj vetra ostane None")
_gen = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "snegofili", "snegofili.js"), encoding="utf-8").read()
check("sg-pw-f" in _gen and "sg-pw-list" in _gen, "JS: filter Powder Trackerja")


# ── namestitev kot aplikacija: manifest z obsegom /snegofili/, ikone, gumb, JS ──
_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
_man = json.load(open(os.path.join(_root, "snegofili", "manifest.json"), encoding="utf-8"))
check(_man["scope"] == "/snegofili/" and _man["id"] == "/snegofili/" and _man["start_url"].startswith("/snegofili/"),
      "manifest: obseg in id sta /snegofili/ (namestitev ne sme postati aplikacija Meteorec s korena)")
check(_man["display"] == "standalone" and _man["short_name"] == "Snegofili", "manifest: standalone in kratko ime")
_sizes = {(i["sizes"], i["purpose"]) for i in _man["icons"]}
check({("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")} <= _sizes, "manifest: ikone 192, 512 in maskable")
check(all(os.path.exists(os.path.join(_root, i["src"].lstrip("/"))) for i in _man["icons"]), "manifest: vse ikone obstajajo")
_sg_head = g.head_extras("")
check('<link rel="manifest" href="/snegofili/manifest.json">' in _sg_head and 'apple-mobile-web-app-title" content="Snegofili"' in _sg_head,
      "glava: povezava na manifest in iOS oznake")
_gen_src = open(os.path.join(_root, "tools", "generate_snegofili_page.py"), encoding="utf-8").read()
check('id="sg-install" hidden' in _gen_src and 'id="sg-install-hint"' in _gen_src and "sg-install-t" in _gen_src,
      "generator: gumb Namesti je privzeto skrit, opomba za iOS obstaja")
_js2 = open(os.path.join(_root, "snegofili", "snegofili.js"), encoding="utf-8").read()
check("beforeinstallprompt" in _js2 and "appinstalled" in _js2 and "display-mode: standalone" in _js2, "JS: namestitveni tok (prompt, appinstalled, že nameščeno)")



# ── Slovenija po regijah, snežna sezona, dnevnik (22. 11. 2026) ──
import tempfile  # noqa: E402
import log_snegofili_sezona as lg  # noqa: E402
import winter_engine as _we  # noqa: E402

check(_we.SNOW_RATIO_CM_PER_MM == 1.0, "razmerje 1 mm ≈ 1 cm: besedilo na strani ('1 mm padavin ≈ 1 cm') zahteva razmerje 1,0")
_days = lg.complete_days("2026-11-22T14:00")
check([x[0] for x in _days] == ["2026-11-20", "2026-11-21"], f"dnevnik: polna dneva sta 20. in 21. 11. ({[x[0] for x in _days]})")
check(_days[0][1:] == (10, 33) and _days[1][1:] == (34, 57), f"dnevnik: indeksi žigov dneva (01:00 … 00:00) ({[x[1:] for x in _days]})")
check(lg.complete_days("2026-07-22T14:00") == [], "dnevnik: julij ni v sezoni")
_late = lg.complete_days("2026-11-22T01:00")   # žig 22. 11. 00:00 je ura nazaj: 21. 11. je poln
check(any(x[0] == "2026-11-21" for x in _late), "dnevnik: dan, ki se je iztekel pred več kot uro, je poln")
_early = lg.complete_days("2026-11-22T00:00")  # zadnji žig dneva je zdaj, ura še teče
check(all(x[0] != "2026-11-21" for x in _early), "dnevnik: dan, katerega zadnji žig je prav zdaj, še ni poln")
_sn = [0] * 144
_sn[20] = 5     # 20. 11. (indeksi 10..33): 0,5 cm
_sn[40] = 12    # 21. 11. (34..57): 1,2 cm
_sn[71] = 99    # ura, ki teče: ne sme v nobeden dan
_tot = lg.day_totals({"x": {"sn": _sn}, "y": {"sn": [None] * 144}}, _days)
check(_tot == {("2026-11-20", "x"): 0.5, ("2026-11-21", "x"): 1.2}, f"dnevnik: seštevek po dnevih, vrzel v seriji ni nič ({_tot})")
with tempfile.TemporaryDirectory() as _td:
    _pth = os.path.join(_td, "s.csv")
    lg.write_log({("2026-11-21", "b"): 1.2, ("2026-11-20", "a"): 0.0}, _pth)
    _rl = lg.read_log(_pth)
    check(_rl == {("2026-11-21", "b"): 1.2, ("2026-11-20", "a"): 0.0}, "dnevnik: zapis in branje CSV")
    _rl.update({("2026-11-21", "b"): 2.0})
    lg.write_log(_rl, _pth)
    check(lg.read_log(_pth)[("2026-11-21", "b")] == 2.0 and len(lg.read_log(_pth)) == 2, "dnevnik: poznejši tek prepiše vrednost dneva")
check(lg.read_log("/nonexistent/x.csv") == {}, "dnevnik: brez datoteke je prazen")

_st = g.season_totals({("2026-11-20", "a"): 0.5, ("2026-11-21", "a"): 3.0, ("2026-11-21", "b"): 0.0, ("2026-04-10", "a"): 9.0})
check(_st["season"] == "2026/27" and _st["first"] == "2026-11-20" and _st["days"] == 2, "sezona: zadnja sezona, aprilski dan stare sezone ne šteje")
_ra = {p["id"]: p for p in _st["rows"]}
check(abs(_ra["a"]["total"] - 3.5) < 1e-9 and _ra["a"]["days_snow"] == 1 and _ra["a"]["best_date"] == "2026-11-21", "sezona: skupaj, dnevi ≥ 1 cm, najmočnejši dan")
check(_ra["b"]["best_date"] is None and _ra["b"]["days_snow"] == 0, "sezona: brez snega ni najmočnejšega dne")
check(g.season_totals({}) is None, "sezona: brez dnevnika ni seštevka")
check(g.season_start_year("2027-02-01") == 2026 and g.season_start_year("2026-10-01") == 2026 and g.season_start_year("2026-09-30") == 2025,
      "sezona: začne se 1. oktobra")
_ar = g.arso_seasons([["2025-09-30", 50.0, 0.0, 0], ["2025-10-05", 0.0, 0.0, 0], ["2025-12-01", 4.0, 4.0, 1], ["2025-12-02", None, None, None],
                      ["2025-12-03", 10.0, None, 2], ["2026-05-01", 30.0, 0.0, 0], ["2026-11-02", 1.0, 1.0, 0]])
check([s["sy"] for s in _ar] == [2026, 2025], "ARSO zime: sezone od najnovejše, dnevi zunaj 1. 10.–30. 4. ne štejejo")
_s25 = _ar[1]
check(_s25["n"] == 3 and _s25["max"] == 10.0 and _s25["max_d"] == "2025-12-03" and _s25["cover"] == 2 and _s25["new"] == 4.0 and _s25["new_n"] == 2,
      f"ARSO zime: samo dnevi z meritvijo, ničla je meritev ({_s25})")

check(g.next_hours_cm({"sn": [0] * 71 + [90] + [10] * 48 + [0] * 24}, 48) == 48.0, "regije: ura, ki teče, se ne šteje v 48 ur naprej")
check(g.next_hours_cm({"sn": [0] * 100}, 48) is None and g.next_hours_cm(None, 48) is None, "regije: kratka ali manjkajoča serija ni nič")
_rows = [
    {"id": "p1", "ime": "Prva", "drzava": "SI", "regija": "Savinjska in Štajerska", "past24_cm": 2.0, "next24_cm": 0.0, "snow_line_m": 1000, "precip_now_mm": 0.4, "snow_now_possible": True},
    {"id": "p2", "ime": "Druga", "drzava": "SI", "regija": "Savinjska in Štajerska", "past24_cm": 5.0, "next24_cm": 1.0, "snow_line_m": 1200, "precip_now_mm": 0.0, "snow_now_possible": True,
     "izmerjeno": {"depth_cm": 7}},
    {"id": "p3", "ime": "Tuja", "drzava": "AT", "regija": "Tirolska", "past24_cm": 50.0, "next24_cm": 9.0, "snow_line_m": 800, "precip_now_mm": 1.0, "snow_now_possible": True},
]
_rs = g.region_summary(_rows, {"p1": {"sn": [0] * 72 + [10] * 48}, "p2": {"sn": [0] * 144}})
check(len(_rs) == 1 and _rs[0]["regija"] == "Savinjska in Štajerska" and _rs[0]["n"] == 2, "regije: samo Slovenija")
check(_rs[0]["past24"] == (5.0, "Druga") and _rs[0]["next48"] == (48.0, "Prva") and _rs[0]["snowing"] == ["Prva"] and _rs[0]["measured"] == (7, "Druga"),
      f"regije: največ po točkah, sneženje zdaj samo ob padavinah in snegu, meritev ({_rs[0]})")
check(_rs[0]["line"] == 1200, "regije: mediana meje sneženja (višji srednji pri sodem številu)")
_sl = g.slovenija_html(_rows)
check("Slovenija po regijah" in _sl and "Tuja" not in _sl and "Karavanke in Pohorje" in _sl, "regije: razdelek, brez tujih točk, razlaga o Karavankah in Pohorju")
check(g.slovenija_html([{"drzava": "AT"}]) == "", "regije: brez slovenskih točk ni razdelka")
_page = open(os.path.join(_root, "snegofili", "index.html"), encoding="utf-8").read()
for _id in ("slovenija", "sezona"):
    check(f'<section id="{_id}"' in _page and f'href="#{_id}"' in _page, f"stran: razdelek #{_id} in povezava v navigaciji")
check("Kako računamo nov sneg" in _page and "Kako so izbrane lokacije" in _page and "Zakaj 1 mm padavin ni vedno 1 cm snega?" in _page,
      "stran: razlaga razmerja 1 mm ≈ 1 cm in izbire lokacij")
check("indoor" not in _page.lower() and "tempinf" not in _page.lower(), "stran: brez notranjih meritev")
_wf = open(os.path.join(_root, ".github", "workflows", "zima-forecast.yml"), encoding="utf-8").read()
check("log_snegofili_sezona.py" in _wf and "data/snegofili-sezona.csv" in _wf, "workflow: dnevnik sezone se zapiše in commita")


# ── južna polobla (23. 11. 2026) ──
_css = open(os.path.join(_root, "snegofili", "snegofili.css"), encoding="utf-8").read()
check(all(f"[data-c={c}]" in _css for c in g.COUNTRIES_WORLD), "južna polobla: vsaka država iz Po svetu ima zastavico v CSS")
check({c for _, cs in g.WORLD_GROUPS for c in cs} == set(g.COUNTRIES_WORLD), "južna polobla: vsaka država je v natanko eni skupini Po svetu")
_sr = [dict(drzava="NZ"), dict(drzava="JP")]
check(g.south_note(_sr, month=11) != "" and g.south_note(_sr, month=7) == "" and g.south_note([dict(drzava="JP")], month=11) == "",
      "južna polobla: opomba o sezoni samo zunaj junija–septembra in samo ob točkah juga")
check(g.powder_groups(_r(drzava="NZ"), True) == "juzna" and g.powder_groups(_r(drzava="CL"), True) == "juzna", "južna polobla: skupina območja v Powder Trackerju")


# ── snežni dogodki iz dnevnika (23. 11. 2026) ──
_cb = {"a": "AT", "b": "AT", "c": "AT", "d": "SI", "e": "SI"}
_lg = {("2026-11-20", "a"): 12, ("2026-11-20", "b"): 15, ("2026-11-20", "c"): 11, ("2026-11-20", "d"): 1,
       ("2026-11-21", "a"): 20, ("2026-11-21", "b"): 10, ("2026-11-21", "c"): 10.5, ("2026-11-21", "d"): 6, ("2026-11-21", "e"): 5,
       ("2026-11-22", "a"): 12, ("2026-11-22", "b"): 12, ("2026-11-22", "c"): 12, ("2026-11-22", "e"): 0,
       ("2026-11-24", "a"): 14, ("2026-11-24", "b"): 14, ("2026-11-24", "c"): 14,
       ("2026-11-26", "a"): 12, ("2026-11-26", "b"): 12}                                   # samo 2 točki: prag 3 ni dosežen          # dan 23. ni zabeležen: vrzel prekine, nov dogodek
_ev = g.snow_events(_lg, _cb)
_al = [e for e in _ev if e["scope"] == "alpe"]
check([(e["start"], e["end"]) for e in _al] == [("2026-11-24", "2026-11-24"), ("2026-11-20", "2026-11-22")], f"dogodki: Alpe, vrzel v dnevniku prekine dogodek ({[(e['start'], e['end']) for e in _al]})")
check(_al[1]["days"] == 3 and _al[1]["points"] == 3 and _al[1]["peak"] == (20, "a", "2026-11-21"), f"dogodki: dnevi, točke, najmočnejši dan ({_al[1]})")
check(abs(_al[1]["totals"]["a"] - 44) < 1e-9, "dogodki: skupaj v dogodku po točki")
_sl = [e for e in _ev if e["scope"] == "slovenija"]
check(len(_sl) == 1 and _sl[0]["start"] == "2026-11-21" and _sl[0]["points"] == 2, f"dogodki: Slovenija ima nižji prag (5 cm na 2 točkah) ({_sl})")
check(g.snow_events({}, _cb) == [], "dogodki: brez dnevnika ni dogodkov")
check("Snežni dogodki sezone" in _page and 'href="#dogodki"' in _page, "stran: razdelek Snežni dogodki in povezava v navigaciji")

print("OK" if not fails else f"{fails} napak")
sys.exit(1 if fails else 0)
