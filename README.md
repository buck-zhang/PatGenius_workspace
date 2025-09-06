# 🔍 PatGenius - 日本特許検索システム

**30,002件の日本特許データを対象としたエンタープライズ級検索エンジン**

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://docker.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![OpenSearch](https://img.shields.io/badge/OpenSearch-2.11.1-orange?logo=opensearch)](https://opensearch.org)
[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)](https://python.org)

## 🚀 **クイックスタート（Docker）**

```bash
# 1. リポジトリクローン
git clone https://github.com/buck-zhang/PatGenius.git
cd PatGenius

# 2. 開発環境で起動（推奨）
./scripts/deploy.sh dev

# 3. APIアクセス
open http://localhost:8000/docs
```

**わずか3コマンドで本格的な特許検索システムが起動！**

## 🎯 **システム概要**

PatGeniusは、日本特許庁の特許XMLデータをOpenSearchに効率的にインポートし、FastAPIによる高速検索・分析機能を提供するコンテナ化されたエンタープライズシステムです。

### **🌟 主要機能**
- 🔍 **30,002件の特許データ** - 完全インデックス済み
- ⚡ **15フィールド高速検索** - 発明名称から技術内容まで包括的検索  
- 🔧 **高度検索機能** - 近傍検索、ブール検索、クエリ文字列、マルチフィールド対応
- 🚀 **183.0ファイル/秒** - 高速一括処理性能
- 🐳 **Docker完全対応** - ワンコマンドデプロイメント
- 📡 **RESTful API** - OpenAPI 3.0準拠、Swagger UI自動生成
- 🌐 **Web検索デモ** - インタラクティブ検索インターフェース（高度検索UI付き）
- 🔧 **本番環境対応** - Nginx、SSL、ヘルスチェック完備

## 🐳 **Dockerアーキテクチャ**

### **サービス構成**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Nginx       │────│   FastAPI       │────│   OpenSearch    │
│  (リバースプロキシ) │    │  (検索エンジン)    │    │   (データストア)   │
│   Port: 80/443  │    │   Port: 8000    │    │   Port: 9200    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                    ┌─────────────────┐
                    │   Dashboards    │
                    │   (Web UI)      │
                    │   Port: 5601    │
                    └─────────────────┘
```

### **🔧 プロジェクト構造**
```
📁 PatGenius/
├── 🐳 Dockerfile                      # FastAPI本番用コンテナ
├── 🐳 docker-compose.yml              # 開発環境構成
├── 🐳 docker-compose.production.yml   # 本番環境構成
├── 📋 requirements.txt                # Python依存関係
├── 📋 api_requirements.txt            # FastAPI依存関係
├── 🔍 patent_search_api.py            # FastAPI検索エンジン
├── 📊 bulk_import_patents.py          # 一括インポートエンジン
├── 🎨 search_demo.html                # Web検索デモ
├── 🧪 test_api.py                     # API総合テスト
├── 📁 scripts/
│   ├── 🐳 deploy.sh                   # 統合デプロイスクリプト
│   └── 🚀 start_api.sh                # API起動スクリプト
├── 📁 config/
│   ├── 🌐 nginx.conf                  # リバースプロキシ設定
│   ├── ⚙️ opensearch_dashboards.yml   # Dashboards設定
│   └── ⚙️ opensearch_tags_analysis.json # フィールド定義
└── 📁 docs/
    ├── 📋 api_examples.md             # API使用ガイド
    └── 📋 prompt.md                   # 開発プロンプト
```

### **📂 データ構造**
```
source_data/                        # 30,002件の特許XMLファイル
├── 0/JP2010000001A/text.txt       # 特許XML (バリカン式刈刃装置)
├── 0/JP2010000002A/text.txt       # 特許XML (燃料電池)
└── ...                            # 29,999件の特許データ
```

## 🚀 **使い方**

### **1. Docker環境構築（推奨）**

```bash
# 1. リポジトリクローン
git clone https://github.com/buck-zhang/PatGenius.git
cd PatGenius

# 2. 開発環境で起動
./scripts/deploy.sh dev

# 3. データインポート実行（オプション）
./scripts/deploy.sh import

# 4. サービス状態確認
./scripts/deploy.sh status
```

### **2. 本番環境デプロイ**

```bash
# 本番環境構成で起動（Nginx + API + OpenSearch）
./scripts/deploy.sh prod

# アクセス先
# API: http://localhost/api/docs
# 検索デモ: http://localhost/demo
# Dashboards: http://localhost/dashboards
```

### **3. データインポート**

```bash
# Docker環境での一括インポート
./scripts/deploy.sh import

# インポート結果確認
curl "localhost:9200/patents/_count"
```

### **4. 検索・API利用**

#### **REST API検索**
```bash
# 発明名称で検索
curl -X GET "localhost:9200/patents/_search" -H 'Content-Type: application/json' -d '{
  "query": {"match": {"invention_title": "画像形成装置"}}
}'

