from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from src.config import ROOT
from src.models import Product


class History:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or ROOT / "data" / "runtime" / "history.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path))
        self.db.execute("""CREATE TABLE IF NOT EXISTS posts (
          publication_key TEXT PRIMARY KEY, product_id TEXT NOT NULL, date TEXT NOT NULL,
          category TEXT, retailer TEXT, product_url TEXT, price REAL, pack_size TEXT,
          rating REAL, reviews INTEGER, score REAL, verdict TEXT, version INTEGER,
          content_hash TEXT, status TEXT, approved_at TEXT, published_at TEXT,
          instagram_media_id TEXT, instagram_permalink TEXT, payload TEXT)""")
        self.db.commit()

    def used_recently(self, product_id: str, days: int = 90) -> bool:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
        row = self.db.execute("SELECT 1 FROM posts WHERE product_id=? AND date>=? LIMIT 1", (product_id, cutoff)).fetchone()
        return bool(row)

    def upsert(self, publication_key: str, product: Product, status: str, **fields):
        payload = product.to_dict()
        payload.update(fields)
        values = (publication_key, product.normalized_id, datetime.now(timezone.utc).date().isoformat(),
                  product.category, product.retailer, product.product_url, product.price_aed,
                  product.pack_size, product.rating, product.reviews_count, fields.get("score"),
                  fields.get("verdict"), fields.get("version", 1), fields.get("content_hash"), status,
                  fields.get("approved_at"), fields.get("published_at"), fields.get("instagram_media_id"),
                  fields.get("instagram_permalink"), json.dumps(payload, ensure_ascii=False))
        self.db.execute("INSERT OR REPLACE INTO posts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)
        self.db.commit()

    def publication_status(self, key: str):
        row = self.db.execute("SELECT status, instagram_media_id, instagram_permalink FROM posts WHERE publication_key=?", (key,)).fetchone()
        return row
