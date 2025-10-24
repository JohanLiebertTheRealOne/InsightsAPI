"""
Database Configuration and Connection Management
===============================================

This module handles PostgreSQL database connection setup using SQLAlchemy ORM.
It provides database session management, connection pooling, and initialization.

Key Features:
- SQLAlchemy async engine configuration
- Database session dependency injection
- Connection pooling for performance
- Automatic database initialization
- Migration support preparation
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData
import logging
from typing import AsyncGenerator

from app.config import settings

logger = logging.getLogger(__name__)

# Create async engine with connection pooling
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.DEBUG,  # Log SQL queries in debug mode
    pool_size=10,  # Number of connections to maintain in pool
    max_overflow=20,  # Additional connections beyond pool_size
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,  # Recycle connections every hour
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Keep objects accessible after commit
    autoflush=True,  # Automatically flush changes
    autocommit=False,  # Require explicit commits
)


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    
    This class provides the foundation for all database models
    and includes common metadata configuration.
    """
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s"
        }
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function to get database session.
    
    This function provides a database session for FastAPI route handlers.
    It automatically handles session creation, cleanup, and error handling.
    
    Yields:
        AsyncSession: Database session for the request
        
    Example:
        @app.get("/users/")
        async def get_users(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()  # Commit successful operations
        except Exception:
            await session.rollback()  # Rollback on error
            raise
        finally:
            await session.close()  # Always close session


async def init_db():
    """
    Initialize database tables and connections.
    
    This function creates all database tables if they don't exist
    and verifies the database connection is working.
    
    Raises:
        Exception: If database initialization fails
    """
    try:
        logger.info("Initializing database connection...")
        
        # Test database connection
        async with engine.begin() as conn:
            # Execute a simple query to test connection
            from sqlalchemy import text
            await conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection test successful")
        
        # Import all models to ensure they're registered
        from app.models import user, asset, signal, portfolio
        
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created/verified")
            
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise


async def close_db():
    """
    Close database connections and cleanup resources.
    
    This function should be called during application shutdown
    to properly close all database connections.
    """
    try:
        logger.info("Closing database connections...")
        await engine.dispose()
        logger.info("✅ Database connections closed")
    except Exception as e:
        logger.error(f"❌ Error closing database connections: {e}")


# Database utility functions
async def execute_query(query, params=None):
    """
    Execute a raw SQL query with parameters.
    
    Args:
        query: SQL query string
        params: Query parameters
        
    Returns:
        Query result
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(query, params or {})
            await session.commit()
            return result
        except Exception as e:
            await session.rollback()
            logger.error(f"Query execution failed: {e}")
            raise


async def health_check():
    """
    Check database health by executing a simple query.
    
    Returns:
        bool: True if database is healthy, False otherwise
    """
    try:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
