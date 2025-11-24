#!/bin/bash
# Cython 模組編譯腳本 (Linux/macOS)
#
# 使用方法：
#   chmod +x build_cython.sh
#   ./build_cython.sh

set -e  # 遇到錯誤立即退出

echo "========================================"
echo "Cython 模組編譯腳本"
echo "========================================"
echo ""

# 檢查 Python 是否可用
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "[ERROR] Python not found"
        echo "Please install Python 3"
        exit 1
    fi
    PYTHON=python
else
    PYTHON=python3
fi

echo "[OK] Python found: $($PYTHON --version)"

# 檢查 Cython 是否已安裝
if ! $PYTHON -c "import Cython" &> /dev/null; then
    echo "[WARN] Cython not installed"
    echo "Installing Cython..."
    $PYTHON -m pip install cython
fi

echo "[OK] Cython available"

# 檢查編譯器
if command -v gcc &> /dev/null; then
    echo "[OK] GCC compiler found"
elif command -v clang &> /dev/null; then
    echo "[OK] Clang compiler found"
else
    echo "[ERROR] No C compiler found"
    echo ""
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "Install with: sudo apt-get install build-essential python3-dev"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Install with: xcode-select --install"
    fi
    exit 1
fi

# 清理舊的編譯檔案
echo ""
echo "Cleaning old build files..."
rm -rf build
rm -f optimizer_core.c
rm -f optimizer_core.*.so
rm -f optimizer_core.*.pyd

# 編譯 Cython 模組
echo ""
echo "Compiling Cython module..."
$PYTHON setup.py build_ext --inplace

# 檢查是否產生了 .so 或 .pyd 檔案
if [ -f optimizer_core.*.so ]; then
    echo ""
    echo "========================================"
    echo "[SUCCESS] Compilation completed!"
    echo "========================================"
    echo ""
    echo "Generated files:"
    ls -lh optimizer_core.*.so
elif [ -f optimizer_core.*.pyd ]; then
    echo ""
    echo "========================================"
    echo "[SUCCESS] Compilation completed!"
    echo "========================================"
    echo ""
    echo "Generated files:"
    ls -lh optimizer_core.*.pyd
else
    echo "[ERROR] No extension module generated (.so or .pyd)"
    exit 1
fi
echo ""
echo "You can now run:"
echo "  $PYTHON multi_optimizer_2_cython.py"
echo ""
echo "Note: Run from project root directory"
echo ""
