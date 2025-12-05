#!/usr/bin/env python3
"""
単一特許のテスト実行
"""

import sys
import json
from pathlib import Path

# performance_test_systemからインポート
from performance_test_system import PerformanceTestSystem

def test_single_patent(patent_id: str, himotuki_id: str):
    """
    単一特許でテスト実行

    Args:
        patent_id: 本願特許番号
        himotuki_id: 紐づき特許番号
    """
    print(f"\n{'='*80}")
    print(f"単一特許テスト")
    print(f"本願: {patent_id}")
    print(f"紐づき: {himotuki_id}")
    print(f"{'='*80}\n")

    # テストシステム初期化
    system = PerformanceTestSystem(
        google_credentials_path='ttdc-in-house-dev-3e07247326cb.json',
        patentfield_key_path='../patentfield_key.json',
        output_dir='tests/performance_test/results'
    )

    # 特許テキスト取得
    print(f"特許テキスト取得: {patent_id}")
    patent_text = system.fetch_patent_text(patent_id)

    if not patent_text:
        print(f"✗ 特許テキスト取得失敗")
        return False

    print(f"✓ 特許テキスト取得成功")

    # 一連の処理実行
    output_prefix = f"test_debug_{patent_id.replace('A', '').replace('B', '')}"

    search_result, token_info = system.run_full_pipeline(
        patent_text=patent_text,
        output_prefix=output_prefix
    )

    if not search_result:
        print(f"✗ 検索実行失敗")
        return False

    # 紐づき特許の検出確認
    detected = system.check_himotuki_detection(search_result, himotuki_id)

    print(f"\n{'='*80}")
    print(f"結果")
    print(f"{'='*80}")
    print(f"検索結果件数: {search_result['total_unique_patents']}件")
    print(f"紐づき特許検出: {'✅ YES' if detected else '❌ NO'}")
    print(f"紐づき特許番号: {himotuki_id}")
    print(f"{'='*80}\n")

    return detected


if __name__ == '__main__':
    # Test #5の特許でテスト
    patent_id = 'JP2014062952A'
    himotuki_id = 'JP2011070088A'

    if len(sys.argv) > 1:
        patent_id = sys.argv[1]
    if len(sys.argv) > 2:
        himotuki_id = sys.argv[2]

    detected = test_single_patent(patent_id, himotuki_id)

    sys.exit(0 if detected else 1)
