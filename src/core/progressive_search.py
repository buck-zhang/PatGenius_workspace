"""
段階的検索戦略モジュール
Progressive Search Strategy Module

3段階の検索戦略を提供:
- Discovery Phase (発見フェーズ): 広範囲検索、高Recall
- Refinement Phase (絞り込みフェーズ): バランス型
- Precision Phase (精密フェーズ): 狭範囲検索、高Precision
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SearchPhase(Enum):
    """検索フェーズ"""
    DISCOVERY = "discovery"      # 発見フェーズ（広範囲）
    REFINEMENT = "refinement"    # 絞り込みフェーズ（中範囲）
    PRECISION = "precision"      # 精密フェーズ（狭範囲）


@dataclass
class PhaseConfig:
    """フェーズ設定"""
    phase: SearchPhase
    classification_hierarchy_level: int  # 分類コード階層レベル
    keyword_hierarchy_level: int         # キーワード階層レベル
    max_classification_codes: int        # 使用する最大分類コード数
    max_keywords: int                    # 使用する最大キーワード数
    importance_threshold: float          # 重要度閾値
    cross_logic: str                     # 分類とキーワードの結合論理
    target_min_hits: int                 # 目標最小ヒット数
    target_max_hits: int                 # 目標最大ヒット数


class ProgressiveSearchStrategy:
    """段階的検索戦略クラス"""

    # 各フェーズのデフォルト設定
    PHASE_CONFIGS = {
        SearchPhase.DISCOVERY: PhaseConfig(
            phase=SearchPhase.DISCOVERY,
            classification_hierarchy_level=1,  # Class level (H10*, G11*)
            keyword_hierarchy_level=1,         # Broad keywords
            max_classification_codes=10,
            max_keywords=15,
            importance_threshold=0.0,          # 全構成要素を使用
            cross_logic="OR",                  # 分類 OR キーワード（広い）
            target_min_hits=1000,
            target_max_hits=10000
        ),
        SearchPhase.REFINEMENT: PhaseConfig(
            phase=SearchPhase.REFINEMENT,
            classification_hierarchy_level=2,  # Subclass level (H10D*, G11C*)
            keyword_hierarchy_level=2,         # Medium keywords
            max_classification_codes=8,
            max_keywords=10,
            importance_threshold=0.3,          # 重要度0.3以上
            cross_logic="AND",                 # 分類 AND キーワード（バランス）
            target_min_hits=100,
            target_max_hits=1000
        ),
        SearchPhase.PRECISION: PhaseConfig(
            phase=SearchPhase.PRECISION,
            classification_hierarchy_level=3,  # Maingroup level (H10D30*, G11C11*)
            keyword_hierarchy_level=3,         # Narrow keywords
            max_classification_codes=5,
            max_keywords=5,
            importance_threshold=0.5,          # 重要度0.5以上
            cross_logic="AND",                 # 分類 AND キーワード（狭い）
            target_min_hits=10,
            target_max_hits=100
        )
    }

    @staticmethod
    def get_phase_config(phase: SearchPhase) -> PhaseConfig:
        """
        フェーズ設定を取得

        Args:
            phase: 検索フェーズ

        Returns:
            PhaseConfig
        """
        return ProgressiveSearchStrategy.PHASE_CONFIGS[phase]

    @staticmethod
    def determine_next_phase(current_phase: SearchPhase,
                            current_hits: int) -> Optional[SearchPhase]:
        """
        現在のヒット数から次のフェーズを決定

        Args:
            current_phase: 現在のフェーズ
            current_hits: 現在のヒット数

        Returns:
            次のフェーズ（Noneの場合は現在のフェーズで終了）
        """
        config = ProgressiveSearchStrategy.get_phase_config(current_phase)

        # 目標範囲内なら終了
        if config.target_min_hits <= current_hits <= config.target_max_hits:
            logger.info(f"Target range achieved in {current_phase.value} phase: {current_hits} hits")
            return None

        # ヒット数が多すぎる場合、次のフェーズへ
        if current_hits > config.target_max_hits:
            if current_phase == SearchPhase.DISCOVERY:
                logger.info(f"Too many hits ({current_hits}), moving to REFINEMENT phase")
                return SearchPhase.REFINEMENT
            elif current_phase == SearchPhase.REFINEMENT:
                logger.info(f"Too many hits ({current_hits}), moving to PRECISION phase")
                return SearchPhase.PRECISION
            else:
                # PRECISION phaseでもまだ多い場合は調整が必要
                logger.warning(f"Too many hits ({current_hits}) even in PRECISION phase")
                return None

        # ヒット数が少なすぎる場合、前のフェーズに戻る
        if current_hits < config.target_min_hits:
            if current_phase == SearchPhase.PRECISION:
                logger.info(f"Too few hits ({current_hits}), returning to REFINEMENT phase")
                return SearchPhase.REFINEMENT
            elif current_phase == SearchPhase.REFINEMENT:
                logger.info(f"Too few hits ({current_hits}), returning to DISCOVERY phase")
                return SearchPhase.DISCOVERY
            else:
                # DISCOVERY phaseでも少ない場合は拡張が必要
                logger.warning(f"Too few hits ({current_hits}) even in DISCOVERY phase")
                return None

        return None

    @staticmethod
    def build_progressive_search_plan(initial_phase: SearchPhase = SearchPhase.REFINEMENT) -> List[PhaseConfig]:
        """
        段階的検索計画を構築

        Args:
            initial_phase: 初期フェーズ（デフォルト: REFINEMENT）

        Returns:
            検索計画のリスト
        """
        plan = []

        # 初期フェーズから開始
        plan.append(ProgressiveSearchStrategy.get_phase_config(initial_phase))

        # 他のフェーズも計画に追加（必要に応じて実行）
        all_phases = [SearchPhase.DISCOVERY, SearchPhase.REFINEMENT, SearchPhase.PRECISION]

        for phase in all_phases:
            if phase != initial_phase:
                plan.append(ProgressiveSearchStrategy.get_phase_config(phase))

        return plan

    @staticmethod
    def analyze_search_results(results_by_phase: Dict[SearchPhase, Dict[str, Any]]) -> Dict[str, Any]:
        """
        各フェーズの検索結果を分析

        Args:
            results_by_phase: {phase: result} の辞書

        Returns:
            分析結果
        """
        analysis = {
            "phases_executed": [],
            "best_phase": None,
            "best_hits": 0,
            "phase_summary": []
        }

        best_score = float('inf')

        for phase, result in results_by_phase.items():
            hits = result.get('total_hits', 0)
            config = ProgressiveSearchStrategy.get_phase_config(phase)

            # 目標範囲からの距離を計算
            target_center = (config.target_min_hits + config.target_max_hits) / 2
            distance = abs(hits - target_center)

            phase_info = {
                "phase": phase.value,
                "total_hits": hits,
                "target_range": f"{config.target_min_hits}-{config.target_max_hits}",
                "in_target_range": config.target_min_hits <= hits <= config.target_max_hits,
                "distance_from_target": distance
            }

            analysis["phases_executed"].append(phase.value)
            analysis["phase_summary"].append(phase_info)

            # 最適なフェーズを選択（目標に最も近い）
            if distance < best_score:
                best_score = distance
                analysis["best_phase"] = phase.value
                analysis["best_hits"] = hits

        return analysis


class AdaptiveSearchStrategy:
    """適応的検索戦略（ヒット数に基づいて動的に調整）"""

    @staticmethod
    def calculate_adjustment_parameters(current_hits: int,
                                       target_min: int,
                                       target_max: int,
                                       iteration: int) -> Dict[str, Any]:
        """
        ヒット数に基づいて調整パラメータを計算

        Args:
            current_hits: 現在のヒット数
            target_min: 目標最小ヒット数
            target_max: 目標最大ヒット数
            iteration: 現在のイテレーション数

        Returns:
            調整パラメータ辞書
        """
        # 目標範囲の中心
        target_center = (target_min + target_max) / 2

        # ヒット数の比率（対数スケール）
        import math
        if current_hits > 0:
            hit_ratio = math.log10(current_hits) / math.log10(target_center)
        else:
            hit_ratio = 0

        # 調整方向を決定
        if current_hits < target_min:
            direction = "expand"
            adjustment_strength = min(1.0, (target_min - current_hits) / target_min)
        elif current_hits > target_max:
            direction = "narrow"
            adjustment_strength = min(1.0, (current_hits - target_max) / current_hits)
        else:
            direction = "maintain"
            adjustment_strength = 0.0

        # 階層レベルを決定
        if direction == "expand":
            # 拡大: より広い階層へ
            classification_level = max(1, 2 - int(adjustment_strength * 2))
            keyword_level = max(1, 2 - int(adjustment_strength * 2))
        elif direction == "narrow":
            # 縮小: より狭い階層へ
            classification_level = min(4, 2 + int(adjustment_strength * 2))
            keyword_level = min(3, 2 + int(adjustment_strength))
        else:
            # 維持
            classification_level = 2
            keyword_level = 2

        return {
            "direction": direction,
            "adjustment_strength": adjustment_strength,
            "classification_hierarchy_level": classification_level,
            "keyword_hierarchy_level": keyword_level,
            "hit_ratio": hit_ratio,
            "iteration": iteration
        }


# テスト用のコード
if __name__ == "__main__":
    print("=" * 80)
    print("段階的検索戦略のテスト")
    print("=" * 80)

    # テスト1: フェーズ設定の取得
    print("\n【テスト1】各フェーズの設定")
    print("-" * 80)
    for phase in [SearchPhase.DISCOVERY, SearchPhase.REFINEMENT, SearchPhase.PRECISION]:
        config = ProgressiveSearchStrategy.get_phase_config(phase)
        print(f"\n{phase.value.upper()} Phase:")
        print(f"  分類階層レベル: {config.classification_hierarchy_level}")
        print(f"  キーワード階層レベル: {config.keyword_hierarchy_level}")
        print(f"  目標ヒット数: {config.target_min_hits}-{config.target_max_hits}")
        print(f"  結合論理: {config.cross_logic}")
        print(f"  重要度閾値: {config.importance_threshold}")

    # テスト2: 次フェーズの決定
    print("\n【テスト2】次フェーズの決定")
    print("-" * 80)
    test_cases = [
        (SearchPhase.DISCOVERY, 50000, "多すぎ → REFINEMENT"),
        (SearchPhase.REFINEMENT, 5000, "多すぎ → PRECISION"),
        (SearchPhase.PRECISION, 5, "少なすぎ → REFINEMENT"),
        (SearchPhase.REFINEMENT, 50, "少なすぎ → DISCOVERY"),
        (SearchPhase.REFINEMENT, 500, "適正 → 終了"),
    ]

    for phase, hits, expected in test_cases:
        next_phase = ProgressiveSearchStrategy.determine_next_phase(phase, hits)
        result = next_phase.value if next_phase else "None (終了)"
        print(f"  {phase.value} phase, {hits} hits → {result} ({expected})")

    # テスト3: 検索計画の構築
    print("\n【テスト3】段階的検索計画")
    print("-" * 80)
    plan = ProgressiveSearchStrategy.build_progressive_search_plan(SearchPhase.REFINEMENT)
    print(f"検索計画（{len(plan)}フェーズ）:")
    for i, config in enumerate(plan, 1):
        print(f"  {i}. {config.phase.value} phase (目標: {config.target_min_hits}-{config.target_max_hits} hits)")

    # テスト4: 適応的調整パラメータ
    print("\n【テスト4】適応的調整パラメータ計算")
    print("-" * 80)
    test_hits = [10, 100, 500, 5000, 50000]
    target_min, target_max = 10, 300

    for hits in test_hits:
        params = AdaptiveSearchStrategy.calculate_adjustment_parameters(
            hits, target_min, target_max, iteration=1
        )
        print(f"\n  {hits} hits:")
        print(f"    方向: {params['direction']}")
        print(f"    調整強度: {params['adjustment_strength']:.2f}")
        print(f"    分類レベル: {params['classification_hierarchy_level']}")
        print(f"    キーワードレベル: {params['keyword_hierarchy_level']}")

    # テスト5: 結果分析
    print("\n【テスト5】検索結果の分析")
    print("-" * 80)
    results_by_phase = {
        SearchPhase.DISCOVERY: {'total_hits': 5000},
        SearchPhase.REFINEMENT: {'total_hits': 150},
        SearchPhase.PRECISION: {'total_hits': 25}
    }

    analysis = ProgressiveSearchStrategy.analyze_search_results(results_by_phase)
    print(f"実行フェーズ: {', '.join(analysis['phases_executed'])}")
    print(f"最適フェーズ: {analysis['best_phase']} ({analysis['best_hits']} hits)")
    print(f"\n各フェーズの詳細:")
    for summary in analysis['phase_summary']:
        status = "✓" if summary['in_target_range'] else "✗"
        print(f"  {status} {summary['phase']}: {summary['total_hits']} hits (目標: {summary['target_range']})")

    print("\n" + "=" * 80)
    print("✓ 段階的検索戦略のテスト完了")
    print("=" * 80)
