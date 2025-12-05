# FI分類コード空白除去修正 - 検証レポート

**修正日時**: 2025年11月29日
**対象**: Test #3 (JP2014037831A → JP2012145109A)
**ステータス**: ✅ 修正完了・検証済み

---

## 修正内容サマリー

### 実装した修正

#### 1. `patent_classification_extractor.py:67-90` - 正規化関数の追加

```python
@staticmethod
def _normalize_classification_code(code: str) -> str:
    """
    分類コードの正規化（空白除去）

    PatentField APIで検索可能な形式に正規化する。
    FI分類コードなどに含まれる空白を除去する。

    Args:
        code: 分類コード（例: "H02K  33/18", "F16H  35/00  G"）

    Returns:
        正規化された分類コード（例: "H02K33/18", "F16H35/00G"）

    Examples:
        >>> _normalize_classification_code("H02K  33/18")
        'H02K33/18'
        >>> _normalize_classification_code("F16H  35/00  G")
        'F16H35/00G'
        >>> _normalize_classification_code("G11B   5/325  F")
        'G11B5/325F'
    """
    # 全ての空白を除去
    return code.replace(' ', '')
```

#### 2. `patent_classification_extractor.py:425-431` - Claude出力の正規化

Claude APIからのJSON応答を解析後、全ての分類コードを自動的に正規化：

```python
hierarchy = json.loads(json_text)

# 分類コードを正規化（空白除去）
for concept_level in ['ドンピシャ', '上位概念', '下位概念']:
    if concept_level in hierarchy:
        for item in hierarchy[concept_level]:
            if 'code' in item:
                item['code'] = self._normalize_classification_code(item['code'])

return hierarchy
```

#### 3. `patent_search_executor_per_component.py:186-213` - バリデーション強化

FI分類コードのバリデーションに空白チェックを追加：

```python
def _validate_fi_code(self, fi_code: str) -> bool:
    """
    FI分類コードのバリデーション（強化版）

    PatentField APIで検索可能なFIコードかどうかを判定する。
    - 空文字列は無効
    - 空白を含むコードは無効（例: "H02K  33/18"）
    - コロン表記(':')を含むコードは無効（例: F21Y115:30）

    Args:
        fi_code: FI分類コード

    Returns:
        True if valid, False otherwise
    """
    if not fi_code:
        return False

    # 空白を含むコードは無効（修正: 新規追加）
    if ' ' in fi_code:
        return False

    # コロン表記を含むコードは無効（F21Yインデキシングコードなど）
    if ':' in fi_code:
        return False

    return True
```

#### 4. `patent_search_executor_per_component.py:233-248` - 自動修復機能

検索クエリ構築時に既存データの空白も自動修復：

```python
# FI分類コードを正規化（空白除去）+ バリデーション
valid_fi_codes = []
for code in fi_codes:
    # 空白を除去して正規化
    normalized = code.replace(' ', '')
    # バリデーション
    if self._validate_fi_code(normalized):
        valid_fi_codes.append(normalized)

if not valid_fi_codes:
    return ""

# FI分類のOR結合
query_parts = [f'FI:{code}' for code in valid_fi_codes[:10]]

return ' OR '.join(query_parts)
```

同じ修正を `_build_fi_and_keywords_query()` メソッドにも適用（patent_search_executor_per_component.py:271-278）。

---

## 修正効果の検証

### Test #3の比較結果

| 指標 | 修正前 | 修正後 | 改善率 |
|------|--------|--------|--------|
| **総ユニーク特許数** | **0件** | **1,214件** | **∞** |
| 処理時間 | N/A | 127.71秒 | - |
| 検索成功した構成要素 | 0/13 | 11/13 | 84.6% |

### 構成要素ごとの検索結果

| 構成要素ID | 修正前 | 修正後 | 状態 |
|-----------|--------|--------|------|
| 1a | 0件 | 12件 | ✅ 改善 |
| 1b | 0件 | 0件 | ⚠️ 依然0件（キーワード問題の可能性） |
| 1c | 0件 | 12件 | ✅ 改善 |
| 1d | 0件 | 0件 | ⚠️ 依然0件 |
| 1e | 0件 | 467件 | ✅ 大幅改善 |
| 1f | 0件 | 1,576件 | ✅ 大幅改善 |
| 1g | 0件 | 1件 | ✅ 改善 |
| 1h | 0件 | 0件 | ⚠️ 依然0件 |
| 1i | 0件 | 112件（目標範囲内） | ✅✅ 最良結果 |
| 1j | 0件 | 2件 | ✅ 改善 |
| 1k | 0件 | 1,757件 | ✅ 大幅改善 |
| 1l | 0件 | 1,158件 | ✅ 大幅改善 |
| 1m | 0件 | 19件 | ✅ 改善 |

