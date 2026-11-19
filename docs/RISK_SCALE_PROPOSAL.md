# Model 2 risk indicators: audit and proposal (historical; **implemented as described in [RISK_SCALE.md](RISK_SCALE.md)** with three levels instead of five)

Status: **proposal for approval.** Training, exported models and front end are untouched. The audit is reproducible with `ml/src/audit_risk_scale.py` (read-only; results in `ml/audit_risk_scale_results.json`).

## 1. What the dashboard shows today and why it confuses

The number on each gauge is a **percentile among vehicles of the same age**: the model's probability is compared with the cross-fitted UK scores of vehicles of exactly that age (deciles per age, interpolated). The age effect is removed on purpose, and age is the strongest driver of the score, so the number cannot be compared between vehicles of different ages.

Real plates, live registry, API as deployed (brakes):

| Vehicle (age at last inspection) | Raw model probability | Number shown today (same-age percentile) |
|---|---|---|
| Hyundai i20 2022 (4 years) | 2.8% to 4.0%, depending on the plate | 53 to 84, depending on the plate |
| Nissan Micra 2014 (12 years) | 7.4% to 8.1% | 23 to 43, depending on the plate |

The Micra has more than twice the estimated risk of the i20 but a lower number. The displayed number says "the i20 is high *for a 4-year-old*", which is a different question from "which car is more likely to have a brake defect at the next inspection".

## 2. Audit

**How the percentile is computed (replicated exactly):** per system and age, deciles of the cross-fitted UK scores stored in the model card; `np.interp` between the deciles. I recomputed the numbers of four real plates from the raw probabilities and obtained the displayed values (73, 54, 23, 30 for brakes). No implementation error in the percentile.

**Raw against calibrated probabilities:** the exported models use the natural logistic objective (`binary:logistic`); there is no separate calibration layer, so raw and calibrated are the same number. On the UK cross-fitted scores predicted and observed rates agree decile by decile (brakes: top decile 14.4% predicted, 15.1% observed). On the Dutch data the **level shifts** (electrical: lowest decile 3.0% predicted, 8.1% observed; highest 25.2% against 34.0%; engine-related over-predicted: 10.8% against 8.0%) while the **order is preserved**. Conclusion: ranks transfer, absolute probabilities do not.

**What drives the score (share of total gain, registry-only models):**

| System | Age | Make | Fuel | Planned interval to the next inspection |
|---|---|---|---|---|
| Brakes | 71% | 20% | 5% | 4% |
| Electrical | 70% | 24% | 2% | 3% |
| Engine-related | 60% | 26% | 7% | 7% |

For the i20 the age contribution is strongly negative (log-odds -0.94 for brakes) and partly offset by the make (+0.34); for the Micra the age contribution is positive (+0.30). That, not an error, explains the ordering of the raw probabilities.

**Problem found: the planned-interval feature.** The model receives `gap_next`, computed from "licence valid until minus last test". For cars of the same model and year this value ranges from 0.74 to 1.07 years only because of *when in the cycle* the owner took the test, and it moves the probability a lot (i20 brakes 2.8% at 0.74 years, 4.0% at 1.07). It explains why identical vehicles show different numbers (i20 plates: 53 to 84). Evidence that it should not be used at inference:
* on the independent Dutch validation, fixing it at 1.0 does not hurt the ranking: AUC 0.6408 to 0.6403 (brakes), 0.6599 to 0.6581 (electrical), **0.7531 to 0.7595** (engine-related, better);
* fixing it changes the probabilities by 19% to 29% on average, and the engine-related curve is not monotone in it;
* in training the value is the *realised* time to the next test, at inference it is the *planned* one: different concepts, never validated for Israel.

This is an interpretation/implementation inconsistency, not a coding bug. With the interval fixed at 12 months both i20 plates give exactly the same result.

