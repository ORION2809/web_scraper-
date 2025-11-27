import argparse
import json
import sys
import time
from typing import List

import requests
from bs4 import BeautifulSoup


def read_urls(path: str) -> List[str]:
    urls = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            urls.append(line)
    return urls


def fetch_url(url: str, timeout: int = 10):
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "web-scraper/1.0"})
        resp.raise_for_status()
        return resp.text, None
    except Exception as e:
        return None, str(e)


def parse_html(html: str):
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.title.string.strip() if soup.title and soup.title.string else ""
    # meta description
    description = ""
    desc_tag = soup.find("meta", attrs={"name": "description"})
    if desc_tag and desc_tag.get("content"):
        description = desc_tag.get("content").strip()
    # text snippet: first 200 chars of body text
    body = soup.body.get_text(separator=" ") if soup.body else soup.get_text(separator=" ")
    snippet = " ".join(body.split())[:200]
    return {"title": title_tag, "description": description, "snippet": snippet}


def scrape(input_path: str, output_path: str, delay: float = 0.5, timeout: int = 10):
    urls = read_urls(input_path)
    if not urls:
        print(f"No URLs found in {input_path}")
        return 1

    with open(output_path, "w", encoding="utf-8") as out:
        for i, url in enumerate(urls, start=1):
            print(f"[{i}/{len(urls)}] Fetching: {url}")
            html, err = fetch_url(url, timeout=timeout)
            record = {"url": url}
            if err:
                record.update({"status": "error", "error": err})
                print(f"  Error: {err}")
            else:
                parsed = parse_html(html)
                record.update({"status": "ok", **parsed})
                print(f"  OK: title='{parsed.get('title','')}'")

            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            time.sleep(delay)

    print(f"Finished. Output written to {output_path}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Simple URL list web scraper -> JSONL output")
    parser.add_argument("--input", "-i", required=True, help="Path to input file with one URL per line")
    parser.add_argument("--output", "-o", required=True, help="Path to output JSONL file")
    parser.add_argument("--delay", "-d", type=float, default=0.5, help="Delay between requests in seconds (default: 0.5)")
    parser.add_argument("--timeout", "-t", type=int, default=10, help="Request timeout seconds (default: 10)")
    args = parser.parse_args(argv)
    return scrape(args.input, args.output, delay=args.delay, timeout=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
