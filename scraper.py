"""
Florida Court Opinion Scraper

Scrapes opinions from all 7 Florida appellate courts:
- Supreme Court of Florida
- 1st through 6th District Courts of Appeal
"""

import io
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urljoin, urlencode

import requests
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader

from config import COURTS, ARCHIVE_PARAMS, USER_AGENT, LOOKBACK_DAYS
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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
    opinion_type: str = ""  # e.g., "Written Opinion", "PCA", etc.
    pdf_url: str = ""
    page_url: str = ""
    text_content: str = ""
    summary: str = ""
    lower_tribunal: str = ""

    @property
    def unique_id(self) -> str:
        return f"{self.court_id}:{self.case_number}"


class FloridaCourtScraper:
    """Scrapes opinions from Florida appellate courts."""

    def __init__(self):
        self.session = requests.Session()
        # Use a realistic browser user-agent
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        # Add retry logic for transient failures
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.cutoff_date = datetime.now() - timedelta(days=LOOKBACK_DAYS)

    def scrape_all_courts(self) -> list[Opinion]:
        """Scrape opinions from all configured courts."""
        all_opinions = []

        for court_id, court_config in COURTS.items():
            try:
                logger.info(f"Scraping {court_config['name']}...")
                opinions = self._scrape_court(court_id, court_config)
                all_opinions.extend(opinions)
                logger.info(f"  Found {len(opinions)} opinions from {court_config['short_name']}")
                time.sleep(2)  # Be respectful with request timing
            except Exception as e:
                logger.error(f"  Error scraping {court_config['name']}: {e}")

        logger.info(f"Total opinions scraped: {len(all_opinions)}")
        return all_opinions

    def _scrape_court(self, court_id: str, config: dict) -> list[Opinion]:
        """Scrape opinions from a single court, trying multiple strategies."""
        opinions = []

        # Strategy 1: Try the "Most Recent" page
        try:
            recent_opinions = self._scrape_recent_page(court_id, config)
            if recent_opinions:
                opinions.extend(recent_opinions)
                return opinions
        except Exception as e:
            logger.debug(f"  Recent page failed for {court_id}: {e}")

        # Strategy 2: Try the archive page with date filtering
        try:
            archive_opinions = self._scrape_archive_page(court_id, config)
            if archive_opinions:
                opinions.extend(archive_opinions)
                return opinions
        except Exception as e:
            logger.debug(f"  Archive page failed for {court_id}: {e}")

        # Strategy 3: Try the main opinions page
        try:
            main_opinions = self._scrape_main_opinions_page(court_id, config)
            if main_opinions:
                opinions.extend(main_opinions)
        except Exception as e:
            logger.debug(f"  Main opinions page failed for {court_id}: {e}")

        return opinions

    def _scrape_recent_page(self, court_id: str, config: dict) -> list[Opinion]:
        """Scrape the Most Recent Opinions page."""
        url = config.get("recent_url")
        if not url:
            return []

        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        return self._parse_opinion_page(soup, court_id, config, url)

    def _scrape_archive_page(self, court_id: str, config: dict) -> list[Opinion]:
        """Scrape the archive page with parameters."""
        url = config.get("archive_url")
        if not url:
            return []

        params = ARCHIVE_PARAMS.copy()
        # Add date filter to only get recent opinions
        params["startdate"] = self.cutoff_date.strftime("%m/%d/%Y")
        params["enddate"] = datetime.now().strftime("%m/%d/%Y")

        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        return self._parse_opinion_page(soup, court_id, config, url)

    def _scrape_main_opinions_page(self, court_id: str, config: dict) -> list[Opinion]:
        """Scrape the main opinions landing page."""
        url = config.get("opinions_url")
        if not url:
            return []

        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        return self._parse_opinion_page(soup, court_id, config, url)

    def _parse_opinion_page(self, soup: BeautifulSoup, court_id: str, config: dict, page_url: str) -> list[Opinion]:
        """
        Parse an opinion listing page. Florida courts use several HTML patterns:
        1. Table-based listings (common in archive pages)
        2. Div-based card/list layouts (common in recent opinions)
        3. Embedded content areas with structured data
        """
        opinions = []

        # --- Pattern 1: Table rows ---
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
            return opinions

        # --- Pattern 2: Links to PDFs with case number patterns ---
        pdf_links = soup.find_all("a", href=re.compile(r"(\.pdf|/download/|opinion)", re.I))
        for link in pdf_links:
            opinion = self._parse_pdf_link(link, court_id, config, page_url)
            if opinion and self._is_recent(opinion):
                opinions.append(opinion)

        if opinions:
            return opinions

        # --- Pattern 3: Structured div containers ---
        # Look for common container patterns
        containers = soup.find_all(["div", "article", "section"], class_=re.compile(
            r"(opinion|case|result|item|entry|row)", re.I
        ))
        for container in containers:
            opinion = self._parse_container(container, court_id, config, page_url)
            if opinion and self._is_recent(opinion):
                opinions.append(opinion)

        if opinions:
            return opinions

        # --- Pattern 4: Fallback - look for any links that look like opinions ---
        all_links = soup.find_all("a", href=True)
        for link in all_links:
            href = link.get("href", "")
            text = link.get_text(strip=True)
            # Match Florida case number patterns
            if re.search(r"\d{4}-\d{2,5}", text) or re.search(r"SC\d{4}-\d+", text):
                opinion = self._parse_case_link(link, court_id, config, page_url)
                if opinion and self._is_recent(opinion):
                    opinions.append(opinion)

        return opinions

    def _parse_table_row(self, cells, headers, court_id, config, page_url) -> Optional[Opinion]:
        """Parse a table row into an Opinion."""
        try:
            cell_texts = [c.get_text(strip=True) for c in cells]

            # Try to identify columns by headers
            case_number = ""
            case_name = ""
            date_str = ""
            opinion_type = ""
            pdf_url = ""
            lower_tribunal = ""

            if headers:
                col_map = {}
                for i, h in enumerate(headers):
                    if "case" in h and "number" in h or h == "case no":
                        col_map["case_number"] = i
                    elif "case" in h and "name" in h or "style" in h or "caption" in h or "title" in h:
                        col_map["case_name"] = i
                    elif "date" in h or "disposition" in h or "filed" in h or "released" in h:
                        col_map["date"] = i
                    elif "type" in h:
                        col_map["opinion_type"] = i
                    elif "tribunal" in h or "lower" in h:
                        col_map["lower_tribunal"] = i

                case_number = cell_texts[col_map["case_number"]] if "case_number" in col_map else ""
                case_name = cell_texts[col_map["case_name"]] if "case_name" in col_map else ""
                date_str = cell_texts[col_map["date"]] if "date" in col_map else ""
                opinion_type = cell_texts[col_map["opinion_type"]] if "opinion_type" in col_map else ""
                lower_tribunal = cell_texts[col_map["lower_tribunal"]] if "lower_tribunal" in col_map else ""
            else:
                # Guess column positions: typically case_number, case_name, date...
                if len(cell_texts) >= 3:
                    case_number = cell_texts[0]
                    case_name = cell_texts[1]
                    date_str = cell_texts[2] if len(cell_texts) > 2 else ""
                    opinion_type = cell_texts[3] if len(cell_texts) > 3 else ""

            # Find PDF link in the row
            for cell in cells:
                link = cell.find("a", href=True)
                if link:
                    href = link.get("href", "")
                    if ".pdf" in href.lower() or "download" in href.lower():
                        pdf_url = urljoin(config["base_url"], href)
                    if not case_name:
                        case_name = link.get_text(strip=True)
                    if not case_number:
                        # Try to extract case number from link text
                        link_text = link.get_text(strip=True)
                        match = re.search(r"(SC\d{4}-\d+|\d{4}-\d{2,5})", link_text)
                        if match:
                            case_number = match.group(1)

            if not case_number:
                # Try to find case number in any cell text
                for text in cell_texts:
                    match = re.search(r"(SC\d{4}-\d+|\d{4}-\d{2,5})", text)
                    if match:
                        case_number = match.group(1)
                        break

            if not case_number:
                return None

            date = self._parse_date(date_str)
            if not date:
                date = datetime.now()  # Default to now if no date found

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

            # Extract case number from URL or text
            case_number = ""
            for source in [href, text]:
                match = re.search(r"(SC\d{4}-\d+|\d{4}-\d{2,5})", source)
                if match:
                    case_number = match.group(1)
                    break

            if not case_number:
                return None

            # Try to find a case name from surrounding context
            parent = link.parent
            case_name = text if text and text != case_number else ""
            if not case_name and parent:
                case_name = parent.get_text(strip=True)[:200]

            # Try to find a date from surrounding context
            date = datetime.now()
            if parent:
                parent_text = parent.get_text()
                date_match = re.search(
                    r"(\d{1,2}/\d{1,2}/\d{2,4}|\w+ \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2})",
                    parent_text
                )
                if date_match:
                    date = self._parse_date(date_match.group(1)) or date

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

            # Find case number
            case_match = re.search(r"(SC\d{4}-\d+|\d{4}-\d{2,5})", text)
            if not case_match:
                return None
            case_number = case_match.group(1)

            # Find PDF link
            pdf_url = ""
            link = container.find("a", href=re.compile(r"(\.pdf|download)", re.I))
            if link:
                pdf_url = urljoin(config["base_url"], link.get("href", ""))

            # Find date
            date = datetime.now()
            date_match = re.search(
                r"(\d{1,2}/\d{1,2}/\d{2,4}|\w+ \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2})", text
            )
            if date_match:
                date = self._parse_date(date_match.group(1)) or date

            # Case name: use the full text, cleaned up
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
            "%m/%d/%Y",
            "%m/%d/%y",
            "%B %d, %Y",
            "%B %d %Y",
            "%b %d, %Y",
            "%b %d %Y",
            "%Y-%m-%d",
            "%d-%b-%Y",
            "%m-%d-%Y",
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

    def extract_pdf_text(self, opinion: Opinion, max_pages: int = 30) -> str:
        """Download and extract text from an opinion PDF."""
        if not opinion.pdf_url:
            return ""

        try:
            response = self.session.get(opinion.pdf_url, timeout=60)
            response.raise_for_status()

            if "application/pdf" not in response.headers.get("Content-Type", ""):
                # Might be HTML - could be a redirect or landing page
                logger.debug(f"Non-PDF response for {opinion.case_number}")
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
