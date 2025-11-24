# SukuShow Deck Miner

适用于 [Link！Like！LoveLive！](https://www.lovelive-anime.jp/hasunosora/system/) (リンクラ) 中的音游模式 School Idol Show (スクショウ) 的卡组模拟器和优化求解器。 

---

**[English](../README.md) | [简体中文](README_zh-cn.md) | [繁體中文](README_zh-tw.md) | [日本語](README_ja-jp.md)**

---

## 🚀 快速开始

### 🛞 环境要求

- **Python 版本**:
  由于代码中使用了 `match ... case ...` 语句，项目**最低要求 Python 3.10**。  
  **为了获得最佳性能，强烈推荐使用 Python 3.11 或更高版本运行。**

- **依赖包**:

  - `PyYAML` - 用于解析 YAML 配置文件
  - `tqdm` - 用于在批量模拟时显示进度条

  可通过以下命令安装：

  ```bash
  pip install PyYAML tqdm
  ```

- **使用 PyPy 进行性能优化**（可选但强烈推荐）：

  使用 PyPy 代替标准 CPython 可获得显著的性能提升（某些情况下可达 **3-5 倍加速**）：

  1. 下载并安装 [PyPy 3.10+](https://www.pypy.org/download.html)
  2. 使用 PyPy 的 pip 安装依赖包：
     ```bash
     pypy -m pip install PyYAML tqdm sortedcontainers
     ```
     **注意**：`sortedcontainers` 仅在 PyPy 下需要，标准 CPython 不需要。
  3. 使用 PyPy 运行模拟器：
     ```bash
     pypy MainBatch.py
     # 或
     pypy MainSingle.py
     ```

  **注意**：PyPy 的 JIT 编译器为计算密集型模拟提供了出色的性能，但在预热阶段可能会使用更多内存。

---

## 🎮 使用方式

### ▶ 运行核心脚本

根据需求选择并运行以下文件：

- `MainBatch.py`: **批量模拟**。输入卡池与课题曲，自动生成卡组并进行批量模拟，以寻找**单曲最优解**。
- `MainSingle.py`: **单次模拟**。输入特定卡组与课题曲，进行单次模拟并输出详细模拟过程。
- `multi_song_optimizer.py`: **多曲优化**。输入多首课题曲，利用 `MainBatch.py` 生成的卡组得分数据，寻找**多曲目的最优解**。

### ⚙ 个性化配置

#### 🆕 配置文件系统（推荐用于公会成员计算）

**对于需要为多位公会成员进行模拟的用户**，我们提供了基于 YAML 的配置系统，可轻松切换不同成员的配置：

**快速开始：**

1. **为每位公会成员创建配置文件：**
   ```bash
   copy config\member-example.yaml config\member-yourname.yaml
   ```

2. **编辑配置文件**以匹配该成员的卡池、粉丝等级和卡牌练度：
   ```yaml
   # config/member-yourname.yaml

   songs:
     - music_id: "405117"
       difficulty: "02"        # 01=Normal, 02=Hard, 03=Expert, 04=Master
       mastery_level: 50

     - music_id: "405118"      # 可以添加多首歌曲
       difficulty: "03"

   card_ids:
     - 1011501  # 列出该成员拥有的所有卡牌
     - 1021701
     # ...

   fan_levels:
     1011: 5    # 该成员的粉丝等级
     1021: 3
     # ...

   card_levels:
     # 覆盖特定卡牌练度（如果未满练）
     # 1021701: [130, 10, 10]  # LR梢 未满练
   ```

3. **使用配置运行模拟：**
   ```bash
   python MainBatch.py --config config/member-yourname.yaml
   ```

4. **结果自动保存到隔离的目录：**
   ```
   # 最终结果（永久保存）
   log/
   └── {member_name}/              # 如 alice/ (使用 member-*.yaml 时)
       └── simulation_results_405117_02.json

   # 临时文件（执行过程中，完成后可清理）
   temp/
   └── {member_name}/              # 与 log/ 保持一致
       └── {timestamp}/            # 执行时间戳
           └── temp_405117/        # 各歌曲独立目录
               └── temp_batch_001.json
   ```

**优点：**
- ✅ **轻松切换** - 快速为不同公会成员运行模拟
- ✅ **无需修改代码** - 所有配置都在 YAML 文件中
- ✅ **隔离输出** - 每次运行创建独立目录（避免文件冲突）
- ✅ **Git 友好** - 配置文件可提交到版本控制

**配置优先级：**
1. 命令行：`python MainBatch.py --config config/member1.yaml`
2. 环境变量：`set CONFIG_FILE=config/member1.yaml`（Windows）或 `export CONFIG_FILE=config/member1.yaml`（Linux）
3. 默认：`config/default.yaml`（如果存在，已被 git 忽略）
4. CardLevelConfig.py 与程序内设置（旧方法，向下兼容）

**注意：** `config/default.yaml` 已被 gitignore。请使用 `config/default-example.yaml` 作为模板创建自己的 `config/default.yaml`。

**公会计算工作流程示例：**
```bash
# 为成员 Alice 计算
python MainBatch.py --config config/member-alice.yaml

# 为成员 Bob 计算
python MainBatch.py --config config/member-bob.yaml

# 结果位于不同目录：
# log/alice/simulation_results_*.json
# log/bob/simulation_results_*.json
#
# 临时文件：
# temp/alice/{timestamp}/temp_*/
# temp/bob/{timestamp}/temp_*/
```

详见 `config/member-example.yaml` 完整示例。

---

#### 传统方式：直接修改文件

也可以根据需要直接调整 Python 文件中的配置：

- [src/config/CardLevelConfig.py](../src/config/CardLevelConfig.py): 配置所有卡牌的**默认等级**和**个别卡牌的等级** (`CARD_CACHE`)。默认情况下，所有卡牌均设置为满级。
利用 `DEATH_NOTE` 配置背水卡牌的挂机血线。卡组中存在多张配置了血线的背水卡时，以最低血线为准。
- [src/deck_gen/DeckGen2.py](../src/deck_gen/DeckGen2.py): 负责卡组生成逻辑。可以在此配置卡牌冲突规则 (`CARD_CONFLICT_RULES`)、卡组技能条件 (`check_skill_tags`) 等约束限制，以实现卡组生成时的进一步剪枝优化。
- [MainBatch.py](../MainBatch.py): **批量模拟的主要配置文件。** 详见下方配置指南。
- [MainSingle.py](../MainSingle.py): 配置单次模拟的卡组与曲目，可在 `logging.basicConfig` 中配置模拟过程的输出详细程度。
  - INFO: 仅输出卡组与模拟结果
  - DEBUG: 输出详细的技能使用记录
  - TIMING: 输出包括所有 Note 与 CD 结束时间点的日志，Note 会刷屏所以建议将日志输出至文本文件查看
- [src/core/Simulator_core.py](../src/core/Simulator_core.py): 可以通过修改代码调整批量模拟时的音游策略，只要你知道自己在做什么。
在这里进行的修改只影响批量模拟，单次模拟的音游策略需要在 `MainSingle.py` 中另行修改。

### 📘 MainBatch.py 配置指南

`MainBatch.py` 运行前需要手动配置。以下是需要修改的主要部分：

#### 1. **卡池配置** (约第 157 行)
定义要包含在模拟中的卡牌：

```python
card_ids = [
    1011501,  # 示例卡牌ID
    1033514,
    # 在此添加你拥有的卡牌ID
]
```

#### 2. **歌曲配置** (约第 208 行)
配置一首或多首要模拟的歌曲：

```python
SONGS_CONFIG = [
    {
        "music_id": "405305",        # 歌曲ID（从游戏数据中查找）
        "difficulty": "02",          # 难度:"01"=Normal, "02"=Hard, "03"=Expert, "04"=Master
        "mustcards_all": [],         # 必须包含的所有卡牌（卡牌ID列表）
        "mustcards_any": [],         # 至少包含其中一张的卡牌
        "center_override": None,     # 覆盖C位角色（None = 使用歌曲默认）
        "color_override": None,      # 覆盖歌曲颜色：1=Smile, 2=Pure, 3=Cool（None = 使用歌曲默认）
    },
    # 根据需要添加更多歌曲
]
```

#### 3. **季度粉丝等级配置** (约第 285 行)
配置粉丝等级以准确计算 Grandprix Pt：

```python
# 季度模式：'sukushow'（仅歌唱成员）或 'sukuste'（全部成员）
SEASON_MODE = 'sukushow'

# 设置每个角色的粉丝等级（1-10）
FAN_LEVELS: dict[int, int] = {
    1011: 10,  # 角色ID -> 粉丝等级
    1021: 8,
    1022: 10,
    # 添加全部12个角色及其粉丝等级
    # 未指定时默认为10
}
```

**粉丝等级加成表：**
- 等级 1: 0%
- 等级 2: 20%
- 等级 3: 27.5%
- 等级 4: 35%
- 等级 5: 42.5%
- 等级 6: 50%
- 等级 7: 55%
- 等级 8: 60%
- 等级 9: 65%
- 等级 10: 70%（默认）

#### 4. **DR剪枝配置** (约第 196 行)
控制是否移除非C位角色的DR卡：

```python
ENABLE_DR_PRUNING = False  # 推荐：False（让算法自动决定）
# True:  移除非C位DR卡 + 强制使用C位DR（旧行为）
# False: 保留所有DR卡，让算法决定最优使用方式
```

#### 5. **技能要求** (约第 236 行)
指定所有生成的卡组必须包含的技能类型：

```python
mustskills_all = [
    SkillEffectType.DeckReset,  # 洗牌（DR）
    SkillEffectType.ScoreGain,  # 分数提升
    # 添加其他必需的技能类型
]
```
---

## ⚠️ **重要警告：CPU 占用与稳定性** ⚠️

> [!CAUTION]  
> ⚠ **批量模拟默认会调用所有可用的 CPU 线程执行，且运行时 CPU 占用率通常高达 99% 以上。** ⚠  
> **存在 i5-13600KF 在满负荷运行一段时间后蓝屏的案例。**
>
> 如对 CPU 体质或散热没有自信，**强烈建议在批量模拟前采取以下措施**：
>
> - 对 CPU 进行**升压/降频**操作。
> - **减少模拟器调用的线程数**。
>
> 保险起见，可将 `MainBatch.py` 文件中的 `num_processes = os.cpu_count() or 1` 这行代码修改为 `num_processes = 12`。其中 `12` 可根据实际线程数替换为**小于 CPU 线程数的其他值**，降低性能压力。

- **资源考量**：理论上可以把所有卡牌都放进备选卡池进行批量模拟。然而，这需要**极其强大的 CPU 性能、巨大的内存容量和充裕的模拟时间**。由于可能出现不可预知的问题，**不建议**这样做。
- **内存堆积**：尽管批量模拟中卡组生成与模拟环节是流水线作业，模拟结果也会分批暂存至硬盘，但**卡越多模拟器吃的内存越多**。因此，请勿在备选卡池中放入过多卡牌，以免造成内存溢出。

---

## 📝 备注与潜在误差

- 本模拟器采用**穷举法**生成卡组进行模拟。所找到的「单曲最优解」仅在**给定卡池范围、卡牌练度、谱面难度、音游策略**下成立。调整卡池、练度或谱面难度后，可能会得到不同的最优解。默认采取的音游策略是：  
  1. 在谱面中的完全准确时机打出 **All Perfect**  
  2. 若卡组中有在 `DEATH_NOTE` 中配置了血线的背水卡，当前血量高于背水血线时自动挂机，仅在血量低于血线时保持 All Perfect。
- 同理，多曲最优解也会随卡池、练度、谱面难度、音游策略等因素而变化。
- 模拟器能够有效**节约实战模拟的时间**，但很难一发入魂找到真正的**绝对最优卡组**。需要对卡牌效果具有一定理解才能充分发挥模拟器的作用。
- **最优卡组 ≠ 最优策略**。卡时间点逐帧凹分或是根据技能条件/效果卡练度的操作请各显神通。
- 在计算 **Grandprix Pt** 时，季度粉丝等级加成会根据 `MainBatch.py` 中的 `FAN_LEVELS` 配置**动态计算**。如果未指定，默认所有成员为10级（相当于旧版默认值6.6）。C 位成员（如果有）的解放倍率则会按其技能或 SP 等级进行换算。
- 由于模拟器**并非 1:1 完全复刻游戏逻辑**，模拟得分与实战不一致是正常现象。

### ⏰ 可能的误差来源

**逻辑不一致**  
未能完全复刻游戏原始逻辑，导致技能处理、分数计算的结果与实战存在较大出入。  
若能提供**实战录像、卡组练度、歌曲 Master Lv. 信息**，我可能会尝试核对一下是哪里不一致进行修复。

**时间处理误差**  
由于**浮点数精度问题**或是其他神秘原因（例如游戏中可能是每帧处理一次所有事件，而非基于每个事件的准确时间点处理）实际技能发动时机可能与模拟存在数十毫秒的偏差。极端情况下曾出现过模拟中在Fever开始前打出的卡牌在实战中晚于Fever开始才打出，导致电加成被Fever开始时触发的C位技能消耗的案例。

**判定时机**  
模拟器只会按谱面中的 `just` 时间点处理 note，无论判定是否为 Perfect。  
然而实战中的 note 判定存在**时间窗口**，在 AP 不足时会导致实战的技能发动时机略微提前/延后，极端情况下可能导致卡牌打出次数比模拟多/少一次。  
对于和 Fever 开始/结束时点在同一拍上的 note，实战凹一下都有机会吃到 Fever 的双倍 Voltage。但 note 在谱面中的记录的时间点一般比 Fever 切换的时间点多两位小数，导致模拟时不一定会在 Fever 内结算得分。  
下表为 Ver.4.0.1 时的判定时机，仅供参考：

<table>
  <thead>
    <tr>
      <th rowspan="2"><b>判定</b></th>
      <th colspan="3"><b>判定时机 (ms)</b></th>
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
      <td>点击但未上划</td>
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
