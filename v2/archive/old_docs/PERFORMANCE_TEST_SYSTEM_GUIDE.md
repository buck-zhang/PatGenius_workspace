# 性能テストシステム 実装ガイド

## 概要

`performance_test_system.py`は、combined_data.csvを使用して構成要件分割から検索までの一連の処理の性能を評価するシステムです。

## 実装済み機能

✅ テストデータ読み込み（CSVから上位N件抽出）
✅ 特許テキスト取得（PatentField API）
✅ 構成要件分割（Claude Sonnet 4.5）
✅ キーワード抽出（Claude Sonnet 4.5）
✅ 特許分類抽出（Claude Sonnet 4.5 + OpenSearch）
✅ 構成要素ごと検索（独立請求項のみ、並行処理）
✅ 紐づき特許検出確認
✅ 精度計算
✅ 処理時間記録
✅ トークン数記録
✅ コスト計算（日本円）

## 使用方法

### 基本実行

```bash
# デフォルト（上位30件）
python3 performance_test_system.py

# テスト件数を指定
python3 performance_test_system.py --limit 10

# 全パラメータ指定
python3 performance_test_system.py \
  --csv tests/performance_test/combined_data.csv \
  --limit 30 \
  --credentials ttdc-in-house-dev-3e07247326cb.json \
  --pf-key ../patentfield_key.json
```

### パラメータ

| パラメータ | デフォルト | 説明 |
|----------|----------|------|
| `--csv` | `tests/performance_test/combined_data.csv` | テストデータCSV |
| `--limit` | `30` | テスト件数 |
| `--credentials` | `ttdc-in-house-dev-3e07247326cb.json` | Google Cloud認証 |
| `--pf-key` | `../patentfield_key.json` | PatentField APIキー |

## 処理フロー

```
テストデータ読み込み（CSV）
  ↓
各本願特許に対してループ:
  ├─ 特許テキスト取得（PatentField API）
  ├─ 構成要件分割（Claude）→ structure.json
  ├─ キーワード抽出（Claude + PatentField）→ keywords.json
  ├─ 特許分類抽出（Claude + OpenSearch）→ classifications.json
  ├─ 構成要素ごと検索（PatentField、並行）→ search_result.json
  └─ 紐づき特許検出確認
  ↓
結果集計:
  ├─ 精度計算（検出数/成功数）
  ├─ 処理時間集計
  ├─ トークン数集計
  └─ コスト計算
```

## 出力ファイル

### ディレクトリ構造

```
tests/performance_test/results/
├── test_001_JP2013224028_structure.json
├── test_001_JP2013224028_keywords.json
├── test_001_JP2013224028_classifications.json
├── test_001_JP2013224028_search_result.json
├── test_002_JP2014007731_structure.json
├── ...
└── performance_test_summary_20251126_120000.json
```

### サマリーファイル

```json
{
  "test_date": "2025-11-26T12:00:00",
  "test_count": 30,
  "success_count": 28,
  "detection_count": 25,
  "accuracy": 0.893,
  "total_elapsed_time": 3600.5,
  "average_time_per_test": 128.6,
  "total_tokens": {
    "structure_analysis": {
      "prompt": 150000,
      "completion": 50000,
      "total": 200000
    },
    "keyword_extraction": {...},
    "classification_extraction": {...}
  },
  "cost_info": {
    "total_tokens": 430000,
    "total_cost_usd": 2.49,
    "total_cost_jpy": 373.5
  },
  "results": [...]
}
```

## コスト計算

### Claude Sonnet 4.5料金（2025年1月）

| トークンタイプ | 料金 |
|-------------|------|
| Prompt tokens | $3.00 / 1M tokens |
| Completion tokens | $15.00 / 1M tokens |

### 計算式

```
総コスト(USD) = (Prompt × $3.00/1M) + (Completion × $15.00/1M)
総コスト(JPY) = 総コスト(USD) × 150円
```

### 推定コスト

| テスト件数 | 推定コスト |
|----------|----------|
| 10件 | ¥125 |
| 30件 | ¥374 |
| 100件 | ¥1,245 |

## 精度評価

### 計算式

```
精度 = 検出成功数 / テスト成功数
```

- **検出成功**: 検索結果に紐づき特許が含まれる
- **テスト成功**: 一連の処理が正常終了

### 目標値

| レベル | 精度 |
|-------|------|
| 最低限 | 70% |
| 良好 | 80% |
| 優秀 | 90%以上 |

## 実装の詳細

### 紐づき特許検出ロジック

```python
def check_himotuki_detection(search_result, himotuki_id):
    # 番号正規化（suffix除去）
    himotuki_normalized = himotuki_id.replace('A', '').replace('B', '')

    # 部分一致で検出
    for patent_id in search_result['merged_patent_ids']:
        if himotuki_normalized in patent_id:
            return True

    return False
```

### トークン数集計

各処理（構成要件分割、キーワード抽出、分類抽出）でトークン数を記録し、累積します。

```python
self.total_tokens = {
    'structure_analysis': {'prompt': 0, 'completion': 0, 'total': 0},
    'keyword_extraction': {'prompt': 0, 'completion': 0, 'total': 0},
    'classification_extraction': {'prompt': 0, 'completion': 0, 'total': 0}
}
```

## トラブルシューティング

### エラー: "特許テキスト取得失敗"

**原因**: PatentField APIで特許が見つからない

**対処**:
- 特許番号の形式を確認
- APIキーを確認
- スキップして次へ進む（自動）

### エラー: "構成要件分割失敗"

**原因**: Claude API呼び出しエラー

**対処**:
- Google Cloud認証情報を確認
- Vertex AI API有効化を確認
- トークン制限を確認

### 処理が遅い

**原因**: 並行処理ワーカー数が少ない

**対処**:
- `max_workers`を増やす（API制限に注意）

## 性能ベンチマーク

### 1件あたりの処理時間

| 処理 | 時間 |
|-----|------|
| 特許テキスト取得 | 2-5秒 |
| 構成要件分割 | 10-20秒 |
| キーワード抽出 | 15-30秒 |
| 特許分類抽出 | 20-40秒 |
| 構成要素ごと検索 | 30-90秒 |
| **合計** | **80-180秒** |

## まとめ

性能テストシステムにより、以下が実現しました：

✅ 本願-紐づき特許の検出精度を定量評価
✅ 処理時間の測定
✅ トークン数の記録
✅ コストの計算（日本円）
✅ 大規模テストの実行基盤

このシステムを使用することで、検索システムの改善効果を定量的に評価できます。
