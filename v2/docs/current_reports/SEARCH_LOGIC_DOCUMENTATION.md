# PatentField特許検索ロジック詳細仕様

**最終更新**: 2025年11月29日
**適用システム**: patent_search_executor_per_component.py
**バージョン**: v2.0（FI分類修正版）

---

## 検索ロジック全体フロー

```
┌─────────────────────────────────────────────────────────────────┐
│ 構成要素ごと適応的検索                                          │
│ 目標: 各構成要素で50-300件の検索結果を取得                     │
└─────────────────────────────────────────────────────────────────┘
                            ↓
        ┌───────────────────────────────────────┐
        │ Step 1: ドンピシャFIのみで検索        │
        │ Query: FI:H02K33/18 OR FI:F16H35/00G │
        └───────────────────────────────────────┘
                            ↓
                    ┌───────┴───────┐
                    │  ヒット件数判定  │
                    └───────┬───────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
   [50-300件]          [> 300件]            [< 50件]
     ✅ 完了          Branch A: 絞り込み   Branch B: 拡張
                            │                   │
                            ▼                   ▼
            ┌───────────────────────┐  ┌──────────────────────┐
            │ A-1: FI AND Keyword   │  │ B-1: FI OR (上位FI  │
            │ ドンピシャFI AND      │  │      AND Keyword)   │
            │ ドンピシャキーワード  │  │                      │
            └───────────────────────┘  └──────────────────────┘
                            │                   │
                    ┌───────┴───────┐   ┌───────┴───────┐
                    │  50-300件?    │   │  50-300件?    │
                    └───────┬───────┘   └───────┬───────┘
                            │                   │
                   No       │       Yes No      │       Yes
                    ↓       ↓                   ↓       ↓
            ┌───────────────┐              ┌──────────────┐
            │ A-2: Claude   │              │ B-2: Claude  │
            │ 検索式絞り込み│              │ キーワード拡張│
            │ (AND/NOT/NEAR)│              │              │
            └───────────────┘              └──────────────┘
                    │                           │
                    ▼                           ▼
              ┌──────────┐                ┌──────────┐
              │ 最終結果 │                │ 最終結果 │
              └──────────┘                └──────────┘
```

---

## Step 1: ドンピシャFI分類のみで検索

### 目的
最も関連性の高いFI分類コードのみを使用して、初回検索を実行

### 検索式構築
```python
def _build_fi_only_query(element_id, concept_level='ドンピシャ'):
    # FI分類コードを取得
    fi_codes = get_fi_codes(element_id, 'ドンピシャ')
    
    # 空白除去（2025-11-29修正）
    valid_fi_codes = []
    for code in fi_codes:
        normalized = code.replace(' ', '')  # H02K  33/18 → H02K33/18
        if validate_fi_code(normalized):
            valid_fi_codes.append(normalized)
    
    # OR結合（最大10件）
    return ' OR '.join([f'FI:{code}' for code in valid_fi_codes[:10]])
```

### 検索式例
```
FI:H02K33/18 OR FI:F16H35/00G OR FI:F16H35/00F OR FI:F16H61/00 OR FI:H01H67/16
```

### 判定基準
- **50 ≤ ヒット件数 ≤ 300**: ✅ 完了（理想的な結果）
- **ヒット件数 > 300**: Branch A（絞り込み）へ
- **ヒット件数 < 50**: Branch B（拡張）へ

---

## Branch A: 絞り込み（ヒット数 > 300件）

### A-1: ドンピシャFI AND ドンピシャキーワード

#### 目的
FI分類とキーワードのAND条件で検索範囲を絞り込む

