from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from datetime import datetime

from .database import init_db, get_db_connection
from .scheduler import start_scheduler
from .models import ListingResponse, Listing

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    init_db()
    logger.info("Starting background scheduler...")
    start_scheduler()
    yield
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(
    title="OLX Flip Scanner API",
    description="Production-ready OLX scraper with background scheduling",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/listings", response_model=ListingResponse, tags=["Listings"])
def get_listings(
    search: str = Query(None, description="Search keyword in title"),
    category: str = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get listings with optional filtering.
    
    - **search**: Search in title (case-insensitive)
    - **category**: Filter by category (iphone, macbook, playstation, xbox)
    - **limit**: Number of results (max 1000)
    - **offset**: Pagination offset
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Build query
    query = "SELECT * FROM listings WHERE 1=1"
    params = []
    
    if search:
        query += " AND title LIKE ?"
        params.append(f"%{search}%")
    
    if category:
        query += " AND category = ?"
        params.append(category)
    
    # Count total
    count_query = query.replace("SELECT *", "SELECT COUNT(*)")
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]
    
    # Fetch paginated results
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    listings = [
        Listing(
            id=row["id"],
            title=row["title"],
            price=row["price"],
            url=row["url"],
            category=row["category"],
            city=row["city"],
            created_at=datetime.fromisoformat(row["created_at"]),
            scanned_at=datetime.fromisoformat(row["scanned_at"])
        )
        for row in rows
    ]
    
    return ListingResponse(total=total, listings=listings)

@app.get("/listings/stats", tags=["Analytics"])
def get_stats():
    """Get statistics about scraped listings."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Total listings
    cursor.execute("SELECT COUNT(*) FROM listings")
    total = cursor.fetchone()[0]
    
    # By category
    cursor.execute("SELECT category, COUNT(*) as count FROM listings GROUP BY category")
    by_category = {row[0]: row[1] for row in cursor.fetchall()}
    
    # Latest scrape time
    cursor.execute("SELECT MAX(scanned_at) FROM listings")
    latest_scrape = cursor.fetchone()[0]
    
    # Price range
    cursor.execute("SELECT MIN(price), MAX(price), AVG(price) FROM listings WHERE price > 0")
    price_row = cursor.fetchone()
    
    conn.close()
    
    return {
        "total_listings": total,
        "by_category": by_category,
        "latest_scrape": latest_scrape,
        "price_stats": {
            "min": price_row[0],
            "max": price_row[1],
            "average": price_row[2]
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
