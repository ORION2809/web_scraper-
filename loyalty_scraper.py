"""
Loyalty Program Web Scraper - Main Pipeline

Stage 1 (Legacy - Manual URLs):
    python loyalty_scraper.py --input seeds.csv --output output/

Stage 2 (Auto-Discovery):
    python loyalty_scraper.py --input brands.csv --output output/ --discover

Options:
    --discover          Enable auto-discovery mode (input: brand,domain)
    --skip-llm          Skip LLM classification
    --use-playwright    Use Playwright for JS-heavy sites
    --max-urls N        Max URLs to discover per brand (default: 15)
"""
import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fetcher import fetch_url, FetchResult
from parser import parse_html
from classifier import classify, classify_with_openai
from schemas import LoyaltyProgram, ParsedContent


def load_seeds(path: str) -> List[Dict[str, str]]:
    """Load seed URLs from CSV file (Stage 1 format: brand,url,page_type)"""
    seeds = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            seeds.append({
                "brand": row.get("brand", "Unknown"),
                "url": row.get("url", ""),
                "page_type": row.get("page_type", "rewards")
            })
    return [s for s in seeds if s["url"]]  # Filter empty URLs


def load_brands(path: str) -> List[Dict[str, str]]:
    """Load brands from CSV file (Stage 2 format: brand,domain)"""
    brands = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            brands.append({
                "brand": row.get("brand", "Unknown"),
                "domain": row.get("domain", "")
            })
    return [b for b in brands if b["domain"]]  # Filter empty domains


