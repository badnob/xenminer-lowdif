# How to get started

**XenBlocks Miner by Tony.x1** — GPU miner for [XenBlocks](https://xenblocks.io) on **Windows** and **Linux**.

---

## What you need

1. **Windows** or **Linux** PC  
2. **Python 3.10+**  
   - Windows: [python.org](https://www.python.org/downloads/) — tick **“Add Python to PATH”**  
   - Linux: `sudo apt install python3 python3-pip python3-venv` (or distro equivalent)  
3. **NVIDIA GPU + drivers**  
   - Windows: [NVIDIA](https://www.nvidia.com/Download/index.aspx)  
   - Linux: proprietary NVIDIA driver + CUDA Toolkit to **build** the native engine  
   - This miner does **not** ship NVIDIA drivers  
4. An **EVM wallet** address (`0x` + 40 hex characters) for rewards  

No NVIDIA GPU? You can mine on **CPU** (much slower) — set `backend = cpu` in `miner.ini` after the first run.

---

## Setup (once)

### Windows

1. Download or clone this repo.  
2. Double-click **`Start-Miner.bat`**.

### Linux

1. Clone this repo.  
2. Build the CUDA engine (once, if using GPU):

```bash
chmod +x native/build.sh start-miner.sh
./native/build.sh
# older GPUs example:  CMAKE_CUDA_ARCHITECTURES=86 ./native/build.sh
```

3. Start mining:

```bash
./start-miner.sh
```

The launcher will:

- create `miner.ini` if needed  
- install Python packages from `requirements.txt`  
- ask for your **EVM wallet** once, then save it  
- create a **unique miner name** (e.g. `xnminer-a1b2c3d4`) so Woodyminer / XenBlockScan stats do not clash with other users  

You do **not** need to edit config files to start mining. Optional: set your own name later in `miner.ini` (`worker` / `woodyminer_custom_name`).

---

## Run

**Windows** — double-click:

```text
Start-Miner.bat
```

**Linux**:

```bash
./start-miner.sh
# or
python3 main.py
```

- First run → enter wallet → mining starts  
- Live dashboard in the console  
- **Ctrl+C** stops mining and flushes any queued blocks  

---

## Check it’s working

| Check | Where |
|--------|--------|
| Hashrate | Dashboard speed / H/s |
| Accepts | Accepted / local accepts |
| Network | Dashboard network status |
| Logs | `data/session.log` |
| Away from PC | [woodyminer.com](https://woodyminer.com) (enabled by default) |

---

## Common issues

| Problem | Fix |
|---------|-----|
| “Python not found” | Windows: reinstall with **Add to PATH**. Linux: install `python3` / `python3-pip` |
| CUDA / library errors | Install NVIDIA driver; on Linux rebuild with `./native/build.sh` |
| No `libxen_cuda.so` | Run `./native/build.sh` (needs cmake + CUDA Toolkit) |
| No GPU | Set `backend = cpu` in `miner.ini` |
| Another miner running | Close the other process, or delete `data/miner.lock` if stale |
| Power limit fails | Run as admin (Windows) or root/`nvidia-smi -pl` permission (Linux) |
| Wrong wallet | Edit `miner.ini` → `[account] address = 0x...` |

---

## Safety

- VRAM limits scale with **your** GPU size (desktop headroom kept free).  
- Temp guard + difficulty-aware power / thermal batch derate cool the card under load.  
- Run **only one** copy of this miner per machine.

---

## More detail

See **`README.md`** for features, advanced config, and project layout.

Happy mining.
