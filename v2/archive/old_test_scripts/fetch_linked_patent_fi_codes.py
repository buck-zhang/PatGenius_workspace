#!/usr/bin/env python3
"""
紐づき特許のFI分類コードを直接取得

目的:
- 各紐づき特許のFI分類コードを確認
- G03F7系かどうかを確認
- 本願特許との違いを明確化
"""

import json
import requests
from pathlib import Path

def get_patent_fi_codes(api_key: str, endpoint: str, patent_id: str):
    """特許のFI分類コードを取得"""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    # pub_idで検索して、FI分類を取得
    query = f'pub_id:{patent_id}'
    payload = {
        'search_type': 'expert',
        'q': query,
        'columns': ['pub_id', 'title', 'abstract'],  # FIは別途取得
        'limit': 1
    }

    try:
        # まず基本情報を取得
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get('n_hits', 0) == 0:
            print(f"⚠ {patent_id}: 検索結果なし")
            return None

        record = data['records'][0]

        # 全文APIでFI分類を取得
        # エンドポイント: https://ttdc.patentfield.com/api/v1/patents/{patent_id}?id_type=pub_id
        base_url = endpoint.replace('/patents/search', '')
        full_url = f"{base_url}/patents/{patent_id}"

        full_response = requests.get(
            full_url,
            headers={'Authorization': f'Bearer {api_key}'},
            params={'id_type': 'pub_id'},
            timeout=30
        )

        fi_codes = []
        ipc_codes = []

        if full_response.status_code == 200:
            full_data = full_response.json()
            fi_codes = full_data.get('FI', [])
            ipc_codes = full_data.get('IPC', [])
        else:
            print(f"  ⚠ FI分類取得失敗 (status: {full_response.status_code})")

        return {
            'pub_id': record['pub_id'],
            'title': record.get('title', ''),
            'FI': fi_codes,
            'IPC': ipc_codes
        }

    except Exception as e:
        print(f"  ✗ エラー: {e}")
        return None


def main():
    # API設定読み込み
    pf_key_path = Path('../patentfield_key.json')
    with open(pf_key_path, 'r') as f:
        pf_config = json.load(f)
        api_key = pf_config['PATENTFIELD_API_KEY']
        endpoint = pf_config['endpoint']

    # 本願特許と紐づき特許
    main_patent = 'JP2014089440'
    linked_patents = [
        'JP2011032263',
        'JP2011191446',
        'JP2012173419',
        'JP2012185472'
    ]

    print("="*80)
    print("紐づき特許のFI分類コード取得")
    print("="*80)

    # 本願特許のFI分類を取得
    print(f"\n【本願特許】{main_patent}")
    print("-"*80)
    main_data = get_patent_fi_codes(api_key, endpoint, main_patent)

    if main_data:
        print(f"タイトル: {main_data['title'][:60]}...")
        print(f"FI分類数: {len(main_data['FI'])}個")
        print(f"IPC分類数: {len(main_data['IPC'])}個")

        # G03F7系のFIコードを抽出
        g03f7_fi = [fi for fi in main_data['FI'] if fi.startswith('G03F7')]
        print(f"G03F7系FI: {len(g03f7_fi)}個")
        if g03f7_fi:
            print(f"  上位5件: {', '.join(g03f7_fi[:5])}")

    # 紐づき特許のFI分類を取得
    all_results = {'main_patent': main_data, 'linked_patents': []}

    for patent_id in linked_patents:
        print(f"\n【紐づき特許】{patent_id}")
        print("-"*80)

        linked_data = get_patent_fi_codes(api_key, endpoint, patent_id)

        if linked_data:
            all_results['linked_patents'].append(linked_data)

            print(f"タイトル: {linked_data['title'][:60]}...")
            print(f"FI分類数: {len(linked_data['FI'])}個")
            print(f"IPC分類数: {len(linked_data['IPC'])}個")

            # G03F7系のFIコードを抽出
            g03f7_fi = [fi for fi in linked_data['FI'] if fi.startswith('G03F7')]
            print(f"G03F7系FI: {len(g03f7_fi)}個")
            if g03f7_fi:
                print(f"  上位5件: {', '.join(g03f7_fi[:5])}")
            else:
                print(f"  ⚠ G03F7系のFIコードなし")

                # 他にどのFI分類があるか確認
                if linked_data['FI']:
                    print(f"  他のFI分類（上位5件）: {', '.join(linked_data['FI'][:5])}")

    # 比較分析
    print("\n" + "="*80)
    print("FI分類比較分析")
    print("="*80)

    if main_data and all_results['linked_patents']:
        main_fi_set = set(main_data['FI'])
        main_g03f7 = set([fi for fi in main_data['FI'] if fi.startswith('G03F7')])

        print(f"\n本願特許:")
        print(f"  総FI数: {len(main_fi_set)}個")
        print(f"  G03F7系: {len(main_g03f7)}個")

        for linked_data in all_results['linked_patents']:
            patent_id = linked_data['pub_id']
            linked_fi_set = set(linked_data['FI'])
            linked_g03f7 = set([fi for fi in linked_data['FI'] if fi.startswith('G03F7')])

            # 完全一致FI
            common_fi = main_fi_set & linked_fi_set
            common_g03f7 = main_g03f7 & linked_g03f7

            print(f"\n{patent_id}:")
            print(f"  総FI数: {len(linked_fi_set)}個")
            print(f"  G03F7系: {len(linked_g03f7)}個")
            print(f"  本願との完全一致FI: {len(common_fi)}個")
            if common_fi:
                print(f"    例: {', '.join(list(common_fi)[:3])}")
            print(f"  G03F7系の一致: {len(common_g03f7)}個")
            if common_g03f7:
                print(f"    {', '.join(list(common_g03f7)[:3])}")

    # 結果保存
    with open('linked_patents_fi_codes.json', 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 結果を保存: linked_patents_fi_codes.json")


if __name__ == '__main__':
    main()
