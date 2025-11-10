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

from patent_component_analyzer import (
    ComponentElement, ComponentKeywords, ComponentClassification,
    SearchRangeAdjustment
)


logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class SearchQuery:
    """検索式"""
    query_string: str  # 検索クエリ文字列
    fi_codes: List[str]  # 使用するFI分類コード
    keywords: List[str]  # 使用するキーワード
    component_queries: List[Dict[str, Any]]  # 各構成要素のクエリ


@dataclass
class SearchResult:
    """検索結果"""
    query: SearchQuery
    total_hits: int
    patents: List[Dict[str, Any]]
    cpc_ranking: List[Dict[str, Any]]
    adjustment_history: List[str]  # 調整履歴


# ============================================================================
# Search Query Builder
# ============================================================================

class SearchQueryBuilder:
    """検索式作成クラス"""

    def __init__(self):
        """初期化"""
        pass

    def build_search_query(self,
                          components: List[ComponentElement],
                          keywords_list: List[ComponentKeywords],
                          classifications_list: List[ComponentClassification],
                          range_adjustment: SearchRangeAdjustment = SearchRangeAdjustment.MAINTAIN,
                          keyword_expansion_level: int = 0) -> SearchQuery:
        """
        検索式を作成

        Args:
            components: 構成要素リスト
            keywords_list: キーワードリスト
            classifications_list: 分類コードリスト
            range_adjustment: 検索範囲調整
            keyword_expansion_level: キーワード拡張レベル（0:基本、1:中、2:高）

        Returns:
            SearchQuery
        """
        logger.info(f"Building search query with adjustment: {range_adjustment.value}")

        component_queries = []
        all_fi_codes = []

        # 各構成要素のクエリを作成
        for comp, keywords, classification in zip(components, keywords_list, classifications_list):
            comp_query = self._build_component_query(
                comp, keywords, classification,
                range_adjustment, keyword_expansion_level
            )
            component_queries.append(comp_query)

            # FIコードを収集
            all_fi_codes.extend(classification.最終分類)

        # 全体のクエリ文字列を作成
        query_string = self._combine_component_queries(component_queries, range_adjustment)

        # 重複を除去
        unique_fi_codes = list(set(all_fi_codes))

        # 使用するキーワードを収集
        all_keywords = []
        for keywords in keywords_list:
            all_keywords.extend(self._select_keywords(keywords, keyword_expansion_level))

        search_query = SearchQuery(
            query_string=query_string,
            fi_codes=unique_fi_codes,
            keywords=list(set(all_keywords)),
            component_queries=component_queries
        )

        return search_query

    def _build_component_query(self,
                               component: ComponentElement,
                               keywords: ComponentKeywords,
                               classification: ComponentClassification,
                               range_adjustment: SearchRangeAdjustment,
                               keyword_expansion_level: int) -> Dict[str, Any]:
        """
        1つの構成要素のクエリを作成

        特許検索セオリー：
        - 一個の構成要素のFI(FIが複数の場合OR条件)を異なる構成要素のキーワードとAND条件の式を作成
        """

        # FI分類コードを取得
        fi_codes = classification.最終分類
        if not fi_codes:
            fi_codes = classification.IPC分類

        # 範囲調整に応じてFIコードを選択
        if range_adjustment == SearchRangeAdjustment.NARROW:
            # 縮小：下位の分類コードを採用（より具体的）
            selected_fi = fi_codes[:2]  # 上位2件
        elif range_adjustment == SearchRangeAdjustment.EXPAND:
            # 拡大：上位の分類コードも含める
            selected_fi = fi_codes[:5]  # 上位5件
            # 上位概念のコードも追加（末尾を切り詰める）
            for code in fi_codes[:2]:
                if len(code) > 4:
                    upper_code = code[:4]  # 例: "B60W30/18" -> "B60W"
                    if upper_code not in selected_fi:
                        selected_fi.append(upper_code)
        else:
            # 維持：通常の範囲
            selected_fi = fi_codes[:3]

        # キーワードを選択
        selected_keywords = self._select_keywords(keywords, keyword_expansion_level)

        # FI部分（OR条件）
        if selected_fi:
            fi_part = " OR ".join([f'classification:"{code}"' for code in selected_fi])
        else:
            fi_part = ""

        # キーワード部分（OR条件）
        if selected_keywords:
            keyword_part = " OR ".join([f'"{kw}"' for kw in selected_keywords])
        else:
            keyword_part = ""

        # FIとキーワードをAND条件で結合
        if fi_part and keyword_part:
            component_query_str = f"({fi_part}) AND ({keyword_part})"
        elif fi_part:
            component_query_str = f"({fi_part})"
        elif keyword_part:
            component_query_str = f"({keyword_part})"
        else:
            component_query_str = ""

        return {
            "component_id": component.構成要素番号,
            "fi_codes": selected_fi,
            "keywords": selected_keywords,
            "query_string": component_query_str,
            "importance": component.構成要素の重要度
        }

    def _select_keywords(self, keywords: ComponentKeywords,
                        expansion_level: int) -> List[str]:
        """
        キーワード拡張レベルに応じてキーワードを選択

        Args:
            keywords: ComponentKeywords
            expansion_level: 0=基本、1=中、2=高

        Returns:
            選択されたキーワードリスト
        """
        if expansion_level == 0:
            # 基本：基本キーワードと機能キーワードのみ
            selected = keywords.基本キーワード[:3] + keywords.機能キーワード[:2]
        elif expansion_level == 1:
            # 中：同義語・上位概念も含む
            selected = (keywords.基本キーワード[:3] +
                       keywords.同義語類義語[:3] +
                       keywords.上位概念[:2] +
                       keywords.機能キーワード[:2])
        else:  # expansion_level >= 2
            # 高：全てのキーワードを含む
            selected = keywords.get_all_keywords()

        return selected

    def _combine_component_queries(self,
                                  component_queries: List[Dict[str, Any]],
                                  range_adjustment: SearchRangeAdjustment) -> str:
        """
        各構成要素のクエリをOR条件で結合して最終的な検索式を作成

        重要度が高い構成要素を優先
        """

        # 重要度でソート（降順）
        sorted_queries = sorted(
            component_queries,
            key=lambda x: x["importance"],
            reverse=True
        )

        # クエリ文字列のみ抽出
        query_strings = [q["query_string"] for q in sorted_queries if q["query_string"]]

        if not query_strings:
            return ""

        # 範囲調整に応じて結合方法を変更
        if range_adjustment == SearchRangeAdjustment.NARROW:
            # 縮小：AND条件を増やす（上位の重要な構成要素のみAND）
            if len(query_strings) >= 2:
                # 重要度上位2つをAND、残りをOR
                main_query = f"({query_strings[0]}) AND ({query_strings[1]})"
                if len(query_strings) > 2:
                    other_queries = " OR ".join([f"({q})" for q in query_strings[2:]])
                    combined = f"({main_query}) OR ({other_queries})"
                else:
                    combined = main_query
            else:
                combined = query_strings[0]
        else:
            # 維持・拡大：OR条件で結合
            combined = " OR ".join([f"({q})" for q in query_strings])

        return combined


