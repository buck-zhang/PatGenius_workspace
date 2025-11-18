#!/usr/bin/env python3
"""
特許構成要件分割・検索システムのテストスクリプト
Test Script for Patent Component Analysis and Search System
"""

import os
import json
import logging
from pathlib import Path

from patent_component_analyzer import (
    GeminiClient, PatentComponentAnalyzer, KeywordGenerator,
    ClassificationFinder, save_components_to_json
)
from patent_search_engine import PatentAnalysisWorkflow


# ============================================================================
# Configuration
# ============================================================================

SERVICE_ACCOUNT_PATH = "/Volumes/T7/patgenius/zhang_opera/ttdc-in-house-dev-3e07247326cb.json"
OPENSEARCH_API_URL = "http://localhost:8000"
GOOGLE_PATENTS_API_URL = "http://localhost:8001"
GEMINI_MODEL_NAME = "gemini-2.5-pro"

# テスト用の特許データ
TEST_PATENT_DATA = """
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


# ============================================================================
# Logging Setup
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Test Functions
# ============================================================================

def test_component_analysis():
    """構成要件分割のテスト"""
    logger.info("\n" + "=" * 80)
    logger.info("Test 1: Component Analysis")
    logger.info("=" * 80)

    # Geminiクライアント初期化（Vertex AI経由）
    gemini_client = GeminiClient(
        service_account_path=SERVICE_ACCOUNT_PATH,
        project_id="ttdc-in-house-dev",
        location="us-central1",
        model_name=GEMINI_MODEL_NAME
    )

    # 構成要件分析
    analyzer = PatentComponentAnalyzer(gemini_client)
    components = analyzer.analyze_patent_components(TEST_PATENT_DATA)

    # 結果表示
    logger.info(f"\n抽出された構成要素数: {len(components)}")

    for comp in components:
        logger.info(f"\n構成要素番号: {comp.構成要素番号}")
        logger.info(f"  構成要素: {comp.構成要素}")
        logger.info(f"  簡単説明: {comp.構成要素の簡単説明}")
        logger.info(f"  重要度: {comp.構成要素の重要度}")

    # JSON保存
    save_components_to_json(components, "test_components.json")
    logger.info("\n構成要素をtest_components.jsonに保存しました")

    return components


def test_keyword_generation(components):
    """キーワード生成のテスト"""
    logger.info("\n" + "=" * 80)
    logger.info("Test 2: Keyword Generation")
    logger.info("=" * 80)

    # Geminiクライアント初期化（Vertex AI経由）
    gemini_client = GeminiClient(
        service_account_path=SERVICE_ACCOUNT_PATH,
        project_id="ttdc-in-house-dev",
        location="us-central1",
        model_name=GEMINI_MODEL_NAME
    )

    # キーワード生成
    keyword_generator = KeywordGenerator(gemini_client)

    keywords_list = []
    for comp in components[:2]:  # 最初の2つの構成要素でテスト
        logger.info(f"\n構成要素 {comp.構成要素番号} のキーワード生成中...")
        keywords = keyword_generator.generate_keywords(comp)
        keywords_list.append(keywords)

        logger.info(f"  基本キーワード: {keywords.基本キーワード}")
        logger.info(f"  同義語類義語: {keywords.同義語類義語}")
        logger.info(f"  上位概念: {keywords.上位概念}")
        logger.info(f"  下位概念: {keywords.下位概念}")
        logger.info(f"  機能キーワード: {keywords.機能キーワード}")
        logger.info(f"  専門用語: {keywords.専門用語}")

    return keywords_list


def test_classification_finding(components, keywords_list):
    """特許分類コード特定のテスト"""
    logger.info("\n" + "=" * 80)
    logger.info("Test 3: Classification Finding")
    logger.info("=" * 80)

    # 分類コードファインダー初期化
    classification_finder = ClassificationFinder(
        opensearch_api_url=OPENSEARCH_API_URL,
        google_patents_api_url=GOOGLE_PATENTS_API_URL
    )

    classifications_list = []
    for comp, keywords in zip(components[:2], keywords_list):
        logger.info(f"\n構成要素 {comp.構成要素番号} の分類コード特定中...")
        try:
            classification = classification_finder.find_classifications(comp, keywords)
            classifications_list.append(classification)

            logger.info(f"  FI分類: {classification.FI分類}")
            logger.info(f"  IPC分類: {classification.IPC分類}")
            logger.info(f"  予備検索CPC: {classification.予備検索CPC}")
            logger.info(f"  最終分類: {classification.最終分類}")

        except Exception as e:
            logger.error(f"分類コード特定に失敗: {e}")
            # ダミーデータで続行
            from patent_component_analyzer import ComponentClassification
            classification = ComponentClassification(
                構成要素番号=comp.構成要素番号,
                FI分類=["B60W30/18"],
                IPC分類=["B60W30/00"],
                CPC分類=["B60W30/18"],
                予備検索CPC=["B60W30/18"],
                最終分類=["B60W30/18"]
            )
            classifications_list.append(classification)

    return classifications_list


def test_full_workflow():
    """フルワークフローのテスト"""
    logger.info("\n" + "=" * 80)
    logger.info("Test 4: Full Workflow")
    logger.info("=" * 80)

    # Geminiクライアント初期化（Vertex AI経由）
    gemini_client = GeminiClient(
        service_account_path=SERVICE_ACCOUNT_PATH,
        project_id="ttdc-in-house-dev",
        location="us-central1",
        model_name=GEMINI_MODEL_NAME
    )

    # ワークフロー初期化
    workflow = PatentAnalysisWorkflow(
        gemini_client=gemini_client,
        opensearch_api_url=OPENSEARCH_API_URL,
        google_patents_api_url=GOOGLE_PATENTS_API_URL
    )

    # 分析・検索実行
    try:
        result = workflow.analyze_and_search(TEST_PATENT_DATA)

        # 結果表示
        logger.info(f"\n構成要素数: {len(result['components'])}")
        logger.info(f"検索ヒット件数: {result['total_hits']}")
        logger.info(f"取得特許数: {len(result['patents'])}")
        logger.info(f"検索式: {result['search_query'][:200]}...")

        # 結果をJSON保存
        with open("test_full_workflow_result.json", 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info("\n結果をtest_full_workflow_result.jsonに保存しました")

    except Exception as e:
        logger.error(f"ワークフロー実行に失敗: {e}", exc_info=True)


# ============================================================================
# Main
# ============================================================================

def main():
    """メイン処理"""
    logger.info("=" * 80)
    logger.info("特許構成要件分割・検索システム テスト")
    logger.info("Patent Component Analysis and Search System - Tests")
    logger.info("=" * 80)

    try:
        # Test 1: 構成要件分割
        components = test_component_analysis()

        # Test 2: キーワード生成
        keywords_list = test_keyword_generation(components)

        # Test 3: 分類コード特定（APIが利用可能な場合）
        classifications_list = test_classification_finding(components, keywords_list)

        # Test 4: フルワークフロー（オプション）
        # test_full_workflow()

        logger.info("\n" + "=" * 80)
        logger.info("全てのテストが完了しました")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"\nテスト中にエラーが発生しました: {e}", exc_info=True)


if __name__ == "__main__":
    main()
