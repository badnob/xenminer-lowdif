# Changelog — xenminer-lowdif

Format: keep newest first. Bump `core/version.py` + `VERSION` together.

## 3.1.2 — 2026-07-30

- Wallet balances: retries + multi-RPC fallback; partial results when ERC-20
  `eth_call` times out (no more whole panel stuck on “RPC unavailable”)
- `wallet_rpc_url` in miner.ini (comma-separated)

## 3.1.1 — 2026-07-30

- Sequential multi-prefix VRAM fill + default max_lanes=8

## 3.1.0 — 2026-07-30

Low-difficulty harvest fork baseline (beyond stock 3.0.0).

## 3.0.0

Upstream Tony.x1 / xnminer baseline label (pre-lowdif feature train).
