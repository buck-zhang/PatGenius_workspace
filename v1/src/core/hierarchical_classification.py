"""
階層的分類コード展開モジュール

分類コード（FI/CPC）を階層的に展開して、兄弟サブグループや親レベルのコードを含めることで、
検索の再現率（リコール）を向上させます。

使用例:
    - H10D30/00 → H10D30/00, H10D (親レベル)
    - H10D30/00 → H10D30/00, H10D86/00 (兄弟グループ)
"""

import re
import logging
from typing import List, Dict, Set


logger = logging.getLogger(__name__)


def extract_parent_code(code: str) -> str:
    """
    分類コードから親レベルのコードを抽出

    Args:
        code: 分類コード（例: "H10D30/00", "G11C11/56220"）

    Returns:
        親レベルのコード（例: "H10D", "G11C"）

    Examples:
        >>> extract_parent_code("H10D30/00")
        'H10D'
        >>> extract_parent_code("G11C11/56220")
        'G11C'
        >>> extract_parent_code("H10D86/421")
        'H10D'
    """
    # スペースと\\ を除去
    cleaned = code.replace(" ", "").replace("\\", "")

    # / より前の部分を取得（サブクラス+グループ番号）
    if "/" in cleaned:
        before_slash = cleaned.split("/")[0]
    else:
        before_slash = cleaned

    # 親レベルコードを抽出
    # パターン: セクション(1文字) + クラス(数字2桁 + オプションで文字1つ)
    # 例: H10D30 → H10D (H + 10D)
    #     G11C11 → G11C (G + 11C)

    match = re.match(r'([A-Z])(\d+)([A-Z]?)', before_slash)
    if match:
        section = match.group(1)  # 例: H
        digits = match.group(2)   # 例: 10
        letter = match.group(3)   # 例: D

        # クラスレベル: 最初の2桁 + その後の文字（あれば）
        if len(digits) >= 2:
            class_part = digits[:2]
            if letter:
                parent = f"{section}{class_part}{letter}"
            else:
                parent = f"{section}{class_part}"
            return parent

    return ""


def expand_classification_hierarchically(
    codes: List[str],
    expansion_level: str = "parent",
    known_siblings: Dict[str, List[str]] = None
) -> List[str]:
    """
    分類コードを階層的に展開

    Args:
        codes: 元の分類コードリスト
        expansion_level: 展開レベル
            - "parent": 親レベルのみ追加
            - "siblings": 既知の兄弟グループのみ追加
            - "both": 親+兄弟の両方
        known_siblings: 既知の兄弟グループマッピング
            例: {"H10D30": ["H10D30", "H10D86"]}

    Returns:
        展開された分類コードリスト（重複除去済み）

    Examples:
        >>> codes = ["H10D30/00", "H10D30/60"]
        >>> expand_classification_hierarchically(codes, "parent")
        ['H10D', 'H10D30/00', 'H10D30/60']

        >>> expand_classification_hierarchically(codes, "siblings")
        ['H10D30/00', 'H10D30/60', 'H10D86/00', 'H10D86/60']
    """
    if known_siblings is None:
        # デフォルトの兄弟グループマッピング
        # ドメイン知識に基づいて定義（必要に応じて拡張可能）
        known_siblings = {
            # 半導体関連
            "H10D30": ["H10D30", "H10D86"],  # 材料 vs デバイス
            "H10D86": ["H10D30", "H10D86"],

            # メモリ関連
            "G11C11": ["G11C11", "G11C27"],  # スタティック vs 他の記憶回路
            "G11C27": ["G11C11", "G11C27"],
            "G11C16": ["G11C11", "G11C16", "G11C27"],  # 不揮発性メモリ

            # 追加の兄弟グループはここに定義
        }

    expanded = set(codes)  # 元のコードを保持
    parent_codes_added = 0
    sibling_codes_added = 0

    if expansion_level in ("parent", "both"):
        # 親レベルコードを追加
        for code in codes:
            parent = extract_parent_code(code)
            if parent and parent not in expanded:
                expanded.add(parent)
                parent_codes_added += 1

        if parent_codes_added > 0:
            logger.info(f"Added {parent_codes_added} parent-level codes")

    if expansion_level in ("siblings", "both"):
        # 兄弟グループを追加
        for code in codes:
            # コードから主要部分を抽出（例: H10D30/00 → H10D30）
            cleaned = code.replace(" ", "").replace("\\", "")

            # サブクラスレベルを抽出（/より前）
            if "/" in cleaned:
                subclass = cleaned.split("/")[0]
            else:
                subclass = cleaned

            # 兄弟グループが定義されている場合、それらを追加
            if subclass in known_siblings:
                siblings = known_siblings[subclass]
                for sibling in siblings:
                    # 元のコードと同じ形式で兄弟コードを生成
                    if "/" in cleaned:
                        group_part = cleaned.split("/")[1]
                        sibling_code = f"{sibling}/{group_part}"
                        if sibling_code not in expanded:
                            expanded.add(sibling_code)
                            sibling_codes_added += 1
                    else:
                        if sibling not in expanded:
                            expanded.add(sibling)
                            sibling_codes_added += 1

        if sibling_codes_added > 0:
            logger.info(f"Added {sibling_codes_added} sibling classification codes")

    result = sorted(list(expanded))

    if len(result) > len(codes):
        logger.info(f"Hierarchical expansion: {len(codes)} → {len(result)} codes")

    return result


def should_enable_hierarchical_expansion(
    recall_mode: bool,
    total_hits: int,
    target_min_hits: int,
    current_adjustment: str
) -> bool:
    """
    階層的展開を有効にすべきかどうかを判断

    Args:
        recall_mode: リコールモードが有効かどうか
        total_hits: 現在の検索ヒット件数
        target_min_hits: 目標最小ヒット件数
        current_adjustment: 現在の調整モード ("expand", "narrow", "maintain")

    Returns:
        階層的展開を有効にすべき場合True
    """
    # リコールモード時は常に有効
    if recall_mode:
        return True

    # ヒット件数が極端に少ない場合
    if total_hits < target_min_hits and total_hits > 0:
        return True

    # 拡大検索モード時
    if current_adjustment == "expand":
        return True

    return False
