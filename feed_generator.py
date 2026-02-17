"""
RSS Feed Generator for Florida Court Opinions

Generates a valid RSS 2.0 / Atom feed from scraped and summarized opinions.
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from feedgen.feed import FeedGenerator

from config import RSS_TITLE, RSS_DESCRIPTION, RSS_LINK, RSS_LANGUAGE
from scraper import Opinion

logger = logging.getLogger(__name__)


def generate_feed(
    opinions: list[Opinion],
    output_dir: str = "docs",
    github_pages_url: str = "",
) -> str:
    """
    Generate RSS and Atom feeds from a list of opinions.

    Args:
        opinions: List of Opinion objects (ideally with summaries)
        output_dir: Directory to write the feed files
        github_pages_url: Base URL for GitHub Pages (e.g., https://username.github.io/repo-name)

    Returns:
        Path to the generated RSS feed file
    """
    fg = FeedGenerator()

    feed_url = f"{github_pages_url}/feed.xml" if github_pages_url else "feed.xml"
    atom_url = f"{github_pages_url}/atom.xml" if github_pages_url else "atom.xml"

    fg.id(github_pages_url or "https://github.com/florida-court-opinions")
    fg.title(RSS_TITLE)
    fg.description(RSS_DESCRIPTION)
    fg.link(href=RSS_LINK, rel="alternate")
    fg.link(href=feed_url, rel="self")
    fg.language(RSS_LANGUAGE)
    fg.lastBuildDate(datetime.now(timezone.utc))
    fg.generator("Florida Court Opinion Scraper")

    # Sort opinions by date (newest first)
    opinions_sorted = sorted(opinions, key=lambda o: o.date, reverse=True)

    for opinion in opinions_sorted:
        fe = fg.add_entry()
        fe.id(opinion.unique_id)
        fe.title(f"[{opinion.court_name}] {opinion.case_number} — {opinion.case_name[:150]}")

        # Build description
        description_parts = []
        if opinion.summary:
            description_parts.append(opinion.summary)
        if opinion.opinion_type:
            description_parts.append(f"<p><strong>Opinion Type:</strong> {opinion.opinion_type}</p>")
        if opinion.lower_tribunal:
            description_parts.append(
                f"<p><strong>Lower Tribunal:</strong> {opinion.lower_tribunal}</p>"
            )
        description_parts.append(f"<p><strong>Court:</strong> {opinion.court_name}</p>")
        description_parts.append(
            f"<p><strong>Case Number:</strong> {opinion.case_number}</p>"
        )
        description_parts.append(
            f"<p><strong>Date:</strong> {opinion.date.strftime('%B %d, %Y')}</p>"
        )
        if opinion.pdf_url:
            description_parts.append(
                f'<p><a href="{opinion.pdf_url}">View Full Opinion (PDF)</a></p>'
            )

        fe.description("\n".join(description_parts))

        # Link to PDF if available, otherwise to page
        if opinion.pdf_url:
            fe.link(href=opinion.pdf_url)
        elif opinion.page_url:
            fe.link(href=opinion.page_url)

        # Set date with timezone
        pub_date = opinion.date.replace(tzinfo=timezone.utc)
        fe.published(pub_date)
        fe.updated(pub_date)

        # Categories
        fe.category(term=opinion.court_name)
        if opinion.opinion_type:
            fe.category(term=opinion.opinion_type)

        # Author
        fe.author(name=opinion.court_name)

    # Write output files
    os.makedirs(output_dir, exist_ok=True)

    rss_path = os.path.join(output_dir, "feed.xml")
    atom_path = os.path.join(output_dir, "atom.xml")

    fg.rss_file(rss_path, pretty=True)
    fg.atom_file(atom_path, pretty=True)

    logger.info(f"RSS feed written to {rss_path}")
    logger.info(f"Atom feed written to {atom_path}")

    # Also generate a simple HTML index page
    _generate_index_html(opinions_sorted, output_dir, github_pages_url)

    return rss_path


def _generate_index_html(opinions: list[Opinion], output_dir: str, github_pages_url: str):
    """Generate a simple HTML index page for the feed."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{RSS_TITLE}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem 1rem;
            background: #fafafa;
            color: #333;
        }}
        header {{
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 2px solid #1a365d;
        }}
        h1 {{
            color: #1a365d;
            font-size: 1.8rem;
            margin-bottom: 0.5rem;
        }}
        .subtitle {{
            color: #666;
            font-size: 0.95rem;
        }}
        .feed-links {{
            margin: 1rem 0;
            padding: 1rem;
            background: #e8f0fe;
            border-radius: 8px;
        }}
        .feed-links a {{
            color: #1a365d;
            margin-right: 1.5rem;
            text-decoration: none;
            font-weight: 500;
        }}
        .feed-links a:hover {{ text-decoration: underline; }}
        .opinion {{
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 1.25rem;
            margin-bottom: 1rem;
        }}
        .opinion:hover {{ border-color: #cbd5e0; }}
        .court-badge {{
            display: inline-block;
            background: #1a365d;
            color: white;
            font-size: 0.75rem;
            padding: 2px 8px;
            border-radius: 4px;
            margin-bottom: 0.5rem;
        }}
        .opinion h2 {{
            font-size: 1.1rem;
            color: #2d3748;
            margin-bottom: 0.5rem;
        }}
        .opinion h2 a {{
            color: inherit;
            text-decoration: none;
        }}
        .opinion h2 a:hover {{ color: #1a365d; }}
        .meta {{
            font-size: 0.85rem;
            color: #718096;
            margin-bottom: 0.75rem;
        }}
        .summary {{
            font-size: 0.95rem;
            line-height: 1.6;
            color: #4a5568;
        }}
        .date-group {{
            font-size: 1.1rem;
            font-weight: 600;
            color: #1a365d;
            margin: 1.5rem 0 0.75rem;
            padding-bottom: 0.25rem;
            border-bottom: 1px solid #e2e8f0;
        }}
        footer {{
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid #e2e8f0;
            text-align: center;
            color: #a0aec0;
            font-size: 0.85rem;
        }}
    </style>
</head>
<body>
    <header>
        <h1>{RSS_TITLE}</h1>
        <p class="subtitle">{RSS_DESCRIPTION}</p>
        <div class="feed-links">
            <a href="feed.xml">📰 RSS Feed</a>
            <a href="atom.xml">⚛️ Atom Feed</a>
        </div>
    </header>
    <main>
"""

    current_date = ""
    for opinion in opinions:
        date_str = opinion.date.strftime("%B %d, %Y")
        if date_str != current_date:
            current_date = date_str
            html += f'        <div class="date-group">{date_str}</div>\n'

        link = opinion.pdf_url or opinion.page_url or "#"
        html += f"""        <div class="opinion">
            <span class="court-badge">{opinion.court_name}</span>
            <h2><a href="{link}">{opinion.case_number} — {opinion.case_name[:150]}</a></h2>
            <div class="meta">
                {f"Type: {opinion.opinion_type} | " if opinion.opinion_type else ""}Case No. {opinion.case_number} | {date_str}
            </div>
            <div class="summary">{opinion.summary or "Summary not available."}</div>
        </div>
"""

    html += f"""    </main>
    <footer>
        <p>Updated {datetime.now().strftime("%B %d, %Y at %I:%M %p")} UTC</p>
        <p>Built with the Florida Court Opinion Scraper</p>
    </footer>
</body>
</html>"""

    index_path = os.path.join(output_dir, "index.html")
    with open(index_path, "w") as f:
        f.write(html)
    logger.info(f"Index page written to {index_path}")
