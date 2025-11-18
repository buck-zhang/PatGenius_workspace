#!/usr/bin/env python3
"""
特許構成要件分割・検索システム 使用例
Example Usage of Patent Component Analysis and Search System
"""

import json
from patent_component_analyzer import GeminiClient
from patent_search_engine import PatentAnalysisWorkflow


def example_basic_usage():
    """
    基本的な使用例
    """
    print("=" * 80)
    print("特許構成要件分割・検索システム - 基本使用例")
    print("=" * 80)

    # サービスアカウント設定
    SERVICE_ACCOUNT_PATH = "/Volumes/T7/patgenius/zhang_opera/ttdc-in-house-dev-3e07247326cb.json"
    OPENSEARCH_API_URL = "http://localhost:8000"
    GOOGLE_PATENTS_API_URL = "http://localhost:8001"

    # サンプル特許データ
    patent_data = """
【発明の名称】空飛ぶ自動車

【技術分野】
本発明は、道路と空中の両方で移動可能な車両に関する。

【課題を解決するための手段】
本発明の空飛ぶ自動車は、以下の構成を有する：
1. 地上走行用の車輪
2. 空中飛行用のプロペラまたはジェットエンジン
3. 走行モードと飛行モードを切り替える制御システム
4. 衝突回避のためのセンサーシステム

【特許請求の範囲】
【請求項1】
地上走行用の車輪と、
空中飛行用の推進装置と、
走行モードと飛行モードを切り替える制御部と、
を備える空飛ぶ自動車。
"""

    # 1. Geminiクライアントの初期化（Vertex AI経由）
    print("\n1. Geminiクライアントを初期化中（Vertex AI）...")
    gemini_client = GeminiClient(
        service_account_path=SERVICE_ACCOUNT_PATH,
        project_id="ttdc-in-house-dev",
        location="us-central1",
        model_name="gemini-2.5-pro"
    )
    print("✓ 初期化完了")

    # 2. ワークフローの初期化
    print("\n2. ワークフローを初期化中...")
    workflow = PatentAnalysisWorkflow(
        gemini_client=gemini_client,
        opensearch_api_url=OPENSEARCH_API_URL,
        google_patents_api_url=GOOGLE_PATENTS_API_URL
    )
    print("✓ 初期化完了")

    # 3. 分析・検索の実行
    print("\n3. 分析・検索を実行中...")
    print("（注意: OpenSearch APIとGoogle Patents APIが起動している必要があります）")

    try:
        result = workflow.analyze_and_search(patent_data)

        # 4. 結果の表示
        print("\n4. 結果:")
        print(f"   - 構成要素数: {len(result['components'])}")
        print(f"   - 検索ヒット件数: {result['total_hits']}")
        print(f"   - 取得特許数: {len(result['patents'])}")

        print("\n   構成要素:")
        for i, comp in enumerate(result['components'], 1):
            print(f"     {i}. [{comp['構成要素番号']}] {comp['構成要素']}")
            print(f"        重要度: {comp['構成要素の重要度']}")

        # 結果を保存
        with open("example_result.json", 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print("\n✓ 結果をexample_result.jsonに保存しました")

    except Exception as e:
        print(f"\n✗ エラーが発生しました: {e}")
        print("\n注意事項:")
        print("  - OpenSearch APIが起動していますか？ (http://localhost:8000)")
        print("  - Google Patents APIが起動していますか？ (http://localhost:8001)")
        print("  - サービスアカウントJSONファイルのパスは正しいですか？")


def example_component_analysis_only():
    """
    構成要件分割のみを実行する例
    """
    print("\n" + "=" * 80)
    print("構成要件分割のみを実行する例")
    print("=" * 80)

    from patent_component_analyzer import PatentComponentAnalyzer, save_components_to_json

    SERVICE_ACCOUNT_PATH = "/Volumes/T7/patgenius/zhang_opera/ttdc-in-house-dev-3e07247326cb.json"

    patent_data = """
【請求項1】
画像データを入力する入力部と、
入力された画像データに対して機械学習処理を行う処理部と、
処理結果を出力する出力部と、
を備える画像処理装置。
"""

    # Geminiクライアント初期化（Vertex AI経由）
    gemini_client = GeminiClient(
        service_account_path=SERVICE_ACCOUNT_PATH,
        project_id="ttdc-in-house-dev",
        location="us-central1",
        model_name="gemini-2.5-pro"
    )

    # 構成要件分析
    analyzer = PatentComponentAnalyzer(gemini_client)
    components = analyzer.analyze_patent_components(patent_data)

    # 結果表示
    print(f"\n抽出された構成要素: {len(components)}個")
    for comp in components:
        print(f"\n[{comp.構成要素番号}] {comp.構成要素}")
        print(f"  説明: {comp.構成要素の簡単説明}")
        print(f"  重要度: {comp.構成要素の重要度}")

    # JSON保存
    save_components_to_json(components, "components_only.json")
    print("\n✓ 構成要素をcomponents_only.jsonに保存しました")


def example_keyword_generation_only():
    """
    キーワード生成のみを実行する例
    """
    print("\n" + "=" * 80)
    print("キーワード生成のみを実行する例")
    print("=" * 80)

    from patent_component_analyzer import (
        ComponentElement, KeywordGenerator
    )

    SERVICE_ACCOUNT_PATH = "/Volumes/T7/patgenius/zhang_opera/ttdc-in-house-dev-3e07247326cb.json"

    # サンプル構成要素
    component = ComponentElement(
        構成要素番号="1a",
        構成要素="画像データを入力する入力部",
        構成要素のサポート箇所="【請求項1】画像データを入力する入力部と、",
        段落番号=["0001"],
        構成要素の簡単説明="画像データを受け取る入力インターフェース",
        構成要素の重要度=0.7
    )

    # Geminiクライアント初期化（Vertex AI経由）
    gemini_client = GeminiClient(
        service_account_path=SERVICE_ACCOUNT_PATH,
        project_id="ttdc-in-house-dev",
        location="us-central1",
        model_name="gemini-2.5-pro"
    )

    # キーワード生成
    keyword_generator = KeywordGenerator(gemini_client)
    keywords = keyword_generator.generate_keywords(component)

    # 結果表示
    print(f"\n構成要素: {component.構成要素}")
    print("\n生成されたキーワード:")
    print(f"  基本キーワード: {keywords.基本キーワード}")
    print(f"  同義語・類義語: {keywords.同義語類義語}")
    print(f"  上位概念: {keywords.上位概念}")
    print(f"  下位概念: {keywords.下位概念}")
    print(f"  機能キーワード: {keywords.機能キーワード}")
    print(f"  専門用語: {keywords.専門用語}")


if __name__ == "__main__":
    print("特許構成要件分割・検索システム - 使用例\n")
    print("実行する例を選択してください:")
    print("1. 基本的な使用例（フルワークフロー）")
    print("2. 構成要件分割のみ")
    print("3. キーワード生成のみ")

    choice = input("\n選択 (1-3): ").strip()

    if choice == "1":
        example_basic_usage()
    elif choice == "2":
        example_component_analysis_only()
    elif choice == "3":
        example_keyword_generation_only()
    else:
        print("無効な選択です。1-3の数字を入力してください。")
