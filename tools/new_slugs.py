#!/usr/bin/env python3
"""
tools/new_slugs.py — slugi člankov, ki so v blog.json NOVI glede na posnetek.

Uporaba v workflowu (invasive-watch.yml):
  cp blog.json "$RUNNER_TEMP/blog_before.json"        # pred generiranjem
  ...
  python3 tools/new_slugs.py "$RUNNER_TEMP/blog_before.json" invazivka

Prej so koraki za FB/IG/IndexNow vzeli *vse* članke s predpono iz blog.json
(zadnjih 5), zato se je vsak ponedeljek znova objavilo isto (opaženo na FB:
isti dve objavi tedenskega pregleda šestkrat zapored). Zdaj gredo ven samo
slugi, ki jih prej ni bilo. Izpiše po en slug na vrstico, najnovejše prve.

  python3 tools/new_slugs.py BEFORE.json [predpona] [--max N]
"""
import json
import sys


def new_slugs(before_path, after_path="blog.json", prefix="", limit=5):
    try:
        before = {p.get("slug") for p in json.load(open(before_path, encoding="utf-8"))}
    except FileNotFoundError:
        before = set()
    after = json.load(open(after_path, encoding="utf-8"))
    out = [p["slug"] for p in after
           if p.get("slug") and p["slug"] not in before and p["slug"].startswith(prefix)]
    return out[:limit]


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    limit = 5
    if "--max" in argv:
        limit = int(argv[argv.index("--max") + 1])
        args = [a for a in args if a != str(limit)]
    if not args:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    prefix = args[1] if len(args) > 1 else ""
    for slug in new_slugs(args[0], prefix=prefix, limit=limit):
        print(slug)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
