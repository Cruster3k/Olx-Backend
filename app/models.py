from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ListingBase(BaseModel):
    id: str
    title: str
    price: float
    url: str
    category: Optional[str] = None
    model: Optional[str] = None
    condition: Optional[str] = None
    city: Optional[str] = None

class Listing(ListingBase):
    created_at: datetime
    scanned_at: datetime

class ListingResponse(BaseModel):
    total: int
    listings: List[Listing]
