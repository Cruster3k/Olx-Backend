import requests
import time
import random
import logging
from datetime import datetime
from .database import get_db_connection

logger = logging.getLogger(__name__)

# Category IDs from previous research
CATEGORIES = {
    "iphone": 2298,
    "macbook": 2302,
    "playstation": 2306,
    "xbox": 2308
}

def is_excluded(title, category):
    title = title.lower()
    # Aggressive exclusion for consoles (games, accounts, etc.)
    if category in ["playstation", "xbox"]:
        excluded_keywords = ["gra", "gry", "pad", "kontroler", "sluchawki", "kabel", "ladowarka", "pudelko", "etui", "digital", "konto", "account", "zamiana", "kupie", "szukam"]
        if any(k in title for k in excluded_keywords):
            return True
    return False

def scrape_olx():
    """
    Refactored scraping logic with database persistence and deduplication.
    """
    all_new_listings = []
    conn = get_db_connection()
    cursor = conn.cursor()

    for cat_name, cat_id in CATEGORIES.items():
        logger.info(f"Scraping category: {cat_name}")
        try:
            # Fetch first 2 pages for each category to keep it light
            for page in range(2):
                offset = page * 40
                url = f"https://www.olx.pl/api/v1/offers/?offset={offset}&limit=40&category_id={cat_id}"
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
                
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code != 200:
                    logger.error(f"Failed to fetch {cat_name} page {page}: {response.status_code}")
                    break
                
                data = response.json()
                offers = data.get("data", [])
                
                for offer in offers:
                    listing_id = str(offer.get("id"))
                    title = offer.get("title")
                    
                    # Skip excluded items
                    if is_excluded(title, cat_name):
                        continue
                        
                    # Extract price
                    price = 0
                    for param in offer.get("params", []):
                        if param.get("key") == "price":
                            price = param.get("value", {}).get("value", 0)
                            break
                    
                    # Deduplication check
                    cursor.execute("SELECT id FROM listings WHERE id = ?", (listing_id,))
                    if cursor.fetchone():
                        continue
                    
                    # Prepare data
                    listing_data = {
                        "id": listing_id,
                        "title": title,
                        "price": float(price),
                        "url": offer.get("url"),
                        "category": cat_name,
                        "city": offer.get("location", {}).get("city", {}).get("name"),
                        "created_at": offer.get("created_time")
                    }
                    
                    # Insert into DB
                    cursor.execute('''
                        INSERT INTO listings (id, title, price, url, category, city, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        listing_data["id"],
                        listing_data["title"],
                        listing_data["price"],
                        listing_data["url"],
                        listing_data["category"],
                        listing_data["city"],
                        listing_data["created_at"]
                    ))
                    
                    all_new_listings.append(listing_data)
                
                # Random delay between pages
                time.sleep(random.uniform(1, 3))
                
        except Exception as e:
            logger.error(f"Error scraping {cat_name}: {e}")

    conn.commit()
    conn.close()
    logger.info(f"Scrape complete. Found {len(all_new_listings)} new listings.")
    return all_new_listings
