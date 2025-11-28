"""
Fetcher module - handles HTTP requests with retry logic.
Supports both requests library and optional Playwright fallback.
"""
import time
import random
from typing import Tuple, Optional, Dict
from dataclasses import dataclass
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass
class FetchResult:
    """Result of a fetch operation"""
    url: str
    html: Optional[str]
    status_code: Optional[int]
    error: Optional[str]
    fetch_time_ms: int
    fetched_at: datetime
    method: str  # 'requests' or 'playwright'


# Rotate through common User-Agents to reduce blocking
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


def create_session() -> requests.Session:
    """Create a requests session with retry logic"""
    session = requests.Session()
    
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


def fetch_with_requests(url: str, timeout: int = 15) -> FetchResult:
    """Fetch URL using requests library"""
    start_time = time.time()
    
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    try:
        session = create_session()
        response = session.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        fetch_time_ms = int((time.time() - start_time) * 1000)
        
        return FetchResult(
            url=url,
            html=response.text,
            status_code=response.status_code,
            error=None,
            fetch_time_ms=fetch_time_ms,
            fetched_at=datetime.utcnow(),
            method="requests"
        )
        
    except requests.exceptions.Timeout:
        fetch_time_ms = int((time.time() - start_time) * 1000)
        return FetchResult(
            url=url,
            html=None,
            status_code=None,
            error=f"Timeout after {timeout}s",
            fetch_time_ms=fetch_time_ms,
            fetched_at=datetime.utcnow(),
            method="requests"
        )
        
    except requests.exceptions.HTTPError as e:
        fetch_time_ms = int((time.time() - start_time) * 1000)
        return FetchResult(
            url=url,
            html=None,
            status_code=e.response.status_code if e.response else None,
            error=str(e),
            fetch_time_ms=fetch_time_ms,
            fetched_at=datetime.utcnow(),
            method="requests"
        )
        
    except Exception as e:
        fetch_time_ms = int((time.time() - start_time) * 1000)
        return FetchResult(
            url=url,
            html=None,
            status_code=None,
            error=str(e),
            fetch_time_ms=fetch_time_ms,
            fetched_at=datetime.utcnow(),
            method="requests"
        )


def fetch_with_playwright(url: str, timeout: int = 30000) -> FetchResult:
    """
    Fetch URL using Playwright for JS-rendered content.
    Requires: pip install playwright && playwright install chromium
    Returns both raw HTML and extracted visible text for better LLM processing.
    """
    start_time = time.time()
    
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()
            
            response = page.goto(url, wait_until="networkidle", timeout=timeout)
            
            # Wait a bit more for dynamic content to load
            page.wait_for_timeout(2000)
            
            # Get both raw HTML and visible text
            html = page.content()
            
            # Extract visible text content (much cleaner for LLM)
            try:
                visible_text = page.inner_text('body')
            except:
                visible_text = ""
            
            status_code = response.status if response else None
            
            browser.close()
            
            fetch_time_ms = int((time.time() - start_time) * 1000)
            
            # Embed the visible text in a special marker for the parser
            if visible_text:
                html = f"<!--PLAYWRIGHT_VISIBLE_TEXT_START-->{visible_text}<!--PLAYWRIGHT_VISIBLE_TEXT_END-->" + html
            
            return FetchResult(
                url=url,
                html=html,
                status_code=status_code,
                error=None,
                fetch_time_ms=fetch_time_ms,
                fetched_at=datetime.utcnow(),
                method="playwright"
            )
            
    except ImportError:
        fetch_time_ms = int((time.time() - start_time) * 1000)
        return FetchResult(
            url=url,
            html=None,
            status_code=None,
            error="Playwright not installed. Run: pip install playwright && playwright install chromium",
            fetch_time_ms=fetch_time_ms,
            fetched_at=datetime.utcnow(),
            method="playwright"
        )
        
    except Exception as e:
        fetch_time_ms = int((time.time() - start_time) * 1000)
        return FetchResult(
            url=url,
            html=None,
            status_code=None,
            error=str(e),
            fetch_time_ms=fetch_time_ms,
            fetched_at=datetime.utcnow(),
            method="playwright"
        )


def fetch_url(url: str, use_playwright: bool = False, timeout: int = 15) -> FetchResult:
    """
    Main fetch function. Tries requests first, falls back to Playwright if enabled and requests fails.
    """
    if use_playwright:
        return fetch_with_playwright(url, timeout=timeout * 1000)
    
    result = fetch_with_requests(url, timeout=timeout)
    
    # If requests failed and we detect JS-heavy indicators, suggest Playwright
    if result.error and "403" in str(result.error):
        result.error += " (Try --use-playwright for JS-heavy sites)"
    
    return result
