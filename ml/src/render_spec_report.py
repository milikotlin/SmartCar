"""Renders docs/SPEC_MODELS.md from ml/model1_results.json, ml/model2_results.json and the model cards (numbers copied by code, never by hand).

Run: ml/.venv/Scripts/python.exe -I -X utf8 ml/src/render_spec_report.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kaggle_sources import KAGGLE  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "backend" / "app" / "ml" / "artifacts" / "spec"
load = lambda p: json.loads(p.read_text(encoding="utf-8"))
r1, r2 = load(ROOT / "ml" / "model1_results.json"), load(ROOT / "ml" / "model2_results.json")
c1, c2 = load(SPEC / "model1_card.json"), load(SPEC / "model2_card.json")
shr = load(ROOT / "ml" / "model1_transfer_shrinkage.json")
ref = load(ROOT / "backend" / "app" / "ml" / "artifacts" / "model2" / "model2_reference.json")
km = lambda x: f"{x:,.0f}"
SC = ["no records (plate only)", "odometer known", "last inspection known", "odometer + last inspection"]


# ------------------------------------------------------------------ Model 1
def m1_compare() -> str:
    t = ["| Test data | Version | RMSE (km) | MAE (km) | R² |", "|---|---|---|---|---|"]
    for name, v in c1["comparison_with_previous_version"].items():
        if "rmse" in v["new"] if isinstance(v["new"], dict) else False:
            for w in ("previous", "new"):
                t.append(f"| {name} | {w} | {km(v[w]['rmse'])} | {km(v[w]['mae'])} | {v[w]['r2']:.3f} |")
    cmp = c1["comparison_with_previous_version"]
    a, b = cmp["interval_80pct_coverage_on_real_odometers"], cmp["cbs_joint_cell_mean_abs_pct_error"]
    t += ["", "| Other checks | Previous | New |", "|---|---|---|",
          f"| Share of real odometers inside the \"80%\" range (should be 80%) | {a['previous']:.1%} | {a['new']:.1%} |",
          f"| Error against the official Israeli averages (CBS cells age x ownership, not fitted directly) | {b['previous']:.1f}% | {b['new']:.1f}% |"]
    return "\n".join(t)


def m1_val_table(d: dict, chosen=None, head="Variant") -> str:
    t = [f"| {head} | Kaggle RMSE | Kaggle MAE | Kaggle R² | Real odometers RMSE | MAE | R² |", "|---|---|---|---|---|---|---|"]
    for k, v in d.items():
        a, b = v["kaggle_val"], v["official_val"]
        t.append(f"| {k}{' **(chosen)**' if k == chosen else ''} | {km(a['rmse'])} | {km(a['mae'])} | {a['r2']:.3f} | {km(b['rmse'])} | {km(b['mae'])} | {b['r2']:.3f} |")
    return "\n".join(t)


def m1_by(key: str) -> str:
    t = ["| Group (real test odometers) | Vehicles | RMSE | MAE | R² | Bias |", "|---|---|---|---|---|---|"]
    t += [f"| {k} | {v['n']:,} | {km(v['rmse'])} | {km(v['mae'])} | {v['r2']:.3f} | {v['bias']:+,.0f} |" for k, v in r1["test"][key].items()]
    return "\n".join(t)


# ------------------------------------------------------------------ Model 2
def m2_compare(b: str) -> str:
    t = ["| Real vehicles | What is known | Version | Recall | Precision | ROC-AUC |", "|---|---|---|---|---|---|"]
    for where, label in (("uk", "UK test"), ("nl", "Netherlands")):
        if where not in r2[b]["test"]:
            continue
        w = r2[b]["test"][where]
        for sc, q in w["scenarios"].items():
            for v in ("previous", "new"):
                t.append(f"| {label} ({w['vehicles']:,}; base rate {w['base_rate']:.1%}) | {sc} | {v} | {q[v]['recall']:.3f} | {q[v]['precision']:.3f} | {q[v]['roc_auc']:.3f} |")
        g = w["age_only"]
        t.append(f"| {label} | age only (baseline) | - | {g['recall']:.3f} | {g['precision']:.3f} | {g['roc_auc']:.3f} |")
    return "\n".join(t)


def m2_mean(b: str) -> str:
    m = r2[b]["test"]["uk"]["mean"]
    t = ["| | Recall | Precision | ROC-AUC | PR-AUC |", "|---|---|---|---|---|"]
    return "\n".join(t + [f"| {w.title()} | {m[w]['recall']:.3f} | {m[w]['precision']:.3f} | {m[w]['roc_auc']:.3f} | {m[w]['pr_auc']:.3f} |" for w in ("previous", "new")])


def m2_val(b: str, key: str, chosen=None) -> str:
    t = ["| Variant (mean of the four situations, real UK validation vehicles) | Recall | Precision | ROC-AUC |", "|---|---|---|---|"]
    for k, v in r2[b][key].items():
        t.append(f"| {k}{' **(chosen)**' if k == chosen else ''} | {v['mean']['recall']:.3f} | {v['mean']['precision']:.3f} | {v['mean']['roc_auc']:.4f} |")
    return "\n".join(t)


def m2_levels(b: str) -> str:
    lv = r2[b]["levels"]
    g = r2[b]["test"]["gain_over_age_only_plate_only_95ci"]
    o = r2[b]["overfitting_check"]
    return (f"Levels: {lv['rule']}. Real UK test vehicles with a defect at the next inspection (Low / Moderate / High): **" + " / ".join(f"{x:.0%}" for x in lv["test_rate_by_level"]) + "**. "
            f"Mean calibration error {c2[b]['mean_calibration_error']:.3f}. Gain over \"age only\" when only the plate is known: {g[1]:+.3f} ROC-AUC (95% interval {g[0]:+.3f} to {g[2]:+.3f}). "
            f"Over-fitting check (same masking): synthetic training rows {o['train_auc']:.3f}, real vehicles of the generator's part {o['real_fit_auc_same_masking']:.3f}, real validation vehicles never seen {o['val_auc_same_masking']:.3f}.")


fid1 = r1["synthetic_fidelity"]["official (against real vehicles the generator never saw)"]
fid = lambda f: f"largest KS distance {max(f['ks_statistic'].values()):.3f}, largest total variation {max(f['total_variation'].values()):.3f}, largest difference in Spearman correlation {f['largest_spearman_difference']:.3f}"
f2 = {b: r2[b]["synthetic_fidelity (against real vehicles the generator never saw)"] for b in ("ice", "ev")}
used = {**r1["data"]["kaggle_sources"], **r2["kaggle_sources"]}
uk = {(r["variant"], r["system"]): r["UK cross-fitted AUC, standardised 12 months"] for r in ref["interval_standardisation_check"] if r["variant"] == "cold"}
d1h = r2["ice"]["test"]["dataset1_held_out"]
ex2 = r2["ice"]["experiment_2_imbalance"]
cmp = c1["comparison_with_previous_version"]
real1 = cmp["real odometers (the same 6,000 official test vehicles)"]
md = f"""# The two models of Smart_Car_Models.pdf (version 3.0.0: data augmentation, leak-free, tested on real vehicles)

