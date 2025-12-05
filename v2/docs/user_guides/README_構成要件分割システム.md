# 特許構成要件分割システム

Claude Sonnet 4.5 (Vertex AI) を使用した特許の自動構成要件分割システム

**作成日:** 2025年
**対象:** 特許審査における先行文献調査実務

---

## 概要

このシステムは、特許データ（テキスト/PDF/XML）を入力として、Claude Sonnet 4.5を使用して自動的に構成要件を分割・分析します。

### 主な機能

- ✅ **多様な入力形式対応**: テキスト(.txt)、PDF(.pdf)、XML(.xml)
- ✅ **Claude Sonnet 4.5**: Google Vertex AI経由で最新AIモデルを使用
- ✅ **構成要件分割ガイド準拠**: 実務に即した分割方法を適用
- ✅ **構造化JSON出力**: 検索システムに直接利用可能な形式
- ✅ **トークン使用量追跡**: コスト管理に必要な情報を提供

---

## インストール

### 1. 必要なパッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. 認証設定

Google Cloudサービスアカウントの認証情報が必要です：

```
/Users/ttdc-user/Desktop/patgenius/zhang_opera/ttdc-in-house-dev-3e07247326cb.json
```

---

## 使用方法

### コマンドライン使用

```bash
# 基本的な使い方
python patent_structure_analyzer.py input_patent.pdf

# 出力ファイル名を指定
python patent_structure_analyzer.py input_patent.pdf -o output_result.json

# 認証情報を指定
python patent_structure_analyzer.py input_patent.pdf -c path/to/credentials.json

# 最大トークン数を指定
python patent_structure_analyzer.py input_patent.pdf -m 10000
```

### Pythonスクリプトから使用

```python
from patent_structure_analyzer import PatentStructureAnalyzer

# アナライザーの初期化
analyzer = PatentStructureAnalyzer(
    credentials_path='../ttdc-in-house-dev-3e07247326cb.json',
    project_id='ttdc-in-house-dev'
)

# ファイルを分析
result = analyzer.analyze_file(
    input_filepath='特許データ.pdf',
    output_filepath='結果.json'
)

# サマリー表示
analyzer.print_summary(result)

# 結果の利用
if result['status'] == 'success':
    for item in result['構成要件']:
        print(f"[{item['構成要素番号']}] {item['構成要素']}")
        print(f"  重要度: {item['構成要素の重要度']}")
```

---

## 出力形式

### 成功時の出力

```json
{
  "status": "success",
  "input_file": "特許データ.pdf",
  "構成要件": [
    {
      "構成要素番号": "1a",
      "構成要素": "太陽電池モジュール",
      "構成要素のサポート箇所": "[0002]太陽電池モジュールは...",
      "構成要素の簡単説明": "発明の主体となる装置",
      "従属関係": "→1b, →1c",
      "構成要素の重要度": 0.9
    },
    {
      "構成要素番号": "1b",
      "構成要素": "第1保護部材",
      "構成要素のサポート箇所": "[0015]第1保護部材は透光性を有し...",
      "構成要素の簡単説明": "太陽光を透過させる保護層",
      "従属関係": "←1a, →1c",
      "構成要素の重要度": 0.7
    }
  ],
  "tokens": {
    "input_tokens": 15000,
    "output_tokens": 3000,
    "total_tokens": 18000
  },
  "処理時間_秒": 45.2,
  "model": "claude-sonnet-4-5@20250929"
}
```

### エラー時の出力

```json
{
  "status": "error",
  "error_type": "FILE_NOT_FOUND",
  "message": "ファイルが見つかりません: input.pdf"
}
```

---

## 構成要件の評価項目

### 構成要素番号
- 請求項ごと: 1, 2, 3, ...
- 請求項内の要素: a, b, c, ...
- 例: "1a" = 請求項1の要素a

### 構成要素の重要度（0〜1）

| スコア | 意味 | 説明 |
|--------|------|------|
| 0.9〜1.0 | 極めて重要 | 発明の核心部分、必須の新規性要素 |
| 0.7〜0.9 | 重要 | 発明の特徴部分、進歩性に関わる |
| 0.5〜0.7 | 中程度 | 実施形態を限定する要素 |
| 0.3〜0.5 | 補助的 | 付加的な構成要素 |
| 0.0〜0.3 | 一般的 | 慣用的・公知の要素 |

### 従属関係の記号

- `→1b`: この要素から1bへ依存
- `←1a`: 1aからこの要素へ依存
- `↔1c`: 相互依存関係

---

## システム構成

```
v2/
├── patent_structure_analyzer.py    # メインシステム
├── 特許検索のための構成要件分割ガイド.md  # 分割ガイド（AIが参照）
├── requirements.txt                # 必要パッケージ
└── README_構成要件分割システム.md    # このファイル
```

---

## 技術仕様

### 使用AI モデル
- **モデル名**: Claude Sonnet 4.5
- **バージョン**: `claude-sonnet-4-5@20250929`
- **提供**: Google Vertex AI

### 認証
- **方法**: Google Cloud サービスアカウント
- **プロジェクトID**: `ttdc-in-house-dev`
- **リージョン**: `us-east5`

### 対応ファイル形式
- **テキスト**: UTF-8エンコーディング
- **PDF**: PyMuPDF (fitz) で処理
- **XML**: ElementTree で処理

---

## トラブルシューティング

### PyMuPDF がインストールできない

```bash
# macOS
brew install mupdf

# または
pip install --upgrade pip
pip install PyMuPDF
```

### 認証エラー

```
google.auth.exceptions.DefaultCredentialsError
```

**解決方法:**
1. サービスアカウントJSONファイルのパスを確認
2. ファイルの読み取り権限を確認
3. プロジェクトIDが正しいか確認

### API呼び出しエラー

```
anthropic.APIError: rate_limit_error
```

**解決方法:**
- Vertex AIのクォータを確認
- リトライ間隔を設定
- max_tokensを調整

---

## 性能

### 処理速度
- **小規模特許**（10ページ以下）: 30〜60秒
- **中規模特許**（30ページ以下）: 60〜120秒
- **大規模特許**（50ページ以上）: 120〜300秒

### トークン使用量（目安）
- **入力**: 10,000〜30,000 tokens（特許の規模による）
- **出力**: 2,000〜8,000 tokens（構成要件の数による）
- **合計**: 12,000〜38,000 tokens

### コスト概算（Vertex AI料金）
- Claude Sonnet 4.5: 入力$3/1M tokens、出力$15/1M tokens
- 1特許あたり: 約$0.40〜$1.20（規模による）

---

## ライセンス

社内使用専用

---

## 更新履歴

### v1.0.0 (2025年)
- 初版リリース
- Claude Sonnet 4.5 対応
- PDF/XML/テキスト入力対応
- 構成要件分割ガイド準拠

---

## サポート

質問やバグ報告は開発チームまでお願いします。
