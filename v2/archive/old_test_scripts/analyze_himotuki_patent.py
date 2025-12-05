#!/usr/bin/env python3
"""
Himotuki特許分類コード分析ツール

himotuki特許の実際の分類コードを取得し、
出願特許から抽出された分類コードと比較して
マッチング問題を特定します。
"""

import json
import sys
import requests
from pathlib import Path
from typing import Dict, List, Set


def fetch_patent_classifications(patent_id: str, pf_api_key: str, pf_endpoint: str) -> Dict:
    """
    PatentField APIから特許の分類コードを取得

    Args:
        patent_id: 特許番号（pub_id）
        pf_api_key: PatentField APIキー
        pf_endpoint: PatentField APIエンドポイント

    Returns:
        分類コード辞書
    """
    # まず検索APIでpub_idを検索（基本情報のみ）
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {pf_api_key}'
    }

    payload = {
        "search_type": "expert",
        "q": f"pub_id:{patent_id}",
        "columns": ["pub_id", "app_doc_id", "title"],
        "limit": 1
    }

    try:
        response = requests.post(
            pf_endpoint,
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()

        data = response.json()

        if data.get('n_hits', 0) == 0:
            print(f"✗ 特許が見つかりません: {patent_id}")
            return {}

        record = data['records'][0]

        # 次に、詳細データエンドポイントで分類コードを取得
        base_url = pf_endpoint.replace('/patents/search', '')
        detail_url = f"{base_url}/patents/{patent_id}"

        detail_response = requests.get(
            detail_url,
            headers={'Authorization': f'Bearer {pf_api_key}'},
            timeout=30
        )
        detail_response.raise_for_status()

        detail_data = detail_response.json()

        # 分類コードを抽出
        return {
            'pub_id': record.get('pub_id', ''),
            'app_doc_id': record.get('app_doc_id', ''),
            'title': record.get('title', ''),
            'FI': detail_data.get('fi_codes', []),
            'Fterm': detail_data.get('fterm_codes', []),
            'IPC': detail_data.get('ipc_codes', []),
            'CPC': detail_data.get('cpc_codes', [])
        }

    except requests.exceptions.HTTPError as e:
        print(f"✗ HTTPエラー: {e}")
        if e.response.status_code == 404:
            print(f"  特許データが見つかりません: {patent_id}")
        else:
            print(f"  レスポンス: {e.response.text[:500]}")
        return {}
    except Exception as e:
        print(f"✗ エラー: {e}")
        import traceback
        traceback.print_exc()
        return {}


def analyze_classification_overlap(
    himotuki_classifications: Dict,
    syutugan_classifications: Dict
) -> Dict:
    """
    分類コードの重複を分析

    Args:
        himotuki_classifications: himotuki特許の分類コード
        syutugan_classifications: 出願特許から抽出された分類コード

    Returns:
        分析結果辞書
    """
    analysis = {}

    for class_type in ['FI', 'Fterm', 'IPC', 'CPC']:
        himotuki_codes = set(himotuki_classifications.get(class_type, []))

        # 出願特許の分類コード（ドンピシャ、上位概念、下位概念を全て含む）
        syutugan_codes = set()
        for concept_level in ['ドンピシャ', '上位概念', '下位概念']:
            level_data = syutugan_classifications.get('classifications', {}).get(class_type, {}).get(concept_level, [])
            for item in level_data:
                if isinstance(item, dict):
                    syutugan_codes.add(item.get('code', ''))
                else:
                    syutugan_codes.add(item)

        # 完全一致
        exact_matches = himotuki_codes & syutugan_codes

        # 部分一致（階層的マッチング）
        partial_matches = set()
        for h_code in himotuki_codes:
            for s_code in syutugan_codes:
                # 階層的マッチング（前方一致）
                if h_code.startswith(s_code) or s_code.startswith(h_code):
                    partial_matches.add((h_code, s_code))

        analysis[class_type] = {
            'himotuki_count': len(himotuki_codes),
            'syutugan_count': len(syutugan_codes),
            'exact_matches': list(exact_matches),
            'exact_match_count': len(exact_matches),
            'partial_matches': [
                {'himotuki': h, 'syutugan': s}
                for h, s in sorted(partial_matches)
            ],
            'partial_match_count': len(partial_matches),
            'himotuki_only': list(himotuki_codes - syutugan_codes),
            'syutugan_only': list(syutugan_codes - himotuki_codes)
        }

    return analysis


def print_analysis_report(
    himotuki_id: str,
    syutugan_id: str,
    himotuki_data: Dict,
    syutugan_data: Dict,
    analysis: Dict
):
    """
    分析レポートを出力
    """
    print("\n" + "="*80)
    print("Himotuki特許分類コード分析レポート")
    print("="*80)

    print(f"\nHimotuki特許: {himotuki_id}")
    print(f"  Title: {himotuki_data.get('title', 'N/A')[:80]}...")
    print(f"  App Doc ID: {himotuki_data.get('app_doc_id', 'N/A')}")

    print(f"\n出願特許: {syutugan_id}")
    print(f"  Title: {syutugan_data.get('title', 'N/A')[:80]}...")

    print("\n" + "-"*80)
    print("分類コード重複分析")
    print("-"*80)

    total_exact = 0
    total_partial = 0

    for class_type in ['IPC', 'FI', 'Fterm', 'CPC']:
        stats = analysis.get(class_type, {})

        print(f"\n【{class_type}】")
        print(f"  Himotuki特許: {stats.get('himotuki_count', 0)}件")
        print(f"  出願特許（抽出）: {stats.get('syutugan_count', 0)}件")
        print(f"  完全一致: {stats.get('exact_match_count', 0)}件")
        print(f"  部分一致: {stats.get('partial_match_count', 0)}件")

        total_exact += stats.get('exact_match_count', 0)
        total_partial += stats.get('partial_match_count', 0)

        # 完全一致の詳細
        if stats.get('exact_matches'):
            print(f"\n  [完全一致コード]")
            for code in stats['exact_matches'][:10]:
                print(f"    ✓ {code}")
            if len(stats['exact_matches']) > 10:
                print(f"    ... 他{len(stats['exact_matches']) - 10}件")

        # 部分一致の詳細
        if stats.get('partial_matches'):
            print(f"\n  [部分一致コード]")
            for match in stats['partial_matches'][:5]:
                print(f"    ~ Himotuki: {match['himotuki']} ⟷ 出願: {match['syutugan']}")
            if len(stats['partial_matches']) > 5:
                print(f"    ... 他{len(stats['partial_matches']) - 5}件")

        # Himotuki特許のみの分類コード
        if stats.get('himotuki_only'):
            print(f"\n  [Himotuki特許のみ（マッチなし）: {len(stats['himotuki_only'])}件]")
            for code in stats['himotuki_only'][:10]:
                print(f"    ✗ {code}")
            if len(stats['himotuki_only']) > 10:
                print(f"    ... 他{len(stats['himotuki_only']) - 10}件")

    print("\n" + "="*80)
    print("総合分析")
    print("="*80)
    print(f"  完全一致合計: {total_exact}件")
    print(f"  部分一致合計: {total_partial}件")

    if total_exact == 0 and total_partial == 0:
        print("\n  ⚠️ 警告: 分類コードの重複が全くありません！")
        print("  → Himotuki特許と出願特許の技術的関連性が分類コードから見えていません")
        print("  → 分類コード以外の検索手法（キーワードのみ、全文検索など）が必要です")
    elif total_exact < 5:
        print("\n  ⚠️ 注意: 分類コードの重複が非常に少ないです")
        print("  → 分類コードベースの検索では発見が困難です")
        print("  → キーワード検索の重要性が高まります")
    else:
        print("\n  ✓ 分類コードに一定の重複があります")
        print("  → 分類コードベースの検索で発見可能な可能性があります")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Himotuki特許分類コード分析ツール'
    )
    parser.add_argument(
        'himotuki_id',
        help='Himotuki特許番号（例: JP2012040876A）'
    )
    parser.add_argument(
        'syutugan_classification_file',
        help='出願特許の分類コードJSONファイル'
    )
    parser.add_argument(
        '--patentfield-key',
        default='../patentfield_key.json',
        help='PatentField APIキーファイル'
    )

    args = parser.parse_args()

    # PatentField API設定読み込み
    try:
        with open(args.patentfield_key, 'r') as f:
            pf_config = json.load(f)
            pf_api_key = pf_config['PATENTFIELD_API_KEY']
            pf_endpoint = pf_config['endpoint']
    except Exception as e:
        print(f"エラー: PatentField API設定の読み込みに失敗: {e}", file=sys.stderr)
        sys.exit(1)

    # 出願特許の分類コード読み込み
    try:
        with open(args.syutugan_classification_file, 'r', encoding='utf-8') as f:
            syutugan_data = json.load(f)
    except Exception as e:
        print(f"エラー: 出願特許分類コードの読み込みに失敗: {e}", file=sys.stderr)
        sys.exit(1)

    # Himotuki特許の分類コード取得
    print(f"\nHimotuki特許の分類コードを取得中: {args.himotuki_id}")
    himotuki_data = fetch_patent_classifications(
        args.himotuki_id,
        pf_api_key,
        pf_endpoint
    )

    if not himotuki_data:
        print("エラー: Himotuki特許の取得に失敗しました", file=sys.stderr)
        sys.exit(1)

    print(f"✓ Himotuki特許取得完了")
    print(f"  Title: {himotuki_data.get('title', 'N/A')[:80]}...")
    print(f"  FI: {len(himotuki_data.get('FI', []))}件")
    print(f"  Fterm: {len(himotuki_data.get('Fterm', []))}件")
    print(f"  IPC: {len(himotuki_data.get('IPC', []))}件")
    print(f"  CPC: {len(himotuki_data.get('CPC', []))}件")

    # 分析実行
    analysis = analyze_classification_overlap(
        himotuki_data,
        syutugan_data
    )

    # レポート出力
    syutugan_id = Path(args.syutugan_classification_file).stem.split('_')[0]
    print_analysis_report(
        args.himotuki_id,
        syutugan_id,
        himotuki_data,
        syutugan_data,
        analysis
    )

    # 結果をJSONで保存
    output_file = f"{args.himotuki_id}_vs_{syutugan_id}_analysis.json"
    result = {
        'himotuki_patent': himotuki_data,
        'syutugan_patent': {
            'pub_id': syutugan_id,
            'classifications': syutugan_data.get('classifications', {})
        },
        'analysis': analysis
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 分析結果を保存: {output_file}")


if __name__ == '__main__':
    main()
