# PatentField特許検索実行システム (patent_search_executor.py)

## 概要

構成要件のキーワードと特許分類コードを統合し、PatentField APIで戦略的検索を実行するシステム。

## 主な機能

1. **データ統合**: キーワードと分類コードを構成要素番号で統合
2. **戦略的検索**: 各構成要素を軸に分類コード+キーワードで検索
3. **ヒット件数自動調整**: 10-300件の目標範囲に収まるよう自動調整
4. **全文データ取得**: 請求の範囲、詳細な説明、図面を取得（オプション）

## 使用方法

### 基本的な使用

```bash
python patent_search_executor.py \
  tests/jp2014007731A_キーワード.json \
  tests/jp2014007731A_COMPLETE_classification.json
```

### オプション指定

```bash
python patent_search_executor.py \
  キーワード.json 分類.json \
  --output results.json \
  --full-text \
  --min-hits 20 --max-hits 200
```

## 検索戦略

### 基本戦略

**軸の構成要素**:
- 特許分類コードのみ使用（FI + Fterm + IPC）
- 同一要素内の分類はOR演算

**他の構成要素**:
- キーワードで補強（検索漏れ防止）
- 同一要素内のキーワードはOR演算

**異なる要素間**: AND演算

### 検索式の例

```
(FI:H01L29/78618B OR FI:H10D30/67103B OR FT:5F110BB03 OR IPC:H01L29/78)
AND
(CL:論理回路 OR CL:トランジスタ OR CL:オフ電流)
```

## ヒット件数調整

### 拡大戦略（ヒット数 < 10）

1. **試行1**: ドンピシャ分類 + ドンピシャキーワード
2. **試行2**: 上位概念分類 + ドンピシャキーワード
3. **試行3**: 上位概念分類のみ
4. **試行4**: 上位概念キーワードのみ
5. **試行5**: ドンピシャキーワードのみ

### 縮小戦略（ヒット数 > 300）

1. **試行1**: ドンピシャ分類 + ドンピシャキーワード
2. **試行2**: ドンピシャ分類 + キーワード削減
3. **試行3**: 下位概念分類 + キーワード
4. **試行4**: 下位概念分類のみ

## 入力ファイル形式

### キーワードJSON

```json
{
  "keywords": [
    {
      "構成要素番号": "1a",
      "構成要素": "論理回路",
      "重要度": 0.95,
      "ドンピシャキーワード_日本語": [
        {"keyword": "論理回路", "priority": 1}
      ],
      "上位概念キーワード_日本語": [...],
      "下位概念キーワード_日本語": [...]
    }
  ]
}
```

### 分類コードJSON

```json
{
  "classifications": {
    "FI": {
      "ドンピシャ": [{"code": "H01L29/78618B", ...}],
      "上位概念": [{"code": "H01L29/786", ...}],
      "下位概念": [{"code": "H01L29/78618B-CAAC", ...}]
    },
    "Fterm": {
      "ドンピシャ": [{"code": "5F110AA06", ...}],
      ...
    },
    "IPC": {...},
    "CPC": {...}
  }
}
```

## 出力ファイル形式

```json
{
  "status": "success",
  "search_summary": {
    "total_searches": 4,
    "successful_searches": 4,
    "total_hits": 408,
    "unique_patents": 100
  },
  "constituent_searches": [
    {
      "element_id": "1a",
      "element_text": "論理回路",
      "final_query": "...",
      "final_hits": 102,
      "final_patent_ids": ["JP...", ...]
    }
  ],
  "unique_patent_ids": [...],
  "patents": [...]  // --full-text指定時のみ
}
```

## 重要な技術的詳細

### PatentField API制約

1. **ネストした括弧禁止**: `CL:(A OR (B AND C))` は不可
2. **1レベルの括弧のみ**: `(A OR B) AND C` は可
3. **分類コードプレフィックス**:
   - FI: `FI:H01L29/78618B`
   - Fterm: `FT:5F110AA06` (注: `Fterm:`ではない)
   - IPC: `IPC:H01L29/78`
   - CPC: `CPC:G11C19/28`

### キーワードのOR演算

**正しい構文**:
```
(CL:keyword1 OR CL:keyword2 OR CL:keyword3)
```

**誤った構文**:
```
CL:(keyword1 OR keyword2 OR keyword3)  ← ネスト禁止
```

