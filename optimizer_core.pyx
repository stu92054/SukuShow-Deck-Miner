# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: initializedcheck=False

"""
Cython 優化的卡組搜尋核心模組

使用純 C 類型和位元運算實現三重迴圈搜尋，
大幅提升效能（預估 10-50x 加速）
"""

from libc.stdint cimport int64_t
from libc.stdlib cimport malloc, free


cdef struct Deck:
    int64_t mask      # 卡組位元遮罩
    int rank          # 排名
    int64_t score     # 分數（可能超過 2^31）
    int64_t pt        # Pt 值（可能超過 2^31）
    int deck_idx      # 原始資料索引


cdef struct BestCombo:
    int64_t pt        # 總 Pt（可能超過 2^31）
    int deck1_idx     # deck1 在 level0 中的索引
    int deck2_idx     # deck2 在 level1 中的索引
    int deck3_idx     # deck3 在 level2 中的索引


def optimize_decks(
    list level0_data,
    list level1_data,
    list level2_data,
    callback=None
):
    """
    使用 Cython 優化的三重迴圈搜尋最優卡組組合

    Args:
        level0_data: 第一首歌的卡組資料 [{"mask": int, "rank": int, "score": int, "pt": int}, ...]
        level1_data: 第二首歌的卡組資料
        level2_data: 第三首歌的卡組資料
        callback: 可選的進度回呼函式 callback(current, total)

    Returns:
        (best_pt, deck1_idx, deck2_idx, deck3_idx) 或 None
    """
    cdef int n0 = len(level0_data)
    cdef int n1 = len(level1_data)
    cdef int n2 = len(level2_data)

    # 初始化指標為 NULL
    cdef Deck* level0 = NULL
    cdef Deck* level1 = NULL
    cdef Deck* level2 = NULL
    cdef int i
    cdef BestCombo result

    try:
        # 分配 C 陣列
        level0 = <Deck*>malloc(n0 * sizeof(Deck))
        level1 = <Deck*>malloc(n1 * sizeof(Deck))
        level2 = <Deck*>malloc(n2 * sizeof(Deck))

        if not level0 or not level1 or not level2:
            raise MemoryError("Failed to allocate memory for deck arrays")

        # 將 Python 資料複製到 C 結構
        for i in range(n0):
            level0[i].mask = level0_data[i]["mask"]
            level0[i].rank = level0_data[i]["rank"]
            level0[i].score = level0_data[i]["score"]
            level0[i].pt = level0_data[i]["pt"]
            level0[i].deck_idx = i

        for i in range(n1):
            level1[i].mask = level1_data[i]["mask"]
            level1[i].rank = level1_data[i]["rank"]
            level1[i].score = level1_data[i]["score"]
            level1[i].pt = level1_data[i]["pt"]
            level1[i].deck_idx = i

        for i in range(n2):
            level2[i].mask = level2_data[i]["mask"]
            level2[i].rank = level2_data[i]["rank"]
            level2[i].score = level2_data[i]["score"]
            level2[i].pt = level2_data[i]["pt"]
            level2[i].deck_idx = i

        # 執行核心搜尋
        result = search_best_combo(
            level0, n0,
            level1, n1,
            level2, n2,
            callback
        )

        if result.pt <= 0:
            return None

        return (result.pt, result.deck1_idx, result.deck2_idx, result.deck3_idx)

    finally:
        # 無論如何都釋放記憶體
        free(level0)
        free(level1)
        free(level2)


cdef BestCombo search_best_combo(
    Deck* level0, int n0,
    Deck* level1, int n1,
    Deck* level2, int n2,
    callback
) noexcept nogil:
    """
    核心搜尋演算法（C 類型，無 GIL）

    使用三重迴圈 + 多級剪枝尋找最優組合
    """
    cdef BestCombo best
    best.pt = -1
    best.deck1_idx = -1
    best.deck2_idx = -1
    best.deck3_idx = -1

    cdef int i1, i2, i3
    cdef int64_t mask1, mask2, mask3, mask12
    cdef int64_t pt1, pt2, pt3, pt12, total_pt
    cdef int64_t max_possible
    cdef int64_t max_pt1 = level0[0].pt if n0 > 0 else 0
    cdef int64_t max_pt2 = level1[0].pt if n1 > 0 else 0
    cdef int64_t max_pt3 = level2[0].pt if n2 > 0 else 0

    cdef int progress_step = n0 // 100 if n0 >= 100 else 1

    # 三重迴圈主體
    for i1 in range(n0):
        mask1 = level0[i1].mask
        pt1 = level0[i1].pt

        # 剪枝 1: 即使選取剩餘兩關最高 pt，也無法超越當前最優
        max_possible = pt1 + max_pt2 + max_pt3
        if max_possible <= best.pt:
            break

        # 進度回呼（需要取得 GIL）
        if callback is not None and i1 % progress_step == 0:
            with gil:
                callback(i1, n0)

        for i2 in range(n1):
            mask2 = level1[i2].mask
            pt2 = level1[i2].pt

            # 衝突檢測：deck1 和 deck2 是否有重複卡牌
            if mask1 & mask2:
                continue

            pt12 = pt1 + pt2
            mask12 = mask1 | mask2

            # 剪枝 2: deck3 最高 pt 都不夠超越當前最優
            if pt12 + max_pt3 <= best.pt:
                break

            for i3 in range(n2):
                mask3 = level2[i3].mask
                pt3 = level2[i3].pt

                # 衝突檢測：deck1+deck2 和 deck3 是否有重複卡牌
                if mask12 & mask3:
                    continue

                total_pt = pt12 + pt3

                if total_pt > best.pt:
                    best.pt = total_pt
                    best.deck1_idx = i1
                    best.deck2_idx = i2
                    best.deck3_idx = i3
                else:
                    # 剪枝 3: 由於 deck 按 pt 降序排列，
                    # 後續 deck3 的 pt 只會更低，直接跳出
                    break

    return best


