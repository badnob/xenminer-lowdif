# XenBlocks Miner by Tony.x1 — **low-difficulty harvest fork** (`v3.1.0`)

Fork of [badnob/xnminer](https://github.com/badnob/xnminer) tuned for **dense multi-lane mining when network difficulty is low**, with **live thermal lane derate** so board temps stay safer when difficulty climbs.

**Version:** see [`VERSION`](VERSION) / [`CHANGELOG.md`](CHANGELOG.md) (single source: `core/version.py`).

| Item | Windows |
|------|---------|
| **Start** | `Start-Miner.bat` or `Start-Miner.ps1` |
| **CUDA library** | `native\build\bin\xen_cuda.dll` |
| **Build** | `.\native\build.ps1` |
| **Upstream** | https://github.com/badnob/xnminer |

**Beginner walkthrough:** [HOWTO.md](HOWTO.md)

> **Linux users:** use the separate repo → [xnminer-linux](https://github.com/badnob/xnminer-linux)

---

## Why this fork (low dif)

At **difficulty 100**, each Argon2id attempt uses far less VRAM than at reference (~1100). A single lane can leave most of a 24–32 GiB card idle. This fork:

1. **Packs many CUDA lanes** (default `max_lanes = 12`) so combined batch VRAM **fills your configured cap** (~24 GiB on a 5090 FE).
2. Uses **`lane_pack_mode = fill`** — pack as many lanes as VRAM allows while each keeps `min_batch_per_lane` (default 2048). Legacy `boost` (`ref // diff`) still available.
3. **Live thermal lane shrink** — as GPU temp approaches warn/max, lanes drop *immediately* (not only after a hard cooldown restart).
4. **Difficulty lane bias** — as difficulty climbs toward reference, lanes ease down before heat builds.
5. **Tighter defaults** — warn 68 °C / max 72 °C, faster power derate on rising difficulty (`full_ratio = 1.5`, min power 65%).

### Practical notes (5090 FE ~32 GiB)

| Diff | Typical behaviour (fill, max_lanes=12, target≈24 GiB) |
|------|--------------------------------------------------------|
| 100 | Dense multi-lane harvest (often 10–12 lanes) |
| 200–400 | Still multi-lane; pack thins as per-attempt memory grows |
| ≥ reference | Collapses to **1 lane**, full VRAM batch |
| Temp → warn | Batch soft-scale + **live lane drop** |
| Temp → max | Hard stop + cooldown; may persist lower lane cap |

More lanes at the same VRAM budget = more parallel key-prefix search. Hashrate gain depends on SM occupancy; if clocks stay high and temps stay low, denser packing is usually a win. If overhead rises (DLL-copy mode), try `max_lanes = 8` or raise `min_batch_per_lane`.

---

## Features (full miner)

### Mining engines

- **Native CUDA** — Argon2id on GPU via `xen_cuda.dll`
- **CPU backend** — pure Python when no NVIDIA GPU is available
- **Legacy GPU bridge** — optional `xenblocks.exe` + DB watcher
- **Merged mining** of **XNM**, **XUNI**, and **XBLK** (superblocks)
- Difficulty-aware batch sizing (Argon2 memory cost tracks network difficulty)

### Low-difficulty multi-lane harvest

- Spins up extra CUDA lanes up to `max_lanes` (default **12**)
- **Fill pack**: uses VRAM budget + `min_batch_per_lane` so low dif doesn’t leave memory idle
- Collapses toward **1 lane** when difficulty rises
- Live **thermal lane cap** + batch derate; post-cooldown lane-cap memory
- Queues hits during short difficulty transitions

### Hardware safety

- VRAM caps as **% or absolute MiB** (example: `target_vram_mib = 24576`)
- Temp guard: warn → cooldown → restart
- Difficulty-aware power + thermal batch + **thermal lanes**
- NVML power control; optional Windows High Performance plan

### Dashboard / queue / network

Same as upstream: Rich UI, SQLite queue, Woodyminer, difficulty poller, wallet balances.

---

## Quick start

```powershell
git clone https://github.com/badnob/xnminer-lowdif.git
cd xnminer-lowdif
.\Start-Miner.bat
```

---

## Configuration (low-dif knobs)

```ini
[efficiency]
target_vram_mib = 24576
max_gpu_temp_c = 72
warn_gpu_temp_c = 68
gpu_power_min_pct = 65
gpu_difficulty_power_full_ratio = 1.5
gpu_thermal_batch_enabled = true
gpu_thermal_batch_min_scale = 0.60
gpu_thermal_lane_enabled = true
gpu_thermal_lane_min = 1
gpu_difficulty_lane_bias = true
gpu_difficulty_lane_full_pack_ratio = 0.35

[cuda]
max_lanes = 12
lane_pack_mode = fill
min_batch_per_lane = 2048
```

| Setting | Role |
|---------|------|
| `max_lanes` | Hard ceiling on parallel CUDA lanes |
| `lane_pack_mode=fill` | Pack lanes to fill VRAM at low dif |
| `min_batch_per_lane` | Lower → more lanes (try 1024–4096) |
| `gpu_thermal_lane_enabled` | Live lane shrink on heat |
| `gpu_difficulty_lane_bias` | Ease lanes as difficulty climbs toward ref |
| `target_vram_mib` | Absolute used-VRAM target (0 = use %) |

---

## Build CUDA engine

```powershell
.\native\build.ps1
```

Output: `native\build\bin\xen_cuda.dll`

---

## License / credits

- Miner UI & orchestration: **Tony.x1**
- Low-dif fork policy: denser lane pack + live thermal lanes
- Native hashing / block rules: XenBlocks ecosystem patterns

**Upstream:** https://github.com/badnob/xnminer  
**Linux:** https://github.com/badnob/xnminer-linux
