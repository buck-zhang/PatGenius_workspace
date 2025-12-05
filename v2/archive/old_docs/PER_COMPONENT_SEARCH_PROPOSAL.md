# 構成要素別並行検索システム提案書

**作成日**: 2025-11-26
**対象システム**: patent_search_executor.py
**目的**: 各構成要素ごとに独立した検索を並行実行し、Recallを最大化

---

## 1. 現状分析

### 現在のシステム (`patent_search_executor.py`)

**検索戦略**:
- 全構成要素を統合した1つの検索式を段階的に調整
- 各構成要素を「軸」として扱う設計だが、実際には統合検索
- ヒット件数10-300件を目標に調整

**問題点**:
1. **カバレッジ不足**: 1つの検索式で全構成要素をカバーするため、各構成要素の最適な検索ができない
2. **調整の困難**: 1つの構成要素を調整すると他の構成要素に影響
3. **Recall低下**: 現在のRecall 0% (tests/performance_test/performance_test.log line 762)

---

## 2. ユーザー要求の理解

### 新しい検索アーキテクチャ

```
全体フロー:
┌─────────────────────────────────────────────────────────────┐
│ 構成要素1  構成要素2  構成要素3  ... 構成要素N              │
│    ↓          ↓          ↓              ↓                   │
│ 並行処理 (concurrent.futures.ThreadPoolExecutor)            │
│    ↓          ↓          ↓              ↓                   │
│ 結果1     結果2     結果3     ...    結果N                  │
└─────────────────────────────────────────────────────────────┘
                          ↓
            ┌─────────────────────────┐
            │  結果統合 (Union)        │
            │  重複削除 (Deduplication)│
            └─────────────────────────┘
                          ↓
                    最終検索結果
```

### 各構成要素の検索ロジック

```python
def search_single_component(component):
    """
    単一構成要素の検索ロジック
    """
    # Step 1: ドンピシャFI (OR条件) で検索
    query1 = build_exact_fi_query(component)
    hits1 = patentfield_search(query1)

    if 50 < len(hits1) < 300:
        return hits1  # ✓ 完了

    # Step 2: ヒット数 > 300 の場合
    elif len(hits1) > 300:
        query2 = f"{query1} AND {build_exact_keywords_query(component)}"
        hits2 = patentfield_search(query2)
        return hits2  # ✓ 完了

    # Step 3: ヒット数 < 50 の場合
    else:  # len(hits1) < 50
        broader_fi = build_broader_fi_query(component)
        exact_keywords = build_exact_keywords_query(component)
        query3 = f"{query1} OR ({broader_fi} AND {exact_keywords})"
        hits3 = patentfield_search(query3)
        return hits3  # ✓ 完了
```

### 並行処理による高速化

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def parallel_search_all_components(components):
    """
    全構成要素を並行検索
    """
    results = []

    with ThreadPoolExecutor(max_workers=5) as executor:  # API制限考慮
        # 全構成要素の検索を並行実行
        future_to_component = {
            executor.submit(search_single_component, comp): comp
            for comp in components
        }

        for future in as_completed(future_to_component):
            component = future_to_component[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"構成要素 {component['id']} エラー: {e}")

    # 結果統合と重複削除
    all_patents = set()
    for result in results:
        all_patents.update(result['patent_ids'])

    return list(all_patents)
```

---

## 3. 2025年ベストプラクティス調査結果

### 並行処理 (Python 2025)

**推奨アプローチ**: `concurrent.futures.ThreadPoolExecutor`

**理由**:
1. **I/O bound問題に最適**: PatentField API呼び出しはネットワークI/O
2. **シンプルな実装**: asyncioより学習コストが低い
3. **既存コードとの統合が容易**: requestsライブラリをそのまま使用可能
4. **Python 3.13対応**: デフォルトmax_workers = min(32, (os.process_cpu_count() or 1) + 4)

**コード例**:
```python
from concurrent.futures import ThreadPoolExecutor
import requests

