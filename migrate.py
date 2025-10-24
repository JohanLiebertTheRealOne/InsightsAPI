#!/usr/bin/env python3
"""
Database Migration Script for InsightFinance API
================================================

This script creates all database tables for the InsightFinance API.
Run this script after setting up your PostgreSQL database.

Usage:
    python migrate.py

Requirements:
    - PostgreSQL database running
    - DATABASE_URL environment variable set
    - All dependencies installed (pip install -r requirements.txt)
"""

import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.core.database import init_db, engine
from app.core.logging import configure_logging, get_logger
from app.config import settings

# Configure logging
configure_logging(log_level="INFO", log_file="migration.log", enable_file=True)
logger = get_logger(__name__)


async def main():
    """Main migration function."""
    try:
        logger.info("🚀 Starting database migration...")
        logger.info(f"Database URL: {settings.DATABASE_URL[:20]}...")
        
        # Initialize database (creates tables)
        await init_db()
        
        logger.info("✅ Database migration completed successfully!")
        logger.info("🎉 All tables created and ready for use.")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)
    finally:
        # Close database connections
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

