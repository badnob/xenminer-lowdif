# How to get started — Linux

**XenBlocks Miner by Tony.x1** — GPU miner for [XenBlocks](https://xenblocks.io) on **Linux**.

| Item | Value |
|------|--------|
| **Start** | `./start-miner.sh` |
| **CUDA lib** | `native/build/bin/libxen_cuda.so` |
| **Build** | `./native/build.sh` |

Full docs: **[README-Linux.md](README-Linux.md)**  
Windows: **[HOWTO-Windows.md](HOWTO-Windows.md)**

---

## What you need

1. **Linux** PC (x86_64)  
2. **Python 3.10+** (`python3`, `python3-pip`)  
3. **NVIDIA proprietary driver**  
4. **CUDA Toolkit** (`nvcc`) + **cmake** to build the native engine  
5. An **EVM wallet** address (`0x` + 40 hex characters) for rewards  

This miner does **not** ship NVIDIA drivers.

No NVIDIA GPU? Use **CPU** mining (slower): set `backend = cpu` in `miner.ini` after first run.

```bash
# Debian/Ubuntu example
sudo apt update
sudo apt install python3 python3-pip python3-venv cmake build-essential
# Install NVIDIA driver + CUDA Toolkit from NVIDIA or your distro docs
```

---

## Setup & run

1. Clone this repo.  
2. Build CUDA (once, for GPU mining).  
3. Start the miner.  
4. Enter your wallet when prompted.

```bash
git clone https://github.com/badnob/xnminer.git
cd xnminer
chmod +x start-miner.sh native/build.sh
./native/build.sh
# older GPUs: CMAKE_CUDA_ARCHITECTURES=86 ./native/build.sh
./start-miner.sh
```

The launcher will:

- create `miner.ini` if needed  
- install Python packages from `requirements.txt`  
- ask for your **EVM wallet** once and save it  
- create a **unique miner name** (e.g. `xnminer-a1b2c3d4`) so stats don’t clash  

Optional later: set your own name in `miner.ini` (`worker` / `woodyminer_custom_name`).

---

## Controls

- **Ctrl+C** — stop mining, flush queue when possible, exit  
- Live dashboard in the console  
- Logs: `data/session.log`  

### Manual start

```bash
python3 main.py
python3 main.py --backend cpu
```

---

## Check it’s working

| Check | Where |
|--------|--------|
| Hashrate | Dashboard H/s |
| Accepts | Accepted / local accepts |
| Network | Dashboard network status |
| Logs | `data/session.log` |
| Away from PC | [woodyminer.com](https://woodyminer.com) (on by default) |

---

## Common issues

| Problem | Fix |
|---------|-----|
| Python not found | Install `python3` / `python3-pip` |
| No `libxen_cuda.so` | Run `./native/build.sh` (needs cmake + CUDA Toolkit) |
| CUDA / library errors | Install NVIDIA driver; rebuild engine |
| No GPU | Set `backend = cpu` in `miner.ini` |
| Another miner running | Stop the other process, or delete `data/miner.lock` if stale |
| Power limit fails | Permissions for `nvidia-smi -pl` (may need root) |
| Wrong wallet | Edit `miner.ini` → `[account] address = 0x...` |

---

## Safety

- VRAM limits scale with **your** GPU size  
- Temp guard + difficulty-aware power + thermal batch derate under load  
- Run **only one** miner instance per machine  

---

Happy mining.
