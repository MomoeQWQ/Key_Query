import sys
import math
import pandas as pd

import prepare_dataset
from config_loader import load_config
from convert_dataset import convert_dataset
from SetupProcess import Setup
from SearchProcess import search_process
from verification import build_integrity_tags, verify_integrity, verify_fx_hmac
from QueryUtils import tokenize_normalized
from GBF import fingerprint


def combine_result_vectors(result_shares: dict):
    parties = sorted(result_shares.keys())
    if not parties:
        return []
    num_blocks = len(result_shares[parties[0]])
    combined = []
    for i in range(num_blocks):
        vec = None
        for l in parties:
            if vec is None:
                vec = list(result_shares[l][i])
            else:
                vec = [bytes(x ^ y for x, y in zip(v1, v2)) for v1, v2 in zip(vec, result_shares[l][i])]
        combined.append(vec if vec is not None else [])
    return combined


def print_readable_results(raw_df: pd.DataFrame, matched_ids: list, limit: int = 20):
    if not matched_ids:
        print("No matches.")
        return
    view = raw_df[raw_df['IPEDSID'].astype(str).isin([str(x) for x in matched_ids])].head(limit)
    for idx, row in enumerate(view.to_dict('records'), 1):
        print(f"{idx}. [{row['IPEDSID']}] {row['NAME']} - {row['ADDRESS']}, {row['CITY']}, {row['STATE']}  ({row.get('Geo Point','')})")


def _hash_pos(item: str, size: int, k: int):
    import hashlib as _hh
    h1 = int(_hh.sha256(item.encode('utf-8')).hexdigest(), 16)
    h2 = int(_hh.md5(item.encode('utf-8')).hexdigest(), 16)
    return [(h1 + i * h2) % size for i in range(k)]


