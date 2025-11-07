# backend/main.py

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from logger import get_logger
from routes import router as api_router
from services.scheduler_service import start_scheduler
from database_setup import init_sqlite_db



# --- Configuration ---
APP_HOST = "127.0.0.1"
APP_PORT = 7070         # ✅ changed to avoid conflict
LOG_LEVEL = "info"

# Ensure you are using get_logger from your logger.py
logger = get_logger(__name__)


# --- Startup / Shutdown Logic ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up...")
    logger.info("Initializing SQLite database...")
    init_sqlite_db()
    logger.info("Starting scheduler thread...")
    start_scheduler()
    yield
    logger.info("Application shutting down...")

# --- FastAPI Setup ---
app = FastAPI(lifespan=lifespan)

# ✅ CORS setup for frontend on port 5050
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5050"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Serve Frontend ---
backend_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(backend_dir)
frontend_dir = os.path.join(root_dir, "frontend")

if not os.path.exists(frontend_dir):
    logger.warning(f"Frontend directory not found at: {frontend_dir}")
    logger.warning("Serving API only.")
else:
    logger.info(f"Serving static files from: {frontend_dir}")
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    templates = Jinja2Templates(directory=frontend_dir)

    @app.get("/", response_class=HTMLResponse)
    async def serve_home(request: Request):
        return templates.TemplateResponse("index.html", {"request": request})
    


# --- Include API Routes ---
app.include_router(api_router, prefix="/api")

# --- Root test endpoint ---
@app.get("/ping")
def ping():
    return {"status": "ok", "message": "Backend running on port 7070"}

# --- Run Server ---
if __name__ == "__main__":
    logger.info(f"Starting server on {APP_HOST}:{APP_PORT} with log level {LOG_LEVEL}")
    uvicorn.run(
        "main:app",
        host=APP_HOST,
        port=APP_PORT,
        log_level=LOG_LEVEL.lower(),
        # Removed reload=True
        # 🚨 FIX: Prevents Uvicorn from overriding custom logging handlers in logger.py
        log_config=None, 
    )