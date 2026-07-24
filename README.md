# XenBlocks Miner by Tony.x1

Modular **Python + native CUDA** miner for [XenBlocks](https://xenblocks.io) — **Windows and Linux**.

Live console dashboard · smart submit queue · XNM / XUNI / XBLK · VRAM & temp safety · difficulty-aware power · Woodyminer remote stats

| Platform | Start | CUDA library |
|----------|--------|----------------|
| **Windows** | `Start-Miner.bat` | `native/build/bin/xen_cuda.dll` |
| **Linux** | `./start-miner.sh` | `native/build/bin/libxen_cuda.so` |

**Full walkthrough:** [HOWTO.md](HOWTO.md)

---

## Features

### Mining engines

- **Native CUDA** — Argon2id on GPU (`xen_cuda.dll` on Windows, `libxen_cuda.so` on Linux)
- **CPU backend** — pure Python when no NVIDIA GPU is available
- **Legacy GPU bridge** — optional `xenblocks.exe` + DB watcher (Windows)
- **Merged mining** of **XNM**, **XUNI**, and **XBLK** (superblocks) in one hash stream
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
- NVML power control (`nvidia-smi` / driver); optional Windows High Performance plan on Windows only
- Continuous NVML monitoring — **no NVIDIA drivers are shipped**

### Network & remote stats

- Background difficulty poller
- Server uptime tracker + session logs
- **[Woodyminer](https://woodyminer.com)** remote stats / leaderboard
- Optional **XenBlockScan** event reporting

---

## Requirements

| Component | Windows | Linux |
|-----------|---------|--------|
| **OS** | Windows 10/11 | Modern x86_64 distro |
| **Python** | 3.10+ ([python.org](https://www.python.org/downloads/) — add to PATH) | 3.10+ (`python3`, `pip`) |
| **NVIDIA driver** | Game Ready / Studio | Proprietary NVIDIA driver |
| **CUDA Toolkit + cmake** | To rebuild native engine | Required to **build** `libxen_cuda.so` |
| **EVM wallet** | `0x…` address (prompted on first run) | Same |

> Drivers are never bundled. A prebuilt `xen_cuda.dll` may be present for Windows; Linux users build with `./native/build.sh`.

---

## Quick start

### Windows

1. Install **Python 3.10+** and an **NVIDIA driver** (for GPU mining).  
2. Download or clone this repo.  
3. Double-click **`Start-Miner.bat`** (or run `.\Start-Miner.ps1`).  
4. Enter your **EVM wallet** when asked — mining starts.

```powershell
git clone https://github.com/badnob/xnminer.git
cd xnminer
.\Start-Miner.bat
```

### Linux

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

### Both platforms

- Launchers create `miner.ini`, install deps from `requirements.txt`, and prompt for wallet  
- **Ctrl+C** stops mining and flushes the queue when possible  
- CPU-only (no CUDA build): set `backend = cpu` in `miner.ini`, then run `python main.py` / `python3 main.py`  
- **Privacy:** real `miner.ini` and `data/` are gitignored — never commit wallet or local paths  

---

## Configuration

Edit **`miner.ini`** (created from `miner.ini.example` on first run):

```ini
[account]
address = 0xYourWallet...
worker =                # empty = auto unique name (xnminer-xxxxxxxx)

[mining]
backend = cuda          # cuda | cpu | gpu (legacy Windows)

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
# Windows default; Linux auto-resolves libxen_cuda.so if this file is missing
dll_path = native/build/bin/xen_cuda.dll
max_lanes = 4
```

| Setting | Role |
|---------|------|
| `gpu_power_target_pct` / `gpu_power_min_pct` | Power band; eases toward min as difficulty rises |
| `gpu_difficulty_power_full_ratio` | Difficulty multiple of reference where power hits min (default 2×) |
| `gpu_thermal_batch_min_scale` | Lowest batch scale near max temp (default 0.70) |
| `dll_path` | Native library path (platform fallbacks apply) |

### CLI

```bash
# Windows: python    Linux: python3
python main.py
python main.py --backend cpu
python main.py --no-dashboard
python main.py --diagnose
python main.py --max-seconds 3600
```

---

## Build CUDA engine

### Windows

Needs Visual Studio C++ tools, CMake, Ninja (or VS generator), CUDA Toolkit:

```powershell
.\native\build.ps1
```

→ `native\build\bin\xen_cuda.dll`

### Linux

Needs cmake, g++/clang, CUDA Toolkit (`nvcc` on `PATH`):

```bash
./native/build.sh
# e.g. RTX 30-series:
CMAKE_CUDA_ARCHITECTURES=86 ./native/build.sh
```

→ `native/build/bin/libxen_cuda.so`

> Default CMake architectures may target newer GPUs (e.g. sm_90 / sm_120). For older cards set `CMAKE_CUDA_ARCHITECTURES` (75, 86, 89, …).

---

## Project layout

```text
├── main.py                 # Entry point
├── miner.ini.example       # Published config template
├── Start-Miner.bat / .ps1  # Windows launchers
├── start-miner.sh          # Linux launcher
├── HOWTO.md                # Beginner walkthrough (Win + Linux)
├── core/                   # Supervisor, models, instance lock
├── mining/                 # CUDA / CPU backends, native lib resolve
├── monitoring/             # Dashboard, wallet, rewards, woodyminer
├── efficiency/             # VRAM, temp, power, thermal policy
├── block_queue/            # Persist + flush submit queue
├── networking/             # Difficulty poller, submitter
├── strategies/             # Key generation strategies
├── native/                 # Engine source + build.ps1 / build.sh
├── data/                   # Runtime DB, logs (local only)
└── tests/                  # Unit tests
```

---

## Limitations

- No NVIDIA drivers bundled  
- CUDA binary may need rebuild for your GPU architecture  
- No automatic CPU fallback if CUDA fails — set `backend = cpu`  
- Linux GPU mining expects a successful `./native/build.sh`  
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

When reporting issues, include log lines, **OS (Windows/Linux)**, GPU model, and `backend` from `miner.ini`.
