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
    # 1011501: [120, 10, 10], #沙知
    # 1021701: [140, 11, 11], #LR梢
    # 1022901: [120, 11, 11], #BR缀
    # 1022504: [120, 13, 13], #明月缀
    # 1023701: [140, 10, 10], #LR慈
    # 1023901: [120, 10, 10], #BR慈
    # 1031901: [120, 12, 12], #BR帆
    # 1031516: [120, 10, 10], #ST帆
    # 1031504: [120, 10, 10], #RG帆
    # 1032528: [120, 11, 11], #IDOME沙
    # 1032901: [120, 10, 10], #BR沙
    # 1033524: [120, 11, 11], #IDOME乃
    # 1033901: [120, 10, 11], #BR乃
    # 1043504: [120, 11, 11], #mrc芽
    # 1052901: [120, 10, 10], #BR塞
    # 1052503: [120, 12, 12], #十六夜塞
}

# 用于配置卡组包含特定卡牌时的背水血线
# 卡组中如有多张背水，以最右边的背水卡的血线为准
# 开局会自动挂机miss到这个血量
# 格式: 卡牌id: 血线,
DEATH_NOTE: dict[int, int] = {
    1041513: 10,
    1041901: 25,
}


def convert_deck_to_simulator_format(
    deck_card_ids_list: list[int]
) -> list[tuple[int, list[int]]]:
    """
    将 CardSeriesId 列表转换为模拟器所需的格式，并根据预加载的缓存或默认值添加等级信息。
    """

    result_deck_data = []
    for card_id in deck_card_ids_list:
        # 尝试从缓存中获取自定义等级，如果不存在则使用默认满级
        levels = CARD_CACHE.get(card_id, None)
        if levels == None:
            levels = [
                default_card_level[int(str(card_id)[4])],
                default_center_skill_level,
                default_skill_level
            ]
            CARD_CACHE[card_id] = levels
        result_deck_data.append((card_id, levels))
    return result_deck_data
