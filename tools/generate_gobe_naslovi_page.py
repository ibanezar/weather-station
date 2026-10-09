#!/usr/bin/env python3
"""
tools/generate_gobe_naslovi_page.py — SKRITA stran z današnjimi kandidati za objavo v
gobjih FB skupinah: gobarska-napoved/orodje-naslovi/index.html

Samo za lastnika: noindex, ni v sitemapu, ni v CORE, ni povezave z nobene strani.
Predloge in ocene so v tools/gobe_naslovi.py (ena sama implementacija, ročni CLI in
ta stran). Stran je statična — kandidate in izbiro člankov vgradi v HTML; JS samo
sestavi povezavo z UTM za izbran članek in kopira besedilo (textContent, nikoli innerHTML).

Teče v gobe-forecast.yml takoj za generate_gobe_page.py (isti git add gobarska-napoved/).
Ob napaki (npr. izbirnik še ne vsebuje današnjega dne) stare strani ne povozi.
"""
import datetime
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gobe_naslovi as gn  # noqa: E402

OUT = os.path.join(gn.ROOT, "gobarska-napoved", "orodje-naslovi", "index.html")
N_POSTS = 8


def gobe_posts():
    posts = gn.load(os.path.join(gn.ROOT, "blog.json"))
    posts = posts if isinstance(posts, list) else posts.get("posts", [])
    out = [p for p in posts if "gob" in p.get("slug", "").lower()][:N_POSTS]
    return [{"slug": p["slug"], "title": p["title"], "url": p["url"]} for p in out]


PAGE = """<!doctype html>
<html lang="sl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Naslovi za gobje skupine</title>
<style>
:root{--bg:#fff;--fg:#1a1d21;--mut:#5b6470;--card:#f4f6f8;--bd:#d9dee4;--ac:#047857;--acfg:#fff}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0e1216;--fg:#e8ecef;--mut:#9aa5b1;--card:#171d23;--bd:#2a333c;--ac:#34d399;--acfg:#06281c}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
main{max-width:720px;margin:0 auto;padding:16px}
h1{font-size:1.3rem;margin:.2em 0}
.meta{color:var(--mut);font-size:.9rem;margin-bottom:12px}
label{display:block;font-size:.85rem;color:var(--mut);margin:12px 0 4px}
select{width:100%;padding:10px;font-size:1rem;border:1px solid var(--bd);border-radius:8px;background:var(--card);color:var(--fg)}
.c{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:14px;margin:12px 0}
.t{font-weight:700;font-size:1.05rem}
.s{color:var(--mut);font-size:.8rem;margin:2px 0 8px}
.i{margin:0 0 10px}
.b{display:flex;gap:8px;flex-wrap:wrap}
button{font:inherit;padding:10px 14px;border-radius:8px;border:1px solid var(--bd);background:transparent;color:var(--fg);cursor:pointer;min-height:44px}
button.p{background:var(--ac);color:var(--acfg);border-color:var(--ac);font-weight:600}
.ok{color:var(--ac);font-size:.85rem;align-self:center}
.warn{background:var(--card);border-left:4px solid #d97706;padding:8px 12px;border-radius:6px;margin:12px 0;font-size:.9rem}
</style>
</head>
<body>
<main>
<h1>Naslovi za gobje skupine</h1>
<div class="meta" id="meta"></div>
<div id="warn"></div>
<label for="post">Članek, na katerega vodi povezava</label>
<select id="post"></select>
<div id="list"></div>
<p class="meta">Zasebna stran. Številke so modelski indeks in meritve postaje IREICA1; nobenih notranjih meritev.
Naslov kartice v skupini FB vzame iz članka (og:title), ne iz te strani — tu je uvodni stavek nad povezavo.</p>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
(function(){
var D=JSON.parse(document.getElementById('data').textContent);
var $=function(i){return document.getElementById(i)};
$('meta').textContent='Datum: '+D.datum+' · dolina '+D.overall+' % ('+D.level+') · ustvarjeno '+D.generated;
if(D.stale){var w=document.createElement('div');w.className='warn';w.textContent=D.stale;$('warn').appendChild(w)}
var sel=$('post');
D.posts.forEach(function(p,i){var o=document.createElement('option');o.value=i;o.textContent=p.title;sel.appendChild(o)});
function link(c){var p=D.posts[sel.value];
 return 'https://meteorec.si'+p.url+'?utm_source=facebook&utm_medium=group&utm_campaign=gn-'+encodeURIComponent(c.id)}
function copy(text,note){
 var done=function(){note.textContent='Kopirano';setTimeout(function(){note.textContent=''},1800)};
 if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(text).then(done,fallback)}else fallback();
 function fallback(){var t=document.createElement('textarea');t.value=text;document.body.appendChild(t);t.select();
  try{document.execCommand('copy');done()}catch(e){note.textContent='Kopiranje ni uspelo'}document.body.removeChild(t)}}
function el(tag,cls,txt){var e=document.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e}
function render(){var L=$('list');L.textContent='';
 D.cands.forEach(function(c){
  var card=el('div','c');
  card.appendChild(el('div','t',c.title));
  card.appendChild(el('div','s','ocena '+c.score+' · '+c.len+' znakov · '+c.id));
  card.appendChild(el('p','i',c.intro));
  var b=el('div','b'),note=el('span','ok','');
  var b1=el('button','p','Kopiraj objavo (uvod + povezava)');
  b1.onclick=function(){copy(c.intro+'\\n\\n'+link(c),note)};
  var b2=el('button','','Kopiraj povezavo');
  b2.onclick=function(){copy(link(c),note)};
  b.appendChild(b1);b.appendChild(b2);b.appendChild(note);card.appendChild(b);L.appendChild(card)})}
sel.onchange=render;render();
})();
</script>
</body>
</html>
"""


def main():
    F = gn.gather()
    cands = [c for c in gn.build(F) if c["score"] >= 7] or gn.build(F)[:3]
    stale = None
    if F["last_obs"] and (F["today"] - F["last_obs"]).days > 2:
        stale = f"history.json zaostaja ({F['last_obs']}) — številke o dežju so lahko zastarele."
    data = {
        "datum": F["today"].isoformat(), "overall": F["overall"], "level": F["level"],
        "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "stale": stale, "posts": gobe_posts(),
        "cands": [{k: c[k] for k in ("id", "title", "intro", "score", "len")} for c in cands],
    }
    # </ in JSON bi zaprl <script>; ensure_ascii=False ohrani šumnike.
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(PAGE.replace("__DATA__", blob))
    print(f"✓ {OUT} ({len(cands)} kandidatov, {len(data['posts'])} člankov)")


if __name__ == "__main__":
    main()