# 技術分野で検索
curl -X GET "localhost:9200/patents/_search" -H 'Content-Type: application/json' -d '{
  "query": {"match": {"technical_field": "電子写真"}}
}'

# 複合条件検索
curl -X GET "localhost:9200/patents/_search" -H 'Content-Type: application/json' -d '{
  "query": {
    "bool": {
      "must": [
        {"match": {"invention_title": "バリカン"}},
        {"match": {"technical_field": "刈刃"}}
      ]
    }
  }
}'
```

#### **Web UI検索**
ブラウザで http://localhost:5601 にアクセス

### **4. 検索API利用**

#### **API起動**
```bash
# APIサーバー起動
./scripts/start_api.sh

# または直接起動
python patent_search_api.py
```

#### **API検索例**
```bash
# シンプル検索
curl "http://localhost:8000/search?q=画像形成装置"

# フィールド指定検索
curl "http://localhost:8000/search?q=電子写真&field=technical_field"

# 高度検索（近傍検索例）
curl -X POST "http://localhost:8000/search/advanced" \
  -H "Content-Type: application/json" \
  -d '{
    "query_type": "proximity",
    "query": "車 near3 両",
    "field": "technical_field",
    "size": 10
  }'

# 高度検索（ブール検索例）
curl -X POST "http://localhost:8000/search/advanced" \
  -H "Content-Type: application/json" \
  -d '{
    "query_type": "boolean",
    "must_terms": ["現像剤"],
    "should_terms": ["トナー", "感光体"],
    "must_not_terms": ["レーザー"],
    "size": 10
  }'

# 文書詳細取得
curl "http://localhost:8000/document/2010000001"
```

#### **API管理画面**
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **API統計**: http://localhost:8000/stats

### **5. 検索実例デモ**

#### **コマンドライン検索デモ**
```bash
# 全検索パターンのデモ実行
python3 search_examples.py
```

#### **Webブラウザ検索デモ**
```bash
# HTMLデモページをブラウザで開く
open search_demo.html
# または直接ファイルパスでアクセス
```

#### **実際の検索例**
- **バリカン関連**: 23件の特許（バリカン式刈刃装置など）
- **画像形成装置**: 10,000件の特許（複写機・プリンター技術）
- **現像剤技術**: 10,000件の特許（電子写真プロセス）
- **電子写真分野**: 8,109件の特許（感光体・現像技術）
- **センサ技術**: 1,209件の特許（検出・制御技術）

## 🔧 **高度検索機能**

PatGeniusは様々な高度検索パターンに対応しています：

### **検索タイプ**

#### **📍 近傍検索（Proximity Search）**
特定の距離内でキーワードが出現する文書を検索
```bash
# API例：「車」と「両」が3語以内の距離で出現
curl -X POST "http://localhost:8000/search/advanced" \
  -H "Content-Type: application/json" \
  -d '{
    "query_type": "proximity",
    "query": "車 near3 両",
    "field": "technical_field"
  }'
```

#### **🔗 ブール検索（Boolean Search）**  
AND/OR/NOT条件を組み合わせた複雑な検索
```bash
# API例：(トナー OR 現像剤) AND プリンター NOT レーザー
curl -X POST "http://localhost:8000/search/advanced" \
  -H "Content-Type: application/json" \
  -d '{
    "query_type": "boolean",
    "should_terms": ["トナー", "現像剤"],
    "must_terms": ["プリンター"],
    "must_not_terms": ["レーザー"]
  }'
```

#### **📝 クエリ文字列検索（Query String）**
フィールド指定とブール演算子を組み合わせ
```bash
# API例：発明名称にトナー AND 技術分野に電子写真
curl -X POST "http://localhost:8000/search/advanced" \
  -H "Content-Type: application/json" \
  -d '{
    "query_type": "query_string", 
    "query": "invention_title:トナー AND technical_field:電子写真"
  }'
```

#### **🎯 マルチフィールド検索**
複数フィールドに異なるクエリを同時実行
```bash
# API例：複数フィールドでの条件指定
curl -X POST "http://localhost:8000/search/advanced" \
  -H "Content-Type: application/json" \
  -d '{
    "query_type": "multi_field",
    "field_queries": {
      "invention_title": "画像形成装置",
      "technical_field": "電子写真",
      "applicant_name": "キヤノン"
    }
  }'