#### 検索式構築
```python
def _build_fi_and_keywords_query(
    element_id, 
    fi_concept_level='ドンピシャ',
    keyword_concept_level='ドンピシャ'
):
    # FI分類（正規化 + バリデーション）
    fi_codes = get_fi_codes(element_id, 'ドンピシャ')
    valid_fi_codes = []
    for code in fi_codes:
        normalized = code.replace(' ', '')
        if validate_fi_code(normalized):
            valid_fi_codes.append(normalized)
    
    fi_query = '(' + ' OR '.join([f'FI:{c}' for c in valid_fi_codes[:10]]) + ')'
    
    # キーワード（最大5件）
    keywords = get_keywords(element_id, 'ドンピシャ')
    keyword_query = '(' + ' OR '.join(keywords[:5]) + ')'
    
    # AND結合
    return f"{fi_query} AND {keyword_query}"
```

#### 検索式例
```
(FI:H02K33/18 OR FI:F16H35/00G OR FI:F16H35/00F) AND (磁極部 OR 異なる磁極を交互に配置 OR 磁極配置 OR N極S極交互配置 OR 磁極部構造)
```

#### 判定基準
- **50 ≤ ヒット件数 ≤ 300**: ✅ 完了
- **それ以外**: A-2（Claude最適化）へ

---

### A-2: Claude APIで検索式絞り込み（オプション）

#### 目的
Claude Sonnet 4.5を使用して、検索結果のTop 100件を分析し、最適化された検索式を生成

#### プロセス
1. **Top 100件取得**
   ```python
   top_results = fetch_top_results(query, limit=100)
   # 各結果には abstract と claims が含まれる
   ```

2. **Claudeプロンプト生成**
   ```python
   prompt = f"""
   # タスク: PatentField検索式の絞り込み最適化
   
   ## 現在の状況
   - 構成要素: {element_text}
   - 現在の検索式: {current_query}
   - ヒット件数: {current_hits}件 (目標: 50-300件)
   
   ## 検索結果のTop 20件サンプル
   [1] JP2012040876A
   要約: ...
   請求項: ...
   
   ## 目標
   検索結果を50-300件の範囲に絞り込む検索式を生成
   
   ## 絞り込み戦略
   1. AND条件でキーワード追加
   2. NOT条件で無関係な特許を除外
   3. NEAR演算子で複数キーワードの近接性を要求
   
   ## 出力形式
   ```json
   {
     "refined_query": "最適化された検索式",
     "reasoning": "絞り込みロジックの説明"
   }
   ```
   """
   ```

3. **Claude実行**
   ```python
   response = claude_client.messages.create(
       model="claude-sonnet-4-5@20250929",
       max_tokens=2048,
       temperature=0.0,
       messages=[{"role": "user", "content": prompt}]
   )
   ```

4. **検索式実行**
   ```python
   refined_query = claude_result['refined_query']
   hits, patent_ids = execute_patentfield_search(refined_query)
   ```

#### 生成される検索式例
```
(FI:H02K33/18 OR FI:F16H35/00G) AND (磁極部 AND 導線群) AND (*N3"磁極 配置") -"電気回路基板"
```

**特徴**:
- AND条件の追加: `磁極部 AND 導線群`
- NEAR演算子: `*N3"磁極 配置"` (3語以内の近接)
- NOT条件: `-"電気回路基板"` (無関係な特許を除外)

---

## Branch B: 拡張（ヒット数 < 50件）

### B-1: ドンピシャFI OR (上位概念FI AND ドンピシャキーワード)

#### 目的
上位概念のFI分類を使用して検索範囲を拡大

#### 検索式構築
```python
def build_expansion_query(element_id):
    # 左辺: ドンピシャFI
    left_query = build_fi_only_query(element_id, 'ドンピシャ')
    
    # 右辺: 上位概念FI AND ドンピシャキーワード
    upper_fi_codes = get_fi_codes(element_id, '上位概念')
    valid_upper_fi = [normalize(c) for c in upper_fi_codes if validate(c)]
    upper_fi_query = ' OR '.join([f'FI:{c}' for c in valid_upper_fi[:10]])
    
    keywords = get_keywords(element_id, 'ドンピシャ')
    keyword_query = ' OR '.join(keywords[:5])
    
    right_query = f"({upper_fi_query}) AND ({keyword_query})"
    
    # OR結合
    return f"({left_query}) OR ({right_query})"
```

