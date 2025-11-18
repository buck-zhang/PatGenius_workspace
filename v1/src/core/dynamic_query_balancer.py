"""
動的クエリバランシングモジュール
Dynamic Query Balancing Module

ヒット数に応じてOR/AND条件を動的に調整し、最適な検索範囲を実現します。
"""

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class QueryLogic(Enum):
    """クエリ論理"""
    OR = "OR"
    AND = "AND"


@dataclass
class BalancingStrategy:
    """バランシング戦略"""
    name: str
    classification_logic: QueryLogic  # 分類コード内の論理
    keyword_logic: QueryLogic         # キーワード内の論理
    cross_logic: QueryLogic           # 分類とキーワード間の論理
    max_classification_groups: int    # 分類コードグループ数
    max_keyword_groups: int           # キーワードグループ数
    max_items_per_group: int          # グループ内の最大項目数
    description: str


class DynamicQueryBalancer:
    """動的クエリバランシングクラス"""

    # 戦略マトリクス（ヒット数範囲に応じた戦略）
    STRATEGIES = {
        # 極端に少ない（0-10件）→ 最大限拡大
        "ultra_expand": BalancingStrategy(
            name="Ultra Expand",
            classification_logic=QueryLogic.OR,
            keyword_logic=QueryLogic.OR,
            cross_logic=QueryLogic.OR,        # CPC OR キーワード（最も広い）
            max_classification_groups=5,
            max_keyword_groups=10,
            max_items_per_group=10,
            description="最大限拡大（0-10件の場合）"
        ),

        # 少なすぎる（10-50件）→ 拡大
        "expand": BalancingStrategy(
            name="Expand",
            classification_logic=QueryLogic.OR,
            keyword_logic=QueryLogic.OR,
            cross_logic=QueryLogic.OR,        # CPC OR キーワード
            max_classification_groups=4,
            max_keyword_groups=8,
            max_items_per_group=8,
            description="拡大戦略（10-50件の場合）"
        ),

        # やや少ない（50-100件）→ 軽度拡大
        "light_expand": BalancingStrategy(
            name="Light Expand",
            classification_logic=QueryLogic.OR,
            keyword_logic=QueryLogic.OR,
            cross_logic=QueryLogic.AND,       # CPC AND キーワード
            max_classification_groups=3,
            max_keyword_groups=6,
            max_items_per_group=6,
            description="軽度拡大（50-100件の場合）"
        ),

        # 適正範囲（100-300件）→ バランス維持
        "balanced": BalancingStrategy(
            name="Balanced",
            classification_logic=QueryLogic.OR,
            keyword_logic=QueryLogic.OR,
            cross_logic=QueryLogic.AND,       # CPC AND キーワード
            max_classification_groups=3,
            max_keyword_groups=5,
            max_items_per_group=5,
            description="バランス型（100-300件の場合）"
        ),

        # やや多い（300-1000件）→ 軽度縮小
        "light_narrow": BalancingStrategy(
            name="Light Narrow",
            classification_logic=QueryLogic.OR,
            keyword_logic=QueryLogic.AND,     # キーワード内をANDに
            cross_logic=QueryLogic.AND,
            max_classification_groups=3,
            max_keyword_groups=4,
            max_items_per_group=4,
            description="軽度縮小（300-1000件の場合）"
        ),

        # 多すぎる（1000-10000件）→ 縮小
        "narrow": BalancingStrategy(
            name="Narrow",
            classification_logic=QueryLogic.AND,  # 分類内もANDに
            keyword_logic=QueryLogic.AND,
            cross_logic=QueryLogic.AND,
            max_classification_groups=2,
            max_keyword_groups=3,
            max_items_per_group=3,
            description="縮小戦略（1000-10000件の場合）"
        ),

        # 極端に多い（10000件以上）→ 最大限縮小
        "ultra_narrow": BalancingStrategy(
            name="Ultra Narrow",
            classification_logic=QueryLogic.AND,
            keyword_logic=QueryLogic.AND,
            cross_logic=QueryLogic.AND,
            max_classification_groups=2,
            max_keyword_groups=2,
            max_items_per_group=2,
            description="最大限縮小（10000件以上の場合）"
        )
    }

    @staticmethod
    def select_strategy(current_hits: int,
                       target_min: int = 10,
                       target_max: int = 300) -> BalancingStrategy:
        """
        ヒット数に基づいて戦略を選択

        Args:
            current_hits: 現在のヒット数
            target_min: 目標最小ヒット数
            target_max: 目標最大ヒット数

        Returns:
            BalancingStrategy
        """
        # 目標範囲内なら balanced を返す
        if target_min <= current_hits <= target_max:
            strategy = DynamicQueryBalancer.STRATEGIES["balanced"]
            logger.info(f"✓ Target range achieved ({current_hits} hits) - using BALANCED strategy")
            return strategy

        # ヒット数に応じて戦略を選択
        if current_hits == 0:
            strategy_key = "ultra_expand"
        elif current_hits < 10:
            strategy_key = "ultra_expand"
        elif current_hits < 50:
            strategy_key = "expand"
        elif current_hits < target_min:
            strategy_key = "light_expand"
        elif current_hits <= target_max:
            strategy_key = "balanced"
        elif current_hits < 1000:
            strategy_key = "light_narrow"
        elif current_hits < 10000:
            strategy_key = "narrow"
        else:
            strategy_key = "ultra_narrow"

        strategy = DynamicQueryBalancer.STRATEGIES[strategy_key]
        logger.info(f"Selected strategy: {strategy.name} for {current_hits} hits")
        return strategy

    @staticmethod
    def build_balanced_query(classification_codes: List[str],
                            keywords: List[str],
                            strategy: BalancingStrategy) -> str:
        """
        戦略に基づいてバランスの取れたクエリを構築

        Args:
            classification_codes: 分類コードリスト
            keywords: キーワードリスト
            strategy: バランシング戦略

        Returns:
            検索クエリ文字列
        """
        # 分類コード部分を構築
        classification_part = DynamicQueryBalancer._build_classification_part(
            classification_codes, strategy
        )

        # キーワード部分を構築
        keyword_part = DynamicQueryBalancer._build_keyword_part(
            keywords, strategy
        )

        # 分類とキーワードを結合
        if classification_part and keyword_part:
            cross_op = strategy.cross_logic.value
            query = f"({classification_part}) {cross_op} ({keyword_part})"
        elif classification_part:
            query = classification_part
        elif keyword_part:
            query = keyword_part
        else:
            query = ""

        return query

    @staticmethod
    def _build_classification_part(codes: List[str],
                                   strategy: BalancingStrategy) -> str:
        """
        分類コード部分を構築

        Google Patents構文ルール:
        - 完全な分類コード (例: G11C11/00): CPC="G11C11/00" (大文字、引用符あり)
        - サブクラスワイルドカード (例: G11C): cpc=G11C (小文字、引用符なし)

        このメソッドは完全なコードを想定しているため、CPC="CODE"を使用

        Args:
            codes: 分類コードリスト (完全なコード、例: G11C11/00)
            strategy: バランシング戦略

        Returns:
            分類コードクエリ
        """
        if not codes:
            return ""

        # グループ数と項目数で制限
        max_codes = strategy.max_classification_groups * strategy.max_items_per_group
        limited_codes = codes[:max_codes]

        # 論理演算子を取得
        logic_op = strategy.classification_logic.value

        # クエリを構築 (完全一致: CPC="CODE")
        code_parts = [f'CPC="{code}"' for code in limited_codes]

        if logic_op == "OR":
            return " OR ".join(code_parts)
        else:  # AND
            # ANDの場合はグループに分けて、グループ内はOR、グループ間はAND
            group_size = strategy.max_items_per_group
            groups = []
            for i in range(0, len(code_parts), group_size):
                group = code_parts[i:i+group_size]
                if len(group) > 1:
                    groups.append(f"({' OR '.join(group)})")
                else:
                    groups.append(group[0])

            return " AND ".join(groups)

    @staticmethod
    def _build_keyword_part(keywords: List[str],
                           strategy: BalancingStrategy) -> str:
        """
        キーワード部分を構築

        Args:
            keywords: キーワードリスト
            strategy: バランシング戦略

        Returns:
            キーワードクエリ
        """
        if not keywords:
            return ""

        # グループ数と項目数で制限
        max_keywords = strategy.max_keyword_groups * strategy.max_items_per_group
        limited_keywords = keywords[:max_keywords]

        # 論理演算子を取得
        logic_op = strategy.keyword_logic.value

        # クエリを構築
        keyword_parts = [f'"{kw}"' for kw in limited_keywords]

        if logic_op == "OR":
            return " OR ".join(keyword_parts)
        else:  # AND
            # ANDの場合はグループに分けて、グループ内はOR、グループ間はAND
            group_size = strategy.max_items_per_group
            groups = []
            for i in range(0, len(keyword_parts), group_size):
                group = keyword_parts[i:i+group_size]
                if len(group) > 1:
                    groups.append(f"({' OR '.join(group)})")
                else:
                    groups.append(group[0])

            return " AND ".join(groups)

    @staticmethod
    def calculate_query_complexity(query: str) -> Dict[str, int]:
        """
        クエリの複雑度を計算

        Args:
            query: 検索クエリ文字列

        Returns:
            複雑度指標の辞書
        """
        and_count = query.count(" AND ")
        or_count = query.count(" OR ")
        paren_depth = DynamicQueryBalancer._calculate_paren_depth(query)
        term_count = query.count('"')// 2  # クォートで囲まれた項目数

        return {
            "and_count": and_count,
            "or_count": or_count,
            "paren_depth": paren_depth,
            "term_count": term_count,
            "total_operators": and_count + or_count,
            "complexity_score": and_count * 2 + or_count + paren_depth
        }

    @staticmethod
    def _calculate_paren_depth(query: str) -> int:
        """括弧の最大ネスト深度を計算"""
        max_depth = 0
        current_depth = 0

        for char in query:
            if char == '(':
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif char == ')':
                current_depth -= 1

        return max_depth


