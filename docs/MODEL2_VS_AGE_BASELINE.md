# What does Model 2 add beyond the age of the vehicle?

Question: how much better is the XGBoost model than the simplest classification possible, one that uses **only the age of the vehicle**? Nothing was retrained for the
product and nothing was exported; the script `ml/src/model2_vs_age_baseline.py` (results in `ml/model2_vs_age_baseline.json`) only evaluates.

## Method (the same test sets for the model and the baseline)

* **Age-only baseline:** the observed defect rate of each age year (3 to 20) in the training data. It is the best possible score that uses age alone.
* **UK, out of sample:** 660,202 inspection pairs, 3-fold cross-fit by vehicle (the same procedure and hyper-parameters as the reference of the risk scale; these evaluation fits are not the exported models). The baseline is fitted on the same training folds.
* **NL, independent:** 366,950 Dutch pairs. The **exported** models (trained on the UK) against the baseline fitted on all UK pairs. The Dutch data have no odometer, so only `cold` and `hist` exist there.
* **ROC-AUC:** overall. **AUC inside each age:** the AUC computed separately for each age year and averaged (weighted by vehicles). An age-only score is 0.50 by construction, so this is the part of the ranking that does **not** come from age.
* **Recall and Precision:** the 31% of vehicles with the highest score are flagged (31% is the share of the "High" level of the risk scale). Recall = share of all vehicles with a defect that were flagged; Precision = share of flagged vehicles that had a defect; Lift = Precision / base rate. Ties of the baseline are broken at random.

## UK, out of sample

| System | Model | ROC-AUC | gain over age | AUC inside each age | Recall (31% flagged) | Precision (31% flagged) | Lift |
|---|---|---|---|---|---|---|---|
| Brakes | age only | 0.655 |  | 0.493 | 51.2% | 11.4% | 1.65 |
| Brakes | XGBoost cold | 0.676 | +0.021 | 0.590 | 53.9% | 12.0% | 1.74 |
| Brakes | XGBoost hist | 0.690 | +0.036 | 0.616 | 56.1% | 12.5% | 1.81 |
| Brakes | XGBoost hist_odo | 0.703 | +0.048 | 0.643 | 57.8% | 12.9% | 1.86 |
| Electrical | age only | 0.681 |  | 0.495 | 52.8% | 19.9% | 1.70 |
| Electrical | XGBoost cold | 0.708 | +0.028 | 0.615 | 56.6% | 21.3% | 1.83 |
| Electrical | XGBoost hist | 0.724 | +0.043 | 0.642 | 58.7% | 22.1% | 1.89 |
| Electrical | XGBoost hist_odo | 0.737 | +0.057 | 0.666 | 61.0% | 22.9% | 1.97 |
| Engine-related | age only | 0.684 |  | 0.489 | 57.4% | 5.8% | 1.85 |
| Engine-related | XGBoost cold | 0.715 | +0.031 | 0.627 | 61.2% | 6.1% | 1.97 |
| Engine-related | XGBoost hist | 0.747 | +0.063 | 0.674 | 65.4% | 6.6% | 2.11 |
| Engine-related | XGBoost hist_odo | 0.767 | +0.083 | 0.709 | 68.6% | 6.9% | 2.21 |

## Netherlands, independent validation (exported models)

| System | Model | ROC-AUC | gain over age | AUC inside each age | Recall (31% flagged) | Precision (31% flagged) | Lift |
|---|---|---|---|---|---|---|---|
| Brakes | age only | 0.638 |  | 0.500 | 49.8% | 14.5% | 1.61 |
| Brakes | XGBoost cold (exported) | 0.642 | +0.005 | 0.539 | 49.8% | 14.5% | 1.61 |
| Brakes | XGBoost hist (exported) | 0.662 | +0.024 | 0.583 | 51.6% | 15.0% | 1.66 |
| Electrical | age only | 0.641 |  | 0.500 | 47.3% | 31.3% | 1.53 |
| Electrical | XGBoost cold (exported) | 0.656 | +0.015 | 0.571 | 48.5% | 32.1% | 1.56 |
| Electrical | XGBoost hist (exported) | 0.685 | +0.044 | 0.624 | 51.7% | 34.2% | 1.67 |
| Engine-related | age only | 0.718 |  | 0.500 | 62.6% | 6.4% | 2.02 |
| Engine-related | XGBoost cold (exported) | 0.737 | +0.019 | 0.600 | 65.6% | 6.7% | 2.12 |
| Engine-related | XGBoost hist (exported) | 0.760 | +0.042 | 0.637 | 69.6% | 7.1% | 2.24 |

## Reading

* **Age alone already ranks vehicles reasonably** (AUC 0.64 to 0.72). Share of the model's discrimination (AUC above 0.5) that age alone reproduces: UK cold variant brakes 88%, electrical 87%, engine-related 85%; NL cold variant brakes 97%, electrical 90%, engine-related 92%; UK with history and odometer brakes 76%, electrical 76%, engine-related 69%.
* **The cold-start model (registry only) adds little beyond age:** +0.021 to +0.031 AUC in the UK. On the independent Dutch data the gain is **+0.005 for brakes** (practically none), +0.015 for electrical and +0.019 for engine-related. Recall and Precision at 31% flagged move by a few percentage points in the UK and not at all for brakes in the NL.
* **The model adds more when it knows more:** with the result of the previous inspection the gain is +0.036 to +0.063 (UK) and +0.024 to +0.044 (NL); with history and measured odometer +0.048 to +0.083 (UK). Recall at 31% flagged rises by 6.6 to 11.2 percentage points over age alone in the UK (variant `hist_odo`).
* **Inside the same age the ranking is modest but real:** AUC 0.54 to 0.63 (cold) and up to 0.71 (history and odometer), against 0.50 for age alone. This is what the "compared with vehicles of the same age" line of the dashboard rests on.
* **What this means for the claims:** the model is a *modest* improvement over a classification by age; its main value is the electrical and engine-related systems, and the cases where an inspection history or a measured odometer exist. It is not a precise predictor, and for brakes without history it is close to an age table. The dashboard already states that the level is relative, mostly reflects age, and has not been validated for Israeli vehicles.
* Limits of this comparison: the baseline is deliberately simple and strong (a table per age year fitted on the same data); both use defects found at an annual inspection as the target, not breakdowns; Israeli inspection results are not available, so nothing here measures performance on Israeli vehicles.
