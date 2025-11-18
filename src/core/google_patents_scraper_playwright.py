"""
Google Patents Web Scraper using Playwright
Scrapes patent search results from https://patents.google.com/
"""

import time
import re
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
from collections import Counter

from playwright.sync_api import sync_playwright, Browser, Page, Playwright
from bs4 import BeautifulSoup
import requests


class GooglePatentsScraperPlaywright:
    """Scraper for Google Patents search results using Playwright"""

    def __init__(self, headless: bool = True, timeout: int = 30):
        """
        Initialize scraper with Playwright

        Args:
            headless: Run browser in headless mode
            timeout: Default timeout for page loads (seconds)
        """
        self.timeout = timeout * 1000  # Playwright uses milliseconds
        self.base_url = "https://patents.google.com/"
        self.headless = headless
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

        # Initialize Playwright
        self._init_browser()

    def _init_browser(self):
        """Initialize or reinitialize the Playwright browser"""
        # Close existing browser if present
        if self.browser is not None:
            try:
                self.browser.close()
            except:
                pass
        if self.playwright is not None:
            try:
                self.playwright.stop()
            except:
                pass

        # Start Playwright
        print("Initializing Playwright browser...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)

        # Create context and page
        context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        self.page = context.new_page()
        self.page.set_default_timeout(self.timeout)
        print("Playwright browser initialized successfully")

    def __del__(self):
        """Clean up Playwright on deletion"""
        self.close()

    def close(self):
        """Explicitly close the browser"""
        if self.browser:
            try:
                self.browser.close()
            except:
                pass
        if self.playwright:
            try:
                self.playwright.stop()
            except:
                pass

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
            fi_query = " OR ".join([f'FI="{code}"' for code in fi_codes])
            query_parts.append(f"({fi_query})")

        # Add IPC codes
        if ipc_codes:
            ipc_query = " OR ".join([f'IPC="{code}"' for code in ipc_codes])
            query_parts.append(f"({ipc_query})")

        # Add CPC codes
        # Note: This method expects FULL CPC codes with '/' (e.g., "G11C11/00")
        # For upper-level classifications (section/class/subclass), use ClassificationHierarchy.build_hierarchical_query()
        # which generates correct syntax: cpc=G11C (lowercase, no quotes) for upper levels
        if cpc_codes:
            cpc_query = " OR ".join([f'CPC="{code}"' for code in cpc_codes])
            query_parts.append(f"({cpc_query})")

        # Combine all parts with AND
        full_query = " AND ".join(query_parts) if query_parts else ""
        return full_query

    def search(self,
              query: str,
              max_results: int = 100,
              language: str = "en",
              cpc_ranking_only: bool = False,
              max_ranking_items: int = 50) -> Dict[str, Any]:
        """
        Execute search on Google Patents

        Args:
            query: Search query string
            max_results: Maximum number of results to scrape
            language: Language for results (en, ja, etc.)
            cpc_ranking_only: If True, only retrieve CPC ranking without fetching individual patents
            max_ranking_items: Maximum number of CPC ranking items to return (when cpc_ranking_only=True)

        Returns:
            Dictionary with search results
        """
        print(f"Searching Google Patents for: {query}")

        # Build search URL with num=100 to get 100 results per page
        encoded_query = quote_plus(query)
        search_url = f"{self.base_url}?q={encoded_query}&num=100&hl={language}"

        print(f"URL: {search_url}")

        # Navigate to search page
        self.page.goto(search_url)

        # Wait for results to load
        try:
            self.page.wait_for_selector("search-result-item", timeout=self.timeout)
            time.sleep(2)  # Additional wait for dynamic content
        except Exception as e:
            print(f"Timeout waiting for search results: {e}")
            return self._empty_results(query)

        # Get total hit count
        total_hits = self._extract_total_hits()
        print(f"Total hits: {total_hits}")

        # Scrape patent results
        patents = []
        page_count = 0
        max_pages = (max_results // 100) + 1  # With num=100, Google shows 100 results per page

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

        # If cpc_ranking_only mode, extract CPC ranking directly from search page
        # No need to visit individual patent detail pages
        if cpc_ranking_only:
            print(f"\n⚡ CPC ranking only mode - extracting from search results page")
            print(f"  No need to visit individual patents (much faster!)")

            # Extract CPC ranking directly from search results page
            cpc_ranking = self._extract_cpc_ranking_from_search_page()

            # If no ranking found from search page, fallback to sampling patents
            if not cpc_ranking:
                print(f"  ⚠️  No CPC ranking found on search page, using fallback method")
                print(f"  Visiting first 5 patents as fallback")

                sample_size = min(5, len(patents))
                for i, patent in enumerate(patents[:sample_size], 1):
                    patent_number = patent.get('patent_number')
                    if patent_number:
                        print(f"    [{i}/{sample_size}] {patent_number}")
                        cpc_codes = self._fetch_cpc_codes_from_detail_page(patent_number)
                        patent['cpc_codes'] = cpc_codes
                    time.sleep(1)

                cpc_ranking = self._create_cpc_ranking(patents[:sample_size])

            # Limit ranking to max_ranking_items
            cpc_ranking = cpc_ranking[:max_ranking_items]

            print(f"✓ Extracted {len(cpc_ranking)} CPC codes")

            return {
                "query": query,
                "total_hits": total_hits,
                "results_count": 0,  # No individual patents returned in ranking-only mode
                "patents": [],  # Empty list in ranking-only mode
                "cpc_ranking": cpc_ranking
            }

        # Normal mode: Fetch CPC codes from detail pages
        print(f"\nFetching CPC codes for {len(patents)} patents...")
        for i, patent in enumerate(patents, 1):
            patent_number = patent.get('patent_number')
            if patent_number:
                print(f"  [{i}/{len(patents)}] {patent_number}")
                cpc_codes = self._fetch_cpc_codes_from_detail_page(patent_number)
                patent['cpc_codes'] = cpc_codes
            time.sleep(1)  # Be polite to the server

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
            # Get page content
            content = self.page.content()
            soup = BeautifulSoup(content, 'lxml')

            # Method 1: Search for "About X results" pattern
            for text in soup.stripped_strings:
                if 'result' in text.lower():
                    match = re.search(r'About\s+([\d,]+)\s+results?', text, re.IGNORECASE)
                    if match:
                        count_str = match.group(1).replace(',', '')
                        return int(count_str)

            # Method 2: Look for specific element
            result_stats = soup.find(id='result-stats')
            if result_stats:
                match = re.search(r'([\d,]+)', result_stats.get_text())
                if match:
                    return int(match.group(1).replace(',', ''))

            # Method 3: Count visible results
            results = self.page.query_selector_all("search-result-item")
            return len(results)

        except Exception as e:
            print(f"Error extracting total hits: {e}")
            return 0

    def _extract_cpc_ranking_from_search_page(self) -> List[Dict[str, Any]]:
        """
        Extract CPC ranking directly from search results page

        This method looks for CPC filter/classification panels on the search results
        page that might contain aggregate CPC statistics.

        Returns:
            List of dicts with 'cpc_code', 'count', and 'percentage'
        """
        cpc_ranking = []

        try:
            # Get page content
            content = self.page.content()
            soup = BeautifulSoup(content, 'lxml')

            print("  Searching for CPC ranking in search results page...")

            # Method 1: Look for classification filter panels
            # Google Patents might have a filter sidebar with classification codes
            filters = soup.find_all(['div', 'span', 'section'], class_=re.compile(r'(filter|facet|classification)', re.I))

            for filter_elem in filters:
                # Look for CPC codes in the filter text
                text = filter_elem.get_text()
                cpc_matches = re.findall(r'\b([A-H]\d{2}[A-Z]\d+/\d+)\b', text)

                for cpc in cpc_matches:
                    if cpc not in [item['cpc_code'] for item in cpc_ranking]:
                        # Try to find count associated with this CPC
                        count_match = re.search(rf'{re.escape(cpc)}\s*\((\d+)\)', text)
                        count = int(count_match.group(1)) if count_match else 1

                        cpc_ranking.append({
                            'cpc_code': cpc,
                            'count': count
                        })

            # Method 2: Look for any CPC codes in the entire page
            if not cpc_ranking:
                all_text = soup.get_text()
                cpc_matches = re.findall(r'\b([A-H]\d{2}[A-Z]\d+/\d+)\b', all_text)

                # Count occurrences of each CPC code
                from collections import Counter
                cpc_counter = Counter(cpc_matches)

                for cpc, count in cpc_counter.most_common(50):  # Top 50
                    cpc_ranking.append({
                        'cpc_code': cpc,
                        'count': count
                    })

            # Calculate total count for percentage calculation
            total_count = sum(item['count'] for item in cpc_ranking)

            # Add percentage field to each item
            if total_count > 0:
                for item in cpc_ranking:
                    item['percentage'] = (item['count'] / total_count) * 100
            else:
                for item in cpc_ranking:
                    item['percentage'] = 0.0

            print(f"  Found {len(cpc_ranking)} CPC codes from search results page")

            return cpc_ranking

        except Exception as e:
            print(f"  Error extracting CPC ranking from search page: {e}")
            return []

    def _extract_patents_from_page(self) -> List[Dict[str, Any]]:
        """Extract patent information from current page"""
        patents = []

        try:
            # Get page content
            content = self.page.content()

            # Find all search result items
            result_elements = self.page.query_selector_all("search-result-item")

            for element in result_elements:
                try:
                    # Get the HTML content
                    html = element.inner_html()
                    soup = BeautifulSoup(html, 'lxml')

                    # Extract patent data
                    patent_data = self._extract_patent_data_from_html(soup)
                    if patent_data:
                        patents.append(patent_data)
                except Exception as e:
                    print(f"Error extracting patent data: {e}")
                    continue

        except Exception as e:
            print(f"Error extracting patents from page: {e}")

        return patents

    def _extract_patent_data_from_html(self, soup) -> Optional[Dict[str, Any]]:
        """Extract data from a single patent result element"""
        try:
            # Try to extract patent number from new structure
            patent_number = None
            patent_url = None
            title = "N/A"

            state_modifier = soup.find('state-modifier')
            if state_modifier:
                data_result = state_modifier.get('data-result', '')
                match = re.search(r'(patent/[A-Z0-9]+)', data_result)
                if match:
                    patent_url = '/' + match.group(1)
                    patent_number = re.search(r'([A-Z0-9]+)$', patent_url).group(1)

                # Extract title
                title_elem = soup.find('h3')
                if title_elem:
                    title = title_elem.get_text(strip=True)

            # Fallback to old structure
            if not patent_number:
                patent_link = soup.find('a', href=re.compile(r'/patent/'))
                if not patent_link:
                    return None

                patent_url = patent_link.get('href', '')
                match = re.search(r'/patent/([A-Z0-9]+)', patent_url)
                if not match:
                    return None

                patent_number = match.group(1)
                title = patent_link.get_text(strip=True)

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
            print(f"  DEBUG: Found {len(cpc_elements)} potential CPC elements for {patent_number}")
            for elem in cpc_elements:
                code = elem.strip()
                if re.match(r'^[A-H]\d{2}[A-Z]', code):
                    cpc_codes.append(code)
            print(f"  DEBUG: Extracted {len(cpc_codes)} CPC codes: {cpc_codes[:3]}")

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

    def _fetch_cpc_codes_from_detail_page(self, patent_number: str) -> List[str]:
        """
        Visit patent detail page and extract CPC codes

        Args:
            patent_number: Patent number (e.g., "JP6898807B2")

        Returns:
            List of CPC codes
        """
        cpc_codes = []

        try:
            # Navigate to patent detail page
            detail_url = f"https://patents.google.com/patent/{patent_number}"
            print(f"Fetching CPC codes from: {detail_url}")

            self.page.goto(detail_url)

            # Wait for page content to load
            self.page.wait_for_selector("patent-result", timeout=15000)
            time.sleep(2)  # Additional wait for JS rendering

            # Get page source and parse
            content = self.page.content()
            soup = BeautifulSoup(content, 'lxml')

            # Method 1: Look for CPC codes in classification-viewer
            classification_viewer = soup.find('classification-viewer')
            if classification_viewer:
                cpc_elements = classification_viewer.find_all(string=re.compile(r'[A-H]\d{2}[A-Z]\d+/\d+'))
                for elem in cpc_elements:
                    code = elem.strip()
                    if re.match(r'^[A-H]\d{2}[A-Z]\d+/\d+$', code):
                        if code not in cpc_codes:
                            cpc_codes.append(code)

            # Method 2: Look for CPC codes anywhere in the page
            if not cpc_codes:
                all_text = soup.get_text()
                cpc_matches = re.findall(r'\b([A-H]\d{2}[A-Z]\d+/\d+)\b', all_text)
                for match in cpc_matches:
                    if match not in cpc_codes:
                        cpc_codes.append(match)

            print(f"  Found {len(cpc_codes)} CPC codes: {cpc_codes[:5]}")

        except Exception as e:
            print(f"Error fetching CPC codes for {patent_number}: {e}")

        return cpc_codes

    def _go_to_next_page(self) -> bool:
        """Navigate to next page of results"""
        try:
            # Store current URL to detect page change
            current_url = self.page.url

            # Method 1: Look for "Next" button with aria-label
            next_button = self.page.query_selector("a[aria-label='Next']")
            if next_button and next_button.is_visible():
                print("  Found Next button (aria-label), clicking...")
                next_button.click()
                # Wait for URL to change or page to update
                time.sleep(5)  # Increased wait time
                # Check if we successfully moved to next page
                if self.page.url != current_url or self.page.query_selector("search-result-item"):
                    print("  Successfully navigated to next page")
                    return True

            # Method 2: Look for Next button with text content
            next_links = self.page.query_selector_all("a")
            for link in next_links:
                try:
                    text = link.inner_text().lower().strip()
                    if text in ['next', '次へ', '›', '»']:
                        print(f"  Found Next button (text='{text}'), clicking...")
                        link.click()
                        time.sleep(5)  # Increased wait time
                        # Check if we successfully moved to next page
                        if self.page.url != current_url or self.page.query_selector("search-result-item"):
                            print("  Successfully navigated to next page")
                            return True
                except:
                    continue

            # Method 3: Try to find pagination buttons
            pagination_buttons = self.page.query_selector_all("button, a")
            for button in pagination_buttons:
                try:
                    aria_label = button.get_attribute("aria-label")
                    if aria_label and ("next" in aria_label.lower() or "次" in aria_label):
                        print(f"  Found Next button (aria-label='{aria_label}'), clicking...")
                        button.click()
                        time.sleep(5)  # Increased wait time
                        # Check if we successfully moved to next page
                        if self.page.url != current_url or self.page.query_selector("search-result-item"):
                            print("  Successfully navigated to next page")
                            return True
                except:
                    continue

            print("  No next page button found")

        except Exception as e:
            print(f"  Error navigating to next page: {e}")

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

    def _empty_results(self, query: str = "") -> Dict[str, Any]:
        """Return empty results structure"""
        return {
            "query": query,
            "total_hits": 0,
            "results_count": 0,
            "patents": [],
            "cpc_ranking": []
        }


def main():
    """Example usage"""
    scraper = GooglePatentsScraperPlaywright(headless=False)

    try:
        # Example: Simple keyword search
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

        # Example: Download first patent PDF
        if results['patents']:
            first_patent = results['patents'][0]
            output_file = f"{first_patent['patent_number']}.pdf"
            scraper.download_pdf(first_patent['patent_number'], output_file)

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
