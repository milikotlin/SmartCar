"""Loads both models once (start-up) and shares them."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import settings
from app.ml.mileage import MileageModel
from app.ml.risk import RiskModel


@dataclass(frozen=True)
class Models:
    mileage: MileageModel
    risk: RiskModel


@lru_cache(maxsize=1)
def get_models(artifact_dir: str | None = None) -> Models:
    path = Path(artifact_dir) if artifact_dir else settings.ml_artifacts_dir
    return Models(mileage=MileageModel(path), risk=RiskModel(path))
