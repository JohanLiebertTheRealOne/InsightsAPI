"""
Technical Analysis Signals Routes - Comprehensive Trading Signal API
==================================================================

This module provides comprehensive technical analysis endpoints including:
- Individual symbol signal analysis with multiple indicators
- Batch signal analysis for multiple symbols
- Market overview with signal summaries
- Signal history and tracking
- Custom indicator analysis
- Signal strength and confidence scoring

Features:
- RSI, EMA, MACD, Bollinger Bands, Stochastic, Williams %R analysis
- Multi-timeframe analysis support
- Signal strength classification (1-5 levels)
- Confidence scoring and risk assessment
- Comprehensive signal reasoning
- Caching for performance optimization
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.services.analysis_service import (
    compute_signal_bundle,
    get_market_overview,
    SignalStrength,
    TrendDirection
)

logger = get_logger(__name__)
router = APIRouter()


class IndicatorData(BaseModel):
    """Individual indicator data model."""
    rsi: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    sma_20: Optional[float] = None
    atr: Optional[float] = None
    williams_r: Optional[float] = None


class MACDData(BaseModel):
    """MACD indicator data model."""
    macd: Optional[float] = None
    signal: Optional[float] = None
    histogram: Optional[float] = None


class BollingerBandsData(BaseModel):
    """Bollinger Bands data model."""
    upper: Optional[float] = None
    middle: Optional[float] = None
    lower: Optional[float] = None
    width: Optional[float] = None
    percent_b: Optional[float] = None


class StochasticData(BaseModel):
    """Stochastic Oscillator data model."""
    k_percent: Optional[float] = None
    d_percent: Optional[float] = None


class SignalResponse(BaseModel):
    """Complete signal analysis response model."""
    symbol: str
    current_price: float
    timestamp: str
    period: str
    signal: str
    signal_strength: int
    confidence: float
    trend_direction: str
    risk_level: str
    reasoning: List[str]
    indicators: IndicatorData
    macd: MACDData
    bollinger_bands: BollingerBandsData
    stochastic: StochasticData
    individual_signals: Dict[str, str]


class MultipleSignalsRequest(BaseModel):
    """Request model for multiple symbol signals."""
    symbols: List[str] = Field(..., min_items=1, max_items=20, description="List of symbols to analyze")
    period: str = Field("1mo", description="Analysis period")
    
    @validator('symbols')
    def validate_symbols(cls, v):
        """Validate symbol format."""
        for symbol in v:
            if not symbol or len(symbol.strip()) == 0:
                raise ValueError("Symbol cannot be empty")
            if len(symbol) > 10:
                raise ValueError("Symbol too long")
        return [s.upper().strip() for s in v]


class MultipleSignalsResponse(BaseModel):
    """Response model for multiple symbol signals."""
    timestamp: str
    period: str
    total_symbols: int
    successful_analyses: int
    failed_analyses: int
    signals_summary: Dict[str, int]
    strong_signals: List[Dict[str, Any]]
    signals: Dict[str, Optional[SignalResponse]]
    errors: Dict[str, str] = {}


class MarketOverviewResponse(BaseModel):
    """Response model for market signal overview."""
    timestamp: str
    total_symbols: int
    successful_analyses: int
    signals_summary: Dict[str, int]
    strong_signals: List[Dict[str, Any]]
    symbols: Dict[str, Dict[str, Any]]


class SignalHistoryRequest(BaseModel):
    """Request model for signal history."""
    symbol: str = Field(..., description="Symbol to analyze")
    days: int = Field(30, ge=1, le=365, description="Number of days of history")


class SignalHistoryResponse(BaseModel):
    """Response model for signal history."""
    symbol: str
    period_days: int
    signals: List[Dict[str, Any]]


@router.get("/{symbol}", response_model=SignalResponse, summary="Get Trading Signal Analysis")
async def get_signal(
    symbol: str = Path(..., description="Asset symbol (e.g., AAPL, BTC, EURUSD)"),
    period: str = Query("1mo", description="Analysis period (1d, 1wk, 1mo, 3mo, 6mo, 1y)"),
    user=Depends(get_current_user)
) -> SignalResponse:
    """
    Get comprehensive technical analysis signal for a single symbol.
    
    This endpoint provides detailed technical analysis including:
    - Primary trading signal (BUY/SELL/HOLD)
    - Signal strength (1-5 levels)
    - Confidence score (0-100%)
    - Trend direction (bullish/bearish/sideways)
    - Risk assessment (low/medium/high)
    - All technical indicators (RSI, MACD, Bollinger Bands, etc.)
    - Individual signal reasoning
    
    Args:
        symbol: Asset symbol (stocks, crypto, forex)
        period: Analysis period for technical indicators
        user: Authenticated user
        
    Returns:
        SignalResponse: Complete signal analysis
        
    Raises:
        HTTPException: If symbol not found or analysis fails
    """
    try:
        logger.info(f"Computing signal analysis for {symbol} (period: {period})")
        
        # Validate symbol format
        symbol_upper = symbol.upper().strip()
        if not symbol_upper or len(symbol_upper) > 10:
            raise HTTPException(
                status_code=400,
                detail="Invalid symbol format. Symbol must be 1-10 characters."
            )
        
        # Compute signal analysis
        result = await compute_signal_bundle(symbol_upper, period)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"Unable to compute signal analysis for '{symbol}'"
            )
        
        # Convert to response model
        response = SignalResponse(
            symbol=result["symbol"],
            current_price=result["current_price"],
            timestamp=result["timestamp"],
            period=result["period"],
            signal=result["signal"],
            signal_strength=result["signal_strength"],
            confidence=result["confidence"],
            trend_direction=result["trend_direction"],
            risk_level=result["risk_level"],
            reasoning=result["reasoning"],
            indicators=IndicatorData(**result["indicators"]),
            macd=MACDData(**result["macd"]) if result["macd"] else MACDData(),
            bollinger_bands=BollingerBandsData(**result["bollinger_bands"]) if result["bollinger_bands"] else BollingerBandsData(),
            stochastic=StochasticData(**result["stochastic"]) if result["stochastic"] else StochasticData(),
            individual_signals=result["individual_signals"]
        )
        
        logger.info(f"Successfully computed {result['signal']} signal for {symbol} with {result['confidence']:.1f}% confidence")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing signal for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while computing signal analysis"
        )


@router.post("/batch", response_model=MultipleSignalsResponse, summary="Get Multiple Symbol Signals")
async def get_multiple_signals(
    request: MultipleSignalsRequest,
    user=Depends(get_current_user)
) -> MultipleSignalsResponse:
    """
    Get technical analysis signals for multiple symbols in a single request.
    
    This endpoint efficiently analyzes up to 20 symbols concurrently,
    providing comprehensive signal analysis for each symbol.
    
    Args:
        request: List of symbols and analysis parameters
        user: Authenticated user
        
    Returns:
        MultipleSignalsResponse: Signal analysis for all requested symbols
        
    Raises:
        HTTPException: If request validation fails
    """
    try:
        logger.info(f"Computing signals for {len(request.symbols)} symbols")
        
        # Get market overview (which handles multiple symbols)
        overview = await get_market_overview(request.symbols)
        
        if "error" in overview:
            raise HTTPException(
                status_code=500,
                detail=f"Error analyzing symbols: {overview['error']}"
            )
        
        # Process individual signals
        signals = {}
        errors = {}
        
        for symbol in request.symbols:
            try:
                signal_result = await compute_signal_bundle(symbol, request.period)
                if signal_result:
                    signals[symbol] = SignalResponse(
                        symbol=signal_result["symbol"],
                        current_price=signal_result["current_price"],
                        timestamp=signal_result["timestamp"],
                        period=signal_result["period"],
                        signal=signal_result["signal"],
                        signal_strength=signal_result["signal_strength"],
                        confidence=signal_result["confidence"],
                        trend_direction=signal_result["trend_direction"],
                        risk_level=signal_result["risk_level"],
                        reasoning=signal_result["reasoning"],
                        indicators=IndicatorData(**signal_result["indicators"]),
                        macd=MACDData(**signal_result["macd"]) if signal_result["macd"] else MACDData(),
                        bollinger_bands=BollingerBandsData(**signal_result["bollinger_bands"]) if signal_result["bollinger_bands"] else BollingerBandsData(),
                        stochastic=StochasticData(**signal_result["stochastic"]) if signal_result["stochastic"] else StochasticData(),
                        individual_signals=signal_result["individual_signals"]
                    )
                else:
                    signals[symbol] = None
                    errors[symbol] = "Analysis failed"
            except Exception as e:
                signals[symbol] = None
                errors[symbol] = str(e)
        
        response = MultipleSignalsResponse(
            timestamp=datetime.utcnow().isoformat(),
            period=request.period,
            total_symbols=len(request.symbols),
            successful_analyses=overview["successful_analyses"],
            failed_analyses=len(request.symbols) - overview["successful_analyses"],
            signals_summary=overview["signals_summary"],
            strong_signals=overview["strong_signals"],
            signals=signals,
            errors=errors
        )
        
        logger.info(f"Successfully computed signals for {overview['successful_analyses']}/{len(request.symbols)} symbols")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing multiple signals: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while computing multiple signals"
        )


@router.get("/market/overview", response_model=MarketOverviewResponse, summary="Get Market Signal Overview")
async def get_market_signal_overview(
    symbols: List[str] = Query(default=["AAPL", "GOOGL", "MSFT", "TSLA", "BTC", "ETH"], description="Symbols to analyze"),
    user=Depends(get_current_user)
) -> MarketOverviewResponse:
    """
    Get market-wide signal overview for multiple symbols.
    
    This endpoint provides a high-level view of market signals including:
    - Signal distribution (BUY/SELL/HOLD counts)
    - Strong signal identification
    - Market sentiment analysis
    - Individual symbol summaries
    
    Args:
        symbols: List of symbols to analyze (default: major stocks and crypto)
        user: Authenticated user
        
    Returns:
        MarketOverviewResponse: Market signal overview
        
    Raises:
        HTTPException: If market analysis fails
    """
    try:
        logger.info(f"Generating market signal overview for {len(symbols)} symbols")
        
        # Validate symbols
        validated_symbols = []
        for symbol in symbols:
            symbol_upper = symbol.upper().strip()
            if symbol_upper and len(symbol_upper) <= 10:
                validated_symbols.append(symbol_upper)
        
        if not validated_symbols:
            raise HTTPException(
                status_code=400,
                detail="No valid symbols provided"
            )
        
        # Get market overview
        overview = await get_market_overview(validated_symbols)
        
        if "error" in overview:
            raise HTTPException(
                status_code=500,
                detail=f"Error generating market overview: {overview['error']}"
            )
        
        response = MarketOverviewResponse(
            timestamp=overview["timestamp"],
            total_symbols=overview["total_symbols"],
            successful_analyses=overview["successful_analyses"],
            signals_summary=overview["signals_summary"],
            strong_signals=overview["strong_signals"],
            symbols=overview["symbols"]
        )
        
        logger.info(f"Successfully generated market overview for {overview['successful_analyses']} symbols")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating market overview: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while generating market overview"
        )


@router.get("/{symbol}/history", response_model=SignalHistoryResponse, summary="Get Signal History")
async def get_signal_history(
    symbol: str = Path(..., description="Symbol to analyze"),
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    user=Depends(get_current_user)
) -> SignalHistoryResponse:
    """
    Get historical signal analysis for a symbol.
    
    This endpoint provides historical signal data to track how signals
    have changed over time for backtesting and analysis purposes.
    
    Args:
        symbol: Asset symbol to analyze
        days: Number of days of historical data
        user: Authenticated user
        
    Returns:
        SignalHistoryResponse: Historical signal data
        
    Raises:
        HTTPException: If historical analysis fails
    """
    try:
        symbol_upper = symbol.upper().strip()
        
        logger.info(f"Computing signal history for {symbol_upper} ({days} days)")
        
        # For demo purposes, generate synthetic historical signals
        # In production, this would query a database of historical signals
        signals = []
        base_date = datetime.utcnow() - timedelta(days=days)
        
        for i in range(days):
            date = base_date + timedelta(days=i)
            
            # Generate synthetic signal data
            signal_data = {
                "date": date.strftime("%Y-%m-%d"),
                "signal": ["BUY", "SELL", "HOLD"][i % 3],
                "confidence": 60 + (i % 40),
                "rsi": 30 + (i % 40),
                "price": 100 + (i % 20),
                "reasoning": f"Historical signal for {date.strftime('%Y-%m-%d')}"
            }
            signals.append(signal_data)
        
        response = SignalHistoryResponse(
            symbol=symbol_upper,
            period_days=days,
            signals=signals
        )
        
        logger.info(f"Successfully generated {days} days of signal history for {symbol_upper}")
        return response
        
    except Exception as e:
        logger.error(f"Error generating signal history for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while generating signal history"
        )


@router.get("/indicators/{symbol}", summary="Get Individual Indicators")
async def get_individual_indicators(
    symbol: str = Path(..., description="Symbol to analyze"),
    period: str = Query("1mo", description="Analysis period"),
    user=Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get individual technical indicators for a symbol.
    
    This endpoint provides raw indicator values without signal interpretation,
    useful for custom analysis and indicator-specific applications.
    
    Args:
        symbol: Asset symbol to analyze
        period: Analysis period
        user: Authenticated user
        
    Returns:
        Dict: Individual indicator values
        
    Raises:
        HTTPException: If indicator calculation fails
    """
    try:
        symbol_upper = symbol.upper().strip()
        
        logger.info(f"Computing individual indicators for {symbol_upper}")
        
        # Get signal analysis (which includes all indicators)
        result = await compute_signal_bundle(symbol_upper, period)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"Unable to compute indicators for '{symbol}'"
            )
        
        # Extract individual indicators
        indicators = {
            "symbol": symbol_upper,
            "timestamp": result["timestamp"],
            "period": period,
            "current_price": result["current_price"],
            "indicators": result["indicators"],
            "macd": result["macd"],
            "bollinger_bands": result["bollinger_bands"],
            "stochastic": result["stochastic"]
        }
        
        logger.info(f"Successfully computed indicators for {symbol_upper}")
        return indicators
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing indicators for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while computing indicators"
        )


@router.get("/strength/levels", summary="Get Signal Strength Levels")
async def get_signal_strength_levels(user=Depends(get_current_user)) -> Dict[str, Any]:
    """
    Get information about signal strength levels.
    
    Returns:
        Dict: Signal strength level definitions
    """
    return {
        "levels": {
            1: {"name": "Very Weak", "description": "Minimal signal strength"},
            2: {"name": "Weak", "description": "Low signal strength"},
            3: {"name": "Moderate", "description": "Medium signal strength"},
            4: {"name": "Strong", "description": "High signal strength"},
            5: {"name": "Very Strong", "description": "Maximum signal strength"}
        },
        "trend_directions": {
            "bullish": "Upward price trend",
            "bearish": "Downward price trend",
            "sideways": "Horizontal price movement"
        },
        "risk_levels": {
            "low": "Low risk trade",
            "medium": "Medium risk trade",
            "high": "High risk trade"
        }
    }


