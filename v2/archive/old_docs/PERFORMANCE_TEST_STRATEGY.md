# 特許検索システム性能テスト - 包括的戦略 v2.0

## 📊 テストデータ概要

### データソース
- **xy_data1.csv**: 62,601ペア（2.5MB）
- **xy_data2.csv**: 360,467ペア（14.9MB）
- **合計**: 423,068ペア

### データ構造
```csv
syutugan,himotuki,category,koukaibi
JP2013224028A,JP2012040876A,Ax,20120301
JP2014007731A,JP2011171723A,Ax,20110901
```

- **syutugan**: 本願出願番号（検索の入力）
- **himotuki**: 紐づいた特許（正解ラベル、検索で見つけるべき）
- **category**: カテゴリ（Ax等）
- **koukaibi**: 公開日

---

## 🎯 テスト目的と評価指標（2025年ベストプラクティス）

### 1. Recall（再現率）- **主要指標**
```
Recall = 検索結果に含まれていた紐づいた特許数 / 全テストケース数
```

**なぜRecallが重要か**:
- 特許検索では「検索漏れ」が最も危険
- False Negative（見逃し）のコストが非常に高い
- 2025年のベストプラクティスでは、「検索漏れゼロ」を目指す

### 2. Precision（適合率）- **副次指標**
```
Precision = 検索結果のうち紐づいた特許の順位 / 総検索結果数
```

**考慮点**:
- ヒット件数が多すぎても実用性が低い
- 目標範囲（10-300件）内での適合率

### 3. その他の重要指標
- **処理時間**: 1件あたりの平均処理時間
- **トークン使用量**: Claude/Geminiの詳細使用量
- **コスト**: 日本円換算での料金
- **エラー率**: API失敗やタイムアウトの割合

---

## 🏗️ システム構築案

### アーキテクチャ概要

```
┌─────────────────────────────────────────────────────────────┐
│  Patent Search Performance Test System v2.0                 │
└─────────────────────────────────────────────────────────────┘

1. Data Preparation
   ├── CSV結合 (xy_data1 + xy_data2)
   ├── 上位30件抽出（初期テスト）
   └── 本願出願番号リスト生成

2. Patent Data Fetcher (PatentField API)
   ├── 各本願の請求の範囲取得
   ├── 詳細な説明取得
   ├── エラーハンドリング（404, timeout等）
   └── レート制限対応（sleep調整）

3. Patent Search Pipeline
   ├── 構成要件分割 (Claude Sonnet 4)
   ├── キーワード抽出 (Claude Sonnet 4)
   ├── 分類コード抽出 (Gemini 1.5 Pro)
   └── PatentField検索実行

4. Result Verification
   ├── 検索結果に紐づいた特許が含まれているか確認
   ├── 含まれている場合の順位記録
   └── Recall計算

5. Metrics Collection
   ├── 処理時間記録（各ステップ＋全体）
   ├── トークン使用量記録
   │   ├── Claude: input/output tokens分離
   │   └── Gemini: input/output tokens分離
   ├── API呼び出し回数
   └── エラー統計

6. Cost Calculation
   ├── Claude料金計算（2025年11月料金）
   ├── Gemini料金計算
   └── 合計コスト（日本円）

7. Report Generation
   ├── 性能サマリー（Recall, Precision等）
   ├── 処理時間分析
   ├── コスト分析
   └── 失敗ケース詳細
```

### 技術スタック

**言語**: Python 3.9+

**依存ライブラリ**:
```python
pandas          # CSV処理
anthropic       # Claude API
google-generativeai  # Gemini API
requests        # PatentField API
time, datetime  # 時間計測
json            # データ保存
logging         # ロギング
```

---

## 📋 実装ステップ（詳細）

### Step 1: データ準備モジュール

```python
class DataPreparator:
    def merge_csv_files(self, file1, file2, output):
        """2つのCSVを縦結合"""

    def extract_top_n(self, input_file, n=30):
        """上位N件を抽出"""

    def deduplicate_syutugan(self, df):
        """本願出願番号の重複削除"""
```

**出力**:
- `tests/performance_test/combined_data.csv`
- `tests/performance_test/test_data_30.csv`

