# 特許分類検索システム (Patent Classification Search System)

RAG（Retrieval-Augmented Generation）機能を備えた特許分類検索API

## 概要 (Overview)

このシステムは、IPC、CPC、FI分類データを検索可能なRAG対応データベースとFast APIで提供します。

**主な機能:**
- IPC、CPC、FI分類の統合検索
- キーワード検索
- RAGベースの意味検索（semantic search）
- 画像検索（準備中）
- AND/OR条件による複合検索
- 日英バイリンガル対応

## システム構成 (System Architecture)

```
┌─────────────────┐
│   Client App    │
│  (Python/Web)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Fast API      │◄─── Sentence Transformers (RAG)
│   (Port 8000)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   OpenSearch    │
│   (Port 9200)   │◄─── KNN Vector Search
└─────────────────┘
```

## クイックスタート (Quick Start)

### 1. 前提条件 (Prerequisites)

- Docker & Docker Compose
- Python 3.11+
- 8GB+ RAM推奨

### 2. インストール (Installation)

```bash
# リポジトリのクローン
git clone <repository-url>
cd zhang_opera

# 環境設定ファイルのコピー
cp .env.example .env

# Dockerコンテナの起動
docker-compose up -d
```

### 3. データのインポート (Data Import)

```bash
# OpenSearchが起動するまで待つ（約30秒）
sleep 30

# データをインポート
docker-compose exec api python import_classification_data.py --data-dir /app/data_20250812
```

データのインポートには10-20分程度かかります。

### 4. APIの動作確認 (API Test)

```bash
# ヘルスチェック
curl http://localhost:8000/health

# 簡単な検索テスト
curl "http://localhost:8000/search/keyword?q=agriculture&top_k=5"
```

### 5. サンプルコードの実行 (Run Sample Code)

```bash
# Pythonの依存関係をインストール
pip install requests

# サンプルコードを実行
python api_client_examples.py
```

## API エンドポイント (API Endpoints)

### 1. ヘルスチェック (Health Check)

```http
GET /health
```

**レスポンス:**
```json
{
  "status": "healthy",
  "opensearch": "connected"
}
```

### 2. キーワード検索 (Keyword Search)

```http
GET /search/keyword?q={keyword}&classification_type={type}&top_k={n}
```

**パラメータ:**
- `q`: 検索キーワード（必須）
- `classification_type`: `ipc`, `cpc`, `fi`, `all`（デフォルト: `all`）
- `top_k`: 結果数（デフォルト: 20）

**例:**
```bash
curl "http://localhost:8000/search/keyword?q=agriculture&top_k=10"
```

### 3. 意味検索 (Semantic Search)

RAGを使用した意味検索

```http
GET /search/text?q={text}&classification_type={type}&top_k={n}
```

**パラメータ:**
- `q`: 検索テキスト（必須）
- `classification_type`: `ipc`, `cpc`, `fi`, `all`
- `top_k`: 結果数

**例:**
```bash
curl "http://localhost:8000/search/text?q=Methods+for+harvesting+crops&top_k=5"
```

### 4. 高度検索 (Advanced Search)

```http
POST /search
Content-Type: application/json
```

**リクエストボディ:**
```json
{
  "keywords": ["keyword1", "keyword2"],
  "text": "semantic search text",
  "ipc_codes": ["A01B", "A01C"],
  "cpc_codes": ["A01B1/00"],
  "fi_codes": ["A01B1/00"],
  "classification_types": ["ipc", "cpc", "fi"],
  "condition": "or",
  "top_k": 20,
  "use_semantic_search": true
}
```

**パラメータ説明:**
- `keywords`: キーワードリスト（オプション）
- `text`: 意味検索用テキスト（オプション）
- `ipc_codes`: IPCコードフィルタ（オプション）
- `cpc_codes`: CPCコードフィルタ（オプション）
- `fi_codes`: FIコードフィルタ（オプション）
- `classification_types`: 検索対象の分類タイプ
- `condition`: `"and"` または `"or"`（デフォルト: `"or"`）
- `top_k`: 結果数（1-100）
- `use_semantic_search`: RAG使用フラグ

**例: OR条件検索**
```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": ["agriculture", "farming"],
    "condition": "or",
    "top_k": 10
  }'
```

**例: AND条件検索**
```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": ["soil", "working"],
    "condition": "and",
    "top_k": 10
  }'
```

### 5. コード検索 (Code Lookup)

