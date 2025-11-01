"""
Asset Metadata Service - Comprehensive Asset Information Lookup
================================================================

This module provides asset metadata lookup and management including:
- Asset name, sector, industry identification
- Exchange and currency information
- Fundamental data (PE ratio, PB ratio, dividend yield, market cap)
- Beta and other risk metrics
- Asset classification and categorization

Features:
- External API integration (Alpha Vantage company overview)
- Caching for performance
- Database storage of asset metadata
- Fallback mechanisms for missing data
"""

import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.core.cache import get_cache
from app.core.logging import get_logger
from app.models.asset import Asset

logger = get_logger(__name__)

# Alpha Vantage endpoints
ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"
ALPHA_VANTAGE_COMPANY_OVERVIEW = "OVERVIEW"
ALPHA_VANTAGE_EARNINGS = "EARNINGS"


async def get_asset_metadata(symbol: str, db: Optional[AsyncSession] = None) -> Dict[str, Any]:
    """
    Get comprehensive asset metadata.
    
    Args:
        symbol: Asset symbol
        db: Optional database session for storing metadata
        
    Returns:
        Dict: Asset metadata including name, sector, industry, fundamentals
    """
    symbol_upper = symbol.upper().strip()
    
    # Check cache first
    cache = get_cache()
    cache_key = f"asset_metadata:{symbol_upper}"
    cached_metadata = await cache.get(cache_key, "assets")
    
    if cached_metadata:
        logger.debug(f"Returning cached metadata for {symbol_upper}")
        return cached_metadata
    
    # Check database if session provided
    metadata = None
    if db:
        result = await db.execute(select(Asset).where(Asset.symbol == symbol_upper))
        asset = result.scalar_one_or_none()
        if asset and asset.name and asset.name != f"{symbol_upper} Corporation":
            metadata = {
                "symbol": asset.symbol,
                "name": asset.name,
                "type": asset.type or "stock",
                "exchange": asset.exchange or "NASDAQ",
                "currency": asset.currency or "USD",
                "sector": getattr(asset, 'sector', None),
                "industry": getattr(asset, 'industry', None)
            }
    
    # If not in database, try external API
    if not metadata:
        metadata = await _fetch_alpha_vantage_metadata(symbol_upper)
        
        # Store in database if session provided
        if db and metadata:
            await _store_asset_metadata(symbol_upper, metadata, db)
    
    # Apply defaults for missing data
    metadata = _apply_defaults(metadata, symbol_upper)
    
    # Cache for 24 hours
    await cache.set(cache_key, metadata, ttl=86400, namespace="assets")
    
    return metadata


