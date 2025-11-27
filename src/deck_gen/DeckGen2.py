import itertools
import json
import logging
import os
import time
from collections import defaultdict, Counter

from ..core.RChart import Chart, MusicDB
from ..core.RDeck import Rarity
from ..core.Simulator_core import DB_CARDDATA, DB_SKILL
from ..core.SkillResolver import SkillEffectType
logger = logging.getLogger(__name__)

CARD_CONFLICT_RULES = {
    # P吟、Blast芽、暧昧Mayday、水果帆、水果吟、太阳沙、COCO夏芽
    1031530: {1041513, 1042515, 1043515, 1031531, 1041516, 1032529, 1043516},  # idome帆
    1032528: {1041513, 1042515, 1043515, 1031531, 1041516, 1032529, 1043516},  # idome沙
    1033524: {1041513, 1042515, 1043515, 1031531, 1041516, 1032529, 1043516},  # idome乃
}


def has_card_conflict(card_ids_in_deck: set[int]) -> bool:
    """
    检查卡组中是否存在冲突卡牌。
    """
    for restricted_card_id, conflicting_ids in CARD_CONFLICT_RULES.items():
        if restricted_card_id in card_ids_in_deck:
            if any(c_id in card_ids_in_deck for c_id in conflicting_ids):
                return True
    return False


