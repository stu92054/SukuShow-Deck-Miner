# Multi Optimizer 2 - Cython 加速版本

這是 `multi_optimizer_2.py` 的 Cython 優化版本，通過將核心搜尋演算法編譯為 C 擴充模組，實現 **10-50 倍效能提升**。

## 📊 效能對比

| 版本 | 搜尋時間 (估計) | 加速比 |
|------|----------------|--------|
| Python 原版 | 100-300 秒 | 1x |
| Cython 優化版 | 2-30 秒 | **10-50x** |

實際加速比取決於：
- CPU 效能
- 資料規模（TOP_N 大小）
- 剪枝效率

## 🚀 快速開始

### 1. 安裝依賴

```bash
# 安裝 Cython
pip install cython

# Windows 使用者需要安裝 Visual Studio Build Tools
# 下載地址: https://visualstudio.microsoft.com/downloads/
# 選擇 "Desktop development with C++" 工作負載

# Linux 使用者需要安裝 gcc
sudo apt-get install build-essential  # Debian/Ubuntu
# 或
sudo yum install gcc gcc-c++  # CentOS/RHEL

# macOS 使用者需要安裝 Xcode Command Line Tools
xcode-select --install
```

### 2. 編譯 Cython 模組

**Windows:**
```bash
cd cython
build_cython.bat
```

**Linux/macOS:**
```bash
cd cython
chmod +x build_cython.sh
./build_cython.sh
```

或手動編譯：
```bash
cd cython
python setup.py build_ext --inplace
```

編譯成功後會在 `cython/` 目錄產生以下檔案：
- Windows: `optimizer_core.cp3xx-win_amd64.pyd`
- Linux: `optimizer_core.cpython-3xx-x86_64-linux-gnu.so`
- macOS: `optimizer_core.cpython-3xx-darwin.so`

### 3. 執行優化版本

```bash
# 基本用法
python multi_optimizer_2_cython.py

# 使用指定配置檔
python multi_optimizer_2_cython.py --config config/member-alice.yaml

# 啟用偵錯模式（顯示詳細統計資訊）
python multi_optimizer_2_cython.py --debug
```

## 📁 檔案說明

```
SukuShow-Deck-Miner/
├── cython/
│   ├── optimizer_core.pyx          # Cython 核心搜尋模組
│   ├── setup.py                    # Cython 編譯配置
│   ├── build_cython.bat            # Windows 編譯腳本
│   └── build_cython.sh             # Linux/macOS 編譯腳本
├── multi_optimizer_2_cython.py     # Cython 優化版主程式
├── multi_optimizer_2.py            # Python 原版（保留用於對比）
├── docs/
│   └── README_CYTHON.md            # 本文件
└── benchmark_optimizer.py          # 效能對比測試腳本
```

## 🔧 核心優化技術

### 1. 靜態類型化
```cython
cdef int64_t mask1, mask2, mask3  # 使用 C 類型代替 Python int
cdef int64_t pt1, pt2, pt3        # 避免 Python 物件開銷
```

### 2. C 結構體
```cython
cdef struct Deck:
    int64_t mask
    int rank
    int64_t score
    int64_t pt
```
直接在記憶體中儲存資料，避免 Python 字典查找開銷。

### 3. nogil 區塊
```cython
cdef BestCombo search_best_combo(...) noexcept nogil:
    # 釋放 GIL，允許真正的平行計算
```

### 4. 編譯器指令
```cython
# cython: boundscheck=False    # 關閉邊界檢查
# cython: wraparound=False     # 關閉負索引
# cython: cdivision=True       # C 風格除法
```

### 5. 編譯器優化
- **Windows (MSVC)**: `/O2`, `/GL`, `/favor:INTEL64`
- **Linux/Mac (GCC)**: `-O3`, `-march=native`, `-ffast-math`

## 📈 效能分析

### 使用偵錯模式

```bash
python multi_optimizer_2_cython.py --debug
```

輸出範例：
```
=== Debug Statistics ===
Total iterations: 12,345,678
Conflicts detected: 1,234,567
Pruned combinations: 9,876,543
```

### 產生效能熱點圖

編譯時會自動產生 `optimizer_core.html`，用瀏覽器開啟可以查看：
- **黃色行**：Python 交互開銷較高
- **白色行**：純 C 程式碼，效能最優

## 🔍 故障排除

### 問題 1: 編譯失敗 - 找不到編譯器

**Windows:**
```
error: Microsoft Visual C++ 14.0 or greater is required
```
解決方案：安裝 [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/)

**Linux:**
```
error: command 'gcc' failed
```
解決方案：`sudo apt-get install build-essential python3-dev`

**macOS:**
```
xcrun: error: invalid active developer path
```
解決方案：`xcode-select --install`

### 問題 2: 匯入失敗

```python
ImportError: No module named 'optimizer_core'
```
解決方案：
1. 檢查是否成功編譯：
   - Windows: `dir cython\optimizer_core*.pyd`
   - Linux/macOS: `ls cython/optimizer_core*.so`
2. 重新編譯：
   - Windows: 執行 `cython\build_cython.bat`
   - Linux/macOS: 執行 `cython/build_cython.sh`

### 問題 3: 執行時崩潰

可能原因：
1. **記憶體不足**：減小 `TOP_N` 值
2. **資料格式錯誤**：檢查 JSON 檔案格式
3. **位元遮罩溢位**：卡牌數量超過 64 張（會在載入時觸發斷言）

### 問題 4: Python 版本不匹配

如果看到 `ImportError`，可能是編譯時的 Python 版本與執行時不同：
- 編譯的 `.pyd` 檔案名稱包含 Python 版本號（如 `cp312` = Python 3.12）
- 必須使用相同版本的 Python 執行
- 解決方法：使用編譯時的 Python 版本，或用目標 Python 版本重新編譯

## 🆚 與原版對比

| 特性 | Python 原版 | Cython 優化版 |
|------|------------|--------------|
| 效能 | 基準 1x | 10-50x |
| 記憶體使用 | 較高 | 較低 |
| 偵錯難度 | 容易 | 中等 |
| 安裝複雜度 | 簡單 | 需要編譯器 |
| 跨平台 | ✓ | ✓ (需編譯) |
| 程式碼可讀性 | 高 | 中 |

## 🎯 使用建議

### 何時使用 Cython 版本：
✅ `TOP_N >= 1000` 時
✅ 需要頻繁執行優化
✅ 有 C 編譯器環境
✅ 追求極致效能

### 何時使用 Python 版本：
✅ `TOP_N < 500` 時
✅ 一次性執行
✅ 無編譯器環境
✅ 需要快速偵錯/修改程式碼

## 📝 配置說明

在 `multi_optimizer_2_cython.py` 中配置：

```python
CHALLENGE_SONGS = [
    ("405119", "02"),
    ("405121", "02"),
    ("405107", "02"),
]

TOP_N = 5000  # 每首歌保留的卡組數量
```

**TOP_N 建議值：**
- **快速測試**: 500-1000
- **平衡模式**: 3000-5000
- **完整搜尋**: 10000+（需要更多時間和記憶體）

---

**效能提示**：首次執行時，Python 版本和 Cython 版本都會經歷資料載入階段（相同時間）。效能差異主要體現在**搜尋階段**，這也是 Cython 優化的重點。