### Step 2: 特許データ取得モジュール

```python
class PatentDataFetcher:
    def __init__(self, api_key, endpoint):
        self.api_key = api_key
        self.endpoint = endpoint

    def fetch_patent_text(self, pub_id):
        """
        PatentField APIから請求の範囲と詳細な説明を取得

        Returns:
            {
                'pub_id': 'JP2014007731A',
                'claims': '...',
                'description': '...',
                'status': 'success'/'not_found'/'error'
            }
        """

    def fetch_batch(self, pub_ids, output_dir):
        """バッチ処理でデータ取得・保存"""
```

**出力**:
- `tests/performance_test/patent_texts/JP2014007731A.json`
- `tests/performance_test/patent_texts/...`

### Step 3: 検索パイプライン実行モジュール

```python
class SearchPipeline:
    def __init__(self, claude_key, gemini_key, pf_key):
        self.claude_key = claude_key
        self.gemini_key = gemini_key
        self.pf_key = pf_key

    def execute(self, patent_text):
        """
        構成要件分割 → キーワード → 分類 → 検索

        Returns:
            {
                'syutugan': 'JP2014007731A',
                'search_results': ['JP...', ...],
                'metrics': {
                    'time_structure': 12.3,
                    'time_keyword': 8.5,
                    'time_classification': 15.2,
                    'time_search': 2.1,
                    'tokens_claude_input': 5000,
                    'tokens_claude_output': 1200,
                    'tokens_gemini_input': 3000,
                    'tokens_gemini_output': 800
                }
            }
        """
```

**既存システムの活用**:
- `patent_structure_analyzer.py`
- `patent_keyword_extractor.py`
- `patent_classification_extractor.py`
- `patent_search_executor.py`

### Step 4: 結果検証モジュール

```python
class ResultVerifier:
    def verify(self, search_results, himotuki_patent):
        """
        検索結果に紐づいた特許が含まれているか検証

        Returns:
            {
                'found': True/False,
                'rank': 42,  # 見つかった場合の順位
                'total_results': 100
            }
        """

    def calculate_recall(self, verification_results):
        """Recall計算"""
        total = len(verification_results)
        found = sum(1 for r in verification_results if r['found'])
        return found / total
```

### Step 5: メトリクス収集モジュール

```python
class MetricsCollector:
    def __init__(self):
        self.metrics = {
            'test_cases': [],
            'total_time': 0,
            'total_tokens_claude': {'input': 0, 'output': 0},
            'total_tokens_gemini': {'input': 0, 'output': 0},
            'errors': []
        }

    def add_test_case(self, syutugan, himotuki, result, metrics):
        """個別テストケースの記録"""

    def calculate_costs(self):
        """
        料金計算（2025年11月料金）

        Claude Sonnet 4:
        - Input: 471円/1M tokens
        - Output: 2,355円/1M tokens

        Gemini 1.5 Pro:
        - Input: 196円/1M tokens
        - Output: 1,570円/1M tokens
        """
```

### Step 6: レポート生成モジュール

```python
class ReportGenerator:
    def generate(self, metrics, output_file):
        """
        包括的なレポート生成

        内容:
        - 性能サマリー
        - 処理時間分析
        - トークン使用量詳細
        - コスト分析（日本円）
        - 失敗ケース一覧
        - 検索結果サンプル
        """
```

**出力**:
- `tests/performance_test/PERFORMANCE_REPORT.md`
- `tests/performance_test/metrics.json`

---

## 💰 コスト見積もり（30件テスト）

### 想定トークン使用量（1件あたり）

| ステップ | モデル | Input | Output |
|---------|--------|-------|--------|
| 構成要件分割 | Claude Sonnet 4 | 8,000 | 2,000 |
| キーワード抽出 | Claude Sonnet 4 | 6,000 | 1,500 |
| 分類コード抽出 | Gemini 1.5 Pro | 7,000 | 1,200 |
| **合計（1件）** | - | **21,000** | **4,700** |

### 料金計算（30件）

