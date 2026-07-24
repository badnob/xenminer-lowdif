# XenBlocks Miner by Tony.x1 #

Modular **Python + native CUDA** miner for [XenBlocks](https://xenblocks.io) with a live console dashboard, smart submit queue, halving-aware rewards, and hardware-safe GPU mining.

> CUDA/CPU miner · live dashboard · XNM / XUNI / XBLK · %VRAM safety caps · superblock detection · Woodyminer online stats

---

## Features

### Mining engines

- **Native CUDA backend** (`xen_cuda.dll` / `libxen_cuda.so`) — high-performance Argon2id hashing without relying on the legacy `xenblocks.exe` path as primary
- **CPU backend** — pure Python Argon2 mining when GPU/CUDA isn’t available
- **Legacy GPU bridge** — optional supervision of external `xenblocks.exe` + DB watcher
- **Merged mining** of **XNM**, **XUNI**, and **XBLK** (superblocks) in one hash stream
- **Official-style block classification**
  - **XUNI** — `XUNI` + digit, time-window rules
  - **XBLK** — XEN11 + superblock uppercase rule (digest body; threshold aligned with the open-source miner)
  - **XNM** — normal XEN11 blocks
- **Key strategies** — random (default), Fibonacci, pluggable strategy registry
- **Difficulty-aware batch sizing** — Argon2 memory cost scales with network difficulty; batch size is recomputed to stay within VRAM caps

### Low-difficulty multi-lane harvest (VRAM fill)

When network difficulty **drops** (e.g. 1100 → 100), each hash uses **less VRAM**. A single lane would leave most of the GPU idle. The miner then:

- **Spins up extra CUDA lanes** (configurable `max_lanes`, e.g. up to 4) with distinct key prefixes  
- **Re-plans batch size per lane** so combined work **keeps the configured VRAM budget full**  
- Logs a **harvest push** summary (lanes × batch, projected VRAM / free)  
- On difficulty **rising** again, **collapses back toward 1 lane** and restores the normal plan  
- During the short transition window, new hits are **queued** (no live submit/flush races) until mining is stable  
- Thermal stress can **temporarily reduce lane cap**; cool-down restores it when safe  

This is the “keep the card full when difficulty dips” path — not a fixed single batch for all difficulties.

### Live dashboard

- Full-screen **Rich** live UI (alternate screen — resize-safe, no scrollback mess)
- Compact stats table: Found / Accepted (tokens) / Rejected (pool) / Queued / Resubmit
- **Session timelapse** with **1-hour H/s sparkline** and 1h average
- Recent events feed (FOUND, ACCEPTED, QUEUED, RESUBMIT, WARN, …)
- GPU readout: VRAM, util %, temperature, power, **CUDA batch / multi-lane** (e.g. `4 lanes × batch`)
- Network status + current difficulty (including stale/offline awareness)

### Wallet & rewards

- On-chain **wallet balances** (XNM / XUNI / XBLK) via XenBlocks RPC
- **Day vs yesterday** and **week-to-date vs Monday** comparisons (1am mining-day boundary)
- **Local accepts** history with day/week deltas
- **Halving-aware token display** for XNM (yearly schedule: 10 → 5 → **2.5** → …)
- XUNI / XBLK shown as **1 token per accepted block**
- First-run **wallet setup** saved into `miner.ini`

### Queue & reliability

- Persistent **SQLite + JSONL** queue for blocks that can’t submit yet
- Holds blocks during difficulty transitions, XUNI window, network down, and shutdown
- **CPU-capped parallel submit pool** for verify/flush work
- Distinguishes true pool rejects vs difficulty mismatch / window / timeouts
- Graceful **Ctrl+C**: stop mining, flush queue when possible, exit cleanly
- Single-instance **lock** (`miner.lock`) so two miners don’t fight one GPU

### Hardware safety & efficiency

- **VRAM caps as % of each GPU’s total** (safe headroom on 8 GB–32 GB+ cards)
  - ~69% target use · ~25% desktop free · ~93% emergency · ~4% min free · ~6% CUDA overhead
- Absolute floors so tiny cards never go to zero free VRAM
- **Temp guard**: warn / graceful cooldown / auto-restart
- **Lane cap reduction** after thermal stress during multi-lane harvest; restore when cool
- **NVML power boost** toward configured % of card power limit; ease near warn temp
- **Difficulty-aware power**: as difficulty rises above `vram_reference_difficulty`, power target eases within `gpu_power_min_pct`–`gpu_power_target_pct` (full ease at `gpu_difficulty_power_full_ratio`× reference)
- **Thermal batch derate**: near warn/max temp, CUDA batch soft-scales down (never below `gpu_thermal_batch_min_scale`)
- Optional Windows performance mode for mining sessions
- Continuous NVML monitoring (temp, VRAM, util, power) via **pynvml**  
  (uses the **installed** NVIDIA driver — **no drivers are shipped**)
- CUDA `max_lanes` / `lane_reserve` / `vram_reference_difficulty` in `miner.ini` control harvest behaviour

### Network & ops

- Background **difficulty poller** (non-blocking mining loop)
- Server **uptime tracker** (last 6 hours, newest first, outage stats)
- Session logging to `data/session.log`
- Diagnostics mode (`--diagnose`)
- One-click Windows start: `Start-Miner.bat` / `Start-Miner.ps1`

### Woodyminer online stats (away from hardware)

- Integrates with **[Woodyminer](https://woodyminer.com)** so you can check mining performance **from any browser** while away from the rig
- Periodic upload of live stats (hashrate, accepts, uptime, GPU snapshot, difficulty, custom worker name)
- **Leaderboard** presence for your wallet / machine without needing the local console open
- Optional and configurable in `miner.ini` (`woodyminer_enabled`, upload URL/period, `woodyminer_custom_name`)
- Does not replace the local dashboard — local UI for at-the-machine detail; Woodyminer for **remote readability**

### Configuration

- Single **`miner.ini`** for wallet, backend, efficiency, CUDA, monitoring, queue
- CLI overrides: `--backend`, `--strategy`, `--lanes`, `--max-seconds`, `--no-dashboard`
- Data directory for DB, queue, stats history, balances, uptime, timelapse

### Developer-friendly

- Modular layout: `core`, `mining`, `monitoring`, `efficiency`, `block_queue`, `networking`
- Native CUDA engine build scripts (`native/build.ps1`, `native/build.sh`)
- Unit tests for rewards, VRAM policy, block types, queue, dashboard, and more

---

## Requirements

| Component | Notes |
|-----------|--------|
| **Python** | 3.10+ |
| **Windows or Linux** | `Start-Miner.bat` / `./start-miner.sh` |
| **NVIDIA GPU + driver** | For CUDA mining |
| **CUDA Toolkit + cmake** | To build the native engine on Linux (and to rebuild on Windows) |
| **EVM wallet** | `0x…` address for rewards (prompted on first run) |

> This project does **not** ship NVIDIA drivers. Windows may ship a prebuilt `xen_cuda.dll`; Linux builds `libxen_cuda.so` via `./native/build.sh`.

---

## Quick start

**Full walkthrough:** **[HOWTO.md](HOWTO.md)**

### Windows

1. Install **Python 3.10+** ([python.org](https://www.python.org/downloads/) — add to PATH).  
2. Install an **NVIDIA driver** if you will use a GPU.  
3. Download or clone this repo.  
4. Double-click **`Start-Miner.bat`**.  
5. Enter your **EVM wallet** when asked — then mining starts.

### Linux

1. Install **Python 3.10+**, NVIDIA driver, **CUDA Toolkit**, and **cmake**.  
2. Clone this repo.  
3. Build the engine, then start:

```bash
chmod +x start-miner.sh native/build.sh
./native/build.sh
./start-miner.sh
```

4. Enter your **EVM wallet** when asked — then mining starts.

The launcher creates `miner.ini`, installs Python packages, and prompts for your wallet. No manual config needed for a normal start.

**Ctrl+C** stops mining, flushes the queue when possible, then exits.

> **Privacy:** Real `miner.ini` (wallet, worker name, local paths) is gitignored. Only `miner.ini.example` is published. Never commit `data/`.

---

## Configuration

Edit **`miner.ini`**:

```ini
[account]
address = 0xYourWallet...
worker =                # empty = auto unique name (xnminer-xxxxxxxx)

[mining]
backend = cuda          # cuda | cpu | gpu (legacy)
strategy = random

[efficiency]
# VRAM policy as % of each GPU's total (auto-scales for all card sizes)
target_vram_pct = 69.09
desktop_headroom_pct = 25.12
emergency_vram_pct = 92.78
min_headroom_pct = 3.68
runtime_overhead_pct = 6.28
max_gpu_temp_c = 75
warn_gpu_temp_c = 72
gpu_power_target_pct = 100
gpu_power_min_pct = 75
gpu_difficulty_power_enabled = true
gpu_thermal_batch_enabled = true
gpu_thermal_batch_min_scale = 0.70

[cuda]
dll_path = native/build/bin/xen_cuda.dll   # Linux auto-resolves libxen_cuda.so
max_lanes = 4
```

### CLI examples

```bash
python main.py                 # Windows: python   Linux: python3
python main.py --backend cpu
python main.py --no-dashboard
python main.py --diagnose
python main.py --max-seconds 3600
```

---

## Build CUDA engine

### Windows

Requires **Visual Studio C++ tools**, **CMake**, **Ninja** (or VS generator), and the **CUDA Toolkit**.

```powershell
.\native\build.ps1
```

Output: `native\build\bin\xen_cuda.dll`

### Linux

Requires **cmake**, a C++ compiler, and the **CUDA Toolkit** (`nvcc` on `PATH`).

```bash
./native/build.sh
# e.g. RTX 30-series:
CMAKE_CUDA_ARCHITECTURES=86 ./native/build.sh
```

Output: `native/build/bin/libxen_cuda.so`

> The engine CMake may target newer architectures (e.g. sm_90 / sm_120). For older GPUs, rebuild with `CMAKE_CUDA_ARCHITECTURES` (e.g. 75, 86, 89).

---

## Project layout

```text
├── main.py                 # Entry point
├── miner.ini               # Config
├── Start-Miner.bat / .ps1  # Windows launchers
├── start-miner.sh          # Linux launcher
├── core/                   # Supervisor, models, instance lock
├── mining/                 # CUDA / CPU backends, block types, Argon2
├── monitoring/             # Dashboard, wallet, uptime, rewards, woodyminer
├── efficiency/             # VRAM %, temp guard, power boost, lanes
├── block_queue/            # Persist + flush submit queue
├── networking/             # Difficulty poller, submitter
├── strategies/             # Key generation strategies
├── native/                 # CUDA engine source + build (.ps1 / .sh)
├── data/                   # Runtime DB, logs, stats (local)
└── tests/                  # Unit tests
```

---

## Limitations

- **No NVIDIA drivers bundled** — install from NVIDIA for CUDA mining
- **CUDA binary** may need a rebuild for older GPU architectures
- **No automatic CPU fallback** if CUDA fails — set `backend = cpu` in `miner.ini`
- **Linux CUDA** requires a local `./native/build.sh` (`.so` is not always prebuilt)
- Network RPC for wallet balances can time out; dashboard shows cached/stale state when needed

---

## License / credits

- Miner UI & orchestration: **Tony.x1**
- Native hashing roots / reference behaviour: XenBlocks ecosystem and open-source miner patterns (Argon2id, XEN11 / XUNI / superblock rules)

---

## Support

- Logs: `data/session.log`
- Queue / DB: `data/blocks.db`, `data/queue.jsonl`
- Stats: `data/mining_stats_history.json`, `data/balance_history.json`, `data/server_uptime.json`

If you hit issues, include the relevant log lines and your GPU model + `backend` setting.
