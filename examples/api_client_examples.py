"""
Patent Classification API Client Examples
サンプルコード - 特許分類検索APIの使い方

This file demonstrates how to use the Patent Classification Search API
"""

import requests
from typing import List, Dict, Any, Optional
import json


class PatentClassificationClient:
    """Client for Patent Classification Search API"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize client

        Args:
            base_url: API base URL
        """
        self.base_url = base_url.rstrip('/')

    def health_check(self) -> Dict[str, Any]:
        """
        Check API health status

        Returns:
            Health status
        """
        response = requests.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    def search_keyword(self,
                      keyword: str,
                      classification_type: str = "all",
                      top_k: int = 20) -> Dict[str, Any]:
        """
        Simple keyword search
        キーワード検索

        Args:
            keyword: Keyword to search
            classification_type: "ipc", "cpc", "fi", or "all"
            top_k: Number of results to return

        Returns:
            Search results
        """
        params = {
            "q": keyword,
            "classification_type": classification_type,
            "top_k": top_k
        }

        response = requests.get(f"{self.base_url}/search/keyword", params=params)
        response.raise_for_status()
        return response.json()

    def search_text(self,
                   text: str,
                   classification_type: str = "all",
                   top_k: int = 20) -> Dict[str, Any]:
        """
        Semantic text search using RAG
        意味検索（RAG使用）

        Args:
            text: Text for semantic search
            classification_type: "ipc", "cpc", "fi", or "all"
            top_k: Number of results to return

        Returns:
            Search results
        """
        params = {
            "q": text,
            "classification_type": classification_type,
            "top_k": top_k
        }

        response = requests.get(f"{self.base_url}/search/text", params=params)
        response.raise_for_status()
        return response.json()

    def search_advanced(self,
                       keywords: Optional[List[str]] = None,
                       text: Optional[str] = None,
                       ipc_codes: Optional[List[str]] = None,
                       cpc_codes: Optional[List[str]] = None,
                       fi_codes: Optional[List[str]] = None,
                       classification_types: List[str] = None,
                       condition: str = "or",
                       top_k: int = 20,
                       use_semantic_search: bool = True) -> Dict[str, Any]:
        """
        Advanced search with multiple conditions
        高度検索（複数条件対応）

        Args:
            keywords: List of keywords
            text: Text for semantic search
            ipc_codes: List of IPC codes to filter
            cpc_codes: List of CPC codes to filter
            fi_codes: List of FI codes to filter
            classification_types: List of classification types ["ipc", "cpc", "fi", "all"]
            condition: "and" or "or" condition
            top_k: Number of results to return
            use_semantic_search: Use RAG semantic search

        Returns:
            Search results
        """
        if classification_types is None:
            classification_types = ["all"]

        payload = {
            "keywords": keywords,
            "text": text,
            "ipc_codes": ipc_codes,
            "cpc_codes": cpc_codes,
            "fi_codes": fi_codes,
            "classification_types": classification_types,
            "condition": condition,
            "top_k": top_k,
            "use_semantic_search": use_semantic_search
        }

        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}

        response = requests.post(f"{self.base_url}/search", json=payload)
        response.raise_for_status()
        return response.json()

    def get_by_code(self,
                   code: str,
                   classification_type: str) -> Dict[str, Any]:
        """
        Get classification by exact code
        コードで検索

        Args:
            code: Classification code (e.g., "A01B", "A01B1/00")
            classification_type: "ipc", "cpc", or "fi"

        Returns:
            Classification result
        """
        response = requests.get(
            f"{self.base_url}/search/code/{classification_type}/{code}"
        )
        response.raise_for_status()
        return response.json()

    def print_results(self, results: Dict[str, Any]):
        """
        Pretty print search results
        検索結果を整形して表示

        Args:
            results: Search results from API
        """
        print(f"\n検索結果: {results['total']} 件 (取得: {len(results['results'])} 件)")
        print(f"処理時間: {results['took_ms']:.2f} ms\n")

        for i, result in enumerate(results['results'], 1):
            print(f"--- Result {i} ---")
            print(f"コード: {result['code']}")
            print(f"分類: {result['classification_type']}")

            if result.get('title_ja'):
                print(f"タイトル(日): {result['title_ja']}")
            if result.get('title_en'):
                print(f"タイトル(英): {result['title_en']}")

            if result.get('subsection_title_ja'):
                print(f"サブセクション(日): {result['subsection_title_ja']}")
            if result.get('subsection_title_en'):
                print(f"サブセクション(英): {result['subsection_title_en']}")

            if result.get('concordance'):
                print(f"対応IPC: {result['concordance']}")
            if result.get('theme'):
                print(f"テーマ: {result['theme']}")

            print(f"スコア: {result['score']:.4f}")
            print()


