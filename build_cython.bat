@echo off
REM Cython 模組編譯腳本 (Windows)
REM
REM 使用方法：
REM   雙擊執行或在命令列執行: build_cython.bat

echo ========================================
echo Cython Module Build Script
echo ========================================
echo.

REM 檢查 Python 是否可用
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH
    echo Please install Python or add it to PATH
    pause
    exit /b 1
)

echo [OK] Python found

REM 檢查 Cython 是否已安裝
python -c "import Cython" >nul 2>&1
if errorlevel 1 (
    echo [WARN] Cython not installed
    echo Installing Cython...
    pip install cython
    if errorlevel 1 (
        echo [ERROR] Failed to install Cython
        pause
        exit /b 1
    )
)

echo [OK] Cython available

REM 清理舊的編譯檔案
echo.
echo Cleaning old build files...
if exist build rmdir /s /q build
if exist optimizer_core.c del optimizer_core.c
if exist optimizer_core.*.pyd del optimizer_core.*.pyd
if exist optimizer_core.*.so del optimizer_core.*.so

REM 編譯 Cython 模組
echo.
echo Compiling Cython module...
python setup.py build_ext --inplace

if errorlevel 1 (
    echo.
    echo [ERROR] Compilation failed
    echo.
    echo Common issues:
    echo   1. Missing Visual Studio Build Tools
    echo      Download from: https://visualstudio.microsoft.com/downloads/
    echo      Select "Desktop development with C++" workload
    echo.
    echo   2. Python development headers missing
    echo      Reinstall Python with "Development" option
    echo.
    pause
    exit /b 1
)

REM 檢查是否產生了 .pyd 檔案
if not exist optimizer_core.*.pyd (
    echo [ERROR] No .pyd file generated
    pause
    exit /b 1
)

echo.
echo ========================================
echo [SUCCESS] Compilation completed!
echo ========================================
echo.
echo Generated files:
dir optimizer_core.*.pyd
echo.
echo You can now run:
echo   python multi_optimizer_2_cython.py
echo.
echo Or run the benchmark:
echo   python benchmark_optimizer.py
echo.
pause