```

### **Web UI高度検索**
- **検索デモ**: http://localhost:8000/demo または search_demo.html
- **高度検索ボタン**をクリックして詳細オプションを表示
- **使用方法ガイド**がUIに組み込まれています

## 📊 **検索可能フィールド**

| フィールド名 | 内容 | 例 |
|-------------|------|-----|
| `invention_title` | 発明名称 | "現像剤搬送装置" |
| `applicant_name` | 出願人名 | "京セラミタ株式会社" |
| `inventor_names` | 発明者名 | "遠藤 裕久" |
| `technical_field` | 技術分野 | "電子写真方式を利用した..." |
| `background_art` | 背景技術 | "従来、電子写真プロセス..." |
| `tech_problem` | 解決課題 | "しかしながら、従来技術では..." |
| `tech_solution` | 解決手段 | "本発明は、上記問題点に鑑み..." |
| `advantageous_effects` | 発明の効果 | "本発明の第１の構成によれば..." |
| `description` | 詳細説明 | "以下、図面を参照しながら..." |
| `claims` | 請求項 | "Claim 1: 現像剤を収容する筐体と..." |
| `abstract` | 要約 | "【課題】トナーを除去するための..." |
| `classification_ipc` | IPC分類 | ["G03G 15/08"] |
| `classification_national` | 国内分類 | ["G03G15/08 507D"] |
| `f_terms` | Fターム | ["2H073AA09", "2H073BA04"] |
| `document_id` | 文献番号 | "2010008759" |

## 📈 **パフォーマンス実績**

### **インポート性能**
- **データ量**: 30,002件の特許XML
- **処理時間**: 2.7分
- **処理速度**: 183.0ファイル/秒
- **成功率**: 100% (失敗0件)

### **検索性能**
- **インデックスサイズ**: 3シャード、1レプリカ
- **レスポンス時間**: < 100ms (典型的なクエリ)
- **同時接続**: 複数クライアント対応

## 🐳 **Docker デプロイメント**

### **クイックスタート**
```bash
# 1. リポジトリクローン
git clone https://github.com/buck-zhang/PatGenius.git
cd PatGenius

# 2. 開発環境起動
./scripts/deploy.sh dev

# 3. データインポート（オプション）
./scripts/deploy.sh import

# 4. アクセス
# API: http://localhost:8000/docs
# Dashboards: http://localhost:5601
```

### **本番環境デプロイ**
```bash
# 本番環境構成で起動（Nginx + API + OpenSearch）
./scripts/deploy.sh prod

# アクセス先
# API: http://localhost/api/docs
# 検索デモ: http://localhost/demo
# Dashboards: http://localhost/dashboards
```

### **デプロイスクリプト**
```bash
./scripts/deploy.sh [COMMAND] [OPTIONS]

# 主要コマンド:
dev      # 開発環境起動
prod     # 本番環境起動  
import   # データインポート
stop     # 全サービス停止
clean    # 全データ削除
logs     # ログ表示
status   # サービス状態確認
test     # APIテスト実行
```

## 🛠 **開発・運用**

### **APIテスト**
```bash
# API総合テスト実行
python test_api.py
# または
./scripts/deploy.sh test

# 個別テスト
curl http://localhost:8000/health
curl http://localhost:8000/stats
```

### **ログ確認**
```bash
# インポートログ
tail -f patent_import.log

# OpenSearchログ
docker logs opensearch-node

# APIログ（起動時に表示）
```

### **データメンテナンス**
```bash
# インデックス再作成
curl -X DELETE "localhost:9200/patents"
python3 bulk_import_patents.py

# クラスター健康状態確認
curl "localhost:9200/_cluster/health"
```

### **拡張方法**
1. `config/opensearch_tags_analysis.json` でフィールド追加
2. `bulk_import_patents.py` でパーサー更新
3. インデックス再作成・データ再投入

## 📋 **技術仕様**

### **バックエンド**
- **OpenSearch**: 2.11.1
- **Python**: 3.9+
- **FastAPI**: 0.104.1
- **解析エンジン**: Standard Analyzer (日本語対応)
- **データ形式**: Japanese Patent XML (JPO形式)
- **文字エンコーディング**: UTF-8

### **API仕様**
- **フレームワーク**: FastAPI + Uvicorn
- **ドキュメント**: OpenAPI 3.0 (Swagger UI)
- **レスポンス形式**: JSON
- **CORS**: 対応済み
- **認証**: 未実装（オープンアクセス）

## 🤝 **貢献**

1. Fork the repository
2. Create your feature branch
3. Commit your changes  
4. Push to the branch
5. Create a Pull Request

## 📄 **ライセンス**

本プロジェクトはMITライセンスの下で公開されています。

---

**PatGenius** - Powered by OpenSearch & 日本特許データ