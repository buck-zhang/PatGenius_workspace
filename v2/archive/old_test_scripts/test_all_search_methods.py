#!/usr/bin/env python3
"""
PatentField API 出願番号検索方法の網羅的検証

JP2013224028A で「インクジェットプリントヘッド前面用の熱安定性疎油性低接着コーティング」
が取得できる検索方法を特定する
"""

import json
import requests
from typing import Dict, List

# API設定読み込み
with open('../patentfield_key.json', 'r') as f:
    pf_config = json.load(f)
    api_key = pf_config['PATENTFIELD_API_KEY']
    endpoint = pf_config['endpoint']

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {api_key}'
}

# テスト対象
TARGET_NUMBER = 'JP2013224028A'
EXPECTED_KEYWORDS = ['インクジェット', 'プリントヘッド', '疎油性', '低接着']

def check_result(result: Dict, method_name: str) -> None:
    """
    検索結果を検証し、表示する
    """
    print(f"\n{'='*80}")
    print(f"【{method_name}】")
    print(f"{'='*80}")

    if result.get('error'):
        print(f"❌ エラー: {result['error']}")
        print(f"   詳細: {result.get('details', 'N/A')}")
        return

    n_hits = result.get('n_hits', 0)
    print(f"ヒット件数: {n_hits}件")

    if n_hits == 0:
        print("❌ 結果なし")
        return

    # 最初の結果を詳細表示
    records = result.get('records', [])
    if records:
        record = records[0]
        app_doc_id = record.get('app_doc_id', 'N/A')
        pub_id = record.get('pub_id', 'N/A')
        title = record.get('title', 'N/A')
        ipcs = record.get('ipcs', [])

        print(f"\n結果1:")
        print(f"  app_doc_id: {app_doc_id}")
        print(f"  pub_id: {pub_id}")
        print(f"  タイトル: {title[:100]}...")
        print(f"  IPC: {', '.join(ipcs[:5])}")

        # キーワードマッチ確認
        matched = [kw for kw in EXPECTED_KEYWORDS if kw in title]
        match_rate = len(matched) / len(EXPECTED_KEYWORDS)

        print(f"  キーワードマッチ: {matched} ({len(matched)}/{len(EXPECTED_KEYWORDS)})")

        if match_rate >= 0.75:  # 75%以上マッチ
            print(f"  ✅ 正しいインクジェット特許です！")
        else:
            print(f"  ❌ 期待と異なる特許")
            print(f"     取得された特許: {title[:80]}")


