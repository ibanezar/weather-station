# Grade calibration

Output of `npm run calibrate` (50,000 runs per strategy) on the 10-year data with the retuned thresholds
(7 November 2026, see `docs/data-notes.md`). The tiers in `src/engine/grades.ts` are the SPEC 1.8 values and were
not changed. Before the retune a random player was Stormbound 72% of the time and the best possible record held a
median of about 50 perfect days; now it holds 215, so decisions move the record a lot more.

**Reading it:** a random player lands in the bottom three tiers 95% of the time; a player who simply picks the
warmest-feeling card reaches the middle tiers (median 74% of the best possible); the top tier needs the best option
every round, which scouting (only three scouts) and second chances make possible but not easy. Second chances are not
modelled here: they only help, and a player who spends them well can beat the "best possible", which is measured on
the first draw of each option.

Runs per strategy: 50000

## Random picks

| grade                                                                                 | runs  | share  |
| ------------------------------------------------------------------------------------- | ----- | ------ |
| stormbound                                                                            | 25680 | 51.36% |
| umbrella-carrier                                                                      | 13741 | 27.48% |
| drizzle-dodger                                                                        | 7845  | 15.69% |
| fair-weather-friend                                                                   | 2403  | 4.81%  |
| sun-chaser                                                                            | 311   | 0.62%  |
| climate-sage                                                                          | 19    | 0.04%  |
| perfect-forecast                                                                      | 1     | 0.00%  |
| Bottom three tiers: 94.53%. Ratio to best possible: median 0.545, p5 0.333, p95 0.755 |

## Picks the card closest to a comfortable temperature (no scouts)

| grade                                                                                 | runs  | share  |
| ------------------------------------------------------------------------------------- | ----- | ------ |
| stormbound                                                                            | 2213  | 4.43%  |
| umbrella-carrier                                                                      | 7981  | 15.96% |
| drizzle-dodger                                                                        | 16577 | 33.15% |
| fair-weather-friend                                                                   | 16484 | 32.97% |
| sun-chaser                                                                            | 5760  | 11.52% |
| climate-sage                                                                          | 939   | 1.88%  |
| perfect-forecast                                                                      | 46    | 0.09%  |
| Bottom three tiers: 53.54%. Ratio to best possible: median 0.740, p5 0.557, p95 0.898 |

## Scouts every round (the game allows only 3), then temperature

| grade                                                                                | runs  | share  |
| ------------------------------------------------------------------------------------ | ----- | ------ |
| stormbound                                                                           | 0     | 0.00%  |
| umbrella-carrier                                                                     | 2     | 0.00%  |
| drizzle-dodger                                                                       | 76    | 0.15%  |
| fair-weather-friend                                                                  | 2146  | 4.29%  |
| sun-chaser                                                                           | 15414 | 30.83% |
| climate-sage                                                                         | 25776 | 51.55% |
| perfect-forecast                                                                     | 6586  | 13.17% |
| Bottom three tiers: 0.16%. Ratio to best possible: median 0.948, p5 0.854, p95 1.000 |
| Best possible perfect days: median 215, min 113, max 303                             |
