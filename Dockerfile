# PatGenius FastAPI Dockerfile
FROM python:3.9-slim

# 作業ディレクトリを設定
WORKDIR /app

# システムパッケージの更新とクリーンアップ
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係をコピーしてインストール
COPY api_requirements.txt .
RUN pip install --no-cache-dir -r api_requirements.txt

# アプリケーションファイルをコピー
COPY patent_search_api.py .
RUN mkdir -p config
COPY config/opensearch_tags_analysis.json ./config/
COPY bulk_import_patents.py .
COPY test_api.py .
COPY search_examples.py .

# ヘルスチェック用スクリプト
RUN echo '#!/bin/bash\ncurl -f http://localhost:8000/health || exit 1' > /healthcheck.sh && \
    chmod +x /healthcheck.sh

# ポートを公開
EXPOSE 8000

# ヘルスチェック設定
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD /healthcheck.sh

# 非rootユーザーで実行
RUN useradd -m -u 1000 patgenius && chown -R patgenius:patgenius /app
USER patgenius

# アプリケーション起動
CMD ["python", "-m", "uvicorn", "patent_search_api:app", "--host", "0.0.0.0", "--port", "8000"]