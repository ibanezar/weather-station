# Data notes and tuning decisions

Hand-written companion to the generated `docs/data-report.md`. Written 7 November 2026 from the
10-year (2016 to 2025) ERA5 build of 72 cities.

## Thresholds

SPEC 1.4 starting values are unchanged:

| Type    | Rule                                                                                    |
| ------- | --------------------------------------------------------------------------------------- |
| storm   | weather code 95, 96 or 99, or gusts at least 70 km/h, or precipitation at least 30 mm   |
| freeze  | max temperature at most 3 °C, or snowfall at least 1 cm                                 |
| heat    | max temperature at least 34 °C                                                          |
| rain    | precipitation at least 1 mm                                                             |
| perfect | max 19 to 28 °C, min at least 9 °C, under 1 mm, gusts under 40 km/h, cloud at most 65 % |

Overall mix: perfect 9.6 %, ok 42.7 %, rain 31.4 %, storm 2.6 %, heat 5.9 %, freeze 7.9 %.

## Rain threshold: kept at 1 mm

ERA5 is known to produce many light-rain days, so the report includes a sensitivity table
(share of days at least 1, 2, 3 and 5 mm). Comparing with well-known climates:

- Temperate cities match reality at 1 mm: Ljubljana 37 %, Edinburgh 43 %, Bergen 59 %.
- A higher threshold would help the wettest tropical cities only by under-counting rain where
  1 mm is right (Ljubljana would fall to 30 %, Bergen to 52 %).
- The tropics are over-wet at 1 mm (Quito 94 %, Singapore 82 %, Colombo 74 %, Lagos 66 %). This is the
  ERA5 drizzle bias, not a threshold problem.

Decision: keep 1 mm. The bias makes some tropical cities hard to win, which fits the game (they are
rainy), but it is a known limitation and should not be described as station accuracy.

## Cities with no perfect day in any month

Explained in `scripts/lib/report.ts` (`EXPLAINED`) from the monthly mean temperatures, not from the
threshold being wrong: Colombo (always above the 28 °C ceiling), La Paz (about 3,700 m, always below
19 °C), Longyearbyen and McMurdo Station (polar). Singapore has a few perfect days over 10 years.

## Caveats

- **Cloud cover.** The cloud condition was applied to every day (no gaps in the data). ERA5 reports
  little cloud over Lima, so Lima has 90 % perfect days in July and August although the city is
  usually grey. Treat Lima's winter as the model sees it.
- **Resolution.** ERA5 is gridded at about 25 km. Mountain and island places (Shillong for Mawsynram,
  Zermatt, La Paz, Kathmandu, Singapore, Honolulu) are regional approximations. The seed list carries a
  `note` for them and the UI must never claim station accuracy.
- **Gusts and storms.** Storm days come mostly from gusts and heavy rain: ERA5 rarely produces
  thunderstorm weather codes. Windy places rank high (Ushuaia, Reykjavik, Bergen, Edinburgh).

## Deviations from the SPEC (agreed during phase 1)

- 72 cities instead of the 63 the list names: Johannesburg, Bangkok, Lhasa, Madrid, Vienna,
  San Francisco, Santiago, Chicago and Brisbane were added.
- Each city has one primary `archetype` (one of the ten icon types) used for the draft rule and card icon.
- McMurdo Station is grouped under Oceania.
- The daily mean temperature (`temperature_2m_mean`) is requested so the card shows a true monthly mean.
- ERA5 is pinned (`models=era5`) for all years, so 2016 and 2025 come from the same model.
