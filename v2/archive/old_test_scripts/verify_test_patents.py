#!/usr/bin/env python3
"""
テストケースの特許情報検証スクリプト
出願番号と公開番号の両方で検索し、正しい特許情報を取得
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

# テストケースの特許番号
test_cases = {
    'Test 1': {
        'syutugan': 'JP2013224028A',
        'himotuki': 'JP2012040876A'
    },
    'Test 2': {
        'syutugan': 'JP2014007731A',
        'himotuki': 'JP2011171723A'
    },
    'Test 3': {
        'syutugan': 'JP2014037831A',
        'himotuki': 'JP2012145109A'
    }
}

for test_name, patents in test_cases.items():
    print('\n' + '='*80)
    print(test_name)
    print('='*80)

    for label, patent_id in patents.items():
        found = False

        # EPODOC形式に変換（末尾の種別コードを削除）
        epodoc_id = patent_id.rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ')

        # app_idとpub_idの両方で試す
        for id_type in ['app_id', 'pub_id']:
            payload = {
                'numbers': [
                    {
                        'n': epodoc_id,  # EPODOC形式を使用
                        't': id_type
                    }
                ],
                'columns': [
                    'app_doc_id',
                    'pub_id',
                    'title',
                    'applicants',
                    'ipcs',
                    'app_claims'
                ]
            }

            try:
                response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                data = response.json()

                if data.get('n_hits', 0) > 0:
                    record = data['records'][0]

                    print(f'\n【{label} - {patent_id} (検索type={id_type})】')
                    print(f'  app_doc_id: {record.get("app_doc_id", "N/A")}')
                    print(f'  pub_id: {record.get("pub_id", "N/A")}')
                    print(f'  exam_id: {record.get("exam_id", "N/A")}')
                    print(f'  発明の名称: {record.get("title", "N/A")}')

                    # 出願人情報
                    applicants = record.get('applicants', [])
                    if applicants:
                        print(f'  出願人:')
                        for app in applicants[:3]:
                            print(f'    - {app}')
                    else:
                        print(f'  出願人: {record.get("applicant", "N/A")}')

                    # IPC分類
                    ipcs = record.get('ipcs', [])
                    if ipcs:
                        print(f'  IPC分類（最初の5件）: {ipcs[:5]}')

                    found = True
                    break

            except Exception as e:
                continue

        if not found:
            print(f'\n【{label} - {patent_id}】')
            print(f'  ✗ app_id/pub_id両方で取得失敗')
