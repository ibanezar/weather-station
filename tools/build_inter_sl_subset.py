#!/usr/bin/env python3
"""Podmnožica Inter (latin-ext) samo s slovenskimi/hrvaškimi znaki: Č č Š š Ž ž Ć ć Đ đ.

Zakaj: latin-ext (133 KiB) je bil preloadan samo zaradi č/š/ž (latin pokriva do U+00FF),
v laboratoriju pa je držal FCP. Podmnožica je nekaj KiB. Polni latin-ext ostane v fonts.css
kot rezerva za druge znake (naloži se samo, če strani res rabi znak zunaj podmnožice).

Poganjanje (enkratno; izhod je commitan): python3 tools/build_inter_sl_subset.py
Potrebuje `pip install fonttools brotli`. Osi spremenljive pisave se ohranijo.
"""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "fonts" / "Inter-latin-ext-normal-400.woff2"
DST = ROOT / "fonts" / "Inter-sl-normal-400.woff2"
# Mora biti enako kot unicode-range v fonts.css (@font-face »sl«).
UNICODES = "U+0106-0107,U+010C-010D,U+0110-0111,U+0160-0161,U+017D-017E"

subprocess.run([
    sys.executable, "-m", "fontTools.subset", str(SRC), f"--unicodes={UNICODES}",
    "--flavor=woff2", "--layout-features=*", f"--output-file={DST}",
], check=True)
print(f"{DST.name}: {DST.stat().st_size} B (izvor {SRC.stat().st_size} B)")
