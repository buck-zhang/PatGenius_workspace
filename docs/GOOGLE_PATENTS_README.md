# Google Patents Search API

Google Patents (https://patents.google.com/) に対する Web スクレイピング API

## 概要

このAPIは、Google Patentsウェブサイトをスクレイピングして、特許検索結果を取得します。

### 主な機能

- **高度な検索クエリ対応**: AND, OR, NOT, NEAR演算子をサポート
- **分類コード検索**: FI, IPC, CPC分類コードによる検索
- **検索結果取得**:
  - 検索ヒット総件数
  - 特許番号一覧
  - CPC分類コードランキング
  - 特許PDF ダウンロード

## システム構成

```
src/core/google_patents_scraper.py       # スクレイパー本体
src/api/google_patents_api.py            # FastAPI エンドポイント
examples/google_patents_client_examples.py  # Pythonクライアント例
```

## 必要な依存関係

```bash
pip install selenium==4.16.0 beautifulsoup4==4.12.3 lxml==5.1.0 webdriver-manager==4.0.1 requests==2.31.0
```

## セットアップ

### 1. Chrome/Chromium のインストール

Selenium は Chrome WebDriver を使用します。Chrome または Chromium がインストールされている必要があります。

**macOS**:
```bash
brew install --cask google-chrome
```

**Ubuntu/Debian**:
```bash
sudo apt-get update
sudo apt-get install -y chromium-browser
```

**Docker** (推奨):
```bash
# Chromeがプリインストールされたコンテナを使用
docker run -it --rm selenium/standalone-chrome
```

### 2. 依存関係のインストール

```bash
pip install -r requirements.txt
```

## 使い方

### オプション1: スクレイパーを直接使用

```python
from google_patents_scraper import GooglePatentsScraper

# スクレイパー初期化
scraper = GooglePatentsScraper(headless=True)

try:
    # 検索実行
    results = scraper.search("agriculture", max_results=20)

    print(f"Total hits: {results['total_hits']}")
    print(f"Results: {results['results_count']}")

    # CPC ランキング
    for cpc in results['cpc_ranking'][:10]:
        print(f"{cpc['cpc_code']}: {cpc['count']} patents")

    # 特許情報
    for patent in results['patents']:
        print(f"{patent['patent_number']}: {patent['title']}")

finally:
    scraper.close()
```

### オプション2: API サーバー経由

#### サーバー起動

```bash
python3 google_patents_api.py
```

APIサーバーは `http://localhost:8001` で起動します。

#### APIエンドポイント

##### 1. 簡単なキーワード検索

```bash
curl "http://localhost:8001/search/simple?q=agriculture&max_results=20"
```

##### 2. 高度な検索（POST）

```bash
curl -X POST "http://localhost:8001/search" \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": ["agriculture", "soil"],
    "fi_codes": ["A01B33/00"],
    "max_results": 50
  }'
```

##### 3. AND/OR/NOT 演算子を使った検索

```bash
# AND検索
curl "http://localhost:8001/search/simple?q=agriculture%20AND%20soil&max_results=20"

# OR検索
curl "http://localhost:8001/search/simple?q=agriculture%20OR%20farming&max_results=20"

# NOT検索
curl "http://localhost:8001/search/simple?q=agriculture%20NOT%20pesticide&max_results=20"

# NEAR検索（近接検索）
curl "http://localhost:8001/search/simple?q=agriculture%20NEAR/5%20crop&max_results=20"

# 複合クエリ
curl "http://localhost:8001/search/simple?q=(agriculture%20OR%20farming)%20AND%20soil%20NOT%20pesticide&max_results=20"
```

##### 4. CPC ランキング取得

```bash
curl "http://localhost:8001/cpc_ranking?q=agriculture&max_results=100&top_k=15"
```

##### 5. 特許番号のみ取得

```bash
curl "http://localhost:8001/patent_numbers?q=agriculture&max_results=100"
```

##### 6. PDF ダウンロード

```bash
curl "http://localhost:8001/download/US1234567A" --output patent.pdf
```

### オプション3: Python クライアント使用

```python
from google_patents_client_examples import GooglePatentsClient

client = GooglePatentsClient(base_url="http://localhost:8001")

# 簡単な検索
results = client.simple_search("agriculture", max_results=20)

# 高度な検索
results = client.advanced_search(
    keywords=["agriculture"],
    fi_codes=["A01B33/00"],
    max_results=50
)

# CPC ランキング
ranking = client.get_cpc_ranking("agriculture", max_results=100, top_k=15)

# PDF ダウンロード
pdf_path = client.download_pdf("US1234567A", output_dir="pdfs")
```

## サンプルコード実行

10個のサンプル使用例を実行：

```bash
python3 google_patents_client_examples.py
```

## 検索クエリ例

### 基本検索

```python
# キーワード検索
query = "agriculture"

# フレーズ検索
query = '"precision agriculture"'
```

### 論理演算子

```python
# AND: すべてのキーワードを含む
query = "agriculture AND soil"

# OR: いずれかのキーワードを含む
query = "agriculture OR farming"

# NOT: 特定のキーワードを除外
query = "agriculture NOT pesticide"
```

### 近接検索 (NEAR)

```python
# agriculture と crop が5単語以内
query = "agriculture NEAR/5 crop"

# デフォルトの近接度（通常10単語）
query = "agriculture NEAR crop"
```

### 複合クエリ

```python
# 複数の演算子を組み合わせ
query = "(agriculture OR farming) AND (soil OR crop) NOT (pesticide OR herbicide)"

# 近接検索と論理演算子
query = '("precision agriculture" OR "smart farming") AND (sensor NEAR/3 data)'
```

### 分類コード検索

```python
# FI コード
query = "FI:A01B33/00"

# IPC コード
query = "IPC:A01B33/00"

# CPC コード
query = "CPC:A01B33/00"

# キーワードと組み合わせ
query = "agriculture AND FI:A01B33/00"
```

## レスポンス例

```json
{
  "query": "agriculture",
  "total_hits": 1234567,
  "results_count": 20,
  "patent_numbers": [
    "US1234567A",
    "US2345678B",
    ...
  ],
  "cpc_ranking": [
    {
      "cpc_code": "A01B33/00",
      "count": 15,
      "percentage": 75.0
    },
    ...
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
    },
    ...
  ]
}
```

## 注意事項

### 1. スクレイピングの制約

- **Rate Limiting**: Google Patents は大量のリクエストを制限する場合があります
- **IP ブロック**: 短時間に大量のリクエストを送るとIPがブロックされる可能性があります
- **robots.txt**: Google Patents の robots.txt を確認してください
- **利用規約**: Google の利用規約を遵守してください

### 2. パフォーマンス

- **処理時間**: Selenium + ブラウザ起動のため、1回の検索に 10-30秒かかります
- **メモリ使用**: Chrome WebDriver は メモリを消費します（約500MB-1GB）
- **並列処理**: 同時に複数のスクレイパーを実行すると、リソースを大量に消費します

### 3. 推奨事項

- **リクエスト間隔**: 各リクエスト間に 2-5秒の待機時間を設ける
- **最大結果数**: 1回の検索で取得する結果は 100件以下に制限
- **キャッシング**: 同じクエリの結果をキャッシュして再利用
- **ヘッドレスモード**: 本番環境では `headless=True` を使用

### 4. エラー処理

スクレイピングは以下の理由で失敗する可能性があります：

- ネットワークエラー
- タイムアウト
- HTML構造の変更（Google Patentsが更新された場合）
- レート制限/IP ブロック

## Docker での実行（推奨）

Dockerを使用すると、Chrome/ChromiumとChromeDriverが自動的にセットアップされます。

### Dockerfile 例

```dockerfile
FROM selenium/standalone-chrome:latest

USER root

# Python とアプリケーションのセットアップ
RUN apt-get update && apt-get install -y python3 python3-pip
COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY google_patents_scraper.py .
COPY google_patents_api.py .

EXPOSE 8001

CMD ["python3", "google_patents_api.py"]
```

### Docker Compose 例

```yaml
version: '3.8'

services:
  google-patents-api:
    build:
      context: .
      dockerfile: Dockerfile.google-patents
    ports:
      - "8001:8001"
    environment:
      - PYTHONUNBUFFERED=1
    volumes:
      - ./downloads:/app/downloads
```

## トラブルシューティング

### Chrome WebDriver エラー

```
selenium.common.exceptions.WebDriverException: Message: 'chromedriver' executable needs to be in PATH
```

**解決方法**: `webdriver-manager` が自動的に ChromeDriver をダウンロードしますが、失敗する場合は手動でインストール：

```bash
# macOS
brew install chromedriver

# Ubuntu
sudo apt-get install chromium-chromedriver
```

### タイムアウトエラー

```
TimeoutException: Message: Timeout waiting for search results
```

**解決方法**: タイムアウト時間を延長：

```python
scraper = GooglePatentsScraper(headless=True, timeout=60)  # 60秒に延長
```

### メモリ不足

**解決方法**: Chrome のメモリ使用を制限：

```python
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
```

## ライセンスと法的事項

このコードは教育・研究目的で提供されています。

- Google Patents の利用規約を確認してください
- robots.txt を尊重してください
- 商用利用の場合は、Google の許可が必要な場合があります
- スクレイピングによるサーバー負荷を最小限に抑えてください

## 今後の改善予定

- [ ] キャッシング機能
- [ ] レート制限の実装
- [ ] プロキシサポート
- [ ] 非同期処理（複数検索の並列実行）
- [ ] 詳細な特許情報の取得（請求項、要約など）
- [ ] 画像検索機能
- [ ] 出願人/発明者検索

## サポート

問題や質問がある場合は、GitHubでissueを作成してください。
