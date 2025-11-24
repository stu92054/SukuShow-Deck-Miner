import json
import logging
import os
import time
import sys
import argparse
from tqdm import tqdm


from src.config.CardLevelConfig import fix_windows_console_encoding
from src.core.Simulator_core import DB_CARDDATA


# Set up logging for this script
logger = logging.getLogger(__name__)


# 角色名称映射
CHARACTER_NAMES = {
    1011: "大賀美沙知",
    1021: "乙宗梢",
    1022: "夕霧綴理",
    1023: "藤島慈",
    1031: "日野下花帆",
    1032: "村野さやか",
    1033: "大沢瑠璃乃",
    1041: "百生吟子",
    1042: "徒町小鈴",
    1043: "安養寺姫芽",
    1051: "桂城泉",
    1052: "セラス 柳田 リリエンフェルト",
}


def get_character_name(character_id: int) -> str:
    """
    根据角色ID获取角色名称

    Args:
        character_id: 角色ID (例如 1031)

    Returns:
        角色名称，如果找不到则返回角色ID字符串
    """
    return CHARACTER_NAMES.get(character_id, f'Unknown({character_id})')


def get_card_name(card_id: int) -> str:
    """
    根据卡面ID获取卡面名称

    Args:
        card_id: 卡面ID (例如 1031519)

    Returns:
        卡面名称，如果找不到则返回卡面ID字符串
    """
    card_key = str(card_id)
    if card_key in DB_CARDDATA:
        return DB_CARDDATA[card_key].get('Name', f'Unknown({card_id})')
    return f'Unknown({card_id})'


def get_card_full_info(card_id: int) -> tuple[str, str]:
    """
    根据卡面ID获取角色名和卡面名

    Args:
        card_id: 卡面ID (例如 1031519)

    Returns:
        (角色名, 卡面名) 元组
    """
    card_key = str(card_id)
    if card_key in DB_CARDDATA:
        card_data = DB_CARDDATA[card_key]
        character_id = card_data.get('CharactersId')
        character_name = get_character_name(character_id) if character_id else 'Unknown'
        card_name = card_data.get('Name', f'Unknown({card_id})')
        return character_name, card_name
    return 'Unknown', f'Unknown({card_id})'


def format_deck_with_names(deck_card_ids: list) -> str:
    """
    格式化卡组，显示ID和名称

    Args:
        deck_card_ids: 卡面ID列表

    Returns:
        格式化的字符串
    """
    lines = []
    for card_id in deck_card_ids:
        card_name = get_card_name(card_id)
        lines.append(f"      {card_id}: {card_name}")
    return '\n'.join(lines)


def get_song_title(music_id: str) -> str:
    """根据歌曲ID获取歌名"""
    try:
        from RChart import MusicDB
        music_db = MusicDB()
        music = music_db.get_music_by_id(music_id)
        if music:
            return music.Title
    except Exception:
        pass
    return f'Unknown({music_id})'


