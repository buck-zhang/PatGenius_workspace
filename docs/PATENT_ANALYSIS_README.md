# 特許構成要件分割・検索システム

## 概要

このシステムは、特許データ（PDF/XML）を入力として受け取り、以下の処理を自動的に実行します：

1. **構成要件分割（本願理解）**: Gemini 2.5 Proを使用して特許を構成要素に分解
2. **キーワード特定**: 各構成要素の検索キーワードを生成（同義語、上位/下位概念含む）
3. **特許分類コード特定**: OpenSearch APIとGoogle Patents APIを使用してFI/IPC/CPCを特定
4. **検索式作成**: 構成要素ごとのキーワードと分類コードを組み合わせた検索式を作成
5. **特許検索**: 動的範囲調整機能により、ヒット件数10-50件を目指して自動調整

## システム構成

### 主要モジュール

- **patent_component_analyzer.py**: 構成要件分割、キーワード生成、分類コード特定
- **patent_search_engine.py**: 検索式作成、特許検索、動的範囲調整
- **run_patent_analysis.py**: メイン実行スクリプト
- **test_patent_analysis.py**: テストスクリプト

### 外部API依存

1. **Vertex AI (Gemini)**: Gemini 2.5 Pro via Vertex AI（構成要件分割、キーワード生成）
   - Project ID: ttdc-in-house-dev
   - Location: us-central1
   - Model: gemini-2.5-pro
2. **OpenSearch API**: 特許分類コード検索（FI/IPC）
3. **Google Patents API**: 特許検索、CPC取得、PDF取得

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements_patent_analysis.txt
```

### 2. API設定

#### Vertex AI (Gemini) サービスアカウント

サービスアカウントJSONファイルを配置：
```
/Volumes/T7/patgenius/zhang_opera/ttdc-in-house-dev-3e07247326cb.json
```

**重要**: Geminiは Vertex AI 経由で利用されます
- Project ID: `ttdc-in-house-dev`
- Location: `us-central1`（デフォルト）
- 必要な権限: `Vertex AI User` ロール

#### OpenSearch API

デフォルト: `http://localhost:8000`

起動方法:
```bash
# patent_classification_api.pyを起動
python patent_classification_api.py
```

#### Google Patents API

デフォルト: `http://localhost:8001`

起動方法:
```bash
# google_patents_api.pyを起動
uvicorn google_patents_api:app --host 0.0.0.0 --port 8001
```

## 使い方

### 基本的な使用方法

```bash
python run_patent_analysis.py --input <特許ファイル> --output <出力ディレクトリ>
```

### オプション

```bash
python run_patent_analysis.py \
  --input sample.xml \
  --output ./output \
  --service-account /path/to/service-account.json \
  --opensearch-api http://localhost:8000 \
  --google-patents-api http://localhost:8001 \
  --verbose
```

#### パラメータ説明

- `--input`, `-i`: 入力特許ファイル（PDF/XML/TXT）**【必須】**
- `--output`, `-o`: 出力ディレクトリ（デフォルト: `./output`）
- `--service-account`: Gemini APIサービスアカウントJSONパス
- `--opensearch-api`: OpenSearch API URL
- `--google-patents-api`: Google Patents API URL
- `--verbose`, `-v`: 詳細ログを出力

### 出力ファイル

出力ディレクトリに以下のファイルが生成されます：

1. **result_YYYYMMDD_HHMMSS.json**: 分析・検索結果（JSON形式）
2. **patent_analysis_YYYYMMDD_HHMMSS.log**: 実行ログ

### 結果JSONの構造

```json
{
  "components": [
    {
      "構成要素番号": "1a",
      "構成要素": "車両周囲の環境情報を取得する複数のセンサー",
      "構成要素のサポート箇所": "【請求項1】車両周囲の...",
      "構成要素の簡単説明": "環境認識用センサー群",
      "構成要素の従属関係": "|",
      "構成要素の重要度": 0.8
    }
  ],
  "keywords": [...],
  "classifications": [...],
  "search_query": "(classification:\"B60W30/18\" OR ...) AND (\"センサー\" OR ...)",
  "total_hits": 35,
  "patents": [...],
  "cpc_ranking": [...],
  "adjustment_history": [...]
}
```

## テスト

