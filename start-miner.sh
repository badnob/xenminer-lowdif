#!/usr/bin/env bash
# XenBlocks Miner by Tony.x1 — Linux launcher
# Usage:  chmod +x start-miner.sh && ./start-miner.sh

set -euo pipefail

MINER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$MINER_ROOT"

CONFIG_PATH="$MINER_ROOT/miner.ini"
EXAMPLE_PATH="$MINER_ROOT/miner.ini.example"
REQ_PATH="$MINER_ROOT/requirements.txt"
LOCK_PATH="$MINER_ROOT/data/miner.lock"
MAIN_PY="$MINER_ROOT/main.py"

read_ini_value() {
  local section="$1" key="$2" path="$3"
  local in_section=0
  local line trimmed
  [[ -f "$path" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    trimmed="${line#"${line%%[![:space:]]*}"}"
    trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
    if [[ "$trimmed" =~ ^\[(.+)\]$ ]]; then
      if [[ "${BASH_REMATCH[1]}" == "$section" ]]; then
        in_section=1
      else
        in_section=0
      fi
      continue
    fi
    if (( in_section )) && [[ "$trimmed" =~ ^${key}[[:space:]]*=[[:space:]]*(.*)$ ]]; then
      echo "${BASH_REMATCH[1]}"
      return 0
    fi
  done <"$path"
}

stop_existing_miners() {
  local pids
  pids="$(pgrep -f "python[0-9.]*[[:space:]].*${MAIN_PY}" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "Stopping existing miner process(es): $pids"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 2
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
  fi
}

if [[ ! -f "$CONFIG_PATH" && -f "$EXAMPLE_PATH" ]]; then
  cp "$EXAMPLE_PATH" "$CONFIG_PATH"
  echo "Created miner.ini from miner.ini.example"
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3.10+ (e.g. sudo apt install python3 python3-pip python3-venv)"
  exit 1
fi

PY_VERSION="$(python3 --version 2>&1)"

if [[ -f "$REQ_PATH" ]]; then
  if ! python3 -c "import argon2, pynvml, psutil, rich" 2>/dev/null; then
    echo "Installing Python packages (one-time)..."
    python3 -m pip install -r "$REQ_PATH"
  fi
fi

BACKEND="$(read_ini_value mining backend "$CONFIG_PATH" || true)"
BACKEND="${BACKEND:-cuda}"
CUDA_LIB="$(read_ini_value cuda dll_path "$CONFIG_PATH" || true)"
if [[ -z "${CUDA_LIB// }" ]]; then
  if [[ "$(uname -s)" == "Linux" ]]; then
    CUDA_LIB="native/build/bin/libxen_cuda.so"
  else
    CUDA_LIB="native/build/bin/xen_cuda.dll"
  fi
fi
CUDA_FULL="$MINER_ROOT/$CUDA_LIB"
# If .dll path from Windows config is missing, also check .so next to it
if [[ "$BACKEND" == "cuda" && ! -f "$CUDA_FULL" ]]; then
  so_alt="${CUDA_FULL%.dll}"
  so_alt="${so_alt%.so}"
  for cand in \
    "$CUDA_FULL" \
    "${so_alt}.so" \
    "$(dirname "$CUDA_FULL")/libxen_cuda.so" \
    "$(dirname "$CUDA_FULL")/xen_cuda.so" \
    "$MINER_ROOT/native/build/bin/libxen_cuda.so"
  do
    if [[ -f "$cand" ]]; then
      CUDA_FULL="$cand"
      break
    fi
  done
fi

if [[ "$BACKEND" == "cuda" && ! -f "$CUDA_FULL" ]]; then
  echo "WARNING: CUDA engine not found (expected libxen_cuda.so)."
  echo "Build with:  ./native/build.sh"
  echo "Or set backend = cpu in miner.ini"
fi

stop_existing_miners
mkdir -p "$MINER_ROOT/data"
rm -f "$LOCK_PATH"

WALLET="$(read_ini_value account address "$CONFIG_PATH" || true)"
if [[ -z "${WALLET// }" || "$WALLET" == "0x" ]]; then
  echo "XenBlocks Miner by Tony.x1  —  first-run setup  —  $PY_VERSION"
  echo "You will be asked for your EVM wallet (0x...). It is saved to miner.ini."
else
  if (( ${#WALLET} > 18 )); then
    WALLET_SHORT="${WALLET:0:10}...${WALLET: -6}"
  else
    WALLET_SHORT="$WALLET"
  fi
  echo "XenBlocks Miner by Tony.x1  —  $WALLET_SHORT  —  $BACKEND  —  $PY_VERSION"
fi
echo "Starting... (Ctrl+C to stop)  log: data/session.log"
echo ""

set +e
python3 "$MAIN_PY"
EXIT_CODE=$?
set -e

if (( EXIT_CODE != 0 )); then
  echo "Miner stopped (exit code $EXIT_CODE). Check data/session.log"
else
  echo "Miner stopped."
fi
exit "$EXIT_CODE"
