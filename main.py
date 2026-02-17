#!/usr/bin/env python3
"""
Florida Court Opinion RSS Feed Generator

Main entry point that orchestrates:
1. Scraping opinions from all Florida appellate courts
2. Summarizing opinions using Claude API
3. Generating RSS/Atom feeds and an HTML index page

Usage:
    python main.py                          # Full run (scrape + summarize + generate feed)
    python main.py --no-summarize           # Skip AI summarization
    python main.py --output-dir ./docs      # Custom output directory
    python main.py --lookback 14            # Override lookback days
    python main.py --github-url https://user.github.io/repo  # Set GitHub Pages URL
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from config import LOOKBACK_DAYS
from scraper import scrape_opinions, FloridaCourtScraper
from summarizer import summarize_all
from feed_generator import generate_feed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def load_seen_opinions(state_file: str) -> set[str]:
    """Load previously seen opinion IDs to avoid re-processing."""
    if not os.path.exists(state_file):
        return set()
    try:
        with open(state_file) as f:
            data = json.load(f)
            return set(data.get("seen_ids", []))
    except Exception:
        return set()


def save_seen_opinions(state_file: str, seen_ids: set[str]):
    """Save seen opinion IDs for deduplication."""
    with open(state_file, "w") as f:
        json.dump({
            "seen_ids": list(seen_ids),
            "last_updated": datetime.now().isoformat(),
        }, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Florida Court Opinion RSS Feed Generator")
    parser.add_argument("--no-summarize", action="store_true", help="Skip AI summarization")
    parser.add_argument("--output-dir", default="docs", help="Output directory for feed files")
    parser.add_argument("--lookback", type=int, default=LOOKBACK_DAYS, help="Days to look back")
    parser.add_argument("--github-url", default="", help="GitHub Pages base URL")
    parser.add_argument("--state-file", default="state.json", help="State file for deduplication")
    parser.add_argument("--api-key", default="", help="Anthropic API key (or use ANTHROPIC_API_KEY env var)")
    args = parser.parse_args()

    # Override lookback if specified
    if args.lookback != LOOKBACK_DAYS:
        import config
        config.LOOKBACK_DAYS = args.lookback

    # Detect GitHub Pages URL from environment (GitHub Actions sets this)
    github_url = args.github_url or os.environ.get("GITHUB_PAGES_URL", "")

    logger.info("=" * 60)
    logger.info("Florida Court Opinion RSS Feed Generator")
    logger.info(f"Lookback: {args.lookback} days")
    logger.info(f"Output: {args.output_dir}")
    logger.info(f"Summarization: {'OFF' if args.no_summarize else 'ON'}")
    logger.info("=" * 60)

    # Step 1: Scrape opinions
    logger.info("\n📋 Step 1: Scraping opinions from all courts...")
    opinions = scrape_opinions()

    if not opinions:
        logger.warning("No opinions found. The feed will be empty.")
        # Still generate the feed (it'll be empty but valid)

    # Step 2: Deduplicate against previously seen opinions
    seen_ids = load_seen_opinions(args.state_file)
    new_opinions = [o for o in opinions if o.unique_id not in seen_ids]
    logger.info(f"Found {len(new_opinions)} new opinions (out of {len(opinions)} total)")

    # Update seen IDs
    for o in opinions:
        seen_ids.add(o.unique_id)
    save_seen_opinions(args.state_file, seen_ids)

    # Step 3: Summarize (if enabled)
    if not args.no_summarize and new_opinions:
        api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            logger.info(f"\n🤖 Step 2: Summarizing {len(new_opinions)} new opinions with Claude...")
            try:
                new_opinions = summarize_all(new_opinions, api_key=api_key)
            except Exception as e:
                logger.error(f"Summarization failed: {e}")
                logger.info("Continuing without summaries...")
        else:
            logger.warning("No ANTHROPIC_API_KEY found. Skipping summarization.")

    # Merge: use all opinions (new + previously seen with summaries from prior runs)
    # For feed generation, we use whatever we have
    all_feed_opinions = opinions  # Use all scraped opinions for the feed

    # Apply summaries from new_opinions to matching items in all_feed_opinions
    summary_map = {o.unique_id: o.summary for o in new_opinions if o.summary}
    for o in all_feed_opinions:
        if o.unique_id in summary_map:
            o.summary = summary_map[o.unique_id]

    # Step 4: Generate feeds
    logger.info(f"\n📰 Step 3: Generating RSS feed with {len(all_feed_opinions)} opinions...")
    feed_path = generate_feed(
        all_feed_opinions,
        output_dir=args.output_dir,
        github_pages_url=github_url,
    )

    logger.info("\n✅ Done!")
    logger.info(f"Feed: {feed_path}")
    logger.info(f"Index: {os.path.join(args.output_dir, 'index.html')}")

    # Print summary
    courts_found = set(o.court_name for o in all_feed_opinions)
    for court in sorted(courts_found):
        count = sum(1 for o in all_feed_opinions if o.court_name == court)
        logger.info(f"  {court}: {count} opinions")


if __name__ == "__main__":
    main()
