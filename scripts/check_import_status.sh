#!/bin/bash

# Check Patent Classification Data Import Status
# インポート状況確認

echo "=========================================================================="
echo "Patent Classification Data Import Status"
echo "特許分類データインポート状況"
echo "=========================================================================="
echo ""

# Check if OpenSearch is running
if curl -s http://localhost:9200/_cluster/health > /dev/null 2>&1; then
    echo "✓ OpenSearch: Running"
else
    echo "✗ OpenSearch: Not running"
    exit 1
fi

# Check if API is running
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ API: Running"
else
    echo "✗ API: Not running"
    exit 1
fi

echo ""
echo "=========================================================================="
echo "Index Statistics"
echo "インデックス統計"
echo "=========================================================================="
echo ""

# Check IPC index
IPC_COUNT=$(curl -s http://localhost:9200/patent_classification_ipc/_count 2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin).get('count', 0))" 2>/dev/null || echo "0")
echo "IPC Records: $IPC_COUNT"

# Check CPC index
CPC_COUNT=$(curl -s http://localhost:9200/patent_classification_cpc/_count 2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin).get('count', 0))" 2>/dev/null || echo "0")
echo "CPC Records: $CPC_COUNT"

# Check FI index
FI_COUNT=$(curl -s http://localhost:9200/patent_classification_fi/_count 2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin).get('count', 0))" 2>/dev/null || echo "0")
echo "FI Records: $FI_COUNT"

TOTAL=$((IPC_COUNT + CPC_COUNT + FI_COUNT))
echo ""
echo "Total Records: $TOTAL"

echo ""
echo "=========================================================================="
echo "Container Status"
echo "コンテナ状態"
echo "=========================================================================="
echo ""

docker-compose ps

echo ""
echo "=========================================================================="
echo "Recent Import Log (last 20 lines)"
echo "最近のインポートログ（最新20行）"
echo "=========================================================================="
echo ""

docker logs patent_classification_api 2>&1 | grep -E "(Reading|Generating|Indexing|Batches|completed|Error)" | tail -20

echo ""
echo "=========================================================================="
echo ""
echo "To monitor import in real-time, run:"
echo "リアルタイム監視を行うには以下を実行："
echo "  ./monitor_import.sh"
echo ""
echo "To check detailed logs:"
echo "詳細ログ確認："
echo "  docker logs -f patent_classification_api"
echo ""