# ============================================================================
# Patent Search Engine
# ============================================================================

class PatentSearchEngine:
    """特許検索エンジン（動的範囲調整機能付き）"""

    def __init__(self, google_patents_api_url: str,
                 target_min_hits: int = 10,
                 target_max_hits: int = 50,
                 max_iterations: int = 5):
        """
        初期化

        Args:
            google_patents_api_url: Google Patents検索APIのURL
            target_min_hits: 目標最小ヒット件数
            target_max_hits: 目標最大ヒット件数
            max_iterations: 最大反復回数
        """
        self.google_patents_api_url = google_patents_api_url
        self.target_min_hits = target_min_hits
        self.target_max_hits = target_max_hits
        self.max_iterations = max_iterations
        self.query_builder = SearchQueryBuilder()

    def search_with_adjustment(self,
                              components: List[ComponentElement],
                              keywords_list: List[ComponentKeywords],
                              classifications_list: List[ComponentClassification]) -> SearchResult:
        """
        動的範囲調整を行いながら検索

        Args:
            components: 構成要素リスト
            keywords_list: キーワードリスト
            classifications_list: 分類コードリスト

        Returns:
            SearchResult
        """
        logger.info("Starting patent search with dynamic range adjustment")

        adjustment_history = []
        current_adjustment = SearchRangeAdjustment.MAINTAIN
        keyword_expansion_level = 0

        for iteration in range(self.max_iterations):
            logger.info(f"Search iteration {iteration + 1}/{self.max_iterations}")
            logger.info(f"Adjustment: {current_adjustment.value}, Keyword level: {keyword_expansion_level}")

            # 検索式を作成
            query = self.query_builder.build_search_query(
                components, keywords_list, classifications_list,
                current_adjustment, keyword_expansion_level
            )

            # 検索実行
            result = self._execute_search(query)

            # 調整履歴に追加
            adjustment_history.append(
                f"Iteration {iteration + 1}: {current_adjustment.value}, "
                f"Keyword level {keyword_expansion_level}, "
                f"Hits: {result['total_hits']}"
            )

            total_hits = result['total_hits']

            # ヒット件数が目標範囲内かチェック
            if self.target_min_hits <= total_hits <= self.target_max_hits:
                logger.info(f"Target range achieved: {total_hits} hits")
                search_result = SearchResult(
                    query=query,
                    total_hits=total_hits,
                    patents=result['patents'],
                    cpc_ranking=result['cpc_ranking'],
                    adjustment_history=adjustment_history
                )

                # PDFダウンロード
                if total_hits <= self.target_max_hits:
                    self._download_pdfs(search_result.patents)

                return search_result

            # ヒット件数が少なすぎる場合
            elif total_hits < self.target_min_hits:
                logger.info(f"Too few hits ({total_hits}), expanding search range")
                current_adjustment = SearchRangeAdjustment.EXPAND

                # キーワード拡張レベルを上げる
                if keyword_expansion_level < 2:
                    keyword_expansion_level += 1

            # ヒット件数が多すぎる場合
            elif total_hits > self.target_max_hits:
                logger.info(f"Too many hits ({total_hits}), narrowing search range")
                current_adjustment = SearchRangeAdjustment.NARROW

                # キーワード拡張レベルを下げる
                if keyword_expansion_level > 0:
                    keyword_expansion_level -= 1

        # 最大反復回数に達した場合は最後の結果を返す
        logger.warning(f"Max iterations reached. Final hits: {total_hits}")

        search_result = SearchResult(
            query=query,
            total_hits=total_hits,
            patents=result['patents'],
            cpc_ranking=result['cpc_ranking'],
            adjustment_history=adjustment_history
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
                    "max_results": 100  # 最大100件取得
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
                 google_patents_api_url: str):
        """
        初期化

        Args:
            gemini_client: GeminiClient
            opensearch_api_url: OpenSearch APIのURL
            google_patents_api_url: Google Patents APIのURL
        """
        from patent_component_analyzer import (
            PatentComponentAnalyzer, KeywordGenerator, ClassificationFinder
        )

        self.component_analyzer = PatentComponentAnalyzer(gemini_client)
        self.keyword_generator = KeywordGenerator(gemini_client)
        self.classification_finder = ClassificationFinder(
            opensearch_api_url, google_patents_api_url
        )
        self.search_engine = PatentSearchEngine(google_patents_api_url)

    def analyze_and_search(self, patent_data: str) -> Dict[str, Any]:
        """
        特許データを分析して先行技術検索を実施

        Args:
            patent_data: 特許データ（テキスト）

        Returns:
            分析・検索結果
        """
        logger.info("=" * 80)
        logger.info("Starting Patent Analysis and Search Workflow")
        logger.info("=" * 80)

        # ステップ1: 構成要件分割
        logger.info("\n[Step 1] Analyzing patent components...")
        components = self.component_analyzer.analyze_patent_components(patent_data)
        logger.info(f"Extracted {len(components)} components")

        # ステップ2: キーワード生成
        logger.info("\n[Step 2] Generating keywords for each component...")
        keywords_list = []
        for component in components:
            keywords = self.keyword_generator.generate_keywords(component)
            keywords_list.append(keywords)
        logger.info(f"Generated keywords for {len(keywords_list)} components")

        # ステップ3: 特許分類コード特定
        logger.info("\n[Step 3] Finding patent classifications...")
        classifications_list = []
        for component, keywords in zip(components, keywords_list):
            classification = self.classification_finder.find_classifications(
                component, keywords
            )
            classifications_list.append(classification)
        logger.info(f"Found classifications for {len(classifications_list)} components")

        # ステップ4: 検索実行（動的範囲調整）
        logger.info("\n[Step 4] Executing patent search with dynamic adjustment...")
        search_result = self.search_engine.search_with_adjustment(
            components, keywords_list, classifications_list
        )
        logger.info(f"Search completed. Total hits: {search_result.total_hits}")

        # 結果をまとめる
        result = {
            "components": [comp.to_dict() for comp in components],
            "keywords": [
                {
                    "構成要素番号": kw.構成要素番号,
                    "全キーワード": kw.get_all_keywords()
                }
                for kw in keywords_list
            ],
            "classifications": [
                {
                    "構成要素番号": cls.構成要素番号,
                    "最終分類": cls.最終分類
                }
                for cls in classifications_list
            ],
            "search_query": search_result.query.query_string,
            "total_hits": search_result.total_hits,
            "patents": search_result.patents,
            "cpc_ranking": search_result.cpc_ranking,
            "adjustment_history": search_result.adjustment_history
        }

        logger.info("\n" + "=" * 80)
        logger.info("Workflow Completed Successfully")
        logger.info("=" * 80)

        return result
