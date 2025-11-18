#!/usr/bin/env python3
"""
既存の分析結果を使って特許検索のみを実行するスクリプト
"""

import json
import logging
import sys
import requests
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def build_search_query_from_components(components):
    """構成要件から検索式を構築"""
    # FIコードを収集
    fi_codes = []
    for comp in components:
        if 'fi_codes' in comp and comp['fi_codes']:
            fi_codes.extend(comp['fi_codes'][:2])  # 各構成要素から上位2つ

    # 重複を削除して上位5つに絞る
    fi_codes = list(dict.fromkeys(fi_codes))[:5]

    # キーワードを収集
    keywords = []
    for comp in components:
        if 'keywords' in comp and comp['keywords']:
            if isinstance(comp['keywords'], dict):
                if 'core' in comp['keywords']:
                    keywords.extend(comp['keywords']['core'][:3])
            elif isinstance(comp['keywords'], list):
                keywords.extend(comp['keywords'][:3])

    # 重複を削除して上位20個に絞る
    keywords = list(dict.fromkeys(keywords))[:20]

    # FIコードをクリーンアップ
    cleaned_fi_codes = []
    for fi in fi_codes:
        cleaned = fi.replace("\\", "").replace(" ", "").strip()
        if cleaned:
            cleaned_fi_codes.append(f"FI:{cleaned}")

    # 検索式を構築
    if cleaned_fi_codes and keywords:
        fi_part = " OR ".join(cleaned_fi_codes)
        keyword_part = " OR ".join([f'"{kw}"' for kw in keywords])
        query = f"(({fi_part}) AND ({keyword_part}))"
    elif cleaned_fi_codes:
        query = " OR ".join(cleaned_fi_codes)
    elif keywords:
        query = " OR ".join([f'"{kw}"' for kw in keywords])
    else:
        query = ""

    return query


def main():
    """Load existing analysis results and run search only"""

    # Load existing analysis results
    result_file = "./output/JP2014007731A_result_20251111_142303.json"
    api_url = "http://localhost:8001/search"

    logger.info("="*80)
    logger.info("特許検索実行（既存分析結果使用）")
    logger.info("="*80)

    try:
        with open(result_file, 'r', encoding='utf-8') as f:
            existing_result = json.load(f)

        logger.info(f"✓ 既存分析結果を読み込み: {result_file}")
        logger.info(f"  構成要素数: {len(existing_result['components'])}")

        # Use existing search query from the analysis result
        logger.info("\n検索式を取得中...")
        search_query = existing_result.get('search_query', '')

        if not search_query:
            logger.info("既存の検索式が見つからないため、再構築します...")
            search_query = build_search_query_from_components(existing_result['components'])

        logger.info(f"✓ 検索式取得完了（{len(search_query)}文字）")
        logger.info(f"  検索式: {search_query[:200]}...")

        # Execute search
        logger.info("\n特許検索を実行中...")
        logger.info("このプロセスには数分かかる場合があります...")

        search_payload = {
            "advanced_query": search_query,
            "max_results": 100
        }

        response = requests.post(api_url, json=search_payload, timeout=300)
        response.raise_for_status()
        search_result = response.json()

        logger.info(f"\n検索完了!")
        logger.info(f"  検索ヒット件数: {search_result['total_hits']}")
        logger.info(f"  取得特許数: {len(search_result.get('patents', []))}")

        # Update existing result with search results
        existing_result.update({
            'search_query': search_result.get('search_query', search_query),
            'total_hits': search_result.get('total_hits', 0),
            'patents': search_result.get('patents', []),
            'cpc_ranking': search_result.get('cpc_ranking', []),
            'patent_numbers': search_result.get('patent_numbers', [])
        })

        # Add query adjustment history if present
        if 'query_adjustment_history' in search_result:
            existing_result['query_adjustment_history'] = search_result['query_adjustment_history']

        # Save updated results
        output_json = "./output/JP2014007731A_search_result.json"
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(existing_result, f, ensure_ascii=False, indent=2)

        logger.info(f"\n✓ 検索結果を保存: {output_json}")

        # Display first few patents
        if existing_result.get('patents'):
            logger.info("\n取得特許（最初の5件）:")
            logger.info("="*80)
            for i, patent in enumerate(existing_result['patents'][:5], 1):
                logger.info(f"\n{i}. {patent.get('patent_number', 'N/A')}")
                logger.info(f"   タイトル: {patent.get('title', 'N/A')[:100]}")
                logger.info(f"   出願人: {patent.get('assignee', 'N/A')}")
                logger.info(f"   公開日: {patent.get('publication_date', 'N/A')}")
                logger.info(f"   URL: {patent.get('url', 'N/A')}")

        # Display CPC ranking
        if existing_result.get('cpc_ranking'):
            logger.info("\n\nCPCコードランキング（トップ10）:")
            logger.info("="*80)
            for i, cpc_data in enumerate(existing_result['cpc_ranking'][:10], 1):
                logger.info(f"{i:2d}. {cpc_data['cpc_code']:20s} : {cpc_data['count']:3d}件 ({cpc_data['percentage']:5.1f}%)")

        logger.info("\n"+"="*80)
        logger.info("検索完了")
        logger.info("="*80)

        return 0

    except FileNotFoundError:
        logger.error(f"分析結果ファイルが見つかりません: {result_file}")
        logger.error("先に構成要件分析を実行してください")
        return 1
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
