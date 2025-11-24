# 公會成員計算指南 / Guild Member Calculation Guide

[繁體中文](#繁體中文) | [简体中文](#简体中文) | [日本語](#日本語) | [English](#english)

---

## 繁體中文

### 🎯 快速開始

#### 1. 創建成員配置檔案

```bash
copy config\member-example.yaml config\member-{成員名稱}.yaml
```

#### 2. 編輯配置檔案

編輯 `config/member-{成員名稱}.yaml`：

```yaml
# 歌曲設定（支援多首）
songs:
  - music_id: "405117"
    difficulty: "02"        # 01=Normal, 02=Hard, 03=Expert, 04=Master
    mastery_level: 50

  - music_id: "405118"
    difficulty: "03"

# 卡池
card_ids:
  - 1011501  # 沙知
  - 1021701  # LR梢
  # ... 列出該成員擁有的所有卡牌

# 粉絲等級
fan_levels:
  1011: 5   # 沙知
  1021: 3   # 梢
  # ...

# 卡牌練度（未滿練的卡才需要設定）
card_levels:
  # 1021701: [130, 10, 10]  # LR梢 未滿練
```

#### 3. 執行模擬

```bash
python MainBatch.py --config config/member-{成員名稱}.yaml
```

#### 4. 查看結果

結果保存在：
```
output/
└── {你的用戶名}/
    └── {時間戳}/
        └── log/
            └── simulation_results_*.json
```

### 📝 多成員工作流程

```bash
# 為 Alice 計算
python MainBatch.py --config config/member-alice.yaml

# 為 Bob 計算
python MainBatch.py --config config/member-bob.yaml

# 為 Charlie 計算
python MainBatch.py --config config/member-charlie.yaml
```

每次執行都會創建獨立的輸出目錄，互不干擾。

### 🔧 配置優先順序

1. **命令列** (最高): `python MainBatch.py --config config/member1.yaml`
2. **環境變數**: `set CONFIG_FILE=config/member1.yaml`
3. **預設配置**: `config/default.yaml`

---

## 简体中文

### 🎯 快速开始

#### 1. 创建成员配置文件

```bash
copy config\member-example.yaml config\member-{成员名称}.yaml
```

#### 2. 编辑配置文件

编辑 `config/member-{成员名称}.yaml`：

```yaml
# 歌曲设定（支持多首）
songs:
  - music_id: "405117"
    difficulty: "02"        # 01=Normal, 02=Hard, 03=Expert, 04=Master
    mastery_level: 50

  - music_id: "405118"
    difficulty: "03"

# 卡池
card_ids:
  - 1011501  # 沙知
  - 1021701  # LR梢
  # ... 列出该成员拥有的所有卡牌

# 粉丝等级
fan_levels:
  1011: 5   # 沙知
  1021: 3   # 梢
  # ...

# 卡牌练度（未满练的卡才需要设定）
card_levels:
  # 1021701: [130, 10, 10]  # LR梢 未满练
```

#### 3. 执行模拟

```bash
python MainBatch.py --config config/member-{成员名称}.yaml
```

#### 4. 查看结果

结果保存在：
```
output/
└── {你的用户名}/
    └── {时间戳}/
        └── log/
            └── simulation_results_*.json
```

### 📝 多成员工作流程

```bash
# 为 Alice 计算
python MainBatch.py --config config/member-alice.yaml

# 为 Bob 计算
python MainBatch.py --config config/member-bob.yaml

# 为 Charlie 计算
python MainBatch.py --config config/member-charlie.yaml
```

每次执行都会创建独立的输出目录，互不干扰。

### 🔧 配置优先级

1. **命令行** (最高): `python MainBatch.py --config config/member1.yaml`
2. **环境变量**: `set CONFIG_FILE=config/member1.yaml`
3. **默认配置**: `config/default.yaml`

---

## 日本語

### 🎯 クイックスタート

#### 1. メンバー設定ファイルを作成

```bash
copy config\member-example.yaml config\member-{メンバー名}.yaml
```

#### 2. 設定ファイルを編集

`config/member-{メンバー名}.yaml` を編集：

```yaml
# 楽曲設定（複数可）
songs:
  - music_id: "405117"
    difficulty: "02"        # 01=Normal, 02=Hard, 03=Expert, 04=Master
    mastery_level: 50

  - music_id: "405118"
    difficulty: "03"

# カードプール
card_ids:
  - 1011501  # 沙知
  - 1021701  # LR梢
  # ... メンバーが所有するすべてのカードをリスト

# ファンレベル
fan_levels:
  1011: 5   # 沙知
  1021: 3   # 梢
  # ...

# カードレベル（最大でないカードのみ設定）
card_levels:
  # 1021701: [130, 10, 10]  # LR梢 最大レベルでない
```

#### 3. シミュレーションを実行

```bash
python MainBatch.py --config config/member-{メンバー名}.yaml
```

#### 4. 結果を確認

結果の保存先：
```
output/
└── {ユーザー名}/
    └── {タイムスタンプ}/
        └── log/
            └── simulation_results_*.json
```

### 📝 複数メンバーのワークフロー

```bash
# Alice の計算
python MainBatch.py --config config/member-alice.yaml

# Bob の計算
python MainBatch.py --config config/member-bob.yaml

# Charlie の計算
python MainBatch.py --config config/member-charlie.yaml
```

各実行は独立した出力ディレクトリを作成し、競合しません。

### 🔧 設定の優先順位

1. **コマンドライン** (最優先): `python MainBatch.py --config config/member1.yaml`
2. **環境変数**: `set CONFIG_FILE=config/member1.yaml`
3. **デフォルト設定**: `config/default.yaml`

---

## English

### 🎯 Quick Start

#### 1. Create Member Configuration File

```bash
copy config\member-example.yaml config\member-{membername}.yaml
```

#### 2. Edit Configuration File

Edit `config/member-{membername}.yaml`:

```yaml
# Songs configuration (supports multiple songs)
songs:
  - music_id: "405117"
    difficulty: "02"        # 01=Normal, 02=Hard, 03=Expert, 04=Master
    mastery_level: 50

  - music_id: "405118"
    difficulty: "03"

# Card pool
card_ids:
  - 1011501  # Sachi
  - 1021701  # LR Kozue
  # ... List all cards the member owns

# Fan levels
fan_levels:
  1011: 5   # Sachi
  1021: 3   # Kozue
  # ...

# Card levels (only for cards not at max level)
card_levels:
  # 1021701: [130, 10, 10]  # LR Kozue not fully leveled
```

#### 3. Run Simulation

```bash
python MainBatch.py --config config/member-{membername}.yaml
```

#### 4. View Results

Results are saved to:
```
output/
└── {your_username}/
    └── {timestamp}/
        └── log/
            └── simulation_results_*.json
```

### 📝 Multi-Member Workflow

```bash
# Calculate for Alice
python MainBatch.py --config config/member-alice.yaml

# Calculate for Bob
python MainBatch.py --config config/member-bob.yaml

# Calculate for Charlie
python MainBatch.py --config config/member-charlie.yaml
```

Each run creates an isolated output directory to avoid conflicts.

### 🔧 Configuration Priority

1. **Command line** (highest): `python MainBatch.py --config config/member1.yaml`
2. **Environment variable**: `set CONFIG_FILE=config/member1.yaml`
3. **Default config**: `config/default.yaml`

---

## 常見問題 / FAQ

**Q: 如何查看配置摘要？/ How to view configuration summary?**
```bash
python -m src.config.config_manager
```

**Q: 輸出目錄太多？/ Too many output directories?**

手動刪除舊目錄或使用 PowerShell 批量清理：
```powershell
Get-ChildItem output -Directory | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | Remove-Item -Recurse
```
