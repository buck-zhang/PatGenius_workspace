#!/usr/bin/env python3
"""
進歩性判断エンジンのテストスクリプト

最新のtest_001_JP2013224028データを使用してシステムを検証
"""

import os
import sys
from pathlib import Path
from novelty_assessment_engine import NoveltyAssessmentEngine


def main():
    """テストメイン"""
    # Google Cloud プロジェクトID（環境変数から取得）
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")

    if not project_id:
        print("エラー: 環境変数GOOGLE_CLOUD_PROJECTを設定してください")
        print("例: export GOOGLE_CLOUD_PROJECT='your-project-id'")
        sys.exit(1)

    # 最新のテストデータ（2025-12-09作成）
    base_dir = Path(__file__).parent.parent
    structure_file = base_dir / "tests/performance_test/results/test_001_JP2013224028_structure.json"
    search_file = base_dir / "tests/performance_test/results/test_001_JP2013224028_search_result.json"

    # ファイル存在確認
    if not structure_file.exists():
        print(f"エラー: 構成要素ファイルが見つかりません: {structure_file}")
        sys.exit(1)

    if not search_file.exists():
        print(f"エラー: 検索結果ファイルが見つかりません: {search_file}")
        sys.exit(1)

    print(f"テストデータ:")
    print(f"  構成要素: {structure_file}")
    print(f"  検索結果: {search_file}\n")

    # エンジン初期化
    output_dir = base_dir / "novelty_assessment_results/test_001_JP2013224028"

    engine = NoveltyAssessmentEngine(
        project_id=project_id,
        location="global",  # Gemini 3 ProはGlobalエンドポイント使用
        model_name="gemini-3-pro-preview",
        patentfield_key_path=str(base_dir / "patentfield_key.json"),
        output_dir=str(output_dir),
        max_workers=5  # 並列5スレッド
    )

    # テスト実行（最初は10件で試す）
    print("=" * 70)
    print("テスト実行: 最初の10件で動作確認")
    print("=" * 70)

    summary = engine.assess_novelty(
        base_patent_structure_file=str(structure_file),
        search_result_file=str(search_file),
        limit=10  # 最初は10件のみ
    )

    # 結果表示
    print("\n" + "=" * 70)
    print("テスト結果サマリー")
    print("=" * 70)
    print(f"本願特許: {summary['base_patent_id']}")
    print(f"対象特許数: {summary['search_results_count']}")
    print(f"成功した構成対比: {summary['successful_comparisons']}")
    print(f"失敗した構成対比: {summary['failed_comparisons']}")
    print(f"\n採用された優先度: {summary['priority_level_used']}")
    print(f"\nX文献（単独文献）: {summary['x_references']['count']}件")
    if summary['x_references']['patents']:
        for patent_id in summary['x_references']['patents'][:5]:
            print(f"  - {patent_id}")

    print(f"\nY文献（組み合わせ文献）: {summary['y_references']['count']}件")
    if summary['y_references']['combinations']:
        for combo in summary['y_references']['combinations'][:3]:
            print(f"  - {combo['combination_count']}件の組み合わせ: {combo['patents']}")

    print(f"\n処理時間: {summary['elapsed_time_seconds']:.1f}秒")
    print(f"結果保存先: {output_dir}")

    # 全件実行の確認
    print("\n" + "=" * 70)
    user_input = input("全件（検索結果全て）で実行しますか？ (yes/no): ")

    if user_input.lower() in ['yes', 'y']:
        print("\n全件実行を開始します...")

        summary_full = engine.assess_novelty(
            base_patent_structure_file=str(structure_file),
            search_result_file=str(search_file),
            limit=None  # 全件
        )

        print(f"\n全件実行完了:")
        print(f"  X文献: {summary_full['x_references']['count']}件")
        print(f"  Y文献: {summary_full['y_references']['count']}件")
        print(f"  処理時間: {summary_full['elapsed_time_seconds']:.1f}秒")

    else:
        print("\n全件実行はスキップされました")

    print("\nテスト完了\n")


if __name__ == "__main__":
    main()
