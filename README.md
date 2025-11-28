# Loyalty Program Web Scraper

A Python-based web scraper that extracts structured loyalty program data from brand websites using LLM-powered classification. Features automatic URL discovery and anti-hallucination safeguards.

## Features

- **Auto-Discovery Mode**: Automatically finds loyalty program URLs from just a brand domain
- **Playwright Support**: Handles JavaScript-heavy sites with headless browser rendering
- **Anti-Hallucination**: Only extracts explicitly stated information, never invents data
- **Multi-Page Merging**: Combines data from multiple pages into a single comprehensive JSON
- **FastBite Rewards Schema**: Outputs structured JSON matching the FastBite Rewards format

## Quick Start

### 1. Install Dependencies

```bash
pip install requests beautifulsoup4 pydantic openai python-dotenv playwright
```

For JavaScript-heavy sites:
```bash
playwright install chromium
```

### 2. Configure API Key

Create a `.env` file in the project root:
```
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Run the Scraper

**Discovery Mode (Recommended)** - Automatically finds loyalty URLs:
```bash
python loyalty_scraper.py -i brands.csv -o output --discover --use-playwright
```

**Manual Mode** - Use specific URLs:
```bash
python loyalty_scraper.py -i seeds.csv -o output
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `-i, --input` | Input CSV file | `seeds.csv` |
| `-o, --output` | Output directory | `output` |
| `--discover` | Enable auto-discovery mode | `False` |
| `--max-urls` | Max URLs to scrape per brand (discovery mode) | `5` |
| `--delay` | Delay between requests (seconds) | `1` |
| `--use-playwright` | Use Playwright for JS-heavy sites | `False` |
| `--skip-llm` | Skip LLM classification | `False` |

## Input Formats

### Discovery Mode (brands.csv)
Simple brand + domain format:
```csv
brand,domain
Starbucks,starbucks.com
McDonalds,mcdonalds.com
Dunkin,dunkindonuts.com
```

### Manual Mode (seeds.csv)
Specific URLs with page types:
```csv
brand,url,page_type
Starbucks,https://www.starbucks.com/rewards,overview
Starbucks,https://www.starbucks.com/rewards/terms,terms
```

## Output Structure

Each run creates a timestamped folder:
```
output/
└── run_20251127_163937/
    ├── discovery/              # Discovered URLs (discovery mode)
    │   └── starbucks_urls.json
    ├── raw/                    # Raw HTML files
    │   ├── starbucks_terms_1.html
    │   └── starbucks_overview_2.html
    ├── pages/                  # Per-page extractions
    │   ├── starbucks_terms_1.json
    │   └── starbucks_overview_2.json
    ├── structured/             # Final merged JSON per brand
    │   └── starbucks.json
    ├── combined/               # All brands combined
    │   ├── all_programs.json
    │   └── all_programs.jsonl
    └── run_summary.json        # Run statistics
```

## Output Schema (FastBite Rewards Format)

```json
{
  "programName": "Starbucks® Rewards",
  "description": "Program description...",
  "strategy": {
    "industry": "Coffee",
    "programType": "B2C Customer Loyalty",
    "goals": [],
    "behaviors": ["Purchases"],
    "audience": [],
    "channels": ["Mobile app", "Website"]
  },
  "design": {
    "segments": [],
    "tiers": [],
    "incentives": [
      {
        "name": "Birthday Reward",
        "description": "Free item on your birthday"
      }
    ],
    "rewards": {
      "loyalty_points": {
        "points_per_dollar": "2 Stars for every $1"
      },
      "achievement_badges": [],
      "gift_cards": [],
      "catalog_products": [
        {"Name": "Beverage Modifiers", "point_cost": "25 Stars"},
        {"Name": "Hot coffee, tea, bakery", "point_cost": "100 Stars"},
        {"Name": "Handcrafted beverage", "point_cost": "200 Stars"},
        {"Name": "Lunch items", "point_cost": "300 Stars"},
        {"Name": "Merchandise", "point_cost": "400 Stars"}
      ]
    }
  },
  "brand": "Starbucks",
  "url": "starbucks.com",
  "scraped_at": "2025-11-27T11:11:53.191733"
}
```

## How Discovery Mode Works

1. **Sitemap Check**: Looks for `/sitemap.xml` and searches for loyalty-related URLs
2. **Common Path Probing**: Tests common paths like `/rewards`, `/loyalty`, `/points`, `/membership`
3. **Homepage Crawling**: Crawls the homepage to find links containing loyalty keywords
4. **Deduplication**: Removes duplicate URLs and limits to `--max-urls` per brand

Keywords used for discovery:
- reward, loyalty, points, member, tier, earn, redeem
- benefits, program, vip, club, gold, silver, platinum

## Examples

### Scrape Starbucks with auto-discovery
```bash
echo "brand,domain" > test.csv
echo "Starbucks,starbucks.com" >> test.csv
python loyalty_scraper.py -i test.csv -o output --discover --use-playwright --max-urls 3
```

### Scrape multiple brands
```bash
python loyalty_scraper.py -i brands.csv -o output --discover --use-playwright
```

### Test without API costs
```bash
python loyalty_scraper.py -i seeds.csv -o output --skip-llm
```

## Anti-Hallucination Rules

The LLM is strictly instructed to:
- ✅ Only extract information explicitly stated in the source text
- ✅ Use exact quotes from the source when possible
- ✅ Leave fields empty if information is not found
- ❌ Never invent tier names (like "Gold", "Silver") unless explicitly stated
- ❌ Never guess point values or earning rates
- ❌ Never fabricate benefits or rewards

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Empty content | Use `--use-playwright` for JS-heavy sites |
| Missing data | Increase `--max-urls` to scrape more pages |
| Timeout errors | Increase `--delay` value |
| 403/Bot blocked | Site has anti-scraping protection |
| Truncated text | Content limit is 25k chars per page |

## File Structure

```
web_scraper/
├── loyalty_scraper.py    # Main pipeline orchestrator
├── fetcher.py            # HTTP fetching (requests + Playwright)
├── parser.py             # HTML parsing with BeautifulSoup
├── classifier.py         # OpenAI LLM integration
├── schemas.py            # Pydantic data models
├── discovery.py          # URL auto-discovery module
├── config.py             # Centralized configuration
├── brands.csv            # Discovery mode input
├── seeds.csv             # Manual mode input
├── .env                  # API key (not in git)
└── output/               # Scraped data
```

## Version History

- **Stage 2** (b749992): Auto-discovery mode, Playwright visible text extraction, improved prompts
- **Stage 1** (ec378c0): Manual URL scraping with basic extraction
