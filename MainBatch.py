import logging
import time
import os
import multiprocessing
import json
import sys
import argparse

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


def parse_arguments(unified_config):
    """
    解析命令列參數，支援單首或多首歌曲配置

    用法示例：
        python MainBatch.py 405117 02 50 0  # 不指定隊長
        python MainBatch.py 405117 02 50 1041802  # 指定隊長卡片ID
        python MainBatch.py 405117 02 50 0 405118 02 50 0  # 多首歌
        python MainBatch.py  # 使用預設配置
        python MainBatch.py --debug  # Debug模式：使用配置中的牌組
        python MainBatch.py --debug 1032528 1022701 1032530 1042802 1031530 1031533  # Debug模式：指定牌組
    """
    parser = argparse.ArgumentParser(description='批次模擬卡組得分')
    parser.add_argument('songs', nargs='*',
                       help='歌曲配置，格式：music_id difficulty mastery_level leader_id [music_id2 difficulty2 mastery_level2 leader_id2 ...]')
    parser.add_argument('--debug', nargs='*', type=int, metavar='CARD_ID',
                       help='Debug模式：可選指定6張卡牌ID（按順序），不指定則使用配置中的牌組')
    parser.add_argument('--center-index', type=int, default=-1,
                       help='Debug模式：指定C位卡在牌組中的索引（0-5），-1表示測試所有C位選擇（預設：-1）')

    args = parser.parse_args()

    # 如果是 Debug 模式，返回特殊標記
    if args.debug is not None:
        # 如果指定了卡牌，使用指定的；否則使用配置中的
        if len(args.debug) == 0:
            # 沒有指定卡牌，使用配置中的
            deck_cards = unified_config["debug_deck_cards"]
            logger.info("使用配置中的 Debug 牌組")
        elif len(args.debug) == 6:
            # 指定了6張卡牌
            deck_cards = args.debug
            logger.info("使用命令列指定的牌組")
        else:
            logger.error("Debug模式錯誤：必須指定6張卡牌ID或不指定任何卡牌")
            sys.exit(1)
        return {"debug_mode": True, "deck_cards": deck_cards, "center_index": args.center_index}

    # 如果沒有命令列參數，使用預設配置
    if not args.songs:
        logger.info("未提供命令列參數，使用預設配置")
        return None  # 返回 None 表示使用統一配置

    # 解析命令列參數（格式：music_id difficulty mastery_level leader_designation）
    if len(args.songs) % 4 != 0:
        logger.error("命令列參數格式錯誤！每首歌需要4個參數：music_id difficulty mastery_level leader_designation")
        logger.error(f"收到 {len(args.songs)} 個參數：{args.songs}")
        sys.exit(1)

    songs_config = []
    for i in range(0, len(args.songs), 4):
        try:
            config = {
                "music_id": str(args.songs[i]),
                "difficulty": str(args.songs[i + 1]),
                "mastery_level": int(args.songs[i + 2]),
                "mustcards_all": [],
                "mustcards_any": [],
                "center_override": None,
                "color_override": None,
                "leader_designation": str(args.songs[i + 3]),  # 第4個參數為隊長ID
            }
            songs_config.append(config)
            logger.info(f"添加歌曲配置：ID={config['music_id']}, 難度={config['difficulty']}, 熟練度={config['mastery_level']}")
        except ValueError as e:
            logger.error(f"解析參數失敗：{e}")
            logger.error(f"參數組 {i//3 + 1}: {args.songs[i:i+3]}")
            sys.exit(1)

    return songs_config


