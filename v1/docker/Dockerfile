FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download sentence transformer model during build
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')"

# Copy application code
COPY *.py .

# Create models directory
RUN mkdir -p /app/models

EXPOSE 8000

CMD ["uvicorn", "patent_classification_api:app", "--host", "0.0.0.0", "--port", "8000"]
