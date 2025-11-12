"""
用于自定义所有卡牌的默认练度，并能指定特定卡牌的练度
"""

# 卡牌等级的默认值
default_card_level = {
    3: 80,  # R
    4: 100,  # SR
    5: 120,  # UR
    7: 140,  # LR
    8: 140,  # DR
    9: 120  # BR
}
default_skill_level = 14  # 技能等级的默认值
default_center_skill_level = 14  # C位技能等级的默认值

# CARD_CACHE 用于配置与上方默认等级不同的卡牌等级
# 格式：
#   卡牌ID: [卡牌等级, C位技能等级, 普通技能等级],
CARD_CACHE: dict[int, list[int]] = {
    # 1011501: [120, 10, 10],  # 沙知
    # 1021701: [140, 11, 11],  # LR梢
    # 1022901: [120, 11, 11],  # BR缀
    # 1022504: [120, 13, 13],  # 明月缀
    # 1023701: [140, 10, 10],  # LR慈
    # 1023901: [120, 10, 10],  # BR慈
    # 1031901: [120, 12, 12],  # BR帆
    # 1031516: [120, 10, 10],  # ST帆
    # 1031504: [120, 10, 10],  # RG帆
    # 1032528: [120, 11, 11],  # IDOME沙
    # 1032901: [120, 10, 10],  # BR沙
    # 1033524: [120, 11, 11],  # IDOME乃
    # 1033901: [120, 10, 11],  # BR乃
    # 1042801: [140, 11, 11],  # EA铃
    # 1042802: [140, 11, 11],  # OE铃
    # 1043504: [120, 11, 11],  # mrc芽
    # 1043801: [140, 11, 11],  # EA芽
    # 1043802: [140, 11, 11],  # OE芽
    # 1052901: [120, 10, 10],  # BR塞
    # 1052503: [120, 12, 12],  # 十六夜塞
}

# 用于配置卡组包含特定卡牌时的背水血线
# 卡组中如有多张背水，以最低的血线为准
# 开局会自动挂机miss到这个血量
# 格式: 卡牌id: 血线,
DEATH_NOTE: dict[int, int] = {
    1041513: 10,  # 宴会吟
    1041901: 25,  # BR吟
}


def convert_deck_to_simulator_format(
    deck_card_ids_list: list[int],
    custom_card_levels: dict[int, list[int]] = None
) -> list[tuple[int, list[int]]]:
    """
    将 CardSeriesId 列表转换为模拟器所需的格式，并根据预加载的缓存或默认值添加等级信息。

    Args:
        deck_card_ids_list: 卡牌ID列表
        custom_card_levels: 自定义卡牌练度 (从配置檔案讀取)，格式: {card_id: [level, center_skill_level, skill_level]}
                           如果为 None，則使用全局 CARD_CACHE (向下兼容)

    Returns:
        模拟器格式的卡组数据: [(card_id, [level, center_skill_level, skill_level]), ...]
    """

    # 創建本地快取，避免污染全局狀態
    local_cache = {}

    # 首先使用全局 CARD_CACHE (向下兼容舊代碼)
    local_cache.update(CARD_CACHE)

    # 然後用自定義練度覆蓋 (優先級更高)
    if custom_card_levels:
        local_cache.update(custom_card_levels)

    result_deck_data = []
    for card_id in deck_card_ids_list:
        # 從本地快取獲取等級，如果不存在則使用默認值
        levels = local_cache.get(card_id, None)
        if levels == None:
            levels = [
                default_card_level[int(str(card_id)[4])],
                default_center_skill_level,
                default_skill_level
            ]
            # 僅更新本地快取，不污染全局 CARD_CACHE
            local_cache[card_id] = levels
        result_deck_data.append((card_id, levels))
    return result_deck_data


def fix_windows_console_encoding():
    """
    避免在 Windows + PyPy 的环境下输出非 ASCII 字符时乱码
    """
    import os

    if "PSModulePath" in os.environ:
        # 在 PowerShell 下，调用一次设置 UTF-8 编码
        import subprocess
        subprocess.run([
            "powershell", "-Command",
            "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding"
        ])
    elif "cmd.exe" in os.environ.get("ComSpec", "").lower():
        # 在 CMD 下，修改代码页为 65001 (UTF-8)
        import subprocess
        subprocess.run(["chcp", "65001"], shell=True)
