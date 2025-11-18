# 特許構成要件分割・検索システム

## 概要

このシステムは、特許データ（PDF/XML）を入力として受け取り、以下の処理を自動的に実行します：

1. **構成要件分割（本願理解）**: Gemini 2.5 Proを使用して特許を構成要素に分解
2. **キーワード特定**: 各構成要素の検索キーワードを生成（同義語、上位/下位概念含む）
3. **特許分類コード特定**: OpenSearch APIとGoogle Patents APIを使用してFI/IPC/CPCを特定
4. **検索式作成**: 構成要素ごとのキーワードと分類コードを組み合わせた検索式を作成
5. **特許検索**: 動的範囲調整機能により、ヒット件数10-50件を目指して自動調整
   - **手動調整**: 最大12回のイテレーションで検索範囲を動的に調整
   - **AI駆動型調整**: 手動調整で目標未達成の場合、Claude Sonnet 4.5による最適化クエリ生成（最大10回試行）

## システム構成

### 主要モジュール

- **src/core/patent_component_analyzer.py**: 構成要件分割、キーワード生成、分類コード特定
- **src/core/patent_search_engine.py**: 検索式作成、特許検索、動的範囲調整
- **src/core/ai_query_generator.py**: AI駆動型検索クエリ生成（Claude Sonnet 4.5使用）
- **examples/run_patent_analysis.py**: メイン実行スクリプト
- **tests/test_patent_analysis.py**: テストスクリプト

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

サービスアカウントJSONファイルをプロジェクトルートに配置：
```
./ttdc-in-house-dev-3e07247326cb.json
```

**重要**: Geminiは Vertex AI 経由で利用されます
- Project ID: `ttdc-in-house-dev`
- Location: `us-central1`（デフォルト）
- 必要な権限: `Vertex AI User` ロール

#### OpenSearch API

デフォルト: `http://localhost:8000`

起動方法:
```bash
# 分類APIを起動
python src/api/patent_classification_api.py
# または
bash scripts/start.sh
```

#### Google Patents API

デフォルト: `http://localhost:8001`

起動方法:
```bash
# Google Patents APIを起動
python -m uvicorn src.api.google_patents_api:app --host 0.0.0.0 --port 8001
# または
bash scripts/start_google_patents_api.sh
```

## 使い方

### 基本的な使用方法

```bash
python examples/run_patent_analysis.py --input <特許ファイル> --output <出力ディレクトリ>
```

### オプション

```bash
python examples/run_patent_analysis.py \
  --input patents_pdf/sample.pdf \
  --output ./output \
  --service-account ./ttdc-in-house-dev-3e07247326cb.json \
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
  "adjustment_history": [...],
  "iteration_details": [
    {
      "iteration": 1,
      "adjustment_type": "MAINTAIN",
      "keyword_expansion_level": 0,
      "importance_threshold": 0.5,
      "total_hits": 35,
      "search_query": "...",
      "fi_codes_used": [...],
      "keywords_used": [...]
    },
    {
      "iteration": 13,
      "adjustment_type": "AI_GENERATED",
      "ai_confidence": 0.75,
      "ai_reasoning": "過去の失敗パターンから最適化",
      "total_hits": 42,
      "search_query": "..."
    }
  ],
  "token_usage": {
    "step1_component_analysis": {
      "prompt_tokens": 15234,
      "completion_tokens": 3456,
      "total_tokens": 18690
    },
    "step2_keyword_generation": {
      "prompt_tokens": 8500,
      "completion_tokens": 2100,
      "total_tokens": 10600,
      "per_component": [
        {"prompt_tokens": 567, "completion_tokens": 140, "total_tokens": 707},
        {"prompt_tokens": 565, "completion_tokens": 138, "total_tokens": 703}
      ]
    },
    "total_tokens_used": {
      "prompt_tokens": 23734,
      "completion_tokens": 5556,
      "total_tokens": 29290
    }
  },
  "processing_times": {
    "step1_component_analysis_seconds": 40.51,
    "step2_keyword_generation_seconds": 57.72,
    "step3_classification_finding_seconds": 2054.65,
    "step4_search_execution_seconds": 404.13,
    "total_workflow_seconds": 2557.01
  }
}
```

