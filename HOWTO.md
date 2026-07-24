# How to get started — Windows

**XenBlocks Miner by Tony.x1** — GPU miner for [XenBlocks](https://xenblocks.io) on **Windows**.

| Item | Value |
|------|--------|
| **Start** | `Start-Miner.bat` |
| **CUDA lib** | `native\build\bin\xen_cuda.dll` |
| **Build** | `.\native\build.ps1` |

Full docs: **[README.md](README.md)**  
Linux port: **[xnminer-linux](https://github.com/badnob/xnminer-linux)**

---

## What you need

1. **Windows 10 / 11** PC  
2. **Python 3.10+** from [python.org](https://www.python.org/downloads/)  
   - Tick **Add Python to PATH** during install  
3. **NVIDIA GPU + drivers** from [NVIDIA](https://www.nvidia.com/Download/index.aspx)  
   - This miner does **not** ship NVIDIA drivers  
4. An **EVM wallet** address (`0x` + 40 hex characters) for rewards  

No NVIDIA GPU? Use **CPU** mining (slower): set `backend = cpu` in `miner.ini` after first run.

---

## Setup & run

1. Download or clone this repo.  
2. Double-click **`Start-Miner.bat`**.  
3. Enter your wallet when prompted.

```powershell
git clone https://github.com/badnob/xnminer.git
cd xnminer
.\Start-Miner.bat
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
- Logs: `data\session.log`  

### Manual start

```bat
python main.py
python main.py --backend cpu
```

---

## Check it’s working

| Check | Where |
|--------|--------|
| Hashrate | Dashboard H/s |
| Accepts | Accepted / local accepts |
| Network | Dashboard network status |
| Logs | `data\session.log` |
| Away from PC | [woodyminer.com](https://woodyminer.com) (on by default) |

---

## Common issues

| Problem | Fix |
|---------|-----|
| Python not found | Reinstall with **Add to PATH**, reopen the window |
| CUDA / DLL errors | Install latest NVIDIA driver; rebuild with `.\native\build.ps1` |
| No GPU | Set `backend = cpu` in `miner.ini` |
| Another miner running | Close the other window, or delete `data\miner.lock` if stale |
| Power limit fails | Run as **Administrator** |
| Wrong wallet | Edit `miner.ini` → `[account] address = 0x...` |

---

## Safety

- VRAM limits scale with **your** GPU size  
- Temp guard + difficulty-aware power + thermal batch derate under load  
- Run **only one** miner instance per machine  

---

Happy mining.
