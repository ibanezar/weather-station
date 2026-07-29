#!/usr/bin/env python3
"""
Jutranji predlogi dnevnega članka za blog Meteorec.
---------------------------------------------------
Namesto samodejne objave (stari način) vsako jutro:
  1. Povleče iste podatke kot generate_daily_post.py (trenutne razmere,
     napoved) in zazna morebitni dogodek.
  2. Izbere TRI raznolike kandidatne teme: dogodek (če obstaja) + evergreen
     ideje, ki se nedavno še niso pojavile; če so vse "porabljene", vzame
     najdlje neuporabljene (ne vedno iste prve s seznama).
  3. En klic Claude API -> za vsako temo naslov + kratek povzetek (teaser).
  4. Zapiše tools/.daily_proposals.json (workflow ga commita na main, da ga
     objavni zagon kasneje najde).
  5. POST na worker /daily-post/proposals -> worker Filipu pošlje e-mail s
     tremi povezavami; klik na povezavo sproži workflow "Dnevni članek" z
     inputom choice=<id> in objavi izbrani članek.

Uporaba:
    python3 tools/generate_daily_proposals.py [--dry-run]

Potrebne env spremenljivke:
    ANTHROPIC_API_KEY   -- Claude API ključ (GitHub secret)
    NOTIFY_SECRET       -- ista skrivnost kot za /blog-subscribe/notify
    POST_DATE           -- (opcijsko, za testiranje) prepiše današnji datum
"""
import json, os, sys, re, random, datetime, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_monthly_post import ROOT, TODAY
from generate_daily_post import (
    IDEAS, PROXY, ANTHROPIC_MODEL, num, STATE_FILE,
    fetch_current, fetch_hourly, fetch_forecast,
    detect_event, load_state, save_state, recent_tags, recent_titles,
    build_stat_cards, stream_claude,
    norm_tag, tag_used, last_used_index, event_is_newsworthy, event_topic,
    remember_event,
)

PROPOSALS_FILE = os.path.join(ROOT, "tools", ".daily_proposals.json")
N_PROPOSALS = 3
# Ideja, ki je bila ponujena v zadnjih toliko zagonih, gre na konec vrste --
# brez tega se v e-pošti isti trije predlogi vrtijo iz dneva v dan.
PROPOSED_COOLDOWN = 6


def pick_candidates(event, state, n=N_PROPOSALS):
    """Vrne do n raznolikih kandidatnih tem.

    Vrstni red: (1) dogodek, a SAMO če je nov ali izrazito hujši od zadnjega
    (drugače je poleti vsak dan prvi predlog "vročina"), (2) ideje, ki niso
    bile ne objavljene ne ponujene v zadnjih dneh, (3) najdlje neuporabljene."""
    month = datetime.date.today().month
    recent = state.get("recentTopics", [])
    proposed = state.get("recentProposed", [])[-PROPOSED_COOLDOWN * N_PROPOSALS:]
    taken = recent_tags(12) | {norm_tag(t) for t in recent[-6:]}
    seasonal = [i for i in IDEAS if month in i["sezona"]] or list(IDEAS)

    fresh, warm, stale = [], [], []
    for idea in seasonal:
        if tag_used(idea["tag"], taken):
            stale.append(idea)
        elif idea["id"] in proposed:
            warm.append(idea)
        else:
            fresh.append(idea)
    random.shuffle(fresh)
    random.shuffle(warm)
    stale.sort(key=lambda i: last_used_index(i["tag"], recent))

    candidates = []
    if event_is_newsworthy(event, state):
        candidates.append(event_topic(event, state))
    elif event:
        print(f"   (dogodek '{event['type']}' izpuščen -- enak kot nedavno in ne hujši)")
    for idea in fresh + warm + stale:
        if len(candidates) >= n:
            break
        candidates.append(idea)
    return candidates[:n]


PROPOSALS_PROMPT = """Si urednik vremenskega bloga meteorec.si (osebna meteorološka postaja IREICA1,
Rečica ob Savinji, Zgornja Savinjska dolina, Slovenija).

Dobiš surove vremenske podatke, seznam kandidatnih tem za današnji članek in
naslove nazadnje objavljenih člankov. Za VSAKO temo predlagaj:
- "title": konkreten naslov članka v slovenščini,
- "teaser": 2-3 povedi o tem, kaj bo članek pokril, utemeljeno na DEJANSKIH
  podanih podatkih. Ne izmišljuj številk -- uporabi samo vrednosti iz podatkov,
  lahko pa jih izpustiš in ostaneš splošen,
- "oblika": katera od spodnjih oblik članka je to (ena beseda s seznama).

RAZNOLIKOST -- to je najpomembnejše. Bralec dobi članek vsak dan, zato se
predlogi ne smejo brati kot včerajšnji:
- Vsak predlog mora biti DRUGA oblika članka. Izbiraj med: "analiza"
  (kaj se je zgodilo in zakaj), "razlaga" (kako neki pojav sploh deluje),
  "preverba" (ali neka trditev/napoved/pregovor drži glede na meritve),
  "primerjava" (z rekordi, s povprečjem, s sosednjimi kraji, z lani),
  "vodic" (kaj to konkretno pomeni za bralca in kaj naj naredi),
  "pregled" (več dni/tednov v številkah).
- Ne ponovi teme ali kota nobenega od nazadnje objavljenih člankov. Če se
  kandidatna tema prekriva z že objavljenim, jo obrni v drug kot.

NASLOVI -- nazadnje objavljeni članki imajo skoraj vsi isto obliko naslova
("Kraj ali pojav: pojasnilo za dvopičjem"). Prekini to:
- največ EN od predlaganih naslovov sme imeti dvopičje,
- največ EN sme vsebovati "Zgornja Savinjska dolina" / "Rečica ob Savinji"
  (kraj naj bo v drugih naslovih razviden posredno ali pa ga ni),
- uporabi različne oblike: vprašanje, naslov s številko na začetku, kratka
  trditev, presenetljiva ugotovitev,
- brez clickbaita, brez klišejev ("kaj se skriva za", "vse, kar morate vedeti"),
- glavno SEO frazo teme vpleti naravno, le če naslov zaradi tega ne postane okoren.

Vrni SAMO veljaven JSON (brez markdown fence) v tej shemi:
{"proposals": [{"id": "id-teme-iz-vhoda", "title": "...", "teaser": "...", "oblika": "..."}]}
Ohrani vrstni red in "id" vrednosti natanko take, kot so v vhodu."""


