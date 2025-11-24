# 項目架構分析文檔

## 1. 整體架構概述

### 核心流程
配置讀取 → 卡組生成 → 批次模擬 → PT計算 → 結果保存

### 專案目錄結構
```
SukuShow-Deck-Miner/
├── src/                 # 源代碼
│   ├── core/           # 核心遊戲邏輯
│   │   ├── Simulator_core.py
│   │   ├── SkillResolver.py
│   │   ├── RChart.py
│   │   ├── RCardData.py
│   │   ├── RDeck.py
│   │   ├── RLiveStatus.py
│   │   └── RSkill.py
│   ├── deck_gen/       # 卡組生成
│   │   ├── DeckGen.py
│   │   └── DeckGen2.py
│   ├── config/         # 配置管理
│   │   ├── config_manager.py
│   │   └── CardLevelConfig.py
│   └── utils/          # 工具函數
│       ├── recalculate_pt.py
│       ├── json2csv.py
│       └── log_tool.py
├── cython/              # Cython 加速模組
│   ├── optimizer_core.pyx
│   ├── setup.py
│   ├── build_cython.bat
│   └── build_cython.sh
├── docs/                # 文檔
│   ├── ARCHITECTURE_CN.md (本文檔)
│   ├── README_zh-tw.md
│   ├── README_zh-cn.md
│   ├── README_ja-jp.md
│   ├── README_CYTHON.md
│   └── GUILD_MEMBER_GUIDE.md
├── config/              # YAML 配置檔案
├── Data/                # 遊戲數據
│   ├── bytes/          # 譜面二進位檔案
│   └── csv/            # 譜面 CSV 檔案
├── log/                 # 模擬結果輸出（按成員隔離）
├── temp/                # 臨時檔案（按成員隔離）
├── output/              # 其他輸出
├── MainBatch.py         # 主程式：批次處理（根目錄）
├── MainSingle.py        # 主程式：單一卡組測試
├── multi_song_optimizer.py      # 多歌曲最佳化（第一代）
├── multi_optimizer_2.py          # 多歌曲最佳化（第二代）
├── multi_optimizer_2_cython.py   # Cython 加速版本（推薦）
└── README.md            # 主文檔
```

### 主要模塊職責

#### 執行腳本（根目錄）
- **MainBatch.py**: 批次處理主程序（單歌曲最佳化）
- **MainSingle.py**: 單一卡組模擬測試
- **multi_song_optimizer.py**: 多歌曲卡組最佳化（第一代）
- **multi_optimizer_2.py**: 多歌曲卡組最佳化（第二代）
- **multi_optimizer_2_cython.py**: 第二代 Cython 加速版本（推薦）

#### 核心遊戲邏輯 (src/core/)
- **Simulator_core.py**: 遊戲模擬引擎
- **SkillResolver.py**: 技能處理與效果計算
- **RChart.py**: 譜面數據處理
- **RCardData.py**: 卡牌數據定義
- **RDeck.py**: 卡組數據結構
- **RLiveStatus.py**: 遊戲狀態管理
- **RSkill.py**: 技能定義

#### 卡組生成 (src/deck_gen/)
- **DeckGen.py**: 第一代卡組生成器
- **DeckGen2.py**: 第二代卡組生成器（支持雙卡）

#### 配置管理 (src/config/)
- **config_manager.py**: YAML 配置讀取、成員隔離
- **CardLevelConfig.py**: 卡牌練度管理（傳統方式）

#### 工具函數 (src/utils/)
- **recalculate_pt.py**: PT 值重新計算（無需重新模擬）
- **json2csv.py**: JSON 轉 CSV 轉換工具
- **log_tool.py**: 日誌工具

#### Cython 加速 (cython/)
- **optimizer_core.pyx**: Cython 原始碼
- **setup.py**: Cython 編譯配置
- **build_cython.bat**: Windows 編譯腳本
- **build_cython.sh**: Linux/Mac 編譯腳本

---

## 2. Cython 加速版本

### 效能提升
Cython 版本的 `multi_optimizer_2_cython.py` 相較於純 Python 版本有顯著的效能提升：
- 計算速度提升：C 語言級別的最佳化，執行效率更高
- 記憶體使用優化：靜態型別宣告減少 Python 物件開銷
- 適用場景：多歌曲卡組最佳化、大規模公會卡池計算

