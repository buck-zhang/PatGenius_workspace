# PatentField特許検索システム v2.0

構成要素ごと検索による高精度な特許検索システム

## 概要

本システムは、PatentField APIとClaude Sonnet 4.5を活用し、特許の構成要件を自動抽出して検索を実行する特許検索システムです。

**主な特徴**:
- 構成要素ごとの適応的検索（50-300件の最適化）
- FI/IPC/CPC/Fterm分類コードの自動抽出
- 3段階階層キーワード抽出（ドンピシャ/上位概念/下位概念）
- 並行処理による高速検索
- Claude API統合による検索式最適化
- **NEW**: AsyncIO + Prompt Caching による超高速化（最大70-80%短縮）

---

## ファイル構造

### メインコード（本番用）

```
v2/
├── patent_structure_analyzer.py        # 構成要件分割システム（最適化版）
├── patent_keyword_extractor.py         # キーワード抽出システム
├── patent_classification_extractor.py  # 特許分類コード抽出システム
├── patent_search_executor.py           # 基本検索実行システム
├── patent_search_executor_per_component.py  # 構成要素ごと検索システム（メイン）
├── patent_search_executor_optimized.py # 統合最適化版（NEW）
├── performance_test_system.py          # 性能テストシステム
├── test_optimization.py                # 最適化テストスクリプト（NEW）
├── requirements.txt                    # Python依存パッケージ
└── requirements_optimized.txt          # 最適化版依存パッケージ（NEW）
```

### ドキュメント

```
docs/
├── current_reports/                    # 最新分析レポート
│   ├── FI_CLASSIFICATION_FIX_VERIFICATION_REPORT.md  # FI分類修正検証レポート
│   ├── TEST3_ZERO_HITS_ROOT_CAUSE_ANALYSIS.md       # Test #3根本原因分析
│   └── PERFORMANCE_OPTIMIZATION_IMPLEMENTATION.md   # 性能最適化実装レポート（NEW）
├── user_guides/                        # ユーザーガイド
│   ├── README_キーワード抽出システム.md
│   ├── README_構成要件分割システム.md
│   ├── README_特許分類抽出システム.md
│   ├── PATENT_SEARCH_EXECUTOR_README.md
│   ├── システム構築prompt.md
│   ├── テスト実行ガイド.md
│   ├── 特許検索のための構成要件分割ガイド.md
│   └── 構築指示.md
└── system_design/                      # システム設計文書（空）

README_OPTIMIZATION.md                  # 性能最適化版クイックガイド（NEW）
IMPLEMENTATION_SUMMARY.md               # 最適化実装サマリー（NEW）
```

### テスト関連

```
tests/
└── performance_test/                   # 性能テストデータ
    ├── combined_data_top10.csv         # テストデータ（上位10件）
    └── results/                        # テスト結果（JSON）
```

### アーカイブ（参照用）

```
archive/
├── old_versions/                       # 古いバージョンのコード
├── old_test_scripts/                   # 古いテストスクリプト
├── temp_data/                          # 一時データファイル
└── old_docs/                           # 古い分析レポート
```

---

## クイックスタート

### 1. 環境セットアップ

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# Google Cloud認証情報の配置
# ../gcp-sa-key.json に配置

# PatentField APIキーの配置
# ../patentfield_key.json に配置
```

### 2. 単一特許の検索実行

```bash
# 構成要件分割
python3 patent_structure_analyzer.py JP2014007731A

# キーワード抽出
python3 patent_keyword_extractor.py JP2014007731A_構成要件.json

# 特許分類コード抽出
python3 patent_classification_extractor.py JP2014007731A_構成要件.json

# 検索実行（構成要素ごと）
python3 patent_search_executor_per_component.py \
  --keywords JP2014007731A_キーワード.json \
  --classifications JP2014007731A_特許分類.json \
  --output JP2014007731A_検索結果.json
```

### 3. 性能テスト実行

```bash
# 複数件テスト（上位10件）
python3 performance_test_system.py \
  --csv tests/performance_test/combined_data_top10.csv \
  --limit 10

# 単一行テスト（特定の行番号を指定）
python3 performance_test_system.py \
  --csv tests/performance_test/combined_data_top10.csv \
  --row 5

