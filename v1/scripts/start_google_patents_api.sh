#!/bin/bash

# Start Google Patents Search API Server

echo "=========================================================================="
echo "Google Patents Search API Server"
echo "=========================================================================="
echo ""

# Check if required dependencies are installed
echo "Checking dependencies..."

if ! python3 -c "import selenium" 2>/dev/null; then
    echo "✗ Selenium not installed"
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
else
    echo "✓ Selenium installed"
fi

if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "✗ FastAPI not installed"
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
else
    echo "✓ FastAPI installed"
fi

echo ""
echo "=========================================================================="
echo "Starting API Server on http://localhost:8001"
echo "=========================================================================="
echo ""
echo "Available endpoints:"
echo "  - GET  /                          : API information"
echo "  - GET  /health                    : Health check"
echo "  - GET  /search/simple             : Simple keyword search"
echo "  - POST /search                    : Advanced search"
echo "  - GET  /cpc_ranking               : Get CPC ranking"
echo "  - GET  /patent_numbers            : Get patent numbers"
echo "  - GET  /download/{patent_number}  : Download PDF"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""
echo "=========================================================================="
echo ""

# Start the API server
python3 -m uvicorn src.api.google_patents_api:app --host 0.0.0.0 --port 8001
