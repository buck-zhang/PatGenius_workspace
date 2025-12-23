#!/usr/bin/env python3
"""
拒絶理由通知生成のテストスクリプト

test_001_JP2013224028の結果を用いて、拒絶理由通知書を生成する。
"""

import os
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from rejection_notice_generator import RejectionNoticeGenerator


def main():
    """メイン関数"""
    print("=" * 80)
    print("拒絶理由通知生成テスト")
    print("=" * 80)
    print()

    # ベースディレクトリ
    base_dir = Path(__file__).parent.parent

    # テストデータのパス
    test_name = "test_001_JP2013224028"

    comparison_table = base_dir / "comparison_tables" / f"comparison_table_{test_name}.md"
    assessment_summary = base_dir / "novelty_assessment_results" / test_name / "novelty_assessment_summary.json"
    structure_file = base_dir / "tests" / "performance_test" / "results" / "test_001_JP2013224028_structure.json"
    output_dir = base_dir / "rejection_notices"

    # ファイル存在確認
    print("入力ファイルの確認:")
    print(f"  構成対比表: {comparison_table.exists() and '✓' or '✗'} {comparison_table}")
    print(f"  進歩性判断サマリー: {assessment_summary.exists() and '✓' or '✗'} {assessment_summary}")
    print(f"  構成要素JSON: {structure_file.exists() and '✓' or '✗'} {structure_file}")
    print()

    if not all([comparison_table.exists(), assessment_summary.exists(), structure_file.exists()]):
        print("❌ エラー: 必要なファイルが見つかりません")
        return

    # 環境変数の確認
    print("環境変数の確認:")
    project_id = os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID")
    model_name = os.environ.get("ANTHROPIC_MODEL")
    print(f"  ANTHROPIC_VERTEX_PROJECT_ID: {project_id and '✓' or '✗'} {project_id}")
    print(f"  ANTHROPIC_MODEL: {model_name and '✓' or '✗'} {model_name}")
    print()

    if not project_id:
        print("❌ エラー: ANTHROPIC_VERTEX_PROJECT_ID環境変数が設定されていません")
        return

    # 拒絶理由通知生成器の初期化
    try:
        generator = RejectionNoticeGenerator()
        print("✓ RejectionNoticeGeneratorを初期化しました")
        print()
    except Exception as e:
        print(f"❌ エラー: 初期化に失敗しました: {e}")
        import traceback
        traceback.print_exc()
        return

    # 拒絶理由通知を生成
    print("【拒絶理由通知の生成】")
    try:
        result = generator.generate_rejection_notice(
            comparison_table_path=str(comparison_table),
            assessment_summary_path=str(assessment_summary),
            base_structure_path=str(structure_file),
            output_dir=str(output_dir)
        )
        print(f"✅ 成功")
        print()
        print("生成されたファイル:")
        for file_type, file_path in result.items():
            print(f"  {file_type}: {file_path}")
    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 80)
    print("テスト完了")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