# 結果はJSON + MD形式で自動保存
# - performance_test_summary_YYYYMMDD_HHMMSS.json
# - performance_test_summary_YYYYMMDD_HHMMSS.md （関連ファイルへのリンク付き）
```

---

## 主要機能

### 1. 構成要素ごと適応的検索

各構成要素に対して以下の検索ロジックを適用：

1. **Step 1**: ドンピシャFI分類のみで検索
2. **判定**: 50-300件の範囲内なら完了
3. **Branch A** (ヒット数 > 300): 絞り込み
   - FI AND キーワードで絞り込み
   - Claude APIで検索式最適化（オプション）
4. **Branch B** (ヒット数 < 50): 拡張
   - ドンピシャFI OR (上位概念FI AND キーワード)
   - Claude APIでキーワード拡張（オプション）

### 2. FI分類コード正規化

**修正済み（2025年11月29日）**:
- FI分類コードの空白を自動除去
- PatentField API互換形式に正規化
- 例: `H02K  33/18` → `H02K33/18`

### 3. 並行処理

- 最大5ワーカーで並行検索
- 処理時間の大幅短縮

### 4. 重複削除

- 複数構成要素の検索結果を統合
- 特許番号の重複を自動削除

### 5. 性能テスト機能

**新機能（2025年11月29日追加）**:

#### 単一行テスト（`--row`オプション）
- CSVの特定の行番号を指定して1件のみテスト可能
- 例: `--row 5` で5行目のテストケースのみ実行
- デバッグや個別検証に最適

#### MD形式レポート自動生成
- テスト結果をMarkdown形式で自動生成
- **関連ファイルへのリンク付き**:
  - 構成要件分割結果（`_structure.json`）
  - キーワード抽出結果（`_keywords.json`）
  - 特許分類抽出結果（`_classifications.json`）
  - 検索結果（`_search_result.json`）
- サマリー統計、コスト情報を見やすく表示
- JSON形式の詳細データも同時生成

---

## 最新の修正・改善

### 🚀 0. 性能最適化実装（2025-11-29）⭐ NEW

**処理速度を最大70-80%短縮する5つの最適化を実装しました。**

#### 実装した最適化

1. **AsyncIO完全移行**（優先度1）
   - 予想効果: 40-50%短縮
   - 全Claude API呼び出しを非同期化
   - `asyncio.to_thread()`でI/O待機時間を最大300%改善

2. **Claude Prompt Caching**（優先度2）
   - 予想効果: 30-40%短縮 + コスト90%削減
   - システムプロンプトをキャッシュ
   - キャッシュヒット時85%レイテンシ削減

3. **PatentField API並列化**（優先度3）
   - 予想効果: 20-30%短縮
   - `aiohttp` + HTTP/2セッション再利用
   - TCP接続再利用でオーバーヘッド削減

4. **早期終了最適化**（優先度4）
   - 予想効果: 10-20%短縮
   - エラーハンドリング改善

5. **並列処理の最適化**（優先度5）
   - 予想効果: 5-10%短縮
   - キーワード抽出・分類抽出を並列実行

#### クイックスタート（最適化版）

```bash
# 依存関係インストール
pip install -r requirements_optimized.txt

# テスト実行
python3 test_optimization.py

# 最適化版システムの使用
python3 patent_search_executor_optimized.py input.txt
```

**詳細**: `README_OPTIMIZATION.md` または `IMPLEMENTATION_SUMMARY.md` を参照

---

### 1. FI分類コード空白除去修正（2025-11-29）

**問題**: FI分類コードに空白が含まれ、PatentField APIで検索失敗（0件）

**修正内容**:
1. `patent_classification_extractor.py`: 正規化関数を追加（空白除去）
2. `patent_search_executor_per_component.py`: バリデーション強化 + 自動修復

**効果**:
- Test #3: 0件 → 1,214件（劇的改善）
- 検索成功率: 0% → 84.6%（11/13構成要素）

詳細: `docs/current_reports/FI_CLASSIFICATION_FIX_VERIFICATION_REPORT.md`

### 2. キーワード検索フィールド修正（2025-11-29）

**問題**: `patent_classification_extractor.py`のキーワードに`CL:`プレフィックスが付与され、請求項のみの検索に制限されていた

**修正内容**:
1. Claude APIシステムプロンプトを修正（フィールドプレフィックス禁止を明記）
2. フォールバック検索式から`CL:`プレフィックスを除去
3. 全文検索（全フィールド横断検索）に変更

**効果**:
- 検索範囲が請求項のみ → 全文（請求項、要約、詳細説明、タイトル）に拡大
- 検索漏れの削減

### 3. 性能テスト機能強化（2025-11-29）

**追加機能**:
1. **単一行テスト（`--row`オプション）**:
   - CSVの特定行のみをテスト可能
   - デバッグや個別検証に最適

2. **MD形式レポート自動生成**:
   - 見やすいMarkdown形式でレポート生成
   - 関連ファイルへのリンク自動挿入
   - サマリー統計、コスト情報を表形式で表示

**使用例**:
```bash
# 単一行テスト
python3 performance_test_system.py --csv test.csv --row 5

