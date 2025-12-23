#!/usr/bin/env python3
"""
構成対比表生成のテストスクリプト

v2.1.2のテスト結果を用いて、構成対比表を生成する。
"""

import os
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from comparison_table_generator import ComparisonTableGenerator


def main():
    """メイン関数"""
    print("=" * 80)
    print("構成対比表生成テスト")
    print("=" * 80)
    print()

    # ベースディレクトリ
    base_dir = Path(__file__).parent.parent

    # テストデータのパス
    test_name = "test_001_JP2013224028"
    results_dir = base_dir / "novelty_assessment_results" / test_name

    summary_file = results_dir / "novelty_assessment_summary.json"
    comparisons_dir = results_dir
    structure_file = base_dir / "tests" / "performance_test" / "results" / "test_001_JP2013224028_structure.json"
    output_dir = base_dir / "comparison_tables"
    output_dir.mkdir(exist_ok=True)

    # ファイル存在確認
    print("入力ファイルの確認:")
    print(f"  サマリーJSON: {summary_file.exists() and '✓' or '✗'} {summary_file}")
    print(f"  構成対比結果: {comparisons_dir.exists() and '✓' or '✗'} {comparisons_dir}")
    print(f"  構成要素JSON: {structure_file.exists() and '✓' or '✗'} {structure_file}")
    print()

    if not all([summary_file.exists(), comparisons_dir.exists(), structure_file.exists()]):
        print("❌ エラー: 必要なファイルが見つかりません")
        return

    # 構成対比表生成器の初期化
    generator = ComparisonTableGenerator()

    # Excel形式で生成
    print("【Excel形式での生成】")
    excel_output = output_dir / f"comparison_table_{test_name}.xlsx"
    try:
        result = generator.generate_comparison_table(
            assessment_summary_path=str(summary_file),
            comparison_results_dir=str(comparisons_dir),
            base_structure_path=str(structure_file),
            output_path=str(excel_output),
            format="excel"
        )
        print(f"✅ 成功: {result}")
    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        import traceback
        traceback.print_exc()

    print()

    # Markdown形式で生成
    print("【Markdown形式での生成】")
    markdown_output = output_dir / f"comparison_table_{test_name}.md"
    try:
        result = generator.generate_comparison_table(
            assessment_summary_path=str(summary_file),
            comparison_results_dir=str(comparisons_dir),
            base_structure_path=str(structure_file),
            output_path=str(markdown_output),
            format="markdown"
        )
        print(f"✅ 成功: {result}")
    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 80)
    print("テスト完了")
    print("=" * 80)
    print()
    print("生成されたファイル:")
    print(f"  Excel: {excel_output}")
    print(f"  Markdown: {markdown_output}")
    print()


if __name__ == "__main__":
    main()