## トークン使用量トラッキング

システムはAI API（Claude Sonnet 4.5 / Gemini 2.5 Pro）の全呼び出しについて、詳細なトークン使用量を自動的に記録します。

### トークン使用量の構造

JSON出力の`token_usage`フィールドには、以下の情報が含まれます：

#### Step 1: 構成要件分割
```json
"step1_component_analysis": {
  "prompt_tokens": 15234,      // 入力トークン数（特許全文）
  "completion_tokens": 3456,   // 出力トークン数（構成要素JSON）
  "total_tokens": 18690        // 合計トークン数
}
```

#### Step 2: キーワード生成
```json
"step2_keyword_generation": {
  "prompt_tokens": 8500,       // 全構成要素の入力トークン合計
  "completion_tokens": 2100,   // 全構成要素の出力トークン合計
  "total_tokens": 10600,       // 全構成要素の合計トークン数
  "per_component": [           // 各構成要素ごとの詳細
    {
      "prompt_tokens": 567,
      "completion_tokens": 140,
      "total_tokens": 707
    },
    // ... 各構成要素ごとの記録
  ]
}
```

#### 合計トークン使用量
```json
"total_tokens_used": {
  "prompt_tokens": 23734,      // Step 1 + Step 2 の合計入力トークン
  "completion_tokens": 5556,   // Step 1 + Step 2 の合計出力トークン
  "total_tokens": 29290        // Step 1 + Step 2 の総合計トークン数
}
```

### トークン使用量の活用

- **コスト管理**: API使用料金の見積もりと最適化
- **パフォーマンス分析**: 処理時間とトークン数の相関分析
- **APIクォータ管理**: 月次・日次のトークン使用量監視
- **モデル比較**: Claude vs Gemini のトークン効率比較

### 注意事項

- **Step 3（分類コード特定）**: OpenSearch APIとGoogle Patents APIを使用するため、AI APIトークンは消費しません
- **Step 4（AI駆動型クエリ生成）**: 手動調整が失敗した場合のみ実行され、実行時はiteration_detailsに記録されます
- **トークン単価**:
  - Claude Sonnet 4.5: 入力 $3.00/MTok、出力 $15.00/MTok（2025年1月時点）
  - Gemini 2.5 Pro: 入力 $1.25/MTok、出力 $5.00/MTok（2025年1月時点）

## テスト

### テストスクリプトの実行

