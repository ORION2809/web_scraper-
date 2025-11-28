"""
Discovery module - automatically finds loyalty-related URLs for a brand domain.
Uses sitemap parsing, common path probing, and homepage crawling.
"""
import re
import time
import xml.etree.ElementTree as ET
from typing import List, Set, Tuple, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup


# Keywords to identify loyalty-related URLs
LOYALTY_KEYWORDS = [
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

# Common URL paths for loyalty programs
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
    "/loyalty-program",
    "/loyalty/terms",
    "/member-rewards",
    "/club",
    "/perks",
    "/vip",
    "/plus",
    "/advantage",
    "/terms",
    "/terms-and-conditions",
]

# Request settings
REQUEST_TIMEOUT = 10
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def normalize_domain(domain: str) -> str:
    """Ensure domain has proper format (no protocol, no trailing slash)"""
    domain = domain.strip().lower()
    domain = re.sub(r'^https?://', '', domain)
    domain = domain.rstrip('/')
    return domain


def get_base_url(domain: str) -> str:
    """Get base URL with https protocol"""
    domain = normalize_domain(domain)
    return f"https://www.{domain}" if not domain.startswith("www.") else f"https://{domain}"


def is_same_domain(url: str, domain: str) -> bool:
    """Check if URL belongs to the same domain"""
    domain = normalize_domain(domain)
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    # Handle www and non-www
    return domain in host or host.replace("www.", "") == domain.replace("www.", "")


def url_matches_keywords(url: str, keywords: List[str] = LOYALTY_KEYWORDS) -> bool:
    """Check if URL path contains any loyalty keywords"""
    path = urlparse(url).path.lower()
    return any(keyword in path for keyword in keywords)


def score_url_relevance(url: str) -> float:
    """Score URL by how many loyalty keywords it contains (higher = more relevant)"""
    path = urlparse(url).path.lower()
    score = 0.0
    for keyword in LOYALTY_KEYWORDS:
        if keyword in path:
            score += 1.0
            # Bonus for primary terms
            if keyword in ["reward", "rewards", "loyalty", "membership", "points"]:
                score += 0.5
    return score


def fetch_url(url: str, timeout: int = REQUEST_TIMEOUT) -> Optional[str]:
    """Fetch URL content, return None on failure"""
    try:
        response = requests.get(
            url, 
            headers=REQUEST_HEADERS, 
            timeout=timeout,
            allow_redirects=True
        )
        if response.status_code == 200:
            return response.text
        return None
    except Exception:
        return None


def fetch_sitemap(domain: str) -> List[str]:
    """
    Fetch and parse sitemap.xml, return all URLs.
    Handles sitemap index files (multiple sitemaps).
    """
    base_url = get_base_url(domain)
    sitemap_urls = [
        f"{base_url}/sitemap.xml",
        f"{base_url}/sitemap_index.xml",
        f"{base_url}/sitemap/sitemap.xml",
        f"{base_url}/sitemaps/sitemap.xml",
    ]
    
    all_urls = set()
    
    for sitemap_url in sitemap_urls:
        content = fetch_url(sitemap_url)
        if not content:
            continue
            
        try:
            # Parse XML
            root = ET.fromstring(content)
            
            # Handle namespace
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            
            # Check if this is a sitemap index
            sitemaps = root.findall(".//sm:sitemap/sm:loc", ns)
            if sitemaps:
                # It's an index, fetch each sub-sitemap
                for sitemap in sitemaps[:10]:  # Limit to first 10 sitemaps
                    sub_content = fetch_url(sitemap.text)
                    if sub_content:
                        try:
                            sub_root = ET.fromstring(sub_content)
                            for loc in sub_root.findall(".//sm:loc", ns):
                                if loc.text:
                                    all_urls.add(loc.text)
                        except ET.ParseError:
                            continue
            else:
                # Regular sitemap
                for loc in root.findall(".//sm:loc", ns):
                    if loc.text:
                        all_urls.add(loc.text)
                        
            # Also try without namespace (some sites don't use it)
            for loc in root.findall(".//loc"):
                if loc.text:
                    all_urls.add(loc.text)
                    
        except ET.ParseError:
            continue
    
    return list(all_urls)


def probe_common_paths(domain: str) -> List[str]:
    """
    Try common loyalty URL paths, return those that return 200 OK.
    """
    base_url = get_base_url(domain)
    valid_urls = []
    
    for path in COMMON_LOYALTY_PATHS:
        url = f"{base_url}{path}"
        try:
            response = requests.head(
                url, 
                headers=REQUEST_HEADERS, 
                timeout=5,
                allow_redirects=True
            )
            if response.status_code == 200:
                valid_urls.append(url)
                print(f"    ✓ Found: {path}")
            time.sleep(0.2)  # Be gentle
        except Exception:
            continue
    
    return valid_urls


