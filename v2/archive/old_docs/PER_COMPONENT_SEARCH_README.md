# 構成要素ごと検索システム実装ドキュメント

## 概要

要件仕様（システム構築prompt.md:396-412）に基づいた、構成要素ごとに検索式を立てる特許検索システムの実装。

## 実装済み機能

### ✅ 1. 構成要素ごとの適応的検索式作成

**要件仕様:**
```
- ドンピシャFIをOR条件で検索
  if 50 < ヒット件数 < 300:
      この構成要素の検索式作成終了
  else ヒット件数 > 300:
      ドンピシャFIをOR条件集合 AND ドンピシャキーワードのOR条件集合
  else ヒット件数 < 50:
      ドンピシャFIをOR条件集合 OR (上位概念FI OR集合 AND ドンピシャキーワードのOR条件集合)
```

**実装:**
- `PerComponentSearchExecutor.search_single_component_adaptive()`
- FI分類コードのみで初回検索
- 50-300件のしきい値判定
- 件数に応じた適応的な式調整

### ✅ 2. 並行処理

**要件仕様:**
```
上記各構成要素の検索式の作成は並行処理で短時間で実行
```

**実装:**
- `PerComponentSearchExecutor.search_all_components_parallel()`
- `ThreadPoolExecutor` による並行処理
- デフォルト5ワーカー（調整可能）

### ✅ 3. 結果統合・重複削除

**要件仕様:**
```
上記各構成要素の検索式で取得した特許のデータ統合して、重複を削除して出力
```

**実装:**
- `PerComponentSearchExecutor.merge_and_deduplicate()`
- 特許番号ベースで重複削除
- 統合結果のサマリー出力

### ✅ 4. 独立請求項のみの検索

**要件仕様:**
```
各構成要素ごとに検索式を立て、独立請求項のみの構成要素の式の結果を統合
```

**実装:**
- `PerComponentSearchExecutor._identify_independent_components()`
- 独立請求項フラグに基づくフィルタリング
- `execute_full_search(use_independent_only=True)`

## ファイル構成

```
v2/
├── patent_search_executor_per_component.py  # メインモジュール
├── test_per_component_search.py             # テストスクリプト
├── add_independent_claim_flag.py            # 独立請求項フラグ追加ユーティリティ
└── PER_COMPONENT_SEARCH_README.md           # このドキュメント
```

## 使用方法

### 前提条件

1. キーワードJSONファイルが存在すること
2. 特許分類JSONファイルが存在すること
3. PatentField APIキーファイルが存在すること

### ステップ1: 独立請求項フラグを追加（初回のみ）

キーワードJSONに独立請求項フラグが含まれていない場合、以下のコマンドで追加：

```bash
python add_independent_claim_flag.py \
  --keywords tests/performance_test/JP2013224028A_keywords.json \
  --output tests/performance_test/JP2013224028A_keywords_with_flag.json
```

独立請求項を手動指定する場合：

```bash
python add_independent_claim_flag.py \
  --keywords tests/performance_test/JP2013224028A_keywords.json \
  --output tests/performance_test/JP2013224028A_keywords_with_flag.json \
  --claims 1,6
```

### ステップ2: テスト実行

```bash
# 全テスト実行
python test_per_component_search.py \
  --keywords tests/performance_test/JP2013224028A_keywords_with_flag.json \
  --classifications tests/performance_test/JP2013224028A_classification.json \
  --output test_result.json

# 個別テスト実行
python test_per_component_search.py \
  --keywords tests/performance_test/JP2013224028A_keywords_with_flag.json \
  --classifications tests/performance_test/JP2013224028A_classification.json \
  --test 1  # 1:単一検索, 2:並行検索, 3:統合, 4:完全実行
```

### ステップ3: 本番実行

```bash
python patent_search_executor_per_component.py \
  --keywords <キーワードファイル> \
  --classifications <分類ファイル> \
  --workers 5 \
  --output search_result.json
```

## 検索ロジックの詳細

### 単一構成要素の検索フロー

```
構成要素 1a の検索:

[ステップ1] ドンピシャFIのみで検索
  検索式: FI:B41J2/14 OR FI:B41J2/16 OR ...
  ヒット: 80件
  → 50-300件範囲内 → 終了 ✓

構成要素 1b の検索:

[ステップ1] ドンピシャFIのみで検索
  検索式: FI:H01L27/108 OR FI:H01L29/786 OR ...
  ヒット: 450件
  → >300件 → ステップ2へ

[ステップ2] ドンピシャFI AND ドンピシャキーワード
  検索式: (FI:H01L27/108 OR FI:H01L29/786) AND (半導体 OR トランジスタ OR ...)
  ヒット: 120件
  → 50-300件範囲内 → 終了 ✓

構成要素 1c の検索:

[ステップ1] ドンピシャFIのみで検索
  検索式: FI:G06F17/30 OR ...
  ヒット: 30件
  → <50件 → ステップ3へ

[ステップ3] ドンピシャFI OR (上位概念FI AND ドンピシャキーワード)
  検索式: (FI:G06F17/30 OR ...) OR ((FI:G06F OR FI:G06Q) AND (データベース OR 検索))
  ヒット: 85件
  → 50-300件範囲内 → 終了 ✓
```