def create_run_folder(base_output: str, discover_mode: bool = False) -> Dict[str, Path]:
    """
    Create a timestamped run folder with organized subfolders.
    
    Structure:
    output/
    └── run_20251127_143022/
        ├── discovery/              # Discovered URLs (Stage 2 only)
        │   └── starbucks_urls.json
        ├── raw/                    # Raw HTML snapshots
        │   └── starbucks_terms.html
        ├── pages/                  # Per-page extractions (Stage 2 only)
        │   └── starbucks_rewards.json
        ├── structured/             # Final merged brand JSON files
        │   └── starbucks.json
        ├── combined/               # Combined output files
        │   ├── all_programs.json
        │   └── all_programs.jsonl
        └── run_summary.json        # Run metadata and summary
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"run_{timestamp}"
    
    base = Path(base_output)
    run_dir = base / run_name
    
    paths = {
        "run_dir": run_dir,
        "raw_dir": run_dir / "raw",
        "structured_dir": run_dir / "structured",
        "combined_dir": run_dir / "combined",
        "run_name": run_name,
        "timestamp": timestamp
    }
    
    # Add discovery and pages folders for Stage 2
    if discover_mode:
        paths["discovery_dir"] = run_dir / "discovery"
        paths["pages_dir"] = run_dir / "pages"
    
    # Create all directories
    for key, path in paths.items():
        if isinstance(path, Path) and key.endswith("_dir"):
            path.mkdir(parents=True, exist_ok=True)
    
    return paths


def save_raw_html(raw_dir: Path, brand: str, page_type: str, html: str, fetch_result: FetchResult):
    """Save raw HTML snapshot with clear naming"""
    # Clean brand name for filename
    brand_clean = brand.lower().replace(' ', '_').replace("'", "")
    filename = f"{brand_clean}_{page_type}.html"
    filepath = raw_dir / filename
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"<!-- URL: {fetch_result.url} -->\n")
        f.write(f"<!-- Brand: {brand} -->\n")
        f.write(f"<!-- Page Type: {page_type} -->\n")
        f.write(f"<!-- Fetched: {fetch_result.fetched_at.isoformat()} -->\n")
        f.write(f"<!-- Status: {fetch_result.status_code} -->\n")
        f.write(f"<!-- Method: {fetch_result.method} -->\n")
        f.write(f"<!-- Time: {fetch_result.fetch_time_ms}ms -->\n\n")
        f.write(html)
    
    return filepath


def save_structured(structured_dir: Path, program: LoyaltyProgram):
    """Save structured loyalty program data"""
    brand_clean = program.brand.lower().replace(' ', '_').replace("'", "")
    filename = f"{brand_clean}.json"
    filepath = structured_dir / filename
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(program.model_dump(mode="json"), f, indent=2, ensure_ascii=False, default=str)
    
    return filepath


def save_combined_outputs(combined_dir: Path, programs: List[LoyaltyProgram]):
    """Save combined output files in multiple formats"""
    # JSONL format (one JSON per line)
    jsonl_path = combined_dir / "all_programs.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for program in programs:
            f.write(json.dumps(program.model_dump(mode="json"), ensure_ascii=False, default=str) + "\n")
    
    # JSON array format (prettier, easier to read)
    json_path = combined_dir / "all_programs.json"
    with open(json_path, "w", encoding="utf-8") as f:
        data = [program.model_dump(mode="json") for program in programs]
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    
    return jsonl_path, json_path


def save_run_summary(run_dir: Path, run_info: Dict[str, Any]):
    """Save run metadata and summary"""
    summary_path = run_dir / "run_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(run_info, f, indent=2, ensure_ascii=False, default=str)
    return summary_path


def run_pipeline(
    input_path: str,
    output_path: str,
    skip_llm: bool = False,
    use_playwright: bool = False,
    delay: float = 1.0,
    model: str = "gpt-4o-mini"
):
    """
    Main pipeline execution.
    
    1. Load seed URLs
    2. For each URL: Fetch → Parse → Classify
    3. Save raw HTML + structured output in organized run folder
    """
    # Create timestamped run folder
    paths = create_run_folder(output_path)
    run_dir = paths["run_dir"]
    raw_dir = paths["raw_dir"]
    structured_dir = paths["structured_dir"]
    combined_dir = paths["combined_dir"]
    run_name = paths["run_name"]
    
    print("=" * 60)
    print("LOYALTY PROGRAM WEB SCRAPER")
    print("=" * 60)
    print(f"Input: {input_path}")
    print(f"Output: {run_dir}")
    print(f"LLM: {'Disabled' if skip_llm else model}")
    print(f"Fetcher: {'Playwright' if use_playwright else 'Requests'}")
    print("=" * 60)
    
    # Load seeds
    seeds = load_seeds(input_path)
    if not seeds:
        print("Error: No valid URLs found in seed file")
        return 1
    
    print(f"\nLoaded {len(seeds)} URLs to scrape\n")
    
    # Track run start time
    run_start = datetime.now()
    
    # Process each URL
    programs = []
    results_summary = []
    
    for i, seed in enumerate(seeds, start=1):
        brand = seed["brand"]
        url = seed["url"]
        page_type = seed.get("page_type", "rewards")
        
        print(f"[{i}/{len(seeds)}] {brand} ({page_type})")
        print(f"  URL: {url}")
        
        # Step 1: Fetch
        print(f"  Fetching...")
        fetch_result = fetch_url(url, use_playwright=use_playwright)
        
        if fetch_result.error:
            print(f"  ✗ Fetch failed: {fetch_result.error}")
            results_summary.append({
                "brand": brand,
                "url": url,
                "page_type": page_type,
                "status": "fetch_error",
                "error": fetch_result.error
            })
            continue
        
        print(f"  ✓ Fetched in {fetch_result.fetch_time_ms}ms ({len(fetch_result.html)} bytes)")
        
        # Save raw HTML
        raw_path = save_raw_html(raw_dir, brand, page_type, fetch_result.html, fetch_result)
        print(f"  Saved: {raw_path.name}")
        
        # Step 2: Parse
        print(f"  Parsing...")
        parsed = parse_html(fetch_result.html, url, brand)
        print(f"  ✓ Parsed: {len(parsed.headings)} headings, {len(parsed.paragraphs)} paragraphs, {len(parsed.list_items)} list items")
        
        # Step 3: Classify
        program = classify(parsed, skip_llm=skip_llm, model=model)
        programs.append(program)
        
        # Save structured output
        struct_path = save_structured(structured_dir, program)
        print(f"  Saved: {struct_path.name}")
        
        # Count extracted items from new schema
        tiers_count = len(program.design.tiers) if program.design else 0
        badges_count = len(program.design.rewards.achievement_badges) if program.design and program.design.rewards else 0
        products_count = len(program.design.rewards.catalog_products) if program.design and program.design.rewards else 0
        
        results_summary.append({
            "brand": brand,
            "url": url,
            "page_type": page_type,
            "status": "success",
            "raw_file": raw_path.name,
            "structured_file": struct_path.name,
            "tiers": tiers_count,
            "badges": badges_count,
            "catalog_products": products_count
        })
        
        print()
        
        # Delay between requests
        if i < len(seeds):
            import time
            time.sleep(delay)
    
    # Save combined outputs
    if programs:
        jsonl_path, json_path = save_combined_outputs(combined_dir, programs)
        print(f"Combined outputs:")
        print(f"  - {jsonl_path}")
        print(f"  - {json_path}")
    
    # Calculate run duration
    run_end = datetime.now()
    run_duration = (run_end - run_start).total_seconds()
    
    # Save run summary
    success_count = sum(1 for r in results_summary if r["status"] == "success")
    error_count = len(results_summary) - success_count
    
    run_info = {
        "run_name": run_name,
        "run_start": run_start.isoformat(),
        "run_end": run_end.isoformat(),
        "run_duration_seconds": run_duration,
        "input_file": input_path,
        "settings": {
            "llm_model": model if not skip_llm else "disabled",
            "fetcher": "playwright" if use_playwright else "requests",
            "delay_seconds": delay
        },
        "summary": {
            "total_urls": len(seeds),
            "success": success_count,
            "errors": error_count
        },
        "results": results_summary
    }
    
    summary_path = save_run_summary(run_dir, run_info)
    print(f"Run summary: {summary_path}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Run: {run_name}")
    print(f"Duration: {run_duration:.1f}s")
    print(f"Total: {len(results_summary)} | Success: {success_count} | Errors: {error_count}")
    print()
    
    for result in results_summary:
        status_icon = "✓" if result["status"] == "success" else "✗"
        if result["status"] == "success":
            print(f"  {status_icon} {result['brand']} ({result['page_type']}): {result['tiers']} tiers, {result['badges']} badges, {result['catalog_products']} products")
        else:
            print(f"  {status_icon} {result['brand']} ({result['page_type']}): {result.get('error', 'Unknown error')[:50]}")
    
    print()
    print(f"Output folder: {run_dir}")
    print("=" * 60)
    
    return 0 if error_count == 0 else 1


# ============================================================
# STAGE 2: AUTO-DISCOVERY PIPELINE
# ============================================================

MERGE_PROMPT = """You are merging loyalty program data extracted from multiple pages of the same brand into a single complete JSON.

