# How to get started

**XenBlocks Miner by Tony.x1** — GPU miner for [XenBlocks](https://xenblocks.io) on **Windows** and **Linux**.

| | Windows | Linux |
|--|---------|--------|
| **Start** | `Start-Miner.bat` | `./start-miner.sh` |
| **CUDA lib** | `xen_cuda.dll` | `libxen_cuda.so` |
| **Build** | `.\native\build.ps1` | `./native/build.sh` |

More detail: **[README.md](README.md)**

---

## What you need

### Both platforms

1. **Python 3.10+**  
2. **NVIDIA GPU + drivers** (for CUDA mining) — this project does **not** ship drivers  
3. An **EVM wallet** (`0x` + 40 hex characters) for rewards  

No NVIDIA GPU? Use **CPU** mining (slower): set `backend = cpu` in `miner.ini` after first run.

### Windows extras

- Python from [python.org](https://www.python.org/downloads/) — tick **Add Python to PATH**  
- NVIDIA driver from [NVIDIA](https://www.nvidia.com/Download/index.aspx)  

### Linux extras

- `python3`, `python3-pip` (and usually `python3-venv`)  
- Proprietary NVIDIA driver  
- **CUDA Toolkit** (`nvcc`) + **cmake** to build the native engine  

```bash
# Debian/Ubuntu example
sudo apt update
sudo apt install python3 python3-pip python3-venv cmake build-essential
# Install NVIDIA driver + CUDA Toolkit from NVIDIA or your distro docs
```

---

## Setup & run

### Windows

1. Download or clone this repo.  
2. Double-click **`Start-Miner.bat`**.  
3. Enter your wallet when prompted.

```powershell
git clone https://github.com/badnob/xnminer.git
cd xnminer
.\Start-Miner.bat
```

### Linux

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

### What the launcher does (both)

- Creates `miner.ini` from the example if needed  
- Installs Python packages from `requirements.txt`  
- Asks for your **EVM wallet** once and saves it  
- Creates a **unique miner name** (e.g. `xnminer-a1b2c3d4`) so stats don’t clash  

Optional later: set your own name in `miner.ini` (`worker` / `woodyminer_custom_name`).

---

## Controls

- **Ctrl+C** — stop mining, flush queue when possible, exit  
- Live dashboard in the console  
- Logs: `data/session.log`  

### Manual start (both)

```bash
# Windows
python main.py

# Linux
python3 main.py
```

CPU only:

```bash
python main.py --backend cpu     # Windows
python3 main.py --backend cpu    # Linux
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

| Problem | Windows | Linux |
|---------|---------|--------|
| Python not found | Reinstall with **Add to PATH** | Install `python3` / `pip` |
| CUDA / library missing | Install driver; rebuild `.\native\build.ps1` | `./native/build.sh` (cmake + CUDA) |
| No GPU | `backend = cpu` in `miner.ini` | Same |
| Another miner running | Close other window; delete `data\miner.lock` if stale | Same (`data/miner.lock`) |
| Power limit fails | Run as Administrator | Permissions for `nvidia-smi -pl` / root |
| Wrong wallet | Edit `miner.ini` → `[account] address` | Same |

---

## Safety (both)

- VRAM limits scale with **your** GPU size  
- Temp guard + difficulty-aware power + thermal batch derate under load  
- Run **only one** miner instance per machine  

---

Happy mining.
