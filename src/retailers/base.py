from __future__ import annotations

from abc import ABC
from pathlib import Path
import json
import re
import time
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

from src.config import ROOT, load_yaml
from src.models import Product


UA = "Mozilla/5.0 (compatible; YestahlWalaLa/1.0; pharmacist content research; +https://github.com/)"


def parse_price(value) -> Optional[float]:
    if value is None:
        return None
    match = re.search(r"(?:AED|د\.?إ\.?)?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", str(value), re.I)
    return float(match.group(1).replace(",", "")) if match else None


def parse_pack(text: str) -> Dict[str, Optional[int]]:
    text = text or ""
    result = {"volume_ml": None, "tablet_count": None, "capsule_count": None,
              "sachet_count": None, "piece_count": None}
    patterns = {
        "volume_ml": r"(\d+(?:\.\d+)?)\s*(?:ml|millilit(?:er|re)s?)\b",
        "tablet_count": r"(\d+)\s*(?:tablets?|tabs?)\b",
        "capsule_count": r"(\d+)\s*(?:capsules?|caps?)\b",
        "sachet_count": r"(\d+)\s*sachets?\b",
        "piece_count": r"(\d+)\s*(?:pieces?|pcs?)\b",
    }
    for field, pattern in patterns.items():
        match = re.search(pattern, text, re.I)
        if match:
            result[field] = int(float(match.group(1)))
    return result


def _nodes(data) -> Iterable[dict]:
    if isinstance(data, list):
        for item in data:
            yield from _nodes(item)
    elif isinstance(data, dict):
        if "@graph" in data:
            yield from _nodes(data["@graph"])
        yield data


def parse_jsonld_products(html: str, retailer: str, category: str, page_url: str) -> List[Product]:
    soup = BeautifulSoup(html, "html.parser")
    products: List[Product] = []
    seen = set()
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        for node in _nodes(data):
            kind = node.get("@type")
            if isinstance(kind, list):
                is_product = "Product" in kind
            else:
                is_product = kind == "Product"
            if not is_product:
                continue
            offers = node.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            aggregate = node.get("aggregateRating") or {}
            brand = node.get("brand")
            if isinstance(brand, dict):
                brand = brand.get("name")
            image = node.get("image")
            images = image if isinstance(image, list) else ([image] if image else [])
            name = node.get("name")
            url = urljoin(page_url, node.get("url") or page_url)
            if not name or (name, url) in seen:
                continue
            seen.add((name, url))
            pack = parse_pack(name)
            availability = offers.get("availability")
            products.append(Product(
                product_name=str(name).strip(), brand=brand, retailer=retailer,
                product_url=url, category=category,
                price_aed=parse_price(offers.get("price") or offers.get("lowPrice")),
                old_price_aed=None, retailer_sku=str(node.get("sku")) if node.get("sku") else None,
                ean=str(node.get("gtin13") or node.get("gtin")) if (node.get("gtin13") or node.get("gtin")) else None,
                pack_size=next((m.group(0) for m in re.finditer(r"\b\d+(?:\.\d+)?\s*(?:ml|g|tablets?|capsules?|sachets?|pcs?)\b", name, re.I)), None),
                rating=parse_price(aggregate.get("ratingValue")),
                reviews_count=int(float(aggregate["reviewCount"])) if aggregate.get("reviewCount") else None,
                availability=("InStock" in availability) if availability else None,
                primary_image=images[0] if images else None, secondary_images=images[1:],
                retailer_description=node.get("description"), **pack,
            ))
    return products


def parse_html_product(html: str, retailer: str, category: str, page_url: str) -> Optional[Product]:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    if not heading:
        return None
    name = heading.get_text(" ", strip=True)
    if not name:
        return None
    def meta(*keys):
        for key in keys:
            node = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key}) or soup.find("meta", attrs={"itemprop": key})
            if node and node.get("content"):
                return node["content"]
        return None
    body = soup.get_text(" ", strip=True)
    price = parse_price(meta("product:price:amount", "price", "og:price:amount"))
    if price is None:
        match = re.search(r"(?:AED|D|د\.?إ\.?)\s*([0-9]+(?:\.[0-9]{1,2})?)", body, re.I)
        price = parse_price(match.group(1)) if match else None
    old_price = parse_price(meta(
        "product:original_price:amount", "product:regular_price:amount",
        "og:price:standard_amount", "original_price", "old_price",
    ))
    if old_price is not None and price is not None and old_price <= price:
        old_price = None
    discount = round((old_price - price) / old_price * 100, 2) if old_price and price is not None else None
    sku_match = re.search(r"\bSKU\s*[:#]?\s*([A-Za-z0-9-]+)", body, re.I)
    pack = parse_pack(name)
    pack_match = re.search(r"\b\d+(?:\.\d+)?\s*(?:ml|g|tablets?|capsules?|sachets?|pcs?)\b", name, re.I)
    description = meta("description", "og:description")
    return Product(product_name=name, brand=None, retailer=retailer, product_url=page_url,
                   category=category, price_aed=price, old_price_aed=old_price,
                   discount_percentage=discount, offer_flag=old_price is not None,
                   retailer_sku=sku_match.group(1) if sku_match else None,
                   pack_size=pack_match.group(0) if pack_match else None, primary_image=meta("og:image", "twitter:image"),
                   retailer_description=description, availability=("out of stock" not in body.lower()), **pack)


class RetailerAdapter(ABC):
    key = ""

    def __init__(self, session: Optional[requests.Session] = None):
        cfg = load_yaml("retailers.yaml")["retailers"][self.key]
        settings = load_yaml("settings.yaml")["selection"]
        self.name, self.base_url, self.search_url = cfg["name"], cfg["base_url"], cfg["search_url"]
        self.timeout, self.retries = settings["timeout_seconds"], settings["max_retries"]
        self.delay = settings["request_delay_seconds"]
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": UA, "Accept-Language": "en-AE,en;q=0.8"})
        self.requests_used = 0

    def fetch(self, url: str) -> str:
        cache = ROOT / "data" / "cache"
        cache.mkdir(parents=True, exist_ok=True)
        key = __import__("hashlib").sha256(url.encode()).hexdigest()
        path = cache / f"{self.key}-{key}.html"
        if path.exists() and time.time() - path.stat().st_mtime < 21600:
            return path.read_text(encoding="utf-8")
        last = None
        for attempt in range(self.retries + 1):
            self.requests_used += 1
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                path.write_text(response.text, encoding="utf-8")
                time.sleep(self.delay)
                return response.text
            except requests.RequestException as exc:
                last = exc
                if attempt < self.retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"{self.name} fetch failed safely: {last}")

    def discover(self, query: str, category: str) -> List[Product]:
        url = self.search_url.format(query=quote_plus(query))
        html = self.fetch(url)
        products = parse_jsonld_products(html, self.name, category, url)
        if products:
            return products
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for anchor in soup.select("a[href]"):
            href = anchor.get("href", "")
            if "/product" in href or "/p/" in href:
                full = urljoin(self.base_url, href)
                if full not in links:
                    links.append(full)
            if len(links) >= 8:
                break
        found = []
        for link in links:
            found.extend(parse_jsonld_products(self.fetch(link), self.name, category, link))
        return found

    def product(self, url: str, category: str) -> Product:
        html = self.fetch(url)
        products = parse_jsonld_products(html, self.name, category, url)
        product = products[0] if products else parse_html_product(html, self.name, category, url)
        if not product:
            raise RuntimeError(f"No product data found at {url}")
        return product
