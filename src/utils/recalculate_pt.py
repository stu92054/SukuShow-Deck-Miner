"""
重新计算Pt工具
读取已有的模拟结果，根据新的 Fan Level 重新计算 Pt
无需重新运行耗时的模拟过程
"""
import json
import os
import logging
from ..core.RChart import MusicDB
from ..config.CardLevelConfig import CARD_CACHE

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(message)s')

# ==================== 配置区域 ====================

# 要重新计算的歌曲
MUSIC_ID = "405117"
DIFFICULTY = "02"

# 新的 Fan Level 设置
FAN_LEVELS = {
    1011: 0,   # 沙知
    1021: 0,   # 梢
    1022: 0,   # 綴理
    1023: 0,   # 慈
    1031: 10,  # 帆
    1032: 10,  # 沙
    1033: 10,  # 乃
    1041: 10,  # 吟
    1042: 8,   # 鈴
    1043: 10,  # 芽
    1051: 10,  # 泉
    1052: 7,   # 塞
    1053: 0,   # セラス
}

# Season 模式
SEASON_MODE = 'sukushow'  # 或 'sukuste'

# ================================================

# Fan Level 加成表
FAN_LV_BONUS_TABLE = {
    1: 0.00,
    2: 0.20,
    3: 0.275,
    4: 0.35,
    5: 0.425,
    6: 0.50,
    7: 0.55,
    8: 0.60,
    9: 0.65,
    10: 0.70,
}

# 歌唱人数补正表
SINGING_COUNT_CORRECTION = {
    'sukushow': {2: 2.75, 8: 1.00, 9: 0.90},
    'sukuste': {2: 2.33, 8: 1.00},
}

# 解放倍率
LIMITBREAK_BONUS = {
    1: 1, 2: 1, 3: 1, 4: 1, 5: 1,
    6: 1, 7: 1, 8: 1, 9: 1, 10: 1,
    11: 1.2,
    12: 1.3,
    13: 1.35,
    14: 1.4
}


def calculate_bonus_sfl(singer_ids, fan_levels, season_mode):
    """
    计算 BONUS_SFL

    Args:
        singer_ids: 歌唱成员ID列表 (包含C位)
        fan_levels: Fan Level 字典
        season_mode: 'sukushow' 或 'sukuste'

    Returns:
        (BONUS_SFL, base_bonus, correction) 元组
        - BONUS_SFL: 最终加成
        - base_bonus: 基础 Fan Level 加成 (未乘以歌唱人数补正)
        - correction: 歌唱人数补正
    """
    # 计算基础 Season Fan Lv bonus
    sum_bonus = 0.0
    for cid in singer_ids:
        lv = fan_levels.get(cid, 10)  # 默认 Lv 10
        if lv < 1:
            lv = 1
        elif lv > 10:
            lv = 10
        sum_bonus += FAN_LV_BONUS_TABLE.get(lv, 0.0)

    base_bonus = 1.0 + sum_bonus

    # 应用歌唱人数补正
    singing_count = len(singer_ids)
    correction = SINGING_COUNT_CORRECTION.get(season_mode, {}).get(singing_count, 1.0)
    bonus_sfl = base_bonus * correction

    return bonus_sfl, base_bonus, correction


