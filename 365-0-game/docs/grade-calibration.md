# Grade calibration

Output of `npm run calibrate -- --chase=all` (10,000 runs per strategy and chase) on the 10-year data with the retuned
thresholds (8 November 2026). The grade tiers in `src/engine/grades.ts` are ratios of the player's wins to the best
possible wins, so they work for every chase; what changes is the size of the best possible year:

| chase    | best possible wins (median) | lowest                |
| -------- | --------------------------- | --------------------- |
| sunshine | 207                         | 113                   |
| snow     | 92                          | 50 (floor, see below) |
| rain     | 117                         | 80 (floor)            |
| storms   | 33                          | 20 (floor)            |
| heat     | 45                          | 25 (floor)            |

**The floor.** Snow, rain, storm and heat runs need enough winnable months: a draft of 36 cities that have no frost, or
no storms, would make the run pointless (before the floor the lowest best possible year held 0 wins for snow and heat).
`MIN_BEST_WINS` in `src/engine/chase.ts` sets the minimum; a draft below it is replaced by the next attempt for the same
seed (up to 12; deterministic, so the daily is still the same for everyone). The sunny game has no floor and its drafts
are unchanged.

**Reading it:** a random player lands in the bottom three tiers 82 to 96% of the time, a player who uses every scout
reaches the upper tiers almost always (the game allows only 3 scouts, so it is harder). Storms are the noisiest chase:
a storm is a rare day, so a year holds few wins and the ratio swings more. Second chances are not modelled here (they
only help), and a player who spends them well can beat the best possible, which is measured on the first draw.

## Chasing: sun

Runs per strategy: 10000

### Random picks

| grade                                                                                 | runs | share  |
| ------------------------------------------------------------------------------------- | ---- | ------ |
| stormbound                                                                            | 5425 | 54.25% |
| umbrella-carrier                                                                      | 2593 | 25.93% |
| drizzle-dodger                                                                        | 1484 | 14.84% |
| fair-weather-friend                                                                   | 436  | 4.36%  |
| sun-chaser                                                                            | 56   | 0.56%  |
| climate-sage                                                                          | 6    | 0.06%  |
| perfect-forecast                                                                      | 0    | 0.00%  |
| Bottom three tiers: 95.02%. Ratio to best possible: median 0.535, p5 0.322, p95 0.749 |

### Picks the card closest to a comfortable temperature (no scouts)

| grade                                                                                 | runs | share  |
| ------------------------------------------------------------------------------------- | ---- | ------ |
| stormbound                                                                            | 515  | 5.15%  |
| umbrella-carrier                                                                      | 1624 | 16.24% |
| drizzle-dodger                                                                        | 3360 | 33.60% |
| fair-weather-friend                                                                   | 3176 | 31.76% |
| sun-chaser                                                                            | 1151 | 11.51% |
| climate-sage                                                                          | 165  | 1.65%  |
| perfect-forecast                                                                      | 9    | 0.09%  |
| Bottom three tiers: 54.99%. Ratio to best possible: median 0.735, p5 0.549, p95 0.896 |

### Scouts every round (the game allows only 3), then temperature

| grade                                                                                | runs | share  |
| ------------------------------------------------------------------------------------ | ---- | ------ |
| stormbound                                                                           | 0    | 0.00%  |
| umbrella-carrier                                                                     | 0    | 0.00%  |
| drizzle-dodger                                                                       | 24   | 0.24%  |
| fair-weather-friend                                                                  | 530  | 5.30%  |
| sun-chaser                                                                           | 3323 | 33.23% |
| climate-sage                                                                         | 4909 | 49.09% |
| perfect-forecast                                                                     | 1214 | 12.14% |
| Bottom three tiers: 0.24%. Ratio to best possible: median 0.945, p5 0.847, p95 1.000 |
| Best possible wins: median 207, min 113, max 290                                     |

## Chasing: snow

Runs per strategy: 10000

### Random picks

| grade                                                                                 | runs | share  |
| ------------------------------------------------------------------------------------- | ---- | ------ |
| stormbound                                                                            | 7421 | 74.21% |
| umbrella-carrier                                                                      | 1070 | 10.70% |
| drizzle-dodger                                                                        | 688  | 6.88%  |
| fair-weather-friend                                                                   | 429  | 4.29%  |
| sun-chaser                                                                            | 191  | 1.91%  |
| climate-sage                                                                          | 125  | 1.25%  |
| perfect-forecast                                                                      | 76   | 0.76%  |
| Bottom three tiers: 91.79%. Ratio to best possible: median 0.379, p5 0.000, p95 0.821 |

