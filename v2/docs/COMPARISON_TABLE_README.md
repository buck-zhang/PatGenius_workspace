# 構成対比表生成機能 - 使用ガイド

**バージョン**: v2.1.2
**作成日**: 2025年12月11日
**システム**: PatentGenius Zhang Opera

---

## 📋 概要

構成対比表生成機能は、進歩性判断エンジン（v2.1.2）の結果から、弁理士が拒絶理由通知への対応や特許性評価を行うための**構成対比表**を自動生成する機能です。

### 主な機能

1. ✅ **X文献との構成対比**: 単独で全要素を開示する先行技術との対比
2. ✅ **Y文献との構成対比**: 主引例・副引例の組み合わせとの対比
3. ✅ **Excel形式での出力**: 色分け、フィルター付きの読みやすい表
4. ✅ **Markdown形式での出力**: GitHubやレポートへの埋め込み用

---

## 🎯 生成される構成対比表の形式

### 表の列構成

| 列名 | 説明 |
|------|------|
| 構成要素番号 | 1a, 1b, ... 5d |
| 構成要素概要 | 各要素の簡単な説明 |
| X文献 | 開示状況（✓ または －） |
| X文献の記載内容 | 該当箇所の引用文 |
| X文献の記載箇所 | 請求項1、段落0025等 |
| Y文献（主引例） | 開示状況（✓ または －） |
| Y文献（主引例）の記載内容 | 該当箇所の引用文 |
| Y文献（主引例）の記載箇所 | 請求項5等 |
| Y文献（副引例） | 開示状況（✓ または －） |
| Y文献（副引例）の記載内容 | 該当箇所の引用文 |
| Y文献（副引例）の記載箇所 | 段落0021等 |

### Excel版の特徴

- **色分け**:
  - 🟢 緑色: 開示あり
  - 🔴 赤色: 開示なし
- **フィルター機能**: 各列でフィルタリング可能
- **ウィンドウ枠固定**: ヘッダー行が常に表示
- **自動列幅調整**: 内容に応じた最適な列幅
- **テキスト折り返し**: 長文も見やすく表示

---

## 🚀 使用方法

### 1. コマンドラインから直接実行

```bash
python3 src/comparison_table_generator.py \
  <進歩性判断サマリーJSON> \
  <構成対比結果ディレクトリ> \
  <本願特許構成要素JSON> \
  <出力ファイルパス> \
  [format]
```

**パラメータ**:
- `<進歩性判断サマリーJSON>`: `novelty_assessment_summary.json`のパス
- `<構成対比結果ディレクトリ>`: `comparison_*.json`ファイルが格納されたディレクトリ
- `<本願特許構成要素JSON>`: `*_structure.json`のパス
- `<出力ファイルパス>`: 出力先のファイルパス
- `[format]`: 出力形式（`excel` または `markdown`、デフォルト: `excel`）

**実行例**:
```bash
python3 src/comparison_table_generator.py \
  novelty_assessment_results/test_001/novelty_assessment_summary.json \
  novelty_assessment_results/test_001/ \
  tests/performance_test/results/test_001_JP2013224028_structure.json \
  comparison_tables/comparison_table_JP2013224028.xlsx \
  excel
```

---

### 2. Pythonスクリプトから使用

```python
from comparison_table_generator import ComparisonTableGenerator

# 生成器の初期化
generator = ComparisonTableGenerator()

# 構成対比表を生成
output_file = generator.generate_comparison_table(
    assessment_summary_path="novelty_assessment_results/test_001/novelty_assessment_summary.json",
    comparison_results_dir="novelty_assessment_results/test_001/",
    base_structure_path="tests/performance_test/results/test_001_JP2013224028_structure.json",
    output_path="comparison_tables/comparison_table_JP2013224028.xlsx",
    format="excel"  # または "markdown"
)

print(f"生成完了: {output_file}")
```

---

### 3. テストスクリプトで実行

```bash
python3 src/test_comparison_table.py
```

このスクリプトは、v2.1.2のテスト結果（test_001_JP2013224028）を用いて、Excel形式とMarkdown形式の両方で構成対比表を生成します。

---

## 📊 Y文献の選択ロジック

複数のY文献組み合わせがある場合、最も重要な**1件**を自動選択します。

### 選択基準（優先順位順）

