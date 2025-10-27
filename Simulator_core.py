import logging
import os
from platform import python_implementation
# 导入所有 R 模块和 db_load 函数
from RCardData import db_load
from RChart import Chart, MusicDB
from RDeck import Deck
from RLiveStatus import PlayerAttributes, MentalDown
from SkillResolver import UseCardSkill, ApplyCenterSkillEffect, ApplyCenterAttribute, CheckCenterSkillCondition
from CardLevelConfig import DEATH_NOTE

# --- Configure logging (for the module itself if needed, or rely on main script's config) ---
# 注意：子进程会继承父进程的logger配置，但为了独立运行和测试，可以保留或简化这里的logger
logger = logging.getLogger(__name__)

# --- Global DBs for the simulator module ---
# 这些DBs也应该在模块的顶层被加载，确保它们在子进程中是可访问的
try:
    MUSIC_DB = MusicDB()
    DB_CARDDATA = db_load(os.path.join("Data", "CardDatas.json"))
    DB_SKILL = db_load(os.path.join("Data", "RhythmGameSkills.json"))
    DB_SKILL.update(db_load(os.path.join("Data", "CenterSkills.json")))
    DB_SKILL.update(db_load(os.path.join("Data", "CenterAttributes.json")))
    logger.info("Simulator core databases loaded.")
except ImportError as e:
    logger.error(f"Failed to import required R modules in simulator_core. Error: {e}")
    # Consider raising an exception or having a fallback
except FileNotFoundError as e:
    logger.error(f"Required database file not found: {e}. Please check your 'Data' directory.")
    # Exit or handle gracefully if critical modules are missing/DBs not found
    exit(1)  # Exit with an error code


MISS_TIMING = {
    "Single": 0.125,
    "Hold": 0.125,
    "Flick": 0.100,
    "HoldMid": 0.070,
    "Trace": 0.070,
}


