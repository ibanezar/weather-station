# Zimski SEO (31. 10. 2026)

## Izhodišče
- GSC (izvoz 27. 10.) o zimskih izrazih skoraj nič ne ve: »zima 2026/27« 126 prikazov brez klika (poz. 8), »žledko« 81 prikazov (poz. 39).
  Izbira iskalnih izrazov za naslove je **presoja, ne meritev**.
- `/zima/*` strani so imele generične naslove (»X — Zgornja Savinjska dolina«), opise 80–110 znakov in hub brez povezav na zimske članke (27. 10.).

## Narejeno
- Naslovi (vsi ≤ 60 znakov s pripono) in opisi (100–160 znakov, `assert` v generatorju) po iskalnem namenu: `HUB_TITLE`/`SPOKE_PAGES` v `tools/generate_zima_page.py`.
- Hub: razdelek »Zimski vodnik« (osem člankov) + 5 novih vprašanj v FAQ (vidno besedilo in FAQPage iz istega seznama).
  Naslovi in povzetki se berejo iz `blog.json`; povzetek, vezan na en dan, ima časovno nevtralen nadomestek (`SUMMARY_OVERRIDE`).
- Spoke strani: »Preberi tudi« s članki, ki ustrezajo bralčevemu namenu (`SPOKE_GUIDES`).

## Za preverit (po 15. 11., ko bo v GSC nekaj podatkov)
1. `python3 tools/gsc_opportunities.py IZVOZ.zip` -- ali se pojavijo »poledica«, »meja sneženja«, »megla jutri«, »zimske gume«; naslove popravi po dejanskih poizvedbah.
2. Članek `prvi-sneg-golte-solcava-menina-1027` je posnetek za 31. 10. (napoved 1 cm na Goltah) -- po 1. 11. ga je treba posodobiti ali označiti kot pretečenega.
