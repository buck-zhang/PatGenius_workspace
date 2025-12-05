#!/usr/bin/env python3
"""
キーワードJSONに独立請求項フラグを追加するユーティリティ

独立請求項の判定ルール:
- 構成要素番号が '1a', '2a', '3a' などの場合、そのクレーム全体（1a, 1b, 1c...）を独立請求項とみなす
- より正確には、構成要素番号の数字部分でクレームを識別

使用方法:
  python add_independent_claim_flag.py --keywords <キーワードファイル> --output <出力ファイル>
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Set


def identify_independent_claims(keywords_data: Dict) -> Set[str]:
    """
    独立請求項を識別

    簡易ルール:
    - 各クレーム番号（1, 2, 3...）の最初の要素（1a, 2a, 3a...）を持つクレームを独立請求項とする
    - より正確には構成要件分割時の「独立請求項」情報を使うべき

    Args:
        keywords_data: キーワードデータ

    Returns:
        独立請求項のクレーム番号セット（例: {'1', '2', '6'}）
    """
    independent_claim_numbers = set()

    for item in keywords_data.get('keywords', []):
        element_id = item.get('構成要素番号', '')

        if not element_id:
            continue

        # 構成要素番号から数字部分を抽出（例: '1a' → '1', '2b' → '2'）
        claim_number = ''
        for ch in element_id:
            if ch.isdigit():
                claim_number += ch
            else:
                break

        if claim_number:
            independent_claim_numbers.add(claim_number)

    return independent_claim_numbers


def add_independent_flag(
    keywords_file: str,
    output_file: str,
    independent_claim_numbers: Set[str] = None
):
    """
    キーワードJSONに独立請求項フラグを追加

    Args:
        keywords_file: 入力キーワードJSONファイル
        output_file: 出力キーワードJSONファイル
        independent_claim_numbers: 独立請求項のクレーム番号セット（Noneなら自動判定）
    """
    # データ読み込み
    with open(keywords_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 独立請求項の判定
    if independent_claim_numbers is None:
        independent_claim_numbers = identify_independent_claims(data)

    print(f"独立請求項として識別されたクレーム番号: {sorted(independent_claim_numbers)}")

    # 各構成要素に独立請求項フラグを追加
    modified_count = 0

    for item in data.get('keywords', []):
        element_id = item.get('構成要素番号', '')

        # クレーム番号を抽出
        claim_number = ''
        for ch in element_id:
            if ch.isdigit():
                claim_number += ch
            else:
                break

        # 独立請求項フラグを設定
        is_independent = claim_number in independent_claim_numbers
        item['独立請求項'] = is_independent

        if is_independent:
            modified_count += 1

    print(f"独立請求項フラグを追加: {modified_count}個の構成要素")

    # ファイル出力
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"結果を保存: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='キーワードJSONに独立請求項フラグを追加')
    parser.add_argument('--keywords', required=True, help='入力キーワードJSONファイル')
    parser.add_argument('--output', help='出力ファイル（指定しない場合は上書き）')
    parser.add_argument('--claims', help='独立請求項のクレーム番号（カンマ区切り、例: 1,2,6）')

    args = parser.parse_args()

    # 出力ファイル名
    output_file = args.output if args.output else args.keywords

    # 独立請求項の指定
    independent_claims = None
    if args.claims:
        independent_claims = set(args.claims.split(','))
        print(f"指定された独立請求項: {independent_claims}")

    # フラグ追加実行
    add_independent_flag(
        keywords_file=args.keywords,
        output_file=output_file,
        independent_claim_numbers=independent_claims
    )

    print("\n完了！")


if __name__ == '__main__':
    main()