### 編譯方式

**Windows:**
```bash
cd cython
build_cython.bat
```

**Linux/Mac:**
```bash
cd cython
bash build_cython.sh
```

編譯成功後會生成：
- `optimizer_core.c` - Cython 產生的 C 代碼（編譯後可刪除）
- `optimizer_core.*.pyd` (Windows) 或 `optimizer_core.*.so` (Linux/Mac) - 編譯模組
- `optimizer_core.html` - Cython 註解檔案（可選）

### 使用方式

```bash
# 使用 Cython 加速版本
python multi_optimizer_2_cython.py

# 或使用純 Python 版本
python multi_optimizer_2.py
```

**注意事項：**
- 編譯產物（.c, .pyd, .so, .html, build/）不應提交到 Git
- 每次修改 `optimizer_core.pyx` 後需重新編譯
- 編譯需要安裝 Cython 和 C 編譯器（Windows 需要 MinGW 或 MSVC）

詳細說明請參考 [README_CYTHON.md](README_CYTHON.md)

---

## 3. 卡牌練度更新流程

### 配置優先級 (從高到低)
1. 命令行 --config config/member-xxx.yaml
2. 環境變數 CONFIG_FILE=config/member-xxx.yaml
3. config/default.yaml
4. CardLevelConfig.py 中的全局設定

### YAML配置格式
```yaml
card_ids:
  - 1011501
  
card_levels:
  1011501: [120, 10, 10]  # [卡牌等級, C位技能等級, 普通技能等級]
  1021701: [140, 11, 11]  # 只設定未滿練的卡
  
fan_levels:
  1011: 5   # 角色ID -> 粉絲等級(1-10)
  1021: 3
```

### 卡牌練度讀取路徑
```
src/config/config_manager.py::get_card_levels()
  ↓
src/config/CardLevelConfig.py::convert_deck_to_simulator_format()
  ↓ (應用自定義練度，優先於全局CARD_CACHE)
src/core/Simulator_core.py (用於模擬)
```

### 粉絲等級對應加成
- Level 1: 0%, Level 2: 20%, Level 3: 27.5%
- Level 4: 35%, Level 5: 42.5%, Level 6: 50%
- Level 7: 55%, Level 8: 60%, Level 9: 65%
- Level 10: 70%

### PT計算過程
```
遊戲模擬分數 × BONUS_SFL × LIMITBREAK_BONUS = 最終PT值
```

其中 BONUS_SFL = (1 + Σ粉絲等級加成) × 歌唱人數補正

### 背水卡片 (DEATH_NOTE)
在 CardLevelConfig.py 中配置：
```python
DEATH_NOTE = {
    1041513: 10,   # 卡片ID -> 目標血線
    1041901: 25,
}
```
程式會在開局自動掛機MISS到血線，然後保持All Perfect。

---

## 4. 卡池計算邏輯

### 卡池來源
**YAML配置** (config/member-{name}.yaml)
- 直接列表: card_ids: [1011501, 1021701, ...]
- 這是推薦的配置方式，支援成員隔離和版本控制

### 卡組生成 (DeckGen2.py)

**核心邏輯:**
1. 生成角色分布 (0-3個角色雙卡, 其他單卡)
2. 對每個分布組合卡片選擇
3. 篩選滿足技能要求的卡組
4. 檢查卡片衝突 (CARD_CONFLICT_RULES)

**必須技能 (MainBatch.py 第500-509行):**
- DeckReset (洗牌)
- ScoreGain (分數)
- VoltagePointChange (電)
- NextAPGainRateChange (分加成)
- NextVoltageGainRateChange (電加成)

**卡片衝突規則:**
```python
CARD_CONFLICT_RULES = {
    1031530: {1041513, 1042515, ...},  # IDOME帆 與這些卡片衝突
}
```

---

## 5. 最終輸出格式與位置

### 目錄結構

**YAML模式 (推薦):**
```
log/{member_name}/simulation_results_{music_id}_{difficulty}.json
temp/{member_name}/{timestamp}/temp_{music_id}/temp_batch_001.json
```

