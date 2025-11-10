"""
Google Patents Web Scraper
Scrapes patent search results from https://patents.google.com/
"""

import time
import re
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
from collections import Counter

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import requests


class GooglePatentsScraper:
    """Scraper for Google Patents search results"""

    def __init__(self, headless: bool = True, timeout: int = 30):
        """
        Initialize scraper with Chrome WebDriver

        Args:
            headless: Run browser in headless mode
            timeout: Default timeout for page loads (seconds)
        """
        self.timeout = timeout
        self.base_url = "https://patents.google.com/"

        # Configure Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

        # Initialize WebDriver
        print("Initializing Chrome WebDriver...")
        driver_path = ChromeDriverManager().install()
        # Fix: ChromeDriverManager may return wrong file (THIRD_PARTY_NOTICES instead of chromedriver)
        if 'THIRD_PARTY_NOTICES' in driver_path or 'LICENSE' in driver_path:
            import os
            driver_dir = os.path.dirname(driver_path)
            correct_path = os.path.join(driver_dir, 'chromedriver')
            if os.path.exists(correct_path):
                driver_path = correct_path
                print(f"Fixed ChromeDriver path: {driver_path}")
        service = Service(driver_path)
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, timeout)

    def __del__(self):
        """Clean up WebDriver on deletion"""
        if hasattr(self, 'driver'):
            self.driver.quit()

    def close(self):
        """Explicitly close the WebDriver"""
        self.driver.quit()

    def build_search_query(self,
                          keywords: Optional[List[str]] = None,
                          fi_codes: Optional[List[str]] = None,
                          ipc_codes: Optional[List[str]] = None,
                          cpc_codes: Optional[List[str]] = None,
                          advanced_query: Optional[str] = None) -> str:
        """
        Build Google Patents search query

        Args:
            keywords: List of keywords (will be OR'd together)
            fi_codes: List of FI classification codes
            ipc_codes: List of IPC classification codes
            cpc_codes: List of CPC classification codes
            advanced_query: Raw advanced query string (e.g., "agriculture AND (soil OR farming)")

        Returns:
            Search query string
        """
        query_parts = []

        # Use advanced query if provided, otherwise build from keywords
        if advanced_query:
            query_parts.append(advanced_query)
        elif keywords:
            # Join keywords with OR by default
            query_parts.append(" ".join(keywords))

        # Add FI codes
        if fi_codes:
            fi_query = " OR ".join([f"FI:{code}" for code in fi_codes])
            query_parts.append(f"({fi_query})")

        # Add IPC codes
        if ipc_codes:
            ipc_query = " OR ".join([f"IPC:{code}" for code in ipc_codes])
            query_parts.append(f"({ipc_query})")

        # Add CPC codes
        if cpc_codes:
            cpc_query = " OR ".join([f"CPC:{code}" for code in cpc_codes])
            query_parts.append(f"({cpc_query})")

        # Combine all parts with AND
        full_query = " AND ".join(query_parts) if query_parts else ""
        return full_query

    def search(self,
              query: str,
              max_results: int = 100,
              language: str = "en") -> Dict[str, Any]:
        """
        Execute search on Google Patents

        Args:
            query: Search query string
            max_results: Maximum number of results to scrape
            language: Language for results (en, ja, etc.)

        Returns:
            Dictionary with search results
        """
        print(f"Searching Google Patents for: {query}")

        # Build search URL
        encoded_query = quote_plus(query)
        search_url = f"{self.base_url}?q={encoded_query}&hl={language}"

        print(f"URL: {search_url}")

        # Navigate to search page
        self.driver.get(search_url)

        # Wait for results to load
        try:
            # Wait for search results container
            self.wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "search-result-item"))
            )
            time.sleep(2)  # Additional wait for dynamic content
        except TimeoutException:
            print("Timeout waiting for search results")
            return self._empty_results()

        # Get total hit count
        total_hits = self._extract_total_hits()
        print(f"Total hits: {total_hits}")

        # Scrape patent results
        patents = []
        page_count = 0
        max_pages = (max_results // 10) + 1  # Google shows ~10 results per page

        while len(patents) < max_results and page_count < max_pages:
            # Extract patents from current page
            page_patents = self._extract_patents_from_page()
            patents.extend(page_patents)

            print(f"Scraped {len(page_patents)} patents from page {page_count + 1} (total: {len(patents)})")

            # Try to navigate to next page
            if not self._go_to_next_page():
                print("No more pages available")
                break

            page_count += 1
            time.sleep(2)  # Be polite to the server

        # Limit to max_results
        patents = patents[:max_results]

        # Extract CPC codes and create ranking
        cpc_ranking = self._create_cpc_ranking(patents)

        return {
            "query": query,
            "total_hits": total_hits,
            "results_count": len(patents),
            "patents": patents,
            "cpc_ranking": cpc_ranking
        }

    def _extract_total_hits(self) -> int:
        """Extract total number of search hits"""
        try:
            # Try to find the result count element
            # Google Patents shows "About X results" or similar
            soup = BeautifulSoup(self.driver.page_source, 'lxml')

            # Look for count in various possible locations
            # Method 1: Search for "results" text
            count_text = soup.find(string=re.compile(r'About.*results|results'))
            if count_text:
                # Extract number from text like "About 123,456 results"
                match = re.search(r'([\d,]+)\s*results', count_text)
                if match:
                    count_str = match.group(1).replace(',', '')
                    return int(count_str)

            # Method 2: Look for specific element (may need to inspect actual page)
            result_stats = soup.find(id='result-stats')
            if result_stats:
                match = re.search(r'([\d,]+)', result_stats.get_text())
                if match:
                    return int(match.group(1).replace(',', ''))

            # If we can't find it, count visible results
            results = self.driver.find_elements(By.TAG_NAME, "search-result-item")
            return len(results)

        except Exception as e:
            print(f"Error extracting total hits: {e}")
            return 0

    def _extract_patents_from_page(self) -> List[Dict[str, Any]]:
        """Extract patent information from current page"""
        patents = []

        try:
            # Find all search result items
            result_items = self.driver.find_elements(By.TAG_NAME, "search-result-item")

            for item in result_items:
                try:
                    patent_data = self._extract_patent_data(item)
                    if patent_data:
                        patents.append(patent_data)
                except Exception as e:
                    print(f"Error extracting patent data: {e}")
                    continue

        except Exception as e:
            print(f"Error extracting patents from page: {e}")

        return patents

    def _extract_patent_data(self, element) -> Optional[Dict[str, Any]]:
        """Extract data from a single patent result element"""
        try:
            # Get the HTML content
            html = element.get_attribute('outerHTML')
            soup = BeautifulSoup(html, 'lxml')

            # Extract patent number (usually in a link)
            patent_link = soup.find('a', href=re.compile(r'/patent/'))
            if not patent_link:
                return None

            patent_url = patent_link.get('href', '')
            # Extract patent number from URL like "/patent/US1234567A"
            match = re.search(r'/patent/([A-Z0-9]+)', patent_url)
            if not match:
                return None

            patent_number = match.group(1)

            # Extract title
            title = patent_link.get_text(strip=True) if patent_link else "N/A"

            # Extract assignee/applicant
            assignee_elem = soup.find(string=re.compile(r'Assignee|Applicant'))
            assignee = "N/A"
            if assignee_elem:
                assignee = assignee_elem.find_next('span').get_text(strip=True) if assignee_elem.find_next('span') else "N/A"

            # Extract publication date
            date_elem = soup.find(string=re.compile(r'Publication date|Filed'))
            pub_date = "N/A"
            if date_elem:
                pub_date = date_elem.find_next('span').get_text(strip=True) if date_elem.find_next('span') else "N/A"

            # Extract CPC codes
            cpc_codes = []
            cpc_elements = soup.find_all(string=re.compile(r'^[A-H]\d{2}[A-Z]'))
            for elem in cpc_elements:
                code = elem.strip()
                if re.match(r'^[A-H]\d{2}[A-Z]', code):
                    cpc_codes.append(code)

            # Build PDF URL
            pdf_url = f"https://patents.google.com{patent_url}/en?download" if patent_url else None

            return {
                "patent_number": patent_number,
                "title": title,
                "assignee": assignee,
                "publication_date": pub_date,
                "cpc_codes": cpc_codes,
                "url": f"https://patents.google.com{patent_url}" if patent_url else None,
                "pdf_url": pdf_url
            }

        except Exception as e:
            print(f"Error extracting patent data from element: {e}")
            return None

    def _go_to_next_page(self) -> bool:
        """Navigate to next page of results"""
        try:
            # Look for "Next" button
            next_button = self.driver.find_element(By.CSS_SELECTOR, "a[aria-label='Next']")
            if next_button and next_button.is_enabled():
                next_button.click()
                time.sleep(3)  # Wait for page load
                return True
        except (NoSuchElementException, Exception) as e:
            print(f"No next page available: {e}")

        return False

    def _create_cpc_ranking(self, patents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create CPC code ranking from patent list"""
        # Collect all CPC codes
        all_cpc_codes = []
        for patent in patents:
            all_cpc_codes.extend(patent.get('cpc_codes', []))

        # Count occurrences
        cpc_counter = Counter(all_cpc_codes)

        # Create ranking list
        ranking = [
            {
                "cpc_code": code,
                "count": count,
                "percentage": round(count / len(patents) * 100, 2) if patents else 0
            }
            for code, count in cpc_counter.most_common()
        ]

        return ranking

    def download_pdf(self, patent_number: str, output_path: str) -> bool:
        """
        Download patent PDF

        Args:
            patent_number: Patent number (e.g., "US1234567A")
            output_path: Path to save PDF file

        Returns:
            True if successful, False otherwise
        """
        try:
            pdf_url = f"https://patents.google.com/patent/{patent_number}/en?download"

            print(f"Downloading PDF from: {pdf_url}")
            response = requests.get(pdf_url, stream=True, timeout=30)
            response.raise_for_status()

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"PDF saved to: {output_path}")
            return True

        except Exception as e:
            print(f"Error downloading PDF: {e}")
            return False

    def _empty_results(self) -> Dict[str, Any]:
        """Return empty results structure"""
        return {
            "query": "",
            "total_hits": 0,
            "results_count": 0,
            "patents": [],
            "cpc_ranking": []
        }


def main():
    """Example usage"""
    scraper = GooglePatentsScraper(headless=False)

    try:
        # Example 1: Simple keyword search
        results = scraper.search("agriculture", max_results=20)

        print(f"\n=== Search Results ===")
        print(f"Query: {results['query']}")
        print(f"Total hits: {results['total_hits']}")
        print(f"Results retrieved: {results['results_count']}")

        print(f"\n=== CPC Ranking ===")
        for i, cpc_data in enumerate(results['cpc_ranking'][:10], 1):
            print(f"{i}. {cpc_data['cpc_code']}: {cpc_data['count']} patents ({cpc_data['percentage']}%)")

        print(f"\n=== Patents ===")
        for i, patent in enumerate(results['patents'][:5], 1):
            print(f"\n{i}. {patent['patent_number']}")
            print(f"   Title: {patent['title']}")
            print(f"   CPC: {', '.join(patent['cpc_codes'][:5])}")
            print(f"   URL: {patent['url']}")

        # Example 2: Download first patent PDF
        if results['patents']:
            first_patent = results['patents'][0]
            output_file = f"{first_patent['patent_number']}.pdf"
            scraper.download_pdf(first_patent['patent_number'], output_file)

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
