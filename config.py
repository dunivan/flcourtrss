"""
Configuration for Florida Court Opinion Scraper
Uses CourtListener API as the data source.
"""

# CourtListener API base URL
COURTLISTENER_API_BASE = "https://www.courtlistener.com/api/rest/v4"

# CourtListener court IDs for Florida appellate courts
COURTS = {
    "fla": {
        "name": "Supreme Court of Florida",
        "short_name": "FLSC",
        "cl_id": "fla",
    },
    "fladistctapp1": {
        "name": "First District Court of Appeal",
        "short_name": "1st DCA",
        "cl_id": "fladistctapp1",
    },
    "fladistctapp2": {
        "name": "Second District Court of Appeal",
        "short_name": "2nd DCA",
        "cl_id": "fladistctapp2",
    },
    "fladistctapp3": {
        "name": "Third District Court of Appeal",
        "short_name": "3rd DCA",
        "cl_id": "fladistctapp3",
    },
    "fladistctapp4": {
        "name": "Fourth District Court of Appeal",
        "short_name": "4th DCA",
        "cl_id": "fladistctapp4",
    },
    "fladistctapp5": {
        "name": "Fifth District Court of Appeal",
        "short_name": "5th DCA",
        "cl_id": "fladistctapp5",
    },
    "fladistctapp": {
        "name": "Sixth District Court of Appeal",
        "short_name": "6th DCA",
        "cl_id": "fladistctapp",
    },
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
