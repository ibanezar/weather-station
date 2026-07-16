#!/usr/bin/env python3
"""
tools/generate_gobe_page.py — Gobarska napoved: freemium sales + forecast page

Renders /gobarska-napoved/index.html: a server-rendered mushroom-foraging
landing page for Zgornja Savinjska dolina built on the species-level model
(tools/gobe_model.py) and the 50-species local database (species_rules.yaml).

Layout:
  * FREE (public, crawlable): today's overall index, today's index per forest,
    the 50-species reference table with edibility + dangerous doubles, the
    monthly calendar, the terrain map and FAQ. Strong SEO + mycological
    credibility, all static HTML.
  * PREMIUM (gated): the forward-looking 7-day, per-species, per-location
    forecast with plain-language explanations. Rendered as a locked placeholder;
    the real content is fetched client-side from the Worker /premium/forecast
    endpoint only when a valid access token is present.

Positioning: the index is an "indeks ugodnosti pogojev" (favourability index),
never a promise of finds — scientifically honest and it protects against angry
subscribers.

Usage:
  python3 tools/generate_gobe_page.py
"""
import datetime as _dt
import os
import sys
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers
import gobe_model as gm           # noqa: E402 — species model + DB loader

ROOT = seo.ROOT
TODAY = seo.TODAY

# Cloudflare Worker base (paywall API). Same host as the rest of the site proxy.
WORKER_BASE = "https://weatherireica1.filip-eremita.workers.dev"

# Paddle.js overlay checkout — fill in after creating the products (docs/premium-setup.md).
# The client-side token is safe to expose publicly. Price IDs must match wrangler.toml.
# TODO: nastavi Paddle vrednosti; dokler je token prazen, gumbi varno padejo na #pricing.
PADDLE_ENV = "production"            # "sandbox" za testiranje, "production" za v živo
PADDLE_CLIENT_TOKEN = ""             # TODO: odjemalski žeton iz Paddle (Developer Tools → Authentication)
PADDLE_PRICE_MONTHLY = "pri_REPLACE_MONTHLY"  # TODO: enako kot v wrangler.toml
PADDLE_PRICE_SEASON = "pri_REPLACE_SEASON"    # TODO: enako kot v wrangler.toml

PRICE_MONTHLY = "3,99 €"
PRICE_SEASON = "24,99 €"

MES_FULL = ["januarju", "februarju", "marcu", "aprilu", "maju", "juniju",
            "juliju", "avgustu", "septembru", "oktobru", "novembru", "decembru"]
DAN_KRATKO = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]

# Edibility → (badge label, CSS colour class)
EDIB_STYLE = {
    "užitna":          ("Užitna", "e-ok"),
    "pogojno užitna":  ("Pogojno užitna", "e-cond"),
    "neužitna":        ("Neužitna", "e-none"),
    "strupena":        ("Strupena", "e-tox"),
    "zelo strupena":   ("Zelo strupena", "e-tox2"),
    "smrtno strupena": ("Smrtno strupena", "e-death"),
    "zaščitena":       ("Zaščitena", "e-prot"),
}


def edib_badge(edibility):
    label, cls = EDIB_STYLE.get((edibility or "").lower().strip(), (edibility or "?", "e-none"))
    return f'<span class="gp-badge {cls}">{seo.esc(label) if hasattr(seo, "esc") else label}</span>'


def _esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def season_months(sp):
    """Set of 1-12 month numbers the species' season window covers."""
    out = set()
    for m in range(1, 13):
        # 15th of the month as representative day
        if gm.in_season(_dt.date(2025, m, 15), sp["season"]):
            out.add(m)
    return out


# ── page CSS (scoped, appended in <head>) ─────────────────────────────────────

