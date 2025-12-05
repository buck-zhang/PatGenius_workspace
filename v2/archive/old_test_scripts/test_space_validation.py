#!/usr/bin/env python3
"""
FI分類コードの空白パターンをテスト

目的:
- `B41M1/30 B` (空白+サブグループ指示記号) が有効か確認
- `B41L47/48 A` (複数語) が無効か確認
"""

import requests
import json
import sys

# PatentField APIキー読み込み
with open('../patentfield_key.json', 'r') as f:
    pf_config = json.load(f)
    api_key = pf_config['PATENTFIELD_API_KEY']
    endpoint = pf_config['endpoint']

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {api_key}'
}

# テストケース
test_cases = [
    {
        'query': 'FI:B41M1/30 B',
        'description': '空白+サブグループ指示記号 (B) - 有効と推定',
        'expected': 'valid'
    },
    {
        'query': 'FI:B41M1/30',
        'description': 'サブグループ指示記号なし - 有効',
        'expected': 'valid'
    },
    {
        'query': 'FI:B41M1/30B',
        'description': '空白削除 (B41M1/30B) - 無効と推定',
        'expected': 'invalid'
    },
    {
        'query': 'FI:B41L47/48 A',
        'description': '複数語パターン (無効コード)',
        'expected': 'invalid'
    },
    {
        'query': 'FI:B41M1/30 C',
        'description': '空白+サブグループ指示記号 (C) - 有効と推定',
        'expected': 'valid'
    }
]

print("\n" + "="*80)
print("FI分類コード空白パターンAPIテスト")
print("="*80)

results = []

for i, test in enumerate(test_cases, 1):
    query = test['query']
    description = test['description']
    expected = test['expected']

    print(f"\n[テスト {i}/5] {description}")
    print(f"  検索式: {query}")

    payload = {
        "search_type": "expert",
        "q": query,
        "columns": ["pub_id"],
        "limit": 10
    }

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=30
        )

        status_code = response.status_code

        if status_code == 200:
            data = response.json()
            n_hits = data.get('n_hits', 0)
            print(f"  ✓ ステータス: 200 OK")
            print(f"  ✓ ヒット件数: {n_hits}件")
            result_status = 'valid'

        elif status_code in [400, 404]:
            print(f"  ✗ ステータス: {status_code}")
            print(f"  ✗ エラー: {response.text[:200]}")
            result_status = 'invalid'

        else:
            print(f"  ? 予期しないステータス: {status_code}")
            result_status = 'unknown'

        # 期待値と結果の比較
        match = "✓" if result_status == expected else "✗"
        print(f"  {match} 期待値: {expected}, 実際: {result_status}")

        results.append({
            'query': query,
            'description': description,
            'expected': expected,
            'actual': result_status,
            'status_code': status_code,
            'match': result_status == expected
        })

    except Exception as e:
        print(f"  ✗ 例外発生: {e}")
        results.append({
            'query': query,
            'description': description,
            'expected': expected,
            'actual': 'error',
            'match': False
        })

# サマリー
print("\n" + "="*80)
print("テスト結果サマリー")
print("="*80)

matches = sum(1 for r in results if r['match'])
total = len(results)

print(f"\n一致: {matches}/{total}")

print("\n詳細:")
for r in results:
    match_symbol = "✓" if r['match'] else "✗"
    print(f"  {match_symbol} {r['query']}")
    print(f"    期待: {r['expected']}, 実際: {r['actual']}")

# 結論
print("\n" + "="*80)
print("結論")
print("="*80)

valid_space_codes = [r for r in results if r['actual'] == 'valid' and ' ' in r['query']]
if valid_space_codes:
    print("\n空白を含む有効なFIコード:")
    for r in valid_space_codes:
        print(f"  • {r['query']}")
    print("\n→ FI分類コードは「[コード] [単一文字]」パターンで有効")
    print("→ バリデーションロジックを修正する必要がある")
else:
    print("\n空白を含む有効なFIコードは見つかりませんでした")

# 結果をJSONファイルに保存
with open('test_space_validation_results.json', 'w', encoding='utf-8') as f:
    json.dump({
        'test_cases': results,
        'summary': {
            'total': total,
            'matches': matches,
            'valid_space_codes': [r['query'] for r in valid_space_codes]
        }
    }, f, ensure_ascii=False, indent=2)

print(f"\n✓ 結果を test_space_validation_results.json に保存しました")
