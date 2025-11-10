#!/bin/bash

# Monitor Patent Classification Data Import
# インポート進捗をリアルタイム監視

echo "=========================================================================="
echo "Patent Classification Data Import Monitor"
echo "特許分類データインポート進捗モニター"
echo "=========================================================================="
echo ""
echo "Press Ctrl+C to stop monitoring (monitoring only, import continues)"
echo "Ctrl+Cで監視を停止（インポートは継続されます）"
echo ""
echo "=========================================================================="
echo ""

# Get container name
CONTAINER_NAME="patent_classification_api"

# Check if container is running
if ! docker ps | grep -q $CONTAINER_NAME; then
    echo "Error: Container $CONTAINER_NAME is not running"
    echo "エラー: コンテナ $CONTAINER_NAME が起動していません"
    exit 1
fi

# Monitor the logs
docker logs -f $CONTAINER_NAME 2>&1 | grep --line-buffered -E "(Reading|Generating|Indexing|Importing|completed|error|Error|Batch|files|records)"
