"""
多歌曲卡組最佳化求解器 - Cython 加速版本

使用 Cython 優化的核心搜尋演算法，效能提升 10-50 倍

使用前請先編譯 Cython 模組：
    python setup.py build_ext --inplace
"""

import json
import logging
import os
import time
import sys
import argparse
from tqdm import tqdm
from CardLevelConfig import fix_windows_console_encoding
from Simulator_core import DB_CARDDATA
from RChart import MusicDB

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

# === 配置 ===
# 配置求解歌曲，格式: ("歌曲ID", "難度"),
# 求解前需執行 MainBatch.py 產生對應的卡組得分記錄
CHALLENGE_SONGS = [
    # 若只輸入兩首歌則會尋找僅針對兩面的最優解，不考慮第三面
    ("405119", "02"),  # 一生に夢が咲くように
    ("405121", "02"),  # ハートにQ
    ("405107", "02"),  # Shocking Party
]

# 每首歌只保留得分排名前 N 名的卡組用於求解
TOP_N = 56005

# 角色名稱映射
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
    """根據角色ID取得角色名稱"""
    return CHARACTER_NAMES.get(character_id, f'Unknown({character_id})')


def get_card_name(card_id: int) -> str:
    """根據卡面ID取得卡面名稱"""
    card_key = str(card_id)
    if card_key in DB_CARDDATA:
        return DB_CARDDATA[card_key].get('Name', f'Unknown({card_id})')
    return f'Unknown({card_id})'


