#!/usr/bin/env python3
"""
特許構成要件分割・検索システム - 完全ワークフローデモ
サンプル特許データ（自動運転車両の制御システム）を使用した実行
"""

import os
import sys
import json
import logging
from datetime import datetime

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.patent_component_analyzer import GeminiClient
from src.core.patent_search_engine import PatentAnalysisWorkflow

# ============================================================================
# Configuration
# ============================================================================

SERVICE_ACCOUNT_PATH = "/Users/ttdc-user/Desktop/patgenius/zhang_opera/ttdc-in-house-dev-3e07247326cb.json"
OPENSEARCH_API_URL = "http://localhost:8000"
GOOGLE_PATENTS_API_URL = "http://localhost:8001"

# サンプル特許データ
SAMPLE_PATENT_DATA = """
【発明の名称】自動運転車両の制御システム

【技術分野】
本発明は、自動運転車両の制御システムに関し、特に走行環境を認識して最適な走行経路を決定する技術に関する。

【背景技術】
近年、自動運転技術の開発が進められている。従来の自動運転システムでは、カメラやLiDARなどのセンサーで周囲環境を認識し、
予め設定された走行経路に従って車両を制御していた。しかし、従来技術では、突発的な障害物や交通状況の変化に対して
柔軟に対応することが困難であった。

【発明が解決しようとする課題】
本発明は、上記の問題を解決するため、走行環境の変化に応じて動的に走行経路を変更できる自動運転車両の制御システムを提供する。

【課題を解決するための手段】
本発明の自動運転車両の制御システムは、以下の構成を有する：
1. 車両周囲の環境情報を取得する複数のセンサー
2. センサーから取得した環境情報を解析する画像処理部
3. 解析された環境情報に基づいて走行経路を決定する経路決定部
4. 決定された走行経路に従って車両を制御する車両制御部

【発明の効果】
本発明により、走行環境の変化に応じて動的に走行経路を変更できるため、より安全で快適な自動運転が実現できる。

【特許請求の範囲】
【請求項1】
車両周囲の環境情報を取得する複数のセンサーと、
前記センサーから取得した環境情報を解析する画像処理部と、
解析された環境情報に基づいて走行経路を決定する経路決定部と、
決定された走行経路に従って車両を制御する車両制御部と、
を備える自動運転車両の制御システム。

【請求項2】
前記センサーは、カメラ、LiDAR、及びレーダーを含む、請求項1に記載の自動運転車両の制御システム。

【請求項3】
前記経路決定部は、機械学習モデルを用いて最適な走行経路を決定する、請求項1または2に記載の自動運転車両の制御システム。
"""

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Main Function
# ============================================================================

