#!/usr/bin/env bash
set -euo pipefail

python_bin="${PYTHON_BIN:-python}"

python_libdir="$("$python_bin" -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR") or "")')"
python_version="$("$python_bin" -c 'import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")')"

export PYO3_CROSS_PYTHON_VERSION="${PYO3_CROSS_PYTHON_VERSION:-$python_version}"

if [[ -n "$python_libdir" ]]; then
  export LD_LIBRARY_PATH="$python_libdir:${LD_LIBRARY_PATH:-}"
  export DYLD_FALLBACK_LIBRARY_PATH="$python_libdir:${DYLD_FALLBACK_LIBRARY_PATH:-}"
  export RUSTFLAGS="${RUSTFLAGS:-} -L $python_libdir"
fi

cargo test
