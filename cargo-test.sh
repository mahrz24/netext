#/bin/bash
export LD_LIBRARY_PATH="$HOME/Library/Application_Support/uv/python/cpython-3.10.14-macos-aarch64-none/lib":$LD_LIBRARY_PATH
export RUSTFLAGS="-L $HOME/Library/Application_Support/uv/python/cpython-3.10.14-macos-aarch64-none/lib"
export PYO3_CROSS_PYTHON_VERSION=3.10
DYLD_FALLBACK_LIBRARY_PATH="$HOME/Library/Application_Support/uv/python/cpython-3.10.14-macos-aarch64-none/lib" cargo test
