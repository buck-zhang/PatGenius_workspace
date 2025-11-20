# 特許構成要件キーワード抽出システム

Claude Sonnet 4.5 (Vertex AI) + PatentField API による先行文献調査用検索キーワード自動生成システム

**作成日:** 2025年
**対象:** 特許審査における先行文献調査実務

---

## 概要

このシステムは、構成要件分割システムで生成されたJSONを入力として、各構成要素について先行文献調査用の検索キーワードを自動生成します。

### 主な機能

- ✅ **重要度ベースの検索式構築**: 重要度0.9以上の構成要素でAND検索式を自動生成
- ✅ **PatentField API予備検索**: 最大50件の先行文献を取得・分析
- ✅ **3階層キーワード生成**: ドンピシャ・上位概念・下位概念の3階層
- ✅ **日英両言語対応**: 日本語と英語のキーワードを同時生成
- ✅ **優先度・頻出度付き**: 検索効率を考慮した優先順位と頻出度を記録
- ✅ **トークン使用量追跡**: コスト管理に必要な情報を提供

---

## システムフロー

```
構成要件JSON（入力）
    ↓
【ステップ1】検索式構築（Claude Sonnet 4.5）
  - 重要度0.9以上の要素を特定
  - AND条件で組み合わせた検索式を生成
    ↓
【ステップ2】PatentField API予備検索
  - 検索式で実際に検索実行
  - 最大50件の先行文献を取得
  - 全文データ（タイトル・要約・請求項）を取得
    ↓
【ステップ3】キーワード精錬（Claude Sonnet 4.5）
  - 予備検索結果を分析
  - 3階層 × 2言語のキーワード生成
  - 優先度と頻出度を付与
    ↓
キーワードJSON（出力）
```

---

## インストール

### 1. 必要なパッケージのインストール

```bash
cd /Users/ttdc-user/Desktop/patgenius/zhang_opera/v2

# パッケージのインストール
pip install -r requirements.txt
```

### 2. 認証情報の確認

**Google Cloud サービスアカウント:**
```bash
ls -la ../ttdc-in-house-dev-3e07247326cb.json
```

**PatentField API認証情報:**
```bash
ls -la ../patentfield_key.json
```

`patentfield_key.json` の内容例:
```json
{
  "PATENTFIELD_API_KEY": "your_api_key_here",
  "endpoint": "https://ttdc.patentfield.com/api/v1/patents/search"
}
```

---

## 使用方法

### コマンドライン使用

```bash
# 基本的な使い方
python3 patent_keyword_extractor.py tests/jp2014007731A_構成要件.json

# 出力ファイル名を指定
python3 patent_keyword_extractor.py tests/jp2014007731A_構成要件.json -o output_keywords.json

# 認証情報を指定
python3 patent_keyword_extractor.py tests/jp2014007731A_構成要件.json \
  -c path/to/credentials.json \
  -p path/to/patentfield_key.json

# 重要度の閾値を調整
python3 patent_keyword_extractor.py tests/jp2014007731A_構成要件.json \
  -m 0.8 \  # 抽出対象の最小重要度
  -t 0.95   # 予備検索で使用する重要度閾値
```

### Pythonスクリプトから使用

```python
from patent_keyword_extractor import PatentKeywordExtractor

# エクストラクター初期化
extractor = PatentKeywordExtractor(
    credentials_path='../ttdc-in-house-dev-3e07247326cb.json',
    patentfield_key_path='../patentfield_key.json',
    project_id='ttdc-in-house-dev'
)

# キーワード抽出実行
result = extractor.extract_keywords(
    constituent_json_path='tests/jp2014007731A_構成要件.json',
    output_path='tests/jp2014007731A_キーワード.json',
    min_importance=0.7,       # 抽出対象の最小重要度
    importance_threshold=0.9  # 予備検索で使用する閾値
)

# サマリー表示
extractor.print_summary(result)

# 結果の利用
if result['status'] == 'success':
    for kw in result['keywords']:
        print(f"[{kw['構成要素番号']}] {kw['構成要素']}")
        print(f"  日本語: {[k['keyword'] for k in kw['ドンピシャキーワード_日本語'][:3]]}")
        print(f"  英語: {[k['keyword'] for k in kw['ドンピシャキーワード_英語'][:3]]}")
```

---

## 出力形式

### 成功時の出力

