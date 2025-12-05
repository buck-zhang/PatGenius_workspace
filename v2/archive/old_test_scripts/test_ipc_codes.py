import requests
import json

with open('../patentfield_key.json', 'r') as f:
    config = json.load(f)
    api_key = config['PATENTFIELD_API_KEY']
    endpoint = config['endpoint']

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {api_key}'
}

# 下位概念IPCコードをテスト
test_codes = [
    'IPC:B41J2/01101',  # 5桁詳細コード
    'IPC:B41J2/1601',   # 4桁詳細コード
    'IPC:B41J31/06',    # 通常の詳細度
    'IPC:B41J2/01',     # 上位コード（比較用）
]

print("=== 下位概念IPCコードの有効性テスト ===\n")

for code in test_codes:
    query = code
    payload = {
        "search_type": "expert",
        "q": query,
        "columns": ["pub_id"],
        "limit": 10
    }
    
    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            hits = data.get('n_hits', 0)
            print(f"✓ {code:25s} → HTTP 200, {hits:6d}件ヒット")
        else:
            print(f"✗ {code:25s} → HTTP {response.status_code}")
    except Exception as e:
        print(f"✗ {code:25s} → エラー: {e}")
    
