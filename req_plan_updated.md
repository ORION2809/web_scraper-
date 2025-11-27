# Loyalty Program Web-Scraping Pipeline

## TODAY'S DEMO SCOPE (Functional MVP – 1 Day)

**Goal:** Demonstrate a working end-to-end pipeline that scrapes loyalty program pages, parses content, classifies it via LLM, and outputs structured JSON.

### Deliverables for Today
- ✅ Seed list CSV with 3-5 F&B brands (Starbucks, Domino's, Zomato)
- ✅ Fetch layer using requests (+ optional Playwright fallback)
- ✅ Parse layer extracting headings, paragraphs, lists, tables, JSON-LD
- ✅ LLM classification stub (OpenAI API) returning structured loyalty JSON
- ✅ File-based output: raw HTML snapshots + structured JSONL per brand
- ❌ No database (Postgres deferred to Phase 2)
- ❌ No REST API (CLI-only for demo)
- ❌ No full normalization engine (LLM handles most transformation)

### Project Structure
```
web_scraper/
├── seeds.csv                 # Brand URLs to scrape
├── loyalty_scraper.py        # Main pipeline orchestrator
├── fetcher.py                # HTTP fetch with retry logic
├── parser.py                 # BeautifulSoup parsing utilities
├── classifier.py             # LLM prompt + OpenAI call
├── schemas.py                # Pydantic models for loyalty data
├── requirements.txt          # Python dependencies
├── output/
│   ├── raw/                  # Raw HTML snapshots
│   └── structured/           # Classified JSON output
└── README.md
```

### Run Command
```powershell
# Install dependencies
pip install -r requirements.txt

# Set OpenAI API key
$env:OPENAI_API_KEY = "your-key-here"

# Run the pipeline
python loyalty_scraper.py --input seeds.csv --output output/

# Run without LLM (parse-only mode for testing)
python loyalty_scraper.py --input seeds.csv --output output/ --skip-llm
```

---

## FULL PHASE-1 PLAN (Reference – 3-4 Weeks)

### 1. Objective
Build an MVP pipeline that reliably extracts public-facing loyalty program information from targeted food & beverage brands, converts it into structured data using LLM classification, and stores the normalized output.

### 2. Scope
- **Target:** 20–30 F&B brands (Starbucks, McDonald's, Domino's, KFC, Zomato, Swiggy, BigBasket, etc.)
- **Extract:** Earn rules, burn rules, tiers, expiry, benefits, terms
- **No:** Login flows, mobile app APIs, hidden program mechanics
- **Output:** Structured JSON based on unified loyalty schema

### 3. Pipeline Architecture

| Layer | Today | Phase 1 |
|-------|-------|---------|
| **Fetch** | requests + retry | Playwright for JS-heavy sites |
| **Parse** | BeautifulSoup headings/paragraphs/tables | + JSON-LD, cookie banner removal |
| **Classify** | Single OpenAI call per page | Chunked + semantic deduplication |
| **Normalize** | LLM inline | Dedicated normalization engine |
| **Storage** | JSON files | Postgres (Neon) |
| **API** | CLI only | FastAPI endpoints |

### 4. Classification Categories
- Earning rules
- Redemption rules
- Tier structure
- Member benefits
- Eligibility criteria
- Expiry logic
- Channels
- Limitations
- Signup bonuses
- FAQs

### 5. Timeline

| When | What |
|------|------|
| **Today** | Functional demo with 3-5 brands, CLI output, LLM classification |
| Week 1 | Playwright integration + expand to 10 brands |
| Week 2 | Parser tuning + prompt optimization |
| Week 3 | Postgres storage + normalization |
| Week 4 | API + Builder integration + remaining brands |

### 6. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| JS-heavy pages | Playwright fallback (Phase 2) |
| Layout changes | Version snapshots + retry |
| Anti-bot throttling | Low-frequency + manual seeds |
| Inconsistent formats | LLM normalization |
| Legal exposure | Respect robots.txt |
