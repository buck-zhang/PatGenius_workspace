#!/bin/bash

# Patent Classification Search System - Quick Start Script
# 特許分類検索システム - クイックスタートスクリプト

set -e

echo "======================================================================"
echo "Patent Classification Search System - Quick Start"
echo "特許分類検索システム - クイックスタート"
echo "======================================================================"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker first."
    echo "エラー: Dockerが起動していません。Dockerを起動してください。"
    exit 1
fi

# Step 1: Start Docker containers
echo "Step 1: Starting Docker containers..."
echo "ステップ1: Dockerコンテナを起動中..."
docker-compose -f docker/docker-compose.yml up -d

# Step 2: Wait for OpenSearch to be ready
echo ""
echo "Step 2: Waiting for OpenSearch to be ready (30 seconds)..."
echo "ステップ2: OpenSearchの起動を待機中（30秒）..."
sleep 30

# Check OpenSearch health
echo "Checking OpenSearch health..."
for i in {1..10}; do
    if curl -s http://localhost:9200/_cluster/health > /dev/null 2>&1; then
        echo "✓ OpenSearch is ready!"
        echo "✓ OpenSearchが準備完了しました！"
        break
    fi

    if [ $i -eq 10 ]; then
        echo "Error: OpenSearch is not responding"
        echo "エラー: OpenSearchが応答しません"
        exit 1
    fi

    echo "Waiting... (attempt $i/10)"
    sleep 5
done

# Step 3: Import data
echo ""
echo "Step 3: Importing patent classification data..."
echo "ステップ3: 特許分類データをインポート中..."
echo "This may take 10-20 minutes depending on your system."
echo "システムによって10-20分程度かかる場合があります。"
echo ""

docker-compose -f docker/docker-compose.yml exec -T api python import_classification_data.py \
    --host opensearch \
    --port 9200 \
    --data-dir /app/data_20250812

# Step 4: Verify installation
echo ""
echo "Step 4: Verifying installation..."
echo "ステップ4: インストールを確認中..."
echo ""

# Check API health
API_HEALTH=$(curl -s http://localhost:8000/health)
echo "API Health: $API_HEALTH"
echo ""

# Check indices
echo "OpenSearch Indices:"
curl -s http://localhost:9200/_cat/indices?v | grep patent_classification
echo ""

# Completion message
echo "======================================================================"
echo "✓ Installation completed successfully!"
echo "✓ インストールが完了しました！"
echo "======================================================================"
echo ""
echo "Services are now running:"
echo "サービスが起動しました："
echo "  - API:                http://localhost:8000"
echo "  - API Documentation:  http://localhost:8000/docs"
echo "  - OpenSearch:         http://localhost:9200"
echo "  - OpenSearch Dashboards: http://localhost:5601"
echo ""
echo "To test the API, run:"
echo "APIをテストするには以下を実行してください："
echo "  python api_client_examples.py"
echo ""
echo "To stop the system:"
echo "システムを停止するには："
echo "  docker-compose -f docker/docker-compose.yml down"
echo ""
