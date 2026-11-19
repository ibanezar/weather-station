#!/usr/bin/env python3
"""tools/test_workflow_git_add.py — varovalka pred tihim ustavljanjem commitov v workflowih (19. 11. 2026).

`git add` s potjo, ki ne obstaja (»pathspec did not match«), prekine CELOTEN ukaz in ne doda nič; `|| true` napako požre, korak pa izpiše »Ni sprememb.«
Tako se je od 18. 11. dnevni tek seo-smart-routine.yml tiho prenehal commitati (data/sneg-porocila-dnevno.csv ob prvem teku še ne obstaja).
Test razčleni vse `git add` v `.github/workflows/*.yml` in zavrne dobesedno pot, ki v repozitoriju ne obstaja, razen če je ukaz v zanki z
`[ -e "$p" ]` (vsaka pot posebej). Poti s spremenljivkami, glob znaki in izključitvami (`:!`) se preskočijo.
"""
import glob
import os
import re
import shlex
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []
# (workflow, pot) -> razlog, zakaj je izjema v redu
ALLOW = {
    ("frost-warning.yml", "tools/.frost_gate_state.json"): "datoteko zapiše `frost_gate.py mark` v istem koraku, tik pred `git add`",
    ("makro-daily.yml", "img/makro/"): "workflow je izklopljen (`if: ${{ false }}`); ob vklopu mora biti pot varovana ali mapa obstajati",
}


def run_texts(path):
    """Vsebina vseh `run:` blokov (en niz na blok, nadaljevanja vrstic z \\ so zlepljena)."""
    lines = open(path, encoding="utf-8").read().split("\n")
    blocks, i = [], 0
    while i < len(lines):
        m = re.match(r"^(\s*)(?:- )?run:\s*(.*)$", lines[i])
        if not m:
            i += 1
            continue
        indent, rest = len(m.group(1)), m.group(2).strip()
        if rest and rest not in ("|", ">", "|-", ">-"):
            blocks.append(rest)
            i += 1
            continue
        body = []
        i += 1
        while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > indent):
            body.append(lines[i])
            i += 1
        blocks.append("\n".join(body))
    return [re.sub(r"\\\n\s*", " ", b) for b in blocks]


def literal_paths(cmd):
    """Dobesedne poti iz enega `git add …` ukaza (brez možnosti, spremenljivk, globov, izključitev)."""
    cmd = cmd.split("||")[0].split("&&")[0].split(";")[0]
    try:
        toks = shlex.split(cmd)
    except ValueError:
        return []
    out = []
    for t in toks:
        if t.startswith("-") or t.startswith(":") or any(c in t for c in "$*?[{`("):
            continue
        out.append(t)
    return out


def check_file(path):
    name = os.path.basename(path)
    text = open(path, encoding="utf-8").read()
    # workflowi z `working-directory:` imajo poti relativne na to mapo
    wds = [""] + re.findall(r"working-directory:\s*(\S+)", text)
    for block in run_texts(path):
        guarded = '[ -e "$' in block or "[ -e $" in block or "test -e" in block
        for m in re.finditer(r"(?m)^\s*(?:[A-Za-z_ ]*?)git add\s+(.+)$", block):
            before = block[:m.start()]
            for p in literal_paths(m.group(1)):
                exists = any(os.path.exists(os.path.join(ROOT, wd, p)) for wd in wds)
                produced = p.rstrip("/") in before   # pot nastane v istem koraku pred `git add` (skript jo zapiše)
                if not exists and not guarded and not produced and (name, p) not in ALLOW:
                    FAILS.append(f"{name}: git add »{p}« — pot ne obstaja; en manjkajoč pathspec prekine ves ukaz")


def main():
    files = sorted(glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")))
    for f in files:
        check_file(f)
    print(f"{len(files)} workflowov pregledanih")
    for f in FAILS:
        print("  ✗", f)
    print(f"{len(FAILS)} napak" if FAILS else "Vse poti v git add obstajajo (ali so varovane).")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
