#!/usr/bin/env python3
"""
tools/generate_daily_fact.py — vidna "dnevna kartica" na naslovni strani.

V nasprotju z .wx-static bloki (tools/inject_current_weather.py,
tools/inject_record_watch.py), ki so namenjeni iskalnikom/bralnikom zaslona
in so na strani vizualno skriti, ta skript injicira VIDNO kartico
(.daily-fact-card) — uporabnik naj ob vsakem obisku takoj opazi nekaj
novega od včeraj.

Izbere en "fact" med več vedno-preverljivimi tipi (razvrščeno po
zanimivosti, izbere se prvi, ki velja):
  1. nov rekord za ta koledarski dan (tempHigh ali tempLow)
  2. blizu rekorda za ta koledarski dan (< 1 °C razlike)
  3. opazen padavinski/suh niz (zaporedni dnevi brez/z dežjem)
  4. percentilna uvrstitev tega koledarskega dne med vsemi leti meritev
  5. primerjava z istim datumom lani (fallback — velja skoraj vedno)

Wired into: .github/workflows/update-history.yml (dnevno, po posodobitvi
history.json).

Usage:
  python3 tools/generate_daily_fact.py
"""
import json, os, re, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
HIST = os.path.join(ROOT, "history.json")
TZ = ZoneInfo("Europe/Berlin")

START = "<!-- WX-DAILY-FACT:START (auto: tools/generate_daily_fact.py) -->"
END = "<!-- WX-DAILY-FACT:END -->"

MES_NOM = {1: "januar", 2: "februar", 3: "marec", 4: "april", 5: "maj",
           6: "junij", 7: "julij", 8: "avgust", 9: "september", 10: "oktober",
           11: "november", 12: "december"}


def num(x, d=1):
    if x is None:
        return "—"
    return f"{x:.{d}f}".replace(".", ",")


def dm_label(iso):
    return f"{int(iso[8:10])}. {MES_NOM[int(iso[5:7])]}"


def day_word(last):
    """'Danes'/'Včeraj' glede na to, kateremu koledarskemu dnevu (Europe/Berlin)
    dejansko pripada zadnja meritev v history.json — ne glede na to, kdaj se
    ta skript požene."""
    now = datetime.now(TZ)
    today_str = now.strftime("%Y-%m-%d")
    yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    if last == today_str:
        return "Danes"
    if last == yesterday_str:
        return "Včeraj"
    return "Nazadnje"


def wrap(icon, text, date):
    return (f'{START}\n'
            f'  <div class="daily-fact-card" id="daily-fact-card" data-date="{date}" role="status">\n'
            f'    <span class="dfc-icon" aria-hidden="true">{icon}</span>\n'
            f'    <span class="dfc-text">{text}</span>\n'
            f'    <button class="dfc-close" onclick="dismissDailyFact()" aria-label="Zapri" title="Skrij za danes">×</button>\n'
            f'  </div>\n'
            f'  {END}')


