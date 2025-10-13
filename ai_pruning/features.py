"""Feature helpers for AI-based query pruning."""

from __future__ import annotations

from typing import Dict, List


def parse_cell_id(cell_id: str) -> tuple[int, int]:
    """Parse a cell token like ``CELL:R56_C-164`` into integer indices."""
    try:
        prefix, rc = cell_id.split(":", 1)
        r_part, c_part = rc.split("_")
        row_idx = int(r_part.replace("R", ""))
        col_idx = int(c_part.replace("C", ""))
        return row_idx, col_idx
    except Exception:
        return 0, 0


def build_feature_vector(cell_id: str, keyword_tokens: List[str], extras: Dict[str, float] | None = None) -> list[float]:
    """Construct a simple feature vector for the pruning model."""
    row_idx, col_idx = parse_cell_id(cell_id)
    feature = [float(row_idx), float(col_idx), float(len(keyword_tokens))]
    if extras:
        for key in sorted(extras):
            feature.append(float(extras[key]))
    return feature