1. **主引例の開示要素数が最多**の組み合わせ
2. 同数の場合、**副引例の開示要素数が最少**の組み合わせ
3. それでも同じ場合、**主引例の特許番号が最も古い**組み合わせ

### 選択理由

実務上、審査官は以下の組み合わせを好む傾向があります:
- 主引例の開示が最も多い（主引例が「最も近い先行技術」）
- 副引例の補足が最小限（組み合わせの容易性を示しやすい）

---

## 🎨 出力例

### Excel形式（イメージ）

| 要素番号 | 要素概要 | X文献<br>JP2013224028 | 記載内容 | 記載箇所 | Y文献（主引例）<br>JP2013224028 | 記載内容 | 記載箇所 |
|---------|---------|---------------------|---------|---------|--------------------------|---------|---------|
| **1a** | インクジェットプリントヘッド前面のための被膜 | ✓ 🟢 | "インクジェットプリントヘッド前面のための被膜であって" | 請求項1 | ✓ 🟢 | 同左 | 請求項1 |
| **1f-2** | エチルオキシドスペーサーを有する材料 | ✓ 🟢 | "エチルオキシド（ｅｔｈｙｌｏｘｉｄｅ）スペーサーを有する..." | 請求項5 | ✓ 🟢 | 同左 | 請求項5 |
| 4b | 140℃で2日間のインク浸漬試験 | ✓ 🟢 | "溶融した固体インクまたはＵＶゲルインク中に約１４０℃の温度で２日間浸漬..." | 請求項4 | － 🔴 | - | - |

**注**:
- 🟢 緑色のセル = 開示あり
- 🔴 赤色のセル = 開示なし
- **太字** = 独立請求項の構成要素

---

### Markdown形式（実際の出力）

```markdown
| 要素番号 | 要素概要 | X文献<br>JP2013224028 | 記載内容 | 記載箇所 |
|---------|---------|---------------------|---------|---------|
| **1a** | インクジェットプリントヘッド前面のための被膜 | ✅ | "インクジェットプリントヘッド..." | 請求項1 |
| **1f-2** | エチルオキシドスペーサーを有する材料 | ✅ | "エチルオキシド（ｅｔｈｙｌｏｘｉｄｅ）..." | 請求項5 |
| 4b | 140℃で2日間のインク浸漬試験 | ❌ | - | - |
```

凡例: ✅ = 開示あり, ❌ = 開示なし

---

## 📂 ファイル構成

### 生成されるファイル

```
comparison_tables/
├── comparison_table_test_001_JP2013224028.xlsx    # Excel形式
└── comparison_table_test_001_JP2013224028.md      # Markdown形式
```

### 入力ファイル

```
novelty_assessment_results/test_001_JP2013224028/
├── novelty_assessment_summary.json                # 進歩性判断サマリー
├── comparison_JP2013224028.json                   # X文献の構成対比結果
├── comparison_JP2013086509.json                   # その他の構成対比結果
└── ...

tests/performance_test/results/
└── test_001_JP2013224028_structure.json           # 本願特許の構成要素
```

---

## 🔍 詳細な機能説明

### 1. データ読み込み

```python
# 進歩性判断サマリーから X文献・Y文献を取得
summary = {
    "x_references": {
        "count": 1,
        "patents": ["JP2013224028"]
    },
    "y_references": {
        "count": 18,
        "combinations": [
            {
                "primary_reference": "JP2013224028",
                "secondary_references": ["JP2013086509"],
                "combination_count": 2,
                "coverage": {...}
            },
            ...
        ]
    },
    "priority_level_used": "x_priority_1_all_elements|priority_1_k2_all_elements"
}
```

### 2. 代表的なY文献の選択

```python
def _select_representative_y_reference(y_combinations):
    # スコアリング: (主引例カバレッジ, -副引例カバレッジ, -主引例ID)
    scored = []
    for combo in y_combinations:
        primary_coverage = len(combo['coverage'][combo['primary_reference']])
        secondary_coverage = sum(len(combo['coverage'][sec])
                                 for sec in combo['secondary_references'])
        score = (primary_coverage, -secondary_coverage, ...)
        scored.append((score, combo))

    # 最良のスコアを選択
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]
```

### 3. 表データの構築

各構成要素について、以下の情報を収集:
- 要素ID、要素説明
- X文献の開示状況、記載内容、記載箇所
- Y文献（主引例）の開示状況、記載内容、記載箇所
- Y文献（副引例）の開示状況、記載内容、記載箇所

