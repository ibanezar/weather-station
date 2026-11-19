#!/usr/bin/env python3
"""tools/test_dispatch_force.py — workerjev dispatch workflowov s časovnimi vrati mora poslati `force: "false"` (19. 11. 2026).

Pri `workflow_dispatch` je privzeti `force` »true«, kar OBIDE okno v `tools/*_gate.py`: workflow bi sestavil/objavil ob vsakem klicu
(npr. dnevna zgodba štirikrat na dan). Zato mora vsak workflow, ki ga `_cronDispatchScheduledWorkflows()` v `worker.js` sproži in ima vrata
(`tools/<ime>_gate.py check`), dobiti `{ force: "false" }`. Test razčleni worker.js in workflowe; dodan ob sprožitvi `padalci-forecast.yml` (issue #1517).
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
worker = open(os.path.join(ROOT, "worker.js"), encoding="utf-8").read()
FAILS = []


def check(ok, name, detail=""):
    if not ok:
        FAILS.append(name)
        print(f"  ✗ {name} {detail}")


# samo klici v telesu _cronDispatchScheduledWorkflows (komentarji z zakomentiranimi klici se preskočijo)
start = worker.index("async function _cronDispatchScheduledWorkflows")
body = worker[start:worker.index("\n}\n", start)]
calls = []
for line in body.split("\n"):
    if line.strip().startswith("//"):
        continue
    m = re.search(r'_cronDispatchGithubWorkflow\(env,\s*"([^"]+\.yml)"(?:,\s*(\{[^}]*\}))?\)', line)
    if m:
        calls.append((m.group(1), m.group(2) or ""))

check(len(calls) >= 3, "razčlenjeni klici dispatcha", str(calls))
names = {c[0] for c in calls}
check({"daily-story.yml", "vodostaj-forecast.yml", "padalci-forecast.yml"} <= names, "pričakovani workflowi so v dispatchu", str(names))

for wf, opts in calls:
    path = os.path.join(ROOT, ".github", "workflows", wf)
    check(os.path.exists(path), f"workflow obstaja: {wf}")
    if not os.path.exists(path):
        continue
    text = open(path, encoding="utf-8").read()
    gated = bool(re.search(r"tools/\w+_gate\.py\s+check", text))
    has_force_input = "force:" in text and "workflow_dispatch" in text
    if gated:
        check(re.search(r'force:\s*"false"', opts) is not None, f"{wf} ima vrata: dispatch mora poslati force \"false\"", opts or "(brez opcij)")
    check(not (re.search(r'force:\s*"true"', opts)), f"{wf}: force \"true\" bi obšel vrata")
    if has_force_input is False and opts:
        check(False, f"{wf} nima vhoda force, a dispatch ga pošilja", opts)

print(f"{len(calls)} dispatchev preverjenih, {len(FAILS)} napak")
sys.exit(1 if FAILS else 0)
