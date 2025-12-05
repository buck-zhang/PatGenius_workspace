#!/usr/bin/env python3
"""
Pattern 2問題（Tests #7, #9, #10）のClaude API有効化検証

既存の中間ファイル（keywords.json, classifications.json）を使用して、
Claude API機能を有効化した新ロジックで検索を実行し、
紐づき特許の検出精度を検証する。
"""

import json
from pathlib import Path
from patent_search_executor_per_component import PerComponentSearchExecutor

# テストケース定義
TEST_CASES = [
    {
        'test_id': 7,
        'patent_id': 'JP2014077998A',
        'himotuki_id': 'JP2012042835A',
        'description': 'Test #7 - Pattern 2問題'
    },
    {
        'test_id': 9,
        'patent_id': 'JP2014089440A',
        'himotuki_id': 'JP2011032263A',
        'description': 'Test #9 - Pattern 2問題'
    },
    {
        'test_id': 10,
        'patent_id': 'JP2014089440A',
        'himotuki_id': 'JP2011191446A',
        'description': 'Test #10 - Pattern 2問題'
    }
]

def run_single_test(test_case: dict, enable_claude: bool = True):
    """
    単一テストケースを実行

    Args:
        test_case: テストケース情報
        enable_claude: Claude API有効化フラグ
    """
    test_id = test_case['test_id']
    patent_id = test_case['patent_id']
    himotuki_id = test_case['himotuki_id']
    description = test_case['description']

    print("\n" + "=" * 80)
    print(f"{description}")
    print("=" * 80)
    print(f"本願特許: {patent_id}")
    print(f"紐づき特許: {himotuki_id}")
    print(f"Claude API: {'有効' if enable_claude else '無効'}")
    print("=" * 80)
    print()

    # ファイルパス
    keywords_file = f"tests/performance_test/results/test_{test_id:03d}_{patent_id.replace('A', '')}_keywords.json"
    classifications_file = f"tests/performance_test/results/test_{test_id:03d}_{patent_id.replace('A', '')}_classifications.json"

    suffix = "_CLAUDE" if enable_claude else "_NO_CLAUDE"
    output_file = f"tests/performance_test/results/test_{test_id:03d}_{patent_id.replace('A', '')}_search_result{suffix}.json"

    # ファイル存在確認
    if not Path(keywords_file).exists():
        print(f"❌ エラー: {keywords_file} が見つかりません")
        return None

    if not Path(classifications_file).exists():
        print(f"❌ エラー: {classifications_file} が見つかりません")
        return None

    # 検索実行
    try:
        executor = PerComponentSearchExecutor(
            keywords_file=keywords_file,
            classifications_file=classifications_file,
            patentfield_key_path='../patentfield_key.json',
            google_credentials_path='ttdc-in-house-dev-3e07247326cb.json' if enable_claude else None,
            enable_claude=enable_claude
        )

        search_result = executor.execute_full_search(
            use_independent_only=True,
            max_workers=5,
            output_file=output_file
        )

        # 結果分析
        total_patents = search_result['total_unique_patents']
        merged_ids = search_result['merged_patent_ids']

        print()
        print("-" * 80)
        print("検索結果")
        print("-" * 80)
        print(f"総取得件数: {total_patents}件")

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

        print("-" * 80)

        return {
            'test_id': test_id,
            'patent_id': patent_id,
            'himotuki_id': himotuki_id,
            'total_patents': total_patents,
            'detected': detected,
            'claude_enabled': enable_claude,
            'output_file': output_file
        }

    except Exception as e:
        print(f"❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("=" * 80)
    print("Pattern 2問題 Claude API有効化検証")
    print("=" * 80)
    print()

    # 結果格納
    results = []

    # 各テストケースを実行（Claude有効）
    for test_case in TEST_CASES:
        result = run_single_test(test_case, enable_claude=True)
        if result:
            results.append(result)

    # 結果サマリー
    print("\n" + "=" * 80)
    print("検証結果サマリー")
    print("=" * 80)

    for result in results:
        status = "✅ 検出" if result['detected'] else "❌ 未検出"
        print(f"Test #{result['test_id']}: {result['total_patents']}件 - {status}")

    # 検出率
    detected_count = sum(1 for r in results if r['detected'])
    total_count = len(results)
    detection_rate = (detected_count / total_count * 100) if total_count > 0 else 0

    print()
    print(f"検出成功: {detected_count}/{total_count} ({detection_rate:.1f}%)")
    print("=" * 80)

    # 旧結果との比較
    print("\n" + "=" * 80)
    print("旧ロジックとの比較")
    print("=" * 80)

    for result in results:
        test_id = result['test_id']
        patent_id = result['patent_id']

        original_file = f"tests/performance_test/results/test_{test_id:03d}_{patent_id.replace('A', '')}_search_result.json"

        if Path(original_file).exists():
            with open(original_file, 'r', encoding='utf-8') as f:
                original_result = json.load(f)

            original_count = original_result['total_unique_patents']
            new_count = result['total_patents']
            diff = new_count - original_count

            print(f"Test #{test_id}:")
            print(f"  旧ロジック: {original_count}件")
            print(f"  新ロジック: {new_count}件")
            print(f"  差分: {diff:+d}件")
            print()

    print("=" * 80)


if __name__ == '__main__':
    main()
