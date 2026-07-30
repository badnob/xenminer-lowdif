## [3.2.3] - Woodyminer wallet totals
- Pull XNM / XUNI / XBLK balances from RPC (wallet_balances)
- Submit to woodyminer.com payload as xnm/xuni/xblk + totalXNM/totalXUNI/totalXBLK
- Enables https://woodyminer.com/stat/total/ and sub-categories (hashrate, by blocks, by superblocks, by machines)
- On-chain holdings persist across restarts (no longer zero)
- Wire automatically when woodyminer_enabled=true and wallet RPC configured

## 3.2.2 — 2026-07-30

- Startup robustness: power boost moved after CUDA alloc (heavy work first)
- Guarded power apply and CUDA start() so one failure does not hard-crash the miner
- Lightened “Connecting to pool…” wait loop (no full UI refresh on every tick)
- Guarded GPU snapshot() in main loop
- Clearer status during long CUDA first-batch alloc (“can take 15-60s on 5090”)
- Wallet label clarified as “fetching balances (background)…” so it does not look like the whole miner is stuck
- Non-blocking poller + fallback already in prior revs

These changes target the “hanging on warming up / fetching / connecting” reports (especially when xenblocks.io is unreachable).

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
