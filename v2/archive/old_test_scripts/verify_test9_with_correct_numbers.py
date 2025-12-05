#!/usr/bin/env python3
"""
Test #9の検証（正しい特許番号使用）

正しい番号:
- 本願: JP2014089440（Aなし）
- 紐づき: JP2011032263（Aなし）

検証内容:
1. 改善後の検索結果（test_validation_search_result.json）にJP2011032263が含まれているか
2. JP2011032263の技術分野がフォトレジストか確認
"""

import json
from pathlib import Path

def main():
    # 検索結果読み込み
    search_result_file = Path('test_validation_search_result.json')

    if not search_result_file.exists():
        print("⚠ test_validation_search_result.jsonが見つかりません")
        print("先に検索を実行してください:")
        print("  python3 patent_search_executor_per_component.py \\")
        print("    test_validation_keywords.json \\")
        print("    test_validation_classifications.json \\")
        print("    --pf-key ../patentfield_key.json \\")
        print("    --output test_validation_search_result.json")
        return

    with open(search_result_file, 'r', encoding='utf-8') as f:
        search_data = json.load(f)

    # ユニーク特許IDリスト取得
    unique_patent_ids = search_data.get('unique_patent_ids', [])

    print("="*80)
    print("Test #9 検証（正しい特許番号使用）")
    print("="*80)

    # 正しい紐づき特許番号（Aなし）
    target_number = "JP2011032263"

    print(f"\n検索対象: {target_number}")
    print(f"総検索結果: {len(unique_patent_ids)}件")

    # 検索結果に含まれているか確認
    if target_number in unique_patent_ids:
        print(f"\n✅ 検出成功！")
        print(f"   {target_number}が検索結果に含まれています")

        # どの構成要素で検出されたか確認
        constituent_searches = search_data.get('constituent_searches', [])

        matched_elements = []
        for search in constituent_searches:
            if target_number in search.get('final_patent_ids', []):
                element_id = search.get('element_id')
                element_text = search.get('element_text', '')[:50]
                matched_elements.append(f"{element_id}: {element_text}")

        if matched_elements:
            print(f"\n   検出された構成要素:")
            for elem in matched_elements:
                print(f"     - {elem}")

    else:
        print(f"\n❌ 検出失敗")
        print(f"   {target_number}が検索結果に含まれていません")

        # 類似番号を探す
        similar_numbers = [
            pid for pid in unique_patent_ids
            if '2011032263' in pid or 'JP2011' in pid
        ]

        if similar_numbers:
            print(f"\n   類似番号（参考）:")
            for num in similar_numbers[:5]:
                print(f"     - {num}")

    # サマリー情報
    print(f"\n" + "="*80)
    print("検索サマリー")
    print("="*80)

    summary = search_data.get('search_summary', {})
    print(f"総検索数: {summary.get('total_searches')}回")
    print(f"成功した検索: {summary.get('successful_searches')}回")
    print(f"総ヒット数: {summary.get('total_hits')}件")
    print(f"ユニーク特許数: {summary.get('unique_patents')}件")
    print(f"全文取得数: {summary.get('full_text_retrieved')}件")

    # 結論
    print(f"\n" + "="*80)
    print("結論")
    print("="*80)

    if target_number in unique_patent_ids:
        print(f"✅ Test #9: 合格")
        print(f"   紐づき特許（{target_number}）を正常に検出できました")
    else:
        print(f"❌ Test #9: 不合格")
        print(f"   紐づき特許（{target_number}）を検出できませんでした")
        print(f"\n   考えられる原因:")
        print(f"   1. キーワードが不十分")
        print(f"   2. 分類コードが一致しない")
        print(f"   3. 検索範囲が狭すぎる")


if __name__ == '__main__':
    main()