### Picks the card closest to a comfortable temperature (no scouts)

| grade                                                                                  | runs  | share   |
| -------------------------------------------------------------------------------------- | ----- | ------- |
| stormbound                                                                             | 10000 | 100.00% |
| umbrella-carrier                                                                       | 0     | 0.00%   |
| drizzle-dodger                                                                         | 0     | 0.00%   |
| fair-weather-friend                                                                    | 0     | 0.00%   |
| sun-chaser                                                                             | 0     | 0.00%   |
| climate-sage                                                                           | 0     | 0.00%   |
| perfect-forecast                                                                       | 0     | 0.00%   |
| Bottom three tiers: 100.00%. Ratio to best possible: median 0.000, p5 0.000, p95 0.198 |

### Scouts every round (the game allows only 3), then temperature

| grade                                                                                 | runs | share  |
| ------------------------------------------------------------------------------------- | ---- | ------ |
| stormbound                                                                            | 182  | 1.82%  |
| umbrella-carrier                                                                      | 324  | 3.24%  |
| drizzle-dodger                                                                        | 718  | 7.18%  |
| fair-weather-friend                                                                   | 1587 | 15.87% |
| sun-chaser                                                                            | 1702 | 17.02% |
| climate-sage                                                                          | 1427 | 14.27% |
| perfect-forecast                                                                      | 4060 | 40.60% |
| Bottom three tiers: 12.24%. Ratio to best possible: median 0.953, p5 0.648, p95 1.000 |
| Best possible wins: median 92, min 50, max 220                                        |

## Chasing: rain

Runs per strategy: 10000

### Random picks

| grade                                                                                 | runs | share  |
| ------------------------------------------------------------------------------------- | ---- | ------ |
| stormbound                                                                            | 6586 | 65.86% |
| umbrella-carrier                                                                      | 1963 | 19.63% |
| drizzle-dodger                                                                        | 1013 | 10.13% |
| fair-weather-friend                                                                   | 358  | 3.58%  |
| sun-chaser                                                                            | 71   | 0.71%  |
| climate-sage                                                                          | 8    | 0.08%  |
| perfect-forecast                                                                      | 1    | 0.01%  |
| Bottom three tiers: 95.62%. Ratio to best possible: median 0.487, p5 0.256, p95 0.739 |

### Picks the card closest to a comfortable temperature (no scouts)

| grade                                                                                 | runs | share  |
| ------------------------------------------------------------------------------------- | ---- | ------ |
| stormbound                                                                            | 4807 | 48.07% |
| umbrella-carrier                                                                      | 2565 | 25.65% |
| drizzle-dodger                                                                        | 1693 | 16.93% |
| fair-weather-friend                                                                   | 771  | 7.71%  |
| sun-chaser                                                                            | 142  | 1.42%  |
| climate-sage                                                                          | 22   | 0.22%  |
| perfect-forecast                                                                      | 0    | 0.00%  |
| Bottom three tiers: 90.65%. Ratio to best possible: median 0.557, p5 0.310, p95 0.791 |

### Scouts every round (the game allows only 3), then temperature

| grade                                                                                | runs | share  |
| ------------------------------------------------------------------------------------ | ---- | ------ |
| stormbound                                                                           | 4    | 0.04%  |
| umbrella-carrier                                                                     | 49   | 0.49%  |
| drizzle-dodger                                                                       | 416  | 4.16%  |
| fair-weather-friend                                                                  | 2032 | 20.32% |
| sun-chaser                                                                           | 3965 | 39.65% |
| climate-sage                                                                         | 3029 | 30.29% |
| perfect-forecast                                                                     | 505  | 5.05%  |
| Bottom three tiers: 4.69%. Ratio to best possible: median 0.904, p5 0.750, p95 0.990 |
| Best possible wins: median 117, min 80, max 217                                      |

## Chasing: storm

Runs per strategy: 10000

### Random picks

