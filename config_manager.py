"""
配置管理系統 - 支援多人協作的配置隔離

使用方式:
    1. 創建個人配置檔案: config/member-{membername}.yaml
    2. 設定環境變量: set CONFIG_FILE=config/member-alice.yaml
    3. 或使用預設: config/default.yaml

日誌目錄結構:
    - 使用 member-{name}.yaml: 輸出到 log/{name}/
    - 使用其他配置檔 (如 default.yaml): 輸出到 log/
"""

import os
import sys
import re
import yaml
import getpass
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

# 設定日誌記錄器
logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器 - 處理多環境配置隔離"""

    def __init__(self, config_file: Optional[str] = None):
        """
        初始化配置管理器

        Args:
            config_file: 配置檔案路徑，如果為 None 則自動偵測

        Raises:
            ValueError: 如果沒有找到任何配置檔案（應使用舊方法）
        """
        self.config_file = self._resolve_config_file(config_file)

        # 如果沒有找到任何配置，拋出異常
        if self.config_file is None:
            raise ValueError("No YAML config file found. Using legacy method (CardLevelConfig.py).")

        self.config = self._load_config()
        self.developer_id = os.environ.get("DEV_ID", getpass.getuser())
        self.member_name = self._extract_member_name(self.config_file)
        self.run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def _resolve_config_file(self, config_file: Optional[str]) -> Optional[str]:
        """
        解析配置檔案路徑優先順序:
        1. 函數參數 config_file
        2. 命令列參數 sys.argv (--config)
        3. 環境變量 CONFIG_FILE
        4. config/default.yaml (如果存在)
        5. 如果都沒有，返回 None（使用舊方法：CardLevelConfig.py）
        """
        # 優先級 1: 直接指定
        if config_file and os.path.exists(config_file):
            logger.info(f"[Config] Using specified config: {config_file}")
            return config_file

        # 優先級 2: 命令列參數 --config
        for i, arg in enumerate(sys.argv):
            if arg == "--config" and i + 1 < len(sys.argv):
                cli_config = sys.argv[i + 1]
                if os.path.exists(cli_config):
                    logger.info(f"[Config] Using CLI config: {cli_config}")
                    return cli_config
                else:
                    raise FileNotFoundError(f"命令列指定的配置檔案不存在: {cli_config}")

        # 優先級 3: 環境變量
        env_config = os.environ.get("CONFIG_FILE")
        if env_config and os.path.exists(env_config):
            logger.info(f"[Config] Using environment config: {env_config}")
            return env_config

        # 優先級 4: 預設配置 (如果存在)
        default_config = os.path.join("config", "default.yaml")
        if os.path.exists(default_config):
            default_config = os.path.abspath(default_config)
            logger.info(f"[Config] Using default config: {default_config}")
            return default_config

        # 如果都沒有指定，返回 None（使用舊方法：CardLevelConfig.py）
        logger.info(f"[Config] No YAML config found, using legacy method (CardLevelConfig.py)")
        return None

    def _load_config(self) -> Dict[str, Any]:
        """載入 YAML 配置檔案"""
        with open(self.config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config

    def _extract_member_name(self, config_file: str) -> Optional[str]:
        """
        從配置檔案路徑中提取成員名稱

        格式: config/member-{name}.yaml -> 提取 {name}

        Args:
            config_file: 配置檔案路徑

        Returns:
            成員名稱，如果無法提取則返回 None（表示使用預設 log/ 目錄）
        """
        # 嘗試匹配 member-{name} 格式
        match = re.search(r'member-([^/\\\.]+)', config_file)
        if match:
            return match.group(1)
        # 如果不是 member 配置（如 default.yaml），返回 None
        return None

    def get_temp_dir(self, music_id: Optional[str] = None) -> str:
        """
        獲取臨時檔案目錄（帶時間戳隔離，避免多次運行衝突）
        格式:
        - member-{name}.yaml: temp/{name}/{timestamp}/temp_{music_id}
        - 其他配置: temp/{developer_id}/{timestamp}/temp_{music_id}
        """
        base_dir = "temp"

        # 優先使用 member_name，沒有才用 developer_id（保持與 log 目錄一致）
        user_dir = self.member_name if self.member_name else self.developer_id

        # 檢查是否啟用環境隔離
        enable_isolation = self.config.get("output", {}).get("enable_isolation", True)

        if enable_isolation:
            # 隔離模式：temp/{user}/{timestamp}/temp_{music_id}
            if music_id:
                temp_path = os.path.join(base_dir, user_dir, self.run_timestamp, f"temp_{music_id}")
            else:
                temp_path = os.path.join(base_dir, user_dir, self.run_timestamp)
        else:
            # 不隔離模式：temp/temp_{music_id}
            if music_id:
                temp_path = os.path.join(base_dir, f"temp_{music_id}")
            else:
                temp_path = base_dir

        # 自動創建目錄
        os.makedirs(temp_path, exist_ok=True)
        return temp_path

    def get_log_dir(self) -> str:
        """
        獲取最終輸出目錄（不帶時間戳，直接覆蓋過去記錄）
        格式:
        - member-{name}.yaml -> log/{name}/
        - default.yaml 或其他 -> log/
        """
        base_dir = "log"

        # 如果是 member 配置，隔離到 log/{member_name}/
        if self.member_name:
            output_path = os.path.join(base_dir, self.member_name)
        else:
            # default.yaml 或其他配置，使用 log/
            output_path = base_dir

        # 自動創建目錄
        os.makedirs(output_path, exist_ok=True)
        return output_path

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
        logger.info("=" * 60)
        logger.info("配置摘要")
        logger.info("=" * 60)
        logger.info(f"配置檔案: {self.config_file}")
        logger.info(f"成員名稱: {self.member_name if self.member_name else '(無，使用開發者ID)'}")
        logger.info(f"開發者ID: {self.developer_id}")
        logger.info(f"運行時間: {self.run_timestamp}")
        logger.info(f"日誌目錄: {self.get_log_dir()}")
        logger.info(f"臨時目錄: {self.get_temp_dir()}")
        logger.info(f"歌曲數量: {len(self.get_songs_config())}")
        logger.info(f"卡牌數量: {len(self.get_card_ids())}")
        logger.info(f"賽季模式: {self.get_season_mode()}")
        logger.info("=" * 60)


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
    # 設定基本日誌格式以便測試
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    try:
        config = ConfigManager()
        config.print_summary()
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"錯誤: {e}")