#### 検索式例
```
(FI:H02K33/18 OR FI:F16H35/00G) OR ((FI:H02K33/00 OR FI:F16H35/00) AND (磁極部 OR 導線群 OR 平行配置))
```

**構造**:
- **左辺**: ドンピシャFI（精度重視）
- **右辺**: 上位概念FI AND キーワード（範囲拡大 + 関連性維持）

#### 判定基準
- **50 ≤ ヒット件数 ≤ 300**: ✅ 完了
- **それ以外**: B-2（Claude拡張）へ

---

### B-2: Claude APIでキーワード拡張（オプション）

#### 目的
Claude Sonnet 4.5を使用して、関連性の高い拡張キーワードを生成

#### プロセス
1. **Claudeプロンプト生成**
   ```python
   prompt = f"""
   # タスク: 特許検索用キーワードの拡張
   
   ## 現在の状況
   - 構成要素: {element_text}
   - 現在のドンピシャキーワード:
     - 磁極部
     - 導線群
     - 平行配置
   - ヒット件数: {current_hits}件 (目標: 50-300件)
   
   ## 目標
   検索範囲を拡大する拡張キーワード生成
   
   ## 拡張戦略
   1. 同義語・類義語
   2. 上位概念キーワード
   3. 関連技術用語
   4. カタカナ表記バリエーション
   
   ## 出力形式
   ```json
   {
     "expanded_keywords": ["拡張キーワード1", "拡張キーワード2", ...],
     "reasoning": "拡張ロジックの説明"
   }
   ```
   """
   ```

2. **Claude実行**
   ```python
   response = claude_client.messages.create(
       model="claude-sonnet-4-5@20250929",
       max_tokens=1024,
       temperature=0.3,  # 少し創造性を持たせる
       messages=[{"role": "user", "content": prompt}]
   )
   ```

3. **拡張キーワードで検索式再構築**
   ```python
   expanded_keywords = claude_result['expanded_keywords']
   
   # ドンピシャFI OR (上位概念FI AND 拡張キーワード)
   fi_donpisya = build_fi_only_query(element_id, 'ドンピシャ')
   upper_fi_query = build_fi_query(element_id, '上位概念')
   expanded_kw_query = ' OR '.join(expanded_keywords[:5])
   
   query = f"({fi_donpisya}) OR (({upper_fi_query}) AND ({expanded_kw_query}))"
   ```

#### 生成されるキーワード例
```json
{
  "expanded_keywords": [
    "磁石配置",
    "磁界発生部",
    "磁極構造",
    "N極S極",
    "複数磁極",
    "コイル配線",
    "巻線構造"
  ],
  "reasoning": "磁極部の同義語・上位概念と、導線群の関連技術用語を抽出"
}
```

#### 最終検索式例
```
(FI:H02K33/18 OR FI:F16H35/00G) OR ((FI:H02K33/00 OR FI:F16H35/00) AND (磁石配置 OR 磁界発生部 OR 磁極構造 OR N極S極 OR 複数磁極))
```

---

## 検索クエリ構文規則

### PatentField API対応構文

#### AND演算子
```
FI:H02K33/18 AND キーワード
FI:H02K33/18 + キーワード  （同義）
```

#### OR演算子
```
FI:H02K33/18 OR FI:F16H35/00G
キーワード1 OR キーワード2
```

#### NOT演算子
```
FI:H02K33/18 -除外キーワード
```

#### 近傍検索（NEAR演算子）
```
*N3"単語1 単語2"     # 3語以内の近接
*N5"磁極 配置"       # 5語以内の近接
```

