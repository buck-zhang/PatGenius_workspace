"""
特許検索エンジン
Patent Search Engine with Dynamic Range Adjustment

構成要件に基づく検索式作成と、ヒット件数に応じた動的な範囲調整を行います。
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import requests
import time

from .patent_component_analyzer import (
    ComponentElement, ComponentKeywords, ComponentClassification,
    SearchRangeAdjustment
)
from .ai_query_generator import AIQueryGenerator
from .classification_hierarchy import ClassificationHierarchy, HybridClassificationStrategy, CPCLateralExpansion
from .keyword_translator import KeywordTranslator


logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class SearchQuery:
    """検索式"""
    query_string: str  # 検索クエリ文字列
    cpc_codes: List[str]  # 使用するCPC分類コード
    keywords: List[str]  # 使用するキーワード
    component_queries: List[Dict[str, Any]]  # 各構成要素のクエリ


@dataclass
class SearchResult:
    """検索結果"""
    query: SearchQuery
    total_hits: int
    patents: List[Dict[str, Any]]
    cpc_ranking: List[Dict[str, Any]]
    adjustment_history: List[str]  # 調整履歴（文字列形式）
    iteration_details: List[Dict[str, Any]]  # 各イテレーションの詳細情報


# ============================================================================
# Search Query Builder
# ============================================================================

class SearchQueryBuilder:
    """検索式作成クラス"""

    def __init__(self, recall_mode: bool = False):
        """
        初期化

        Args:
            recall_mode: リコール重視モード（Trueの場合、OR条件で検索範囲を拡大）
        """
        self.recall_mode = recall_mode

    @staticmethod
    def build_hierarchical_wildcard_query(cpc_codes: List[str],
                                         max_codes: int = 15) -> str:
        """
        階層的検索クエリを生成（ワイルドカード展開）

        Google Patents構文ルール:
        - サブクラスレベル (例: G11C, H10D): cpc=G11C (小文字、引用符なし)
        - 特定分類コード (例: G11C11/00): CPC="G11C11/00" (大文字、引用符あり)

        例: G11C11/56 → cpc=G11C, CPC="G11C11/56"

        Args:
            cpc_codes: CPCコードのリスト
            max_codes: 使用する最大コード数

        Returns:
            階層的ワイルドカード検索式
        """
        hierarchical_codes = []

        # CPCコードを階層ごとに展開（より多くのCPCを使用）
        for cpc in cpc_codes[:10]:  # 上位10個のCPCコード（FI廃止により枠が増える）
            cleaned_cpc = cpc.replace(" ", "")

            # 主分類 (例: H03K)
            if '/' in cleaned_cpc:
                main_cpc = cleaned_cpc.split('/')[0]
                # サブクラスレベル: 小文字cpc=、引用符なし
                # 例: H10D → cpc=H10D
                if len(main_cpc) >= 4:  # サブクラスレベル (例: G11C, H10D)
                    hierarchical_codes.append(f'cpc={main_cpc}')

            # 完全一致: 大文字CPC=、引用符あり
            hierarchical_codes.append(f'CPC="{cleaned_cpc}"')

        # 重複を除去
        unique_codes = list(dict.fromkeys(hierarchical_codes))  # 順序を保持して重複除去

        return " OR ".join(unique_codes[:max_codes])

    @staticmethod
    def _build_classification_codes_query(cpc_codes: List[str],
                                          max_codes: int = 15, hierarchy_level: int = None,
                                          use_wildcard_expansion: bool = False,
                                          enable_lateral_expansion: bool = False) -> str:
        """
        CPCコードをOR条件で結合した検索式を生成（階層的検索 + 横方向展開対応）

        Args:
            cpc_codes: CPCコードのリスト
            max_codes: 使用する最大コード数
            hierarchy_level: 階層レベル (0=section, 1=class, 2=subclass, 3=maingroup, 4=full, None=従来方式)
            use_wildcard_expansion: ワイルドカード展開を使用するか（リコールモード推奨）
            enable_lateral_expansion: 横方向展開を有効化（関連技術領域のCPCコードを追加、リコールモード推奨）

        Returns:
            分類コードの検索式（例: "CPC=\"H10D30/00\" OR CPC=\"H10D86/00\" OR ..."）
        """
        code_parts = []

        # 横方向展開（関連技術領域のCPCを追加）
        if enable_lateral_expansion and cpc_codes:
            logger.info(f"Applying lateral expansion to {len(cpc_codes)} CPC codes")
            expanded_cpc = CPCLateralExpansion.expand_cpc_codes(cpc_codes, max_expansion=1)
            logger.info(f"Expanded to {len(expanded_cpc)} CPC codes (added {len(expanded_cpc) - len(cpc_codes)} related codes)")
            cpc_codes = expanded_cpc

        # ワイルドカード展開モード（リコールモード時に推奨）
        if use_wildcard_expansion:
            return SearchQueryBuilder.build_hierarchical_wildcard_query(
                cpc_codes, max_codes=15
            )

        # 階層的検索が指定されている場合
        if hierarchy_level is not None:
            # CPCコードの階層的クエリ生成
            if cpc_codes:
                cpc_query = ClassificationHierarchy.build_hierarchical_query(
                    cpc_codes, level=hierarchy_level
                )
                if cpc_query:
                    code_parts.append(cpc_query)

            return " OR ".join(code_parts) if code_parts else ""

        # 従来方式（hierarchy_level=Noneの場合）
        # CPCコードを使用（max_codes個まで）
        cpc_count = min(len(cpc_codes), max_codes)

        # CPCコードを追加（スペース除去のみ）
        for cpc in cpc_codes[:cpc_count]:
            cleaned_cpc = cpc.replace(" ", "")
            code_parts.append(f'CPC="{cleaned_cpc}"')

        return " OR ".join(code_parts) if code_parts else ""

    def build_search_query(self,
                          components: List[ComponentElement],
                          keywords_list: List[ComponentKeywords],
                          classifications_list: List[ComponentClassification],
                          range_adjustment: SearchRangeAdjustment = SearchRangeAdjustment.MAINTAIN,
                          keyword_expansion_level: int = 0,
                          importance_threshold: float = 0.0,
                          hierarchy_level: int = None) -> SearchQuery:
        """
        検索式を作成

        Args:
            components: 構成要素リスト
            keywords_list: キーワードリスト
            classifications_list: 分類コードリスト
            range_adjustment: 検索範囲調整
            keyword_expansion_level: キーワード拡張レベル（0:基本、1:中、2:高）
            importance_threshold: 重要度閾値（この値以上の構成要素のみ検索に使用）
            hierarchy_level: 分類コード階層レベル（0=section, 1=class, 2=subclass, 3=maingroup, 4=full, None=従来方式）

        Returns:
            SearchQuery
        """
        logger.info(f"Building search query with adjustment: {range_adjustment.value}, importance_threshold: {importance_threshold}, hierarchy_level: {hierarchy_level}")

        component_queries = []
        all_cpc_codes = []
        included_count = 0
        excluded_count = 0

        # 各構成要素のクエリを作成
        for comp, keywords, classification in zip(components, keywords_list, classifications_list):
            # 重要度閾値でフィルタリング
            if comp.構成要素の重要度 < importance_threshold:
                logger.info(f"Excluding component {comp.構成要素番号} (importance: {comp.構成要素の重要度} < threshold: {importance_threshold})")
                excluded_count += 1
                continue

            included_count += 1
            comp_query = self._build_component_query(
                comp, keywords, classification,
                range_adjustment, keyword_expansion_level, hierarchy_level
            )
            component_queries.append(comp_query)

            # CPCコードを収集
            all_cpc_codes.extend(classification.get_all_cpc())

        logger.info(f"Included components: {included_count}, Excluded components: {excluded_count}")

        # 全体のクエリ文字列を作成
        query_string = self._combine_component_queries(component_queries, range_adjustment, hierarchy_level)

        # 重複を除去
        unique_cpc_codes = list(set(all_cpc_codes))

        # 使用するキーワードを収集
        all_keywords = []
        for keywords in keywords_list:
            all_keywords.extend(self._select_keywords(keywords, keyword_expansion_level))

        search_query = SearchQuery(
            query_string=query_string,
            cpc_codes=unique_cpc_codes,
            keywords=list(set(all_keywords)),
            component_queries=component_queries
        )

        return search_query

    def _build_component_query(self,
                               component: ComponentElement,
                               keywords: ComponentKeywords,
                               classification: ComponentClassification,
                               range_adjustment: SearchRangeAdjustment,
                               keyword_expansion_level: int,
                               hierarchy_level: int = None) -> Dict[str, Any]:
        """
        1つの構成要素のクエリデータを作成（検索式構築用）

        Args:
            component: 構成要素
            keywords: キーワード情報
            classification: 分類コード情報
            range_adjustment: 検索範囲調整
            keyword_expansion_level: キーワード拡張レベル
            hierarchy_level: 分類コード階層レベル（None=従来方式）

        Returns:
            構成要素ごとのクエリデータ辞書
        """

        # 範囲調整に応じてCPCコードを選択
        if range_adjustment == SearchRangeAdjustment.NARROW:
            # 縮小：検索範囲縮小最終CPCを使用
            selected_cpc = classification.get_narrowed_cpc()
            if not selected_cpc:
                selected_cpc = classification.get_primary_cpc()
        elif range_adjustment == SearchRangeAdjustment.EXPAND:
            # 拡大：検索範囲拡大最終CPCも含む
            selected_cpc = classification.get_expanded_cpc()
        else:
            # 維持：一次特定最終CPCのみ
            selected_cpc = classification.get_primary_cpc()

        # CPCがない場合はIPCを使用
        if not selected_cpc:
            selected_cpc = classification.IPC分類[:3]

        # キーワードを選択
        selected_keywords = self._select_keywords(keywords, keyword_expansion_level)

        return {
            "component_id": component.構成要素番号,
            "cpc_codes": selected_cpc,
            "keywords": selected_keywords,
            "importance": component.構成要素の重要度
        }

    def _select_keywords(self, keywords: ComponentKeywords,
                        expansion_level: int) -> List[str]:
        """
        キーワード拡張レベルに応じてキーワードを選択

        Args:
            keywords: ComponentKeywords
            expansion_level: -1=範囲縮小、0=一次検索、1=範囲拡大、2=全てのキーワード

        Returns:
            選択されたキーワードリスト
        """
        if expansion_level == -1:
            # 縮小：範囲縮小キーワード
            selected = keywords.get_narrowed_keywords()
        elif expansion_level == 0:
            # 基本：一次検索キーワードのみ
            selected = keywords.get_primary_keywords()
        elif expansion_level == 1:
            # 拡大：範囲拡大キーワードも含む
            selected = keywords.get_expanded_keywords()
        else:  # expansion_level >= 2
            # 全て：全てのキーワードを含む
            selected = keywords.get_all_keywords()

        return selected

    def _select_components_for_query(self,
                                      sorted_queries: List[Dict[str, Any]],
                                      range_adjustment: SearchRangeAdjustment) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        検索式に使用する構成要素を選択（統一ロジック）

        検索範囲調整に応じて、適応的に構成要素数と重要度閾値を決定:
        - NARROW（縮小）: 上位3個のみ、重要度≥0.8
        - MAINTAIN（維持）: 上位5個まで、重要度≥0.7
        - EXPAND（拡大）: 上位8個まで、重要度≥0.5

        Args:
            sorted_queries: 重要度でソート済みの構成要素クエリリスト
            range_adjustment: 検索範囲調整モード

        Returns:
            (major_components, other_components): 主要構成要素と他の構成要素
        """
        if not sorted_queries:
            return [], []

        # 検索範囲調整に応じてパラメータを決定
        if range_adjustment == SearchRangeAdjustment.NARROW:
            # 縮小: 上位3個、重要度≥0.8（精度重視）
            max_components = 3
            importance_threshold = 0.8
            mode_desc = "NARROW (precision-focused)"
        elif range_adjustment == SearchRangeAdjustment.EXPAND:
            # 拡大: 上位5個、重要度≥0.5（リコール重視）
            max_components = 5
            importance_threshold = 0.5
            mode_desc = "EXPAND (recall-focused)"
        else:
            # 維持: 上位5個、重要度≥0.7（バランス型）
            max_components = 5
            importance_threshold = 0.7
            mode_desc = "MAINTAIN (balanced)"

        logger.info(f"Component selection mode: {mode_desc}")
        logger.info(f"  Max components: {max_components}, Importance threshold: {importance_threshold}")

        # 重要度閾値でフィルタリング + 個数制限
        filtered_queries = [
            q for q in sorted_queries
            if q["importance"] >= importance_threshold
        ][:max_components]

        logger.info(f"Total components: {len(sorted_queries)} → Selected: {len(filtered_queries)}")

        # 主要構成要素（重要度≥0.9）を軸として特定
        major_components = [q for q in filtered_queries if q["importance"] >= 0.9]
        other_components = [q for q in filtered_queries if q["importance"] < 0.9]

        logger.info(f"Major components (importance >= 0.9): {len(major_components)}")
        logger.info(f"Other components (importance < 0.9): {len(other_components)}")

        # 主要構成要素がない場合は最高重要度の構成要素を使用
        if not major_components and filtered_queries:
            logger.warning("No major components found (importance >= 0.9). Using top component.")
            major_components = [filtered_queries[0]]
            other_components = filtered_queries[1:]

        return major_components, other_components

    def _combine_component_queries(self,
                                  component_queries: List[Dict[str, Any]],
                                  range_adjustment: SearchRangeAdjustment,
                                  hierarchy_level: int = None) -> str:
        """
        統一検索式構築ロジック

        新ロジック:
        1. 検索範囲調整に応じて構成要素を適応的に選択
           - NARROW: 3個（重要度≥0.8）
           - MAINTAIN: 5個（重要度≥0.7）
           - EXPAND: 8個（重要度≥0.5）
        2. 主要構成要素（重要度≥0.9）を軸とした検索式作成
        3. 軸構成要素の分類コード AND 他構成要素のキーワード
        4. 全ての軸クエリをOR結合

        Args:
            component_queries: 各構成要素のクエリデータリスト
            range_adjustment: 検索範囲調整
            hierarchy_level: 分類コード階層レベル（None=従来方式）

        Returns:
            最終的な検索クエリ文字列
        """

        if not component_queries:
            return ""

        # 重要度でソート（降順）
        sorted_queries = sorted(
            component_queries,
            key=lambda x: x["importance"],
            reverse=True
        )

        # 統一ロジックで構成要素を選択
        major_components, other_components = self._select_components_for_query(
            sorted_queries, range_adjustment
        )

        filtered_queries = major_components + other_components

        # 各主要構成要素ごとに検索式を作成
        query_parts = []

        for major_comp in major_components:
            major_comp_id = major_comp["component_id"]
            logger.info(f"Building query for major component (axis): {major_comp_id}")

            # 主要構成要素の分類コード（CPC）
            major_cpc_codes = major_comp.get("cpc_codes", [])

            if not major_cpc_codes:
                logger.warning(f"No classification codes for major component {major_comp_id}, skipping")
                continue

            # 範囲調整に応じてコード数を調整
            # CPC-only: より多くのコードを使用可能
            if range_adjustment == SearchRangeAdjustment.EXPAND:
                # 拡大：最大15個（より広範囲に検索）
                max_cpc = 15
            elif range_adjustment == SearchRangeAdjustment.NARROW:
                # 縮小：少数のコードのみ（5個）
                max_cpc = 5
            else:
                # 通常：10個
                max_cpc = 10

            # リコールモード時はワイルドカード展開と横方向展開を使用
            use_wildcard = self.recall_mode and range_adjustment == SearchRangeAdjustment.EXPAND
            use_lateral = self.recall_mode  # リコールモード時は常に横方向展開を有効化

            classification_part = self._build_classification_codes_query(
                major_cpc_codes[:max_cpc],
                max_codes=max_cpc,
                hierarchy_level=hierarchy_level,
                use_wildcard_expansion=use_wildcard,
                enable_lateral_expansion=use_lateral
            )

            # キーワード（他の構成要素から - 軸構成要素自身のキーワードは除外）
            keyword_parts = []

            # 軸構成要素以外の全ての構成要素からキーワードを収集
            # 仕様: 軸構成要素のキーワードは除外する
            components_for_keywords = [
                comp for comp in filtered_queries
                if comp["component_id"] != major_comp_id
            ]

            logger.info(f"Using keywords from {len(components_for_keywords)} components (excluding axis component {major_comp_id})")

            for comp in components_for_keywords:
                comp_keywords = comp.get("keywords", [])

                if not comp_keywords:
                    continue

                # 範囲調整に応じてキーワード数を調整
                # ユーザー要件: OR条件で繋ぐキーワードを5以内にする
                # バイリンガルキーワード（日本語+英語）を使用
                if range_adjustment == SearchRangeAdjustment.EXPAND:
                    # 拡大：最大5個のキーワードをバイリンガル展開
                    selected_keywords = comp_keywords[:5]
                    keyword_or_part = KeywordTranslator.build_bilingual_keyword_query(
                        selected_keywords, max_keywords=5, max_translations_per_keyword=2
                    )
                    if keyword_or_part:
                        keyword_parts.append(f"({keyword_or_part})")
                elif range_adjustment == SearchRangeAdjustment.NARROW:
                    # 縮小：少数のキーワードのみ（2個）、翻訳も少なめ
                    selected_keywords = comp_keywords[:2]
                    keyword_or_part = KeywordTranslator.build_bilingual_keyword_query(
                        selected_keywords, max_keywords=2, max_translations_per_keyword=1
                    )
                    if keyword_or_part:
                        keyword_parts.append(f"({keyword_or_part})")
                else:
                    # 通常：最大5個のキーワード、標準的な翻訳数
                    selected_keywords = comp_keywords[:5]
                    keyword_or_part = KeywordTranslator.build_bilingual_keyword_query(
                        selected_keywords, max_keywords=5, max_translations_per_keyword=2
                    )
                    if keyword_or_part:
                        keyword_parts.append(f"({keyword_or_part})")

            # 主要構成要素の分類コード AND/OR 他の構成要素のキーワード
            if classification_part and keyword_parts:
                # リコールモード時はOR条件、通常モード時はAND条件
                if self.recall_mode:
                    # リコールモード: (CPC) AND (keyword1 OR keyword2 OR ...)
                    all_keyword_or = " OR ".join(keyword_parts)
                    query_part = f"(({classification_part}) AND ({all_keyword_or}))"
                else:
                    # 通常モード: (CPC) AND keyword1 AND keyword2 AND ...
                    all_keyword_and = " AND ".join(keyword_parts)
                    query_part = f"(({classification_part}) AND {all_keyword_and})"
                query_parts.append(query_part)
            elif classification_part and not keyword_parts:
                # キーワードがない場合は分類コードのみ
                query_part = f"({classification_part})"
                query_parts.append(query_part)

        # 全ての主要構成要素の検索式をOR条件で結合
        if query_parts:
            final_query = " OR ".join(query_parts)
        else:
            # フォールバック：主要構成要素が使えない場合
            logger.warning("No valid query parts created. Using fallback method.")

            # 最上位の構成要素の分類コードとキーワードのみ使用
            if filtered_queries:
                top_comp = filtered_queries[0]
                top_cpc = top_comp.get("cpc_codes", [])
                top_keywords = top_comp.get("keywords", [])

                if top_cpc and top_keywords:
                    classification_part = self._build_classification_codes_query(
                        top_cpc[:15], max_codes=15, hierarchy_level=hierarchy_level,
                        enable_lateral_expansion=self.recall_mode
                    )
                    keyword_part = " OR ".join([f'"{kw}"' for kw in top_keywords[:10]])
                    final_query = f"(({classification_part}) AND ({keyword_part}))"
                elif top_cpc:
                    final_query = self._build_classification_codes_query(
                        top_cpc[:15], max_codes=15, hierarchy_level=hierarchy_level,
                        enable_lateral_expansion=self.recall_mode
                    )
                else:
                    final_query = ""
            else:
                final_query = ""

        logger.info(f"Generated query length: {len(final_query)} characters")
        logger.info(f"Number of OR-combined major component queries: {len(query_parts)}")

        return final_query