```json
{
  "status": "success",
  "input_file": "tests/jp2014007731A_構成要件.json",
  "予備検索": {
    "検索式": "CL:論理回路 AND CL:トランジスタ AND CL:オフ電流",
    "戦略": "重要度1.0の「オフ電流」を核として、重要度0.95の「論理回路」「トランジスタ」をAND条件で組み合わせ",
    "ヒット件数": 234,
    "取得件数": 50,
    "高重要度構成要素": ["1d", "1a", "1c"]
  },
  "keywords": [
    {
      "構成要素番号": "1a",
      "構成要素": "入力端子を介してデータ信号が入力される論理回路",
      "重要度": 0.95,
      "ドンピシャキーワード_日本語": [
        {"keyword": "論理回路", "priority": 1, "頻出度": 45},
        {"keyword": "論理ゲート", "priority": 2, "頻出度": 23},
        {"keyword": "ロジック回路", "priority": 3, "頻出度": 18}
      ],
      "上位概念キーワード_日本語": [
        {"keyword": "回路", "priority": 1, "頻出度": 87},
        {"keyword": "電子回路", "priority": 2, "頻出度": 34},
        {"keyword": "デジタル回路", "priority": 3, "頻出度": 29}
      ],
      "下位概念キーワード_日本語": [
        {"keyword": "AND回路", "priority": 1, "頻出度": 15},
        {"keyword": "OR回路", "priority": 2, "頻出度": 12},
        {"keyword": "NOT回路", "priority": 3, "頻出度": 10}
      ],
      "ドンピシャキーワード_英語": [
        {"keyword": "logic circuit", "priority": 1, "頻出度": 42},
        {"keyword": "logic gate", "priority": 2, "頻出度": 21},
        {"keyword": "logic element", "priority": 3, "頻出度": 16}
      ],
      "上位概念キーワード_英語": [
        {"keyword": "circuit", "priority": 1, "頻出度": 82},
        {"keyword": "electronic circuit", "priority": 2, "頻出度": 31},
        {"keyword": "digital circuit", "priority": 3, "頻出度": 27}
      ],
      "下位概念キーワード_英語": [
        {"keyword": "AND gate", "priority": 1, "頻出度": 14},
        {"keyword": "OR gate", "priority": 2, "頻出度": 11},
        {"keyword": "NOT gate", "priority": 3, "頻出度": 9}
      ]
    }
  ],
  "tokens": {
    "step1_構築": {
      "input_tokens": 1500,
      "output_tokens": 400,
      "total_tokens": 1900
    },
    "step3_精錬": {
      "input_tokens": 45000,
      "output_tokens": 3500,
      "total_tokens": 48500
    },
    "total_tokens": 50400
  },
  "処理時間_秒": 89.3,
  "model": "claude-sonnet-4-5@20250929"
}
```

---

## キーワードの階層

### 3階層の意味

| 階層 | 意味 | 用途 |
|------|------|------|
| **ドンピシャ** | 構成要素に完全一致する用語 | 精密検索、ノイズを減らす |
| **上位概念** | より広い概念の用語 | 網羅的検索、見落としを防ぐ |
| **下位概念** | より具体的な用語 | 特定実施形態の検索 |

### 使用例

**構成要素**: 「酸化物半導体」

```
ドンピシャ: 酸化物半導体、oxide semiconductor
上位概念: 半導体、semiconductor、半導体材料
下位概念: In-Ga-Zn-O、IGZO、CAAC-OS、酸化インジウムガリウム亜鉛
```

---

## システム構成

```
v2/
├── patent_keyword_extractor.py       # キーワード抽出システム（新規）
├── patent_structure_analyzer.py      # 構成要件分割システム（既存）
├── requirements.txt                   # 必要パッケージ（更新）
├── README_キーワード抽出システム.md   # このファイル
├── README_構成要件分割システム.md     # 既存
└── tests/
    ├── jp2014007731A.xml
    ├── jp2014007731A_構成要件.json   # 入力
    └── jp2014007731A_キーワード.json  # 出力
```

---

## 技術仕様

### 使用AI モデル
- **モデル名**: Claude Sonnet 4.5
- **バージョン**: `claude-sonnet-4-5@20250929`
- **提供**: Google Vertex AI

### 認証
- **Google Cloud**: サービスアカウント認証
- **PatentField API**: APIキー認証
- **プロジェクトID**: `ttdc-in-house-dev`
- **リージョン**: `us-east5`

