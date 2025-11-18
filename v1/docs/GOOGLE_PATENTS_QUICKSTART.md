# Google Patents API クイックスタートガイド

このガイドでは、Google Patents検索APIを最短で起動して使用する方法を説明します。

## 📋 要件

- Python 3.8以上
- Chrome または Chromium ブラウザ
- インターネット接続

## 🚀 クイックスタート（3ステップ）

### ステップ1: 依存関係のインストール

```bash
pip3 install -r requirements.txt
```

必要なパッケージ：
- `selenium` - ブラウザ自動化
- `beautifulsoup4` - HTML解析
- `fastapi` - APIサーバー
- `webdriver-manager` - ChromeDriver自動管理

### ステップ2: APIサーバー起動

```bash
./start_google_patents_api.sh
```

または直接：

```bash
python3 google_patents_api.py
```

サーバーが `http://localhost:8001` で起動します。

### ステップ3: テスト

別のターミナルで：

```bash
curl "http://localhost:8001/search/simple?q=agriculture&max_results=10"
```

## 📝 基本的な使い方

### 1. シンプルなキーワード検索

```bash
curl "http://localhost:8001/search/simple?q=agriculture&max_results=20"
```

### 2. AND/OR/NOT演算子

```bash
# AND検索（すべてのキーワードを含む）
curl "http://localhost:8001/search/simple?q=agriculture%20AND%20soil&max_results=20"

# OR検索（いずれかのキーワードを含む）
curl "http://localhost:8001/search/simple?q=agriculture%20OR%20farming&max_results=20"

# NOT検索（特定のキーワードを除外）
curl "http://localhost:8001/search/simple?q=agriculture%20NOT%20pesticide&max_results=20"
```

### 3. NEAR演算子（近接検索）

```bash
# "agriculture" と "crop" が5単語以内
curl "http://localhost:8001/search/simple?q=agriculture%20NEAR/5%20crop&max_results=20"
```

### 4. 複合クエリ

```bash
curl "http://localhost:8001/search/simple?q=(agriculture%20OR%20farming)%20AND%20soil%20NOT%20pesticide&max_results=20"
```

### 5. FI/IPC/CPC分類コード検索

```bash
# POST リクエストで高度な検索
curl -X POST "http://localhost:8001/search" \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": ["agriculture"],
    "fi_codes": ["A01B33/00"],
    "max_results": 50
  }'
```

### 6. CPC ランキング取得

```bash
curl "http://localhost:8001/cpc_ranking?q=agriculture&max_results=100&top_k=15"
```

**レスポンス例：**
```json
{
  "query": "agriculture",
  "total_hits": 1234567,
  "results_analyzed": 100,
  "cpc_ranking": [
    {
      "cpc_code": "A01B33/00",
      "count": 45,
      "percentage": 45.0
    },
    ...
  ]
}
```

### 7. 特許番号のみ取得（高速）

```bash
curl "http://localhost:8001/patent_numbers?q=agriculture&max_results=100"
```

**レスポンス例：**
```json
{
  "query": "agriculture",
  "total_hits": 1234567,
  "patent_numbers": [
    "US1234567A",
    "US2345678B",
    "JP6789012B2",
    ...
  ]
}
```

### 8. PDF ダウンロード

```bash
curl "http://localhost:8001/download/US1234567A" --output patent.pdf
```

## 🐍 Pythonクライアントの使用

### インストール

```python
# 依存関係は既にインストール済み
from google_patents_client_examples import GooglePatentsClient
```

### 基本的な使い方

```python
from google_patents_client_examples import GooglePatentsClient

# クライアント初期化
client = GooglePatentsClient(base_url="http://localhost:8001")

# 簡単な検索
results = client.simple_search("agriculture", max_results=20)

# 結果表示
client.print_results(results)

# 出力:
# Total hits: 1,234,567
# Results retrieved: 20
#
# TOP CPC CODES
#  1. A01B33/00     - 15 patents (75.00%)
#  2. C05F17/00     - 8 patents (40.00%)
# ...
```

### 高度な検索

```python
# FIコードと組み合わせ
results = client.advanced_search(
    keywords=["agriculture"],
    fi_codes=["A01B33/00"],
    max_results=50
)

# CPC ランキングのみ取得
ranking = client.get_cpc_ranking(
    query="agriculture",
    max_results=100,
    top_k=15
)

for cpc in ranking['cpc_ranking']:
    print(f"{cpc['cpc_code']}: {cpc['count']} patents")
```

### PDF ダウンロード

```python
# 検索してPDFダウンロード
results = client.simple_search("agriculture", max_results=5)

for patent in results['patents'][:3]:
    pdf_path = client.download_pdf(
        patent['patent_number'],
        output_dir="pdfs"
    )
    print(f"Downloaded: {pdf_path}")
```

## 📚 サンプルコード実行

10個のサンプル例を用意しています：

```bash
python3 google_patents_client_examples.py
```

利用可能なサンプル：
1. Simple Keyword Search
2. Advanced Query with Operators
3. Search with FI Codes
4. Search with CPC Codes
5. CPC Code Ranking
6. Get Patent Numbers Only
7. Download PDFs
8. NEAR Operator
9. Complex Boolean Query
10. Japanese Language Search

## 🔍 検索クエリの例

### 基本検索

| クエリ | 説明 |
|--------|------|
| `agriculture` | "agriculture" を含む |
| `"precision agriculture"` | 完全一致フレーズ |
| `農業 AND 土壌` | 日本語検索 |

### 論理演算子