def run_debug_mode(deck_cards, center_index, config):
    """
    Debug模式：計算單一固定牌組的分數

    參數：
        deck_cards: 6張卡牌ID的列表（按順序）
        center_index: 指定使用第幾張C位卡（-1表示測試所有）
        config: 統一配置字典
    """
    logger.info("="*60)
    logger.info("進入 Debug 模式：計算單一牌組分數")
    logger.info("="*60)

    # 從統一配置區讀取歌曲配置（使用第一首歌的配置）
    first_song = config["songs"][0]
    fixed_music_id = first_song["music_id"]
    fixed_difficulty = first_song["difficulty"]
    fixed_player_master_level = first_song["mastery_level"]
    center_override = first_song["center_override"]
    color_override = first_song["color_override"]

    logger.info(f"\n牌組卡片ID: {deck_cards}")
    logger.info(f"\n歌曲配置:")
    logger.info(f"  歌曲ID: {fixed_music_id}")
    logger.info(f"  難度: {fixed_difficulty}")
    logger.info(f"  熟練度: {fixed_player_master_level}")

    # 初始化 Chart
    try:
        pre_initialized_chart = Chart(MUSIC_DB, fixed_music_id, fixed_difficulty)
        pre_initialized_chart.ChartEvents = [(float(t), e) for t, e in pre_initialized_chart.ChartEvents]

        if center_override:
            pre_initialized_chart.music.CenterCharacterId = center_override
        if color_override:
            pre_initialized_chart.music.MusicType = color_override
        logger.info(f"Chart for {pre_initialized_chart.music.Title} (ID: {fixed_music_id}) and Difficulty {fixed_difficulty} pre-initialized.")
    except Exception as e:
        logger.error(f"Failed to pre-initialize Chart object: {e}")
        sys.exit(1)

    # 找出所有C位角色的卡片索引
    center_char_id = pre_initialized_chart.music.CenterCharacterId
    center_card_indices = []
    for idx, card_id in enumerate(deck_cards):
        char_id = card_id // 1000
        if char_id == center_char_id:
            center_card_indices.append(idx)

    logger.info(f"\n找到 {len(center_card_indices)} 張C位角色 ({center_char_id}) 的卡片")
    for idx in center_card_indices:
        logger.info(f"  索引 {idx}: {deck_cards[idx]}")

    if not center_card_indices:
        logger.error("錯誤：牌組中沒有C位角色的卡片！")
        sys.exit(1)

    # 根據center_index決定測試哪些C位
    if center_index == -1:
        # 測試所有C位選擇
        logger.info(f"\n將測試所有 {len(center_card_indices)} 種C位選擇")
        center_indices_to_test = center_card_indices
    elif center_index in center_card_indices:
        # 使用指定的C位卡索引
        center_indices_to_test = [center_index]
        logger.info(f"\n使用指定的C位選擇（牌組索引 {center_index}）")
    else:
        logger.error(f"錯誤：center_index={center_index} 不是有效的C位角色卡索引")
        logger.error(f"有效的C位索引為: {center_card_indices}")
        sys.exit(1)

    # 對每個C位選擇進行模擬
    results = []
    for test_idx, center_idx in enumerate(center_indices_to_test):
        logger.info(f"\n{'='*60}")
        logger.info(f"測試 C位 #{test_idx+1}/{len(center_indices_to_test)}: 使用索引 {center_idx} 的卡片 ({deck_cards[center_idx]})")
        logger.info(f"{'='*60}")

        # 轉換牌組格式
        sim_deck_format = convert_deck_to_simulator_format(deck_cards)

        # 調用 run_game_simulation
        result = run_game_simulation(
            (sim_deck_format, pre_initialized_chart, fixed_player_master_level, 0, deck_cards, center_idx)
        )

        current_score = result['final_score']
        cards_played_log = result["cards_played_log"]
        center_card = result['center_card']

        logger.info(f"\n--- 模擬結束 ---")
        logger.info(f"分數: {current_score:,}")
        logger.info(f"C位卡片: {center_card}")
        logger.info(f"打出記錄: {cards_played_log}")
        logger.info(f"打出次數: {len(cards_played_log)}")

        results.append({
            "center_index": center_idx,
            "center_card": center_card,
            "score": current_score,
            "card_log": cards_played_log
        })

    # 輸出結果摘要
    logger.info(f"\n{'='*60}")
    logger.info("結果摘要")
    logger.info(f"{'='*60}")
    for result in results:
        logger.info(f"C位索引 {result['center_index']} (卡片ID: {result['center_card']}): {result['score']:,} 分")

    if len(results) > 1:
        best_result = max(results, key=lambda r: r['score'])
        logger.info(f"\n最佳C位選擇：索引 {best_result['center_index']} (卡片ID: {best_result['center_card']})")
        logger.info(f"最高分數：{best_result['score']:,}")


