#!/usr/bin/env python3
"""
特許構成要件分割・検索システム実行スクリプト
Patent Component Analysis and Search - Main Execution Script

使用方法:
    python run_patent_analysis.py --input <特許データファイル> --output <出力ディレクトリ>
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

from patent_component_analyzer import GeminiClient
from patent_search_engine import PatentAnalysisWorkflow


# ============================================================================
# Configuration
# ============================================================================

# API設定
DEFAULT_SERVICE_ACCOUNT_PATH = "/Volumes/T7/patgenius/zhang_opera/ttdc-in-house-dev-3e07247326cb.json"
DEFAULT_OPENSEARCH_API_URL = "http://localhost:8000"
DEFAULT_GOOGLE_PATENTS_API_URL = "http://localhost:8001"

# Geminiモデル設定
GEMINI_MODEL_NAME = "gemini-2.5-pro"


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging(output_dir: str, verbose: bool = False):
    """ロギング設定"""
    log_level = logging.DEBUG if verbose else logging.INFO

    # ログファイル
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(output_dir, f"patent_analysis_{timestamp}.log")

    # ロギング設定
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return log_file


# ============================================================================
# File Readers
# ============================================================================

def read_patent_file(file_path: str) -> str:
    """
    特許ファイルを読み込む（PDF/XML/TXT対応）

    Args:
        file_path: ファイルパス

    Returns:
        特許データ（テキスト）
    """
    file_ext = Path(file_path).suffix.lower()

    if file_ext == '.txt':
        # テキストファイル
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    elif file_ext == '.xml':
        # XMLファイル
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    elif file_ext == '.pdf':
        # PDFファイル（テキスト抽出が必要）
        try:
            import PyPDF2
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text()
                return text
        except ImportError:
            logging.error("PyPDF2 is required for PDF files. Install: pip install PyPDF2")
            raise
        except Exception as e:
            logging.error(f"Failed to read PDF file: {e}")
            raise

    else:
        raise ValueError(f"Unsupported file format: {file_ext}")


# ============================================================================
# Main Function
# ============================================================================

def main():
    """メイン処理"""

    # コマンドライン引数のパース
    parser = argparse.ArgumentParser(
        description="特許構成要件分割・検索システム"
    )

    parser.add_argument(
        '--input', '-i',
        type=str,
        required=True,
        help='入力特許ファイル（PDF/XML/TXT）'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        default='./output',
        help='出力ディレクトリ（デフォルト: ./output）'
    )

    parser.add_argument(
        '--service-account',
        type=str,
        default=DEFAULT_SERVICE_ACCOUNT_PATH,
        help=f'Gemini APIサービスアカウントJSONパス（デフォルト: {DEFAULT_SERVICE_ACCOUNT_PATH}）'
    )

    parser.add_argument(
        '--opensearch-api',
        type=str,
        default=DEFAULT_OPENSEARCH_API_URL,
        help=f'OpenSearch API URL（デフォルト: {DEFAULT_OPENSEARCH_API_URL}）'
    )

    parser.add_argument(
        '--google-patents-api',
        type=str,
        default=DEFAULT_GOOGLE_PATENTS_API_URL,
        help=f'Google Patents API URL（デフォルト: {DEFAULT_GOOGLE_PATENTS_API_URL}）'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='詳細ログを出力'
    )

    args = parser.parse_args()

    # 出力ディレクトリを作成
    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)

    # ロギング設定
    log_file = setup_logging(output_dir, args.verbose)
    logger = logging.getLogger(__name__)

    logger.info("=" * 80)
    logger.info("特許構成要件分割・検索システム")
    logger.info("Patent Component Analysis and Search System")
    logger.info("=" * 80)

    try:
        # 入力ファイルの確認
        if not os.path.exists(args.input):
            raise FileNotFoundError(f"Input file not found: {args.input}")

        logger.info(f"Input file: {args.input}")
        logger.info(f"Output directory: {output_dir}")
        logger.info(f"Service account: {args.service_account}")
        logger.info(f"OpenSearch API: {args.opensearch_api}")
        logger.info(f"Google Patents API: {args.google_patents_api}")

        # 特許ファイルを読み込み
        logger.info("\nReading patent file...")
        patent_data = read_patent_file(args.input)
        logger.info(f"Patent data length: {len(patent_data)} characters")

        # Geminiクライアントの初期化
        logger.info("\nInitializing Gemini client (Vertex AI)...")
        gemini_client = GeminiClient(
            service_account_path=args.service_account,
            project_id="ttdc-in-house-dev",
            location="us-central1",
            model_name=GEMINI_MODEL_NAME
        )

        # ワークフローの初期化
        logger.info("Initializing workflow...")
        workflow = PatentAnalysisWorkflow(
            gemini_client=gemini_client,
            opensearch_api_url=args.opensearch_api,
            google_patents_api_url=args.google_patents_api
        )

        # 分析・検索を実行
        logger.info("\nStarting analysis and search...")
        result = workflow.analyze_and_search(patent_data)

        # 結果を保存
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = os.path.join(output_dir, f"result_{timestamp}.json")

        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"\nResults saved to: {result_file}")

        # サマリーを表示
        logger.info("\n" + "=" * 80)
        logger.info("分析・検索結果サマリー")
        logger.info("=" * 80)
        logger.info(f"構成要素数: {len(result['components'])}")
        logger.info(f"検索ヒット件数: {result['total_hits']}")
        logger.info(f"取得特許数: {len(result['patents'])}")
        logger.info(f"検索式: {result['search_query'][:200]}...")

        logger.info("\n調整履歴:")
        for history in result['adjustment_history']:
            logger.info(f"  {history}")

        logger.info("\nCPCランキング (上位5件):")
        for i, cpc in enumerate(result['cpc_ranking'][:5], 1):
            logger.info(f"  {i}. {cpc.get('cpc_code', 'N/A')} - {cpc.get('count', 0)}件 ({cpc.get('percentage', 0):.1f}%)")

        logger.info("\n" + "=" * 80)
        logger.info("処理が正常に完了しました")
        logger.info(f"ログファイル: {log_file}")
        logger.info(f"結果ファイル: {result_file}")
        logger.info("=" * 80)

        return 0

    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("エラーが発生しました")
        logger.error("=" * 80)
        logger.error(f"Error: {e}", exc_info=True)
        logger.error(f"ログファイル: {log_file}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
