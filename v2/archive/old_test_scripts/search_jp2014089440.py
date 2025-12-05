#!/usr/bin/env python3
"""
JP2014089440Aをpub_idで検索
"""

import json
import requests
from pathlib import Path

def main():
    # PatentField API設定読み込み
    pf_key_path = Path('../patentfield_key.json')

    with open(pf_key_path, 'r') as f:
        pf_config = json.load(f)
        api_key = pf_config['PATENTFIELD_API_KEY']
        endpoint = pf_config['endpoint']

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    # pub_idで検索
    query = "pub_id:JP2014089440A"

    payload = {
        "search_type": "expert",
        "q": query,
        "columns": ["pub_id", "app_doc_id", "title", "abstract"],
        "limit": 1
    }

    print(f"\n{'='*80}")
    print(f"検索: {query}")
    print(f"{'='*80}")

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=30
        )

        print(f"ステータスコード: {response.status_code}")
        response.raise_for_status()

        data = response.json()
        n_hits = data.get('n_hits', 0)

        print(f"ヒット件数: {n_hits}件\n")

        if n_hits > 0:
            record = data['records'][0]

            print(f"pub_id: {record.get('pub_id')}")
            print(f"app_doc_id: {record.get('app_doc_id')}")
            print(f"タイトル: {record.get('title', '')}\n")

            abstract = record.get('abstract', '')
            if abstract:
                print(f"要約:\n{abstract[:300]}...")

            # JSONファイルに保存
            output_file = 'jp2014089440_pub_id_search.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"\n✓ 検索結果を保存: {output_file}")

        else:
            print("ヒットなし")

    except requests.exceptions.HTTPError as e:
        print(f"✗ HTTPエラー: {e}")
        print(f"レスポンス: {e.response.text[:500]}")
    except Exception as e:
        print(f"✗ エラー: {e}")

if __name__ == '__main__':
    main()