#  --- Main Execution Block for Parallel Simulation ---
if __name__ == "__main__":
    pypy_impl = python_implementation() == "PyPy"
    if pypy_impl:
        fix_windows_console_encoding()
    start_time = time.time()

    # ==================== 統一配置區 ====================
    # 所有模式共用的配置，包括批次模式和 Debug 模式
    #
    # 使用說明：
    # 1. Debug 模式：python MainBatch.py --debug
    # 2. 批次模式（使用下方配置）：python MainBatch.py
    #    - 如果 songs 列表有 1 首歌 → 單首模式
    #    - 如果 songs 列表有多首歌 → 自動多首模式
    # 3. 命令列指定歌曲：python MainBatch.py 405117 03 50 405118 02 50

    UNIFIED_CONFIG = {
        # --- 批次模式歌曲配置 ---
        # 可以配置一首或多首歌曲，程式會自動判斷
        "songs": [
            {
                "music_id": "405305",        # 歌曲ID
                "difficulty": "02",          # 難度 (01=Normal, 02=Hard, 03=Expert, 04=Master)
                "mastery_level": 50,         # 熟練度 (1-50)
                "mustcards_all": [1032528, 1032530, 1031530],  # 必須包含的所有卡牌
                "mustcards_any": [],                           # 必須包含至少一張的卡牌
                "center_override": None,     # 強制替換C位角色ID (None=使用歌曲預設)
                "color_override": None,      # 強制替換顏色 (None=使用歌曲預設, 1=Smile, 2=Pure, 3=Cool)
                "leader_designation": "0",   # 指定隊長卡片ID，"0"=不指定（自動選擇）
            },
            # 複製以下區塊可以添加第二首、第三首歌曲：
            # {
            #     "music_id": "405117",      # 第二首歌
            #     "difficulty": "03",
            #     "mastery_level": 50,
            #     "mustcards_all": [],
            #     "mustcards_any": [],
            #     "center_override": None,
            #     "color_override": None,
            #     "leader_designation": "0",
            # },
        ],

        # --- Debug 模式專用（從第一首歌繼承歌曲配置） ---
        "debug_deck_cards": [1011501, 1052506, 1041802, 1052901, 1041517, 1051506],  # 固定的6張卡牌順序
    }

    # ====================================================

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

    # 解析命令列參數或使用預設配置
    SONGS_CONFIG = parse_arguments(UNIFIED_CONFIG)

    # 如果是 Debug 模式，直接運行並退出
    if isinstance(SONGS_CONFIG, dict) and SONGS_CONFIG.get("debug_mode"):
        run_debug_mode(SONGS_CONFIG["deck_cards"], SONGS_CONFIG["center_index"], UNIFIED_CONFIG)
        end_time = time.time()
        logger.info(f"\n總耗時: {end_time - start_time:.2f} 秒")
        sys.exit(0)

    # 如果沒有命令列參數，使用統一配置中的歌曲列表
    if SONGS_CONFIG is None:
        SONGS_CONFIG = UNIFIED_CONFIG["songs"]
        logger.info(f"從配置區載入 {len(SONGS_CONFIG)} 首歌曲")

    logger.info(f"將模擬 {len(SONGS_CONFIG)} 首歌曲")
    for idx, config in enumerate(SONGS_CONFIG, 1):
        logger.info(f"  歌曲 {idx}: ID={config['music_id']}, 難度={config['difficulty']}, 熟練度={config['mastery_level']}")






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
            # 優化：經過測試，chunksize=7500 在 PyPy 下性能最佳（比 10000 快 1.3%）
            if pypy_impl:
                chunksize = 7500
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