DB_TAG = {}
"""
卡牌id -> 技能效果类型、稀有度
多段同类效果只记录一个tag
"""
for data in DB_CARDDATA.values():
    skill_series_id = data["RhythmGameSkillSeriesId"][-1]
    skill_effect = DB_SKILL[str(skill_series_id * 100 + 14)]["RhythmGameSkillEffectId"]
    tag = set()
    for effect in skill_effect:
        tag.add(SkillEffectType(effect // 100000000))
    tag.add(Rarity(data["Rarity"]))
    DB_TAG[data["CardSeriesId"]] = tag


def count_skill_tags(card_ids_input: list[int]):
    """
    计算给定卡牌ID列表中所有卡牌的技能tag的出现次数。

    Args:
        card_ids_input (list[int]): 包含6个卡牌ID的列表。

    Returns:
        collections.Counter: 一个Counter对象，键是tag，值是其出现次数。
    """
    # 直接使用Counter，避免创建中间列表
    tag_counts = Counter()

    for card_id in card_ids_input:
        if card_id in DB_TAG:
            # 将当前卡牌的所有tag（一个集合）累加到Counter中
            tag_counts.update(DB_TAG[card_id])

    return tag_counts


def generate_role_distributions(all_characters, allow_double_cards=True):
    """
    生成6个卡位的角色分布

    Args:
        all_characters: 可用角色ID列表
        allow_double_cards: 是否允许双卡
            - True: LGP模式，允许0-3个角色双卡
            - False: 日常模式，每个角色最多1张卡

    Returns:
        角色分布列表，每个分布是一个长度6的角色ID元组
    """
    results = []

    if allow_double_cards:
        # LGP模式：允许0,1,2,3个角色双卡
        for double_count in range(0, 4):
            for doubles in itertools.combinations(all_characters, double_count):
                remaining_roles_needed = 6 - 2 * double_count
                for singles in itertools.combinations(
                    [r for r in all_characters if r not in doubles],
                    remaining_roles_needed
                ):
                    distribution = list(doubles) * 2 + list(singles)
                    results.append(tuple(sorted(distribution)))
    else:
        # 日常模式：每个角色最多1张卡（6个不同角色）
        if len(all_characters) >= 6:
            for singles in itertools.combinations(all_characters, 6):
                results.append(tuple(sorted(singles)))

    return list(set(results))


def load_simulated_decks(path: str):
    simulated_decks = set()
    if path and os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for result in data:
            current_deck_card_ids = result['deck_card_ids']
            sorted_card_ids_tuple = tuple(sorted(current_deck_card_ids))
            simulated_decks.add(sorted_card_ids_tuple)
        logger.info(f"{len(simulated_decks)} simulation results loaded.")
    return simulated_decks


class DeckGeneratorWithDoubleCards:
    def __init__(self, cardpool: list[int], mustcards: list[list[int]], center_char=None, force_dr=False, log_path: str = None, allow_double_cards=True):
        """
        卡组生成器（支持单卡/双卡模式）

        Args:
            cardpool: 卡池列表
            mustcards: 必须包含的卡片列表 [mustcards_all, mustcards_any, mustskills_all]
            center_char: C位角色ID
            force_dr: 是否强制包含DR卡
            log_path: 日志路径（用于去重已模拟的卡组）
            allow_double_cards: 是否允许双卡（True=LGP模式，False=日常模式）
        """
        self.cardpool = cardpool
        self.center_char = center_char
        self.char_id_to_cards = defaultdict(list)
        self.force_dr = force_dr
        self.mustcards = mustcards
        self.allow_double_cards = allow_double_cards
        self.simulated_decks = load_simulated_decks(log_path)
        for card_id in self.cardpool:
            char_id = card_id // 1000
            self.char_id_to_cards[char_id].append(card_id)
        self.all_available_chars = list(self.char_id_to_cards.keys())

        # 预计算数量
        self.total_decks = self.compute_total_count()

    def __iter__(self):
        min_chars_required = 6 if not self.allow_double_cards else 3
        if len(self.all_available_chars) < min_chars_required:
            return
        for char_distribution in generate_role_distributions(self.all_available_chars, self.allow_double_cards):
            if self.center_char and self.center_char not in char_distribution:
                continue
            yield from self._generate_decks_for_distribution(char_distribution)

    def check_skill_tags(self, tag_counts: Counter, force_dr=False):
        """
        检查卡组中的技能类型是否符合给定条件。

        - LGP 模式（双卡）：DR数量<=1
        - 日常模式（单卡）：不限制DR数量
        """
        # 检查必须技能
        if not all(tag_counts[skill] for skill in self.mustcards[2]):
            return False

        # DR 数量限制
        if self.allow_double_cards:
            # LGP 模式：限制 DR <= 1
            if tag_counts[Rarity.DR] > 1:
                return False
        # 日常模式：不限制 DR 数量

        # force_dr 检查
        if force_dr and tag_counts[Rarity.DR] == 0:
            return False

        return True

    def _generate_valid_permutations(self, deck):
        """
        PyPy 优化：

        规则：
        - 第一位不能是分卡 (ScoreGain)
        - 最后一位不能是洗牌卡 (DeckReset)
        """
        # 预先分类卡牌
        score_gain_cards = set()
        deck_reset_cards = set()

        for card_id in deck:
            tags = DB_TAG[card_id]
            if SkillEffectType.ScoreGain in tags:
                score_gain_cards.add(card_id)
            if SkillEffectType.DeckReset in tags:
                deck_reset_cards.add(card_id)

        # PyPy JIT 高度优化 itertools.permutations
        # 全排列+过滤比嵌套循环更快
        for perm in itertools.permutations(deck):
            # 第一位不能是分卡
            if perm[0] in score_gain_cards:
                continue
            # 最后一位不能是洗牌卡
            if perm[-1] in deck_reset_cards:
                continue
            yield perm

    def _count_valid_permutations(self, deck):
        """
        计算有效排列的数量，用于预估总卡组数。

        注意：由于C位选择逻辑的修改，每个deck中有多张C位角色卡时，
        会生成多个任务（每张C位卡一个任务）。

        改用實際計數而非公式計算，以確保準確性。
        """
        # 统计C位角色卡的数量
        center_card_count = 0
        if self.center_char:
            for card_id in deck:
                char_id = card_id // 1000
                if char_id == self.center_char:
                    center_card_count += 1

        # 如果没有C位卡，默认为1（不影响计算）
        if center_card_count == 0:
            center_card_count = 1

        # 實際計數有效排列
        # 使用與 _generate_valid_permutations 相同的邏輯
        score_gain_cards = set()
        deck_reset_cards = set()

        for card_id in deck:
            tags = DB_TAG[card_id]
            if SkillEffectType.ScoreGain in tags:
                score_gain_cards.add(card_id)
            if SkillEffectType.DeckReset in tags:
                deck_reset_cards.add(card_id)

        # 計數符合條件的排列
        valid_count = 0
        for perm in itertools.permutations(deck):
            # 第一位不能是分卡
            if perm[0] in score_gain_cards:
                continue
            # 最后一位不能是洗牌卡
            if perm[-1] in deck_reset_cards:
                continue
            valid_count += 1

        # 乘以C位卡數量（每張C位卡都會生成一個獨立任務）
        return valid_count * center_card_count

    def _generate_decks_for_distribution(self, char_distribution):
        char_counts = {char_id: char_distribution.count(char_id) for char_id in set(char_distribution)}
        card_choices_per_char = []
        for char_id, count in char_counts.items():
            card_pool = self.char_id_to_cards[char_id]
            if count == 1:
                card_choices_per_char.append([(card_id,) for card_id in card_pool])
            elif count == 2:
                card_choices_per_char.append(list(itertools.combinations(card_pool, 2)))
            else:
                raise ValueError("角色数量超过2，不符合规则")

        for combo in itertools.product(*card_choices_per_char):
            deck = []
            for item in combo:
                deck.extend(item)
            if tuple(sorted(deck)) in self.simulated_decks:
                continue
            if self.mustcards[0]:
                if not all(card in deck for card in self.mustcards[0]):
                    continue
            if self.mustcards[1]:
                if not any(card in deck for card in self.mustcards[1]):
                    continue
            if has_card_conflict(set(deck)):
                continue
            if self.check_skill_tags(count_skill_tags(deck), self.force_dr):
                # 使用优化的排列生成器，避免生成无效排列
                yield from self._generate_valid_permutations(deck)

    def _count_decks_for_distribution(self, char_distribution):
        char_counts = {char_id: char_distribution.count(char_id) for char_id in set(char_distribution)}
        card_choices_per_char = []
        for char_id, count in char_counts.items():
            card_pool = self.char_id_to_cards[char_id]
            if count == 1:
                card_choices_per_char.append([(card_id,) for card_id in card_pool])
            elif count == 2:
                card_choices_per_char.append(list(itertools.combinations(card_pool, 2)))
            else:
                raise ValueError("角色数量超过2，不符合规则")

        total = 0
        for combo in itertools.product(*card_choices_per_char):
            deck = []
            for item in combo:
                deck.extend(item)
            if tuple(sorted(deck)) in self.simulated_decks:
                continue
            if self.mustcards[0]:
                if not all(card in deck for card in self.mustcards[0]):
                    continue
            if self.mustcards[1]:
                if not any(card in deck for card in self.mustcards[1]):
                    continue
            if has_card_conflict(set(deck)):
                continue
            if self.check_skill_tags(count_skill_tags(deck), self.force_dr):
                # 使用优化的计数方法
                total += self._count_valid_permutations(deck)
        return total

    def compute_total_count(self):
        total = 0
        min_chars_required = 6 if not self.allow_double_cards else 3
        if len(self.all_available_chars) < min_chars_required:
            return 0
        for char_distribution in generate_role_distributions(self.all_available_chars, self.allow_double_cards):
            if self.center_char and self.center_char not in char_distribution:
                continue
            total += self._count_decks_for_distribution(char_distribution)
        return total


def generate_decks_with_double_cards(cardpool: list[int], mustcards: list[list[int]], center_char: int = None, force_dr: bool = False, log_path: str = None, allow_double_cards: bool = True):
    """
    外部接口函数，返回卡组生成器（支持单卡/双卡模式）

    Args:
        cardpool: 卡池列表
        mustcards: 必须包含的卡片列表 [mustcards_all, mustcards_any, mustskills_all]
        center_char: C位角色ID
        force_dr: 是否强制包含DR卡
        log_path: 日志路径（用于去重已模拟的卡组）
        allow_double_cards: 是否允许双卡（True=LGP模式，False=日常模式）

    Returns:
        DeckGeneratorWithDoubleCards 实例
    """
    return DeckGeneratorWithDoubleCards(cardpool, mustcards, center_char, force_dr, log_path, allow_double_cards)


if __name__ == "__main__":
    card_ids = [
        1011501,  # 沙知
        1021523, 1021901, 1021512, 1021701,  # 梢: 银河 BR 舞会 LR
        1022521, 1022701, 1022901, 1022504,  # 缀: 银河 LR BR 明月
        1023520, 1023701, 1023901,  # 慈: 银河 LR BR
        1031519, 1031530, 1031901,  # 帆: 舞会 IDOME BR(2024)
        1032518, 1032528, 1032901,  # 沙: 舞会 IDOME BR
        1033514, 1033524, 1033901,  # 乃: 舞会 IDOME BR
        1041513,  # 吟: 舞会
        # 1042515, # 1042512,  # 铃: 暧昧mayday 舞会
        1043515,  # 芽: BLAST 舞会1043512
        # 1051503, #1051501, 1051502,  # 泉: 天地黎明 DB RF
        1052901, 1052503,  # 1052504  # 塞: BR 十六夜 天地黎明
    ]

    MUSIC_DB = MusicDB()
    fixed_music_id = "405302"  # aiscream
    fixed_difficulty = "02"
    pre_initialized_chart = Chart(MUSIC_DB, fixed_music_id, fixed_difficulty)

    decks_generator = generate_decks_with_double_cards(
        card_ids, pre_initialized_chart.music.CenterCharacterId
    )
    total_decks_to_simulate = decks_generator.total_decks
    print(f"预计算总共将模拟 {total_decks_to_simulate} 个卡组。")

    time_list = []
    for _ in range(10):
        start_time = time.time()
        for deck in decks_generator:
            pass
        end_time = time.time()
        time_list.append(end_time - start_time)
    print(f"avg: {sum(time_list)/len(time_list)}")
