# Stage 2: Automatic URL Discovery & Deep Crawling

## Overview

Stage 2 enhances the loyalty program scraper with **automatic URL discovery**. Instead of manually specifying URLs, you provide only the brand name and domain. The system automatically finds and crawls all loyalty-related pages to populate the complete JSON schema.

---

## Current State (Stage 1)

```
Input: Manual URLs in CSV
       ↓
Fetch → Parse → Classify → Output JSON
```

**Limitations:**
- Must manually find and specify each URL
- May miss important pages (T&Cs, FAQs, tier details)
- Incomplete data extraction

---

## Target State (Stage 2)

```
Input: Brand + Domain only
       ↓
Discovery → Fetch All → Parse → Classify → Merge → Complete JSON
```

**Benefits:**
- Automatic discovery of all loyalty-related pages
- Complete data extraction (tiers, earning, redemption, T&Cs)
- Minimal manual input required

---

## Architecture

### Phase 1: URL Discovery (`discovery.py`)

```
┌─────────────────────────────────────────────────────────────┐
│                    URL DISCOVERY                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. SITEMAP DISCOVERY                                       │
│     ├── Fetch /sitemap.xml                                  │
│     ├── Fetch /sitemap_index.xml                            │
│     ├── Parse all <loc> entries                             │
│     └── Filter URLs matching loyalty keywords               │
│                                                             │
│  2. COMMON PATH PROBING                                     │
│     ├── Try: /rewards, /loyalty, /membership, /points       │
│     ├── Try: /rewards/terms, /loyalty/faq, /rewards/tiers   │
│     └── Keep URLs that return 200 OK                        │
│                                                             │
│  3. HOMEPAGE CRAWL (Depth 2)                                │
│     ├── Fetch homepage                                      │
│     ├── Extract all internal links                          │
│     ├── Filter links matching loyalty keywords              │
│     ├── Follow filtered links (depth 1)                     │
│     ├── Extract more internal links                         │
│     └── Filter again for loyalty keywords                   │
│                                                             │
│  4. DEDUPLICATION & SCORING                                 │
│     ├── Merge all discovered URLs                           │
│     ├── Remove duplicates                                   │
│     ├── Score by keyword relevance                          │
│     └── Return top N most relevant URLs                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Phase 2: Batch Fetching

```
┌─────────────────────────────────────────────────────────────┐
│                    BATCH FETCHING                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  For each discovered URL:                                   │
│  ├── Check if JS-heavy (optional Playwright detection)      │
│  ├── Fetch with requests OR Playwright                      │
│  ├── Rate limit: 1-2 second delay between requests          │
│  ├── Handle errors gracefully (404, timeout, blocked)       │
│  └── Save raw HTML to output/raw/                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Phase 3: Parse & Classify

```
┌─────────────────────────────────────────────────────────────┐
│                 PARSE & CLASSIFY                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  For each fetched page:                                     │
│  ├── Parse HTML (headings, paragraphs, lists, tables)       │
│  ├── Classify page type:                                    │
│  │   ├── "overview" - main rewards landing page             │
│  │   ├── "terms" - terms and conditions                     │
│  │   ├── "faq" - frequently asked questions                 │
│  │   ├── "tiers" - tier/status level details                │
│  │   ├── "earn" - how to earn points                        │
│  │   ├── "redeem" - redemption catalog                      │
│  │   └── "other" - related but less relevant                │
│  ├── Extract data relevant to page type                     │
│  └── Save structured JSON per page                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Phase 4: Merge & Output

```
┌─────────────────────────────────────────────────────────────┐
│                   MERGE & OUTPUT                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Collect all page extractions for brand                  │
│  2. LLM merges data from multiple pages:                    │
│     ├── Combine tier information                            │
│     ├── Merge earning rules                                 │
│     ├── Consolidate redemption catalog                      │
│     ├── Include T&C details                                 │
│     └── Deduplicate overlapping info                        │
│  3. Validate against schema                                 │
│  4. Output complete JSON                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## New Input Format

### Before (Stage 1)
```csv
brand,url,page_type
Starbucks,https://www.starbucks.com/rewards,rewards
Starbucks,https://www.starbucks.com/rewards/terms,terms
Chipotle,https://www.chipotle.com/rewards,rewards
```

### After (Stage 2)
```csv
brand,domain
Starbucks,starbucks.com
Chipotle,chipotle.com
Dominos,dominos.com
Zomato,zomato.com
```

---

## Keyword Configuration

### URL Discovery Keywords
```python
LOYALTY_URL_KEYWORDS = [
    # Primary
    "reward", "rewards", "loyalty", "points", "member", "membership",
    # Tiers
    "tier", "tiers", "level", "levels", "status", "gold", "silver", 
    "platinum", "bronze", "vip", "elite", "premier",
    # Actions
    "earn", "earning", "redeem", "redemption", "collect",
    # Program names
    "program", "club", "perks", "benefits", "bonus",
    # Info pages
    "terms", "conditions", "faq", "how-it-works", "about",
]
```