# ============================================================================
# Patent Search Engine
# ============================================================================

class PatentSearchEngine:
    """特許検索エンジン（動的範囲調整機能付き）"""

    def __init__(self, google_patents_api_url: str,
                 target_min_hits: int = 10,
                 target_max_hits: int = 50,
                 max_iterations: int = 12,
                 recall_mode: bool = False,
                 ai_client = None,
                 max_ai_attempts: int = 10):
        """
        初期化

        Args:
            google_patents_api_url: Google Patents検索APIのURL
            target_min_hits: 目標最小ヒット件数（デフォルト: 10）
            target_max_hits: 目標最大ヒット件数（デフォルト: 50）
            max_iterations: 最大反復回数（デフォルト: 12）
            recall_mode: リコール重視モード（Trueの場合、再現率重視で検索範囲を拡大）
            ai_client: AI client for query generation after manual iterations (optional)
            max_ai_attempts: AI生成クエリの最大試行回数（デフォルト: 10）
        """
        self.google_patents_api_url = google_patents_api_url
        self.recall_mode = recall_mode
        self.ai_client = ai_client
        self.max_ai_attempts = max_ai_attempts

        # パラメータをそのまま使用（recall_modeでも上書きしない）
        self.target_min_hits = target_min_hits
        self.target_max_hits = target_max_hits
        self.max_iterations = max_iterations

        if recall_mode:
            logger.info(f"Recall mode enabled - target hits: {target_min_hits}-{target_max_hits}, max iterations: {max_iterations}")

        self.query_builder = SearchQueryBuilder(recall_mode=recall_mode)

        # Initialize AI query generator if AI client is provided
        self.ai_query_generator = None
        if self.ai_client:
            self.ai_query_generator = AIQueryGenerator(self.ai_client, max_ai_attempts)
            logger.info(f"AI query generator initialized with max {max_ai_attempts} attempts")

    def search_with_adjustment(self,
                              components: List[ComponentElement],
                              keywords_list: List[ComponentKeywords],
                              classifications_list: List[ComponentClassification],
                              initial_importance_threshold: float = 0.5) -> SearchResult:
        """
        動的範囲調整を行いながら検索

        重要度閾値を使用して、発明の特徴ではない構成要素を検索式から除外します。

        Args:
            components: 構成要素リスト
            keywords_list: キーワードリスト
            classifications_list: 分類コードリスト
            initial_importance_threshold: 初期重要度閾値（デフォルト: 0.5）
                                        0.5以上の構成要素のみを検索に使用
                                        リコールモード時は0.0を推奨

        Returns:
            SearchResult
        """
        logger.info("Starting patent search with dynamic range adjustment")

        # リコールモードの場合、より低い初期重要度閾値を使用
        if self.recall_mode and initial_importance_threshold > 0.0:
            logger.info(f"Recall mode: Lowering initial importance threshold from {initial_importance_threshold} to 0.0")
            initial_importance_threshold = 0.0

        adjustment_history = []
        iteration_details = []  # 各イテレーションの詳細情報を保存
        current_adjustment = SearchRangeAdjustment.MAINTAIN
        keyword_expansion_level = 0
        importance_threshold = initial_importance_threshold

        for iteration in range(self.max_iterations):
            logger.info(f"Search iteration {iteration + 1}/{self.max_iterations}")
            logger.info(f"Adjustment: {current_adjustment.value}, Keyword level: {keyword_expansion_level}, Importance threshold: {importance_threshold}")

            # 階層レベルを調整モードに応じて決定
            # EXPAND: レベル2（サブクラス、広範囲）
            # MAINTAIN: レベル3（メイングループ、中範囲）
            # NARROW: レベル4（完全一致、狭範囲）
            # リコールモードではタイムアウト回避のため完全一致を使用
            if self.recall_mode:
                # リコールモード: レベル4（完全一致）を使用してタイムアウトを回避
                # サブクラスレベル（cpc=G11C）はGoogle Patentsでタイムアウトするため
                hierarchy_level = 4
            elif current_adjustment == SearchRangeAdjustment.EXPAND:
                hierarchy_level = 2  # サブクラスレベル（例: G11C*, H10D*）
            elif current_adjustment == SearchRangeAdjustment.NARROW:
                hierarchy_level = 4  # 完全一致
            else:  # MAINTAIN
                hierarchy_level = 3  # メイングループレベル

            logger.info(f"Using classification hierarchy level: {hierarchy_level}")

            # 検索式を作成
            query = self.query_builder.build_search_query(
                components, keywords_list, classifications_list,
                current_adjustment, keyword_expansion_level, importance_threshold,
                hierarchy_level
            )

            # 検索実行
            result = self._execute_search(query)

            # 調整履歴に追加（従来の文字列形式）
            adjustment_history.append(
                f"Iteration {iteration + 1}: {current_adjustment.value}, "
                f"Keyword level {keyword_expansion_level}, "
                f"Importance threshold {importance_threshold:.1f}, "
                f"Hits: {result['total_hits']}"
            )

            # 各イテレーションの詳細情報を構造化して保存
            iteration_detail = {
                "iteration": iteration + 1,
                "adjustment_type": current_adjustment.value,
                "keyword_expansion_level": keyword_expansion_level,
                "importance_threshold": importance_threshold,
                "total_hits": result['total_hits'],
                "search_query": query.query_string,
                "cpc_codes_used": query.cpc_codes,
                "keywords_used": query.keywords,
                "component_queries": query.component_queries
            }
            iteration_details.append(iteration_detail)

            total_hits = result['total_hits']

            # ヒット件数が目標範囲内かチェック
            if self.target_min_hits <= total_hits <= self.target_max_hits:
                logger.info(f"Target range achieved: {total_hits} hits")
                search_result = SearchResult(
                    query=query,
                    total_hits=total_hits,
                    patents=result['patents'],
                    cpc_ranking=result['cpc_ranking'],
                    adjustment_history=adjustment_history,
                    iteration_details=iteration_details
                )

                # PDFダウンロード
                if total_hits <= self.target_max_hits:
                    self._download_pdfs(search_result.patents)

                return search_result

            # ヒット件数が少なすぎる場合（拡大検索）
            elif total_hits < self.target_min_hits:
                logger.info(f"Too few hits ({total_hits}), expanding search range")

                # 仕様通りの調整順序：キーワード→分類コード→構成要素
                # ステップ1: キーワード拡張レベルを上げる
                if keyword_expansion_level < 2:
                    keyword_expansion_level += 1
                    logger.info(f"Expanding keywords: level {keyword_expansion_level}")
                # ステップ2: 分類コードを拡大検索に切り替え
                elif current_adjustment != SearchRangeAdjustment.EXPAND:
                    current_adjustment = SearchRangeAdjustment.EXPAND
                    logger.info(f"Expanding classification codes")
                # ステップ3: 重要度閾値を下げる（より多くの構成要素を含める）
                elif importance_threshold > 0.0:
                    importance_threshold = max(0.0, importance_threshold - 0.2)
                    logger.info(f"Lowering importance threshold to {importance_threshold}")

            # ヒット件数が多すぎる場合（縮小検索）
            elif total_hits > self.target_max_hits:
                logger.info(f"Too many hits ({total_hits}), narrowing search range")

                # 仕様通りの調整順序：キーワード→分類コード→構成要素
                # ステップ1: キーワードを縮小検索に切り替え
                if keyword_expansion_level > -1:
                    keyword_expansion_level -= 1
                    logger.info(f"Narrowing keywords: level {keyword_expansion_level}")
                # ステップ2: 分類コードを縮小検索に切り替え
                elif current_adjustment != SearchRangeAdjustment.NARROW:
                    current_adjustment = SearchRangeAdjustment.NARROW
                    logger.info(f"Narrowing classification codes")
                # ステップ3: 重要度閾値を上げる（低重要度の構成要素を除外）
                elif importance_threshold < 0.8:
                    importance_threshold = min(0.8, importance_threshold + 0.2)
                    logger.info(f"Raising importance threshold to {importance_threshold}")

        # 最大反復回数に達した場合、AI生成クエリを試行
        logger.warning(f"Max iterations ({self.max_iterations}) reached without achieving target hits.")
        logger.warning(f"Final hits from manual iterations: {total_hits}")

        # AI生成クエリの試行（ai_query_generatorが利用可能な場合のみ）
        if self.ai_query_generator:
            logger.info("=" * 80)
            logger.info("Starting AI-driven query generation after manual iterations failed")
            logger.info("=" * 80)

            for ai_attempt in range(self.max_ai_attempts):
                logger.info(f"\nAI Query Generation Attempt {ai_attempt + 1}/{self.max_ai_attempts}")

                # AIを使用して最適化されたクエリを生成
                ai_query, ai_token_usage = self.ai_query_generator.generate_optimized_query(
                    components=components,
                    keywords_list=keywords_list,
                    classifications_list=classifications_list,
                    iteration_details=iteration_details,
                    target_min_hits=self.target_min_hits,
                    target_max_hits=self.target_max_hits
                )

                if ai_query is None:
                    logger.error(f"AI query generation failed on attempt {ai_attempt + 1}")
                    continue

                logger.info(f"AI Query Confidence: {ai_query.confidence}")
                logger.info(f"AI Reasoning: {ai_query.reasoning}")
                logger.info(f"Generated Query: {ai_query.query_string[:200]}...")
                if ai_token_usage:
                    logger.info(f"AI Query Generation Token Usage: {ai_token_usage.to_dict()}")

                # AI生成クエリで検索実行
                try:
                    response = requests.post(
                        f"{self.google_patents_api_url}/search",
                        json={
                            "advanced_query": ai_query.query_string,
                            "max_results": 300
                        },
                        timeout=120
                    )
                    response.raise_for_status()
                    ai_result = response.json()

                    ai_total_hits = ai_result.get('total_hits', 0)
                    logger.info(f"AI-generated query hits: {ai_total_hits}")

                    # イテレーション詳細を記録
                    ai_iteration_detail = {
                        "iteration": self.max_iterations + ai_attempt + 1,
                        "adjustment_type": "AI_GENERATED",
                        "keyword_expansion_level": "AI",
                        "importance_threshold": "AI",
                        "total_hits": ai_total_hits,
                        "search_query": ai_query.query_string,
                        "ai_confidence": ai_query.confidence,
                        "ai_reasoning": ai_query.reasoning,
                        "cpc_codes_used": [],
                        "keywords_used": [],
                        "component_queries": []
                    }
                    iteration_details.append(ai_iteration_detail)

                    # 調整履歴に追加
                    adjustment_history.append(
                        f"AI Attempt {ai_attempt + 1}: Confidence {ai_query.confidence}, "
                        f"Hits: {ai_total_hits}"
                    )

                    # 目標範囲内かチェック
                    if self.target_min_hits <= ai_total_hits <= self.target_max_hits:
                        logger.info(f"✓ AI-generated query achieved target range: {ai_total_hits} hits")

                        # SearchQueryオブジェクトを作成
                        ai_search_query = SearchQuery(
                            query_string=ai_query.query_string,
                            cpc_codes=[],
                            keywords=[],
                            component_queries=[]
                        )

                        search_result = SearchResult(
                            query=ai_search_query,
                            total_hits=ai_total_hits,
                            patents=ai_result.get('patents', []),
                            cpc_ranking=ai_result.get('cpc_ranking', []),
                            adjustment_history=adjustment_history,
                            iteration_details=iteration_details
                        )

                        # PDFダウンロード
                        if ai_total_hits <= self.target_max_hits:
                            self._download_pdfs(search_result.patents)

                        return search_result

                    else:
                        logger.info(f"AI-generated query did not achieve target range: {ai_total_hits} hits")
                        logger.info(f"Suggested adjustments: {ai_query.suggested_adjustments}")

                except Exception as e:
                    logger.error(f"AI query execution failed: {e}")
                    continue

            # 全てのAI試行が失敗した場合
            logger.warning(f"All {self.max_ai_attempts} AI attempts failed to achieve target hits")

        else:
            logger.info("AI query generator not available, skipping AI-driven optimization")

        # 最終的に最後のマニュアル結果を返す
        logger.warning(f"Returning final manual iteration result: {total_hits} hits")

        search_result = SearchResult(
            query=query,
            total_hits=total_hits,
            patents=result['patents'],
            cpc_ranking=result['cpc_ranking'],
            adjustment_history=adjustment_history,
            iteration_details=iteration_details
        )

        return search_result

    def _execute_search(self, query: SearchQuery) -> Dict[str, Any]:
        """
        検索を実行

        Args:
            query: SearchQuery

        Returns:
            検索結果の辞書
        """
        try:
            # Google Patents APIに検索リクエスト
            response = requests.post(
                f"{self.google_patents_api_url}/search",
                json={
                    "advanced_query": query.query_string,
                    "max_results": 300  # 最大300件取得（target_max_hitsに合わせて変更）
                },
                timeout=120
            )
            response.raise_for_status()

            data = response.json()

            return {
                'total_hits': data.get('total_hits', 0),
                'patents': data.get('patents', []),
                'cpc_ranking': data.get('cpc_ranking', [])
            }

        except Exception as e:
            logger.error(f"Search execution failed: {e}")
            return {
                'total_hits': 0,
                'patents': [],
                'cpc_ranking': []
            }

    def _download_pdfs(self, patents: List[Dict[str, Any]]):
        """
        特許PDFをダウンロード

        Args:
            patents: 特許リスト
        """
        logger.info(f"Downloading PDFs for {len(patents)} patents")

        for patent in patents:
            pdf_url = patent.get('pdf_url')
            patent_number = patent.get('patent_number')

            if not pdf_url:
                logger.warning(f"No PDF URL for patent: {patent_number}")
                continue

            try:
                # PDFダウンロードAPIを呼び出し
                response = requests.post(
                    f"{self.google_patents_api_url}/download_pdf",
                    json={"patent_number": patent_number},
                    timeout=60
                )
                response.raise_for_status()

                logger.info(f"Downloaded PDF for patent: {patent_number}")

            except Exception as e:
                logger.error(f"Failed to download PDF for {patent_number}: {e}")

            # レート制限を考慮
            time.sleep(1)


