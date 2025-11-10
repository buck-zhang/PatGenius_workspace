"""
Basic tests for Google Patents scraper and API
Tests functionality without actually scraping (to avoid rate limits and save time)
"""

import sys
from google_patents_scraper import GooglePatentsScraper


def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")

    try:
        from google_patents_scraper import GooglePatentsScraper
        print("✓ google_patents_scraper imported successfully")
    except Exception as e:
        print(f"✗ Failed to import google_patents_scraper: {e}")
        return False

    try:
        from google_patents_api import app
        print("✓ google_patents_api imported successfully")
    except Exception as e:
        print(f"✗ Failed to import google_patents_api: {e}")
        return False

    try:
        from google_patents_client_examples import GooglePatentsClient
        print("✓ google_patents_client_examples imported successfully")
    except Exception as e:
        print(f"✗ Failed to import google_patents_client_examples: {e}")
        return False

    return True


def test_query_builder():
    """Test query building functionality"""
    print("\nTesting query builder...")

    # Create scraper instance (don't initialize WebDriver yet)
    class MockScraper:
        def build_search_query(self, **kwargs):
            return GooglePatentsScraper.build_search_query(None, **kwargs)

    scraper = MockScraper()

    # Test 1: Simple keywords
    query = scraper.build_search_query(keywords=["agriculture", "soil"])
    expected = "agriculture soil"
    assert query == expected, f"Expected '{expected}', got '{query}'"
    print(f"✓ Keywords: '{query}'")

    # Test 2: FI codes
    query = scraper.build_search_query(fi_codes=["A01B33/00", "A01B49/02"])
    expected = "(FI:A01B33/00 OR FI:A01B49/02)"
    assert query == expected, f"Expected '{expected}', got '{query}'"
    print(f"✓ FI codes: '{query}'")

    # Test 3: IPC codes
    query = scraper.build_search_query(ipc_codes=["A01B"])
    expected = "(IPC:A01B)"
    assert query == expected, f"Expected '{expected}', got '{query}'"
    print(f"✓ IPC codes: '{query}'")

    # Test 4: CPC codes
    query = scraper.build_search_query(cpc_codes=["A01B33/00"])
    expected = "(CPC:A01B33/00)"
    assert query == expected, f"Expected '{expected}', got '{query}'"
    print(f"✓ CPC codes: '{query}'")

    # Test 5: Advanced query
    query = scraper.build_search_query(advanced_query="agriculture AND (soil OR crop)")
    expected = "agriculture AND (soil OR crop)"
    assert query == expected, f"Expected '{expected}', got '{query}'"
    print(f"✓ Advanced query: '{query}'")

    # Test 6: Combined
    query = scraper.build_search_query(
        keywords=["agriculture"],
        fi_codes=["A01B33/00"],
        ipc_codes=["A01B"]
    )
    expected = "agriculture AND (FI:A01B33/00) AND (IPC:A01B)"
    assert query == expected, f"Expected '{expected}', got '{query}'"
    print(f"✓ Combined query: '{query}'")

    return True


def test_api_endpoints():
    """Test that API endpoints are defined correctly"""
    print("\nTesting API endpoints...")

    try:
        from google_patents_api import app
        from fastapi.testclient import TestClient

        # This import might fail if fastapi.testclient is not installed
        # In that case, we'll just check that the app exists
        if 'TestClient' in dir():
            client = TestClient(app)

            # Test health endpoint
            response = client.get("/health")
            assert response.status_code == 200
            print(f"✓ Health endpoint: {response.json()}")

            # Test root endpoint
            response = client.get("/")
            assert response.status_code == 200
            print(f"✓ Root endpoint: {response.json()}")
        else:
            print("✓ API app created successfully (TestClient not available)")

    except ImportError as e:
        print(f"⚠ FastAPI TestClient not available, skipping endpoint tests: {e}")
        return True
    except Exception as e:
        print(f"✗ API endpoint test failed: {e}")
        return False

    return True


def test_cpc_ranking_logic():
    """Test CPC ranking calculation"""
    print("\nTesting CPC ranking logic...")

    # Mock patent data
    patents = [
        {"cpc_codes": ["A01B33/00", "A01B49/02"]},
        {"cpc_codes": ["A01B33/00", "C05F17/00"]},
        {"cpc_codes": ["A01B33/00"]},
        {"cpc_codes": ["C05F17/00"]},
    ]

    # Create mock scraper
    class MockScraper:
        def _create_cpc_ranking(self, patents):
            return GooglePatentsScraper._create_cpc_ranking(None, patents)

    scraper = MockScraper()
    ranking = scraper._create_cpc_ranking(patents)

    # Verify ranking
    assert len(ranking) == 3, f"Expected 3 unique CPC codes, got {len(ranking)}"
    assert ranking[0]["cpc_code"] == "A01B33/00", "Most common should be A01B33/00"
    assert ranking[0]["count"] == 3, f"A01B33/00 count should be 3, got {ranking[0]['count']}"
    assert ranking[0]["percentage"] == 75.0, f"Expected 75%, got {ranking[0]['percentage']}"

    print(f"✓ CPC ranking: {ranking}")

    return True


def main():
    """Run all tests"""
    print("="*80)
    print("GOOGLE PATENTS SCRAPER - BASIC TESTS")
    print("="*80)

    tests = [
        ("Import tests", test_imports),
        ("Query builder", test_query_builder),
        ("API endpoints", test_api_endpoints),
        ("CPC ranking", test_cpc_ranking_logic),
    ]

    results = []
    for name, test_func in tests:
        print(f"\n{'-'*80}")
        print(f"Running: {name}")
        print(f"{'-'*80}")
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