```bash
python tests/test_patent_analysis.py
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
    ├─ 手動調整（最大12回）
    │   ├─ ヒット件数 < 10 → 範囲拡大
    │   ├─ ヒット件数 10-50 → 完了
    │   └─ ヒット件数 > 50 → 範囲縮小
    ├─ AI駆動型調整（手動失敗時）
    │   ├─ Claude Sonnet 4.5による最適化クエリ生成
    │   ├─ 過去の失敗パターン分析
    │   └─ 最大10回のAI生成試行
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

#### ai_query_generator.py

- `AIQueryGenerator`: AI駆動型クエリ生成（Claude Sonnet 4.5使用）
- `AIGeneratedQuery`: AI生成クエリのデータモデル

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

### AI駆動型クエリ生成（手動調整失敗時）

手動調整で最大12回のイテレーションを行っても目標ヒット件数（10-50件）に到達しない場合、AI（Claude Sonnet 4.5）が自動的に最適化されたクエリを生成します。

**処理フロー**:
1. **過去の失敗パターン分析**
   - 最近5回のイテレーション履歴を分析
   - ヒット件数のパターンを認識
   - 失敗要因を特定

2. **最適化クエリ生成**
   - 構成要素情報（上位10個）を総合的に評価
   - 最適なFI/CPCコード選択（最大5個）
   - 最適なキーワード選択（各構成要素から最大5個）
   - 適切な論理演算子（AND, OR）の配置

3. **信頼度評価**
   - AI自身がクエリ品質を0.0～1.0で評価
   - 高信頼度（0.8以上）: 目標達成の可能性が高い
   - 中信頼度（0.5～0.8）: 目標達成の可能性は中程度
   - 低信頼度（0.5未満）: 試行的なクエリ

4. **反復試行**
   - 最大10回のAI生成クエリ試行
   - 目標範囲達成で即座に終了
   - 全AI試行失敗時は最後の手動調整結果を返却

**設定パラメータ**:
- `max_ai_attempts`: AI生成クエリの最大試行回数（デフォルト: 10）
- `temperature`: AIの創造性レベル（0.3：精度と創造性のバランス）

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

## 詳細処理フロー（v15仕様準拠）

### ステップ1: 構成要件分解

**処理内容**: 入力された特許データをGemini 2.5 Proで分析し、構成要素に分割

**実装**: `PatentComponentAnalyzer.analyze_patent_components()`

**出力**:
```json
{
  "構成要素番号": "1a",
  "構成要素": "構成要素のテキスト",
  "構成要素のサポート箇所": "【請求項１】、【００２１】",
  "段落番号": ["0001", "0021"],
  "構成要素の簡単説明": "簡単な説明",
  "構成要素の重要度": 0.8
}
```

### ステップ2: 各構成要素の一次検索キーワード生成

**処理内容**: 各構成要素に対してキーワードを生成（合計15個以内）

**実装**: `KeywordGenerator.generate_keywords()` （各構成要素ごと）

**キーワード種類**:
- **一次検索キーワード**: 基本的な検索キーワード（5個程度）
- **検索範囲拡大キーワード**: 上位概念、同義語など（5個程度）
- **検索範囲縮小キーワード**: 下位概念、専門用語など（5個程度）

### ステップ3: 各構成要素のCPC/FI特定

#### 3-1. OpenSearch APIでCPC/FI特定

**処理内容**: 各構成要素のテキストを使用してOpenSearch APIでFI/IPCを検索

**実装**: `ClassificationFinder._search_opensearch_classifications()`

**検索パラメータ**:
- `text`: 構成要素テキスト + 簡単説明
- `classification_types`: ["fi", "ipc"]
- `top_k`: 10
- `use_semantic_search`: True

#### 3-2. Google Patents APIで予備検索

**処理内容**: 各構成要素の一次検索キーワードを使用してGoogle Patents APIで予備検索

**実装**: `ClassificationFinder._preliminary_search()` （各構成要素ごと、`use_global_preliminary=False`）

**重要仕様**:
- 検索結果のCPCランキングから**上位3個以内**のデータを取得
- 実装箇所: `patent_component_analyzer.py:593, 730`

```python
# CPCランキングを取得（仕様書: 上位3個以内）
cpc_ranking = data.get("cpc_ranking", [])
cpc_codes = [item["cpc_code"] for item in cpc_ranking[:3]]
```

#### 3-3. CPC→FI変換

**処理内容**: 取得した全てのCPCをOpenSearch APIでFIに変換

**実装**: `ClassificationFinder._convert_cpc_to_fi()`

**APIエンドポイント**: `POST /convert/cpc_to_fi`

#### 3-4. 交差の特定

**処理内容**: OpenSearch APIで特定したCPC/FIとGoogle Patents APIで取得したCPC/FIの**交差**を一次CPC/FIにする

**実装**: `ClassificationFinder._categorize_fi_codes()` (lines 793-798)

**ロジック**:
```python
# ステップ1: 両方に現れるFIコード（交差）を最優先
fi_opensearch_set = set(fi_opensearch)
fi_preliminary_set = set(fi_preliminary)
intersection_fi = list(fi_opensearch_set & fi_preliminary_set)
```

**実用的な実装**:
- 交差結果を最優先でprimary_fiに含める
- 交差が少ない場合は、OpenSearch→予備検索の順で追加（検索失敗を防ぐため）

**カテゴリ分け（合計10個以内）**:
- `一次特定最終FI`: 最上位3-4件（交差を優先）
- `検索範囲拡大最終FI`: 次の3件
- `検索範囲縮小最終FI`: 次の3件

### ステップ4: 検索実行（ループ: max5回）

#### 4-1. 一次検索（ヒット件数10~50）

**処理内容**: 一次キーワード + 一次CPC/FI で検索、ヒット件数10~50 → 完了

**実装**: `PatentSearchEngine.search_with_adjustment()` (target: 10-50 hits)

**検索式構築**: `SearchQueryBuilder._build_classification_codes_query()`

**重要仕様**: FI+CPC OR条件で検索式作成

```python
# 例: "FI:G11C11/56220 OR FI:H10D30/01101Z OR CPC:H10D30/00 OR CPC:H10D86/00"
```

**実装箇所**: `patent_search_engine.py:75-102`

#### 4-2. 拡大検索（ヒット件数<10）

**処理内容**: 拡大キーワード生成 + 拡大CPC/FI で検索

**実装**: `SearchRangeAdjustment.EXPAND` + `keyword_expansion_level`調整

**調整パラメータ**:
- `importance_threshold` を下げる（0.8 → 0.6 → 0.4）
- `keyword_expansion_level` を上げる（PRIMARY → EXPANDED）

#### 4-3. 縮小検索（ヒット件数>50）

**処理内容**: 縮小キーワード生成 + 縮小CPC/FI で検索

**実装**: `SearchRangeAdjustment.NARROW` + `importance_threshold`調整

**調整パラメータ**:
- `importance_threshold` を上げる（0.6 → 0.8 → 0.9）
- `keyword_expansion_level` を下げる（EXPANDED → PRIMARY → NARROWED）

### ステップ5: FIとCPCをOR条件

**処理内容**: FIとCPCをOR条件で結合した検索式を作成

**実装**: `SearchQueryBuilder._build_classification_codes_query()` (v15で実装完了)

**検索式例**:
```
FI:G11C11/56220 OR FI:H10D30/01101Z OR CPC:H10D30/00 OR CPC:H10D86/00
```

**背景**:
- Google PatentsはH10D（2020年導入）などの新しいFI分類を完全サポートしていない
- FIとCPCを組み合わせることで検索カバレッジを最大化

## 実装の特徴と改善点

### v15実装の主要改善点

1. ✅ **CPCランキング取得数の修正**: 10個 → **3個** (仕様書準拠)
   - 実装箇所: `patent_component_analyzer.py:593, 730`

2. ✅ **FI+CPC OR条件の実装**: FIとCPCを組み合わせた検索式
   - 実装箇所: `patent_search_engine.py:75-102`
   - Google Patentsの新FI非対応問題を解決

3. ✅ **CPC分類の保持**: グローバル予備検索がFIとCPCの両方を保持
   - 実装箇所: `patent_component_analyzer.py:609`

4. ✅ **各構成要素ごとの予備検索**: 仕様書通りの個別検索実装
   - 実装箇所: `patent_search_engine.py:672` (`use_global_preliminary=False`)

### 交差処理の実用的な実装

仕様書では「交差のみ」を一次CPC/FIとすることが示唆されていますが、現在の実装では：

1. **交差結果を最優先**
2. **交差が少ない場合、OpenSearch結果を追加**
3. **さらに不足する場合、予備検索結果を追加**

これにより、交差が0の場合でも検索が可能になり、実用性が高まっています。

### 動的範囲調整の詳細

ヒット件数に応じて以下を調整：
- **重要度閾値**（importance_threshold）: 0.4 ↔ 0.6 ↔ 0.8 ↔ 0.9
- **キーワード拡張レベル**（keyword_expansion_level）: PRIMARY ↔ EXPANDED ↔ NARROWED
- **検索範囲**（SearchRangeAdjustment）: MAINTAIN / EXPAND / NARROW

## 検証結果

### 処理フロー検証

✅ **処理フローは仕様書と一致しています**

主な修正:
- CPCランキング取得数: 10個→3個に変更
- FI+CPC OR条件: 実装完了
- 各構成要素ごとの予備検索: 正しく実装済み

### v15実装検証

検証スクリプト: `/tmp/verify_v15_implementation.py`

```bash
python3 /tmp/verify_v15_implementation.py
```

**検証項目**:
- ✅ FIコード含む
- ✅ CPCコード含む
- ✅ OR条件
- ✅ グローバル予備検索がFIとCPCの両方を保持

## 変更履歴

### v1.5.0 (2025-11-11)

- ✅ 仕様書準拠の処理フロー検証・修正完了
- ✅ CPCランキング取得数を3個に修正（仕様書準拠）
- ✅ FI+CPC OR条件検索の実装完了
- ✅ 各構成要素ごとの個別予備検索実装
- ✅ 交差処理ロジックの実用的な実装

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