| クエリ | 説明 |
|--------|------|
| `agriculture AND soil` | 両方を含む |
| `agriculture OR farming` | いずれかを含む |
| `agriculture NOT pesticide` | "pesticide"を含まない |
| `(agriculture OR farming) AND soil` | 組み合わせ |

### 近接検索

| クエリ | 説明 |
|--------|------|
| `agriculture NEAR crop` | 近くに出現 |
| `agriculture NEAR/5 crop` | 5単語以内 |
| `"smart farming" NEAR/10 sensor` | フレーズと組み合わせ |

### 分類コード検索

| クエリ | 説明 |
|--------|------|
| `FI:A01B33/00` | FI分類 |
| `IPC:A01B` | IPC分類 |
| `CPC:A01B33/00` | CPC分類 |
| `agriculture AND FI:A01B33/00` | キーワード + 分類 |

## ⚙️ 出力フォーマット

### 検索結果

```json
{
  "query": "agriculture",
  "total_hits": 1234567,
  "results_count": 20,
  "patent_numbers": ["US1234567A", "US2345678B", ...],
  "cpc_ranking": [
    {
      "cpc_code": "A01B33/00",
      "count": 15,
      "percentage": 75.0
    }
  ],
  "patents": [
    {
      "patent_number": "US1234567A",
      "title": "Agricultural soil working implement",
      "assignee": "Company ABC",
      "publication_date": "2023-01-15",
      "cpc_codes": ["A01B33/00", "A01B49/02"],
      "url": "https://patents.google.com/patent/US1234567A",
      "pdf_url": "https://patents.google.com/patent/US1234567A/en?download"
    }
  ]
}
```

## 🎯 要求仕様の実装状況

| 要求 | 実装状況 | エンドポイント |
|------|----------|----------------|
| ✅ キーワード検索 | 完了 | `/search/simple` |
| ✅ FI検索 | 完了 | `/search` (POST) |
| ✅ OR/AND/NOT/NEAR | 完了 | クエリ文字列で指定 |
| ✅ 検索ヒット総件数 | 完了 | `total_hits` フィールド |
| ✅ CPCランキング | 完了 | `/cpc_ranking` |
| ✅ 特許番号一覧 | 完了 | `patent_numbers` フィールド |
| ✅ PDF ダウンロード | 完了 | `/download/{patent_number}` |

## ⚠️ 重要な注意事項

### パフォーマンス

- **処理時間**: 1回の検索に 10-30秒かかります（ブラウザ起動含む）
- **推奨max_results**: 100件以下（大量取得は時間がかかります）

### レート制限

Google Patentsは大量のリクエストを制限する場合があります：

- **推奨**: リクエスト間に 2-5秒の待機時間
- **注意**: 短時間に大量リクエストするとIPブロックの可能性

### 使用上の注意

```python
# 良い例: 適切な待機時間
for query in queries:
    results = client.simple_search(query, max_results=20)
    time.sleep(3)  # 3秒待機

# 悪い例: 連続リクエスト（推奨しません）
for query in queries:
    results = client.simple_search(query, max_results=100)
    # 待機なし → IPブロックのリスク
```

## 🐛 トラブルシューティング

### 問題: ChromeDriver エラー

```
selenium.common.exceptions.WebDriverException: 'chromedriver' executable needs to be in PATH
```

**解決策**:
```bash
# macOS
brew install chromedriver

# Ubuntu
sudo apt-get install chromium-chromedriver
```

### 問題: タイムアウト

```
TimeoutException: Timeout waiting for search results
```

**解決策**: スクレイパーのタイムアウトを延長
```python
scraper = GooglePatentsScraper(headless=True, timeout=60)
```

### 問題: メモリ不足

**解決策**: ヘッドレスモードを使用（既定で有効）
```python
scraper = GooglePatentsScraper(headless=True)  # メモリ節約
```

## 📊 使用例：完全なワークフロー

```python
from google_patents_client_examples import GooglePatentsClient
import time

# 1. クライアント初期化
client = GooglePatentsClient()

# 2. 検索実行
results = client.simple_search(
    "agriculture AND soil",
    max_results=50
)

# 3. 結果確認
print(f"Total hits: {results['total_hits']:,}")
print(f"Retrieved: {results['results_count']}")

# 4. CPC ランキング表示
print("\nTop CPC Codes:")
for i, cpc in enumerate(results['cpc_ranking'][:10], 1):
    print(f"{i}. {cpc['cpc_code']}: {cpc['count']} patents")

# 5. 特許番号取得
patent_numbers = results['patent_numbers']
print(f"\nPatent numbers: {', '.join(patent_numbers[:10])}")

# 6. PDFダウンロード（最初の3件）
print("\nDownloading PDFs...")
for patent in results['patents'][:3]:
    pdf_path = client.download_pdf(patent['patent_number'])
    print(f"  Downloaded: {pdf_path}")
    time.sleep(2)  # 待機

print("\n✓ Complete!")
```

## 📖 詳細ドキュメント

詳細な説明は以下を参照：
- `GOOGLE_PATENTS_README.md` - 完全なドキュメント
- `google_patents_client_examples.py` - 10個のサンプルコード
- `test_google_patents_basic.py` - テストコード

## 🆘 サポート

問題が発生した場合：
1. `GOOGLE_PATENTS_README.md` のトラブルシューティングセクションを確認
2. テストを実行: `python3 test_google_patents_basic.py`
3. GitHubでissueを作成

## 📝 ライセンス

このコードは教育・研究目的で提供されています。Google Patents の利用規約を遵守してください。
