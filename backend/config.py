import os
import logging
import urllib.parse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from contextlib import contextmanager

# Load environment variables
load_dotenv()

# -----------------------------
# Logging Configuration
# -----------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("config")

# -----------------------------
# Application Configuration
# -----------------------------
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", 7070))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# -----------------------------
# Database Configuration (Now pulling SA credentials from .env)
# -----------------------------
# ⚠️ NOTE: ODBC Driver must be wrapped in curly braces {}
DB_DRIVER = "{" + os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server") + "}"
DB_SERVER = os.getenv("DB_SERVER", "10.192.0.173") 
DB_NAME = os.getenv("DB_DATABASE", "vtasdata_amazon") 
DB_USER = os.getenv("DB_USERNAME", "sa")               
DB_PASSWORD = os.getenv("DB_PASSWORD", "m00se_1234")
DB_TRUST_CERT = os.getenv("DB_TRUST_CERT", "yes")

# -----------------------------
# ProServer Configuration
# -----------------------------
PROSERVER_IP = os.getenv("PROSERVER_IP", "10.192.0.173")
PROSERVER_PORT = int(os.getenv("PROSERVER_PORT", "7777"))

# -----------------------------
# Connection String Builder
# -----------------------------
def create_connection_string():
    """Builds a fully compatible SQL Server ODBC connection string for SQLAlchemy."""
    # Convert DB_TRUST_CERT env var to a value the ODBC driver expects
    trust_cert_value = 'yes' if DB_TRUST_CERT.lower() in ('true', 'yes', '1') else 'no'

    odbc_str = (
        f"DRIVER={DB_DRIVER};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_NAME};"
        f"UID={DB_USER};"
        f"PWD={DB_PASSWORD};"
        # Explicitly set Encrypt and TrustServerCertificate for connection stability
        f"Encrypt=yes;" 
        f"TrustServerCertificate={trust_cert_value};"
        f"Connection Timeout=30;"
    )

    params = urllib.parse.quote_plus(odbc_str)
    return f"mssql+pyodbc:///?odbc_connect={params}"

CONNECTION_STRING = create_connection_string()
logger.debug("✅ Connection string created successfully")

# -----------------------------
# SQLAlchemy Engine Setup
# -----------------------------
try:
    engine = create_engine(
        CONNECTION_STRING,
        echo=False, 
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600,
    )
    logger.info("✅ SQLAlchemy engine created successfully")
except Exception as e:
    logger.error(f"❌ Error creating engine: {e}")
    raise

# -----------------------------
# Session Factory
# -----------------------------
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

# -----------------------------
# Health Check Function
# -----------------------------
def health_check():
    """Verifies database connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Database connection successful for health check")
        return True
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return False

# -----------------------------
# Context Manager for DB Sessions
# -----------------------------
@contextmanager
def get_db_connection():
    """Provides a transactional scope around DB operations."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------
# Helper Query Functions
# -----------------------------
def fetch_one(query: str, params: dict = None):
    """Fetch a single row."""
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        row = result.fetchone()
        return dict(row._mapping) if row else None

def fetch_all(query: str, params: dict = None):
    """Fetch all rows."""
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]

def execute_query(query: str, params: dict = None):
    """Execute insert/update/delete query and return affected row count."""
    with engine.begin() as conn: 
        result = conn.execute(text(query), params or {})
        return result.rowcount