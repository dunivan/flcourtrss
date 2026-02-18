"""
Florida Court Opinion Scraper — CourtListener API Edition

Fetches recent opinions from all 7 Florida appellate courts using
the CourtListener REST API v4 (courtlistener.com).

No web scraping needed — this uses a clean JSON API.
"""

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import requests

from config import COURTS, COURTLISTENER_API_BASE, USER_AGENT, LOOKBACK_DAYS, DCA_PREFIX_MAP

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
    docket_number: str = ""
    citation: str = ""
    judges: str = ""

    @property
    def unique_id(self) -> str:
        return f"{self.court_id}:{self.case_number or self.docket_number}"


class CourtListenerScraper:
    """Fetches opinions from CourtListener API."""

    def __init__(self, api_token: str = ""):
        self.api_token = api_token or os.environ.get("COURTLISTENER_API_TOKEN", "")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        })
        if self.api_token:
            self.session.headers["Authorization"] = f"Token {self.api_token}"
        self.cutoff_date = datetime.now() - timedelta(days=LOOKBACK_DAYS)

    def scrape_all_courts(self) -> list[Opinion]:
        """Fetch recent opinions from all configured Florida courts."""
        all_opinions = []

        for court_id, court_config in COURTS.items():
            try:
                logger.info(f"Fetching {court_config['name']}...")
                opinions = self._fetch_court_opinions(court_id, court_config)
                all_opinions.extend(opinions)
                logger.info(f"  Found {len(opinions)} opinions from {court_config['short_name']}")
                time.sleep(0.5)  # Rate limiting
            except Exception as e:
                logger.error(f"  Error fetching {court_config['name']}: {e}")

        logger.info(f"Total opinions fetched: {len(all_opinions)}")
        return all_opinions

    def _fetch_court_opinions(self, court_id: str, config: dict) -> list[Opinion]:
        """Fetch opinions for a single court using the opinion-clusters endpoint."""
        opinions = []
        cl_court_id = config["cl_id"]
        date_after = self.cutoff_date.strftime("%Y-%m-%d")

        # Use the search endpoint with type=o for opinions
        # This is the best-documented endpoint for court filtering
        url = f"{COURTLISTENER_API_BASE}/search/"
        params = {
            "type": "o",  # opinions
            "court": cl_court_id,
            "filed_after": date_after,
            "order_by": "dateFiled desc",
            "format": "json",
        }

        page_count = 0
        while url and page_count < 10:  # Safety limit: max 10 pages
            try:
                response = self.session.get(url, params=params if page_count == 0 else None, timeout=30)
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                if not results:
                    break

                for result in results:
                    opinion = self._parse_search_result(result, court_id, config)
                    if opinion:
                        opinions.append(opinion)

                # Follow pagination
                url = data.get("next")
                params = None  # Next URL already has params
                page_count += 1
                if url:
                    time.sleep(0.3)

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    logger.warning("  Rate limited — waiting 30 seconds...")
                    time.sleep(30)
                    continue
                elif e.response.status_code == 400:
                    logger.error(f"  400 Bad Request. Response: {e.response.text[:500]}")
                    break
                raise

        return opinions

    @staticmethod
    def _resolve_court(docket_number: str, default_court_id: str, default_config: dict) -> tuple[str, str]:
        """Determine actual court from docket number prefix (e.g., '1D24-1234' -> 1st DCA)."""
        docket = docket_number.strip().upper()
        for prefix, (full_name, short_name) in DCA_PREFIX_MAP.items():
            if docket.startswith(prefix):
                return full_name, prefix.lower()
        # Fallback to the config-provided court info
        return default_config["name"], default_court_id

    def _parse_search_result(self, result: dict, court_id: str, config: dict) -> Optional[Opinion]:
        """Parse a CourtListener search result into an Opinion."""
        try:
            # The search endpoint returns fields like caseName, dateFiled, docketNumber, etc.
            case_name = (
                result.get("caseName", "")
                or result.get("case_name", "")
                or result.get("caseNameShort", "")
                or result.get("case_name_short", "")
                or "Unknown"
            )
            date_filed = result.get("dateFiled", "") or result.get("date_filed", "")
            docket_number = result.get("docketNumber", "") or result.get("docket_number", "") or ""
            judges = result.get("judge", "") or result.get("judges", "") or ""
            citation = result.get("citation", [])
            status = result.get("status", "") or result.get("precedentialStatus", "") or ""

            # Resolve the actual court from docket number prefix
            actual_court_name, actual_court_id = self._resolve_court(docket_number, court_id, config)

            # Parse date
            date = datetime.now()
            if date_filed:
                try:
                    # Could be "YYYY-MM-DD" or "YYYY-MM-DDT..."
                    date = datetime.strptime(date_filed[:10], "%Y-%m-%d")
                except ValueError:
                    pass

            # Build the opinion page URL
            cluster_id = result.get("cluster_id", "") or result.get("id", "")
            slug = result.get("slug", "") or case_name.lower().replace(" ", "-")[:50]
            absolute_url = result.get("absolute_url", "")
            if absolute_url:
                page_url = f"https://www.courtlistener.com{absolute_url}"
            elif cluster_id:
                page_url = f"https://www.courtlistener.com/opinion/{cluster_id}/{slug}/"
            else:
                page_url = ""

            # Get download URL if available
            pdf_url = result.get("download_url", "") or ""
            if pdf_url and not pdf_url.startswith("http"):
                pdf_url = f"https://www.courtlistener.com{pdf_url}"

            # Get snippet/text if available
            text_content = result.get("snippet", "") or result.get("text", "") or ""

            # Build citation string
            citation_str = ""
            if isinstance(citation, list) and citation:
                citation_str = citation[0] if isinstance(citation[0], str) else str(citation[0])
            elif isinstance(citation, str):
                citation_str = citation

            # Opinion type
            opinion_type = ""
            if status:
                status_map = {
                    "Published": "Written Opinion",
                    "Unpublished": "Unpublished",
                    "Errata": "Errata",
                    "Separate": "Separate Opinion",
                    "In-chambers": "In-Chambers",
                    "Relating-to": "Relating-to",
                    "Unknown": "",
                }
                opinion_type = status_map.get(status, status)

            return Opinion(
                case_number=docket_number,
                case_name=case_name,
                court_id=actual_court_id,
                court_name=actual_court_name,
                date=date,
                opinion_type=opinion_type,
                pdf_url=pdf_url,
                page_url=page_url,
                text_content=text_content[:15000] if text_content else "",
                docket_number=docket_number,
                citation=citation_str,
                judges=judges,
            )
        except Exception as e:
            logger.debug(f"Error parsing search result: {e}")
            return None

    def _fetch_opinion_text(self, opinion_url: str) -> tuple[str, str]:
        """Fetch the text content of an individual opinion."""
        try:
            if not opinion_url.startswith("http"):
                opinion_url = f"https://www.courtlistener.com{opinion_url}"

            response = self.session.get(opinion_url, timeout=15)
            response.raise_for_status()
            data = response.json()

            text = (
                data.get("plain_text", "")
                or data.get("html", "")
                or data.get("html_lawbox", "")
                or data.get("html_columbia", "")
                or data.get("html_anon_2020", "")
                or ""
            )

            pdf_url = data.get("download_url", "") or ""
            if pdf_url and not pdf_url.startswith("http"):
                pdf_url = f"https://www.courtlistener.com{pdf_url}"

            return text, pdf_url
        except Exception as e:
            logger.debug(f"Error fetching opinion text: {e}")
            return "", ""

    def extract_pdf_text(self, opinion: Opinion, max_pages: int = 30) -> str:
        """Return existing text content (already fetched from API)."""
        return opinion.text_content


# Keep the same function signatures for compatibility with main.py
def scrape_opinions() -> list[Opinion]:
    """Main entry point: fetch all courts and return opinions."""
    scraper = CourtListenerScraper()
    return scraper.scrape_all_courts()


# Alias for backward compatibility
FloridaCourtScraper = CourtListenerScraper


if __name__ == "__main__":
    opinions = scrape_opinions()
    for op in opinions:
        print(f"[{op.court_name}] {op.case_number}: {op.case_name[:80]} ({op.date.strftime('%Y-%m-%d')})")
        if op.pdf_url:
            print(f"  PDF: {op.pdf_url}")
        if op.page_url:
            print(f"  URL: {op.page_url}")
        print()
