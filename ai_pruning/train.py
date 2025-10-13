"""Train a LightGBM model for client-side pruning."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

try:
    import lightgbm as lgb
except ImportError as exc:  # pragma: no cover
    raise ImportError("LightGBM is required to train the pruning model") from exc

from .features import build_feature_vector

DATA_PATH = Path("ai_pruning/pruning_dataset.json")
MODEL_PATH = Path("ai_pruning/model.txt")


def load_dataset(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = json.loads(path.read_text(encoding="utf-8"))
    features: list[list[float]] = []
    labels: list[int] = []
    for item in data:
        cell_id = item.get("cell_id")
        if not cell_id:
            cell_tokens = item.get("cell_tokens", [])
            if not cell_tokens:
                continue
            cell_id = cell_tokens[0]
        kw_tokens = item.get("keyword_tokens", [])
        extras = item.get("extras", {})
        features.append(build_feature_vector(cell_id, kw_tokens, extras))
        labels.append(int(item.get("hit", 0)))
    if not features:
        raise ValueError("Dataset is empty; build pruning dataset first")
    return np.array(features, dtype=float), np.array(labels, dtype=int)


def train() -> None:
    X, y = load_dataset(DATA_PATH)
    dataset = lgb.Dataset(X, label=y)
    params = {
        "objective": "binary",
        "metric": "auc",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "feature_fraction": 0.9,
        "seed": 42,
        "verbosity": -1,
    }
    booster = lgb.train(params, dataset, num_boost_round=200)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(MODEL_PATH))
    print(f"Model trained and saved to {MODEL_PATH}")


if __name__ == "__main__":
    train()
