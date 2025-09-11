import argparse
import base64
import json
import math
import os
import sys
import pickle
import urllib.request

# Ensure project root on sys.path
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..'))
if PROJ_ROOT not in sys.path:
    sys.path.insert(0, PROJ_ROOT)

from config_loader import load_config  # noqa: E402
from verification import verify_fx_hmac  # noqa: E402
from QueryUtils import tokenize_normalized  # noqa: E402
from GBF import fingerprint  # noqa: E402


def _hash_pos(item: str, size: int, k: int):
    import hashlib as _hh
    h1 = int(_hh.sha256(item.encode('utf-8')).hexdigest(), 16)
    h2 = int(_hh.md5(item.encode('utf-8')).hexdigest(), 16)
    return [(h1 + i * h2) % size for i in range(k)]


def _prp(zeta: bytes, x: int) -> int:
    import hashlib
    return int(hashlib.sha256(zeta + x.to_bytes(8, 'big')).hexdigest(), 16)


def _cuckoo_bucketize(indices: list, m: int, kappa: int, M: int, zeta: bytes) -> dict:
    buckets = {b: [] for b in range(M)}
    for j in indices:
        cands = []
        for i in range(kappa):
            val = _prp(zeta, j + m * i)
            b = val % M
            cands.append(b)
        best = min(cands, key=lambda b: len(buckets[b]))
        buckets[best].append(j)
    return {b: lst for b, lst in buckets.items() if lst}


