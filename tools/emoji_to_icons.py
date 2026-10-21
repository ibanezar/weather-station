#!/usr/bin/env python3
"""Emojiji v naslovih, gumbih in meniju naslovne strani -> SVG ikone (Lucide, ISC).

Ročno orodje, izhod je commitan (isti vzorec kot build_inter_sl_subset.py):
    python3 tools/emoji_to_icons.py          # preoblikuje index.html + osveži sprite
    python3 tools/emoji_to_icons.py --docs   # zapiše docs/ikone.md
Idempotentno: že preoblikovan element nima več vodilnega emojija. Ikone so v
tools/icons/lucide/<ime>.svg (kopija iz `lucide-static`, licenca v LICENSE-lucide.txt);
sprite (<svg id="icon-sprite">) je v index.html med ICON-SPRITE:START/END.
Obseg: samo vodilni emoji v elementih iz TARGET. Vsebina, <option>, skupnostni vnosi,
taksonomski čipi (.inat-filter), tipografske puščice in tabele v app.js ostanejo.
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "index.html"
ICONS = ROOT / "tools" / "icons" / "lucide"

# emoji (brez FE0F) -> ime ikone Lucide
MAP = {
 "📊":"chart-column","🌡":"thermometer","💨":"wind","☀":"sun","📈":"trending-up","🌧":"cloud-rain",
 "📅":"calendar","🗓":"calendar","📆":"calendar","🎯":"target","💧":"droplet","🗺":"map","❄":"snowflake",
 "🌊":"waves","🔗":"link","🔥":"flame","📡":"radio-tower","🌾":"wheat","🌿":"leafy-green","🌍":"globe",
 "🌐":"globe","🔍":"search","🪂":"wind","🌤":"cloud-sun","📷":"camera","📸":"camera","🧭":"compass",
 "🌱":"sprout","⚡":"zap","📋":"clipboard-list","🕐":"clock","⏰":"alarm-clock","⏱":"timer","🌀":"tornado",
 "🏔":"mountain-snow","⛰":"mountain","🍄":"sprout","📖":"book-open","📚":"library","🍂":"leaf","↻":"rotate-cw",
 "⏳":"hourglass","🔮":"sparkles","💬":"message-circle","🔄":"refresh-cw","⏸":"pause","▶":"play","🌸":"flower",
 "🌌":"moon-star","👯":"users","🌅":"sunrise","📍":"map-pin","🔬":"microscope","🌬":"wind","📉":"trending-down",
 "🛰":"satellite","📜":"scroll","🧊":"thermometer-snowflake","🏫":"school","⬆":"share-2","📲":"smartphone",
 "🔔":"bell","⚙":"settings","🎧":"headphones","🖼":"image","🌹":"flower-2","🌫":"cloud-fog","📝":"pencil",
 "⚔":"swords","☔":"umbrella","🌙":"moon","🏅":"medal","📐":"ruler","🎭":"drama","📂":"folder-open",
 "💥":"sparkles","🕯":"flame","🎁":"gift","🧠":"brain","🐞":"bug","❓":"circle-help","📌":"map-pin",
 "🛡":"shield","🌩":"cloud-lightning","⛈":"cloud-lightning","⚠":"triangle-alert","☁":"cloud","🔵":"circle",
 "🔭":"telescope","🐛":"bug","👧":"baby","💦":"droplets","🌓":"moon","🧪":"flask-conical","💊":"pill",
 "✈":"plane","🏘":"house","🏖":"tree-palm","🥾":"footprints","🌵":"sun","🌲":"tree-pine","🏆":"trophy",
 "🏷":"tag","🗜":"minimize-2","🗑":"trash-2","🔒":"lock","☰":"menu",
}
# ikone, ki jih potrebuje JS (app.js), tudi če jih HTML ne uporablja
EXTRA = ["sun","moon","play","pause","hourglass","cloud-rain","cloud-lightning","thermometer-snowflake","refresh-cw","tag","minimize-2","share-2"]

# razredi elementov, katerih VODILNI emoji zamenjamo
TARGET = ["clabel","an-title","tri-title","nt-title","kf-label","qn-ico","qn-burger","mode-btn-ico","mi-ico",
          "sc-icon","notif-btn","install-btn","share-btn","radar-btn","ai-brief-btn","ev-filter-btn",
          "gallery-cat-chip","gallery-pending-btn","hb-icon","nc-badge-ic","theme-btn","mode-cta-btn"]

EMO = "[\U0001F300-\U0001FAFF☀-➿⬀-⯿⏩-⏿↻←-⇿⬆▶]"
LEAD = re.compile(r'(?P<open><(?P<tag>div|span|button|label|summary|a)\b(?P<attrs>[^>]*?class="(?P<cls>[^"]*)"[^>]*)>'
                  r'(?P<pre>(?:<span>)?\s*))(?P<e>' + EMO + r')️?(?P<sp>[ \t]*)')
LEAD_ICHEAD = re.compile(r'(?P<open><div class="ic-head"><span>)(?P<e>' + EMO + r')️?(?P<sp>[ \t]*)')

def svg(name):
    return f'<svg class="ic" aria-hidden="true"><use href="#i-{name}"/></svg>'

def strip(e):
    return e.replace("️", "")

def convert(s, used):
    def rep(m):
        e = strip(m.group("e"))
        name = MAP.get(e)
        if not name:
            return m.group(0)
        used.add(name)
        return m.group("open") + svg(name) + (" " if m.group("sp") else "")
    def rep_target(m):
        if not any(c in TARGET for c in m.group("cls").split()):
            return m.group(0)
        return rep(m)
    s = LEAD.sub(rep_target, s)
    s = LEAD_ICHEAD.sub(rep, s)
    return s

def add_labels(s):
    # gumb samo z ikono: aria-label iz title
    def rep(m):
        tag = m.group(1)
        if "aria-label" in tag:
            return m.group(0)
        t = re.search(r'title="([^"]+)"', tag)
        if not t:
            return m.group(0)
        return tag[:-1] + f' aria-label="{t.group(1)}">' + m.group(2)
    return re.sub(r'(<button\b[^>]*>)(<svg class="ic" aria-hidden="true"><use href="#i-[a-z0-9-]+"/></svg></button>)', rep, s)

def symbol(name):
    f = ICONS / f"{name}.svg"
    if not f.exists():
        src = Path(sys.argv[0]).resolve().parent / "icons" / "_src" / f"{name}.svg"
        raise SystemExit(f"manjka {f}")
    inner = re.search(r'<svg[^>]*>(.*)</svg>', f.read_text(), re.S).group(1)
    inner = re.sub(r'\s+', ' ', inner).strip()
    return f'<symbol id="i-{name}" viewBox="0 0 24 24">{inner}</symbol>'

def sprite(names):
    body = "".join(symbol(n) for n in sorted(names))
    return ('<!-- ICON-SPRITE:START (auto: tools/emoji_to_icons.py) -->'
            '<svg id="icon-sprite" xmlns="http://www.w3.org/2000/svg" width="0" height="0" '
            'style="position:absolute" aria-hidden="true" focusable="false">' + body + '</svg>'
            '<!-- ICON-SPRITE:END -->')

def main():
    s = HTML.read_text()
    used = set(EXTRA)
    s = convert(s, used)
    s = add_labels(s)
    used |= set(re.findall(r'#i-([a-z0-9-]+)', s))
    new = sprite(used)
    if "ICON-SPRITE:START" in s:
        s = re.sub(r'<!-- ICON-SPRITE:START.*?ICON-SPRITE:END -->', lambda m: new, s, flags=re.S)
    else:
        s = s.replace("<body>", "<body>\n" + new, 1)
    HTML.write_text(s)
    print(f"ikon v spritu: {len(used)}")
    if "--docs" in sys.argv:
        write_docs()

def write_docs():
    rows = {}
    for e, n in MAP.items():
        rows.setdefault(n, []).append(e)
    out = ["# Emoji → SVG ikone (faza 2 redizajna)", "",
           "Ikone so Lucide (ISC, `tools/icons/LICENSE-lucide.txt`), vdelane kot inline sprite v `index.html`",
           "(`<svg id=\"icon-sprite\">`, `<use href=\"#i-ime\">`). Orodje: `python3 tools/emoji_to_icons.py`.", "",
           "## Preslikava", "", "| Ikona | Emoji |", "|---|---|"]
    for n in sorted(rows):
        out.append(f"| `{n}` | {' '.join(rows[n])} |")
    out += ["", "## Namerno ohranjeni emojiji", "",
            "- Vsebina besedil in analiz (`<li>`, odstavki), blogi in članki.",
            "- `<option>` (SVG ne more v izbirnik).",
            "- Skupnostni/uporabniški vnosi: `.community-*`, `.feel-poll-emoji`.",
            "- Taksonomski čipi `.inat-filter` (🐸 🦎 🐦 …): Lucide nima ustreznih živali.",
            "- Tipografske puščice (↑ ↓ ↔ →) v besedilu.",
            "- Tabele v `app.js`: vremenske kode (`cond.icon`), fenologija, cvetovi, `sc-risk-icon`, `.dfc-icon` (generator).",
            "- Podstrani z lastnimi generatorji (ne nalagajo `style.css` in spritea).", "",
            "## Dodajanje ikone", "",
            "1. Kopiraj `<ime>.svg` iz `lucide-static/icons/` v `tools/icons/lucide/`.",
            "2. Dodaj vnos v `MAP` (emoji → ime) ali v `EXTRA` (če jo uporablja samo JS).",
            "3. Poženi `python3 tools/emoji_to_icons.py`, nato `npm run minify`.",
            "4. V JS uporabi `_ico('ime')` (app.js)."]
    (ROOT / "docs" / "ikone.md").write_text("\n".join(out) + "\n")

if __name__ == "__main__":
    main()
