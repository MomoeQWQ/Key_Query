"""Inference utilities for client-side pruning."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np

try:
    import lightgbm as lgb
except ImportError as exc:  # pragma: no cover
    raise ImportError("LightGBM is required for pruning inference") from exc

from .features import build_feature_vector


class PruningModel:
    """LightGBM-based pruning model loader."""

    def __init__(self, model_path: str | Path):
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Pruning model not found: {self.model_path}")
        self.booster = lgb.Booster(model_file=str(self.model_path))

    def predict_probability(
        self,
        cell_id: str,
        keyword_tokens: List[str],
        extras: Dict[str, float] | None = None,
    ) -> float:
        """Return probability that querying this cell yields results."""
        features = np.array([build_feature_vector(cell_id, keyword_tokens, extras)], dtype=float)
        score = self.booster.predict(features)
        return float(score[0])


def should_query_cell(
    model: PruningModel,
    cell_id: str,
    keyword_tokens: List[str],
    threshold: float = 0.2,
    extras: Dict[str, float] | None = None,
) -> bool:
    """Decide whether to keep the cell in the query plan."""
    prob = model.predict_probability(cell_id, keyword_tokens, extras)
    return prob >= threshold
