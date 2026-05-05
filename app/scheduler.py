from apscheduler.schedulers.background import BackgroundScheduler
from .scraper import scrape_olx
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

def start_scheduler():
    scheduler = BackgroundScheduler()
    # Run every 2 minutes as requested
    scheduler.add_job(scrape_olx, 'interval', minutes=2, id='olx_scraper_job')
    scheduler.add_job(
        scrape_olx,
        'date',
        run_date=datetime.now(timezone.utc),
        id='olx_initial_scrape_job',
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Background scheduler started (interval: 2 minutes)")
    logger.info("Initial scrape queued in the background.")
