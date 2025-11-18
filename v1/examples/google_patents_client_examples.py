"""
Google Patents API Client Examples
Demonstrates how to use the Google Patents Search API
"""

import requests
import json
from typing import List, Dict, Any, Optional
from pathlib import Path


class GooglePatentsClient:
    """Client for Google Patents Search API"""

    def __init__(self, base_url: str = "http://localhost:8001"):
        """
        Initialize client

        Args:
            base_url: Base URL of the API
        """
        self.base_url = base_url.rstrip('/')

    def simple_search(self, query: str, max_results: int = 50, language: str = "en") -> Dict[str, Any]:
        """
        Simple keyword search

        Args:
            query: Search query string
            max_results: Maximum number of results
            language: Language code (en, ja, etc.)

        Returns:
            Search results dictionary
        """
        url = f"{self.base_url}/search/simple"
        params = {
            "q": query,
            "max_results": max_results,
            "language": language
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def advanced_search(self,
                       keywords: Optional[List[str]] = None,
                       fi_codes: Optional[List[str]] = None,
                       ipc_codes: Optional[List[str]] = None,
                       cpc_codes: Optional[List[str]] = None,
                       advanced_query: Optional[str] = None,
                       max_results: int = 50,
                       language: str = "en") -> Dict[str, Any]:
        """
        Advanced search with classification codes

        Args:
            keywords: List of keywords
            fi_codes: FI classification codes
            ipc_codes: IPC classification codes
            cpc_codes: CPC classification codes
            advanced_query: Custom query string
            max_results: Maximum number of results
            language: Language code

        Returns:
            Search results dictionary
        """
        url = f"{self.base_url}/search"
        payload = {
            "keywords": keywords,
            "fi_codes": fi_codes,
            "ipc_codes": ipc_codes,
            "cpc_codes": cpc_codes,
            "advanced_query": advanced_query,
            "max_results": max_results,
            "language": language
        }

        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}

        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def get_patent_numbers(self, query: str, max_results: int = 100) -> Dict[str, Any]:
        """
        Get only patent numbers (faster)

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            Dictionary with patent numbers
        """
        url = f"{self.base_url}/patent_numbers"
        params = {
            "q": query,
            "max_results": max_results
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_cpc_ranking(self, query: str, max_results: int = 100, top_k: int = 20) -> Dict[str, Any]:
        """
        Get CPC code ranking

        Args:
            query: Search query
            max_results: Maximum results to analyze
            top_k: Top K CPC codes to return

        Returns:
            CPC ranking dictionary
        """
        url = f"{self.base_url}/cpc_ranking"
        params = {
            "q": query,
            "max_results": max_results,
            "top_k": top_k
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def download_pdf(self, patent_number: str, output_dir: str = "pdfs") -> str:
        """
        Download patent PDF

        Args:
            patent_number: Patent number (e.g., "US1234567A")
            output_dir: Directory to save PDF

        Returns:
            Path to downloaded PDF
        """
        url = f"{self.base_url}/download/{patent_number}"

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        # Download PDF
        response = requests.get(url, stream=True)
        response.raise_for_status()

        # Save to file
        output_file = output_path / f"{patent_number}.pdf"
        with open(output_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return str(output_file)

    @staticmethod
    def print_results(results: Dict[str, Any], max_patents: int = 5):
        """Pretty print search results"""
        print(f"\n{'='*80}")
        print(f"GOOGLE PATENTS SEARCH RESULTS")
        print(f"{'='*80}")
        print(f"Query: {results['query']}")
        print(f"Total hits: {results['total_hits']:,}")
        print(f"Results retrieved: {results['results_count']}")

        # Print CPC ranking
        if results.get('cpc_ranking'):
            print(f"\n{'='*80}")
            print(f"TOP CPC CODES")
            print(f"{'='*80}")
            for i, cpc in enumerate(results['cpc_ranking'][:10], 1):
                print(f"{i:2d}. {cpc['cpc_code']:15s} - {cpc['count']:3d} patents ({cpc['percentage']:5.2f}%)")

        # Print patent numbers
        if results.get('patent_numbers'):
            print(f"\n{'='*80}")
            print(f"PATENT NUMBERS ({len(results['patent_numbers'])} total)")
            print(f"{'='*80}")
            for i in range(0, min(20, len(results['patent_numbers'])), 5):
                batch = results['patent_numbers'][i:i+5]
                print("  ".join(batch))

        # Print detailed patent info
        if results.get('patents'):
            print(f"\n{'='*80}")
            print(f"PATENT DETAILS (First {max_patents})")
            print(f"{'='*80}")
            for i, patent in enumerate(results['patents'][:max_patents], 1):
                print(f"\n{i}. {patent['patent_number']}")
                print(f"   Title: {patent['title'][:100]}...")
                print(f"   Assignee: {patent['assignee']}")
                print(f"   Date: {patent['publication_date']}")
                print(f"   CPC: {', '.join(patent['cpc_codes'][:8])}")
                print(f"   URL: {patent['url']}")
                print(f"   PDF: {patent['pdf_url']}")

        print(f"\n{'='*80}\n")


# ============================================================================
# Examples
# ============================================================================

def example_1_simple_keyword_search():
    """Example 1: Simple keyword search"""
    print("\n=== Example 1: Simple Keyword Search ===")

    client = GooglePatentsClient()
    results = client.simple_search("agriculture", max_results=20)
    client.print_results(results)


def example_2_advanced_query_with_operators():
    """Example 2: Advanced query with AND, OR, NOT operators"""
    print("\n=== Example 2: Advanced Query with Operators ===")

    client = GooglePatentsClient()

    # Search for agriculture AND (soil OR farming) NOT pesticide
    results = client.simple_search(
        query="agriculture AND (soil OR farming) NOT pesticide",
        max_results=30
    )

    client.print_results(results)


def example_3_search_with_fi_codes():
    """Example 3: Search with FI classification codes"""
    print("\n=== Example 3: Search with FI Codes ===")

    client = GooglePatentsClient()

    # Search for patents with specific FI code
    results = client.advanced_search(
        keywords=["agriculture"],
        fi_codes=["A01B33/00"],  # Soil working implements
        max_results=20
    )

    client.print_results(results)


def example_4_search_with_cpc_codes():
    """Example 4: Search with CPC classification codes"""
    print("\n=== Example 4: Search with CPC Codes ===")

    client = GooglePatentsClient()

    # Search for patents with specific CPC code
    results = client.advanced_search(
        cpc_codes=["A01B"],  # Soil working in agriculture
        max_results=20
    )

    client.print_results(results)


def example_5_get_cpc_ranking():
    """Example 5: Get CPC code ranking from search"""
    print("\n=== Example 5: CPC Code Ranking ===")

    client = GooglePatentsClient()

    # Get top CPC codes for agriculture patents
    ranking = client.get_cpc_ranking(
        query="agriculture",
        max_results=100,
        top_k=15
    )

    print(f"\nQuery: {ranking['query']}")
    print(f"Total hits: {ranking['total_hits']:,}")
    print(f"Results analyzed: {ranking['results_analyzed']}")
    print(f"\nTop CPC Codes:")
    for i, cpc in enumerate(ranking['cpc_ranking'], 1):
        print(f"{i:2d}. {cpc['cpc_code']:15s} - {cpc['count']:3d} patents ({cpc['percentage']:5.2f}%)")


def example_6_get_patent_numbers_only():
    """Example 6: Get only patent numbers (fast)"""
    print("\n=== Example 6: Get Patent Numbers Only ===")

    client = GooglePatentsClient()

    # Get patent numbers only (faster than full search)
    result = client.get_patent_numbers(
        query="agriculture AND soil",
        max_results=50
    )

    print(f"\nQuery: {result['query']}")
    print(f"Total hits: {result['total_hits']:,}")
    print(f"Patent numbers retrieved: {len(result['patent_numbers'])}")
    print(f"\nFirst 20 patent numbers:")
    for i in range(0, min(20, len(result['patent_numbers'])), 5):
        batch = result['patent_numbers'][i:i+5]
        print("  ".join(batch))


def example_7_download_pdfs():
    """Example 7: Download patent PDFs"""
    print("\n=== Example 7: Download Patent PDFs ===")

    client = GooglePatentsClient()

    # First, search for patents
    results = client.simple_search("agriculture", max_results=5)

    if results['patents']:
        print(f"\nDownloading PDFs for first 3 patents...")

        for patent in results['patents'][:3]:
            patent_number = patent['patent_number']
            print(f"\nDownloading {patent_number}...")

            try:
                pdf_path = client.download_pdf(patent_number)
                print(f"  Saved to: {pdf_path}")
            except Exception as e:
                print(f"  Error: {e}")


def example_8_near_operator():
    """Example 8: Use NEAR operator for proximity search"""
    print("\n=== Example 8: NEAR Operator (Proximity Search) ===")

    client = GooglePatentsClient()

    # Search for "agriculture" within 5 words of "crop"
    results = client.simple_search(
        query="agriculture NEAR/5 crop",
        max_results=20
    )

    client.print_results(results)


def example_9_complex_boolean_query():
    """Example 9: Complex boolean query"""
    print("\n=== Example 9: Complex Boolean Query ===")

    client = GooglePatentsClient()

    # Complex query: (agriculture OR farming) AND (soil OR crop) NOT (pesticide OR herbicide)
    results = client.simple_search(
        query="(agriculture OR farming) AND (soil OR crop) NOT (pesticide OR herbicide)",
        max_results=30
    )

    client.print_results(results)


def example_10_japanese_language_search():
    """Example 10: Search in Japanese"""
    print("\n=== Example 10: Japanese Language Search ===")

    client = GooglePatentsClient()

    # Search with Japanese keywords
    results = client.simple_search(
        query="農業 AND 土壌",
        max_results=20,
        language="ja"
    )

    client.print_results(results)


# ============================================================================
# Main
# ============================================================================

def main():
    """Run all examples"""
    print("\n" + "="*80)
    print("GOOGLE PATENTS API CLIENT EXAMPLES")
    print("="*80)

    examples = [
        ("Simple Keyword Search", example_1_simple_keyword_search),
        ("Advanced Query with Operators", example_2_advanced_query_with_operators),
        ("Search with FI Codes", example_3_search_with_fi_codes),
        ("Search with CPC Codes", example_4_search_with_cpc_codes),
        ("CPC Code Ranking", example_5_get_cpc_ranking),
        ("Get Patent Numbers Only", example_6_get_patent_numbers_only),
        ("Download PDFs", example_7_download_pdfs),
        ("NEAR Operator", example_8_near_operator),
        ("Complex Boolean Query", example_9_complex_boolean_query),
        ("Japanese Language Search", example_10_japanese_language_search),
    ]

    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"{i:2d}. {name}")

    print("\nEnter example number to run (or 'all' to run all, 'q' to quit): ", end='')

    try:
        choice = input().strip().lower()

        if choice == 'q':
            print("Exiting...")
            return

        if choice == 'all':
            for name, func in examples:
                print(f"\n\n{'='*80}")
                print(f"Running: {name}")
                print(f"{'='*80}")
                try:
                    func()
                except Exception as e:
                    print(f"Error running example: {e}")
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(examples):
                    name, func = examples[idx]
                    print(f"\nRunning: {name}")
                    func()
                else:
                    print("Invalid example number")
            except ValueError:
                print("Invalid input")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")


if __name__ == "__main__":
    # Quick test - run example 1
    example_1_simple_keyword_search()

    # Uncomment to run interactive menu
    # main()
