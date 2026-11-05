#!/usr/bin/env python3
"""Test kartice »Zakaj je danes takšno vreme?« (generateWhyWeather v app.js, 5. 11. 2026).

Kartica ni več odstavek, ampak tri ploščice (tlačni sistem, zrak v dolini, kaj sledi). Preverja:
  - pri vseh kombinacijah vhodov nastanejo natanko tri ploščice z naslovom, besedilom in ikono iz sklada;
  - v izhodu ni `undefined`, `NaN`, emojijev ali decimalne pike (Pravopis: vejica);
  - vsaka veja pogojev (pragovi so isti kot v prejšnjem odstavku) da pričakovan naslov;
  - lestvici sta v mejah 0–100 %;
  - HTML skelet (index.html) ima tri ploščice, ker se mora ujemati z izrisom (CLS).
Resnična koda se izreže iz app.js (tools/_parity_js.mjs), ne kopija.
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FAILS = []
CHECKS = 0


def check(ok, name, detail=""):
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILS.append(name)
        print(f"  ✗ {name}  {detail}"[:400])


# `hour` in zgodovina tlaka se podtaknejo prek lažnega Date in _pressureHistory.
PRELUDE = r"""
var _ico=n=>'<svg class="ic"><use href="#i-'+n+'"/></svg>';
var _pressureHistory=[];
var __hour=10;
var __RealDate=Date;
Date=class extends __RealDate{constructor(...a){super(...(a.length?a:[2026,10,5,__hour,0,0]));}
  static now(){return new __RealDate(2026,10,5,__hour,0,0).getTime();}};
var __out={html:'',upd:''};
var document={getElementById:id=>id==='why-text'?{set innerHTML(v){__out.html=v;}}:id==='why-updated'?{set textContent(v){__out.upd=v;}}:null};
function __run(o){
  __hour=o.hour;
  _pressureHistory.length=0;
  if(o.trend!=null){_pressureHistory.push({t:Date.now()-3*3600000,p:o.pres-o.trend});}
  generateWhyWeather({humidity:o.hum,metric:{temp:o.T,dewpt:o.Td,windSpeed:o.wind,pressure:o.pres,precipRate:o.rain}});
  return __out.html;
}
"""

# (ime, vhod, pričakovani naslovi ploščic 1, 2, 3)
CASES = [
    ("anticiklon, megla, dvig dopoldne", dict(hour=8, hum=99, T=7.0, Td=6.9, wind=0, pres=1027, rain=0, trend=0.1),
     ("Anticiklon", "Pogoji za meglo", "Megla se dvigne dopoldne")),
    ("hiter padec tlaka", dict(hour=15, hum=70, T=18, Td=10, wind=12, pres=1008, rain=0, trend=-3.0),
     ("Tlak hitro pada", None, "Poslabšanje vremena")),
    ("postopen padec", dict(hour=15, hum=60, T=18, Td=8, wind=10, pres=1012, rain=0, trend=-1.5),
     ("Tlak postopno pada", None, None)),
    ("tlak narašča", dict(hour=15, hum=60, T=15, Td=5, wind=10, pres=1012, rain=0, trend=2.0),
     ("Tlak narašča", None, None)),
    ("nizek tlak z dežjem", dict(hour=15, hum=70, T=10, Td=6, wind=10, pres=1000, rain=2, trend=0.0),
     ("Območje nizkega tlaka", "Dvig ob pobočjih", "Padavine slabijo")),
    ("stabilno, suh dan", dict(hour=11, hum=50, T=20, Td=8, wind=8, pres=1021, rain=0, trend=0.0),
     ("Stabilno ozračje", "Razmeroma suh zrak", "Stabilno do večera")),
    ("slana", dict(hour=6, hum=75, T=1.0, Td=-1.5, wind=8, pres=1014, rain=0, trend=0.0),
     (None, "Možna slana ali ivje", None)),
    ("hladna noč z inverzijo", dict(hour=21, hum=70, T=6.0, Td=0.0, wind=2, pres=1017, rain=0, trend=0.0),
     (None, "Temperaturna inverzija", "Hladna in mirna noč")),
    ("močan veter", dict(hour=14, hum=55, T=14, Td=4, wind=30, pres=1013, rain=0, trend=0.0),
     (None, "Veter premeša ozračje", None)),
    ("nasičen zrak", dict(hour=14, hum=88, T=9, Td=7, wind=10, pres=1013, rain=0, trend=0.0),
     (None, "Zrak je nasičen z vlago", None)),
    ("poletna konvekcija", dict(hour=15, hum=65, T=27, Td=17, wind=10, pres=1013, rain=0, trend=0.0),
     (None, None, "Možne popoldanske plohe")),
    ("brez zgodovine tlaka", dict(hour=12, hum=60, T=15, Td=6, wind=10, pres=1013, rain=0, trend=None),
     ("Prehodno stanje", None, None)),
]

calls = [{"expr": f"__run({json.dumps(c[1])})"} for c in CASES]
p = subprocess.run(["node", os.path.join(HERE, "_parity_js.mjs")],
                   input=json.dumps({"file": "app.js", "names": ["_whyTile", "generateWhyWeather"], "prelude": PRELUDE, "calls": calls}),
                   capture_output=True, text=True, cwd=ROOT, timeout=120)
try:
    out = json.loads(p.stdout)
except ValueError:
    print("node:", p.stdout[:300], p.stderr[:400]); sys.exit(1)
if "error" in out:
    print("napaka:", out["error"]); sys.exit(1)

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿✅⏱]")
for (name, _inp, titles), html in zip(CASES, out["results"]):
    n_tiles = html.count('class="why-tile"')
    check(n_tiles == 3, f"{name}: ploščic {n_tiles}, pričakovane 3")
    got = re.findall(r'class="why-tile-title">([^<]+)<', html)
    check(len(got) == 3, f"{name}: naslovov {len(got)}", str(got))
    for i, (want, have) in enumerate(zip(titles, got)):
        if want is not None:
            check(have == want, f"{name}: ploščica {i + 1} je »{have}«, pričakovano »{want}«")
    check("undefined" not in html and "NaN" not in html and "null" not in html, f"{name}: undefined/NaN/null v izhodu")
    check(not EMOJI.search(html), f"{name}: emoji v izhodu (ikone morajo biti iz sklada)")
    visible = re.sub(r"<[^>]+>", "", html)
    check(not re.search(r"\d\.\d", visible), f"{name}: decimalna pika v besedilu", visible[:200])
    for pos in re.findall(r"--p:([0-9.]+)%", html):
        check(0 <= float(pos) <= 100, f"{name}: lestvica izven 0–100 %: {pos}")
    check(html.count('class="ic"') >= 3, f"{name}: ikone iz sklada manjkajo")
    check("ni napoved" in html, f"{name}: manjka nota, da razlaga ni napoved")

# skelet v index.html: tri ploščice (višina je rezervirana, sicer CLS)
with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
    idx = f.read()
m = re.search(r'id="why-text">(.*?)<span class="visually-hidden">Nalaganje razlage', idx, re.S)
check(m is not None and m.group(1).count('class="why-tile"') == 3, "index.html: skelet kartice »Zakaj …« nima treh ploščic")

print(f"{CHECKS} preverjanj, {len(FAILS)} napak")
sys.exit(1 if FAILS else 0)