def main():
    """メイン処理"""

    logger.info("=" * 80)
    logger.info("特許構成要件分割・検索システム - 完全ワークフローデモ")
    logger.info("サンプル特許: 自動運転車両の制御システム")
    logger.info("=" * 80)

    # ステップ1: Geminiクライアント初期化
    logger.info("\n[Step 1] Gemini 2.5 Pro (Vertex AI) 初期化中...")

    try:
        gemini_client = GeminiClient(
            service_account_path=SERVICE_ACCOUNT_PATH,
            project_id="ttdc-in-house-dev",
            location="us-central1",
            model_name="gemini-2.5-pro"
        )
        logger.info("✓ Gemini client initialized")

    except Exception as e:
        logger.error(f"Gemini初期化に失敗: {e}")
        logger.info(f"\nNote: サービスアカウントファイルが存在することを確認してください: {SERVICE_ACCOUNT_PATH}")
        return 1

    # ステップ2: 完全なワークフロー実行
    logger.info("\n[Step 2] 特許構成要件分割・検索システム実行中...")
    logger.info("このプロセスには数分かかります...")
    logger.info(f"\n処理フロー:")
    logger.info("  1. 構成要件分解 (Gemini 2.5 Pro)")
    logger.info("  2. 各構成要素の一次検索キーワード生成 (Gemini 2.5 Pro)")
    logger.info("  3. 各構成要素のCPC/FI特定")
    logger.info("     - OpenSearch APIでCPC/FI検索")
    logger.info("     - Google Patents APIで予備検索 (上位3個のCPC取得)")
    logger.info("     - CPC→FI変換")
    logger.info("     - 交差処理 (OpenSearch ∩ 予備検索)")
    logger.info("  4. 検索実行 (動的範囲調整: 目標10-50件)")
    logger.info("  5. FI+CPC OR条件検索\n")

    try:
        workflow = PatentAnalysisWorkflow(
            gemini_client=gemini_client,
            opensearch_api_url=OPENSEARCH_API_URL,
            google_patents_api_url=GOOGLE_PATENTS_API_URL
        )

        # 分析と検索を実行
        result = workflow.analyze_and_search(SAMPLE_PATENT_DATA)

        logger.info("\n" + "=" * 80)
        logger.info("ワークフロー実行完了")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"ワークフロー実行に失敗: {e}", exc_info=True)
        return 1

    # ステップ3: 結果を保存
    logger.info("\n[Step 3] 結果を保存中...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = "./output"
    os.makedirs(output_dir, exist_ok=True)

    # JSON結果を保存
    json_output_path = os.path.join(output_dir, f"autonomous_vehicle_result_{timestamp}.json")

    with open(json_output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info(f"✓ 結果をJSONファイルに保存: {json_output_path}")

    # 読みやすいサマリーを保存
    summary_output_path = os.path.join(output_dir, f"autonomous_vehicle_summary_{timestamp}.txt")

    with open(summary_output_path, 'w', encoding='utf-8') as f:
        f.write("特許構成要件分割・検索システム - 実行結果\n")
        f.write(f"サンプル特許: 自動運転車両の制御システム\n")
        f.write(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"構成要素数: {len(result['components'])}\n")
        f.write(f"検索ヒット件数: {result['total_hits']}\n")
        f.write(f"取得特許数: {len(result['patents'])}\n\n")

        f.write("検索式:\n")
        f.write("-" * 80 + "\n")
        f.write(result['search_query'] + "\n")
        f.write("-" * 80 + "\n\n")

        f.write("調整履歴:\n")
        for entry in result['adjustment_history']:
            f.write(f"  {entry}\n")
        f.write("\n")

        f.write("構成要素一覧:\n")
        f.write("=" * 80 + "\n")
        for i, comp in enumerate(result['components'], 1):
            f.write(f"\n{i}. [{comp['構成要素番号']}] {comp['構成要素']}\n")
            f.write(f"   簡単説明: {comp['構成要素の簡単説明']}\n")
            f.write(f"   重要度: {comp['構成要素の重要度']}\n")
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

    logger.info("\n構成要素:")
    for i, comp in enumerate(result['components'], 1):
        logger.info(f"  {i}. [{comp['構成要素番号']}] {comp['構成要素'][:50]}...")

    logger.info(f"\n検索式 (最初の500文字):")
    logger.info(result['search_query'][:500])

    logger.info("\n調整履歴:")
    for entry in result['adjustment_history']:
        logger.info(f"  {entry}")

    logger.info("\n検索結果特許 (上位5件):")
    for i, patent in enumerate(result['patents'][:5], 1):
        logger.info(f"  {i}. {patent.get('title', 'N/A')}")
        logger.info(f"     {patent.get('publication_number', 'N/A')} - {patent.get('applicant', 'N/A')}")

    logger.info("\n" + "=" * 80)
    logger.info("出力ファイル")
    logger.info("=" * 80)
    logger.info(f"1. JSON結果: {json_output_path}")
    logger.info(f"2. サマリー: {summary_output_path}")
    logger.info("=" * 80)

    logger.info("\n✓ 完全ワークフロー実行完了！")

    return 0


if __name__ == "__main__":
    sys.exit(main())