**傳統模式:**
```
log/simulation_results_{music_id}_{difficulty}.json
temp_{music_id}/temp_batch_001.json
```

### 結果JSON格式

最終結果 (log/ 中):
```json
[
  {
    "deck_card_ids": [1011501, 1052506, 1051506, 1052901, 1041517, 1041802],
    "center_card": 1041802,
    "score": 3665412517,
    "pt": 32457227838
  }
]
```

按PT值降序排列，重複卡組只保留最高分。

### 輸出邏輯 (MainBatch.py::save_simulation_results)
1. 去重：相同卡組只保留最高分
2. 排序：按PT降序
3. PT計算：Score × BONUS_SFL × LIMITBREAK_BONUS
4. 合併：與既有結果合併 (如果需要)
5. 寫入JSON

---

## 6. 緩存與增量更新機制

### 快取系統

**臨時檔案管理：**
- 臨時檔案存放在 `temp/{member_name}/{timestamp}/` 目錄
- 程序結束時自動合併所有臨時批次檔案
- 建議定期手動清理過期的臨時檔案

**效能最佳化：**
- Cython 版本提供 C 語言級別的執行效能
- 多歌曲最佳化支援平行處理和批次計算

### 增量更新機制

**A. 練度更新 (無需重新模擬)**
編輯 YAML 中的 card_levels，重新運行：
```bash
python MainBatch.py --config config/member-alice.yaml
```
卡組生成不變，只在模擬時應用新練度。

**B. 粉絲等級更新 (無需重新模擬)**
使用 recalculate_pt.py 直接重計算：
```python
FAN_LEVELS = {1011: 5, 1021: 3, ...}
SEASON_MODE = 'sukushow'
python recalculate_pt.py
```
讀取既有結果，直接重新計算PT，不需要卡組模擬。

**C. 批次管理**
- BATCH_SIZE = 1,000,000 (每100萬結果保存一個臨時文件)
- 臨時文件位置：temp_{music_id}/temp_batch_XXX.json
- 程式結束前自動合併所有臨時文件

### 配置隔離

不同成員的輸出自動隔離：
```
config/member-alice.yaml → log/alice/
config/member-bob.yaml → log/bob/
config/default.yaml → log/
```

臨時文件也按成員隔離 (temp/{member_name}/{timestamp}/)，
支援多個成員的並行計算。

---

## 7. 關鍵文件位置速查

| 任務 | 文件 | 說明 |
|-----|------|------|
| 設定卡池、粉絲等級、練度 | config/member-{name}.yaml | 推薦方式 |
| 背水卡片配置 | CardLevelConfig.py | DEATH_NOTE |
| 卡牌默認練度 | CardLevelConfig.py | default_card_level |
| 卡組篩選規則 | DeckGen2.py | CARD_CONFLICT_RULES |
| 必須技能配置 | MainBatch.py | mustskills_all |
| 粉絲等級計算 | MainBatch.py | BONUS_SFL計算 |
| 結果保存邏輯 | MainBatch.py | save_simulation_results |
| PT重計算 | recalculate_pt.py | 無需重新模擬 |
| JSON轉CSV | json2csv.py | 結果格式轉換 |
| 日誌工具 | log_tool.py | 日誌處理 |
| Cython編譯 | build_cython.bat / .sh | Windows / Linux編譯 |

---

## 8. 典型工作流程

### 場景1: 添加新的公會成員
```bash
copy config\member-example.yaml config\member-alice.yaml
# 編輯配置：設定卡池、粉絲等級、未滿練卡牌
python MainBatch.py --config config/member-alice.yaml
# 結果在 log/alice/ 中
```

### 場景2: 更新粉絲等級
編輯 config/member-alice.yaml，修改 fan_levels，重新運行。

### 場景3: 重新計算PT (無需重新模擬)
編輯 src/utils/recalculate_pt.py，修改 FAN_LEVELS，運行：
```bash
python src/utils/recalculate_pt.py
```

### 場景4: 清理臨時文件
```bash
# 手動刪除過期的臨時目錄
rm -rf temp/*/
rm -rf tmp_fingerprints/

# 清理 Cython 編譯產物（在 cython/ 目錄中）
cd cython
rm -f optimizer_core.c optimizer_core.*.pyd optimizer_core.html
rm -rf build/
```

