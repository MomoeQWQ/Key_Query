from __future__ import annotations

from typing import List

from .query import prepare_query_plan

try:
    from ai_pruning import PruningModel, should_query_cell
except ImportError:  # pragma: no cover
    PruningModel = None
    should_query_cell = None


def prepare_query_plan_with_pruning(query_text: str, aui: dict, config: dict, model_path: str | None = None):
    plan = prepare_query_plan(query_text, aui, config)
    if model_path is None or PruningModel is None:
        return plan

    model = PruningModel(model_path)
    keyword_tokens = [tok for typ, tok in plan.tokens if typ == "kw"]
    keep_mask: List[bool] = []
    for typ, tok in plan.tokens:
        keep_mask.append(True if typ != "spa" else should_query_cell(model, tok, keyword_tokens))

    expected_len = len(plan.tokens)
    for party_payload in plan.payloads:
        if len(party_payload) != expected_len:
            raise ValueError("party payload length mismatch")
        for entry, keep in zip(party_payload, keep_mask):
            if entry["type"] == "spa" and not keep:
                entry["buckets"] = []
    return plan
