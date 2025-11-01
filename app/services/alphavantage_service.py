"""
External Market Data Services with Fallback Mechanisms
======================================================

This module provides comprehensive market data integration with multiple sources:
- Alpha Vantage (primary) - Professional financial data API
- Yahoo Finance (fallback) - Free financial data via web scraping
- CoinGecko (crypto) - Cryptocurrency market data

Features:
- Automatic fallback between data sources
- Intelligent caching with TTL management
- Rate limiting and error handling
- Support for stocks, crypto, and forex
- Historical data retrieval
- Real-time price updates
"""

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union
import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.core.cache import get_cached_price_data, cache_price_data, get_cache
from app.core.logging import get_logger

logger = get_logger(__name__)

# API Configuration
ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"
YAHOO_FINANCE_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

# Rate limiting
RATE_LIMIT_DELAY = 1.0  # seconds between requests
_last_request_time = 0


class MarketDataError(Exception):
    """Custom exception for market data errors."""
    pass


class RateLimitError(MarketDataError):
    """Exception raised when rate limit is exceeded."""
    pass


async def _rate_limit():
    """Implement rate limiting between requests."""
    global _last_request_time
    current_time = asyncio.get_event_loop().time()
    time_since_last = current_time - _last_request_time
    
    if time_since_last < RATE_LIMIT_DELAY:
        await asyncio.sleep(RATE_LIMIT_DELAY - time_since_last)
    
    _last_request_time = asyncio.get_event_loop().time()


