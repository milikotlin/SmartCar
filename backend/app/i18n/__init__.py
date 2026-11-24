"""Languages of the API (English = default, Hebrew). The pipeline (services/prediction.py and app/ml) always works in English; texts are translated AFTER the result exists,
so the language can never change a prediction, a level or an input of a model."""
from typing import Literal

Lang = Literal["en", "he"]
DEFAULT_LANG: Lang = "en"
