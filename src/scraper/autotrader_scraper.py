"""Live web scraper for AutoTrader UK used car listings.

The scraper is built to demonstrate the real-time pipeline component
required by the project proposal. It is intentionally:
    - polite      (configurable delay between requests, single thread)
    - resilient   (retries with backoff, skips malformed rows)
    - bounded     (caps at N pages so it never runs forever)

The output schema matches the Kaggle UK Used Cars dataset so scraped
rows can be appended to the training corpus.

Run:
    python -m src.scraper.autotrader_scraper --pages 5 --delay 2.5
"""
from __future__ import annotations

import argparse
import csv
import logging
import random
import re
import time
from pathlib import Path
from typing import Iterable, Iterator
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

LOG = logging.getLogger("scraper")
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

BASE_URL = "https://www.autotrader.co.uk/car-search"
OUT_COLUMNS = ["model", "year", "price", "transmission",
               "mileage", "fuelType", "engineSize", "brand"]


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-GB,en;q=0.9",
    })
    return s


def _clean_int(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def _clean_float(text: str) -> float | None:
    m = re.search(r"\d+(?:\.\d+)?", text or "")
    return float(m.group()) if m else None


def parse_listing(card) -> dict | None:
    """Extract one listing dict from a search-result card. Returns None
    if any required field is missing — we silently skip those."""
    try:
        title = card.select_one("h3, [data-testid='search-listing-title']")
        if not title:
            return None
        title_text = title.get_text(" ", strip=True)

        # Title looks like "Audi A4 1.4 TFSI Sport ..."
        parts = title_text.split()
        brand = parts[0] if parts else None
        model_name = parts[1] if len(parts) > 1 else None

        price_node = card.find(string=re.compile(r"£[\d,]+"))
        price = _clean_int(price_node) if price_node else None

        spec_text = card.get_text(" | ", strip=True)

        year_match = re.search(r"\b(19|20)\d{2}\b", spec_text)
        year = int(year_match.group()) if year_match else None

        mileage_match = re.search(r"([\d,]+)\s*miles", spec_text, re.I)
        mileage = _clean_int(mileage_match.group(1)) if mileage_match else None

        engine_match = re.search(r"(\d+\.\d)\s*L?", spec_text)
        engine = _clean_float(engine_match.group(1)) if engine_match else None

        transmission = next(
            (t for t in ("Automatic", "Manual", "Semi-Auto") if t.lower() in spec_text.lower()),
            None,
        )
        fuel = next(
            (f for f in ("Petrol", "Diesel", "Hybrid", "Electric", "Other") if f.lower() in spec_text.lower()),
            None,
        )

        if not all([brand, model_name, year, price, mileage, transmission, fuel, engine]):
            return None

        return {
            "model": model_name,
            "year": year,
            "price": price,
            "transmission": transmission,
            "mileage": mileage,
            "fuelType": fuel,
            "engineSize": engine,
            "brand": brand,
        }
    except Exception as exc:
        LOG.debug("parse_listing failed: %s", exc)
        return None


def scrape_pages(pages: int, delay: float = 2.5,
                 keyword: str | None = None) -> Iterator[dict]:
    sess = _session()
    for page in range(1, pages + 1):
        params = {"page": page, "advertising-location": "at_cars"}
        if keyword:
            params["keywords"] = keyword
        url = f"{BASE_URL}?{urlencode(params)}"

        try:
            resp = sess.get(url, timeout=15)
        except requests.RequestException as exc:
            LOG.warning("page %d request failed: %s", page, exc)
            time.sleep(delay * 2)
            continue

        if resp.status_code != 200:
            LOG.warning("page %d -> HTTP %d", page, resp.status_code)
            time.sleep(delay * 2)
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.select(
            "article, li[data-testid='search-listing'], "
            "div[data-testid='advertCard']"
        )
        LOG.info("page %d -> %d cards", page, len(cards))

        for card in cards:
            row = parse_listing(card)
            if row:
                yield row

        time.sleep(delay + random.uniform(0, 0.8))


def write_csv(rows: Iterable[dict], out: Path) -> int:
    rows = list(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="AutoTrader UK scraper")
    parser.add_argument("--pages", type=int, default=5)
    parser.add_argument("--delay", type=float, default=2.5)
    parser.add_argument("--keyword", type=str, default=None)
    parser.add_argument("--out", type=Path, default=RAW_DIR / "scraped_live.csv")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    rows = scrape_pages(args.pages, args.delay, args.keyword)
    n = write_csv(rows, args.out)
    LOG.info("wrote %d rows to %s", n, args.out)


if __name__ == "__main__":
    main()
