#!/usr/bin/env python3
"""
Debug script: fetches each court's opinions page and dumps
the HTML structure so we can see what we're working with.

Run this locally:
    python debug_scraper.py

It will create a debug_output/ folder with:
- Raw HTML for each court page
- A summary of the HTML structure (tags, classes, links)
"""

import os
import re
import requests
from bs4 import BeautifulSoup
from config import COURTS

OUTPUT_DIR = "debug_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})

summary_lines = []

for court_id, config in COURTS.items():
    # Try the recent opinions URL first, fall back to opinions URL
    urls_to_try = []
    if "recent_url" in config:
        urls_to_try.append(("recent", config["recent_url"]))
        # Also try with ?searchtype=opinions
        urls_to_try.append(("recent_search", config["recent_url"] + "?searchtype=opinions"))
    if "archive_url" in config:
        urls_to_try.append(("archive", config["archive_url"]))
    if "opinions_url" in config:
        urls_to_try.append(("main", config["opinions_url"]))

    for label, url in urls_to_try:
        print(f"\n{'='*60}")
        print(f"[{court_id}] Fetching {label}: {url}")

        try:
            resp = session.get(url, timeout=30, allow_redirects=True)
            print(f"  Status: {resp.status_code}")
            print(f"  Content-Length: {len(resp.text)} chars")
            print(f"  Final URL: {resp.url}")

            # Save raw HTML
            filename = f"{court_id}_{label}.html"
            with open(os.path.join(OUTPUT_DIR, filename), "w") as f:
                f.write(resp.text)
            print(f"  Saved to {OUTPUT_DIR}/{filename}")

            # Parse and analyze structure
            soup = BeautifulSoup(resp.text, "lxml")

            # Find all tables
            tables = soup.find_all("table")
            print(f"  Tables found: {len(tables)}")
            for i, table in enumerate(tables):
                rows = table.find_all("tr")
                print(f"    Table {i}: {len(rows)} rows")
                if rows:
                    first_row = rows[0]
                    cells = first_row.find_all(["th", "td"])
                    print(f"      First row cells: {[c.get_text(strip=True)[:50] for c in cells]}")

            # Find all links with PDF or opinion-related hrefs
            pdf_links = soup.find_all("a", href=re.compile(r"(\.pdf|download|opinion)", re.I))
            print(f"  PDF/opinion links: {len(pdf_links)}")
            for link in pdf_links[:10]:
                print(f"    - href: {link.get('href', '')[:100]}")
                print(f"      text: {link.get_text(strip=True)[:80]}")

            # Find case number patterns in text
            all_text = soup.get_text()
            case_numbers = re.findall(r"(SC\d{4}-\d+|\d{4}-\d{2,5})", all_text)
            unique_cases = list(set(case_numbers))[:20]
            print(f"  Case number patterns found: {len(case_numbers)} total, {len(set(case_numbers))} unique")
            if unique_cases:
                print(f"    Examples: {unique_cases[:10]}")

            # Find divs/sections with opinion-related classes
            containers = soup.find_all(["div", "article", "section"], class_=True)
            opinion_containers = [
                c for c in containers
                if any(kw in str(c.get("class", [])).lower() for kw in
                       ["opinion", "case", "result", "item", "entry", "row", "view", "content", "field"])
            ]
            print(f"  Content containers with relevant classes: {len(opinion_containers)}")
            for c in opinion_containers[:10]:
                classes = c.get("class", [])
                text_preview = c.get_text(strip=True)[:100]
                print(f"    - <{c.name} class='{' '.join(classes)}'> {text_preview}")

            # Look for any iframes or AJAX indicators
            iframes = soup.find_all("iframe")
            scripts_with_ajax = [s for s in soup.find_all("script") if s.string and ("ajax" in s.string.lower() or "fetch" in s.string.lower() or "xmlhttp" in s.string.lower())]
            print(f"  Iframes: {len(iframes)}")
            print(f"  Scripts with AJAX/fetch: {len(scripts_with_ajax)}")

            summary_lines.append(f"\n[{court_id} - {label}] Status={resp.status_code}, Size={len(resp.text)}, Tables={len(tables)}, PDF links={len(pdf_links)}, Cases={len(set(case_numbers))}")

            # If we found data on this URL, don't need to try the other URLs
            if case_numbers or pdf_links:
                break

        except Exception as e:
            print(f"  ERROR: {e}")
            summary_lines.append(f"\n[{court_id} - {label}] ERROR: {e}")

print("\n\n" + "="*60)
print("SUMMARY")
print("="*60)
for line in summary_lines:
    print(line)