def fact_record(hist, last, mmdd, param, label, unit, superlative):
    """Nov rekord ali bližina rekorda za ta koledarski dan, za en parameter.

    Ločeno preveri tudi, ali gre hkrati za ABSOLUTNI rekord postaje (najvišja/
    najnižja vrednost v celotni zgodovini, ne le na ta koledarski dan) — enako
    razlikovanje kot že v tools/seo_smart_routine.py (detect_events, "rekord-
    vrocina"/"rekord-mraz" proti ožjemu "rekord-dneva-*"). Ta kartica je bila
    prej slepa za absolutni rekord in bi 37,6 °C 4. 8. 2026 (dejansko nov
    absolutni rekord postaje) napovedala samo kot "rekord za ta dan".
    """
    today_v = hist[last].get(param)
    if today_v is None:
        return None
    prior = [(d, v[param]) for d, v in hist.items()
             if d != last and d[5:] == mmdd and v.get(param) is not None]
    if len(prior) < 2:
        return None

    years = len({d[:4] for d, _ in prior})
    all_prior = [(d, v[param]) for d, v in hist.items()
                 if d != last and v.get(param) is not None]
    all_years = len({d[:4] for d in hist})
    if superlative == "max":
        rec_date, rec_val = max(prior, key=lambda dv: dv[1])
        is_new = today_v > rec_val
        diff = today_v - rec_val if is_new else rec_val - today_v
        is_absolute = bool(all_prior) and today_v > max(v for _, v in all_prior)
        superlat_word = "najvišja"
    else:
        rec_date, rec_val = min(prior, key=lambda dv: dv[1])
        is_new = today_v < rec_val
        diff = rec_val - today_v if is_new else today_v - rec_val
        is_absolute = bool(all_prior) and today_v < min(v for _, v in all_prior)
        superlat_word = "najnižja"

    word = day_word(last)
    if is_new and is_absolute:
        score = 120  # bolj zanimivo od navadnega dnevnega rekorda -- naj med kandidati vedno zmaga
        text = (f'{word}, {dm_label(last)}, smo na Rečici ob Savinji postavili <strong>nov absolutni rekord '
                 f'postaje</strong> — {label} <strong>{num(today_v)}{unit}</strong>, {superlat_word} vrednost '
                 f'v celotni {all_years}-letni zgodovini meritev postaje IREICA1. Hkrati je to tudi nov rekord '
                 f'za ta koledarski dan — padel je dosedanji {num(rec_val)}{unit} iz leta {rec_date[:4]}.')
        icon = "🥇"
    elif is_new:
        score = 100
        text = (f'{word}, {dm_label(last)}, smo na Rečici ob Savinji izmerili nov rekord za ta koledarski dan — '
                 f'{label} <strong>{num(today_v)}{unit}</strong>. S tem je padel dosedanji rekord '
                 f'{num(rec_val)}{unit} iz leta {rec_date[:4]}, v {years}-letni zgodovini meritev postaje IREICA1.')
        icon = "🏆"
    elif diff < 0.05:
        # Zaokroženo na eno decimalko bi razlika pokazala kot "0,0 °C", kar bi
        # bralcu povedalo, da je rekord SKORAJ padel -- v resnici je izenačen.
        score = 90
        text = (f'{word}, {dm_label(last)}, smo na Rečici ob Savinji izenačili rekord za ta koledarski dan — '
                 f'{label}: <strong>{num(today_v)}{unit}</strong>, prav toliko kot rekord iz leta {rec_date[:4]}.')
        icon = "🤝"
    elif diff < 1.0:
        score = 80
        text = (f'{word}, {dm_label(last)}, nas je na Rečici ob Savinji od rekorda za ta koledarski dan ločilo le '
                 f'<strong>{num(diff)}{unit}</strong> — {label}: {num(today_v)}{unit}, rekord {num(rec_val)}{unit} '
                 f'iz leta {rec_date[:4]}.')
        icon = "📈"
    else:
        return None
    return (score, icon, text)


def fact_streak(hist, last):
    """Zaporedni dnevi brez/z dežjem do vključno zadnjega dne."""
    days = sorted(d for d in hist if d <= last and hist[d].get("src") != "era5")
    if not days:
        return None
    wet_today = (hist[last].get("precipTotal") or 0) > 0.1

    streak = 0
    for d in reversed(days):
        v = hist[d].get("precipTotal")
        if v is None:
            break
        is_wet = v > 0.1
        if is_wet != wet_today:
            break
        streak += 1

    if streak < 7:
        return None
    if wet_today:
        score = 60 + min(streak, 20)
        text = (f'Na Rečici ob Savinji dežuje že <strong>{streak}. zaporedni dan</strong> — '
                 f'nenavadno dolgo mokro obdobje za {dm_label(last)}.')
        icon = "🌧️"
    else:
        score = 60 + min(streak, 20)
        text = (f'Na Rečici ob Savinji dežja ni bilo že <strong>{streak} dni zapored</strong> — '
                 f'sušni niz se tako nadaljuje.')
        icon = "☀️"
    return (score, icon, text)


