#!/bin/bash

# GCP Ubuntu Server Deployment Script
# For Patent Search System (Classification RAG + Google Patents Scraper)

set -e

echo "=========================================================================="
echo "Patent Search System - GCP Ubuntu Deployment"
echo "=========================================================================="
echo ""

# Configuration
PROJECT_DIR="/opt/patent-search"
DATA_DIR="/opt/patent-search/data_20250812"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root or with sudo"
    exit 1
fi

print_status "Starting deployment..."

# Step 1: Update system
echo ""
echo "Step 1: Updating system packages..."
apt-get update
apt-get upgrade -y
print_status "System updated"

# Step 2: Install Docker
echo ""
echo "Step 2: Installing Docker..."
if ! command -v docker &> /dev/null; then
    # Install Docker dependencies
    apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release

    # Add Docker GPG key
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

    # Add Docker repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Install Docker
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    print_status "Docker installed"
else
    print_status "Docker already installed"
fi

# Step 3: Install Docker Compose
echo ""
echo "Step 3: Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    print_status "Docker Compose installed"
else
    print_status "Docker Compose already installed"
fi

# Verify installations
DOCKER_VERSION=$(docker --version)
COMPOSE_VERSION=$(docker-compose --version)
print_status "Docker: $DOCKER_VERSION"
print_status "Docker Compose: $COMPOSE_VERSION"

# Step 4: Configure firewall
echo ""
echo "Step 4: Configuring firewall..."
if command -v ufw &> /dev/null; then
    ufw allow 22/tcp    # SSH
    ufw allow 80/tcp    # HTTP
    ufw allow 443/tcp   # HTTPS
    ufw allow 8000/tcp  # Classification API
    ufw allow 8001/tcp  # Google Patents API
    ufw allow 9200/tcp  # OpenSearch
    ufw allow 5601/tcp  # OpenSearch Dashboards

    # Enable UFW if not already enabled
    echo "y" | ufw enable || true

    print_status "Firewall configured"
else
    print_warning "UFW not found, skipping firewall configuration"
fi

# Step 5: Create project directory
echo ""
echo "Step 5: Setting up project directory..."
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

print_status "Project directory created: $PROJECT_DIR"

# Step 6: Install system dependencies for Chrome
echo ""
echo "Step 6: Installing Chrome dependencies..."
apt-get install -y \
    wget \
    gnupg \
    unzip \
    libgconf-2-4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libgbm-dev \
    libnss3-dev \
    libxss-dev \
    libasound2

print_status "Chrome dependencies installed"

# Step 7: Set system limits for OpenSearch
echo ""
echo "Step 7: Configuring system limits for OpenSearch..."

# Set vm.max_map_count
sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" >> /etc/sysctl.conf

# Set file descriptors
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

print_status "System limits configured"

# Step 8: Create directories
echo ""
echo "Step 8: Creating required directories..."
mkdir -p config
mkdir -p downloads
mkdir -p logs

print_status "Directories created"

# Step 9: Display next steps
echo ""
echo "=========================================================================="
echo "Installation Complete!"
echo "=========================================================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Upload your project files to: $PROJECT_DIR"
echo "   - docker-compose.gcp.yml"
echo "   - Dockerfile"
echo "   - Dockerfile.google-patents"
echo "   - All Python files"
echo "   - config/ directory"
echo "   - data_20250812/ directory (if you have classification data)"
echo ""
echo "2. Navigate to project directory:"
echo "   cd $PROJECT_DIR"
echo ""
echo "3. Build and start services:"
echo "   docker-compose -f docker-compose.gcp.yml up -d"
echo ""
echo "4. Check service status:"
echo "   docker-compose -f docker-compose.gcp.yml ps"
echo ""
echo "5. View logs:"
echo "   docker-compose -f docker-compose.gcp.yml logs -f"
echo ""
echo "6. Import classification data (if needed):"
echo "   docker-compose -f docker-compose.gcp.yml exec classification-api \\"
echo "     python import_classification_data.py --host opensearch --port 9200"
echo ""
echo "API Endpoints will be available at:"
echo "  - Classification API: http://YOUR_SERVER_IP:8000"
echo "  - Google Patents API:  http://YOUR_SERVER_IP:8001"
echo "  - OpenSearch:          http://YOUR_SERVER_IP:9200"
echo "  - Dashboards:          http://YOUR_SERVER_IP:5601"
echo ""
echo "=========================================================================="
echo ""

print_status "Deployment script completed successfully!"
