// Test odločitvene logike čuvaja videza (tools/visual_watch.mjs): mediana, meje, razliv, axe.
// Brez brskalnika in omrežja; meritve same so na živi strani (visual-watch.yml).
import { median, evaluate, worstInteraction, CLS_MAX, AXE_BAD, INP_MAX, INP_POOR, INP_STEPS } from './visual_watch.mjs';
let fails = 0, checks = 0;
const ok = (c, name, d = '') => { checks++; if (!c) { fails++; console.log('  ✗', name, d); } };

ok(median([0.001, 0.172, 0.172]) === 0.172, 'mediana lihega števila');
ok(median([0.2, 0.4]) === 0.30000000000000004 || Math.abs(median([0.2, 0.4]) - 0.3) < 1e-9, 'mediana sodega števila');
ok(Number.isNaN(median([])), 'mediana praznega seznama je NaN');

const good = { cls: { mobile: [0.01, 0.02, 0.04], desktop: [0.006, 0.006, 0.057] }, overflow: [{ path: '/', sw: 360, W: 360, over: [] }], axe: [{ theme: 'dark', id: 'color-contrast', impact: 'moderate', nodes: 1 }] };
ok(evaluate(good).length === 0, 'dobro stanje brez napak', evaluate(good).join('|'));

// en slab tek od treh je šum (primer iz 5. 11. 2026: [0,001, 0,172, 0,172] je napaka, [0,01, 0,02, 0,5] ni)
ok(evaluate({ ...good, cls: { mobile: [0.01, 0.02, 0.5], desktop: [0.006] } }).length === 0, 'osamljen izstopajoč tek ni napaka');
ok(evaluate({ ...good, cls: { mobile: [0.001, 0.172, 0.172], desktop: [0.006] } }).length === 1, 'dva slaba teka od treh sta napaka (mobile)');
ok(evaluate({ ...good, cls: { mobile: [0.01], desktop: [0.158, 0.158, 0.158] } }).some(f => /desktop/.test(f)), 'namizni CLS 0,158 je napaka');
ok(evaluate({ ...good, cls: { mobile: [], desktop: [0.006] } }).some(f => /brez meritve/.test(f)), 'brez meritve je napaka, ne tiha uspešnost');
ok(evaluate({ ...good, cls: { mobile: [CLS_MAX], desktop: [0.006] } }).length === 0, 'natanko na meji je še v redu');

ok(evaluate({ ...good, overflow: [{ path: '/zima/', sw: 400, W: 360, over: ['TABLE.stats'] }] }).some(f => /razliv \/zima\//.test(f) && /TABLE\.stats/.test(f)), 'razliv javi stran in kriv element');
ok(AXE_BAD.includes('serious') && AXE_BAD.includes('critical') && !AXE_BAD.includes('moderate'), 'axe šteje samo resne in kritične');
ok(evaluate({ ...good, axe: [{ theme: 'light', id: 'color-contrast', impact: 'serious', nodes: 3 }] }).some(f => /light/.test(f) && /color-contrast/.test(f)), 'resna axe kršitev je napaka');

// odzivnost (INP)
ok(worstInteraction([{ id: 1, d: 184 }, { id: 1, d: 120 }, { id: 2, d: 360 }, { id: 0, d: 900 }]) === 360, 'najdaljši dotik; dogodki brez interactionId se ne štejejo');
ok(worstInteraction([{ id: 7, d: 100 }, { id: 7, d: 328 }]) === 328, 'dogodki istega dotika štejejo kot največji');
ok(Number.isNaN(worstInteraction([])) && Number.isNaN(worstInteraction([{ id: 0, d: 500 }])) && Number.isNaN(worstInteraction(undefined)), 'brez interakcij je NaN, ne 0');
ok(evaluate({ ...good, inp: { mobile: [424, 360, 528], desktop: [576, 568, 640] } }).length === 0, 'današnje stanje (360–640 ms) ni napaka');
ok(evaluate({ ...good, inp: { mobile: [900, 950, 400], desktop: [500] } }).some(f => /INP mobile/.test(f)), 'mediana INP nad mejo je napaka');
ok(evaluate({ ...good, inp: { mobile: [400, 400, 2000], desktop: [500] } }).length === 0, 'osamljen počasen tek ni napaka');
ok(evaluate({ ...good, inp: { mobile: [INP_MAX], desktop: [500] } }).length === 0, 'INP natanko na meji je še v redu');
ok(evaluate({ ...good, inp: { mobile: [], desktop: [500] } }).some(f => /INP mobile.*brez meritve/.test(f)), 'brez meritve INP je napaka');
ok(evaluate(good).length === 0, 'brez podatka o INP (staro klicanje) ne pade');
ok(INP_POOR < INP_MAX && INP_POOR === 500, 'CWV meja »slabo« je 500 ms in pod varovalko');
ok(INP_STEPS.includes('#tab-btn-mtr') && INP_STEPS.includes('#more-toggle'), 'dotiki merijo zavihek MTR in preklop podrobnosti');

console.log(`${checks} preverjanj, ${fails} napak`);
process.exit(fails ? 1 : 0);
