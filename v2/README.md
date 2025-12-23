# PatGenius

**特許検索・分析システム - AI駆動型先行技術調査プラットフォーム**

[![License](https://img.shields.io/badge/license-Proprietary-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)

## 概要

PatGeniusは、Claude Sonnet 4.5とGemini 3.0 Proを活用した、特許審査官向けの高度な先行技術調査システムです。特許の構成要件を自動分割し、PatentField APIで検索、新規性・進歩性を判断して拒絶理由通知書を生成します。

### 主な機能

1. 📋 **構成分割**: Claude Sonnet 4.5による高精度な構成要件分割
2. 🔍 **キーワード抽出**: 3階層（ドンピシャ/上位概念/下位概念）キーワード生成
3. 🏷️ **分類コード抽出**: FI/IPC/CPC分類コードの自動抽出
4. 🔎 **適応的検索**: 構成要素ごとの最適化された特許検索
5. 🤖 **新規性進歩性判断**: Gemini 3.0 ProによるX/Y文献摘出
6. 📊 **構成対比表作成**: Excel形式での詳細な対比表生成
7. 📝 **拒絶理由通知作成**: 審査官視点の通知書自動生成

## プロジェクト構造（モノレポ）

```
PatGenius/
├── apps/
│   ├── backend/                  # FastAPIバックエンド（特許分析パイプライン）
│   ├── classification-search/    # ベクトル検索API（FI/IPC/CPC）
│   └── web/                      # Next.js フロントエンド（準備中）
├── packages/                     # 共有パッケージ
│   ├── shared-types/             # 共有型定義
│   └── config/                   # 共有設定
├── data/                         # データディレクトリ
│   ├── test_data/                # テスト用データ
│   ├── test_results/             # テスト結果
│   └── reference_data/           # 参照データ
├── credentials/                  # 認証情報（.gitignore）
└── docs/                         # ドキュメント
```

## クイックスタート

### 前提条件

- **Python**: 3.10以上
- **Node.js**: 18以上
- **pnpm**: 8以上
- **Docker**: 最新版（Qdrant用）

### 1. リポジトリのクローン

```bash
git clone https://github.com/buck-zhang/PatGenius.git
cd PatGenius
```

### 2. 認証情報の設定

```bash
# .env.templateをコピー
cp credentials/.env.template credentials/.env

# 認証ファイルを配置
cp /path/to/google_credentials.json credentials/
cp /path/to/patentfield_key.json credentials/

# .envを編集して API キーを設定
nano credentials/.env
```

### 3. バックエンドのセットアップ

```bash
cd apps/backend

# 仮想環境の作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存パッケージのインストール
pip install -r requirements.txt
```

### 4. 分類検索APIのセットアップ

```bash
cd apps/classification-search

# Qdrantの起動
docker-compose up -d

# 仮想環境がない場合は作成
python -m venv venv
source venv/bin/activate

# 依存パッケージのインストール
pip install -r requirements.txt

# データのインジェスト（初回のみ）
python scripts/ingest_data.py --batch-size 500
```

### 5. 開発サーバーの起動

#### バックエンド
```bash
cd apps/backend
python -m uvicorn app.main:app --reload --port 8000
```

APIドキュメント: http://localhost:8000/api/docs

#### 分類検索API
```bash
cd apps/classification-search
python -m app.main
```

APIドキュメント: http://localhost:8001/docs

### 6. テスト実行

```bash
# E2Eテスト（上位3件）
cd apps/backend
python tests/e2e/end_to_end_test.py \
  --csv ../../data/test_data/combined_data.csv \
  --limit 3
```

## 技術スタック

### バックエンド
- **Framework**: FastAPI 0.115+
- **AI Models**:
  - Claude Sonnet 4.5 (Vertex AI) - 構成分割、キーワード抽出、拒絶理由生成
  - Gemini 3.0 Pro - 新規性進歩性判断
- **APIs**:
  - PatentField API - 特許検索
  - Qdrant - ベクトルデータベース
- **Python**: 3.10+

### フロントエンド（準備中）
- **Framework**: Next.js 15
- **UI Library**: shadcn/ui + Tailwind CSS
- **Type Safety**: End-to-End TypeScript (OpenAPI自動生成)
- **Build Tool**: Turbo

### 分類検索API
- **Framework**: FastAPI
- **Vector DB**: Qdrant
- **Embeddings**:
  - テキスト: sentence-transformers (multilingual-mpnet)
  - 画像: CLIP (vit-base-patch32)

## パフォーマンス

### Test #1 (JP2013224028A) の実績

| 指標 | 値 |
|-----|-----|
| 処理時間 | 17.5分 |
| トークン数 | 147,342 tokens |
| コスト | ¥191 |
| 検索結果 | 627件（重複削除後） |
| 紐づき特許検出 | ✅ 成功 |

### 最適化機能

- ⚡ AsyncIO完全移行（40-50%高速化）
- 💾 Claude Prompt Caching（コスト90%削減）
- 🔄 PatentField API並列化（20-30%高速化）
- 🚀 Turboによるビルドキャッシュ

## ドキュメント

- [Backend README](apps/backend/README.md) - バックエンドAPI詳細
- [Classification Search README](apps/classification-search/README.md) - 分類検索API詳細
- [構成要件分割ガイド](docs/guides/特許検索のための構成要件分割ガイド.md) - 構成分割の指針
- [API仕様書](http://localhost:8000/api/docs) - OpenAPI/Swagger UI

## 開発

### モノレポ管理

```bash
# 全アプリの開発サーバーを起動
pnpm dev

# 個別起動
pnpm dev:backend
pnpm dev:classification
pnpm dev:web

# ビルド
pnpm build

# テスト
pnpm test
```

### API型定義の自動生成

```bash
# バックエンドからTypeScript型を自動生成
pnpm generate-api
```

## ライセンス

Proprietary - All Rights Reserved

## サポート

技術的な質問や問題報告は、プロジェクトリーダーまでお問い合わせください。

---

**最終更新**: 2025年12月23日
**バージョン**: 2.0.0
**ステータス**: モノレポ構造への移行完了