def _detect_asset_type(symbol: str) -> str:
    """
    Detect asset type based on symbol patterns.
    
    Args:
        symbol: Asset symbol
        
    Returns:
        str: Asset type ('stock', 'crypto', 'forex')
    """
    symbol_upper = symbol.upper()
    
    # Crypto patterns
    crypto_patterns = ['BTC', 'ETH', 'ADA', 'DOT', 'LINK', 'UNI', 'AAVE', 'SOL', 'MATIC', 'AVAX']
    if any(pattern in symbol_upper for pattern in crypto_patterns):
        return 'crypto'
    
    # Forex patterns (currency pairs)
    forex_patterns = ['USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'NZD']
    if len(symbol_upper) == 6 and any(pattern in symbol_upper for pattern in forex_patterns):
        return 'forex'
    
    # Default to stock
    return 'stock'


async def _fetch_alpha_vantage_price(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Fetch current price from Alpha Vantage API.
    
    Args:
        symbol: Asset symbol
        
    Returns:
        Optional[Dict]: Price data or None if failed
    """
    try:
        await _rate_limit()
        
        params = {
            "function": "GLOBAL_QUOTE",
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
                logger.warning(f"Alpha Vantage error: {data['Error Message']}")
                return None
            
            if "Note" in data:
                logger.warning(f"Alpha Vantage rate limit: {data['Note']}")
                return None
            
            global_quote = data.get("Global Quote", {})
            if not global_quote or "05. price" not in global_quote:
                logger.warning(f"No price data for symbol: {symbol}")
                return None
            
            # Extract price data
            price = float(global_quote["05. price"])
            change = float(global_quote.get("09. change", 0))
            change_percent = float(global_quote.get("10. change percent", "0%").rstrip("%"))
            
            return {
                "symbol": symbol.upper(),
                "current_price": price,
                "change": change,
                "change_percent": change_percent,
                "volume": int(global_quote.get("06. volume", 0)),
                "high": float(global_quote.get("03. high", price)),
                "low": float(global_quote.get("04. low", price)),
                "open": float(global_quote.get("02. open", price)),
                "previous_close": float(global_quote.get("08. previous close", price)),
                "source": "alpha_vantage",
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Alpha Vantage fetch error for {symbol}: {e}")
        return None


async def _fetch_alpha_vantage_history(symbol: str, period: str = "1mo") -> Optional[List[Dict[str, Any]]]:
    """
    Fetch historical data from Alpha Vantage.
    
    Args:
        symbol: Asset symbol
        period: Time period (1d, 1wk, 1mo, 3mo, 6mo, 1y)
        
    Returns:
        Optional[List]: Historical data or None if failed
    """
    try:
        await _rate_limit()
        
        # Map period to Alpha Vantage function
        function_map = {
            "1d": "TIME_SERIES_INTRADAY",
            "1wk": "TIME_SERIES_WEEKLY",
            "1mo": "TIME_SERIES_MONTHLY",
            "3mo": "TIME_SERIES_MONTHLY",
            "6mo": "TIME_SERIES_MONTHLY",
            "1y": "TIME_SERIES_MONTHLY"
        }
        
        function = function_map.get(period, "TIME_SERIES_MONTHLY")
        params = {
            "function": function,
            "symbol": symbol,
            "apikey": settings.ALPHA_VANTAGE_API_KEY
        }
        
        if function == "TIME_SERIES_INTRADAY":
            params["interval"] = "5min"
        
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(ALPHA_VANTAGE_BASE_URL, params=params)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            if "Error Message" in data or "Note" in data:
                return None
            
            # Extract time series data
            time_series_key = None
            for key in data.keys():
                if "Time Series" in key:
                    time_series_key = key
                    break
            
            if not time_series_key:
                return None
            
            time_series = data[time_series_key]
            history = []
            
            for date_str, values in time_series.items():
                history.append({
                    "date": date_str,
                    "open": float(values["1. open"]),
                    "high": float(values["2. high"]),
                    "low": float(values["3. low"]),
                    "close": float(values["4. close"]),
                    "volume": int(values["5. volume"])
                })
            
            # Sort by date and limit results
            history.sort(key=lambda x: x["date"])
            return history[-30:]  # Last 30 data points
            
    except Exception as e:
        logger.error(f"Alpha Vantage history fetch error for {symbol}: {e}")
        return None


async def _fetch_yahoo_finance_price(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Fetch current price from Yahoo Finance API.
    
    Args:
        symbol: Asset symbol
        
    Returns:
        Optional[Dict]: Price data or None if failed
    """
    try:
        await _rate_limit()
        
        url = f"{YAHOO_FINANCE_BASE_URL}/{symbol}"
        params = {
            "range": "1d",
            "interval": "1m",
            "includePrePost": "true"
        }
        
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            if "chart" not in data or not data["chart"]["result"]:
                return None
            
            result = data["chart"]["result"][0]
            meta = result["meta"]
            
            if not meta.get("regularMarketPrice"):
                return None
            
            price = meta["regularMarketPrice"]
            previous_close = meta.get("previousClose", price)
            change = price - previous_close
            change_percent = (change / previous_close) * 100 if previous_close else 0
            
            return {
                "symbol": symbol.upper(),
                "current_price": price,
                "change": change,
                "change_percent": change_percent,
                "volume": meta.get("regularMarketVolume", 0),
                "high": meta.get("regularMarketDayHigh", price),
                "low": meta.get("regularMarketDayLow", price),
                "open": meta.get("regularMarketOpen", price),
                "previous_close": previous_close,
                "source": "yahoo_finance",
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Yahoo Finance fetch error for {symbol}: {e}")
        return None


async def _fetch_coingecko_price(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Fetch cryptocurrency price from CoinGecko API.
    
    Args:
        symbol: Cryptocurrency symbol
        
    Returns:
        Optional[Dict]: Price data or None if failed
    """
    try:
        await _rate_limit()
        
        # Map common crypto symbols to CoinGecko IDs
        crypto_id_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "ADA": "cardano",
            "DOT": "polkadot",
            "LINK": "chainlink",
            "UNI": "uniswap",
            "AAVE": "aave",
            "SOL": "solana",
            "MATIC": "matic-network",
            "AVAX": "avalanche-2"
        }
        
        crypto_id = crypto_id_map.get(symbol.upper())
        if not crypto_id:
            return None
        
        url = f"{COINGECKO_BASE_URL}/simple/price"
        params = {
            "ids": crypto_id,
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_24hr_vol": "true",
            "include_last_updated_at": "true"
        }
        
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            if crypto_id not in data:
                return None
            
            crypto_data = data[crypto_id]
            price = crypto_data["usd"]
            change_percent = crypto_data.get("usd_24h_change", 0)
            change = price * (change_percent / 100)
            
            return {
                "symbol": symbol.upper(),
                "current_price": price,
                "change": change,
                "change_percent": change_percent,
                "volume": crypto_data.get("usd_24h_vol", 0),
                "high": price * 1.05,  # Approximate high
                "low": price * 0.95,   # Approximate low
                "open": price - change,  # Approximate open
                "previous_close": price - change,
                "source": "coingecko",
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"CoinGecko fetch error for {symbol}: {e}")
        return None


async def get_price_with_history(symbol: str, period: str = "1mo") -> Optional[Dict[str, Any]]:
    """
    Get current price and historical data with intelligent fallback.
    
    Args:
        symbol: Asset symbol
        period: Historical period (1d, 1wk, 1mo, 3mo, 6mo, 1y)
        
    Returns:
        Optional[Dict]: Complete price data with history
    """
    symbol_upper = symbol.upper()
    cache_key = f"{symbol_upper}_{period}"
    
    # Check cache first
    cached_data = await get_cached_price_data(cache_key)
    if cached_data:
        logger.debug(f"Returning cached data for {symbol_upper}")
        return cached_data
    
    logger.info(f"Fetching fresh data for {symbol_upper}")
    
    # Determine asset type
    asset_type = _detect_asset_type(symbol_upper)
    
    # Try different data sources based on asset type
    price_data = None
    history_data = None
    
    if asset_type == "crypto" and settings.COINGECKO_ENABLED:
        # Try CoinGecko first for crypto
        price_data = await _fetch_coingecko_price(symbol_upper)
        if price_data:
            logger.info(f"Got crypto data from CoinGecko for {symbol_upper}")
    
    if not price_data and settings.ALPHA_VANTAGE_API_KEY != "demo":
        # Try Alpha Vantage
        price_data = await _fetch_alpha_vantage_price(symbol_upper)
        if price_data:
            logger.info(f"Got data from Alpha Vantage for {symbol_upper}")
            history_data = await _fetch_alpha_vantage_history(symbol_upper, period)
    
    if not price_data and settings.YAHOO_FINANCE_ENABLED:
        # Try Yahoo Finance as fallback
        price_data = await _fetch_yahoo_finance_price(symbol_upper)
        if price_data:
            logger.info(f"Got data from Yahoo Finance for {symbol_upper}")
    
    if not price_data:
        logger.warning(f"No price data available for {symbol_upper}")
        return None
    
    # Combine price and history data
    result = {
        **price_data,
        "history": history_data or [],
        "asset_type": asset_type,
        "period": period
    }
    
    # Cache the result
    await cache_price_data(cache_key, result, ttl=300)  # 5 minutes
    
    return result


async def get_multiple_prices(symbols: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Get prices for multiple symbols concurrently.
    
    Args:
        symbols: List of asset symbols
        
    Returns:
        Dict: Symbol to price data mapping
    """
    tasks = [get_price_with_history(symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return {
        symbol: result if not isinstance(result, Exception) else None
        for symbol, result in zip(symbols, results)
    }


async def search_symbols(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search for symbols matching a query.
    
    Args:
        query: Search query
        limit: Maximum number of results
        
    Returns:
        List: Matching symbols with metadata
    """
    # This is a simplified implementation
    # In production, you'd integrate with symbol search APIs
    
    common_symbols = [
        {"symbol": "AAPL", "name": "Apple Inc.", "type": "stock"},
        {"symbol": "GOOGL", "name": "Alphabet Inc.", "type": "stock"},
        {"symbol": "MSFT", "name": "Microsoft Corporation", "type": "stock"},
        {"symbol": "TSLA", "name": "Tesla Inc.", "type": "stock"},
        {"symbol": "AMZN", "name": "Amazon.com Inc.", "type": "stock"},
        {"symbol": "BTC", "name": "Bitcoin", "type": "crypto"},
        {"symbol": "ETH", "name": "Ethereum", "type": "crypto"},
        {"symbol": "ADA", "name": "Cardano", "type": "crypto"},
    ]
    
    query_upper = query.upper()
    matches = [
        symbol for symbol in common_symbols
        if query_upper in symbol["symbol"] or query_upper in symbol["name"].upper()
    ]
    
    return matches[:limit]


async def get_market_summary() -> Dict[str, Any]:
    """
    Get overall market summary and indices with top gainers/losers/most active.
    
    Returns:
        Dict: Market summary data including top movers
    """
    try:
        # Get major indices
        indices = ["SPY", "QQQ", "IWM", "DIA"]  # S&P 500, NASDAQ, Russell 2000, Dow Jones
        
        index_data = await get_multiple_prices(indices)
        
        # Get a broad universe of stocks for market breadth
        market_universe = [
            "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "NFLX",
            "JPM", "BAC", "WFC", "GS", "MS", "C", "AXP", "V", "MA",
            "JNJ", "PFE", "UNH", "ABBV", "MRK", "TMO", "ABT", "DHR",
            "KO", "PEP", "WMT", "PG", "HD", "DIS", "NKE", "BA", "CAT"
        ]
        
        # Get prices for market universe
        universe_prices = await get_multiple_prices(market_universe)
        
        # Calculate top gainers, losers, and most active
        top_gainers = []
        top_losers = []
        most_active = []
        
        for symbol, data in universe_prices.items():
            if not data:
                continue
            
            change_percent = data.get("change_percent", 0.0)
            volume = data.get("volume", 0)
            
            # Top gainers
            if change_percent > 0:
                top_gainers.append({
                    "symbol": symbol,
                    "price": data["current_price"],
                    "change": data.get("change", 0.0),
                    "change_percent": change_percent,
                    "volume": volume
                })
            
            # Top losers
            if change_percent < 0:
                top_losers.append({
                    "symbol": symbol,
                    "price": data["current_price"],
                    "change": data.get("change", 0.0),
                    "change_percent": change_percent,
                    "volume": volume
                })
            
            # Most active (by volume)
            most_active.append({
                "symbol": symbol,
                "price": data["current_price"],
                "volume": volume,
                "change_percent": change_percent
            })
        
        # Sort and limit results
        top_gainers.sort(key=lambda x: x["change_percent"], reverse=True)
        top_losers.sort(key=lambda x: x["change_percent"])
        most_active.sort(key=lambda x: x["volume"], reverse=True)
        
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "indices": {},
            "market_status": "open",  # Simplified - would need real market hours logic
            "top_gainers": top_gainers[:10],  # Top 10
            "top_losers": top_losers[:10],    # Bottom 10
            "most_active": most_active[:10]   # Top 10 by volume
        }
        
        for symbol, data in index_data.items():
            if data:
                summary["indices"][symbol] = {
                    "price": data["current_price"],
                    "change": data["change"],
                    "change_percent": data["change_percent"]
                }
        
        return summary
        
    except Exception as e:
        logger.error(f"Market summary error: {e}")
        return {"error": "Failed to fetch market summary"}


