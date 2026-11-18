# SmartCar-Ops - Machine Learning (offline research and training)

The deployed models are in `backend/app/ml/artifacts/` (XGBoost JSON + model cards); their numbers are in `docs/MODEL_CARDS.md`. This folder holds the research and the training code.

## Final training (reproducible)

```bash
# Python environment: ml/.venv (the same library versions as the backend image: numpy 2.5, pandas 3.0, xgboost 3.4)
ml/.venv/Scripts/python.exe -I -X utf8 ml/src/final_model1.py        # Model 1: Datasets 7+8+3, monotone XGBoost on age + fuel, CBS calibration, 80% range
ml/.venv/Scripts/python.exe -I -X utf8 ml/src/mot_vehicle_sample.py 2022 41      # UK MOT: full-year streams read and CRC32-verified, 1-in-41 vehicles kept (idem 2023)
ml/.venv/Scripts/python.exe -I -X utf8 ml/src/verify_uk_extraction.py            # independent checks -> docs/UK_EXTRACTION.md
ml/.venv/Scripts/python.exe -I -X utf8 ml/src/final_model2.py        # Model 2: tuning, UK test, Dutch validation, cross-fitted bands, export
```

Raw and intermediate data live outside the project (`~/smartcar_data`, override with `SMARTCAR_DATA_DIR`): Kaggle datasets (`download_datasets.py`), a random sample of the Israeli registry (`sample_gov_registry.py`),
open recalls (`fetch_recalls.py`), Dutch RDW pulls (`rdw_nl_sample.py`).

## Source modules (`src/`)

| Module | Purpose |
|---|---|
| `final_model1.py`, `final_model2.py` | final training and export (approved design) |
| `model2_data.py`, `real_outcome_data.py` | pair tables (inspection i -> next inspection) from UK MOT and Dutch RDW |
| `mot_vehicle_sample.py` | verified UK extraction (decoder chosen from the zip header, CRC32 + size check of the whole stream); `mot_pilot_sample.py` is the earlier test-level sampler |
| `verify_uk_extraction.py` | structural and completeness checks of the extraction |
| `mileage_data.py`, `mileage_experiments.py`, `calibration.py`, `cbs_reference.py` | Model 1 data, experiments, CBS calibration and the official statistics used |
| `israel_registry.py`, `brand_reliability.py` | Hebrew normalisation of registry samples (research); brand reliability experiment |

## Notebooks (research record, in order)

| Notebook | Question | Result used by the final system |
|---|---|---|
| 01 | Model 1: data audit, units, encodings, algorithms, 7+8+3 against 7+8+3+6 | Datasets 7+8+3, XGBoost, age + fuel |
| 02 | Model 2 with Dataset 1: leakage audit, label reverse-engineering | Labels are rules, runtime features give AUC 0.50: Dataset 1 rejected |
| 03 | Model 1 calibration with CBS statistics | Age band x ownership calibration, held-out CBS cells |
| 04, 05 | Real inspection outcomes: UK MOT and Dutch RDW (cross-sectional) | A defect at inspection is learnable; Stage-1 estimate adds nothing |
| 06 | Transfer between countries | Age transfers fully, make effects partly; absolute rates do not |
| 07 | Can Model 1 help Model 2? | Only a **measured** odometer helps; the design with a measured/estimated flag |
| 08, 09 | Next-inspection prediction with histories (NL, UK) | Final target definition; history adds 0.01-0.03 AUC |

**Erratum (found during the final implementation).** The first versions of notebooks 04 to 09 explained an unreadable second half of the UK defect-item files as "decoder corruption". The real cause was that the DVSA item zips use plain Deflate (type 8) while the result zips use Deflate64 (type 9), and a Deflate64 decoder had been used for both. `mot_vehicle_sample.py` now selects the decoder from the zip header and proves the integrity of every stream by CRC32; the final Model 2 was trained on the verified full years. The conclusions of the notebooks, which used only the clean part, are unchanged (see `docs/UK_EXTRACTION.md`).

`src/train_regression.py` and `src/train_classification.py` and the old `.joblib` files come from a first attempt that mixed miles and kilometres and used synthetic labels. They are obsolete and must not be used.
