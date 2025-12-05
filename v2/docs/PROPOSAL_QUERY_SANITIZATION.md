# Claude生成検索式の404エラー対策 - 実装提案

## 提案日時
2025-11-30

## 問題の理解

### 現状の問題
Claude APIが生成した検索式をPatentField APIに送信すると、404エラーが発生しヒット件数が0になるケースがある。

### 根本原因の分析

#### 1. **404エラーの意味**
PatentField APIドキュメントによると、404エラーは明示的に記載されていませんが、一般的なREST API設計では：
- **404 Not Found**: リソースが存在しない、または不正なエンドポイント
- **400 Bad Request**: リクエストの構文が不正

PatentFieldの場合、検索式の構文エラーが404として返される可能性があります。

#### 2. **Claude生成クエリの問題点**

**現在の検証ロジック (`_validate_and_fix_query()`):**
```python
# 修正項目（patent_search_executor_per_component.py:942-1033）
1. AND演算子: 'AND' → '+' に変換
2. キーワードのフィールドプレフィックス除去: 'CL:keyword', 'AB:keyword' → 'keyword'
3. 不正な構文削除: '/CL', '/AB', '/TI' など
4. 括弧のバランス修正
5. 過度な空白の削除
```

**不足している検証項目:**
- ✗ PatentField固有の構文ルール検証
- ✗ フィールド指定（FI:, IPC:等）の妥当性検証
- ✗ 演算子の正しい使用方法検証
- ✗ 特殊文字のエスケープ
- ✗ 404エラー発生時の再整形ロジック
- ✗ Claude APIを使った構文修正

#### 3. **PatentField API仕様**

**search_type: expert の要件:**
- "コマンド形式である必要がある"
- EPODOC形式の番号フォーマット
- フィールド指定: FI:, IPC:, CPC:, Fterm: など
- 演算子: AND(`+`), OR, NOT(`-`), NEAR(`*N`)
- 括弧によるグルーピング

**制約:**
- limit: 最大1000件
- query長: 実質的な上限あり（10000文字推奨）
- レート制限: 分/時/日/月単位

## 最新ベストプラクティスの確認

### 1. Claude AI 2025ベストプラクティス

