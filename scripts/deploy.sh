#!/bin/bash

# PatGenius Docker デプロイスクリプト

set -e  # エラー時に停止

# 色付きログ用の関数
log_info() {
    echo -e "\033[32m[INFO]\033[0m $1"
}

log_warn() {
    echo -e "\033[33m[WARN]\033[0m $1"
}

log_error() {
    echo -e "\033[31m[ERROR]\033[0m $1"
}

# ヘルプ表示
show_help() {
    cat << EOF
PatGenius Docker デプロイスクリプト

使用方法:
    $0 [COMMAND] [OPTIONS]

コマンド:
    dev         開発環境で起動 (既存のdocker-compose.yml使用)
    prod        本番環境で起動 (フル構成)
    import      データインポートのみ実行
    stop        全サービス停止
    clean       全データ削除 (注意: データが失われます)
    logs        ログ表示
    status      サービス状態確認
    test        APIテスト実行

オプション:
    -h, --help      このヘルプを表示
    -v, --verbose   詳細ログ表示
    --no-build      イメージをビルドしない

例:
    $0 dev                # 開発環境で起動
    $0 prod --no-build   # 本番環境で起動 (ビルドスキップ)
    $0 import            # データインポート実行
    $0 logs patgenius-api # APIサービスのログ表示

EOF
}

# Docker Composeファイルの選択
get_compose_file() {
    case "$1" in
        "dev")
            echo "docker-compose.yml"
            ;;
        "prod")
            echo "docker-compose.production.yml"
            ;;
        *)
            echo "docker-compose.yml"
            ;;
    esac
}

# 前提条件チェック
check_prerequisites() {
    log_info "前提条件をチェック中..."
    
    # Docker確認
    if ! command -v docker &> /dev/null; then
        log_error "Dockerがインストールされていません"
        exit 1
    fi
    
    # Docker Compose確認
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Composeがインストールされていません"
        exit 1
    fi
    
    # 必要ファイル確認
    required_files=("patent_search_api.py" "api_requirements.txt" "Dockerfile")
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "必要ファイルが見つかりません: $file"
            exit 1
        fi
    done
    
    log_info "前提条件チェック完了"
}

# 開発環境起動
start_dev() {
    local compose_file=$(get_compose_file "dev")
    log_info "開発環境を起動中..."
    
    if [[ "$NO_BUILD" != "true" ]]; then
        log_info "FastAPI Dockerイメージをビルド中..."
        docker build -t patgenius-api:latest .
    fi
    
    log_info "OpenSearchとDashboardsを起動中..."
    docker-compose -f "$compose_file" up -d opensearch opensearch-dashboards
    
    # OpenSearchの起動待ち
    log_info "OpenSearchの起動を待機中..."
    timeout=300
    while [[ $timeout -gt 0 ]]; do
        if curl -s http://localhost:9200/_cluster/health >/dev/null 2>&1; then
            log_info "OpenSearch起動完了"
            break
        fi
        sleep 5
        ((timeout-=5))
    done
    
    if [[ $timeout -le 0 ]]; then
        log_error "OpenSearchの起動がタイムアウトしました"
        exit 1
    fi
    
    log_info "FastAPI サービスを起動中..."
    docker run -d \
        --name patgenius-api \
        --network zhang_opera_default \
        -p 8000:8000 \
        -e OPENSEARCH_URL=http://opensearch:9200 \
        --restart unless-stopped \
        patgenius-api:latest
    
    log_info "開発環境起動完了!"
    log_info "API: http://localhost:8000/docs"
    log_info "Dashboards: http://localhost:5601"
}

# 本番環境起動
start_prod() {
    local compose_file=$(get_compose_file "prod")
    log_info "本番環境を起動中..."
    
    # 環境ファイル確認
    if [[ ! -f ".env" ]] && [[ -f ".env.example" ]]; then
        log_warn ".envファイルが見つかりません。.env.exampleからコピーしています..."
        cp .env.example .env
    fi
    
    # 静的ファイルディレクトリ作成
    mkdir -p static
    cp search_demo.html static/ 2>/dev/null || true
    cp api_examples.md static/ 2>/dev/null || true
    
    if [[ "$NO_BUILD" != "true" ]]; then
        log_info "本番環境用イメージをビルド中..."
        docker-compose -f "$compose_file" build
    fi
    
    log_info "本番環境サービスを起動中..."
    docker-compose -f "$compose_file" --profile production up -d
    
    log_info "本番環境起動完了!"
    log_info "API: http://localhost/api/docs"
    log_info "検索デモ: http://localhost/demo"
    log_info "Dashboards: http://localhost/dashboards"
}

