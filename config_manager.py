"""
配置管理系統 - 支援多人協作的配置隔離

使用方式:
    1. 創建個人配置檔案: config/dev-{username}.yaml
    2. 設定環境變量: set CONFIG_FILE=config/dev-alice.yaml
    3. 或使用預設: config/default.yaml
"""

import os
import yaml
import getpass
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path


class ConfigManager:
    """配置管理器 - 處理多環境配置隔離"""

    def __init__(self, config_file: Optional[str] = None):
        """
        初始化配置管理器

        Args:
            config_file: 配置檔案路徑，如果為 None 則自動偵測
        """
        self.config_file = self._resolve_config_file(config_file)
        self.config = self._load_config()
        self.developer_id = os.environ.get("DEV_ID", getpass.getuser())
        self.run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def _resolve_config_file(self, config_file: Optional[str]) -> str:
        """
        解析配置檔案路徑優先順序:
        1. 函數參數 config_file
        2. 命令列參數 sys.argv (--config)
        3. 環境變量 CONFIG_FILE
        4. config/default.yaml
        """
        import sys

        # 優先級 1: 直接指定
        if config_file and os.path.exists(config_file):
            print(f"✓ 使用指定配置: {config_file}")
            return config_file

        # 優先級 2: 命令列參數 --config
        for i, arg in enumerate(sys.argv):
            if arg == "--config" and i + 1 < len(sys.argv):
                cli_config = sys.argv[i + 1]
                if os.path.exists(cli_config):
                    print(f"✓ 使用命令列指定配置: {cli_config}")
                    return cli_config
                else:
                    raise FileNotFoundError(f"命令列指定的配置檔案不存在: {cli_config}")

        # 優先級 3: 環境變量
        env_config = os.environ.get("CONFIG_FILE")
        if env_config and os.path.exists(env_config):
            print(f"✓ 使用環境變量配置: {env_config}")
            return env_config

        # 優先級 4: 預設配置
        default_config = os.path.join("config", "default.yaml")
        if os.path.exists(default_config):
            print(f"✓ 使用預設配置: {default_config}")
            return default_config

        raise FileNotFoundError(
            f"找不到配置檔案！請使用以下任一方式指定:\n"
            f"  1. 命令列: python MainBatch.py --config config/member1.yaml\n"
            f"  2. 環境變量: set CONFIG_FILE=config/member1.yaml\n"
            f"  3. 創建預設配置: {default_config}"
        )

    def _load_config(self) -> Dict[str, Any]:
        """載入 YAML 配置檔案"""
        with open(self.config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config

    def get_output_dir(self, subdir: str = "") -> str:
        """
        獲取隔離的輸出目錄

        Args:
            subdir: 子目錄名稱 (如 "log", "temp")

        Returns:
            完整輸出路徑，格式: output/{developer_id}/{timestamp}/{subdir}
        """
        base_dir = self.config.get("output", {}).get("base_dir", "output")

        # 檢查是否啟用環境隔離
        enable_isolation = self.config.get("output", {}).get("enable_isolation", True)

        if enable_isolation:
            output_path = os.path.join(
                base_dir,
                self.developer_id,
                self.run_timestamp,
                subdir
            )
        else:
            # 不隔離模式 (用於正式運行)
            output_path = os.path.join(base_dir, subdir)

        # 自動創建目錄
        os.makedirs(output_path, exist_ok=True)
        return output_path

    def get_temp_dir(self, music_id: Optional[str] = None) -> str:
        """獲取臨時檔案目錄"""
        if music_id:
            return self.get_output_dir(f"temp/temp_{music_id}")
        return self.get_output_dir("temp")

    def get_log_dir(self) -> str:
        """獲取日誌目錄"""
        return self.get_output_dir("log")

    def get_cache_dir(self) -> str:
        """獲取快取目錄"""
        cache_dir = self.get_output_dir("cache")
        return cache_dir

    def get_songs_config(self) -> List[Dict[str, Any]]:
        """獲取歌曲配置列表"""
        return self.config.get("songs", [])

    def get_card_ids(self) -> List[int]:
        """獲取卡牌ID列表"""
        return self.config.get("card_ids", [])

    def get_fan_levels(self) -> Dict[int, int]:
        """獲取粉絲等級配置"""
        return self.config.get("fan_levels", {})

    def get_card_levels(self) -> Dict[int, List[int]]:
        """
        獲取卡牌練度配置

        Returns:
            格式: {card_id: [level, center_skill_level, skill_level]}
        """
        return self.config.get("card_levels", {})

    def get_debug_deck(self) -> Optional[List[int]]:
        """獲取 Debug 卡組"""
        return self.config.get("debug_deck_cards", None)

    def get_season_mode(self) -> str:
        """獲取賽季模式"""
        return self.config.get("season_mode", "sukushow")

    def get_batch_size(self) -> int:
        """獲取批次大小"""
        return self.config.get("batch_size", 1_000_000)

    def get_num_processes(self) -> Optional[int]:
        """獲取進程數量 (None 表示使用 CPU 核心數)"""
        return self.config.get("num_processes", None)

    def get_guild_cardpool_file(self) -> str:
        """獲取公會卡池檔案路徑"""
        return self.config.get("guild_cardpool_file", "guild_cardpools.json")

    def print_summary(self):
        """列印配置摘要"""
        print("=" * 60)
        print("配置摘要")
        print("=" * 60)
        print(f"配置檔案: {self.config_file}")
        print(f"開發者ID: {self.developer_id}")
        print(f"運行時間: {self.run_timestamp}")
        print(f"日誌目錄: {self.get_log_dir()}")
        print(f"臨時目錄: {self.get_temp_dir()}")
        print(f"快取目錄: {self.get_cache_dir()}")
        print(f"歌曲數量: {len(self.get_songs_config())}")
        print(f"卡牌數量: {len(self.get_card_ids())}")
        print(f"賽季模式: {self.get_season_mode()}")
        print("=" * 60)


# 全局配置實例 (延遲初始化)
_global_config: Optional[ConfigManager] = None


def get_config(config_file: Optional[str] = None) -> ConfigManager:
    """
    獲取全局配置實例 (單例模式)

    Args:
        config_file: 配置檔案路徑 (僅首次調用有效)

    Returns:
        ConfigManager 實例
    """
    global _global_config
    if _global_config is None:
        _global_config = ConfigManager(config_file)
    return _global_config


def reset_config():
    """重置全局配置 (用於測試)"""
    global _global_config
    _global_config = None


if __name__ == "__main__":
    # 測試配置管理器
    try:
        config = ConfigManager()
        config.print_summary()
    except FileNotFoundError as e:
        print(f"錯誤: {e}")
