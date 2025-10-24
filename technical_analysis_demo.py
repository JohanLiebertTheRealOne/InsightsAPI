#!/usr/bin/env python3
"""
Technical Analysis Demo Script for InsightFinance API
=====================================================

This script demonstrates the comprehensive technical analysis capabilities by:
1. Testing all technical indicators (RSI, EMA, MACD, Bollinger Bands, etc.)
2. Showing signal generation and confidence scoring
3. Demonstrating market overview functionality
4. Testing different market conditions and scenarios

Usage:
    python technical_analysis_demo.py

Requirements:
    - API server running (uvicorn app.main:app --reload)
    - Database and Redis initialized
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.analysis_service import (
    compute_signal_bundle,
    get_market_overview,
    simple_moving_average,
    exponential_moving_average,
    relative_strength_index,
    macd,
    bollinger_bands,
    stochastic_oscillator,
    williams_r,
    average_true_range,
    SignalStrength,
    TrendDirection
)
from app.core.logging import configure_logging, get_logger

# Configure logging
configure_logging(log_level="INFO", log_file="technical_analysis_demo.log", enable_file=True)
logger = get_logger(__name__)


def test_individual_indicators():
    """Test individual technical indicators with sample data."""
    print("📊 Testing Individual Technical Indicators")
    print("=" * 50)
    
    # Sample price data (simulating a trending market)
    prices = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110, 112, 114, 113, 115, 117, 116, 118, 120]
    
    print(f"Sample price data: {len(prices)} data points")
    print(f"Price range: ${min(prices):.2f} - ${max(prices):.2f}")
    print()
    
    # Test Simple Moving Average
    sma_5 = simple_moving_average(prices, 5)
    sma_10 = simple_moving_average(prices, 10)
    print(f"📈 Simple Moving Averages:")
    print(f"   SMA(5):  ${sma_5:.2f}")
    print(f"   SMA(10): ${sma_10:.2f}")
    print()
    
    # Test Exponential Moving Average
    ema_5 = exponential_moving_average(prices, 5)
    ema_10 = exponential_moving_average(prices, 10)
    print(f"📈 Exponential Moving Averages:")
    print(f"   EMA(5):  ${ema_5:.2f}")
    print(f"   EMA(10): ${ema_10:.2f}")
    print()
    
    # Test RSI
    rsi = relative_strength_index(prices, 14)
    print(f"📊 Relative Strength Index (RSI):")
    print(f"   RSI(14): {rsi:.2f}")
    if rsi:
        if rsi < 30:
            print("   Status: Oversold (Bullish)")
        elif rsi > 70:
            print("   Status: Overbought (Bearish)")
        else:
            print("   Status: Neutral")
    print()
    
    # Test MACD
    macd_data = macd(prices, 12, 26, 9)
    print(f"📊 MACD (Moving Average Convergence Divergence):")
    if macd_data:
        print(f"   MACD Line: {macd_data['macd']:.4f}")
        print(f"   Signal Line: {macd_data['signal']:.4f}")
        print(f"   Histogram: {macd_data['histogram']:.4f}")
        
        if macd_data['macd'] > macd_data['signal']:
            print("   Status: Bullish (MACD above Signal)")
        else:
            print("   Status: Bearish (MACD below Signal)")
    else:
        print("   Status: Insufficient data")
    print()
    
    # Test Bollinger Bands
    bb_data = bollinger_bands(prices, 20, 2.0)
    print(f"📊 Bollinger Bands:")
    if bb_data:
        print(f"   Upper Band: ${bb_data['upper']:.2f}")
        print(f"   Middle Band: ${bb_data['middle']:.2f}")
        print(f"   Lower Band: ${bb_data['lower']:.2f}")
        print(f"   Band Width: ${bb_data['width']:.2f}")
        print(f"   %B Position: {bb_data['percent_b']:.1f}%")
        
        current_price = prices[-1]
        if current_price <= bb_data['lower']:
            print("   Status: Price at lower band (Potential Buy)")
        elif current_price >= bb_data['upper']:
            print("   Status: Price at upper band (Potential Sell)")
        else:
            print("   Status: Price within bands (Neutral)")
    else:
        print("   Status: Insufficient data")
    print()
    
    # Test Stochastic Oscillator
    stoch_data = stochastic_oscillator(prices, 14, 3)
    print(f"📊 Stochastic Oscillator:")
    if stoch_data:
        print(f"   %K: {stoch_data['k_percent']:.2f}%")
        print(f"   %D: {stoch_data['d_percent']:.2f}%")
        
        if stoch_data['k_percent'] < 20:
            print("   Status: Oversold (Bullish)")
        elif stoch_data['k_percent'] > 80:
            print("   Status: Overbought (Bearish)")
        else:
            print("   Status: Neutral")
    else:
        print("   Status: Insufficient data")
    print()
    
    # Test Williams %R
    williams_r_val = williams_r(prices, 14)
    print(f"📊 Williams %R:")
    if williams_r_val is not None:
        print(f"   Williams %R: {williams_r_val:.2f}")
        
        if williams_r_val < -80:
            print("   Status: Oversold (Bullish)")
        elif williams_r_val > -20:
            print("   Status: Overbought (Bearish)")
        else:
            print("   Status: Neutral")
    else:
        print("   Status: Insufficient data")
    print()
    
    # Test Average True Range
    atr = average_true_range(prices, 14)
    print(f"📊 Average True Range (ATR):")
    if atr:
        print(f"   ATR(14): ${atr:.2f}")
        print(f"   Volatility: {'High' if atr > 2 else 'Low'}")
    else:
        print("   Status: Insufficient data")
    print()


async def test_signal_generation():
    """Test signal generation for different market scenarios."""
    print("🎯 Testing Signal Generation Scenarios")
    print("=" * 50)
    
    test_symbols = ["AAPL", "BTC", "TSLA"]
    
    for symbol in test_symbols:
        print(f"Analyzing {symbol}...")
        try:
            result = await compute_signal_bundle(symbol)
            if result:
                print(f"✅ {symbol} Analysis:")
                print(f"   Signal: {result['signal']}")
                print(f"   Strength: {result['signal_strength']}/5")
                print(f"   Confidence: {result['confidence']:.1f}%")
                print(f"   Trend: {result['trend_direction']}")
                print(f"   Risk Level: {result['risk_level']}")
                print(f"   Current Price: ${result['current_price']:.2f}")
                
                if result['reasoning']:
                    print(f"   Reasoning: {', '.join(result['reasoning'][:2])}")
                
                # Show key indicators
                indicators = result['indicators']
                print(f"   Key Indicators:")
                if indicators.get('rsi'):
                    print(f"     RSI: {indicators['rsi']:.1f}")
                if indicators.get('ema_20'):
                    print(f"     EMA(20): ${indicators['ema_20']:.2f}")
                if indicators.get('ema_50'):
                    print(f"     EMA(50): ${indicators['ema_50']:.2f}")
                
                print()
            else:
                print(f"❌ {symbol}: No analysis available")
                print()
        except Exception as e:
            print(f"❌ {symbol}: Error - {e}")
            print()


async def test_market_overview():
    """Test market overview functionality."""
    print("🌍 Testing Market Overview")
    print("=" * 50)
    
    symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "BTC", "ETH"]
    
    try:
        overview = await get_market_overview(symbols)
        
        if "error" in overview:
            print(f"❌ Market overview error: {overview['error']}")
            return
        
        print(f"📊 Market Overview ({overview['timestamp']})")
        print(f"Total Symbols Analyzed: {overview['successful_analyses']}/{overview['total_symbols']}")
        print()
        
        # Signal summary
        summary = overview['signals_summary']
        print("📈 Signal Summary:")
        print(f"   BUY Signals: {summary['BUY']}")
        print(f"   SELL Signals: {summary['SELL']}")
        print(f"   HOLD Signals: {summary['HOLD']}")
        print()
        
        # Strong signals
        if overview['strong_signals']:
            print("🔥 Strong Signals:")
            for signal in overview['strong_signals']:
                print(f"   {signal['symbol']}: {signal['signal']} ({signal['confidence']:.1f}% confidence)")
            print()
        
        # Individual symbol details
        print("📋 Individual Symbol Analysis:")
        for symbol, data in overview['symbols'].items():
            if 'error' in data:
                print(f"   {symbol}: Error - {data['error']}")
            else:
                signal_emoji = "🟢" if data['signal'] == "BUY" else "🔴" if data['signal'] == "SELL" else "🟡"
                print(f"   {symbol}: {signal_emoji} {data['signal']} ({data['confidence']:.1f}% confidence)")
                print(f"      Trend: {data['trend']}, Risk: {data['risk']}, Price: ${data['price']:.2f}")
        
    except Exception as e:
        print(f"❌ Market overview error: {e}")


def test_signal_strength_enum():
    """Test signal strength enumeration."""
    print("💪 Testing Signal Strength Levels")
    print("=" * 50)
    
    strengths = [
        (SignalStrength.VERY_WEAK, "Very Weak"),
        (SignalStrength.WEAK, "Weak"),
        (SignalStrength.MODERATE, "Moderate"),
        (SignalStrength.STRONG, "Strong"),
        (SignalStrength.VERY_STRONG, "Very Strong")
    ]
    
    for strength, name in strengths:
        print(f"   {strength.value}/5: {name}")
    print()


def test_trend_direction_enum():
    """Test trend direction enumeration."""
    print("📈 Testing Trend Directions")
    print("=" * 50)
    
    trends = [
        (TrendDirection.BULLISH, "🟢 Bullish"),
        (TrendDirection.BEARISH, "🔴 Bearish"),
        (TrendDirection.SIDEWAYS, "🟡 Sideways")
    ]
    
    for trend, name in trends:
        print(f"   {trend.value}: {name}")
    print()


async def test_performance():
    """Test performance with multiple symbols."""
    print("⚡ Testing Performance")
    print("=" * 50)
    
    symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN", "NVDA", "BTC", "ETH", "ADA", "DOT"]
    
    print(f"Analyzing {len(symbols)} symbols concurrently...")
    start_time = datetime.now()
    
    try:
        overview = await get_market_overview(symbols)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        if "error" not in overview:
            print(f"✅ Completed in {duration:.2f} seconds")
            print(f"   Average time per symbol: {duration/len(symbols):.2f} seconds")
            print(f"   Successful analyses: {overview['successful_analyses']}/{overview['total_symbols']}")
        else:
            print(f"❌ Performance test failed: {overview['error']}")
    
    except Exception as e:
        print(f"❌ Performance test error: {e}")


async def main():
    """Main demo function."""
    print("🚀 InsightFinance API Technical Analysis Demo")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # Run all tests
        test_individual_indicators()
        await test_signal_generation()
        await test_market_overview()
        test_signal_strength_enum()
        test_trend_direction_enum()
        await test_performance()
        
        print("🎉 Technical Analysis Demo Completed Successfully!")
        print()
        print("Key Features Demonstrated:")
        print("• RSI, EMA, MACD, Bollinger Bands calculations")
        print("• Stochastic Oscillator and Williams %R")
        print("• Average True Range (ATR) volatility measure")
        print("• Comprehensive signal generation with confidence scoring")
        print("• Market overview with multiple symbol analysis")
        print("• Signal strength and trend direction classification")
        print("• Performance optimization with concurrent processing")
        print()
        print("Next Steps:")
        print("- Test the API endpoints: http://localhost:8000/docs")
        print("- Try different symbols and time periods")
        print("- Monitor the logs for detailed analysis information")
        print("- Experiment with different market conditions")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"❌ Demo failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

