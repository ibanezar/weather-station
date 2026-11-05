# FB objava: nabor podatkov postaje je citirljiv (DOI), osnutek 5. 11. 2026

**Samo osnutek, ni objavljeno.** Pisano po `docs/slog-pisanja.md` (vikanje, uvod s konkretno številko, kratki stavki, vprašanje na koncu,
UTM povezava). Številke so iz `podatki/ireica1-dnevni-podatki.csv` (2536 dni, 7. 11. 2019–4. 11. 2026, samo zunanje meritve, dnevi
reanalize izpuščeni) in `data/dataset-metadata.json` (DOI `10.5281/zenodo.23979571`). Prej preverite, da DOI na zenodo.org res odpre zapis.

Namen: nova vrsta vsebine (ne vremenska novica), zato ne gre samodejno ven. Objavite ročno kot link objavo (`/feed` + link), kot za
ostale ročne članke.

## Besedilo

2536 dni meritev iz Rečice ob Savinji je zdaj zbranih na enem mestu in ima svojo številko DOI.

Postaja IREICA1 meri od 7. novembra 2019. Najvišja izmerjena temperatura je 37,8 °C (5. avgusta 2026), najnižja −16,5 °C (8. januarja 2026). Vsak dan je v preglednici: najvišja, najnižja in povprečna temperatura, padavine, veter in vlaga. Prosto, z navedbo vira (CC BY 4.0).

Zakaj DOI? Ker lahko zdaj kdorkoli, od študenta do občine, podatke navede kot vir, in ostanejo na istem naslovu tudi čez leta. Postaja je amaterska, brez uradne kalibracije, in to piše v opisu.

Prenos in navodilo za citiranje: https://meteorec.si/podatki/?utm_source=facebook&utm_medium=social&utm_campaign=podatki-doi

Bi ga uporabili za šolsko nalogo, kmetijo ali kaj tretjega?

## Opombe

- Dolžina in ton sta kot pri uspešnih objavah (številka v uvodu, brez pridevnikov). Brez emojijev je pravilnejše za ta tip vsebine; če želite enega, pred prvo vrstico.
- Licenca: preverite v `data/dataset-metadata.json` (polje `license`) in na /podatki/, preden objavite besedilo »CC BY 4.0«.
- Povezava `doi.org/10.5281/zenodo.23979571` je lahko v prvem komentarju namesto v besedilu (FB mehkeje obravnava dve povezavi).
