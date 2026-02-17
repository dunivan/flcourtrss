# Florida Court Opinion RSS Feed

Automatically scrapes new opinions from all 7 Florida appellate courts, generates AI-powered summaries using Claude, and publishes an RSS feed via GitHub Pages.

## Courts Covered

| Court | Schedule |
|-------|----------|
| Supreme Court of Florida | Typically Thursdays at 11:00 AM |
| 1st District Court of Appeal | Wed & Fri at 11:00 AM |
| 2nd District Court of Appeal | Wed & Fri at 11:00 AM |
| 3rd District Court of Appeal | Varies |
| 4th District Court of Appeal | Wed 10:30 AM (written), Thu 10:30 AM (PCA) |
| 5th District Court of Appeal | Fridays before noon |
| 6th District Court of Appeal | Fri 11:00 AM (written), Tue 11:00 AM (PCA) |

## Quick Start

### 1. Create a GitHub Repository

```bash
git init fl-court-opinions
cd fl-court-opinions
# Copy all project files here
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/fl-court-opinions.git
git push -u origin main
```

### 2. Enable GitHub Pages

1. Go to **Settings → Pages** in your repository
2. Under **Source**, select **GitHub Actions**

### 3. Add Your Anthropic API Key

1. Go to **Settings → Secrets and variables → Actions**
2. Click **New repository secret**
3. Name: `ANTHROPIC_API_KEY`
4. Value: Your Anthropic API key

### 4. Run It

The workflow runs automatically **daily at 3:00 PM ET** (Mon–Fri). You can also trigger it manually:

1. Go to **Actions → Scrape FL Court Opinions & Publish Feed**
2. Click **Run workflow**

### 5. Subscribe to the Feed

Once deployed, your feeds will be at:

- **RSS**: `https://YOUR_USERNAME.github.io/fl-court-opinions/feed.xml`
- **Atom**: `https://YOUR_USERNAME.github.io/fl-court-opinions/atom.xml`
- **Web**: `https://YOUR_USERNAME.github.io/fl-court-opinions/`

Add the RSS URL to any feed reader (Feedly, Inoreader, NetNewsWire, etc.).

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run with summarization
export ANTHROPIC_API_KEY="your-key-here"
python main.py

# Run without summarization
python main.py --no-summarize

# Custom lookback window
python main.py --lookback 14
```

## Configuration

Edit `config.py` to customize:

- `LOOKBACK_DAYS`: How many days back to scrape (default: 7)
- `RSS_TITLE` / `RSS_DESCRIPTION`: Feed metadata
- Court URLs and parameters

## Project Structure

```
├── .github/workflows/
│   └── scrape-and-publish.yml   # GitHub Actions workflow
├── config.py                     # Court URLs and settings
├── scraper.py                    # Web scraper for all 7 courts
├── summarizer.py                 # Claude API summarization
├── feed_generator.py             # RSS/Atom feed + HTML generation
├── main.py                       # Main orchestrator script
├── requirements.txt              # Python dependencies
└── README.md
```

## How It Works

1. **Scrape**: Visits each court's opinion page and extracts case metadata (case number, name, date, PDF link)
2. **Deduplicate**: Compares against previously seen opinions (stored in `state.json`)
3. **Summarize**: Downloads new opinion PDFs, extracts text, and sends to Claude for plain-language summaries
4. **Generate**: Creates RSS 2.0, Atom, and HTML feeds in the `docs/` directory
5. **Publish**: GitHub Actions deploys the `docs/` folder to GitHub Pages

## Cost Estimate

Each opinion summary uses roughly 3,000–5,000 input tokens and ~200 output tokens. With ~50–100 new opinions per week across all courts, expect approximately:

- ~300K–500K input tokens/week
- ~10K–20K output tokens/week
- **Roughly $1–3/month** on Claude Sonnet

## Notes

- The scraper uses multiple parsing strategies (table-based, link-based, container-based) to handle the varying HTML structures across courts
- PDFs are downloaded temporarily for text extraction — they are not stored
- The `state.json` file is cached between GitHub Actions runs to avoid re-summarizing old opinions
- Rate limiting is built in (2s between courts, 1s between PDF downloads, 0.5s between API calls)
