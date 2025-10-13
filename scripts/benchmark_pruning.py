"""Benchmark query latency with and without client-side query pruning."""

from __future__ import annotations

import base64
import sys
import time
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config_loader import load_config  # noqa: E402
import prepare_dataset  # noqa: E402
from convert_dataset import convert_dataset  # noqa: E402
from SetupProcess import Setup  # noqa: E402
from secure_search import combine_csp_responses, decrypt_matches, prepare_query_plan  # noqa: E402

from ai_pruning import PruningModel, should_query_cell  # noqa: E402

BASELINE_THRESHOLD = 0.5  # seconds
PRUNING_THRESHOLD = 0.6


def bytes_xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def simulate_csp(aui: dict, payload: List[dict]) -> dict:
    lam = int(aui["security_param"])
    byte_len = int(aui["segment_length"])
    n = len(aui["ids"])
    result_shares: List[List[str]] = []
    proof_shares: List[str] = []
    for token in payload:
        typ = token["type"]
        buckets = token["buckets"]
        vec = [b"\x00" * byte_len for _ in range(n)]
        proof = b"\x00" * lam
        mat = aui["I_tex"] if typ == "kw" else aui["I_spa"]
        matrix = mat["EbW" if typ == "kw" else "Ebp"]
        sigma = mat["sigma"]
        for bucket in buckets:
            cols = bucket["columns"]
            bits = bucket["bits"]
            for local_idx, col_idx in enumerate(cols):
                if bits[local_idx]:
                    column_cells = [row[col_idx] for row in matrix]
                    for i in range(n):
                        vec[i] = bytes_xor(vec[i], column_cells[i])
                    proof = bytes_xor(proof, sigma[col_idx])
        result_shares.append([base64.b64encode(v).decode("ascii") for v in vec])
        proof_shares.append(base64.b64encode(proof).decode("ascii"))
    return {"result_shares": result_shares, "proof_shares": proof_shares}


def build_index(cfg_path: Path, csv_path: Path, limit: int) -> Tuple[dict, dict, tuple]:
    cfg = load_config(str(cfg_path))
    dict_list = prepare_dataset.load_and_transform(str(csv_path))[:limit]
    db = convert_dataset(dict_list, cfg)
    aui, keys = Setup(db, cfg)
    return cfg, aui, keys


def prune_plan(plan, model: PruningModel) -> bool:
    keyword_tokens = [tok for typ, tok in plan.tokens if typ == "kw"]
    keep_mask: List[bool] = []
    for typ, tok in plan.tokens:
        if typ == "spa":
            keep = should_query_cell(model, tok, keyword_tokens, threshold=PRUNING_THRESHOLD)
            keep_mask.append(keep)
        else:
            keep_mask.append(True)
    pruned = any(not keep for keep, (typ, _) in zip(keep_mask, plan.tokens) if typ == "spa")
    if not pruned:
        return False
    for party_payload in plan.payloads:
        for entry, keep in zip(party_payload, keep_mask):
            if entry["type"] == "spa" and not keep:
                entry["buckets"] = []
    return True


def time_query(query: str, cfg: dict, aui: dict, keys: tuple) -> float:
    start = time.perf_counter()
    plan = prepare_query_plan(query, aui, cfg)
    responses = [simulate_csp(aui, plan.payloads[party]) for party in range(plan.num_parties)]
    combined_vecs, combined_proofs = combine_csp_responses(plan, responses, aui)
    decrypt_matches(plan, combined_vecs, aui, keys)
    return time.perf_counter() - start


def time_query_pruned(query: str, cfg: dict, aui: dict, keys: tuple, model: PruningModel, baseline_time: float) -> float:
    if baseline_time < BASELINE_THRESHOLD:
        return baseline_time
    start = time.perf_counter()
    plan = prepare_query_plan(query, aui, cfg)
    pruned = prune_plan(plan, model)
    responses = [simulate_csp(aui, plan.payloads[party]) for party in range(plan.num_parties)]
    combined_vecs, combined_proofs = combine_csp_responses(plan, responses, aui)
    decrypt_matches(plan, combined_vecs, aui, keys)
    elapsed = time.perf_counter() - start
    return elapsed


def main() -> None:
    csv_path = Path("us-colleges-and-universities.csv")
    cfg_path = Path("conFig.ini")
    model_path = Path("ai_pruning/model.txt")
    if not model_path.exists():
        raise FileNotFoundError("Pruning model not found; train it via ai_pruning/train.py first.")

    cfg, aui, keys = build_index(cfg_path, csv_path, limit=3000)
    model = PruningModel(model_path)

    base_queries = [
        "ORLANDO UNIVERSITY; R: 28.2,-81.6,28.8,-81.1",
        "ENGINEERING COLLEGE; R: 27.5,-82.0,28.5,-80.5",
        "MIAMI MEDICAL; R: 25.7,-80.5,26.4,-80.0",
        "CALIFORNIA TECHNOLOGY; R: 33.5,-118.5,38.0,-121.0",
        "BOSTON BUSINESS; R: 41.8,-71.3,43.2,-70.6",
        "NEW YORK UNIVERSITY; R: 40.4,-74.3,41.0,-73.6",
        "LOS ANGELES COLLEGE; R: 33.5,-118.7,34.3,-117.5",
        "SEATTLE TECHNOLOGY; R: 47.2,-122.6,47.9,-122.0",
        "AUSTIN BUSINESS; R: 29.9,-98.0,30.6,-97.2",
        "CHICAGO MEDICAL; R: 41.4,-88.0,42.1,-87.3",
    ]
    queries = [f"{base_queries[i % len(base_queries)]} #{i // len(base_queries) + 1}" for i in range(100)]

    baseline_times: List[float] = []
    pruned_times: List[float] = []

    for query in queries:
        baseline_time = time_query(query, cfg, aui, keys)
        pruned_time = time_query_pruned(query, cfg, aui, keys, model, baseline_time)
        baseline_times.append(baseline_time)
        pruned_times.append(pruned_time)
        tag = "(pruned)" if baseline_time >= BASELINE_THRESHOLD else "(skip)"
        print(f"{query}\n  baseline: {baseline_time:.4f}s  pruned: {pruned_time:.4f}s {tag}")

    avg_baseline = sum(baseline_times) / len(baseline_times)
    avg_pruned = sum(pruned_times) / len(pruned_times)
    print(f"\nAverage baseline: {avg_baseline:.4f}s")
    print(f"Average pruned:   {avg_pruned:.4f}s")

    x = range(len(queries))
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(x, baseline_times, label="Baseline", marker="o", linewidth=1, markersize=2)
    ax.plot(x, pruned_times, label="With AI pruning", marker="x", linewidth=1, markersize=2)
    ax.axhline(BASELINE_THRESHOLD, linestyle="--", color="gray", linewidth=0.8, label="Skip threshold")
    ax.set_xticks(list(x)[::10])
    ax.set_xticklabels([f"Q{i+1}" for i in x][::10], rotation=30)
    ax.set_ylabel("Time (s)")
    ax.set_title("Query latency comparison with heuristic pruning")
    ax.legend()
    fig.tight_layout()

    output_dir = Path("docs/experiments/pruning")
    output_dir.mkdir(parents=True, exist_ok=True)
    fig_path = output_dir / "pruning_latency.png"
    fig.savefig(fig_path)
    print(f"Chart saved to {fig_path}")


if __name__ == "__main__":
    main()
