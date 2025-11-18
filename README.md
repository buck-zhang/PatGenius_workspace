# Zhang Opera - Patent Analysis & Search System

特許分類検索、Google Patents連携、AI構成要件分割を統合した特許分析システム

## プロジェクト構成

このリポジトリは2つのバージョンを含んでいます：

### v1/ - 安定版（保守モード）

現在の本番システムです。詳細は [`v1/README.md`](v1/README.md) を参照してください。

**主要機能**:
- 特許分類検索API（IPC/CPC/FI分類のRAG検索）
- Google Patents API（Webスクレイピング）
- 特許構成要件分割（Gemini AI使用）

### v2/ - 次世代版（開発中）

新しいアーキテクチャで開発中です。詳細は [`v2/README.md`](v2/README.md) を参照してください。

## クイックスタート

### v1（安定版）の使用

```bash
cd v1
# v1のREADME.mdに従ってセットアップ
```

### v2（開発版）の使用

```bash
cd v2
# 現在開発中
```

## ディレクトリ構造

```
zhang_opera/
├── v1/                    # v1.x 安定版
│   ├── src/              # ソースコード
│   ├── docker/           # Docker設定
│   ├── docs/             # ドキュメント
│   ├── examples/         # 使用例
│   ├── tests/            # テスト
│   ├── scripts/          # スクリプト
│   └── README.md         # v1ドキュメント
├── v2/                    # v2.0 開発版
│   ├── src/              # ソースコード
│   ├── docs/             # ドキュメント
│   ├── config/           # 設定
│   ├── examples/         # 使用例
│   ├── tests/            # テスト
│   └── README.md         # v2ドキュメント
├── data_20250812/        # 共有特許分類データ
├── CLAUDE.md             # 開発ログ
└── README.md             # このファイル
```

## 技術スタック

### v1
- Python 3.11+
- FastAPI
- OpenSearch
- Vertex AI (Gemini)
- Docker & Docker Compose

### v2
- TBD

## ブランチ戦略

- `main`: v1.x安定版
- `feature/v2.0-directory-structure`: v2.0開発ブランチ

## ライセンス

MIT License

## お問い合わせ

GitHubのIssueを作成してください。
