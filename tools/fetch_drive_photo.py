#!/usr/bin/env python3
"""
tools/fetch_drive_photo.py — izbere naključno fotografijo Filipa Eremite iz
javno deljene Google Drive mape ("Razstava Rečica 2016") in jo prenese
lokalno, da jo generate_og_images.make_og() uporabi kot ozadje naslovne
kartice namesto fiksnega kataloga og/bg/*.jpg.

Rotacija: izogiba se ponovitvam, dokler niso vse fotografije v mapi
porabljene (stanje v tools/.photo_rotation_state.json, ki ga je treba
commitati skupaj z ostalimi spremembami objave).

Mapa mora biti deljena kot "kdorkoli s povezavo" -- dostop je prek golega
Google API ključa (GDRIVE_API_KEY), brez OAuth prijave. Za mape/datoteke s
starim (kratkim) ID-jem je poleg tega potreben resourceKey -- gl.
GDRIVE_FOLDER_RESOURCE_KEY.

Rabi okoljske spremenljivke:
  GDRIVE_FOLDER_ID            -- ID mape (iz deljene povezave)
  GDRIVE_API_KEY               -- Google Cloud API ključ (samo Drive API)
  GDRIVE_FOLDER_RESOURCE_KEY   -- opcijsko, samo za mape s starim ID-jem

Izpiše na stdout pot do prenesene fotke (ali nič, če ni na voljo --
klicatelj naj se v tem primeru vrne na privzeti og/bg/ katalog).

Usage:
  python3 tools/fetch_drive_photo.py [--out PATH]
"""
import json, os, random, sys, urllib.request, urllib.parse, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(ROOT, "tools", ".photo_rotation_state.json")
DEFAULT_OUT = os.path.join(ROOT, "tools", ".drive_photo_tmp.jpg")
DRIVE_API = "https://www.googleapis.com/drive/v3/files"


def load_state():
    if os.path.isfile(STATE_FILE):
        return json.load(open(STATE_FILE, encoding="utf-8"))
    return {"used": []}


def save_state(state):
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def list_photos(folder_id, api_key, folder_resource_key):
    q = f"'{folder_id}' in parents and mimeType contains 'image/' and trashed = false"
    qs = urllib.parse.urlencode({
        "q": q, "key": api_key,
        "fields": "files(id,name,resourceKey)", "pageSize": 1000,
    })
    req = urllib.request.Request(f"{DRIVE_API}?{qs}")
    if folder_resource_key:
        req.add_header("X-Goog-Drive-Resource-Keys", f"{folder_id}/{folder_resource_key}")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)["files"]


def download_photo(file_id, resource_key, api_key, out_path):
    qs = urllib.parse.urlencode({"alt": "media", "key": api_key})
    req = urllib.request.Request(f"{DRIVE_API}/{file_id}?{qs}")
    if resource_key:
        req.add_header("X-Goog-Drive-Resource-Keys", f"{file_id}/{resource_key}")
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    open(out_path, "wb").write(data)


def fetch_random_photo(out_path=DEFAULT_OUT):
    """Vrne pot do prenesene fotke, ali None, če ni na voljo (manjkajoči
    secreti, prazna mapa, napaka API-ja) -- klicatelj naj se v tem primeru
    vrne na privzeti og/bg/ katalog."""
    folder_id = os.environ.get("GDRIVE_FOLDER_ID")
    api_key = os.environ.get("GDRIVE_API_KEY")
    folder_resource_key = os.environ.get("GDRIVE_FOLDER_RESOURCE_KEY")
    if not folder_id or not api_key:
        print("GDRIVE_FOLDER_ID / GDRIVE_API_KEY nista nastavljena — preskačem (uporabljen bo privzet katalog).", file=sys.stderr)
        return None

    try:
        photos = list_photos(folder_id, api_key, folder_resource_key)
    except urllib.error.HTTPError as e:
        print(f"Napaka pri branju Drive mape {e.code}: {e.read().decode('utf-8', 'replace')[:300]}", file=sys.stderr)
        return None

    if not photos:
        print("V Drive mapi ni fotografij.", file=sys.stderr)
        return None

    state = load_state()
    used = set(state.get("used", []))
    unused = [p for p in photos if p["id"] not in used]
    if not unused:
        print("Vse fotografije porabljene — rotacija se začne znova.", file=sys.stderr)
        used = set()
        unused = photos

    chosen = random.choice(unused)
    try:
        download_photo(chosen["id"], chosen.get("resourceKey"), api_key, out_path)
    except urllib.error.HTTPError as e:
        print(f"Napaka pri prenosu fotke {e.code}: {e.read().decode('utf-8', 'replace')[:300]}", file=sys.stderr)
        return None

    used.add(chosen["id"])
    save_state({"used": sorted(used)})
    print(f"Izbrana fotka: {chosen['name']} ({len(used)}/{len(photos)} porabljenih v tem krogu)", file=sys.stderr)
    return out_path


def main():
    out_path = DEFAULT_OUT
    if "--out" in sys.argv:
        out_path = sys.argv[sys.argv.index("--out") + 1]
    result = fetch_random_photo(out_path)
    if result:
        print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
