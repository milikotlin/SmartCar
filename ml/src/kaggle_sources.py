"""Where the Kaggle datasets of SmartCar_Data.pdf / Smart_Car_Models.pdf come from: `kagglehub`, with the dataset handles of the PDF.

    import kagglehub
    path = kagglehub.dataset_download("adityadesai13/used-car-dataset-ford-and-mercedes")

kagglehub keeps a local cache (~/.cache/kagglehub), so each dataset is downloaded once. Public datasets download without an account, EXCEPT Dataset 1
(Logistics), for which Kaggle answers 403 to anonymous requests: it needs Kaggle credentials (KAGGLE_USERNAME / KAGGLE_KEY, ~/.kaggle/kaggle.json, or
`kagglehub.login()`). Without them the copy downloaded from the same Kaggle page on 2026-11-17 (RAW_DIR/d1_logistics) is used, and the script says so.

Run:  ml/.venv/Scripts/python.exe -I -X utf8 ml/src/kaggle_sources.py      (downloads / checks every dataset the models use)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import RAW_DIR  # noqa: E402

# key -> (Kaggle handle from the PDF, folder of the earlier manual download used only as a fallback)
KAGGLE = {
    "d1_logistics": ("datasetengineer/logistics-vehicle-maintenance-history-data", "d1_logistics"),
    "d3_cardekho": ("manishkr1754/cardekho-used-car-data", "d3_cardekho"),
    "d4_telemetry": ("tejalaveti2306/vehicle-maintenance-telemetry-data", "d4_telemetry"),
    "d5_nev": ("ziya07/fault-prediction-and-optimization-in-nevs", "d5_nev_faults"),
    "d7_uk": ("adityadesai13/used-car-dataset-ford-and-mercedes", "d7_uk_cars"),
    "d8_in": ("avikasliwal/used-cars-price-prediction", "d8_used_cars_in"),
}
_cache: dict[str, Path] = {}
SOURCE: dict[str, str] = {}        # key -> "kagglehub" | "local copy (...)", recorded in the model cards


def dataset_dir(key: str) -> Path:
    """Folder holding the dataset's files, downloaded with kagglehub (falls back to the earlier Kaggle download only if kagglehub is refused)."""
    if key in _cache:
        return _cache[key]
    handle, local = KAGGLE[key]
    try:
        import kagglehub

        path = Path(kagglehub.dataset_download(handle))
        SOURCE[key] = f"kagglehub: {handle}"
    except Exception as exc:  # noqa: BLE001 - reported below, never silent
        fallback = RAW_DIR / local
        if not (fallback.exists() and any(fallback.iterdir())):
            raise RuntimeError(f"kagglehub could not download {handle} ({type(exc).__name__}) and no local copy exists in {fallback}. "
                               "Configure Kaggle credentials (kagglehub.login()) and run again.") from exc
        print(f"[kaggle] {handle}: kagglehub refused ({type(exc).__name__}: needs Kaggle credentials); using the earlier download from the same page: {fallback}", flush=True)
        path = fallback
        SOURCE[key] = f"local copy of {handle} (kagglehub needs credentials for this dataset)"
    _cache[key] = path
    return path


def find(key: str, filename: str) -> Path:
    """A file of the dataset by name, wherever it sits inside the downloaded folder."""
    root = dataset_dir(key)
    hits = sorted(root.rglob(filename))
    if not hits:
        raise FileNotFoundError(f"{filename} not found in {root}")
    return hits[0]


if __name__ == "__main__":
    for k in KAGGLE:
        d = dataset_dir(k)
        print(f"{k:13s} {SOURCE[k]}\n{'':13s} {d} -> {sorted(p.name for p in d.rglob('*.csv'))}")