#### グルーピング
```
(FI:H02K33/18 OR FI:F16H35/00G) AND (キーワード1 OR キーワード2)
```

#### フィールド指定
```
FI:H02K33/18        # FI分類
IPC:H02K33/18       # IPC分類
CPC:H02K33/18       # CPC分類
Fterm:5H609AA01     # Fターム
CL:キーワード       # 請求項（Claims）
AB:キーワード       # 要約（Abstract）
```

### 構文制約
- **ネスト禁止**: 括弧は1レベルのみ
  - ✅ 正: `(A OR B) AND C`
  - ❌ 誤: `A AND (B OR (C AND D))`
- **OR条件**: 同じフィールド内でのみ使用
  - ✅ 正: `FI:A OR FI:B`
  - ❌ 誤: `(FI:A OR FI:B) AND (CL:X OR CL:Y)`（複数のOR句）

---

## FI分類コード正規化（2025-11-29修正）

### 問題
Claude APIが返すFI分類コードに空白が含まれ、PatentField APIで検索失敗

### 修正内容

#### 1. 正規化関数（patent_classification_extractor.py）
```python
@staticmethod
def _normalize_classification_code(code: str) -> str:
    """
    FI分類コードの正規化（空白除去）
    
    Args:
        code: "H02K  33/18" または "F16H  35/00  G"
    
    Returns:
        "H02K33/18" または "F16H35/00G"
    """
    return code.replace(' ', '')
```

#### 2. Claude出力の正規化
```python
hierarchy = json.loads(claude_response)

# 全ての分類コードを正規化
for concept_level in ['ドンピシャ', '上位概念', '下位概念']:
    if concept_level in hierarchy:
        for item in hierarchy[concept_level]:
            if 'code' in item:
                item['code'] = _normalize_classification_code(item['code'])
```

#### 3. バリデーション強化（patent_search_executor_per_component.py）
```python
def _validate_fi_code(self, fi_code: str) -> bool:
    """FI分類コードのバリデーション"""
    if not fi_code:
        return False
    
    # 空白チェック（新規追加）
    if ' ' in fi_code:
        return False
    
    # コロン表記チェック
    if ':' in fi_code:
        return False
    
    return True
```

#### 4. 検索時の自動修復
```python
def _build_fi_only_query(element_id, concept_level='ドンピシャ'):
    fi_codes = get_fi_codes(element_id, concept_level)
    
    valid_fi_codes = []
    for code in fi_codes:
        # 空白を除去して正規化
        normalized = code.replace(' ', '')
        # バリデーション
        if _validate_fi_code(normalized):
            valid_fi_codes.append(normalized)
    
    return ' OR '.join([f'FI:{code}' for code in valid_fi_codes[:10]])
```

### 効果
- Test #3: 0件 → 1,214件（劇的改善）
- 検索成功率: 0% → 84.6%（11/13構成要素）

---

## 並行処理

### 実装
```python
def search_all_components_parallel(component_ids, max_workers=5):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_component = {
            executor.submit(search_single_component_adaptive, comp_id): comp_id
            for comp_id in component_ids
        }
        
        for future in as_completed(future_to_component):
            comp_id = future_to_component[future]
            result = future.result()
            results.append(result)
    
    return results
```

### 特徴
- **最大5ワーカー**: CPU・ネットワーク負荷のバランス
- **非同期実行**: 各構成要素の検索を並行実行
- **処理時間短縮**: シーケンシャル実行の1/3〜1/5

---

## 重複削除

### 実装
```python
def merge_and_deduplicate(search_results):
    all_patent_ids = []
    
    for result in search_results:
        patent_ids = result.get('patent_ids', [])
        all_patent_ids.extend(patent_ids)
    
    # 重複削除（順序維持）
    unique_patent_ids = list(dict.fromkeys(all_patent_ids))
    
    return {
        'total_unique_patents': len(unique_patent_ids),
        'merged_patent_ids': unique_patent_ids,
        'deduplicated_count': len(all_patent_ids) - len(unique_patent_ids)
    }
```

