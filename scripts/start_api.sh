#!/bin/bash

# PatGenius API 起動スクリプト

echo "🚀 PatGenius Search API を起動しています..."

# 仮想環境確認（存在する場合は有効化）
if [ -d "venv" ]; then
    echo "📦 仮想環境を有効化..."
    source venv/bin/activate
fi

# 依存関係インストール
echo "📚 依存関係をインストール..."
pip install -r api_requirements.txt

# OpenSearchの起動確認
echo "🔍 OpenSearch接続確認..."
if ! curl -s http://localhost:9200/_cluster/health > /dev/null; then
    echo "❌ OpenSearchが起動していません。"
    echo "   docker-compose up -d を実行してOpenSearchを起動してください。"
    exit 1
fi

echo "✅ OpenSearch接続確認完了"

# APIサーバー起動
echo "🌐 APIサーバーを起動..."
echo ""
echo "📖 利用可能なエンドポイント:"
echo "   - API Root: http://localhost:8000/"
echo "   - Swagger UI: http://localhost:8000/docs"
echo "   - ReDoc: http://localhost:8000/redoc"
echo "   - Health Check: http://localhost:8000/health"
echo ""
echo "⏹️  停止するには Ctrl+C を押してください"
echo ""

# uvicornでAPIサーバー起動
python -m uvicorn patent_search_api:app --host 0.0.0.0 --port 8000 --reload