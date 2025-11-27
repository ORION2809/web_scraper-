"""
Parser module - extracts structured content from HTML.
Uses BeautifulSoup to pull headings, paragraphs, lists, tables, and JSON-LD.
"""
import re
import json
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup, Comment

from schemas import ParsedContent


# Elements to remove (navigation, footers, ads, etc.)
REMOVE_SELECTORS = [
    "nav", "header", "footer", "aside",
    ".nav", ".navbar", ".navigation", ".menu",
    ".header", ".footer", ".sidebar",
    ".cookie", ".cookie-banner", ".cookie-consent",
    ".ad", ".ads", ".advertisement",
    ".social", ".share", ".sharing",
    "script", "style", "noscript", "iframe",
]


def clean_text(text: str) -> str:
    """Normalize whitespace and clean text"""
    if not text:
        return ""
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text


def extract_json_ld(soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
    """Extract JSON-LD structured data if present"""
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string)
            # Return first valid JSON-LD (could be expanded to return all)
            return data
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def extract_meta_description(soup: BeautifulSoup) -> Optional[str]:
    """Extract meta description"""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return clean_text(meta.get("content"))
    
    # Try OpenGraph description
    og_desc = soup.find("meta", attrs={"property": "og:description"})
    if og_desc and og_desc.get("content"):
        return clean_text(og_desc.get("content"))
    
    return None


def remove_unwanted_elements(soup: BeautifulSoup) -> None:
    """Remove navigation, footers, scripts, etc. in place"""
    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    
    # Remove by selector
    for selector in REMOVE_SELECTORS:
        for element in soup.select(selector):
            element.decompose()


def extract_headings(soup: BeautifulSoup) -> List[str]:
    """Extract all headings (H1-H4)"""
    headings = []
    for tag in ["h1", "h2", "h3", "h4"]:
        for heading in soup.find_all(tag):
            text = clean_text(heading.get_text())
            if text and len(text) > 2:
                headings.append(f"[{tag.upper()}] {text}")
    return headings


def extract_paragraphs(soup: BeautifulSoup, min_length: int = 20) -> List[str]:
    """Extract paragraphs with meaningful content"""
    paragraphs = []
    for p in soup.find_all("p"):
        text = clean_text(p.get_text())
        if text and len(text) >= min_length:
            paragraphs.append(text)
    return paragraphs


def extract_list_items(soup: BeautifulSoup) -> List[str]:
    """Extract list items (ul/ol > li)"""
    items = []
    for li in soup.find_all("li"):
        text = clean_text(li.get_text())
        if text and len(text) > 5:
            items.append(f"• {text}")
    return items


def extract_tables(soup: BeautifulSoup) -> List[List[List[str]]]:
    """Extract tables as list of rows (each row is list of cells)"""
    tables = []
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = []
            for cell in tr.find_all(["th", "td"]):
                cells.append(clean_text(cell.get_text()))
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """Extract page title"""
    if soup.title and soup.title.string:
        return clean_text(soup.title.string)
    return None


def parse_html(html: str, url: str, brand: str) -> ParsedContent:
    """
    Main parsing function.
    Takes raw HTML and returns structured ParsedContent.
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # Extract metadata before cleaning
    title = extract_title(soup)
    meta_description = extract_meta_description(soup)
    json_ld = extract_json_ld(soup)
    
    # Remove unwanted elements
    remove_unwanted_elements(soup)
    
    # Extract content
    headings = extract_headings(soup)
    paragraphs = extract_paragraphs(soup)
    list_items = extract_list_items(soup)
    tables = extract_tables(soup)
    
    # Build full text for LLM (combining everything)
    full_text_parts = []
    
    if title:
        full_text_parts.append(f"Title: {title}")
    if meta_description:
        full_text_parts.append(f"Description: {meta_description}")
    
    full_text_parts.append("\n--- HEADINGS ---")
    full_text_parts.extend(headings)
    
    full_text_parts.append("\n--- CONTENT ---")
    full_text_parts.extend(paragraphs[:50])  # Limit to avoid huge prompts
    
    full_text_parts.append("\n--- LIST ITEMS ---")
    full_text_parts.extend(list_items[:100])  # Limit
    
    if tables:
        full_text_parts.append("\n--- TABLES ---")
        for i, table in enumerate(tables[:5]):  # Limit to 5 tables
            full_text_parts.append(f"Table {i+1}:")
            for row in table[:20]:  # Limit rows
                full_text_parts.append(" | ".join(row))
    
    full_text = "\n".join(full_text_parts)
    
    return ParsedContent(
        url=url,
        brand=brand,
        title=title,
        headings=headings,
        paragraphs=paragraphs,
        list_items=list_items,
        tables=tables,
        json_ld=json_ld,
        meta_description=meta_description,
        full_text=full_text
    )