Generated by `ml/src/render_spec_report.py` from `ml/model1_results.json`, `ml/model2_results.json` and the model cards (no number is typed by hand). Training:
`ml/src/model1_train.py`, `ml/src/model2_train.py`; generators: `ml/src/synthesis.py`; real data: `ml/src/official_data.py`. The superseded version 2.0.0 is in `ml/archive/`.

## In one minute

| | Before (2.0.0) | Now (3.0.0) | Measured on |
|---|---|---|---|
| Model 1 RMSE | {km(real1['previous']['rmse'])} km | **{km(real1['new']['rmse'])} km** | the same 6,000 real odometers |
| Model 1 MAE | {km(real1['previous']['mae'])} km | **{km(real1['new']['mae'])} km** | the same |
| Model 1 R² | {real1['previous']['r2']:.3f} | **{real1['new']['r2']:.3f}** | the same |
| Model 2 Recall (combustion) | {r2['ice']['test']['uk']['mean']['previous']['recall']:.3f} | **{r2['ice']['test']['uk']['mean']['new']['recall']:.3f}** | {r2['ice']['test']['uk']['vehicles']:,} real UK vehicles, riskiest 40% flagged |
| Model 2 Precision (combustion) | {r2['ice']['test']['uk']['mean']['previous']['precision']:.3f} | **{r2['ice']['test']['uk']['mean']['new']['precision']:.3f}** | the same (base rate {r2['ice']['test']['uk']['base_rate']:.3f}) |
| Model 2 ROC-AUC (combustion) | {r2['ice']['test']['uk']['mean']['previous']['roc_auc']:.3f} | **{r2['ice']['test']['uk']['mean']['new']['roc_auc']:.3f}** | the same |
| Model 2 ROC-AUC (electric / hybrid) | {r2['ev']['test']['uk']['mean']['previous']['roc_auc']:.3f} | **{r2['ev']['test']['uk']['mean']['new']['roc_auc']:.3f}** | {r2['ev']['test']['uk']['vehicles']:,} real UK vehicles |

