"""
Configuration settings for the loyalty program scraper.
Centralizes all configurable parameters.
"""

# ============================================================
# DISCOVERY SETTINGS
# ============================================================

# Maximum URLs to discover per brand
DISCOVERY_MAX_URLS = 15

# How deep to crawl from homepage (1 = only homepage links, 2 = follow those links)
DISCOVERY_CRAWL_DEPTH = 2

# Timeout for requests during discovery (seconds)
DISCOVERY_TIMEOUT = 10

# Maximum pages to visit during crawling
DISCOVERY_MAX_PAGES = 50


# ============================================================
# FETCHING SETTINGS  
# ============================================================

# Delay between requests (rate limiting, seconds)
FETCH_DELAY = 1.5

# Timeout for fetching pages (seconds)
FETCH_TIMEOUT = 15

# Use Playwright by default for JS-heavy sites
USE_PLAYWRIGHT_DEFAULT = False

# User agent for requests
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


# ============================================================
# LLM SETTINGS
# ============================================================

# Default model for classification
LLM_MODEL = "gpt-4o-mini"

# Maximum tokens for LLM response
LLM_MAX_TOKENS = 4000

# Temperature for LLM (lower = more deterministic)
LLM_TEMPERATURE = 0.1

# Maximum text length to send to LLM (characters)
LLM_MAX_TEXT_LENGTH = 15000


# ============================================================
# KEYWORDS FOR URL DISCOVERY
# ============================================================

LOYALTY_URL_KEYWORDS = [
    # Primary loyalty terms
    "reward", "rewards", "loyalty", "points", "member", "membership",
    # Tier/status terms  
    "tier", "tiers", "level", "levels", "status", "gold", "silver",
    "platinum", "bronze", "vip", "elite", "premier", "plus",
    # Action terms
    "earn", "earning", "redeem", "redemption", "collect", "spend",
    # Program terms
    "program", "club", "perks", "benefits", "bonus", "advantage",
    # Info pages
    "terms", "conditions", "faq", "how-it-works", "about-rewards",
    "terms-and-conditions", "terms-of-use",
]


# ============================================================
# COMMON URL PATHS TO PROBE
# ============================================================

COMMON_LOYALTY_PATHS = [
    "/rewards",
    "/loyalty", 
    "/membership",
    "/points",
    "/rewards/terms",
    "/rewards/faq",
    "/rewards/how-it-works",
    "/rewards/about",
    "/rewards/earn",
    "/rewards/redeem",
    "/rewards/tiers",
    "/rewards/benefits",
    "/loyalty-program",
    "/loyalty/terms",
    "/loyalty/faq",
    "/member-rewards",
    "/member/rewards",
    "/club",
    "/perks",
    "/vip",
    "/plus",
    "/advantage",
    "/myrewards",
    "/my-rewards",
    "/terms",
    "/terms-and-conditions",
    "/legal/rewards-terms",
]


# ============================================================
# PAGE TYPE CLASSIFICATION
# ============================================================

PAGE_TYPE_KEYWORDS = {
    "overview": ["reward", "loyalty", "join", "earn", "member", "program"],
    "terms": ["terms", "condition", "legal", "policy", "agreement"],
    "faq": ["faq", "question", "help", "support", "how"],
    "tiers": ["tier", "level", "status", "gold", "silver", "platinum", "bronze"],
    "earn": ["earn", "point", "collect", "accumulate"],
    "redeem": ["redeem", "catalog", "reward", "exchange", "spend"],
}


# ============================================================
# OUTPUT SETTINGS
# ============================================================

# Output folder structure
OUTPUT_RAW_FOLDER = "raw"
OUTPUT_PAGES_FOLDER = "pages"
OUTPUT_STRUCTURED_FOLDER = "structured"
OUTPUT_COMBINED_FOLDER = "combined"
OUTPUT_DISCOVERY_FOLDER = "discovery"
