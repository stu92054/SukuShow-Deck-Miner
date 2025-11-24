import itertools
import math
from collections import defaultdict
from ..core.RCardData import db_load

CHAR_ORDERED_PRIORITIES = [
    # 1011,  # 默认沙知优先级最高
    # 1041,  # 其次P吟，模拟其他吟子时需删除
]


def get_char_priority_rank(characters_id):
    """
    根据 CharactersId 获取其在优先级列表中的排名。
    排名越小优先级越高。不在列表中的 CharactersId 返回一个较大的值（最低优先级）。
    """
    try:
        return CHAR_ORDERED_PRIORITIES.index(characters_id)
    except ValueError:
        return len(CHAR_ORDERED_PRIORITIES)  # 最低优先级


CARD_CONFLICT_RULES = {
    1041513: {1031530, 1032528, 1033524},  # P吟 → idome
    1043515: {1031530, 1032528, 1033524},  # blast芽 → idome
    1042515: {1031530, 1032528, 1033524},  # 暧昧mayday → idome
    # 你可以根据需要添加更多规则
    # 10002: {10001},
    # 10003: {10001},
    # 10004: {10001},
}


def parse_card_id_for_char_and_rarity(card_id: int) -> tuple[int, int]:
    """
    从 CardSeriesId 中解析 CharactersId 和 Rarity。
    假设 CardSeriesId 为 int 类型，前四位是 CharactersId，第五位是 Rarity。
    例如：1011501 -> CharactersId=1011, Rarity=5
    """
    card_id_str = str(card_id)
    if len(card_id_str) < 5:
        # 处理异常情况，或者返回默认值
        raise ValueError(f"Invalid CardSeriesId format: {card_id}")

    characters_id = int(card_id_str[:4])
    rarity = int(card_id_str[4])  # 第五位为 Rarity
    return characters_id, rarity


# 配置允许纳入卡组的卡牌稀有度
# R = 3; SR = 4; UR = 5; LR = 7; DR = 8; BR = 9 #
# ALLOWED_RARITIES = {5, 7, 9}  # 将可接受的稀有度定义为集合以便快速查找


def has_card_conflict(card_ids_in_deck: set[int]) -> bool:
    """
    Checks if the given set of card IDs contains any conflicting pairs based on CARD_CONFLICT_RULES.
    """
    for restricted_card_id, conflicting_ids in CARD_CONFLICT_RULES.items():
        if restricted_card_id in card_ids_in_deck:  # If card A is in the deck
            # Check if any of B, C, D are also in the deck
            if any(c_id in card_ids_in_deck for c_id in conflicting_ids):
                return True  # Conflict found
    return False


