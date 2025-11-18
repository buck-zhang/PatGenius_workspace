# GCP Ubuntu サーバーデプロイガイド

Google Cloud Platform (GCP) の Ubuntu サーバーに特許検索システムをデプロイする完全ガイド

## 📋 目次

1. [システム要件](#システム要件)
2. [GCPインスタンスのセットアップ](#gcpインスタンスのセットアップ)
3. [自動デプロイ（推奨）](#自動デプロイ推奨)
4. [手動デプロイ](#手動デプロイ)
5. [動作確認](#動作確認)
6. [トラブルシューティング](#トラブルシューティング)

## システム要件

### GCP Compute Engine インスタンス

推奨スペック：

| 項目 | 推奨値 | 最小値 |
|------|--------|--------|
| マシンタイプ | e2-standard-4 | e2-standard-2 |
| CPU | 4 vCPU | 2 vCPU |
| メモリ | 16 GB | 8 GB |
| ディスク | 100 GB SSD | 50 GB SSD |
| OS | Ubuntu 22.04 LTS | Ubuntu 20.04 LTS |

### 必要なポート

| ポート | サービス | 説明 |
|--------|----------|------|
| 22 | SSH | リモート接続 |
| 80 | HTTP | Nginx (optional) |
| 443 | HTTPS | Nginx SSL (optional) |
| 8000 | Classification API | 特許分類検索API |
| 8001 | Google Patents API | Google Patents検索API |
| 9200 | OpenSearch | 検索エンジン |
| 5601 | Dashboards | OpenSearch Dashboards |

## GCPインスタンスのセットアップ

### 1. GCPコンソールでインスタンス作成

```bash
# gcloud CLI を使用（推奨）
gcloud compute instances create patent-search-server \
  --zone=asia-northeast1-a \
  --machine-type=e2-standard-4 \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=100GB \
  --boot-disk-type=pd-ssd \
  --tags=http-server,https-server,patent-api
```

### 2. ファイアウォールルール設定

```bash
# HTTP/HTTPS
gcloud compute firewall-rules create allow-http-https \
  --allow tcp:80,tcp:443 \
  --target-tags http-server,https-server

# API ポート
gcloud compute firewall-rules create allow-patent-api \
  --allow tcp:8000,tcp:8001,tcp:9200,tcp:5601 \
  --target-tags patent-api
```

### 3. SSHでインスタンスに接続

```bash
gcloud compute ssh patent-search-server --zone=asia-northeast1-a
```

## 自動デプロイ（推奨）

### ステップ1: デプロイスクリプトのダウンロード

```bash
# ローカルからサーバーにファイルをアップロード
gcloud compute scp deploy_gcp.sh patent-search-server:~ --zone=asia-northeast1-a
```

または、サーバー上で直接作成：

```bash
# SSH接続後
sudo -i
cd /opt
git clone YOUR_REPO_URL patent-search
cd patent-search
```

### ステップ2: 自動セットアップ実行

```bash
sudo chmod +x deploy_gcp.sh
sudo ./deploy_gcp.sh
```

このスクリプトは以下を自動実行します：
- ✅ システムパッケージの更新
- ✅ Docker & Docker Compose のインストール
- ✅ ファイアウォールの設定
- ✅ Chrome/Chromium依存関係のインストール
- ✅ OpenSearch用のシステム設定
- ✅ 必要なディレクトリの作成

### ステップ3: プロジェクトファイルのアップロード

ローカルマシンから：

```bash
# プロジェクト全体をアップロード
gcloud compute scp --recurse \
  . \
  patent-search-server:/opt/patent-search \
  --zone=asia-northeast1-a \
  --exclude=".git/*" \
  --exclude="__pycache__/*" \
  --exclude="*.pyc"
```

### ステップ4: サービス起動

```bash
# サーバー上で
cd /opt/patent-search

# ビルドして起動
sudo docker-compose -f docker-compose.gcp.yml up -d --build

# ログ確認
sudo docker-compose -f docker-compose.gcp.yml logs -f
```

## 手動デプロイ

### 1. Docker インストール

```bash
# 依存関係
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# Docker GPG キー
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Docker リポジトリ
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Docker インストール
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
```

### 2. Docker Compose インストール

```bash
sudo curl -L \
  "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose

sudo chmod +x /usr/local/bin/docker-compose
```

### 3. システム設定

```bash
# OpenSearch用
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf

# ファイル記述子
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf
```

### 4. Chrome依存関係

```bash
sudo apt-get install -y \
  wget gnupg unzip \
  libgconf-2-4 libatk1.0-0 libatk-bridge2.0-0 \
  libgdk-pixbuf2.0-0 libgtk-3-0 libgbm-dev \
  libnss3-dev libxss-dev libasound2
```

### 5. プロジェクトセットアップ

```bash
sudo mkdir -p /opt/patent-search
cd /opt/patent-search

# ファイルをアップロード（gcloud scp使用）
# または git clone

sudo docker-compose -f docker-compose.gcp.yml up -d --build
```

## 動作確認

### 1. コンテナ状態確認

```bash
sudo docker-compose -f docker-compose.gcp.yml ps
```

期待される出力：
```
NAME                          STATUS    PORTS
patent_opensearch             Up        0.0.0.0:9200->9200/tcp
patent_classification_api     Up        0.0.0.0:8000->8000/tcp
google_patents_api            Up        0.0.0.0:8001->8001/tcp
patent_opensearch_dashboards  Up        0.0.0.0:5601->5601/tcp
```

### 2. ヘルスチェック

```bash
# OpenSearch
curl http://localhost:9200/_cluster/health

# Classification API
curl http://localhost:8000/health

# Google Patents API
curl http://localhost:8001/health
```

### 3. 外部からのアクセス確認

ローカルマシンから：

```bash
# YOUR_SERVER_IP を実際のIPアドレスに置き換え
export SERVER_IP=YOUR_SERVER_IP

# Classification API
curl http://$SERVER_IP:8000/health

# Google Patents API
curl http://$SERVER_IP:8001/health
```

### 4. 検索テスト

```bash
# Classification API - キーワード検索
curl "http://$SERVER_IP:8000/search/keyword?q=agriculture&top_k=5"

# Google Patents API - 簡単な検索
curl "http://$SERVER_IP:8001/search/simple?q=agriculture&max_results=5"
```

## データインポート

### 分類データのインポート

```bash
cd /opt/patent-search

# data_20250812 ディレクトリがアップロードされている場合
sudo docker-compose -f docker-compose.gcp.yml exec classification-api \
  python import_classification_data.py \
  --host opensearch \
  --port 9200 \
  --data-dir /app/data_20250812

# 進捗確認
sudo docker-compose -f docker-compose.gcp.yml logs -f classification-api
```

## サービス管理

### 起動・停止

```bash
# 起動
sudo docker-compose -f docker-compose.gcp.yml up -d

# 停止
sudo docker-compose -f docker-compose.gcp.yml down

# 再起動
sudo docker-compose -f docker-compose.gcp.yml restart

# 特定のサービスのみ再起動
sudo docker-compose -f docker-compose.gcp.yml restart google-patents-api
```

### ログ確認

```bash
# 全サービスのログ
sudo docker-compose -f docker-compose.gcp.yml logs -f

# 特定のサービス
sudo docker-compose -f docker-compose.gcp.yml logs -f google-patents-api

# 最新100行
sudo docker-compose -f docker-compose.gcp.yml logs --tail=100 classification-api
```

### リソース使用状況

```bash
# Docker stats
sudo docker stats

# ディスク使用量
sudo docker system df

# クリーンアップ（未使用のイメージ削除）
sudo docker system prune -a
```

## 自動起動設定

### Systemd サービス作成

```bash
sudo nano /etc/systemd/system/patent-search.service
```

内容：
```ini
[Unit]
Description=Patent Search System
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/patent-search
ExecStart=/usr/local/bin/docker-compose -f docker-compose.gcp.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.gcp.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

有効化：
```bash
sudo systemctl daemon-reload
sudo systemctl enable patent-search.service
sudo systemctl start patent-search.service

# 状態確認
sudo systemctl status patent-search.service
```

## トラブルシューティング

### コンテナが起動しない

```bash
# ログを確認
sudo docker-compose -f docker-compose.gcp.yml logs

# 個別コンテナの状態
sudo docker inspect patent_opensearch

# 再ビルド
sudo docker-compose -f docker-compose.gcp.yml up -d --build --force-recreate
```

### OpenSearchがメモリ不足

```bash
# docker-compose.gcp.yml のメモリ設定を調整
# OPENSEARCH_JAVA_OPTS=-Xms2g -Xmx2g → -Xms1g -Xmx1g
```

### Google Patents APIがタイムアウト

```bash
# コンテナのshm_sizeを増やす（docker-compose.gcp.yml）
# shm_size: 2gb → 4gb
```

### ポートが使用中

```bash
# 使用中のポートを確認
sudo netstat -tulpn | grep :8000

# プロセスを停止
sudo kill -9 PID
```

## バックアップ

### OpenSearchデータのバックアップ

```bash
# ボリュームのバックアップ
sudo docker run --rm \
  -v patent-search_opensearch-data:/data \
  -v $(pwd):/backup \
  ubuntu tar czf /backup/opensearch-backup-$(date +%Y%m%d).tar.gz /data
```

### 復元

```bash
# バックアップから復元
sudo docker run --rm \
  -v patent-search_opensearch-data:/data \
  -v $(pwd):/backup \
  ubuntu tar xzf /backup/opensearch-backup-YYYYMMDD.tar.gz -C /
```

## セキュリティ

### ファイアウォール設定

```bash
# 必要なポートのみ開放
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS

# APIポートは信頼できるIPからのみ
sudo ufw allow from TRUSTED_IP to any port 8000
sudo ufw allow from TRUSTED_IP to any port 8001

sudo ufw enable
```

### SSL/TLS設定（Nginx使用）

Let's Encryptで証明書取得：

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## モニタリング

### ヘルスチェックスクリプト

```bash
#!/bin/bash
# health_check.sh

curl -f http://localhost:8000/health || echo "Classification API down"
curl -f http://localhost:8001/health || echo "Google Patents API down"
curl -f http://localhost:9200/_cluster/health || echo "OpenSearch down"
```

### Cron設定

```bash
# 5分ごとにヘルスチェック
crontab -e

*/5 * * * * /opt/patent-search/health_check.sh >> /var/log/patent-health.log 2>&1
```

## パフォーマンスチューニング

### OpenSearch

```yaml
# docker-compose.gcp.yml
environment:
  - "OPENSEARCH_JAVA_OPTS=-Xms4g -Xmx4g"  # メモリを増やす
  - thread_pool.search.size=30            # 検索スレッド数
  - thread_pool.write.size=30             # 書き込みスレッド数
```

### Google Patents API

```yaml
# 並列スクレイピング用にレプリカ増加
deploy:
  replicas: 3
```

## コスト最適化

### インスタンス自動停止

開発環境では夜間停止：

```bash
# 停止（午後11時）
0 23 * * * gcloud compute instances stop patent-search-server --zone=asia-northeast1-a

# 起動（午前7時）
0 7 * * 1-5 gcloud compute instances start patent-search-server --zone=asia-northeast1-a
```

## まとめ

GCP Ubuntuサーバーへのデプロイが完了すると：

✅ 特許分類RAG検索API（ポート8000）
✅ Google Patents スクレイピングAPI（ポート8001）
✅ OpenSearch（ポート9200）
✅ OpenSearch Dashboards（ポート5601）

がすべて稼働し、外部からアクセス可能になります。

サポートが必要な場合は、ログを確認してトラブルシューティングセクションを参照してください。
