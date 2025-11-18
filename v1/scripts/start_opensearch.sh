#!/bin/bash

# OpenSearch Quick Start Script
# OpenSearch クイックスタートスクリプト

set -e

echo "======================================================================"
echo "OpenSearch Quick Start"
echo "OpenSearch クイックスタート"
echo "======================================================================"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker first."
    echo "エラー: Dockerが起動していません。Dockerを起動してください。"
    echo ""
    echo "To start Docker:"
    echo "Dockerを起動するには："
    echo "  - macOS: Open Docker Desktop application"
    echo "  - Linux: sudo systemctl start docker"
    exit 1
fi

echo "✓ Docker is running"
echo "✓ Dockerが起動しています"
echo ""

# Start OpenSearch container
echo "Starting OpenSearch container..."
echo "OpenSearchコンテナを起動中..."
docker-compose -f docker/docker-compose.yml up opensearch -d

# Wait for OpenSearch to be ready
echo ""
echo "Waiting for OpenSearch to be ready..."
echo "OpenSearchの起動を待機中..."
sleep 10

# Check OpenSearch health
echo "Checking OpenSearch health..."
for i in {1..10}; do
    if curl -s http://localhost:9200/_cluster/health > /dev/null 2>&1; then
        echo ""
        echo "======================================================================"
        echo "✓ OpenSearch is ready!"
        echo "✓ OpenSearchが準備完了しました！"
        echo "======================================================================"
        echo ""
        echo "OpenSearch is now running at:"
        echo "OpenSearchが起動しました："
        echo "  - http://localhost:9200"
        echo ""
        echo "To check cluster health:"
        echo "クラスターの状態を確認するには："
        echo "  curl http://localhost:9200/_cluster/health?pretty"
        echo ""
        echo "To stop OpenSearch:"
        echo "OpenSearchを停止するには："
        echo "  docker-compose -f docker/docker-compose.yml stop opensearch"
        echo ""
        exit 0
    fi

    if [ $i -eq 10 ]; then
        echo ""
        echo "Error: OpenSearch is not responding"
        echo "エラー: OpenSearchが応答しません"
        echo ""
        echo "Please check logs with:"
        echo "ログを確認してください："
        echo "  docker-compose -f docker/docker-compose.yml logs opensearch"
        exit 1
    fi

    echo "Waiting... (attempt $i/10)"
    sleep 5
done
