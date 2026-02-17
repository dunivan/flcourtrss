#!/usr/bin/env python3
"""
Debug script: uses Playwright to render each court's opinions page
and dumps the fully-rendered HTML structure.

Run via GitHub Actions (Debug Scraper workflow) or locally:
    pip install -r requirements.txt
    playwright install chromium
    python debug_scraper.py
"""

import os
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from config import COURTS

OUTPUT_DIR = "debug_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

summary_lines = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    page = context.new_page()

    for court_id, config in COURTS.items():
        urls_to_try = []
        if "recent_url" in config:
            urls_to_try.append(("recent", config["recent_url"]))
        if "archive_url" in config:
            urls_to_try.append(("archive", config["archive_url"]))

        for label, url in urls_to_try:
            print(f"\n{'='*60}")
            print(f"[{court_id}] Fetching {label}: {url}")

            try:
                page.goto(url, wait_until="networkidle", timeout=30000)

                # Wait for dynamic content
                try:
                    page.wait_for_selector(
                        "table, a[href*='download'], a[href*='.pdf'], [class*='opinion'], [class*='case']",
                        timeout=10000,
                    )
                    print("  ✓ Found expected content selectors")
                except Exception:
                    print("  ✗ No expected content selectors found after 10s")

                # Extra wait for lazy loading
                page.wait_for_timeout(3000)

                html = page.content()
                print(f"  Rendered HTML size: {len(html)} chars")

                # Save raw HTML
                filename = f"{court_id}_{label}.html"
                with open(os.path.join(OUTPUT_DIR, filename), "w") as f:
                    f.write(html)
                print(f"  Saved to {OUTPUT_DIR}/{filename}")

                # Parse and analyze
                soup = BeautifulSoup(html, "lxml")

                # Tables
                tables = soup.find_all("table")
                print(f"  Tables found: {len(tables)}")
                for i, table in enumerate(tables):
                    rows = table.find_all("tr")
                    print(f"    Table {i}: {len(rows)} rows")
                    for row in rows[:3]:
                        cells = row.find_all(["th", "td"])
                        print(f"      [{'/'.join(c.name for c in cells)}]: {[c.get_text(strip=True)[:60] for c in cells]}")

                # PDF / download links
                pdf_links = soup.find_all("a", href=re.compile(r"(\.pdf|/download/|/content/download)", re.I))
                print(f"  PDF/download links: {len(pdf_links)}")
                for link in pdf_links[:10]:
                    print(f"    href: {link.get('href', '')[:120]}")
                    print(f"    text: {link.get_text(strip=True)[:80]}")

                # Case numbers in text
                all_text = soup.get_text()
                case_numbers = list(set(re.findall(r"(SC\d{4}-\d+|\d{4}-\d{2,5})", all_text)))
                print(f"  Unique case numbers in text: {len(case_numbers)}")
                if case_numbers:
                    print(f"    Examples: {case_numbers[:15]}")

                # Content containers
                containers = soup.find_all(["div", "article", "section", "li"], class_=True)
                opinion_containers = [
                    c for c in containers
                    if any(kw in str(c.get("class", [])).lower() for kw in
                           ["opinion", "case", "result", "item", "entry", "row", "view", "content", "field", "record", "search"])
                ]
                print(f"  Relevant containers: {len(opinion_containers)}")
                for c in opinion_containers[:15]:
                    classes = c.get("class", [])
                    text_preview = c.get_text(strip=True)[:120]
                    print(f"    <{c.name} class='{' '.join(classes)}'> {text_preview}")

                # Check for iframes
                iframes = soup.find_all("iframe")
                if iframes:
                    print(f"  Iframes: {len(iframes)}")
                    for iframe in iframes:
                        print(f"    src: {iframe.get('src', 'no src')[:120]}")

                summary_lines.append(
                    f"[{court_id} - {label}] Size={len(html)}, Tables={len(tables)}, "
                    f"PDF links={len(pdf_links)}, Cases={len(case_numbers)}"
                )

                # If we found opinions, skip the archive URL
                if case_numbers or pdf_links:
                    break

            except Exception as e:
                print(f"  ERROR: {e}")
                summary_lines.append(f"[{court_id} - {label}] ERROR: {e}")

    browser.close()

print("\n\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
for line in summary_lines:
    print(line)
