# 特許分類コード抽出システム

構成要件JSONから特許分類コード（IPC, CPC, FI, Fterm）を自動抽出するシステムです。

## 概要

このシステムは以下の3つのデータソースを統合して特許分類コードを抽出します：

1. **PatentField API予備検索**: 分類コードランキング取得
2. **OpenSearch特許分類検索**: セマンティック検索
3. **Claude Sonnet 4.5**: 結果統合と階層化

## 主要機能

### 1. 複数ソース統合

- PatentField APIから分類コードの出現頻度ランキングを取得
- OpenSearch APIでセマンティック検索を実行
- 両方のソースに出現する分類コードを優先

### 2. 3段階階層化

各分類タイプ（IPC, CPC, FI, Fterm）について、以下の3つの階層を生成：

- **ドンピシャ**: 構成要件に最も適合する分類コード
- **上位概念**: ドンピシャの親分類コード
- **下位概念**: ドンピシャの子分類コード

### 3. 4つの分類タイプ対応

- **IPC**: 国際特許分類
- **CPC**: 共同特許分類
- **FI**: 日本特許庁ファイルインデックス
- **Fterm**: 日本特許庁テーマコード/観点

## セットアップ

### 前提条件

- Python 3.10以上
- Google Cloud認証情報（Vertex AI用）
- PatentField APIキー
- OpenSearch特許分類検索API（オプション、port 8000）

### 依存パッケージのインストール

```bash
cd /Users/ttdc-user/Desktop/patgenius/zhang_opera/v2
pip install -r requirements.txt
```

### 認証情報の配置

1. **Google Cloud認証情報**:
   ```
   ../ttdc-in-house-dev-3e07247326cb.json
   ```

2. **PatentField APIキー**:
   ```
   ../patentfield_key.json
   ```

## 使用方法

### コマンドライン実行

```bash
# 基本実行
python patent_classification_extractor.py tests/jp2014007731A_構成要件.json

# 出力ファイルを指定
python patent_classification_extractor.py input.json --output output.json

# 最小重要度を指定（デフォルト: 0.9）
python patent_classification_extractor.py input.json --min-importance 0.95

# 認証情報ファイルを指定
python patent_classification_extractor.py input.json \\
  --credentials path/to/gcp-sa-key.json \\
  --patentfield-key path/to/patentfield_key.json

# OpenSearch APIのURLを指定
python patent_classification_extractor.py input.json \\
  --opensearch-url http://localhost:8000
```

### Pythonスクリプトから使用

```python
from patent_classification_extractor import PatentClassificationExtractor

# 抽出器の初期化
extractor = PatentClassificationExtractor(
    credentials_path='../ttdc-in-house-dev-3e07247326cb.json',
    patentfield_key_path='../patentfield_key.json',
    opensearch_base_url='http://localhost:8000'
)

# 分類コード抽出
result = extractor.extract(
    input_file='tests/jp2014007731A_構成要件.json',
    output_file='output_classifications.json',
    min_importance=0.9
)

# 結果の参照
print(f"IPC ドンピシャ: {len(result['classifications']['IPC']['ドンピシャ'])}件")
```

## 入力ファイル形式

### 構成要件JSON

```json
{
  "status": "success",
  "構成要件": [
    {
      "構成要素番号": "1a",
      "構成要素": "入力端子を介してデータ信号が入力される論理回路",
      "構成要素の重要度": 0.95,
      "構成要素のサポート箇所": "[0024]論理回路...",
      "構成要素の簡単説明": "データ信号を受け取り...",
      "従属関係": "→1b, →1c"
    }
  ]
}
```

**必須フィールド**:
- `構成要素`: 構成要素の説明文
- `構成要素の重要度`: 重要度スコア（0.0-1.0）

## 出力ファイル形式

### 特許分類JSON

```json
{
  "status": "success",
  "input_file": "tests/jp2014007731A_構成要件.json",
  "min_importance": 0.9,
  "classifications": {
    "IPC": {
      "ドンピシャ": [
        {
          "code": "G11C14/00",
          "title_ja": "特定の構成又は動作モードに特徴のあるデジタル記憶装置",
          "title_en": "Digital stores characterised by arrangements...",
          "priority": 1,
          "sources": ["PatentField", "OpenSearch"],
          "evidence": "容量素子とトランジスタによる不揮発性データ保持機構..."
        }
      ],
      "上位概念": [...],
      "下位概念": [...]
    },
    "CPC": {...},
    "FI": {...},
    "Fterm": {...}
  },
  "metadata": {
    "patentfield_counts": {
      "IPC": 20,
      "CPC": 18,
      "FI": 15,
      "Fterm": 25
    },
    "opensearch_counts": {
      "IPC": 30,
      "CPC": 28,
      "FI": 22
    }
  }
}
```

## 処理フロー

### STEP 1: PatentField予備検索

1. **検索クエリ構築**
   - 重要度 >= min_importance の構成要素を使用
   - Claude Sonnet 4.5がPatentField検索式を生成
   - 構文制約: ネスト禁止、OR句は最大1つ

2. **分類コードランキング取得**
   ```python
   {
     "query": "CL:論理回路 AND CL:トランジスタ AND CL:オフ電流",
     "type": "expert",
     "options": {
       "group_conditions": [
         {
           "key": "ipcs",  # or "cpcs", "fi_themes", "fterms"
           "limit": 20,
           "sort_keys": ["-_nsubrecs"]
         }
       ]
     }
   }
   ```

