"""Loads the models once (start-up) and shares them.

  * mileage       - Model 1 as Smart_Car_Models.pdf specifies (Kaggle Datasets 7 + 8 + 3), with the CBS calibration;
  * failure_risk  - Model 2 as Smart_Car_Models.pdf specifies (Kaggle Datasets 1 + 4, and 5 for electric / hybrid vehicles);
  * risk          - the comparison model trained on REAL inspection outcomes (UK MOT, validated on Dutch RDW), kept as an additional panel.
"""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import settings
from app.ml.risk import RiskModel
from app.ml.spec_mileage import SpecMileageModel
from app.ml.spec_risk import SpecRiskModel


@dataclass(frozen=True)
class Models:
    mileage: SpecMileageModel
    failure_risk: SpecRiskModel
    risk: RiskModel


@lru_cache(maxsize=1)
def get_models(artifact_dir: str | None = None) -> Models:
    path = Path(artifact_dir) if artifact_dir else settings.ml_artifacts_dir
    return Models(mileage=SpecMileageModel(path), failure_risk=SpecRiskModel(path), risk=RiskModel(path))