PAGE_CSS = """<style>
.gp-hero{background:var(--card-bg);border:1px solid var(--card-border);border-radius:18px;
  padding:1.4rem 1.5rem;margin:.6rem 0 1.2rem;box-shadow:var(--card-shadow)}
.gp-hero-top{display:flex;align-items:center;gap:1.2rem;flex-wrap:wrap}
.gp-gauge{font-size:3.2rem;font-weight:800;line-height:1;color:var(--green)}
.gp-gauge small{font-size:1.1rem;color:var(--muted);font-weight:600}
.gp-hero-lvl{font-size:1.05rem;font-weight:700;letter-spacing:.02em}
.gp-hero-sub{color:var(--muted);font-size:.9rem;margin-top:.35rem;line-height:1.55}
.gp-cta{display:inline-block;background:var(--blue);color:#04070e;font-weight:700;font:inherit;
  font-weight:700;padding:.6rem 1.2rem;border-radius:10px;text-decoration:none;margin-top:.4rem;
  border:0;cursor:pointer;line-height:1.2}
.gp-cta.alt{background:transparent;color:var(--blue);border:1px solid var(--blue)}
.gp-forests{display:grid;gap:.5rem;margin:.6rem 0 1rem}
.gp-forest{display:flex;align-items:center;justify-content:space-between;gap:.8rem;
  background:var(--fc-bg);border:1px solid var(--fc-border);border-radius:10px;padding:.55rem .8rem}
.gp-forest b{font-variant-numeric:tabular-nums}
.gp-terr{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.gp-lock{position:relative;border:1px dashed var(--card-border);border-radius:16px;
  padding:1.3rem;margin:.6rem 0 1rem;background:linear-gradient(180deg,rgba(77,159,248,.06),transparent)}
.gp-lock h3{margin:.1rem 0 .3rem}
.gp-skel{filter:blur(3px);opacity:.5;pointer-events:none;user-select:none;margin:.7rem 0}
.gp-skel .gp-forest{background:var(--badge-bg)}
.gp-lockbar{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center;margin-top:.8rem}
.gp-login{display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.6rem}
.gp-login input{flex:1;min-width:180px;background:var(--badge-bg);border:1px solid var(--card-border);
  border-radius:9px;padding:.5rem .7rem;color:var(--text);font-size:.9rem}
.gp-login button{background:var(--blue);color:#04070e;border:0;border-radius:9px;
  padding:.5rem 1rem;font-weight:700;cursor:pointer}
.gp-msg{font-size:.85rem;color:var(--muted);margin-top:.4rem;min-height:1.1em}
.gp-pricing{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:.8rem;margin:.8rem 0}
.gp-plan{background:var(--card-bg);border:1px solid var(--card-border);border-radius:14px;padding:1.1rem;
  display:flex;flex-direction:column;gap:.5rem;box-shadow:var(--card-shadow)}
.gp-plan.best{border-color:var(--blue);box-shadow:0 0 0 1px var(--blue),var(--card-shadow)}
.gp-plan .p-price{font-size:1.9rem;font-weight:800}
.gp-plan .p-price small{font-size:.85rem;color:var(--muted);font-weight:600}
.gp-plan ul{margin:.2rem 0;padding-left:1.1rem;color:var(--muted);font-size:.88rem;line-height:1.7}
.gp-tag{display:inline-block;font-size:.7rem;font-weight:700;color:var(--blue);
  border:1px solid var(--blue);border-radius:6px;padding:.05rem .4rem;align-self:flex-start}
.gp-badge{display:inline-block;font-size:.72rem;font-weight:700;padding:.08rem .45rem;border-radius:6px;white-space:nowrap}
.e-ok{background:rgba(52,211,153,.15);color:var(--green)}
.e-cond{background:rgba(245,158,11,.15);color:var(--amber)}
.e-none{background:var(--badge-bg);color:var(--muted)}
.e-tox,.e-tox2{background:rgba(248,113,113,.16);color:#f87171}
.e-death{background:rgba(248,113,113,.28);color:#fecaca;font-weight:800}
.e-prot{background:rgba(167,139,250,.18);color:var(--purple)}
.gp-sptable{width:100%;border-collapse:collapse;font-size:.86rem}
.gp-sptable th,.gp-sptable td{text-align:left;padding:.4rem .5rem;border-bottom:1px solid var(--border);vertical-align:top}
.gp-sptable th{color:var(--muted);font-weight:600;position:sticky;top:0;background:var(--bg)}
.gp-sptable .lat{color:var(--muted);font-style:italic;font-size:.8rem}
.gp-scroll{max-height:560px;overflow:auto;border:1px solid var(--card-border);border-radius:12px}
.gp-dbl{color:var(--muted);font-size:.8rem}
.gp-terrmap{display:grid;gap:.6rem;margin:.6rem 0}
.gp-terrmap .t{background:var(--card-bg);border:1px solid var(--card-border);border-radius:12px;padding:.8rem 1rem}
.gp-terrmap .t b{color:var(--text)}
.gp-matrix{width:100%;border-collapse:collapse;font-size:.8rem}
.gp-matrix th,.gp-matrix td{padding:.3rem .35rem;text-align:center;border-bottom:1px solid var(--border)}
.gp-matrix td.nm{text-align:left;white-space:nowrap}
.gp-cell{display:inline-block;min-width:2.1em;border-radius:5px;padding:.1rem .2rem;font-variant-numeric:tabular-nums}
.gp-disc{font-size:.82rem;color:var(--muted);border-left:3px solid var(--amber);padding:.3rem .8rem;margin:1rem 0}
</style>"""

