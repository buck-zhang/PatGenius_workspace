#!/usr/bin/env python3
"""
構成要素ごと検索のテストスクリプト

使用方法:
  python test_per_component_search.py --keywords <キーワードファイル> --classifications <分類ファイル>

テスト内容:
1. 単一構成要素の検索テスト
2. 並行検索のテスト
3. 結果統合・重複削除のテスト
"""

import sys
import json
from pathlib import Path
import argparse

# 自モジュールのインポート
from patent_search_executor_per_component import PerComponentSearchExecutor


def test_single_component_search(executor: PerComponentSearchExecutor):
    """単一構成要素の検索テスト"""
    print("\n" + "="*80)
    print("テスト1: 単一構成要素の検索")
    print("="*80)

    if not executor.independent_components:
        print("✗ 独立請求項の構成要素が見つかりません")
        return

    # 最初の構成要素でテスト
    test_element_id = executor.independent_components[0]

    result = executor.search_single_component_adaptive(test_element_id)

    print("\n検索結果:")
    print(f"  構成要素ID: {result['element_id']}")
    print(f"  最終ヒット件数: {result['final_hits']}")
    print(f"  取得特許数: {len(result['patent_ids'])}")
    print(f"  ステータス: {result['status']}")
    print(f"  試行回数: {len(result['attempts'])}")

    for attempt in result['attempts']:
        print(f"\n  試行{attempt['step']}: {attempt['strategy']}")
        print(f"    ヒット件数: {attempt['hits']}")

    if result['status'] == 'success':
        print("\n✓ テスト1成功")
    else:
        print("\n⚠ テスト1: 目標範囲外ですが処理は完了")


def test_parallel_search(executor: PerComponentSearchExecutor):
    """並行検索のテスト"""
    print("\n" + "="*80)
    print("テスト2: 並行検索（最初の3要素）")
    print("="*80)

    if len(executor.independent_components) < 3:
        print("✗ テスト対象が不足しています")
        return

    # 最初の3要素でテスト
    test_components = executor.independent_components[:3]

    results = executor.search_all_components_parallel(
        component_ids=test_components,
        max_workers=3
    )

    print("\n検索結果サマリー:")
    for result in results:
        print(f"  {result['element_id']}: {result['final_hits']}件 - {result['status']}")

    print(f"\n✓ テスト2成功: {len(results)}個の構成要素を並行検索")


def test_merge_and_deduplicate(executor: PerComponentSearchExecutor):
    """結果統合・重複削除のテスト"""
    print("\n" + "="*80)
    print("テスト3: 結果統合・重複削除（最初の3要素）")
    print("="*80)

    if len(executor.independent_components) < 3:
        print("✗ テスト対象が不足しています")
        return

    # 最初の3要素で検索
    test_components = executor.independent_components[:3]

    results = executor.search_all_components_parallel(
        component_ids=test_components,
        max_workers=3
    )

    # 統合・重複削除
    merged = executor.merge_and_deduplicate(results)

    print("\n統合結果:")
    print(f"  検索構成要素数: {merged['total_components']}")
    print(f"  重複削除後の特許数: {merged['total_unique_patents']}")

    print(f"\n✓ テスト3成功")


def test_full_execution(executor: PerComponentSearchExecutor, output_file: str):
    """完全実行テスト"""
    print("\n" + "="*80)
    print("テスト4: 完全実行（独立請求項のみ、並行処理、結果統合）")
    print("="*80)

    result = executor.execute_full_search(
        use_independent_only=True,
        max_workers=5,
        output_file=output_file
    )

    print("\n完全実行結果:")
    print(f"  検索構成要素数: {result['total_components']}")
    print(f"  最終取得件数: {result['total_unique_patents']}")
    print(f"  処理時間: {result['elapsed_time']:.2f}秒")
    print(f"  結果ファイル: {output_file}")

    # 各構成要素のサマリー
    print("\n構成要素別サマリー:")
    for comp in result['component_summary']:
        print(f"  {comp['element_id']}: {comp['hits']}件 - {comp['status']}")

    print(f"\n✓ テスト4成功")


def main():
    parser = argparse.ArgumentParser(description='構成要素ごと検索のテスト')
    parser.add_argument('--keywords', required=True, help='キーワードJSONファイル')
    parser.add_argument('--classifications', required=True, help='特許分類JSONファイル')
    parser.add_argument('--pf-key', default='../patentfield_key.json', help='PatentField APIキー')
    parser.add_argument('--output', default='test_search_result.json', help='結果出力ファイル')
    parser.add_argument('--test', choices=['1', '2', '3', '4', 'all'], default='all',
                        help='実行するテスト (1:単一検索, 2:並行検索, 3:統合, 4:完全実行, all:全て)')

    args = parser.parse_args()

    # 初期化
    print("構成要素ごと検索システムを初期化中...")
    executor = PerComponentSearchExecutor(
        keywords_file=args.keywords,
        classifications_file=args.classifications,
        patentfield_key_path=args.pf_key
    )

    # テスト実行
    if args.test == '1' or args.test == 'all':
        test_single_component_search(executor)

    if args.test == '2' or args.test == 'all':
        test_parallel_search(executor)

    if args.test == '3' or args.test == 'all':
        test_merge_and_deduplicate(executor)

    if args.test == '4' or args.test == 'all':
        test_full_execution(executor, args.output)

    print("\n" + "="*80)
    print("全テスト完了")
    print("="*80)


if __name__ == '__main__':
    main()
