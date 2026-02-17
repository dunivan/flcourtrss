"""
Opinion Summarizer using Claude API

Generates concise, plain-language summaries of Florida appellate court opinions.
"""

import logging
import os
import time

from anthropic import Anthropic

from scraper import Opinion, FloridaCourtScraper

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = """You are a legal analyst who summarizes Florida appellate court opinions for a general legal audience.

For each opinion, provide a concise summary (3-5 sentences) that covers:
1. The key legal issue(s) in the case
2. The court's holding/decision
3. The practical significance or notable aspects of the ruling

Use clear, professional language. Avoid excessive legalese but don't oversimplify.
If the opinion is a Per Curiam Affirmed (PCA) with no written opinion, note that.
If you cannot determine the substance of the opinion from the text provided, say so briefly."""

SUMMARY_USER_PROMPT = """Summarize this Florida appellate court opinion:

Court: {court_name}
Case Number: {case_number}
Case Name: {case_name}
Date: {date}

Opinion Text (excerpt):
{text}"""


class OpinionSummarizer:
    """Summarizes court opinions using the Claude API."""

    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY must be set as an environment variable or passed directly"
            )
        self.client = Anthropic(api_key=self.api_key)
        self.model = model

    def summarize_opinion(self, opinion: Opinion, text: str = "") -> str:
        """Generate a summary for a single opinion."""
        if not text and not opinion.text_content:
            return f"[{opinion.court_name}] {opinion.case_number} — No opinion text available for summarization."

        content = text or opinion.text_content
        # Truncate to ~12k chars to stay within reasonable token limits
        if len(content) > 12000:
            content = content[:12000] + "\n\n[... remainder truncated for summarization ...]"

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                system=SUMMARY_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": SUMMARY_USER_PROMPT.format(
                            court_name=opinion.court_name,
                            case_number=opinion.case_number,
                            case_name=opinion.case_name,
                            date=opinion.date.strftime("%B %d, %Y"),
                            text=content,
                        ),
                    }
                ],
            )
            return message.content[0].text.strip()
        except Exception as e:
            logger.error(f"Error summarizing {opinion.case_number}: {e}")
            return f"Summary unavailable for {opinion.case_number}."

    def summarize_opinions(
        self, opinions: list[Opinion], scraper: FloridaCourtScraper | None = None
    ) -> list[Opinion]:
        """Summarize a list of opinions, extracting PDF text as needed."""
        if scraper is None:
            scraper = FloridaCourtScraper()

        total = len(opinions)
        for i, opinion in enumerate(opinions):
            logger.info(
                f"Summarizing [{i+1}/{total}]: {opinion.court_name} - {opinion.case_number}"
            )

            # Extract text if not already present
            if not opinion.text_content and opinion.pdf_url:
                opinion.text_content = scraper.extract_pdf_text(opinion)
                time.sleep(1)  # Rate limit PDF downloads

            # Generate summary
            opinion.summary = self.summarize_opinion(opinion)
            time.sleep(0.5)  # Rate limit API calls

        return opinions


def summarize_all(opinions: list[Opinion], api_key: str | None = None) -> list[Opinion]:
    """Convenience function to summarize a list of opinions."""
    summarizer = OpinionSummarizer(api_key=api_key)
    return summarizer.summarize_opinions(opinions)
