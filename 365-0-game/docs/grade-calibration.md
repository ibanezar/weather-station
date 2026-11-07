# Grade calibration

Output of `npm run calibrate` (50,000 runs per strategy) on the 10-year data, 7 November 2026. The tiers in
`src/engine/grades.ts` are the SPEC 1.8 values and were not changed.

**Reading it:** a random player lands in the bottom three tiers 96% of the time; the top tier is reachable only
by skill (picking the best city every round gives exactly 100%); a player who scouts everywhere reaches the
upper tiers most of the time. Scouts are therefore worth spending, and the three-scout limit is a real constraint.

Runs per strategy: 50000

## Random picks

| grade               | runs  | share  |
| ------------------- | ----- | ------ |
| stormbound          | 35970 | 71.94% |
| umbrella-carrier    | 7974  | 15.95% |
| drizzle-dodger      | 4130  | 8.26%  |
| fair-weather-friend | 1561  | 3.12%  |
| sun-chaser          | 312   | 0.62%  |
| climate-sage        | 52    | 0.10%  |
| perfect-forecast    | 1     | 0.00%  |

Bottom three tiers: 96.15%. Ratio to best possible: median 0.450, p5 0.190, p95 0.728

## Picks the card closest to a comfortable temperature (no scouts)

| grade               | runs  | share  |
| ------------------- | ----- | ------ |
| stormbound          | 18200 | 36.40% |
| umbrella-carrier    | 11876 | 23.75% |
| drizzle-dodger      | 10524 | 21.05% |
| fair-weather-friend | 6569  | 13.14% |
| sun-chaser          | 2220  | 4.44%  |
| climate-sage        | 550   | 1.10%  |
| perfect-forecast    | 61    | 0.12%  |

Bottom three tiers: 81.20%. Ratio to best possible: median 0.608, p5 0.333, p95 0.857

## Scouts every round (the game allows only 3), then temperature

| grade               | runs  | share  |
| ------------------- | ----- | ------ |
| stormbound          | 84    | 0.17%  |
| umbrella-carrier    | 545   | 1.09%  |
| drizzle-dodger      | 2607  | 5.21%  |
| fair-weather-friend | 9799  | 19.60% |
| sun-chaser          | 16441 | 32.88% |
| climate-sage        | 15452 | 30.90% |
| perfect-forecast    | 5072  | 10.14% |

Bottom three tiers: 6.47%. Ratio to best possible: median 0.911, p5 0.731, p95 1.000

Best possible perfect days: median 86, min 19, max 172
