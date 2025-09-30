import argparse
import json
import os
import sys
import urllib.request

# Ensure project root on sys.path
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..'))
if PROJ_ROOT not in sys.path:
    sys.path.insert(0, PROJ_ROOT)

from config_loader import load_config
from secure_search import (
    prepare_query_plan,
    combine_csp_responses,
    decrypt_matches,
    run_fx_hmac_verification,
)
from secure_search.indexing import load_index_artifacts


def http_post(url: str, obj: dict) -> dict:
    data = json.dumps(obj).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        body = resp.read()
        return json.loads(body.decode('utf-8'))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--csp', nargs='+', default=['http://127.0.0.1:8001', 'http://127.0.0.1:8002', 'http://127.0.0.1:8003'])
    ap.add_argument('--query', type=str, default=None)
    ap.add_argument('--aui', type=str, default=os.path.join(THIS_DIR, 'aui.pkl'))
    ap.add_argument('--keys', type=str, default=os.path.join(THIS_DIR, 'K.pkl'))
    ap.add_argument('--config', type=str, default=os.path.join(PROJ_ROOT, 'conFig.ini'))
    args = ap.parse_args()

    cfg = load_config(args.config)
    aui, keys = load_index_artifacts(args.aui, args.keys)

    query_in = args.query or (sys.argv[1] if len(sys.argv) > 1 else input("Enter query (kw; optional R): "))
    plan = prepare_query_plan(query_in, aui, cfg)

    if len(args.csp) != plan.num_parties:
        raise ValueError(f"Expected {plan.num_parties} CSP endpoints, got {len(args.csp)}")

    responses = []
    for party_id, base in enumerate(args.csp):
        body = {
            'party_id': party_id,
            'tokens': plan.payloads[party_id],
            'security_param': plan.security_param,
        }
        responses.append(http_post(base + '/eval', body))

    combined_vecs, combined_proofs = combine_csp_responses(plan, responses, aui)
    _, hits = decrypt_matches(plan, combined_vecs, aui, keys)
    ok_verify = run_fx_hmac_verification(plan, combined_vecs, combined_proofs, aui, keys)
    print(f"[client] Verify: {'pass' if ok_verify else 'fail'}")
    print(f"[client] Matches: {len(hits)}")

    import pandas as pd

    raw_df = pd.read_csv(os.path.join(PROJ_ROOT, 'us-colleges-and-universities.csv'), sep=';')
    view = raw_df[raw_df['IPEDSID'].astype(str).isin([str(x) for x in hits])].head(20)
    for idx, row in enumerate(view.to_dict('records'), 1):
        print(f"{idx}. [{row['IPEDSID']}] {row['NAME']} - {row['ADDRESS']}, {row['CITY']}, {row['STATE']}  ({row.get('Geo Point', '')})")


if __name__ == '__main__':
    main()
