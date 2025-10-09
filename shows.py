
import os
import base64
from textwrap import indent

from config_loader import load_config
import prepare_dataset
from convert_dataset import convert_dataset
from SetupProcess import Setup, F
from secure_search import prepare_query_plan, combine_csp_responses, decrypt_matches
from verification import verify_fx_hmac
from GBF import fingerprint

def bytes_xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))

def hash_positions(item: str, size: int, k: int):
    import hashlib
    h1 = int(hashlib.sha256(item.encode("utf-8")).hexdigest(), 16)
    h2 = int(hashlib.md5(item.encode("utf-8")).hexdigest(), 16)
    return [(h1 + i * h2) % size for i in range(k)]

def simulate_csp(aui, payload):
    lam = int(aui["security_param"])
    byte_len = int(aui["segment_length"])
    n = len(aui["ids"])
    result_shares = []
    proof_shares = []
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
        result_shares.append([base64.b64encode(v).decode() for v in vec])
        proof_shares.append(base64.b64encode(proof).decode())
    return {"result_shares": result_shares, "proof_shares": proof_shares}

def show_bytes(label, data):
    print(label)
    for idx, (col_idx, blob) in enumerate(data):
        print(f"  column {col_idx:>3}: {blob.hex()}")

cfg_path = "conFig.ini"
csv_path = "us-colleges-and-universities.csv"
cfg = load_config(cfg_path)
dict_list = prepare_dataset.load_and_transform(csv_path)
db = convert_dataset(dict_list, cfg)
aui, keys = Setup(db, cfg)

query = "ORLANDO UNIVERSITY; R: 28.2,-81.6,28.8,-81.1"
print(f"Query: {query}\n")
plan = prepare_query_plan(query, aui, cfg)
print(f"Tokens: {[t for _, t in plan.tokens]}\n")

kw_token_idx = 0
kw_token = plan.tokens[kw_token_idx][1]
m2 = int(aui["m2"])
k_tex = int(aui.get("k_tex", 4))
kw_positions = hash_positions(kw_token, m2, k_tex)

responses = [
    simulate_csp(aui, plan.payloads[party_id])
    for party_id in range(plan.num_parties)
]

combined_vecs, combined_proofs = combine_csp_responses(plan, responses, aui)
match_mask, hits = decrypt_matches(plan, combined_vecs, aui, keys)
first_obj_idx = next((idx for idx, ok in enumerate(match_mask) if ok), 0)

Ke, Kv, Kh = keys
byte_len = int(aui["segment_length"])
total_len = (int(aui["m1"]) + m2) * byte_len
pad_bytes = F(Ke, (str(first_obj_idx + 1) + str(aui["ids"][first_obj_idx])).encode(), total_len)

plain_segments = []
cipher_segments = []
for col in kw_positions:
    plain = db[first_obj_idx].keyword_gbf.array[col]
    enc = aui["I_tex"]["EbW"][first_obj_idx][col]
    pad = pad_bytes[(int(aui["m1"]) + col) * byte_len : (int(aui["m1"]) + col + 1) * byte_len]
    plain_segments.append((col, plain))
    cipher_segments.append((col, enc))

show_bytes("Step 1) Plain GBF segments (per hashed column)", plain_segments)
rebuilt = []
for col, plain in plain_segments:
    pad = pad_bytes[(int(aui["m1"]) + col) * byte_len : (int(aui["m1"]) + col + 1) * byte_len]
    rebuilt.append((col, bytes_xor(plain, pad)))
show_bytes("\nStep 2) XOR with per-object pad (should give ciphertext columns)", rebuilt)

show_bytes("\nStep 3) Stored ciphertext columns (I_tex)", cipher_segments)

print("\nStep 4) CSP shares (each party returns XOR share + proof)")
for party_id, resp in enumerate(responses):
    print(f"\n  CSP {party_id}:")
    token_share = base64.b64decode(resp["result_shares"][kw_token_idx][first_obj_idx])
    token_share_hex = token_share.hex()
    print(f"    share (hex, first token, object {aui['ids'][first_obj_idx]}): {token_share_hex}")

combined_hex = combined_vecs[kw_token_idx][first_obj_idx].hex()
print(f"\nStep 5) Combined ciphertext (XOR of CSP shares): {combined_hex}")

ok_verify = verify_fx_hmac(query, aui, keys, combined_vecs, combined_proofs, [tok for _, tok in plan.tokens])
print(f"\nStep 6) Decrypt + verify -> hits: {len(hits)}, verification: {'pass' if ok_verify else 'fail'}")
print(f"Matching IDs: {hits[:5]}")
