# 特許検索システム性能テスト - エグゼクティブサマリー

## 🎯 プロジェクト概要

**目的**: PatentField特許検索システムv2.0の性能を定量的に評価

**評価データ**: 423,068件の特許ペア（本願 ⇔ 紐づいた特許）

**評価指標**:
1. **Recall（再現率）**: 検索漏れ率
2. **処理時間**: スケーラビリティ
3. **コスト**: 実用性の判断

---

## 📊 テストデータ

| 項目 | 詳細 |
|------|------|
| **データソース** | xy_data1.csv (62,601件) + xy_data2.csv (360,467件) |
| **合計** | 423,068ペア |
| **データ構造** | syutugan (本願), himotuki (紐づいた特許), category, koukaibi |
| **初期テスト** | 30件（プロトタイプ）|

**データ例**:
```csv
syutugan,himotuki,category,koukaibi
JP2013224028A,JP2012040876A,Ax,20120301
JP2014007731A,JP2011171723A,Ax,20110901  ← 前回のエンドツーエンドテストと同じ！
```

---

## 🏗️ システムアーキテクチャ

### フルパイプライン

```
[本願特許] → PatentField API → [請求の範囲 + 詳細な説明]
    ↓
構成要件分割 (Claude Sonnet 4) → 構成要件JSON
    ↓
キーワード抽出 (Claude Sonnet 4) → キーワードJSON
    ↓
分類コード抽出 (Gemini 1.5 Pro) → 分類コードJSON
    ↓
PatentField検索実行 → [検索結果リスト]
    ↓
検証: 紐づいた特許が含まれているか? → Recall計算
```

### 実装ファイル

```
v2/
├── performance_test_runner.py         # メイン実行システム
├── PERFORMANCE_TEST_STRATEGY.md       # 包括的戦略ドキュメント
├── PERFORMANCE_TEST_README.md         # 使用ガイド
└── tests/
    ├── xy_data1.csv                   # テストデータ1
    ├── xy_data2.csv                   # テストデータ2
    └── performance_test/              # 出力ディレクトリ
        ├── test_results.json          # テスト結果
        ├── performance_test.log       # 実行ログ
        └── patent_texts/              # 特許データキャッシュ
```

---

## ⚡ クイックスタート

### 最小テスト（3件、2分、30円）

```bash
python3 performance_test_runner.py -n 3
```

### プロトタイプテスト（30件、20分、543円）

```bash
python3 performance_test_runner.py -n 30
```

### 結果確認

```bash
cat tests/performance_test/test_results.json | jq '.summary'
```

**出力例**:
```json
{
  "total_test_cases": 30,
  "successful_tests": 30,
  "found_count": 24,
  "recall": 0.800,
  "total_time": 1143.0,
  "avg_time_per_case": 38.1,
  "total_cost_jpy": 525.60,
  "avg_cost_per_case": 17.52
}
```

---

## 💰 コスト見積もり（2025年11月料金）

### AI API料金（USD → JPY: 157円/USD）

| モデル | Input | Output |
|--------|-------|--------|
| **Claude Sonnet 4** | 471円/1M tokens | 2,355円/1M tokens |
| **Gemini 1.5 Pro** | 196円/1M tokens | 1,570円/1M tokens |

### 1件あたりのコスト

| ステップ | モデル | Input | Output | コスト |
|---------|--------|-------|--------|--------|
| 構成要件分割 | Claude | 8,000 | 2,000 | 8.48円 |
| キーワード抽出 | Claude | 6,000 | 1,500 | 6.36円 |
| 分類コード抽出 | Gemini | 7,000 | 1,200 | 3.26円 |
| **合計** | - | **21,000** | **4,700** | **18.10円** |

### スケール見積もり

| テスト規模 | 処理時間 | コスト（円） |
|-----------|----------|-------------|
| 3件（最小） | 2分 | 54円 |
| 30件（プロトタイプ） | 20分 | 543円 |
| 100件 | 65分 | 1,810円 |
| 1,000件 | 11時間 | 18,100円 |
| **全件（423,068件）** | **283日** | **766万円** |

**最適化後（5並列）**:
- 処理時間: 283日 → **57日**
- コスト: 変わらず（766万円）

---

## 📈 期待される成果

### 定量的目標

| 指標 | 目標値 | 評価基準 |
|------|--------|----------|
| **Recall** | 80%以上 | 検索漏れ20%以下 |
| **処理時間** | 40秒/件 | スケーラビリティ確保 |
| **コスト** | 20円/件 | 実用性の確保 |

### 定性的成果

1. **システムの信頼性検証**
   - エラー率の測定
   - 安定性の確認

2. **検索漏れパターンの分析**
   - どのような特許で検索漏れが発生するか
   - 改善点の特定

3. **スケーラビリティの実証**
   - 大規模データでの動作確認
   - 並列処理の必要性評価

4. **コスト最適化の方向性**
   - プロンプトキャッシングの効果測定
   - モデル選択の最適化

---

## 🎓 2025年ベストプラクティス適用

### 1. 評価指標の選択

**Recallを最優先**:
- 特許検索では「検索漏れ（False Negative）」が最も危険
- 訴訟リスク、ライセンス機会損失につながる
- 2025年のベストプラクティスでは、検索漏れゼロを目指す

**複数指標の併用**:
- Recall: 主要指標
- Precision: 実用性評価
- F1-Score: バランス評価
- 処理時間: スケーラビリティ

**継続的モニタリング**:
- モデルドリフト検出
- 性能劣化の早期発見
- 定期的な再評価

