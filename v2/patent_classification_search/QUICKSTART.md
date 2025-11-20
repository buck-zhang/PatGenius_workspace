# クイックスタートガイド

## 5分でシステムを起動

### ステップ 1: Qdrantを起動

```bash
cd /Users/ttdc-user/Desktop/patgenius/zhang_opera/v2/patent_classification_search

# Qdrant起動
docker-compose up -d

# 確認（数秒待つ）
curl http://localhost:6333/
```

### ステップ 2: Pythonパッケージをインストール

```bash
# 仮想環境作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# パッケージインストール（初回は数分かかります）
pip install -r requirements.txt
```

### ステップ 3: 環境変数の設定

```bash
# .envファイル作成
cp .env.example .env

# デフォルト設定で問題なければそのまま使用可能
```

### ステップ 4: データをインジェスト

```bash
# データ読み込み（10-30分）
python scripts/ingest_data.py --batch-size 500
```

進行状況が表示されます:
```
Loading classifications: 100%|██████████| 12345/12345 [10:23<00:00, 19.76it/s]
```

### ステップ 5: APIサーバーを起動

```bash
# APIサーバー起動
python -m patent_classification_search.api.main
```

起動メッセージ:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### ステップ 6: ブラウザで確認

以下のURLにアクセス:

- **APIドキュメント**: http://localhost:8000/docs
- **ヘルスチェック**: http://localhost:8000/health

### ステップ 7: テスト実行

別のターミナルで:

```bash
# テストスクリプト実行
python scripts/test_search.py
```

## 基本的な使い方

### 1. テキスト検索（Swagger UI使用）

1. http://localhost:8000/docs にアクセス
2. `POST /search/text` を展開
3. "Try it out" をクリック
4. 以下のJSONを入力:

```json
{
  "query": "農業用手工具",
  "limit": 10
}
```

5. "Execute" をクリック

### 2. curlで検索

```bash
curl -X POST "http://localhost:8000/search/text" \
  -H "Content-Type: application/json" \
  -d '{"query": "semiconductor", "limit": 5}'
```

### 3. Pythonで検索

```python
import requests

response = requests.post(
    "http://localhost:8000/search/text",
    json={"query": "通信装置", "limit": 10}
)

results = response.json()
for item in results["results"]:
    classification = item["classification"]
    score = item["similarity_score"]
    print(f"{classification['code']}: {classification['title_ja']} (score: {score:.2f})")
```

## よくある問題と解決方法

### Qdrantに接続できない

```bash
# Qdrantが起動しているか確認
docker ps | grep qdrant

# 起動していない場合
docker-compose up -d
```

### ポート8000が使用中

```bash
# .envファイルでポートを変更
echo "API_PORT=8001" >> .env

# APIを再起動
```

### モデルダウンロードが遅い

初回起動時、以下のモデルがダウンロードされます（合計 ~2GB）:

- `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (~1.1GB)
- `openai/clip-vit-base-patch32` (~600MB)

ネットワーク速度により5-15分かかることがあります。

### メモリ不足エラー

バッチサイズを削減:

```bash
python scripts/ingest_data.py --batch-size 100
```

## 次のステップ

- [README.md](README.md) で詳細な機能を確認
- [API Documentation](http://localhost:8000/docs) で全エンドポイントを試す
- Boolean検索（OR/AND）を使用
- 画像検索機能を試す

## サポート

問題が発生した場合は、ログを確認してください:

```bash
# APIログ（ターミナルに表示）
# Qdrantログ
docker logs <container_id>
```

Happy searching! 🔍