def http_post(url, obj):
    data = json.dumps(obj).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        body = resp.read()
        return json.loads(body.decode('utf-8'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csp', nargs='+', default=['http://127.0.0.1:8001', 'http://127.0.0.1:8002', 'http://127.0.0.1:8003'])
    ap.add_argument('--query', type=str, default=None)
    args = ap.parse_args()

    cfg = load_config(os.path.join(PROJ_ROOT, 'conFig.ini'))
    with open(os.path.join(THIS_DIR, 'aui.pkl'), 'rb') as f:
        aui = pickle.load(f)
    with open(os.path.join(THIS_DIR, 'K.pkl'), 'rb') as f:
        K = pickle.load(f)

    query_in = args.query or (sys.argv[1] if len(sys.argv) > 1 else input("Enter query (kw; optional R): "))
    tokens_kw = tokenize_normalized(query_in)
    # Parse R
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

    # Build per-party payloads via PRP+Cuckoo bucketing and local-domain DMPF bits
    U = int(aui['U'])
    lam = int(aui['security_param'])
    m1 = int(aui['m1'])
    m2 = int(aui['m2'])
    k_tex = int(aui.get('k_tex', 4))
    k_spa = int(aui.get('k_spa', 3))
    ck_kw = aui.get('cuckoo_kw', {"kappa": 3, "load": 1.27, "seed": "cuckoo-seed"})
    ck_spa = aui.get('cuckoo_spa', {"kappa": 3, "load": 1.27, "seed": "cuckoo-seed-spa"})

    from DMPF import Gen

    # Tokenize sequence: first keywords, then spatial cells
    tokens_all = [("kw", t) for t in (tokens_kw or [query_in])] + [("spa", c) for c in spa_cells]
    per_party_tokens = [[{"type": typ, "buckets": []} for (typ, _) in tokens_all] for _ in range(U)]

    for tok_idx, (typ, tok) in enumerate(tokens_all):
        if typ == 'kw':
            S = _hash_pos(tok, m2, k_tex)
            kappa = min(int(ck_kw.get('kappa', 3)), k_tex)
            load = float(ck_kw.get('load', 1.27))
            zeta = str(ck_kw.get('seed', 'cuckoo-seed')).encode('utf-8')
            m = m2
        else:
            S = _hash_pos(tok, m1, k_spa)
            kappa = min(int(ck_spa.get('kappa', 3)), k_spa)
            load = float(ck_spa.get('load', 1.27))
            zeta = str(ck_spa.get('seed', 'cuckoo-seed-spa')).encode('utf-8')
            m = m1
        buckets = _cuckoo_bucketize(S, m, kappa, max(1, int(math.ceil(load * max(1, len(S))))), zeta)
        for b_id, cols in buckets.items():
            domain = list(range(len(cols)))
            keys = Gen(lam, domain, len(domain), num_parties=U)
            for l in range(U):
                bits = [int(keys[l]['bits'].get(j, 0)) for j in domain]
                per_party_tokens[l][tok_idx]["buckets"].append({"columns": cols, "bits": bits})

    # Send to CSPs
    responses = []
    for l, base in enumerate(args.csp):
        body = {"party_id": l, "tokens": per_party_tokens[l], "security_param": lam}
        resp = http_post(base + '/eval', body)
        responses.append(resp)

    # Combine shares across parties
    def b64_to_bytes(s):
        return base64.b64decode(s.encode('utf-8'))

    # tokens dimension
    T = len(tokens_all)
    n = len(aui['ids'])
    byte_len = aui['segment_length']

    combined_vecs = []
    combined_proofs = []
    for t in range(T):
        vec = [b"\x00" * byte_len for _ in range(n)]
        proof = b"\x00" * lam
        for resp in responses:
            token_vecs = resp['result_shares'][t]
            token_proof = resp['proof_shares'][t]
            for i in range(n):
                vec[i] = bytes(x ^ y for x, y in zip(vec[i], b64_to_bytes(token_vecs[i])))
            proof = bytes(x ^ y for x, y in zip(proof, b64_to_bytes(token_proof)))
        combined_vecs.append(vec)
        combined_proofs.append(proof)

    # Decrypt and match
    Ke, Kv, Kh = K
    def pad_for_obj(idx1, obj_id):
        total_len = (m1 + m2) * byte_len
        from SetupProcess import F
        return F(Ke, (str(idx1) + str(obj_id)).encode('utf-8'), total_len)

    matches = [True] * n  # AND over keywords
    # decrypt keywords first
    for t_idx, (typ, tok) in enumerate(tokens_all):
        if typ != 'kw':
            continue
        S = _hash_pos(tok, m2, k_tex)
        fp = fingerprint(tok, aui['segment_length'] * 8)
        for row_idx, obj_id in enumerate(aui['ids'], start=1):
            enc_vec = combined_vecs[t_idx][row_idx - 1]
            pad = pad_for_obj(row_idx, obj_id)
            pad_acc = b"\x00" * byte_len
            for j in S:
                start = (m1 + j) * byte_len
                pad_acc = bytes(x ^ y for x, y in zip(pad_acc, pad[start:start + byte_len]))
            plain = bytes(x ^ y for x, y in zip(enc_vec, pad_acc))
            matches[row_idx - 1] &= (plain == fp)

    # spatial OR
    spa_ok = [False] * n if spa_cells else [True] * n
    if spa_cells:
        base_idx = len(tokens_kw or [query_in])
        for s_off, cell in enumerate(spa_cells):
            S = _hash_pos(cell, m1, k_spa)
            fp = fingerprint(cell, aui['segment_length'] * 8)
            t_idx = base_idx + s_off
            for row_idx, obj_id in enumerate(aui['ids'], start=1):
                enc_vec = combined_vecs[t_idx][row_idx - 1]
                pad = pad_for_obj(row_idx, obj_id)
                pad_acc = b"\x00" * byte_len
                for j in S:
                    start = j * byte_len  # spatial in keyword area? here spatial pad should be at bp part; spatial GBF mapped to first m1 segments
                    pad_acc = bytes(x ^ y for x, y in zip(pad_acc, pad[start:start + byte_len]))
                plain = bytes(x ^ y for x, y in zip(enc_vec, pad_acc))
                if plain == fp:
                    spa_ok[row_idx - 1] = True

    final_ok = [matches[i] and spa_ok[i] for i in range(n)]

    # Strict verify
    ok_verify = verify_fx_hmac(query_in, aui, K, combined_vecs, combined_proofs,
                               tokens_override=[t for _, t in tokens_all])
    print(f"[client] Verify: {'pass' if ok_verify else 'fail'}")

    # Print top 20
    import pandas as pd
    raw_df = pd.read_csv(os.path.join(PROJ_ROOT, 'us-colleges-and-universities.csv'), sep=';')
    hits = [aui['ids'][i] for i, ok in enumerate(final_ok) if ok]
    print(f"[client] Matches: {len(hits)}")
    view = raw_df[raw_df['IPEDSID'].astype(str).isin([str(x) for x in hits])].head(20)
    for idx, row in enumerate(view.to_dict('records'), 1):
        print(f"{idx}. [{row['IPEDSID']}] {row['NAME']} - {row['ADDRESS']}, {row['CITY']}, {row['STATE']}  ({row.get('Geo Point','')})")


if __name__ == '__main__':
    main()
