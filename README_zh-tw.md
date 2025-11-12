# SukuShow Deck Miner

適用於 [Link！Like！LoveLive！](https://www.lovelive-anime.jp/hasunosora/system/) (リンクラ) 中的音遊模式 School Idol Show (スクショウ) 的卡組模擬器和優化求解器。

---

**[English](README.md) | [简体中文](README_zh-cn.md) | [繁體中文](README_zh-tw.md) | [日本語](README_ja-jp.md)**

---

## 🚀 快速開始

### 🛞 環境需求

- **Python 版本**:
  由於程式碼中使用了 `match ... case ...` 語法，專案**最低要求 Python 3.10**。
  **為了獲得最佳效能，強烈推薦使用 Python 3.11 或更高版本執行。**

- **依賴套件**:

  - `PyYAML` - 用於解析 YAML 設定檔
  - `tqdm` - 用於在批次模擬時顯示進度條

  可透過以下指令安裝：

  ```bash
  pip install PyYAML tqdm
  ```

- **使用 PyPy 進行效能優化**（可選但強烈推薦）：

  使用 PyPy 代替標準 CPython 可獲得顯著的效能提升（某些情況下可達 **3-5 倍加速**）：

  1. 下載並安裝 [PyPy 3.10+](https://www.pypy.org/download.html)
  2. 使用 PyPy 的 pip 安裝依賴套件：
     ```bash
     pypy -m pip install PyYAML tqdm sortedcontainers
     ```
     **注意**：`sortedcontainers` 僅在 PyPy 下需要，標準 CPython 不需要。
  3. 使用 PyPy 執行模擬器：
     ```bash
     pypy MainBatch.py
     # 或
     pypy MainSingle.py
     ```

  **注意**：PyPy 的 JIT 編譯器為計算密集型模擬提供了出色的效能，但在預熱階段可能會使用更多記憶體。

---

## 🎮 使用方式

### ▶ 執行核心腳本

根據需求選擇並執行以下檔案：

- `MainBatch.py`: **批次模擬**。輸入卡池與課題曲，自動生成卡組並進行批次模擬，以尋找**單曲最優解**。
- `MainSingle.py`: **單次模擬**。輸入特定卡組與課題曲，進行單次模擬並輸出詳細模擬過程。
- `multi_song_optimizer.py`: **多曲優化**。輸入多首課題曲，利用 `MainBatch.py` 生成的卡組得分資料，尋找**多曲目的最優解**。

### ⚙ 個性化設定

#### 🆕 配置檔案系統（推薦用於公會成員計算）

**對於需要為多位公會成員進行模擬的使用者**，我們提供了基於 YAML 的配置系統，可輕鬆切換不同成員的配置：

**快速開始：**

1. **為每位公會成員創建配置檔案：**
   ```bash
   copy config\member-example.yaml config\member-yourname.yaml
   ```

2. **編輯配置檔案**以匹配該成員的卡池、粉絲等級和卡牌練度：
   ```yaml
   # config/member-yourname.yaml

   songs:
     - music_id: "405117"
       difficulty: "02"        # 01=Normal, 02=Hard, 03=Expert, 04=Master
       mastery_level: 50

     - music_id: "405118"      # 可以添加多首歌曲
       difficulty: "03"

   card_ids:
     - 1011501  # 列出該成員擁有的所有卡牌
     - 1021701
     # ...

   fan_levels:
     1011: 5    # 該成員的粉絲等級
     1021: 3
     # ...

   card_levels:
     # 覆寫特定卡牌練度（如果未滿練）
     # 1021701: [130, 10, 10]  # LR梢 未滿練
   ```

3. **使用配置執行模擬：**
   ```bash
   python MainBatch.py --config config/member-yourname.yaml
   ```

4. **結果自動保存到隔離的目錄：**
   ```
   # 最終結果（永久保存）
   log/
   └── {member_name}/              # 如 alice/ (使用 member-*.yaml 時)
       └── simulation_results_405117_02.json

   # 臨時檔案（執行過程中，完成後可清理）
   temp/
   └── {member_name}/              # 與 log/ 保持一致
       └── {timestamp}/            # 執行時間戳
           └── temp_405117/        # 各歌曲獨立目錄
               └── temp_batch_001.json
   ```

**優點：**
- ✅ **輕鬆切換** - 快速為不同公會成員執行模擬
- ✅ **無需修改程式碼** - 所有配置都在 YAML 檔案中
- ✅ **隔離輸出** - 每次執行創建獨立目錄（避免檔案衝突）
- ✅ **Git 友善** - 配置檔案可提交到版本控制

**配置優先順序：**
1. 命令列：`python MainBatch.py --config config/member1.yaml`
2. 環境變數：`set CONFIG_FILE=config/member1.yaml`（Windows）或 `export CONFIG_FILE=config/member1.yaml`（Linux）
3. 預設：`config/default.yaml`（如果存在，已被 git 忽略）
4. CardLevelConfig.py 與程式內設定（舊方法，向下相容）

**注意：** `config/default.yaml` 已被 gitignore。請使用 `config/default-example.yaml` 作為範本創建自己的 `config/default.yaml`。

**公會計算工作流程範例：**
```bash
# 為成員 Alice 計算
python MainBatch.py --config config/member-alice.yaml

# 為成員 Bob 計算
python MainBatch.py --config config/member-bob.yaml

# 結果位於不同目錄：
# log/alice/simulation_results_*.json
# log/bob/simulation_results_*.json
#
# 臨時檔案：
# temp/alice/{timestamp}/temp_*/
# temp/bob/{timestamp}/temp_*/
```

詳見 `config/member-example.yaml` 完整範例。

---

#### 傳統方式：直接修改檔案

也可以根據需要直接調整 Python 檔案中的設定：

- `CardLevelConfig.py`: 設定所有卡牌的**預設等級**和**個別卡牌的等級** (`CARD_CACHE`)。預設情況下，所有卡牌均設定為滿級。
利用 `DEATH_NOTE` 設定背水卡牌的掛機血線。卡組中存在多張設定了血線的背水卡時，以最低血線為準。
- `DeckGen2.py`: 負責卡組生成邏輯。可以在此設定卡牌衝突規則 (`CARD_CONFLICT_RULES`)、卡組技能條件 (`check_skill_tags`) 等約束限制，以實現卡組生成時的進一步剪枝優化。
- `MainBatch.py`: **批次模擬的主要設定檔。** 詳見下方設定指南。
- `MainSingle.py`: 設定單次模擬的卡組與曲目，可在 `logging.basicConfig` 中設定模擬過程的輸出詳細程度。
  - INFO: 僅輸出卡組與模擬結果
  - DEBUG: 輸出詳細的技能使用記錄
  - TIMING: 輸出包括所有 Note 與 CD 結束時間點的日誌，Note 會刷屏所以建議將日誌輸出至文字檔案檢視
- `Simulator_core.py`: 可以透過修改程式碼調整批次模擬時的音遊策略，只要你知道自己在做什麼。
在這裡進行的修改只影響批次模擬，單次模擬的音遊策略需要在 `MainSingle.py` 中另行修改。

### 📘 MainBatch.py 設定指南

`MainBatch.py` 執行前需要手動設定。以下是需要修改的主要部分：

#### 1. **卡池設定** (約第 157 行)
定義要包含在模擬中的卡牌：

```python
card_ids = [
    1011501,  # 範例卡牌ID
    1033514,
    # 在此新增你擁有的卡牌ID
]
```

#### 2. **歌曲設定** (約第 208 行)
設定一首或多首要模擬的歌曲：

```python
SONGS_CONFIG = [
    {
        "music_id": "405305",        # 歌曲ID（從遊戲資料中查詢）
        "difficulty": "02",          # 難度："01"=Normal, "02"=Hard, "03"=Expert, "04"=Master
        "mustcards_all": [],         # 必須包含的所有卡牌（卡牌ID清單）
        "mustcards_any": [],         # 至少包含其中一張的卡牌
        "center_override": None,     # 覆寫C位角色（None = 使用歌曲預設）
        "color_override": None,      # 覆寫歌曲顏色：1=Smile, 2=Pure, 3=Cool（None = 使用歌曲預設）
    },
    # 根據需要新增更多歌曲
]
```

#### 3. **季度粉絲等級設定** (約第 285 行)
設定粉絲等級以準確計算 Grandprix Pt：

```python
# 季度模式：'sukushow'（僅歌唱成員）或 'sukuste'（全部成員）
SEASON_MODE = 'sukushow'

# 設定每個角色的粉絲等級（1-10）
FAN_LEVELS: dict[int, int] = {
    1011: 10,  # 角色ID -> 粉絲等級
    1021: 8,
    1022: 10,
    # 新增全部12個角色及其粉絲等級
    # 未指定時預設為10
}
```

**粉絲等級加成表：**
- 等級 1: 0%
- 等級 2: 20%
- 等級 3: 27.5%
- 等級 4: 35%
- 等級 5: 42.5%
- 等級 6: 50%
- 等級 7: 55%
- 等級 8: 60%
- 等級 9: 65%
- 等級 10: 70%（預設）

#### 4. **DR剪枝設定** (約第 196 行)
控制是否移除非C位角色的DR卡：

```python
ENABLE_DR_PRUNING = False  # 推薦：False（讓演算法自動決定）
# True:  移除非C位DR卡 + 強制使用C位DR（舊行為）
# False: 保留所有DR卡，讓演算法決定最優使用方式
```

#### 5. **技能要求** (約第 236 行)
指定所有生成的卡組必須包含的技能類型：

```python
mustskills_all = [
    SkillEffectType.DeckReset,  # 洗牌（DR）
    SkillEffectType.ScoreGain,  # 分數提升
    # 新增其他必需的技能類型
]
```
---

## ⚠️ **重要警告：CPU 佔用與穩定性** ⚠️

> [!CAUTION]
> ⚠ **批次模擬預設會呼叫所有可用的 CPU 執行緒執行，且執行時 CPU 佔用率通常高達 99% 以上。** ⚠
> **存在 i5-13600KF 在滿負荷執行一段時間後藍屏的案例。**
>
> 如對 CPU 體質或散熱沒有信心，**強烈建議在批次模擬前採取以下措施**：
>
> - 對 CPU 進行**升壓/降頻**操作。
> - **減少模擬器呼叫的執行緒數**。
>
> 保險起見，可將 `MainBatch.py` 檔案中的 `num_processes = os.cpu_count() or 1` 這行程式碼修改為 `num_processes = 12`。其中 `12` 可根據實際執行緒數替換為**小於 CPU 執行緒數的其他值**，降低效能壓力。

- **資源考量**：理論上可以把所有卡牌都放進備選卡池進行批次模擬。然而，這需要**極其強大的 CPU 效能、巨大的記憶體容量和充裕的模擬時間**。由於可能出現不可預知的問題，**不建議**這樣做。
- **記憶體堆積**：儘管批次模擬中卡組生成與模擬環節是流水線作業，模擬結果也會分批暫存至硬碟，但**卡越多模擬器吃的記憶體越多**。因此，請勿在備選卡池中放入過多卡牌，以免造成記憶體溢位。

---

## 📝 備註與潛在誤差

- 本模擬器採用**窮舉法**生成卡組進行模擬。所找到的「單曲最優解」僅在**給定卡池範圍、卡牌練度、譜面難度、音遊策略**下成立。調整卡池、練度或譜面難度後，可能會得到不同的最優解。預設採取的音遊策略是：
  1. 在譜面中的完全準確時機打出 **All Perfect**
  2. 若卡組中有在 `DEATH_NOTE` 中設定了血線的背水卡，當前血量高於背水血線時自動掛機，僅在血量低於血線時保持 All Perfect。
- 同理，多曲最優解也會隨卡池、練度、譜面難度、音遊策略等因素而變化。
- 模擬器能夠有效**節約實戰模擬的時間**，但很難一發入魂找到真正的**絕對最優卡組**。需要對卡牌效果具有一定理解才能充分發揮模擬器的作用。
- **最優卡組 ≠ 最優策略**。卡時間點逐幀凹分或是根據技能條件/效果卡練度的操作請各顯神通。
- 在計算 **Grandprix Pt** 時，季度粉絲等級加成會根據 `MainBatch.py` 中的 `FAN_LEVELS` 設定**動態計算**。如果未指定，預設所有成員為10級（相當於舊版預設值6.6）。C 位成員（如果有）的解放倍率則會按其技能或 SP 等級進行換算。
- 由於模擬器**並非 1:1 完全複刻遊戲邏輯**，模擬得分與實戰不一致是正常現象。

### ⏰ 可能的誤差來源

**邏輯不一致**
未能完全複刻遊戲原始邏輯，導致技能處理、分數計算的結果與實戰存在較大出入。
若能提供**實戰錄影、卡組練度、歌曲 Master Lv. 資訊**，我可能會嘗試核對一下是哪裡不一致進行修復。

**時間處理誤差**
由於**浮點數精度問題**或是其他神祕原因（例如遊戲中可能是每幀處理一次所有事件，而非基於每個事件的準確時間點處理）實際技能發動時機可能與模擬存在數十毫秒的偏差。極端情況下曾出現過模擬中在Fever開始前打出的卡牌在實戰中晚於Fever開始才打出，導致電加成被Fever開始時觸發的C位技能消耗的案例。

**判定時機**
模擬器只會按譜面中的 `just` 時間點處理 note，無論判定是否為 Perfect。
然而實戰中的 note 判定存在**時間視窗**，在 AP 不足時會導致實戰的技能發動時機略微提前/延後，極端情況下可能導致卡牌打出次數比模擬多/少一次。
對於和 Fever 開始/結束時點在同一拍上的 note，實戰凹一下都有機會吃到 Fever 的雙倍 Voltage。但 note 在譜面中的記錄的時間點一般比 Fever 切換的時間點多兩位小數，導致模擬時不一定會在 Fever 內結算得分。
下表為 Ver.4.0.1 時的判定時機，僅供參考：

<table>
  <thead>
    <tr>
      <th rowspan="2"><b>判定</b></th>
      <th colspan="3"><b>判定時機 (ms)</b></th>
    </tr>
    <tr>
      <th><i>Single / Hold</i></th>
      <th><i>Flick</i></th>
      <th><i>Trace</i></th>
    </tr>
  </thead>
  <tbody align="center">
    <tr>
      <td>Perfect</td>
      <td>0 ~ ±40</td>
      <td>0 ~ ±70</td>
      <td>0 ~ ±70</td>
    </tr>
    <tr>
      <td>Great</td>
      <td>±40 ~ ±70</td>
      <td>±70 ~ ±100</td>
      <td>－</td>
    </tr>
    <tr>
      <td>Good</td>
      <td>±70 ~ ±100</td>
      <td>點擊但未上滑</td>
      <td>－</td>
    </tr>
    <tr>
      <td>Bad</td>
      <td>±100 ~ ±125</td>
      <td>－</td>
      <td>－</td>
    </tr>
    <tr>
      <td>Miss</td>
      <td>±125 ~</td>
      <td>±100 ~</td>
      <td>±70 ~</td>
    </tr>
  </tbody>
</table>
