#!/usr/bin/env python3
"""
タイトルで正しい特許を検索して特定するスクリプト

JP2013224028A と JP2012040876A が本当にインクジェット関連の特許かを確認
"""

import json
import requests

with open('../patentfield_key.json', 'r') as f:
    pf_config = json.load(f)
    api_key = pf_config['PATENTFIELD_API_KEY']
    endpoint = pf_config['endpoint']

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {api_key}'
}

# 検索対象の特許番号とそのタイトルに含まれるべきキーワード
search_targets = {
    'JP2013224028A': {
        'expected_keywords': ['インクジェット', 'プリントヘッド', 'コーティング', '疎油性', '低接着'],
        'expected_title_partial': 'インクジェットプリントヘッド前面用の熱安定性疎油性低接着コーティング'
    },
    'JP2012040876A': {
        'expected_keywords': ['インクジェット', 'プリントヘッド', 'コーティング', '撥油性', '低接着'],
        'expected_title_partial': 'インクジェットプリントヘッド前面用の熱安定性撥油性低接着コーティング'
    }
}

print("=" * 80)
print("特許番号からタイトル検索による正しい特許の特定")
print("=" * 80)

for patent_number, criteria in search_targets.items():
    print(f"\n\n{'='*80}")
    print(f"特許番号: {patent_number}")
    print(f"期待されるタイトル: {criteria['expected_title_partial']}")
    print(f"{'='*80}")

    # 方法1: app_doc_idで検索（現在の方法）
    print(f"\n【方法1: app_doc_id検索】")
    payload = {
        "search_type": "expert",
        "q": f"app_doc_id:{patent_number}",
        "columns": ["app_doc_id", "pub_id", "exam_id", "title", "applicants", "ipcs"],
        "limit": 10
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        n_hits = data.get('n_hits', 0)
        print(f"  ヒット件数: {n_hits}件")

        if n_hits > 0:
            for i, record in enumerate(data.get('records', [])[:3], 1):
                print(f"\n  結果{i}:")
                print(f"    app_doc_id: {record.get('app_doc_id', 'N/A')}")
                print(f"    pub_id: {record.get('pub_id', 'N/A')}")
                print(f"    exam_id: {record.get('exam_id', 'N/A')}")
                print(f"    タイトル: {record.get('title', 'N/A')}")
                print(f"    出願人: {', '.join(record.get('applicants', [])[:2])}")
                print(f"    IPC: {', '.join(record.get('ipcs', [])[:5])}")

                # キーワードマッチ確認
                title = record.get('title', '')
                matched_keywords = [kw for kw in criteria['expected_keywords'] if kw in title]
                print(f"    キーワードマッチ: {matched_keywords} ({len(matched_keywords)}/{len(criteria['expected_keywords'])})")

                if len(matched_keywords) >= 3:
                    print(f"    ✓ 正しい特許と思われます！")
                else:
                    print(f"    ✗ 期待と異なる特許の可能性")
        else:
            print("  ヒットなし")

    except Exception as e:
        print(f"  エラー: {e}")

    # 方法2: numbersパラメータでapp_id検索
    print(f"\n【方法2: numbers[app_id]検索】")
    payload = {
        "numbers": [
            {"n": patent_number, "t": "app_id"}
        ]
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        n_hits = data.get('n_hits', 0)
        print(f"  ヒット件数: {n_hits}件")

        if n_hits > 0:
            record = data['records'][0]
            print(f"    app_doc_id: {record.get('app_doc_id', 'N/A')}")
            print(f"    pub_id: {record.get('pub_id', 'N/A')}")
            print(f"    タイトル: {record.get('title', 'N/A')}")
            print(f"    IPC: {', '.join(record.get('ipcs', [])[:5])}")

            title = record.get('title', '')
            matched_keywords = [kw for kw in criteria['expected_keywords'] if kw in title]
            print(f"    キーワードマッチ: {matched_keywords} ({len(matched_keywords)}/{len(criteria['expected_keywords'])})")
        else:
            print("  ヒットなし")

    except Exception as e:
        print(f"  エラー: {e}")

    # 方法3: numbersパラメータでpub_id検索
    print(f"\n【方法3: numbers[pub_id]検索】")
    payload = {
        "numbers": [
            {"n": patent_number, "t": "pub_id"}
        ]
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        n_hits = data.get('n_hits', 0)
        print(f"  ヒット件数: {n_hits}件")

        if n_hits > 0:
            record = data['records'][0]
            print(f"    app_doc_id: {record.get('app_doc_id', 'N/A')}")
            print(f"    pub_id: {record.get('pub_id', 'N/A')}")
            print(f"    タイトル: {record.get('title', 'N/A')}")
            print(f"    IPC: {', '.join(record.get('ipcs', [])[:5])}")

            title = record.get('title', '')
            matched_keywords = [kw for kw in criteria['expected_keywords'] if kw in title]
            print(f"    キーワードマッチ: {matched_keywords} ({len(matched_keywords)}/{len(criteria['expected_keywords'])})")
        else:
            print("  ヒットなし")

    except Exception as e:
        print(f"  エラー: {e}")

    # 方法4: タイトルキーワードで検索
    print(f"\n【方法4: タイトルキーワード検索】")
    keyword_query = " AND ".join(criteria['expected_keywords'][:3])
    payload = {
        "search_type": "expert",
        "q": keyword_query,
        "columns": ["app_doc_id", "pub_id", "title", "ipcs"],
        "limit": 20
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        n_hits = data.get('n_hits', 0)
        print(f"  検索式: {keyword_query}")
        print(f"  ヒット件数: {n_hits}件")

        # 目的の特許番号が含まれているか確認
        found_target = False
        for i, record in enumerate(data.get('records', [])[:10], 1):
            app_doc_id = record.get('app_doc_id', '')
            pub_id = record.get('pub_id', '')

            if patent_number in [app_doc_id, pub_id]:
                print(f"\n  ✓ 目的の特許が見つかりました（{i}番目）:")
                print(f"    app_doc_id: {app_doc_id}")
                print(f"    pub_id: {pub_id}")
                print(f"    タイトル: {record.get('title', 'N/A')}")
                print(f"    IPC: {', '.join(record.get('ipcs', [])[:5])}")
                found_target = True
                break

        if not found_target and n_hits > 0:
            print(f"\n  目的の特許番号は見つかりませんでした。上位3件:")
            for i, record in enumerate(data.get('records', [])[:3], 1):
                print(f"\n  結果{i}:")
                print(f"    app_doc_id: {record.get('app_doc_id', 'N/A')}")
                print(f"    pub_id: {record.get('pub_id', 'N/A')}")
                print(f"    タイトル: {record.get('title', 'N/A')[:80]}...")
                print(f"    IPC: {', '.join(record.get('ipcs', [])[:3])}")

    except Exception as e:
        print(f"  エラー: {e}")

print("\n\n" + "=" * 80)
print("結論")
print("=" * 80)
print("""
上記の4つの検索方法で、JP2013224028A と JP2012040876A が
本当にインクジェットプリントヘッド関連の特許かを確認しました。

もし方法1-3で異なる特許が返ってきた場合、
方法4のタイトルキーワード検索で正しい特許番号を特定する必要があります。
""")