### Common URL Paths to Probe
```python
COMMON_LOYALTY_PATHS = [
    "/rewards",
    "/loyalty", 
    "/membership",
    "/points",
    "/rewards/terms",
    "/rewards/faq",
    "/rewards/how-it-works",
    "/loyalty-program",
    "/member-rewards",
    "/club",
    "/perks",
    "/vip",
]
```

---

## New Module: `discovery.py`

### Functions

```python
def discover_loyalty_urls(domain: str, max_urls: int = 20) -> List[str]:
    """
    Main discovery function. Returns list of loyalty-related URLs.
    
    Args:
        domain: Brand domain (e.g., "starbucks.com")
        max_urls: Maximum URLs to return
        
    Returns:
        List of discovered loyalty-related URLs, sorted by relevance
    """

def fetch_sitemap(domain: str) -> List[str]:
    """
    Fetch and parse sitemap.xml, return all URLs.
    Handles sitemap index files (multiple sitemaps).
    """

def filter_urls_by_keywords(urls: List[str], keywords: List[str]) -> List[str]:
    """
    Filter URLs that contain any of the keywords in path or query.
    """

def probe_common_paths(domain: str) -> List[str]:
    """
    Try common loyalty URL paths, return those that return 200 OK.
    """

def crawl_for_links(url: str, depth: int = 2) -> List[str]:
    """
    Crawl page and extract internal links, optionally following to depth.
    """

def score_url_relevance(url: str) -> float:
    """
    Score URL by how many loyalty keywords it contains.
    Higher score = more relevant.
    """

def deduplicate_and_rank(urls: List[str], max_urls: int) -> List[str]:
    """
    Remove duplicates, score by relevance, return top N.
    """
```

### Example Usage

```python
from discovery import discover_loyalty_urls

# Discover all loyalty-related pages for Starbucks
urls = discover_loyalty_urls("starbucks.com", max_urls=15)

# Returns:
# [
#   "https://www.starbucks.com/rewards",
#   "https://www.starbucks.com/rewards/terms",
#   "https://www.starbucks.com/rewards/how-it-works",
#   "https://www.starbucks.com/rewards/mobile-apps",
#   "https://www.starbucks.com/rewards/credit-card",
#   ...
# ]
```

---

## Updated Pipeline: `loyalty_scraper.py`

### New Flow

```python
def run_pipeline_v2(brands_file: str, output_dir: str):
    """
    Stage 2 pipeline with automatic discovery.
    """
    brands = load_brands(brands_file)  # Now just brand,domain
    
    for brand, domain in brands:
        print(f"\n{'='*60}")
        print(f"Processing: {brand} ({domain})")
        print(f"{'='*60}")
        
        # PHASE 1: Discovery
        print("\n[Phase 1] Discovering loyalty URLs...")
        urls = discover_loyalty_urls(domain, max_urls=15)
        print(f"  Found {len(urls)} relevant URLs")
        
        # PHASE 2: Fetch all pages
        print("\n[Phase 2] Fetching pages...")
        pages = []
        for url in urls:
            html = fetch_page(url)
            if html:
                pages.append((url, html))
                save_raw_html(html, url, output_dir)
        
        # PHASE 3: Parse & Classify each page
        print("\n[Phase 3] Parsing & classifying...")
        extractions = []
        for url, html in pages:
            parsed = parse_html(html, url, brand)
            page_type = classify_page_type(parsed)
            extraction = extract_loyalty_data(parsed, page_type)
            extractions.append(extraction)
        
        # PHASE 4: Merge all extractions
        print("\n[Phase 4] Merging data...")
        complete_json = merge_extractions(brand, extractions)
        save_structured_json(complete_json, brand, output_dir)
        
        print(f"\n✓ {brand} complete!")
```

### New Merge Function

```python
def merge_extractions(brand: str, extractions: List[dict]) -> dict:
    """
    Use LLM to intelligently merge data from multiple page extractions.
    Handles deduplication and conflict resolution.
    """
    
    MERGE_PROMPT = """
    You have extracted loyalty program data from multiple pages of the same brand.
    Merge all the data into a single complete JSON.
    
    Rules:
    - Combine all tiers found across pages
    - Merge all catalog products (remove duplicates)
    - Use the most detailed description available
    - Include earning rates from all sources
    - Consolidate incentives/promotions
    - If there are conflicts, prefer data from "terms" or "overview" pages
    
    Extractions from {num_pages} pages:
    {extractions_json}
    
    Return a single merged JSON following the schema.
    """
    
    # Call LLM to merge
    merged = call_openai(MERGE_PROMPT.format(
        num_pages=len(extractions),
        extractions_json=json.dumps(extractions, indent=2)
    ))
    
    return merged
```

