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

    def __init__(self, headless: bool = True, timeout: int = 30, use_pool: bool = False):
        """
        Initialize scraper with Chrome WebDriver

        Args:
            headless: Run browser in headless mode
            timeout: Default timeout for page loads (seconds)
            use_pool: Use ChromeDriverPool instead of creating own driver
        """
        self.timeout = timeout
        self.base_url = "https://patents.google.com/"
        self.headless = headless
        self.use_pool = use_pool
        self.driver = None
        self.wait = None
        self._pool = None

        # Initialize WebDriver (only if not using pool)
        if not use_pool:
            self._init_driver()
        else:
            # Get reference to pool but don't acquire driver yet
            self._pool = get_driver_pool(max_drivers=3, headless=headless, timeout=timeout)

    def _init_driver(self):
        """Initialize or reinitialize the WebDriver"""
        # Close existing driver if present
        if self.driver is not None:
            try:
                self.driver.quit()
            except:
                pass

        # Configure Chrome options
        chrome_options = Options()
        if self.headless:
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
        self.wait = WebDriverWait(self.driver, self.timeout)
        print("Chrome WebDriver initialized successfully")

    def _ensure_valid_session(self):
        """Ensure WebDriver session is valid, reinitialize if needed"""
        try:
            # Try a simple operation to check if session is valid
            _ = self.driver.current_url
        except Exception as e:
            print(f"WebDriver session invalid ({e}), reinitializing...")
            self._init_driver()

    def __del__(self):
        """Clean up WebDriver on deletion"""
        if hasattr(self, 'driver') and self.driver is not None:
            self.driver.quit()

    def close(self):
        """Explicitly close the WebDriver"""
        if self.driver:
            self.driver.quit()

    def _acquire_driver(self):
        """Acquire driver from pool if using pool mode"""
        if self.use_pool:
            self.driver = self._pool.acquire()
            self.wait = WebDriverWait(self.driver, self.timeout)
        elif not self.driver:
            self._init_driver()

    def _release_driver(self):
        """Release driver back to pool if using pool mode"""
        if self.use_pool and self.driver:
            self._pool.release(self.driver)
            self.driver = None
            self.wait = None

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
        # Acquire driver from pool if using pool mode
        self._acquire_driver()

        try:
            # Ensure WebDriver session is valid
            self._ensure_valid_session()

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
                return self._empty_results(query)

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

            # Fetch CPC codes from detail pages
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
        finally:
            # Release driver back to pool if using pool mode
            self._release_driver()

    def _extract_total_hits(self) -> int:
        """Extract total number of search hits"""
        try:
            # Try to find the result count element
            # Google Patents shows "About X results" or similar
            soup = BeautifulSoup(self.driver.page_source, 'lxml')

            # Method 1: Search for "About X results" pattern in all text nodes
            # We need to check all strings, not just the first one
            for text in soup.stripped_strings:
                # Look for "About X results" pattern
                if 'result' in text.lower():
                    # Extract number from text like "About 1,531 results"
                    match = re.search(r'About\s+([\d,]+)\s+results?', text, re.IGNORECASE)
                    if match:
                        count_str = match.group(1).replace(',', '')
                        return int(count_str)

            # Method 2: Look for specific element (fallback)
            result_stats = soup.find(id='result-stats')
            if result_stats:
                match = re.search(r'([\d,]+)', result_stats.get_text())
                if match:
                    return int(match.group(1).replace(',', ''))

            # Method 3: If we can't find the total, count visible results
            # (This is a fallback and will return only the current page count)
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

            # Try to extract patent number from new structure (data-result attribute)
            patent_number = None
            patent_url = None
            title = "N/A"

            state_modifier = soup.find('state-modifier')
            if state_modifier:
                data_result = state_modifier.get('data-result', '')
                # Extract patent number from data-result like "patent/US10032503B2/en"
                match = re.search(r'(patent/[A-Z0-9]+)', data_result)
                if match:
                    patent_url = '/' + match.group(1)  # "/patent/US10032503B2"
                    patent_number = re.search(r'([A-Z0-9]+)$', patent_url).group(1)

                # Extract title from h3 or raw-html
                title_elem = soup.find('h3')
                if title_elem:
                    title = title_elem.get_text(strip=True)

            # Fallback to old structure if new structure not found
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

    def _fetch_cpc_codes_from_detail_page(self, patent_number: str) -> List[str]:
        """
        Visit patent detail page and extract CPC codes

        Args:
            patent_number: Patent number (e.g., "JP6898807B2")

        Returns:
            List of CPC codes
        """
        # Ensure WebDriver session is valid
        self._ensure_valid_session()

        cpc_codes = []

        try:
            # Navigate to patent detail page
            detail_url = f"https://patents.google.com/patent/{patent_number}"
            print(f"Fetching CPC codes from: {detail_url}")

            self.driver.get(detail_url)
            time.sleep(3)  # Wait for page load

            # Wait for page content to load
            wait = WebDriverWait(self.driver, 15)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "patent-result")))

            # Additional wait for JavaScript to render classifications
            time.sleep(2)

            # Get page source and parse
            soup = BeautifulSoup(self.driver.page_source, 'lxml')

            # Method 1: Look for CPC codes in classification-viewer
            classification_viewer = soup.find('classification-viewer')
            if classification_viewer:
                # Look for CPC code patterns in the viewer's content
                cpc_elements = classification_viewer.find_all(string=re.compile(r'[A-H]\d{2}[A-Z]\d+/\d+'))
                for elem in cpc_elements:
                    code = elem.strip()
                    if re.match(r'^[A-H]\d{2}[A-Z]\d+/\d+$', code):
                        if code not in cpc_codes:
                            cpc_codes.append(code)

            # Method 2: Look for CPC codes anywhere in the page (fallback)
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


