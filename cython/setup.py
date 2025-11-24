"""
Cython 編譯配置檔

用於編譯 optimizer_core.pyx 為 C 擴充模組

使用方法:
    python setup.py build_ext --inplace
"""

from setuptools import setup, Extension
from Cython.Build import cythonize
import sys
import os
import platform

# 檢測編譯器類型
def is_msvc():
    """檢測是否使用 MSVC 編譯器"""
    if sys.platform != "win32":
        return False
    # 檢查是否在 MINGW/MSYS 環境
    if 'GCC' in platform.python_compiler().upper():
        return False
    if os.environ.get('MSYSTEM'):  # MINGW/MSYS 環境變數
        return False
    return True

# 編譯器優化選項
extra_compile_args = []
extra_link_args = []

if is_msvc():
    # Windows MSVC
    print("Detected compiler: MSVC")
    extra_compile_args = [
        "/O2",           # 最大優化
        "/GL",           # 全程式優化
        "/favor:INTEL64" # 針對 Intel64 優化
    ]
    extra_link_args = ["/LTCG"]  # 連結時程式碼產生

    # 嘗試啟用 AVX2（需要 CPU 支援）
    try:
        import cpuinfo
        if 'avx2' in cpuinfo.get_cpu_info().get('flags', []):
            extra_compile_args.append("/arch:AVX2")
            print("AVX2 support detected and enabled")
    except:
        # 如果無法檢測，保守起見不啟用 AVX2
        pass
else:
    # GCC/Clang (Linux/Mac/MinGW)
    print("Detected compiler: GCC/Clang")
    extra_compile_args = [
        "-O3",              # 最大優化
        "-march=native",    # 使用本機 CPU 所有指令集
        "-ffast-math",      # 快速數學運算
    ]

    # 嘗試啟用 LTO（連結時優化）
    # 注意：某些 MinGW 版本可能不支援 LTO
    if sys.platform != "win32":
        # Linux/Mac 通常支援 LTO
        extra_compile_args.append("-flto")
        extra_link_args.append("-flto")
    else:
        # MinGW 環境，保守處理
        print("MinGW environment detected, LTO disabled for compatibility")

extensions = [
    Extension(
        "optimizer_core",
        ["optimizer_core.pyx"],
        extra_compile_args=extra_compile_args,
        extra_link_args=extra_link_args,
    )
]

setup(
    name="optimizer_core",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",
            "boundscheck": False,      # 關閉邊界檢查
            "wraparound": False,        # 關閉負索引
            "cdivision": True,          # C 風格除法
            "initializedcheck": False,  # 關閉初始化檢查
            "nonecheck": False,         # 關閉 None 檢查
            "embedsignature": True,     # 嵌入函式簽名（方便偵錯）
            "profile": False,           # 關閉效能分析
            "linetrace": False,         # 關閉行追蹤
        },
        annotate=True  # 產生 HTML 註解檔，用於分析效能瓶頸
    ),
)
