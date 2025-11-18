#!/usr/bin/env python3
"""
JP2014007731A 特許の完全なワークフロー実行
構成要件分割 → キーワード生成 → 分類コード特定 → 検索実行
"""

import os
import sys
import json
import logging
import requests
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.patent_component_analyzer import create_ai_client
from src.core.patent_search_engine import PatentAnalysisWorkflow
from config.config_loader import config

# ============================================================================
# Configuration
# ============================================================================

# 設定ファイルから読み込み
vertex_ai_config = config.get_vertex_ai_config()
api_endpoints = config.get_api_endpoints()
search_params = config.get_search_parameters()

SERVICE_ACCOUNT_PATH = vertex_ai_config.get("service_account_path", "./cred/ttdc-in-house-dev-2a46b2cf52e6.json")
OPENSEARCH_API_URL = api_endpoints.get("opensearch", "http://localhost:8000")
GOOGLE_PATENTS_API_URL = api_endpoints.get("google_patents", "http://localhost:8001")
PATENT_NUMBER = "JP2014007731A"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Functions
# ============================================================================

def get_patent_pdf(patent_number: str, output_dir: str = "./patents_pdf") -> str:
    """
    Google Patents APIで特許PDFを取得

    Args:
        patent_number: 特許番号
        output_dir: 出力ディレクトリ

    Returns:
        PDFファイルのパス
    """
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f"{patent_number}.pdf")

    # 既に存在する場合はそのまま使用
    if os.path.exists(pdf_path):
        logger.info(f"Using existing PDF: {pdf_path}")
        return pdf_path

    try:
        logger.info(f"Downloading PDF for {patent_number}...")

        # PDFダウンロードAPIを使用
        response = requests.post(
            f"{GOOGLE_PATENTS_API_URL}/download_pdf",
            json={"patent_number": patent_number},
            timeout=120
        )
        response.raise_for_status()

        data = response.json()

        if "local_path" in data:
            # サーバー側でダウンロード済み
            server_path = data["local_path"]
            logger.info(f"PDF downloaded on server: {server_path}")

            # サーバーからファイルを取得してローカルに保存
            # 注: この実装では、サーバーとクライアントが同じマシンと仮定
            import shutil
            if os.path.exists(server_path):
                shutil.copy(server_path, pdf_path)
                logger.info(f"PDF copied to: {pdf_path}")
                return pdf_path
            else:
                logger.warning(f"Server path not accessible: {server_path}")

        logger.error(f"Failed to download PDF for {patent_number}")
        return None

    except Exception as e:
        logger.error(f"Failed to get patent PDF: {e}")
        return None


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    PDFからテキストを抽出

    Args:
        pdf_path: PDFファイルパス

    Returns:
        抽出されたテキスト
    """
    try:
        import PyPDF2

        with open(pdf_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text = ""

            logger.info(f"Extracting text from {len(pdf_reader.pages)} pages...")

            for page in pdf_reader.pages:
                text += page.extract_text()

            logger.info(f"Total text extracted: {len(text)} characters")
            return text

    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {e}")
        raise


def main():
    """メイン処理"""

    logger.info("=" * 80)
    logger.info(f"特許構成要件分割・検索システム - 完全ワークフロー実行")
    logger.info(f"特許番号: {PATENT_NUMBER}")
    logger.info("=" * 80)

    # ステップ1: PDFを取得
    logger.info("\n[Step 1] PDF取得中...")

    pdf_path = get_patent_pdf(PATENT_NUMBER)

    if not pdf_path or not os.path.exists(pdf_path):
        logger.error("PDF取得に失敗しました")
        logger.info("\nNote: Google Patents APIが http://localhost:8001 で起動していることを確認してください")
        return 1

    logger.info(f"✓ PDF取得完了: {pdf_path}")

    # ステップ2: PDFからテキストを抽出
    logger.info("\n[Step 2] テキスト抽出中...")

    try:
        patent_text = extract_text_from_pdf(pdf_path)
        logger.info(f"✓ テキスト抽出完了: {len(patent_text)} 文字")

        # プレビュー
        logger.info("\nText preview (first 300 characters):")
        logger.info("-" * 80)
        logger.info(patent_text[:300])
        logger.info("-" * 80)

    except Exception as e:
        logger.error(f"テキスト抽出に失敗: {e}")
        return 1

    # ステップ3: AIクライアント初期化（設定ファイルから自動選択）
    component_analyzer_config = config.get_component_analyzer_config()
    provider = component_analyzer_config.get("provider", "anthropic")
    model_name = component_analyzer_config.get("model_name", "claude-sonnet-4-5@20250929")

    logger.info(f"\n[Step 3] AI Client 初期化中...")
    logger.info(f"Provider: {provider}")
    logger.info(f"Model: {model_name}")

    try:
        # 設定ファイルから自動的にAIクライアントを作成
        ai_client = create_ai_client()
        logger.info("✓ AI client initialized")

    except Exception as e:
        logger.error(f"Gemini初期化に失敗: {e}")
        logger.info(f"\nNote: サービスアカウントファイルが存在することを確認してください: {SERVICE_ACCOUNT_PATH}")
        return 1

    # ステップ4: 完全なワークフロー実行（設定ファイルから検索パラメータを読み込み）
    logger.info("\n[Step 4] 特許構成要件分割・検索システム実行中...")
    logger.info("このプロセスには数分かかります...")

    # 設定ファイルから検索パラメータを読み込み
    recall_mode = search_params.get("recall_mode", True)
    target_min_hits = search_params.get("target_min_hits", 10)
    target_max_hits = search_params.get("target_max_hits", 300)
    max_iterations = search_params.get("max_iterations", 12)
    max_ai_attempts = search_params.get("max_ai_attempts", 10)
    initial_importance_threshold = search_params.get("initial_importance_threshold", 0.0)
    target_patent_number = search_params.get("target_patent_number", None)

    logger.info("\n検索パラメータ設定:")
    logger.info(f"  - recall_mode: {recall_mode}（リコール重視モード）")
    logger.info(f"  - importance_threshold: {initial_importance_threshold}（全構成要素を使用）")
    logger.info(f"  - target_hits: {target_min_hits}-{target_max_hits}（この範囲で検索を停止）")
    logger.info(f"  - max_iterations: {max_iterations}（最大調整回数）")
    logger.info(f"  - max_ai_attempts: {max_ai_attempts}（AI生成クエリの最大試行回数）")
    if target_patent_number:
        logger.info(f"  - target_patent: {target_patent_number}（自動検証）")
    logger.info("")

    try:
        workflow = PatentAnalysisWorkflow(
            gemini_client=ai_client,
            opensearch_api_url=OPENSEARCH_API_URL,
            google_patents_api_url=GOOGLE_PATENTS_API_URL,
            recall_mode=recall_mode,
            target_min_hits=target_min_hits,
            target_max_hits=target_max_hits,
            max_iterations=max_iterations,
            max_ai_attempts=max_ai_attempts,
            target_patent_number=target_patent_number
        )

        # 分析と検索を実行
        result = workflow.analyze_and_search(patent_text)

        logger.info("\n" + "=" * 80)
        logger.info("ワークフロー実行完了")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"ワークフロー実行に失敗: {e}", exc_info=True)
        return 1

    # ステップ5: 結果を保存
    logger.info("\n[Step 5] 結果を保存中...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = "./output"
    os.makedirs(output_dir, exist_ok=True)

    # JSON結果を保存
    json_output_path = os.path.join(output_dir, f"{PATENT_NUMBER}_result_{timestamp}.json")

    with open(json_output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info(f"✓ 結果をJSONファイルに保存: {json_output_path}")

    # 読みやすいサマリーを保存
    summary_output_path = os.path.join(output_dir, f"{PATENT_NUMBER}_summary_{timestamp}.txt")

    with open(summary_output_path, 'w', encoding='utf-8') as f:
        f.write(f"特許番号: {PATENT_NUMBER}\n")
        f.write(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"構成要素数: {len(result['components'])}\n")
        f.write(f"検索ヒット件数: {result['total_hits']}\n")
        f.write(f"取得特許数: {len(result['patents'])}\n\n")

        # 処理時間情報を追加
        if 'processing_times' in result:
            times = result['processing_times']
            f.write("処理時間:\n")
            f.write("=" * 80 + "\n")
            f.write(f"  Step 1 (構成要素分析): {times['step1_component_analysis_seconds']:.2f} 秒\n")
            f.write(f"  Step 2 (キーワード生成): {times['step2_keyword_generation_seconds']:.2f} 秒\n")
            f.write(f"  Step 3 (分類コード特定): {times['step3_classification_finding_seconds']:.2f} 秒\n")
            f.write(f"  Step 4 (検索実行): {times['step4_search_execution_seconds']:.2f} 秒\n")
            f.write(f"  合計処理時間: {times['total_workflow_seconds']:.2f} 秒 ({times['total_workflow_seconds']/60:.2f} 分)\n")
            f.write("\n")

        f.write("最終検索式:\n")
        f.write("-" * 80 + "\n")
        f.write(result['search_query'] + "\n")
        f.write("-" * 80 + "\n\n")

        f.write("調整履歴:\n")
        for entry in result['adjustment_history']:
            f.write(f"  {entry}\n")
        f.write("\n")

        # 各イテレーションの詳細情報を追加
        f.write("各イテレーションの詳細:\n")
        f.write("=" * 80 + "\n")
        for iteration_detail in result.get('iteration_details', []):
            f.write(f"\nIteration {iteration_detail['iteration']}:\n")
            f.write(f"  調整タイプ: {iteration_detail['adjustment_type']}\n")
            f.write(f"  キーワード拡張レベル: {iteration_detail['keyword_expansion_level']}\n")
            f.write(f"  重要度閾値: {iteration_detail['importance_threshold']}\n")
            f.write(f"  ヒット件数: {iteration_detail['total_hits']}\n")
            f.write(f"  検索式 (最初の300文字):\n")
            f.write(f"    {iteration_detail['search_query'][:300]}...\n")
            f.write("-" * 80 + "\n")
        f.write("\n")

        f.write("構成要素一覧（詳細）:\n")
        f.write("=" * 80 + "\n")
        for i, comp in enumerate(result['components'], 1):
            # 対応するキーワードと分類コードを取得
            comp_id = comp['構成要素番号']
            keywords = next((kw for kw in result['keywords'] if kw['構成要素番号'] == comp_id), None)
            classification = next((cls for cls in result['classifications'] if cls['構成要素番号'] == comp_id), None)

            f.write(f"\n{i}. [{comp['構成要素番号']}] {comp['構成要素']}\n")
            f.write(f"   簡単説明: {comp['構成要素の簡単説明']}\n")
            f.write(f"   重要度: {comp['構成要素の重要度']}\n")
            f.write(f"   サポート箇所: {comp.get('構成要素のサポート箇所', 'N/A')}\n")

            # キーワード情報を追加
            if keywords:
                f.write(f"\n   【キーワード】\n")
                f.write(f"   一次検索キーワード: {', '.join(keywords['一次検索キーワード'])}\n")
                f.write(f"   検索範囲拡大キーワード: {', '.join(keywords['検索範囲拡大キーワード'])}\n")
                f.write(f"   検索範囲縮小キーワード: {', '.join(keywords['検索範囲縮小キーワード'])}\n")

            # 分類コード情報を追加
            if classification:
                f.write(f"\n   【分類コード】\n")
                f.write(f"   一次特定最終CPC: {', '.join(classification['一次特定最終CPC'])}\n")
                f.write(f"   検索範囲拡大最終CPC: {', '.join(classification['検索範囲拡大最終CPC'])}\n")
                f.write(f"   検索範囲縮小最終CPC: {', '.join(classification['検索範囲縮小最終CPC'])}\n")
                if classification.get('IPC分類'):
                    f.write(f"   IPC分類: {', '.join(classification['IPC分類'])}\n")

            f.write("\n" + "-" * 80 + "\n")

        f.write("\n検索結果特許一覧:\n")
        f.write("=" * 80 + "\n")
        for i, patent in enumerate(result['patents'][:10], 1):  # 最初の10件
            f.write(f"\n{i}. {patent.get('title', 'N/A')}\n")
            f.write(f"   番号: {patent.get('publication_number', 'N/A')}\n")
            f.write(f"   出願人: {patent.get('applicant', 'N/A')}\n")
            f.write(f"   公開日: {patent.get('publication_date', 'N/A')}\n")
            f.write("\n" + "-" * 80 + "\n")

    logger.info(f"✓ サマリーをテキストファイルに保存: {summary_output_path}")

    # 結果サマリー表示
    logger.info("\n" + "=" * 80)
    logger.info("実行結果サマリー")
    logger.info("=" * 80)
    logger.info(f"構成要素数: {len(result['components'])}")
    logger.info(f"検索ヒット件数: {result['total_hits']}")
    logger.info(f"取得特許数: {len(result['patents'])}")
    logger.info(f"\n検索式 (最初の500文字):")
    logger.info(result['search_query'][:500])

    logger.info("\n調整履歴:")
    for entry in result['adjustment_history']:
        logger.info(f"  {entry}")

    # JP2011171723A検証
    logger.info("\n" + "=" * 80)
    logger.info("ターゲット特許検証（JP2011171723A）")
    logger.info("=" * 80)

    target_patent = "JP2011171723A"
    patent_numbers = [p.get("patent_number", "") for p in result['patents']]

    if target_patent in patent_numbers:
        logger.info(f"✅ {target_patent} が検索結果に含まれています！")
        logger.info("")
        logger.info("改善成功: リコールモードにより、ターゲット特許が検索結果に含まれました。")
    else:
        logger.info(f"❌ {target_patent} は検索結果に含まれていません。")
        logger.info("")
        logger.info("検索結果の特許リスト（最初の20件）:")
        for i, patent_num in enumerate(patent_numbers[:20], 1):
            logger.info(f"  {i:2d}. {patent_num}")

    logger.info("\n" + "=" * 80)
    logger.info("出力ファイル")
    logger.info("=" * 80)
    logger.info(f"1. PDF: {pdf_path}")
    logger.info(f"2. JSON結果: {json_output_path}")
    logger.info(f"3. サマリー: {summary_output_path}")
    logger.info("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
