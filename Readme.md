# ST-VLS: Privacy-Preserving Spatio-Temporal Secure Search

ST-VLS (Spatio-Temporal Secure Search with Verifiable Leakage Suppression) is a research prototype that blends searchable encryption, distributed multi-party computation, and lightweight verification. It demonstrates how multiple cloud service providers (CSPs) can cooperatively answer encrypted spatio-textual queries while the client verifies correctness and suppresses query leakage. The implementation reflects the algorithms and experiments described in the accompanying technical report, including optional AI-assisted query expansion and pruning.

---

## Key Features

- **Authenticated encrypted index** - Garbled Bloom Filters (GBF) encode spatial and textual tokens; one-time pads and FX+HMAC tags protect integrity and confidentiality.
- **Leakage-suppressed querying** - PRP-based Cuckoo bucketing plus Distributed Multi-Point Function (DMPF) shares hide column selections from each CSP.
- **Client-side verification** - FX + HMAC proofs allow the querier to detect missing or tampered results with constant proof size.
- **AI-assisted expansion** - Optional large language model (LLM) pipeline enriches keyword queries while enforcing local truncation and masking to retain privacy.
- **Multiple demos** - Command-line, GUI, and evaluation scripts illustrate end-to-end flows from index construction to experimentation.

---

## Repository Layout

| Path | Description |
| --- | --- |
| `secure_search/` | Core package with indexing (`indexing.py`), query processing (`query.py`), verification helpers, GBF/DMPF primitives, and AI utilities (`query_expansion.py`, `expansion_client.py`, `pruning_client.py`). |
| `online_demo/` | Console-based end-to-end demo (owner setup, CSP servers, client). |
| `gui_demo/` | Tkinter GUI for launching CSP nodes and interactive client queries. |
| `docs/` | Technical documentation, experiment reports, plots, and bilingual write-ups. |
| `docs/experiments/` | Reproducible evaluation scripts (`performance_study.py`, etc.) plus generated metrics/figures. |
| `ai_pruning/` | LightGBM training and inference utilities for keyword pruning experiments. |
| `ai_clients/` | Optional LLM adapters (e.g., Google Gemini). |
| `scripts/` | Utility scripts for dataset prep, query expansion, pruning benchmarks, automation. |
| `GBF.py`, `DMPF.py`, `SetupProcess.py`, `verification.py`, `QueryUtils.py`, `convert_dataset.py` | Stand-alone primitives used by the package. |
| `conFig.ini` | Sample configuration for bloom filter sizes, suppression knobs, and CSP count. |
| `us-colleges-and-universities.csv` | Default public dataset used in demos. |

---

## Installation

1. **Environment** - Python 3.10+ is recommended.
2. **Core dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   If `requirements.txt` is unavailable, manually install the essentials:
   ```bash
   pip install pandas numpy matplotlib lightgbm
   ```
3. **Optional AI expansion** - For the Gemini client, install `google-generativeai` and export `GEMINI_API_KEY`. Other providers can be integrated via `secure_search/query_expansion.py`.
4. (Optional) create a virtual environment for isolation.

---

## Preparing Data & Index

1. Review `conFig.ini` to adjust bloom filter parameters, suppression padding, and CSP count (`U`).
2. Run the owner setup script to build encrypted artifacts:
   ```bash
   python online_demo/owner_setup.py --csv us-colleges-and-universities.csv --config conFig.ini --out online_demo
   ```
   The script produces `aui.pkl` (authenticated index) and `K.pkl` (keys). Re-run whenever you change the dataset, configuration, or setup logic.

---

## Running the Demos

### Offline Quick Tests

- **Keyword only**
  ```bash
  python offline_demo.py "ORLANDO"
  ```
- **Keyword + spatial range**
  ```bash
  python offline_demo_spatial.py "ORLANDO; R: 28.3,-81.5,28.7,-81.2"
  ```

### Online Multi-CSP Demo

Launch three CSP servers and the client in one shot (default ports 8001-8003):
```bash
python online_demo/run_all.py "ORLANDO; R: 28.3,-81.5,28.7,-81.2"
```
Send a query via stdin as well:
```bash
echo ORLANDO | python online_demo/run_all.py
```
To run servers and client separately: start `online_demo/csp_server.py` on each port with `--aui`/`--keys`, then invoke `online_demo/client.py` with endpoints and query text.

### GUI Workflow

1. Start the CSP GUI:
   ```bash
   python gui_demo/server_gui.py
   ```
   Load `aui.pkl`, choose ports, click **Start servers**.
2. Launch the client GUI:
   ```bash
   python gui_demo/client_gui.py
   ```
   Provide `aui.pkl`, `K.pkl`, `conFig.ini`, and (optionally) the CSV for plaintext inspection. Submit a query to view verification status and decrypted matches.

---

## API Usage

Use the `secure_search` package directly inside your applications:
```python
from config_loader import load_config
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

cfg = load_config("conFig.ini")
aui, keys = build_index_from_csv("us-colleges-and-universities.csv", "conFig.ini")
plan = prepare_query_plan("ORLANDO ENGINEERING", aui, cfg)
# or plan = prepare_query_plan_with_expansion(...)
```
`online_demo/client.py` shows how to serialise payloads, contact CSP endpoints, aggregate responses, and verify proofs.

---

## AI-Assisted Query Expansion & Pruning

- **Expansion** - `secure_search.expansion_client.prepare_query_plan_with_expansion` augments keyword lists using either an LLM (Gemini by default) or a local synonym table. Demo: `python scripts/demo_query_expansion.py`. Generated plots live under `docs/experiments/query_expansion/`.
- **Pruning** - `ai_pruning/` contains LightGBM models that estimate discriminative keywords; see `scripts/pruning_benchmark.py` for usage.
- Both modules honour the leakage-suppression policy: expanded tokens are truncated to the configured padding length before secret-sharing.

---

## Experiments & Evaluation

`docs/experiments/performance_study.py` reproduces the metrics cited in the technical report. It generates:
- `docs/experiments/metrics.json` — raw timing data.
- `docs/experiments/figures/` — plots for index scaling, query latency breakdown, and CSP scaling.

Additional evaluation assets (e.g., incremental hits for AI expansion) are stored under `docs/experiments/query_expansion/`.

---

## Configuration & Customisation

- Adjust `conFig.ini` to control bloom filter sizes (`m1`, `m2`, `psi`), hash counts (`k_spa`, `k_tex`), suppression knobs (padding length, dummy tokens), and CSP count (`U`).
- To support a different dataset, update `prepare_dataset.py` and `convert_dataset.py` so they emit the required `SpatioTextualRecord` structure.
- For production deployments add TLS, authentication, nonces, and vectorised XOR operations.

---

## License

MIT © Project contributors.

