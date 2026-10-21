# Emoji → SVG ikone (faza 2 redizajna)

Ikone so Lucide (ISC, `tools/icons/LICENSE-lucide.txt`), vdelane kot inline sprite v `index.html`
(`<svg id="icon-sprite">`, `<use href="#i-ime">`). Orodje: `python3 tools/emoji_to_icons.py`.

## Preslikava

| Ikona | Emoji |
|---|---|
| `alarm-clock` | ⏰ |
| `baby` | 👧 |
| `bell` | 🔔 |
| `book-open` | 📖 |
| `brain` | 🧠 |
| `bug` | 🐞 🐛 |
| `calendar` | 📅 🗓 📆 |
| `camera` | 📷 📸 |
| `chart-column` | 📊 |
| `circle` | 🔵 |
| `circle-help` | ❓ |
| `clipboard-list` | 📋 |
| `clock` | 🕐 |
| `cloud` | ☁ |
| `cloud-fog` | 🌫 |
| `cloud-lightning` | 🌩 ⛈ |
| `cloud-rain` | 🌧 |
| `cloud-sun` | 🌤 |
| `compass` | 🧭 |
| `drama` | 🎭 |
| `droplet` | 💧 |
| `droplets` | 💦 |
| `flame` | 🔥 🕯 |
| `flask-conical` | 🧪 |
| `flower` | 🌸 |
| `flower-2` | 🌹 |
| `folder-open` | 📂 |
| `footprints` | 🥾 |
| `gift` | 🎁 |
| `globe` | 🌍 🌐 |
| `headphones` | 🎧 |
| `hourglass` | ⏳ |
| `house` | 🏘 |
| `image` | 🖼 |
| `leaf` | 🍂 |
| `leafy-green` | 🌿 |
| `library` | 📚 |
| `link` | 🔗 |
| `lock` | 🔒 |
| `map` | 🗺 |
| `map-pin` | 📍 📌 |
| `medal` | 🏅 |
| `menu` | ☰ |
| `message-circle` | 💬 |
| `microscope` | 🔬 |
| `minimize-2` | 🗜 |
| `moon` | 🌙 🌓 |
| `moon-star` | 🌌 |
| `mountain` | ⛰ |
| `mountain-snow` | 🏔 |
| `pause` | ⏸ |
| `pencil` | 📝 |
| `pill` | 💊 |
| `plane` | ✈ |
| `play` | ▶ |
| `radio-tower` | 📡 |
| `refresh-cw` | 🔄 |
| `rotate-cw` | ↻ |
| `ruler` | 📐 |
| `satellite` | 🛰 |
| `school` | 🏫 |
| `scroll` | 📜 |
| `search` | 🔍 |
| `settings` | ⚙ |
| `share-2` | ⬆ |
| `shield` | 🛡 |
| `smartphone` | 📲 |
| `snowflake` | ❄ |
| `sparkles` | 🔮 💥 |
| `sprout` | 🌱 🍄 |
| `sun` | ☀ 🌵 |
| `sunrise` | 🌅 |
| `swords` | ⚔ |
| `tag` | 🏷 |
| `target` | 🎯 |
| `telescope` | 🔭 |
| `thermometer` | 🌡 |
| `thermometer-snowflake` | 🧊 |
| `timer` | ⏱ |
| `tornado` | 🌀 |
| `trash-2` | 🗑 |
| `tree-palm` | 🏖 |
| `tree-pine` | 🌲 |
| `trending-down` | 📉 |
| `trending-up` | 📈 |
| `triangle-alert` | ⚠ |
| `trophy` | 🏆 |
| `umbrella` | ☔ |
| `users` | 👯 |
| `waves` | 🌊 |
| `wheat` | 🌾 |
| `wind` | 💨 🪂 🌬 |
| `zap` | ⚡ |

## Namerno ohranjeni emojiji

- Vsebina besedil in analiz (`<li>`, odstavki), blogi in članki.
- `<option>` (SVG ne more v izbirnik).
- Skupnostni/uporabniški vnosi: `.community-*`, `.feel-poll-emoji`.
- Taksonomski čipi `.inat-filter` (🐸 🦎 🐦 …): Lucide nima ustreznih živali.
- Tipografske puščice (↑ ↓ ↔ →) v besedilu.
- Tabele v `app.js`: vremenske kode (`cond.icon`), fenologija, cvetovi, `sc-risk-icon`, `.dfc-icon` (generator).
- Podstrani z lastnimi generatorji (ne nalagajo `style.css` in spritea).

## Dodajanje ikone

1. Kopiraj `<ime>.svg` iz `lucide-static/icons/` v `tools/icons/lucide/`.
2. Dodaj vnos v `MAP` (emoji → ime) ali v `EXTRA` (če jo uporablja samo JS).
3. Poženi `python3 tools/emoji_to_icons.py`, nato `npm run minify`.
4. V JS uporabi `_ico('ime')` (app.js).