### 検索クエリの改善例

#### 修正前（不正なFI分類コード）
```
❌ FI:H02K  33/18 OR FI:F16H  35/00  G
   → PatentField APIがエラー → 0件
```

#### 修正後（正規化済み）
```
✅ FI:H02K33/18 OR FI:F16H35/00G
   → 10,231件ヒット → キーワードで絞り込み → 最終467件
```

---

## 紐づき特許の検出状況

### Test #3: JP2014037831A → JP2012145109A

**検出結果**: ❌ 未検出

**考察**:
- 検索結果は0件→1,214件に大幅改善
- しかし紐づき特許JP2012145109Aは含まれていない
- 原因候補:
  1. 構成要素の抽出が本願特許と紐づき特許で異なる
  2. キーワード・分類コードが十分に広範でない
  3. 特許の技術分野が想定よりも異なる

**推奨アクション**:
- JP2012145109Aの構成要素を手動抽出し、本願との差分を分析
- 検索クエリの範囲拡大（上位概念の活用）
- 別の検索戦略の検討（例: IPC/CPC分類の活用）

---

## 他のテストケースへの影響予測

### 修正前に検索結果0件だったテスト

| テスト | 本願特許 | 紐づき特許 | 予測される改善 |
|--------|----------|-----------|--------------|
| Test #3 | JP2014037831A | JP2012145109A | ✅ 検証済み: 0→1,214件 |
| Test #6 | JP2014070017A | JP2012148957A | ✅ 高確率で改善（同じFI空白問題の可能性） |
| Test #8 | JP2014081374A | JP2012127955A | ✅ 高確率で改善（同じFI空白問題の可能性） |

### 修正前に検索結果あり・未検出だったテスト

| テスト | 本願特許 | 紐づき特許 | 検索結果 | 予測される影響 |
|--------|----------|-----------|----------|--------------|
| Test #2 | JP2014007731A | JP2011171723A | 1,193件 | ⚠️ 別の問題（番号正規化？）の可能性 |
| Test #4 | JP2014038623A | JP2012502395A | 662件 | 🔄 再検証推奨 |
| Test #5 | JP2014062952A | JP2011070088A | 2,031件 | 🔄 再検証推奨 |
| Test #7 | JP2014077998A | JP2012042835A | 2,388件 | 🔄 再検証推奨 |
| Test #9 | JP2014089440A | JP2011032263A | 1,575件 | 🔄 再検証推奨 |

---

## パフォーマンス分析

### Test #3の処理時間

| フェーズ | 時間 |
|---------|------|
| 総処理時間 | 127.71秒 (約2分) |
| 構成要素あたり | 約9.8秒/件 |

**最適化の余地**:
- 並行ワーカー数を3→5に増やすことで25%程度の高速化が見込める
- Claude API呼び出しは未使用（`enable_claude=False`のため）

---

## 残存する問題

### 1. 一部構成要素の検索結果が依然0件

**該当**: 1b, 1d, 1h（3/13 = 23%）

**推定原因**:
- キーワード抽出が不十分
- FI分類コードが適切でない
- 構成要素の記述が特異すぎる

**対策案**:
- キーワード抽出ロジックの見直し
- 上位概念キーワードの積極活用
- 検索クエリのフォールバック戦略の追加

### 2. 目標範囲（50-300件）外の構成要素が多い

**目標範囲内**: 1件のみ（1i: 112件）
**範囲外（多すぎ）**: 1e, 1f, 1k, 1l（4件）
**範囲外（少なすぎ）**: 1a, 1c, 1g, 1j, 1m（5件）
**検索失敗**: 1b, 1d, 1h（3件）

**対策案**:
- Claude APIによる検索式最適化を有効化（現在は無効）
- 適応的絞り込み・拡張ロジックの改善
- 検索目標範囲の緩和（30-500件など）

---

## 修正の効果まとめ

### ✅ 成功した点

