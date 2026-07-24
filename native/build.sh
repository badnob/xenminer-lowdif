#!/usr/bin/env bash
# Build xen_cuda shared library for Linux.
# Requires: cmake, g++/clang, CUDA Toolkit (nvcc), NVIDIA driver
#
# Usage:
#   chmod +x native/build.sh
#   ./native/build.sh
#   CMAKE_CUDA_ARCHITECTURES=86 ./native/build.sh   # e.g. RTX 30-series

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_DIR="$ROOT/engine"
BUILD_DIR="$ROOT/build"
JOBS="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)"

if ! command -v cmake >/dev/null 2>&1; then
  echo "ERROR: cmake not found. Install cmake and try again."
  exit 1
fi
if ! command -v nvcc >/dev/null 2>&1; then
  echo "WARNING: nvcc not on PATH. Ensure CUDA Toolkit is installed."
fi

CMAKE_ARGS=(-S "$ENGINE_DIR" -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release)
if [[ -n "${CMAKE_CUDA_ARCHITECTURES:-}" ]]; then
  CMAKE_ARGS+=("-DCMAKE_CUDA_ARCHITECTURES=${CMAKE_CUDA_ARCHITECTURES}")
fi

echo "Configuring: cmake ${CMAKE_ARGS[*]}"
cmake "${CMAKE_ARGS[@]}"
echo "Building with $JOBS jobs..."
cmake --build "$BUILD_DIR" --config Release -j"$JOBS"

# Report output (Linux: libxen_cuda.so)
shopt -s nullglob
FOUND=()
for f in \
  "$BUILD_DIR/bin/libxen_cuda.so" \
  "$BUILD_DIR/bin/xen_cuda.so" \
  "$BUILD_DIR/lib/libxen_cuda.so" \
  "$BUILD_DIR"/bin/libxen_cuda.*
do
  [[ -f "$f" ]] && FOUND+=("$f")
done
shopt -u nullglob

if (( ${#FOUND[@]} > 0 )); then
  echo "Build OK:"
  for f in "${FOUND[@]}"; do
    echo "  $f"
  done
else
  echo "Build finished; look under $BUILD_DIR/bin for the shared library."
fi
