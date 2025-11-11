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
    level=logging.INFO,  # Adjust logging level as needed (e.g., INFO, DEBUG)
    format='%(message)s'
)

# === 配置 ===
# 配置求解歌曲，格式: ("歌曲ID", "难度"),
# 求解前需运行 MainBatch.py 生成对应的卡组得分记录
CHALLENGE_SONGS = [
    # 若只输入两首歌则会寻找仅针对两面的最优解，不考虑第三面
    # ("405119", "02"),  # 一生に夢が咲くように
    ("405121", "02"),  # ハートにQ
    ("405107", "02"),  # Shocking Party
]

# 每首歌只保留得分排名前 N 名的卡组用于求解
TOP_N = 5000

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
    """根据角色ID获取角色名称"""
    return CHARACTER_NAMES.get(character_id, f'Unknown({character_id})')


def get_card_name(card_id: int) -> str:
    """根据卡面ID获取卡面名称"""
    card_key = str(card_id)
    if card_key in DB_CARDDATA:
        return DB_CARDDATA[card_key].get('Name', f'Unknown({card_id})')
    return f'Unknown({card_id})'


def get_card_full_info(card_id: int) -> tuple[str, str]:
    """
    根据卡面ID获取角色名和卡面名

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
    """格式化卡组，显示ID和名称"""
    lines = []
    for card_id in deck_card_ids:
        character_name, card_name = get_card_full_info(card_id)
        lines.append(f"      {card_id}: {character_name} - {card_name}")
    return '\n'.join(lines)


def get_song_title(music_id: str) -> str:
    """根据歌曲ID获取歌名"""
    try:
        music_db = MusicDB()
        music = music_db.get_music_by_id(music_id)
        if music:
            return music.Title
    except Exception:
        pass
    return f'Unknown({music_id})'


if __name__ == "__main__":
    fix_windows_console_encoding()

    # 解析命令列參數
    parser = argparse.ArgumentParser(description='多歌曲卡組最佳化求解器')
    parser.add_argument('--config', type=str, metavar='CONFIG_FILE',
                       help='YAML配置檔案路徑（例如：config/member-alice.yaml）')
    args = parser.parse_args()

    start_time = time.time()

    # 嘗試讀取配置管理器以獲取正確的 log 目錄
    try:
        from config_manager import get_config
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
    except (ImportError, FileNotFoundError) as e:
        # 如果沒有配置管理器或找不到配置，使用默認的 log 目錄
        LOG_DIR = "log"
        logger.info(f"配置管理器不可用或找不到配置檔 ({e})，使用默認 log 目錄: {LOG_DIR}")

    level_files = []
    for music_id, difficulty in CHALLENGE_SONGS:
        level_files.append(os.path.join(LOG_DIR, f"simulation_results_{music_id}_{difficulty}.json"))

    # === 读取与准备数据 ===
    logger.info("Preparing data...")
    levels_raw = []
    all_cards = set()

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
        song_title = get_song_title(song_id)
        logger.info(f"Loaded top {TOP_N} of {total} results for {song_id}_{difficulty} ({song_title})")

    # 仅针对两首歌曲求解时，第三首歌填充假数据
    if len(CHALLENGE_SONGS) == 2:
        levels_raw.append([{
            "deck_card_ids": [],
            "score": 0,
            "pt": 0
        }])

    # === 根据每关最高 Pt 重新排序（默认按大、小、中顺序）===
    if len(CHALLENGE_SONGS) == 3:
        best = [deck[0]["pt"] for deck in levels_raw]
        i_max = max(range(3), key=lambda i: best[i])
        i_min = min(range(3), key=lambda i: best[i])
        i_mid = 3 - i_max - i_min
        sorted_indices = [i_max, i_min, i_mid]
        # 重排 level_files 和 levels_raw
        CHALLENGE_SONGS = [CHALLENGE_SONGS[i] for i in sorted_indices]
        levels_raw = [levels_raw[i] for i in sorted_indices]
        logger.info(f"Challenge songs reordered for optimization: {CHALLENGE_SONGS}")

    # === 建立卡牌ID到bit位的映射 ===
    card_to_bit = {cid: i for i, cid in enumerate(sorted(all_cards))}
    logger.info(f"Loaded {len(card_to_bit)} unique cards")
    assert len(card_to_bit) <= 64, "卡牌种类超过64张时需使用更复杂的bitarray方案"

    # === 转换deck为bitmask ===
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

    logger.info("Starting deck optimization...")
    # === 主搜索逻辑 ===
    best_pt = -1
    best_combo = None

    # 三重循环 + 多级剪枝
    for i1, deck1 in tqdm(enumerate(levels[0]), total=len(levels[0]), desc="Song 1", leave=True, position=0):
        mask1, pt1 = deck1["mask"], deck1["pt"]

        # 上限剪枝：即便选取剩下两关最高pt，也不可能超过best_pt
        max_possible = pt1 + levels[1][0]["pt"] + levels[2][0]["pt"]
        if max_possible <= best_pt:
            break

        for i2, deck2 in enumerate(levels[1]):
            mask2, pt2 = deck2["mask"], deck2["pt"]

            # 检查冲突
            if mask1 & mask2:
                continue

            pt12 = pt1 + pt2

            # 第二层剪枝：deck3最高pt都不够超越当前最优
            if pt12 + levels[2][0]["pt"] <= best_pt:
                break

            for i3, deck3 in enumerate(levels[2]):
                mask3, pt3 = deck3["mask"], deck3["pt"]

                # 冲突检测
                if (mask1 | mask2) & mask3:
                    continue

                total_pt = pt12 + pt3

                if total_pt > best_pt:
                    best_pt = total_pt
                    best_combo = (deck1, deck2, deck3)
                    logger.info(f"New best total pt found: {best_pt}")
                    for i, d in enumerate(best_combo):
                        # 只顯示有效的歌曲（當只有2首歌時，第3首是假數據）
                        if i < len(CHALLENGE_SONGS):
                            logger.info(f"  Song {i+1} {CHALLENGE_SONGS[i]}: ")
                            logger.info(f"    Pt: {d['pt']:,}\tScore: {d['score']:,}\tRank: {d['rank']}")
                            logger.info(f"    Deck (ID): {d['deck']}")
                else:
                    break

    end_time = time.time()
    logger.info("--- Optimization completed! ---")
    logger.info(f"Total time: {end_time - start_time:.2f} seconds \n")

    # === 输出结果 ===
    output = []
    output.append("=== Best Combination ===")
    output.append("")
    output.append(f"Total Pt: {best_pt:,}")
    output.append("")

    for i, d in enumerate(best_combo):
        if i < len(CHALLENGE_SONGS):
            song_id, difficulty = CHALLENGE_SONGS[i]
            song_title = get_song_title(song_id)
            output.append(f"Song {i+1}: {song_id} (Difficulty: {difficulty}) - {song_title}")
            output.append(f"  Score: {d['score']:,}")
            output.append(f"  Pt: {d['pt']:,}  (Rank: #{d['rank']})")
            output.append(f"  Deck:")
            # 使用新的格式化函數顯示卡組
            output.append(format_deck_with_names(d['deck']))
            output.append("")

    output = "\n".join(output)
    logger.info(f"\n{output}")

    with open("best_3_song_combo.txt", "w", encoding="utf-8") as f:
        f.write(output)
        f.write("\n")
    logger.info(f"Best 3-song combination saved to best_3_song_combo.txt")
