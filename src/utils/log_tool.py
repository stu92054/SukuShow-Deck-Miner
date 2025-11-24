import json
import logging
import os
from tqdm import tqdm

from ..config.CardLevelConfig import CARD_CACHE

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

# 填写需要重算 pt 的 log 的歌曲 ID 和难度
MUSIC_ID = "204108"
DIFFICULTY = "02"

# 填写季度倍率与人数补正，正常情况下参演成员季度全10级时为 6.6
BONUS_SFL = 5.2 * 0.9
# 解放倍率会根据 C 位卡牌在 CardLevelConfig.py 中的练度自动计算
LIMITBREAK_BONUS = {
    1: 1, 2: 1, 3: 1, 4: 1, 5: 1,
    6: 1, 7: 1, 8: 1, 9: 1, 10: 1,
    11: 1.2,
    12: 1.3,
    13: 1.35,
    14: 1.4
}


def score2pt(results):
    card_limitbreak = dict()
    for deck in results:
        bonus = BONUS_SFL
        centercard = deck["center_card"]
        if centercard:
            limitbreak = card_limitbreak.get(centercard, None)
            if limitbreak == None:
                levels = CARD_CACHE.get(centercard, [140, 14, 14])
                card_limitbreak[centercard] = limitbreak = max(levels[1:])
            bonus *= LIMITBREAK_BONUS[limitbreak]
        deck['pt'] = int(deck['score'] * bonus)  # 实际为向上取整而非截断
    return results


def save_simulation_results(results_data: list, filename: str = os.path.join("log", "simulation_results.json"), calc_pt=False):
    """
    将模拟结果数据保存到 JSON 文件，只保留最高分的顺序。
    results_data: 包含每个卡组及其得分的字典列表。
                  例如: [{"deck_cards": [id1, id2, ...], "center_card": id1, "score": 123456}, ...]
    filename: 保存 JSON 文件的名称。
    """

    unique_decks_best_scores = {}  # Key: tuple of sorted card IDs, Value: {'deck_card_ids': original_list, 'score': best_score}

    for result in results_data:
        current_deck_card_ids = result['deck_card_ids']
        current_score = result['score']
        center_card = result['center_card']

        sorted_card_ids_tuple = tuple(sorted(map(int, current_deck_card_ids)))

        if sorted_card_ids_tuple not in unique_decks_best_scores or \
                current_score > unique_decks_best_scores[sorted_card_ids_tuple]['score']:
            # If this is a new unique combination or we found a higher score for it
            unique_decks_best_scores[sorted_card_ids_tuple] = {
                'deck_card_ids': current_deck_card_ids,  # Keep the original list for clarity/consistency
                'center_card': center_card,
                'score': current_score
            }

    # Convert the unique decks dictionary back to a list of results
    processed_results = list(unique_decks_best_scores.values())
    if calc_pt:
        processed_results = score2pt(processed_results)
        processed_results.sort(key=lambda i: i["pt"], reverse=True)
    else:
        processed_results.sort(key=lambda i: i["score"], reverse=True)
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(processed_results, f, ensure_ascii=False, indent=0)
        logger.info(f"Simulation results saved to {filename}")
    except Exception as e:
        logger.error(f"Error saving simulation results to JSON: {e}")


if __name__ == "__main__":
    # 在列表中填写需要重新计算 pt 的 log 文件路径
    # 也可以用于合并未完成所有模拟就被中断时遗留的 log 缓存
    temp_files = [os.path.join("log", f"simulation_results_{MUSIC_ID}_{DIFFICULTY}.json")]

    all_simulation_results = []
    for temp_file in tqdm(temp_files, desc="Merging Files", ascii=True):
        with open(temp_file, 'r') as f:
            all_simulation_results.extend(json.load(f))

    # 重新计算 pt 的 log 会有 "_re" 后缀
    json_output_filename = os.path.join("log", f"simulation_results_{MUSIC_ID}_{DIFFICULTY}_re.json")
    save_simulation_results(all_simulation_results, json_output_filename, calc_pt=True)