def search_component(component_id):
    response = requests.post(api_endpoint, json=payload)
    return response.json()

with ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(search_component, component_ids))
```

### API レート制限対策 (2025)

**推奨ライブラリ**: `ratelimit` + `tenacity`

```python
from ratelimit import limits, sleep_and_retry
from tenacity import retry, stop_after_attempt, wait_exponential

# PatentField API: 推定レート制限 10 req/sec
@sleep_and_retry
@limits(calls=10, period=1)  # 10 calls per second
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def patentfield_api_call(query):
    response = requests.post(endpoint, json=query)
    response.raise_for_status()
    return response.json()
```

### 特許検索最適化 (2025)

**参考**: Google Query Fan-Out Patent (2025)

- 複数のサブクエリに分割して並行検索
- 各サブクエリは独立して最適化
- 結果を統合してランキング

**当システムへの適用**:
- 各構成要素 = 1つのサブクエリ
- 構成要素ごとに最適な検索式を自動調整
- 統合後に重要度でランキング

---

## 4. 提案実装設計

### 新クラス構造

```python
class ParallelComponentSearchExecutor:
    """
    構成要素別並行検索エグゼキューター (v3.0)
    """

    def __init__(self, keywords_file, classifications_file, max_workers=5):
        """
        Args:
            max_workers: 並行検索ワーカー数 (デフォルト: 5)
                        PatentField APIレート制限を考慮
        """
        self.max_workers = max_workers
        # データ読み込み...

    def search_single_component(self, component_id: str) -> Dict:
        """
        単一構成要素の検索ロジック

        Returns:
            {
                'component_id': '1a',
                'patent_ids': ['JP2012040876', ...],
                'query': '検索式',
                'hit_count': 125,
                'strategy': 'exact_fi_only'  # or 'exact_fi_and_keywords' or 'expanded'
            }
        """
        # Step 1: ドンピシャFI検索
        exact_fi_query = self._build_exact_fi_query(component_id)
        exact_fi_results = self._execute_search(exact_fi_query)

        if 50 < len(exact_fi_results) < 300:
            return {
                'component_id': component_id,
                'patent_ids': exact_fi_results,
                'query': exact_fi_query,
                'hit_count': len(exact_fi_results),
                'strategy': 'exact_fi_only'
            }

        # Step 2: ヒット数 > 300 → AND絞り込み
        elif len(exact_fi_results) > 300:
            exact_kw_query = self._build_exact_keywords_query(component_id)
            combined_query = f"{exact_fi_query} AND {exact_kw_query}"
            combined_results = self._execute_search(combined_query)

            return {
                'component_id': component_id,
                'patent_ids': combined_results,
                'query': combined_query,
                'hit_count': len(combined_results),
                'strategy': 'exact_fi_and_keywords'
            }

        # Step 3: ヒット数 < 50 → OR拡張
        else:
            broader_fi_query = self._build_broader_fi_query(component_id)
            exact_kw_query = self._build_exact_keywords_query(component_id)
            expanded_query = f"{exact_fi_query} OR ({broader_fi_query} AND {exact_kw_query})"
            expanded_results = self._execute_search(expanded_query)

            return {
                'component_id': component_id,
                'patent_ids': expanded_results,
                'query': expanded_query,
                'hit_count': len(expanded_results),
                'strategy': 'expanded'
            }

    @sleep_and_retry
    @limits(calls=10, period=1)  # 10 req/sec
    def _execute_search(self, query: str) -> List[str]:
        """
        PatentField API検索実行（レート制限付き）
        """
        # API呼び出し...
        pass

    def execute_parallel_search(self, target_components: List[str]) -> Dict:
        """
        並行検索実行

        Args:
            target_components: 検索対象の構成要素番号リスト

        Returns:
            {
                'component_results': [各構成要素の結果],
                'unique_patent_ids': [重複削除後の特許ID],
                'total_hits': 総ヒット数,
                'processing_time': 処理時間
            }
        """
        start_time = time.time()
        component_results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_component = {
                executor.submit(self.search_single_component, comp_id): comp_id
                for comp_id in target_components
            }

            for future in as_completed(future_to_component):
                comp_id = future_to_component[future]
                try:
                    result = future.result()
                    component_results.append(result)
                    print(f"✓ [{comp_id}] {result['hit_count']}件ヒット ({result['strategy']})")
                except Exception as e:
                    print(f"✗ [{comp_id}] エラー: {e}")

        # 重複削除
        all_patents = set()
        for result in component_results:
            all_patents.update(result['patent_ids'])

        processing_time = time.time() - start_time

        return {
            'component_results': component_results,
            'unique_patent_ids': list(all_patents),
            'total_hits': len(all_patents),
            'processing_time': processing_time
        }