**Coherence across ages:** for 7 make/fuel combinations the probability rises with age for all three systems (brakes: Toyota petrol 1.8% at age 3, 6.5% at 10, 12.2% at 20), following the observed UK rates by age. Small non-monotone steps appear only above age 15 in sparse make-by-age cells (for example Hyundai petrol electrical 21.6% at 15 against 18.9% at 20), where the observed UK rates themselves flatten (electrical about 22% from age 16). They are within noise and are left as the model produced them.

## 3. Is a population-wide scale more useful than a same-age scale? (measured, UK cross-fitted and Dutch out-of-sample, registry-only model)

| System | Data | Defects captured by the top 20%, **all ages** | ... by the top 20% **within each age** | Base rate | Correlation of the number shown with the raw probability: all-ages / same-age |
|---|---|---|---|---|---|
| Brakes | UK | 39.0% | 28.8% | 6.9% | 1.00 / 0.44 |
| Brakes | NL | 34.0% | 23.9% | 9.0% | 1.00 / 0.41 |
| Electrical | UK | 40.0% | 30.3% | 11.6% | 1.00 / 0.45 |
| Electrical | NL | 32.4% | 28.3% | 20.5% | 1.00 / 0.45 |
| Engine-related | UK | 45.1% | 32.2% | 3.1% | 1.00 / 0.52 |
| Engine-related | NL | 47.3% | 31.9% | 3.2% | 1.00 / 0.43 |

The population-wide comparison finds more of the defects (age carries real information) and keeps the order of the model's own estimates. Observed defect rate by population-wide level (five equal groups of the reference population; same reference for both countries):

| System | UK: level 1 to 5 | NL: level 1 to 5 |
|---|---|---|
| Brakes | 2.3%, 4.1%, 6.0%, 8.8%, 13.5% | 3.8%, 5.1%, 6.2%, 9.0%, 14.5% |
| Electrical | 2.8%, 5.7%, 10.4%, 16.2%, 23.2% | 7.7%, 11.3%, 15.7%, 22.3%, 32.2% |
| Engine-related | 0.6%, 1.6%, 2.4%, 4.0%, 7.0% | 0.4%, 0.8%, 1.2%, 2.7%, 6.3% |

Monotone in both countries (the ordering replicates; the levels shift). The levels are largely a function of age (mean age of level 1 to 5 in the UK: 4.4, 6.2, 8.3, 11.6, 14.9 years for brakes): this is what a user expects ("an old car is more likely to fail than a new one") and the interface must say it.

## 4. Which reference population?

Percentile of the same four vehicles (gap fixed at 12 months) against different references:

| Reference | Mean age | i20 2022 brakes / electrical / engine | Micra 2014 brakes / electrical / engine |
|---|---|---|---|
| **UK cross-fitted (training population, out-of-sample)** | 9.05 | 21 / 13 / 4 | 66 / 80 / 59 |
| Dutch (independent validation population) | 11.5 | 10 / 5 / 2 | 53 / 70 / 47 |
| Israeli registry sample (covered vehicles, scores only, no labels) | 9.03 | 20 / 14 / 11 | 57 / 82 / 64 |
| UK + NL pooled | - | 18 / 10 / 3 | 61 / 76 / 54 |

Recommendation: **the UK cross-fitted scores, per model variant.** Reasons: (1) they are out-of-sample scores of labelled vehicles, so each level can be documented with observed defect rates; (2) the age mix of the covered Israeli fleet is almost identical (mean 9.03 against 9.05 years) and the brakes and electrical decile thresholds are within about 5% to 17% of those computed on the Israeli registry sample (for engine-related the lowest deciles are lower in the Israeli sample, 0.3% to 1.4% against 0.6% to 1.9%, which is why the i20 engine-related percentile is 11 there against 4); (3) it is fixed and reproducible; (4) the Dutch fleet is older (11.5 years), which shifts percentiles by about 10 points, so it is shown only as a sensitivity check. The scale is **not** "compared with Israeli cars" and must not be described so; it is "compared with reference vehicles from UK inspection data". Replacing the reference by Israeli data requires Israeli inspection results (or, without labels, the registry sample, which would only be a description of the fleet).