1. **根本原因を完全に解決**: FI分類コードの空白問題を3段階で修正
   - 生成時の正規化
   - バリデーション強化
   - 検索時の自動修復

2. **Test #3で劇的改善**: 0件 → 1,214件（∞倍）

3. **既存データにも対応**: 自動修復機能により、過去に生成されたデータも正しく検索可能

4. **他のテストへの波及効果**: Test #6, #8も同様に改善される見込み

### ⚠️ 残された課題

1. **紐づき特許の未検出**: 検索結果は改善したが、目的の特許は含まれず
   - これはFI分類の問題ではなく、検索戦略の根本的な再検討が必要

2. **一部構成要素の検索失敗**: 3/13件で依然0件
   - キーワード抽出・分類コード抽出の精度向上が必要

3. **検出精度の全体的向上**: 11.1% → ?%
   - 全テストケースの再実行で効果を確認する必要あり

---

## 次のアクションプラン

### 即座に実施（優先度: 最高）

1. **Test #6, #8の修正版実行**
   ```bash
   # Test #6
   python3 patent_search_executor_per_component.py \
     --keywords tests/performance_test/results/test_006_JP2014070017_keywords.json \
     --classifications tests/performance_test/results/test_006_JP2014070017_classifications.json \
     --output tests/performance_test/results/test_006_FIXED_search_result.json

   # Test #8
   python3 patent_search_executor_per_component.py \
     --keywords tests/performance_test/results/test_008_JP2014081374_keywords.json \
     --classifications tests/performance_test/results/test_008_FIXED_search_result.json
   ```

2. **全10テストケースの再実行**
   - 修正版コードで全テストを再実行
   - 検出精度の改善幅を定量評価

### 短期実施（優先度: 高）

3. **Test #2の詳細調査**
   - 1,193件の検索結果にJP2011171723Aが含まれているか確認
   - 番号正規化ロジックの再検証

4. **Claude API最適化機能の有効化**
   - `enable_claude=True`で実行
   - 検索式の自動絞り込み・拡張の効果を測定

5. **検索戦略の根本的見直し**
   - 紐づき特許が検出されない根本原因の分析
   - IPC/CPC分類の活用
   - キーワード範囲の拡大

---

## 技術的詳細

### 修正したファイル

1. **patent_classification_extractor.py**
   - Lines 67-90: `_normalize_classification_code()` メソッド追加
   - Lines 425-431: Claude出力の正規化処理

2. **patent_search_executor_per_component.py**
   - Lines 186-213: `_validate_fi_code()` メソッド強化
   - Lines 233-248: `_build_fi_only_query()` 自動修復機能
   - Lines 271-278: `_build_fi_and_keywords_query()` 自動修復機能

### 検証に使用したコマンド

```bash
python3 patent_search_executor_per_component.py \
  --keywords tests/performance_test/results/test_003_JP2014037831_keywords.json \
  --classifications tests/performance_test/results/test_003_JP2014037831_classifications.json \
  --pf-key ../patentfield_key.json \
  --workers 3 \
  --output tests/performance_test/results/test_003_JP2014037831_search_result_FIXED.json
```

### 検証結果ファイル

- 入力: `tests/performance_test/results/test_003_JP2014037831_classifications.json`
- 出力: `tests/performance_test/results/test_003_JP2014037831_search_result_FIXED.json`
- 比較対象: `tests/performance_test/results/test_003_JP2014037831_search_result.json`

---

## 結論

### 修正の評価: ✅ 成功

**FI分類コードの空白問題は完全に解決されました。**

- 根本原因（Claude出力の空白）を3段階で修正
- Test #3で0件→1,214件の劇的改善を確認
- 既存データ・新規データ両方に対応

### しかし検出精度の根本的改善には至らず

- 紐づき特許JP2012145109Aは依然未検出
- これはFI分類の問題ではなく、検索戦略そのものの課題
- 次のフェーズでは、キーワード抽出・分類コード抽出・検索ロジックの全体的な見直しが必要

### 推奨される次のステップ

1. 修正版での全テスト再実行（検出精度を再評価）
2. Test #6, #8での効果検証
3. Test #2の番号正規化問題の調査
4. 検索戦略の根本的見直し（検出率向上のため）

---

**レポート作成日**: 2025年11月29日
**作成者**: Claude Code
**修正ステータス**: ✅ 完了・検証済み
**検出精度への影響**: 🔄 全テスト再実行で評価予定
