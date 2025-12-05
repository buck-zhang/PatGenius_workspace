# Component 1c Broken Pipe エラー修正実装

## 実装日
2025年11月29日

## 問題の概要

### 発生したエラー
```
Component 1c: [Errno 32] Broken pipe
試行回数: 0
ステータス: error
```

### エラーの特徴
- 並列処理（ThreadPoolExecutor）での実行時にのみ発生
- 試行回数が0（クエリバリデーションが実行される前にクラッシュ）
- 修正前のテストでは150件の結果を正常に取得していた
- コード変更とは直接関係ない並列処理の問題

### 根本原因の仮説
1. **ThreadPoolExecutorのリソース競合**
   - 4コンポーネント同時実行時の過負荷
   - Claude API呼び出しの同時実行制限に抵触

2. **Claude API接続の問題**
   - Component 1cの実行タイミングでAPI接続が切断
   - パイプ破損エラー（Broken Pipe）が発生

3. **例外処理の不足**
   - 並列処理での一時的エラーに対するリトライがない
   - 詳細なエラーログが不足

---

## 実装した修正

### 1. `_execute_with_retry()` メソッドの追加 ✅

**場所**: `patent_search_executor_per_component.py` lines 1033-1088

**機能**:
- Broken Pipe、OSError、ConnectionErrorの自動リトライ
- 最大3回まで再試行（2秒間隔）
- 詳細なエラーロギング（スタックトレース付き）

**実装**:
```python
def _execute_with_retry(
    self,
    func: callable,
    max_retries: int = 3,
    delay: float = 2.0,
    context: str = ""
):
    """
    Broken pipeエラー時の自動リトライ

    Args:
        func: 実行する関数
        max_retries: 最大リトライ回数
        delay: リトライ間隔（秒）
        context: エラーログ用のコンテキスト情報

    Returns:
        func()の戻り値

    Raises:
        最終的に失敗した場合の例外
    """
    import time
    import traceback

    for attempt in range(max_retries):
        try:
            return func()
        except (BrokenPipeError, OSError, ConnectionError) as e:
            error_type = type(e).__name__
            error_msg = str(e)

            if attempt < max_retries - 1:
                print(f"    ⚠️ {error_type}エラー発生: {error_msg}")
                if context:
                    print(f"       コンテキスト: {context}")
                print(f"       {delay}秒後に再試行します ({attempt+1}/{max_retries})...")
                time.sleep(delay)
            else:
                print(f"    ❌ {error_type}エラー: 最大リトライ回数({max_retries})に達しました")
                print(f"       エラー詳細: {error_msg}")
                if context:
                    print(f"       コンテキスト: {context}")
                print("       スタックトレース:")
                traceback.print_exc()
                raise
        except Exception as e:
            # その他の予期しない例外
            error_type = type(e).__name__
            error_msg = str(e)
            print(f"    ❌ 予期しないエラー ({error_type}): {error_msg}")
            if context:
                print(f"       コンテキスト: {context}")
            print("       スタックトレース:")
            traceback.print_exc()
            raise
```

**リトライ対象のエラー**:
- `BrokenPipeError`: パイプ破損
- `OSError`: OS関連エラー（ファイルディスクリプタ枯渇など）
- `ConnectionError`: 接続エラー

---

### 2. `search_all_components_parallel()` の改善 ✅

**場所**: `patent_search_executor_per_component.py` lines 1652-1716

#### 変更1: リトライロジックの統合

**修正前**:
```python
future_to_component = {
    executor.submit(self.search_single_component_adaptive, comp_id): comp_id
    for comp_id in component_ids
}
```

**修正後**:
```python
future_to_component = {}
for comp_id in component_ids:
    # リトライロジックを組み込んだラムダ関数
    retry_func = lambda cid=comp_id: self._execute_with_retry(
        lambda: self.search_single_component_adaptive(cid),
        max_retries=3,
        delay=2.0,
        context=f"Component {cid}"
    )
    future = executor.submit(retry_func)
    future_to_component[future] = comp_id
```

#### 変更2: 詳細なエラーロギング

**修正前**:
```python
except Exception as e:
    print(f"\n✗ 構成要素 {comp_id} の検索でエラー: {e}")
```

