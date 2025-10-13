# Spatio-Textual Secure Search System (VPBRQSupL-inspired)

## Overview
Prototype implementation of a verifiable, leakage-suppressed spatial keyword search system inspired by the 2024 IEEE TIFS paper “Beyond Result Verification: Efficient Privacy-Preserving Spatial Keyword Query With Suppressed Leakage”. Data is encoded with Garbled Bloom Filters (GBF); queries rely on PRP-based Cuckoo hashing, Distributed Multi-Point Function (DMPF) shares, and FX+HMAC proofs so that multiple CSPs can answer encrypted queries while the client verifies correctness.

## Highlights
- **Encrypted index**: `SetupProcess` derives per-object one-time pads via `F(Ke, ·)` to encrypt spatial/textual GBF segments and builds column tags `sigma`.
- **Query privacy**: `secure_search.query` packages PRP-based Cuckoo bucketing + DMPF so CSPs only see randomised column selections and return XOR shares.
- **Lightweight verification**: `verification.verify_fx_hmac` combines `Kv → Ki` derived keys with HMAC so proof size stays independent of dataset size.
- **Modular package**: `secure_search` exposes indexing and query APIs for CLI demos, GUIs, or higher-level services.
- **GUI demos**: `gui_demo` provides Tkinter-based client/CSP launchers that mirror a basic C/S deployment.

## Repository Layout
- `secure_search/`
  - `indexing.py`: build/save/load authenticated index artifacts.
  - `query.py`: query planning, CSP response combination, decryption, FX+HMAC verification.
  - `pruning_client.py`, `query_expansion.py`, `expansion_client.py`: AI pruning & LLM expansion helpers.
- `online_demo/`: command-line CSP + client demo.
- `gui_demo/`: GUI wrappers for client and CSP.
- `ai_pruning/`: dataset construction, LightGBM training, and inference utilities for pruning experiments.
- `ai_clients/`: optional LLM wrappers (Gemini).
- `scripts/`: assorted utilities (index building, pruning benchmark, query expansion demo, etc.).
- Core primitives: `GBF.py`, `DMPF.py`, `SetupProcess.py`, `verification.py`, `QueryUtils.py`, `convert_dataset.py`.

## Setup
1. Python 3.10+
2. Install dependencies:
```
pip install pandas matplotlib lightgbm
```
3. Optional: for Gemini query expansion, also install `google-generativeai` and set `GEMINI_API_KEY`.

## Build the Index
```
python online_demo/owner_setup.py
```
Reads the CSV and writes `online_demo/aui.pkl` + `online_demo/K.pkl`. Re-run after changing `SetupProcess`, `verification`, or configuration.

## Command-Line Demos
- Offline keyword only:
```
python offline_demo.py "ORLANDO"
```
- Offline spatial + keyword:
```
python offline_demo_spatial.py "ORLANDO; R: 28.3,-81.5,28.7,-81.2"
```
- Online CSP + client (launch 3 CSPs then run client):
```
python online_demo/run_all.py "ORLANDO; R: 28.3,-81.5,28.7,-81.2"
```
Quick keyword test:
```
echo ORLANDO | python online_demo/run_all.py
```

## GUI Workflow
1. `python gui_demo/server_gui.py` – pick `aui.pkl`, configure ports (default 8001/8002/8003), click **Start servers**.
2. `python gui_demo/client_gui.py` – choose `aui.pkl`, `K.pkl`, `conFig.ini`, dataset CSV, enter endpoints and query, click **Run query** to view FX+HMAC verification and top matches.

## API Cheat Sheet
```
from secure_search import (
    build_index_from_csv,
    save_index_artifacts,
    load_index_artifacts,
    prepare_query_plan,
    prepare_query_plan_with_expansion,
    combine_csp_responses,
    decrypt_matches,
    run_fx_hmac_verification,
)
```
```
aui, keys = build_index_from_csv(csv_path, config_path)
plan = prepare_query_plan(query_text, aui, config)
combined_vecs, combined_proofs = combine_csp_responses(plan, responses, aui)
_, hits = decrypt_matches(plan, combined_vecs, aui, keys)
ok = run_fx_hmac_verification(plan, combined_vecs, combined_proofs, aui, keys)
```

## LLM-Assisted Query Expansion
- Use `secure_search.expansion_client.prepare_query_plan_with_expansion` to enrich keyword sets before running the secure protocol.
- Demo: `python scripts/demo_query_expansion.py`
  - Tries Google Gemini if `GEMINI_API_KEY` is set and `google-generativeai` is installed (`pip install google-generativeai`).
  - Falls back to a built-in synonym list when Gemini is unavailable.
- Customize prompts or swap in other LLM providers via `secure_search.query_expansion`.

## Notes
- Current demo uses Python `http.server`; production deployments should add TLS, authentication, nonces, and vectorised XOR operations.
- Modifying pad/key derivation logic requires rebuilding the index (re-run `owner_setup.py`).

## License
MIT

