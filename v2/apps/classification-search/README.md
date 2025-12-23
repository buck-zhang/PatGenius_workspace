# Patent Classification Search System v2.0

特許分類コード（IPC、CPC、FI）のためのRAG付き検索エンジン

## 概要

このシステムは、特許分類コードを検索可能なベクトルデータベースに格納し、FastAPI経由でアクセス可能にします。

### 主要機能

- ✅ **テキスト検索**: 自然言語クエリでセマンティック検索
- ✅ **コード検索**: 分類コードによる直接検索
- ✅ **Boolean検索**: OR/AND演算子による複合検索
- ✅ **画像検索**: CLIPを使用した画像ベース検索
- ✅ **マルチ分類サポート**: IPC、CPC、FI全対応

### 技術スタック

- **API**: FastAPI 0.115.0
- **ベクトルDB**: Qdrant 1.12.0
- **埋め込みモデル**:
  - テキスト: sentence-transformers (multilingual-mpnet)
  - 画像: CLIP (vit-base-patch32)
- **言語**: Python 3.10+

## セットアップ

### 1. 依存関係のインストール

```bash
# 仮想環境の作成（推奨）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存パッケージのインストール
pip install -r requirements.txt
```

### 2. Qdrantの起動

```bash
# Docker Composeを使用
docker-compose up -d

# Qdrantが起動したことを確認
curl http://localhost:6333/
```

### 3. 環境変数の設定

```bash
# .env.example をコピー
cp .env.example .env

# 必要に応じて .env を編集
```

### 4. データのインジェスト

```bash
# データを読み込んでQdrantに保存
python scripts/ingest_data.py --batch-size 500

# コレクションを再作成する場合
python scripts/ingest_data.py --batch-size 500 --recreate
```

処理時間の目安:
- IPC: ~660ファイル
- CPC: ~690ファイル
- FI: ~664ファイル
- 合計: 約10-30分（ハードウェアに依存）

### 5. APIサーバーの起動

```bash
# 開発モード（自動リロード有効）
cd patent_classification_search
python -m api.main

# または uvicorn 直接実行
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

APIドキュメント: http://localhost:8000/docs

## API使用例

### 1. テキスト検索

```bash
curl -X POST "http://localhost:8000/search/text" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "agricultural hand tools",
    "classification_type": "IPC",
    "limit": 10,
    "min_score": 0.5
  }'
```

### 2. コード検索

```bash
curl -X POST "http://localhost:8000/search/code" \
  -H "Content-Type: application/json" \
  -d '{
    "codes": ["A01B1/00", "H04L29/06"]
  }'
```

### 3. Boolean検索（OR）

```bash
curl -X POST "http://localhost:8000/search/boolean" \
  -H "Content-Type: application/json" \
  -d '{
    "queries": ["hand tools", "agricultural equipment"],
    "operator": "OR",
    "limit": 10
  }'
```

### 4. Boolean検索（AND）

```bash
curl -X POST "http://localhost:8000/search/boolean" \
  -H "Content-Type: application/json" \
  -d '{
    "queries": ["手工具", "農業"],
    "operator": "AND",
    "classification_type": "FI",
    "limit": 10
  }'
```

### 5. 画像検索

```bash
curl -X POST "http://localhost:8000/search/image" \
  -F "image=@/path/to/image.jpg" \
  -F "limit=10" \
  -F "classification_type=IPC"
```

### 6. ヘルスチェック

```bash
curl "http://localhost:8000/health"
```

### 7. 統計情報

```bash
curl "http://localhost:8000/health/stats"
```

## プロジェクト構造

```
patent_classification_search/
├── api/
│   ├── main.py              # FastAPIアプリケーション
│   ├── schemas.py           # Pydanticスキーマ
│   └── routes/
│       ├── search.py        # 検索エンドポイント
│       └── health.py        # ヘルスチェック
├── core/
│   ├── config.py            # 設定管理
│   ├── data_loader.py       # IPC/CPC/FIパーサー
│   ├── embeddings.py        # 埋め込みモデル
│   └── vector_store.py      # Qdrant操作
├── models/
│   └── patent_class.py      # データモデル
└── scripts/
    └── ingest_data.py       # データインジェスト
```

## データ形式

### IPC
```
A01B   1/00	7	手工具	Hand tools	1737
```

### CPC
```
A01B1/00	7	Hand tools	A01B1/00	A01B1/00	手工具	652
```

### FI
```
A01B   1/00  \	0	0	2B031	A01B   1/00	407	手工具	Hand tools
```

## クラウドデプロイ

### Docker化

```bash
# Dockerイメージのビルド
docker build -t patent-search-api .

# コンテナの実行
docker run -p 8000:8000 --env-file .env patent-search-api
```

### Kubernetes

```yaml
# 別途 k8s マニフェストを用意
kubectl apply -f k8s/deployment.yaml
```

## パフォーマンス最適化

### 推奨設定

1. **バッチサイズ**: 500-1000（メモリに応じて調整）
2. **ベクトル次元**: 768（multilingual-mpnet）
3. **Qdrantレプリカ**: 本番環境では3台以上推奨

### スケーリング

- **水平スケーリング**: FastAPIサーバーを複数起動（ロードバランサー経由）
- **Qdrantクラスター**: 大規模データ対応

## トラブルシューティング

### Qdrant接続エラー

```bash
# Qdrantが起動しているか確認
docker ps | grep qdrant

# ログ確認
docker logs <container_id>
```

### モデルダウンロードエラー

```bash
# 手動でモデルをダウンロード
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/paraphrase-multilingual-mpnet-base-v2')"
```

### メモリ不足

- バッチサイズを削減
- スワップメモリを有効化
- より小さい埋め込みモデルを使用

## ライセンス

MIT License

## 参考資料

- [JPO 特許分類](https://www.jpo.go.jp/cgi/cgi-bin/search-portal/narabe_tool/narabe.cgi)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Sentence Transformers](https://www.sbert.net/)
- [OpenAI CLIP](https://github.com/openai/CLIP)
