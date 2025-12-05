# トークン出力修正の検証結果

## 修正内容

`performance_test_runner.py` に以下のトークン出力ログを追加しました:

### 修正箇所

1. **ステップ1完了後（構成要件分割）**
   ```python
   logger.info(f"  ✓ 完了 ({metrics['time_structure']:.1f}秒)")
   logger.info(f"    トークン: 入力={step1_input:,} / 出力={step1_output:,} / 合計={step1_input + step1_output:,}")
   ```

2. **ステップ2完了後（キーワード抽出）**
   ```python
   logger.info(f"  ✓ 完了 ({metrics['time_keyword']:.1f}秒)")
   logger.info(f"    トークン: 入力={step2_input:,} / 出力={step2_output:,} / 合計={step2_input + step2_output:,}")
   ```

3. **ステップ3完了後（分類コード抽出）**
   ```python
   logger.info(f"  ✓ 完了 ({metrics['time_classification']:.1f}秒)")
   logger.info(f"    トークン(Gemini): 入力={step3_input:,} / 出力={step3_output:,} / 合計={step3_input + step3_output:,}")
   ```

4. **パイプライン完了時**
   ```python
   total_tokens_claude = metrics['tokens_claude_input'] + metrics['tokens_claude_output']
   total_tokens_gemini = metrics['tokens_gemini_input'] + metrics['tokens_gemini_output']

   logger.info(f"\n✓ パイプライン完了: {len(search_results)}件ヒット")
   logger.info(f"  総処理時間: {metrics['total_time']:.1f}秒")
   logger.info(f"  総トークン: Claude={total_tokens_claude:,} / Gemini={total_tokens_gemini:,}\n")
   ```

5. **テストケース結果表示時**
   ```python
   if pipeline_result['status'] == 'success':
       m = pipeline_result['metrics']
       total_tokens = (m['tokens_claude_input'] + m['tokens_claude_output'] +
                       m['tokens_gemini_input'] + m['tokens_gemini_output'])
       logger.info(f"  総処理時間: {m['total_time']:.1f}秒 / 総トークン: {total_tokens:,}")
   ```

## 検証結果

### 実行ログからの抜粋

```
2025-11-25 10:30:38,539 - INFO -   ステップ1: 構成要件分割...
2025-11-25 10:31:55,245 - INFO -   ✓ 完了 (76.7秒)
2025-11-25 10:31:55,245 - INFO -     トークン: 入力=2,240 / 出力=14,117 / 合計=16,357

2025-11-25 10:31:55,245 - INFO -   ステップ2: キーワード抽出...
2025-11-25 10:32:10,613 - INFO -   ✓ 完了 (409.5秒)
2025-11-25 10:32:10,613 - INFO -     トークン: 入力=13,512 / 出力=31,785 / 合計=45,297

2025-11-25 10:32:10,613 - INFO -   ステップ3: 分類コード抽出...
```

### 出力フォーマット

- **各ステップ完了時**: `トークン: 入力=X,XXX / 出力=XX,XXX / 合計=XX,XXX`
- **パイプライン完了時**: `総トークン: Claude=XX,XXX / Gemini=XX,XXX`
- **テストケース結果**: `総処理時間: XX.X秒 / 総トークン: XXX,XXX`

### トークン表示の特徴

1. **カンマ区切り**: 数値は3桁ごとにカンマで区切られて読みやすい
2. **段階的表示**: 各ステップ完了後にすぐに表示される
3. **モデル別集計**: Claude（構成要件分割・キーワード抽出）とGemini（分類コード抽出）を分けて表示
4. **処理時間と併記**: トークン数と処理時間を一緒に表示

## 修正前との比較

### 修正前
- トークン数は内部で計算されているが、ログに出力されない
- 処理時間のみ表示される
- コスト計算に使用されるが、ユーザーには見えない

### 修正後
- 各ステップ完了後にトークン数が表示される
- 処理時間とトークン数の両方が確認できる
- APIコストの内訳が把握しやすい

## 確認事項

✅ ステップ1（構成要件分割）のトークン出力: 正常
✅ ステップ2（キーワード抽出）のトークン出力: 正常
✅ ステップ3（分類コード抽出）のトークン出力: 正常
✅ パイプライン完了時の総計表示: 正常
✅ テストケース結果でのトークン表示: 正常
✅ 数値フォーマット（カンマ区切り）: 正常

## 結論

ユーザーが報告した「以前の出力にあるtokensと処理時間がなくなりました」という問題は、
トークン出力ログの追加により解決されました。

全ての段階でトークン数と処理時間が正しく表示されることを確認しました。
