"""
多様なAI検索戦略モジュール
Multi-Strategy Search Module

5つの異なる検索戦略を提供し、最適な戦略を自動選択します。
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class StrategyType(Enum):
    """検索戦略タイプ"""
    HIERARCHICAL_CPC = "hierarchical_cpc"          # 階層的分類中心
    KEYWORD_CENTRIC = "keyword_centric"            # キーワード中心
    HYBRID_BALANCED = "hybrid_balanced"            # ハイブリッドバランス
    COMPONENT_BASED = "component_based"            # 構成要素ベース
    SEMANTIC_SIMILARITY = "semantic"               # 意味的類似性


@dataclass
class PatentFeatures:
    """特許の特徴"""
    classification_clarity: float     # 分類の明確さ (0-1)
    keyword_diversity: float          # キーワードの多様性 (0-1)
    component_complexity: float       # 構成要素の複雑さ (0-1)
    num_classifications: int          # 分類コード数
    num_keywords: int                 # キーワード数
    num_components: int               # 構成要素数


@dataclass
class StrategyResult:
    """戦略実行結果"""
    strategy_type: StrategyType
    query_string: str
    estimated_hits: str
    confidence: float
    reasoning: str
    parameters: Dict[str, Any]


class SearchStrategy(ABC):
    """検索戦略の基底クラス"""

    def __init__(self, strategy_type: StrategyType):
        self.strategy_type = strategy_type

    @abstractmethod
    def build_query(self,
                   classifications: List[str],
                   keywords: List[str],
                   components: Optional[List[Any]] = None) -> str:
        """
        検索クエリを構築

        Args:
            classifications: 分類コードリスト
            keywords: キーワードリスト
            components: 構成要素リスト（オプション）

        Returns:
            検索クエリ文字列
        """
        pass

    @abstractmethod
    def evaluate_applicability(self, features: PatentFeatures) -> float:
        """
        この戦略の適用可能性を評価

        Args:
            features: 特許の特徴

        Returns:
            適用可能性スコア (0-1)
        """
        pass

    def execute(self,
               classifications: List[str],
               keywords: List[str],
               components: Optional[List[Any]] = None,
               features: Optional[PatentFeatures] = None) -> StrategyResult:
        """
        戦略を実行

        Args:
            classifications: 分類コードリスト
            keywords: キーワードリスト
            components: 構成要素リスト
            features: 特許の特徴

        Returns:
            StrategyResult
        """
        # クエリを構築
        query = self.build_query(classifications, keywords, components)

        # 適用可能性を評価
        confidence = 0.5  # デフォルト
        if features:
            confidence = self.evaluate_applicability(features)

        # ヒット数を推定
        estimated_hits = self._estimate_hits(query, classifications, keywords)

        # 推論を生成
        reasoning = self._generate_reasoning(confidence, estimated_hits)

        return StrategyResult(
            strategy_type=self.strategy_type,
            query_string=query,
            estimated_hits=estimated_hits,
            confidence=confidence,
            reasoning=reasoning,
            parameters=self._get_parameters()
        )

    def _estimate_hits(self, query: str, classifications: List[str],
                      keywords: List[str]) -> str:
        """ヒット数を推定（簡易版）"""
        # クエリの複雑度に基づいて推定
        and_count = query.count(" AND ")
        or_count = query.count(" OR ")

        if and_count >= 3:
            return "10-100"
        elif and_count >= 2:
            return "100-1000"
        elif and_count >= 1:
            return "1000-10000"
        else:
            return "10000+"

    def _generate_reasoning(self, confidence: float, estimated_hits: str) -> str:
        """推論を生成"""
        return f"{self.strategy_type.value}戦略を適用。" \
               f"信頼度: {confidence:.2f}、推定ヒット数: {estimated_hits}"

    @abstractmethod
    def _get_parameters(self) -> Dict[str, Any]:
        """戦略パラメータを取得"""
        pass


class HierarchicalCPCStrategy(SearchStrategy):
    """階層的分類中心戦略"""

    def __init__(self):
        super().__init__(StrategyType.HIERARCHICAL_CPC)
        self.classification_level = 2  # Subclass level (default)

    def build_query(self,
                   classifications: List[str],
                   keywords: List[str],
                   components: Optional[List[Any]] = None) -> str:
        """
        階層的分類を中心とした検索クエリを構築
        """
        # 分類コードから上位階層を抽出
        from ..core.classification_hierarchy import ClassificationHierarchy

        # Level 2 (Subclass) の分類クエリを生成
        cpc_query = ClassificationHierarchy.build_hierarchical_query(
            classifications, level=self.classification_level
        )

        # キーワードは汎用的な上位概念のみ使用（OR条件で緩く）
        generic_keywords = self._extract_generic_keywords(keywords)
        keyword_query = " OR ".join([f'"{kw}"' for kw in generic_keywords[:3]])

        # 分類中心、キーワードは補助
        if cpc_query and keyword_query:
            return f"({cpc_query}) AND ({keyword_query})"
        elif cpc_query:
            return cpc_query
        else:
            return keyword_query

    def evaluate_applicability(self, features: PatentFeatures) -> float:
        """
        分類が明確な場合に高スコア
        """
        score = features.classification_clarity * 0.7

        # 分類コード数が多い場合はボーナス
        if features.num_classifications >= 3:
            score += 0.2

        return min(score, 1.0)

    def _extract_generic_keywords(self, keywords: List[str]) -> List[str]:
        """汎用的なキーワードを抽出"""
        # 簡易版: 短いキーワードを優先（一般的に上位概念は短い）
        generic = ["memory", "メモリ", "storage", "記憶", "transistor",
                  "トランジスタ", "semiconductor", "半導体", "circuit", "回路"]
        return [kw for kw in keywords if kw in generic]

    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "classification_level": self.classification_level,
            "keyword_usage": "generic_only",
            "cross_logic": "AND"
        }


class KeywordCentricStrategy(SearchStrategy):
    """キーワード中心戦略"""

    def __init__(self):
        super().__init__(StrategyType.KEYWORD_CENTRIC)
        self.keyword_level = 2  # Medium level keywords

    def build_query(self,
                   classifications: List[str],
                   keywords: List[str],
                   components: Optional[List[Any]] = None) -> str:
        """
        キーワードを中心とした検索クエリを構築
        """
        # キーワードを階層的に選択
        from ..core.hierarchical_keywords import HierarchicalKeywordSystem

        # 技術領域を推定
        domain_scores = HierarchicalKeywordSystem.get_domain_suggestions(keywords)
        top_domains = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)[:3]

        # Level 2 (Medium) のキーワードを取得
        expanded_keywords = HierarchicalKeywordSystem.get_keywords_by_level(
            level=self.keyword_level,
            domains=[domain for domain, _ in top_domains]
        )

        # キーワードグループを構築（上位5個、各グループはOR）
        keyword_groups = self._group_keywords(keywords + expanded_keywords[:10])

        # 各グループをANDで結合
        keyword_query_parts = []
        for group in keyword_groups[:3]:  # 最大3グループ
            group_query = " OR ".join([f'"{kw}"' for kw in group])
            keyword_query_parts.append(f"({group_query})")

        keyword_query = " AND ".join(keyword_query_parts)

        # 分類コードは広い範囲で補助的に使用
        from ..core.classification_hierarchy import ClassificationHierarchy
        cpc_query = ClassificationHierarchy.build_hierarchical_query(
            classifications, level=1  # Class level (広い)
        )

        # キーワード主体、分類は補助
        if keyword_query and cpc_query:
            return f"({keyword_query}) AND ({cpc_query})"
        elif keyword_query:
            return keyword_query
        else:
            return cpc_query

    def evaluate_applicability(self, features: PatentFeatures) -> float:
        """
        キーワードが多様な場合に高スコア
        """
        score = features.keyword_diversity * 0.7

        # キーワード数が多い場合はボーナス
        if features.num_keywords >= 5:
            score += 0.2

        return min(score, 1.0)

    def _group_keywords(self, keywords: List[str]) -> List[List[str]]:
        """キーワードを意味的にグループ化（簡易版）"""
        # 技術領域ごとにグループ化
        groups = {
            "memory": [],
            "semiconductor": [],
            "circuit": []
        }

        for kw in keywords:
            kw_lower = kw.lower()
            if any(term in kw_lower for term in ["memory", "メモリ", "storage", "記憶"]):
                groups["memory"].append(kw)
            elif any(term in kw_lower for term in ["semiconductor", "半導体", "oxide", "酸化物"]):
                groups["semiconductor"].append(kw)
            elif any(term in kw_lower for term in ["circuit", "回路", "transistor", "トランジスタ"]):
                groups["circuit"].append(kw)

        # 空でないグループのみ返す
        return [g for g in groups.values() if g]

    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "keyword_level": self.keyword_level,
            "classification_level": 1,  # Broad
            "cross_logic": "AND"
        }


class HybridBalancedStrategy(SearchStrategy):
    """ハイブリッドバランス戦略"""

    def __init__(self):
        super().__init__(StrategyType.HYBRID_BALANCED)
        self.classification_level = 2
        self.keyword_level = 2

    def build_query(self,
                   classifications: List[str],
                   keywords: List[str],
                   components: Optional[List[Any]] = None) -> str:
        """
        分類とキーワードをバランスよく組み合わせた検索クエリを構築
        """
        from ..core.classification_hierarchy import ClassificationHierarchy
        from ..core.hierarchical_keywords import HierarchicalKeywordSystem

        # 中階層の分類コードクエリ
        cpc_query = ClassificationHierarchy.build_hierarchical_query(
            classifications, level=self.classification_level
        )

        # 中位概念のキーワード
        domain_scores = HierarchicalKeywordSystem.get_domain_suggestions(keywords)
        top_domains = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)[:2]

        expanded_keywords = HierarchicalKeywordSystem.get_keywords_by_level(
            level=self.keyword_level,
            domains=[domain for domain, _ in top_domains]
        )

        # キーワードクエリ（OR条件）
        selected_keywords = (keywords + expanded_keywords)[:8]
        keyword_query = " OR ".join([f'"{kw}"' for kw in selected_keywords])

        # 分類 AND キーワード（バランス型）
        if cpc_query and keyword_query:
            return f"({cpc_query}) AND ({keyword_query})"
        elif cpc_query:
            return cpc_query
        else:
            return keyword_query

    def evaluate_applicability(self, features: PatentFeatures) -> float:
        """
        常に中程度のスコア（バランス型なので汎用的）
        """
        # 分類とキーワードの両方が適度にある場合に高スコア
        balance_score = min(
            features.classification_clarity * 0.5 +
            features.keyword_diversity * 0.5,
            1.0
        )

        # バランス型は常にベースライン0.6以上
        return max(balance_score, 0.6)

    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "classification_level": self.classification_level,
            "keyword_level": self.keyword_level,
            "cross_logic": "AND",
            "balance_weight": 0.5
        }


class ComponentBasedStrategy(SearchStrategy):
    """構成要素ベース戦略"""

    def __init__(self):
        super().__init__(StrategyType.COMPONENT_BASED)

    def build_query(self,
                   classifications: List[str],
                   keywords: List[str],
                   components: Optional[List[Any]] = None) -> str:
        """
        構成要素ごとに検索クエリを構築し、OR結合
        """
        if not components:
            # 構成要素がない場合はハイブリッド戦略にフォールバック
            return HybridBalancedStrategy().build_query(
                classifications, keywords, components
            )

        from ..core.classification_hierarchy import ClassificationHierarchy

        component_queries = []

        # 各構成要素ごとに検索式を作成
        for comp in components[:5]:  # 最大5構成要素
            comp_classifications = []
            comp_keywords = []

            # 構成要素の分類コードを取得
            if hasattr(comp, 'CPC分類'):
                comp_classifications = comp.CPC分類 or []

            # 構成要素の特徴的なキーワードを抽出
            if hasattr(comp, '説明'):
                comp_keywords = self._extract_keywords_from_description(comp.説明)

            # この構成要素の検索式
            if comp_classifications and comp_keywords:
                cpc_query = ClassificationHierarchy.build_hierarchical_query(
                    comp_classifications, level=3  # Maingroup level
                )
                kw_query = " OR ".join([f'"{kw}"' for kw in comp_keywords[:3]])
                comp_query = f"(({cpc_query}) AND ({kw_query}))"
                component_queries.append(comp_query)

        # 構成要素クエリをOR結合
        if component_queries:
            return " OR ".join(component_queries)
        else:
            # フォールバック
            return HybridBalancedStrategy().build_query(
                classifications, keywords, components
            )

    def evaluate_applicability(self, features: PatentFeatures) -> float:
        """
        構成要素が複雑な場合に高スコア
        """
        score = features.component_complexity * 0.7

        # 構成要素数が多い場合はボーナス
        if features.num_components >= 3:
            score += 0.2

        return min(score, 1.0)

    def _extract_keywords_from_description(self, description: str) -> List[str]:
        """説明文から特徴的なキーワードを抽出（簡易版）"""
        # 簡易版: 技術用語のみを抽出
        technical_terms = [
            "トランジスタ", "transistor", "容量", "capacitor", "メモリ",
            "memory", "酸化物", "oxide", "半導体", "semiconductor",
            "電極", "electrode", "配線", "wiring", "データ", "data"
        ]

        keywords = []
        for term in technical_terms:
            if term in description:
                keywords.append(term)

        return keywords[:5]  # 最大5個

    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "classification_level": 3,  # Maingroup
            "max_components": 5,
            "cross_logic": "OR"
        }


class SemanticSimilarityStrategy(SearchStrategy):
    """意味的類似性戦略"""

    def __init__(self):
        super().__init__(StrategyType.SEMANTIC_SIMILARITY)

    def build_query(self,
                   classifications: List[str],
                   keywords: List[str],
                   components: Optional[List[Any]] = None) -> str:
        """
        意味的に類似したキーワードを展開して検索クエリを構築
        """
        # キーワードの意味的な拡張
        expanded_keywords = self._semantic_expand(keywords)

        # 上位概念、同義語、類義語を含む
        semantic_groups = self._group_by_semantics(expanded_keywords)

        # 各意味グループをOR結合
        group_queries = []
        for group in semantic_groups[:3]:  # 最大3グループ
            group_query = " OR ".join([f'"{kw}"' for kw in group])
            group_queries.append(f"({group_query})")

        keyword_query = " AND ".join(group_queries) if group_queries else ""

        # 分類は広範囲で補助的に
        from ..core.classification_hierarchy import ClassificationHierarchy
        cpc_query = ClassificationHierarchy.build_hierarchical_query(
            classifications, level=1  # Class level
        )

        if keyword_query and cpc_query:
            return f"({keyword_query}) AND ({cpc_query})"
        elif keyword_query:
            return keyword_query
        else:
            return cpc_query

    def evaluate_applicability(self, features: PatentFeatures) -> float:
        """
        キーワードが不明確な場合、または他の戦略が失敗した場合に高スコア
        """
        # 分類が不明確な場合に高スコア
        score = (1.0 - features.classification_clarity) * 0.5

        # キーワードが多様な場合にも高スコア
        score += features.keyword_diversity * 0.5

        return min(score, 1.0)

    def _semantic_expand(self, keywords: List[str]) -> List[str]:
        """意味的にキーワードを拡張（簡易版）"""
        expansion_dict = {
            "メモリ": ["memory", "storage", "記憶", "保持", "retention"],
            "memory": ["メモリ", "storage", "記憶", "data retention"],
            "トランジスタ": ["transistor", "TFT", "switching element", "スイッチング素子"],
            "transistor": ["トランジスタ", "TFT", "switching element"],
            "半導体": ["semiconductor", "oxide", "酸化物", "film", "膜"],
            "semiconductor": ["半導体", "oxide", "film"],
            "回路": ["circuit", "device", "デバイス", "system", "システム"],
            "circuit": ["回路", "device", "system"],
        }

        expanded = set(keywords)
        for kw in keywords:
            if kw in expansion_dict:
                expanded.update(expansion_dict[kw])

        return list(expanded)

    def _group_by_semantics(self, keywords: List[str]) -> List[List[str]]:
        """意味的にグループ化"""
        # 簡易版: 技術領域でグループ化
        groups = {
            "storage": [],
            "device": [],
            "material": []
        }

        for kw in keywords:
            kw_lower = kw.lower()
            if any(term in kw_lower for term in ["memory", "メモリ", "storage", "記憶", "retention", "保持"]):
                groups["storage"].append(kw)
            elif any(term in kw_lower for term in ["transistor", "トランジスタ", "circuit", "回路", "device"]):
                groups["device"].append(kw)
            elif any(term in kw_lower for term in ["semiconductor", "半導体", "oxide", "酸化物", "film", "膜"]):
                groups["material"].append(kw)

        return [g for g in groups.values() if g]

    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "expansion_level": "high",
            "classification_level": 1,  # Broad
            "semantic_grouping": True
        }


class MultiStrategySelector:
    """複数戦略を試行し、最適な戦略を選択"""

    def __init__(self):
        self.strategies = {
            StrategyType.HIERARCHICAL_CPC: HierarchicalCPCStrategy(),
            StrategyType.KEYWORD_CENTRIC: KeywordCentricStrategy(),
            StrategyType.HYBRID_BALANCED: HybridBalancedStrategy(),
            StrategyType.COMPONENT_BASED: ComponentBasedStrategy(),
            StrategyType.SEMANTIC_SIMILARITY: SemanticSimilarityStrategy()
        }

    def execute_all_strategies(self,
                               classifications: List[str],
                               keywords: List[str],
                               components: Optional[List[Any]] = None,
                               features: Optional[PatentFeatures] = None) -> List[StrategyResult]:
        """
        全戦略を並列実行

        Args:
            classifications: 分類コードリスト
            keywords: キーワードリスト
            components: 構成要素リスト
            features: 特許の特徴

        Returns:
            全戦略の実行結果
        """
        results = []

        for strategy_type, strategy in self.strategies.items():
            try:
                result = strategy.execute(
                    classifications, keywords, components, features
                )
                results.append(result)
                logger.info(f"{strategy_type.value}: confidence={result.confidence:.2f}")
            except Exception as e:
                logger.error(f"Error in {strategy_type.value}: {e}")

        # 信頼度でソート
        results.sort(key=lambda r: r.confidence, reverse=True)

        return results

    def select_best_strategy(self,
                            classifications: List[str],
                            keywords: List[str],
                            components: Optional[List[Any]] = None,
                            features: Optional[PatentFeatures] = None,
                            search_history: Optional[Dict] = None) -> StrategyResult:
        """
        最適な戦略を選択して実行

        Args:
            classifications: 分類コードリスト
            keywords: キーワードリスト
            components: 構成要素リスト
            features: 特許の特徴
            search_history: 過去の検索履歴

        Returns:
            最適な戦略の実行結果
        """
        # 全戦略を実行
        results = self.execute_all_strategies(
            classifications, keywords, components, features
        )

        # 検索履歴がある場合は、過去の成功率を反映
        if search_history:
            results = self._adjust_by_history(results, search_history)

        # 最も信頼度の高い戦略を選択
        best_result = results[0] if results else None

        if best_result:
            logger.info(f"Selected strategy: {best_result.strategy_type.value} "
                       f"(confidence: {best_result.confidence:.2f})")

        return best_result

    def _adjust_by_history(self,
                          results: List[StrategyResult],
                          search_history: Dict) -> List[StrategyResult]:
        """検索履歴に基づいて信頼度を調整"""
        # 各戦略の過去の成功率を取得
        for result in results:
            strategy_name = result.strategy_type.value
            historical_success = search_history.get(strategy_name, {}).get("success_rate", 0.5)

            # 現在の信頼度と過去の成功率を加重平均
            adjusted_confidence = result.confidence * 0.7 + historical_success * 0.3
            result.confidence = adjusted_confidence

        # 再ソート
        results.sort(key=lambda r: r.confidence, reverse=True)

        return results


# テスト用のコード
if __name__ == "__main__":
    print("=" * 80)
    print("多様なAI検索戦略のテスト")
    print("=" * 80)

    # テストデータ
    test_classifications = ["G11C11/00", "G11C19/00", "H10D30/00", "H10D86/00"]
    test_keywords = ["メモリ", "トランジスタ", "酸化物半導体", "容量素子"]

    # 特許の特徴
    test_features = PatentFeatures(
        classification_clarity=0.8,
        keyword_diversity=0.6,
        component_complexity=0.7,
        num_classifications=4,
        num_keywords=4,
        num_components=3
    )

    # 戦略セレクターを作成
    selector = MultiStrategySelector()

    print("\n【テスト1】全戦略の並列実行")
    print("-" * 80)
    results = selector.execute_all_strategies(
        test_classifications, test_keywords, features=test_features
    )

    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result.strategy_type.value}")
        print(f"   信頼度: {result.confidence:.2f}")
        print(f"   推定ヒット数: {result.estimated_hits}")
        print(f"   クエリ (前半100文字): {result.query_string[:100]}...")

    print("\n【テスト2】最適戦略の自動選択")
    print("-" * 80)
    best_result = selector.select_best_strategy(
        test_classifications, test_keywords, features=test_features
    )

    print(f"\n選択された戦略: {best_result.strategy_type.value}")
    print(f"信頼度: {best_result.confidence:.2f}")
    print(f"推定ヒット数: {best_result.estimated_hits}")
    print(f"\nクエリ:")
    print(best_result.query_string)

    print("\n" + "=" * 80)
    print("✓ 多様なAI検索戦略のテスト完了")
    print("=" * 80)
