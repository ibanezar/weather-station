# Ilustracije za podstrani `/podjetja/` — navodila za generiranje

Za tri nove podstrani (hmeljarji, komunala, zimska služba) še ni lastnih ilustracij: kartica na glavni strani je brez slike,
hero uporablja splošno ilustracijo postaje. Spodaj so prompti za generator slik (ista vrsta kot `primer-*.webp`).

## Skupna pravila (veljajo za vse)

- **To so ilustracije, ne fotografije naše opreme ali strank.** Na strani imajo vidno oznako »Ilustracija« in splošno opombo (`ILLUS_NOTE`); ne trdi, da je prikazana postaja naša ali da je to konkretna stranka.
- **Oprema je splošna** (Ecowitt-tipa: merilnik vetra na vrhu droga, zaščita za temperaturo in vlago, dežemer, sončna celica). **Brez logotipov, napisov, registrskih tablic in berljivega besedila** na sliki.
- **Brez prepoznavnih obrazov**: ljudje samo od zadaj, od daleč ali v profilu, v zaščitni opremi.
- **Format**: ležeč 3:2, izvirnik vsaj 1800 × 1200 px (shranim kot 1200 × 800 WebP). Hero na namizju prireže na ~4:5 okrog levih 60 % slike (`object-position: 30% 50%`), na telefonu na 16:10: **postaja in glavni motiv naj bosta v levi do sredinski tretjini**, zgoraj in spodaj naj ostane prostor.
- **Slog**: fotorealističen, naravna svetloba, nasičenost zmerna (kot obstoječe slike), brez HDR-videza, brez risanega sloga.
- **Pokrajina**: zgornja Savinjska dolina, alpski gozdnati griči, slovenska arhitektura (strma strešna kritina, lesene fasade).
- **Datoteke** poimenuj `primer-hmelj`, `primer-komunala`, `primer-zimska`, pošlji PNG ali JPG; WebP in vpis v generator (`img`, `w`, `h`, `alt` v `CASES`) naredim jaz.

Skupni **negativni prompt** (če ga generator ima): `text, letters, logo, watermark, brand name, license plate, recognizable face, cartoon, illustration style, oversaturated, HDR, distorted equipment, extra limbs, warped poles`

## 1. Hmeljarji — `primer-hmelj`

Sceno naj nosi visoka hmeljska žičnica in jutranja megla; postaja stoji med vrstami, nizko ob tleh nasada, ne na vrhu žičnice.

```
Photorealistic landscape photo of a hop yard (hop field) in the Savinja valley, Slovenia, early morning. Tall hop trellis poles about 7 metres high with wires and lush green hop bines climbing up them, rows converging into the distance. Low mist between the rows, forested Alpine foothills in the background, soft golden light from the left. In the left third of the frame, between two rows, a compact generic weather station on a short mast (small anemometer on top, white louvered radiation shield, tipping-bucket rain gauge, small solar panel), sharp and in focus. No people, no text, no logos. Natural colours, shallow mist, 3:2 landscape, high detail.
```

Alt za stran (predlog): *Ilustracija: vremenska postaja v hmeljišču z visokimi žičnicami ob jutranji megli*.

## 2. Komunala — `primer-komunala`

Motiv naj pokaže javno službo ob odvodnjavanju/javni površini po nalivu, ne konkretnega podjetja ali vozila z napisom.

```
Photorealistic photo of a small Alpine town street in Slovenia right after a heavy rain shower, wet asphalt reflecting the sky, a storm drain and a roadside green strip with trees. A municipal utility worker in an orange high-visibility vest and helmet, seen from behind and at a distance, checks a storm drain next to a plain white utility pickup truck with no markings. In the left third of the frame, a generic weather station on a mast beside the road (anemometer on top, white radiation shield, rain gauge, small solar panel), sharp and in focus. Overcast sky with breaking clouds, houses with steep roofs and forested hills in the background. No readable text, no logos, no license plates, no recognizable faces. Natural muted colours, 3:2 landscape, high detail.
```

Alt za stran (predlog): *Ilustracija: komunalni delavec ob odtoku po nalivu in vremenska postaja ob cesti v alpskem kraju*.

## 3. Zimska služba — `primer-zimska`

Pomembno: postaja stoji **ob cesti na drogu in meri zrak**, ne vgrajena v cestišče (naša postaja temperature cestišča ne meri); sneg ob robu ceste, cesta naj bo vidno očiščena ali mokra, ne zasnežena do neprevoznosti.

```
Photorealistic photo of a mountain road in Slovenia at dawn in winter, blue hour turning to first light. A plain orange snow plough truck with flashing amber beacons, seen at a distance on the road, spreading a light trail of grit; snow banks along the edges, frost on the roadside grass, spruce forest and snowy ridges behind. In the left third of the frame, a generic weather station on a roadside post next to the guardrail (anemometer on top, white radiation shield, rain gauge, small solar panel), dusted with frost and in sharp focus, standing beside the road, not on it. Cold blue-and-warm-amber palette, a few light snowflakes. No readable text, no logos, no license plates, no recognizable faces. 3:2 landscape, high detail.
```

Alt za stran (predlog): *Ilustracija: pluženje ceste ob zori in vremenska postaja ob cestišču pozimi*.

## 4. Gozdarstvo (pripravljeno vnaprej, še ni odločeno)

Podstrani za gozdarstvo še ni (čaka na odločitve o ponudbi); prompt je tu, da ne zamuja.

```
Photorealistic photo of a mixed spruce and beech forest edge in the Slovenian Alps on a windy day, tall trees slightly swaying, a forest access road with stacked timber logs at the side. In the left third of the frame, in a small clearing, a generic weather station on a tall mast (anemometer on top, white radiation shield, rain gauge, solar panel), sharp and in focus. A forestry worker in an orange helmet and protective trousers, from behind and at a distance. Moody overcast light, breaking clouds. No readable text, no logos, no recognizable faces. 3:2 landscape, high detail.
```

Alt (predlog): *Ilustracija: vremenska postaja na jasi ob gozdni cesti z zloženim lesom*.

## Po prejemu slik

1. Datoteke v `podjetja/img/` kot `primer-<ime>.webp` (1200 × 800, kakovost ~80).
2. V `CASES` nastavi `img`, `w`, `h`, `alt` (zdaj `None`); `python3 tools/generate_podjetja_page.py`; `python3 tools/test_podjetja.py`.
3. Preveri pregled na 1280 in 369 px (postaja in motiv v levi tretjini, oznaka »Ilustracija« ne prekriva postaje).
