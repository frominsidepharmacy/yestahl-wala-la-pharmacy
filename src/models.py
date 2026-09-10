from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Dict, List, Optional


STATUSES = {
    "DISCOVERED", "RESEARCHING", "REJECTED_DATA", "REJECTED_EVIDENCE",
    "DRAFTING", "QC", "PENDING_APPROVAL", "EDIT_REQUESTED", "REJECTED_USER",
    "APPROVED", "PUBLISHING", "PUBLISHED", "PUBLISH_FAILED_SAFE",
}


@dataclass
class Product:
    product_name: str
    brand: Optional[str]
    retailer: str
    product_url: str
    category: str
    price_aed: Optional[float] = None
    old_price_aed: Optional[float] = None
    discount_percentage: Optional[float] = None
    best_offer_price_aed: Optional[float] = None
    best_offer_retailer: Optional[str] = None
    retailer_sku: Optional[str] = None
    ean: Optional[str] = None
    pack_size: Optional[str] = None
    volume_ml: Optional[int] = None
    tablet_count: Optional[int] = None
    capsule_count: Optional[int] = None
    sachet_count: Optional[int] = None
    piece_count: Optional[int] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    availability: Optional[bool] = None
    bestseller_flag: Optional[bool] = None
    new_flag: Optional[bool] = None
    offer_flag: Optional[bool] = None
    primary_image: Optional[str] = None
    secondary_images: List[str] = field(default_factory=list)
    retailer_description: Optional[str] = None
    ingredients: List[str] = field(default_factory=list)
    usage: Optional[str] = None
    written_side_effects: List[str] = field(default_factory=list)
    available_sizes: List[str] = field(default_factory=list)
    competitive_advantage: Optional[str] = None
    competitive_advantage_source: Optional[str] = None
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def normalized_id(self) -> str:
        if self.ean:
            key = f"ean:{self.ean}:{self.pack_signature}"
        else:
            raw = f"{self.brand or ''} {self.product_name}".lower()
            name = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
            key = f"name:{name}:{self.pack_signature}"
        return sha256(key.encode()).hexdigest()[:20]

    @property
    def pack_signature(self) -> str:
        parts = [self.pack_size, self.volume_ml, self.tablet_count, self.capsule_count,
                 self.sachet_count, self.piece_count]
        return "|".join("" if p is None else str(p).lower().replace(" ", "") for p in parts)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["product_id"] = self.normalized_id
        return data


@dataclass
class Claim:
    claim_id: str
    claim_text: str
    source_url: str
    source_type: str
    evidence_strength: int
    retrieved_at: str


def stable_hash(slides: List[bytes], caption: str, metadata: Dict[str, Any]) -> str:
    digest = sha256()
    for slide in slides:
        digest.update(slide)
    digest.update(caption.encode("utf-8"))
    digest.update(json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
    return digest.hexdigest()
