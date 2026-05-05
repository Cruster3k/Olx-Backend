from apscheduler.schedulers.background import BackgroundScheduler
from .scraper import scrape_olx
import logging

logger = logging.getLogger(__name__)

def start_scheduler():
    scheduler = BackgroundScheduler()
    # Run every 2 minutes as requested
    scheduler.add_job(scrape_olx, 'interval', minutes=2, id='olx_scraper_job')
    scheduler.start()
    logger.info("Background scheduler started (interval: 2 minutes)")
    
    # Run once immediately on startup
    logger.info("Running initial scrape...")
    scrape_olx()