# ── client-side paywall JS ────────────────────────────────────────────────────

PAGE_JS = """<script>
(function(){
  var API=""" + '"' + WORKER_BASE + '"' + """;
  var LS="mr_gobe_token";
  function tok(){
    try{
      var u=new URL(location.href);
      var t=u.searchParams.get("token");
      if(t){localStorage.setItem(LS,t);u.searchParams.delete("token");
        history.replaceState({},"",u.pathname+u.search+u.hash);}
      return localStorage.getItem(LS);
    }catch(e){return null;}
  }
  var lock=document.getElementById("gp-lock");
  var content=document.getElementById("gp-content");
  var statusEl=document.getElementById("gp-premium-status");
  function color(v){
    if(v>=75)return"rgba(52,211,153,.28)";if(v>=55)return"rgba(52,211,153,.16)";
    if(v>=35)return"rgba(245,158,11,.16)";if(v>=18)return"rgba(248,113,113,.14)";
    return"var(--badge-bg)";
  }
  function render(d){
    var meta=d.species_meta||{};
    var home=(d.locations||[]).filter(function(l){return l.home;})[0]||d.locations[0];
    var html="";
    // today per forest
    html+='<h3>Danes po gozdovih</h3><div class="gp-forests">';
    (d.locations||[]).slice().sort(function(a,b){return b.days[0].overall-a.days[0].overall;})
      .forEach(function(l){var o=l.days[0];var top=o.species[0];
        html+='<div class="gp-forest"><span>'+l.name+' <span class="gp-terr">'+(l.terrain||'')+
          ' · '+l.elev_m+' m</span></span><b>'+o.overall+'% '+o.level+
          (top?' · '+(meta[top.id]?meta[top.id].name_sl:''):'')+'</b></div>';});
    html+='</div>';
    // 7-day matrix for home, top 8 species by today's index
    var top=home.days[0].species.slice(0,8).map(function(s){return s.id;});
    html+='<h3>'+home.name+' — 7-dnevni indeks po vrstah</h3><div class="gp-scroll"><table class="gp-matrix"><thead><tr><th style="text-align:left">Vrsta</th>';
    home.days.forEach(function(day){var dt=new Date(day.date);
      html+='<th>'+(day===home.days[0]?'danes':(dt.getDate()+'.'+(dt.getMonth()+1)+'.'))+'</th>';});
    html+='</tr></thead><tbody>';
    top.forEach(function(id){html+='<tr><td class="nm">'+(meta[id]?meta[id].name_sl:id)+'</td>';
      home.days.forEach(function(day){var s=day.species.filter(function(x){return x.id===id;})[0];
        var v=s?s.index:0;html+='<td><span class="gp-cell" style="background:'+color(v)+'">'+v+'</span></td>';});
      html+='</tr>';});
    html+='</tbody></table></div>';
    // today's carriers with explanation
    html+='<h3>Danes — zakaj (razlage)</h3><ul style="color:var(--muted);font-size:.88rem;line-height:1.7">';
    home.days[0].species.slice(0,6).forEach(function(s){var m=meta[s.id]||{};
      html+='<li><b style="color:var(--text)">'+(m.name_sl||s.id)+' — '+s.index+'%</b>: '+s.explanation+
        (m.doubles?' <span class="gp-dbl">⚠ dvojnica: '+m.doubles+'</span>':'')+'</li>';});
    html+='</ul>';
    content.innerHTML=html;
    content.hidden=false;lock.hidden=true;
  }
  var t=tok();
  if(t){
    fetch(API+"/premium/forecast?token="+encodeURIComponent(t))
      .then(function(r){if(!r.ok)throw 0;return r.json();})
      .then(function(d){render(d);
        if(statusEl){statusEl.hidden=false;statusEl.textContent="✓ Premium dostop aktiven.";}})
      .catch(function(){localStorage.removeItem(LS);});
  }
  var f=document.getElementById("gp-login");
  if(f){f.addEventListener("submit",function(e){e.preventDefault();
    var msg=document.getElementById("gp-login-msg");var em=(f.email.value||"").trim();
    if(!em){return;}msg.textContent="Pošiljam …";
    fetch(API+"/premium/login",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({email:em})}).then(function(r){return r.json();})
      .then(function(x){msg.textContent=x.msg||"Če je e-naslov naročen, smo nanj poslali povezavo za dostop.";})
      .catch(function(){msg.textContent="Napaka pri pošiljanju. Poskusi znova.";});});}

  // ── Paddle.js overlay checkout ──────────────────────────────────────────
  // Config comes from window.MR_PADDLE (injected in <head>); when it or the
  // token is missing, buttons fall back to scrolling to #pricing.
  var cfg=window.MR_PADDLE||null;
  var ready=false;
  if(cfg&&cfg.token&&window.Paddle){
    try{
      if(cfg.env==="sandbox"){Paddle.Environment.set("sandbox");}
      Paddle.Initialize({token:cfg.token});
      ready=true;
    }catch(e){ready=false;}
  }
  function checkoutMsg(txt){
    var el=document.getElementById("gp-checkout-msg");
    if(el){el.textContent=txt;}
  }
  document.querySelectorAll("[data-paddle]").forEach(function(btn){
    btn.addEventListener("click",function(e){
      var plan=btn.getAttribute("data-paddle");
      var priceId=cfg?cfg.prices[plan]:null;
      if(!ready||!priceId){
        // Fallback: not configured yet — go to pricing, don't break the page.
        var p=document.getElementById("pricing");
        if(p){e.preventDefault();p.scrollIntoView({behavior:"smooth"});
          checkoutMsg("Spletno plačilo bo kmalu na voljo. Za dostop lahko medtem pišeš na filip.eremita@gmail.com.");}
        return;
      }
      e.preventDefault();
      Paddle.Checkout.open({
        items:[{priceId:priceId,quantity:1}],
        customData:{plan:plan},
        settings:{displayMode:"overlay",theme:"dark",locale:"sl"},
        eventCallback:function(ev){
          if(ev&&ev.name==="checkout.completed"){
            checkoutMsg("✅ Hvala! Na tvoj e-naslov smo poslali povezavo za dostop — preveri tudi vsiljeno pošto.");
          }
        }
      });
    });
  });
})();
</script>"""