### テストスクリプトの実行

```bash
python test_patent_analysis.py
```

このスクリプトは以下のテストを実行します：

1. **構成要件分割テスト**: サンプル特許データを構成要素に分割
2. **キーワード生成テスト**: 各構成要素のキーワードを生成
3. **分類コード特定テスト**: OpenSearch/Google Patents APIを使用して分類コードを特定

### テスト用特許データ

テストスクリプトには、自動運転車両の制御システムに関するサンプル特許データが含まれています。

## アーキテクチャ

### ワークフローの流れ

```
入力特許データ（PDF/XML）
    ↓
【ステップ1】構成要件分割（Gemini）
    ↓
構成要素リスト（JSON）
    ↓
【ステップ2】キーワード生成（Gemini）
    ↓
各構成要素のキーワード
    ↓
【ステップ3】分類コード特定
    ├─ OpenSearch API（FI/IPC検索）
    └─ Google Patents API（予備検索 → CPC → FI変換）
    ↓
各構成要素の最終分類コード（FI優先）
    ↓
【ステップ4】検索式作成
    ↓
検索クエリ（FI + キーワードのAND/OR組み合わせ）
    ↓
【ステップ5】特許検索（動的範囲調整）
    ├─ ヒット件数 < 10 → 範囲拡大
    ├─ ヒット件数 10-50 → 完了
    └─ ヒット件数 > 50 → 範囲縮小
    ↓
検索結果（10-50件）
    ↓
PDF自動ダウンロード
```

### クラス構成

#### patent_component_analyzer.py

- `GeminiClient`: Gemini API クライアント
- `PatentComponentAnalyzer`: 構成要件分割
- `KeywordGenerator`: キーワード生成
- `ClassificationFinder`: 特許分類コード特定

#### patent_search_engine.py

- `SearchQueryBuilder`: 検索式作成
- `PatentSearchEngine`: 特許検索エンジン（動的範囲調整）
- `PatentAnalysisWorkflow`: 全体ワークフロー統括

## 動的範囲調整の仕組み

### 検索範囲拡大（ヒット件数が少ない場合）

1. **キーワード拡張**
   - 同義語・類義語の追加
   - 上位概念の採用
   - ワイルドカード使用

2. **分類コード拡大**
   - 上位の分類コードを採用
   - 関連する分類コードの追加

### 検索範囲縮小（ヒット件数が多い場合）

1. **キーワード絞り込み**
   - 必須キーワードの追加（AND条件）
   - 下位概念の採用
   - 不要なキーワードの除外

2. **分類コード絞り込み**
   - 下位の分類コードに限定
   - 複数の分類コードをAND条件で掛け合わせ

## トラブルシューティング

### Vertex AI (Gemini) APIエラー

```
Error: Failed to configure Vertex AI Gemini API
```

**解決方法**:
- サービスアカウントJSONファイルのパスが正しいか確認
- サービスアカウントに `Vertex AI User` 権限があるか確認
- プロジェクト `ttdc-in-house-dev` で Vertex AI API が有効化されているか確認
- リージョン `us-central1` で Gemini モデルが利用可能か確認

### OpenSearch API接続エラー

```
Error: OpenSearch classification search failed
```

**解決方法**:
- OpenSearch APIが起動しているか確認
- `http://localhost:8000` でアクセス可能か確認
- Dockerコンテナが起動しているか確認（Docker使用の場合）

### Google Patents API接続エラー

```
Error: Search execution failed
```

**解決方法**:
- Google Patents APIが起動しているか確認
- `http://localhost:8001` でアクセス可能か確認
- Selenium WebDriverが正しくインストールされているか確認

### PDF読み込みエラー

```
Error: PyPDF2 is required for PDF files
```

**解決方法**:
```bash
pip install PyPDF2
```

## ライセンス

このプロジェクトは内部使用を目的としています。

## 変更履歴

### v1.0.0 (2025-11-10)

- 初回リリース
- Gemini 2.5 Pro統合（Vertex AI経由）
- 構成要件分割機能
- キーワード生成機能
- 特許分類コード特定機能
- 検索式作成機能
- 動的範囲調整機能
- PDF自動ダウンロード機能

## 連絡先

問題や質問がある場合は、プロジェクトチームにお問い合わせください。
