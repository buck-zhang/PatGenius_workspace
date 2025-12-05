#!/usr/bin/env python3
"""
FI分類コードのみの検索テスト

仮説検証:
- G03F7.（フォトレジスト全般）で検索すれば、紐づき特許が検出されるはず
- 検出されれば、問題はキーワードの特異性とFI分類の詳細度であることが確定
"""

import json
import requests
from pathlib import Path

def search_by_fi_only(api_key: str, endpoint: str, fi_code: str, limit: int = 5000):
    """FI分類コードのみで検索"""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    # G03F7系のみで検索
    query = f'FI:{fi_code}'
    payload = {
        'search_type': 'expert',
        'q': query,
        'columns': ['pub_id', 'title'],
        'limit': limit
    }

    print(f"検索クエリ: {query}")
    print(f"最大取得件数: {limit}件")

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        n_hits = data.get('n_hits', 0)
        records = data.get('records', [])
        patent_ids = [record['pub_id'] for record in records]

        print(f"\n総ヒット数: {n_hits}件")
        print(f"取得した件数: {len(patent_ids)}件")

        return patent_ids, n_hits

    except Exception as e:
        print(f"エラー: {e}")
        return [], 0


def main():
    # API設定読み込み
    pf_key_path = Path('../patentfield_key.json')
    with open(pf_key_path, 'r') as f:
        pf_config = json.load(f)
        api_key = pf_config['PATENTFIELD_API_KEY']
        endpoint = pf_config['endpoint']

    # 紐づき特許リスト（正しい番号、Aなし）
    linked_patents = [
        'JP2011032263',
        'JP2011191446',
        'JP2012173419',
        'JP2012185472'
    ]

    print("="*80)
    print("FI分類コードのみの検索テスト")
    print("="*80)
    print("\n目的: G03F7系で検索すれば紐づき特許が検出されるか検証\n")

    # テスト1: G03F7.（フォトレジスト全般）
    print("\n【テスト1】G03F7.で検索（上位3桁 + ワイルドカード）")
    print("-"*80)
    patent_ids_1, n_hits_1 = search_by_fi_only(api_key, endpoint, 'G03F7.', limit=5000)

    detected_1 = []
    for linked_id in linked_patents:
        if linked_id in patent_ids_1:
            detected_1.append(linked_id)
            print(f"✅ {linked_id}: 検出成功")
        else:
            print(f"❌ {linked_id}: 検出失敗（取得範囲外の可能性）")

    # テスト2: G03F7/039.（レジスト成分系）
    print("\n【テスト2】G03F7/039.で検索（上位6桁 + ワイルドカード）")
    print("-"*80)
    patent_ids_2, n_hits_2 = search_by_fi_only(api_key, endpoint, 'G03F7/039.', limit=5000)

    detected_2 = []
    for linked_id in linked_patents:
        if linked_id in patent_ids_2:
            detected_2.append(linked_id)
            print(f"✅ {linked_id}: 検出成功")
        else:
            print(f"❌ {linked_id}: 検出失敗（取得範囲外の可能性）")

    # テスト3: G03F7/004.（レジスト材料系）
    print("\n【テスト3】G03F7/004.で検索（上位6桁 + ワイルドカード）")
    print("-"*80)
    patent_ids_3, n_hits_3 = search_by_fi_only(api_key, endpoint, 'G03F7/004.', limit=5000)

    detected_3 = []
    for linked_id in linked_patents:
        if linked_id in patent_ids_3:
            detected_3.append(linked_id)
            print(f"✅ {linked_id}: 検出成功")
        else:
            print(f"❌ {linked_id}: 検出失敗（取得範囲外の可能性）")

    # 結果サマリー
    print("\n" + "="*80)
    print("検証結果サマリー")
    print("="*80)

    print(f"\nテスト1（G03F7.）:")
    print(f"  総ヒット数: {n_hits_1}件")
    print(f"  取得件数: {len(patent_ids_1)}件")
    print(f"  検出された紐づき特許: {len(detected_1)}/4件")
    if detected_1:
        print(f"    {', '.join(detected_1)}")

    print(f"\nテスト2（G03F7/039.）:")
    print(f"  総ヒット数: {n_hits_2}件")
    print(f"  取得件数: {len(patent_ids_2)}件")
    print(f"  検出された紐づき特許: {len(detected_2)}/4件")
    if detected_2:
        print(f"    {', '.join(detected_2)}")

    print(f"\nテスト3（G03F7/004.）:")
    print(f"  総ヒット数: {n_hits_3}件")
    print(f"  取得件数: {len(patent_ids_3)}件")
    print(f"  検出された紐づき特許: {len(detected_3)}/4件")
    if detected_3:
        print(f"    {', '.join(detected_3)}")

    # 結論
    print("\n" + "="*80)
    print("結論")
    print("="*80)

    total_detected = len(set(detected_1 + detected_2 + detected_3))

    if total_detected == 4:
        print("\n✅ 仮説確認:")
        print("   FI分類コードを広く取れば、紐づき特許を検出できる")
        print("   → 問題は「詳細すぎるFI分類」と「固有すぎるキーワード」")
    elif total_detected > 0:
        print(f"\n⚠ 部分的に検出: {total_detected}/4件")
        print("   一部の紐づき特許は広範なFI検索でも検出できない")
        print("   → 取得件数の制限（5000件）を超えている可能性")
    else:
        print("\n❌ 検出失敗:")
        print("   広範なFI検索でも紐づき特許を検出できない")
        print("   → 紐づき特許のFI分類がG03F7系ではない可能性")

    # 結果保存
    output = {
        'test_1_G03F7': {
            'n_hits': n_hits_1,
            'detected': detected_1,
            'detection_rate': len(detected_1) / 4
        },
        'test_2_G03F7_039': {
            'n_hits': n_hits_2,
            'detected': detected_2,
            'detection_rate': len(detected_2) / 4
        },
        'test_3_G03F7_004': {
            'n_hits': n_hits_3,
            'detected': detected_3,
            'detection_rate': len(detected_3) / 4
        },
        'linked_patents': linked_patents,
        'total_detected': total_detected
    }

    with open('fi_only_search_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 結果を保存: fi_only_search_results.json")


if __name__ == '__main__':
    main()