```http
GET /search/code/{classification_type}/{code}
```

**パラメータ:**
- `classification_type`: `ipc`, `cpc`, `fi`
- `code`: 分類コード

**例:**
```bash
curl "http://localhost:8000/search/code/ipc/A01B"
```

## Python クライアント使用例 (Python Client Examples)

### 基本的な使い方

```python
from api_client_examples import PatentClassificationClient

# クライアント初期化
client = PatentClassificationClient(base_url="http://localhost:8000")

# キーワード検索
results = client.search_keyword("agriculture", top_k=10)
client.print_results(results)

# 意味検索
results = client.search_text(
    "Methods for harvesting agricultural products",
    top_k=10
)
client.print_results(results)

# コード検索
result = client.get_by_code("A01B", "ipc")
print(result)
```

### 高度な検索

```python
# OR条件での複合検索
results = client.search_advanced(
    keywords=["agriculture", "farming"],
    text="crop harvesting methods",
    classification_types=["ipc"],
    condition="or",
    top_k=20,
    use_semantic_search=True
)

# AND条件での検索
results = client.search_advanced(
    keywords=["soil", "working", "agriculture"],
    condition="and",
    top_k=10
)

# コードフィルタ付き検索
results = client.search_advanced(
    text="harvesting equipment",
    ipc_codes=["A01D", "A01B"],
    condition="or",
    top_k=15
)
```

### 日本語検索

```python
# 日本語でのキーワード検索
results = client.search_keyword("農業", classification_type="fi", top_k=10)

# 日本語での意味検索
results = client.search_text(
    "農業における土壌処理の方法と装置",
    classification_type="all",
    top_k=10
)
```

## データ構造 (Data Structure)

### IPC (International Patent Classification)

- **code**: IPCコード
- **title_ja**: タイトル（日本語）
- **title_en**: タイトル（英語）
- **level**: 階層レベル
- **num_families**: 特許ファミリー数

### CPC (Cooperative Patent Classification)

- **code**: CPCコード
- **title_ja**: タイトル（日本語）
- **title_en**: タイトル（英語）
- **concordance**: 対応するIPC
- **ipc_part**: IPC部分
- **level**: 階層レベル
- **num_families**: 特許ファミリー数

### FI (File Index)

- **code**: FIコード
- **title_ja**: タイトル（日本語）
- **title_en**: タイトル（英語）
- **theme**: テーマ
- **concordance**: 対応するIPC
- **level**: 階層レベル
- **num_documents**: 文献数

## 技術仕様 (Technical Specifications)

### RAG (Retrieval-Augmented Generation)

- **埋め込みモデル**: `paraphrase-multilingual-mpnet-base-v2`
- **ベクトル次元**: 768
- **類似度計算**: Cosine similarity
- **インデックス**: HNSW (Hierarchical Navigable Small World)

### パフォーマンス

- **検索レスポンス**: 通常 50-200ms
- **ベクトル検索**: KNN with HNSW algorithm
- **スケーリング**: 水平スケーリング対応

## 開発ガイド (Development Guide)

### ローカル開発

```bash
# 依存関係のインストール
pip install -r requirements.txt

# OpenSearchを起動
docker-compose up opensearch -d

# APIをローカルで起動
export OPENSEARCH_HOST=localhost
export OPENSEARCH_PORT=9200
python patent_classification_api.py
```

### テスト

```bash
# APIテスト
curl http://localhost:8000/health

# サンプルコード実行
python api_client_examples.py
```

## トラブルシューティング (Troubleshooting)

### OpenSearchに接続できない

```bash
# OpenSearchのステータス確認
docker-compose ps

# ログ確認
docker-compose logs opensearch

# 再起動
docker-compose restart opensearch
```

### データのインポートに失敗

```bash
# OpenSearchのヘルスチェック
curl http://localhost:9200/_cluster/health

# インデックス確認
curl http://localhost:9200/_cat/indices?v

# インデックス削除（再インポート前）
curl -X DELETE http://localhost:9200/patent_classification_*
```

### メモリ不足

```bash
# docker-compose.ymlのメモリ設定を調整
# OPENSEARCH_JAVA_OPTS=-Xms2g -Xmx2g → -Xms1g -Xmx1g
```

## ライセンス (License)

このプロジェクトはMITライセンスの下で公開されています。

## お問い合わせ (Contact)

質問や問題がある場合は、Issueを作成してください。