def run_game_simulation(
    task_args: tuple  # This will be (deck_card_data, chart_obj, player_master_level, original_deck_index)
) -> dict:
    """
    Runs a single game simulation and includes the original deck index in the result.
    Designed to be run in parallel.

    Args:
        deck_card_data (list[tuple[int, list[int]]]): A list of tuples, where each tuple
            is (CardSeriesId, [card_level, center_skill_level, skill_level]).
            Example: [(1011501, [120, 1, 12]), ...]
        chart_obj (Chart): The music chart to simulate (e.g., Chart(MUSIC_DB, "103105", "02").
        player_master_level (int): The player's master level. 1 ~ 50.

    Returns:
        dict: A dictionary containing key simulation results (e.g., final score, card log).
              You can expand this to return more detailed metrics.
    """
    # NOTE: DBs (MUSIC_DB, DB_CARDDATA, DB_SKILL) are now global to this module
    # and inherited by child processes (copy-on-write).
    deck_card_data, chart_obj, player_master_level, original_deck_index, deck_card_ids, center_card_index = task_args

    d = Deck(DB_CARDDATA, DB_SKILL, deck_card_data)
    c: Chart = chart_obj
    player = PlayerAttributes(masterlv=player_master_level)
    player.set_deck(d)

    centercard = None
    afk_mental = 0
    flag_hanabi_ginko = 1041517 in deck_card_ids

    # 扫描卡片收集信息
    for card in d.cards:
        cid = int(card.card_id)
        if cid in DEATH_NOTE:
            if afk_mental:
                afk_mental = min(afk_mental, DEATH_NOTE[cid])
            else:
                afk_mental = DEATH_NOTE[cid]

    # C位选择逻辑
    if center_card_index >= 0:
        # 使用指定索引的卡片作为C位
        centercard = d.cards[center_card_index]
    else:
        # 自动选择C位（DR优先，无DR则靠左）
        for card in d.cards:
            if card.characters_id == c.music.CenterCharacterId:
                if not centercard or card.card_id[4] == "8":
                    centercard = card

    if centercard:
        for target, effect in centercard.get_center_attribute():
            ApplyCenterAttribute(player, effect, target)

    d.appeal_calc(c.music.MusicType)
    player.hp_calc()

    # --- Defensive check: ensure chart has notes before using AllNoteSize ---
    if not getattr(c, "AllNoteSize", 0):
        logger.error(
            f"Chart for music id {getattr(c.music, 'Id', getattr(c.music, 'Id', None))} "
            f"tier {getattr(c, 'tier', None)} has AllNoteSize={getattr(c, 'AllNoteSize', None)}. "
            "Skipping this simulation. Check Data/bytes file and chart parsing."
        )
        # Return a minimal result to avoid crashing the worker pool
        return {
            "final_score": 0,
            "cards_played_log": d.card_log,
            "original_deck_index": original_deck_index,
            "deck_card_ids": deck_card_ids,
            "center_card": int(centercard.card_id) if centercard is not None else None
        }

    player.basescore_calc(c.AllNoteSize)
    # player.cooldown = int(player.cooldown * 1_000_000)

    # Use a heap for ChartEvents for better performance
    pypy_impl = python_implementation() == "PyPy"
    if pypy_impl:
        event_heap = c.ChartEvents.copy()
        event_heap.add((player.cooldown, "CDavailable"))
    else:
        import heapq
        event_heap = list(c.ChartEvents)
        heapq.heappush(event_heap, (player.cooldown, "CDavailable"))

    combo_count = 0
    cardnow = d.topcard()

    # 動態重新計算血線的函數
    def recalculate_afk_mental():
        """重新檢查牌組中未除外的卡片，計算當前血線"""
        nonlocal afk_mental
        new_afk_mental = 0
        for card in d.cards:
            # 只檢查未被除外的卡片
            if not card.is_except:
                cid = int(card.card_id)
                if cid in DEATH_NOTE:
                    if new_afk_mental:
                        new_afk_mental = min(new_afk_mental, DEATH_NOTE[cid])
                    else:
                        new_afk_mental = DEATH_NOTE[cid]
        afk_mental = new_afk_mental

    # 提取重复的技能触发逻辑为内联函数
    def try_use_skill():
        nonlocal cardnow, afk_mental
        if cardnow and player.ap >= cardnow.cost:
            player.ap -= cardnow.cost

            # 記錄打出前是否有卡片被除外
            cards_except_before = [card for card in d.cards if card.is_except]

            conditions, effects = d.topskill()
            UseCardSkill(player, effects, conditions, cardnow)

            # 檢查是否有新的卡片被除外
            cards_except_after = [card for card in d.cards if card.is_except]
            if len(cards_except_after) > len(cards_except_before):
                # 有卡片被除外，重新計算血線
                recalculate_afk_mental()

            player.CDavailable = False
            cdtime_float = timestamp + player.cooldown
            if pypy_impl:
                event_heap.add((cdtime_float, "CDavailable"))
            else:
                heapq.heappush(event_heap, (cdtime_float, "CDavailable"))
            cardnow = d.topcard()

    while event_heap:
        if pypy_impl:
            timestamp, event = event_heap.pop(0)
        else:
            timestamp, event = heapq.heappop(event_heap)

        match event:
            case "Single" | "Hold" | "HoldMid" | "Flick" | "Trace":
                combo_count += 1
                if afk_mental and player.mental.get_rate() > afk_mental:
                    # 需要仰卧起坐时，将 MISS 时机按判定窗口延后以提高精度
                    if flag_hanabi_ginko:
                        if pypy_impl:
                            event_heap.add((timestamp + MISS_TIMING[event], "_" + event))
                        else:
                            heapq.heappush(event_heap, (timestamp + MISS_TIMING[event], "_" + event))
                    else:
                        try:
                            player.combo_add("MISS", event)
                        except MentalDown:
                            break
                else:
                    player.combo_add("PERFECT")

                if player.CDavailable:
                    try_use_skill()

            case "CDavailable":
                player.CDavailable = True
                try_use_skill()

            case event if event[0] == "_":
                if player.mental.get_rate() > afk_mental:
                    try:
                        player.combo_add("MISS", event[1:])
                    except MentalDown:
                        break
                else:
                    player.combo_add("PERFECT")

            case "LiveStart" | "LiveEnd" | "FeverStart":
                if event == "FeverStart":
                    player.fevertime = True
                if centercard is not None:
                    for condition, effect in centercard.get_center_skill():
                        if CheckCenterSkillCondition(player, condition, centercard, event):
                            ApplyCenterSkillEffect(player, effect)
                if event == "LiveEnd":
                    break

            case "FeverEnd":
                player.fevertime = False
            case _:
                pass

    return {
        "final_score": player.score,
        "cards_played_log": d.card_log,
        "original_deck_index": original_deck_index,
        "deck_card_ids": deck_card_ids,
        "center_card": int(centercard.card_id)
    }
