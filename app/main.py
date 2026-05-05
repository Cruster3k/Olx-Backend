from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import get_db_connection, init_db
from .locations import distance_km as calculate_distance_km
from .locations import enrich_location, get_city_info, normalize_location, normalize_province
from .models import Listing, ListingResponse
from .scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
NEW_WINDOW = timedelta(minutes=60)
VALID_TABS = {"all", "deals", "new", "pending", "watchlist"}
VALID_AVAILABILITY_FILTERS = {"", "active", "available", "unavailable", "unknown", "all"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    init_db()
    logger.info("Starting background scheduler...")
    start_scheduler()
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="OLX Flip Scanner API",
    description="Production-ready OLX scraper with background scheduling",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def parse_datetime(value):
    if not value:
        return None

    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                parsed = None
        if parsed is None:
            return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def bool_from_db(value):
    return bool(int(value or 0))


def row_value(row, key, default=None):
    try:
        return row[key]
    except (KeyError, IndexError):
        return default


def is_recent_time(value, now=None):
    parsed = parse_datetime(value)
    if parsed is None:
        return False

    now = now or datetime.now(timezone.utc)
    age = now - parsed
    return timedelta(0) <= age <= NEW_WINDOW


def is_recent_listing(row, now=None):
    now = now or datetime.now(timezone.utc)
    created_at = parse_datetime(row_value(row, "created_at"))
    fallback_at = (
        parse_datetime(row_value(row, "first_seen_at"))
        or parse_datetime(row_value(row, "scanned_at"))
    )
    reference_time = created_at or fallback_at

    if reference_time is None:
        return False

    age = now - reference_time
    return timedelta(0) <= age <= NEW_WINDOW


def compute_is_opportunity(listing):
    return (
        listing["availability_status"] == "active"
        and bool(listing["url"])
        and listing["deal_label"] in {"hot_deal", "good_deal"}
        and listing["price"] > 0
        and listing["market_median"] is not None
        and listing["discount_pct"] >= 20
        and not listing["is_suspicious"]
    )


def listing_from_row(row, now=None):
    price = float(row_value(row, "price", 0) or 0)
    discount_pct = float(row_value(row, "discount_pct", 0) or 0)
    market_median = row_value(row, "market_median")
    deal_score = float(row_value(row, "deal_score", 0) or 0)
    city = row_value(row, "city")
    fallback_location = enrich_location(city)
    latitude = row_value(row, "latitude")
    longitude = row_value(row, "longitude")
    is_new = is_recent_listing(row, now=now)
    availability_status = row_value(row, "availability_status", "unknown") or "unknown"
    deal_label = row_value(row, "deal_label", "none") or "none"

    listing = {
        "id": str(row_value(row, "id", "")),
        "title": row_value(row, "title", "") or "Untitled listing",
        "price": price,
        "url": row_value(row, "url", "") or "",
        "category": row_value(row, "category"),
        "model": row_value(row, "model"),
        "condition": row_value(row, "condition"),
        "city": city,
        "location_normalized": row_value(row, "location_normalized") or fallback_location["location_normalized"],
        "province": row_value(row, "province") or fallback_location["province"],
        "region": row_value(row, "region") or fallback_location["region"],
        "latitude": latitude if latitude is not None else fallback_location["latitude"],
        "longitude": longitude if longitude is not None else fallback_location["longitude"],
        "distance_km": None,
        "thumb": row_value(row, "thumb"),
        "created_display": row_value(row, "created_display"),
        "created_at": row_value(row, "created_at"),
        "first_seen_at": row_value(row, "first_seen_at"),
        "last_seen_at": row_value(row, "last_seen_at"),
        "scanned_at": row_value(row, "scanned_at"),
        "listing_status": row_value(row, "listing_status", "unknown") or "unknown",
        "availability_status": availability_status,
        "availability_checked_at": row_value(row, "availability_checked_at"),
        "unavailable_at": row_value(row, "unavailable_at"),
        "is_new": is_new,
        "discount_pct": discount_pct,
        "market_median": float(market_median) if market_median is not None else None,
        "deal_label": deal_label,
        "deal_score": deal_score,
        "is_suspicious": bool_from_db(row_value(row, "is_suspicious", 0)),
        "is_opportunity": False,
    }

    if listing["availability_status"] != "active":
        listing["deal_label"] = "none"
        listing["deal_score"] = 0

    listing["is_opportunity"] = compute_is_opportunity(listing)
    return listing


def matches_tab(listing, tab, now=None):
    if tab == "all":
        return True
    if tab == "new":
        if listing["availability_status"] == "unavailable":
            return False
        if listing["availability_status"] == "unknown":
            return is_recent_time(listing["last_seen_at"], now=now)
        return listing["is_new"]
    if tab == "pending":
        return listing["listing_status"] == "pending"
    if tab == "deals":
        return listing["is_opportunity"]
    if tab == "watchlist":
        return True
    return True


def matches_availability(listing, availability):
    availability = (availability or "").lower()
    if availability not in VALID_AVAILABILITY_FILTERS:
        availability = ""

    if availability == "all":
        return True
    if availability == "active":
        return listing["availability_status"] == "active"
    if availability == "unavailable":
        return listing["availability_status"] == "unavailable"
    if availability == "unknown":
        return listing["availability_status"] == "unknown"

    return listing["availability_status"] != "unavailable"


def matches_location_text(listing, location_filter):
    if not location_filter:
        return True
    return location_filter in (listing["location_normalized"] or "")


def matches_province(listing, province_filter):
    if not province_filter:
        return True
    return normalize_province(listing["province"]) == province_filter


def apply_radius_filter(listings, origin, radius_km):
    if not origin or not radius_km:
        return listings

    filtered = []
    for listing in listings:
        distance = calculate_distance_km(
            origin["latitude"],
            origin["longitude"],
            listing["latitude"],
            listing["longitude"],
        )
        if distance is not None and distance <= radius_km:
            listing["distance_km"] = distance
            filtered.append(listing)
    return filtered


def apply_sort(listings, sort, tab):
    sort_key = sort or ("best" if tab == "deals" else "newest")

    if sort_key == "price":
        listings.sort(key=lambda item: item["price"])
    elif sort_key == "price_desc":
        listings.sort(key=lambda item: item["price"], reverse=True)
    elif sort_key == "newest":
        listings.sort(
            key=lambda item: (
                parse_datetime(item["created_at"])
                or parse_datetime(item["first_seen_at"])
                or parse_datetime(item["last_seen_at"])
                or datetime.min.replace(tzinfo=timezone.utc)
            ),
            reverse=True,
        )
    elif sort_key == "oldest":
        listings.sort(
            key=lambda item: (
                parse_datetime(item["created_at"])
                or parse_datetime(item["first_seen_at"])
                or parse_datetime(item["last_seen_at"])
                or datetime.max.replace(tzinfo=timezone.utc)
            ),
        )
    elif sort_key == "discount":
        listings.sort(key=lambda item: (item["discount_pct"], item["deal_score"]), reverse=True)
    else:
        listings.sort(key=lambda item: (item["deal_score"], item["discount_pct"]), reverse=True)


@app.get("/", include_in_schema=False)
def frontend():
    """Serve the OLX Flip Scanner Pro frontend."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/listings", response_model=ListingResponse, tags=["Listings"])
def get_listings(
    tab: str = Query("all", description="UI tab: all, deals, new, pending, watchlist"),
    search: str = Query(None, description="Search keyword in title or model"),
    category: str = Query(None, description="Product category"),
    city: str = Query(None, description="Filter by city/location"),
    location: str = Query(None, description="Alias for city/location filter"),
    radius_km: float = Query(None, ge=0, le=300, description="Nearby city radius in km"),
    province: str = Query(None, description="Filter by Polish province/wojewodztwo"),
    condition: str = Query(None, description="Filter by condition"),
    availability: str = Query(None, description="Availability filter: active, unavailable, unknown, all"),
    sort: str = Query(None, description="Sort: best, discount, newest, oldest, price, price_desc"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Get listings with tab, product category, location, search, and pagination filters."""
    tab = (tab or "all").lower()
    if tab not in VALID_TABS:
        tab = "all"

    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM listings WHERE 1=1"
    params = []

    if search:
        query += " AND (title LIKE ? OR model LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param])

    if category:
        query += " AND category = ?"
        params.append(category)

    if condition:
        query += " AND condition = ?"
        params.append(condition)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    now = datetime.now(timezone.utc)
    listings = [listing_from_row(row, now=now) for row in rows]

    location_text = city or location
    location_filter = normalize_location(location_text)
    radius_origin = get_city_info(location_text) if location_text and radius_km else None
    province_filter = normalize_province(province) if province else None

    if radius_origin and radius_km:
        listings = apply_radius_filter(listings, radius_origin, radius_km)
    elif location_filter:
        listings = [listing for listing in listings if matches_location_text(listing, location_filter)]

    if province_filter:
        listings = [listing for listing in listings if matches_province(listing, province_filter)]

    listings = [listing for listing in listings if matches_availability(listing, availability)]
    listings = [listing for listing in listings if matches_tab(listing, tab, now=now)]

    apply_sort(listings, sort, tab)
    total = len(listings)
    paged = listings[offset:offset + limit]

    return ListingResponse(total=total, listings=[Listing(**listing) for listing in paged])


@app.get("/listings/stats", tags=["Analytics"])
def get_stats():
    """Get listing counts used by the frontend dashboard."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM listings")
    rows = cursor.fetchall()
    conn.close()

    now = datetime.now(timezone.utc)
    listings = [listing_from_row(row, now=now) for row in rows]
    total = len(listings)
    active_count = sum(1 for listing in listings if listing["availability_status"] == "active")
    unknown_count = sum(1 for listing in listings if listing["availability_status"] == "unknown")
    unavailable_count = sum(1 for listing in listings if listing["availability_status"] == "unavailable")
    deals_count = sum(1 for listing in listings if listing["is_opportunity"])
    new_count = sum(1 for listing in listings if matches_tab(listing, "new", now=now))
    pending_count = sum(
        1
        for listing in listings
        if listing["listing_status"] == "pending" and listing["availability_status"] != "unavailable"
    )
    scan_times = [parse_datetime(listing["scanned_at"]) for listing in listings if parse_datetime(listing["scanned_at"])]
    last_scan_dt = max(scan_times) if scan_times else None
    last_scan = last_scan_dt.isoformat() if last_scan_dt else None

    by_category = {}
    for listing in listings:
        key = listing["category"] or "unknown"
        by_category[key] = by_category.get(key, 0) + 1

    return {
        "total_listings": total,
        "active_count": active_count,
        "unknown_count": unknown_count,
        "unavailable_count": unavailable_count,
        "deals_count": deals_count,
        "new_count": new_count,
        "pending_count": pending_count,
        "last_scan": last_scan,
        "status": "ok",
        "by_category": by_category,
        "latest_scrape": last_scan,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
