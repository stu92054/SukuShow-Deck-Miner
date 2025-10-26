import logging
import time
import os
import multiprocessing
import json
import sys

from platform import python_implementation
from tqdm import tqdm
from RChart import Chart
from DeckGen import generate_decks_with_sequential_priority_pruning
from DeckGen2 import generate_decks_with_double_cards
from CardLevelConfig import convert_deck_to_simulator_format, fix_windows_console_encoding, CARD_CACHE
from SkillResolver import SkillEffectType
from Simulator_core import run_game_simulation, MUSIC_DB

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

# NOTE: BONUS_SFL will be computed dynamically later based on Season Fan Lv settings
# Default placeholder; actual value will be set after chart is loaded
BONUS_SFL = None
CENTERCHAR = None
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
                levels = CARD_CACHE[centercard]
                card_limitbreak[centercard] = limitbreak = max(levels[1:])
            bonus *= LIMITBREAK_BONUS[limitbreak]
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
        center_card = result['center_card']

        # Create a standardized key for comparison (sorted tuple of card IDs)
        # Ensure card IDs are integers for consistent sorting if they are not already
        sorted_card_ids_tuple = tuple(sorted(map(int, current_deck_card_ids)))

        if sorted_card_ids_tuple not in unique_decks_best_scores or \
                current_score > unique_decks_best_scores[sorted_card_ids_tuple]['score']:
            # If this is a new unique combination or we found a higher score for it
            unique_decks_best_scores[sorted_card_ids_tuple] = {
                'deck_card_ids': current_deck_card_ids,
                'center_card': center_card,
                'score': current_score,
            }

    # Convert the unique decks dictionary back to a list of results
    processed_results = list(unique_decks_best_scores.values())
    if calc_pt:
        processed_results = score2pt(processed_results)
        # 合并既有log
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                processed_results.extend(json.load(f))
        processed_results.sort(key=lambda i: i["pt"], reverse=True)
    else:
        processed_results.sort(key=lambda i: i["score"], reverse=True)
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(processed_results, f, ensure_ascii=False, indent=0)
        logger.info(f"Simulation results saved to {filename}")
    except Exception as e:
        logger.error(f"Error saving simulation results to JSON: {e}")


def task_generator_func(decks_generator, chart, player_level,leader_designation):
    """
    一个生成器函数，从 decks_generator 获取每个卡组，
    并将其转换为 run_game_simulation 所需的任务格式。

    对于有多张C位角色卡的卡组，生成所有可能的C位选择。
    """
    task_index = 0
    center_char_id = chart.music.CenterCharacterId

    for deck_card_ids_list in decks_generator:
        # 找出所有C位角色的卡片索引
        center_card_indices = []
        # New solution: if a vaild leader is entered via the command line, the decks would already have the leader.
        # We only need to find the index of the leader card now.
        if leader_designation != 0 :
            for idx, card_id in enumerate(deck_card_ids_list):
                if int(leader_designation) == card_id: center_card_indices.append(idx)
        # Old solution OR if no leader is supplied
        else:
            for idx, card_id in enumerate(deck_card_ids_list):
                char_id = card_id // 1000
                if char_id == center_char_id:
                    center_card_indices.append(idx)

        # 如果有多张C位角色的卡，为每张生成一个任务
        # 如果只有一张或没有，生成一个任务（索引为-1表示自动选择）
        if not center_card_indices:
            # 没有C位角色卡（理论上不应该发生）
            center_indices_to_test = [-1]
        else:
            # 测试每张C位角色卡作为C位
            center_indices_to_test = center_card_indices

        for center_index in center_indices_to_test:
            sim_deck_format = convert_deck_to_simulator_format(deck_card_ids_list)
            # 传递C位卡索引给模拟器
            yield (sim_deck_format, chart, player_level, task_index, deck_card_ids_list, center_index)
            task_index += 1


