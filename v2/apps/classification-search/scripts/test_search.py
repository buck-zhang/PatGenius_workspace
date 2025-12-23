"""Test script for patent classification search system."""

import sys
from pathlib import Path
import requests
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from loguru import logger

API_BASE_URL = "http://localhost:8000"


def test_health_check():
    """Test health check endpoint."""
    logger.info("Testing health check...")
    response = requests.get(f"{API_BASE_URL}/health")

    if response.status_code == 200:
        logger.success("Health check passed")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        return True
    else:
        logger.error(f"Health check failed: {response.status_code}")
        return False


def test_text_search():
    """Test text search endpoint."""
    logger.info("Testing text search...")

    queries = [
        "agricultural hand tools",
        "手工具",
        "通信装置",
        "semiconductor devices"
    ]

    for query in queries:
        logger.info(f"Query: '{query}'")
        response = requests.post(
            f"{API_BASE_URL}/search/text",
            json={
                "query": query,
                "limit": 5,
                "min_score": 0.3
            }
        )

        if response.status_code == 200:
            result = response.json()
            logger.success(f"Found {result['total']} results")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            print("-" * 80)
        else:
            logger.error(f"Text search failed: {response.status_code}")


def test_code_search():
    """Test code search endpoint."""
    logger.info("Testing code search...")

    codes = ["A01B1/00", "H04L29/06", "G06F"]

    response = requests.post(
        f"{API_BASE_URL}/search/code",
        json={"codes": codes}
    )

    if response.status_code == 200:
        result = response.json()
        logger.success(f"Found {result['total']} results")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("-" * 80)
    else:
        logger.error(f"Code search failed: {response.status_code}")


def test_boolean_search_or():
    """Test Boolean search with OR operator."""
    logger.info("Testing Boolean search (OR)...")

    response = requests.post(
        f"{API_BASE_URL}/search/boolean",
        json={
            "queries": ["agricultural tools", "farming equipment"],
            "operator": "OR",
            "limit": 10,
            "min_score": 0.3
        }
    )

    if response.status_code == 200:
        result = response.json()
        logger.success(f"OR search found {result['total']} results")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("-" * 80)
    else:
        logger.error(f"Boolean OR search failed: {response.status_code}")


def test_boolean_search_and():
    """Test Boolean search with AND operator."""
    logger.info("Testing Boolean search (AND)...")

    response = requests.post(
        f"{API_BASE_URL}/search/boolean",
        json={
            "queries": ["hand tools", "agricultural"],
            "operator": "AND",
            "limit": 10,
            "min_score": 0.3
        }
    )

    if response.status_code == 200:
        result = response.json()
        logger.success(f"AND search found {result['total']} results")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("-" * 80)
    else:
        logger.error(f"Boolean AND search failed: {response.status_code}")


def test_classification_type_filter():
    """Test filtering by classification type."""
    logger.info("Testing classification type filters...")

    for class_type in ["IPC", "CPC", "FI"]:
        logger.info(f"Testing {class_type}...")
        response = requests.post(
            f"{API_BASE_URL}/search/text",
            json={
                "query": "tools",
                "classification_type": class_type,
                "limit": 5
            }
        )

        if response.status_code == 200:
            result = response.json()
            logger.success(f"{class_type}: Found {result['total']} results")
            print(f"\n{class_type} Results:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            print("-" * 80)
        else:
            logger.error(f"{class_type} search failed: {response.status_code}")


def test_statistics():
    """Test statistics endpoint."""
    logger.info("Testing statistics endpoint...")

    response = requests.get(f"{API_BASE_URL}/health/stats")

    if response.status_code == 200:
        logger.success("Statistics retrieved")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        print("-" * 80)
    else:
        logger.error(f"Statistics failed: {response.status_code}")


def run_all_tests():
    """Run all tests."""
    logger.info("=" * 80)
    logger.info("Starting API Tests")
    logger.info("=" * 80)

    # Check if API is running
    try:
        test_health_check()
    except requests.exceptions.ConnectionError:
        logger.error(f"Cannot connect to API at {API_BASE_URL}")
        logger.error("Make sure the API server is running:")
        logger.error("  cd patent_classification_search")
        logger.error("  python -m api.main")
        return

    # Run tests
    test_statistics()
    test_text_search()
    test_code_search()
    test_boolean_search_or()
    test_boolean_search_and()
    test_classification_type_filter()

    logger.info("=" * 80)
    logger.info("All tests completed!")
    logger.info("=" * 80)


if __name__ == "__main__":
    run_all_tests()
