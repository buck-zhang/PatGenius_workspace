#!/usr/bin/env python3
"""
ステップ5-7の統合テスト

既存のtest_001_JP2013224028データを使用して、
構成対比→構成対比表→拒絶理由通知の一連の処理をテストする。

実行例:
    python test_steps_5_to_7.py
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

# ステップ5-7のモジュールをインポート
sys.path.insert(0, str(Path(__file__).parent / "src"))
from novelty_assessment_engine import NoveltyAssessmentEngine
from comparison_table_generator import ComparisonTableGenerator
from rejection_notice_generator import RejectionNoticeGenerator


def main():
    """メイン関数"""
    print(f"\n{'='*80}")
    print(f"ステップ5-7統合テスト")
    print(f"{'='*80}\n")

    # ベースディレクトリ
    base_dir = Path(__file__).parent

    # 既存のtest_001データ
    test_name = "test_001_JP2013224028"
    results_base = base_dir / "tests/performance_test/results"

    structure_file = results_base / f"{test_name}_structure.json"
    search_file = results_base / f"{test_name}_search_result.json"

    # 出力ディレクトリ
    output_dir = base_dir / "test_steps_5_to_7_results" / test_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # ファイル存在確認
    print("入力ファイルの確認:")
    print(f"  構成要素JSON: {structure_file.exists() and '✓' or '✗'} {structure_file}")
    print(f"  検索結果JSON: {search_file.exists() and '✗' or '✓'} {search_file}")
    print(f"  出力先: {output_dir}")
    print()

    if not structure_file.exists():
        print(f"❌ エラー: {structure_file} が見つかりません")
        return

    if not search_file.exists():
        print(f"❌ エラー: {search_file} が見つかりません")
        return

    # 環境変数の確認
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "ttdc-in-house-dev")
    anthropic_project = os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID")

    print("環境変数の確認:")
    print(f"  GOOGLE_CLOUD_PROJECT: {project_id}")
    print(f"  ANTHROPIC_VERTEX_PROJECT_ID: {anthropic_project or '(未設定)'}")
    print()

    if not anthropic_project:
        print("⚠ 警告: ANTHROPIC_VERTEX_PROJECT_IDが未設定です")
        print("   export ANTHROPIC_VERTEX_PROJECT_ID='ttdc-in-house-dev' を実行してください")
        print()

    # PatentField APIキーのパス
    patentfield_key = base_dir / "patentfield_key.json"
    if not patentfield_key.exists():
        print(f"❌ エラー: {patentfield_key} が見つかりません")
        return

    # 統計情報
    stats = {
        'start_time': time.time(),
        'steps': {}
    }

    try:
        # ====================================================================
        # ステップ5: 構成対比（進歩性判断）
        # ====================================================================
        print(f"\n{'='*80}")
        print(f"ステップ5: 構成対比（進歩性判断）")
        print(f"{'='*80}\n")

        step5_start = time.time()

        # 構成対比結果の出力先
        novelty_dir = output_dir / "novelty_assessment"
        novelty_dir.mkdir(exist_ok=True)

        print(f"初期化中...")
        engine = NoveltyAssessmentEngine(
            project_id=project_id,
            location="global",
            model_name="gemini-3-pro-preview",
            patentfield_key_path=str(patentfield_key),
            output_dir=str(novelty_dir),
            max_workers=5
        )

        print(f"構成対比を実行中...")
        summary = engine.assess_novelty(
            base_patent_structure_file=str(structure_file),
            search_result_file=str(search_file),
            limit=10  # 最初は10件でテスト
        )

        step5_time = time.time() - step5_start
        stats['steps']['step5'] = {
            'time_seconds': step5_time,
            'x_references': summary['x_references']['count'],
            'y_references': summary['y_references']['count']
        }

        print(f"\n✅ ステップ5完了 ({step5_time:.1f}秒)")
        print(f"   X文献: {summary['x_references']['count']}件")
        print(f"   Y文献: {summary['y_references']['count']}件")
        print(f"   結果ディレクトリ: {novelty_dir}\n")

        summary_file = novelty_dir / "novelty_assessment_summary.json"

        # ====================================================================
        # ステップ6: 構成対比表生成
        # ====================================================================
        print(f"\n{'='*80}")
        print(f"ステップ6: 構成対比表生成")
        print(f"{'='*80}\n")

        step6_start = time.time()

        generator = ComparisonTableGenerator()

        # Excel形式
        print("Excel形式で生成中...")
        excel_file = output_dir / "comparison_table.xlsx"
        generator.generate_comparison_table(
            assessment_summary_path=str(summary_file),
            comparison_results_dir=str(novelty_dir),
            base_structure_path=str(structure_file),
            output_path=str(excel_file),
            format="excel"
        )

        # Markdown形式
        print("Markdown形式で生成中...")
        markdown_file = output_dir / "comparison_table.md"
        generator.generate_comparison_table(
            assessment_summary_path=str(summary_file),
            comparison_results_dir=str(novelty_dir),
            base_structure_path=str(structure_file),
            output_path=str(markdown_file),
            format="markdown"
        )

        step6_time = time.time() - step6_start
        stats['steps']['step6'] = {
            'time_seconds': step6_time,
            'excel_file': str(excel_file),
            'markdown_file': str(markdown_file)
        }

        print(f"\n✅ ステップ6完了 ({step6_time:.1f}秒)")
        print(f"   Excel: {excel_file}")
        print(f"   Markdown: {markdown_file}\n")

        # ====================================================================
        # ステップ7: 拒絶理由通知生成
        # ====================================================================
        print(f"\n{'='*80}")
        print(f"ステップ7: 拒絶理由通知生成")
        print(f"{'='*80}\n")

        step7_start = time.time()

        rejection_dir = output_dir / "rejection_notice"
        rejection_dir.mkdir(exist_ok=True)

        print("拒絶理由通知を生成中...")
        rejection_generator = RejectionNoticeGenerator()

        result_files = rejection_generator.generate_rejection_notice(
            comparison_table_path=str(markdown_file),
            assessment_summary_path=str(summary_file),
            base_structure_path=str(structure_file),
            output_dir=str(rejection_dir)
        )

        step7_time = time.time() - step7_start
        stats['steps']['step7'] = {
            'time_seconds': step7_time,
            'output_files': result_files
        }

        print(f"\n✅ ステップ7完了 ({step7_time:.1f}秒)")
        for file_type, file_path in result_files.items():
            print(f"   {file_type}: {file_path}")
        print()

        # ====================================================================
        # 統計情報の保存
        # ====================================================================
        stats['end_time'] = time.time()
        stats['total_time'] = stats['end_time'] - stats['start_time']

        stats_file = output_dir / "test_stats.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        # ====================================================================
        # 完了メッセージ
        # ====================================================================
        print(f"\n{'='*80}")
        print(f"✅ テスト完了")
        print(f"{'='*80}")
        print(f"総処理時間: {stats['total_time']:.1f}秒")
        print(f"  - ステップ5（構成対比）: {stats['steps']['step5']['time_seconds']:.1f}秒")
        print(f"  - ステップ6（構成対比表）: {stats['steps']['step6']['time_seconds']:.1f}秒")
        print(f"  - ステップ7（拒絶理由通知）: {stats['steps']['step7']['time_seconds']:.1f}秒")
        print(f"\n最終成果物:")
        print(f"  📊 構成対比表:")
        print(f"     Excel: {excel_file}")
        print(f"     Markdown: {markdown_file}")
        print(f"  📝 拒絶理由通知書:")
        for file_type, file_path in result_files.items():
            print(f"     {file_type}: {file_path}")
        print(f"\n統計情報: {stats_file}")
        print(f"{'='*80}\n")

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()

        # エラー情報の保存
        stats['end_time'] = time.time()
        stats['total_time'] = stats['end_time'] - stats['start_time']
        stats['error'] = str(e)

        error_file = output_dir / "test_error.json"
        with open(error_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        print(f"\nエラー情報: {error_file}")
        sys.exit(1)


if __name__ == "__main__":
    main()
