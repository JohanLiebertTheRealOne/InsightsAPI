"""
InsightFinance API - Main FastAPI Application
============================================

This is the main entry point for the InsightFinance API, providing comprehensive
financial data and smart insights for traders, coaches, and fintech startups.

Features:
- Real-time financial data from multiple sources (Alpha Vantage, Yahoo Finance, CoinGecko)
- Advanced technical analysis indicators (RSI, EMA, MACD, Bollinger Bands, Stochastic, Williams %R)
- Portfolio analytics and risk metrics (Sharpe ratio, beta, volatility, max drawdown)
- Asset screening and opportunity detection with 8+ strategies
- JWT-based authentication with refresh tokens
- Comprehensive API documentation with Swagger UI and ReDoc
- Rate limiting and security middleware
- Performance monitoring and health checks
- Caching with Redis for optimal performance

Author: InsightFinance Team
Version: 1.0.0
License: MIT
"""

import time
import uuid
from typing import Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
import uvicorn
import logging
from contextlib import asynccontextmanager

# Import our custom modules
from app.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.database import init_db, health_check as db_health_check
from app.core.cache import init_cache, health_check as cache_health_check
from app.routes import auth, prices, signals, portfolio, screener

# Configure centralized logging
configure_logging(log_level=settings.LOG_LEVEL, log_file=settings.LOG_FILE, enable_file=True)
logger = get_logger(__name__)


# Application startup time for uptime calculation
startup_time = datetime.utcnow()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    
    This function handles:
    - Database initialization and health checks
    - Redis cache setup and validation
    - Performance monitoring setup
    - Graceful shutdown and cleanup
    """
    # Startup
    logger.info("🚀 Starting InsightFinance API...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    try:
        # Initialize database connection
        await init_db()
        logger.info("✅ Database connection established")
        
        # Test database health
        db_status = await db_health_check()
        if db_status:
            logger.info("✅ Database health check passed")
        else:
            logger.warning("⚠️ Database health check failed")
        
        # Initialize Redis cache
        await init_cache()
        logger.info("✅ Redis cache initialized")
        
        # Test cache health
        cache_status = await cache_health_check()
        if cache_status:
            logger.info("✅ Cache health check passed")
        else:
            logger.warning("⚠️ Cache health check failed")
        
        # Log configuration summary
        logger.info("📋 Configuration Summary:")
        logger.info(f"   - Database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'configured'}")
        logger.info(f"   - Redis: {settings.REDIS_URL}")
        logger.info(f"   - CORS Origins: {len(settings.CORS_ORIGINS)} configured")
        logger.info(f"   - Log Level: {settings.LOG_LEVEL}")
        
        logger.info("🎉 InsightFinance API is ready!")
        logger.info(f"📚 API Documentation: http://localhost:8000/docs")
        logger.info(f"📖 ReDoc Documentation: http://localhost:8000/redoc")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down InsightFinance API...")
    
    try:
        # Close database connections
        from app.core.database import close_db
        await close_db()
        logger.info("✅ Database connections closed")
        
        # Close Redis connections
        from app.core.cache import close_cache
        await close_cache()
        logger.info("✅ Cache connections closed")
        
        logger.info("✅ Cleanup completed successfully")
    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}")


# Create FastAPI application instance
app = FastAPI(
    title="InsightFinance API",
    description="""
    ## 🚀 Modern Financial Data & Analytics API
    
    A comprehensive financial API that provides:
    
    * **Real-time Market Data** - Stock prices, crypto, forex from multiple sources
    * **Technical Analysis** - RSI, EMA, MACD, Bollinger Bands with BUY/SELL signals
    * **Portfolio Analytics** - Risk metrics, performance tracking, Sharpe ratios
    * **Smart Screening** - Find opportunities based on momentum, growth, dividends
    * **Authentication** - Secure JWT-based user management
    
    ### 🔑 Authentication
    Most endpoints require authentication. Register a user and use the JWT token
    in the Authorization header: `Bearer <your-token>`
    
    ### 📊 Data Sources
    - Alpha Vantage (primary)
    - Yahoo Finance (fallback)
    - CoinGecko (crypto)
    
    ### 🚀 Getting Started
    1. Register a user account
    2. Get your API token
    3. Start making requests!
    """,
    version="1.0.0",
    contact={
        "name": "InsightFinance Support",
        "email": "support@insightfinance.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # In production, specify actual domains
)

# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_CREDENTIALS,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)


# Global exception handler for unhandled errors
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler that catches all unhandled exceptions
    and returns a standardized error response.
    
    This ensures the API always returns proper JSON responses
    even when unexpected errors occur.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
            "status_code": 500
        }
    )


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """
    Health check endpoint to verify API status.
    
    Returns:
        dict: API status and basic information
    """
    return {
        "status": "healthy",
        "message": "InsightFinance API is running",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }


# Root endpoint with API information
@app.get("/", tags=["System"])
async def root():
    """
    Root endpoint providing API information and navigation.
    
    Returns:
        dict: API overview and available endpoints
    """
    return {
        "message": "Welcome to InsightFinance API",
        "description": "Modern financial data and analytics API",
        "version": "1.0.0",
        "documentation": "/docs",
        "redoc": "/redoc",
        "health_check": "/health",
        "endpoints": {
            "authentication": "/auth",
            "market_data": "/prices",
            "technical_analysis": "/signals",
            "portfolio_analytics": "/portfolio",
            "asset_screening": "/screener"
        }
    }


# Include all route modules
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(prices.router, prefix="/prices", tags=["Market Data"])
app.include_router(signals.router, prefix="/signals", tags=["Technical Analysis"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["Portfolio Analytics"])
app.include_router(screener.router, prefix="/screener", tags=["Asset Screening"])


if __name__ == "__main__":
    """
    Run the application directly with uvicorn.
    
    Usage:
        python app/main.py
        or
        uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    """
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