def main():
    cfg = load_config("conFig.ini")
    csv_file = "us-colleges-and-universities.csv"
    dict_list = prepare_dataset.load_and_transform(csv_file)
    DB = convert_dataset(dict_list, cfg)
    raw_df = pd.read_csv(csv_file, sep=';')

    AUI, K = Setup(DB, cfg)
    print("[OK] Built AUI and secret keys.")

    tags = build_integrity_tags(AUI, K)
    ok = verify_integrity(AUI, K, tags)
    print(f"[OK] Index integrity: {'pass' if ok else 'fail'}")

    query_in = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Enter query (e.g., 'ORLANDO' or 'ORLANDO; R: lat_min,lon_min,lat_max,lon_max'): ")
    tokens_kw = tokenize_normalized(query_in)

    # Parse range into spatial cells
    spa_cells = []
    try:
        if 'R:' in query_in:
            head, rng = query_in.split('R:', 1)
            parts = rng.replace(';', ' ').replace(',', ' ').split()
            if len(parts) >= 4:
                lat_min, lon_min, lat_max, lon_max = map(float, parts[:4])
                lat_step = float(cfg.get('spatial_grid', {}).get('cell_size_lat', 0.5))
                lon_step = float(cfg.get('spatial_grid', {}).get('cell_size_lon', 0.5))
                r0 = math.floor(lat_min / lat_step)
                r1 = math.floor(lat_max / lat_step)
                c0 = math.floor(lon_min / lon_step)
                c1 = math.floor(lon_max / lon_step)
                for r in range(min(r0, r1), max(r0, r1) + 1):
                    for c in range(min(c0, c1), max(c0, c1) + 1):
                        spa_cells.append(f"CELL:R{r}_C{c}")
    except Exception:
        spa_cells = []

    result_shares, proof_shares = search_process(query_in, AUI, suppression=cfg.get("suppression", {}), spa_cells=spa_cells)
    final_vectors = combine_result_vectors(result_shares)
    print(f"[OK] Blocks: {len(final_vectors)}; per-party lengths: {{ {', '.join(str(k)+': '+str([len(v_i) for v_i in v]) for k, v in result_shares.items())} }}")

    Ke, Kv, Kh = K
    m1 = AUI['m1']
    m2 = AUI['m2']
    psi = AUI['segment_length'] * 8
    byte_len = AUI['segment_length']
    ids = AUI.get('ids', [])
    n = len(ids)

    # Decrypt keywords
    tokens_kw = tokens_kw or [query_in]
    k_tex = AUI.get('k_tex', 4)
    token_indices_kw = [_hash_pos(tok, m2, k_tex) for tok in tokens_kw]

    def one_time_pad_for_obj(idx1, obj_id):
        total_len = (m1 + m2) * byte_len
        from SetupProcess import F
        return F(Ke, (str(idx1) + str(obj_id)).encode('utf-8'), total_len)

    decrypted_vectors = []
    token_match = [[False] * n for _ in tokens_kw]
    for t_i, tok in enumerate(tokens_kw):
        indices = token_indices_kw[t_i]
        fp = fingerprint(tok, psi)
        per_vec = []
        for row_idx, obj_id in enumerate(ids, start=1):
            enc_vec = final_vectors[t_i][row_idx - 1]
            pad = one_time_pad_for_obj(row_idx, obj_id)
            pad_acc = b"\x00" * byte_len
            for j in indices:
                start = (m1 + j) * byte_len
                pad_acc = bytes(a ^ b for a, b in zip(pad_acc, pad[start:start + byte_len]))
            plain = bytes(a ^ b for a, b in zip(enc_vec, pad_acc))
            token_match[t_i][row_idx - 1] = (plain == fp)
            per_vec.append(plain)
        decrypted_vectors.append(per_vec)

    kw_ok = [all(token_match[t_i][r] for t_i in range(len(tokens_kw))) for r in range(n)] if tokens_kw else [True] * n

    # Decrypt spatial cells (OR)
    tokens_spa = spa_cells
    if tokens_spa:
        start_idx = len(tokens_kw)
        k_spa = AUI.get('k_spa', 3)
        token_indices_spa = [_hash_pos(cell, m1, k_spa) for cell in tokens_spa]
        for s_i, cell in enumerate(tokens_spa):
            indices = token_indices_spa[s_i]
            fp = fingerprint(cell, psi)
            per_vec = []
            for row_idx, obj_id in enumerate(ids, start=1):
                enc_vec = final_vectors[start_idx + s_i][row_idx - 1]
                pad = one_time_pad_for_obj(row_idx, obj_id)
                pad_acc = b"\x00" * byte_len
                for j in indices:
                    start = (m1 + j) * byte_len
                    pad_acc = bytes(a ^ b for a, b in zip(pad_acc, pad[start:start + byte_len]))
                plain = bytes(a ^ b for a, b in zip(enc_vec, pad_acc))
                per_vec.append(plain)
            decrypted_vectors.append(per_vec)
        spa_ok = [False] * n
        for s_i, cell in enumerate(tokens_spa):
            fp = fingerprint(cell, psi)
            vec_idx = start_idx + s_i
            for r in range(n):
                if decrypted_vectors[vec_idx][r] == fp:
                    spa_ok[r] = True
    else:
        spa_ok = [True] * n

    match_flags = [kw_ok[r] and spa_ok[r] for r in range(n)]
    matched_ids = [ids[i] for i, flag in enumerate(match_flags) if flag]
    print(f"[OK] Matches: {len(matched_ids)}")
    print_readable_results(raw_df, matched_ids)

    # Combine proofs across parties
    parties = sorted(proof_shares.keys())
    combined_proofs = []
    for i in range(len(proof_shares[parties[0]])):
        p = proof_shares[parties[0]][i]
        for l in parties[1:]:
            p = bytes(a ^ b for a, b in zip(p, proof_shares[l][i]))
        combined_proofs.append(p)

    tokens_all = tokens_kw + tokens_spa
    ok2 = verify_fx_hmac(query_in, AUI, K, decrypted_vectors, combined_proofs, tokens_override=tokens_all)
    print(f"[OK] Proof verification (FX+HMAC): {'pass' if ok2 else 'fail'}")


if __name__ == "__main__":
    main()