def paddle_head():
    """Paddle.js loader + client config injected into <head>. When the client
    token is not configured yet, injects window.MR_PADDLE=null so the buttons
    fall back to #pricing instead of breaking."""
    if not PADDLE_CLIENT_TOKEN:
        return "<script>window.MR_PADDLE=null;</script>"
    import json as _json
    cfg = _json.dumps({
        "env": PADDLE_ENV,
        "token": PADDLE_CLIENT_TOKEN,
        "prices": {"monthly": PADDLE_PRICE_MONTHLY, "season": PADDLE_PRICE_SEASON},
    })
    return ('<script src="https://cdn.paddle.com/paddle/v2/paddle.js"></script>\n'
            f"<script>window.MR_PADDLE={cfg};</script>")


def build_body(rules, premium, free):
    home = next((l for l in premium["locations"] if l["home"]), premium["locations"][0])
    pct = free["index"]
    lvl = free["level"]
    top_sl = free["top_species_sl"] or "—"
    best_loc = max(premium["locations"], key=lambda l: l["days"][0]["overall"])
    best_o = best_loc["days"][0]

    species = rules["species"]
    indexed = [s for s in species if s.get("gets_index")]
    month = TODAY.month

    # ── HERO (free teaser) ────────────────────────────────────────────────────
    hero = f'''  <div class="gp-hero">
    <div class="gp-hero-top">
      <div class="gp-gauge">{pct}<small> %</small></div>
      <div>
        <div class="gp-hero-lvl">Gobarski indeks danes — <strong>{lvl}</strong></div>
        <div class="gp-hero-sub">Rečica ob Savinji · nosilna vrsta danes: <strong>{_esc(top_sl)}</strong>.<br>
        Najugodnejši gozd danes: <strong>{_esc(best_loc["name"])}</strong> ({best_o["overall"]} % — {best_o["level"]}).</div>
        <a class="gp-cta" href="#pricing">Odkleni 7-dnevno napoved po vrstah →</a>
      </div>
    </div>
    <div class="gp-hero-sub" style="margin-top:.9rem">Indeks je <strong>ocena ugodnosti pogojev</strong> za rast,
    ne obljuba najdbe. Upošteva temperaturo in vlago tal, kumulativne padavine (lokalno iz postaje IREICA1),
    zračno vlago in nočno ohladitev — po vrstah in po geologiji terena.</div>
  </div>'''

    # ── today per forest (free) ───────────────────────────────────────────────
    forests = ['  <div class="gp-forests">']
    for loc in sorted(premium["locations"], key=lambda l: l["days"][0]["overall"], reverse=True):
        o = loc["days"][0]
        top = o["species"][0]
        top_nm = premium["species_meta"][top["id"]]["name_sl"] if top else "—"
        forests.append(
            f'    <div class="gp-forest"><span>{_esc(loc["name"])} '
            f'<span class="gp-terr">{loc.get("terrain","")} · {loc["elev_m"]} m</span></span>'
            f'<b>{o["overall"]} % {o["level"]} · {_esc(top_nm)}</b></div>')
    if premium.get("protected_areas"):
        forests.append(
            f'    <div class="gp-forest" style="opacity:.7"><span>{_esc(", ".join(premium["protected_areas"]))} '
            f'<span class="gp-terr">zaščiteno</span></span><b>nabiranje prepovedano</b></div>')
    forests.append("  </div>")
    forests_html = "\n".join(forests)

    # ── PREMIUM locked block ──────────────────────────────────────────────────
    skel_rows = "\n".join(
        f'      <div class="gp-forest"><span>{_esc(premium["species_meta"][s["id"]]["name_sl"])}</span><b>•• % ······</b></div>'
        for s in home["days"][0]["species"][:5])
    premium_block = f'''  <div id="gp-premium-status" class="gp-msg" hidden></div>
  <div id="gp-content" hidden></div>
  <div id="gp-lock" class="gp-lock">
    <span class="gp-tag">🔒 PREMIUM</span>
    <h3>7-dnevna napoved po vrstah in gozdovih</h3>
    <p class="gp-hero-sub">Za vsak dan naslednjega tedna in vsako od {len(premium["locations"])} nabiralnih območij:
    indeks po posameznih vrstah, plastovita razlaga (»talna temp. optimalna, padavine pod pragom, nočna ohladitev zaznana«)
    in opozorila na nevarne dvojnice.</p>
    <div class="gp-skel">
{skel_rows}
    </div>
    <div class="gp-lockbar">
      <button type="button" class="gp-cta" data-paddle="monthly">Naroči se ({PRICE_MONTHLY}/mes)</button>
      <button type="button" class="gp-cta alt" data-paddle="season">Sezonski dostop ({PRICE_SEASON})</button>
    </div>
    <form id="gp-login" class="gp-login" autocomplete="email">
      <input type="email" name="email" placeholder="Že plačano? Vpiši e-naslov za povezavo" required>
      <button type="submit">Pošlji povezavo</button>
    </form>
    <div id="gp-login-msg" class="gp-msg"></div>
  </div>'''

    # ── pricing ───────────────────────────────────────────────────────────────
    pricing = f'''  <h2 id="pricing">Naročnina</h2>
  <div class="gp-pricing">
    <div class="gp-plan">
      <span class="gp-tag">MESEČNO</span>
      <div class="p-price">{PRICE_MONTHLY}<small> / mesec</small></div>
      <ul>
        <li>7-dnevna napoved po vrstah</li>
        <li>Indeks za vsa nabiralna območja</li>
        <li>Razlage in opozorila na dvojnice</li>
        <li>Prekliči kadarkoli</li>
      </ul>
      <button type="button" class="gp-cta" data-paddle="monthly">Naroči se</button>
    </div>
    <div class="gp-plan best">
      <span class="gp-tag">CELA SEZONA · najugodneje</span>
      <div class="p-price">{PRICE_SEASON}<small> / sezona</small></div>
      <ul>
        <li>Vse iz mesečnega paketa</li>
        <li>Dostop do konca sezone (30. 11.)</li>
        <li>Enkratno plačilo, brez obnavljanja</li>
        <li>Podpora lokalnemu projektu</li>
      </ul>
      <button type="button" class="gp-cta" data-paddle="season">Kupi sezono</button>
    </div>
  </div>
  <div id="gp-checkout-msg" class="gp-msg"></div>
  <p class="muted-note">Plačila varno obdeluje Paddle (prodajalec od zapisa, uredi DDV za EU). Brez ustvarjanja
  računa — po plačilu prejmeš povezavo za dostop na svoj e-naslov, ki deluje na vseh napravah.</p>'''

    # ── monthly calendar (free) ───────────────────────────────────────────────
    cal_rows = []
    for m in range(1, 13):
        names = [s["name_sl"] for s in indexed if m in season_months(s)]
        mark = " ←" if m == month else ""
        hi = ' style="background:var(--fc-today-bg)"' if m == month else ""
        joined = ", ".join(names) or "—"
        cal_rows.append(
            f'      <tr{hi}>'
            f'<th>{seo.MES_NOM[m].capitalize()}{mark}</th>'
            f'<td style="text-align:left">{_esc(joined)}</td></tr>')
    calendar_html = ('  <table class="stats">\n' + "\n".join(cal_rows) + "\n  </table>")

    # ── 50-species reference table (free, SEO + credibility) ──────────────────
    sp_rows = []
    for s in sorted(species, key=lambda x: (not x.get("gets_index"), x["name_sl"])):
        se = s["season"]
        season_txt = f'{se["start"]}–{se["end"]}'
        sp_rows.append(
            f'      <tr><td><b>{_esc(s["name_sl"])}</b><br><span class="lat">{_esc(s["name_lat"])}</span></td>'
            f'<td>{edib_badge(s.get("edibility"))}</td>'
            f'<td>{season_txt}</td>'
            f'<td class="gp-dbl">{_esc(s.get("doubles") or "—")}</td></tr>')
    species_table = (
        '  <div class="gp-scroll"><table class="gp-sptable"><thead><tr>'
        '<th>Vrsta</th><th>Užitnost</th><th>Sezona</th><th>Nevarne dvojnice</th></tr></thead><tbody>\n'
        + "\n".join(sp_rows) + "\n  </tbody></table></div>")

    # ── terrain map (free) ────────────────────────────────────────────────────
    terr_items = []
    for t in rules.get("terrains", []):
        locs_here = [l["name"] for l in rules["locations"]
                     if l.get("terrain") == t["id"] and not l.get("protected")]
        terr_items.append(
            f'    <div class="t"><b>{_esc(t["name_sl"])}</b><br>'
            f'<span class="gp-hero-sub">{_esc(t.get("note",""))}</span><br>'
            f'<span class="gp-terr">Napovedne točke: {_esc(", ".join(locs_here) or "—")}</span></div>')
    terrain_html = '  <div class="gp-terrmap">\n' + "\n".join(terr_items) + "\n  </div>"

    # ── FAQ (free) ────────────────────────────────────────────────────────────
    qa = [
        ("Je gobarski indeks napoved najdbe?",
         "Ne. Indeks (0–100) je ocena, kako ugodni so vremenski in talni pogoji za rast posamezne vrste — "
         "temperatura in vlaga tal, kumulativne padavine, zračna vlaga in nočna ohladitev, uteženo po vrsti in "
         "geologiji terena. Gozd ima vedno zadnjo besedo; visok indeks pomeni ugodne razmere, ne zajamčene gobe."),
        ("Katere vrste zajema premium napoved?",
         "Napoved po vrstah pokriva užitne in pogojno užitne gobe iz lokalne baze Zgornje Savinjske doline. "
         "Strupene vrste se pojavijo le kot opozorilo na nevarne dvojnice ob pripadajoči užitni vrsti."),
        ("Zakaj se indeks razlikuje med gozdovi?",
         "Model upošteva geologijo: kislo vulkansko pogorje Smrekovca ustreza jurčkom in žametastemu gobanu, "
         "karbonatni masivi Golte in Menine pa marelam in poletnemu gobanu. Zato ista vrsta isti dan ni enako "
         "verjetna povsod."),
        ("Kako plačam in dostopam?",
         "Plačilo obdela Paddle. Po nakupu prejmeš na e-naslov povezavo za dostop, ki deluje na vseh napravah — "
         "brez ustvarjanja računa in gesla. Če izgubiš povezavo, jo z istim e-naslovom kadarkoli zahtevaš znova."),
        ("Koliko gob smem nabrati?",
         "V Sloveniji je dovoljeno nabrati do 2 kg gob na osebo na dan (Uredba o varstvu samoniklih gliv). "
         "Logarska dolina, Robanov in Matkov kot so zaščitena območja — nabiranje je tam prepovedano."),
        ("Ali je to uradna napoved ARSO?",
         "Ne. Gre za samostojen model, izračunan iz podatkov Open-Meteo in meritev postaje IREICA1 v Rečici ob "
         "Savinji. Ni uradna napoved ARSO."),
    ]
    faq_html = ("  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{_esc(q)}</summary><p>{_esc(a)}</p></details>' for q, a in qa
    ) + "\n  </div>")

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Gobarska napoved", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Gobarska napoved — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Model rasti gob po vrstah · lokalna baza {len(species)} vrst · osvežuje se dnevno · {TODAY.isoformat()}</p>
{hero}
  <h2>Danes po gozdovih</h2>
  <p class="archive-intro">Gobarski indeks za nabiralna območja Zgornje Savinjske doline, izračunan iz istih vhodnih
  podatkov (vlaga in temperatura tal, padavine, zračna vlaga) ter geologije terena.</p>
{forests_html}
  <h2>Premium: 7-dnevna napoved po vrstah</h2>
{premium_block}
{pricing}
  <h2>Kaj utegne rasti v {MES_FULL[month - 1]}</h2>
  <p class="archive-intro">Užitne in pogojno užitne vrste, ki so ta mesec v sezoni (iz lokalne baze).</p>
{calendar_html}
  <h2>Baza {len(species)} vrst — užitnost in nevarne dvojnice</h2>
  <p class="archive-intro">Referenčni pregled najpogostejših gob doline z oznako užitnosti in ključno razliko do
  nevarnih dvojnic. <strong>Nikoli ne uživaj gobe, ki je ne poznaš 100 %.</strong></p>
{species_table}
  <h2>Geološki tereni doline</h2>
  <p class="archive-intro">Podlaga odloča, kaj raste: model za vsako vrsto upošteva afiniteto do terena.</p>
{terrain_html}
  <div class="card" style="margin:1rem 0">
    <div class="clabel">📋 Nasveti in pravila</div>
    <div style="font-size:.85rem;color:var(--muted);line-height:1.7;margin-top:.5rem">
      ⚖️ Do <b>2 kg gob na osebo na dan</b> (Uredba o varstvu samoniklih gliv).<br>
      🧺 Gobe nosi v zračni košari, ne v vrečki — trosi se tako raznašajo.<br>
      🔪 Gobo izvij ali odreži pri dnu in mesto rahlo prekrij.<br>
      ☠️ <b>Nikoli ne uživaj gobe, ki je ne poznaš 100 %.</b> Ob dvomu vprašaj gobarsko društvo ali mikologa.<br>
      🚫 Logarska dolina, Robanov in Matkov kot: <b>zaščiteno — nabiranje prepovedano.</b>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.65rem">
      <a href="https://www.gobe.si/" target="_blank" rel="noopener" class="mtn-avk-link">🍄 Gobe.si</a>
      <a href="https://www.gobarskazveza.si/" target="_blank" rel="noopener" class="mtn-avk-link">🇸🇮 Gobarska zveza Slovenije</a>
      <a href="https://meteo.arso.gov.si/met/sl/agromet/" target="_blank" rel="noopener" class="mtn-avk-link">🌱 ARSO — agrometeorologija</a>
    </div>
  </div>
{faq_html}
  <p class="gp-disc">Napoved je <strong>indeks ugodnosti pogojev</strong>, ne obljuba najdbe. Pripravlja jo Filip Eremita
  (gozdarstvo/mikologija) iz meritev postaje IREICA1 in podatkov Open-Meteo. Ni uradna napoved ARSO.</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>
{PAGE_JS}'''
    return body


def main():
    print(f"[{TODAY}] Gradim gobarsko prodajno stran …")
    rules = gm.load_rules()
    spots, protected = gm.load_locations(rules)
    try:
        locs = gm.fetch_forecast(spots)
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"✗ Open-Meteo: {e}", file=sys.stderr)
        sys.exit(1)
    if len(locs) != len(spots):
        print(f"✗ Pričakoval {len(spots)} lokacij, dobil {len(locs)}", file=sys.stderr)
        sys.exit(1)

    station_precip = gm.load_station_precip()
    premium = gm.compute_forecast(rules, spots, locs, station_precip, protected)
    free = gm.free_payload(premium)

    body = build_body(rules, premium, free)

    url = "/gobarska-napoved/"
    title = "Gobarska napoved — Zgornja Savinjska dolina"
    desc = (f"Gobarski indeks danes: {free['index']} % ({free['level']}). Napoved rasti gob po vrstah za "
            f"Zgornjo Savinjsko dolino — 7-dnevni premium model, baza {len(rules['species'])} vrst, "
            f"nevarne dvojnice in gobarski koledar.")

    qa_for_schema = [
        ("Je gobarski indeks napoved najdbe?",
         "Ne. Indeks je ocena ugodnosti vremenskih in talnih pogojev za rast, ne obljuba najdbe."),
        ("Katere vrste zajema premium napoved?",
         "Užitne in pogojno užitne gobe Zgornje Savinjske doline; strupene le kot opozorilo na dvojnice."),
        ("Ali je to uradna napoved ARSO?",
         "Ne. Samostojen model iz podatkov Open-Meteo in meritev postaje IREICA1. Ni uradna napoved ARSO."),
    ]
    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-07-02"),
        seo.crumbs_schema([("Meteorec", "/"), ("Gobarska napoved", None)]),
        seo.faq_schema(qa_for_schema),
    ])
    head_extras = schema + "\n" + PAGE_CSS + "\n" + paddle_head()

    og_image = f"{seo.SITE}/og/gobarska-napoved.jpg"
    html = seo.page_shell(title, desc, url, head_extras, body, og_image=og_image)
    seo.write_page("gobarska-napoved/index.html", html, force=True)
    print(f"  → gobarska-napoved/index.html ({free['index']} %, {free['level']})")


if __name__ == "__main__":
    main()