def method_1_numbers_app_id_epodoc() -> Dict:
    """
    方法1: numbersパラメータ + app_id タイプ + EPODOC形式
    公式ドキュメント推奨方法
    """
    epodoc = TARGET_NUMBER.rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ')

    payload = {
        "numbers": [
            {"n": epodoc, "t": "app_id"}
        ],
        "columns": ["app_doc_id", "pub_id", "title", "ipcs", "app_claims"]
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {'error': str(e), 'details': getattr(e, 'response', None)}


def method_2_numbers_app_id_with_kind() -> Dict:
    """
    方法2: numbersパラメータ + app_id タイプ + 種別コード付き
    """
    payload = {
        "numbers": [
            {"n": TARGET_NUMBER, "t": "app_id"}
        ],
        "columns": ["app_doc_id", "pub_id", "title", "ipcs"]
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {'error': str(e), 'details': getattr(e, 'response', None)}


def method_3_numbers_pub_id_epodoc() -> Dict:
    """
    方法3: numbersパラメータ + pub_id タイプ + EPODOC形式
    """
    epodoc = TARGET_NUMBER.rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ')

    payload = {
        "numbers": [
            {"n": epodoc, "t": "pub_id"}
        ],
        "columns": ["app_doc_id", "pub_id", "title", "ipcs"]
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {'error': str(e), 'details': getattr(e, 'response', None)}


def method_4_numbers_pub_id_with_kind() -> Dict:
    """
    方法4: numbersパラメータ + pub_id タイプ + 種別コード付き
    """
    payload = {
        "numbers": [
            {"n": TARGET_NUMBER, "t": "pub_id"}
        ],
        "columns": ["app_doc_id", "pub_id", "title", "ipcs"]
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {'error': str(e), 'details': getattr(e, 'response', None)}


def method_5_numbers_no_type_epodoc() -> Dict:
    """
    方法5: numbersパラメータ（タイプ指定なし）+ EPODOC形式
    自動判定
    """
    epodoc = TARGET_NUMBER.rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ')

    payload = {
        "numbers": [
            {"n": epodoc}
        ],
        "columns": ["app_doc_id", "pub_id", "title", "ipcs"]
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {'error': str(e), 'details': getattr(e, 'response', None)}


def method_6_numbers_no_type_with_kind() -> Dict:
    """
    方法6: numbersパラメータ（タイプ指定なし）+ 種別コード付き
    自動判定
    """
    payload = {
        "numbers": [
            {"n": TARGET_NUMBER}
        ],
        "columns": ["app_doc_id", "pub_id", "title", "ipcs"]
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {'error': str(e), 'details': getattr(e, 'response', None)}


def method_7_expert_app_doc_id() -> Dict:
    """
    方法7: expert検索 + app_doc_id:コマンド
    """
    payload = {
        "search_type": "expert",
        "q": f"app_doc_id:{TARGET_NUMBER}",
        "columns": ["app_doc_id", "pub_id", "title", "ipcs"],
        "limit": 10
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {'error': str(e), 'details': getattr(e, 'response', None)}


def method_8_fulltext_search() -> Dict:
    """
    方法8: fulltext検索（デフォルト）
    """
    payload = {
        "search_type": "fulltext",
        "q": TARGET_NUMBER,
        "columns": ["app_doc_id", "pub_id", "title", "ipcs"],
        "limit": 10
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {'error': str(e), 'details': getattr(e, 'response', None)}


def method_9_expert_pub_id() -> Dict:
    """
    方法9: expert検索 + pub_id:コマンド
    """
    payload = {
        "search_type": "expert",
        "q": f"pub_id:{TARGET_NUMBER}",
        "columns": ["app_doc_id", "pub_id", "title", "ipcs"],
        "limit": 10
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {'error': str(e), 'details': getattr(e, 'response', None)}


def main():
    """
    全ての検索方法を実行
    """
    print("=" * 80)
    print("PatentField API 出願番号検索方法 網羅的検証")
    print("=" * 80)
    print(f"\nテスト対象: {TARGET_NUMBER}")
    print(f"期待されるタイトル: インクジェットプリントヘッド前面用の熱安定性疎油性低接着コーティング")
    print(f"期待されるキーワード: {', '.join(EXPECTED_KEYWORDS)}")

    # 全メソッドを実行
    methods = [
        ("方法1: numbers + app_id + EPODOC形式（現在の実装）", method_1_numbers_app_id_epodoc),
        ("方法2: numbers + app_id + 種別コード付き", method_2_numbers_app_id_with_kind),
        ("方法3: numbers + pub_id + EPODOC形式", method_3_numbers_pub_id_epodoc),
        ("方法4: numbers + pub_id + 種別コード付き", method_4_numbers_pub_id_with_kind),
        ("方法5: numbers（タイプなし）+ EPODOC形式", method_5_numbers_no_type_epodoc),
        ("方法6: numbers（タイプなし）+ 種別コード付き", method_6_numbers_no_type_with_kind),
        ("方法7: expert検索 + app_doc_id:", method_7_expert_app_doc_id),
        ("方法8: fulltext検索", method_8_fulltext_search),
        ("方法9: expert検索 + pub_id:", method_9_expert_pub_id),
    ]

    results_summary = []

    for method_name, method_func in methods:
        result = method_func()
        check_result(result, method_name)

        # サマリー用に結果を保存
        if result.get('error'):
            results_summary.append({
                'method': method_name,
                'status': 'ERROR',
                'correct': False
            })
        else:
            n_hits = result.get('n_hits', 0)
            if n_hits > 0:
                record = result['records'][0]
                title = record.get('title', '')
                matched = [kw for kw in EXPECTED_KEYWORDS if kw in title]
                is_correct = len(matched) / len(EXPECTED_KEYWORDS) >= 0.75

                results_summary.append({
                    'method': method_name,
                    'status': 'SUCCESS',
                    'hits': n_hits,
                    'correct': is_correct,
                    'match_rate': f"{len(matched)}/{len(EXPECTED_KEYWORDS)}"
                })
            else:
                results_summary.append({
                    'method': method_name,
                    'status': 'NO_RESULTS',
                    'correct': False
                })

    # 最終サマリー
    print("\n\n" + "=" * 80)
    print("検証結果サマリー")
    print("=" * 80)

    for i, summary in enumerate(results_summary, 1):
        method = summary['method']
        status = summary['status']
        correct = summary['correct']

        if status == 'ERROR':
            print(f"{i}. {method}")
            print(f"   ❌ エラー発生")
        elif status == 'NO_RESULTS':
            print(f"{i}. {method}")
            print(f"   ❌ 結果なし")
        else:
            hits = summary['hits']
            match_rate = summary['match_rate']
            icon = "✅" if correct else "❌"
            print(f"{i}. {method}")
            print(f"   {icon} ヒット: {hits}件, キーワードマッチ: {match_rate}")

    # 正しい方法の推奨
    print("\n" + "=" * 80)
    print("推奨される検索方法")
    print("=" * 80)

    correct_methods = [s for s in results_summary if s['correct']]
    if correct_methods:
        print("以下の方法で正しいインクジェット特許が取得できます:\n")
        for i, method in enumerate(correct_methods, 1):
            print(f"  {i}. {method['method']}")
    else:
        print("⚠️ どの方法でも正しいインクジェット特許が取得できませんでした。")
        print("   データベースに問題がある可能性があります。")


if __name__ == '__main__':
    main()