---

## Configuration Options

### `config.py` (new file)

```python
# Discovery settings
DISCOVERY_MAX_URLS = 15          # Max URLs to discover per brand
DISCOVERY_CRAWL_DEPTH = 2        # How deep to crawl from homepage
DISCOVERY_TIMEOUT = 10           # Seconds per request during discovery

# Fetching settings
FETCH_DELAY = 1.5                # Seconds between requests (rate limiting)
FETCH_TIMEOUT = 15               # Seconds per request
USE_PLAYWRIGHT_DEFAULT = False   # Use Playwright by default

# LLM settings
LLM_MODEL = "gpt-4o-mini"
LLM_MAX_TOKENS = 4000

# Keywords
LOYALTY_URL_KEYWORDS = [...]
COMMON_LOYALTY_PATHS = [...]
```

---

## Output Structure

```
output/
└── run_20251127_150000/
    ├── discovery/                    # NEW: Discovery results
    │   ├── starbucks_urls.json       # Discovered URLs for brand
    │   └── chipotle_urls.json
    ├── raw/                          # Raw HTML files
    │   ├── starbucks_rewards.html
    │   ├── starbucks_terms.html
    │   ├── starbucks_faq.html
    │   └── ...
    ├── pages/                        # NEW: Per-page extractions
    │   ├── starbucks_rewards.json
    │   ├── starbucks_terms.json
    │   └── starbucks_faq.json
    ├── structured/                   # Final merged JSONs
    │   ├── starbucks.json
    │   └── chipotle.json
    ├── combined/
    │   ├── all_programs.json
    │   └── all_programs.jsonl
    └── run_summary.json
```

---

## CLI Updates

### New Arguments

```bash
# Stage 2 mode (auto-discovery)
python loyalty_scraper.py -i brands.csv -o output --discover

# With options
python loyalty_scraper.py -i brands.csv -o output \
    --discover \
    --max-urls 20 \
    --crawl-depth 3 \
    --use-playwright

# Legacy mode (manual URLs, Stage 1 behavior)
python loyalty_scraper.py -i seeds.csv -o output --legacy
```

---

## Error Handling

### Discovery Errors
- Sitemap not found → Fall back to path probing + crawling
- Domain unreachable → Skip brand, log error
- Too few URLs found → Warn, proceed with available URLs

### Fetch Errors
- 404/403 → Skip page, log warning
- Timeout → Retry once, then skip
- Rate limited (429) → Increase delay, retry

### Merge Errors
- No data extracted → Output empty JSON with error flag
- LLM timeout → Retry with smaller context

---

## Estimated Performance

| Metric | Stage 1 | Stage 2 |
|--------|---------|---------|
| Input effort | High (manual URLs) | Low (just domain) |
| Time per brand | 10-30 sec | 1-2 min |
| Data completeness | Partial | Complete |
| Pages processed | 1-3 | 5-15 |

---

## Implementation Order

### Step 1: Create `discovery.py`
- [ ] Sitemap fetching and parsing
- [ ] Common path probing
- [ ] Homepage crawling (depth 2)
- [ ] URL filtering and scoring
- [ ] Main `discover_loyalty_urls()` function

### Step 2: Create `config.py`
- [ ] Centralize all configuration
- [ ] Keywords lists
- [ ] Timeouts and limits

### Step 3: Update `loyalty_scraper.py`
- [ ] Add `--discover` flag
- [ ] Integrate discovery phase
- [ ] Add page type classification
- [ ] Implement merge function
- [ ] Update output structure

### Step 4: Update `classifier.py`
- [ ] Add page type classification prompt
- [ ] Add merge prompt for combining extractions
- [ ] Optimize prompts for multi-page context

### Step 5: Testing
- [ ] Test discovery on 5+ brands
- [ ] Verify data completeness improvement
- [ ] Benchmark performance
- [ ] Handle edge cases

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Bot detection/blocking | Rate limiting, rotating user agents, respectful crawling |
| Too many irrelevant pages | Strict keyword filtering, relevance scoring |
| Slow performance | Parallel fetching, caching, sitemap-first approach |
| Inconsistent merging | Structured merge prompts, validation against schema |
| Missing pages | Multiple discovery methods (sitemap + crawl + probe) |

---

## Success Criteria

1. **Discovery**: Find ≥80% of loyalty-related pages per brand
2. **Completeness**: Extract data for all schema fields when available
3. **Accuracy**: No hallucination (only explicit data)
4. **Performance**: <2 minutes per brand
5. **Reliability**: Handle errors gracefully, no crashes

---

## Next Steps

1. Review and approve this implementation plan
2. Implement `discovery.py` module
3. Test discovery on sample brands
4. Integrate with main pipeline
5. Full testing and refinement
