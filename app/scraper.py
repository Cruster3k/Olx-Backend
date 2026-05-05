import logging
import random
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests

from .database import get_db_connection
from .locations import enrich_location, normalize_location

logger = logging.getLogger(__name__)

OLX_API_BASE = "https://www.olx.pl/api/v1/offers/"
MAX_AVAILABILITY_CHECKS_PER_CYCLE = 20
AVAILABILITY_TIMEOUT_SECONDS = 8
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

PAGE_HEADERS = {
    **HEADERS,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

UNAVAILABLE_PHRASES = [
    "ogloszenie nieaktualne",
    "to ogloszenie jest nieaktualne",
    "oferta nieaktywna",
    "nie znaleziono",
    "strona nie istnieje",
    "ogloszenie zostalo usuniete",
]

# These are OLX product buckets, not UI tabs.
CATEGORIES = {
    "iphone": {"category_id": 2298},
    "oneplus": {"category_id": 2306},
    "poco": {"category_id": 2308},
    "samsung": {"category_id": 2310},
    "macbook": {"query": "macbook"},
    "playstation": {"category_id": 2268},
    "xbox": {"category_id": 2269},
}

DAMAGED_KEYWORDS = [
    "uszkodzony", "uszkodzona", "uszkodzone", "broken", "cracked", "zbity",
    "zbita", "zbite", "peknięty", "pekniety", "pęknięty", "rozbity",
    "rozbita", "na części", "na czesci", "defekt", "wada", "serwis",
]

SUSPICIOUS_KEYWORDS = [
    "kupie", "kupię", "szukam", "zamiana", "wymiana", "replika", "fake",
    "blokada", "icloud", "simlock", "konto", "account", "raty", "leasing",
]

ACCESSORY_KEYWORDS = [
    "etui", "case", "pudełko", "pudelko", "kabel", "ładowarka", "ladowarka",
    "szkło", "szklo", "folia", "uchwyt", "stojak", "klawisz", "klawiatura",
    "torba", "pokrowiec", "naklejka",
]

CONSOLE_ACCESSORY_KEYWORDS = [
    "gra", "gry", "game", "games", "pad", "kontroler", "controller", "psn",
    "kod", "voucher", "płyta", "plyta", "cd", "dvd", "blu-ray", "gamepass",
    "gold", "headset", "słuchawki", "sluchawki",
]

MODEL_PATTERNS = {
    "iphone": [
        (r"iphone\s*17", "iPhone 17"),
        (r"iphone\s*16\s*pro\s*max", "iPhone 16 Pro Max"),
        (r"iphone\s*16\s*pro", "iPhone 16 Pro"),
        (r"iphone\s*16\s*plus", "iPhone 16 Plus"),
        (r"iphone\s*16", "iPhone 16"),
        (r"iphone\s*15\s*pro\s*max", "iPhone 15 Pro Max"),
        (r"iphone\s*15\s*pro", "iPhone 15 Pro"),
        (r"iphone\s*15\s*plus", "iPhone 15 Plus"),
        (r"iphone\s*15", "iPhone 15"),
        (r"iphone\s*14\s*pro\s*max", "iPhone 14 Pro Max"),
        (r"iphone\s*14\s*pro", "iPhone 14 Pro"),
        (r"iphone\s*14\s*plus", "iPhone 14 Plus"),
        (r"iphone\s*14", "iPhone 14"),
        (r"iphone\s*13\s*pro\s*max", "iPhone 13 Pro Max"),
        (r"iphone\s*13\s*pro", "iPhone 13 Pro"),
        (r"iphone\s*13\s*mini", "iPhone 13 Mini"),
        (r"iphone\s*13", "iPhone 13"),
        (r"iphone\s*12\s*pro\s*max", "iPhone 12 Pro Max"),
        (r"iphone\s*12\s*pro", "iPhone 12 Pro"),
        (r"iphone\s*12\s*mini", "iPhone 12 Mini"),
        (r"iphone\s*12", "iPhone 12"),
        (r"iphone\s*11\s*pro\s*max", "iPhone 11 Pro Max"),
        (r"iphone\s*11\s*pro", "iPhone 11 Pro"),
        (r"iphone\s*11", "iPhone 11"),
    ],
    "oneplus": [
        (r"one\s*plus\s*13|oneplus\s*13", "OnePlus 13"),
        (r"one\s*plus\s*12|oneplus\s*12", "OnePlus 12"),
        (r"one\s*plus\s*11|oneplus\s*11", "OnePlus 11"),
        (r"one\s*plus\s*10|oneplus\s*10", "OnePlus 10"),
        (r"one\s*plus\s*nord\s*4|oneplus\s*nord\s*4", "OnePlus Nord 4"),
        (r"one\s*plus\s*nord\s*3|oneplus\s*nord\s*3", "OnePlus Nord 3"),
        (r"one\s*plus\s*nord|oneplus\s*nord", "OnePlus Nord"),
        (r"one\s*plus|oneplus", "OnePlus"),
    ],
    "poco": [
        (r"poco\s*f7", "POCO F7"),
        (r"poco\s*f6", "POCO F6"),
        (r"poco\s*f5", "POCO F5"),
        (r"poco\s*x7", "POCO X7"),
        (r"poco\s*x6", "POCO X6"),
        (r"poco\s*x5", "POCO X5"),
        (r"poco\s*m6", "POCO M6"),
        (r"poco\s*m5", "POCO M5"),
        (r"poco", "POCO"),
    ],
    "samsung": [
        (r"samsung\s*galaxy\s*s25|galaxy\s*s25", "Samsung Galaxy S25"),
        (r"samsung\s*galaxy\s*s24|galaxy\s*s24", "Samsung Galaxy S24"),
        (r"samsung\s*galaxy\s*s23|galaxy\s*s23", "Samsung Galaxy S23"),
        (r"samsung\s*galaxy\s*s22|galaxy\s*s22", "Samsung Galaxy S22"),
        (r"samsung\s*galaxy\s*s21|galaxy\s*s21", "Samsung Galaxy S21"),
        (r"galaxy\s*z\s*fold", "Samsung Galaxy Z Fold"),
        (r"galaxy\s*z\s*flip", "Samsung Galaxy Z Flip"),
        (r"galaxy\s*a\d{2}", "Samsung Galaxy A"),
        (r"samsung", "Samsung"),
    ],
    "macbook": [
        (r"macbook\s*air\s*m4", "MacBook Air M4"),
        (r"macbook\s*air\s*m3", "MacBook Air M3"),
        (r"macbook\s*air\s*m2", "MacBook Air M2"),
        (r"macbook\s*air\s*m1", "MacBook Air M1"),
        (r"macbook\s*pro\s*m4", "MacBook Pro M4"),
        (r"macbook\s*pro\s*m3", "MacBook Pro M3"),
        (r"macbook\s*pro\s*m2", "MacBook Pro M2"),
        (r"macbook\s*pro\s*m1", "MacBook Pro M1"),
        (r"macbook\s*air", "MacBook Air"),
        (r"macbook\s*pro", "MacBook Pro"),
        (r"macbook", "MacBook"),
    ],
    "playstation": [
        (r"playstation\s*5\s*pro|ps5\s*pro", "PS5 Pro"),
        (r"playstation\s*5\s*digital|ps5\s*digital", "PS5 Digital"),
        (r"playstation\s*5|ps5", "PS5"),
        (r"playstation\s*4\s*pro|ps4\s*pro", "PS4 Pro"),
        (r"playstation\s*4|ps4", "PS4"),
    ],
    "xbox": [
        (r"xbox\s*series\s*x", "Xbox Series X"),
        (r"xbox\s*series\s*s", "Xbox Series S"),
        (r"xbox\s*one\s*x", "Xbox One X"),
        (r"xbox\s*one\s*s", "Xbox One S"),
    ],
}


def utc_now():
    return datetime.now(timezone.utc)


def parse_datetime(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_recent(value, fallback):
    reference_time = parse_datetime(value) or parse_datetime(fallback)
    if reference_time is None:
        return False
    age = utc_now() - reference_time
    return timedelta(0) <= age <= timedelta(minutes=60)


def extract_params(offer):
    params = {}
    for param in offer.get("params", []):
        key = param.get("key")
        if key:
            params[key] = param.get("value")
    return params


def extract_price(params):
    price = params.get("price", {})
    if isinstance(price, dict):
        price = price.get("value", 0)
    try:
        return float(price or 0)
    except (TypeError, ValueError):
        return 0.0


def detect_condition(title, description, params):
    state = params.get("state", {})
    if isinstance(state, dict):
        state_key = str(state.get("key", "")).lower()
        if state_key == "new":
            return "new"

    text = f"{title} {description}".lower()
    if any(keyword in text for keyword in DAMAGED_KEYWORDS):
        return "damaged"
    return "used"


def detect_model(title, category):
    title_lower = title.lower()
    for pattern, model in MODEL_PATTERNS.get(category, []):
        if re.search(pattern, title_lower):
            return model
    return None


def detect_listing_status(offer):
    raw_status = offer.get("status")
    status_text = ""
    if isinstance(raw_status, dict):
        status_text = " ".join(str(value) for value in raw_status.values())
    elif raw_status is not None:
        status_text = str(raw_status)

    normalized = status_text.lower()
    if "pending" in normalized or "oczek" in normalized:
        return "pending"
    if normalized == "active":
        return "active"
    return "unknown"


def initial_availability_status(listing_status):
    if listing_status in {"active", "pending", "unknown"}:
        return "active"
    return "unknown"


def check_listing_availability(url):
    checked_at = utc_now().isoformat()
    if not url:
        return "unknown", checked_at, None

    try:
        response = requests.get(
            url,
            headers=PAGE_HEADERS,
            timeout=AVAILABILITY_TIMEOUT_SECONDS,
            allow_redirects=True,
        )
    except requests.RequestException:
        return "unknown", checked_at, None

    if response.status_code in {404, 410}:
        return "unavailable", checked_at, checked_at

    if response.status_code >= 500 or response.status_code in {403, 429}:
        return "unknown", checked_at, None

    normalized_text = normalize_location(response.text[:200000])
    if any(phrase in normalized_text for phrase in UNAVAILABLE_PHRASES):
        return "unavailable", checked_at, checked_at

    if response.status_code == 200:
        return "active", checked_at, None

    return "unknown", checked_at, None


def detect_thumb(offer):
    photos = offer.get("photos", [])
    if not photos:
        return None

    link = photos[0].get("link")
    if not link:
        return None
    return link.replace("{width}", "300").replace("{height}", "300")


def created_display(created_at):
    parsed = parse_datetime(created_at)
    if not parsed:
        return created_at or ""

    local_time = parsed.astimezone(timezone(timedelta(hours=2)))
    now_local = utc_now().astimezone(timezone(timedelta(hours=2)))
    if local_time.date() == now_local.date():
        return local_time.strftime("%H:%M")
    return local_time.strftime("%d.%m %H:%M")


def is_suspicious(title, category, price):
    title_lower = title.lower()
    if any(keyword in title_lower for keyword in SUSPICIOUS_KEYWORDS):
        return True
    if any(keyword in title_lower for keyword in ACCESSORY_KEYWORDS):
        return True
    if category in {"playstation", "xbox"}:
        if price < 300:
            return True
        if any(keyword in title_lower for keyword in CONSOLE_ACCESSORY_KEYWORDS):
            return True
    return False


def fetch_page(category_config, offset=0, limit=50):
    params = {"offset": offset, "limit": limit, "sort_by": "created_at:desc"}
    params.update(category_config)
    response = requests.get(OLX_API_BASE, headers=HEADERS, params=params, timeout=15)
    if response.status_code != 200:
        logger.error("Failed to fetch OLX page: %s", response.status_code)
        return {}
    return response.json()


def parse_offer(offer, category, scanned_at):
    title = offer.get("title") or ""
    params = extract_params(offer)
    price = extract_price(params)
    model = detect_model(title, category)

    if not model or price <= 0:
        return None

    description = offer.get("description") or ""
    location = offer.get("location", {})
    city = location.get("city", {}).get("name")
    location_data = enrich_location(city)
    created_at = offer.get("created_time")
    suspicious = is_suspicious(title, category, price)
    listing_status = detect_listing_status(offer)
    availability_status = initial_availability_status(listing_status)

    return {
        "id": str(offer.get("id")),
        "title": title,
        "price": price,
        "url": offer.get("url") or "",
        "category": category,
        "model": model,
        "condition": detect_condition(title, description, params),
        "city": city,
        "location_normalized": location_data["location_normalized"],
        "latitude": location_data["latitude"],
        "longitude": location_data["longitude"],
        "region": location_data["region"],
        "province": location_data["province"],
        "thumb": detect_thumb(offer),
        "created_at": created_at,
        "created_display": created_display(created_at),
        "scanned_at": scanned_at,
        "last_seen_at": scanned_at,
        "listing_status": listing_status,
        "availability_status": availability_status,
        "availability_checked_at": scanned_at if availability_status == "active" else None,
        "unavailable_at": None,
        "is_new": is_recent(created_at, scanned_at),
        "is_suspicious": suspicious,
        "discount_pct": 0.0,
        "market_median": None,
        "deal_label": "none",
        "deal_score": 0.0,
        "is_opportunity": False,
    }


def score_offers(offers):
    prices_by_model = defaultdict(list)
    for offer in offers:
        if offer["price"] > 0 and not offer["is_suspicious"]:
            prices_by_model[(offer["category"], offer["model"], offer["condition"])].append(offer["price"])

    medians = {}
    for key, prices in prices_by_model.items():
        if len(prices) < 2:
            continue
        sorted_prices = sorted(prices)
        midpoint = len(sorted_prices) // 2
        if len(sorted_prices) % 2:
            median = sorted_prices[midpoint]
        else:
            median = (sorted_prices[midpoint - 1] + sorted_prices[midpoint]) / 2
        medians[key] = round(median, 2)

    for offer in offers:
        median = medians.get((offer["category"], offer["model"], offer["condition"]))
        if median and median > 0:
            discount_pct = round((median - offer["price"]) / median * 100, 1)
            offer["market_median"] = median
            offer["discount_pct"] = discount_pct
        else:
            discount_pct = 0.0
            offer["market_median"] = None
            offer["discount_pct"] = 0.0

        if discount_pct >= 35:
            offer["deal_label"] = "hot_deal"
        elif discount_pct >= 20:
            offer["deal_label"] = "good_deal"
        else:
            offer["deal_label"] = "none"

        offer["is_opportunity"] = (
            offer["deal_label"] in {"hot_deal", "good_deal"}
            and offer["price"] > 0
            and offer["market_median"] is not None
            and offer["discount_pct"] >= 20
            and not offer["is_suspicious"]
            and offer["availability_status"] == "active"
            and bool(offer["url"])
        )
        offer["deal_score"] = max(discount_pct, 0) + (15 if offer["deal_label"] == "hot_deal" else 0) + (5 if offer["is_new"] else 0)

    return offers


def save_listing(cursor, listing):
    cursor.execute("SELECT first_seen_at FROM listings WHERE id = ?", (listing["id"],))
    existing = cursor.fetchone()
    first_seen_at = None
    if existing:
        first_seen_at = existing["first_seen_at"]
    if not first_seen_at:
        first_seen_at = listing["created_at"] or listing["scanned_at"]

    values = (
        listing["id"],
        listing["title"],
        listing["price"],
        listing["url"],
        listing["category"],
        listing["model"],
        listing["condition"],
        listing["city"],
        listing["location_normalized"],
        listing["latitude"],
        listing["longitude"],
        listing["region"],
        listing["province"],
        listing["created_at"],
        listing["scanned_at"],
        first_seen_at,
        listing["last_seen_at"],
        int(listing["is_new"]),
        listing["listing_status"],
        listing["availability_status"],
        listing["availability_checked_at"],
        listing["unavailable_at"],
        listing["thumb"],
        listing["created_display"],
        listing["discount_pct"],
        listing["market_median"],
        listing["deal_label"],
        listing["deal_score"],
        int(listing["is_opportunity"]),
        int(listing["is_suspicious"]),
    )

    cursor.execute(
        """
        INSERT INTO listings (
            id, title, price, url, category, model, condition, city,
            location_normalized, latitude, longitude, region, province,
            created_at, scanned_at, first_seen_at, last_seen_at,
            is_new, listing_status, availability_status, availability_checked_at,
            unavailable_at, thumb,
            created_display, discount_pct, market_median, deal_label,
            deal_score, is_opportunity, is_suspicious
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            price = excluded.price,
            url = excluded.url,
            category = excluded.category,
            model = excluded.model,
            condition = excluded.condition,
            city = excluded.city,
            location_normalized = excluded.location_normalized,
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            region = excluded.region,
            province = excluded.province,
            created_at = excluded.created_at,
            scanned_at = excluded.scanned_at,
            last_seen_at = excluded.last_seen_at,
            is_new = excluded.is_new,
            listing_status = excluded.listing_status,
            availability_status = excluded.availability_status,
            availability_checked_at = excluded.availability_checked_at,
            unavailable_at = excluded.unavailable_at,
            thumb = excluded.thumb,
            created_display = excluded.created_display,
            discount_pct = excluded.discount_pct,
            market_median = excluded.market_median,
            deal_label = excluded.deal_label,
            deal_score = excluded.deal_score,
            is_opportunity = excluded.is_opportunity,
            is_suspicious = excluded.is_suspicious
        """,
        values,
    )


def run_availability_checks(cursor, limit=MAX_AVAILABILITY_CHECKS_PER_CYCLE):
    cursor.execute(
        """
        SELECT id, url
        FROM listings
        WHERE url IS NOT NULL
          AND url != ''
          AND COALESCE(availability_status, 'unknown') != 'unavailable'
        ORDER BY
          CASE
            WHEN COALESCE(is_opportunity, 0) = 1 THEN 0
            WHEN COALESCE(is_new, 0) = 1 THEN 1
            ELSE 2
          END,
          CASE
            WHEN availability_checked_at IS NULL OR availability_checked_at = '' THEN 0
            ELSE 1
          END,
          availability_checked_at ASC,
          last_seen_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cursor.fetchall()

    checked_count = 0
    unavailable_count = 0
    active_count = 0
    unknown_count = 0

    for row in rows:
        status, checked_at, unavailable_at = check_listing_availability(row["url"])
        checked_count += 1
        if status == "unavailable":
            unavailable_count += 1
            cursor.execute(
                """
                UPDATE listings
                SET availability_status = ?,
                    availability_checked_at = ?,
                    unavailable_at = ?,
                    is_opportunity = 0,
                    deal_label = 'none',
                    deal_score = 0
                WHERE id = ?
                """,
                (status, checked_at, unavailable_at, row["id"]),
            )
        elif status == "active":
            active_count += 1
            cursor.execute(
                """
                UPDATE listings
                SET availability_status = ?,
                    availability_checked_at = ?,
                    unavailable_at = NULL
                WHERE id = ?
                """,
                (status, checked_at, row["id"]),
            )
        else:
            unknown_count += 1
            cursor.execute(
                """
                UPDATE listings
                SET availability_status = ?,
                    availability_checked_at = ?,
                    is_opportunity = 0,
                    deal_label = 'none',
                    deal_score = 0
                WHERE id = ?
                """,
                ("unknown", checked_at, row["id"]),
            )

        time.sleep(random.uniform(0.2, 0.6))

    if rows:
        logger.info(
            "Availability maintenance checked %s listings: marked %s unavailable, kept %s active, kept %s unknown.",
            checked_count,
            unavailable_count,
            active_count,
            unknown_count,
        )


def scrape_olx():
    """Scrape OLX, persist listing metadata, and keep old rows intact."""
    scanned_at = utc_now().isoformat()
    parsed_offers = []

    for category, category_config in CATEGORIES.items():
        logger.info("Scraping category: %s", category)
        try:
            for page in range(2):
                data = fetch_page(category_config, offset=page * 50, limit=50)
                for raw_offer in data.get("data", []):
                    parsed = parse_offer(raw_offer, category, scanned_at)
                    if parsed:
                        parsed_offers.append(parsed)
                time.sleep(random.uniform(0.5, 1.5))
        except Exception as exc:
            logger.error("Error scraping %s: %s", category, exc)

    scored_offers = score_offers(parsed_offers)

    conn = get_db_connection()
    cursor = conn.cursor()
    for listing in scored_offers:
        save_listing(cursor, listing)
    run_availability_checks(cursor)
    conn.commit()
    conn.close()

    new_count = sum(1 for listing in scored_offers if listing["is_new"])
    deals_count = sum(1 for listing in scored_offers if listing["is_opportunity"])
    logger.info("Scrape complete. Seen %s listings, %s new, %s deals.", len(scored_offers), new_count, deals_count)
    return scored_offers
