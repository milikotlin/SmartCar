# Mileage selection: "I know my car's mileage" or the automatic estimate

The mileage block of the dashboard (next to the vehicle card) lets the user choose where the mileage comes from. The choice is explicit and every number says where it comes from.

| Option | Shown as | Source of the number | Verified? |
|---|---|---|---|
| **I don't know my car's mileage** (selected first) | **AI-Estimated Mileage** (tag ML), with the 80% range and the reliability warnings | Model 1 (XGBoost regression on age, fuel type and ownership type, calibrated with CBS statistics) | No: a statistical average for similar vehicles |
| **I know my car's mileage** | **User-Reported Mileage** (tag USER-REPORTED) | Typed by the user in "Enter your current mileage (km)", applied with **Use This Mileage** | **No**: not verified, not officially confirmed, **not saved** |
| (when a record exists) | **Recorded odometer** (tag RECORD) | An odometer stored on a service or inspection record (entered with the workshop key) | As reliable as the record; shown in both options, never replaced |

A vehicle that is only looked up keeps working as before: the automatic estimate is selected and Model 2 receives no odometer.

## Input validation

Client (`frontend/lib/mileage.ts`) and server (`GET /api/v1/predict/{plate}?odometer_km=`, also the chat) both enforce: a whole number from **1 to 1,000,000 km**. Empty, negative, zero, decimal, non-numeric (`abc`, `1e6`) and above 1,000,000 are refused with a clear message (HTTP 422 from the API). A value that is valid but implausible for the vehicle's age is accepted for display and **not given to Model 2** (below).

## How Model 2 uses the value

**Model 2 of Smart_Car_Models.pdf** (the main risk panel) takes the mileage as an input, as specified: the user-reported value when given, otherwise a recorded
odometer, otherwise the Model 1 estimate (`failure_risk.inputs.km` and `km_source` in the API). The rules below concern the **comparison model** trained on real
inspections, which keeps its own design:


Model 2 has four variants. The two **odometer variants** (`cold_odo`, `hist_odo`) were trained with the odometer printed on the UK MOT test, that is, **the odometer at the last annual inspection**. The rules in `services/prediction.py`:

1. **The Model 1 estimate is never an input of Model 2** (unchanged architecture; the experiments of notebooks 04, 07 and 09 showed no gain). With the automatic option Model 2 runs on the registry data (and the stored inspection history, if any).
2. **A recorded inspection odometer always wins.** If an inspection stored for the registry's last test carries an odometer, Model 2 uses it (it is exactly the trained quantity) and says so; a typed value is then shown but not used by the model.
3. **Otherwise a plausible user-reported value is given to Model 2** as the odometer at the last inspection. It is an approximation: it is the *current* mileage, so it includes the driving since that inspection. The risk panel then states the source ("the mileage reported by the user: not verified, treated as the odometer at the last inspection") and the mileage block says the same.
4. **Implausible values are not used:** more than 60,000 km per year of the vehicle's age (for example 900,000 km on an 11-year-old car). They are shown as reported, with the note "Not used by the risk model", because a typing mistake is far more likely than such a usage.
5. If Model 2 does not cover the vehicle (electric, gas, under 3 or over 20 years), the value is shown but not used, and the note says so.
6. The maintenance rules use a user-reported value like a current odometer, labelled "user-reported (not verified)" in the panel.

The risk is recomputed whenever the odometer variant changes; if the typed value does not change Model 2's valid input, the risk stays exactly what it was.

### Hypothesis and evidence (`ml/src/model2_odometer_sensitivity.py`, `ml/model2_odometer_sensitivity.json`)

**Hypothesis:** the current mileage typed by the user is close enough to the odometer at the last inspection (a few months to a year of driving earlier) for the odometer variants to stay useful. Test: the exported models on 150,000 UK pairs, scoring with the true odometer and with perturbed values (the exported models were fitted on these pairs, so absolute AUCs are slightly optimistic; the comparison between rows is what matters). ROC-AUC, brakes / electrical / engine-related:

