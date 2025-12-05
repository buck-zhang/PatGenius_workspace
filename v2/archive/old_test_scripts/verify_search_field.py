#!/usr/bin/env python3
"""
PatentField API検索フィールド検証
=================================

JP2011032263Aが本当に公開番号(pub_id)か出願番号(app_doc_id)かを
PatentField APIのsearchエンドポイントで検証します。

検証方法:
1. JP2011032263Aを全文検索で検索
2. ヒットした特許のpub_idとapp_doc_idを確認
3. JP2012171629も同様に検索して比較
"""

import json
import requests
from pathlib import Path

def search_patent_by_number(api_key: str, endpoint: str, patent_number: str):
    """特許番号で検索（全文検索）"""

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    # 全文検索で特許番号を検索
    payload = {
        "search_type": "expert",
        "q": patent_number,
        "columns": ["pub_id", "app_doc_id", "title"],
        "limit": 10
    }

    print(f"\n{'='*80}")
    print(f"検索: {patent_number}")
    print(f"{'='*80}")
    print(f"クエリ: {patent_number}")
    print(f"エンドポイント: {endpoint}")

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=30
        )

        print(f"\nステータスコード: {response.status_code}")

        response.raise_for_status()

        data = response.json()
        n_hits = data.get('n_hits', 0)

        print(f"ヒット件数: {n_hits}件")

        if n_hits > 0:
            print(f"\n検索結果（上位{min(n_hits, 10)}件）:")
            print("-" * 80)

            for i, record in enumerate(data.get('records', []), 1):
                pub_id = record.get('pub_id', 'N/A')
                app_doc_id = record.get('app_doc_id', 'N/A')
                title = record.get('title', 'N/A')

                print(f"\n{i}. pub_id: {pub_id}")
                print(f"   app_doc_id: {app_doc_id}")
                print(f"   タイトル: {title[:80]}...")

                # 検索番号がどこにマッチしたか確認
                if pub_id == patent_number:
                    print(f"   ✓ {patent_number}はpub_idとして一致")
                if app_doc_id == patent_number:
                    print(f"   ✓ {patent_number}はapp_doc_idとして一致")

        return data

    except requests.exceptions.HTTPError as e:
        print(f"\n✗ HTTPエラー: {e}")
        print(f"レスポンス: {e.response.text[:500]}")
        return None
    except Exception as e:
        print(f"\n✗ エラー: {e}")
        return None


def main():
    # PatentField API設定読み込み
    pf_key_path = Path('../patentfield_key.json')

    if not pf_key_path.exists():
        print(f"エラー: {pf_key_path}が見つかりません")
        return

    with open(pf_key_path, 'r') as f:
        pf_config = json.load(f)
        api_key = pf_config['PATENTFIELD_API_KEY']
        endpoint = pf_config['endpoint']

    print("\n" + "="*80)
    print("PatentField API検索フィールド検証")
    print("="*80)
    print("\n検証内容:")
    print("1. JP2011032263Aを検索してpub_id/app_doc_idを確認")
    print("2. JP2012171629を検索してpub_id/app_doc_idを確認")
    print("3. 両者の関係を分析")

    # 検索1: JP2011032263A
    result1 = search_patent_by_number(api_key, endpoint, "JP2011032263A")

    # 検索2: JP2012171629
    result2 = search_patent_by_number(api_key, endpoint, "JP2012171629")

    # 分析
    print(f"\n{'='*80}")
    print("分析結果")
    print(f"{'='*80}")

    if result1 and result1.get('n_hits', 0) > 0:
        record1 = result1['records'][0]
        print(f"\nJP2011032263Aで検索した結果:")
        print(f"  pub_id: {record1.get('pub_id')}")
        print(f"  app_doc_id: {record1.get('app_doc_id')}")

        if record1.get('pub_id') == 'JP2011032263A':
            print(f"  → JP2011032263Aは公開番号(pub_id)です ✓")
        elif record1.get('app_doc_id') == 'JP2011032263A':
            print(f"  → JP2011032263Aは出願番号(app_doc_id)です")
            print(f"  → 対応する公開番号(pub_id)は: {record1.get('pub_id')}")
    else:
        print(f"\nJP2011032263Aで検索: ヒットなし")

    if result2 and result2.get('n_hits', 0) > 0:
        record2 = result2['records'][0]
        print(f"\nJP2012171629で検索した結果:")
        print(f"  pub_id: {record2.get('pub_id')}")
        print(f"  app_doc_id: {record2.get('app_doc_id')}")

        if record2.get('pub_id') == 'JP2012171629':
            print(f"  → JP2012171629は公開番号(pub_id)です ✓")
        elif record2.get('app_doc_id') == 'JP2012171629':
            print(f"  → JP2012171629は出願番号(app_doc_id)です")
    else:
        print(f"\nJP2012171629で検索: ヒットなし")

    # 同一性チェック
    if result1 and result2:
        if result1.get('n_hits', 0) > 0 and result2.get('n_hits', 0) > 0:
            record1 = result1['records'][0]
            record2 = result2['records'][0]

            print(f"\n同一性チェック:")
            if record1.get('pub_id') == record2.get('pub_id'):
                print(f"  ✓ 両者は同じ特許です")
                print(f"    公開番号: {record1.get('pub_id')}")
                print(f"    出願番号: {record1.get('app_doc_id')}")
            else:
                print(f"  ✗ 両者は異なる特許です")
                print(f"    JP2011032263A検索結果の公開番号: {record1.get('pub_id')}")
                print(f"    JP2012171629検索結果の公開番号: {record2.get('pub_id')}")

    print(f"\n{'='*80}")
    print("結論")
    print(f"{'='*80}")

    if result1 and result1.get('n_hits', 0) > 0:
        record1 = result1['records'][0]

        if record1.get('app_doc_id') == 'JP2011032263A' and record1.get('pub_id') == 'JP2012171629':
            print("\n✓ 確認:")
            print("  - JP2011032263A = 出願番号(app_doc_id)")
            print("  - JP2012171629 = 公開番号(pub_id)")
            print("  - 両者は同じ特許の異なる番号です")
            print("\n✓ ユーザーの指摘「両方とも公開番号です」に対して:")
            print("  - JP2011032263Aは出願番号であり、公開番号ではありません")
            print("  - 正しい公開番号はJP2012171629です")
        elif record1.get('pub_id') == 'JP2011032263A':
            print("\n✓ 確認:")
            print("  - JP2011032263A = 公開番号(pub_id)")
            print("  - ユーザーの指摘は正しいです")


if __name__ == '__main__':
    main()
