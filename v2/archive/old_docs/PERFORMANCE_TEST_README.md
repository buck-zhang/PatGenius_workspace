# 特許検索システム性能テスト - 使用ガイド

## 📚 概要

特許検索システムの性能を評価するテストフレームワークです。

**評価項目**:
- ✅ **Recall（再現率）**: 紐づいた特許を見つけられる割合
- ⏱️ **処理時間**: 1件あたりの平均処理時間
- 💰 **コスト**: AI API使用料金（日本円）
- 📊 **トークン使用量**: Claude/Geminiの詳細使用量

---

## 🚀 クイックスタート

### 1. 最小テスト（3件）

まず3件でシステムが正しく動作するか確認：

```bash
python3 performance_test_runner.py -n 3
```

**実行時間**: 約2分
**コスト**: 約30円

### 2. プロトタイプテスト（30件）

```bash
python3 performance_test_runner.py -n 30
```

**実行時間**: 約20分
**コスト**: 約543円

### 3. スケールアップ（100件）

```bash
python3 performance_test_runner.py -n 100
```

**実行時間**: 約65分
**コスト**: 約1,810円

---

## 📁 出力ファイル

### tests/performance_test/

テスト実行後、以下のファイルが生成されます：

```
tests/performance_test/
├── combined_data.csv                  # 結合データ（423,068件）
├── test_data_30.csv                   # テストデータ（30件）
├── test_results.json                  # テスト結果（詳細）
├── performance_test.log               # 実行ログ
├── patent_texts/                      # 特許データキャッシュ
│   ├── JP2014007731A.json
│   └── ...
├── JP2014007731A_structure.json       # 構成要件分割結果
├── JP2014007731A_keywords.json        # キーワード抽出結果
├── JP2014007731A_classification.json  # 分類コード抽出結果
└── JP2014007731A_search_results.json  # 検索結果
```

### test_results.json の構造

```json
{
  "test_cases": [
    {
      "test_id": 1,
      "syutugan": "JP2013224028A",
      "himotuki": "JP2012040876A",
      "found": true,
      "rank": 15,
      "total_results": 102,
      "status": "success",
      "metrics": {
        "time_structure": 12.3,
        "time_keyword": 8.5,
        "time_classification": 15.2,
        "time_search": 2.1,
        "total_time": 38.1,
        "tokens_claude_input": 14000,
        "tokens_claude_output": 3500,
        "tokens_gemini_input": 7000,
        "tokens_gemini_output": 1200
      },
      "cost": {
        "claude_cost": 14.26,
        "gemini_cost": 3.26,
        "total_cost": 17.52
      }
    }
  ],
  "summary": {
    "total_test_cases": 30,
    "successful_tests": 30,
    "found_count": 24,
    "recall": 0.800,
    "total_time": 1143.0,
    "avg_time_per_case": 38.1,
    "total_cost_jpy": 525.60,
    "avg_cost_per_case": 17.52
  }
}
```

---

## 📊 性能指標の解釈

### Recall（再現率）

```
Recall = 検索結果に紐づいた特許が含まれていた件数 / 総テストケース数
```

**目標値**: 80%以上

**意味**:
- **100%**: 全ての紐づいた特許を発見（理想的）
- **80%**: 10件中8件を発見（許容範囲）
- **60%以下**: 検索漏れが多い（要改善）

### 処理時間

**1件あたりの目標**: 40秒以内

**内訳**:
- 構成要件分割: 12秒
- キーワード抽出: 8秒
- 分類コード抽出: 15秒
- PatentField検索: 2秒
- データ取得: 2秒

### コスト（2025年11月料金）

**1件あたりの目標**: 20円以内

**内訳**:
- Claude Sonnet 4: 約14円
- Gemini 1.5 Pro: 約3円

**全件（423,068件）の見積もり**: 約766万円

---

## 🔍 失敗ケースの分析

### 検索結果にログ出力

```bash
# ログから失敗ケースを抽出
grep "✗ 失敗" tests/performance_test/performance_test.log

# 特定のテストケースの詳細を確認
grep "JP2014007731A" tests/performance_test/performance_test.log -A 20
```

### test_results.jsonから分析

