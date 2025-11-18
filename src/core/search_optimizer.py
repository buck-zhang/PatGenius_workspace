"""
検索パラメータの自動最適化
Search Parameter Auto-Optimization
"""

import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SearchParameters:
    """検索パラメータ"""
    importance_threshold: float  # 重要度閾値
    keyword_expansion_level: int  # キーワード拡張レベル
    top_cpc_count: int  # 取得するCPCコード数
    max_cpc_codes: int  # 使用する最大CPCコード数
    use_hierarchical_search: bool  # 階層的検索を使用するか

    def __str__(self):
        return (f"SearchParameters(importance={self.importance_threshold}, "
                f"keyword_level={self.keyword_expansion_level}, "
                f"cpc_count={self.top_cpc_count}, "
                f"max_cpc_codes={self.max_cpc_codes}, "
                f"hierarchical={self.use_hierarchical_search})")


class SearchOptimizer:
    """検索パラメータを最適化するクラス"""

    def __init__(self, patent_search_engine, google_patents_api_url: str):
        """
        初期化

        Args:
            patent_search_engine: PatentSearchEngineインスタンス
            google_patents_api_url: Google Patents APIのURL
        """
        self.search_engine = patent_search_engine
        self.google_patents_api_url = google_patents_api_url

    def optimize_for_target(self,
                           components: List,
                           keywords_list: List,
                           classifications_list: List,
                           target_patent_number: str,
                           max_trials: int = 10) -> Tuple[SearchParameters, Dict[str, Any]]:
        """
        ターゲット特許を含むように検索パラメータを最適化

        Args:
            components: 構成要素リスト
            keywords_list: キーワードリスト
            classifications_list: 分類コードリスト
            target_patent_number: ターゲット特許番号
            max_trials: 最大試行回数

        Returns:
            最適なパラメータと検索結果
        """
        logger.info(f"Optimizing search parameters for target: {target_patent_number}")
        logger.info(f"Max trials: {max_trials}")

        # パラメータの候補（段階的に検索範囲を拡大）
        parameter_grid = [
            SearchParameters(0.0, 0, 3, 5, False),    # 試行1: デフォルト
            SearchParameters(0.0, 1, 5, 8, False),    # 試行2: キーワード拡張
            SearchParameters(0.0, 0, 10, 10, True),   # 試行3: CPC増加 + 階層的検索
            SearchParameters(0.0, 2, 10, 15, True),   # 試行4: 全拡張
            SearchParameters(0.3, 0, 3, 5, False),    # 試行5: 重要度0.3
            SearchParameters(0.5, 1, 5, 8, False),    # 試行6: バランス型
            SearchParameters(0.0, 0, 15, 20, True),   # 試行7: 最大拡張
            SearchParameters(0.7, 0, 3, 5, False),    # 試行8: 高重要度
            SearchParameters(0.0, 2, 20, 30, True),   # 試行9: 超拡張
            SearchParameters(0.4, 1, 10, 12, True),   # 試行10: 中間拡張
        ]

        best_params = None
        best_result = None
        trial_results = []

        for i, params in enumerate(parameter_grid[:max_trials]):
            logger.info(f"\nTrial {i+1}/{max_trials}: {params}")

            try:
                # 検索を実行
                # 注: 現在のsearch_engineは動的パラメータをサポートしていないため、
                # デフォルトのsearch_with_adjustmentを使用
                result = self.search_engine.search_with_adjustment(
                    components, keywords_list, classifications_list,
                    initial_importance_threshold=params.importance_threshold
                )

                # 検索結果からターゲット特許が含まれているかチェック
                patents = result.patents
                patent_numbers = [p.get("patent_number", "") for p in patents]

                is_found = target_patent_number in patent_numbers

                trial_results.append({
                    "trial": i + 1,
                    "parameters": params,
                    "total_hits": result.total_hits,
                    "target_found": is_found
                })

                logger.info(f"  Total hits: {result.total_hits}")
                logger.info(f"  Target found: {'✅ YES' if is_found else '❌ NO'}")

                if is_found:
                    logger.info(f"✅ Target patent {target_patent_number} found with parameters: {params}")
                    best_params = params
                    best_result = {
                        "query": result.query,
                        "total_hits": result.total_hits,
                        "patents": result.patents,
                        "cpc_ranking": result.cpc_ranking,
                        "adjustment_history": result.adjustment_history,
                        "iteration_details": result.iteration_details
                    }
                    break

            except Exception as e:
                logger.error(f"Trial {i+1} failed: {e}")
                trial_results.append({
                    "trial": i + 1,
                    "parameters": params,
                    "error": str(e)
                })

        if best_params is None:
            logger.warning(f"❌ Target patent {target_patent_number} not found after {max_trials} trials")
            # 最後の試行結果を返す
            if trial_results:
                last_trial = trial_results[-1]
                if "error" not in last_trial:
                    best_params = last_trial["parameters"]
                    # Note: result might not be defined if last trial failed
                    if 'result' in locals():
                        best_result = {
                            "query": result.query,
                            "total_hits": result.total_hits,
                            "patents": result.patents,
                            "cpc_ranking": result.cpc_ranking,
                            "adjustment_history": result.adjustment_history,
                            "iteration_details": result.iteration_details
                        }
            else:
                best_params = parameter_grid[0]
                best_result = None

        # サマリーを出力
        logger.info("\n" + "=" * 80)
        logger.info("Optimization Summary")
        logger.info("=" * 80)
        logger.info(f"Total trials: {len(trial_results)}")
        logger.info(f"Best parameters: {best_params}")
        logger.info(f"Target found: {'✅ YES' if best_result else '❌ NO'}")

        return best_params, best_result

    def generate_recommendations(self,
                                trial_results: List[Dict[str, Any]],
                                target_patent_number: str) -> List[str]:
        """
        試行結果に基づいて改善提案を生成

        Args:
            trial_results: 各試行の結果リスト
            target_patent_number: ターゲット特許番号

        Returns:
            改善提案のリスト
        """
        recommendations = []

        if not trial_results:
            recommendations.append("試行結果がありません。")
            return recommendations

        # ターゲットが見つかった試行を確認
        found_trials = [t for t in trial_results if t.get("target_found", False)]

        if found_trials:
            # 最も早く見つかった試行
            first_found = found_trials[0]
            recommendations.append(f"✅ ターゲット特許は試行{first_found['trial']}で発見されました")
            recommendations.append(f"📊 推奨パラメータ: {first_found['parameters']}")
        else:
            recommendations.append(f"❌ ターゲット特許 {target_patent_number} は全試行で見つかりませんでした")
            recommendations.append("💡 以下の追加対策を検討してください:")
            recommendations.append("   1. CPCコード数をさらに増やす（30個以上）")
            recommendations.append("   2. より広範な階層的検索を使用")
            recommendations.append("   3. キーワードの完全OR条件化")
            recommendations.append("   4. 重要度閾値を0.0に固定")

        return recommendations