```

### クエリ構築メソッド

```python
def _build_exact_fi_query(self, component_id: str) -> str:
    """
    ドンピシャFI (OR条件)

    例: (FI:H01L27/108 OR FI:H01L29/786 OR FI:H01L21/8238)
    """
    component = self.integrated_data[component_id]
    fi_codes = component['classifications']['FI']['ドンピシャ']

    # 無効なコードを除外
    valid_codes = [
        code for code in fi_codes
        if self._is_valid_classification_code(code, 'FI')
    ]

    if not valid_codes:
        return ""

    fi_parts = [f"FI:{code}" for code in valid_codes]
    return '(' + ' OR '.join(fi_parts) + ')'

def _build_exact_keywords_query(self, component_id: str) -> str:
    """
    ドンピシャキーワード (OR条件)

    例: (論理回路 OR トランジスタ OR オフ電流)
    """
    component = self.integrated_data[component_id]
    keywords = component['keywords']['ドンピシャ']

    if not keywords:
        return ""

    return '(' + ' OR '.join(keywords[:5]) + ')'  # 上位5件

def _build_broader_fi_query(self, component_id: str) -> str:
    """
    上位概念FI (OR条件)

    例: (FI:H01L27. OR FI:H01L29.)  # ワイルドカード
    """
    component = self.integrated_data[component_id]
    broader_fi_codes = component['classifications']['FI']['上位概念']

    # 無効なコードを除外
    valid_codes = [
        code for code in broader_fi_codes
        if self._is_valid_classification_code(code, 'FI')
    ]

    if not valid_codes:
        return ""

    # ワイルドカード付きクエリ
    fi_parts = [f"FI:{code}." for code in valid_codes[:5]]
    return '(' + ' OR '.join(fi_parts) + ')'
```

---

## 5. 期待される効果

### Recall改善

| 指標 | 現在 | 提案後 | 改善 |
|------|------|--------|------|
| **Recall** | 0% | 50-70% | +50-70pt |
| **カバレッジ** | 単一検索式 | 構成要素数×検索式 | N倍 |
| **柔軟性** | 低（全体最適化の困難） | 高（要素別最適化） | ◎ |

**改善理由**:
1. **各構成要素が独立最適化**: 1つの構成要素の調整が他に影響しない
2. **段階的拡張戦略**: ドンピシャ → AND絞り込み → OR拡張
3. **カバレッジ最大化**: 各構成要素が50-300件の適切なヒット数を目指す

### 処理時間への影響

**現在の処理時間** (performance_test.log line 747):
- 総処理時間: 985.5秒/件
- PatentField検索: 約235秒 (line 744)

**提案後の処理時間** (並行処理):
```
構成要素数: 20個
各構成要素の検索時間: 10-15秒 (段階的調整含む)
逐次実行: 20 × 15秒 = 300秒
並行実行 (max_workers=5): 20 / 5 × 15秒 = 60秒

