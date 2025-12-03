"""
Database Setup Script
=====================
Creates all necessary SQLite tables for the application.
NEW: Added tables for admin users and query configurations.
"""

import sqlite3
import os
from logger import get_logger
from auth import hash_password  # NEW: Import for password hashing

logger = get_logger(__name__)

SQLITE_DB_PATH = "building_schedules.db"

def init_sqlite_db():
    """
    Ensures the SQLite database and all tables exist
    without deleting existing data.
    """
    try:
        with sqlite3.connect(SQLITE_DB_PATH) as conn:
            logger.info("Connecting to database... ensuring tables exist.")

            # ============ EXISTING TABLES ============

            # Table for building schedules (removed end_time)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS building_times (
                    building_id INTEGER PRIMARY KEY,
                    start_time TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Table for ignored proevents
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ignored_proevents (
                    proevent_id INTEGER PRIMARY KEY,
                    building_frk INTEGER NOT NULL,
                    device_prk INTEGER NOT NULL,
                    ignore_on_arm BOOLEAN NOT NULL DEFAULT 0,
                    ignore_on_disarm BOOLEAN NOT NULL DEFAULT 0
                )
            """)

            # Table for ProEvent state history
            conn.execute("""
                CREATE TABLE IF NOT EXISTS proevent_state_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proevent_id INTEGER NOT NULL,
                    building_frk INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Table for snapshots
            conn.execute("""
                CREATE TABLE IF NOT EXISTS device_state_snapshot (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    building_id INTEGER NOT NULL,
                    device_id INTEGER NOT NULL,
                    original_state INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(building_id, device_id)
                )
            """)

            # Table for proevents selected by user
            conn.execute("""
                CREATE TABLE IF NOT EXISTS SelectedProEvents_TBL (
                    speBuilding_FRK INT NOT NULL,
                    speProEvent_FRK INT NOT NULL,
                    CONSTRAINT PK_SelectedProEvents PRIMARY KEY (speBuilding_FRK, speProEvent_FRK)
                )
            """)

            # ============ NEW TABLES FOR ADMIN PANEL ============

            # Table for admin users
            conn.execute("""
                CREATE TABLE IF NOT EXISTS admin_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Table for query configurations
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_name TEXT UNIQUE NOT NULL,
                    query_sql TEXT NOT NULL,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()
            logger.info("✅ SQLite database tables verified successfully.")

            # ============ CREATE DEFAULT ADMIN USER ============
            create_default_admin(conn)

    except Exception as e:
        logger.error(f"❌ Error initializing SQLite database: {e}")
        raise


def create_default_admin(conn):
    """
    Creates a default admin user if no admin users exist.
    
    ⚠️ DEFAULT CREDENTIALS:
    Username: admin
    Password: admin123
    
    🔒 SECURITY WARNING: Change these credentials immediately after first login!
    """
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM admin_users")
    count = cursor.fetchone()[0]
    
    if count == 0:
        logger.warning("=" * 60)
        logger.warning("⚠️  NO ADMIN USERS FOUND - CREATING DEFAULT ADMIN")
        logger.warning("=" * 60)
        
        default_username = "admin"
        default_password = "admin123"
        
        password_hash = hash_password(default_password)
        
        cursor.execute("""
            INSERT INTO admin_users (username, password_hash)
            VALUES (?, ?)
        """, (default_username, password_hash))
        
        conn.commit()
        
        logger.warning("✅ Default admin user created:")
        logger.warning(f"   Username: {default_username}")
        logger.warning(f"   Password: {default_password}")
        logger.warning("")
        logger.warning("🔒 SECURITY: Please change this password immediately!")
        logger.warning("   Go to: http://127.0.0.1:7070/login")
        logger.warning("=" * 60)
    else:
        logger.info(f"✅ Found {count} existing admin user(s)")


if __name__ == "__main__":
    init_sqlite_db()
    print("\n✅ Database setup complete (safe mode).")
    print("\n🔐 If default admin was created, please change the password!")