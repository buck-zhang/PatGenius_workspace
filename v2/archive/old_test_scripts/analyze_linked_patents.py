#!/usr/bin/env python3
"""
紐づき特許の分類コード・キーワード分析

4件の紐づき特許がなぜヒットしないのかを解析：
1. JP2011032263 - 感活性光線性樹脂組成物
2. JP2011191446 - 感活性光線性樹脂組成物
3. JP2012173419 - レジスト組成物
4. JP2012185472 - 感放射線性樹脂組成物
"""

import json
import requests
from pathlib import Path
from collections import Counter

def fetch_patent_details(api_key: str, endpoint: str, patent_id: str):
    """特許の詳細情報を取得"""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    # 基本情報 + 要約を取得（FI/IPCは別途取得）
    query = f'pub_id:{patent_id}'
    payload = {
        'search_type': 'expert',
        'q': query,
        'columns': ['pub_id', 'title', 'abstract', 'app_year'],
        'limit': 1
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get('n_hits', 0) > 0:
            record = data['records'][0]

            # FI/IPC分類を別途取得（全文APIを使用）
            base_url = endpoint.replace('/patents/search', '')
            full_url = f"{base_url}/patents/{patent_id}"

            full_response = requests.get(
                full_url,
                headers={'Authorization': f'Bearer {api_key}'},
                params={'id_type': 'pub_id'},
                timeout=30
            )

            if full_response.status_code == 200:
                full_data = full_response.json()
                record['FI'] = full_data.get('FI', [])
                record['IPC'] = full_data.get('IPC', [])
                record['Fterm'] = full_data.get('Fterm', [])
                record['claims'] = full_data.get('app_claims', full_data.get('grant_claims', ''))

            return record

        return None

    except Exception as e:
        print(f"エラー ({patent_id}): {e}")
        return None


def extract_keywords_from_text(text: str, max_keywords: int = 20):
    """テキストからキーワードを抽出（簡易版）"""
    # フォトレジスト関連の技術用語を抽出
    keywords = set()

    # よく使われる技術用語パターン
    patterns = [
        '樹脂', '組成物', 'レジスト', '感光', '露光', '現像',
        '酸', '発生剤', '不安定', '構造単位', '重合',
        'フッ素', '脂環', '炭化水素', 'アルキル', 'カルボニル',
        'スルホニウム', 'ヨードニウム', 'カチオン',
        'メタクリル', 'アクリル', 'ポリマー',
        '溶解', '抑制', '基板', 'パターン', '形成',
        '解像', '感度', 'コントラスト', 'ライン', '幅'
    ]

    for pattern in patterns:
        if pattern in text:
            keywords.add(pattern)

    # 式番号を抽出（例: 式(a4), 式(I)）
    import re
    formula_patterns = re.findall(r'式\([a-zA-Z0-9]+\)', text)
    keywords.update(formula_patterns[:10])

    return list(keywords)[:max_keywords]


def main():
    # API設定読み込み
    pf_key_path = Path('../patentfield_key.json')
    with open(pf_key_path, 'r') as f:
        pf_config = json.load(f)
        api_key = pf_config['PATENTFIELD_API_KEY']
        endpoint = pf_config['endpoint']

    # 本願特許と紐づき特許のリスト
    main_patent = 'JP2014089440'
    linked_patents = [
        'JP2011032263',
        'JP2011191446',
        'JP2012173419',
        'JP2012185472'
    ]

    print("="*80)
    print("紐づき特許の分類コード・キーワード分析")
    print("="*80)

    # 本願特許の情報を取得
    print(f"\n【本願特許】{main_patent}")
    print("-"*80)
    main_data = fetch_patent_details(api_key, endpoint, main_patent)

    if main_data:
        print(f"タイトル: {main_data.get('title', '')}")
        print(f"FI分類（上位10件）:")
        for i, fi in enumerate(main_data.get('FI', [])[:10], 1):
            print(f"  {i}. {fi}")

        main_keywords = extract_keywords_from_text(
            main_data.get('abstract', '') + main_data.get('claims', '')[:1000]
        )
        print(f"抽出キーワード: {', '.join(main_keywords[:15])}")

    # 紐づき特許の分析
    all_linked_data = []

    for patent_id in linked_patents:
        print(f"\n【紐づき特許】{patent_id}")
        print("-"*80)

        data = fetch_patent_details(api_key, endpoint, patent_id)

        if data:
            all_linked_data.append({
                'patent_id': patent_id,
                'data': data
            })

            print(f"タイトル: {data.get('title', '')}")
            print(f"FI分類（上位10件）:")
            for i, fi in enumerate(data.get('FI', [])[:10], 1):
                print(f"  {i}. {fi}")

            linked_keywords = extract_keywords_from_text(
                data.get('abstract', '') + data.get('claims', '')[:1000]
            )
            print(f"抽出キーワード: {', '.join(linked_keywords[:15])}")

    # 分類コードの比較分析
    print(f"\n\n" + "="*80)
    print("分類コード比較分析")
    print("="*80)

    if main_data and all_linked_data:
        main_fi_set = set(main_data.get('FI', []))
        main_fi_top3 = set([fi.split('/')[0] if '/' in fi else fi[:9]
                           for fi in list(main_fi_set)[:20]])  # 上位グループ

        print(f"\n本願特許のFI上位グループ: {', '.join(sorted(main_fi_top3)[:10])}")

        for linked in all_linked_data:
            patent_id = linked['patent_id']
            data = linked['data']
            linked_fi_set = set(data.get('FI', []))
            linked_fi_top3 = set([fi.split('/')[0] if '/' in fi else fi[:9]
                                 for fi in list(linked_fi_set)[:20]])

            # 共通FI
            common_fi = main_fi_set & linked_fi_set
            common_fi_groups = main_fi_top3 & linked_fi_top3

            print(f"\n{patent_id}:")
            print(f"  完全一致FI: {len(common_fi)}個")
            if common_fi:
                print(f"    例: {', '.join(list(common_fi)[:5])}")
            print(f"  グループ一致: {len(common_fi_groups)}個")
            if common_fi_groups:
                print(f"    {', '.join(sorted(common_fi_groups)[:5])}")

            # 紐づき特許のみにあるFI
            unique_fi = linked_fi_top3 - main_fi_top3
            if unique_fi:
                print(f"  紐づき特許固有のFIグループ: {', '.join(sorted(unique_fi)[:5])}")

    # 本願特許の検索条件を読み込み
    print(f"\n\n" + "="*80)
    print("本願特許の検索条件分析")
    print("="*80)

    classifications_file = Path('test_validation_classifications.json')
    keywords_file = Path('test_validation_keywords.json')

    if classifications_file.exists():
        with open(classifications_file, 'r', encoding='utf-8') as f:
            classifications = json.load(f)

        fi_codes = classifications.get('classifications', {}).get('FI', {})
        fi_donpisha = [item['code'] for item in fi_codes.get('ドンピシャ', [])]

        print(f"\n使用されたFI分類（ドンピシャ、上位10件）:")
        for i, code in enumerate(fi_donpisha[:10], 1):
            print(f"  {i}. {code}")

    if keywords_file.exists():
        with open(keywords_file, 'r', encoding='utf-8') as f:
            keywords_data = json.load(f)

        print(f"\n使用されたキーワード（各構成要素のドンピシャ、最初の5要素）:")
        for kw_item in keywords_data['keywords'][:5]:
            element_id = kw_item['構成要素番号']
            element = kw_item['構成要素'][:40]
            donpisha = [kw['keyword'] for kw in kw_item.get('ドンピシャキーワード_日本語', [])][:3]
            print(f"  {element_id} ({element}...): {', '.join(donpisha)}")

    # 結論
    print(f"\n\n" + "="*80)
    print("ヒットしない原因の分析")
    print("="*80)

    print("""
分析結果に基づく推定原因:

1. FI分類コードの詳細度の違い
   - 本願特許: G03F7/039601, G03F7/038601 など非常に詳細な分類
   - 紐づき特許: 同じG03F7系でも異なる下位分類の可能性

2. キーワードの特異性
   - 本願特許の検索キーワード: 式(a4), 式(a5), R4 など本願固有の記号
   - 紐づき特許: 異なる式番号や構造記号を使用

3. 検索式の厳密性
   - 現在の検索: (詳細FI) AND (固有キーワード)
   - この組み合わせは本願特許にピンポイントで当たるが、
     類似の技術を持つ他の特許は除外される

推奨される改善策:
1. FI分類の上位階層を使用 (G03F7. のワイルドカード検索)
2. 汎用的な技術キーワードを使用 (レジスト組成物、感放射線性など)
3. 検索式の緩和 (AND → OR の一部採用)
""")

    # 結果を保存
    output = {
        'main_patent': main_patent,
        'linked_patents': all_linked_data,
        'analysis_summary': {
            'total_linked': len(all_linked_data),
            'detection_rate': 0.0
        }
    }

    with open('linked_patents_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 分析結果を保存: linked_patents_analysis.json")


if __name__ == '__main__':
    main()