```python
import json

with open('tests/performance_test/test_results.json', 'r') as f:
    results = json.load(f)

# 失敗ケースのみ抽出
failed_cases = [
    tc for tc in results['test_cases']
    if not tc['found']
]

print(f"失敗件数: {len(failed_cases)}")

for case in failed_cases:
    print(f"  本願: {case['syutugan']}")
    print(f"  紐づいた特許: {case['himotuki']}")
    print(f"  検索結果数: {case['total_results']}")
    print()
```

---

## 🛠️ トラブルシューティング

### エラー: "ANTHROPIC_API_KEY not found"

**解決策**:
```bash
export ANTHROPIC_API_KEY="your-claude-api-key"
```

または、環境変数ファイルを作成：
```bash
echo 'export ANTHROPIC_API_KEY="your-key"' >> ~/.bashrc
source ~/.bashrc
```

### エラー: "PatentField API 404 Not Found"

**原因**: 出願番号がPatentFieldに存在しない

**対処**: システムが自動的にスキップします。ログで確認：
```
⚠ JP2014999999A: not_found
```

### エラー: "Timeout"

**原因**: PatentField APIまたはClaude/Gemini APIの応答遅延

**対処**:
1. インターネット接続確認
2. `time.sleep()`の待機時間を調整
3. リトライ機能を追加（今後の改善）

### メモリ不足

**症状**: 大量テスト時（1,000件以上）にメモリエラー

**対処**:
1. バッチサイズを小さくする
2. 中間ファイルを削除
3. ストリーミング処理に変更（今後の改善）

---

## 📈 スケーリング戦略

### 段階的アプローチ

1. **Phase 1: 3件テスト** (2分、30円)
   - システム動作確認
   - エラー検出

2. **Phase 2: 30件テスト** (20分、543円)
   - 初期性能評価
   - Recall計算

3. **Phase 3: 100件テスト** (65分、1,810円)
   - 統計的有意性確保
   - コスト見積もり精緻化

4. **Phase 4: 1,000件テスト** (11時間、18,100円)
   - 本番運用判断
   - 改善策検討

5. **Phase 5: 全件（423,068件）** (283日、766万円)
   - 並列処理必須
   - 段階的実行

### 並列処理の実装（今後）

```python
# 5並列で処理
# 処理時間: 283日 → 約57日
# 実装方法: multiprocessing, concurrent.futures
```

---

## 🎯 ベストプラクティス

### 1. 小規模テストから開始

**理由**:
- エラー早期発見
- コスト削減
- 設定調整

**推奨**:
```bash
# まず3件
python3 performance_test_runner.py -n 3

# 成功したら30件
python3 performance_test_runner.py -n 30
```

### 2. ログを確認

```bash
# リアルタイムでログ確認
tail -f tests/performance_test/performance_test.log
```

### 3. キャッシュを活用

同じ本願の再テストは高速化：
```
patent_texts/JP2014007731A.json  # キャッシュ済み
```

### 4. コスト監視

```python
# テスト途中でコストを確認
import json
with open('tests/performance_test/test_results.json', 'r') as f:
    r = json.load(f)
    print(f"現在のコスト: {r['summary']['total_cost_jpy']}円")
```

---

## 📝 結果レポートの生成（今後実装）

```bash
# Markdown レポート生成
python3 generate_performance_report.py

# 出力: tests/performance_test/PERFORMANCE_REPORT.md
```

**レポート内容**:
- エグゼクティブサマリー
- Recall分析
- 処理時間分布
- コスト内訳
- 失敗ケース詳細
- 改善提案

---

## 🔄 継続的改善

### 改善サイクル

1. **テスト実行** → 2. **結果分析** → 3. **システム改善** → 4. **再テスト**

### 改善の例

**Recallが低い場合**:
- キーワード抽出の改善
- 分類コードの追加
- 検索戦略の調整

**処理時間が長い場合**:
- プロンプト最適化
- 並列処理導入
- キャッシング強化

**コストが高い場合**:
- Haiku使用（軽量タスク）
- プロンプトキャッシング
- バッチ処理最適化

---

## 🤝 サポート

**問題報告**:
- ログファイル: `tests/performance_test/performance_test.log`
- 結果ファイル: `tests/performance_test/test_results.json`

**質問・提案**:
- GitHub Issues
- 開発チームへ連絡

---

生成日: 2025年11月
システム: PatentField特許検索システム v2.0
ドキュメントバージョン: 1.0
