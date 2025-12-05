#!/usr/bin/env python3
"""
Test #8の新ロジック検証スクリプト

既存のkeywords.jsonとclassifications.jsonを使用して、
新しい適応的検索ロジック（Claude統合版）を実行する。
"""

import json
from pathlib import Path
from patent_search_executor_per_component import PerComponentSearchExecutor

def main():
    print("=" * 80)
    print("Test #8 新ロジック検証: Claude統合適応的検索")
    print("=" * 80)
    print()

    # Test #8の情報
    test_id = 8
    patent_id = "JP2014081374A"
    himotuki_id = "JP2012127955A"

    # 既存の中間ファイルを使用
    keywords_file = f"tests/performance_test/results/test_{test_id:03d}_{patent_id.replace('A', '')}_keywords.json"
    classifications_file = f"tests/performance_test/results/test_{test_id:03d}_{patent_id.replace('A', '')}_classifications.json"
    output_file = f"tests/performance_test/results/test_{test_id:03d}_{patent_id.replace('A', '')}_search_result_NEW_LOGIC.json"

    print(f"本願特許: {patent_id}")
    print(f"紐づき特許: {himotuki_id}")
    print()
    print(f"使用ファイル:")
    print(f"  - Keywords: {keywords_file}")
    print(f"  - Classifications: {classifications_file}")
    print()

    # ファイル存在確認
    if not Path(keywords_file).exists():
        print(f"❌ エラー: {keywords_file} が見つかりません")
        return

    if not Path(classifications_file).exists():
        print(f"❌ エラー: {classifications_file} が見つかりません")
        return

    print("✓ 中間ファイルの存在を確認")
    print()

    # 新ロジック実行（Claude APIは無効化してテスト）
    print("-" * 80)
    print("新適応的検索ロジック実行中（Claude API無効）")
    print("-" * 80)
    print()

    executor = PerComponentSearchExecutor(
        keywords_file=keywords_file,
        classifications_file=classifications_file,
        patentfield_key_path='../patentfield_key.json',
        google_credentials_path=None,  # Claudeは今回無効
        enable_claude=False
    )

    # 検索実行
    search_result = executor.execute_full_search(
        use_independent_only=True,
        max_workers=5,
        output_file=output_file
    )

    # 結果分析
    print()
    print("=" * 80)
    print("検索結果")
    print("=" * 80)

    total_patents = search_result['total_unique_patents']
    merged_ids = search_result['merged_patent_ids']

    print(f"総取得件数: {total_patents}件")
    print()

    # 紐づき特許の検出確認
    himotuki_normalized = himotuki_id.replace('A', '').replace('B', '')
    detected = False

    for patent in merged_ids:
        if himotuki_normalized in patent:
            detected = True
            print(f"✅ 紐づき特許を検出しました: {patent}")
            print(f"   （期待値: {himotuki_id}）")
            break

    if not detected:
        print(f"❌ 紐づき特許が検出されませんでした")
        print(f"   期待値: {himotuki_id}")
        print()
        print("先頭10件の検索結果:")
        for i, patent in enumerate(merged_ids[:10], 1):
            print(f"  {i}. {patent}")

    print()
    print("=" * 80)
    print("結果サマリー")
    print("=" * 80)
    print(f"検索結果件数: {total_patents}件")
    print(f"紐づき特許検出: {'✅ YES' if detected else '❌ NO'}")
    print(f"結果保存: {output_file}")
    print("=" * 80)

    # 元のTest #8との比較
    original_result_file = f"tests/performance_test/results/test_{test_id:03d}_{patent_id.replace('A', '')}_search_result.json"
    if Path(original_result_file).exists():
        with open(original_result_file, 'r', encoding='utf-8') as f:
            original_result = json.load(f)

        original_count = original_result['total_unique_patents']

        print()
        print("=" * 80)
        print("新旧ロジックの比較")
        print("=" * 80)
        print(f"旧ロジック: {original_count}件")
        print(f"新ロジック: {total_patents}件")
        print(f"差分: {total_patents - original_count:+d}件")
        print("=" * 80)

    # 各構成要素の詳細を表示
    print()
    print("=" * 80)
    print("構成要素ごとの検索結果詳細")
    print("=" * 80)

    for component in search_result.get('component_summary', []):
        element_id = component['element_id']
        hits = component['hits']
        status = component['status']
        print(f"  {element_id}: {hits}件 ({status})")

    print("=" * 80)

if __name__ == '__main__':
    main()