### 効果
- 複数構成要素で同じ特許が検出された場合、1件としてカウント
- 最終結果の精度向上

---

## パフォーマンス最適化

### 1. API呼び出し制限
```python
# FI分類: 最大10件
fi_codes[:10]

# キーワード: 最大5件
keywords[:5]

# Top結果取得: 最大100件（絞り込み用）
fetch_top_results(query, limit=100)
```

### 2. タイムアウト設定
```python
# 通常の検索: 60秒
response = requests.post(endpoint, json=payload, timeout=60)

# Top結果取得: 120秒（データ量が多いため）
response = requests.post(endpoint, json=payload, timeout=120)
```

### 3. リトライロジック
```python
@retry(
    retry=retry_if_exception_type((Exception,)),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(3),
    reraise=False
)
def _call_claude_for_refinement(prompt):
    # Claude API呼び出し
    ...
```

---

## 検索結果の評価基準

### ステータス
- **success**: 目標範囲内（50-300件）
- **out_of_range**: 範囲外だが検索成功
- **no_fi_codes**: FI分類コードなし
- **error**: 検索エラー

### 検索試行の記録
```python
{
    'element_id': '1a',
    'element_text': '異なる磁極を交互に配置した磁極部',
    'final_query': '(FI:H02K33/18 OR FI:F16H35/00G) AND (磁極部 OR 導線群)',
    'final_hits': 120,
    'patent_ids': ['JP2012040876A', ...],
    'attempts': [
        {
            'step': '1',
            'strategy': 'ドンピシャFIのみ',
            'query': 'FI:H02K33/18 OR FI:F16H35/00G',
            'hits': 10231
        },
        {
            'step': 'A-1',
            'strategy': 'ドンピシャFI AND ドンピシャキーワード',
            'query': '(FI:H02K33/18 OR FI:F16H35/00G) AND (磁極部 OR 導線群)',
            'hits': 120
        }
    ],
    'status': 'success'
}
```

---

## トラブルシューティング

### 検索結果0件

#### 原因1: FI分類コードの空白
```
❌ 不正: "H02K  33/18"
✅ 正常: "H02K33/18"
```
**対処**: 2025-11-29修正で自動修復対応済み

#### 原因2: コロン表記の分類コード
```
❌ 不正: "F21Y115:30" （インデキシングコード）
```
**対処**: バリデーションで自動除外

#### 原因3: キーワードが一般的すぎる
**対処**: 
- ドンピシャキーワードの見直し
- FI AND キーワード の併用

### Claude API未初期化

#### 原因
Google Cloud認証情報が見つからない

#### 対処
```bash
# 認証情報ファイルの確認
ls -la ../gcp-sa-key.json

# 明示的に指定
python3 patent_search_executor_per_component.py \
  --credentials ../gcp-sa-key.json \
  ...
```

---

## まとめ

### 検索ロジックの特徴
1. **適応的検索**: ヒット件数に応じて動的に戦略変更
2. **3段階最適化**: ドンピシャ → AND/OR → Claude
3. **自動修復**: FI分類コードの空白除去
4. **並行処理**: 最大5ワーカーで高速実行
5. **重複削除**: 構成要素間の重複を自動除去

### 検索精度
- **目標範囲内**: 50-300件
- **現在の達成率**: 7.7%（1/13構成要素、Test #3の場合）
- **検索成功率**: 84.6%（11/13構成要素で検索結果あり）

### 今後の改善
1. Claude API最適化機能の有効化
2. 検索範囲の最適化（30-500件など）
3. キーワード抽出精度の向上
4. IPC/CPC分類の積極活用

---

**ドキュメント作成日**: 2025年11月29日
**作成者**: Claude Code
**適用バージョン**: patent_search_executor_per_component.py v2.0
