# Implementation Details

## Overview

This document describes the implementation of the Loyalty Program Web-Scraping & Structuring Pipeline - a system designed to extract structured loyalty program data from F&B brand websites.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  seeds.csv  │ ──▶ │   Fetcher   │ ──▶ │    Parser    │ ──▶ │ Classifier  │
│   (URLs)    │     │ (HTTP/Play) │     │ (BeautifulSoup)│    │  (OpenAI)   │
└─────────────┘     └─────────────┘     └──────────────┘     └─────────────┘
                           │                    │                    │
                           ▼                    ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
                    │  raw/*.html │     │  Parsed     │     │ structured/ │
                    │             │     │  Content    │     │   *.json    │
                    └─────────────┘     └─────────────┘     └─────────────┘
```

## Components Implemented

### 1. Fetcher Module (`fetcher.py`)

**Purpose:** Retrieve HTML content from URLs with reliability and stealth.

**Features:**
- **Dual fetching modes:**
  - `requests` library for standard HTTP (default)
  - `Playwright` for JavaScript-rendered pages
- **User-Agent rotation** to avoid bot detection
- **Retry logic** with exponential backoff
- **Configurable timeouts** (15s default)

**Key Functions:**
```python
def fetch_url(url: str, use_playwright: bool = False) -> Tuple[str, int]:
    """Fetch URL content, returns (html, status_code)"""

def fetch_with_requests(url: str) -> Tuple[str, int]:
    """Standard HTTP fetch with rotating User-Agents"""

def fetch_with_playwright(url: str) -> Tuple[str, int]:
    """Headless browser fetch for JS-heavy sites"""
```

### 2. Parser Module (`parser.py`)

**Purpose:** Extract meaningful text content from raw HTML.

**Features:**
- **Content extraction:**
  - Headings (H1-H4)
  - Paragraphs
  - Lists (ul, ol)
  - Tables
  - JSON-LD structured data
  - Meta descriptions
- **Noise removal:** Strips scripts, styles, nav, footer, ads
- **Text cleaning:** Normalizes whitespace, removes empty elements

**Key Functions:**
```python
def parse_html(html: str, url: str) -> ParsedContent:
    """Parse HTML and return structured content"""

def extract_json_ld(soup: BeautifulSoup) -> List[dict]:
    """Extract JSON-LD structured data if present"""

def remove_unwanted_elements(soup: BeautifulSoup) -> None:
    """Remove scripts, styles, navigation, etc."""
```

**Output Schema (`ParsedContent`):**
```python
class ParsedContent(BaseModel):
    url: str
    title: str
    meta_description: str
    headings: List[str]
    paragraphs: List[str]
    lists: List[str]
    tables: List[str]
    json_ld: List[dict]
    raw_text: str
```

### 3. Classifier Module (`classifier.py`)

**Purpose:** Use LLM to extract structured loyalty program data from parsed content.

**Features:**
- **OpenAI GPT-4o-mini** integration
- **Structured JSON output** with retry logic
- **Detailed system prompt** for loyalty program extraction
- **Error handling** for API failures and malformed responses

**Key Functions:**
```python
def classify(parsed: ParsedContent, brand: str, model: str = "gpt-4o-mini") -> LoyaltyProgram:
    """Classify parsed content into structured loyalty program"""

def classify_with_openai(text: str, brand: str, url: str, model: str) -> dict:
    """Call OpenAI API with loyalty extraction prompt"""

def build_loyalty_program(data: dict, brand: str, url: str, raw_length: int) -> LoyaltyProgram:
    """Build Pydantic model from LLM response"""
```

**LLM Prompt Strategy:**
The classifier uses a detailed system prompt that instructs the LLM to extract:
- Program name and region
- Earning rules (points per dollar, conditions, channels)
- Redemption rules (points required, rewards)
- Membership tiers with thresholds
- Benefits and perks
- Expiry policies
- Eligibility requirements
- Signup bonuses
- Channel availability
- Limitations and restrictions
- FAQs

### 4. Schemas Module (`schemas.py`)

**Purpose:** Define Pydantic models for type-safe data handling.

**Models:**

```python
class EarningRule(BaseModel):
    action: str                    # "Purchase", "Signup", etc.
    points_earned: str             # "1 Star per $1"
    conditions: Optional[str]      # "Minimum $5 purchase"
    channels: List[str]            # ["app", "web", "in-store"]

class RedemptionRule(BaseModel):
    points_required: str           # "150 Stars"
    reward: str                    # "Free drink"
    conditions: Optional[str]

class Tier(BaseModel):
    name: str                      # "Gold", "Platinum"
    threshold: Optional[str]       # "300 Stars/year"
    benefits: List[str]

class Benefit(BaseModel):
    name: str                      # "Free birthday reward"
    description: Optional[str]
    tier_required: Optional[str]

class ExpiryPolicy(BaseModel):
    points_expiry: Optional[str]   # "6 months of inactivity"
    tier_expiry: Optional[str]
    conditions: Optional[str]

class LoyaltyProgram(BaseModel):
    brand: str
    program_name: Optional[str]
    url: str
    region: Optional[str]
    earning_rules: List[EarningRule]
    redemption_rules: List[RedemptionRule]
    tiers: List[Tier]
    benefits: List[Benefit]
    expiry_policy: Optional[ExpiryPolicy]
    eligibility: Optional[str]
    signup_bonus: Optional[str]
    channels: List[str]
    limitations: List[str]
    faqs: List[str]
    scraped_at: datetime
    raw_text_length: int
```

### 5. Main Pipeline (`loyalty_scraper.py`)

**Purpose:** Orchestrate the entire scraping pipeline.

**Features:**
- **Timestamped run folders** for organized output
- **Progress tracking** with colored console output
- **Error handling** with detailed logging
- **Multiple output formats:** Individual JSON, combined JSONL, summary
- **Configurable delays** between requests

**Pipeline Flow:**
1. Load URLs from CSV
2. Create timestamped output folder
3. For each URL:
   - Fetch HTML content
   - Save raw HTML
   - Parse with BeautifulSoup
   - Classify with LLM (optional)
   - Save structured JSON
4. Generate combined outputs
5. Save run summary

**Output Organization:**
```
output/run_YYYYMMDD_HHMMSS/
├── raw/                    # Raw HTML files
├── structured/             # Per-brand JSON
├── combined/
│   ├── all_programs.json   # Array of all programs
│   └── all_programs.jsonl  # Line-delimited JSON
└── run_summary.json        # Statistics and errors
```

## Data Flow Example

**Input (seeds.csv):**
```csv
brand,category,url
Starbucks,rewards,https://www.starbucks.com/rewards/terms
```

**Step 1 - Fetch:** Raw HTML (249KB)

**Step 2 - Parse:**
```json
{
  "headings": ["Starbucks Rewards Terms", "Earning Stars", ...],
  "paragraphs": ["Earn 1 Star per $1...", ...],
  "lists": ["Free birthday drink", "Free refills", ...]
}
```

**Step 3 - Classify (LLM):**
```json
{
  "brand": "Starbucks",
  "program_name": "Starbucks Rewards",
  "earning_rules": [{
    "action": "Purchase with registered card",
    "points_earned": "1-3 Stars per $1",
    "channels": ["app", "web", "in-store"]
  }],
  "expiry_policy": {
    "points_expiry": "6 months of inactivity"
  }
}
```

## Technologies Used

| Component | Technology | Purpose |
|-----------|------------|---------|
| HTTP Client | `requests` | Standard web fetching |
| Browser Automation | `playwright` | JS-rendered pages |
| HTML Parsing | `beautifulsoup4` | Content extraction |
| Data Validation | `pydantic` | Type-safe schemas |
| LLM | `openai` (GPT-4o-mini) | Structured extraction |
| Config | `python-dotenv` | Environment variables |

## Results Summary

**Test Run (November 27, 2025):**

| Brand | Status | Data Extracted |
|-------|--------|----------------|
| Starbucks | ✅ Success | Full program: Stars, tiers, expiry, eligibility |
| Zomato Gold | ✅ Success | Benefits, delivery terms, limitations |
| Chipotle | ✅ Success | Rewards, signup bonus, expiry policy |
| Dominos | ✅ Success | Page fetched (minimal content on page) |
| Swiggy | ❌ 404 | URL needs updating |
| PizzaHut | ❌ Timeout | Heavy bot protection |

**Key Metrics:**
- Success rate: 5/7 URLs (71%)
- Average fetch time: 2-8 seconds
- LLM processing: ~3-5 seconds per page
- Total run time: ~2 minutes for 7 URLs

## Known Limitations

1. **Bot Detection:** Some sites (PizzaHut, Chipotle main page) block automated requests
2. **JS-Heavy Sites:** Playwright helps but can be slower and sometimes blocked
3. **Dynamic Content:** Single-page apps may not fully render
4. **Rate Limiting:** Need delays between requests to avoid blocks
5. **Content Variability:** LLM extraction quality depends on page structure

## Future Enhancements (Phase 2+)

1. **Proxy rotation** for better anonymity
2. **Stealth Playwright** with anti-detection
3. **Redis caching** for parsed content
4. **Scheduled runs** with change detection
5. **Multi-language support**
6. **API endpoint** for on-demand scraping
7. **Dashboard** for monitoring and results