async def _fetch_alpha_vantage_metadata(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Fetch asset metadata from Alpha Vantage.
    
    Args:
        symbol: Asset symbol
        
    Returns:
        Optional[Dict]: Asset metadata or None if failed
    """
    if settings.ALPHA_VANTAGE_API_KEY == "demo":
        logger.debug(f"Skipping Alpha Vantage API call for {symbol} (demo key)")
        return None
    
    try:
        params = {
            "function": ALPHA_VANTAGE_COMPANY_OVERVIEW,
            "symbol": symbol,
            "apikey": settings.ALPHA_VANTAGE_API_KEY
        }
        
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(ALPHA_VANTAGE_BASE_URL, params=params)
            
            if response.status_code != 200:
                logger.warning(f"Alpha Vantage API error: {response.status_code}")
                return None
            
            data = response.json()
            
            # Check for API errors
            if "Error Message" in data:
                logger.warning(f"Alpha Vantage error for {symbol}: {data['Error Message']}")
                return None
            
            if "Note" in data:
                logger.warning(f"Alpha Vantage rate limit for {symbol}")
                return None
            
            # Extract metadata
            if not data or "Symbol" not in data:
                return None
            
            metadata = {
                "symbol": data.get("Symbol", symbol),
                "name": data.get("Name", f"{symbol} Corporation"),
                "type": "stock",  # Alpha Vantage primarily covers stocks
                "exchange": data.get("Exchange", "NASDAQ"),
                "currency": data.get("Currency", "USD"),
                "sector": data.get("Sector"),
                "industry": data.get("Industry"),
                "pe_ratio": _parse_float(data.get("PERatio")),
                "pb_ratio": _parse_float(data.get("PriceToBookRatio")),
                "dividend_yield": _parse_float(data.get("DividendYield")),
                "market_cap": _parse_float(data.get("MarketCapitalization")),
                "beta": _parse_float(data.get("Beta")),
                "52_week_high": _parse_float(data.get("52WeekHigh")),
                "52_week_low": _parse_float(data.get("52WeekLow")),
                "eps": _parse_float(data.get("EPS")),
                "revenue": _parse_float(data.get("RevenueTTM")),
                "profit_margin": _parse_float(data.get("ProfitMargin"))
            }
            
            logger.info(f"Fetched metadata from Alpha Vantage for {symbol}")
            return metadata
            
    except Exception as e:
        logger.error(f"Error fetching Alpha Vantage metadata for {symbol}: {e}")
        return None


def _parse_float(value: Optional[str]) -> Optional[float]:
    """Parse float value from string, handling None and empty strings."""
    if value is None or value == "" or value == "None":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _apply_defaults(metadata: Optional[Dict[str, Any]], symbol: str) -> Dict[str, Any]:
    """
    Apply default values for missing metadata.
    
    Args:
        metadata: Existing metadata or None
        symbol: Asset symbol
        
    Returns:
        Dict: Complete metadata with defaults
    """
    if metadata is None:
        metadata = {}
    
    # Use known symbol mappings for common assets
    symbol_defaults = _get_symbol_defaults(symbol)
    
    return {
        "symbol": symbol,
        "name": metadata.get("name") or symbol_defaults.get("name") or f"{symbol} Corporation",
        "type": metadata.get("type") or symbol_defaults.get("type") or "stock",
        "exchange": metadata.get("exchange") or symbol_defaults.get("exchange") or "NASDAQ",
        "currency": metadata.get("currency") or symbol_defaults.get("currency") or "USD",
        "sector": metadata.get("sector") or symbol_defaults.get("sector") or "Other",
        "industry": metadata.get("industry") or symbol_defaults.get("industry") or "General",
        "pe_ratio": metadata.get("pe_ratio"),
        "pb_ratio": metadata.get("pb_ratio"),
        "dividend_yield": metadata.get("dividend_yield"),
        "market_cap": metadata.get("market_cap"),
        "beta": metadata.get("beta") or 1.0,
        "52_week_high": metadata.get("52_week_high"),
        "52_week_low": metadata.get("52_week_low"),
        "eps": metadata.get("eps"),
        "revenue": metadata.get("revenue"),
        "profit_margin": metadata.get("profit_margin")
    }


def _get_symbol_defaults(symbol: str) -> Dict[str, str]:
    """Get default metadata for well-known symbols."""
    defaults = {
        "AAPL": {"name": "Apple Inc.", "sector": "Technology", "industry": "Consumer Electronics", "exchange": "NASDAQ"},
        "GOOGL": {"name": "Alphabet Inc.", "sector": "Technology", "industry": "Internet Services", "exchange": "NASDAQ"},
        "MSFT": {"name": "Microsoft Corporation", "sector": "Technology", "industry": "Software", "exchange": "NASDAQ"},
        "AMZN": {"name": "Amazon.com Inc.", "sector": "Consumer", "industry": "E-commerce", "exchange": "NASDAQ"},
        "TSLA": {"name": "Tesla Inc.", "sector": "Consumer", "industry": "Automotive", "exchange": "NASDAQ"},
        "NVDA": {"name": "NVIDIA Corporation", "sector": "Technology", "industry": "Semiconductors", "exchange": "NASDAQ"},
        "META": {"name": "Meta Platforms Inc.", "sector": "Technology", "industry": "Social Media", "exchange": "NASDAQ"},
        "JPM": {"name": "JPMorgan Chase & Co.", "sector": "Financial", "industry": "Banking", "exchange": "NYSE"},
        "BAC": {"name": "Bank of America Corp.", "sector": "Financial", "industry": "Banking", "exchange": "NYSE"},
        "WFC": {"name": "Wells Fargo & Company", "sector": "Financial", "industry": "Banking", "exchange": "NYSE"},
        "JNJ": {"name": "Johnson & Johnson", "sector": "Healthcare", "industry": "Pharmaceuticals", "exchange": "NYSE"},
        "PFE": {"name": "Pfizer Inc.", "sector": "Healthcare", "industry": "Pharmaceuticals", "exchange": "NYSE"},
        "KO": {"name": "The Coca-Cola Company", "sector": "Consumer", "industry": "Beverages", "exchange": "NYSE"},
        "PEP": {"name": "PepsiCo Inc.", "sector": "Consumer", "industry": "Beverages", "exchange": "NASDAQ"},
        "BTC": {"name": "Bitcoin", "type": "crypto", "sector": "Cryptocurrency", "industry": "Digital Currency", "exchange": "Crypto"},
        "ETH": {"name": "Ethereum", "type": "crypto", "sector": "Cryptocurrency", "industry": "Digital Currency", "exchange": "Crypto"},
        "ADA": {"name": "Cardano", "type": "crypto", "sector": "Cryptocurrency", "industry": "Digital Currency", "exchange": "Crypto"}
    }
    
    return defaults.get(symbol, {})


async def _store_asset_metadata(symbol: str, metadata: Dict[str, Any], db: AsyncSession) -> None:
    """
    Store asset metadata in database.
    
    Args:
        symbol: Asset symbol
        metadata: Metadata dictionary
        db: Database session
    """
    try:
        result = await db.execute(select(Asset).where(Asset.symbol == symbol))
        asset = result.scalar_one_or_none()
        
        if asset:
            # Update existing asset
            asset.name = metadata.get("name", asset.name)
            asset.type = metadata.get("type", asset.type)
            asset.exchange = metadata.get("exchange", asset.exchange)
            asset.currency = metadata.get("currency", asset.currency)
            # Note: sector and industry would need to be added to Asset model if needed
        else:
            # Create new asset
            asset = Asset(
                symbol=symbol,
                name=metadata.get("name"),
                type=metadata.get("type", "stock"),
                exchange=metadata.get("exchange"),
                currency=metadata.get("currency", "USD")
            )
            db.add(asset)
        
        await db.flush()
        logger.debug(f"Stored asset metadata for {symbol} in database")
        
    except Exception as e:
        logger.error(f"Error storing asset metadata for {symbol}: {e}")


async def get_fundamentals(symbol: str) -> Dict[str, Any]:
    """
    Get fundamental data for an asset.
    
    Args:
        symbol: Asset symbol
        
    Returns:
        Dict: Fundamental metrics (PE, PB, dividend yield, etc.)
    """
    metadata = await get_asset_metadata(symbol)
    
    return {
        "pe_ratio": metadata.get("pe_ratio"),
        "pb_ratio": metadata.get("pb_ratio"),
        "dividend_yield": metadata.get("dividend_yield"),
        "market_cap": metadata.get("market_cap"),
        "beta": metadata.get("beta"),
        "eps": metadata.get("eps"),
        "revenue": metadata.get("revenue"),
        "profit_margin": metadata.get("profit_margin")
    }


async def get_sector_for_symbol(symbol: str) -> str:
    """Get sector for a symbol."""
    metadata = await get_asset_metadata(symbol)
    return metadata.get("sector", "Other")


async def get_industry_for_symbol(symbol: str) -> str:
    """Get industry for a symbol."""
    metadata = await get_asset_metadata(symbol)
    return metadata.get("industry", "General")


async def batch_get_metadata(symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Get metadata for multiple symbols efficiently.
    
    Args:
        symbols: List of asset symbols
        
    Returns:
        Dict: Mapping of symbol to metadata
    """
    results = {}
    
    # Process in batches to avoid overwhelming the API
    batch_size = 5
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        
        # Could parallelize this, but keeping it simple for rate limiting
        for symbol in batch:
            metadata = await get_asset_metadata(symbol)
            results[symbol] = metadata
    
    return results