logging.basicConfig(
    level=logging.INFO,  # Adjust logging level as needed (e.g., INFO, DEBUG)
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Configuration ---
# 配置求解歌曲，格式: ("歌曲ID", "难度"),
# 求解前需运行 MainBatch.py 生成对应的卡组得分记录
CHALLENGE_SONGS = [
    # 若只输入两首歌则会寻找仅针对两面的最优解，不考虑第三面
    # ("405119", "02"),  # 一生に夢が咲くように
    ("405121", "02"),  # ハートにQ
    ("405107", "02"),  # Shocking Party
]

# 每首歌只保留得分排名前 N 名的卡组用于求解
TOP_N_CANDIDATES = 5000

# 仅根据每面最高分剪枝，不考虑重复卡
# 三面分差较大时适用，小分差时很慢
simple_pruning_mode = False


def load_song_simulation_results_from_file(filename: str, music_id: str, difficulty: str) -> list[dict]:
    """
    Loads simulation results for a specific song and difficulty from a JSON file.
    Deduplicates decks based on card composition (ignoring order) and keeps the highest score
    for each unique composition. Then filters and returns the top N candidates.

    Args:
        filename (str): The path to the JSON file.
        music_id (str): The ID of the music track.
        difficulty (str): The difficulty level of the chart.

    Returns:
        list[dict]: A sorted list of dictionaries, each representing a candidate deck
                    with its 'deck_card_ids', 'pt' and 'score'.
                    Returns an empty list if the file is not found or an error occurs.
    """
    if not os.path.exists(filename):
        logger.error(f"Error: Simulation results file not found for {music_id}-{difficulty}: {filename}")
        return []

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            raw_results = json.load(f)

        # --- New Logic: Deduplicate and keep highest score for each unique card combination ---
        unique_decks_best_pts = {}  # Key: tuple of sorted card IDs, Value: {'deck_card_ids': original_list, 'score': best_score}

        for result in raw_results:
            current_deck_card_ids = result['deck_card_ids']
            current_score = result['score']
            current_pt = result['pt']

            # Create a standardized key for comparison (sorted tuple of card IDs)
            # Ensure card IDs are integers for consistent sorting if they are not already
            sorted_card_ids_tuple = tuple(sorted(map(int, current_deck_card_ids)))

            if sorted_card_ids_tuple not in unique_decks_best_pts or \
               current_pt > unique_decks_best_pts[sorted_card_ids_tuple]['pt']:
                # If this is a new unique combination or we found a higher score for it
                unique_decks_best_pts[sorted_card_ids_tuple] = {
                    'deck_card_ids': current_deck_card_ids,
                    'score': current_score,
                    'pt': current_pt
                }

        # Convert the unique decks dictionary back to a list of results
        processed_results = list(unique_decks_best_pts.values())
        logger.info(f"Loaded {len(raw_results)} raw results for {music_id}-{difficulty}.")
        logger.info(f"After deduplication, {len(processed_results)} unique deck compositions remain.")

        # Sort results by score in descending order
        processed_results.sort(key=lambda x: x['pt'], reverse=True)

        # Return only the top N candidates
        logger.info(f"Returning top {TOP_N_CANDIDATES} candidates for {music_id}-{difficulty}.")
        return processed_results[:TOP_N_CANDIDATES]

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {filename}: {e}")
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading {filename}: {e}")
        return []


# --- Core Optimization Logic (Backtracking) ---
# Global variables to store the best result found during backtracking
best_global_pt = -1
best_global_decks = []  # Stores a list of {"song_id": ..., "deck_card_ids": [...], "score": ...} for the best combination


def find_best_three_decks(
    song_idx: int,
    all_song_candidates: dict[str, list[dict]],
    challenge_song_ids: list[str],
    current_selected_decks_info: list[dict],
    used_card_ids_set: set[int],
    current_total_pt: int,
):
    """
    Recursively searches for the best combination of three decks (one for each song)
    such that no card ID is repeated across the three decks.

    Args:
        song_idx (int): The current song index being processed (0, 1, or 2).
        all_song_candidates (dict): Dictionary mapping song_id to its list of candidate decks.
        challenge_song_ids (list): An ordered list of the song IDs for the challenge.
        current_selected_decks_info (list): List of dictionaries, each describing a deck
                                            selected for previous songs in the current path.
                                            Format: [{"song_id": ..., "deck_card_ids": [...], "score": ...}]
        used_card_ids_set (set): A set of card IDs already used in current_selected_decks_info.
        current_total_pt (float): The accumulated pt from decks in current_selected_decks_info.
    """
    global best_global_pt
    global best_global_decks

    # Base Case: All three songs have been assigned a deck
    if song_idx == len(challenge_song_ids):  # Check if we've processed all songs
        if current_total_pt > best_global_pt:
            best_global_pt = current_total_pt
            # Deep copy to store the current best combination
            best_global_decks = list(current_selected_decks_info)
            logger.info(f"New best total pt found: {best_global_pt}")
            for i, deck_info in enumerate(best_global_decks):
                logger.info(f"  Song {i+1} ({deck_info['music_id']}): ")
                logger.info(f"    Pt: {deck_info['pt']:,}\tScore: {deck_info['score']:,}\tRank: {deck_info['rank']}")
                logger.info(f"    Deck (ID): {deck_info['deck_card_ids']}")
            # Optionally print the decks for the new best score
            # for deck_info in best_global_decks:
            #     logger.info(f"  Song {deck_info['music_id']}: Score {deck_info['score']:.2f}, Cards {deck_info['deck_card_ids']}")
        return

    current_song_id = challenge_song_ids[song_idx]
    candidates_for_current_song = all_song_candidates.get(current_song_id, [])

    if simple_pruning_mode:
        # 切换到更简单的剪枝策略：
        # 1. 只考虑剩余最高分，不排除卡牌冲突
        # 2. 如果当前total_pt加上剩余最高分小于等于best_global_pt，立即剪枝
        # 在三面分数相差较大时很快，分数接近时基本无效
        remaining_max_pt_estimate = 0
        for i in range(song_idx, len(challenge_song_ids)):
            next_song_id = challenge_song_ids[i]
            remaining_max_pt_estimate += all_song_candidates[next_song_id][0]['pt']

        if current_total_pt + remaining_max_pt_estimate <= best_global_pt and best_global_pt != -1:
            return

    else:
        # Pruning: 基于可用卡牌池的动态剪枝
        remaining_max_pt_estimate = 0
        # 模拟剩下的歌曲
        for i in range(song_idx, len(challenge_song_ids)):
            next_song_id = challenge_song_ids[i]

            # 在all_song_candidates中寻找与当前used_card_ids_set无冲突的最高分卡组
            # 这是一个关键的内层循环，可能会带来一些开销，但比无意义的递归要少
            found_candidate_pt = 0
            for candidate in all_song_candidates.get(next_song_id, []):
                deck_card_ids = candidate['deck_card_ids']
                has_conflict = False
                for card_id in deck_card_ids:
                    if card_id in used_card_ids_set:
                        has_conflict = True
                        break

                if not has_conflict:
                    # 找到第一个无冲突的最高分卡组
                    found_candidate_pt = candidate['pt']
                    break

            remaining_max_pt_estimate += found_candidate_pt

        # 如果当前路径即使加上所有无冲突的最高分也无法超越全局最佳，则剪枝
        if best_global_pt != -1 and current_total_pt + remaining_max_pt_estimate <= best_global_pt:
            return

    iterable = candidates_for_current_song
    if song_idx == 0:
        iterable = tqdm(candidates_for_current_song, desc=f"Searching decks for {current_song_id}", unit="deck")

    for index, candidate_deck_info in enumerate(iterable):
        deck_card_ids = candidate_deck_info['deck_card_ids']
        deck_score = candidate_deck_info['score']
        deck_pt = candidate_deck_info['pt']

        # Check for card conflicts
        has_conflict = False
        for card_id in deck_card_ids:
            if card_id in used_card_ids_set:
                has_conflict = True
                break

        if not has_conflict:
            # If no conflict, make the choice
            new_used_card_ids_set = used_card_ids_set.union(set(deck_card_ids))
            new_selected_decks_info = current_selected_decks_info + [{
                "music_id": current_song_id,
                "difficulty": CHALLENGE_SONGS[song_idx][1],  # Get difficulty from CHALLENGE_SONGS
                "deck_card_ids": deck_card_ids,
                "score": deck_score,
                "pt": deck_pt,
                "rank": index + 1
            }]
            new_total_pt = current_total_pt + deck_pt

            # Recurse
            find_best_three_decks(
                song_idx + 1,
                all_song_candidates,
                challenge_song_ids,
                new_selected_decks_info,
                new_used_card_ids_set,
                new_total_pt
            )
            # No explicit 'backtrack' needed here for the list and set as we create new ones
            # for each recursive call. This simplifies the code but might use more memory
            # for very deep recursion with many branches. For 3 songs, it's fine.


# --- Main Execution Block ---
if __name__ == "__main__":
    fix_windows_console_encoding()

    # 解析命令列參數
    parser = argparse.ArgumentParser(description='多歌曲卡組最佳化求解器（回溯算法版本）')
    parser.add_argument('--config', type=str, metavar='CONFIG_FILE',
                       help='YAML配置檔案路徑（例如：config/member-alice.yaml）')
    args = parser.parse_args()

    logger.info("Starting multi-song deck optimization...")
    start_time = time.time()

    # 嘗試讀取配置管理器以獲取正確的 log 目錄
    try:
        from src.config.config_manager import get_config
        if args.config:
            # 使用命令列指定的配置檔
            config = get_config(args.config)
            logger.info(f"使用命令列指定的配置檔: {args.config}")
        else:
            # 使用預設配置檔（從環境變量或預設路徑）
            config = get_config()
            logger.info(f"使用預設配置檔: {config.config_file}")

        LOG_DIR = config.get_log_dir()
        logger.info(f"log 目錄: {LOG_DIR}")
    except (ImportError, ValueError, FileNotFoundError) as e:
        # 如果沒有配置管理器或找不到配置，使用默認的 log 目錄
        LOG_DIR = "log"
        logger.info(f"配置管理器不可用或找不到配置檔 ({e})，使用默認 log 目錄: {LOG_DIR}")

    all_song_candidates_data = {}
    challenge_song_ids_ordered = []  # Keep track of the order of songs

    # Step 1: Load candidate decks for each challenge song
    for music_id, difficulty in CHALLENGE_SONGS:
        song_key = f"{music_id}_{difficulty}"  # Use a combined key for the dictionary
        challenge_song_ids_ordered.append(song_key)  # Add to ordered list

        # 從正確的 log 目錄讀取
        filename = os.path.join(LOG_DIR, f"simulation_results_{music_id}_{difficulty}.json")
        candidates = load_song_simulation_results_from_file(filename, music_id, difficulty)
        if not candidates:
            logger.error(f"No candidates found for {music_id}-{difficulty}. Cannot proceed with optimization.")
            sys.exit(1)
        all_song_candidates_data[song_key] = candidates

    logger.info(f"Loaded candidates for {len(all_song_candidates_data)} songs.")

    # Step 2: Initiate the backtracking search
    logger.info("Starting backtracking search for best 3-deck combination...")
    challenge_song_ids_ordered.sort(key=lambda song_key: all_song_candidates_data[song_key][0]['pt'], reverse=True)
    logger.info(f"Challenge songs reordered for optimization: {challenge_song_ids_ordered}")

    # Initialize global bests
    best_global_pt = -1
    best_global_decks = []

    find_best_three_decks(
        song_idx=0,
        all_song_candidates=all_song_candidates_data,
        challenge_song_ids=challenge_song_ids_ordered,
        current_selected_decks_info=[],
        used_card_ids_set=set(),
        current_total_pt=0
    )

    end_time = time.time()
    logger.info("--- Multi-song optimization completed! ---")
    logger.info(f"Total optimization time: {end_time - start_time:.2f} seconds")

    # Step 3: Output the best combination
    logger.info("\n--- Overall Best 3-Deck Combination ---")
    if best_global_pt != -1:
        logger.info(f"Total Combined Pt: {best_global_pt:,}")
        for i, deck_info in enumerate(best_global_decks):
            # 從 music_id 中解析出實際的歌曲ID和難度
            music_id_parts = deck_info['music_id'].split('_')
            music_id = music_id_parts[0]
            difficulty = music_id_parts[1] if len(music_id_parts) > 1 else '??'
            song_title = get_song_title(music_id)

            logger.info(f"  Song {i+1}: {music_id} (Difficulty: {difficulty}) - {song_title}")
            logger.info(f"    Score: {deck_info['score']:,}")
            logger.info(f"    Pt: {deck_info['pt']:,}  (Rank: #{deck_info['rank']})")
            logger.info(f"    Deck:")
            for card_id in deck_info['deck_card_ids']:
                character_name, card_name = get_card_full_info(card_id)
                logger.info(f"      {card_id}: {character_name} - {card_name}")

        # Optional: Save the best combination to a separate JSON file
        output_filename = "best_3_song_combo.json"
        try:
            # 为每个卡组添加卡面名称和角色名信息
            decks_with_names = []
            for deck_info in best_global_decks:
                deck_with_names = deck_info.copy()
                # 添加卡面详细信息列表（包含角色名和卡面名）
                deck_with_names['deck_card_names'] = [
                    {
                        'id': card_id,
                        'character': get_card_full_info(card_id)[0],
                        'name': get_card_full_info(card_id)[1]
                    }
                    for card_id in deck_info['deck_card_ids']
                ]
                decks_with_names.append(deck_with_names)

            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump({
                    "total_pt": best_global_pt,
                    "decks": decks_with_names
                }, f, ensure_ascii=False, indent=4)
            logger.info(f"Best 3-song combination saved to {output_filename}")
        except Exception as e:
            logger.error(f"Error saving best combination to JSON: {e}")

    else:
        logger.info("No valid 3-deck combination found that meets the criteria.")
