# SmartCar-Ops — Sprint 3 (Machine Learning experiments)

**Status: experiments only.** Nothing here is exported (`.joblib`) or wired into the backend yet — that waits for approval.
The `.joblib` files in `ml/models/` and the scripts `src/train_regression.py` / `src/train_classification.py` come from a
first attempt that mixed miles and km and used a dataset with random component labels. **Do not use them.**

## Reproduce

```bash
# from the project root, using the ml virtualenv (ml/.venv)
ml/.venv/Scripts/python.exe -I ml/src/download_datasets.py        # public Kaggle datasets -> ~/smartcar_data/raw (outside OneDrive)
ml/.venv/Scripts/python.exe -I -X utf8 ml/src/sample_gov_registry.py 20   # 20k random Israeli registry rows
ml/.venv/Scripts/python.exe -I -X utf8 ml/src/fetch_recalls.py            # official open-recall dataset
cd ml/notebooks && ../.venv/Scripts/python.exe -I -m nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=-1 01_model1_mileage_experiments.ipynb
cd ml/notebooks && ../.venv/Scripts/python.exe -I -m nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=-1 02_model2_maintenance_feasibility.ipynb
```

Data directory: `~/smartcar_data` (override with `SMARTCAR_DATA_DIR`). It is deliberately **outside** the project because the
project lives in OneDrive and the Craigslist file alone is >1 GB. The notebooks print file hashes for provenance.

## Notebooks

| Notebook | Question |
|---|---|
| `notebooks/01_model1_mileage_experiments.ipynb` | Model 1 (Kilometers_Driven): data audit, units, features, encodings, algorithms, **7+8+3 vs 7+8+3+6**, Israeli compatibility |
| `notebooks/02_model2_maintenance_feasibility.ipynb` | Model 2 (maintenance risk): leakage audit, label reverse-engineering, honest models, per-component feasibility, official recall data |

## Source modules (`src/`)

`config.py` (paths) · `download_datasets.py` · `mileage_data.py` (loaders + cleaning) · `mileage_experiments.py` (pipelines/metrics) ·
`israel_registry.py` (he→en normalisation, research only) · `sample_gov_registry.py` · `fetch_recalls.py`
