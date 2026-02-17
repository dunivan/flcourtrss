"""
Configuration for Florida Court Opinion Scraper
"""

# Court definitions with their scraping URLs
COURTS = {
    "florida_supreme_court": {
        "name": "Supreme Court of Florida",
        "short_name": "FLSC",
        "base_url": "https://supremecourt.flcourts.gov",
        "opinions_url": "https://supremecourt.flcourts.gov/content/download/opinion-search-results",
        "archive_url": "https://supremecourt.flcourts.gov/Opinions/Archived-Opinions",
        "recent_url": "https://supremecourt.flcourts.gov/case-information/opinions/most-recent-opinions",
    },
    "1dca": {
        "name": "First District Court of Appeal",
        "short_name": "1st DCA",
        "base_url": "https://1dca.flcourts.gov",
        "opinions_url": "https://1dca.flcourts.gov/Opinions",
        "recent_url": "https://1dca.flcourts.gov/Opinions/Most-Recent-Written-Opinions",
        "archive_url": "https://1dca.flcourts.gov/Opinions/Opinions-Archive",
    },
    "2dca": {
        "name": "Second District Court of Appeal",
        "short_name": "2nd DCA",
        "base_url": "https://2dca.flcourts.gov",
        "opinions_url": "https://2dca.flcourts.gov/Opinions",
        "recent_url": "https://2dca.flcourts.gov/Opinions/Most-Recent-Written-Opinions",
        "archive_url": "https://2dca.flcourts.gov/Opinions/Opinions-Archive",
    },
    "3dca": {
        "name": "Third District Court of Appeal",
        "short_name": "3rd DCA",
        "base_url": "https://3dca.flcourts.gov",
        "opinions_url": "https://3dca.flcourts.gov/Opinions",
        "recent_url": "https://3dca.flcourts.gov/Opinions/Most-Recent-Opinion-Release",
        "archive_url": "https://3dca.flcourts.gov/Opinions/Opinions-Archive",
    },
    "4dca": {
        "name": "Fourth District Court of Appeal",
        "short_name": "4th DCA",
        "base_url": "https://4dca.flcourts.gov",
        "opinions_url": "https://4dca.flcourts.gov/Opinions",
        "recent_url": "https://4dca.flcourts.gov/Opinions/Most-Recent-Written-Opinions",
        "archive_url": "https://4dca.flcourts.gov/Opinions/Opinions-Archive",
    },
    "5dca": {
        "name": "Fifth District Court of Appeal",
        "short_name": "5th DCA",
        "base_url": "https://5dca.flcourts.gov",
        "opinions_url": "https://5dca.flcourts.gov/Opinions",
        "recent_url": "https://5dca.flcourts.gov/Opinions/Most-Recent-Written-Opinions",
        "archive_url": "https://5dca.flcourts.gov/Opinions/Opinions-Archive",
    },
    "6dca": {
        "name": "Sixth District Court of Appeal",
        "short_name": "6th DCA",
        "base_url": "https://6dca.flcourts.gov",
        "opinions_url": "https://6dca.flcourts.gov/Opinions",
        "recent_url": "https://6dca.flcourts.gov/Opinions/Most-Recent-Written-Opinions",
        "archive_url": "https://6dca.flcourts.gov/Opinions/Opinions-Archive",
    },
}

# Archive URL parameters (common pattern across DCA courts)
ARCHIVE_PARAMS = {
    "sort": "opinion/disposition_date desc, opinion/type Asc, opinion/case_number asc",
    "view": "embed_custom",
    "searchtype": "opinions",
    "limit": "25",
    "offset": "0",
}

# PDF media base URL
PDF_MEDIA_BASE = "https://flcourts-media.flcourts.gov/content/download"

# RSS feed settings
RSS_TITLE = "Florida Appellate Court Opinions"
RSS_DESCRIPTION = "Daily summaries of new opinions from Florida's Supreme Court and District Courts of Appeal"
RSS_LINK = "https://flcourts.gov"
RSS_LANGUAGE = "en"

# How many days back to look for opinions
LOOKBACK_DAYS = 7

# User agent for requests
USER_AGENT = "FloridaCourtOpinionScraper/1.0 (RSS Feed Generator)"
