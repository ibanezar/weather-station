# Data licence check

Checked 7 November 2026 against open-meteo.com/en/terms, /en/pricing and /en/docs/historical-weather-api.
Terms change; re-read them before shipping.

## What 365-0 uses

- Source: the Open-Meteo Historical Weather API (`archive-api.open-meteo.com`), model ERA5
  (0.25°, about 25 km), daily values for 2016 to 2025, fetched once by `npm run data`.
- ERA5 is produced by ECMWF for the Copernicus Climate Change Service.
- The game ships only derived data: one character per day (perfect, ok, rain, storm, heat, freeze),
  a mean temperature per month and bucketed scout values. No raw API responses are shipped or committed.

## What the terms say

| Topic | Free API | Paid API |
| --- | --- | --- |
| Use | Non-commercial only | Commercial licence |
| Limits | 10,000 calls/day, 5,000/hour, 600/minute, per IP | Unlimited per day |
| Historical Weather API | Included | Professional plan or higher (not in Standard) |
| Data licence | CC BY 4.0 | CC BY 4.0 |

- Non-commercial examples in the terms: private or non-profit sites and apps **without subscriptions or
  advertising**, research at public institutions, educational content. Voluntary donations are allowed.
- Commercial examples: sites or apps **with subscriptions or advertisements**, commercial products or
  promotional activities.
- A request spanning more than two weeks or more than 10 variables counts as several calls. A full-year
  request is therefore far more than one call, and the whole 72-city, 10-year pull needs roughly 19,000
  weighted calls or more. It cannot finish in one day on the free tier, so the build script caches every
  response and resumes the next day.
- The limits are per IP address. In the Claude cloud sandbox the egress IP is shared, so the daily
  allowance can already be used up by other traffic (seen on 7 November 2026). The script stops cleanly and
  can be re-run.

## Decision (7 November 2026)

365-0 is free and ad-free: no advertising, subscriptions or in-app purchases. On that basis the free API
is acceptable, with attribution.

**If that ever changes** (ads, subscriptions or purchases, including in the Play Store release), the free
tier no longer fits. Before shipping, do one of:

1. Re-fetch the data under an Open-Meteo Professional plan (a one-month subscription is enough, since the
   data is built once), or
2. Switch `scripts/lib/fetch.ts` to ERA5 straight from the Copernicus Climate Data Store, which permits
   commercial use with attribution, and keep the same output format.

A grey area to be aware of: the terms restrict use of the free *service* to non-commercial purposes; they do
not spell out whether a static dataset derived once from it and redistributed inside an app is covered. The
data itself is CC BY 4.0, which allows commercial use with attribution. A free, ad-free game sits clearly
inside the non-commercial definition, so the question does not arise today.

## Attribution (required by CC BY 4.0)

Show on the Settings screen and the About screen (implemented in phases 4 and 5):

> Weather data by Open-Meteo.com (CC BY 4.0), from ERA5 reanalysis by ECMWF and the Copernicus Climate
> Change Service. Processed by 365-0: daily values are grouped into six day types and are not the original
> data.

- Link the first part to https://open-meteo.com.
- CC BY 4.0 asks us to indicate changes: the second sentence does that.
- Copernicus asks for the wording "Contains modified Copernicus Climate Change Service information" when
  ERA5 is used. Confirm the exact wording against the current Copernicus licence before shipping.

## Accuracy statement

ERA5 is gridded at about 25 km, so micro-climates (Shillong standing in for Mawsynram, the Zermatt area, La Paz,
Kathmandu) are approximations. The cities that need it carry a `note` in `data/cities.seed.json`. The UI must
never claim station-level accuracy.
