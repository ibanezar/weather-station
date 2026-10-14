// og/valovi-src/valovi.html -> og/valovi.jpg (1200x630). Poganja se ročno po build_valovi_brand.py.
import { chromium } from 'playwright';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const b = await chromium.launch();
const pg = await b.newPage({ viewport: { width: 1200, height: 630 } });
await pg.goto('file://' + path.join(root, 'og/valovi-src/valovi.html'));
await pg.screenshot({ path: path.join(root, 'og/valovi.jpg'), type: 'jpeg', quality: 88 });
await b.close();
