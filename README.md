# 🚀 OLX Flip Scanner Backend

A production-ready, deployable backend service for scanning OLX listings.

## ✨ Features
- **FastAPI**: High-performance API for reading data.
- **Background Scheduler**: Scraper runs independently every 2 minutes.
- **SQLite Storage**: Persistent storage with automatic deduplication.
- **Dockerized**: Ready for deployment on any cloud provider.
- **Clean Architecture**: Modular structure for easy maintenance.

## 📁 Project Structure
```text
/app
  ├── __init__.py
  ├── main.py       # FastAPI app & endpoints
  ├── scraper.py    # Refactored scraping logic
  ├── database.py   # SQLite connection & init
  ├── models.py     # Pydantic models
  └── scheduler.py  # APScheduler background job
Dockerfile          # Container configuration
requirements.txt    # Python dependencies
```

## 🛠 Installation & Running

### 1. Run Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2. Run with Docker
```bash
# Build the image
docker build -t olx-backend .

# Run the container
docker run -d -p 8000:8000 -v $(pwd)/data:/app/data olx-backend
```

## ☁️ Deployment

### Railway / Render
1. Connect your GitHub repository.
2. Set the **Build Command**: `pip install -r requirements.txt`
3. Set the **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
4. Add a **Persistent Disk** (Volume) mounted at `/app/data` to keep your SQLite database across restarts.

## 📡 API Endpoints
- `GET /health`: Check if the service is alive.
- `GET /listings`: Get latest listings (supports `search`, `category`, `limit`, `offset`).
- `GET /listings/stats`: Get statistics about the database.

## 🛡 Performance & Safety
- **Random Delays**: Scraper uses `random.uniform(1, 3)` between page requests.
- **Deduplication**: Listings are checked against the database before insertion.
- **Error Handling**: Try/Except blocks catch network errors without crashing the service.