---

## 9. 數據流圖

```
YAML配置 / src/config/CardLevelConfig.py
    ↓
src/config/config_manager.py (讀取、驗證)
    ↓
MainBatch.py
    ├─ 讀取卡池
    ├─ src/deck_gen/DeckGen2.py 生成卡組
    ├─ src/core/Simulator_core.py 模擬每個卡組
    │   ├─ 讀取卡牌練度 (YAML 優先)
    │   ├─ 應用技能效果
    │   └─ 計算得分
    ├─ 保存臨時結果 (temp_batch_XXX.json)
    └─ 去重、排序、計算PT → 最終結果JSON

src/utils/recalculate_pt.py (無需重新模擬)
    ├─ 讀取既有結果
    ├─ 重新計算 BONUS_SFL
    └─ 更新PT值
```

---

## 10. 專案維護最佳實踐

### 檔案管理

**應該提交到 Git 的檔案：**
- 所有 `.py` 源代碼
- `.pyx` Cython 原始碼
- 配置範例檔案（`config/*-example.yaml`）
- 文檔檔案（`README*.md`, `ARCHITECTURE_CN.md` 等）
- 編譯腳本（`build_cython.bat`, `build_cython.sh`, `setup.py`）
- `.gitignore` 和其他專案配置

**不應該提交到 Git 的檔案（已在 .gitignore 中）：**
- Cython 編譯產物：`*.c`, `*.pyd`, `*.so`, `*.html`, `build/`
- Python 快取：`__pycache__/`, `*.pyc`, `*.pyo`
- 個人配置：`config/member-*.yaml`（除了 example）
- 臨時檔案：`temp/`, `tmp_fingerprints/`
- 輸出結果：`log/*/`, `output/`

### 定期清理

**每週建議清理：**
```bash
# 清理 Cython 編譯產物
cd cython
rm -f optimizer_core.c optimizer_core.*.pyd optimizer_core.*.so optimizer_core.html
rm -rf build/
cd ..

# 清理 Python 快取
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# 手動清理過期的 temp/ 和 log/ 目錄
```

### 效能最佳化建議

1. **使用 Cython 版本**：對於多歌曲最佳化，優先使用 `multi_optimizer_2_cython.py`
2. **批次大小調整**：根據記憶體大小調整 `BATCH_SIZE`（預設 1,000,000）
3. **平行處理**：利用多核心 CPU 進行平行計算
4. **快取管理**：定期清理過期快取，避免磁碟空間不足

### 開發流程

**添加新功能：**
1. 在 `dev` 分支開發
2. 測試功能正常運作
3. 更新相關文檔（README、ARCHITECTURE_CN.md）
4. 提交到 Git 並推送

**修復錯誤：**
1. 重現問題
2. 修復並測試
3. 更新測試案例（如適用）
4. 提交修復

**版本發布：**
1. 確保所有測試通過
2. 更新版本號（如適用）
3. 合併到 `main` 分支
4. 標記版本標籤

### 多人協作注意事項

1. **配置隔離**：每個成員使用獨立的 `config/member-{name}.yaml`
2. **輸出隔離**：輸出自動按成員名稱隔離到 `log/{member_name}/`
3. **並行計算**：臨時檔案也會按成員和時間戳隔離，支援同時運行
4. **Git 衝突**：避免修改他人的配置檔案，只修改自己的配置

### 疑難排解

**記憶體不足：**
- 減小 `BATCH_SIZE`
- 使用 Cython 版本
- 清理過期快取

**Cython 編譯失敗：**
- 確認已安裝 Cython：`pip install Cython`
- Windows 需要安裝 MinGW 或 MSVC
- Linux/Mac 需要 gcc

**結果不正確：**
- 檢查配置檔案中的卡牌練度、粉絲等級
- 確認卡池設定正確
- 查看 log 檔案中的錯誤訊息

---

## 11. 版本歷史

- **v2.0**: 新增 Cython 加速版本、多歌曲最佳化第二代
- **v1.5**: 完善 YAML 配置系統、成員隔離機制
- **v1.0**: 基礎批次模擬、卡組生成功能

