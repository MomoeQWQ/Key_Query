# Online Demo (Client + CSPs)

This minimal demo simulates a client and multiple CSP servers using the existing local project as a library. No changes are made to the core codebase.

## Steps

1) Prepare AUI and keys

```
python online_demo/owner_setup.py
```

This writes `online_demo/aui.pkl` and `online_demo/K.pkl`. Re-run this step after any changes to `SetupProcess.py` or `verification.py` that touch FX/HMAC logic.

2) Start CSP servers and run client

- Three CSP servers on ports 8001/8002/8003 are launched, then the client runs.

```
python online_demo/run_all.py "ORLANDO; R: 28.3,-81.5,28.7,-81.2"
```

Expect to see `[client] Verify: pass` on success; the client prints matching rows (up to 20).

or keywords only:

```
echo ORLANDO | python online_demo/run_all.py
```

## Design

- CSP servers (`csp_server.py`) load the pickled AUI and expose `/eval`. They aggregate selected columns per token and return per-party shares.
- The client (`client.py`) normalizes tokens, discretizes range into grid cells, performs PRP-based Cuckoo bucketing per token and generates small-domain DMPF shares, posts requests to U CSPs and XOR-combines the returned shares.
- The client then decrypts, matches GBF fingerprints (AND over keywords, OR over spatial cells) and runs strict FX+HMAC verification.

## Configuration

Uses `conFig.ini` for params:
- `spatial_grid.cell_size_lat/cell_size_lon` for grid size.
- `cuckoo.*` (kappa/load/seed) for PRP-based Cuckoo bucketing of keywords and spatial tokens.

## Notes

- This is a minimal prototype and uses Python http.server. For production, use TLS and a framework (FastAPI), add nonce and authentication, and vectorize XOR operations.
- The verification step relies on sigma computed from raw GBF columns; regenerate the pickles if keys or pad generation change.

