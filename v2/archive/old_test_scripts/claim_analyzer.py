#!/usr/bin/env python3
"""
請求項分析ユーティリティ

構成要件データから独立請求項とコア要素を識別する小さな関数群。
テスト駆動開発により段階的に構築。
"""

from typing import List, Dict


def identify_independent_claims(elements: List[Dict]) -> List[str]:
    """
    独立請求項の要素IDを抽出

    Args:
        elements: 構成要件リスト（各要素は'claim_type'フィールドを持つ）

    Returns:
        独立請求項のelement_idリスト（構成要素番号）

    Example:
        >>> elements = [
        ...     {'構成要素番号': '1a', 'claim_type': 'independent'},
        ...     {'構成要素番号': '1b', 'claim_type': 'dependent'}
        ... ]
        >>> identify_independent_claims(elements)
        ['1a']
    """
    return [
        e['構成要素番号']
        for e in elements
        if e.get('claim_type') == 'independent'
    ]


def identify_core_elements(
    elements: List[Dict],
    importance_threshold: float = 0.95
) -> List[str]:
    """
    コア要素を特定（重要度とコアフラグの組み合わせ）

    Args:
        elements: 構成要件リスト
        importance_threshold: 重要度の閾値（デフォルト: 0.95）

    Returns:
        コア要素のelement_idリスト（構成要素番号）

    Note:
        コア要素の条件:
        - 重要度が閾値以上 AND
        - is_core_elementフラグがTrue

    Example:
        >>> elements = [
        ...     {'構成要素番号': '1a', '構成要素の重要度': 1.0, 'is_core_element': True},
        ...     {'構成要素番号': '1b', '構成要素の重要度': 0.95, 'is_core_element': False},
        ...     {'構成要素番号': '1d', '構成要素の重要度': 1.0, 'is_core_element': True}
        ... ]
        >>> identify_core_elements(elements)
        ['1a', '1d']
    """
    return [
        e['構成要素番号']
        for e in elements
        if e.get('構成要素の重要度', 0) >= importance_threshold
        and e.get('is_core_element', False)
    ]