def recalculate_pt(input_file, output_file, music_id, fan_levels, season_mode):
    """
    重新计算Pt并保存结果

    Args:
        input_file: 输入的模拟结果JSON文件
        output_file: 输出的新结果JSON文件
        music_id: 歌曲ID
        fan_levels: Fan Level 字典
        season_mode: Season 模式
    """
    if not os.path.exists(input_file):
        logger.error(f"错误：文件不存在 {input_file}")
        return

    # 加载歌曲信息
    music_db = MusicDB()
    music = music_db.get_music_by_id(music_id)
    if not music:
        logger.error(f"错误：找不到歌曲 {music_id}")
        return

    # 获取歌唱成员（包含C位）
    singer_ids = getattr(music, 'SingerCharacterId', [])
    center_id = music.CenterCharacterId

    if not isinstance(singer_ids, list):
        singer_ids = []

    all_singers = set(singer_ids)
    if center_id:
        all_singers.add(center_id)

    singer_ids = sorted(list(all_singers))

    # 计算 BONUS_SFL
    bonus_sfl, base_fan_bonus, singing_correction = calculate_bonus_sfl(singer_ids, fan_levels, season_mode)

    logger.info(f"歌曲: {music.Title}")
    logger.info(f"歌唱成员: {singer_ids}")
    logger.info(f"歌唱人数: {len(singer_ids)}")
    logger.info(f"Fan Level 基礎加成: {base_fan_bonus:.4f}")
    logger.info(f"歌唱人数補正: {singing_correction:.4f}")
    logger.info(f"BONUS_SFL (= 基礎加成 × 歌唱人数補正): {bonus_sfl:.4f}")
    logger.info(f"Season模式: {season_mode}")
    logger.info("")

    # 读取原始结果
    with open(input_file, 'r', encoding='utf-8') as f:
        results = json.load(f)

    logger.info(f"读取了 {len(results)} 条结果")

    # 重新计算Pt
    card_limitbreak = {}
    updated_count = 0

    for result in results:
        score = result['score']
        center_card = result.get('center_card')

        # 计算解放倍率
        bonus = bonus_sfl
        if center_card:
            limitbreak = card_limitbreak.get(center_card, None)
            if limitbreak is None:
                levels = CARD_CACHE.get(center_card, [140, 14, 14])
                card_limitbreak[center_card] = limitbreak = max(levels[1:])
            bonus *= LIMITBREAK_BONUS[limitbreak]

        # 更新Pt
        old_pt = result.get('pt', 0)
        new_pt = int(score * bonus)
        result['pt'] = new_pt

        if old_pt != new_pt:
            updated_count += 1

    logger.info(f"更新了 {updated_count} 条结果的Pt值")

    # 按Pt排序
    results.sort(key=lambda x: x['pt'], reverse=True)

    # 保存结果
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=0)

    logger.info(f"结果已保存到: {output_file}")

    # 显示前10名及其详细计算参数
    logger.info(f"\n排名前10的卡组 (详细计算参数):")
    logger.info("=" * 80)
    for i, result in enumerate(results[:10], 1):
        score = result['score']
        pt = result['pt']
        center_card = result.get('center_card')

        # 获取中央卡的解放等级
        limitbreak_bonus = 1.0
        limitbreak_lv = 0
        if center_card:
            levels = CARD_CACHE.get(center_card, [140, 14, 14])
            limitbreak_lv = max(levels[1:])
            limitbreak_bonus = LIMITBREAK_BONUS[limitbreak_lv]

        # 计算总加成
        total_bonus = bonus_sfl * limitbreak_bonus

        logger.info(f"\n#{i}:")
        logger.info(f"  獲得スコア (Score): {score:,}")
        logger.info(f"  Season Fan Lv. ボーナス (基礎): {base_fan_bonus:.4f}")
        logger.info(f"  歌唱人数補正: {singing_correction:.4f}")
        logger.info(f"  BONUS_SFL (上記兩者相乘): {bonus_sfl:.4f}")
        logger.info(f"  センター解放Lv.: Lv.{limitbreak_lv} (ボーナス: {limitbreak_bonus:.2f})")
        logger.info(f"  總加成 (BONUS_SFL × 解放ボーナス): {total_bonus:.4f}")
        logger.info(f"  グランプリPt. = {score:,} × {total_bonus:.4f} = {pt:,}")
        logger.info(f"  卡組: {result['deck_card_ids']}")
        if center_card:
            logger.info(f"  中央卡: {center_card}")
        logger.info("-" * 80)


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("Pt 重新计算工具")
    logger.info("=" * 80)
    logger.info("")

    # 输入输出文件
    input_file = os.path.join("log", f"simulation_results_{MUSIC_ID}_{DIFFICULTY}.json")
    output_file = os.path.join("log", f"simulation_results_{MUSIC_ID}_{DIFFICULTY}_recalc.json")

    # 执行重新计算
    recalculate_pt(input_file, output_file, MUSIC_ID, FAN_LEVELS, SEASON_MODE)

    logger.info("")
    logger.info("=" * 80)
    logger.info("完成！")
    logger.info("=" * 80)

    # 提示
    logger.info(f"\n如果确认结果正确，可以用新文件替换原文件：")
    logger.info(f"  原文件: {input_file}")
    logger.info(f"  新文件: {output_file}")
    logger.info(f"\n或者直接覆盖（请先备份）：")
    logger.info(f"  import shutil")
    logger.info(f"  shutil.copy('{output_file}', '{input_file}')")
