import logging
import time
import os
import multiprocessing
import json

from tqdm import tqdm
from RChart import Chart
from DeckGen import generate_decks_with_sequential_priority_pruning
from DeckGen2 import generate_decks_with_double_cards
from CardLevelConfig import convert_deck_to_simulator_format
from Simulator_core import run_game_simulation, MUSIC_DB

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

BONUS_SFL = 1
CENTERCHAR = None


def score2pt(results):
    for deck in results:
        card_chars = {str(card_id)[:4] for card_id in deck['deck_card_ids']}
        bonus = BONUS_SFL

        if CENTERCHAR in card_chars:
            bonus *= 1.4
        deck['pt'] = int(deck['score'] * bonus)  # 实际为向上取整而非截断
    return results


def save_simulation_results(results_data: list, filename: str = os.path.join("log", "simulation_results.json"), calc_pt=False):
    """
    将模拟结果数据保存到 JSON 文件，只保留最高分的顺序。
    results_data: 包含每个卡组及其得分的字典列表。
                  例如: [{"deck_cards": [id1, id2, ...], "score": 123456}, ...]
    filename: 保存 JSON 文件的名称。
    """

    unique_decks_best_scores = {}  # Key: tuple of sorted card IDs, Value: {'deck_card_ids': original_list, 'score': best_score}

    for result in results_data:
        current_deck_card_ids = result['deck_card_ids']
        current_score = result['score']

        # Create a standardized key for comparison (sorted tuple of card IDs)
        # Ensure card IDs are integers for consistent sorting if they are not already
        sorted_card_ids_tuple = tuple(sorted(map(int, current_deck_card_ids)))

        if sorted_card_ids_tuple not in unique_decks_best_scores or \
                current_score > unique_decks_best_scores[sorted_card_ids_tuple]['score']:
            # If this is a new unique combination or we found a higher score for it
            unique_decks_best_scores[sorted_card_ids_tuple] = {
                'deck_card_ids': current_deck_card_ids,  # Keep the original list for clarity/consistency
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


def task_generator_func(decks_generator, chart, player_level):
    """
    一个生成器函数，从 decks_generator 获取每个卡组，
    并将其转换为 run_game_simulation 所需的任务格式。
    """
    for i, deck_card_ids_list in enumerate(decks_generator):  # Simulate all decks as example
        sim_deck_format = convert_deck_to_simulator_format(deck_card_ids_list)
        yield (sim_deck_format, chart, player_level, i, deck_card_ids_list)


#  --- Main Execution Block for Parallel Simulation ---
if __name__ == "__main__":
    start_time = time.time()

    # --- Step 1: Define all valid cards ---

    # 模拟时实际使用的卡牌范围
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

    # 塔桑精选池，实际未使用
    # 如有需要可以从里面拿一些卡到上面跑
    card_ids_B = [
        1011501,  # 沙知
        1021523, 1021901, 1021512, 1021701,  # 梢: 银河 BR 舞会 LR
        1022701, 1022504, 1022521, 1022901, 1022512,  # 缀: LR 明月 银河 BR 舞会
        1023520, 1023701, 1023901, 1023505, 1023513,  # 1023504, # 慈: 银河 LR BR 湖边 教师 舞会
        1031519, 1031530, 1031901, 1031516, 1031504,  # 帆: 舞会 IDOME BR(2024) ST RG
        1032518, 1032528, 1032901, 1032505, 1032509,  # 沙: 舞会 IDOME BR 明月 海豚
        1033514, 1033524, 1033901, 1033520, 1033504,  # 乃: 舞会 IDOME BR JK ID
        1041513, 1041515, 1041503, 1041901,  # 吟: 舞会 37.5 青岚 br
        1042515, 1042503, 1042901, 1042512,  # 铃: 暧昧mayday 瓢虫 BR 舞会
        1043515, 1043512, 1043504,  # 1043901, # 芽: BLAST 舞会 mrc BR
        1044401,  # 泉塞
        1051501, 1051502,  # 泉: DB RF
        1052901, 1052503  # 塞: BR 十六夜
    ]

    # --- Step 2: Prepare simulation tasks ---
    fixed_music_id = "305107"  # IDOME
    fixed_difficulty = "02"
    fixed_player_master_level = 50

    # 强制指定歌曲C位和颜色
    center_override = None  # 1032
    color_override = None  # 1 # 1=Smile 2=Pure 3=Cool

    # 新增：批次大小和临时文件目录
    BATCH_SIZE = 1_000_000  # 每100万条结果保存一个文件
    TEMP_OUTPUT_DIR = "temp"
    FINAL_OUTPUT_DIR = "log"

    try:
        pre_initialized_chart = Chart(MUSIC_DB, fixed_music_id, fixed_difficulty)
        if center_override:
            pre_initialized_chart.music.CenterCharacterId = center_override
        if color_override:
            pre_initialized_chart.music.MusicType = color_override
        logger.info(f"Chart object for Music ID {fixed_music_id} and Difficulty {fixed_difficulty} pre-initialized.")
    except Exception as e:
        logger.error(f"Failed to pre-initialize Chart object: {e}")
        exit()

    BONUS_SFL = (len(pre_initialized_chart.music.SingerCharacterId) + 1) * 0.7 + 1
    CENTERCHAR = str(pre_initialized_chart.music.CenterCharacterId)

    logger.info("开始生成卡组并提交到模拟池...")

    # 3. 获取卡组生成器
    decks_generator = generate_decks_with_double_cards(
        card_ids, pre_initialized_chart.music.CenterCharacterId
    )
    total_decks_to_simulate = decks_generator.total_decks
    logger.info(f"预计算总共将模拟 {total_decks_to_simulate} 个卡组。")

    # 4. 创建模拟任务生成器
    # task_generator_func 会按需从 generated_decks_generator 中拉取卡组
    simulation_tasks_generator = task_generator_func(
        decks_generator, pre_initialized_chart, fixed_player_master_level
    )

    os.makedirs(TEMP_OUTPUT_DIR, exist_ok=True)
    os.makedirs(FINAL_OUTPUT_DIR, exist_ok=True)

    # Use multiprocessing.Pool with imap_unordered
    num_processes = os.cpu_count() or 1
    logger.info(f"Starting parallel simulations using {num_processes} processes...")
    highest_score_overall = -1
    highest_score_deck_info = None  # 存储最佳卡组的完整信息
    best_log = []

    current_batch_results = []  # 存储当前批次的结果
    temp_files = []            # 存储所有临时文件的路径
    batch_counter = 0          # 批次计数器
    results_processed_count = 0  # 已处理结果的总数

    with multiprocessing.Pool(processes=num_processes) as pool:
        # imap_unordered returns results as they are completed, in no particular order.
        # This is perfect for checking high scores on the fly.
        results_iterator = pool.imap_unordered(run_game_simulation, simulation_tasks_generator, chunksize=500)

        for result in tqdm(results_iterator, total=total_decks_to_simulate):
            current_score = result['final_score']
            original_index = result['original_deck_index']
            current_log = result["cards_played_log"]
            deck_card_ids = result['deck_card_ids']

            # 记录当前卡组的得分和卡牌ID，添加到结果列表中
            current_batch_results.append({
                "deck_card_ids": deck_card_ids,  # 使用卡牌ID列表
                "score": current_score
            })
            results_processed_count += 1

            if current_score > highest_score_overall:
                highest_score_overall = current_score
                highest_score_deck_info = {
                    "original_index": original_index,
                    "deck_card_ids": deck_card_ids,
                    "score": current_score
                }
                best_log = current_log
                logger.info(f"\nNEW HI-SCORE! Deck: {original_index}, Score: {current_score}")
                logger.info(f"  Deck: {deck_card_ids}")

            if len(current_batch_results) >= BATCH_SIZE:
                batch_counter += 1
                temp_filename = os.path.join(TEMP_OUTPUT_DIR, f"temp_batch_{batch_counter:0>3}.json")
                save_simulation_results(current_batch_results, temp_filename)
                temp_files.append(temp_filename)
                current_batch_results = []  # 清空当前批次列表

        # --- 处理最后一批可能不满BATCH_SIZE的结果 ---
        if current_batch_results:
            batch_counter += 1
            temp_filename = os.path.join(TEMP_OUTPUT_DIR, f"temp_batch_{batch_counter:0>3}.json")
            save_simulation_results(current_batch_results, temp_filename)
            temp_files.append(temp_filename)
            current_batch_results = []  # 清空

    end_time = time.time()
    logger.info("--- All simulations completed! ---")
    logger.info(f"Total simulation time: {end_time - start_time:.2f} seconds")

    # --- Step 4: Save all results to JSON ---
    all_simulation_results = []
    for temp_file in tqdm(temp_files, desc="Merging Files"):
        with open(temp_file, 'r') as f:
            all_simulation_results.extend(json.load(f))
        os.remove(temp_file)
    json_output_filename = os.path.join("log", f"simulation_results_{fixed_music_id}_{fixed_difficulty}.json")
    save_simulation_results(all_simulation_results, json_output_filename, calc_pt=True)

    # --- Step 5: Final Summary ---
    logger.info(f"\n--- Final Simulation Summary ---")
    logger.info(f"Map: {MUSIC_DB.get_music_by_id(fixed_music_id).Title} ({fixed_difficulty})")
    logger.info(f"Total simulations run: {total_decks_to_simulate}")
    if highest_score_overall != -1:
        logger.info(f"Overall Highest Score: {highest_score_overall}")
        logger.info(f"Highest Score Deck: {highest_score_deck_info['original_index']}")
        logger.info(f"Cards: {highest_score_deck_info['deck_card_ids']}")
        logger.info(f"Log: {best_log}")
    else:
        logger.info("No simulations yielded a score.")
