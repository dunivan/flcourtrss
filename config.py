"""
Configuration for Florida Court Opinion Scraper
Uses CourtListener API as the data source.
"""

# CourtListener API base URL
COURTLISTENER_API_BASE = "https://www.courtlistener.com/api/rest/v4"

# CourtListener court IDs for Florida appellate courts
# Note: "fladistctapp" is a catch-all that returns opinions from ALL DCAs.
# Individual DCA IDs (fladistctapp1-5) return 0 results on the search endpoint,
# so we use the catch-all and parse the case number prefix to determine the actual court.
COURTS = {
    "fla": {
        "name": "Supreme Court of Florida",
        "short_name": "FLSC",
        "cl_id": "fla",
    },
    "fladistctapp": {
        "name": "District Courts of Appeal",
        "short_name": "DCA",
        "cl_id": "fladistctapp",
    },
}

# Mapping from case number prefix to actual court name/short name
DCA_PREFIX_MAP = {
    "1D": ("First District Court of Appeal", "1st DCA"),
    "2D": ("Second District Court of Appeal", "2nd DCA"),
    "3D": ("Third District Court of Appeal", "3rd DCA"),
    "4D": ("Fourth District Court of Appeal", "4th DCA"),
    "5D": ("Fifth District Court of Appeal", "5th DCA"),
    "6D": ("Sixth District Court of Appeal", "6th DCA"),
    "SC": ("Supreme Court of Florida", "FLSC"),
}

# RSS feed settings
RSS_TITLE = "Florida Appellate Court Opinions"
RSS_DESCRIPTION = "Daily summaries of new opinions from Florida's Supreme Court and District Courts of Appeal"
RSS_LINK = "https://www.courtlistener.com"
RSS_LANGUAGE = "en"

# How many days back to look for opinions
LOOKBACK_DAYS = 7

# User agent for requests
USER_AGENT = "FloridaCourtOpinionRSS/1.0 (GitHub Pages RSS Feed Generator)"
