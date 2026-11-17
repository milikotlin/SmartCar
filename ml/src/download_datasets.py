"""Download the Kaggle datasets used in Sprint 3 (public, no credentials needed).

Usage:  python -I ml/src/download_datasets.py [dataset_key ...]
Each dataset is extracted into its own empty directory under RAW_DIR.
"""
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import KAGGLE_DATASETS, RAW_DIR  # noqa: E402


def download(key: str) -> None:
    dest = RAW_DIR / key
    if dest.exists() and any(dest.iterdir()):
        print(f"[skip] {key}: already present in {dest}")
        return
    dest.mkdir(parents=True, exist_ok=True)
    url = f"https://www.kaggle.com/api/v1/datasets/download/{KAGGLE_DATASETS[key]}"
    zip_path = RAW_DIR / f"{key}.zip"
    print(f"[download] {key} <- {url}")
    urllib.request.urlretrieve(url, zip_path)
    with zipfile.ZipFile(zip_path) as zf:  # ZipFile.extractall sanitizes absolute/.. paths
        zf.extractall(dest)
    zip_path.unlink()
    print(f"[ok] {key}: {sorted(p.name for p in dest.iterdir())}")


if __name__ == "__main__":
    keys = sys.argv[1:] or list(KAGGLE_DATASETS)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for k in keys:
        download(k)
