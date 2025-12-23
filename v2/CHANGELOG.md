# Changelog

All notable changes to PatGenius will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-12-23

### Added
- **モノレポ構造**: Turborepo + pnpm workspaces導入
- **FastAPI統合**: バックエンドAPIの基本構造を実装
- **環境変数管理**: Pydantic BaseSettingsによる集中管理
- **ドキュメント**: README、API仕様書の刷新
- **Next.js対応準備**: apps/web ディレクトリ構造の作成

### Changed
- **ディレクトリ構造**: フラット構造からモノレポへ完全移行
  - \`apps/backend\`: メインバックエンド（特許分析パイプライン）
  - \`apps/classification-search\`: ベクトル検索API
  - \`apps/web\`: Next.js フロントエンド（準備中）
  - \`packages/\`: 共有パッケージ
  - \`data/\`: データディレクトリ統一
  - \`credentials/\`: 認証情報の集約
- **認証情報**: ハードコードパスから環境変数へ移行
- **テスト結果**: \`data/test_results/\` に統一

### Removed
- 一時ファイル（temp_*.json）の削除
- 旧テストスクリプト（test_consistency_*.py等）の削除
- 散在していたテスト結果フォルダの統合
- 空フォルダの削除

### Fixed
- FI分類コードの空白除去処理
- キーワード検索フィールドの最適化

## [1.0.0] - 2025-11-29

### Added
- 構成要件分割システム（Claude Sonnet 4.5）
- キーワード抽出システム（3階層）
- 特許分類コード抽出システム
- 構成要素ごと検索実行システム
- 新規性進歩性判断エンジン（Gemini 3.0 Pro）
- 構成対比表生成機能
- 拒絶理由通知生成機能

### Performance
- AsyncIO完全移行（40-50%高速化）
- Claude Prompt Caching（コスト90%削減）
- PatentField API並列化（20-30%高速化）
