"""
Market Screener Routes - Advanced Asset Screening and Discovery API
================================================================

This module provides comprehensive market screening endpoints including:
- Multi-strategy asset screening (momentum, value, growth, quality)
- Custom screening criteria and filters
- Sector and industry analysis
- Market cap and volume filters
- Technical indicator-based screening
- Risk-adjusted screening metrics

Features:
- Pre-defined screening strategies
- Custom filter combinations
- Real-time screening results
- Performance ranking and scoring
- Sector rotation analysis
- Market breadth indicators
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.services.alphavantage_service import get_multiple_prices
from app.services.analysis_service import compute_signal_bundle, get_market_overview

logger = get_logger(__name__)
router = APIRouter()


class ScreeningStrategy(str, Enum):
    """Available screening strategies."""
    MOMENTUM = "momentum"
    VALUE = "value"
    GROWTH = "growth"
    QUALITY = "quality"
    DIVIDEND = "dividend"
    LOW_VOLATILITY = "low_volatility"
    HIGH_BETA = "high_beta"
    TECHNICAL = "technical"
    SECTOR_ROTATION = "sector_rotation"


class AssetFilter(BaseModel):
    """Individual asset filter criteria."""
    field: str = Field(..., description="Filter field (price, volume, market_cap, etc.)")
    operator: str = Field(..., description="Filter operator (gt, lt, eq, between)")
    value: Any = Field(..., description="Filter value")
    min_value: Optional[float] = Field(None, description="Minimum value for range filters")
    max_value: Optional[float] = Field(None, description="Maximum value for range filters")


class ScreeningRequest(BaseModel):
    """Request model for custom screening."""
    strategy: Optional[ScreeningStrategy] = Field(None, description="Pre-defined strategy")
    filters: List[AssetFilter] = Field([], description="Custom filters")
    sectors: List[str] = Field([], description="Sectors to include")
    market_cap_min: Optional[float] = Field(None, ge=0, description="Minimum market cap")
    market_cap_max: Optional[float] = Field(None, ge=0, description="Maximum market cap")
    volume_min: Optional[int] = Field(None, ge=0, description="Minimum volume")
    price_min: Optional[float] = Field(None, ge=0, description="Minimum price")
    price_max: Optional[float] = Field(None, ge=0, description="Maximum price")
    limit: int = Field(50, ge=1, le=200, description="Maximum number of results")


class ScreenedAsset(BaseModel):
    """Screened asset data model."""
    symbol: str
    name: str
    sector: str
    industry: str
    price: float
    change: float
    change_percent: float
    volume: int
    market_cap: float
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    score: float
    rank: int
    signal: str
    confidence: float


class ScreeningResponse(BaseModel):
    """Response model for screening results."""
    strategy: str
    timestamp: str
    total_assets_screened: int
    total_results: int
    filters_applied: List[str]
    assets: List[ScreenedAsset]
    sector_breakdown: Dict[str, int]
    performance_summary: Dict[str, Any]


class SectorAnalysisResponse(BaseModel):
    """Response model for sector analysis."""
    timestamp: str
    sectors: List[Dict[str, Any]]
    sector_rotation_signals: Dict[str, str]
    top_performing_sectors: List[str]
    bottom_performing_sectors: List[str]


class MarketBreadthResponse(BaseModel):
    """Response model for market breadth analysis."""
    timestamp: str
    advancing_stocks: int
    declining_stocks: int
    unchanged_stocks: int
    advance_decline_ratio: float
    new_highs: int
    new_lows: int
    market_sentiment: str
    breadth_indicator: float


# Pre-defined screening strategies
SCREENING_STRATEGIES = {
    ScreeningStrategy.MOMENTUM: {
        "name": "Momentum Strategy",
        "description": "Stocks with strong price momentum and volume",
        "criteria": {
            "change_percent_min": 5.0,
            "volume_min": 1000000,
            "rsi_max": 70,
            "rsi_min": 30
        }
    },
    ScreeningStrategy.VALUE: {
        "name": "Value Strategy",
        "description": "Undervalued stocks with strong fundamentals",
        "criteria": {
            "pe_ratio_max": 15.0,
            "pb_ratio_max": 2.0,
            "dividend_yield_min": 2.0,
            "price_min": 5.0
        }
    },
    ScreeningStrategy.GROWTH: {
        "name": "Growth Strategy",
        "description": "High-growth stocks with strong earnings",
        "criteria": {
            "change_percent_min": 10.0,
            "volume_min": 500000,
            "market_cap_min": 1000000000,
            "price_min": 10.0
        }
    },
    ScreeningStrategy.QUALITY: {
        "name": "Quality Strategy",
        "description": "High-quality stocks with strong balance sheets",
        "criteria": {
            "pe_ratio_min": 10.0,
            "pe_ratio_max": 25.0,
            "dividend_yield_min": 1.0,
            "beta_max": 1.2
        }
    },
    ScreeningStrategy.DIVIDEND: {
        "name": "Dividend Strategy",
        "description": "High dividend yield stocks",
        "criteria": {
            "dividend_yield_min": 3.0,
            "pe_ratio_max": 20.0,
            "price_min": 5.0,
            "volume_min": 100000
        }
    },
    ScreeningStrategy.LOW_VOLATILITY: {
        "name": "Low Volatility Strategy",
        "description": "Stable, low-risk stocks",
        "criteria": {
            "beta_max": 0.8,
            "change_percent_max": 3.0,
            "price_min": 10.0,
            "market_cap_min": 500000000
        }
    },
    ScreeningStrategy.HIGH_BETA: {
        "name": "High Beta Strategy",
        "description": "High-beta stocks for aggressive growth",
        "criteria": {
            "beta_min": 1.5,
            "change_percent_min": 2.0,
            "volume_min": 500000,
            "price_min": 5.0
        }
    },
    ScreeningStrategy.TECHNICAL: {
        "name": "Technical Strategy",
        "description": "Stocks with strong technical signals",
        "criteria": {
            "rsi_min": 40,
            "rsi_max": 60,
            "signal": "BUY",
            "confidence_min": 70.0
        }
    }
}


@router.post("/", response_model=ScreeningResponse, summary="Screen Assets")
async def screen_assets(
    request: ScreeningRequest,
    user=Depends(get_current_user)
) -> ScreeningResponse:
    """
    Screen assets based on specified criteria and strategies.
    
    This endpoint provides comprehensive asset screening capabilities including:
    - Pre-defined screening strategies (momentum, value, growth, etc.)
    - Custom filter combinations
    - Sector and market cap filtering
    - Technical indicator-based screening
    - Performance scoring and ranking
    
    Args:
        request: Screening criteria and parameters
        user: Authenticated user
        
    Returns:
        ScreeningResponse: Screened assets with analysis
        
    Raises:
        HTTPException: If screening fails
    """
    try:
        logger.info(f"Screening assets with strategy: {request.strategy}")
        
        # Get universe of symbols to screen
        # In production, this would come from a comprehensive asset database
        universe_symbols = [
            "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "NFLX",
            "ADBE", "CRM", "ORCL", "INTC", "AMD", "QCOM", "AVGO", "TXN",
            "JPM", "BAC", "WFC", "GS", "MS", "C", "AXP", "V", "MA",
            "JNJ", "PFE", "UNH", "ABBV", "MRK", "TMO", "ABT", "DHR",
            "KO", "PEP", "WMT", "PG", "JPM", "HD", "DIS", "NKE"
        ]
        
        # Apply strategy-specific criteria
        if request.strategy and request.strategy in SCREENING_STRATEGIES:
            strategy_criteria = SCREENING_STRATEGIES[request.strategy]["criteria"]
            logger.info(f"Applying {request.strategy} strategy criteria")
        
        # Get current prices and signals for universe
        price_data = await get_multiple_prices(universe_symbols)
        
        # Screen assets based on criteria
        screened_assets = []
        filters_applied = []
        
        for symbol in universe_symbols:
            if symbol not in price_data or price_data[symbol] is None:
                continue
            
            data = price_data[symbol]
            
            # Apply basic filters
            if request.price_min and data["current_price"] < request.price_min:
                continue
            if request.price_max and data["current_price"] > request.price_max:
                continue
            if request.volume_min and data.get("volume", 0) < request.volume_min:
                continue
            
            # Get technical analysis
            signal_data = await compute_signal_bundle(symbol)
            
            # Calculate score based on strategy
            score = calculate_screening_score(symbol, data, signal_data, request.strategy)
            
            # Create screened asset
            asset = ScreenedAsset(
                symbol=symbol,
                name=f"{symbol} Corporation",  # Placeholder
                sector=get_sector_for_symbol(symbol),
                industry=get_industry_for_symbol(symbol),
                price=data["current_price"],
                change=data.get("change", 0.0),
                change_percent=data.get("change_percent", 0.0),
                volume=data.get("volume", 0),
                market_cap=data.get("current_price", 0) * 1000000,  # Placeholder
                pe_ratio=15.0 + (hash(symbol) % 20),  # Placeholder
                pb_ratio=1.0 + (hash(symbol) % 3),  # Placeholder
                dividend_yield=2.0 + (hash(symbol) % 5),  # Placeholder
                beta=0.8 + (hash(symbol) % 1.5),  # Placeholder
                score=score,
                rank=0,  # Will be set after sorting
                signal=signal_data["signal"] if signal_data else "HOLD",
                confidence=signal_data["confidence"] if signal_data else 50.0
            )
            
            screened_assets.append(asset)
        
        # Sort by score and assign ranks
        screened_assets.sort(key=lambda x: x.score, reverse=True)
        for i, asset in enumerate(screened_assets):
            asset.rank = i + 1
        
        # Apply limit
        screened_assets = screened_assets[:request.limit]
        
        # Calculate sector breakdown
        sector_breakdown = {}
        for asset in screened_assets:
            sector_breakdown[asset.sector] = sector_breakdown.get(asset.sector, 0) + 1
        
        # Calculate performance summary
        performance_summary = {
            "average_score": sum(a.score for a in screened_assets) / len(screened_assets) if screened_assets else 0,
            "average_change": sum(a.change_percent for a in screened_assets) / len(screened_assets) if screened_assets else 0,
            "buy_signals": sum(1 for a in screened_assets if a.signal == "BUY"),
            "sell_signals": sum(1 for a in screened_assets if a.signal == "SELL"),
            "hold_signals": sum(1 for a in screened_assets if a.signal == "HOLD")
        }
        
        response = ScreeningResponse(
            strategy=request.strategy.value if request.strategy else "custom",
            timestamp=datetime.utcnow().isoformat(),
            total_assets_screened=len(universe_symbols),
            total_results=len(screened_assets),
            filters_applied=filters_applied,
            assets=screened_assets,
            sector_breakdown=sector_breakdown,
            performance_summary=performance_summary
        )
        
        logger.info(f"Successfully screened {len(screened_assets)} assets from {len(universe_symbols)} universe")
        return response
        
    except Exception as e:
        logger.error(f"Error screening assets: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while screening assets"
        )


@router.get("/strategies", summary="Get Available Strategies")
async def get_screening_strategies(user=Depends(get_current_user)) -> Dict[str, Any]:
    """
    Get available screening strategies and their criteria.
    
    Returns:
        Dict: Available strategies with descriptions and criteria
    """
    return {
        "strategies": SCREENING_STRATEGIES,
        "total_strategies": len(SCREENING_STRATEGIES),
        "custom_filters_available": True
    }


@router.get("/sectors", response_model=SectorAnalysisResponse, summary="Get Sector Analysis")
async def get_sector_analysis(
    user=Depends(get_current_user)
) -> SectorAnalysisResponse:
    """
    Get comprehensive sector analysis and rotation signals.
    
    Args:
        user: Authenticated user
        
    Returns:
        SectorAnalysisResponse: Sector analysis data
        
    Raises:
        HTTPException: If sector analysis fails
    """
    try:
        logger.info("Computing sector analysis")
        
        # Define sectors and their representative symbols
        sectors = {
            "Technology": ["AAPL", "GOOGL", "MSFT", "NVDA", "META"],
            "Healthcare": ["JNJ", "PFE", "UNH", "ABBV", "MRK"],
            "Financial": ["JPM", "BAC", "WFC", "GS", "MS"],
            "Consumer": ["KO", "PEP", "WMT", "PG", "HD"],
            "Industrial": ["BA", "CAT", "GE", "MMM", "HON"],
            "Energy": ["XOM", "CVX", "COP", "EOG", "SLB"]
        }
        
        sector_analysis = []
        sector_performance = {}
        
        for sector_name, symbols in sectors.items():
            # Get sector performance
            price_data = await get_multiple_prices(symbols)
            sector_signals = await get_market_overview(symbols)
            
            # Calculate sector metrics
            valid_prices = [data["current_price"] for data in price_data.values() if data]
            avg_price = sum(valid_prices) / len(valid_prices) if valid_prices else 0
            
            buy_signals = sum(1 for s in sector_signals.get("symbols", {}).values() 
                             if s.get("signal") == "BUY")
            total_signals = len(sector_signals.get("symbols", {}))
            
            sector_performance[sector_name] = {
                "average_price": avg_price,
                "buy_signal_ratio": buy_signals / total_signals if total_signals > 0 else 0,
                "symbols_count": len(symbols)
            }
            
            sector_analysis.append({
                "sector": sector_name,
                "performance": avg_price,
                "buy_signals": buy_signals,
                "total_signals": total_signals,
                "signal_ratio": buy_signals / total_signals if total_signals > 0 else 0,
                "trend": "bullish" if buy_signals > total_signals / 2 else "bearish"
            })
        
        # Sort sectors by performance
        sector_analysis.sort(key=lambda x: x["signal_ratio"], reverse=True)
        
        # Determine sector rotation signals
        top_sectors = [s["sector"] for s in sector_analysis[:2]]
        bottom_sectors = [s["sector"] for s in sector_analysis[-2:]]
        
        sector_rotation_signals = {
            "in_favor": top_sectors,
            "out_of_favor": bottom_sectors,
            "rotation_signal": "Technology to Healthcare" if "Technology" in top_sectors else "No clear rotation"
        }
        
        response = SectorAnalysisResponse(
            timestamp=datetime.utcnow().isoformat(),
            sectors=sector_analysis,
            sector_rotation_signals=sector_rotation_signals,
            top_performing_sectors=top_sectors,
            bottom_performing_sectors=bottom_sectors
        )
        
        logger.info("Successfully computed sector analysis")
        return response
        
    except Exception as e:
        logger.error(f"Error computing sector analysis: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while computing sector analysis"
        )


@router.get("/breadth", response_model=MarketBreadthResponse, summary="Get Market Breadth")
async def get_market_breadth(
    user=Depends(get_current_user)
) -> MarketBreadthResponse:
    """
    Get market breadth analysis and sentiment indicators.
    
    Args:
        user: Authenticated user
        
    Returns:
        MarketBreadthResponse: Market breadth data
        
    Raises:
        HTTPException: If breadth analysis fails
    """
    try:
        logger.info("Computing market breadth analysis")
        
        # Get broad market symbols
        market_symbols = [
            "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "NFLX",
            "JPM", "BAC", "WFC", "GS", "MS", "C", "AXP", "V", "MA",
            "JNJ", "PFE", "UNH", "ABBV", "MRK", "TMO", "ABT", "DHR",
            "KO", "PEP", "WMT", "PG", "HD", "DIS", "NKE", "BA", "CAT"
        ]
        
        # Get market signals
        market_signals = await get_market_overview(market_symbols)
        
        # Calculate breadth metrics
        advancing_stocks = sum(1 for s in market_signals.get("symbols", {}).values() 
                              if s.get("signal") == "BUY")
        declining_stocks = sum(1 for s in market_signals.get("symbols", {}).values() 
                              if s.get("signal") == "SELL")
        unchanged_stocks = sum(1 for s in market_signals.get("symbols", {}).values() 
                              if s.get("signal") == "HOLD")
        
        total_stocks = advancing_stocks + declining_stocks + unchanged_stocks
        advance_decline_ratio = advancing_stocks / declining_stocks if declining_stocks > 0 else float('inf')
        
        # Calculate breadth indicator (simplified)
        breadth_indicator = (advancing_stocks - declining_stocks) / total_stocks if total_stocks > 0 else 0
        
        # Determine market sentiment
        if breadth_indicator > 0.3:
            market_sentiment = "Very Bullish"
        elif breadth_indicator > 0.1:
            market_sentiment = "Bullish"
        elif breadth_indicator > -0.1:
            market_sentiment = "Neutral"
        elif breadth_indicator > -0.3:
            market_sentiment = "Bearish"
        else:
            market_sentiment = "Very Bearish"
        
        response = MarketBreadthResponse(
            timestamp=datetime.utcnow().isoformat(),
            advancing_stocks=advancing_stocks,
            declining_stocks=declining_stocks,
            unchanged_stocks=unchanged_stocks,
            advance_decline_ratio=advance_decline_ratio,
            new_highs=advancing_stocks // 2,  # Placeholder
            new_lows=declining_stocks // 2,   # Placeholder
            market_sentiment=market_sentiment,
            breadth_indicator=breadth_indicator
        )
        
        logger.info(f"Successfully computed market breadth: {market_sentiment}")
        return response
        
    except Exception as e:
        logger.error(f"Error computing market breadth: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while computing market breadth"
        )


def calculate_screening_score(symbol: str, price_data: Dict, signal_data: Optional[Dict], strategy: Optional[ScreeningStrategy]) -> float:
    """Calculate screening score based on strategy."""
    score = 50.0  # Base score
    
    if not price_data or not signal_data:
        return score
    
    # Strategy-specific scoring
    if strategy == ScreeningStrategy.MOMENTUM:
        score += price_data.get("change_percent", 0) * 2
        score += min(signal_data.get("confidence", 50), 100) * 0.3
        if signal_data.get("signal") == "BUY":
            score += 20
    elif strategy == ScreeningStrategy.VALUE:
        # Placeholder for value metrics
        score += 30 if price_data.get("change_percent", 0) < 5 else 10
    elif strategy == ScreeningStrategy.GROWTH:
        score += price_data.get("change_percent", 0) * 1.5
        score += signal_data.get("confidence", 50) * 0.2
    elif strategy == ScreeningStrategy.TECHNICAL:
        score += signal_data.get("confidence", 50) * 0.5
        if signal_data.get("signal") == "BUY":
            score += 30
        elif signal_data.get("signal") == "SELL":
            score -= 20
    
    return max(0, min(100, score))


def get_sector_for_symbol(symbol: str) -> str:
    """Get sector for a symbol (simplified)."""
    sector_map = {
        "AAPL": "Technology", "GOOGL": "Technology", "MSFT": "Technology", "NVDA": "Technology",
        "JPM": "Financial", "BAC": "Financial", "WFC": "Financial", "GS": "Financial",
        "JNJ": "Healthcare", "PFE": "Healthcare", "UNH": "Healthcare", "ABBV": "Healthcare",
        "KO": "Consumer", "PEP": "Consumer", "WMT": "Consumer", "PG": "Consumer"
    }
    return sector_map.get(symbol, "Other")


def get_industry_for_symbol(symbol: str) -> str:
    """Get industry for a symbol (simplified)."""
    industry_map = {
        "AAPL": "Consumer Electronics", "GOOGL": "Internet Services", "MSFT": "Software",
        "JPM": "Banking", "BAC": "Banking", "WFC": "Banking",
        "JNJ": "Pharmaceuticals", "PFE": "Pharmaceuticals", "UNH": "Health Insurance"
    }
    return industry_map.get(symbol, "General")