def call_claude_proposals(candidates, current, forecast, stat_cards):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY manjka.")
    context = {
        "datum": TODAY,
        "kandidatne_teme": [
            {"id": c["id"], "brief": c["brief"], "seo_keywords": c.get("seo_keywords", [])}
            for c in candidates
        ],
        "trenutne_razmere": current,
        "napoved_4dni": (forecast or {}).get("daily"),
        "izracunane_stat_kartice": [{"label": l, "value": v, "sub": s} for _, l, v, s in stat_cards],
        "nazadnje_objavljeni_clanki": recent_titles(12),
    }
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 2000,
        "system": PROPOSALS_PROMPT,
        "messages": [{"role": "user", "content":
                      "Podatki in kandidatne teme:\n" + json.dumps(context, ensure_ascii=False, indent=2)
                      + "\n\nPredlagaj naslov in teaser za vsako temo."}],
    }
    try:
        text = stream_claude(payload, api_key)
    except urllib.error.HTTPError as e:
        sys.exit(f"Claude API napaka {e.code}: {e.read().decode('utf-8', 'replace')[:500]}")
    except (TimeoutError, urllib.error.URLError) as e:
        sys.exit(f"Claude API klic ni uspel (timeout/omrežje): {e}")
    except RuntimeError as e:
        sys.exit(str(e))
    if not text:
        sys.exit("Claude ni vrnil besedila.")
    cleaned = re.sub(r"^```json|```$", "", text.strip(), flags=re.M).strip()
    parsed = json.loads(cleaned)
    by_id = {p.get("id"): p for p in parsed.get("proposals", [])}
    out = []
    for c in candidates:
        p = by_id.get(c["id"])
        if not p or not p.get("title"):
            sys.exit(f"Claude ni vrnil predloga za temo '{c['id']}'.")
        out.append({"id": c["id"], "title": p["title"].strip(),
                    "teaser": (p.get("teaser") or "").strip(),
                    "oblika": (p.get("oblika") or "").strip(), "topic": c})
    return out


def notify_worker(date, proposals):
    """POST na worker -> shrani predloge v KV in pošlje Filipu e-mail z izbiro."""
    secret = os.environ.get("NOTIFY_SECRET")
    if not secret:
        sys.exit("NOTIFY_SECRET manjka -- e-maila s predlogi ni mogoče poslati.")
    payload = json.dumps({
        "secret": secret,
        "date": date,
        "proposals": [{"id": p["id"], "title": p["title"], "teaser": p["teaser"]} for p in proposals],
    }).encode()
    req = urllib.request.Request(
        PROXY + "/daily-post/proposals",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; Meteorec-DailyProposals/1.0; +https://meteorec.si)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print(f"✓ Worker obveščen: {r.status} — {r.read().decode()[:200]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        sys.exit(f"Worker /daily-post/proposals napaka {e.code}: {body}")
    except (TimeoutError, urllib.error.URLError) as e:
        sys.exit(f"Worker /daily-post/proposals ni dosegljiv: {e}")


def main():
    dry_run = "--dry-run" in sys.argv

    print("1/4 Pridobivam podatke...")
    current = fetch_current()
    hourly = fetch_hourly()
    forecast = fetch_forecast()

    print("2/4 Izbiram kandidatne teme...")
    state = load_state()
    event = detect_event(current, hourly, forecast)
    candidates = pick_candidates(event, state)
    for c in candidates:
        print(f"   - {c['id']}: {c['brief'][:70]}")
    if len(candidates) < N_PROPOSALS:
        print(f"⚠ Na voljo le {len(candidates)} tem (namesto {N_PROPOSALS}).")

    if dry_run:
        print("   (--dry-run: preskačem klic Claude API in e-mail)")
        return

    stat_cards = build_stat_cards(current, hourly)

    print("3/4 Kličem Claude API (naslovi + teaserji)...")
    proposals = call_claude_proposals(candidates, current, forecast, stat_cards)
    for p in proposals:
        print(f"   [{p['id']}] ({p.get('oblika') or '?'}) {p['title']}")

    # Kaj smo ponudili, si zapomnimo tudi če Filip ne izbere ničesar -- sicer
    # naslednje jutro pride e-pošta z istimi tremi predlogi.
    for c in candidates:
        if c["id"] == "dogodek":
            remember_event(state, c)
    state.setdefault("recentProposed", []).extend(c["id"] for c in candidates)
    state["recentProposed"] = state["recentProposed"][-PROPOSED_COOLDOWN * N_PROPOSALS:]
    save_state(state)
    print(f"✓ posodobljeno: {os.path.relpath(STATE_FILE, ROOT)}")

    data = {
        "date": TODAY,
        "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "proposals": proposals,
    }
    json.dump(data, open(PROPOSALS_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(PROPOSALS_FILE, "a", encoding="utf-8").write("\n")
    print(f"✓ zapisano: tools/.daily_proposals.json")

    print("4/4 Pošiljam predloge workerju (e-mail)...")
    notify_worker(TODAY, proposals)


if __name__ == "__main__":
    main()