# データインポート実行
run_import() {
    local compose_file=$(get_compose_file "prod")
    log_info "データインポートを実行中..."
    
    # source_dataディレクトリ確認
    if [[ ! -d "source_data" ]]; then
        log_error "source_dataディレクトリが見つかりません"
        log_info "特許XMLファイルをsource_dataディレクトリに配置してください"
        exit 1
    fi
    
    # OpenSearchが起動していることを確認
    if ! curl -s http://localhost:9200/_cluster/health >/dev/null 2>&1; then
        log_error "OpenSearchが起動していません。まず環境を起動してください。"
        exit 1
    fi
    
    docker-compose -f "$compose_file" --profile import up patgenius-importer
    
    log_info "データインポート完了!"
}

# サービス停止
stop_services() {
    log_info "全サービスを停止中..."
    
    # 個別コンテナの停止
    docker stop patgenius-api 2>/dev/null || true
    docker rm patgenius-api 2>/dev/null || true
    
    # Docker Composeサービスの停止
    docker-compose -f docker-compose.yml down 2>/dev/null || true
    docker-compose -f docker-compose.production.yml down 2>/dev/null || true
    
    log_info "全サービス停止完了"
}

# データクリーンアップ
clean_data() {
    log_warn "この操作により全データが削除されます。続行しますか? (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log_info "データをクリーンアップ中..."
        
        stop_services
        
        # ボリュームとイメージの削除
        docker-compose -f docker-compose.yml down -v 2>/dev/null || true
        docker-compose -f docker-compose.production.yml down -v 2>/dev/null || true
        
        # カスタムイメージの削除
        docker rmi patgenius-api:latest 2>/dev/null || true
        
        log_info "クリーンアップ完了"
    else
        log_info "キャンセルされました"
    fi
}

# ログ表示
show_logs() {
    local service="$1"
    if [[ -n "$service" ]]; then
        log_info "$service のログを表示中..."
        docker logs -f "$service" 2>/dev/null || \
        docker-compose logs -f "$service" 2>/dev/null || \
        log_error "サービス '$service' が見つかりません"
    else
        log_info "全サービスのログを表示中..."
        docker-compose logs -f
    fi
}

# サービス状態確認
show_status() {
    log_info "サービス状態を確認中..."
    
    echo "=== Dockerコンテナ状態 ==="
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    echo -e "\n=== サービス接続テスト ==="
    
    # OpenSearch
    if curl -s http://localhost:9200/_cluster/health >/dev/null 2>&1; then
        echo "✅ OpenSearch: 正常"
    else
        echo "❌ OpenSearch: 接続不可"
    fi
    
    # API
    if curl -s http://localhost:8000/health >/dev/null 2>&1; then
        echo "✅ PatGenius API: 正常"
    else
        echo "❌ PatGenius API: 接続不可"
    fi
    
    # Dashboards
    if curl -s http://localhost:5601/api/status >/dev/null 2>&1; then
        echo "✅ OpenSearch Dashboards: 正常"
    else
        echo "❌ OpenSearch Dashboards: 接続不可"
    fi
}

# APIテスト実行
run_tests() {
    log_info "APIテストを実行中..."
    
    if [[ -f "test_api.py" ]]; then
        python3 test_api.py
    else
        log_error "test_api.py が見つかりません"
        exit 1
    fi
}

# メイン処理
main() {
    local command="$1"
    shift || true
    
    # オプション解析
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--verbose)
                set -x
                shift
                ;;
            --no-build)
                NO_BUILD=true
                shift
                ;;
            *)
                # その他の引数（ログ表示のサービス名など）
                EXTRA_ARG="$1"
                shift
                ;;
        esac
    done
    
    # 前提条件チェック
    check_prerequisites
    
    # コマンド実行
    case "$command" in
        "dev")
            start_dev
            ;;
        "prod")
            start_prod
            ;;
        "import")
            run_import
            ;;
        "stop")
            stop_services
            ;;
        "clean")
            clean_data
            ;;
        "logs")
            show_logs "$EXTRA_ARG"
            ;;
        "status")
            show_status
            ;;
        "test")
            run_tests
            ;;
        "")
            log_error "コマンドが指定されていません"
            show_help
            exit 1
            ;;
        *)
            log_error "不明なコマンド: $command"
            show_help
            exit 1
            ;;
    esac
}

# スクリプト実行
main "$@"