# ============================================================================
# Main Workflow
# ============================================================================

class PatentAnalysisWorkflow:
    """特許分析ワークフロー全体を統括するクラス"""

    def __init__(self,
                 gemini_client,
                 opensearch_api_url: str,
                 google_patents_api_url: str,
                 recall_mode: bool = False,
                 target_min_hits: int = 10,
                 target_max_hits: int = 50,
                 max_iterations: int = 12,
                 max_ai_attempts: int = 10,
                 target_patent_number: str = None):
        """
        初期化

        Args:
            gemini_client: GeminiClient
            opensearch_api_url: OpenSearch APIのURL
            google_patents_api_url: Google Patents APIのURL
            recall_mode: リコール重視モード（再現率重視で検索範囲を拡大）
            target_min_hits: 目標最小ヒット件数
            target_max_hits: 目標最大ヒット件数
            max_iterations: 最大反復回数（デフォルト: 12）
            max_ai_attempts: AI生成クエリの最大試行回数（デフォルト: 10）
            target_patent_number: ターゲット特許番号（検証用、例: JP2011171723A）
        """
        from .patent_component_analyzer import (
            PatentComponentAnalyzer, KeywordGenerator, ClassificationFinder
        )
        from .patent_verification import PatentVerificationTool

        self.component_analyzer = PatentComponentAnalyzer(gemini_client)
        self.keyword_generator = KeywordGenerator(gemini_client)
        self.classification_finder = ClassificationFinder(
            opensearch_api_url, google_patents_api_url
        )
        self.google_patents_api_url = google_patents_api_url
        self.target_patent_number = target_patent_number

        # ターゲット特許検証ツールを初期化
        self.verifier = PatentVerificationTool(google_patents_api_url)
        self.search_engine = PatentSearchEngine(
            google_patents_api_url,
            target_min_hits=target_min_hits,
            target_max_hits=target_max_hits,
            max_iterations=max_iterations,
            recall_mode=recall_mode,
            ai_client=gemini_client,
            max_ai_attempts=max_ai_attempts
        )

    def analyze_and_search(self, patent_data: str) -> Dict[str, Any]:
        """
        特許データを分析して先行技術検索を実施

        Args:
            patent_data: 特許データ（テキスト）

        Returns:
            分析・検索結果
        """
        import time
        workflow_start_time = time.time()

        logger.info("=" * 80)
        logger.info("Starting Patent Analysis and Search Workflow")
        logger.info("=" * 80)

        # ステップ1: 構成要件分割
        logger.info("\n[Step 1] Analyzing patent components...")
        step1_start = time.time()
        components, step1_token_usage = self.component_analyzer.analyze_patent_components(patent_data)
        step1_elapsed = time.time() - step1_start
        logger.info(f"Extracted {len(components)} components")
        logger.info(f"Step 1 completed in {step1_elapsed:.2f} seconds")

        # ステップ2: キーワード生成
        logger.info("\n[Step 2] Generating keywords for each component...")
        step2_start = time.time()
        keywords_list = []
        step2_token_usage_list = []
        for component in components:
            keywords, token_usage = self.keyword_generator.generate_keywords(component)
            keywords_list.append(keywords)
            step2_token_usage_list.append(token_usage)
        step2_elapsed = time.time() - step2_start
        logger.info(f"Generated keywords for {len(keywords_list)} components")
        logger.info(f"Step 2 completed in {step2_elapsed:.2f} seconds")

        # ステップ2.5: 全体で一度だけ予備検索を実行（旧方式 - コメントアウト）
        # 仕様書通りの実装では、各構成要素ごとに個別に予備検索を実行
        # logger.info("\n[Step 2.5] Performing global preliminary search...")
        # self.classification_finder.perform_global_preliminary_search(
        #     components, keywords_list
        # )
        # logger.info("Global preliminary search completed")

        # ステップ3: 特許分類コード特定（各構成要素ごとに予備検索を実行）
        logger.info("\n[Step 3] Finding patent classifications (with individual preliminary search per component)...")
        step3_start = time.time()
        classifications_list = []
        classification_history_list = []  # 分類特定プロセスの詳細履歴を保存
        for idx, (component, keywords) in enumerate(zip(components, keywords_list)):
            classification, classification_history = self.classification_finder.find_classifications(
                component, keywords, use_global_preliminary=False  # 各構成要素ごとに予備検索
            )
            classifications_list.append(classification)
            classification_history_list.append(classification_history)

            # Google Patents APIの負荷軽減のため、各構成要素の処理後に待機
            if idx < len(components) - 1:  # 最後の要素以外
                wait_time = 3  # 秒
                logger.info(f"Waiting {wait_time} seconds before processing next component to reduce API load...")
                time.sleep(wait_time)

        step3_elapsed = time.time() - step3_start
        logger.info(f"Found classifications for {len(classifications_list)} components")
        logger.info(f"Step 3 completed in {step3_elapsed:.2f} seconds")

        # ステップ4: 検索実行（動的範囲調整）
        logger.info("\n[Step 4] Executing patent search with dynamic adjustment...")
        step4_start = time.time()
        search_result = self.search_engine.search_with_adjustment(
            components, keywords_list, classifications_list
        )
        step4_elapsed = time.time() - step4_start
        logger.info(f"Search completed. Total hits: {search_result.total_hits}")
        logger.info(f"Step 4 completed in {step4_elapsed:.2f} seconds")

        # 全体の処理時間を計算
        total_elapsed = time.time() - workflow_start_time

        # Step 2のトークン使用量を集計
        step2_total_prompt_tokens = sum(tu.prompt_tokens for tu in step2_token_usage_list)
        step2_total_completion_tokens = sum(tu.completion_tokens for tu in step2_token_usage_list)
        step2_total_tokens = sum(tu.total_tokens for tu in step2_token_usage_list)

        # AI Query GenerationのトークンUsageを集計（iteration_detailsから抽出）
        ai_query_token_usage_list = []
        for iteration_detail in search_result.iteration_details:
            if iteration_detail.get("adjustment_type") == "AI_GENERATED":
                # Note: AI token usage is already logged in iteration_details but not aggregated
                # We'll extract it if available in the future
                pass

        # トークン使用量のサマリーを作成
        token_usage_summary = {
            "step1_component_analysis": step1_token_usage.to_dict(),
            "step2_keyword_generation": {
                "prompt_tokens": step2_total_prompt_tokens,
                "completion_tokens": step2_total_completion_tokens,
                "total_tokens": step2_total_tokens,
                "per_component": [tu.to_dict() for tu in step2_token_usage_list]
            },
            "total_tokens_used": {
                "prompt_tokens": step1_token_usage.prompt_tokens + step2_total_prompt_tokens,
                "completion_tokens": step1_token_usage.completion_tokens + step2_total_completion_tokens,
                "total_tokens": step1_token_usage.total_tokens + step2_total_tokens
            }
        }

        # 結果をまとめる
        result = {
            "components": [comp.to_dict() for comp in components],
            "keywords": [
                {
                    "構成要素番号": kw.構成要素番号,
                    "一次検索キーワード": kw.一次検索キーワード,
                    "検索範囲拡大キーワード": kw.検索範囲拡大キーワード,
                    "検索範囲縮小キーワード": kw.検索範囲縮小キーワード
                }
                for kw in keywords_list
            ],
            "classifications": [
                cls.to_dict() for cls in classifications_list
            ],
            "classification_history": classification_history_list,  # 分類特定プロセスの詳細履歴
            "search_query": search_result.query.query_string,
            "total_hits": search_result.total_hits,
            "patents": search_result.patents,
            "cpc_ranking": search_result.cpc_ranking,
            "adjustment_history": search_result.adjustment_history,  # 調整履歴（文字列形式）
            "iteration_details": search_result.iteration_details,  # 各イテレーションの詳細情報
            "token_usage": token_usage_summary,  # トークン使用量の詳細
            "processing_times": {  # 各工程の処理時間
                "step1_component_analysis_seconds": round(step1_elapsed, 2),
                "step2_keyword_generation_seconds": round(step2_elapsed, 2),
                "step3_classification_finding_seconds": round(step3_elapsed, 2),
                "step4_search_execution_seconds": round(step4_elapsed, 2),
                "total_workflow_seconds": round(total_elapsed, 2)
            }
        }

        logger.info("\n" + "=" * 80)
        logger.info("Workflow Completed Successfully")
        logger.info(f"Total processing time: {total_elapsed:.2f} seconds ({total_elapsed/60:.2f} minutes)")
        logger.info("=" * 80)

        # ターゲット特許番号が指定されている場合、自動検証を実行
        if self.target_patent_number:
            logger.info("\n" + "=" * 80)
            logger.info(f"Target Patent Verification: {self.target_patent_number}")
            logger.info("=" * 80)

            verification_result = self.verifier.verify_target_patent(
                target_patent_number=self.target_patent_number,
                search_result=result
            )

            # 検証結果を結果に追加
            result["target_verification"] = verification_result

            if verification_result["found"]:
                logger.info(f"✅ {verification_result['message']}")
            else:
                logger.warning(f"❌ {verification_result['message']}")

                # 分析結果と改善提案を表示
                if "analysis" in verification_result and "error" not in verification_result["analysis"]:
                    analysis = verification_result["analysis"]
                    logger.warning(f"CPC Overlap Rate: {analysis.get('cpc_overlap_rate', 0) * 100:.1f}%")

                if "suggestions" in verification_result:
                    logger.info("\n💡 Improvement Suggestions:")
                    for suggestion in verification_result["suggestions"]:
                        logger.info(f"  {suggestion}")

            logger.info("=" * 80)

        return result