# テスト用のコード
if __name__ == "__main__":
    print("=" * 80)
    print("動的クエリバランシングのテスト")
    print("=" * 80)

    # テスト1: 戦略選択
    print("\n【テスト1】ヒット数に応じた戦略選択")
    print("-" * 80)
    test_hits = [0, 5, 25, 75, 200, 500, 5000, 50000]

    for hits in test_hits:
        strategy = DynamicQueryBalancer.select_strategy(hits, target_min=10, target_max=300)
        print(f"{hits:6} hits → {strategy.name:15} : {strategy.description}")

    # テスト2: クエリ構築
    print("\n【テスト2】バランスの取れたクエリ構築")
    print("-" * 80)

    test_codes = ["G11C11/00", "G11C19/00", "H10D30/00", "H10D86/00", "G09G3/00"]
    test_keywords = ["メモリ", "memory", "トランジスタ", "transistor", "IGZO", "oxide"]

    # 異なる戦略でクエリを生成
    test_strategies = ["ultra_expand", "balanced", "ultra_narrow"]

    for strategy_key in test_strategies:
        strategy = DynamicQueryBalancer.STRATEGIES[strategy_key]
        query = DynamicQueryBalancer.build_balanced_query(
            test_codes, test_keywords, strategy
        )
        print(f"\n{strategy.name}:")
        print(f"  {query[:200]}...")

    # テスト3: クエリ複雑度の計算
    print("\n【テスト3】クエリ複雑度の計算")
    print("-" * 80)

    for strategy_key in test_strategies:
        strategy = DynamicQueryBalancer.STRATEGIES[strategy_key]
        query = DynamicQueryBalancer.build_balanced_query(
            test_codes, test_keywords, strategy
        )
        complexity = DynamicQueryBalancer.calculate_query_complexity(query)

        print(f"\n{strategy.name}:")
        print(f"  AND count: {complexity['and_count']}")
        print(f"  OR count: {complexity['or_count']}")
        print(f"  括弧深度: {complexity['paren_depth']}")
        print(f"  項目数: {complexity['term_count']}")
        print(f"  複雑度スコア: {complexity['complexity_score']}")

    # テスト4: 段階的調整シミュレーション
    print("\n【テスト4】段階的調整シミュレーション")
    print("-" * 80)

    # シミュレーション: 14360 hits → 目標範囲（10-300）へ調整
    simulated_hits = [14360, 5000, 1500, 500, 200]
    print("シミュレーション: 14360 hits から 10-300 hits へ調整")

    for i, hits in enumerate(simulated_hits, 1):
        strategy = DynamicQueryBalancer.select_strategy(hits, 10, 300)
        print(f"\nIteration {i}: {hits} hits")
        print(f"  → 戦略: {strategy.name}")
        print(f"  → 分類論理: {strategy.classification_logic.value}")
        print(f"  → キーワード論理: {strategy.keyword_logic.value}")
        print(f"  → 結合論理: {strategy.cross_logic.value}")

        # 目標範囲に到達したら終了
        if 10 <= hits <= 300:
            print(f"\n✓ 目標範囲達成！")
            break

    print("\n" + "=" * 80)
    print("✓ 動的クエリバランシングのテスト完了")
    print("=" * 80)
