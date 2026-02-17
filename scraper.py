"""
Florida Court Opinion Scraper

Scrapes opinions from all 7 Florida appellate courts using Playwright
(headless browser) since the court websites are JavaScript SPAs that
render content client-side.

Courts:
- Supreme Court of Florida
- 1st through 6th District Courts of Appeal
"""

import io
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout

from config import COURTS, USER_AGENT, LOOKBACK_DAYS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class Opinion:
    """Represents a single court opinion."""
    case_number: str
    case_name: str
    court_id: str
    court_name: str
    date: datetime
    opinion_type: str = ""
    pdf_url: str = ""
    page_url: str = ""
    text_content: str = ""
    summary: str = ""
    lower_tribunal: str = ""

    @property
    def unique_id(self) -> str:
        return f"{self.court_id}:{self.case_number}"


class FloridaCourtScraper:
    """Scrapes opinions from Florida appellate courts using Playwright."""

    def __init__(self):
        self.cutoff_date = datetime.now() - timedelta(days=LOOKBACK_DAYS)
        # requests session for PDF downloads (doesn't need JS rendering)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def scrape_all_courts(self) -> list[Opinion]:
        """Scrape opinions from all configured courts."""
        all_opinions = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = context.new_page()

            for court_id, court_config in COURTS.items():
                try:
                    logger.info(f"Scraping {court_config['name']}...")
                    opinions = self._scrape_court(page, court_id, court_config)
                    all_opinions.extend(opinions)
                    logger.info(f"  Found {len(opinions)} opinions from {court_config['short_name']}")
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"  Error scraping {court_config['name']}: {e}")

            browser.close()

        logger.info(f"Total opinions scraped: {len(all_opinions)}")
        return all_opinions

    def _scrape_court(self, page: Page, court_id: str, config: dict) -> list[Opinion]:
        """Scrape opinions from a single court, trying multiple page URLs."""
        # Try URLs in priority order
        urls_to_try = []
        if "recent_url" in config:
            urls_to_try.append(("recent", config["recent_url"]))
        if "archive_url" in config:
            urls_to_try.append(("archive", config["archive_url"]))
        if "opinions_url" in config:
            urls_to_try.append(("main", config["opinions_url"]))

        for label, url in urls_to_try:
            try:
                opinions = self._scrape_page_with_playwright(page, url, court_id, config)
                if opinions:
                    logger.info(f"  Got {len(opinions)} opinions from {label} page")
                    return opinions
            except Exception as e:
                logger.warning(f"  {label} page failed for {court_id}: {e}")

        return []

    def _scrape_page_with_playwright(self, page: Page, url: str, court_id: str, config: dict) -> list[Opinion]:
        """Navigate to a page, wait for JS rendering, then parse the content."""
        logger.info(f"  Loading: {url}")

        # Navigate and wait for the page to be fully loaded
        page.goto(url, wait_until="networkidle", timeout=30000)

        # Wait for content to appear — look for common indicators that opinions loaded
        # Try waiting for tables, links with case numbers, or any substantial content
        try:
            page.wait_for_selector(
                "table, a[href*='download'], a[href*='.pdf'], [class*='opinion'], [class*='case']",
                timeout=10000,
            )
        except PlaywrightTimeout:
            # Content might be structured differently; continue anyway
            logger.debug(f"  No expected selectors found, parsing what we have")

        # Give an extra moment for any lazy-loaded content
        page.wait_for_timeout(2000)

        # Get the fully-rendered HTML
        html = page.content()
        logger.info(f"  Rendered page size: {len(html)} chars")

        # Parse the rendered HTML
        soup = BeautifulSoup(html, "lxml")
        return self._parse_opinion_page(soup, court_id, config, url)

    def _parse_opinion_page(self, soup: BeautifulSoup, court_id: str, config: dict, page_url: str) -> list[Opinion]:
        """Parse a rendered opinion page using multiple strategies."""
        opinions = []

        # --- Strategy 1: Table rows ---
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            headers = []
            for row in rows:
                cells = row.find_all(["th", "td"])
                if row.find("th"):
                    headers = [c.get_text(strip=True).lower() for c in cells]
                    continue
                if not cells or len(cells) < 2:
                    continue
                opinion = self._parse_table_row(cells, headers, court_id, config, page_url)
                if opinion and self._is_recent(opinion):
                    opinions.append(opinion)

        if opinions:
            logger.info(f"  Parsed {len(opinions)} opinions from tables")
            return self._dedupe(opinions)

        # --- Strategy 2: Links to PDFs / downloads ---
        pdf_links = soup.find_all("a", href=re.compile(r"(\.pdf|/download/|/content/download)", re.I))
        for link in pdf_links:
            opinion = self._parse_pdf_link(link, court_id, config, page_url)
            if opinion and self._is_recent(opinion):
                opinions.append(opinion)

        if opinions:
            logger.info(f"  Parsed {len(opinions)} opinions from PDF links")
            return self._dedupe(opinions)

        # --- Strategy 3: Structured containers ---
        containers = soup.find_all(["div", "article", "section", "li"], class_=re.compile(
            r"(opinion|case|result|item|entry|row|record|search)", re.I
        ))
        for container in containers:
            opinion = self._parse_container(container, court_id, config, page_url)
            if opinion and self._is_recent(opinion):
                opinions.append(opinion)

        if opinions:
            logger.info(f"  Parsed {len(opinions)} opinions from containers")
            return self._dedupe(opinions)

        # --- Strategy 4: Any links with case number patterns ---
        all_links = soup.find_all("a", href=True)
        for link in all_links:
            text = link.get_text(strip=True)
            if re.search(r"(SC\d{4}-\d+|\d{4}-\d{2,5})", text):
                opinion = self._parse_case_link(link, court_id, config, page_url)
                if opinion and self._is_recent(opinion):
                    opinions.append(opinion)

        if opinions:
            logger.info(f"  Parsed {len(opinions)} opinions from case links")
            return self._dedupe(opinions)

        # --- Strategy 5: Broad text search for case numbers ---
        all_text = soup.get_text()
        case_matches = re.findall(r"(SC\d{4}-\d+|\d{4}-\d{2,5})", all_text)
        if case_matches:
            logger.info(f"  Found {len(set(case_matches))} case numbers in page text but couldn't extract structured data")
        else:
            logger.warning(f"  No case numbers found in rendered page at all")

        return []

    def _parse_table_row(self, cells, headers, court_id, config, page_url) -> Optional[Opinion]:
        """Parse a table row into an Opinion."""
        try:
            cell_texts = [c.get_text(strip=True) for c in cells]

            case_number = ""
            case_name = ""
            date_str = ""
            opinion_type = ""
            pdf_url = ""
            lower_tribunal = ""

            if headers:
                col_map = {}
                for i, h in enumerate(headers):
                    if ("case" in h and "number" in h) or h == "case no" or h == "case no.":
                        col_map["case_number"] = i
                    elif ("case" in h and "name" in h) or "style" in h or "caption" in h or "title" in h:
                        col_map["case_name"] = i
                    elif "date" in h or "disposition" in h or "filed" in h or "released" in h:
                        col_map["date"] = i
                    elif "type" in h:
                        col_map["opinion_type"] = i
                    elif "tribunal" in h or "lower" in h:
                        col_map["lower_tribunal"] = i

                case_number = cell_texts[col_map["case_number"]] if "case_number" in col_map and col_map["case_number"] < len(cell_texts) else ""
                case_name = cell_texts[col_map["case_name"]] if "case_name" in col_map and col_map["case_name"] < len(cell_texts) else ""
                date_str = cell_texts[col_map["date"]] if "date" in col_map and col_map["date"] < len(cell_texts) else ""
                opinion_type = cell_texts[col_map["opinion_type"]] if "opinion_type" in col_map and col_map["opinion_type"] < len(cell_texts) else ""
                lower_tribunal = cell_texts[col_map["lower_tribunal"]] if "lower_tribunal" in col_map and col_map["lower_tribunal"] < len(cell_texts) else ""
            else:
                if len(cell_texts) >= 3:
                    case_number = cell_texts[0]
                    case_name = cell_texts[1]
                    date_str = cell_texts[2] if len(cell_texts) > 2 else ""
                    opinion_type = cell_texts[3] if len(cell_texts) > 3 else ""

            # Find PDF link in the row
            for cell in cells:
                for link in cell.find_all("a", href=True):
                    href = link.get("href", "")
                    if ".pdf" in href.lower() or "download" in href.lower():
                        pdf_url = urljoin(config["base_url"], href)
                    if not case_name:
                        case_name = link.get_text(strip=True)
                    if not case_number:
                        link_text = link.get_text(strip=True)
                        match = re.search(r"(SC\d{4}-\d+|\d{4}-\d{2,5})", link_text)
                        if match:
                            case_number = match.group(1)

            if not case_number:
                for text in cell_texts:
                    match = re.search(r"(SC\d{4}-\d+|\d{4}-\d{2,5})", text)
                    if match:
                        case_number = match.group(1)
                        break

            if not case_number:
                return None

            date = self._parse_date(date_str) or datetime.now()

            return Opinion(
                case_number=case_number,
                case_name=case_name or case_number,
                court_id=court_id,
                court_name=config["name"],
                date=date,
                opinion_type=opinion_type,
                pdf_url=pdf_url,
                page_url=page_url,
                lower_tribunal=lower_tribunal,
            )
        except Exception as e:
            logger.debug(f"Error parsing table row: {e}")
            return None

    def _parse_pdf_link(self, link, court_id, config, page_url) -> Optional[Opinion]:
        """Parse a PDF link into an Opinion."""
        try:
            href = link.get("href", "")
            text = link.get_text(strip=True)
            pdf_url = urljoin(config["base_url"], href)

            case_number = ""
            for source in [href, text]:
                match = re.search(r"(SC\d{4}-\d+|\d{4}-\d{2,5})", source)
                if match:
                    case_number = match.group(1)
                    break

            if not case_number:
                return None

            # Get case name and date from surrounding context
            parent = link.parent
            case_name = text if text and text != case_number else ""

            # Walk up to find more context
            context_el = parent
            for _ in range(3):
                if context_el is None:
                    break
                context_text = context_el.get_text(strip=True)
                if not case_name and len(context_text) > len(case_number) + 5:
                    case_name = re.sub(r"\s+", " ", context_text)[:300]
                context_el = context_el.parent

            date = datetime.now()
            if parent:
                # Search upward for a date
                for ancestor in [parent] + list(parent.parents)[:5]:
                    if ancestor is None or ancestor.name is None:
                        break
                    ancestor_text = ancestor.get_text()
                    date_match = re.search(
                        r"(\d{1,2}/\d{1,2}/\d{2,4}|\w+ \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2})",
                        ancestor_text,
                    )
                    if date_match:
                        parsed = self._parse_date(date_match.group(1))
                        if parsed:
                            date = parsed
                            break

            return Opinion(
                case_number=case_number,
                case_name=case_name or case_number,
                court_id=court_id,
                court_name=config["name"],
                date=date,
                pdf_url=pdf_url,
                page_url=page_url,
            )
        except Exception as e:
            logger.debug(f"Error parsing PDF link: {e}")
            return None

    def _parse_container(self, container, court_id, config, page_url) -> Optional[Opinion]:
        """Parse a structured div container into an Opinion."""
        try:
            text = container.get_text(strip=True)
            case_match = re.search(r"(SC\d{4}-\d+|\d{4}-\d{2,5})", text)
            if not case_match:
                return None
            case_number = case_match.group(1)

            pdf_url = ""
            link = container.find("a", href=re.compile(r"(\.pdf|download)", re.I))
            if link:
                pdf_url = urljoin(config["base_url"], link.get("href", ""))

            date = datetime.now()
            date_match = re.search(
                r"(\d{1,2}/\d{1,2}/\d{2,4}|\w+ \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2})", text
            )
            if date_match:
                date = self._parse_date(date_match.group(1)) or date

            case_name = re.sub(r"\s+", " ", text)[:300]

            return Opinion(
                case_number=case_number,
                case_name=case_name,
                court_id=court_id,
                court_name=config["name"],
                date=date,
                pdf_url=pdf_url,
                page_url=page_url,
            )
        except Exception as e:
            logger.debug(f"Error parsing container: {e}")
            return None

    def _parse_case_link(self, link, court_id, config, page_url) -> Optional[Opinion]:
        """Parse a generic case link into an Opinion."""
        try:
            href = link.get("href", "")
            text = link.get_text(strip=True)

            case_match = re.search(r"(SC\d{4}-\d+|\d{4}-\d{2,5})", text)
            if not case_match:
                return None

            case_number = case_match.group(1)
            full_url = urljoin(config["base_url"], href)
            is_pdf = ".pdf" in href.lower() or "download" in href.lower()

            return Opinion(
                case_number=case_number,
                case_name=text or case_number,
                court_id=court_id,
                court_name=config["name"],
                date=datetime.now(),
                pdf_url=full_url if is_pdf else "",
                page_url=full_url if not is_pdf else page_url,
            )
        except Exception:
            return None

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Try multiple date formats."""
        if not date_str:
            return None
        date_str = date_str.strip()
        formats = [
            "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%B %d %Y",
            "%b %d, %Y", "%b %d %Y", "%Y-%m-%d", "%d-%b-%Y", "%m-%d-%Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def _is_recent(self, opinion: Opinion) -> bool:
        """Check if the opinion is within our lookback window."""
        return opinion.date >= self.cutoff_date

    def _dedupe(self, opinions: list[Opinion]) -> list[Opinion]:
        """Remove duplicate opinions by case number."""
        seen = set()
        deduped = []
        for op in opinions:
            if op.unique_id not in seen:
                seen.add(op.unique_id)
                deduped.append(op)
        return deduped

    def extract_pdf_text(self, opinion: Opinion, max_pages: int = 30) -> str:
        """Download and extract text from an opinion PDF."""
        if not opinion.pdf_url:
            return ""
        try:
            response = self.session.get(opinion.pdf_url, timeout=60)
            response.raise_for_status()
            if "application/pdf" not in response.headers.get("Content-Type", ""):
                return ""
            reader = PdfReader(io.BytesIO(response.content))
            pages_to_read = min(len(reader.pages), max_pages)
            text = ""
            for i in range(pages_to_read):
                page_text = reader.pages[i].extract_text()
                if page_text:
                    text += page_text + "\n\n"
            return text.strip()
        except Exception as e:
            logger.warning(f"Error extracting PDF for {opinion.case_number}: {e}")
            return ""


def scrape_opinions() -> list[Opinion]:
    """Main entry point: scrape all courts and return opinions."""
    scraper = FloridaCourtScraper()
    return scraper.scrape_all_courts()


if __name__ == "__main__":
    opinions = scrape_opinions()
    for op in opinions:
        print(f"[{op.court_name}] {op.case_number}: {op.case_name[:80]} ({op.date.strftime('%Y-%m-%d')})")
        if op.pdf_url:
            print(f"  PDF: {op.pdf_url}")
        print()
