# Javna gobarska opažanja proti modelu (15. 10. 2026)

Vir: `GET /gobe/opazovanja?dni=120` (javni vnosi, 13 opažanj od 20. 9. do 14. 10. 2026) in `history.json` (postaja IREICA1). Rezultat je okviren: vnosi so javni in nepreverjeni, vzorec je majhen.

## Jurček (7 vnosov: »Jesenski goban« in »Jurček«)

Sprožilni dež: 10. in 11. 9. (85,1 + 35,6 mm). Model za mikorizne vrste uporablja zamik 8–16 dni.

| Datum vnosa | Dni od 10. 9. | V oknu 8–16? |
|---|---:|---|
| 20. 9. | 10 | da |
| 21. 9. | 11 | da |
| 23. 9. | 13 | da |
| 25. 9. | 15 | da |
| 26. 9. | 16 | da |
| 2. 10. | 22 | ne (zadnji vnos) |
| 13. 10. | 33 | ne |

Vseh pet vnosov iz prvega vala je v oknu 8–16 dni, prvi pa je bil šele deseti dan po dežju. Zamika 8–16 torej opažanja ne kličejo spremeniti. Dva poznejša vnosa (22 in 33 dni) sta lahko posledica kasnejših manjših padavin ali daljše razpoložljivosti trosnjakov; iz teh podatkov tega ne moremo ločiti.

## Orjaški dežnik (marela), 2 vnosa

20. in 21. 9., torej 10 in 11 dni po dežju. Model za razkrojevalke uporablja 2–8 dni. Opažanja iNaturalist (članek o zamikih) kažejo isto: marela ni hitra. Dva vnosa nista dovolj za spremembo.

## Lisička, 1 vnos

14. 10. v Rečici, 6 dni po dežju 8. 10. (9,9 mm). Zamik 4–14 dni to pokrije, okno je od 12. 10.

## Ali bi signal `--use-observations` kaj spremenil?

Ne. Pogoj je najmanj 3 opažanja iste vrste na istem območju, na 2 različnih dneh, v zadnjih 21 dneh. Največ sta 2 vnosa iste vrste na istem območju (Spodnje Pobrežje 20. in 25. 9.; Pod Smrekovcem 23. in 26. 9.), v zadnjih 21 dneh pa je v vsakem območju največ 1. Pogoj ni nikjer izpolnjen, stikalo bi bilo brez učinka. **Priporočilo: ne vklapljati**; ponovno pogledati, ko bo vsaj ~50 opažanj. Skrajšani zamik 3–10 dni (`OBS_*`) ostaja neumerjen: opažanja v prvem valu so bila 10–16 dni po dežju, torej v običajnem oknu in ne prej.

## Omejitve

- 13 vnosov, od tega 7 jurčkov. Ni podatka, kdaj je bil trosnjak najden, samo kdaj je bil vnesen.
- Vnosi niso preverjeni (ime vrste je prosto besedilo).
- Sprožilni dež je izbran ročno (dan ≥ 10 mm), ne po pravilu modela.