RULES:
1. Combine all information found across pages - don't lose any data
2. Remove exact duplicates (same tier name, same product name)
3. Keep the most detailed/complete version when there are conflicts
4. Use the official program name and description from the overview/main page
5. Merge all tiers, incentives, catalog products, badges, gift cards
6. ONLY include data that was extracted - DO NOT invent anything new

The data below was extracted from {num_pages} pages for {brand}:

{extractions_json}

Return a single merged JSON with this structure:
{{
  "programName": "string or null",
  "description": "string or null",
  "strategy": {{
    "industry": "string or null",
    "programType": "string or null",
    "goals": [],
    "behaviors": [],
    "audience": [],
    "channels": []
  }},
  "design": {{
    "segments": [],
    "tiers": [],
    "incentives": [],
    "rewards": {{
      "loyalty_points": {{"points_per_dollar": "string or null"}},
      "achievement_badges": [],
      "gift_cards": [],
      "catalog_products": []
    }}
  }}
}}

Merge the data carefully. Keep everything that was found. Add nothing new."""


def merge_extractions(brand: str, extractions: List[dict], model: str = "gpt-4o-mini") -> dict:
    """
    Use LLM to intelligently merge data from multiple page extractions.
    """
    if not extractions:
        return {}
    
    if len(extractions) == 1:
        return extractions[0]
    
    # Prepare prompt
    prompt = MERGE_PROMPT.format(
        num_pages=len(extractions),
        brand=brand,
        extractions_json=json.dumps(extractions, indent=2, default=str)
    )
    
    # Call LLM
    try:
        import openai
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            # Fallback: simple merge without LLM
            return extractions[0]
        
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You merge loyalty program data from multiple pages. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
        
    except Exception as e:
        print(f"    Warning: Merge failed ({e}), using first extraction")
        return extractions[0]


def run_discovery_pipeline(
    input_path: str,
    output_path: str,
    skip_llm: bool = False,
    use_playwright: bool = False,
    delay: float = 1.5,
    model: str = "gpt-4o-mini",
    max_urls: int = 15
):
    """
    Stage 2 pipeline with automatic URL discovery.
    
    1. Load brands (brand, domain)
    2. For each brand: Discover URLs → Fetch all → Parse → Classify → Merge
    3. Save complete structured output
    """
    from discovery import discover_loyalty_urls
    
    # Create timestamped run folder with discovery folders
    paths = create_run_folder(output_path, discover_mode=True)
    run_dir = paths["run_dir"]
    raw_dir = paths["raw_dir"]
    pages_dir = paths["pages_dir"]
    discovery_dir = paths["discovery_dir"]
    structured_dir = paths["structured_dir"]
    combined_dir = paths["combined_dir"]
    run_name = paths["run_name"]
    
    print("=" * 60)
    print("LOYALTY PROGRAM WEB SCRAPER - DISCOVERY MODE")
    print("=" * 60)
    print(f"Input: {input_path}")
    print(f"Output: {run_dir}")
    print(f"LLM: {'Disabled' if skip_llm else model}")
    print(f"Fetcher: {'Playwright' if use_playwright else 'Requests'}")
    print(f"Max URLs per brand: {max_urls}")
    print("=" * 60)
    
    # Load brands
    brands = load_brands(input_path)
    if not brands:
        print("Error: No valid brands found in input file")
        print("Expected format: brand,domain")
        return 1
    
    print(f"\nLoaded {len(brands)} brands to process\n")
    
    run_start = datetime.now()
    all_programs = []
    brand_results = []
    
    for brand_idx, brand_info in enumerate(brands, start=1):
        brand = brand_info["brand"]
        domain = brand_info["domain"]
        
        print(f"\n{'='*60}")
        print(f"[{brand_idx}/{len(brands)}] {brand} ({domain})")
        print("="*60)
        
        brand_start = datetime.now()
        
        # PHASE 1: Discovery
        print("\n[Phase 1] Discovering loyalty URLs...")
        try:
            discovered_urls = discover_loyalty_urls(domain, max_urls=max_urls, verbose=True)
        except Exception as e:
            print(f"  ✗ Discovery failed: {e}")
            brand_results.append({
                "brand": brand,
                "domain": domain,
                "status": "discovery_error",
                "error": str(e)
            })
            continue
        
        if not discovered_urls:
            print("  ✗ No loyalty URLs found")
            brand_results.append({
                "brand": brand,
                "domain": domain,
                "status": "no_urls_found",
                "error": "No loyalty-related URLs discovered"
            })
            continue
        
        # Save discovered URLs
        discovery_file = discovery_dir / f"{brand.lower().replace(' ', '_')}_urls.json"
        with open(discovery_file, "w", encoding="utf-8") as f:
            json.dump({"brand": brand, "domain": domain, "urls": discovered_urls}, f, indent=2)
        print(f"  Saved: {discovery_file.name}")
        
        # PHASE 2: Fetch all pages
        print(f"\n[Phase 2] Fetching {len(discovered_urls)} pages...")
        fetched_pages = []
        
        for url_idx, url in enumerate(discovered_urls, start=1):
            print(f"  [{url_idx}/{len(discovered_urls)}] {url[:60]}...")
            
            fetch_result = fetch_url(url, use_playwright=use_playwright)
            
            if fetch_result.error:
                print(f"    ✗ Failed: {fetch_result.error[:40]}")
                continue
            
            print(f"    ✓ Fetched ({len(fetch_result.html)} bytes)")
            
            # Determine page type from URL
            url_lower = url.lower()
            if "term" in url_lower:
                page_type = "terms"
            elif "faq" in url_lower:
                page_type = "faq"
            elif "tier" in url_lower or "level" in url_lower:
                page_type = "tiers"
            elif "earn" in url_lower:
                page_type = "earn"
            elif "redeem" in url_lower:
                page_type = "redeem"
            else:
                page_type = "overview"
            
            # Save raw HTML
            brand_clean = brand.lower().replace(' ', '_').replace("'", "")
            raw_filename = f"{brand_clean}_{page_type}_{url_idx}.html"
            raw_path = raw_dir / raw_filename
            with open(raw_path, "w", encoding="utf-8") as f:
                f.write(f"<!-- URL: {url} -->\n")
                f.write(f"<!-- Brand: {brand} -->\n")
                f.write(f"<!-- Page Type: {page_type} -->\n\n")
                f.write(fetch_result.html)
            
            fetched_pages.append({
                "url": url,
                "html": fetch_result.html,
                "page_type": page_type,
                "raw_file": raw_filename
            })
            
            time.sleep(delay)
        
        if not fetched_pages:
            print("  ✗ No pages successfully fetched")
            brand_results.append({
                "brand": brand,
                "domain": domain,
                "status": "fetch_error",
                "error": "All page fetches failed"
            })
            continue
        
        print(f"  ✓ Fetched {len(fetched_pages)} pages")
        
        # PHASE 3: Parse & Classify each page
        print(f"\n[Phase 3] Parsing & classifying {len(fetched_pages)} pages...")
        page_extractions = []
        
        for page in fetched_pages:
            # Parse
            parsed = parse_html(page["html"], page["url"], brand)
            
            # Classify
            if skip_llm:
                extraction = {}
            else:
                extraction = classify_with_openai(parsed, model=model)
                if extraction is None:
                    extraction = {}
            
            # Save per-page extraction
            page_filename = f"{brand.lower().replace(' ', '_')}_{page['page_type']}_{len(page_extractions)+1}.json"
            page_path = pages_dir / page_filename
            with open(page_path, "w", encoding="utf-8") as f:
                json.dump({
                    "url": page["url"],
                    "page_type": page["page_type"],
                    "extraction": extraction
                }, f, indent=2, default=str)
            
            if extraction:
                page_extractions.append(extraction)
            
            print(f"    ✓ {page['page_type']}: extracted")
        
        # PHASE 4: Merge extractions
        print(f"\n[Phase 4] Merging {len(page_extractions)} extractions...")
        
        if page_extractions:
            if skip_llm:
                merged = page_extractions[0] if page_extractions else {}
            else:
                merged = merge_extractions(brand, page_extractions, model=model)
        else:
            merged = {}
        
        # Add metadata
        merged["brand"] = brand
        merged["domain"] = domain
        merged["scraped_at"] = datetime.now().isoformat()
        merged["pages_scraped"] = len(fetched_pages)
        merged["urls_discovered"] = len(discovered_urls)
        
        # Build LoyaltyProgram object for consistent output
        from classifier import build_loyalty_program
        program = build_loyalty_program(
            ParsedContent(url=domain, brand=brand, full_text=""),
            merged
        )
        
        # Save structured output
        struct_path = save_structured(structured_dir, program)
        print(f"  ✓ Saved: {struct_path.name}")
        
        all_programs.append(program)
        
        # Calculate stats
        tiers_count = len(program.design.tiers) if program.design else 0
        badges_count = len(program.design.rewards.achievement_badges) if program.design and program.design.rewards else 0
        products_count = len(program.design.rewards.catalog_products) if program.design and program.design.rewards else 0
        incentives_count = len(program.design.incentives) if program.design else 0
        
        brand_duration = (datetime.now() - brand_start).total_seconds()
        
        brand_results.append({
            "brand": brand,
            "domain": domain,
            "status": "success",
            "urls_discovered": len(discovered_urls),
            "pages_fetched": len(fetched_pages),
            "duration_seconds": brand_duration,
            "tiers": tiers_count,
            "badges": badges_count,
            "products": products_count,
            "incentives": incentives_count
        })
        
        print(f"\n  ✓ {brand} complete! ({brand_duration:.1f}s)")
        print(f"    Tiers: {tiers_count}, Badges: {badges_count}, Products: {products_count}, Incentives: {incentives_count}")
    
    # Save combined outputs
    if all_programs:
        jsonl_path, json_path = save_combined_outputs(combined_dir, all_programs)
        print(f"\nCombined outputs:")
        print(f"  - {jsonl_path}")
        print(f"  - {json_path}")
    
    # Calculate run duration
    run_end = datetime.now()
    run_duration = (run_end - run_start).total_seconds()
    
    # Save run summary
    success_count = sum(1 for r in brand_results if r["status"] == "success")
    error_count = len(brand_results) - success_count
    
    run_info = {
        "run_name": run_name,
        "mode": "discovery",
        "run_start": run_start.isoformat(),
        "run_end": run_end.isoformat(),
        "run_duration_seconds": run_duration,
        "input_file": input_path,
        "settings": {
            "llm_model": model if not skip_llm else "disabled",
            "fetcher": "playwright" if use_playwright else "requests",
            "delay_seconds": delay,
            "max_urls_per_brand": max_urls
        },
        "summary": {
            "total_brands": len(brands),
            "success": success_count,
            "errors": error_count
        },
        "brand_results": brand_results
    }
    
    summary_path = save_run_summary(run_dir, run_info)
    print(f"Run summary: {summary_path}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("DISCOVERY MODE SUMMARY")
    print("=" * 60)
    print(f"Run: {run_name}")
    print(f"Duration: {run_duration:.1f}s")
    print(f"Brands: {len(brands)} | Success: {success_count} | Errors: {error_count}")
    print()
    
    for result in brand_results:
        status_icon = "✓" if result["status"] == "success" else "✗"
        if result["status"] == "success":
            print(f"  {status_icon} {result['brand']}: {result['urls_discovered']} URLs, {result['pages_fetched']} pages")
            print(f"      → {result['tiers']} tiers, {result['badges']} badges, {result['products']} products")
        else:
            print(f"  {status_icon} {result['brand']}: {result.get('error', 'Unknown error')[:50]}")
    
    print()
    print(f"Output folder: {run_dir}")
    print("=" * 60)
    
    return 0 if error_count == 0 else 1


def main():
    parser = argparse.ArgumentParser(
        description="Loyalty Program Web Scraper - Extract structured loyalty data from brand websites"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to input CSV file"
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output directory for raw HTML and structured JSON"
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Enable auto-discovery mode (input format: brand,domain)"
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM classification (parse-only mode)"
    )
    parser.add_argument(
        "--use-playwright",
        action="store_true",
        help="Use Playwright for JS-rendered pages (requires: pip install playwright)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Delay between requests in seconds (default: 1.5)"
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model to use for classification (default: gpt-4o-mini)"
    )
    parser.add_argument(
        "--max-urls",
        type=int,
        default=15,
        help="Maximum URLs to discover per brand in discovery mode (default: 15)"
    )
    
    args = parser.parse_args()
    
    if args.discover:
        # Stage 2: Auto-discovery mode
        return run_discovery_pipeline(
            input_path=args.input,
            output_path=args.output,
            skip_llm=args.skip_llm,
            use_playwright=args.use_playwright,
            delay=args.delay,
            model=args.model,
            max_urls=args.max_urls
        )
    else:
        # Stage 1: Legacy mode with manual URLs
        return run_pipeline(
            input_path=args.input,
            output_path=args.output,
            skip_llm=args.skip_llm,
            use_playwright=args.use_playwright,
            delay=args.delay,
            model=args.model
        )


if __name__ == "__main__":
    sys.exit(main())
