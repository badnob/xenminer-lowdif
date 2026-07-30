# Changelog — xenminer-lowdif

Format: keep newest first. Bump `core/version.py` + `VERSION` together.

## 3.1.1 — 2026-07-30

- **Sequential multi-prefix VRAM fill**: when lanes run one-at-a-time (Win11 default, no DLL copies / no native multi-lane), each lane gets the **full** batch budget so NVML used approaches target. Previously the planner assumed parallel VRAM (`lanes × batch`) and left most of the card idle (~9 GiB at dif 100).
- Default `max_lanes` raised to **8** for low-dif key coverage under sequential mode.

## 3.1.0 — 2026-07-30

Low-difficulty harvest fork baseline (beyond stock 3.0.0):

- Dense lane pack (`lane_pack_mode=fill`) + live thermal lane derate
- Multi-sensor temps; separate **die** vs **board** caps (board max 90)
- Win11 multi-lane: no crash on DLL copies; sequential fallback; daily-driver defaults
- VRAM: account for desktop/background used; **soft derate** when over target (keep mining)
- Difficulty RPC: stricter parse; logs clarify Argon2 `m=` must match pool
- Session timelapse sparkline rewrite (no carry-forward plateaus)
- Central version module (`core/version.py`)

## 3.0.0

Upstream Tony.x1 / xnminer baseline label (pre-lowdif feature train).
