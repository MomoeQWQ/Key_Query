# Technical Documentation

## Overview

This document details the crypto design, algorithms, data flow and evolution of this project (VPBRQSupL-inspired spatio-textual secure search).

## Data Encoding

- Spatial and Keyword components are encoded via Garbled Bloom Filter (GBF).
- Keyword tokens: normalized (uppercase, alphanumeric only) and inserted individually.
- GBF parameters: size m, hash_count k, cell bit length psi (bytes = psi/8).

## Setup (Index Construction)

Let DB contain n objects with ids {id_i}.
- One-time pad: Ke. For object i, compute pad_i = F(Ke, (str(i)||id_i), (m1+m2)*bytes). Encrypt keyword matrix I_tex by per-column XOR with pad slices.
- Prefix-constrained PRF: choose prefix v; Kv = FC.Cons(K_main, v); Ki = FC.Eval(Kv, i).
- XOR-homomorphic PRF FX: for input bitstring u, FX(K,u) = XOR over bit indices where u_b=1 of PRF(K,b).
- Column tags (sigma): for each column j,
  sigma[j] = XOR_i FX(Ki, I[:,j]) XOR HMAC(Kh, (j+m1)||cat_ids).

The authenticated index packs encrypted matrices and sigma.

## Query (Keyword + Spatial paths)

- Normalize keyword tokens; for each token t compute GBF positions S(t).
- Spatial range R is discretized into grid cells (CELL:R{row}_C{col}); each cell is treated as a token with its own GBF S(cell).
- PRP-based Cuckoo hashing shrinks the DMPF domain per token:
  - Bucket S(t) using M ≈ load*|S| buckets and κ candidate buckets via PRP(ζ, ·) mapping.
  - For each bucket, run DMPF over the local domain (bucket size) and aggregate byte-wise XOR for result/proof.
  - XOR across buckets to obtain the token-level result/proof.
- Each party l returns, for every token (keywords + spatial):
  - result_share[token]: object-level vectors via byte-wise XOR of selected columns.
  - proof_share[token]: XOR of sigma[j] over selected columns.
- Client XORs shares to get combined vectors & proofs per token; AND across keywords; OR across spatial cells; final match is AND(keywords) ∩ OR(spatial).

## Decryption & Matching

- For token t and object i, compute pad_acc(i,t) by XORing pad_i slices at selected columns (keyword or spatial path).
- Plain vector: plain(i,t) = combined_vec(i,t) XOR pad_acc(i,t).
- Match if plain(i,t) equals GBF fingerprint of t; for multi-token query, apply AND across keywords, OR across spatial cells.

## Verification (Strict)

For each token t (keyword or spatial) with selection S(t), verify:

combined_proof(t) == XOR_i FX(Ki, plain(i,t)) XOR XOR_i FX(Ki, pad_acc(i,t)) XOR N_S,ID

where N_S,ID = XOR_{j in S(t)} HMAC(Kh, (j+m1)||cat_ids), and Ki = FC.Eval(Kv,i).

This proof is independent of dataset size (depends only on number of tokens and lambda).

## Suppression of Leakage

- Access pattern: DMPF across U parties; each party only sees shares.
- Search pattern: randomized DMPF shares; optional padding to a fixed number of tokens; optional result blinding (XOR masks that cancel on combine).

## Parameters & Trade-offs

- Larger m/k/psi reduce false positives but increase CPU & memory.
- Lambda controls PRF/HMAC output length.
- For Python demo, prefer small to moderate m2/psi for interactive latency.

## Evolution (Changelog)

- v0: Initial GBF, numeric DMPF, non-zero-as-match demo.
- v1: Integrity tags (HMAC columns), offline_demo skeleton.
- v2: Leakage suppression (padding/blinding) and cleanup.
- v3: Paper alignment (XOR path): DMPF bit-shares, byte-wise XOR aggregation, decrypt & fingerprint match.
- v4: Strict verification (FX(Ki,·)+HMAC); implemented XOR-homomorphic FX and full equality check.

## Extending to Spatial (Future)

- Build spatial GBF with its own m1/k1 and integrate similarly.
- For range queries, encode Gray code/bounds to GBF tokens or adopt PRP-based Cuckoo hashing as paper suggests, then reuse DMPF bit-shares and XOR aggregation.

## Notes

- The demo favors clarity over speed; production use should vectorize XOR and cache Ki/pad segments.
- Normalization must be identical for data and queries to avoid mismatches.
