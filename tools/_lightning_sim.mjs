/*
 * tools/_lightning_sim.mjs — simulacija PRAVEGA razreda LightningLogger iz worker.js z lažnim
 * WebSocketom, SQLite in alarmi; izpiše rezultate scenarijev (JSON) za tools/test_lightning_logger.py.
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
const a = src.indexOf('function _ltgDecode(b)');
const b = src.indexOf('async function _cronKeepLightningAlive');
if (a < 0 || b < a) throw new Error('blok LightningLogger v worker.js ni najden');
const code = src.slice(a, b).replace('export class LightningLogger', 'class LightningLogger');

let clock = 1_000_000_000_000;
class FakeDate extends Date { static now() { return clock; } constructor(...x) { super(...(x.length ? x : [clock])); } }
const sockets = [];
class FakeWS {
  constructor(url) { this.url = url; this.readyState = 0; this.h = {}; this.sent = []; this.closed = false; sockets.push(this); }
  addEventListener(t, f) { (this.h[t] = this.h[t] || []).push(f); }
  send(m) { this.sent.push(m); }
  close() { this.closed = true; this.readyState = 3; }
  fire(t, ev) { (this.h[t] || []).forEach(f => f(ev)); }
  open() { this.readyState = 1; this.fire('open'); }
  drop() { this.readyState = 3; this.fire('close'); }
}
const alarms = [];
const sqlLog = [];
const ctx = vm.createContext({
  Date: FakeDate, WebSocket: FakeWS, JSON, Math, Number, Promise, String, isFinite: Number.isFinite, console,
  DurableObject: class { constructor(c, e) { this.ctx = c; this.env = e; } },
});
vm.runInContext(code + '\nglobalThis.LightningLogger = LightningLogger;', ctx);

function make() {
  sockets.length = 0; alarms.length = 0; sqlLog.length = 0;
  const dctx = {
    blockConcurrencyWhile: async (f) => f(),
    storage: {
      sql: { exec: (q, ...p) => { sqlLog.push(q.trim().split(/\s+/).slice(0, 3).join(' ')); return { toArray: () => [{ n: 0, first: null }] }; } },
      setAlarm: (t) => alarms.push(t),
    },
  };
  return new ctx.LightningLogger(dctx, {});
}

const out = {};
// 1. prvi keepAlive odpre vtičnico (in ne dveh)
let d = make();
await d.keepAlive();
out.first_sockets = sockets.length;
// 2. še odpiranje: naslednji keepAlive ne ustvari druge vtičnice
clock += 5000; await d.keepAlive();
out.connecting_no_dup = sockets.length;
// 3. odpiranje se zatakne > 20 s: vtičnica se zamenja in stara zapre
clock += 30000; await d.keepAlive();
out.stuck_replaced = sockets.length; out.stuck_old_closed = sockets[0].closed;
// 4. odprta in živa: keepAlive ne naredi nič novega, pokritost se zabeleži
sockets[1].open(); sockets[1].fire('message', { data: 'x' });
const before = sockets.length; sqlLog.length = 0;
const r4 = await d.keepAlive();
out.live_no_new = sockets.length === before; out.live_connected = r4.connected;
out.live_counts_uptime = sqlLog.some(q => q.startsWith('INSERT OR IGNORE'));
// 5. prekinitev: vtičnica null, alarm nastavljen takoj (ne šele ob cronu)
alarms.length = 0; sockets[1].drop();
out.drop_ws_null = d.ws === null; out.drop_alarm = alarms.length === 1 && alarms[0] - clock === 10000;
// 6. alarm vzpostavi novo povezavo; če se ne odpre, naslednji alarm
await d.alarm();
out.alarm_reconnected = sockets.length === before + 1;
out.alarm_reschedules_while_connecting = alarms.length === 2;
// 7. zombi: odprta, a 4 min brez sporočila → zamenjana, v pokritost ne šteje
const live = sockets[sockets.length - 1]; live.open(); live.fire('message', { data: 'x' });
clock += 240000; sqlLog.length = 0;
const n7 = sockets.length;
const r7 = await d.keepAlive();
out.zombie_not_counted = !sqlLog.some(q => q.startsWith('INSERT OR IGNORE'));
out.zombie_replaced = sockets.length === n7 + 1 && live.closed;
out.zombie_age_reported = r7.last_msg_age_s >= 240;
// 8. sporočilo osveži »živost«
const nw = sockets[sockets.length - 1]; nw.open(); clock += 100000; nw.fire('message', { data: 'x' }); clock += 100000;
const n8 = sockets.length; await d.keepAlive();
out.message_keeps_alive = sockets.length === n8;
// 9. napaka (error) tudi sproži alarm
alarms.length = 0; nw.readyState = 3; nw.fire('error'); out.error_alarm = alarms.length === 1;
// 10. vtičnica zamenjana: stari dogodek close ne sme pobrisati nove
d = make(); await d.keepAlive(); const o1 = sockets[0]; clock += 30000; await d.keepAlive(); const o2 = sockets[1];
o1.fire('close'); out.stale_close_ignored = d.ws === o2;
out.host_rotation = new Set(sockets.map(s => s.url)).size === 2;
process.stdout.write(JSON.stringify(out));