def fact_percentile(hist, last, mmdd):
    """Uvrstitev tega koledarskega dne po tempHigh med vsemi leti meritev."""
    today_v = hist[last].get("tempHigh")
    if today_v is None:
        return None
    same_day = [(d, v["tempHigh"]) for d, v in hist.items()
                if d[5:] == mmdd and v.get("tempHigh") is not None]
    years = len({d[:4] for d, _ in same_day})
    if years < 4:
        return None
    ranked = sorted(same_day, key=lambda dv: dv[1], reverse=True)
    rank = next(i for i, (d, _) in enumerate(ranked, start=1) if d == last)
    if rank > 3 and rank < years - 2:
        return None  # ni ne posebej vroč ne posebej mrzel dan -- ni zanimivo

    if rank <= 3:
        score = 50
        text = (f'{dm_label(last)} se letos uvršča med najtoplejše koledarske dni v {years}-letni zgodovini '
                 f'meritev postaje IREICA1 — na <strong>{rank}. mesto</strong> z {num(today_v)} °C.')
        icon = "🌡️"
    else:
        rank_from_bottom = years - rank + 1
        score = 50
        text = (f'{dm_label(last)} se letos uvršča med najhladnejše koledarske dni v {years}-letni zgodovini '
                 f'meritev postaje IREICA1 — na <strong>{rank_from_bottom}. mesto</strong> z {num(today_v)} °C.')
        icon = "❄️"
    return (score, icon, text)


def fact_year_ago(hist, last):
    """Primerjava z istim datumom lani -- vedno na voljo, če obstaja lanski zapis."""
    year, rest = int(last[:4]), last[4:]
    prev = f"{year - 1}{rest}"
    prev_v = hist.get(prev, {})
    today_v = hist[last].get("tempHigh")
    prev_temp = prev_v.get("tempHigh")
    if today_v is None or prev_temp is None:
        return None

    diff = today_v - prev_temp
    if abs(diff) < 0.05:
        text = (f'{dm_label(last)} je bilo letos enako toplo kot lani — '
                 f'<strong>{num(today_v)} °C</strong> oba dneva.')
        icon = "🔁"
    elif abs(diff) < 0.2:
        text = (f'{dm_label(last)} je bilo letos skoraj enako toplo kot lani — '
                 f'<strong>{num(today_v)} °C</strong> letos in {num(prev_temp)} °C lani.')
        icon = "🔁"
    elif diff > 0:
        text = (f'{dm_label(last)} je bilo letos za <strong>{num(diff)} °C topleje</strong> kot na isti dan lani — '
                 f'{num(today_v)} °C letos proti {num(prev_temp)} °C lani.')
        icon = "📊"
    else:
        text = (f'{dm_label(last)} je bilo letos za <strong>{num(-diff)} °C hladneje</strong> kot na isti dan lani — '
                 f'{num(today_v)} °C letos proti {num(prev_temp)} °C lani.')
        icon = "📊"
    return (10, icon, text)


def build_block():
    hist = json.load(open(HIST, encoding="utf-8"))
    real = [k for k in hist if hist[k].get("src") != "era5"]
    if not real:
        return None
    last = max(real)
    mmdd = last[5:]

    candidates = []
    for param, label, unit, sup in (
        ("tempHigh", "vročina", " °C", "max"),
        ("tempLow", "mraz", " °C", "min"),
    ):
        r = fact_record(hist, last, mmdd, param, label, unit, sup)
        if r:
            candidates.append(r)

    for fn in (fact_streak, lambda h, l: fact_percentile(h, l, mmdd), fact_year_ago):
        r = fn(hist, last)
        if r:
            candidates.append(r)

    if not candidates:
        return None

    _, icon, text = max(candidates, key=lambda c: c[0])
    return wrap(icon, text, last)


def main():
    block = build_block()
    if block is None:
        print("Premalo podatkov za dnevno dejstvo -- preskačem.")
        return 0

    html = open(INDEX, encoding="utf-8").read()
    if START not in html or END not in html:
        print("ERROR: markers not found in index.html -- add them once first.", file=sys.stderr)
        return 1

    new = re.sub(re.escape(START) + r".*?" + re.escape(END), block, html, flags=re.S)
    if new != html:
        open(INDEX, "w", encoding="utf-8").write(new)
        print("index.html: posodobljena kartica 'dnevno dejstvo'.")
    else:
        print("index.html: brez sprememb.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
