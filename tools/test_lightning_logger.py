#!/usr/bin/env python3
"""tools/test_lightning_logger.py — LightningLogger (worker.js): ponovna vzpostavitev in zombi povezave.

Požene PRAVI razred v simulaciji (tools/_lightning_sim.mjs: lažen WebSocket, SQLite, alarmi) in preveri,
da prekinitev sproži alarm (ne čaka 5 min), se zataknjeno odpiranje zamenja, tiha (zombi) povezava
ne šteje v pokritost in se zamenja, ni podvojenih vtičnic.
Zaženi:  python3 tools/test_lightning_logger.py
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
p = subprocess.run(["node", os.path.join(HERE, "_lightning_sim.mjs")], capture_output=True, text=True, cwd=os.path.dirname(HERE), timeout=60)
try:
    r = json.loads(p.stdout)
except ValueError:
    print("✗ simulacija se ne zažene:", (p.stdout + p.stderr)[:400])
    sys.exit(1)
EXPECT = {
    "first_sockets": 1, "connecting_no_dup": 1, "stuck_replaced": 2, "stuck_old_closed": True,
    "live_no_new": True, "live_connected": True, "live_counts_uptime": True,
    "drop_ws_null": True, "drop_alarm": True, "alarm_reconnected": True, "alarm_reschedules_while_connecting": True,
    "zombie_not_counted": True, "zombie_replaced": True, "zombie_age_reported": True,
    "message_keeps_alive": True, "error_alarm": True, "stale_close_ignored": True, "host_rotation": True,
    "msg_uptime_once_per_slot": True, "msg_uptime_next_slot": True,
}
bad = {k: (r.get(k), v) for k, v in EXPECT.items() if r.get(k) != v}
for k, (got, want) in bad.items():
    print(f"  ✗ {k}: dobil {got!r}, pričakovano {want!r}")
print(f"\n{len(EXPECT)} preverjanj, {len(bad)} napak")
sys.exit(1 if bad else 0)