**出典:**
- [Claude AI Development: Best Practices for 2025](https://collabnix.com/claude-code-best-practices-advanced-command-line-ai-development-in-2025/)
- [Prompt engineering best practices | Claude](https://www.claude.com/blog/best-practices-for-prompt-engineering)
- [My 7 essential Claude Code best practices for production-ready AI](https://www.eesel.ai/blog/claude-code-best-practices)

**適用すべき実践:**

#### 入力検証とサニタイゼーション
- 期待されるパターンに対してすべての入力を検証
- 処理または公開前にコンテンツをサニタイズ
- コンテンツモデレーションチェックの実装

#### 構造化出力の要求
```
"Output only valid JSON with no preamble. Begin your response with an opening brace"
```

#### 明示的なコンテキストと制約
- 検索式の構文ルールを明示的に提示
- 使用可能なフィールドと演算子のリストを提供
- 成功例と失敗例を示す

### 2. API エラーハンドリング 2025ベストプラクティス

**出典:**
- [Best Practice: Implementing Retry Logic in HTTP API Clients](https://api4.ai/blog/best-practice-implementing-retry-logic-in-http-api-clients)
- [Best Practices for API Error Handling | Postman Blog](https://blog.postman.com/best-practices-for-api-error-handling/)
- [API Error Handling That Won't Make Users Rage-Quit](https://zuplo.com/blog/2025/04/30/optimizing-api-error-handling-response-codes)

**重要な知見:**

#### 404エラーはリトライすべきでない
> **No, 404 errors should generally NOT be retried.** Client-side errors like 404 (Not Found) or 400 (Bad Request) usually signify issues that retries won't resolve.

#### リトライすべきエラー
- 500 Internal Server Error
- 502 Bad Gateway
- 503 Service Unavailable
- 504 Gateway Timeout
- 429 Too Many Requests (指数バックオフ)

#### リトライすべきでないエラー
- 400 Bad Request
- 401 Unauthorized
- 403 Forbidden
- **404 Not Found** ← 今回の問題
- 405 Method Not Allowed

#### 404エラーの適切な処理
1. **自動リトライしない** - リソースが存在しないかURLが不正
2. エラーをログに記録してデバッグ
3. ユーザーに明確で実行可能なエラーメッセージを返す
4. **代替アプローチ: クエリの再生成・修正**

## 提案する解決策

### アプローチ: Claude APIによる検索式の再整形

404エラーが発生した場合、**リトライではなく、Claude APIを使って検索式を修正**します。

### 実装方針

#### 1. **404エラー検出と分類**

```python
def _execute_patentfield_search(self, query: str) -> Tuple[int, List[str]]:
    try:
        response = requests.post(...)
        response.raise_for_status()
        # 成功
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            # 404エラー: 検索式の構文エラーの可能性
            return self._handle_query_syntax_error(query, e)
        elif e.response.status_code == 400:
            # 400エラー: リクエストパラメータエラー
            return self._handle_bad_request_error(query, e)
        else:
            # その他のHTTPエラー
            return 0, []
```

#### 2. **Claude APIによる検索式修正**

新しいメソッド `_sanitize_query_with_claude()` を実装：

```python
def _sanitize_query_with_claude(
    self,
    original_query: str,
    error_message: str,
    attempt: int = 1
) -> Optional[str]:
    """
    Claude APIを使用して検索式を修正

    Args:
        original_query: 元の検索式
        error_message: エラーメッセージ
        attempt: 試行回数

    Returns:
        修正された検索式（または None）
    """
```

**Claudeプロンプト設計:**
```
あなたはPatentField API検索式の専門家です。
以下の検索式でエラーが発生しました。

元の検索式:
{original_query}

エラー情報:
{error_message}

PatentField APIの構文ルール:
1. フィールド指定: FI:, IPC:, CPC:, Fterm:のみ有効
2. キーワード検索: CL:, AB:, TI:, DE:は使用不可（全文検索）
3. 演算子: AND(+), OR, NOT(-), NEAR(*N)
4. 括弧のバランス: 必須
5. 特殊文字: 適切にエスケープ
6. EPODOC形式: 文献番号フォーマット

タスク:
上記のルールに従って、検索式を修正してください。
修正理由も簡潔に説明してください。

出力形式（JSONのみ、説明不要）:
{
  "corrected_query": "修正された検索式",
  "reason": "修正理由"
}
```

#### 3. **段階的フォールバック戦略**

```
Step 1: 現在の検証ロジック (_validate_and_fix_query)
  ↓ 404エラー
Step 2: Claude APIで検索式を修正 (_sanitize_query_with_claude)
  ↓ 404エラー
Step 3: 簡略化戦略（AND条件を削除、OR条件のみ）
  ↓ 404エラー
Step 4: 最小限の検索式（FI:コードのみ）
  ↓ それでも失敗
Step 5: エラーとして記録、スキップ
```

#### 4. **エラーログと統計収集**

```python
# エラー統計
self.query_error_stats = {
    '404_errors': 0,
    '404_claude_fixed': 0,
    '404_fallback_success': 0,
    '404_final_failure': 0
}
```

### 実装の詳細設計

#### A. 新しいメソッドの追加

1. **`_handle_query_syntax_error(query, error)`**
   - 404エラー専用ハンドラー
   - Claude修正を試行
   - フォールバック戦略を実行

2. **`_sanitize_query_with_claude(query, error, attempt)`**
   - Claude APIで検索式を修正
   - 構文ルールを明示的に伝える
   - JSON形式で修正結果を取得

3. **`_generate_sanitization_prompt(query, error, syntax_rules)`**
   - Claude用のプロンプトを生成
   - PatentField構文ルールを含む
   - 成功例・失敗例を提示

4. **`_simplify_query_fallback(query)`**
   - 簡略化戦略
   - AND条件を削除してOR条件のみに
   - FI:コードのみの最小限検索

#### B. 既存メソッドの拡張

1. **`_execute_patentfield_search()`**
   - 404エラーハンドリングを追加
   - エラー統計を収集

2. **`_validate_and_fix_query()`**
   - PatentField固有ルールを追加
   - フィールド指定の検証強化

#### C. 設定パラメータ

```python
class PerComponentSearchExecutor:
    def __init__(self, ...):
        # 404エラーハンドリング設定
        self.enable_claude_sanitization = True  # Claude修正を有効化
        self.max_sanitization_attempts = 2      # 最大修正試行回数
        self.enable_fallback_strategy = True    # フォールバック有効化
```

### 期待される効果

1. **404エラー削減**: 推定70-90%のエラーを解消
2. **検索成功率向上**: より多くの構成要素で有効な検索を実行
3. **ログの改善**: エラー原因と修正履歴の追跡
4. **デバッグ容易性**: Claude修正理由の記録

### リスクと対策

#### リスク1: Claude API呼び出し増加
**対策:**
- 修正試行回数を制限（最大2回）
- キャッシュ機能（同じエラーパターンの修正を再利用）

#### リスク2: 過度な簡略化
**対策:**
- 段階的フォールバック（急激な簡略化を避ける）
- 修正前後の検索式を記録

#### リスク3: 無限ループ
**対策:**
- 最大試行回数を厳格に制限
- 同じクエリの繰り返し検出

## 実装計画

### Phase 1: エラー検出とログ強化（1-2時間）
1. 404エラーの専用ハンドリング追加
2. エラー統計の収集
3. 詳細ログの記録

### Phase 2: Claude修正ロジック実装（2-3時間）
1. `_sanitize_query_with_claude()` 実装
2. プロンプト設計と最適化
3. JSON応答のパース

### Phase 3: フォールバック戦略（1-2時間）
1. `_simplify_query_fallback()` 実装
2. 段階的簡略化ロジック
3. 最小限検索式の生成

### Phase 4: テストと検証（2-3時間）
1. 単体テスト作成
2. 既存テストデータでの検証
3. エッジケースのテスト

**合計推定時間: 6-10時間**

## 承認ポイント

このアプローチについて、以下の点をご確認ください：

### ✅ 確認事項

1. **404エラーの扱い**
   - リトライではなく、Claude修正で対応する方針でよろしいですか？

2. **Claude API使用量**
   - 404エラー時に追加でClaude APIを呼び出すことを許容できますか？
   - 推定: 全検索の5-10%で発生と仮定

3. **フォールバック戦略**
   - 段階的簡略化（AND削除→OR のみ→FI:のみ）でよろしいですか？

4. **実装優先度**
   - すぐに実装を開始してよろしいですか？
   - または他の優先タスクがありますか？

### 🤔 質問事項

1. 現在の404エラー発生頻度はどの程度ですか？
2. 特定のパターン（特定の構成要素など）で多発していますか？
3. エラーログやサンプルクエリを確認できますか？

## 参考資料

### PatentField API
- [API操作ドキュメント](https://api.patentfield.com/api_docs/v1/patents/search)
- [検索式構文](https://support.patentfield.com/portal/ja/kb/articles/%E3%82%B3%E3%83%9E%E3%83%B3%E3%83%89%E6%A4%9C%E7%B4%A2#_1)

### ベストプラクティス (2025)
- [Claude AI Development: Best Practices for 2025](https://collabnix.com/claude-code-best-practices-advanced-command-line-ai-development-in-2025/)
- [Prompt engineering best practices | Claude](https://www.claude.com/blog/best-practices-for-prompt-engineering)
- [Best Practice: Implementing Retry Logic in HTTP API Clients](https://api4.ai/blog/best-practice-implementing-retry-logic-in-http-api-clients)
- [Best Practices for API Error Handling | Postman Blog](https://blog.postman.com/best-practices-for-api-error-handling/)
- [API Error Handling That Won't Make Users Rage-Quit](https://zuplo.com/blog/2025/04/30/optimizing-api-error-handling-response-codes)

---

**次のステップ:**
承認いただければ、Phase 1から実装を開始します。