def extract_links_from_html(html: str, base_url: str, domain: str) -> Set[str]:
    """Extract all internal links from HTML content"""
    links = set()
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            
            # Skip empty, javascript, mailto, tel links
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            
            # Convert relative to absolute
            full_url = urljoin(base_url, href)
            
            # Only keep same-domain links
            if is_same_domain(full_url, domain):
                # Clean URL (remove fragments)
                parsed = urlparse(full_url)
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    clean_url += f"?{parsed.query}"
                links.add(clean_url)
                
    except Exception:
        pass
    
    return links


def crawl_for_links(url: str, domain: str, depth: int = 2) -> List[str]:
    """
    Crawl page and extract internal links, optionally following to specified depth.
    Returns list of loyalty-related URLs found.
    """
    visited = set()
    to_visit = [(url, 0)]  # (url, current_depth)
    loyalty_urls = set()
    
    while to_visit:
        current_url, current_depth = to_visit.pop(0)
        
        if current_url in visited:
            continue
        visited.add(current_url)
        
        # Fetch page
        html = fetch_url(current_url)
        if not html:
            continue
        
        # Extract links
        links = extract_links_from_html(html, current_url, domain)
        
        for link in links:
            # Check if loyalty-related
            if url_matches_keywords(link):
                loyalty_urls.add(link)
            
            # Add to crawl queue if within depth
            if current_depth < depth and link not in visited:
                # Prioritize loyalty-related links
                if url_matches_keywords(link):
                    to_visit.insert(0, (link, current_depth + 1))
                elif current_depth < depth - 1:
                    to_visit.append((link, current_depth + 1))
        
        # Limit visited pages to avoid excessive crawling
        if len(visited) >= 50:
            break
        
        time.sleep(0.3)  # Rate limiting
    
    return list(loyalty_urls)


def deduplicate_and_rank(urls: List[str], max_urls: int = 20) -> List[str]:
    """
    Remove duplicates, score by relevance, return top N.
    """
    # Deduplicate
    unique_urls = list(set(urls))
    
    # Score and sort
    scored = [(url, score_url_relevance(url)) for url in unique_urls]
    scored.sort(key=lambda x: x[1], reverse=True)
    
    # Return top N
    return [url for url, score in scored[:max_urls]]


def discover_loyalty_urls(domain: str, max_urls: int = 20, verbose: bool = True) -> List[str]:
    """
    Main discovery function. Returns list of loyalty-related URLs.
    
    Uses multiple discovery methods:
    1. Sitemap parsing
    2. Common path probing
    3. Homepage crawling (depth 2)
    
    Args:
        domain: Brand domain (e.g., "starbucks.com")
        max_urls: Maximum URLs to return
        verbose: Print progress messages
        
    Returns:
        List of discovered loyalty-related URLs, sorted by relevance
    """
    if verbose:
        print(f"  Discovering loyalty URLs for: {domain}")
    
    all_urls = set()
    base_url = get_base_url(domain)
    
    # Method 1: Sitemap
    if verbose:
        print("    [1/3] Checking sitemap...")
    sitemap_urls = fetch_sitemap(domain)
    if sitemap_urls:
        loyalty_from_sitemap = [url for url in sitemap_urls if url_matches_keywords(url)]
        all_urls.update(loyalty_from_sitemap)
        if verbose:
            print(f"    Found {len(loyalty_from_sitemap)} loyalty URLs in sitemap")
    else:
        if verbose:
            print("    No sitemap found")
    
    # Method 2: Common paths
    if verbose:
        print("    [2/3] Probing common paths...")
    common_urls = probe_common_paths(domain)
    all_urls.update(common_urls)
    if verbose:
        print(f"    Found {len(common_urls)} valid common paths")
    
    # Method 3: Homepage crawl
    if verbose:
        print("    [3/3] Crawling homepage (depth 2)...")
    crawled_urls = crawl_for_links(base_url, domain, depth=2)
    all_urls.update(crawled_urls)
    if verbose:
        print(f"    Found {len(crawled_urls)} URLs from crawling")
    
    # Deduplicate and rank
    ranked_urls = deduplicate_and_rank(list(all_urls), max_urls)
    
    if verbose:
        print(f"  Total unique loyalty URLs: {len(ranked_urls)}")
    
    return ranked_urls


def discover_for_brand(brand: str, domain: str, max_urls: int = 20) -> dict:
    """
    Discover URLs for a brand and return structured result.
    """
    urls = discover_loyalty_urls(domain, max_urls)
    
    return {
        "brand": brand,
        "domain": domain,
        "discovered_urls": urls,
        "count": len(urls)
    }


# CLI for testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python discovery.py <domain>")
        print("Example: python discovery.py starbucks.com")
        sys.exit(1)
    
    domain = sys.argv[1]
    urls = discover_loyalty_urls(domain, max_urls=15)
    
    print("\n" + "="*60)
    print("DISCOVERED LOYALTY URLS")
    print("="*60)
    for i, url in enumerate(urls, 1):
        print(f"{i:2}. {url}")