# 結果ファイル
# - performance_test_summary_YYYYMMDD_HHMMSS.json (詳細データ)
# - performance_test_summary_YYYYMMDD_HHMMSS.md (レポート)
```

---

## パフォーマンス

### Test #1 (JP2013224028A) の実績

| 指標 | 値 |
|-----|-----|
| 処理時間 | 17.5分 |
| トークン数 | 147,342 tokens |
| コスト | ¥191 |
| 検索結果 | 627件（重複削除後） |
| 紐づき特許検出 | ✅ 成功 |

### 性能テスト結果（2025-11-29）

| 指標 | 値 |
|-----|-----|
| テスト実施件数 | 9件 |
| 検出成功率 | 11.1%（1/9件） |
| 総処理時間 | 約2.6時間 |
| 総コスト | 約¥1,719 |

---

## API設定

### PatentField API

`../patentfield_key.json`:
```json
{
  "PATENTFIELD_API_KEY": "your_api_key_here",
  "endpoint": "https://ttdc.patentfield.com/api/v1/patents/search"
}
```

### Google Cloud / Vertex AI (Claude API)

`../gcp-sa-key.json`:
- Google Cloud サービスアカウントキー
- Vertex AI APIへのアクセス権限が必要

---

## トラブルシューティング

### 検索結果が0件

1. **FI分類コードの形式確認**
   - 空白が含まれていないか
   - コロン表記（`:`）が含まれていないか

2. **キーワードの妥当性確認**
   - ドンピシャキーワードが存在するか
   - キーワードが一般的すぎないか

3. **ログ確認**
   ```bash
   # 検索クエリを確認
   python3 patent_search_executor_per_component.py ... 2>&1 | grep "検索式"
   ```

### Claude API未初期化エラー

```
⚠️ Claude API未初期化のため絞り込みスキップ
```

**原因**: Google Cloud認証情報が見つからない

**対処**:
```bash
# 認証情報ファイルの確認
ls -la ../gcp-sa-key.json

# パスを明示的に指定
python3 patent_search_executor_per_component.py \
  --credentials ../gcp-sa-key.json \
  ...
```

---

## 今後の改善計画

### 短期（1週間以内）

1. Test #6, #8の修正版実行（FI分類問題の検証）
2. Test #2の詳細調査（番号正規化問題）
3. 全10テストケースの再実行

### 中期（1ヶ月以内）

1. Claude API最適化機能の有効化と効果測定
2. 検索戦略の根本的見直し（検出率向上）
3. IPC/CPC分類の活用拡大

### 長期（3ヶ月以内）

1. キーワード抽出精度の向上
2. 検索範囲の最適化（30-500件など）
3. 検出率目標: 70%以上

---

## ライセンス

プロプライエタリ

---

## サポート

技術的な質問や問題報告は、プロジェクトリーダーまでお問い合わせください。

---

**更新日**: 2025年11月29日
**バージョン**: 2.1.0
**ステータス**: 本番運用中 + 最適化版リリース
**最新アップデート**:
- ⭐ **性能最適化実装**（AsyncIO + Prompt Caching + 並列化、最大70-80%短縮）
- FI分類空白除去修正
- キーワード全文検索対応
- 性能テスト機能強化（`--row`オプション、MDレポート生成）
