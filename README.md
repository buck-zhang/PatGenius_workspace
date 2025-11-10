# Zhang Opera - Patent Analysis & Search System

特許分類検索、Google Patents連携、AI構成要件分割を統合した特許分析システム

## 概要

このシステムは3つの主要機能を提供します：

1. **特許分類検索API** - IPC/CPC/FI分類のRAG対応検索システム
2. **Google Patents API** - Google Patentsのウェブスクレイピング検索
3. **特許構成要件分割** - Gemini AIによる特許文書の自動構成要件分割

## プロジェクト構造

```
zhang_opera/
├── src/                          # ソースコード
│   ├── api/                      # APIサーバー
│   │   ├── patent_classification_api.py    # 特許分類検索API
│   │   ├── google_patents_api.py           # Google Patents API
│   │   └── import_classification_data.py   # データインポートツール
│   └── core/                     # コアライブラリ
│       ├── patent_component_analyzer.py    # AI構成要件分割
│       ├── patent_search_engine.py         # 検索エンジン
│       └── google_patents_scraper.py       # Google Patentsスクレイパー
├── examples/                     # 使用例
│   ├── api_client_examples.py              # 分類API使用例
│   ├── google_patents_client_examples.py   # Google Patents API使用例
│   ├── example_usage.py                    # 構成要件分割の基本例
│   ├── search_sample.py                    # 統合検索サンプル
│   ├── run_patent_analysis.py              # 特許分析ワークフロー
│   └── demo_jp2014007731a_analysis.py      # 実特許分析デモ
├── tests/                        # テストファイル
│   ├── test_google_patents_search.py       # Google Patents統合テスト
│   ├── test_google_patents_basic.py        # Google Patents基本テスト
│   └── test_patent_analysis.py             # 特許分析テスト
├── docs/                         # ドキュメント
│   ├── README.md                           # 詳細README
│   ├── IMPLEMENTATION_SUMMARY.md           # 実装サマリー
│   ├── GOOGLE_PATENTS_README.md            # Google Patentsガイド
│   ├── GOOGLE_PATENTS_QUICKSTART.md        # クイックスタート
│   ├── PATENT_ANALYSIS_README.md           # 特許分析ガイド
│   ├── GCP_DEPLOYMENT.md                   # GCPデプロイガイド
│   ├── MONITORING.md                       # モニタリングガイド
│   ├── VERTEX_AI_MIGRATION.md              # Vertex AI移行ガイド
│   └── prompt.md                           # AIプロンプト集
├── scripts/                      # スクリプト
│   ├── start.sh                            # 分類APIサーバー起動
│   ├── start_google_patents_api.sh         # Google Patents API起動
│   ├── deploy_gcp.sh                       # GCPデプロイスクリプト
│   ├── monitor_import.sh                   # インポート監視
│   └── check_import_status.sh              # インポート状況確認
├── docker/                       # Docker設定
│   ├── Dockerfile                          # 分類API用Dockerfile
│   ├── Dockerfile.google-patents           # Google Patents API用
│   ├── docker-compose.yml                  # 開発環境
│   └── docker-compose.gcp.yml              # GCP本番環境
├── data_20250812/                # 特許分類データ（IPC/FI/CPC）
├── models/                       # AIモデルキャッシュ（.gitignore）
├── output/                       # 分析結果出力（.gitignore）
├── patents_pdf/                  # ダウンロード特許PDF（.gitignore）
├── requirements.txt              # メイン依存関係
├── requirements_patent_analysis.txt        # 特許分析用依存関係
├── client_requirements.txt       # クライアント用依存関係
├── .env.example                  # 環境変数テンプレート
└── .gitignore
```

## クイックスタート

### 1. 前提条件

- Docker & Docker Compose
- Python 3.11+
- 8GB+ RAM推奨
- Google Cloud Platform アカウント（特許分析機能使用時）

### 2. インストール

```bash
# リポジトリのクローン
git clone <repository-url>
cd zhang_opera

# 環境変数の設定
cp .env.example .env
# .envファイルを編集して必要な設定を追加

# Dockerコンテナの起動
docker-compose -f docker/docker-compose.yml up -d
```

### 3. データのインポート

```bash
# OpenSearchが起動するまで待つ（約30秒）
sleep 30

# 分類データをインポート
docker-compose -f docker/docker-compose.yml exec api python src/api/import_classification_data.py --data-dir /app/data_20250812
```

### 4. 動作確認

```bash
# 分類検索APIのヘルスチェック
curl http://localhost:8000/health

# Google Patents APIのヘルスチェック
curl http://localhost:8001/health

# サンプルコードの実行
pip install -r client_requirements.txt
python examples/api_client_examples.py
```

## 主要機能

### 1. 特許分類検索API (Port 8000)

