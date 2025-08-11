import logging
import time
import os
from RCardData import db_load
from RChart import Chart, MusicDB
from RDeck import Deck
from RLiveStatus import PlayerAttributes
from SkillResolver import UseCardSkill, ApplyCenterSkillEffect, ApplyCenterAttribute, CheckCenterSkillCondition
from CardLevelConfig import convert_deck_to_simulator_format, DEATH_NOTE

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
    # 读取歌曲、卡牌、技能db
    musicdb = MusicDB()
    db_carddata = db_load(os.path.join("Data", "CardDatas.json"))
    db_skill = db_load(os.path.join("Data", "RhythmGameSkills.json"))
    db_skill.update(db_load(os.path.join("Data", "CenterSkills.json")))
    db_skill.update(db_load(os.path.join("Data", "CenterAttributes.json")))

    # 配置卡组、练度
    # 完整格式: (CardSeriesId, [卡牌等级, C位技能等级, 技能等级])

    d = Deck(db_carddata, db_skill, [(1011501, [120, 1, 9]),  # 沙知
                                     (1021523, [120, 7, 7]),  # 银河梢
                                     (1023901, [80, 1, 7]),  # BR慈
                                     (1033514, [100, 1, 1]),  # P乃
                                     (1032518, [100, 1, 1]),  # P沙
                                     (1031519, [120, 1, 7])  # P帆
                                     ])

    # 使用convert_deck_to_simulator_format时可只输入id列表
    # 此时需要在CardLevelConfig中自定义练度，未定义则默认全满级
    """
    d = Deck(
        db_carddata, db_skill,
        convert_deck_to_simulator_format(
            [1041513, 1021523, 1033514, 1022701, 1032518, 1043515]
        )
    )
    """

    # 歌曲、难度设置
    # 难度 01 / 02 / 03 / 04 对应 Normal / Hard / Expert / Master
    fixed_music_id = "305107"  # IDOME
    fixed_difficulty = "02"
    fixed_player_master_level = 50

    # 强制替换歌曲C位和颜色
    center_override = None  # 1052 #1032
    color_override = None  # 1 # 1=Smile 2=Pure 3=Cool

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

    logging.debug("\n--- 应用C位特性 ---")
    centercard = None
    afk_mental = 0
    for card in d.cards:
        cid = int(card.card_id)
        if cid in DEATH_NOTE:
            if afk_mental:
                afk_mental = min(afk_mental, DEATH_NOTE[cid])
            else:
                afk_mental = DEATH_NOTE[cid]
        if card.characters_id == c.music.CenterCharacterId:
            # DR优先C位，无DR则靠左为C位
            if not centercard or card.card_id[4] == "8":
                centercard = card
    if centercard:
        for target, effect in centercard.get_center_attribute():
            ApplyCenterAttribute(player, effect, target)

    logging.debug("\n--- C位特性应用完毕 ---")
    for card in d.cards:
        logging.debug(f"Cost: {card.cost:2}\t{card.full_name}")

    # 根据歌曲颜色计算三围、基础分
    d.appeal_calc(c.music.MusicType)
    player.basescore_calc(c.AllNoteSize)

    logging.debug(f"Appeal: {player.deck.appeal}")
    logging.debug(f"技能CD: {player.cooldown} 秒")

    # 插入开局cd
    c.ChartEvents.append((str(player.cooldown), "CDavailable"))
    c.ChartEvents.sort(key=lambda event: float(event[0]))

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

                elif afk_mental and player.mental.get_rate() >= afk_mental:
                    # 不同note类型和判定会影响扣血多少
                    # 模拟开局挂机到背水时需向combo_add()传入note类型(即event)
                    # 卡组有p吟/BR吟时自动模拟背水，可在DEATH_NOTE中添加其他背水血线
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
                    conditions, effects = d.topskill()
                    UseCardSkill(player, effects, conditions, cardnow)
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
                    conditions, effects = d.topskill()
                    UseCardSkill(player, effects, conditions, cardnow)
                    player.CDavailable = False
                    cdtime = str(float(timestamp) + player.cooldown)
                    c.ChartEvents.append((cdtime, "CDavailable"))
                    c.ChartEvents.sort(key=lambda event: float(event[0]))
                    cardnow = d.topcard()

            case "LiveStart" | "LiveEnd" | "FeverStart":
                if event == "FeverStart":
                    player.fevertime = True
                    logging.debug(f"\n【FEVER开始】\t时间: {timestamp}")
                if centercard != None:
                    logger.debug(f"\n尝试应用C位技能: {centercard.full_name}")
                    for condition, effect in centercard.get_center_skill():
                        if CheckCenterSkillCondition(player, condition, centercard, event):
                            ApplyCenterSkillEffect(player, effect)
                if event == "LiveEnd":
                    break

            case "FeverEnd":
                player.fevertime = False
                logging.debug(f"\n【FEVER结束】\t时间: {timestamp}")
            case _:
                logging.warning(f"未定义的事件: {event}\t时间: {timestamp}")

    logging.debug("\n--- 模拟结束 ---")
    logging.info(player)
    logging.info(f"打出记录: {d.card_log}")
    logging.info(f"打出次数: {len(d.card_log)}")
