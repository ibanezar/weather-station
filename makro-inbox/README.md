# `/makro/` — nabiralnik fotografij

Sem naložiš surove makro fotografije (žuželke, kasneje morda gobe/rastline).
`tools/generate_makro_post.py` teče enkrat dnevno (`makro-daily.yml`) in
objavi **eno** čakajočo fotko — nabiralnik se torej prazni z enim vnosom na
dan, ne vse naenkrat.

## Kako naložiti fotko

1. Datoteko poimenuj `LETO-MESEC-DAN_kratek-opis.jpg`, npr.
   `2026-08-30_kosceva-muha.jpg` (datum v imenu je rezerva, če EXIF manjka).
2. Poleg nje po želji dodaj sidecar `LETO-MESEC-DAN_kratek-opis.yaml` z istim
   imenom (samo pripona drugačna) — vsa polja so opcijska:

   ```yaml
   datum: 2026-08-30          # če manjka, se vzame iz EXIF (DateTimeOriginal)
   lokacija:
     lat: 46.326               # če manjka, se vzame iz EXIF GPS
     lon: 14.921
     label: "Rečica ob Savinji, vrt"
   vrsta: "Koščeva muha"        # če manjka, gre fotka v /pregled/ (ročna identifikacija)
   sci: "Panorpa communis"      # znanstveno ime, če ga poznaš
   opomba: "na robu vrta, na kopriv"
   ```

3. Brez sidecarja skripta poskusi vrsto prepoznati sama (iNaturalist), sicer
   fotko premakne v `makro-inbox/pregled/` in počaka na ročni vpis `vrsta`.

## Kam skripta premika datoteke po objavi

- `makro-inbox/objavljeno/` — uspešno objavljene fotke (arhiv, ne briši).
- `makro-inbox/pregled/` — fotke, ki čakajo na ročno določitev vrste
  (dopolni sidecar `vrsta:` in jih ročno premakni nazaj v `makro-inbox/`).
