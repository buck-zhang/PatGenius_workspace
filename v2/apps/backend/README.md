# PatGenius Backend

特許検索・分析システムのバックエンドAPI

## 概要

FastAPIベースの特許分析APIサーバー。7つの主要処理ステップを提供：

1. **構成分割**: 特許請求項を構成要件に分割
2. **キーワード抽出**: 検索用キーワードを3階層で抽出
3. **分類コード抽出**: FI/IPC/CPC分類コードを抽出
4. **検索実行**: PatentField APIで特許検索
5. **新規性進歩性判断**: Gemini 3.0 Proで判断
6. **構成対比表作成**: Excel形式で対比表生成
7. **拒絶理由通知作成**: 審査官視点の通知書生成

## セットアップ

### 1. 仮想環境の作成

```bash
cd apps/backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 2. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 3. 環境変数の設定

```bash
# ルートの credentials/.env を編集
# または、環境変数を直接設定
export GOOGLE_CREDENTIALS_PATH=../../credentials/google_credentials.json
export PATENTFIELD_KEY_PATH=../../credentials/patentfield_key.json
```

### 4. サーバーの起動

```bash
# 開発モード（自動リロード）
python -m uvicorn app.main:app --reload --port 8000

# または
python app/main.py
```

## APIドキュメント

サーバー起動後:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc
- OpenAPI JSON: http://localhost:8000/api/openapi.json

## ディレクトリ構造

```
app/
├── main.py                 # FastAPIアプリケーション
├── config.py               # 環境変数設定
├── api/
│   └── v1/
│       ├── endpoints/      # APIエンドポイント
│       └── router.py       # ルーター統合
├── core/                   # コア機能
│   ├── structure_analyzer.py
│   ├── keyword_extractor.py
│   ├── classification_extractor.py
│   ├── search_executor.py
│   ├── novelty_assessment.py
│   ├── comparison_generator.py
│   └── rejection_generator.py
├── services/               # 外部API統合
├── models/                 # Pydanticモデル
└── utils/                  # ユーティリティ

tests/
├── unit/                   # ユニットテスト
├── integration/            # 統合テスト
└── e2e/                    # E2Eテスト
```

## 既存CLIスクリプトの使用

FastAPI化後も、既存のコマンドラインスクリプトは引き続き使用可能です。

## 技術スタック

- **Framework**: FastAPI 0.115.0
- **AI Models**:
  - Claude Sonnet 4.5 (構成分割、キーワード、分類コード、拒絶理由)
  - Gemini 3.0 Pro (新規性進歩性判断)
- **APIs**:
  - PatentField API (特許検索)
  - Classification Search API (ベクトル検索)
- **Python**: 3.10+
