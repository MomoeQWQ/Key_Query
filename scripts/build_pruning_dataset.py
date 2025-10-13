"""Build a lightweight dataset for training the pruning model."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable

import base64
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config_loader import load_config
import prepare_dataset
from convert_dataset import convert_dataset
from SetupProcess import Setup
from secure_search import prepare_query_plan, combine_csp_responses, decrypt_matches

OUTPUT_PATH = Path("ai_pruning/pruning_dataset.json")
DATA_LIMIT = 3000
QUERIES = [
    "ORLANDO UNIVERSITY; R: 28.2,-81.6,28.8,-81.1",
    "ENGINEERING COLLEGE; R: 27.5,-82.0,28.5,-80.5",
    "MIAMI MEDICAL; R: 25.7,-80.5,26.4,-80.0",
    "CALIFORNIA TECHNOLOGY; R: 33.5,-118.5,38.0,-121.0",
    "BOSTON BUSINESS; R: 41.8,-71.3,43.2,-70.6",
]


def bytes_xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def simulate_csp(aui: dict, payload: list[dict]) -> dict:
    lam = int(aui["security_param"])
    byte_len = int(aui["segment_length"])
    n = len(aui["ids"])
    result_shares: list[list[str]] = []
    proof_shares: list[str] = []
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


def compute_cell_density(records: Iterable[prepare_dataset.dict]):
    counter: Counter[str] = Counter()
    for rec in records:
        cell_token = rec["keywords"].split()[0] if False else None  # placeholder
    # 实际在 convert_dataset 中才能得到 cell token，因此这里先返回空字典
    return {}


def main() -> None:
    cfg = load_config("conFig.ini")
    dict_list = prepare_dataset.load_and_transform("us-colleges-and-universities.csv")[:DATA_LIMIT]
    db = convert_dataset(dict_list, cfg)
    aui, keys = Setup(db, cfg)

    rows: list[dict] = []
    for query in QUERIES:
        print(f"Processing query: {query}")
        plan = prepare_query_plan(query, aui, cfg)
        responses = [simulate_csp(aui, plan.payloads[party_id]) for party_id in range(plan.num_parties)]
        combined_vecs, combined_proofs = combine_csp_responses(plan, responses, aui)
        match_mask, hits = decrypt_matches(plan, combined_vecs, aui, keys)
        any_hit = bool(hits)

        cell_tokens = [tok for typ, tok in plan.tokens if typ == "spa"]
        keyword_tokens = [tok for typ, tok in plan.tokens if typ == "kw"]

        for cell in cell_tokens or ["CELL:R0_C0"]:
            rows.append(
                {
                    "query": query,
                    "cell_id": cell,
                    "keyword_tokens": keyword_tokens,
                    "hit": 1 if any_hit else 0,
                }
            )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"Dataset written to {OUTPUT_PATH} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
