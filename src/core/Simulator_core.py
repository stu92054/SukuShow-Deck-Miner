import logging
import os
import sys
from math import ceil
# 导入所有 R 模块和 db_load 函数
from .RCardData import db_load
from .RChart import Chart, MusicDB
from .RDeck import Deck
from .RLiveStatus import PlayerAttributes
from .SkillResolver import UseCardSkill, ApplyCenterSkillEffect, ApplyCenterAttribute, CheckCenterSkillCondition
from ..config.CardLevelConfig import DEATH_NOTE

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
    sys.exit(1)  # Exit with an error code


MISS_TIMING = {
    "Single": 0.125,
    "Hold": 0.125,
    "Flick": 0.100,
    "HoldMid": 0.070,
    "Trace": 0.070,
}

# 快轉優化用的 Note 類型集合
NOTE_TYPES = frozenset({"Single", "Hold", "HoldMid", "Flick", "Trace"})

def run_game_simulation(
    task_args: tuple  # (deck_card_data, chart_obj, player_master_level, original_deck_index, deck_card_ids, center_card_index, friendcard_id, fast_forward)
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
        original_deck_index (int): The index of this deck in the batch.
        deck_card_ids (list[int]): List of card IDs in the deck.
        center_card_index (int): Index of the center card (-1 for auto selection).
        friendcard_id (int): Friend card ID (None if no friend card).
        fast_forward (bool): Whether to enable fast-forward optimization (default True).

    Returns:
        dict: A dictionary containing key simulation results (e.g., final score, card log).
              You can expand this to return more detailed metrics.
    """
    # NOTE: DBs (MUSIC_DB, DB_CARDDATA, DB_SKILL) are now global to this module
    # and inherited by child processes (copy-on-write).
    if len(task_args) == 8:
        deck_card_data, chart_obj, player_master_level, original_deck_index, deck_card_ids, center_card_index, friendcard_id, fast_forward = task_args
    elif len(task_args) == 7:
        deck_card_data, chart_obj, player_master_level, original_deck_index, deck_card_ids, center_card_index, friendcard_id = task_args
        fast_forward = True
    else:
        raise ValueError(f"task_args 長度必須為 7 或 8，收到 {len(task_args)}")

    d = Deck(DB_CARDDATA, DB_SKILL, deck_card_data)
    c: Chart = chart_obj
    player = PlayerAttributes(masterlv=player_master_level)
    player.set_deck(d)

    # 處理助戰卡
    from .RDeck import Card
    centerfriend = False
    if friendcard_id:
        d.friend = Card.get_friend(DB_CARDDATA, DB_SKILL, friendcard_id)
        centerfriend = d.friend.characters_id == c.music.CenterCharacterId

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
            "center_card": int(centercard.card_id) if centercard is not None else None,
            "friend_card": friendcard_id
        }

    player.basescore_calc(c.AllNoteSize)
    # player.cooldown = int(player.cooldown * 1_000_000)

    # Dual-queue optimization: O(n^2) -> O(n log n)
    # Use pre-sorted chart events + heap for dynamic events
    import heapq
    chart_events = c.ChartEvents  # Pre-sorted list (read-only)
    extra_events = list()         # Heap for dynamic events
    heapq.heappush(extra_events, (player.cooldown, "CDavailable"))

    i_event = 0
    chart_length = len(chart_events)

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
        # 如果沒有剩餘的背水卡，血線重置為0（禁用背水）
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
            heapq.heappush(extra_events, (cdtime_float, "CDavailable"))
            cardnow = d.topcard()

    # 快轉優化用的緩存變數
    cached_ap_gain = 0.0
    cached_note_score = 0

    while i_event < chart_length or extra_events:
        # Choose the earliest event from either queue
        # 注意: MainBatch.py 會在傳入前將 chart_events 的 timestamp 轉為 float
        if i_event < chart_length and (not extra_events or chart_events[i_event][0] <= extra_events[0][0]):
            timestamp, event = chart_events[i_event]
            from_chart = True
        else:
            timestamp, event = heapq.heappop(extra_events)
            from_chart = False

        # === 快轉邏輯 (僅處理 chart_events 中的 Note) ===
        # 快轉條件：Combo >= 50, 無背水卡, 有待打的卡, 且無法發動技能
        if fast_forward and from_chart and event in NOTE_TYPES:
            can_fast_forward = (
                player.combo >= 50 and
                afk_mental == 0 and
                cardnow is not None and
                (not player.CDavailable or player.ap < cardnow.cost)
            )

            if can_fast_forward:
                # 計算緩存值
                cached_ap_gain = ceil(player.full_ap_plus * 1.5) / 10000
                cached_note_score = int(ceil(player.note_score["PERFECT+"] * player.voltage.bonus))

                # 計算終點 1: CD 轉好時刻
                if player.CDavailable:
                    next_cd_time = float('inf')
                else:
                    next_cd_time = extra_events[0][0] if extra_events else float('inf')

                # 計算終點 2: AP 足夠時刻
                next_ap_time = float('inf')
                if player.CDavailable and player.ap < cardnow.cost:
                    ap_deficit = cardnow.cost - player.ap
                    if cached_ap_gain > 0:
                        # 計算還需要幾個 note 才能累積足夠的 AP
                        notes_needed = int(ceil(ap_deficit / cached_ap_gain))
                        # AP 會在處理完第 (i_event + notes_needed - 1) 個 note 後達到要求
                        # 快轉應該在該 note 之前停止，讓正常流程處理並觸發技能
                        target_index = i_event + notes_needed - 1
                        if target_index < chart_length:
                            next_ap_time = chart_events[target_index][0]

                safe_horizon = min(next_cd_time, next_ap_time)

                # 只有當 safe_horizon 嚴格大於當前時間時才快轉
                # 否則讓正常流程處理當前 Note
                if safe_horizon > timestamp:
                    # 快轉迴圈 - 處理到 safe_horizon 之前的所有 Note
                    # 注意：當前事件還沒推進 i_event，先處理當前 Note
                    while i_event < chart_length:
                        ts, ev = chart_events[i_event]

                        # 停止條件 1: 超出安全時間 (這個 Note 可能觸發技能，需正常處理)
                        if ts >= safe_horizon:
                            break

                        # 停止條件 2: 遇到特殊事件
                        if ev not in NOTE_TYPES:
                            break

                        # 快速處理 Note
                        player.combo += 1
                        player.ap += cached_ap_gain
                        player.score += cached_note_score
                        combo_count += 1

                        i_event += 1

                    # 快轉後，回到主迴圈重新選擇下一個事件
                    continue

        # 推進 chart_events 索引 (如果是從 chart 取得)
        if from_chart:
            i_event += 1

        match event:
            case "Single" | "Hold" | "HoldMid" | "Flick" | "Trace":
                combo_count += 1
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"[NOTE] i_event={i_event}, time={timestamp:.3f}, type={event}, combo_before={player.combo}, score_before={player.score}")
                if afk_mental and player.mental.get_rate() > afk_mental:
                    # 檢查 MISS 是否會導致血量歸零
                    if event == "Trace" or event == "HoldMid":
                        miss_damage = player.mental.traceMinus
                    else:
                        miss_damage = player.mental.missMinus

                    will_die = (player.mental.current_hp <= miss_damage)

                    if will_die:
                        # 如果 MISS 會導致遊戲結束，改為 PERFECT+
                        player.combo_add("PERFECT+")
                    else:
                        # 需要仰卧起坐时，将 MISS 时机按判定窗口延后以提高精度
                        if flag_hanabi_ginko:
                            heapq.heappush(extra_events, (timestamp + MISS_TIMING[event], "_" + event))
                        else:
                            player.combo_add("MISS", event)
                else:
                    player.combo_add("PERFECT+")

                if player.CDavailable:
                    try_use_skill()

            case "CDavailable":
                player.CDavailable = True
                try_use_skill()

            case event if event[0] == "_":
                if player.mental.get_rate() > afk_mental:
                    # 延遲的 MISS（花火吟子模式）
                    note_type = event[1:]
                    if note_type == "Trace" or note_type == "HoldMid":
                        miss_damage = player.mental.traceMinus
                    else:
                        miss_damage = player.mental.missMinus

                    will_die = (player.mental.current_hp <= miss_damage)

                    if will_die:
                        # 如果 MISS 會導致遊戲結束，改為 PERFECT+
                        player.combo_add("PERFECT+")
                    else:
                        player.combo_add("MISS", note_type)
                else:
                    player.combo_add("PERFECT+")

            case "LiveStart" | "LiveEnd" | "FeverStart":
                if event == "FeverStart":
                    player.voltage.set_fever(True)
                if centercard is not None:
                    for condition, effect in centercard.get_center_skill():
                        if CheckCenterSkillCondition(player, condition, centercard, event):
                            ApplyCenterSkillEffect(player, effect)
                # 助戰卡 C 位技能
                if centerfriend:
                    for condition, effect in d.friend.get_center_skill():
                        if CheckCenterSkillCondition(player, condition, d.friend, event):
                            ApplyCenterSkillEffect(player, effect)
                if event == "LiveEnd":
                    break

            case "FeverEnd":
                player.voltage.set_fever(False)
            case _:
                pass

    return {
        "final_score": player.score,
        "cards_played_log": d.card_log,
        "original_deck_index": original_deck_index,
        "deck_card_ids": deck_card_ids,
        "center_card": int(centercard.card_id),
        "friend_card": friendcard_id
    }