改善: 235秒 → 60秒 (-75%)
```

**APIレート制限考慮**:
- PatentField推定制限: 10 req/sec
- 最大並行数: 5 workers
- レート制限ライブラリで自動調整

### コストへの影響

**API呼び出し回数**:
- 現在: 構成要素数に関係なく固定回数
- 提案後: 構成要素数 × 平均2-3回 (段階的調整)

**例** (20構成要素の場合):
- 現在: 約10回のAPI呼び出し
- 提案後: 20 × 2.5 = 50回

**増加コスト**: PatentField APIは従量課金ではないため影響なし

---

## 6. 実装計画

### Phase 1: 新クラス実装 (2時間)

1. `ParallelComponentSearchExecutor` クラス作成
2. `search_single_component()` メソッド実装
3. クエリ構築メソッド実装
   - `_build_exact_fi_query()`
   - `_build_exact_keywords_query()`
   - `_build_broader_fi_query()`

### Phase 2: 並行処理実装 (1.5時間)

1. `concurrent.futures.ThreadPoolExecutor` 統合
2. `execute_parallel_search()` メソッド実装
3. レート制限実装 (`ratelimit` + `tenacity`)

### Phase 3: テスト実行 (2時間)

1. 単一構成要素テスト (各戦略の動作確認)
2. 並行検索テスト (5構成要素で動作確認)
3. 既存テストケース (JP2013224028A) での検証

### Phase 4: 過去実施題材での検証 (2時間)

1. tests/performance_test/test_data_3.csv の3件で検証
2. 目標特許がヒットするか確認:
   - JP2013224028A → JP2012040876A
   - JP2014007731A → JP2011171723A
   - JP2014037831A → JP2012145109A
3. Recall計算と結果レポート

**総所要時間**: 約7-8時間

---

## 7. リスク評価と対策

### リスク1: APIレート制限

**問題**: 並行検索でAPIレート制限に引っかかる可能性

**対策**:
1. `ratelimit` ライブラリで 10 req/sec に制限
2. `tenacity` でエラー時の自動リトライ (exponential backoff)
3. `max_workers=5` で並行数を制限

### リスク2: 処理時間の増加

**問題**: 検索回数増加により処理時間が伸びる可能性

**対策**:
1. 並行処理で75%削減見込み (300秒 → 60秒)
2. キャッシュ機構の導入 (同一クエリの重複実行を防止)
3. タイムアウト設定 (各検索30秒まで)

### リスク3: 検索結果の重複

**問題**: 各構成要素の検索結果に重複が多い場合、効率が悪い

**対策**:
1. Pythonの`set`で効率的に重複削除
2. 重複率をログ出力してモニタリング
3. 重複率が高い場合は検索戦略を調整

---

## 8. 承認確認事項

以下の内容で実装を進めてよろしいでしょうか？

### ✓ 確認事項

1. **アーキテクチャ変更**: 統合検索 → 構成要素別並行検索
2. **検索ロジック**:
   - ドンピシャFI (50-300件目標)
   - > 300件の場合: AND ドンピシャキーワード
   - < 50件の場合: OR (上位概念FI AND ドンピシャキーワード)
3. **並行処理**: `concurrent.futures.ThreadPoolExecutor` (max_workers=5)
4. **レート制限**: 10 req/sec (`ratelimit` + `tenacity`)
5. **期待効果**: Recall 0% → 50-70%, 処理時間 -75%
6. **検証**: 過去3件のテストケースで目標特許がヒットするか確認

### ⏭ 次のアクション

承認いただければ、直ちに以下を実行します:

1. **Phase 1**: `ParallelComponentSearchExecutor` クラス実装
2. **Phase 2**: 並行処理とレート制限の統合
3. **Phase 3**: 単一構成要素テスト実行
4. **Phase 4**: 過去題材での検証とRecall測定
5. **最終レポート**: 結果とRecall改善効果の報告

---

**提案者**: Claude Sonnet 4.5
**レビュー待ち**: ユーザー承認
**参考資料**:
- Python Concurrency Best Practices 2025
- Google Query Fan-Out Patent 2025
- Patent Retrieval Optimization Research 2025