# ============================================================================
# ChromeDriver Connection Pool
# ============================================================================

import threading
from queue import Queue, Empty
import atexit


class ChromeDriverPool:
    """
    ChromeDriver接続プール

    複数のChromeDriverインスタンスを管理し、リクエスト間で再利用する。
    起動時間を大幅に削減し、安定性を向上させる。
    """

    def __init__(self, max_drivers: int = 3, headless: bool = True, timeout: int = 30):
        """
        初期化

        Args:
            max_drivers: プール内の最大ドライバー数
            headless: ヘッドレスモードで実行
            timeout: デフォルトタイムアウト（秒）
        """
        self.max_drivers = max_drivers
        self.headless = headless
        self.timeout = timeout
        self.pool = Queue(maxsize=max_drivers)
        self.lock = threading.Lock()
        self.driver_count = 0
        self.active_drivers = []  # 使用中のドライバー追跡

        print(f"ChromeDriver Pool initialized (max: {max_drivers} drivers)")

        # プログラム終了時のクリーンアップを登録
        atexit.register(self.cleanup_all)

    def _create_driver(self):
        """新しいChromeDriverインスタンスを作成"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

        driver_path = ChromeDriverManager().install()
        # Fix: ChromeDriverManager may return wrong file
        if 'THIRD_PARTY_NOTICES' in driver_path or 'LICENSE' in driver_path:
            import os
            driver_dir = os.path.dirname(driver_path)
            correct_path = os.path.join(driver_dir, 'chromedriver')
            if os.path.exists(correct_path):
                driver_path = correct_path

        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver

    def acquire(self):
        """
        プールからドライバーを取得

        Returns:
            ChromeDriverインスタンス
        """
        try:
            # プールから既存のドライバーを取得（非ブロッキング）
            driver = self.pool.get_nowait()
            print(f"[Pool] Reusing existing driver (pool size: {self.pool.qsize()})")

            # ヘルスチェック
            try:
                _ = driver.current_url
                self.active_drivers.append(driver)
                return driver
            except Exception as e:
                print(f"[Pool] Driver unhealthy ({e}), creating new one")
                try:
                    driver.quit()
                except:
                    pass
                # 新しいドライバーを作成
                with self.lock:
                    driver = self._create_driver()
                    self.active_drivers.append(driver)
                    return driver

        except Empty:
            # プールが空の場合
            with self.lock:
                if self.driver_count < self.max_drivers:
                    # 新しいドライバーを作成
                    print(f"[Pool] Creating new driver ({self.driver_count + 1}/{self.max_drivers})")
                    driver = self._create_driver()
                    self.driver_count += 1
                    self.active_drivers.append(driver)
                    return driver
                else:
                    # 最大数に達した場合、プールから解放されるまで待機
                    print(f"[Pool] Max drivers reached, waiting for available driver...")
                    driver = self.pool.get(block=True)  # ブロッキング
                    print(f"[Pool] Driver became available")

                    # ヘルスチェック
                    try:
                        _ = driver.current_url
                        self.active_drivers.append(driver)
                        return driver
                    except Exception as e:
                        print(f"[Pool] Driver unhealthy ({e}), creating new one")
                        try:
                            driver.quit()
                        except:
                            pass
                        driver = self._create_driver()
                        self.active_drivers.append(driver)
                        return driver

    def release(self, driver):
        """
        ドライバーをプールに返却

        Args:
            driver: ChromeDriverインスタンス
        """
        if driver in self.active_drivers:
            self.active_drivers.remove(driver)

        try:
            # ドライバーが正常に動作しているか確認
            _ = driver.current_url
            # プールに返却
            self.pool.put(driver, block=False)
            print(f"[Pool] Driver returned to pool (pool size: {self.pool.qsize()})")
        except Exception as e:
            # ドライバーが異常な場合、破棄
            print(f"[Pool] Driver unhealthy on release ({e}), discarding")
            try:
                driver.quit()
            except:
                pass
            with self.lock:
                self.driver_count -= 1

    def cleanup_all(self):
        """全てのドライバーをクリーンアップ"""
        print("[Pool] Cleaning up all drivers...")

        # アクティブなドライバーをクリーンアップ
        for driver in list(self.active_drivers):
            try:
                driver.quit()
            except:
                pass
        self.active_drivers.clear()

        # プール内のドライバーをクリーンアップ
        while not self.pool.empty():
            try:
                driver = self.pool.get_nowait()
                driver.quit()
            except:
                pass

        self.driver_count = 0
        print("[Pool] Cleanup complete")


# グローバルChromeDriverプール（モジュールレベル）
_global_driver_pool = None
_pool_lock = threading.Lock()


def get_driver_pool(max_drivers: int = 3, headless: bool = True, timeout: int = 30) -> ChromeDriverPool:
    """
    グローバルChromeDriverプールを取得（シングルトン）

    Args:
        max_drivers: プール内の最大ドライバー数
        headless: ヘッドレスモードで実行
        timeout: デフォルトタイムアウト（秒）

    Returns:
        ChromeDriverPool インスタンス
    """
    global _global_driver_pool

    if _global_driver_pool is None:
        with _pool_lock:
            if _global_driver_pool is None:
                _global_driver_pool = ChromeDriverPool(
                    max_drivers=max_drivers,
                    headless=headless,
                    timeout=timeout
                )

    return _global_driver_pool


if __name__ == "__main__":
    main()