def get_card_full_info(card_id: int) -> tuple[str, str]:
    """
    根據卡面ID取得角色名和卡面名

    Returns:
        (角色名, 卡面名) 元組
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
    """格式化卡組，顯示ID和名稱"""
    lines = []
    for card_id in deck_card_ids:
        character_name, card_name = get_card_full_info(card_id)
        lines.append(f"      {card_id}: {character_name} - {card_name}")
    return '\n'.join(lines)


def get_song_title(music_id: str, music_db=None) -> str:
    """根據歌曲ID取得歌名"""
    try:
        if music_db is None:
            music_db = MusicDB()
        music = music_db.get_music_by_id(music_id)
        if music:
            return music.Title
    except Exception:
        pass
    return f'Unknown({music_id})'


if __name__ == "__main__":
    fix_windows_console_encoding()

    # 嘗試匯入 Cython 模組
    try:
        import optimizer_core
        logger.info("✓ Cython module loaded successfully")
    except ImportError as e:
        logger.error("✗ Failed to import Cython module 'optimizer_core'")
        logger.error(f"  Error: {e}")
        logger.error("\n請先編譯 Cython 模組：")
        logger.error("  python setup.py build_ext --inplace\n")
        logger.error("如果編譯失敗，請確保已安裝：")
        logger.error("  pip install cython")
        logger.error("  並安裝 C 編譯器 (Windows: Visual Studio Build Tools, Linux: gcc)")
        sys.exit(1)

    # 解析命令列參數
    parser = argparse.ArgumentParser(description='多歌曲卡組最佳化求解器 (Cython 加速版)')
    parser.add_argument('--config', type=str, metavar='CONFIG_FILE',
                       help='YAML配置檔案路徑（例如：config/member-alice.yaml）')
    parser.add_argument('--debug', action='store_true',
                       help='啟用偵錯模式，顯示詳細統計資訊')
    args = parser.parse_args()

    start_time = time.time()

    # 嘗試讀取配置管理器以取得正確的 log 目錄
    try:
        from config_manager import get_config
        if args.config:
            config = get_config(args.config)
            logger.info(f"使用命令列指定的配置檔: {args.config}")
        else:
            config = get_config()
            logger.info(f"使用預設配置檔: {config.config_file}")

        LOG_DIR = config.get_log_dir()
        logger.info(f"log 目錄: {LOG_DIR}")
    except (ImportError, ValueError, FileNotFoundError) as e:
        LOG_DIR = "log"
        logger.info(f"配置管理器不可用或找不到配置檔 ({e})，使用預設 log 目錄: {LOG_DIR}")

    level_files = []
    for music_id, difficulty in CHALLENGE_SONGS:
        level_files.append(os.path.join(LOG_DIR, f"simulation_results_{music_id}_{difficulty}.json"))

    # === 讀取與準備資料 ===
    logger.info("Preparing data...")
    levels_raw = []
    all_cards = set()

    # 初始化一次 MusicDB 避免重複載入
    try:
        music_db = MusicDB()
    except Exception:
        music_db = None
        logger.warning("Failed to load MusicDB, song titles will show as Unknown")

    for i, f in enumerate(level_files):
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            total = len(data)
            data.sort(key=lambda x: x["pt"], reverse=True)
            data = data[:TOP_N]
            levels_raw.append(data)
            for deck in data:
                all_cards.update(deck["deck_card_ids"])
        song_id, difficulty = CHALLENGE_SONGS[i]
        song_title = get_song_title(song_id, music_db)
        logger.info(f"Loaded top {TOP_N} of {total} results for {song_id}_{difficulty} ({song_title})")

    # 僅針對兩首歌曲求解時，第三首歌填充假資料
    if len(CHALLENGE_SONGS) == 2:
        levels_raw.append([{
            "deck_card_ids": [],
            "score": 0,
            "pt": 0
        }])

    # === 根據每關最高 Pt 重新排序（預設按大、小、中順序）===
    if len(CHALLENGE_SONGS) == 3:
        best = [deck[0]["pt"] for deck in levels_raw]
        i_max = max(range(3), key=lambda i: best[i])
        i_min = min(range(3), key=lambda i: best[i])
        i_mid = 3 - i_max - i_min
        sorted_indices = [i_max, i_min, i_mid]
        CHALLENGE_SONGS = [CHALLENGE_SONGS[i] for i in sorted_indices]
        levels_raw = [levels_raw[i] for i in sorted_indices]
        logger.info(f"Challenge songs reordered for optimization: {CHALLENGE_SONGS}")

    # === 建立卡牌ID到bit位的映射 ===
    card_to_bit = {cid: i for i, cid in enumerate(sorted(all_cards))}
    logger.info(f"Loaded {len(card_to_bit)} unique cards")
    assert len(card_to_bit) <= 64, "卡牌種類超過64張時需使用更複雜的bitarray方案"

    # === 轉換deck為bitmask ===
    def deck_to_mask(deck):
        mask = 0
        for cid in deck["deck_card_ids"]:
            mask |= 1 << card_to_bit[cid]
        return mask

    levels = []
    for data in levels_raw:
        decks = []
        for i, deck in enumerate(data, start=1):
            decks.append({
                "mask": deck_to_mask(deck),
                "rank": i,
                "score": deck["score"],
                "pt": deck["pt"],
                "deck": deck["deck_card_ids"]
            })
        levels.append(decks)

    logger.info("Starting Cython-optimized deck search...")
    logger.info(f"Search space: {len(levels[0])} × {len(levels[1])} × {len(levels[2])} = {len(levels[0]) * len(levels[1]) * len(levels[2]):,} combinations")

    # === 使用 Cython 核心搜尋 ===
    search_start = time.time()

    # 進度條回呼
    pbar = tqdm(total=len(levels[0]), desc="Cython Search", unit="deck")

    def progress_callback(current, total):
        pbar.n = current
        pbar.refresh()

    if args.debug:
        # 偵錯模式：使用帶統計的版本
        result = optimizer_core.optimize_decks_debug(
            levels[0],
            levels[1],
            levels[2]
        )
        pbar.close()

        logger.info("\n=== Debug Statistics ===")
        logger.info(f"Total iterations: {result['iterations']:,}")
        logger.info(f"Conflicts detected: {result['conflicts']:,}")
        logger.info(f"Pruned combinations: {result['pruned']:,}")

        best_pt = result["best_pt"]
        i1, i2, i3 = result["deck1_idx"], result["deck2_idx"], result["deck3_idx"]
    else:
        # 正常模式：使用優化版本
        result = optimizer_core.optimize_decks(
            levels[0],
            levels[1],
            levels[2],
            callback=progress_callback
        )
        pbar.close()

        if result is None:
            logger.error("No valid combination found!")
            sys.exit(1)

        best_pt, i1, i2, i3 = result

    search_end = time.time()
    search_time = search_end - search_start

    best_combo = (levels[0][i1], levels[1][i2], levels[2][i3])

    logger.info(f"\n✓ Optimization completed in {search_time:.2f} seconds")
    logger.info(f"Best total pt found: {best_pt:,}")

    end_time = time.time()
    total_time = end_time - start_time

    logger.info(f"Total time (including data loading): {total_time:.2f} seconds")

    # === 輸出結果 ===
    output = []
    output.append("=== Best Combination (Cython Optimized) ===")
    output.append("")
    output.append(f"Total Pt: {best_pt:,}")
    output.append(f"Search Time: {search_time:.2f} seconds")
    output.append("")

    for i, d in enumerate(best_combo):
        if i < len(CHALLENGE_SONGS):
            song_id, difficulty = CHALLENGE_SONGS[i]
            song_title = get_song_title(song_id, music_db)
            output.append(f"Song {i+1}: {song_id} (Difficulty: {difficulty}) - {song_title}")
            output.append(f"  Score: {d['score']:,}")
            output.append(f"  Pt: {d['pt']:,}  (Rank: #{d['rank']})")
            output.append(f"  Deck:")
            output.append(format_deck_with_names(d['deck']))
            output.append("")

    output = "\n".join(output)
    logger.info(f"\n{output}")

    with open("best_3_song_combo_cython.txt", "w", encoding="utf-8") as f:
        f.write(output)
        f.write("\n")
    logger.info(f"Best 3-song combination saved to best_3_song_combo_cython.txt")