## 5. Proposal

### Main indicator: "Risk level compared with all reference vehicles"
* One indicator per system (brakes, electrical, engine-related), same scale for every vehicle and every age.
* Value: percentile of the vehicle's XGBoost score in the reference distribution (all ages 3 to 20), shown as five levels: **Very low** (below 20), **Low** (20-40), **Medium** (40-60), **High** (60-80), **Very high** (80 and above), with a bar and a marker, and the text "higher than X of 100 reference vehicles".
* The score is the model's own prediction at a **standard 12-month interval** (no per-plate planned interval).
* Percentiles are never presented as probabilities. The foreign-calibrated probability stays in the details with its caveat; "times the reference average" (for example 1.2 times) is also kept in the details only, because multiples are less reliable across countries than the order (the model's predicted top-to-bottom ratio is 6.3 against 4.0 observed in the Netherlands for brakes).

### Complementary indicator: "Compared with vehicles of the same age"
* Three words, explicitly relative: "Among 12-year-old vehicles: lower than most / typical / higher than most" (below 20th, 20th-80th, above 80th percentile of that age).
* Label under the bar: "This compares only with cars of the same age; use the bar above to compare different vehicles."

### Examples (gap fixed at 12 months, UK reference; the two plates of each model now give identical results)

| Vehicle | System | Estimated risk (reference, foreign calibration, details only) | **Main: level and percentile** | Complementary: same age |
|---|---|---|---|---|
| Hyundai i20 2022 (age 4) | Brakes | 3.3% | **Low (21)** | higher than most 4-year-olds (74) |
| | Electrical | 3.1% | **Very low (13)** | typical for age 4 (46) |
| | Engine-related | 0.3% | **Very low (4)** | lower than most 4-year-olds (16) |
| Nissan Micra 2014 (age 12) | Brakes | 7.8% | **High (66)** | typical for age 12 (31) |
| | Electrical | 18.9% | **High (80)** | typical for age 12 (65) |
| | Engine-related | 2.8% | **Medium (59)** | typical for age 12 (21) |

Reading for a lay user: *"The Micra is estimated to have a higher risk than the i20 in all three systems. The i20 looks relatively high for brakes only when compared with other 4-year-olds, but 4-year-old cars have few defects in general."*

### Wording on the dashboard (plain language)
* Title: "Estimated risk of a defect at the next annual inspection".
* Subtitle (always visible): "This estimates how likely the next annual test is to find a defect in each system, based on age, make and fuel, learned from UK and Dutch inspections. It is not a prediction of a breakdown, and it has not been validated for Israeli cars."
* Bar caption: "Compared with reference vehicles of all ages (UK inspection data). Further right = higher estimated risk."
* Help text: "Older cars have more defects at inspection, so an older car usually sits further right than a newer one."
* Optional later: a compare view for two plates on the same bars.

## 6. What the change would involve (after approval)

* **No retraining and no change to the exported boosters.** The scale is computed from their scores.
* Inference: set the interval to 12 months for the indicators (and, for cleanliness, optionally retrain without that feature later).
* New artifact: reference score deciles (about 100 percentile cut points per system and variant) from the cross-fitted UK scores re-scored at 12 months; `model2_card.json` gets the new reference and the observed defect rate by level.
* API: new fields `risk_level`, `reference_percentile` (main) and `same_age_label` (complementary); existing fields kept for compatibility.
* Front end: replace the circular gauges by the bar with five levels, the same-age line, the plain-language texts above; update tests, the SRS change log (C2) and the demo script.

## 7. Open points for your decision

1. Reference population: UK cross-fitted (recommended) or UK + NL pooled.
2. Standardise the interval at 12 months (recommended) and, optionally, retrain without that feature.
3. Show the "times the reference average" figure in the details (recommended) or not at all.
4. Number of levels: five (recommended) or three.