IPC、CPC、FI分類データのRAG対応検索システム

- キーワード検索
- 意味検索（RAG）
- コード検索
- AND/OR条件による複合検索
- 日英バイリンガル対応

**ドキュメント**: `docs/README.md`

### 2. Google Patents API (Port 8001)

Google Patentsのウェブスクレイピング検索API

- キーワード検索
- 特許詳細取得
- PDF自動ダウンロード
- 分類コード検索
- 出願人・発明者検索

**ドキュメント**: `docs/GOOGLE_PATENTS_README.md`

### 3. 特許構成要件分割システム

Gemini AIを使用した特許文書の自動構成要件分割

- 特許請求の範囲の自動分割
- 構成要件の抽出
- JSON形式での出力
- 複数請求項の一括処理

**ドキュメント**: `docs/PATENT_ANALYSIS_README.md`

## 使用例

### 分類検索API

```python
from examples.api_client_examples import PatentClassificationClient

client = PatentClassificationClient(base_url="http://localhost:8000")

# キーワード検索
results = client.search_keyword("agriculture", top_k=10)

# 意味検索（RAG）
results = client.search_text("Methods for harvesting crops", top_k=5)

# 高度検索（AND条件）
results = client.search_advanced(
    keywords=["soil", "working"],
    condition="and",
    top_k=10
)
```

### Google Patents検索

```python
from examples.google_patents_client_examples import GooglePatentsClient

client = GooglePatentsClient(base_url="http://localhost:8001")

# 特許検索
results = client.search_patents("autonomous vehicle", max_results=10)

# 特許詳細取得
patent = client.get_patent_details("US10000000B2")

# PDF自動ダウンロード
pdf_path = client.download_patent_pdf("US10000000B2")
```

### 特許構成要件分割

```python
from src.core.patent_component_analyzer import PatentComponentAnalyzer

analyzer = PatentComponentAnalyzer()

# 特許テキストを分析
result = analyzer.analyze_patent_text(patent_text)

# 結果を保存
result.save_to_json("output/result.json")
result.save_readable("output/result.txt")
```

## 技術スタック

- **API Framework**: FastAPI
- **Search Engine**: OpenSearch with KNN Vector Search
- **RAG Model**: Sentence Transformers (paraphrase-multilingual-mpnet-base-v2)
- **AI Model**: Google Gemini 1.5 Flash (Vertex AI)
- **Web Scraping**: Selenium WebDriver
- **Containerization**: Docker & Docker Compose
- **Deployment**: Google Cloud Platform (Cloud Run, Vertex AI)

## API エンドポイント

### 分類検索API (Port 8000)

- `GET /health` - ヘルスチェック
- `GET /search/keyword` - キーワード検索
- `GET /search/text` - 意味検索（RAG）
- `POST /search` - 高度検索
- `GET /search/code/{type}/{code}` - コード検索

### Google Patents API (Port 8001)

- `GET /health` - ヘルスチェック
- `GET /search` - 特許検索
- `GET /patent/{patent_id}` - 特許詳細
- `GET /download/{patent_id}` - PDF取得

詳細は各ドキュメントを参照してください。

## 開発

### ローカル開発環境

```bash
# 依存関係のインストール
pip install -r requirements.txt

# OpenSearchを起動
docker-compose -f docker/docker-compose.yml up opensearch -d

# APIサーバーをローカルで起動
export OPENSEARCH_HOST=localhost
export OPENSEARCH_PORT=9200
python src/api/patent_classification_api.py
```

### テスト実行

```bash
# 全テストを実行
pytest tests/

# 特定のテストを実行
pytest tests/test_google_patents_basic.py
```

## デプロイ

### GCPへのデプロイ

```bash
# デプロイスクリプトを実行
bash scripts/deploy_gcp.sh
```

詳細は `docs/GCP_DEPLOYMENT.md` を参照してください。

## トラブルシューティング

### OpenSearchに接続できない

```bash
# ステータス確認
docker-compose -f docker/docker-compose.yml ps

# ログ確認
docker-compose -f docker/docker-compose.yml logs opensearch

# 再起動
docker-compose -f docker/docker-compose.yml restart opensearch
```

### メモリ不足

`docker/docker-compose.yml`のメモリ設定を調整してください：
```yaml
OPENSEARCH_JAVA_OPTS: "-Xms1g -Xmx1g"  # デフォルト: -Xms2g -Xmx2g
```

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## お問い合わせ

質問や問題がある場合は、GitHubのIssueを作成してください。

---

**詳細ドキュメント**:
- 分類検索API: `docs/README.md`
- Google Patents: `docs/GOOGLE_PATENTS_README.md`
- 特許分析: `docs/PATENT_ANALYSIS_README.md`
- GCPデプロイ: `docs/GCP_DEPLOYMENT.md`
