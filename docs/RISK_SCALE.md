# Risk indicators of Model 2: the implemented scale (before and after)

Decision record: the audit and proposal are in [RISK_SCALE_PROPOSAL.md](RISK_SCALE_PROPOSAL.md); the student approved it with these choices: reference = UK out-of-sample scores (the Netherlands stays as independent validation), prediction standardised to a 12-month interval, **three levels (Low / Moderate / High)** set from observed defect rates, same-age comparison kept as complementary information, no "times the average" figure.
**The trained and exported models were not changed or retrained.** Only the scale built on their scores, the 12-month standardisation at inference, the API fields and the dashboard changed.

## 1. What a user sees now

For each system (brakes, electrical, engine-related) separately:

* **Main indicator:** a three-segment bar (Low, Moderate, High) with a marker, comparing the vehicle with **all reference vehicles, any age**, plus "Higher than about N of 100 reference vehicles" (N rounded to 5: it is a rank, not a probability). The same scale applies to every vehicle, so two vehicles can be compared directly.
* **Complementary line:** "Compared with vehicles aged N only: lower than most / about typical / higher than most" (below the 20th / between / above the 80th percentile of that age).
* **Always visible text:** the bars show relative risk of a defect being found at the next annual inspection against UK reference data; older cars usually sit further right; it is not a probability, not a breakdown forecast and not validated for Israeli vehicles.
* **Details (collapsed):** how the levels were set, and how often a defect was actually found at the next inspection in each level of the UK reference data (for example brakes: about 3%, 6%, 12%). These are frequencies of *groups* of reference vehicles, not a forecast for the vehicle.
* **No longer shown:** per-vehicle probabilities, "times the average", and percentiles as numbers beyond the rounded rank.

## 2. How the scale is defined

* **Score:** the model's own output for the vehicle, computed for a **standard interval of 12 months** to the next inspection.
* **Reference distribution:** UK pairs (inspection in 2022, next inspection in 2023), scored **out of sample** (3-fold cross-fitting by vehicle, same hyper-parameters as the exported models), all ages 3 to 20, petrol/diesel/hybrid, one distribution per model variant and system. The Dutch data are used only as an independent check.
* **Percentile:** share of reference vehicles with a lower score. The covered Israeli fleet has almost the same age mix as this reference (mean age 9.03 against 9.05 years).
* **Levels:** the cut points were **chosen from the data**, not by appearance: among cut points that leave at least 20% of the reference vehicles in every level, the pair that maximises the log-likelihood of a three-level step function of the observed defects (UK cross-fitted, registry-only variant). Per-system optima were 39/76 (brakes), 36/69 (electrical) and 25/68 (engine-related); the **common** optimum **36/69** loses at most 1.8% of the likelihood gain for any system, so one common rule is used: **Low = lowest 36% of reference vehicles, Moderate = the next 33%, High = the top 31%** (about thirds).

Evidence that the levels mean something (observed share of vehicles with a defect found at the next inspection; 95% intervals are about plus or minus 0.1 to 0.2 points):

| System | Data | Base rate | Low | Moderate | High |
|---|---|---|---|---|---|
| Brakes | UK (cross-fitted) | 6.9% | 3.0% | 6.4% | 12.0% |
| Brakes | NL (independent, UK-trained models) | 9.0% | 4.5% | 6.6% | 13.5% |
| Electrical | UK | 11.6% | 3.9% | 11.1% | 21.3% |
| Electrical | NL | 20.5% | 9.6% | 16.2% | 30.4% |
| Engine-related | UK | 3.1% | 1.0% | 2.6% | 6.1% |
| Engine-related | NL | 3.2% | 0.6% | 1.5% | 5.8% |

In the UK Low is about 0.3 to 0.45 times the base rate, Moderate close to it (0.85 to 0.95) and High 1.7 to 2 times it; the Netherlands shows the same order. Low and High are statistically separated for every variant, system and country (tested). The Dutch fleet is older, so about 40% to 48% of its vehicles fall in High: the order replicates, the proportions and absolute rates differ. Alternative cut points (30/70, 33/67, 20/80, 40/80) are tabulated in `model2_reference.json`.

Covered Israeli fleet (12,597 registry vehicles, scores only): brakes 32% / 30% / 37% in Low / Moderate / High, electrical 36% / 29% / 34%, engine-related 45% / 28% / 27%.

## 3. Standardising the interval does not hurt the models