**Correction of an earlier result.** Version 2.0.0 reported ROC-AUC {c2['previous_version']['reported_dataset1_test_auc_affected_by_leakage']:.3f} for Model 2 on Dataset 1. That figure was largely **data leakage** and is withdrawn:
* `Maintenance_Type`: {r2['leakage_removed']['Maintenance_Type']};
* `Days_Since_Last_Maintenance > 180`: {r2['leakage_removed']['Days_Since_Last_Maintenance > 180']};
* the brand index was computed with the same vehicles used for the external check; "no inspection on file" was read as "zero failures".

On real vehicles that model was close to chance. A ROC-AUC near 0.67 on real inspections is lower than 0.978 on rule-generated labels, but it is a real ability to rank real vehicles.

## Data: what is real, what is synthetic, where each is used

| Data | Nature | Used for |
|---|---|---|
""" + "\n".join(f"| Kaggle {k}: {used.get(k, 'kagglehub: ' + KAGGLE[k][0])} | original, unchanged | training (and a held-out part for testing) |" for k in KAGGLE) + f"""
| UK DVSA MOT 2022 + 2023, part `fit` (60% of vehicles) | official, real | only to fit the synthetic generator, the brand index and the reference counts |
| UK MOT, part `val` (20%) | official, real | every choice (algorithm, augmentation, weights, hyper-parameters, calibration of the score, level cuts) |
| UK MOT, part `test` (20%) | official, real | final test |
| Netherlands RDW inspections | official, real | final test in a second country (Model 2) |
| Synthetic vehicles ({r1['data']['synthetic_training_rows']:,} for Model 1; {r2['ice']['synthetic_rows']:,} + {r2['ev']['synthetic_rows']:,} for Model 2) | **synthetic** | **training only**; never in a validation or test set |
| CBS Publication 1923, Israeli registry | official, real | Israeli level of Model 1 |

The split is by vehicle (a hash of its identifier): no vehicle is in two parts. The synthetic rows come from sequential CART synthesis (each column drawn given the previous ones, as in `synthpop`) with
SMOTE-like interpolation inside a leaf. Fidelity against real vehicles the generator never saw: Model 1 {fid(fid1)}; Model 2 combustion {fid(f2['ice'])}; electric / hybrid {fid(f2['ev'])}.
Training on real rows instead of synthetic ones gives practically the same result (reference rows in the tables below), which shows the synthetic vehicles carry the same information.

Adding vehicles generated from official inspections goes beyond the datasets named in the PDF. It was the only way to improve predictions for vehicles **in use** (the Kaggle listings are cars for sale, and the
Kaggle Dataset 1 and 5 labels are rule-generated); all PDF datasets, encodings, algorithms, experiments and metrics stay.
Dataset 1 answers 403 to anonymous Kaggle requests: without `kagglehub.login()` the copy downloaded from the same page on 2026-11-17 is used and the log says so.