| Odometer given to the model | Brakes | Electrical | Engine | Vehicles whose level changes (brakes) |
|---|---|---|---|---|
| none (registry-only variant) | 0.6791 | 0.7093 | 0.7160 | |
| true odometer | 0.6971 | 0.7280 | 0.7468 | 0% |
| 5% off (months of driving since the test) | 0.6966 | 0.7275 | 0.7451 | 3% |
| 10% off (about a year of driving) | 0.6964 | 0.7272 | 0.7443 | 6% |
| rounded to the nearest 10,000 km | 0.6968 | 0.7275 | 0.7458 | 2% |
| random error of 10% | 0.6966 | 0.7271 | 0.7447 | 3% |
| random error of 25% | 0.6947 | 0.7251 | 0.7411 | 7% |
| random error of 50% | 0.6894 | 0.7186 | 0.7322 | 15% |
| always 30% too high | 0.6958 | 0.7258 | 0.7424 | 14% |
| always 50% too low | 0.6940 | 0.7248 | 0.7312 | 43% |

Reading: a value off by the driving done since the last inspection (5% to 10%) keeps 95% to 97% of the gain of a true odometer and changes the level of 3% to 8% of the vehicles; rounding costs almost nothing; an error of 25% keeps 85% to 90% of the gain. **In no tested scenario does a wrong odometer make the ranking worse than giving none** (AUC). But the *level* is a position on a fixed scale, so a gross error moves it: 15% of the vehicles change level with a random error of 50%, 43% when the value is always half the real one. This is why the value is labelled unverified, why it is not back-dated (the difference is small and a correction would be an unvalidated assumption), and why implausible values are excluded.

## Persistence and security

* The typed value lives only in the page state and in the request of that view (`?odometer_km=`): **it is not written to the database**, not cached, and disappears when the plate is searched again or the option is switched back. Nothing stored is overwritten: an estimate or a typed value never replaces a recorded odometer.
* Saving a mileage as a record remains a separate, deliberate action: the service log forms, protected by the workshop key (`X-Write-Key`), rate limits and date checks. Nothing about those endpoints changed.
* The key field and the backend security are unchanged; the new parameter is read-only (GET) and validated.

## Switching between the options

The page keeps one counter for requests: only the answer to the **last** request reaches the screen. Choosing the automatic estimate drops the typed value and reloads. While a result loads, the mileage block shows "Updating the results…", the maintenance and recall panels are dimmed, and if the load takes longer than a quarter of a second the risk panel is replaced by a placeholder, so a result computed from a value that is no longer selected is not left as current. Switching again during a slow request is safe (tested with 1.5 s of added latency).

## API fields (`mileage`, `inspection_risk`)

`primary_source` is `user_reported`, `measured` (a stored record) or `estimated`; `user_reported_km`, `user_reported_used_by_model2`, `user_reported_note`; `measured_km` / `measured_as_of` are only ever stored records; `inspection_risk.odometer_source` is `recorded_inspection`, `user_reported` or `null`; the previously used field `uses_measured_odometer` now means "an odometer value (recorded or user-reported) is an input".

## Tests

`backend/tests/test_mileage_selection.py` (9 tests) and the updated `test_api.py`: both options, labels, nothing stored, Model 2 receives exactly the typed value when used (levels equal to a direct model call), implausible and uncovered cases, recorded odometer wins and is never overwritten, invalid values (API returns 422), chat facts labelled "USER-REPORTED". `scripts/e2e_live.py`: the contract on real plates. `scripts/visual_check.py` (desktop and phone): default selection, invalid inputs and messages, valid value, implausible value, back to the estimate without stale values, switching during a slow request.

## Limitations

* The typed value is trusted as typed: the system cannot verify it. A wrong but plausible value changes the risk level (see the table).
* It is the current mileage used as the odometer at the last inspection: slightly higher than the trained quantity.
* The evidence of the sensitivity test is on UK data with the exported models (not out of sample), and no Israeli odometer data exist to test on.
* The 60,000 km per year threshold is a conservative guard, not a statistic: it only catches gross typing mistakes. Values that are too low are not detectable.