**Claude Sonnet 4**:
- Input: (8,000 + 6,000) × 30 = 420,000 tokens × 471円/1M = **198円**
- Output: (2,000 + 1,500) × 30 = 105,000 tokens × 2,355円/1M = **247円**
- **小計**: 445円

**Gemini 1.5 Pro**:
- Input: 7,000 × 30 = 210,000 tokens × 196円/1M = **41円**
- Output: 1,200 × 30 = 36,000 tokens × 1,570円/1M = **57円**
- **小計**: 98円

**合計（30件テスト）**: **約543円**

**全データ（423,068件）の見積もり**:
- 543円 × (423,068 / 30) ≈ **766万円**

### コスト最適化戦略

1. **プロンプトキャッシング活用**（Claude）
   - 繰り返しクエリで最大90%削減可能

2. **バッチ処理の最適化**
   - 並列処理でAPI呼び出し削減

3. **段階的テスト**
   - 30件 → 100件 → 1,000件 → 全件

---

## ⚡ 処理時間見積もり

### 1件あたりの処理時間

| ステップ | 時間 |
|---------|------|
| PatentField データ取得 | 2秒 |
| 構成要件分割 | 12秒 |
| キーワード抽出 | 8秒 |
| 分類コード抽出 | 15秒 |
| PatentField 検索 | 2秒 |
| **合計** | **39秒** |

### スケール見積もり

- **30件**: 39秒 × 30 = 約20分
- **100件**: 39秒 × 100 = 約65分
- **1,000件**: 39秒 × 1,000 = 約11時間
- **全件（423,068件）**: 約6,800時間 = **約283日**

### 最適化戦略

1. **並列処理**
   - 5並列で処理時間を1/5に短縮
   - 全件 → 約57日

2. **キャッシング**
   - 同一特許の重複処理を削減

3. **段階的アプローチ**
   - サンプリングによる精度検証

---

## 🔧 実装の優先順位

### Phase 1: プロトタイプ（30件テスト）
**期間**: 2日
**内容**:
1. データ準備モジュール実装
2. 特許データ取得実装
3. 既存パイプライン統合
4. 基本メトリクス収集
5. 簡易レポート生成

**成果物**:
- `performance_test_runner.py`
- 30件のテスト結果
- 初期性能レポート

### Phase 2: スケールアップ（100件テスト）
**期間**: 3日
**内容**:
1. エラーハンドリング強化
2. 並列処理実装
3. 詳細メトリクス収集
4. コスト追跡機能

**成果物**:
- スケーラブルなシステム
- 100件のテスト結果
- コスト分析レポート

### Phase 3: 本番運用（1,000件以上）
**期間**: 1週間
**内容**:
1. バッチ処理最適化
2. キャッシング実装
3. 包括的ダッシュボード
4. 継続的モニタリング

**成果物**:
- 本番運用可能なシステム
- 大規模テスト結果
- 精度改善の提案

---

## 📈 期待される成果

### 定量的成果
- **Recall**: 80%以上を目標（検索漏れ20%以下）
- **処理時間**: 1件あたり40秒以内
- **コスト**: 1件あたり20円以内

### 定性的成果
- システムの信頼性検証
- 検索漏れのパターン分析
- 改善点の明確化
- スケーラビリティの実証

### 次のステップ
1. Phase 1実装（30件プロトタイプ）
2. 結果分析と改善
3. Phase 2へ進行判断
4. 本番運用計画策定

---

## 🎓 ベストプラクティス（2025年）

### 1. 評価指標の選択
- **Recallを最優先**: 特許検索では検索漏れが致命的
- **複数指標の併用**: Precision, F1-Score, 処理時間
- **継続的モニタリング**: モデルドリフト検出

### 2. コスト最適化
- **プロンプトキャッシング**: Claude独自機能の活用
- **バッチ処理**: API呼び出しの効率化
- **段階的スケールアップ**: 小規模テストから開始

### 3. 品質保証
- **エラーハンドリング**: API失敗、タイムアウト対応
- **ロギング**: 詳細なログ記録
- **再現性**: テスト結果の保存と再実行可能性

---

生成日: 2025年11月
システム: PatentField特許検索システム v2.0
ステータス: 戦略策定完了
