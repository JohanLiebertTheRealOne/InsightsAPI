"""
Market Data Routes - Comprehensive Price and Historical Data API
==============================================================

This module provides comprehensive market data endpoints including:
- Current price data with detailed information
- Historical price data with multiple timeframes
- Multiple symbol batch requests
- Market summary and overview
- Symbol search and validation
- Real-time market status

Features:
- Support for stocks, crypto, and forex
- Multiple data sources with fallback
- Intelligent caching for performance
- Comprehensive error handling
- Rate limiting and validation
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.services.alphavantage_service import (
    get_price_with_history,
    get_multiple_prices,
    search_symbols,
    get_market_summary
)

logger = get_logger(__name__)
router = APIRouter()


class PriceData(BaseModel):
    """Individual price data model."""
    symbol: str
    current_price: float
    change: float
    change_percent: float
    volume: int
    high: float
    low: float
    open: float
    previous_close: float
    source: str
    timestamp: str


class HistoricalData(BaseModel):
    """Historical data point model."""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class PriceResponse(BaseModel):
    """Complete price response model."""
    symbol: str
    current_price: float
    change: float
    change_percent: float
    volume: int
    high: float
    low: float
    open: float
    previous_close: float
    source: str
    timestamp: str
    asset_type: str
    period: str
    history: List[HistoricalData] = []
    market_status: str = "unknown"


class MultiplePricesRequest(BaseModel):
    """Request model for multiple symbol prices."""
    symbols: List[str] = Field(..., min_items=1, max_items=20, description="List of symbols to fetch")
    
    @validator('symbols')
    def validate_symbols(cls, v):
        """Validate symbol format."""
        for symbol in v:
            if not symbol or len(symbol.strip()) == 0:
                raise ValueError("Symbol cannot be empty")
            if len(symbol) > 10:
                raise ValueError("Symbol too long")
        return [s.upper().strip() for s in v]


class MultiplePricesResponse(BaseModel):
    """Response model for multiple symbol prices."""
    timestamp: str
    total_symbols: int
    successful_requests: int
    failed_requests: int
    prices: Dict[str, Optional[PriceData]]
    errors: Dict[str, str] = {}


class SymbolSearchRequest(BaseModel):
    """Request model for symbol search."""
    query: str = Field(..., min_length=1, max_length=50, description="Search query")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of results")


class SymbolSearchResponse(BaseModel):
    """Response model for symbol search."""
    query: str
    total_results: int
    symbols: List[Dict[str, Any]]


class MarketSummaryResponse(BaseModel):
    """Response model for market summary."""
    timestamp: str
    market_status: str
    indices: Dict[str, Dict[str, float]]
    top_gainers: List[Dict[str, Any]] = []
    top_losers: List[Dict[str, Any]] = []
    most_active: List[Dict[str, Any]] = []


@router.get("/{symbol}", response_model=PriceResponse, summary="Get Current Price Data")
async def get_price(
    symbol: str = Path(..., description="Asset symbol (e.g., AAPL, BTC, EURUSD)"),
    period: str = Query("1mo", description="Historical period (1d, 1wk, 1mo, 3mo, 6mo, 1y)"),
    user=Depends(get_current_user)
) -> PriceResponse:
    """
    Get current price data and historical information for a single symbol.
    
    This endpoint provides comprehensive price data including:
    - Current price, change, and percentage change
    - Volume, high, low, open, and previous close
    - Historical data for the specified period
    - Asset type detection and market status
    
    Args:
        symbol: Asset symbol (stocks, crypto, forex)
        period: Historical period for analysis
        user: Authenticated user
        
    Returns:
        PriceResponse: Complete price data with history
        
    Raises:
        HTTPException: If symbol not found or data unavailable
    """
    try:
        logger.info(f"Fetching price data for {symbol} (period: {period})")
        
        # Validate symbol format
        symbol_upper = symbol.upper().strip()
        if not symbol_upper or len(symbol_upper) > 10:
            raise HTTPException(
                status_code=400,
                detail="Invalid symbol format. Symbol must be 1-10 characters."
            )
        
        # Get price data
        data = await get_price_with_history(symbol_upper, period)
        if data is None:
            raise HTTPException(
                status_code=404,
                detail=f"Symbol '{symbol}' not found or data unavailable"
            )
        
        # Convert history data
        history = []
        for h in data.get("history", []):
            history.append(HistoricalData(
                date=h.get("date", ""),
                open=h.get("open", 0.0),
                high=h.get("high", 0.0),
                low=h.get("low", 0.0),
                close=h.get("close", 0.0),
                volume=h.get("volume", 0)
            ))
        
        # Determine market status (simplified)
        market_status = "open"  # In production, check actual market hours
        
        response = PriceResponse(
            symbol=data["symbol"],
            current_price=data["current_price"],
            change=data.get("change", 0.0),
            change_percent=data.get("change_percent", 0.0),
            volume=data.get("volume", 0),
            high=data.get("high", data["current_price"]),
            low=data.get("low", data["current_price"]),
            open=data.get("open", data["current_price"]),
            previous_close=data.get("previous_close", data["current_price"]),
            source=data.get("source", "unknown"),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            asset_type=data.get("asset_type", "unknown"),
            period=period,
            history=history,
            market_status=market_status
        )
        
        logger.info(f"Successfully fetched price data for {symbol}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching price data for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching price data"
        )


@router.post("/batch", response_model=MultiplePricesResponse, summary="Get Multiple Symbol Prices")
async def get_multiple_prices_endpoint(
    request: MultiplePricesRequest,
    user=Depends(get_current_user)
) -> MultiplePricesResponse:
    """
    Get current price data for multiple symbols in a single request.
    
    This endpoint efficiently fetches price data for up to 20 symbols
    concurrently, providing better performance than individual requests.
    
    Args:
        request: List of symbols to fetch
        user: Authenticated user
        
    Returns:
        MultiplePricesResponse: Price data for all requested symbols
        
    Raises:
        HTTPException: If request validation fails
    """
    try:
        logger.info(f"Fetching prices for {len(request.symbols)} symbols")
        
        # Get prices for all symbols concurrently
        results = await get_multiple_prices(request.symbols)
        
        # Process results
        prices = {}
        errors = {}
        successful = 0
        
        for symbol in request.symbols:
            if symbol in results and results[symbol] is not None:
                data = results[symbol]
                prices[symbol] = PriceData(
                    symbol=data["symbol"],
                    current_price=data["current_price"],
                    change=data.get("change", 0.0),
                    change_percent=data.get("change_percent", 0.0),
                    volume=data.get("volume", 0),
                    high=data.get("high", data["current_price"]),
                    low=data.get("low", data["current_price"]),
                    open=data.get("open", data["current_price"]),
                    previous_close=data.get("previous_close", data["current_price"]),
                    source=data.get("source", "unknown"),
                    timestamp=data.get("timestamp", datetime.utcnow().isoformat())
                )
                successful += 1
            else:
                prices[symbol] = None
                errors[symbol] = "Data unavailable"
        
        response = MultiplePricesResponse(
            timestamp=datetime.utcnow().isoformat(),
            total_symbols=len(request.symbols),
            successful_requests=successful,
            failed_requests=len(request.symbols) - successful,
            prices=prices,
            errors=errors
        )
        
        logger.info(f"Successfully fetched prices for {successful}/{len(request.symbols)} symbols")
        return response
        
    except Exception as e:
        logger.error(f"Error fetching multiple prices: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching multiple prices"
        )


@router.post("/search", response_model=SymbolSearchResponse, summary="Search Symbols")
async def search_symbols_endpoint(
    request: SymbolSearchRequest,
    user=Depends(get_current_user)
) -> SymbolSearchResponse:
    """
    Search for symbols matching a query string.
    
    This endpoint helps users find symbols by name or symbol code,
    supporting both exact matches and partial matches.
    
    Args:
        request: Search query and parameters
        user: Authenticated user
        
    Returns:
        SymbolSearchResponse: Matching symbols with metadata
        
    Raises:
        HTTPException: If search fails
    """
    try:
        logger.info(f"Searching symbols for query: {request.query}")
        
        # Search for symbols
        results = search_symbols(request.query, request.limit)
        
        response = SymbolSearchResponse(
            query=request.query,
            total_results=len(results),
            symbols=results
        )
        
        logger.info(f"Found {len(results)} symbols for query: {request.query}")
        return response
        
    except Exception as e:
        logger.error(f"Error searching symbols: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while searching symbols"
        )


@router.get("/market/summary", response_model=MarketSummaryResponse, summary="Get Market Summary")
async def get_market_summary_endpoint(
    user=Depends(get_current_user)
) -> MarketSummaryResponse:
    """
    Get overall market summary and key indices.
    
    This endpoint provides a high-level view of market conditions
    including major indices, market status, and top movers.
    
    Args:
        user: Authenticated user
        
    Returns:
        MarketSummaryResponse: Market summary data
        
    Raises:
        HTTPException: If market data unavailable
    """
    try:
        logger.info("Fetching market summary")
        
        # Get market summary
        summary = await get_market_summary()
        
        if "error" in summary:
            raise HTTPException(
                status_code=503,
                detail="Market data temporarily unavailable"
            )
        
        response = MarketSummaryResponse(
            timestamp=summary.get("timestamp", datetime.utcnow().isoformat()),
            market_status=summary.get("market_status", "unknown"),
            indices=summary.get("indices", {}),
            top_gainers=[],  # Placeholder - would be implemented with real data
            top_losers=[],   # Placeholder - would be implemented with real data
            most_active=[]   # Placeholder - would be implemented with real data
        )
        
        logger.info("Successfully fetched market summary")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching market summary: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching market summary"
        )


@router.get("/market/status", summary="Get Market Status")
async def get_market_status(user=Depends(get_current_user)) -> Dict[str, Any]:
    """
    Get current market status and trading hours.
    
    Args:
        user: Authenticated user
        
    Returns:
        Dict: Market status information
    """
    try:
        # Simplified market status - in production, check actual market hours
        current_time = datetime.utcnow()
        
        # Basic market hours logic (simplified)
        is_weekday = current_time.weekday() < 5
        is_trading_hours = 9 <= current_time.hour < 16  # 9 AM - 4 PM UTC
        
        market_status = "open" if is_weekday and is_trading_hours else "closed"
        
        return {
            "status": market_status,
            "timestamp": current_time.isoformat(),
            "next_open": "Next trading day at 9:00 AM UTC",
            "next_close": "Today at 4:00 PM UTC" if is_trading_hours else "Next trading day at 4:00 PM UTC"
        }
        
    except Exception as e:
        logger.error(f"Error fetching market status: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching market status"
        )


@router.get("/symbols/validate/{symbol}", summary="Validate Symbol")
async def validate_symbol(
    symbol: str = Path(..., description="Symbol to validate"),
    user=Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Validate if a symbol exists and get basic information.
    
    Args:
        symbol: Symbol to validate
        user: Authenticated user
        
    Returns:
        Dict: Validation result and symbol information
    """
    try:
        symbol_upper = symbol.upper().strip()
        
        # Try to get basic price data to validate symbol
        data = await get_price_with_history(symbol_upper, "1d")
        
        if data:
            return {
                "valid": True,
                "symbol": symbol_upper,
                "name": f"{symbol_upper} Corporation",  # Placeholder
                "type": data.get("asset_type", "unknown"),
                "exchange": "NASDAQ",  # Placeholder
                "currency": "USD"  # Placeholder
            }
        else:
            return {
                "valid": False,
                "symbol": symbol_upper,
                "error": "Symbol not found or data unavailable"
            }
            
    except Exception as e:
        logger.error(f"Error validating symbol {symbol}: {e}")
        return {
            "valid": False,
            "symbol": symbol.upper(),
            "error": "Validation failed"
        }


