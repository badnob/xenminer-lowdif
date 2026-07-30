# Low-difficulty harvest notes

## Goal

At very low network difficulty (e.g. 100), Argon2id memory per attempt is small.
Without multi-lane packing the GPU sits cool with high clocks but under-uses VRAM.
This fork fills a ~24 GiB VRAM target with **many parallel key-prefix lanes**, then
**pulls lanes back live** when difficulty or board temperature rises.

## Defaults (5090 FE ~32 GiB)

| Knob | Value | Why |
|------|-------|-----|
| `target_vram_mib` | 24576 | ~24 GiB used cap |
| `max_lanes` | 12 | dense harvest ceiling |
| `lane_pack_mode` | fill | pack by VRAM + min batch |
| `min_batch_per_lane` | 2048 | each lane still does real work |
| `warn_gpu_temp_c` / `max_gpu_temp_c` | **78 / 84** | **die** limits |
| `warn_board_temp_c` / `max_board_temp_c` | **85 / 90** | **board** limits (Tony: ~88 peak week) |
| `gpu_thermal_lane_enabled` | true | live lane shrink |
| `gpu_difficulty_lane_bias` | true | ease lanes toward reference |
| `gpu_power_min_pct` / full ratio | 65 / 1.5 | power eases sooner on high dif |

## Tuning

- **More lanes at dif 100:** lower `min_batch_per_lane` (e.g. 1024) and/or raise `max_lanes` (16).
- **Too hot / clocks drop:** lower `max_lanes`, raise `min_batch_per_lane`, or tighten warn/max temps.
- **DLL-copy overhead (old DLL without native multi-lane):** prefer `max_lanes` 6–8.
- **Legacy behaviour:** `lane_pack_mode = boost` (reference // difficulty only).

## Safety ladder

1. Separate **die** and **board** caps — stop if either hits max
2. Multi-sensor NVML when available; high-diff +°C proxy only if board sensor missing
3. Difficulty lane bias (as dif climbs toward reference)
4. Thermal batch scale (soft shrink near die or board warn)
5. Thermal lane cap (live drop lanes)
6. Power target ease (difficulty-aware NVML limit)
7. Hard temp stop + cooldown; optional persistent lane-cap reduction

**Board 90°C** is a hard ceiling (Tony measured ~88°C sustained). **Die** stays on a tighter band (default warn 78 / max 84).

## Files touched vs upstream

- `mining/vram_batch.py` — fill pack, `apply_lane_cap`, batch top-up
- `efficiency/thermal_policy.py` — `thermal_lane_cap`, `difficulty_lane_bias`
- `efficiency/cuda_lane_policy.py` — remove duplicate restore helper
- `mining/backends/cuda_native.py` — live thermal lanes + pack settings
- `core/supervisor.py` — poll thermal lanes with power/batch
- `config/settings.py` + `miner.ini.example` — new knobs / safer defaults
- tests for pack + thermal lanes
