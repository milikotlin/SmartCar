"""Renders docs/MODEL2_VS_AGE_BASELINE.md from ml/model2_vs_age_baseline.json (numbers copied by code). Run: python ml/src/render_age_baseline_report.py"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
d = json.loads((ROOT / "ml" / "model2_vs_age_baseline.json").read_text(encoding="utf-8"))
rows = d["rows"]
NAME = {"brakes": "Brakes", "electrical": "Electrical", "engine_emissions": "Engine-related"}
SETS = ["UK out-of-sample (3-fold by vehicle)", "NL independent (UK-trained)"]


def get(ts, system, model):
    return next(r for r in rows if r["test_set"] == ts and r["system"] == system and r["model"] == model)


def table(ts, models):
    out = ["| System | Model | ROC-AUC | gain over age | AUC inside each age | Recall (31% flagged) | Precision (31% flagged) | Lift |", "|---|---|---|---|---|---|---|---|"]
    for s in NAME:
        base = get(ts, s, "age only")
        for m in ["age only"] + models:
            r = get(ts, s, m)
            gain = "" if m == "age only" else f"{r['auc'] - base['auc']:+.3f}"
            out.append(f"| {NAME[s]} | {m} | {r['auc']:.3f} | {gain} | {r['within_age_auc']:.3f} | {r['recall'] * 100:.1f}% | {r['precision'] * 100:.1f}% | {r['lift']:.2f} |")
    return "\n".join(out)


def share_of_age(ts, model):
    out = []
    for s in NAME:
        a, m = get(ts, s, "age only")["auc"], get(ts, s, model)["auc"]
        out.append(f"{NAME[s].lower()} {100 * (a - 0.5) / (m - 0.5):.0f}%")
    return ", ".join(out)


md = f"""# What does Model 2 add beyond the age of the vehicle?

Question: how much better is the XGBoost model than the simplest classification possible, one that uses **only the age of the vehicle**? Nothing was retrained for the
product and nothing was exported; the script `ml/src/model2_vs_age_baseline.py` (results in `ml/model2_vs_age_baseline.json`) only evaluates.

## Method (the same test sets for the model and the baseline)

* **Age-only baseline:** the observed defect rate of each age year (3 to 20) in the training data. It is the best possible score that uses age alone.
* **UK, out of sample:** {d['uk_pairs']:,} inspection pairs, 3-fold cross-fit by vehicle (the same procedure and hyper-parameters as the reference of the risk scale; these evaluation fits are not the exported models). The baseline is fitted on the same training folds.
* **NL, independent:** {d['nl_pairs']:,} Dutch pairs. The **exported** models (trained on the UK) against the baseline fitted on all UK pairs. The Dutch data have no odometer, so only `cold` and `hist` exist there.
* **ROC-AUC:** overall. **AUC inside each age:** the AUC computed separately for each age year and averaged (weighted by vehicles). An age-only score is 0.50 by construction, so this is the part of the ranking that does **not** come from age.
* **Recall and Precision:** the 31% of vehicles with the highest score are flagged (31% is the share of the "High" level of the risk scale). Recall = share of all vehicles with a defect that were flagged; Precision = share of flagged vehicles that had a defect; Lift = Precision / base rate. Ties of the baseline are broken at random.

## UK, out of sample

{table(SETS[0], ["XGBoost cold", "XGBoost hist", "XGBoost hist_odo"])}

## Netherlands, independent validation (exported models)

{table(SETS[1], ["XGBoost cold (exported)", "XGBoost hist (exported)"])}

## Reading

* **Age alone already ranks vehicles reasonably** (AUC 0.64 to 0.72). Share of the model's discrimination (AUC above 0.5) that age alone reproduces: UK cold variant {share_of_age(SETS[0], "XGBoost cold")}; NL cold variant {share_of_age(SETS[1], "XGBoost cold (exported)")}; UK with history and odometer {share_of_age(SETS[0], "XGBoost hist_odo")}.
* **The cold-start model (registry only) adds little beyond age:** +0.021 to +0.031 AUC in the UK. On the independent Dutch data the gain is **+0.005 for brakes** (practically none), +0.015 for electrical and +0.019 for engine-related. Recall and Precision at 31% flagged move by a few percentage points in the UK and not at all for brakes in the NL.
* **The model adds more when it knows more:** with the result of the previous inspection the gain is +0.036 to +0.063 (UK) and +0.024 to +0.044 (NL); with history and measured odometer +0.048 to +0.083 (UK). Recall at 31% flagged rises by 6.6 to 11.2 percentage points over age alone in the UK (variant `hist_odo`).
* **Inside the same age the ranking is modest but real:** AUC 0.54 to 0.63 (cold) and up to 0.71 (history and odometer), against 0.50 for age alone. This is what the "compared with vehicles of the same age" line of the dashboard rests on.
* **What this means for the claims:** the model is a *modest* improvement over a classification by age; its main value is the electrical and engine-related systems, and the cases where an inspection history or a measured odometer exist. It is not a precise predictor, and for brakes without history it is close to an age table. The dashboard already states that the level is relative, mostly reflects age, and has not been validated for Israeli vehicles.
* Limits of this comparison: the baseline is deliberately simple and strong (a table per age year fitted on the same data); both use defects found at an annual inspection as the target, not breakdowns; Israeli inspection results are not available, so nothing here measures performance on Israeli vehicles.
"""
(ROOT / "docs" / "MODEL2_VS_AGE_BASELINE.md").write_text(md, encoding="utf-8")
print("written docs/MODEL2_VS_AGE_BASELINE.md")