def optimize_decks_debug(
    list level0_data,
    list level1_data,
    list level2_data
):
    """
    偵錯版本：回傳詳細統計資訊

    Returns:
        dict: {
            "best_pt": int,
            "deck1_idx": int,
            "deck2_idx": int,
            "deck3_idx": int,
            "iterations": int,
            "conflicts": int,
            "pruned": int
        }
    """
    cdef int n0 = len(level0_data)
    cdef int n1 = len(level1_data)
    cdef int n2 = len(level2_data)

    # 初始化指標為 NULL
    cdef Deck* level0 = NULL
    cdef Deck* level1 = NULL
    cdef Deck* level2 = NULL
    cdef int i
    cdef int64_t iterations = 0
    cdef int64_t conflicts = 0
    cdef int64_t pruned = 0
    cdef BestCombo best

    try:
        level0 = <Deck*>malloc(n0 * sizeof(Deck))
        level1 = <Deck*>malloc(n1 * sizeof(Deck))
        level2 = <Deck*>malloc(n2 * sizeof(Deck))

        if not level0 or not level1 or not level2:
            raise MemoryError("Failed to allocate memory")

        for i in range(n0):
            level0[i].mask = level0_data[i]["mask"]
            level0[i].pt = level0_data[i]["pt"]
            level0[i].deck_idx = i

        for i in range(n1):
            level1[i].mask = level1_data[i]["mask"]
            level1[i].pt = level1_data[i]["pt"]
            level1[i].deck_idx = i

        for i in range(n2):
            level2[i].mask = level2_data[i]["mask"]
            level2[i].pt = level2_data[i]["pt"]
            level2[i].deck_idx = i

        # 執行帶統計的搜尋
        best = search_best_combo_debug(
            level0, n0,
            level1, n1,
            level2, n2,
            &iterations,
            &conflicts,
            &pruned
        )

        return {
            "best_pt": best.pt,
            "deck1_idx": best.deck1_idx,
            "deck2_idx": best.deck2_idx,
            "deck3_idx": best.deck3_idx,
            "iterations": iterations,
            "conflicts": conflicts,
            "pruned": pruned
        }

    finally:
        # 無論如何都釋放記憶體
        free(level0)
        free(level1)
        free(level2)


cdef BestCombo search_best_combo_debug(
    Deck* level0, int n0,
    Deck* level1, int n1,
    Deck* level2, int n2,
    int64_t* iterations,
    int64_t* conflicts,
    int64_t* pruned
) noexcept nogil:
    """偵錯版本的搜尋演算法，記錄統計資訊"""
    cdef BestCombo best
    best.pt = -1
    best.deck1_idx = -1
    best.deck2_idx = -1
    best.deck3_idx = -1

    iterations[0] = 0
    conflicts[0] = 0
    pruned[0] = 0

    cdef int i1, i2, i3
    cdef int64_t mask1, mask2, mask3, mask12
    cdef int64_t pt1, pt2, pt3, pt12, total_pt
    cdef int64_t max_possible
    cdef int64_t max_pt1 = level0[0].pt if n0 > 0 else 0
    cdef int64_t max_pt2 = level1[0].pt if n1 > 0 else 0
    cdef int64_t max_pt3 = level2[0].pt if n2 > 0 else 0

    for i1 in range(n0):
        mask1 = level0[i1].mask
        pt1 = level0[i1].pt

        max_possible = pt1 + max_pt2 + max_pt3
        if max_possible <= best.pt:
            pruned[0] += (n0 - i1) * n1 * n2
            break

        for i2 in range(n1):
            mask2 = level1[i2].mask
            pt2 = level1[i2].pt

            if mask1 & mask2:
                conflicts[0] += 1
                continue

            pt12 = pt1 + pt2
            mask12 = mask1 | mask2

            if pt12 + max_pt3 <= best.pt:
                pruned[0] += (n1 - i2) * n2
                break

            for i3 in range(n2):
                iterations[0] += 1
                mask3 = level2[i3].mask
                pt3 = level2[i3].pt

                if mask12 & mask3:
                    conflicts[0] += 1
                    continue

                total_pt = pt12 + pt3

                if total_pt > best.pt:
                    best.pt = total_pt
                    best.deck1_idx = i1
                    best.deck2_idx = i2
                    best.deck3_idx = i3
                else:
                    pruned[0] += (n2 - i3)
                    break

    return best
