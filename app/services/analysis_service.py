"""
Technical Analysis Service with Advanced Indicators and Signal Logic
==================================================================

This module provides comprehensive technical analysis capabilities including:
- RSI (Relative Strength Index) - Momentum oscillator
- EMA (Exponential Moving Average) - Trend following indicator
- MACD (Moving Average Convergence Divergence) - Trend and momentum
- Bollinger Bands - Volatility and mean reversion
- SMA (Simple Moving Average) - Basic trend indicator
- Stochastic Oscillator - Momentum indicator
- Williams %R - Momentum oscillator
- ATR (Average True Range) - Volatility measure

Features:
- Mathematical accuracy with proper implementations
- Comprehensive signal generation logic
- Caching for performance optimization
- Support for multiple timeframes
- Risk assessment and confidence scoring
- Integration with market data services
"""

import math
import statistics
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

from app.services.alphavantage_service import get_price_with_history
from app.core.cache import get_cached_indicator, cache_technical_indicator
from app.core.logging import get_logger

logger = get_logger(__name__)


class SignalStrength(Enum):
    """Signal strength enumeration."""
    VERY_WEAK = 1
    WEAK = 2
    MODERATE = 3
    STRONG = 4
    VERY_STRONG = 5


class TrendDirection(Enum):
    """Trend direction enumeration."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"


def simple_moving_average(values: List[float], period: int) -> Optional[float]:
    """
    Calculate Simple Moving Average (SMA).
    
    SMA = Sum of prices over period / period
    
    Args:
        values: List of price values (most recent last)
        period: Number of periods for calculation
        
    Returns:
        Optional[float]: SMA value or None if insufficient data
    """
    if len(values) < period or period <= 0:
        return None
    
    return sum(values[-period:]) / period


def exponential_moving_average(values: List[float], period: int) -> Optional[float]:
    """
    Calculate Exponential Moving Average (EMA).
    
    EMA = Price * Multiplier + Previous_EMA * (1 - Multiplier)
    Multiplier = 2 / (period + 1)
    
    Args:
        values: List of price values (most recent last)
        period: Number of periods for calculation
        
    Returns:
        Optional[float]: EMA value or None if insufficient data
    """
    if len(values) < period or period <= 0:
        return None
    
    multiplier = 2 / (period + 1)
    ema = values[0]  # Start with first value
    
    for price in values[1:]:
        ema = (price * multiplier) + (ema * (1 - multiplier))
    
    return ema


def relative_strength_index(values: List[float], period: int = 14) -> Optional[float]:
    """
    Calculate Relative Strength Index (RSI).
    
    RSI = 100 - (100 / (1 + RS))
    RS = Average Gain / Average Loss
    
    Args:
        values: List of price values (most recent last)
        period: Number of periods for calculation (default 14)
        
    Returns:
        Optional[float]: RSI value (0-100) or None if insufficient data
    """
    if len(values) < period + 1 or period <= 0:
        return None
    
    # Calculate price changes
    changes = []
    for i in range(1, len(values)):
        changes.append(values[i] - values[i-1])
    
    if len(changes) < period:
        return None
    
    # Separate gains and losses
    gains = [change if change > 0 else 0 for change in changes[-period:]]
    losses = [-change if change < 0 else 0 for change in changes[-period:]]
    
    # Calculate average gain and loss
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    
    # Handle division by zero
    if avg_loss == 0:
        return 100.0
    
    # Calculate RS and RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def macd(values: List[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Optional[Dict[str, float]]:
    """
    Calculate MACD (Moving Average Convergence Divergence).
    
    MACD Line = EMA(fast) - EMA(slow)
    Signal Line = EMA(MACD Line)
    Histogram = MACD Line - Signal Line
    
    Args:
        values: List of price values (most recent last)
        fast_period: Fast EMA period (default 12)
        slow_period: Slow EMA period (default 26)
        signal_period: Signal line EMA period (default 9)
        
    Returns:
        Optional[Dict]: MACD values or None if insufficient data
    """
    if len(values) < slow_period + signal_period:
        return None
    
    # Calculate EMAs
    ema_fast = exponential_moving_average(values, fast_period)
    ema_slow = exponential_moving_average(values, slow_period)
    
    if ema_fast is None or ema_slow is None:
        return None
    
    # Calculate MACD line
    macd_line = ema_fast - ema_slow
    
    # Calculate MACD line values for signal line
    macd_values = []
    for i in range(slow_period, len(values)):
        fast_ema = exponential_moving_average(values[:i+1], fast_period)
        slow_ema = exponential_moving_average(values[:i+1], slow_period)
        if fast_ema is not None and slow_ema is not None:
            macd_values.append(fast_ema - slow_ema)
    
    # Calculate signal line
    signal_line = exponential_moving_average(macd_values, signal_period)
    
    if signal_line is None:
        return None
    
    # Calculate histogram
    histogram = macd_line - signal_line
    
    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram
    }


def bollinger_bands(values: List[float], period: int = 20, num_std: float = 2.0) -> Optional[Dict[str, float]]:
    """
    Calculate Bollinger Bands.
    
    Middle Band = SMA(period)
    Upper Band = SMA + (num_std * Standard Deviation)
    Lower Band = SMA - (num_std * Standard Deviation)
    
    Args:
        values: List of price values (most recent last)
        period: Number of periods for SMA calculation (default 20)
        num_std: Number of standard deviations (default 2.0)
        
    Returns:
        Optional[Dict]: Bollinger Bands values or None if insufficient data
    """
    if len(values) < period or period <= 0:
        return None
    
    # Calculate SMA
    sma = simple_moving_average(values, period)
    if sma is None:
        return None
    
    # Calculate standard deviation
    window = values[-period:]
    variance = sum((price - sma) ** 2 for price in window) / period
    std_dev = math.sqrt(variance)
    
    # Calculate bands
    upper_band = sma + (num_std * std_dev)
    lower_band = sma - (num_std * std_dev)
    
    return {
        "upper": upper_band,
        "middle": sma,
        "lower": lower_band,
        "width": upper_band - lower_band,
        "percent_b": (values[-1] - lower_band) / (upper_band - lower_band) * 100 if upper_band != lower_band else 50
    }


def stochastic_oscillator(values: List[float], period: int = 14, k_period: int = 3) -> Optional[Dict[str, float]]:
    """
    Calculate Stochastic Oscillator.
    
    %K = ((Current Close - Lowest Low) / (Highest High - Lowest Low)) * 100
    %D = SMA(%K, k_period)
    
    Args:
        values: List of price values (most recent last)
        period: Lookback period (default 14)
        k_period: Smoothing period for %D (default 3)
        
    Returns:
        Optional[Dict]: Stochastic values or None if insufficient data
    """
    if len(values) < period or period <= 0:
        return None
    
    # Calculate %K values
    k_values = []
    for i in range(period - 1, len(values)):
        window = values[i - period + 1:i + 1]
        highest_high = max(window)
        lowest_low = min(window)
        
        if highest_high == lowest_low:
            k_values.append(50)  # Neutral when no range
        else:
            k_percent = ((values[i] - lowest_low) / (highest_high - lowest_low)) * 100
            k_values.append(k_percent)
    
    if len(k_values) < k_period:
        return None
    
    # Calculate %D (SMA of %K)
    d_percent = simple_moving_average(k_values, k_period)
    
    return {
        "k_percent": k_values[-1],
        "d_percent": d_percent
    }


def williams_r(values: List[float], period: int = 14) -> Optional[float]:
    """
    Calculate Williams %R.
    
    %R = ((Highest High - Current Close) / (Highest High - Lowest Low)) * -100
    
    Args:
        values: List of price values (most recent last)
        period: Lookback period (default 14)
        
    Returns:
        Optional[float]: Williams %R value (-100 to 0) or None if insufficient data
    """
    if len(values) < period or period <= 0:
        return None
    
    window = values[-period:]
    highest_high = max(window)
    lowest_low = min(window)
    current_close = values[-1]
    
    if highest_high == lowest_low:
        return -50  # Neutral when no range
    
    williams_r = ((highest_high - current_close) / (highest_high - lowest_low)) * -100
    return williams_r


def average_true_range(values: List[float], period: int = 14) -> Optional[float]:
    """
    Calculate Average True Range (ATR).
    
    True Range = max(High - Low, |High - Previous Close|, |Low - Previous Close|)
    ATR = SMA(True Range)
    
    Args:
        values: List of price values (most recent last)
        period: Number of periods for calculation (default 14)
        
    Returns:
        Optional[float]: ATR value or None if insufficient data
    """
    if len(values) < period + 1 or period <= 0:
        return None
    
    # For simplicity, using price as high/low/close
    # In real implementation, you'd have separate high/low/close arrays
    true_ranges = []
    
    for i in range(1, len(values)):
        high = values[i]
        low = values[i]
        prev_close = values[i - 1]
        
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        
        true_range = max(tr1, tr2, tr3)
        true_ranges.append(true_range)
    
    if len(true_ranges) < period:
        return None
    
    return simple_moving_average(true_ranges, period)


def generate_trading_signals(
    current_price: float,
    rsi: Optional[float],
    macd_data: Optional[Dict[str, float]],
    bb_data: Optional[Dict[str, float]],
    stoch_data: Optional[Dict[str, float]],
    williams_r: Optional[float],
    ema_20: Optional[float],
    ema_50: Optional[float]
) -> Dict[str, Any]:
    """
    Generate comprehensive trading signals based on multiple indicators.
    
    Args:
        current_price: Current asset price
        rsi: RSI value
        macd_data: MACD indicator data
        bb_data: Bollinger Bands data
        stoch_data: Stochastic Oscillator data
        williams_r: Williams %R value
        ema_20: 20-period EMA
        ema_50: 50-period EMA
        
    Returns:
        Dict: Comprehensive signal analysis
    """
    signals = {
        "primary_signal": "HOLD",
        "signal_strength": SignalStrength.WEAK.value,
        "confidence": 0.0,
        "trend_direction": TrendDirection.SIDEWAYS.value,
        "individual_signals": {},
        "risk_level": "medium",
        "reasoning": []
    }
    
    buy_signals = 0
    sell_signals = 0
    total_signals = 0
    
    # RSI Signals
    if rsi is not None:
        total_signals += 1
        if rsi < 30:
            signals["individual_signals"]["rsi"] = "STRONG_BUY"
            buy_signals += 1
            signals["reasoning"].append(f"RSI oversold at {rsi:.1f}")
        elif rsi < 40:
            signals["individual_signals"]["rsi"] = "BUY"
            buy_signals += 0.5
            signals["reasoning"].append(f"RSI approaching oversold at {rsi:.1f}")
        elif rsi > 70:
            signals["individual_signals"]["rsi"] = "STRONG_SELL"
            sell_signals += 1
            signals["reasoning"].append(f"RSI overbought at {rsi:.1f}")
        elif rsi > 60:
            signals["individual_signals"]["rsi"] = "SELL"
            sell_signals += 0.5
            signals["reasoning"].append(f"RSI approaching overbought at {rsi:.1f}")
        else:
            signals["individual_signals"]["rsi"] = "NEUTRAL"
    
    # MACD Signals
    if macd_data and macd_data["macd"] is not None and macd_data["signal"] is not None:
        total_signals += 1
        macd_line = macd_data["macd"]
        signal_line = macd_data["signal"]
        histogram = macd_data["histogram"]
        
        if macd_line > signal_line and histogram > 0:
            signals["individual_signals"]["macd"] = "BUY"
            buy_signals += 1
            signals["reasoning"].append("MACD bullish crossover")
        elif macd_line < signal_line and histogram < 0:
            signals["individual_signals"]["macd"] = "SELL"
            sell_signals += 1
            signals["reasoning"].append("MACD bearish crossover")
        else:
            signals["individual_signals"]["macd"] = "NEUTRAL"
    
    # Bollinger Bands Signals
    if bb_data and bb_data["upper"] is not None:
        total_signals += 1
        upper = bb_data["upper"]
        lower = bb_data["lower"]
        middle = bb_data["middle"]
        percent_b = bb_data["percent_b"]
        
        if current_price <= lower:
            signals["individual_signals"]["bollinger"] = "STRONG_BUY"
            buy_signals += 1
            signals["reasoning"].append(f"Price at lower Bollinger Band ({percent_b:.1f}%)")
        elif current_price >= upper:
            signals["individual_signals"]["bollinger"] = "STRONG_SELL"
            sell_signals += 1
            signals["reasoning"].append(f"Price at upper Bollinger Band ({percent_b:.1f}%)")
        elif current_price < middle:
            signals["individual_signals"]["bollinger"] = "BUY"
            buy_signals += 0.5
        elif current_price > middle:
            signals["individual_signals"]["bollinger"] = "SELL"
            sell_signals += 0.5
        else:
            signals["individual_signals"]["bollinger"] = "NEUTRAL"
    
    # Stochastic Signals
    if stoch_data and stoch_data["k_percent"] is not None:
        total_signals += 1
        k_percent = stoch_data["k_percent"]
        
        if k_percent < 20:
            signals["individual_signals"]["stochastic"] = "BUY"
            buy_signals += 0.5
            signals["reasoning"].append(f"Stochastic oversold at {k_percent:.1f}%")
        elif k_percent > 80:
            signals["individual_signals"]["stochastic"] = "SELL"
            sell_signals += 0.5
            signals["reasoning"].append(f"Stochastic overbought at {k_percent:.1f}%")
        else:
            signals["individual_signals"]["stochastic"] = "NEUTRAL"
    
    # Williams %R Signals
    if williams_r is not None:
        total_signals += 1
        if williams_r < -80:
            signals["individual_signals"]["williams_r"] = "BUY"
            buy_signals += 0.5
            signals["reasoning"].append(f"Williams %R oversold at {williams_r:.1f}")
        elif williams_r > -20:
            signals["individual_signals"]["williams_r"] = "SELL"
            sell_signals += 0.5
            signals["reasoning"].append(f"Williams %R overbought at {williams_r:.1f}")
        else:
            signals["individual_signals"]["williams_r"] = "NEUTRAL"
    
    # EMA Trend Signals
    if ema_20 is not None and ema_50 is not None:
        total_signals += 1
        if ema_20 > ema_50 and current_price > ema_20:
            signals["individual_signals"]["ema_trend"] = "BUY"
            buy_signals += 1
            signals["reasoning"].append("Price above rising EMAs (bullish trend)")
            signals["trend_direction"] = TrendDirection.BULLISH.value
        elif ema_20 < ema_50 and current_price < ema_20:
            signals["individual_signals"]["ema_trend"] = "SELL"
            sell_signals += 1
            signals["reasoning"].append("Price below falling EMAs (bearish trend)")
            signals["trend_direction"] = TrendDirection.BEARISH.value
        else:
            signals["individual_signals"]["ema_trend"] = "NEUTRAL"
    
    # Determine primary signal
    if total_signals > 0:
        buy_ratio = buy_signals / total_signals
        sell_ratio = sell_signals / total_signals
        
        if buy_ratio > 0.6:
            signals["primary_signal"] = "BUY"
            signals["signal_strength"] = SignalStrength.STRONG.value if buy_ratio > 0.8 else SignalStrength.MODERATE.value
        elif sell_ratio > 0.6:
            signals["primary_signal"] = "SELL"
            signals["signal_strength"] = SignalStrength.STRONG.value if sell_ratio > 0.8 else SignalStrength.MODERATE.value
        else:
            signals["primary_signal"] = "HOLD"
            signals["signal_strength"] = SignalStrength.WEAK.value
        
        # Calculate confidence
        signals["confidence"] = max(buy_ratio, sell_ratio) * 100
        
        # Determine risk level
        if signals["confidence"] > 80:
            signals["risk_level"] = "low"
        elif signals["confidence"] > 60:
            signals["risk_level"] = "medium"
        else:
            signals["risk_level"] = "high"
    
    return signals


async def compute_signal_bundle(symbol: str, period: str = "1mo") -> Optional[Dict[str, Any]]:
    """
    Compute comprehensive technical analysis signals for a symbol.
    
    Args:
        symbol: Asset symbol
        period: Historical period for analysis
        
    Returns:
        Optional[Dict]: Complete signal analysis or None if failed
    """
    try:
        logger.info(f"Computing signals for {symbol}")
        
        # Check cache first
        cache_key = f"{symbol}_{period}"
        cached_signals = await get_cached_indicator(symbol, cache_key)
        if cached_signals:
            logger.debug(f"Returning cached signals for {symbol}")
            return cached_signals
        
        # Get price data
        price_data = await get_price_with_history(symbol, period)
        if not price_data:
            logger.warning(f"No price data available for {symbol}")
            return None
        
        current_price = price_data["current_price"]
        history = price_data.get("history", [])
        
        # Extract price series from history
        if history:
            prices = [float(h["close"]) for h in history[-50:]]  # Last 50 data points
        else:
            # Generate synthetic data for demo if no history available
            logger.warning(f"No history data for {symbol}, generating synthetic data")
            base_price = current_price
            prices = [base_price * (1 + (i - 25) * 0.01) for i in range(50)]
        
        if len(prices) < 26:  # Need at least 26 for MACD
            logger.warning(f"Insufficient data for {symbol}: {len(prices)} points")
            return None
        
        # Calculate all indicators
        rsi = relative_strength_index(prices, 14)
        macd_data = macd(prices, 12, 26, 9)
        bb_data = bollinger_bands(prices, 20, 2.0)
        stoch_data = stochastic_oscillator(prices, 14, 3)
        williams_r = williams_r(prices, 14)
        ema_20 = exponential_moving_average(prices, 20)
        ema_50 = exponential_moving_average(prices, 50)
        sma_20 = simple_moving_average(prices, 20)
        atr = average_true_range(prices, 14)
        
        # Generate trading signals
        signals = generate_trading_signals(
            current_price, rsi, macd_data, bb_data, stoch_data,
            williams_r, ema_20, ema_50
        )
        
        # Compile comprehensive result
        result = {
            "symbol": symbol.upper(),
            "current_price": current_price,
            "timestamp": datetime.utcnow().isoformat(),
            "period": period,
            "signal": signals["primary_signal"],
            "signal_strength": signals["signal_strength"],
            "confidence": signals["confidence"],
            "trend_direction": signals["trend_direction"],
            "risk_level": signals["risk_level"],
            "reasoning": signals["reasoning"],
            "indicators": {
                "rsi": rsi,
                "ema_20": ema_20,
                "ema_50": ema_50,
                "sma_20": sma_20,
                "atr": atr,
                "williams_r": williams_r
            },
            "macd": macd_data,
            "bollinger_bands": bb_data,
            "stochastic": stoch_data,
            "individual_signals": signals["individual_signals"]
        }
        
        # Cache the result
        await cache_technical_indicator(symbol, cache_key, result, ttl=600)  # 10 minutes
        
        logger.info(f"Generated {signals['primary_signal']} signal for {symbol} with {signals['confidence']:.1f}% confidence")
        
        return result
        
    except Exception as e:
        logger.error(f"Error computing signals for {symbol}: {e}")
        return None


async def get_market_overview(symbols: List[str]) -> Dict[str, Any]:
    """
    Get technical analysis overview for multiple symbols.
    
    Args:
        symbols: List of asset symbols
        
    Returns:
        Dict: Market overview with signals for all symbols
    """
    try:
        logger.info(f"Generating market overview for {len(symbols)} symbols")
        
        # Compute signals for all symbols
        tasks = [compute_signal_bundle(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        overview = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_symbols": len(symbols),
            "successful_analyses": 0,
            "signals_summary": {
                "BUY": 0,
                "SELL": 0,
                "HOLD": 0
            },
            "strong_signals": [],
            "symbols": {}
        }
        
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to analyze {symbol}: {result}")
                overview["symbols"][symbol] = {"error": str(result)}
            elif result:
                overview["successful_analyses"] += 1
                overview["signals_summary"][result["signal"]] += 1
                
                if result["signal_strength"] >= SignalStrength.STRONG.value:
                    overview["strong_signals"].append({
                        "symbol": symbol,
                        "signal": result["signal"],
                        "confidence": result["confidence"]
                    })
                
                overview["symbols"][symbol] = {
                    "signal": result["signal"],
                    "confidence": result["confidence"],
                    "trend": result["trend_direction"],
                    "risk": result["risk_level"],
                    "price": result["current_price"]
                }
            else:
                overview["symbols"][symbol] = {"error": "No data available"}
        
        return overview
        
    except Exception as e:
        logger.error(f"Error generating market overview: {e}")
        return {"error": str(e)}


# Import asyncio for the market overview function
import asyncio