## 依存関係

- Python 3.7+
- requests
- patentfield_key.json (APIキー設定ファイル)

## APIキー設定

```json
{
  "PATENTFIELD_API_KEY": "your_api_key",
  "endpoint": "https://ttdc.patentfield.com/api/v1/patents/search"
}
```

## 実行例

```bash
# 基本実行
python patent_search_executor.py \
  tests/jp2014007731A_キーワード.json \
  tests/jp2014007731A_COMPLETE_classification.json

# 全文データ取得
python patent_search_executor.py \
  tests/jp2014007731A_キーワード.json \
  tests/jp2014007731A_COMPLETE_classification.json \
  --full-text

# カスタム目標件数
python patent_search_executor.py \
  tests/jp2014007731A_キーワード.json \
  tests/jp2014007731A_COMPLETE_classification.json \
  --min-hits 20 \
  --max-hits 200
```

## テスト結果例

```
================================================================================
PatentField特許検索実行
================================================================================

検索対象構成要素: 4個
目標ヒット件数: 10-300件

================================================================================
構成要素 1d: トランジスタにおいて、チャネル幅１μｍあたりのオフ電流...
================================================================================

  試行1: ドンピシャ分類 + ドンピシャキーワード
  ヒット件数: 102件
  ✓ 目標範囲内（10-300件）に到達

================================================================================
検索結果集計
================================================================================
  成功した検索: 4/4
  総ヒット件数: 408件
  ユニーク特許数: 100件

✓ 結果を保存: patent_search_results.json
```

## トラブルシューティング

### "invalid query" エラー

**原因**: ネストした括弧または不正な分類コードプレフィックス

**解決策**:
1. Ftermは `FT:` プレフィックスを使用
2. キーワードOR演算は `(CL:A OR CL:B)` 形式

### ヒット件数が0

**原因**: 分類コードとキーワードの組み合わせが厳しすぎる

**解決策**: システムが自動的に上位概念へ拡大（最大5回試行）

### API制限エラー

**原因**: リクエスト数またはレスポンスサイズの制限

**解決策**:
- `time.sleep()` で待機時間を調整（現在0.5秒）
- 検索対象要素数を削減

### 検索漏れ（重要な特許が見つからない）

**原因**: キーワード削減ロジックのバグ（v2.0初期版）

**症状**:
- 縮小戦略で`use_keywords = False`となり、分類コードのみの検索になる
- 技術的に関連する特許を逃す（例：JP2011171723A）

**解決策**（v2.0修正版で対応済み）:
- 縮小戦略でも`use_keywords = True`を維持
- キーワード+分類コードの組み合わせを保持
- 詳細: `tests/END_TO_END_TEST_REPORT.md` 参照

**検証方法**:
```bash
# 修正版で検索実行
python3 patent_search_executor.py \
  tests/jp2014007731A_キーワード.json \
  tests/jp2014007731A_COMPLETE_classification.json

# 結果にJP2011171723Aが含まれているか確認
grep "JP2011171723" jp2014007731A_FIXED_search_results.json
```

## エンドツーエンドテスト結果

### JP2014007731Aテストケース

詳細なテスト結果は `tests/END_TO_END_TEST_REPORT.md` を参照。

**検証内容**:
- 構成要件分割 → キーワード抽出 → 分類抽出 → 検索の完全フロー
- JP2011171723A（技術的に関連する特許）の捕捉確認
- 特許ファミリー関係の調査

**結果サマリ**:

| 検索方式 | JP2011171723A | ヒット件数 | 評価 |
|---------|--------------|----------|-----|
| SUCCESS（CL限定） | ✓ | 102件 | ◎ |
| FULLTEXT（旧版） | ✗ | 73,787件 | ✗ |
| FIXED（修正版） | ✓ | 674件 | ○ |

**重要な発見**:
1. キーワード検索は検索漏れ防止に不可欠
2. 分類コードのみでは技術的に関連する特許を逃す可能性
3. 縮小戦略でのキーワード維持が重要

## 関連ファイル

- `patent_keyword_extractor.py`: キーワード抽出システム
- `patent_classification_extractor.py`: 特許分類コード抽出システム
- `patentfield_key.json`: PatentField APIキー設定

## ライセンス

(プロジェクトのライセンスに従う)
