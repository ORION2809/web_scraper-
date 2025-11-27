# Loyalty Program Web Scraper

A Python-based web scraper that extracts structured loyalty program data from F&B brand websites using LLM-powered classification.

## Quick Start

### 1. Install Dependencies

```bash
pip install requests beautifulsoup4 pydantic openai python-dotenv playwright
```

For JavaScript-heavy sites (optional):
```bash
playwright install chromium
```

### 2. Configure API Key

Create a `.env` file in the project root:
```
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Run the Scraper

**Basic usage:**
```bash
python loyalty_scraper.py -i seeds.csv -o output
```

**With custom delay between requests:**
```bash
python loyalty_scraper.py -i seeds.csv -o output --delay 2
```

**Using Playwright for JS-rendered pages:**
```bash
python loyalty_scraper.py -i seeds.csv -o output --use-playwright
```

**Skip LLM classification (fetch & parse only):**
```bash
python loyalty_scraper.py -i seeds.csv -o output --skip-llm
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `-i, --input` | Input CSV file with URLs | `seeds.csv` |
| `-o, --output` | Output directory | `output` |
| `--delay` | Delay between requests (seconds) | `1` |
| `--use-playwright` | Use Playwright for JS-heavy sites | `False` |
| `--skip-llm` | Skip LLM classification | `False` |

## Input Format (seeds.csv)

CSV file with columns:
```csv
brand,category,url
Starbucks,rewards,https://www.starbucks.com/rewards
Zomato,membership,https://www.zomato.com/gold
```

## Output Structure

Each run creates a timestamped folder:
```
output/
└── run_20251127_123750/
    ├── raw/                    # Raw HTML files
    │   ├── starbucks_rewards.html
    │   └── zomato_membership.html
    ├── structured/             # Individual JSON files
    │   ├── starbucks.json
    │   └── zomato.json
    ├── combined/               # Aggregated outputs
    │   ├── all_programs.json
    │   └── all_programs.jsonl
    └── run_summary.json        # Run statistics
```

## Output Schema

Each extracted loyalty program includes:

```json
{
  "brand": "Starbucks",
  "program_name": "Starbucks Rewards",
  "url": "https://www.starbucks.com/rewards",
  "region": "USA",
  "earning_rules": [
    {
      "action": "Purchase",
      "points_earned": "1-3 Stars per $1",
      "conditions": "Varies by payment method",
      "channels": ["app", "web", "in-store"]
    }
  ],
  "redemption_rules": [...],
  "tiers": [...],
  "benefits": [...],
  "expiry_policy": {...},
  "eligibility": "Age 13+",
  "signup_bonus": "Free drink",
  "channels": ["app", "web", "in-store"],
  "limitations": [...],
  "faqs": [...]
}
```

## Examples

### Scrape a single brand
Create a CSV with one URL and run:
```bash
python loyalty_scraper.py -i single_brand.csv -o output
```

### Test without API costs
```bash
python loyalty_scraper.py -i seeds.csv -o output --skip-llm
```

### Debug JS-heavy sites
```bash
python loyalty_scraper.py -i seeds.csv -o output --use-playwright --delay 3
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Empty content | Try `--use-playwright` flag |
| Timeout errors | Increase `--delay` value |
| 403/Bot blocked | Site has anti-scraping protection |
| HTTP2 errors | Some sites block headless browsers |
| Missing API key | Check `.env` file exists with valid key |

## File Structure

```
web_scraper/
├── loyalty_scraper.py    # Main pipeline orchestrator
├── fetcher.py            # HTTP fetching (requests + Playwright)
├── parser.py             # HTML parsing with BeautifulSoup
├── classifier.py         # OpenAI LLM integration
├── schemas.py            # Pydantic data models
├── seeds.csv             # Input URLs
├── .env                  # API key (not in git)
└── output/               # Scraped data
```
