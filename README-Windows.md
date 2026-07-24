# XenBlocks Miner by Tony.x1 — Windows

Modular **Python + native CUDA** miner for [XenBlocks](https://xenblocks.io) on **Windows**.

Live console dashboard · smart submit queue · XNM / XUNI / XBLK · VRAM & temp safety · difficulty-aware power · Woodyminer remote stats

| Item | Windows |
|------|---------|
| **Start** | `Start-Miner.bat` or `Start-Miner.ps1` |
| **CUDA library** | `native\build\bin\xen_cuda.dll` |
| **Build** | `.\native\build.ps1` |
| **Python** | `python` |

**Beginner walkthrough:** [HOWTO-Windows.md](HOWTO-Windows.md)  
**Linux docs:** [README-Linux.md](README-Linux.md)

---

## Features

### Mining engines

- **Native CUDA** — Argon2id on GPU via `xen_cuda.dll`
- **CPU backend** — pure Python when no NVIDIA GPU is available
- **Legacy GPU bridge** — optional `xenblocks.exe` + DB watcher
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
- Single-instance lock (`data\miner.lock`)

### Hardware safety & efficiency

- VRAM caps as **% of each GPU** (~69% target, desktop headroom, emergency stop)
- Temp guard: warn → cooldown → restart
- **Difficulty-aware power** — as difficulty rises above reference, power target eases within `gpu_power_min_pct`–`gpu_power_target_pct`
- **Thermal batch derate** — near warn/max temp, batch soft-scales (never below `gpu_thermal_batch_min_scale`)
- NVML power control; optional **Windows High Performance** power plan
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
| **OS** | Windows 10 / 11 |
| **Python** | 3.10+ from [python.org](https://www.python.org/downloads/) — tick **Add to PATH** |
| **NVIDIA driver** | Game Ready or Studio for CUDA mining |
| **CUDA Toolkit + VS C++ / CMake** | Only if you rebuild `xen_cuda.dll` |
| **EVM wallet** | `0x…` address (prompted on first run) |

> Drivers are never bundled. A prebuilt `xen_cuda.dll` may already be present under `native\build\bin\`.

---

## Quick start

1. Install **Python 3.10+** and an **NVIDIA driver** (for GPU mining).  
2. Download or clone this repo.  
3. Double-click **`Start-Miner.bat`**.  
4. Enter your **EVM wallet** when asked — mining starts.

```powershell
git clone https://github.com/badnob/xnminer.git
cd xnminer
.\Start-Miner.bat
```

The launcher creates `miner.ini`, installs packages from `requirements.txt`, and prompts for your wallet.

- **Ctrl+C** stops mining and flushes the queue when possible  
- CPU-only: set `backend = cpu` in `miner.ini`, then `python main.py --backend cpu`  
- **Privacy:** real `miner.ini` and `data\` are gitignored — never commit wallet or local paths  

---

## Configuration

Edit **`miner.ini`** (created from `miner.ini.example` on first run):

```ini
[account]
address = 0xYourWallet...
worker =                # empty = auto unique name (xnminer-xxxxxxxx)

[mining]
backend = cuda          # cuda | cpu | gpu (legacy)

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
gpu_windows_performance_mode = true

[cuda]
dll_path = native/build/bin/xen_cuda.dll
max_lanes = 4
```

| Setting | Role |
|---------|------|
| `gpu_power_target_pct` / `gpu_power_min_pct` | Power band; eases toward min as difficulty rises |
| `gpu_difficulty_power_full_ratio` | Difficulty multiple of reference where power hits min (default 2×) |
| `gpu_thermal_batch_min_scale` | Lowest batch scale near max temp (default 0.70) |
| `dll_path` | Path to `xen_cuda.dll` |

### CLI

```bat
python main.py
python main.py --backend cpu
python main.py --no-dashboard
python main.py --diagnose
python main.py --max-seconds 3600
```

---

## Build CUDA engine

Needs **Visual Studio C++ tools**, **CMake**, **Ninja** (or VS generator), and the **CUDA Toolkit**.

```powershell
.\native\build.ps1
```

Output: `native\build\bin\xen_cuda.dll`

> Default architectures may target newer GPUs (e.g. sm_90 / sm_120). For older cards rebuild with `CMAKE_CUDA_ARCHITECTURES` (75, 86, 89, …).

---

## Project layout

```text
├── main.py                 # Entry point
├── miner.ini.example       # Config template
├── Start-Miner.bat / .ps1  # Windows launchers
├── README-Windows.md       # This file
├── HOWTO-Windows.md        # Beginner walkthrough
├── core/                   # Supervisor, models, instance lock
├── mining/                 # CUDA / CPU backends
├── monitoring/             # Dashboard, wallet, rewards, woodyminer
├── efficiency/             # VRAM, temp, power, thermal policy
├── block_queue/            # Persist + flush submit queue
├── networking/             # Difficulty poller, submitter
├── strategies/             # Key generation strategies
├── native/                 # Engine source + build.ps1
├── data\                   # Runtime DB, logs (local only)
└── tests/                  # Unit tests
```

---

## Limitations

- No NVIDIA drivers bundled  
- CUDA binary may need rebuild for your GPU architecture  
- No automatic CPU fallback if CUDA fails — set `backend = cpu`  
- Power limit changes may need **Administrator**  
- Network RPC for balances can time out; dashboard may show cached values  

---

## License / credits

- Miner UI & orchestration: **Tony.x1**
- Native hashing / block rules: XenBlocks ecosystem and open-source miner patterns (Argon2id, XEN11 / XUNI / superblock)

---

## Support

| Item | Path |
|------|------|
| Session log | `data\session.log` |
| Queue / DB | `data\blocks.db`, `data\queue.jsonl` |
| Stats | `data\mining_stats_history.json`, `data\balance_history.json` |

When reporting issues, include log lines, **Windows**, GPU model, and `backend` from `miner.ini`.