**修正後**:
```python
except Exception as e:
    import traceback
    error_type = type(e).__name__
    error_msg = str(e)

    print(f"\n✗ 構成要素 {comp_id} の検索でエラー ({error_type}): {error_msg}")
    print(f"   詳細なスタックトレース:")
    traceback.print_exc()

    results.append({
        'element_id': comp_id,
        'element_text': '',
        'final_query': '',
        'final_hits': 0,
        'patent_ids': [],
        'attempts': [],
        'status': 'error',
        'error': f"{error_type}: {error_msg}"
    })
```

#### 変更3: Worker数の削減

**修正前**:
```python
def search_all_components_parallel(
    self,
    component_ids: Optional[List[str]] = None,
    max_workers: int = 5
) -> List[Dict]:
```

**修正後**:
```python
def search_all_components_parallel(
    self,
    component_ids: Optional[List[str]] = None,
    max_workers: int = 2  # 修正: 5 → 2 (Claude API負荷軽減)
) -> List[Dict]:
```

**理由**:
- Claude API の同時実行制限を考慮
- 並列処理によるリソース競合を軽減
- 処理時間は増加するが、安定性を優先

---

## 期待される効果

### 1. Broken Pipe エラーの自動回復
- 一時的なAPI接続エラーでも最大3回まで自動リトライ
- Component 1c が成功する可能性が大幅に向上

### 2. リソース競合の軽減
- Worker数を5 → 2に削減
- Claude API への同時リクエストを制限
- より安定した並列処理

### 3. デバッグ性の向上
- エラータイプの明示（`BrokenPipeError` vs `OSError` など）
- 完全なスタックトレースの出力
- コンテキスト情報（Component ID）の記録

### 4. 処理時間への影響
- **並列処理の遅延**: Worker数削減により処理時間が増加する可能性
- **リトライによる遅延**: エラー発生時に2秒×最大3回のリトライ
- **トレードオフ**: 安定性を優先し、処理時間の増加を許容

---

## テストケース（Row #2の改善予測）

### 修正前の問題
- Component 1a: 14件（成功）
- Component 1b: 39件（成功）
- Component 1c: 0件（Broken Pipe エラー）← **修正対象**
- Component 1d: 1,573件（成功）

### 修正後の期待結果
- Component 1a: 14件（継続して成功）
- Component 1b: 39件（継続して成功）
- Component 1c: **150件前後**（リトライで成功の可能性）← **改善期待**
- Component 1d: 1,573件（継続して成功）

---

## 次のステップ

### 1. 検証テスト実行 ✅ 次のタスク
```bash
python3 performance_test_system.py \
  --csv tests/performance_test/combined_data_top10.csv \
  --row 2 \
  --credentials ../ttdc-in-house-dev-3e07247326cb.json \
  --pf-key ../patentfield_key.json
```

### 2. 結果の比較分析
- Component 1c が成功したか確認
- リトライログの出力を確認
- 処理時間への影響を測定

### 3. 全体影響の検証
- Row #1-10の全件再テスト
- Broken Pipe エラーの発生率確認
- 並列処理の安定性確認

---

## 実装の品質保証

### チェックリスト
- ✅ `_execute_with_retry()` メソッドが正しく実装されている
- ✅ リトライロジックが並列処理に統合されている
- ✅ エラータイプごとに適切なハンドリングが実装されている
- ✅ スタックトレースが完全に出力される
- ✅ Worker数が2に削減されている

### 既知の制限事項
- **処理時間の増加**: Worker数削減により全体処理時間が増加する可能性
- **リトライ回数の固定**: 最大3回のリトライは固定値（将来的にパラメータ化可能）
- **リトライ間隔の固定**: 2秒間隔は固定値（将来的に指数バックオフ実装可能）

---

## まとめ

3つの主要な改善を実装：

1. **自動リトライ機構**: Broken Pipe エラーを最大3回まで自動リトライ
2. **並列処理の最適化**: Worker数を5 → 2に削減してAPI負荷を軽減
3. **エラーロギングの強化**: 詳細なスタックトレースとコンテキスト情報を記録

これにより、Component 1c の Broken Pipe エラーが解消され、並列処理の安定性が向上することが期待されます。

**実装完了日**: 2025年11月29日
**実装者**: Claude Code Assistant
**次のアクション**: 検証テスト実行（Row #2）
