from pydantic import BaseModel
from typing import Optional, List

class ListingBase(BaseModel):
    id: str
    title: str
    price: float
    url: str
    category: Optional[str] = None
    model: Optional[str] = None
    condition: Optional[str] = None
    city: Optional[str] = None
    location_normalized: Optional[str] = None
    province: Optional[str] = None
    region: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_km: Optional[float] = None
    thumb: Optional[str] = None
    created_display: Optional[str] = None
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    listing_status: str = "unknown"
    availability_status: str = "unknown"
    availability_checked_at: Optional[str] = None
    unavailable_at: Optional[str] = None
    is_new: bool = False
    discount_pct: float = 0
    market_median: Optional[float] = None
    deal_label: str = "none"
    deal_score: float = 0
    is_opportunity: bool = False
    is_suspicious: bool = False

class Listing(ListingBase):
    created_at: Optional[str] = None
    scanned_at: Optional[str] = None

class ListingResponse(BaseModel):
    total: int
    listings: List[Listing]
