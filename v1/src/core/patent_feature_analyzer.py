"""
特許特徴分析モジュール
Patent Feature Analyzer Module

特許の特徴を分析し、最適な検索戦略の選択を支援します。
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class PatentFeatures:
    """特許の特徴"""
    classification_clarity: float     # 分類の明確さ (0-1)
    keyword_diversity: float          # キーワードの多様性 (0-1)
    component_complexity: float       # 構成要素の複雑さ (0-1)
    num_classifications: int          # 分類コード数
    num_keywords: int                 # キーワード数
    num_components: int               # 構成要素数
    technical_domain: Optional[str] = None  # 技術領域


class PatentFeatureAnalyzer:
    """特許の特徴を分析するクラス"""

    @staticmethod
    def analyze(classifications: List[str],
               keywords: List[str],
               components: Optional[List[Any]] = None) -> PatentFeatures:
        """
        特許の特徴を分析

        Args:
            classifications: 分類コードリスト
            keywords: キーワードリスト
            components: 構成要素リスト

        Returns:
            PatentFeatures
        """
        # 分類の明確さを評価
        classification_clarity = PatentFeatureAnalyzer._evaluate_classification_clarity(
            classifications
        )

        # キーワードの多様性を評価
        keyword_diversity = PatentFeatureAnalyzer._evaluate_keyword_diversity(
            keywords
        )

        # 構成要素の複雑さを評価
        component_complexity = PatentFeatureAnalyzer._evaluate_component_complexity(
            components
        )

        # 技術領域を推定
        technical_domain = PatentFeatureAnalyzer._estimate_technical_domain(
            classifications, keywords
        )

        return PatentFeatures(
            classification_clarity=classification_clarity,
            keyword_diversity=keyword_diversity,
            component_complexity=component_complexity,
            num_classifications=len(classifications),
            num_keywords=len(keywords),
            num_components=len(components) if components else 0,
            technical_domain=technical_domain
        )

    @staticmethod
    def _evaluate_classification_clarity(classifications: List[str]) -> float:
        """
        分類の明確さを評価

        評価基準:
        - 分類コード数が適度（3-10個）: 高スコア
        - 分類コードが階層的に関連している: 高スコア
        - 分類コードが分散している: 低スコア

        Returns:
            明確さスコア (0-1)
        """
        if not classifications:
            return 0.0

        num_codes = len(classifications)

        # 分類コード数によるスコア
        if 3 <= num_codes <= 10:
            quantity_score = 0.8
        elif 1 <= num_codes < 3:
            quantity_score = 0.5
        elif 10 < num_codes <= 20:
            quantity_score = 0.6
        else:
            quantity_score = 0.3

        # 階層的関連性によるスコア
        hierarchy_score = PatentFeatureAnalyzer._evaluate_classification_hierarchy(
            classifications
        )

        # 総合スコア
        return quantity_score * 0.6 + hierarchy_score * 0.4

    @staticmethod
    def _evaluate_classification_hierarchy(classifications: List[str]) -> float:
        """
        分類コードの階層的関連性を評価

        同じサブクラス（例: G11C, H10D）に属するコードが多いほど高スコア

        Returns:
            階層性スコア (0-1)
        """
        if len(classifications) <= 1:
            return 1.0

        # サブクラス（最初の4文字）を抽出
        subclasses = set()
        for code in classifications:
            if len(code) >= 4:
                subclasses.add(code[:4])

        # サブクラス数が少ないほど関連性が高い
        num_subclasses = len(subclasses)
        if num_subclasses == 1:
            return 1.0
        elif num_subclasses == 2:
            return 0.8
        elif num_subclasses <= 4:
            return 0.6
        else:
            return 0.3

    @staticmethod
    def _evaluate_keyword_diversity(keywords: List[str]) -> float:
        """
        キーワードの多様性を評価

        評価基準:
        - 異なる技術領域のキーワードが含まれる: 高スコア
        - 日本語と英語の両方が含まれる: 高スコア
        - キーワード数が適度: 高スコア

        Returns:
            多様性スコア (0-1)
        """
        if not keywords:
            return 0.0

        num_keywords = len(keywords)

        # キーワード数によるスコア
        if 5 <= num_keywords <= 15:
            quantity_score = 0.8
        elif 3 <= num_keywords < 5:
            quantity_score = 0.6
        elif 15 < num_keywords <= 30:
            quantity_score = 0.7
        else:
            quantity_score = 0.4

        # 言語の多様性（日本語と英語）
        has_japanese = any(PatentFeatureAnalyzer._is_japanese(kw) for kw in keywords)
        has_english = any(not PatentFeatureAnalyzer._is_japanese(kw) for kw in keywords)
        language_diversity = 1.0 if (has_japanese and has_english) else 0.5

        # 技術領域の多様性
        domain_diversity = PatentFeatureAnalyzer._evaluate_keyword_domain_diversity(
            keywords
        )

        # 総合スコア
        return quantity_score * 0.4 + language_diversity * 0.3 + domain_diversity * 0.3

    @staticmethod
    def _is_japanese(text: str) -> bool:
        """テキストに日本語が含まれているか判定"""
        return any('\u3040' <= char <= '\u30ff' or '\u4e00' <= char <= '\u9fff'
                  for char in text)

    @staticmethod
    def _evaluate_keyword_domain_diversity(keywords: List[str]) -> float:
        """
        キーワードの技術領域の多様性を評価

        Returns:
            領域多様性スコア (0-1)
        """
        domains = {
            "memory": 0,
            "semiconductor": 0,
            "circuit": 0,
            "display": 0,
            "material": 0
        }

        for kw in keywords:
            kw_lower = kw.lower()
            if any(term in kw_lower for term in ["memory", "メモリ", "storage", "記憶"]):
                domains["memory"] = 1
            elif any(term in kw_lower for term in ["semiconductor", "半導体", "oxide", "酸化物"]):
                domains["semiconductor"] = 1
            elif any(term in kw_lower for term in ["circuit", "回路", "transistor", "トランジスタ"]):
                domains["circuit"] = 1
            elif any(term in kw_lower for term in ["display", "表示", "pixel", "画素"]):
                domains["display"] = 1
            elif any(term in kw_lower for term in ["material", "材料", "film", "膜"]):
                domains["material"] = 1

        # ドメイン数が多いほど多様性が高い
        num_domains = sum(domains.values())
        if num_domains >= 3:
            return 0.9
        elif num_domains == 2:
            return 0.7
        elif num_domains == 1:
            return 0.5
        else:
            return 0.3

    @staticmethod
    def _evaluate_component_complexity(components: Optional[List[Any]]) -> float:
        """
        構成要素の複雑さを評価

        評価基準:
        - 構成要素数が多い: 高スコア
        - 構成要素間の関連が複雑: 高スコア

        Returns:
            複雑さスコア (0-1)
        """
        if not components:
            return 0.0

        num_components = len(components)

        # 構成要素数によるスコア
        if num_components >= 5:
            quantity_score = 0.9
        elif num_components >= 3:
            quantity_score = 0.7
        elif num_components >= 1:
            quantity_score = 0.5
        else:
            quantity_score = 0.0

        # 構成要素の説明の長さ（複雑さの指標）
        total_description_length = 0
        for comp in components:
            if hasattr(comp, '説明'):
                total_description_length += len(comp.説明)

        avg_description_length = total_description_length / num_components if num_components > 0 else 0

        if avg_description_length > 100:
            complexity_score = 0.9
        elif avg_description_length > 50:
            complexity_score = 0.7
        else:
            complexity_score = 0.5

        # 総合スコア
        return quantity_score * 0.6 + complexity_score * 0.4

    @staticmethod
    def _estimate_technical_domain(classifications: List[str],
                                   keywords: List[str]) -> Optional[str]:
        """
        技術領域を推定

        Args:
            classifications: 分類コードリスト
            keywords: キーワードリスト

        Returns:
            技術領域名
        """
        domain_scores = {
            "memory_storage": 0.0,
            "semiconductor_transistor": 0.0,
            "circuit_switching": 0.0,
            "display": 0.0,
            "material": 0.0
        }

        # 分類コードから推定
        for code in classifications:
            if code.startswith("G11C") or code.startswith("G11B"):
                domain_scores["memory_storage"] += 2.0
            elif code.startswith("H10D") or code.startswith("H01L"):
                domain_scores["semiconductor_transistor"] += 2.0
            elif code.startswith("H03K") or code.startswith("H03M"):
                domain_scores["circuit_switching"] += 2.0
            elif code.startswith("G09G") or code.startswith("G02F"):
                domain_scores["display"] += 2.0

        # キーワードから推定
        for kw in keywords:
            kw_lower = kw.lower()
            if any(term in kw_lower for term in ["memory", "メモリ", "storage", "記憶", "ram", "rom"]):
                domain_scores["memory_storage"] += 1.0
            if any(term in kw_lower for term in ["transistor", "トランジスタ", "tft", "semiconductor", "半導体"]):
                domain_scores["semiconductor_transistor"] += 1.0
            if any(term in kw_lower for term in ["circuit", "回路", "switching", "スイッチング"]):
                domain_scores["circuit_switching"] += 1.0
            if any(term in kw_lower for term in ["display", "表示", "pixel", "画素", "lcd", "液晶"]):
                domain_scores["display"] += 1.0
            if any(term in kw_lower for term in ["oxide", "酸化物", "film", "膜", "material", "材料"]):
                domain_scores["material"] += 1.0

        # 最もスコアの高い領域を返す
        max_domain = max(domain_scores.items(), key=lambda x: x[1])

        if max_domain[1] > 0:
            return max_domain[0]
        else:
            return None


# テスト用のコード
if __name__ == "__main__":
    print("=" * 80)
    print("特許特徴分析のテスト")
    print("=" * 80)

    # テストデータ1: メモリ関連特許
    print("\n【テスト1】メモリ関連特許の分析")
    print("-" * 80)
    test_classifications_1 = ["G11C11/00", "G11C11/56", "G11C19/00", "H10D86/00"]
    test_keywords_1 = ["メモリ", "memory", "トランジスタ", "transistor",
                      "酸化物半導体", "oxide", "容量素子", "capacitor"]

    features_1 = PatentFeatureAnalyzer.analyze(
        test_classifications_1, test_keywords_1
    )

    print(f"分類の明確さ: {features_1.classification_clarity:.2f}")
    print(f"キーワードの多様性: {features_1.keyword_diversity:.2f}")
    print(f"構成要素の複雑さ: {features_1.component_complexity:.2f}")
    print(f"分類コード数: {features_1.num_classifications}")
    print(f"キーワード数: {features_1.num_keywords}")
    print(f"技術領域: {features_1.technical_domain}")

    # テストデータ2: 表示装置関連特許
    print("\n【テスト2】表示装置関連特許の分析")
    print("-" * 80)
    test_classifications_2 = ["G09G3/00", "G09G3/20", "G09G3/36", "G02F1/133"]
    test_keywords_2 = ["液晶表示", "LCD", "pixel", "画素", "表示装置", "display"]

    features_2 = PatentFeatureAnalyzer.analyze(
        test_classifications_2, test_keywords_2
    )

    print(f"分類の明確さ: {features_2.classification_clarity:.2f}")
    print(f"キーワードの多様性: {features_2.keyword_diversity:.2f}")
    print(f"構成要素の複雑さ: {features_2.component_complexity:.2f}")
    print(f"分類コード数: {features_2.num_classifications}")
    print(f"キーワード数: {features_2.num_keywords}")
    print(f"技術領域: {features_2.technical_domain}")

    # テストデータ3: 複雑な融合技術特許
    print("\n【テスト3】複雑な融合技術特許の分析")
    print("-" * 80)
    test_classifications_3 = ["G11C11/00", "G09G3/00", "H10D86/00",
                              "H01L27/00", "G06F12/00", "G02F1/00"]
    test_keywords_3 = ["memory", "display", "transistor", "oxide", "pixel",
                      "メモリ", "表示", "トランジスタ", "酸化物", "画素",
                      "circuit", "回路", "semiconductor", "半導体"]

    features_3 = PatentFeatureAnalyzer.analyze(
        test_classifications_3, test_keywords_3
    )

    print(f"分類の明確さ: {features_3.classification_clarity:.2f}")
    print(f"キーワードの多様性: {features_3.keyword_diversity:.2f}")
    print(f"構成要素の複雑さ: {features_3.component_complexity:.2f}")
    print(f"分類コード数: {features_3.num_classifications}")
    print(f"キーワード数: {features_3.num_keywords}")
    print(f"技術領域: {features_3.technical_domain}")

    print("\n【テスト4】分類の階層性評価")
    print("-" * 80)

    # 階層的に関連（全てG11C系）
    hierarchical_codes = ["G11C11/00", "G11C11/56", "G11C19/00"]
    clarity_1 = PatentFeatureAnalyzer._evaluate_classification_clarity(hierarchical_codes)
    print(f"階層的に関連する分類: {clarity_1:.2f}")

    # 分散している
    scattered_codes = ["G11C11/00", "H10D86/00", "G09G3/00", "A01B1/00"]
    clarity_2 = PatentFeatureAnalyzer._evaluate_classification_clarity(scattered_codes)
    print(f"分散している分類: {clarity_2:.2f}")

    print("\n【テスト5】キーワードの多様性評価")
    print("-" * 80)

    # 多様（日英両方、複数領域）
    diverse_keywords = ["memory", "メモリ", "display", "表示", "transistor", "回路"]
    diversity_1 = PatentFeatureAnalyzer._evaluate_keyword_diversity(diverse_keywords)
    print(f"多様なキーワード: {diversity_1:.2f}")

    # 限定的（日本語のみ、単一領域）
    limited_keywords = ["メモリ", "記憶", "データ保持"]
    diversity_2 = PatentFeatureAnalyzer._evaluate_keyword_diversity(limited_keywords)
    print(f"限定的なキーワード: {diversity_2:.2f}")

    print("\n" + "=" * 80)
    print("✓ 特許特徴分析のテスト完了")
    print("=" * 80)
