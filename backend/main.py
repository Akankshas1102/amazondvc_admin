"""
Main Application Entry Point
=============================
MODIFICATIONS:
- Added admin routes import and registration
- Added routes to serve login.html and admin.html
"""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import logging

from logger import get_logger, redirect_prints_to_logging
from routes import router as api_router
from admin_routes import router as admin_router  # NEW: Import admin routes
from services.scheduler_service import start_scheduler
from database_setup import init_sqlite_db

# --- Configuration ---
APP_HOST = "127.0.0.1"
APP_PORT = 7070
LOG_LEVEL = "debug"

# Initialize logger FIRST
logger = get_logger(__name__)

# Redirect all print statements to logger
redirect_prints_to_logging(logger)

logger.info("="*50)
logger.info("Application Initialization Started")
logger.info("="*50)


# --- Startup / Shutdown Logic ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up...")
    logger.info("Initializing SQLite database...")
    try:
        init_sqlite_db()
        logger.info("✅ SQLite database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize SQLite database: {e}", exc_info=True)
        raise
    
    logger.info("Starting scheduler thread...")
    try:
        start_scheduler()
        logger.info("✅ Scheduler started successfully")
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}", exc_info=True)
        raise
    
    yield
    
    logger.info("Application shutting down...")

# --- FastAPI Setup ---
app = FastAPI(lifespan=lifespan)

logger.info("Setting up CORS middleware...")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5050", "http://127.0.0.1:7070"],  # Added port 7070 for admin access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("✅ CORS middleware configured")

# --- Serve Frontend ---
backend_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(backend_dir)
frontend_dir = os.path.join(root_dir, "frontend")

logger.info(f"Backend directory: {backend_dir}")
logger.info(f"Root directory: {root_dir}")
logger.info(f"Frontend directory: {frontend_dir}")

if not os.path.exists(frontend_dir):
    logger.warning(f"⚠️ Frontend directory not found at: {frontend_dir}")
    logger.warning("Serving API only.")
else:
    logger.info(f"✅ Serving static files from: {frontend_dir}")
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    templates = Jinja2Templates(directory=frontend_dir)

    # Main application page
    @app.get("/", response_class=HTMLResponse)
    async def serve_home(request: Request):
        logger.debug("Serving home page (index.html)")
        return templates.TemplateResponse("index.html", {"request": request})
    
    # NEW: Login page
    @app.get("/login", response_class=HTMLResponse)
    async def serve_login(request: Request):
        logger.debug("Serving login page (login.html)")
        return templates.TemplateResponse("login.html", {"request": request})
    
    # NEW: Admin panel page
    @app.get("/admin", response_class=HTMLResponse)
    async def serve_admin(request: Request):
        logger.debug("Serving admin panel (admin.html)")
        return templates.TemplateResponse("admin.html", {"request": request})


# --- Include API Routes ---
logger.info("Registering API routes...")
app.include_router(api_router, prefix="/api")
logger.info("✅ API routes registered")

# NEW: Include Admin Routes
logger.info("Registering Admin routes...")
app.include_router(admin_router, prefix="/api")
logger.info("✅ Admin routes registered")

# --- Root test endpoint ---
@app.get("/ping")
def ping():
    logger.debug("Ping endpoint called")
    return {"status": "ok", "message": "Backend running on port 7070"}

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"⮕ Incoming request: {request.method} {request.url.path}")
    logger.debug(f"Request headers: {dict(request.headers)}")
    
    response = await call_next(request)
    
    logger.info(f"⮐ Response: {request.method} {request.url.path} - Status: {response.status_code}")
    return response

# --- Run Server ---
if __name__ == "__main__":
    logger.info("="*50)
    logger.info(f"🚀 Starting server on {APP_HOST}:{APP_PORT}")
    logger.info(f"📊 Log level: {LOG_LEVEL}")
    logger.info("="*50)
    logger.info("")
    logger.info("🔗 Application URLs:")
    logger.info(f"   Main App:    http://{APP_HOST}:{APP_PORT}/")
    logger.info(f"   Admin Login: http://{APP_HOST}:{APP_PORT}/login")
    logger.info(f"   Admin Panel: http://{APP_HOST}:{APP_PORT}/admin")
    logger.info("")
    logger.info("="*50)
    
    uvicorn.run(
        "main:app",
        host=APP_HOST,
        port=APP_PORT,
        log_level=LOG_LEVEL.lower(),
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "loggers": {
                "uvicorn": {"handlers": ["default"], "level": "DEBUG"},
                "uvicorn.error": {"level": "DEBUG"},
                "uvicorn.access": {"handlers": ["default"], "level": "DEBUG"},
            },
        },
    )