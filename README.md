# OLX Flip Scanner Backend

Deployable FastAPI backend for OLX Flip Scanner Pro.

## What It Does

- Serves the dark OLX Flip Scanner Pro dashboard at `/`.
- Scrapes OLX in the background on a schedule.
- Stores listings in SQLite.
- Separates product categories from dashboard tabs.
- Marks unavailable OLX listings instead of deleting them.
- Supports city/location, radius, and province filtering.
- Keeps Deals strict: only confirmed active listings can appear as hot/good deals.

## Project Structure

```text
app/
  main.py        FastAPI app and API endpoints
  scraper.py     OLX scraping, deal scoring, availability checks
  database.py    SQLite setup and safe schema updates
  locations.py   Local Polish city/province coordinates and normalization
  models.py      API response models
  scheduler.py   Background schedule
  static/
    index.html   Dashboard UI
Dockerfile
requirements.txt
run_local.bat
```

## Run Locally On Windows

Open Windows CMD, then run:

```cmd
cd /d "C:\Users\kamil\OneDrive\Pulpit\OLX Scraper\scrape 2.0\olx-backend-production\olx-backend"
run_local.bat
```

The script will:

- create `.venv` if missing
- install `requirements.txt`
- start the server on `127.0.0.1:8000`

To stop the server, click the CMD window and press:

```cmd
Ctrl+C
```

Then answer `Y` if CMD asks whether to terminate the batch job.

## Test URLs

Open these in your browser:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/health
http://127.0.0.1:8000/listings/stats
http://127.0.0.1:8000/listings?tab=deals&city=Warszawa&limit=5
http://127.0.0.1:8000/listings?tab=deals&city=Katowice&radius_km=50&limit=20
http://127.0.0.1:8000/listings?tab=deals&province=slaskie&limit=20
```

You can also test from CMD:

```cmd
powershell -Command "Invoke-RestMethod http://127.0.0.1:8000/health"
powershell -Command "Invoke-RestMethod http://127.0.0.1:8000/listings/stats"
powershell -Command "Invoke-RestMethod 'http://127.0.0.1:8000/listings?tab=deals&limit=5'"
powershell -Command "Invoke-RestMethod 'http://127.0.0.1:8000/listings?tab=deals&city=Warszawa&limit=5'"
powershell -Command "Invoke-RestMethod 'http://127.0.0.1:8000/listings?tab=deals&city=Katowice&radius_km=50&limit=20'"
powershell -Command "Invoke-RestMethod 'http://127.0.0.1:8000/listings?tab=deals&province=slaskie&limit=20'"
```

## Useful API Examples

```text
GET /listings?tab=all
GET /listings?tab=deals
GET /listings?tab=new
GET /listings?tab=pending
GET /listings?tab=deals&category=iphone
GET /listings?tab=deals&city=Warszawa
GET /listings?tab=deals&city=Katowice&radius_km=50
GET /listings?tab=deals&province=slaskie
GET /listings?tab=new&city=Wroclaw
GET /listings?tab=all&availability=all
GET /listings?availability=unavailable
GET /listings?availability=unknown
```

Availability filters:

- No availability parameter hides unavailable listings. This is the default.
- `availability=active` shows only confirmed active listings.
- `availability=unknown` shows only listings that are not verified yet.
- `availability=unavailable` shows only unavailable listings.
- `availability=all` includes unavailable listings.

## Railway Deployment

Recommended Railway settings:

```text
Build command: pip install -r requirements.txt
Start command: uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Use a persistent volume mounted at `/app/data` and set:

```text
DB_PATH=/app/data/olx_listings.db
```

## Safety Notes

- Unavailable listings are marked, not deleted.
- Availability checks happen in the background scraper flow, not during normal dashboard loading.
- The scraper checks only a small number of listing pages per cycle to avoid hammering OLX.
- If OLX times out or blocks an availability check, the listing is marked `unknown`, not deleted.