3. **結果**: 各分類タイプの上位20件

### STEP 2: OpenSearch特許分類検索

1. **構成要素ごとにセマンティック検索**
   ```python
   POST http://localhost:8000/search/text
   {
     "query": "入力端子を介してデータ信号が入力される論理回路",
     "classification_type": "IPC",
     "limit": 20
   }
   ```

2. **結果統合**: 全構成要素の結果を統合、最高スコアを保持

3. **結果**: 各分類タイプの上位30件（スコア順）

### STEP 3: 結果統合と階層化

1. **Claude Sonnet 4.5で分析**
   - PatentFieldとOpenSearchの交差を特定
   - 分類コードの親子関係を分析
   - 3段階階層に分類

2. **優先順位ルール**:
   - 両方のソースに出現 → 最優先でドンピシャ
   - 高頻度・高スコア → ドンピシャ
   - ドンピシャの親 → 上位概念
   - ドンピシャの子 → 下位概念

3. **出力**: 各階層に最大15件

## フォールバック動作

### PatentField API利用不可時

- OpenSearch結果のみを使用
- Claude単独で分類コードを推定

### OpenSearch API利用不可時

- PatentField結果のみを使用
- Fterm情報は取得可能

### 両方のAPI利用不可時

- **Claude Sonnet 4.5の知識ベース**を使用
- 構成要件の技術内容から分類コードを推定
- 品質は下がるが、結果は出力可能

## 実行例

### テストデータでの実行

```bash
python patent_classification_extractor.py \\
  tests/jp2014007731A_構成要件.json \\
  --credentials ../ttdc-in-house-dev-3e07247326cb.json
```

**出力例**:
```
✓ Claude Sonnet 4.5クライアント初期化完了
✓ PatentField API設定読み込み完了
✓ OpenSearch API: http://localhost:8000

入力ファイル: tests/jp2014007731A_構成要件.json
構成要件数: 14
最小重要度: 0.9

================================================================================
STEP 1: PatentField予備検索（分類コードランキング取得）
================================================================================

検索式: (CL:論理回路 OR CL:フリップフロップ) AND CL:容量素子 AND CL:トランジスタ
戦略: 最重要特性である極低オフ電流(100zA以下)を「オフ電流」キーワードで捕捉...

IPCランキング取得中...
  ✓ 20件取得

================================================================================
STEP 2: OpenSearch特許分類検索
================================================================================

IPC検索中...
  ✓ 30件取得

================================================================================
STEP 3: 結果統合と階層化（Claude使用）
================================================================================

IPC処理中...
  ✓ ドンピシャ: 10件
  ✓ 上位概念: 8件
  ✓ 下位概念: 12件

...

================================================================================
✓ 処理完了
================================================================================
出力ファイル: tests/jp2014007731A_構成要件_特許分類.json

IPC:
  ドンピシャ: 10件
  上位概念: 8件
  下位概念: 12件

CPC:
  ドンピシャ: 10件
  上位概念: 9件
  下位概念: 11件

FI:
  ドンピシャ: 10件
  上位概念: 8件
  下位概念: 12件

Fterm:
  ドンピシャ: 12件
  上位概念: 8件
  下位概念: 12件
```

## パフォーマンス

### 処理時間の目安

- 構成要件14件の場合: 約60-90秒
  - STEP 1: 20-30秒（Claude + PatentField API × 4分類）
  - STEP 2: 10-20秒（OpenSearch API × 14要素 × 3分類）
  - STEP 3: 30-40秒（Claude × 4分類）

### トークン使用量

- 構成要件14件の場合: 約100,000-150,000トークン
  - 検索クエリ構築: ~2,000トークン
  - 階層化 × 4分類: ~100,000トークン

## トラブルシューティング

### PatentField API: 400 Bad Request

**エラー**: `"message":"invalid query"`

**原因**: 検索式の構文エラー
- ネストした括弧使用
- 複数のOR句

**対策**: Claude生成クエリの検証を強化（すでに実装済み）

---

**エラー**: `"message":"search condition is empty"`

**原因**: APIリクエストのペイロード不備

**対策**:
```python
# 正しいペイロード構造を確認
payload = {
    "query": "検索式",
    "type": "expert",
    "options": {
        "size": 100,
        "group_conditions": [...]
    }
}
```

### OpenSearch API: Connection Refused

**エラー**: `[Errno 61] Connection refused`

**原因**: OpenSearch APIが起動していない

**対策**:
```bash
cd patent_classification_search
docker-compose up -d  # Qdrant起動
python -m api.main     # API起動
```

### Claude API: Rate Limit

**エラー**: `429 Too Many Requests`

**対策**:
- 処理間隔を空ける
- バッチサイズを削減

## ディレクトリ構造

```
v2/
├── patent_classification_extractor.py  # メインスクリプト
├── README_特許分類抽出システム.md      # このファイル
├── tests/
│   ├── jp2014007731A_構成要件.json              # 入力サンプル
│   └── jp2014007731A_構成要件_特許分類.json     # 出力サンプル
└── patent_classification_search/        # OpenSearch APIシステム
    ├── api/
    │   └── main.py
    ├── core/
    └── docker-compose.yml
```

## ライセンス

MIT License

## 関連システム

- [patent_keyword_extractor.py](./patent_keyword_extractor.py): キーワード抽出システム
- [patent_classification_search/](./patent_classification_search/): OpenSearch分類検索API
