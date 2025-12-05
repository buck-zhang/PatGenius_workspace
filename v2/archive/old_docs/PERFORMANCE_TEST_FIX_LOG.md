# 性能テストシステム - 修正ログ

## 2025年11月26日 - パラメータ名修正

### 問題の発生

初回テスト実行時に以下のエラーが発生:

```
✗ エラー: extract() got an unexpected keyword argument 'constituents_file'
```

### 原因

`patent_classification_extractor.py`の`extract()`メソッドのパラメータ名が間違っていた。

### 修正内容

**performance_test_system.py (lines 255-257)**

```python
# 修正前
classification_result = classifier.extract(
    constituents_file=str(structure_file)
)

# 修正後
classification_result = classifier.extract(
    input_file=str(structure_file)
)
```

**根拠**: patent_classification_extractor.py:505-510で確認
```python
def extract(
    self,
    input_file: str,  # ← 正しいパラメータ名
    output_file: Optional[str] = None,
    min_importance: float = 0.9
) -> Dict:
```

### 修正実施

- 修正日時: 2025-11-26 14:44
- 修正ファイル: performance_test_system.py
- 修正箇所: line 256

### テスト再実行

```bash
python3 performance_test_system.py --limit 1
```

実行中...

### 修正履歴まとめ

これまでに修正した全てのパラメータ・メソッド名エラー:

1. **PatentField APIクエリフィールド名**: `PUB_ID:` → `pub_id:` (line 139)
2. **特許番号正規化**: A/B/Cサフィックス除去を追加 (line 129)
3. **構成要件分割メソッド名**: `analyze_patent_text()` → `analyze()` (line 197)
4. **構成要件分割パラメータ名**: `text=` → `patent_text=` (line 198)
5. **キーワード抽出メソッド名**: `extract_keywords_from_structure()` → `extract_keywords()` (line 228)
6. **キーワード抽出パラメータ名**: (暗黙的に正しかった) `constituent_json_path=` (line 229)
7. **分類抽出メソッド名**: `extract_classifications()` → `extract()` (line 255)
8. **分類抽出パラメータ名**: `constituents_file=` → `input_file=` (line 256) ← **今回の修正**

---

生成日時: 2025-11-26 14:44
システム: PatentField特許検索システム v2.0
