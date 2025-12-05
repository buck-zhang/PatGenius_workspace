#!/usr/bin/env python3
"""
FI分類コードフィルタリング機能の検証スクリプト

Test #5で発生した0件問題を直接検証する。
キーワード抽出をスキップし、既知のFI分類コードで検索APIを直接呼び出す。
"""

import json
import requests
from typing import List, Tuple

# PatentField API設定
with open('../patentfield_key.json', 'r') as f:
    pf_config = json.load(f)
    PF_API_KEY = pf_config['PATENTFIELD_API_KEY']
    PF_ENDPOINT = pf_config['endpoint']

# Test #5の既知のFI分類コード（1a-2-1要素から抽出）
TEST_FI_CODES = [
    'G03B21/14A',
    'F21V9/16100',
    'F21V9/40200',
    'F21Y115:30',  # ← コロン表記の無効なコード
    'F21V9/35',
    'F21S8/10A',
    'G02B5/20',
    'G02B5/30',
    'H01L33/50',
    'H01L33/44',
    'F21V9/45',
    'F21V29/85',
    'F21V13/02',
    'G03B21/20',
    'G02B27/48'
]


def validate_fi_code(fi_code: str) -> bool:
    """
    FI分類コードのバリデーション

    PatentField APIで検索可能なFIコードかどうかを判定する。
    - コロン表記(':')を含むコードは無効（例: F21Y115:30）
    - 空文字列は無効

    Args:
        fi_code: FI分類コード

    Returns:
        True if valid, False otherwise
    """
    if not fi_code:
        return False

    # コロン表記を含むコードは無効（F21Yインデキシングコードなど）
    if ':' in fi_code:
        return False

    return True


def execute_search(query: str) -> Tuple[int, str]:
    """
    PatentField APIで検索実行

    Args:
        query: 検索式

    Returns:
        (ヒット件数, ステータス)
    """
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {PF_API_KEY}'
    }

    payload = {
        "search_type": "expert",
        "q": query,
        "columns": ["pub_id"],
        "limit": 300
    }

    try:
        response = requests.post(
            PF_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=60
        )

        if response.status_code == 400:
            return 0, f"400 Bad Request (無効な検索式)"

        response.raise_for_status()

        data = response.json()
        n_hits = data.get('n_hits', 0)

        return n_hits, "success"

    except requests.exceptions.HTTPError as e:
        return 0, f"HTTPエラー: {e}"
    except Exception as e:
        return 0, f"エラー: {e}"


def main():
    print("=" * 80)
    print("FI分類コードフィルタリング検証")
    print("=" * 80)
    print()

    # テスト1: 全てのFI分類コード（無効コード含む）
    print("[テスト1] 全てのFI分類コード（フィルタリングなし）")
    print("-" * 80)
    print(f"総コード数: {len(TEST_FI_CODES)}")

    all_codes_query = ' OR '.join([f'FI:{code}' for code in TEST_FI_CODES[:10]])
    print(f"検索式（最初の10件）: {all_codes_query[:150]}...")

    hits, status = execute_search(all_codes_query)
    print(f"結果: {hits}件")
    print(f"ステータス: {status}")
    print()

    # テスト2: バリデーション後のFI分類コード（無効コード除外）
    print("[テスト2] バリデーション後のFI分類コード（フィルタリング適用）")
    print("-" * 80)

    # 無効なコードを表示
    invalid_codes = [code for code in TEST_FI_CODES if not validate_fi_code(code)]
    print(f"除外される無効コード: {invalid_codes}")
    print()

    # 有効なコードのみでクエリ構築
    valid_codes = [code for code in TEST_FI_CODES if validate_fi_code(code)]
    print(f"有効なコード数: {len(valid_codes)}")

    valid_codes_query = ' OR '.join([f'FI:{code}' for code in valid_codes[:10]])
    print(f"検索式（最初の10件）: {valid_codes_query[:150]}...")

    hits, status = execute_search(valid_codes_query)
    print(f"結果: {hits}件")
    print(f"ステータス: {status}")
    print()

    # 結果の評価
    print("=" * 80)
    print("検証結果")
    print("=" * 80)

    if status == "success" and hits > 0:
        print("✅ フィルタリング機能は正常に動作しています")
        print(f"   - 無効なFI分類コード（{invalid_codes}）を除外")
        print(f"   - 有効なコードのみで検索実行 → {hits}件ヒット")
        print()
        print("【結論】Pattern 1（0件問題）の修正が成功しました")
        print("   Test #5, #8で0件だった原因が解決されました")
    else:
        print("❌ フィルタリング後も検索が失敗しています")
        print(f"   ステータス: {status}")
        print(f"   ヒット件数: {hits}")

    print("=" * 80)


if __name__ == '__main__':
    main()