### PatentField API仕様
- **エンドポイント**: `https://ttdc.patentfield.com/api/v1/patents/search`
- **検索タイプ**: `expert`（コマンド検索）
- **取得項目**: `app_doc_id`, `title`, `abstract`, `app_claims`, `description`
- **取得件数**: 最大50件
- **レート制限**: 60リクエスト/分

---

## トラブルシューティング

### エラー1: PatentField API認証エラー

```
requests.exceptions.HTTPError: 401 Client Error: Unauthorized
```

**解決方法:**
1. `patentfield_key.json` が正しいパスにあるか確認
2. APIキーが有効か確認
3. エンドポイントURLが正しいか確認

```bash
cat ../patentfield_key.json
```

### エラー2: PatentField APIレート制限

```
requests.exceptions.HTTPError: 429 Client Error: Too Many Requests
```

**解決方法:**
- 60秒待ってから再実行
- 複数の特許を処理する場合、リクエスト間に待機時間を追加

### エラー3: 予備検索でヒット件数が0件

```
ヒット件数: 0件
```

**解決方法:**
1. 検索式が厳しすぎる可能性
2. `importance_threshold` を下げる（例: 0.9 → 0.8）
3. 構成要件JSONの重要度を確認

```bash
python3 patent_keyword_extractor.py input.json -t 0.8
```

### エラー4: Claude APIエラー

```
anthropic.APIError: rate_limit_error
```

**解決方法:**
- Vertex AIのクォータを確認
- 処理を分割して実行

---

## 性能

### 処理速度（1特許あたり）
- **検索式構築**: 5-10秒
- **予備検索**: 3-5秒
- **キーワード精錬**: 60-90秒（構成要素数による）
- **合計**: 約70-110秒

### トークン使用量（目安）
- **検索式構築**: ~2,000 tokens
- **キーワード精錬**: ~50,000 tokens（構成要素数による）
- **合計**: 約52,000 tokens

### コスト概算（Vertex AI料金）
- Claude Sonnet 4.5: 入力$3/1M tokens、出力$15/1M tokens
- **1特許あたり**: 約$0.80-1.00

---

## 使用例

### 例1: 基本的な使用

```bash
# 構成要件JSONからキーワード抽出
python3 patent_keyword_extractor.py tests/jp2014007731A_構成要件.json

# 出力
# ステップ1: 検索式構築
# 検索式: CL:論理回路 AND CL:トランジスタ AND CL:オフ電流
#
# ステップ2: PatentField API予備検索
# ヒット件数: 234件
# 取得件数: 50件
#
# ステップ3: キーワード精錬
# [1a] キーワード精錬中...
# [1c] キーワード精錬中...
# ...
#
# 結果を保存しました: tests/jp2014007731A_キーワード.json
```

### 例2: 結果の活用

```python
import json

# キーワードJSONを読み込み
with open('tests/jp2014007731A_キーワード.json', 'r') as f:
    data = json.load(f)

# 各構成要素のドンピシャキーワードを抽出
for kw in data['keywords']:
    print(f"\n[{kw['構成要素番号']}] {kw['構成要素']}")

    # 日本語キーワード
    ja_keywords = [k['keyword'] for k in kw['ドンピシャキーワード_日本語']]
    print(f"  日本語: {', '.join(ja_keywords)}")

    # 英語キーワード
    en_keywords = [k['keyword'] for k in kw['ドンピシャキーワード_英語']]
    print(f"  英語: {', '.join(en_keywords)}")
```

---

## ワークフロー統合

### 構成要件分割 → キーワード抽出

```bash
# ステップ1: 特許XMLから構成要件を分割
python3 patent_structure_analyzer.py patent.xml

# ステップ2: 構成要件からキーワード抽出
python3 patent_keyword_extractor.py patent_構成要件.json

# 結果
# - patent_構成要件.json: 構成要件リスト
# - patent_キーワード.json: 検索キーワードリスト
```

---

## ライセンス

社内使用専用

---

## 更新履歴

### v1.0.0 (2025年)
- 初版リリース
- Claude Sonnet 4.5 + PatentField API連携
- 3階層キーワード生成（日英両言語対応）
- 重要度ベースの検索式構築
- 予備検索による頻出度分析

---

## サポート

質問やバグ報告は開発チームまでお願いします。