class DeckGeneratorWithCount:
    def __init__(self, card_ids_to_consider: list[int], center_char=None):  # <--- 不再接收 card_data_full
        self.card_ids_to_consider = card_ids_to_consider
        self.center_char = center_char
        self.char_id_to_cards = defaultdict(list)
        # 现在，我们遍历 card_ids_to_consider，直接解析出 CharactersId 和 Rarity
        for card_id in self.card_ids_to_consider:
            char_id = card_id // 1000
            self.char_id_to_cards[char_id].append(card_id)

        self.all_available_chars = list(self.char_id_to_cards.keys())

        # 预计算总数
        self._total_count = self._calculate_total_decks_count()

    def _calculate_total_decks_count(self) -> int:
        """
        在不实际生成完整卡牌字典的情况下，计算满足条件的卡组总数。
        这会遍历所有组合并应用剪枝规则。
        """
        if len(self.all_available_chars) < 6:
            return 0

        count = 0
        for chosen_char_ids_tuple in itertools.combinations(self.all_available_chars, 6):
            if self.center_char and self.center_char not in chosen_char_ids_tuple:
                continue
            chosen_char_ids_for_this_deck = list(chosen_char_ids_tuple)

            def _count_recursive(current_permutation_card_ids: list[int], current_permutation_char_ids_set: set[int], depth: int):
                nonlocal count

                if depth == 6:
                    count += 1
                    return

                highest_priority_remaining_char_in_deck = None
                if CHAR_ORDERED_PRIORITIES:
                    min_rank = float('inf')
                    for char_id in chosen_char_ids_for_this_deck:
                        if char_id not in current_permutation_char_ids_set:
                            rank = get_char_priority_rank(char_id)
                            if rank < min_rank:
                                min_rank = rank
                                highest_priority_remaining_char_in_deck = char_id

                if highest_priority_remaining_char_in_deck is not None and \
                   highest_priority_remaining_char_in_deck in CHAR_ORDERED_PRIORITIES:

                    # 遍历该角色下所有可用的 card_id
                    for card_id in self.char_id_to_cards[highest_priority_remaining_char_in_deck]:
                        _count_recursive(
                            current_permutation_card_ids + [card_id],  # 只传递 card_id
                            current_permutation_char_ids_set.union({highest_priority_remaining_char_in_deck}),
                            depth + 1
                        )
                else:
                    remaining_chars_for_itertools = [
                        char_id for char_id in chosen_char_ids_for_this_deck
                        if char_id not in current_permutation_char_ids_set
                    ]

                    if not remaining_chars_for_itertools and depth < 6:
                        return

                    # 列表的列表，现在每个子列表都包含 CardSeriesId
                    lists_of_remaining_card_ids = [
                        self.char_id_to_cards[char_id] for char_id in remaining_chars_for_itertools
                    ]

                    for combo_of_remaining_card_ids in itertools.product(*lists_of_remaining_card_ids):
                        partial_deck_card_ids_for_composition_check = current_permutation_card_ids + \
                            list(combo_of_remaining_card_ids)

                        current_composition_card_ids_set = set(partial_deck_card_ids_for_composition_check)

                        if not has_card_conflict(current_composition_card_ids_set):
                            num_remaining_slots = len(combo_of_remaining_card_ids)
                            count += math.factorial(num_remaining_slots)
            _count_recursive([], set(), 0)
        return count

    def __iter__(self):
        """
        实现迭代器协议，实际生成卡组。
        这里修改为只 yield 卡牌的 CardSeriesId 列表。
        """
        if len(self.all_available_chars) < 6:
            return

        for chosen_char_ids_tuple in itertools.combinations(self.all_available_chars, 6):
            if self.center_char and self.center_char not in chosen_char_ids_tuple:
                continue
            chosen_char_ids_for_this_deck = list(chosen_char_ids_tuple)

            def _generate_recursive(current_permutation_card_ids: list[int], current_permutation_char_ids_set: set[int], depth: int):
                if depth == 6:
                    yield tuple(current_permutation_card_ids)  # <--- 只 yield CardSeriesId 列表
                    return

                highest_priority_remaining_char_in_deck = None
                if CHAR_ORDERED_PRIORITIES:
                    min_rank = float('inf')
                    for char_id in chosen_char_ids_for_this_deck:
                        if char_id not in current_permutation_char_ids_set:
                            rank = get_char_priority_rank(char_id)
                            if rank < min_rank:
                                min_rank = rank
                                highest_priority_remaining_char_in_deck = char_id

                if highest_priority_remaining_char_in_deck is not None and \
                   highest_priority_remaining_char_in_deck in CHAR_ORDERED_PRIORITIES:

                    for card_id in self.char_id_to_cards[highest_priority_remaining_char_in_deck]:
                        yield from _generate_recursive(
                            current_permutation_card_ids + [card_id],  # <--- 传递 CardSeriesId
                            current_permutation_char_ids_set.union({highest_priority_remaining_char_in_deck}),
                            depth + 1
                        )
                else:
                    remaining_chars_for_itertools = [
                        char_id for char_id in chosen_char_ids_for_this_deck
                        if char_id not in current_permutation_char_ids_set
                    ]

                    if not remaining_chars_for_itertools and depth < 6:
                        return

                    lists_of_remaining_card_ids = [
                        self.char_id_to_cards[char_id] for char_id in remaining_chars_for_itertools
                    ]

                    for combo_of_remaining_card_ids in itertools.product(*lists_of_remaining_card_ids):
                        partial_deck_card_ids_for_composition_check = current_permutation_card_ids + \
                            list(combo_of_remaining_card_ids)
                        current_composition_card_ids_set = set(partial_deck_card_ids_for_composition_check)

                        if not has_card_conflict(current_composition_card_ids_set):
                            for final_segment_permutation_card_ids in itertools.permutations(list(combo_of_remaining_card_ids)):
                                final_permutation_card_ids = current_permutation_card_ids + list(final_segment_permutation_card_ids)
                                yield tuple(final_permutation_card_ids)  # <--- 只 yield CardSeriesId 列表

            yield from _generate_recursive([], set(), 0)

    @property
    def total_decks(self):
        return self._total_count

# 对外暴露的函数，返回一个 DeckGeneratorWithCount 实例


def generate_decks_with_sequential_priority_pruning(card_ids_to_consider: list[int], center_char: int = None):  # <--- 不再接收 card_data_full
    return DeckGeneratorWithCount(card_ids_to_consider, center_char)


if __name__ == "__main__":

    # 示例用法 (与之前相同，但为了测试方便，我增加了更多符合条件的卡牌)
    card_data = db_load("Data\\CardDatas.json")
    card_data.pop("0")

    card_ids = [
        1011501,
        1021523, 1021701,
        1022521, 1022701,
        1023520, 1023701,
        1031519, 1031901,
        1032518, 1032901,
        1033514, 1033901,
        1041513,
        1042512,
        1043512,
        1051501, 1051502,
        1052501, 1052502,
    ]
    # all_valid_decks = generate_card_decks_grouped_by_character(card_data, card_ids)

    final_ranked_permutations_pruned = generate_decks_with_sequential_priority_pruning(card_data, card_ids)

    print(f"Total number of valid permutations found after sequential priority pruning (with itertools optimization): {len(final_ranked_permutations_pruned)}")

    # 打印前几个结果作为示例
    for i, perm in enumerate(final_ranked_permutations_pruned[:10]):  # 只打印前10个排列
        card_series_ids = [c["CardSeriesId"] for c in perm]
        names = [c["Name"] for c in perm]
        chars = [c["CharactersId"] for c in perm]
        print(f"\n--- Permutation {i+1} ---")
        print(f"  CardSeriesIds: {card_series_ids}")
        print(f"  Names: {names}")
        print(f"  CharactersIds: {chars}")
        print(f"  First Card CharactersId: {chars[0]}, Priority Rank: {get_char_priority_rank(chars[0])}")
    print(len(final_ranked_permutations_pruned))