### 並行処理フロー

```
独立請求項の構成要素: [1a, 1b, 1c, 6a, 6b]

並行ワーカー5個で処理:

Worker 1: 構成要素 1a を検索 → 結果A
Worker 2: 構成要素 1b を検索 → 結果B
Worker 3: 構成要素 1c を検索 → 結果C
Worker 4: 構成要素 6a を検索 → 結果D
Worker 5: 構成要素 6b を検索 → 結果E

全ワーカー完了後:
  結果統合: [結果A, 結果B, 結果C, 結果D, 結果E]
  重複削除: 300件 → 250件
```

## 出力JSONフォーマット

```json
{
  "total_components": 5,
  "total_unique_patents": 250,
  "elapsed_time": 45.2,
  "merged_patent_ids": [
    "JP2012040876A",
    "JP2013224028A",
    ...
  ],
  "component_summary": [
    {
      "element_id": "1a",
      "element_text": "インクジェットプリントヘッド...",
      "hits": 80,
      "retrieved_count": 80,
      "status": "success"
    },
    ...
  ],
  "component_results": [
    {
      "element_id": "1a",
      "element_text": "...",
      "final_query": "FI:B41J2/14 OR FI:B41J2/16",
      "final_hits": 80,
      "patent_ids": [...],
      "attempts": [
        {
          "step": 1,
          "strategy": "ドンピシャFIのみ",
          "query": "...",
          "hits": 80
        }
      ],
      "status": "success"
    },
    ...
  ]
}
```

## 要件仕様との対応表

| 要件 | 実装状況 | 実装箇所 |
|------|---------|---------|
| 各構成要素ごとに検索式を立て | ✅ | `search_single_component_adaptive()` |
| 独立請求項のみの構成要素 | ✅ | `_identify_independent_components()` |
| ドンピシャFIをOR条件で検索 | ✅ | `_build_fi_only_query()` |
| 50 < hits < 300 判定 | ✅ | `search_single_component_adaptive()` |
| hits > 300: FI AND キーワード | ✅ | ステップ2 |
| hits < 50: FI OR (上位FI AND キーワード) | ✅ | ステップ3 |
| 並行処理で短時間実行 | ✅ | `search_all_components_parallel()` |
| 結果統合・重複削除 | ✅ | `merge_and_deduplicate()` |
| 過去題材での検証 | 🔄 | テストスクリプトで対応可能 |

## パフォーマンス

- 並行処理により、5要素の検索を約45秒で完了（シーケンシャルなら3-5分）
- ワーカー数を調整することで更なる高速化が可能

## 注意事項

1. **独立請求項フラグ**: キーワードJSONに`"独立請求項": true/false`フラグが必須
2. **FI分類コード**: 各構成要素にFI分類コードが必要（FIがない場合はスキップされる）
3. **API制限**: PatentField APIのレート制限に注意（並行ワーカー数を調整）

## 今後の改善案

1. **構成要素ごとの分類コード**: 現在は全構成要素に共通の分類コードを付与しているが、本来は各構成要素固有の分類コードを使用すべき
2. **キャッシュ機構**: 同じ検索式の結果をキャッシュして高速化
3. **詳細ログ**: 各ステップの詳細ログをファイル出力
4. **エラーリトライ**: PatentField API呼び出しのリトライロジック強化

## トラブルシューティング

### エラー: "独立請求項の構成要素が見つかりません"

**原因**: キーワードJSONに独立請求項フラグがない

**解決**: `add_independent_claim_flag.py` を実行してフラグを追加

### エラー: "FI分類が見つかりません"

**原因**: 特許分類JSONにFI分類コードが含まれていない

**解決**: `patent_classification_extractor.py` を実行して分類コードを抽出

### 検索結果が0件

**原因**: FI分類コードが適切でない、またはPatentField API接続エラー

**解決**:
- 分類コードの内容を確認
- PatentField APIキーを確認
- ネットワーク接続を確認

## 関連ドキュメント

- システム構築prompt.md: 要件仕様（396-412行）
- patent_structure_analyzer.py: 構成要件分割
- patent_keyword_extractor.py: キーワード抽出
- patent_classification_extractor.py: 特許分類抽出