#  --- Main Execution Block for Parallel Simulation ---
if __name__ == "__main__":
    pypy_impl = python_implementation() == "PyPy"
    if pypy_impl:
        fix_windows_console_encoding()
    start_time = time.time()

    # --- Step 1: Define all valid cards ---

    # 模拟时实际使用的卡牌范围
    # card_ids = [
    #     1011501,  # 沙知
    #     1021523, 1021901, 1021512, 1021701, 1021801, 1021802,  # 梢: 银河 BR 舞会 LR PE EA
    #     1022701, 1022901,  # 1022521, # 1022504,  # 缀: LR BR 银河 明月
    #     1023701, 1023901,  # 1023520,  # 慈: LR BR 银河
    #     1031530, 1031533, 1031534,  # 1031519, 1031901, 1031801, 1031802,  # 帆: IDOME 地平 乙女 舞会 BR(2024) PE EA
    #     1032518, 1032528, 1032530, 1032901, #1032801, 1032802, # 沙: 舞会 IDOME 地平 BR PE EA
    #     1033514, 1033524, 1033525, 1033526, 1033527, 
    #     1033528,  # 1033901, #1033801, 1033802, # 乃: 舞会 IDOME COCO夏 喵信号 一生梦 地平 BR PE EA
    #     1041513, 1041901, 1041801, 1041802, 1041516,  # 1041517, # 吟: 舞会 BR EA OE 水果 花火
    #     1042516, 1042801, 1042802,  # 1042515, # 1042512,  # 铃: 太阳 EA OE 暧昧mayday 舞会
    #     1043515, 1043516, 1043902, 1043801, 1043802,  # 芽: BLAST COCO夏 BR EA OE 舞会1043512
    #     1051506, 1051503,  # 1051501, 1051502,  # 泉: 片翼 天地黎明 DB RF
    #     1052506, 1052901, 1052503,  # 1052801, # 1052504  # 塞: 片翼 BR 十六夜 OE 天地黎明
    # ]
    card_ids = [
        1021701, 1021504, 1022701, 1023701, 1023520, 1031533, 1031530, 1031519, 1032530, 1032528, 1032518, 1033528, 1033902, 1033525, 1033524, 1041516, 1041503, 1042514, 1042515, 1043902, 1043516, 1052506, 1052901, 1051506, 1051503, 1033512, 1033529
    ]

    # ==================== DR剪枝配置 ====================
    # 控制是否移除非C位角色的DR卡，并强制卡组包含DR
    # True:  移除非C位DR + 强制使用C位DR（旧逻辑，可能限制搜索空间）
    # False: 保留所有DR，让算法自由决定（推荐，可能找到更高分）
    ENABLE_DR_PRUNING = False

    # --- 配置多首歌曲 ---
    # 每首歌的配置格式: {
    #     "music_id": "歌曲ID",
    #     "difficulty": "難度",
    #     "mustcards_all": [必須包含的所有卡牌],
    #     "mustcards_any": [必須包含至少一張的卡牌],
    #     "center_override": None 或 角色ID,
    #     "color_override": None 或 1/2/3
    # }


    
    # 卡组必须包含以下所有技能类型 (對所有歌曲生效)
    mustskills_all = [
        SkillEffectType.DeckReset,  # 洗牌
        SkillEffectType.ScoreGain,  # 分
        SkillEffectType.VoltagePointChange,  # 电
        SkillEffectType.NextAPGainRateChange,  # 分加成 (但是写作AP加成)
        SkillEffectType.NextVoltageGainRateChange,  # 电加成
        # SkillEffectType.APChange,  # 回复/扣除AP
        # SkillEffectType.MentalRateChange,  # 回复/扣除血量
        # SkillEffectType.CardExcept,  # 卡牌除外
    ]

    # --- Step 2: Prepare simulation tasks ---
    # fixed_player_master_level = 50

    # 將songs_config 搬到step 2底下，並加入命列參數帶入
    SONGS_CONFIG = [
        {
            "music_id": str(sys.argv[1]),  # 第一首歌 (請修改為實際歌曲ID)
            "difficulty": str(sys.argv[2]),
            "mastery_level": int(sys.argv[3]),
        #    "music_id": '405305',  
        #    "difficulty": '04',
        #    "mastery_level": 50,
            "mustcards_all": [],  # 設定第一首歌必須包含的卡牌
            "mustcards_any": [],
            "center_override": None, # 此為C位override非指定隊長
            "color_override": None, # 此為歌曲屬性override
            "leader_designation": sys.argv[4], # 指定隊長，卡片ID 若不指定請務必設為0
        },
        # {
        #     "music_id": "405117",  # 第二首歌 (請修改為實際歌曲ID)
        #     "difficulty": "02",
        #     "mustcards_all": [],  # 設定第二首歌必須包含的卡牌
        #     "mustcards_any": [],
        #     "center_override": None,
        #     "color_override": None,
        # },
        # {
        #     "music_id": "405118",  # 第三首歌 (請修改為實際歌曲ID)
        #     "difficulty": "02",
        #     "mustcards_all": [],  # 設定第三首歌必須包含的卡牌
        #     "mustcards_any": [],
        #     "center_override": None,
        #     "color_override": None,
        # },
    ]






    # 新增：批次大小和临时文件目录
    BATCH_SIZE = 1_000_000  # 每100万条结果保存一个文件
    TEMP_OUTPUT_DIR = "temp"
    FINAL_OUTPUT_DIR = "log"

    # ==================== 開始處理多首歌曲 ====================
    for song_config in SONGS_CONFIG:
        fixed_music_id = song_config["music_id"]
        fixed_difficulty = song_config["difficulty"]
        mustcards_all = song_config["mustcards_all"]
        mustcards_any = song_config["mustcards_any"]
        center_override = song_config["center_override"]
        color_override = song_config["color_override"]
        mastery_level = song_config["mastery_level"]
        leader_designation = song_config["leader_designation"]

        logger.info(f"\n{'='*60}")
        logger.info(f"開始處理歌曲: ID={fixed_music_id}, 難度={fixed_difficulty}")
        logger.info(f"{'='*60}")

        try:
            pre_initialized_chart = Chart(MUSIC_DB, fixed_music_id, fixed_difficulty)
            pre_initialized_chart.ChartEvents = [(float(t), e) for t, e in pre_initialized_chart.ChartEvents]
            # pre_initialized_chart.ChartEvents = [(int(float(t) * 1_000_000) , e) for t, e in pre_initialized_chart.ChartEvents]

            if pypy_impl:
                from sortedcontainers import SortedList
                pre_initialized_chart.ChartEvents = SortedList(pre_initialized_chart.ChartEvents)

            if center_override:
                pre_initialized_chart.music.CenterCharacterId = center_override
            if color_override:
                pre_initialized_chart.music.MusicType = color_override
            logger.info(f"Chart for {pre_initialized_chart.music.Title} (ID: {fixed_music_id}) and Difficulty {fixed_difficulty} pre-initialized.")
        except Exception as e:
            logger.error(f"Failed to pre-initialize Chart object: {e}")
            continue  # 跳過這首歌，繼續處理下一首

        # BONUS_SFL = (len(pre_initialized_chart.music.SingerCharacterId) + 1) * 0.7 + 1
        CENTERCHAR = str(pre_initialized_chart.music.CenterCharacterId)

        # Check if the leader is in cardpool. If not, exit.
        failed_designation = 0
        if int(leader_designation) == 0: 
            failed_designation = failed_designation + 1
        else:
            if (int(leader_designation) in card_ids) == False: 
                logger.fatal("The specified leader is not in the card pool. Simulation cannot continue.")
                continue
            if leader_designation[0:4] != CENTERCHAR:
                logger.fatal("The specified leader is not the center of the song. Simulation cannot continue.")
                continue
        
        
        
        
        # Add the leader to mustcards_all list.
        if failed_designation == 0:
            mustcards_all.append(int(leader_designation))
            print(mustcards_all)
            logger.info(f"{leader_designation} has been added to the must have list.")
        else:
            leader_designation = 0
        

        # ------------------ Season Fan Lv (動態計算 BONUS_SFL) ------------------
        # 使用方式：在下方的 FAN_LEVELS 填入 character_id -> fan_lv(1..10)
        # 如果對某個成員未指定，預設為 10（保留既有行為，使預設 BONUS_SFL 等於舊有 6.6）
        # mode: 'sukushow' (スクショウ) 或 'sukuste' (スクステ)
        SEASON_MODE = 'sukushow'  # 可改為 'sukuste' 以套用スクステ 行為

        # 在此填寫你要覆寫的 Fan Lv（character id -> level 1..10）
        # 例如: FAN_LEVELS = {1021: 8, 1032: 10}
        FAN_LEVELS: dict[int, int] = {
        # 填寫範例（角色編號 -> Fan Lv 1..10）:
            1011: 0,  # 沙知
            1021: 0,  # 梢
            1022: 0,  # 綴理
            1023: 0,  # 慈
            1031: 10,  # 帆
            1032: 10,  # 沙
            1033: 10,  # 乃
            1041: 8,  # 吟
            1042: 10,  # 鈴
            1043: 10,  # 芽
            1051: 10,  # 泉
            1052: 7,  # 塞
        }

        # Fan Lv -> bonus(百分比) 對照表 (轉為小數時需除以100)
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

        # 歌唱人數補正表 (只列出已知的倍數，其他人數使用 1.0)
        SINGING_COUNT_CORRECTION = {
            'sukushow': {2: 2.75, 8: 1.00, 9: 0.90},
            'sukuste': {2: 2.33, 8: 1.00},
        }

        # 取得此曲的歌唱成員（包含 C位）
        # 注意：SingerCharacterId 只包含副唱，需要加上 CenterCharacterId
        singer_ids = getattr(pre_initialized_chart.music, 'SingerCharacterId', [])
        center_id = pre_initialized_chart.music.CenterCharacterId

        # 确保 singer_ids 是列表
        if not isinstance(singer_ids, list):
            singer_ids = []

        # 将 C位加入歌唱成员（如果不在列表中）
        all_singers = set(singer_ids)
        if center_id:
            all_singers.add(center_id)

        singer_ids = sorted(list(all_singers))

        # 計算基礎 Season Fan Lv bonus (= 1 + sum(member_bonus))
        sum_bonus = 0.0
        for cid in singer_ids:
            lv = FAN_LEVELS.get(cid, 10)  # 未指定預設為 10 (原有行為)
            if lv < 1:
                lv = 1
            elif lv > 10:
                lv = 10
            sum_bonus += FAN_LV_BONUS_TABLE.get(lv, 0.0)

        base_bonus = 1.0 + sum_bonus

        # 應用歌唱人數補正
        singing_count = len(singer_ids)
        correction = SINGING_COUNT_CORRECTION.get(SEASON_MODE, {}).get(singing_count, 1.0)
        BONUS_SFL = base_bonus * correction

        logger.info(f"Computed BONUS_SFL={BONUS_SFL:.4f} (mode={SEASON_MODE}, singers={singer_ids}, fan_lv_overrides={FAN_LEVELS})")
        # -------------------------------------------------------------------------

        # DR剪枝处理（可通过 ENABLE_DR_PRUNING 配置）
        if ENABLE_DR_PRUNING:
            # 旧逻辑：移除非C位角色DR，如果有C位DR则强制使用
            temp = list()
            force_dr = False
            for card in card_ids:
                card_str = str(card)
                if card_str[4] != "8":  # 不是DR
                    temp.append(card)
                elif card_str[0:4] == CENTERCHAR:  # C位DR
                    temp.append(card)
                    force_dr = True
            if force_dr:
                current_card_ids = temp
                logger.info(f"[DR Pruning] Non-center DR removed, {len(current_card_ids)} cards remaining.")
                logger.info("[DR Pruning] Center DR detected, forcing all decks to contain 1 DR card.")
            else:
                current_card_ids = card_ids
                logger.info(f"[DR Pruning] No center DR found, using all {len(current_card_ids)} cards.")
        else:
            # 新逻辑：保留所有卡牌，让算法自由决定
            current_card_ids = card_ids
            force_dr = False
            logger.info(f"[No DR Pruning] Using all {len(current_card_ids)} cards, algorithm decides DR usage.")

        logger.info("Pre-calculating deck amount...")

        # 3. 获取卡组生成器
        decks_generator = generate_decks_with_double_cards(
            cardpool=current_card_ids,
            mustcards=[mustcards_all, mustcards_any, mustskills_all],
            center_char=pre_initialized_chart.music.CenterCharacterId,
            force_dr=force_dr,
            log_path=os.path.join("log", f"simulation_results_{fixed_music_id}_{fixed_difficulty}.json")
        )
        total_decks_to_simulate = decks_generator.total_decks
        logger.info(f"{total_decks_to_simulate} decks to be simulated.")

        # 4. 创建模拟任务生成器
        # task_generator_func 会按需从 generated_decks_generator 中拉取卡组
        # 指定C位的點在`task_generator_func`裡面。上面卡組沒有做到這點
        
        simulation_tasks_generator = task_generator_func(
            decks_generator, pre_initialized_chart, mastery_level, leader_designation
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
            # 若 CPU 占用率偏低，可以在此增加每次获取任务时给单个进程分配的卡组数量
            if pypy_impl:
                chunksize = 10000
            else:
                chunksize = 500
            results_iterator = pool.imap_unordered(run_game_simulation, simulation_tasks_generator, chunksize)

            for result in tqdm(results_iterator, total=total_decks_to_simulate):
                current_score = result['final_score']
                original_index = result['original_deck_index']
                current_log = result["cards_played_log"]
                deck_card_ids = result['deck_card_ids']
                center_card = result['center_card']

                # 记录当前卡组的得分、卡牌、C位卡牌，添加到结果列表中
                current_batch_results.append({
                    "deck_card_ids": deck_card_ids,  # 使用卡牌ID列表
                    "center_card": center_card,
                    "score": current_score,
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
                    logger.info(f"\nNEW HI-SCORE! Deck: {original_index}, Score: {current_score:,}")
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

        song_end_time = time.time()
        logger.info(f"--- Song {fixed_music_id} simulation completed! ---")
        logger.info(f"Simulation time: {song_end_time - start_time:.2f} seconds")

        # --- Step 4: Save all results to JSON ---
        all_simulation_results = []
        for temp_file in tqdm(temp_files, desc="Merging Files"):
            with open(temp_file, 'r') as f:
                all_simulation_results.extend(json.load(f))
            os.remove(temp_file)
        json_output_filename = os.path.join("log", f"simulation_results_{fixed_music_id}_{fixed_difficulty}.json")
        save_simulation_results(all_simulation_results, json_output_filename, calc_pt=True)

        # --- Step 5: Final Summary ---
        logger.info(f"\n--- Final Simulation Summary for {fixed_music_id} ---")
        logger.info(f"Map: {MUSIC_DB.get_music_by_id(fixed_music_id).Title} ({fixed_difficulty})")
        logger.info(f"Total simulations run: {total_decks_to_simulate}")
        if highest_score_overall != -1:
            logger.info(f"Overall Highest Score: {highest_score_overall:,}")
            logger.info(f"Highest Score Deck: {highest_score_deck_info['original_index']}")
            logger.info(f"Cards: {highest_score_deck_info['deck_card_ids']}")
            logger.info(f"Log: {best_log}")
        else:
            logger.info("No simulations yielded a score.")
    
    # ==================== 所有歌曲處理完畢 ====================
    end_time = time.time()
    logger.info(f"\n{'='*60}")
    logger.info(f"所有歌曲模擬完成！")
    logger.info(f"總耗時: {end_time - start_time:.2f} seconds")
    logger.info(f"{'='*60}")