### 2. コスト最適化戦略

**プロンプトキャッシング（Claude独自機能）**:
- 繰り返しクエリで最大90%削減
- 実装: `anthropic.Anthropic(default_headers={"anthropic-beta": "prompt-caching-2024-07-31"})`

**バッチ処理**:
- API呼び出しの効率化
- レート制限内での最大スループット

**段階的スケールアップ**:
- 3件 → 30件 → 100件 → 1,000件
- 各段階で評価・改善

### 3. 品質保証

**エラーハンドリング**:
- PatentField API失敗（404, timeout）
- Claude/Gemini API制限
- ネットワークエラー

**ロギング**:
- 詳細な実行ログ
- デバッグ情報
- 性能メトリクス

**再現性**:
- 全テスト結果の保存
- 再実行可能性
- バージョン管理

---

## 🔄 実装フェーズ

### Phase 1: プロトタイプ（完了）✅

**成果物**:
- ✅ `performance_test_runner.py`: メイン実行システム
- ✅ `PERFORMANCE_TEST_STRATEGY.md`: 包括的戦略
- ✅ `PERFORMANCE_TEST_README.md`: 使用ガイド
- ✅ `PERFORMANCE_TEST_SUMMARY.md`: エグゼクティブサマリー

**次のステップ**:
1. 3件テスト実行（動作確認）
2. 30件テスト実行（初期性能評価）
3. 結果分析と改善提案

### Phase 2: スケールアップ（次回）

**内容**:
- エラーハンドリング強化
- 並列処理実装
- コスト追跡機能
- 詳細レポート生成

### Phase 3: 本番運用（今後）

**内容**:
- バッチ処理最適化
- キャッシング実装
- ダッシュボード構築
- 継続的モニタリング

---

## 📋 実行手順（推奨）

### ステップ1: 最小テスト（3件）

```bash
# 動作確認
python3 performance_test_runner.py -n 3

# 結果確認
cat tests/performance_test/test_results.json | jq '.summary.recall'

# ログ確認
tail -100 tests/performance_test/performance_test.log
```

**期待される結果**:
- Recall: 33-100%（サンプルが小さいため変動大）
- 処理時間: 約2分
- コスト: 約54円
- エラー: 0件

### ステップ2: プロトタイプテスト（30件）

```bash
# 本格テスト
python3 performance_test_runner.py -n 30

# 詳細分析
python3 -c "
import json
with open('tests/performance_test/test_results.json', 'r') as f:
    r = json.load(f)
    print(f'Recall: {r[\"summary\"][\"recall\"]:.1%}')
    print(f'平均処理時間: {r[\"summary\"][\"avg_time_per_case\"]:.1f}秒')
    print(f'総コスト: {r[\"summary\"][\"total_cost_jpy\"]:.2f}円')
"
```

**期待される結果**:
- Recall: 70-90%
- 処理時間: 約20分
- コスト: 約543円
- エラー: 0-3件

### ステップ3: 結果分析と判断

**判断基準**:
- ✅ **Recall ≥ 80%**: Phase 2へ進行
- ⚠️ **Recall 60-80%**: 改善後に再テスト
- ✗ **Recall < 60%**: システム見直し

---

## 🌟 重要な発見（既知の成果）

### JP2014007731Aケース

**テストデータ2行目に含まれている**:
```csv
JP2014007731A,JP2011171723A,Ax,20110901
```

これは先ほどのエンドツーエンドテストと同じケースです！

**既知の結果**:
- ✅ SUCCESS版（CL限定）: JP2011171723A **含む**
- ✅ FIXED版（修正版）: JP2011171723A **含む**
- ✗ FULLTEXT版（旧版バグ）: JP2011171723A **含まない**

**現在のシステム**: FIXED版を使用 → **JP2011171723Aを発見できるはず**

**性能テストでの検証**:
- このケースが正しく動作すれば、システムの信頼性が実証される
- Recall計算にも含まれる

---

## 🎯 成功の定義

### 技術的成功

- **Recall ≥ 80%**: 検索漏れ20%以下
- **処理時間 ≤ 40秒/件**: スケーラブル
- **エラー率 < 5%**: 安定性確保

### ビジネス的成功

- **コスト ≤ 20円/件**: 実用的
- **全件処理見積もり明確**: 766万円、57日（並列処理）
- **改善の方向性明確**: Recall向上の具体策

---

## 📞 サポート・質問

**ドキュメント**:
- 戦略: `PERFORMANCE_TEST_STRATEGY.md`
- 使用ガイド: `PERFORMANCE_TEST_README.md`
- 本サマリー: `PERFORMANCE_TEST_SUMMARY.md`

**実行**:
```bash
# ヘルプ
python3 performance_test_runner.py --help

# 最小テスト
python3 performance_test_runner.py -n 3
```

**結果確認**:
```bash
# JSON
cat tests/performance_test/test_results.json | jq

# ログ
less tests/performance_test/performance_test.log
```

---

## 🚀 次のアクション

### 即時（今日）

1. ✅ システム構築完了
2. 🔄 **3件テスト実行**（推奨）
3. 🔄 **30件テスト実行**（時間があれば）

### 短期（今週）

1. 結果分析
2. 改善提案作成
3. Phase 2計画策定

### 中期（今月）

1. 100件テスト実行
2. 並列処理実装
3. 本番運用判断

---

生成日: 2025年11月20日
システム: PatentField特許検索システム v2.0
ステータス: **Phase 1完了、テスト実行可能**
推奨アクション: `python3 performance_test_runner.py -n 3`
