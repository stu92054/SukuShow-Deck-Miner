import logging
import time
import os
from RCardData import db_load
from RChart import Chart, MusicDB
from RDeck import Deck
from RLiveStatus import PlayerAttributes
from SkillResolver import UseCardSkill, ApplyCenterSkillEffect, ApplyCenterAttribute, CheckCenterSkillCondition
from CardLevelConfig import convert_deck_to_simulator_format, fix_windows_console_encoding, DEATH_NOTE

logger = logging.getLogger(__name__)

logging.TIMING = 5
logging.addLevelName(logging.TIMING, "TIMING")


def timing(self, message, *args, **kws):
    if self.isEnabledFor(logging.TIMING):
        self._log(logging.TIMING, message, args, **kws)


logging.Logger.timing = timing

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    # filename=f"log\log_{int(time.time())}.txt",
    # encoding="utf-8"
)

if __name__ == "__main__":
    fix_windows_console_encoding()

    # 嘗試讀取 YAML 配置中的自定義練度（如果有的話）
    custom_card_levels = None
    try:
        from config_manager import get_config
        yaml_config = get_config()
        custom_card_levels = yaml_config.get_card_levels()
        if custom_card_levels:
            logger.info(f"從配置載入 {len(custom_card_levels)} 張卡牌的自定義練度")
    except (ImportError, ValueError, FileNotFoundError):
        # 沒有配置管理器或沒有配置檔案，使用 CardLevelConfig.py
        logger.info("使用 CardLevelConfig.py 中的練度設定")
        pass

    # 读取歌曲、卡牌、技能db
    musicdb = MusicDB()
    db_carddata = db_load(os.path.join("Data", "CardDatas.json"))
    db_skill = db_load(os.path.join("Data", "RhythmGameSkills.json"))
    db_skill.update(db_load(os.path.join("Data", "CenterSkills.json")))
    db_skill.update(db_load(os.path.join("Data", "CenterAttributes.json")))

    # 配置卡组、练度
    # 完整格式: (CardSeriesId, [卡牌等级, C位技能等级, 技能等级])

    """
    d = Deck(db_carddata, db_skill, [(1011501, [120, 1, 9]),  # 沙知
                                     (1021523, [120, 7, 7]),  # 银河梢
                                     (1023901, [80, 1, 7]),  # BR慈
                                     (1033514, [100, 1, 1]),  # P乃
                                     (1032518, [100, 1, 1]),  # P沙
                                     (1031519, [120, 1, 7])  # P帆
                                     ])
    """
    # 使用convert_deck_to_simulator_format时可只输入id列表
    # 此时需要在CardLevelConfig中自定义练度，未定义则默认全满级
    # 如果有 YAML 配置，會優先使用 YAML 中的 card_levels

    d = Deck(
        db_carddata, db_skill,
        convert_deck_to_simulator_format(
            [1041513, 1021701, 1021523, 1022701, 1043516, 1043802],
            custom_card_levels
        )
    )

    # 歌曲、难度设置
    # 难度 01 / 02 / 03 / 04 对应 Normal / Hard / Expert / Master
    fixed_music_id = "405105"  # Very! Very! COCO夏っ
    fixed_difficulty = "02"
    fixed_player_master_level = 50

    # 强制替换歌曲C位和颜色
    center_override = None  # 1052 #1032
    color_override = None  # 1 # 1=Smile 2=Pure 3=Cool

    # C位卡选择：指定使用卡组中第几张C位角色的卡作为C位
    # None: 自动选择（DR优先，无DR则第一张）
    # 0: 使用第1张C位角色的卡
    # 1: 使用第2张C位角色的卡
    # -1: 测试所有C位选择并输出对比（会运行多次模拟）
    center_card_choice = -1

    c = Chart(musicdb, fixed_music_id, fixed_difficulty)
    player = PlayerAttributes(fixed_player_master_level)
    player.set_deck(d)

    if center_override:
        c.music.CenterCharacterId = center_override
    if color_override:
        c.music.MusicType = color_override

    logging.info("--- 卡组信息 ---")
    for card in d.cards:
        logging.info(f"Cost: {card.cost:2}\t{card.full_name}")

    # 找出所有C位角色的卡片
    center_char_id = c.music.CenterCharacterId
    center_cards_indices = []
    afk_mental = 0
    flag_hanabi_ginko = False

    for idx, card in enumerate(d.cards):
        cid = int(card.card_id)
        if cid in DEATH_NOTE:
            if afk_mental:
                afk_mental = min(afk_mental, DEATH_NOTE[cid])
            else:
                afk_mental = DEATH_NOTE[cid]
        if cid == 1041517:
            flag_hanabi_ginko = True
        if card.characters_id == center_char_id:
            center_cards_indices.append((idx, card))

    logging.info(f"\n找到 {len(center_cards_indices)} 张C位角色 ({center_char_id}) 的卡片")
    for idx, card in center_cards_indices:
        logging.info(f"  索引 {idx}: {card.full_name}")

    if not center_cards_indices:
        logging.error("错误：卡组中没有C位角色的卡片！")
        exit(1)

    # 根据center_card_choice决定测试哪些C位
    if center_card_choice == -1:
        # 测试所有C位选择
        logging.info(f"\n将测试所有 {len(center_cards_indices)} 种C位选择")
        center_cards_to_test = center_cards_indices
    elif center_card_choice is None:
        # 自动选择（DR优先）
        dr_card = None
        first_card = None
        for idx, card in center_cards_indices:
            if first_card is None:
                first_card = (idx, card)
            if card.card_id[4] == "8":  # DR卡
                dr_card = (idx, card)
                break
        center_cards_to_test = [dr_card if dr_card else first_card]
    elif 0 <= center_card_choice < len(center_cards_indices):
        # 使用指定的C位卡
        center_cards_to_test = [center_cards_indices[center_card_choice]]
    else:
        logging.error(f"错误：center_card_choice={center_card_choice} 无效！")
        exit(1)

    # 注意：由于原有代码结构的限制，这里只能选择一个C位来运行
    # 如果要测试所有C位，需要重构整个模拟循环
    # 这里我们选择第一个来运行，并输出警告
    if len(center_cards_to_test) > 1:
        logging.warning(f"\n{'='*80}")
        logging.warning(f"警告：MainSingle.py 暂不支持运行多次模拟对比")
        logging.warning(f"将只使用第一个C位选择运行")
        logging.warning(f"如需测试所有C位，请使用 MainBatch.py")
        logging.warning(f"{'='*80}\n")

    center_idx, centercard = center_cards_to_test[0]
    logging.info(f"\n使用 {centercard.full_name} 作为C位 (索引 {center_idx})")

    logging.debug("\n--- 应用C位特性 ---")
    if centercard:
        for target, effect in centercard.get_center_attribute():
            ApplyCenterAttribute(player, effect, target)

    logging.debug("\n--- C位特性应用完毕 ---")
    for card in d.cards:
        logging.debug(f"Cost: {card.cost:2}\t{card.full_name}")

    # 根据歌曲颜色计算三围、基础分
    d.appeal_calc(c.music.MusicType)
    player.hp_calc()
    player.basescore_calc(c.AllNoteSize)

    logging.debug(f"Appeal: {player.deck.appeal}")
    logging.debug(f"技能CD: {player.cooldown} 秒")

    # 插入开局cd
    c.ChartEvents.append((str(player.cooldown), "CDavailable"))
    c.ChartEvents.sort(key=lambda event: float(event[0]))

    MISS_TIMING = {
        "Single": 0.125,
        "Hold": 0.125,
        "Flick": 0.100,
        "HoldMid": 0.070,
        "Trace": 0.070,
    }

    logging.info(f"\n--- 开始模拟: {c.music.Title} ({fixed_difficulty})  ---")
    i = 0
    combo_count = 0
    cardnow = d.topcard()
    while i < len(c.ChartEvents):
        timestamp, event = c.ChartEvents[i]
        i += 1
        match event:
            case "Single" | "Hold" | "HoldMid" | "Flick" | "Trace":
                combo_count += 1
                if combo_count in []:  # 按需模拟其他判定/策略
                    player.combo_add("GOOD")
                    # player.combo_add("BAD", event)

                elif afk_mental and player.mental.get_rate() > afk_mental:
                    # 不同note类型和判定会影响扣血多少
                    # 模拟开局挂机到背水时需向combo_add()传入note类型(即event)
                    # 卡组有p吟/BR吟时自动模拟背水，可在DEATH_NOTE中添加其他背水血线

                    # 檢查 MISS 是否會導致血量歸零
                    if event == "Trace" or event == "HoldMid":
                        miss_damage = player.mental.traceMinus
                    else:
                        miss_damage = player.mental.missMinus

                    will_die = (player.mental.current_hp <= miss_damage)

                    if will_die:
                        # 如果 MISS 會導致遊戲結束，改為 PERFECT
                        player.combo_add("PERFECT")
                        logger.timing(f"[连击{player.combo}x]\t总分: {player.score}\t时间: {timestamp}\t{event} (避免血量歸零)")
                    else:
                        # 需要仰卧起坐时，将 MISS 时机按判定窗口延后以提高精度
                        if flag_hanabi_ginko:
                            misstime = str(float(timestamp) + MISS_TIMING[event])
                            c.ChartEvents.append((misstime, "_" + event))
                            c.ChartEvents.sort(key=lambda event: float(event[0]))
                        else:
                            player.combo_add("MISS", event)
                            logger.timing(f"[连击{player.combo}x]\t总分: {player.score}\t时间: {timestamp}\t{event}")
                elif combo_count in []:
                    player.combo_add("GREAT")
                    # 连击计数、AP速度更新、回复AP、扣血
                    logger.timing(f"[连击{player.combo}x]\t总分: {player.score}\t时间: {timestamp}\t{event}")
                else:
                    player.combo_add("PERFECT")
                    # 连击计数、AP速度更新、回复AP、扣血
                    logger.timing(f"[连击{player.combo}x]\t总分: {player.score}\t时间: {timestamp}\t{event}")
                # AP足够 且 冷却完毕 时打出技能
                if cardnow and player.ap >= cardnow.cost and player.CDavailable:
                    player.ap -= cardnow.cost
                    logger.debug(f"\n打出技能: {cardnow.full_name}\t时间: {timestamp}")

                    # 記錄打出前被除外的卡片數量
                    cards_except_before = sum(1 for card in d.cards if card.is_except)

                    conditions, effects = d.topskill()
                    UseCardSkill(player, effects, conditions, cardnow)

                    # 檢查是否有新的卡片被除外，重新計算血線
                    cards_except_after = sum(1 for card in d.cards if card.is_except)
                    if cards_except_after > cards_except_before:
                        # 動態重新計算血線
                        new_afk_mental = 0
                        for card in d.cards:
                            if not card.is_except:
                                cid = int(card.card_id)
                                if cid in DEATH_NOTE:
                                    if new_afk_mental:
                                        new_afk_mental = min(new_afk_mental, DEATH_NOTE[cid])
                                    else:
                                        new_afk_mental = DEATH_NOTE[cid]
                        # 如果沒有剩餘的背水卡，血線重置為100%（不需要背水）
                        if new_afk_mental == 0:
                            new_afk_mental = 100
                        afk_mental = new_afk_mental
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"  動態血線更新: {afk_mental}%")

                    player.CDavailable = False
                    cdtime = str(float(timestamp) + player.cooldown)
                    c.ChartEvents.append((cdtime, "CDavailable"))
                    c.ChartEvents.sort(key=lambda event: float(event[0]))
                    cardnow = d.topcard()

            case "CDavailable":
                player.CDavailable = True
                logger.timing(f"[CD结束]\t总分: {player.score}\t时间: {timestamp}")
                if cardnow and player.ap >= cardnow.cost:
                    player.ap -= cardnow.cost
                    logger.debug(f"\n打出技能: {cardnow.full_name}\t时间: {timestamp}")

                    # 記錄打出前被除外的卡片數量
                    cards_except_before = sum(1 for card in d.cards if card.is_except)

                    conditions, effects = d.topskill()
                    UseCardSkill(player, effects, conditions, cardnow)

                    # 檢查是否有新的卡片被除外，重新計算血線
                    cards_except_after = sum(1 for card in d.cards if card.is_except)
                    if cards_except_after > cards_except_before:
                        # 動態重新計算血線
                        new_afk_mental = 0
                        for card in d.cards:
                            if not card.is_except:
                                cid = int(card.card_id)
                                if cid in DEATH_NOTE:
                                    if new_afk_mental:
                                        new_afk_mental = min(new_afk_mental, DEATH_NOTE[cid])
                                    else:
                                        new_afk_mental = DEATH_NOTE[cid]
                        # 如果沒有剩餘的背水卡，血線重置為100%（不需要背水）
                        if new_afk_mental == 0:
                            new_afk_mental = 100
                        afk_mental = new_afk_mental
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"  動態血線更新: {afk_mental}%")

                    player.CDavailable = False
                    cdtime = str(float(timestamp) + player.cooldown)
                    c.ChartEvents.append((cdtime, "CDavailable"))
                    c.ChartEvents.sort(key=lambda event: float(event[0]))
                    cardnow = d.topcard()

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
                        # 如果 MISS 會導致遊戲結束，改為 PERFECT
                        player.combo_add("PERFECT")
                        logger.timing(f"[连击{player.combo}x]\t总分: {player.score}\t时间: {timestamp}\t{note_type} (避免血量歸零)")
                    else:
                        player.combo_add("MISS", note_type)
                        logger.timing(f"[连击{player.combo}x]\t总分: {player.score}\t时间: {timestamp}\tMISS: {note_type}")
                else:
                    player.combo_add("PERFECT")
                    logger.timing(f"[连击{player.combo}x]\t总分: {player.score}\t时间: {timestamp}\t{event[1:]} (延后)")

            case "LiveStart" | "LiveEnd" | "FeverStart":
                if event == "FeverStart":
                    player.voltage.set_fever(True)
                    logging.debug(f"\n【FEVER开始】\t时间: {timestamp}")
                if centercard != None:
                    logger.debug(f"\n尝试应用C位技能: {centercard.full_name}")
                    for condition, effect in centercard.get_center_skill():
                        if CheckCenterSkillCondition(player, condition, centercard, event):
                            ApplyCenterSkillEffect(player, effect)
                if event == "LiveEnd":
                    break

            case "FeverEnd":
                player.voltage.set_fever(False)
                logging.debug(f"\n【FEVER结束】\t时间: {timestamp}")
            case _:
                logging.warning(f"未定义的事件: {event}\t时间: {timestamp}")

    logging.debug("\n--- 模拟结束 ---")
    logging.info(player)
    logging.info(f"打出记录: {d.card_log}")
    logging.info(f"打出次数: {len(d.card_log)}")
