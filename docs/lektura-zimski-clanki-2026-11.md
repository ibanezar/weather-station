# Lektura osmih zimskih člankov (5. 11. 2026)

Ročni pregled po `docs/slog-pisanja.md` (lektura prek API-ja je izklopljena od 2. 10. 2026). `tools/lektura_scan.py` je v osmih člankih našel 0 mest; popravki spodaj so iz branja.
Popravljeno je v objavljenih `blog/<slug>.html` in v `tools/generate_zima_clanki.py` (isto besedilo). Generatorja ni mogoče znova pognati (assert na `history.json` do 26. 10.), zato sta kopiji usklajeni ročno.
Za sedem popravljenih člankov sta `dateModified` (JSON-LD) in `updated` v `blog.json` nastavljena na 5. 11. 2026. **Številke in grafi so nedotaknjeni.**

| Članek | Popravek | Razlog |
|---|---|---|
| kdaj-pade-prvi-sneg-v-dolini | »Zunaj tega razpona ga v teh zimah ni bilo.« → »Pred 18. novembrom v teh zimah nov sneg ni padel.« | prvotni stavek je bil tavtologija (prvi sneg je po definiciji v razponu) |
| isti | »datum pa se spreminja za približno tri tedne« → »datum pa niha v razponu približno treh tednov« | slovnica/pomen |
| bela-bozic | »Obeh številk ne smete primerjati« → »ni mogoče primerjati« | prepoved ni na mestu, gre za dejstvo |
| isti | »Takrat sneg ni bil blizu.« → »V dolini takrat ni bilo hladnih padavin.« | prvotno ni bilo podprto (Črnivec nima podatkov za 2019/2020); zdaj je trditev iz tabele |
| isti | nov odstavek o božiču 2021 (9,2 mm, –1,0 °C, hladen padavinski dan; Črnivec brez odeje) in naslov »Božiči so bili zelo različni« | naslov je obljubil tri zgodbe, besedilo je pokrilo šest od sedmih božičev; 2021 je bil tihi izpad, čeprav je eden od dveh »hladnih padavinskih« božičev v uvodu |
| isti | »zima 2023/24, je bil topel in mokar« → »Najbližji lokalni analog je zima 2023/24, ki je bila topla in mokra« | ujemanje spola |
| zled-ali-poledica | »Kaplje skozi hladno plast padejo prehitro, da bi zmrznile« → »se v hladni plasti podhladijo in v zraku ne zmrznejo« | skladno s sliko in vsebinsko točneje (podhladitev, ne hitrost) |
| crnivec-pozimi | »Snežne odeje je bilo v zimi 22–57 dni« → »Snežna odeja je v posamezni zimi ležala 22–57 dni« (tudi ploščica) | dvoumno »v zimi« |
| prvi-sneg-golte-solcava | »Več o razmerah: o razmerah na Goltah najdete več v članku …« → »Razmere na Goltah: več v članku …« | ponavljanje |
| stopinjski-dnevi | »V zadnjih petih kurilnih sezonah« → »V petih popolnih kurilnih sezonah« | zadnja sezona (2025/26) je izpuščena, torej niso »zadnjih pet« |
| kdaj-se-dvigne-jutranja-megla | dodan pogoj »veter pod 3 km/h« v uvod, ploščico in omejitve (jutro ob 7. uri) | kodа (`at7 = sat(h[7]) and wind < 3`) pogoj ima, besedilo ga je zamolčalo: število 23 od 25 je z njim |
| isti | »Samo ena jesen« → »Samo ena sezona«; »ki ga ugotavljam« → »ki ga računam« | zapis sega od julija; leksika |
| kdaj-menjati-zimske-gume | brez sprememb | |

## Ni spremenjeno (za Filipovo odločitev)

- **Žled 2014** (`zled-ali-poledica`): »žled je prekril velik del Slovenije in povzročil veliko škodo« nima vira v članku; omejitve pravijo, da uradnih poročil nisem povzemal. Predlog: dodaj vir (ARSO/URSZR) ali omehčaj.
- **Naslov »… Izmerjeno«** (`kdaj-se-dvigne-jutranja-megla`): merjena je nasičenost zraka, ne megla; članek to sam pove. Naslov lahko bralca zavede (`seo_title`, OG, FB).
- **»okoli 1528 m«** (inverzija): lažna natančnost modelske ocene; po vodniku zaokrožiti (npr. »okoli 1500 m«), a potem Menina planina (1500 m) ni več razločljiva.
- **Povezave ARSO** (Črnivec): vir je naveden z imenom postaje; 14. člen ZDMHS terja »Vir: ARSO«, `test_arso_vir.py` teh strani ne zajema.