ROC-AUC with the realised interval to the next inspection (how the models were evaluated) against the interval fixed at 12 months (how the indicators are computed):

| Variant | Brakes | Electrical | Engine-related |
|---|---|---|---|
| Registry only, UK cross-fitted | 0.6781 to 0.6761 | 0.7101 to 0.7085 | 0.7171 to 0.7149 |
| + measured odometer | 0.6933 to 0.6919 | 0.7279 to 0.7269 | 0.7427 to 0.7411 |
| + previous inspection | 0.6921 to 0.6904 | 0.7257 to 0.7243 | 0.7489 to 0.7470 |
| + both | 0.7039 to 0.7027 | 0.7384 to 0.7374 | 0.7683 to 0.7667 |
| Registry only, NL (independent) | 0.6432 to 0.6423 | 0.6565 to 0.6557 | 0.7333 to 0.7372 |
| + previous inspection, NL | 0.6625 to 0.6618 | 0.6866 to 0.6853 | 0.7577 to 0.7600 |

The change is at most about 0.002 AUC (the Dutch engine-related models even gain 0.004 and 0.002). The planned interval from the registry (licence valid until minus last test) varied from 0.74 to 1.07 years for identical vehicles only because of when in the cycle the owner took the test, and it had changed the estimate by 19% to 29% on average without improving the ranking.

## 4. Before and after on real plates (live registry)

Ten real plates of each model (`docs/risk_scale_before.json`, `docs/risk_scale_after.json`).

**Hyundai i20 2022** (age 4 at the last inspection):

| | Brakes | Electrical | Engine-related |
|---|---|---|---|
| Before (same-age percentile, depended on the plate) | 53 to 84 | 32 to 63 | 15 to 36 |
| **After (all ten plates identical)** | **Low** (higher than about 20 of 100); about typical for age 4 | **Low** (about 10); about typical for age 4 | **Low** (about 5); lower than most of age 4 |

**Nissan Micra 2014** (age 12; 11 for plates whose last test was in 2025):

| | Brakes | Electrical | Engine-related |
|---|---|---|---|
| Before (same-age percentile) | 23 to 43 | 55 to 71 | 14 to 59 |
| **After** | **Moderate** (about 65); about typical for age 12 | **High** (about 75 to 80); about typical for age 12 | **Moderate** (about 60); about typical for age 12 |

Reading: on the same scale the Micra has a higher estimated risk than the i20 in all three systems, which the old numbers contradicted for brakes (the i20 showed 73 against 23 for the Micra). The i20 no longer looks "high for brakes" just because it is compared with other 4-year-olds. The remaining differences between Micra plates come from the age at the last inspection (2025 against 2026 tests).

## 5. Consistency checks (automatic, 66 tests pass)

* percentile and level are monotone functions of the model output across the whole grid of ages (3 to 20), fuels and makes, for the three systems, and all three levels occur;
* the i20 (age 4) and the Micra (age 12): higher probability, higher percentile and a level at least as high for the Micra in every system;
* the same-age position compresses the age difference that the overall scale keeps;
* identical vehicles with different registry dates get identical indicators;
* for every variant, system and country: observed defect rate Low < Moderate < High, Low and High statistically separated, each UK level at least 19% of the vehicles;
* standardising the interval changes AUC by no more than 0.01 for any variant (actual maximum 0.002);
* the API contains no probability, no "times the average" and no percentile number beyond the rank rounded to 5; golden probabilities and levels computed in the training environment equal those of the API image.

88 real plates end to end (live registry): 1,570 automatic checks, 0 failures; among the 52 vehicles covered by Model 2 the levels spread over Low, Moderate and High (brakes 17 / 12 / 23, electrical 20 / 14 / 18, engine-related 24 / 14 / 14). Dashboard checked in the browser: for the i20 at desktop width the bar segments take 36/33/31% of the width and the marker lies inside the segment of its level; the Micra at phone width (375 px) renders its three cards with no horizontal overflow. (The browser window was minimised, so the check read the rendered page and its geometry; no screenshots were possible.)

## 6. What remains true

The reference is UK inspection data: the levels say how a vehicle ranks against it, not against Israeli cars, and nothing is validated on Israeli vehicles. The target is a defect found at the next annual inspection, not a breakdown. Discrimination is modest (ROC-AUC about 0.64 to 0.77 depending on system, variant and country), so a level is a coarse screening, not a diagnosis.
