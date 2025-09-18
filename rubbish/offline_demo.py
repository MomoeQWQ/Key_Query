import sys
import pandas as pd

import prepare_dataset
from config_loader import load_config
from convert_dataset import convert_dataset
from SetupProcess import Setup
from SearchProcess import search_process
from verification import build_integrity_tags, verify_integrity, verify_fx_hmac
from verify_query import verify_demo
from QueryUtils import tokenize_normalized


def combine_result_vectors(result_shares: dict):
    """XOR-combine per-party object-level vectors for each query block."""
    parties = sorted(result_shares.keys())
    if not parties:
        return []
    num_blocks = len(result_shares[parties[0]])
    combined = []
    for i in range(num_blocks):
        vec = None  # list[bytes] per object
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
        print(
            f"{idx}. [{row['IPEDSID']}] {row['NAME']} - "
            f"{row['ADDRESS']}, {row['CITY']}, {row['STATE']}  (" 
            f"{row.get('Geo Point', '')})"
        )


def main():
    # 1) Load config
    cfg = load_config("conFig.ini")

    # 2) Load dataset and build index
    csv_file = "us-colleges-and-universities.csv"
    dict_list = prepare_dataset.load_and_transform(csv_file)
    DB = convert_dataset(dict_list, cfg)
    raw_df = pd.read_csv(csv_file, sep=';')

    AUI, K = Setup(DB, cfg)
    print("[OK] Built AUI and secret keys.")

    # 3) Integrity check for outsourced index (offline)
    tags = build_integrity_tags(AUI, K)
    ok = verify_integrity(AUI, K, tags)
    print(f"[OK] Index integrity: {'pass' if ok else 'fail'}")

    # 4) Query input
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Enter query: ")
    norm_tokens = tokenize_normalized(query)

    # 5) Run search with suppression settings
    result_shares, proof_shares = search_process(query, AUI, suppression=cfg.get("suppression", {}))
    final_vectors = combine_result_vectors(result_shares)
    print(
        f"[OK] Blocks: {len(final_vectors)}; per-party lengths: "
        f"{ {k: [len(v_i) for v_i in v] for k, v in result_shares.items()} }"
    )

    # 6) Decrypt and match per-token using GBF fingerprint (AND semantics)
    from GBF import fingerprint
    Ke, Kv, Kh = K
    m1 = AUI['m1']
    m2 = AUI['m2']
    psi = AUI['segment_length'] * 8
    byte_len = AUI['segment_length']
    ids = AUI.get('ids', [])

    tokens = norm_tokens or [query]

    # 预先重建每个 token 的选择列索�?    import hashlib as _hh
    def _hash_pos(item: str, size: int, k: int):
        h1 = int(_hh.sha256(item.encode('utf-8')).hexdigest(), 16)
        h2 = int(_hh.md5(item.encode('utf-8')).hexdigest(), 16)
        return [(h1 + i * h2) % size for i in range(k)]
    k_tex = AUI.get('k_tex', 4)
    token_indices = [ _hash_pos(tok, m2, k_tex) for tok in tokens ]

    # 计算每个对象、每�?token 的解密后向量，并与指纹对比，同时收集解密后的向量供严�?Verify 使用
    decrypted_vectors = []  # list[token] -> list[bytes per object]
    def one_time_pad_for_obj(idx1, obj_id):
        total_len = (m1 + m2) * byte_len
        from SetupProcess import F
        return F(Ke, (str(idx1) + str(obj_id)).encode('utf-8'), total_len)

    n = len(ids)
    token_match = [ [False]*n for _ in tokens ]
    # final_vectors: per-token combined encrypted vec per object
    for t_i, tok in enumerate(tokens):
        indices = token_indices[t_i]
        fp = fingerprint(tok, psi)
        per_token_vec = []
        for row_idx, obj_id in enumerate(ids, start=1):
            enc_vec = final_vectors[t_i][row_idx-1]
            pad = one_time_pad_for_obj(row_idx, obj_id)
            # 累计关键�?pad：位�?pad �?(m1 + j) �?            pad_acc = b"\x00" * byte_len
            for j in indices:
                start = (m1 + j) * byte_len
                pad_acc = bytes(a ^ b for a, b in zip(pad_acc, pad[start:start+byte_len]))
            plain = bytes(a ^ b for a, b in zip(enc_vec, pad_acc))
            token_match[t_i][row_idx-1] = (plain == fp)
            per_token_vec.append(plain)
        decrypted_vectors.append(per_token_vec)

    # AND 所�?token
    match_flags = [ all(token_match[t_i][r] for t_i in range(len(tokens))) for r in range(n) ]
    matched_ids = [ids[i] for i, flag in enumerate(match_flags) if flag]
    print(f"[OK] Matches: {len(matched_ids)}")
    print_readable_results(raw_df, matched_ids)

    # 7) Strict Verify: FX(Ki, ·) + HMAC 等式
    # Combine proofs across parties
    parties = sorted(proof_shares.keys())
    combined_proofs = []
    for i in range(len(proof_shares[parties[0]])):
        p = proof_shares[parties[0]][i]
        for l in parties[1:]:
            p = bytes(a ^ b for a, b in zip(p, proof_shares[l][i]))
        combined_proofs.append(p)
    ok2 = verify_fx_hmac(query, AUI, K, decrypted_vectors, combined_proofs)
    print(f"[OK] Proof verification (FX+HMAC): {'pass' if ok2 else 'fail'}")

    # 8) 自检：直接对若干对象用本�?GBF 查询（不走密态），应和规范化 token 一�?    try:
        from convert_dataset import SpatioTextualRecord  # type: ignore
        if norm_tokens:
            tok0 = norm_tokens[0]
            # 抽样�?20 个对象在本地 GBF 上判�?            sample_ok = 0
            total = min(20, len(DB))
            first_idx = None
            for obj in DB[:total]:
                if obj.keyword_gbf.query(tok0):
                    sample_ok += 1
                    if first_idx is None:
                        first_idx = DB.index(obj)
            print(f"[OK] Self-check (local GBF) for token '{tok0}': {sample_ok}/{total} matched locally")
            # 进一步比对第一条本地命中对象在密态路径的解密是否等于指纹
            if first_idx is not None:
                i = first_idx
                # 查找 final_vectors 对应 token 的加密聚合向�?                if final_vectors:
                    enc_vec = final_vectors[0][i]
                    from GBF import fingerprint
                    fp = fingerprint(tok0, psi)
                    # 计算对应对象 pad_acc
                    def one_time_pad_for_obj(idx1, obj_id):
                        total_len = (m1 + m2) * byte_len
                        from SetupProcess import F
                        return F(Ke, (str(idx1) + str(obj_id)).encode('utf-8'), total_len)
                    pad = one_time_pad_for_obj(i+1, ids[i])
                    pad_acc = b"\x00" * byte_len
                    for j in token_indices[0]:
                        start = (m1 + j) * byte_len
                        pad_acc = bytes(a ^ b for a, b in zip(pad_acc, pad[start:start+byte_len]))
                    plain = bytes(a ^ b for a, b in zip(enc_vec, pad_acc))
                    ok_plain = (plain == fp)
                    print(f"[DBG] First-local-match decrypt-ok: {ok_plain}")
    except Exception as e:
        print(f"[WARN] Self-check skipped: {e}")


if __name__ == "__main__":
    main()