## Model 1: odometer regression

**As specified:** Datasets 7 (backbone), 8 (Owner_Type) and 3 (Cardekho); One-Hot Encoding; Target vs Frequency Encoding for Make/Model; KNN imputer K=5 (now on standardised columns and within the same fuel); Linear and
Ridge with StandardScaler / MinMaxScaler against Random Forest and XGBoost; chosen by RMSE and MAE. Kaggle rows: {', '.join(f'{k} {v:,}' for k, v in c1['rows_by_dataset'].items())}.

### Before and after (final test, rows never used)

{m1_compare()}

Against a plain table on all {r1['test']['official_test']['n']:,} real test odometers: {"; ".join(f"{k} RMSE {km(v['rmse'])}, R² {v['r2']:.3f}" for k, v in r1['test']['baselines_on_official_test'].items())}; the model RMSE {km(r1['test']['official_test']['rmse'])}, MAE {km(r1['test']['official_test']['mae'])}, R² {r1['test']['official_test']['r2']:.3f}.
Most of the information is age and fuel; make, model and engine add a smaller part, and these figures describe the regression itself on UK cars, not the error in Israel.

The previous model was trained only on cars for sale: on real cars in use it was {abs(real1['previous']['bias']):,.0f} km too low on average (now {real1['new']['bias']:+,.0f} km). A `listing` flag lets one model serve both populations.

{m1_by('official_test_by_age')}

{m1_by('official_test_by_fuel')}

### Experiments (validation, real rows)

{m1_val_table(r1['experiment_1_encoding'], r1['experiment_1_chosen'], 'Encoding of Make/Model')}

{m1_val_table(r1['experiment_2_algorithms'], r1['experiment_2_chosen'], 'Algorithm')}

{m1_val_table(r1['experiment_3_augmentation'], None, 'Training data')}

Final: {r1['final']['algorithm']}, {r1['final']['encoding']} encoding, {r1['final']['params']}; Kaggle rows weigh {r1['final']['kaggle_weight']:g}. Over-fitting check (R²): Kaggle train {r1['overfitting_check']['kaggle_train_r2']:.3f} / validation {r1['overfitting_check']['kaggle_val_r2']:.3f};
synthetic train {r1['overfitting_check']['synthetic_train_r2']:.3f} / real validation {r1['overfitting_check']['official_val_real_r2']:.3f}.

### From the model to an Israeli estimate

* **Level**: official. CBS kilometres per year by age, with raked factors for age band, ownership and propulsion. Error on the joint CBS cells: {cmp['cbs_joint_cell_mean_abs_pct_error']['new']:.1f}% (before {cmp['cbs_joint_cell_mean_abs_pct_error']['previous']:.1f}%).
* **Shape**: learned from real odometers by fuel and age. The individual effect of make / model / engine is shrunk (lambda = {c1['chosen']['lambda']}): tested on two foreign markets (India, US) it did not transfer (`ml/model1_transfer_shrinkage.json`).
* **Range**: how real vehicles spread around the estimate; {c1['interval_80pct_heldout_coverage']:.1%} of real test odometers fall inside.
* **Low reliability** is shown for electric vehicles (no CBS figure), hybrids older than {c1['support_max_age']['hybrid']} years (the real UK ones are mostly former taxis), groups with fewer than 100 real vehicles, and more than 40,000 km a year.
* Dataset 8 `Owner_Type` is the *number of owners*, not private / leasing as the PDF says; it is used as such.
* **Not measurable:** the error for one Israeli car. Israel publishes no odometers.

## Model 2: predictive maintenance classifier

**As specified:** Dataset 1 for combustion vehicles, Dataset 5 branch for electric / hybrid, Dataset 4 aggregated into failure rates by mileage group, sensors dropped, Vehicle_Age, Days_Since_Last_Maintenance, Brand_Reliability_Index,
failure history, the mileage predicted by Model 1 (**Model 1 -> Model 2**); SMOTE vs scale_pos_weight; XGBoost vs Logistic Regression; tuning that maximises Recall.