| grade                                                                                 | runs | share  |
| ------------------------------------------------------------------------------------- | ---- | ------ |
| stormbound                                                                            | 7224 | 72.24% |
| umbrella-carrier                                                                      | 1337 | 13.37% |
| drizzle-dodger                                                                        | 829  | 8.29%  |
| fair-weather-friend                                                                   | 473  | 4.73%  |
| sun-chaser                                                                            | 116  | 1.16%  |
| climate-sage                                                                          | 16   | 0.16%  |
| perfect-forecast                                                                      | 5    | 0.05%  |
| Bottom three tiers: 93.90%. Ratio to best possible: median 0.423, p5 0.118, p95 0.762 |

### Picks the card closest to a comfortable temperature (no scouts)

| grade                                                                                 | runs | share  |
| ------------------------------------------------------------------------------------- | ---- | ------ |
| stormbound                                                                            | 7957 | 79.57% |
| umbrella-carrier                                                                      | 1090 | 10.90% |
| drizzle-dodger                                                                        | 618  | 6.18%  |
| fair-weather-friend                                                                   | 255  | 2.55%  |
| sun-chaser                                                                            | 73   | 0.73%  |
| climate-sage                                                                          | 6    | 0.06%  |
| perfect-forecast                                                                      | 1    | 0.01%  |
| Bottom three tiers: 96.65%. Ratio to best possible: median 0.378, p5 0.094, p95 0.714 |

### Scouts every round (the game allows only 3), then temperature

| grade                                                                                 | runs | share  |
| ------------------------------------------------------------------------------------- | ---- | ------ |
| stormbound                                                                            | 1374 | 13.74% |
| umbrella-carrier                                                                      | 1376 | 13.76% |
| drizzle-dodger                                                                        | 1826 | 18.26% |
| fair-weather-friend                                                                   | 2158 | 21.58% |
| sun-chaser                                                                            | 1820 | 18.20% |
| climate-sage                                                                          | 1092 | 10.92% |
| perfect-forecast                                                                      | 354  | 3.54%  |
| Bottom three tiers: 45.76%. Ratio to best possible: median 0.765, p5 0.441, p95 0.972 |
| Best possible wins: median 33, min 20, max 89                                         |

## Chasing: heat

Runs per strategy: 10000

### Random picks

| grade                                                                                 | runs | share  |
| ------------------------------------------------------------------------------------- | ---- | ------ |
| stormbound                                                                            | 6953 | 69.53% |
| umbrella-carrier                                                                      | 659  | 6.59%  |
| drizzle-dodger                                                                        | 608  | 6.08%  |
| fair-weather-friend                                                                   | 582  | 5.82%  |
| sun-chaser                                                                            | 455  | 4.55%  |
| climate-sage                                                                          | 379  | 3.79%  |
| perfect-forecast                                                                      | 364  | 3.64%  |
| Bottom three tiers: 82.20%. Ratio to best possible: median 0.317, p5 0.000, p95 0.968 |

### Picks the card closest to a comfortable temperature (no scouts)

| grade                                                                                 | runs | share  |
| ------------------------------------------------------------------------------------- | ---- | ------ |
| stormbound                                                                            | 8708 | 87.08% |
| umbrella-carrier                                                                      | 385  | 3.85%  |
| drizzle-dodger                                                                        | 266  | 2.66%  |
| fair-weather-friend                                                                   | 206  | 2.06%  |
| sun-chaser                                                                            | 143  | 1.43%  |
| climate-sage                                                                          | 91   | 0.91%  |
| perfect-forecast                                                                      | 201  | 2.01%  |
| Bottom three tiers: 93.59%. Ratio to best possible: median 0.200, p5 0.000, p95 0.815 |

### Scouts every round (the game allows only 3), then temperature

| grade                                                                                 | runs | share  |
| ------------------------------------------------------------------------------------- | ---- | ------ |
| stormbound                                                                            | 495  | 4.95%  |
| umbrella-carrier                                                                      | 301  | 3.01%  |
| drizzle-dodger                                                                        | 486  | 4.86%  |
| fair-weather-friend                                                                   | 875  | 8.75%  |
| sun-chaser                                                                            | 965  | 9.65%  |
| climate-sage                                                                          | 1159 | 11.59% |
| perfect-forecast                                                                      | 5719 | 57.19% |
| Bottom three tiers: 12.82%. Ratio to best possible: median 1.000, p5 0.552, p95 1.000 |
| Best possible wins: median 45, min 25, max 122                                        |