def example_1_simple_keyword_search():
    """
    Example 1: Simple keyword search
    例1: シンプルなキーワード検索
    """
    print("=" * 80)
    print("Example 1: Simple Keyword Search")
    print("例1: シンプルなキーワード検索")
    print("=" * 80)

    client = PatentClassificationClient()

    # Search for "agriculture" in all classifications
    results = client.search_keyword("agriculture", classification_type="all", top_k=5)
    client.print_results(results)


def example_2_semantic_text_search():
    """
    Example 2: Semantic text search using RAG
    例2: RAGを使った意味検索
    """
    print("=" * 80)
    print("Example 2: Semantic Text Search (RAG)")
    print("例2: RAGを使った意味検索")
    print("=" * 80)

    client = PatentClassificationClient()

    # Search with a descriptive text
    text_query = "Methods and apparatus for harvesting crops and agricultural products"
    results = client.search_text(text_query, classification_type="all", top_k=5)
    client.print_results(results)


def example_3_search_by_code():
    """
    Example 3: Get classification by exact code
    例3: コードで検索
    """
    print("=" * 80)
    print("Example 3: Search by Code")
    print("例3: コードで検索")
    print("=" * 80)

    client = PatentClassificationClient()

    # Get IPC code A01B
    try:
        result = client.get_by_code("A01B", "ipc")
        print(f"コード: {result['code']}")
        print(f"タイトル(日): {result.get('title_ja', 'N/A')}")
        print(f"タイトル(英): {result.get('title_en', 'N/A')}")
    except requests.HTTPError as e:
        print(f"Error: {e}")


def example_4_advanced_search_with_or_condition():
    """
    Example 4: Advanced search with OR condition
    例4: OR条件での高度検索
    """
    print("=" * 80)
    print("Example 4: Advanced Search with OR Condition")
    print("例4: OR条件での高度検索")
    print("=" * 80)

    client = PatentClassificationClient()

    # Search with multiple keywords using OR condition
    results = client.search_advanced(
        keywords=["agriculture", "farming", "cultivation"],
        condition="or",
        classification_types=["ipc"],
        top_k=10
    )
    client.print_results(results)


def example_5_advanced_search_with_and_condition():
    """
    Example 5: Advanced search with AND condition
    例5: AND条件での高度検索
    """
    print("=" * 80)
    print("Example 5: Advanced Search with AND Condition")
    print("例5: AND条件での高度検索")
    print("=" * 80)

    client = PatentClassificationClient()

    # Search with multiple keywords using AND condition
    results = client.search_advanced(
        keywords=["soil", "working"],
        condition="and",
        classification_types=["ipc"],
        top_k=10
    )
    client.print_results(results)


def example_6_search_with_code_filter():
    """
    Example 6: Search with IPC/CPC/FI code filters
    例6: IPC/CPC/FIコードでフィルタリング
    """
    print("=" * 80)
    print("Example 6: Search with Code Filter")
    print("例6: IPC/CPC/FIコードでフィルタリング")
    print("=" * 80)

    client = PatentClassificationClient()

    # Search within specific IPC codes
    results = client.search_advanced(
        text="harvesting methods",
        ipc_codes=["A01D", "A01B"],
        condition="or",
        top_k=10,
        use_semantic_search=True
    )
    client.print_results(results)