### 4. Excel形式での出力

openpyxlライブラリを使用して:
- ヘッダー行の書式設定（青色背景、白文字）
- データ行の色分け（緑色 = 開示あり、赤色 = 開示なし）
- セルの罫線、テキスト折り返し
- 列幅の自動調整
- フィルター機能の追加
- ウィンドウ枠の固定

---

## 🎯 実務での活用方法

### 1. 拒絶理由通知への対応

**構成対比表を用いた対応フロー**:

1. **差別化要素の特定**:
   - 赤色のセル（開示なし）を確認
   - 特に副引例で未開示の要素が重要

2. **意見書の作成**:
   - 差別化要素の技術的意義を説明
   - 予想外の効果を主張

3. **補正書の作成**:
   - 差別化要素を独立請求項に追加
   - 権利範囲を最適化

### 2. 出願前の特許性評価

**構成対比表を用いた評価**:

1. **新規性の評価**:
   - X文献の列を確認
   - 全要素が開示されている場合、新規性喪失リスク高

2. **進歩性の評価**:
   - Y文献の列を確認
   - 主引例と副引例の組み合わせで全要素がカバーされる場合、進歩性欠如リスク高

3. **差別化戦略の立案**:
   - 開示率の低い要素（赤色が多い）を強調
   - 請求項の記載を最適化

### 3. ライセンス交渉

**構成対比表を用いた交渉**:

1. **侵害分析**:
   - 競合製品が全要素を実施しているか確認
   - 文言侵害、均等論の検討

2. **無効資料の調査**:
   - X文献・Y文献の詳細調査
   - 追加の先行技術調査

---

## ⚙️ カスタマイズ

### 色のカスタマイズ

`comparison_table_generator.py`のスタイル定義を変更:

```python
class ComparisonTableGenerator:
    def __init__(self):
        # ヘッダー行の色（青色）
        self.header_fill = PatternFill(
            start_color="366092",
            end_color="366092",
            fill_type="solid"
        )

        # 開示ありの色（薄い緑）
        self.disclosed_fill = PatternFill(
            start_color="C6EFCE",  # お好みの色コードに変更
            end_color="C6EFCE",
            fill_type="solid"
        )

        # 開示なしの色（薄い赤）
        self.not_disclosed_fill = PatternFill(
            start_color="FFC7CE",  # お好みの色コードに変更
            end_color="FFC7CE",
            fill_type="solid"
        )
```

### 列幅のカスタマイズ

```python
# 列幅の調整（_export_to_excelメソッド内）
ws.column_dimensions['A'].width = 12   # 構成要素番号
ws.column_dimensions['B'].width = 40   # 構成要素概要（お好みの幅に変更）
ws.column_dimensions['D'].width = 50   # X文献記載内容（お好みの幅に変更）
...
```

---

## 🐛 トラブルシューティング

### エラー: "No module named 'openpyxl'"

**原因**: openpyxlライブラリがインストールされていない

**解決方法**:
```bash
python3 -m pip install --user openpyxl tabulate
```

### エラー: "FileNotFoundError"

**原因**: 入力ファイルのパスが間違っている

**解決方法**:
1. パスが正しいか確認
2. ファイルが存在するか確認
3. 絶対パスを使用

### Y文献が選択されない

**原因**: Y文献の組み合わせが0件

**解決方法**:
1. 進歩性判断結果を確認
2. `novelty_assessment_summary.json`の`y_references.count`を確認
3. 検索結果の特許数を増やす

---

## 📚 関連ドキュメント

1. **進歩性判断エンジン**: `docs/NOVELTY_ASSESSMENT_README.md`
2. **テスト結果詳細**: `docs/current_reports/テスト結果詳細_v2.1.2_20251211.md`
3. **CHANGELOG**: `CHANGELOG.md` (v2.1.2セクション)

---

## 🎉 まとめ

構成対比表生成機能により、弁理士は以下の作業を効率化できます:

1. ✅ 拒絶理由通知への迅速な対応
2. ✅ 出願前の特許性評価の精度向上
3. ✅ 差別化要素の明確な特定
4. ✅ 意見書・補正書の作成時間短縮

**v2.1.2の構成対比表生成機能で、特許実務を次のレベルへ！**

---

**作成者**: Claude Sonnet 4.5
**作成日**: 2025年12月11日
**バージョン**: v2.1.2
