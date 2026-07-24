# XenBlocks Miner by Tony.x1 — Linux

Modular **Python + native CUDA** miner for [XenBlocks](https://xenblocks.io) on **Linux**.

Live console dashboard · smart submit queue · XNM / XUNI / XBLK · VRAM & temp safety · difficulty-aware power · Woodyminer remote stats

| Item | Linux |
|------|--------|
| **Start** | `./start-miner.sh` |
| **CUDA library** | `native/build/bin/libxen_cuda.so` |
| **Build** | `./native/build.sh` |
| **Python** | `python3` |

**Beginner walkthrough:** [HOWTO-Linux.md](HOWTO-Linux.md)  
**Windows docs:** [README-Windows.md](README-Windows.md)

---

## Features

### Mining engines

- **Native CUDA** — Argon2id on GPU via `libxen_cuda.so`
- **CPU backend** — pure Python when no NVIDIA GPU is available
- **Merged mining** of **XNM**, **XUNI**, and **XBLK** (superblocks)
- Official-style block rules (XUNI window, XEN11, superblock uppercase)
- Key strategies: random (default), Fibonacci, pluggable registry
- Difficulty-aware batch sizing (Argon2 memory cost tracks network difficulty)

### Low-difficulty multi-lane harvest

When difficulty **drops**, each hash uses less VRAM. The miner:

- Spins up extra CUDA lanes (e.g. up to `max_lanes = 4`)
- Re-plans batch so combined work **fills the VRAM budget**
- Collapses toward **1 lane** when difficulty rises again
- Queues hits during short difficulty transitions
- Can **reduce lane cap** after thermal stress (restores when cool)

### Live dashboard

- Full-screen **Rich** UI (resize-safe alternate screen)
- Found / Accepted / Rejected / Queued / Resubmit
- Session timelapse + 1-hour H/s sparkline
- GPU: VRAM, util %, temp, power, CUDA batch / multi-lane
- Network status + difficulty (stale/offline aware)

### Wallet & rewards

- On-chain balances (XNM / XUNI / XBLK)
- Day / week comparisons (1am mining-day boundary)
- Halving-aware XNM display; XUNI / XBLK = 1 token per accept
- First-run wallet setup saved to `miner.ini`

### Queue & reliability

- Persistent SQLite + JSONL queue
- Holds blocks during transitions, XUNI window, network down, shutdown
- CPU-capped parallel submit pool
- Graceful **Ctrl+C** (stop → flush → exit)
- Single-instance lock (`data/miner.lock`)

### Hardware safety & efficiency

- VRAM caps as **% of each GPU** (~69% target, desktop headroom, emergency stop)
- Temp guard: warn → cooldown → restart
- **Difficulty-aware power** — as difficulty rises above reference, power target eases within `gpu_power_min_pct`–`gpu_power_target_pct`
- **Thermal batch derate** — near warn/max temp, batch soft-scales (never below `gpu_thermal_batch_min_scale`)
- NVML / `nvidia-smi` power control
- Continuous NVML monitoring — **no NVIDIA drivers are shipped**

### Network & remote stats

- Background difficulty poller
- Server uptime tracker + session logs
- **[Woodyminer](https://woodyminer.com)** remote stats / leaderboard
- Optional **XenBlockScan** event reporting

---

## Requirements

| Component | Notes |
|-----------|--------|
| **OS** | Modern x86_64 Linux |
| **Python** | 3.10+ (`python3`, `python3-pip`) |
| **NVIDIA driver** | Proprietary driver for CUDA mining |
| **CUDA Toolkit + cmake** | Required to **build** `libxen_cuda.so` |
| **EVM wallet** | `0x…` address (prompted on first run) |

```bash
# Debian/Ubuntu example (driver/CUDA still needed from NVIDIA or distro)
sudo apt update
sudo apt install python3 python3-pip python3-venv cmake build-essential
```

> Drivers are never bundled. You must run `./native/build.sh` once for GPU mining.

---

## Quick start

1. Install **Python 3.10+**, NVIDIA driver, **CUDA Toolkit** (`nvcc`), and **cmake**.  
2. Clone this repo.  
3. Build the CUDA engine, then start:

```bash
git clone https://github.com/badnob/xnminer.git
cd xnminer
chmod +x start-miner.sh native/build.sh
./native/build.sh
./start-miner.sh
```

4. Enter your **EVM wallet** when asked — mining starts.

The launcher creates `miner.ini`, installs packages from `requirements.txt`, and prompts for your wallet.

- **Ctrl+C** stops mining and flushes the queue when possible  
- CPU-only (skip CUDA build): set `backend = cpu` in `miner.ini`, then `python3 main.py --backend cpu`  
- **Privacy:** real `miner.ini` and `data/` are gitignored — never commit wallet or local paths  

---

## Configuration

Edit **`miner.ini`** (created from `miner.ini.example` on first run):

```ini
[account]
address = 0xYourWallet...
worker =                # empty = auto unique name (xnminer-xxxxxxxx)

[mining]
backend = cuda          # cuda | cpu

[efficiency]
target_vram_pct = 69.09
max_gpu_temp_c = 75
warn_gpu_temp_c = 72
gpu_power_target_pct = 100
gpu_power_min_pct = 75
gpu_difficulty_power_enabled = true
gpu_difficulty_power_full_ratio = 2.0
gpu_thermal_batch_enabled = true
gpu_thermal_batch_min_scale = 0.70

[cuda]
# Windows-style path is fine — miner auto-resolves libxen_cuda.so when .dll is missing
dll_path = native/build/bin/xen_cuda.dll
# Or set explicitly:
# dll_path = native/build/bin/libxen_cuda.so
max_lanes = 4
```

| Setting | Role |
|---------|------|
| `gpu_power_target_pct` / `gpu_power_min_pct` | Power band; eases toward min as difficulty rises |
| `gpu_difficulty_power_full_ratio` | Difficulty multiple of reference where power hits min (default 2×) |
| `gpu_thermal_batch_min_scale` | Lowest batch scale near max temp (default 0.70) |
| `dll_path` | Path to native library (`.so` auto-resolved) |

### CLI

```bash
python3 main.py
python3 main.py --backend cpu
python3 main.py --no-dashboard
python3 main.py --diagnose
python3 main.py --max-seconds 3600
```

---

## Build CUDA engine

Needs **cmake**, a C++ compiler, and the **CUDA Toolkit** (`nvcc` on `PATH`).

```bash
./native/build.sh
# e.g. RTX 30-series:
CMAKE_CUDA_ARCHITECTURES=86 ./native/build.sh
```

Output: `native/build/bin/libxen_cuda.so`

> Default architectures may target newer GPUs (e.g. sm_90 / sm_120). For older cards set `CMAKE_CUDA_ARCHITECTURES` (75, 86, 89, …).

---

## Project layout

```text
├── main.py                 # Entry point
├── miner.ini.example       # Config template
├── start-miner.sh          # Linux launcher
├── README-Linux.md         # This file
├── HOWTO-Linux.md          # Beginner walkthrough
├── core/                   # Supervisor, models, instance lock
├── mining/                 # CUDA / CPU backends, .so resolve
├── monitoring/             # Dashboard, wallet, rewards, woodyminer
├── efficiency/             # VRAM, temp, power, thermal policy
├── block_queue/            # Persist + flush submit queue
├── networking/             # Difficulty poller, submitter
├── strategies/             # Key generation strategies
├── native/                 # Engine source + build.sh
├── data/                   # Runtime DB, logs (local only)
└── tests/                  # Unit tests
```

---

## Limitations

- No NVIDIA drivers bundled  
- CUDA library must be built locally with `./native/build.sh`  
- CUDA binary may need rebuild for your GPU architecture  
- No automatic CPU fallback if CUDA fails — set `backend = cpu`  
- Power limit changes may need elevated permissions for `nvidia-smi -pl`  
- Network RPC for balances can time out; dashboard may show cached values  

---

## License / credits

- Miner UI & orchestration: **Tony.x1**
- Native hashing / block rules: XenBlocks ecosystem and open-source miner patterns (Argon2id, XEN11 / XUNI / superblock)

---

## Support

| Item | Path |
|------|------|
| Session log | `data/session.log` |
| Queue / DB | `data/blocks.db`, `data/queue.jsonl` |
| Stats | `data/mining_stats_history.json`, `data/balance_history.json` |

When reporting issues, include log lines, **Linux**, GPU model, and `backend` from `miner.ini`.
