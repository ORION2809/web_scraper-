"""
Loyalty Program Web Scraper - Main Pipeline

Usage:
    python loyalty_scraper.py --input seeds.csv --output output/
    python loyalty_scraper.py --input seeds.csv --output output/ --skip-llm
    python loyalty_scraper.py --input seeds.csv --output output/ --use-playwright
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fetcher import fetch_url, FetchResult
from parser import parse_html
from classifier import classify
from schemas import LoyaltyProgram, ParsedContent


def load_seeds(path: str) -> List[Dict[str, str]]:
    """Load seed URLs from CSV file"""
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


def create_run_folder(base_output: str) -> Dict[str, Path]:
    """
    Create a timestamped run folder with organized subfolders.
    
    Structure:
    output/
    └── run_20251127_143022/
        ├── raw/                    # Raw HTML snapshots
        │   └── starbucks_terms.html
        ├── structured/             # Individual brand JSON files
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


def main():
    parser = argparse.ArgumentParser(
        description="Loyalty Program Web Scraper - Extract structured loyalty data from brand websites"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to seeds CSV file (columns: brand, url, page_type)"
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output directory for raw HTML and structured JSON"
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
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model to use for classification (default: gpt-4o-mini)"
    )
    
    args = parser.parse_args()
    
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