**Recall and Precision** are measured when the {r2['flag_share']:.0%} of vehicles with the highest score are flagged. A fixed share makes versions comparable and stops Recall from being "improved" by flagging every vehicle.
**Missing information** is part of training: rows are masked at random, so "unknown" is not read as "zero". A known odometer enters on Model 1's own scale (its ratio to the estimate), so the Israeli level does not distort the score.

### Combustion branch: before and after on real vehicles (final test)

{m2_mean('ice')}

{m2_compare('ice')}

{m2_levels('ice')}

On Dataset 1 rows never used (leak-free columns, 40% flagged): """ + "; ".join(f"{k}: ROC-AUC {v['roc_auc']:.3f}, Recall {v['recall']:.3f}, Precision {v['precision']:.3f} (base rate {v['base_rate']:.2f})" for k, v in d1h.items()) + f""".
The 250K file stays high because its label *is* a rule on the days since the last maintenance; this is reported for completeness and is not evidence of quality.

{m2_val('ice', 'experiment_1_training_data', f"Kaggle {int(r2['ice']['experiment_1_chosen']['kaggle_share'] * 100)}% + synthetic official")}

{m2_val('ice', 'experiment_2_imbalance', r2['ice']['experiment_2_chosen'])}

SMOTE was tested and {'chosen' if r2['ice']['experiment_2_chosen'].endswith('SMOTE') else 'not chosen: on real vehicles it was slightly worse than scale_pos_weight'} (its interpolated rows need complete inputs, and the classes are only mildly imbalanced). Final hyper-parameters (chosen by Recall): {r2['ice']['final']['params'] or 'defaults'}.

### Electric / hybrid branch: before and after on real vehicles (final test)

{m2_mean('ev')}

{m2_compare('ev')}

{m2_levels('ev')}

{m2_val('ev', 'experiment_1_training_data', f"Kaggle {int(r2['ev']['experiment_1_chosen']['kaggle_share'] * 100)}% + synthetic official")}

{m2_val('ev', 'experiment_2_imbalance', r2['ev']['experiment_2_chosen'])}

The Dataset 5 columns left after the strict dropping carry no signal (single-feature ROC-AUC: {', '.join(f'{k} {v:.3f}' for k, v in r2['ev']['test']['dataset5']['single_feature_auc'].items())}); what this branch knows comes from the real inspections of hybrids (few electric vehicles).

## Comparison model on the dashboard

The model trained directly on UK inspections stays as a comparison panel (plate-only ROC-AUC brakes / electrical / engine: {uk.get(('cold', 'brakes'), float('nan')):.3f} / {uk.get(('cold', 'electrical'), float('nan')):.3f} / {uk.get(('cold', 'engine_emissions'), float('nan')):.3f}).

## What these models still cannot do

* No Israeli odometers or inspection results exist: neither model can be validated on Israeli vehicles.
* The UK test vehicles were evaluated again after two corrections that were not chosen on them (a duplicated Dutch column; non-decreasing Dataset 4 rates, so that a new car is never riskier than an older one);
  the score calibration and the level cuts were then fitted on validation vehicles. No choice was made on the test vehicles, but this was not a single blind opening.
* With only the plate, the electric / hybrid branch is not significantly better than age alone (interval above includes zero).
* Model 2 predicts a *defect at the next inspection*, the only real outcome available, not a breakdown on the road. It is shown as three levels, never as a percentage.
* With only the plate, Model 2 is a modest improvement over age alone; it becomes clearly better when the odometer and the last inspection are entered. Inside the same age it separates vehicles only moderately.
* The service log (days since maintenance) is learned from rule-generated Kaggle labels: no real data set links services to failures.
"""
(ROOT / "docs" / "SPEC_MODELS.md").write_text(md, encoding="utf-8")
print("written docs/SPEC_MODELS.md")
