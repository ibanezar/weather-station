#!/usr/bin/env python3
"""
tools/zenodo_publish.py — objava CSV z dnevnimi meritvami IREICA1 na Zenodo (DOI, trajna citirljivost).

ROČNO orodje (ni v nobenem workflowu). Zenodo zapisa ni mogoče umakniti: objavljen zapis z DOI ostane za vedno, zato je
PRIVZETO samo OSNUTEK: skript ustvari osnutek, naloži CSV in metapodatke (data/dataset-metadata.json), izpiše povezavo,
objavi pa ga šele z --publish. Osnutek lahko pregledaš na zenodo.org, preden ga potrdiš.

Potrebuje osebni dostopni žeton z dovoljenji deposit:write + deposit:actions (zenodo.org → Applications → Personal access
tokens) v okolju `ZENODO_TOKEN`. Žetona nikoli ne zapisuj v repozitorij. Za preizkus: --sandbox (sandbox.zenodo.org, drug žeton).

Nova različica istega zapisa: --new-version <id obstoječega zapisa> (DOI koncepta ostane isti, vsaka različica dobi svoj DOI).
Po --publish skript zapiše `doi` v data/dataset-metadata.json; ponovno poženi tools/generate_podatki_page.py (stran in shema
ga prikažeta) in doda `doi:` v CITATION.cff.

Kaj gre ven: samo podatki/ireica1-dnevni-podatki.csv (zunanje meritve, brez dni iz reanalize, brez notranjih meritev;
glej tools/export_dataset.py) in metapodatki iz data/dataset-metadata.json.

Usage:
  ZENODO_TOKEN=… python3 tools/zenodo_publish.py [--sandbox] [--publish] [--new-version ID]
"""
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "podatki", "ireica1-dnevni-podatki.csv")
META_PATH = os.path.join(ROOT, "data", "dataset-metadata.json")
FORBIDDEN = ("indoor", "tempinf")


def api(method, url, token, body=None, raw=None, opener=urllib.request.urlopen):
    """En klic Zenodo REST API. `opener` je za teste. Vrne razčlenjen JSON (ali {})."""
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if raw is not None:
        data, headers["Content-Type"] = raw, "application/octet-stream"
    elif body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode("utf-8"), "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with opener(req, timeout=120) as r:
        txt = r.read().decode("utf-8")
    return json.loads(txt) if txt.strip() else {}


def build_metadata(meta, first_day, last_day):
    """Metapodatki za Zenodo iz data/dataset-metadata.json (brez ključa doi) + obdobje meritev."""
    m = {k: v for k, v in meta.items() if k != "doi"}
    m["version"] = last_day
    m["publication_date"] = last_day
    m["dates"] = [{"type": "Collected", "start": first_day, "end": last_day}]
    return m


def csv_span(path=CSV_PATH):
    with open(path, encoding="utf-8") as f:
        lines = [l for l in f.read().splitlines() if l]
    if len(lines) < 3:
        raise SystemExit("CSV je prazen: poženi tools/export_dataset.py")
    return lines[1].split(",")[0], lines[-1].split(",")[0]


def publish(token, base, new_version=None, do_publish=False, opener=urllib.request.urlopen, csv_path=CSV_PATH, meta_path=META_PATH):
    with open(csv_path, "rb") as f:
        payload = f.read()
    if any(w in payload.decode("utf-8", "ignore").lower() for w in FORBIDDEN):
        raise SystemExit("CSV omenja notranje meritve: ustavljeno (CLAUDE.md, zasebnost).")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    first, last = csv_span(csv_path)
    if new_version:
        dep = api("POST", f"{base}/deposit/depositions/{new_version}/actions/newversion", token, opener=opener)
        draft = api("GET", dep["links"]["latest_draft"], token, opener=opener)
        for old in draft.get("files", []):                       # nova različica prevzame stare datoteke: zamenjamo
            api("DELETE", f"{base}/deposit/depositions/{draft['id']}/files/{old['id']}", token, opener=opener)
    else:
        draft = api("POST", f"{base}/deposit/depositions", token, body={}, opener=opener)
    bucket = draft["links"]["bucket"]
    api("PUT", f"{bucket}/{os.path.basename(csv_path)}", token, raw=payload, opener=opener)
    api("PUT", f"{base}/deposit/depositions/{draft['id']}", token, body={"metadata": build_metadata(meta, first, last)}, opener=opener)
    out = {"id": draft["id"], "html": draft["links"].get("html"), "published": False}
    if do_publish:
        done = api("POST", f"{base}/deposit/depositions/{draft['id']}/actions/publish", token, opener=opener)
        out.update(published=True, doi=done.get("doi"))
        if done.get("doi"):
            meta["doi"] = done["doi"]
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
                f.write("\n")
    return out


def main(argv=None):
    a = argv if argv is not None else sys.argv[1:]
    token = os.environ.get("ZENODO_TOKEN", "")
    if not token:
        print("Manjka ZENODO_TOKEN (osebni žeton z deposit:write in deposit:actions). Nič ni bilo poslano.", file=sys.stderr)
        return 2
    base = "https://sandbox.zenodo.org/api" if "--sandbox" in a else "https://zenodo.org/api"
    nv = a[a.index("--new-version") + 1] if "--new-version" in a else None
    res = publish(token, base, nv, "--publish" in a)
    print(json.dumps(res, ensure_ascii=False))
    if not res["published"]:
        print("Osnutek je pripravljen, NI objavljen. Preglej ga na zgornji povezavi; objavi z --publish ali na zenodo.org.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