def example_7_multilingual_search():
    """
    Example 7: Multilingual search (Japanese)
    例7: 多言語検索（日本語）
    """
    print("=" * 80)
    print("Example 7: Multilingual Search (Japanese)")
    print("例7: 多言語検索（日本語）")
    print("=" * 80)

    client = PatentClassificationClient()

    # Search in Japanese
    results = client.search_text(
        "農業における土壌処理方法",
        classification_type="all",
        top_k=5
    )
    client.print_results(results)


def example_8_combined_search():
    """
    Example 8: Combined keyword and semantic search
    例8: キーワードと意味検索の組み合わせ
    """
    print("=" * 80)
    print("Example 8: Combined Search")
    print("例8: キーワードと意味検索の組み合わせ")
    print("=" * 80)

    client = PatentClassificationClient()

    # Combine keyword and semantic search
    results = client.search_advanced(
        keywords=["harvesting"],
        text="Machines for collecting agricultural products from fields",
        classification_types=["ipc", "cpc"],
        condition="or",
        top_k=10,
        use_semantic_search=True
    )
    client.print_results(results)


def example_9_search_specific_classification():
    """
    Example 9: Search only in specific classification type
    例9: 特定の分類タイプのみで検索
    """
    print("=" * 80)
    print("Example 9: Search in Specific Classification")
    print("例9: 特定の分類タイプのみで検索")
    print("=" * 80)

    client = PatentClassificationClient()

    # Search only in FI classifications
    results = client.search_keyword(
        "土壌",
        classification_type="fi",
        top_k=10
    )
    client.print_results(results)


def example_10_batch_code_lookup():
    """
    Example 10: Batch lookup of multiple codes
    例10: 複数コードの一括検索
    """
    print("=" * 80)
    print("Example 10: Batch Code Lookup")
    print("例10: 複数コードの一括検索")
    print("=" * 80)

    client = PatentClassificationClient()

    codes_to_lookup = [
        ("A01B", "ipc"),
        ("A01C", "ipc"),
        ("A01D", "ipc")
    ]

    for code, classification_type in codes_to_lookup:
        try:
            result = client.get_by_code(code, classification_type)
            print(f"\nコード: {result['code']}")
            print(f"タイトル(英): {result.get('title_en', 'N/A')}")
            print(f"タイトル(日): {result.get('title_ja', 'N/A')}")
        except requests.HTTPError as e:
            print(f"Error fetching {code}: {e}")


def main():
    """Run all examples"""
    print("\n")
    print("=" * 80)
    print("Patent Classification Search API - Sample Code")
    print("特許分類検索API - サンプルコード")
    print("=" * 80)
    print("\n")

    # Check API health
    client = PatentClassificationClient()
    try:
        health = client.health_check()
        print(f"API Status: {health['status']}")
        print(f"OpenSearch: {health.get('opensearch', 'unknown')}")
        print("\n")
    except Exception as e:
        print(f"Error: Cannot connect to API. Please ensure the API is running.")
        print(f"Details: {e}")
        return

    # Run examples
    examples = [
        example_1_simple_keyword_search,
        example_2_semantic_text_search,
        example_3_search_by_code,
        example_4_advanced_search_with_or_condition,
        example_5_advanced_search_with_and_condition,
        example_6_search_with_code_filter,
        example_7_multilingual_search,
        example_8_combined_search,
        example_9_search_specific_classification,
        example_10_batch_code_lookup
    ]

    for example_func in examples:
        try:
            example_func()
            print("\n" + "=" * 80 + "\n")
        except Exception as e:
            print(f"Error running example: {e}")
            print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
