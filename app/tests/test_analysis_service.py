"""
Technical Analysis Service Tests
===============================

This module contains comprehensive tests for the technical analysis service
including all indicators, signal generation, and market overview functionality.
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime

from app.services.analysis_service import (
    simple_moving_average,
    exponential_moving_average,
    relative_strength_index,
    macd,
    bollinger_bands,
    stochastic_oscillator,
    williams_r,
    average_true_range,
    generate_trading_signals,
    compute_signal_bundle,
    get_market_overview,
    SignalStrength,
    TrendDirection
)


class TestMovingAverages:
    """Test moving average calculations."""
    
    def test_simple_moving_average(self):
        """Test SMA calculation."""
        prices = [10, 12, 14, 16, 18, 20, 22, 24, 26, 28]
        
        # Test valid calculation
        sma = simple_moving_average(prices, 5)
        assert sma == 22.0  # (18+20+22+24+26)/5
        
        # Test insufficient data
        sma_short = simple_moving_average(prices, 15)
        assert sma_short is None
        
        # Test invalid period
        sma_invalid = simple_moving_average(prices, 0)
        assert sma_invalid is None
    
    def test_exponential_moving_average(self):
        """Test EMA calculation."""
        prices = [10, 12, 14, 16, 18, 20, 22, 24, 26, 28]
        
        # Test valid calculation
        ema = exponential_moving_average(prices, 5)
        assert ema is not None
        assert isinstance(ema, float)
        
        # Test insufficient data
        ema_short = exponential_moving_average(prices, 15)
        assert ema_short is None


class TestRSI:
    """Test RSI calculation."""
    
    def test_rsi_calculation(self):
        """Test RSI calculation with known values."""
        # Test data with clear uptrend
        prices = [44, 44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.85, 47.25, 47.61]
        
        rsi = relative_strength_index(prices, 5)
        assert rsi is not None
        assert 0 <= rsi <= 100
        
        # Test insufficient data
        rsi_short = relative_strength_index(prices, 15)
        assert rsi_short is None
    
    def test_rsi_edge_cases(self):
        """Test RSI edge cases."""
        # All gains (should be 100)
        prices_up = [10, 11, 12, 13, 14, 15]
        rsi_up = relative_strength_index(prices_up, 5)
        assert rsi_up == 100.0
        
        # All losses (should be 0)
        prices_down = [15, 14, 13, 12, 11, 10]
        rsi_down = relative_strength_index(prices_down, 5)
        assert rsi_down == 0.0


class TestMACD:
    """Test MACD calculation."""
    
    def test_macd_calculation(self):
        """Test MACD calculation."""
        prices = [i for i in range(50)]  # 50 data points
        
        macd_data = macd(prices, 12, 26, 9)
        assert macd_data is not None
        assert "macd" in macd_data
        assert "signal" in macd_data
        assert "histogram" in macd_data
        
        # Test insufficient data
        macd_short = macd(prices[:20], 12, 26, 9)
        assert macd_short is None


class TestBollingerBands:
    """Test Bollinger Bands calculation."""
    
    def test_bollinger_bands_calculation(self):
        """Test Bollinger Bands calculation."""
        prices = [i for i in range(30)]  # 30 data points
        
        bb_data = bollinger_bands(prices, 20, 2.0)
        assert bb_data is not None
        assert "upper" in bb_data
        assert "middle" in bb_data
        assert "lower" in bb_data
        assert "width" in bb_data
        assert "percent_b" in bb_data
        
        # Verify bands are ordered correctly
        assert bb_data["upper"] > bb_data["middle"] > bb_data["lower"]
        
        # Test insufficient data
        bb_short = bollinger_bands(prices[:10], 20, 2.0)
        assert bb_short is None


class TestStochasticOscillator:
    """Test Stochastic Oscillator calculation."""
    
    def test_stochastic_calculation(self):
        """Test Stochastic Oscillator calculation."""
        prices = [i for i in range(20)]  # 20 data points
        
        stoch_data = stochastic_oscillator(prices, 14, 3)
        assert stoch_data is not None
        assert "k_percent" in stoch_data
        assert "d_percent" in stoch_data
        
        # Verify %K is between 0 and 100
        assert 0 <= stoch_data["k_percent"] <= 100
        
        # Test insufficient data
        stoch_short = stochastic_oscillator(prices[:10], 14, 3)
        assert stoch_short is None


class TestWilliamsR:
    """Test Williams %R calculation."""
    
    def test_williams_r_calculation(self):
        """Test Williams %R calculation."""
        prices = [i for i in range(20)]  # 20 data points
        
        williams_r_val = williams_r(prices, 14)
        assert williams_r_val is not None
        assert -100 <= williams_r_val <= 0
        
        # Test insufficient data
        williams_r_short = williams_r(prices[:10], 14)
        assert williams_r_short is None


class TestATR:
    """Test Average True Range calculation."""
    
    def test_atr_calculation(self):
        """Test ATR calculation."""
        prices = [i for i in range(20)]  # 20 data points
        
        atr_val = average_true_range(prices, 14)
        assert atr_val is not None
        assert atr_val >= 0
        
        # Test insufficient data
        atr_short = average_true_range(prices[:10], 14)
        assert atr_short is None


class TestSignalGeneration:
    """Test trading signal generation."""
    
    def test_bullish_signals(self):
        """Test generation of bullish signals."""
        signals = generate_trading_signals(
            current_price=100.0,
            rsi=25.0,  # Oversold
            macd_data={"macd": 1.0, "signal": 0.5, "histogram": 0.5},  # Bullish crossover
            bb_data={"upper": 110, "middle": 100, "lower": 90, "percent_b": 20},  # Near lower band
            stoch_data={"k_percent": 15},  # Oversold
            williams_r=-85,  # Oversold
            ema_20=102,  # Above EMA50
            ema_50=98
        )
        
        assert signals["primary_signal"] == "BUY"
        assert signals["signal_strength"] >= SignalStrength.MODERATE.value
        assert signals["confidence"] > 50
        assert signals["trend_direction"] == TrendDirection.BULLISH.value
    
    def test_bearish_signals(self):
        """Test generation of bearish signals."""
        signals = generate_trading_signals(
            current_price=100.0,
            rsi=75.0,  # Overbought
            macd_data={"macd": 0.5, "signal": 1.0, "histogram": -0.5},  # Bearish crossover
            bb_data={"upper": 110, "middle": 100, "lower": 90, "percent_b": 80},  # Near upper band
            stoch_data={"k_percent": 85},  # Overbought
            williams_r=-15,  # Overbought
            ema_20=98,  # Below EMA50
            ema_50=102
        )
        
        assert signals["primary_signal"] == "SELL"
        assert signals["signal_strength"] >= SignalStrength.MODERATE.value
        assert signals["confidence"] > 50
        assert signals["trend_direction"] == TrendDirection.BEARISH.value
    
    def test_neutral_signals(self):
        """Test generation of neutral signals."""
        signals = generate_trading_signals(
            current_price=100.0,
            rsi=50.0,  # Neutral
            macd_data={"macd": 0.5, "signal": 0.5, "histogram": 0.0},  # Neutral
            bb_data={"upper": 110, "middle": 100, "lower": 90, "percent_b": 50},  # Middle
            stoch_data={"k_percent": 50},  # Neutral
            williams_r=-50,  # Neutral
            ema_20=100,  # Same as EMA50
            ema_50=100
        )
        
        assert signals["primary_signal"] == "HOLD"
        assert signals["signal_strength"] == SignalStrength.WEAK.value
        assert signals["confidence"] < 50


class TestSignalBundle:
    """Test comprehensive signal bundle computation."""
    
    @pytest.mark.asyncio
    async def test_compute_signal_bundle_success(self):
        """Test successful signal bundle computation."""
        mock_price_data = {
            "current_price": 150.0,
            "history": [
                {"close": 140 + i} for i in range(50)
            ]
        }
        
        with patch('app.services.analysis_service.get_price_with_history') as mock_get_price, \
             patch('app.services.analysis_service.get_cached_indicator') as mock_cache, \
             patch('app.services.analysis_service.cache_technical_indicator') as mock_cache_set:
            
            mock_cache.return_value = None
            mock_get_price.return_value = mock_price_data
            
            result = await compute_signal_bundle("AAPL")
            
            assert result is not None
            assert result["symbol"] == "AAPL"
            assert "signal" in result
            assert "confidence" in result
            assert "indicators" in result
            assert "macd" in result
            assert "bollinger_bands" in result
            assert "stochastic" in result
            assert "individual_signals" in result
            
            mock_cache_set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_compute_signal_bundle_no_data(self):
        """Test signal bundle computation with no price data."""
        with patch('app.services.analysis_service.get_price_with_history') as mock_get_price, \
             patch('app.services.analysis_service.get_cached_indicator') as mock_cache:
            
            mock_cache.return_value = None
            mock_get_price.return_value = None
            
            result = await compute_signal_bundle("INVALID")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_compute_signal_bundle_cached(self):
        """Test signal bundle computation with cached data."""
        cached_data = {
            "symbol": "AAPL",
            "signal": "BUY",
            "confidence": 75.0
        }
        
        with patch('app.services.analysis_service.get_cached_indicator') as mock_cache:
            mock_cache.return_value = cached_data
            
            result = await compute_signal_bundle("AAPL")
            
            assert result == cached_data


class TestMarketOverview:
    """Test market overview functionality."""
    
    @pytest.mark.asyncio
    async def test_market_overview_success(self):
        """Test successful market overview generation."""
        symbols = ["AAPL", "GOOGL", "MSFT"]
        
        mock_results = [
            {
                "symbol": "AAPL",
                "signal": "BUY",
                "confidence": 75.0,
                "trend_direction": "bullish",
                "risk_level": "medium",
                "current_price": 150.0,
                "signal_strength": 4
            },
            {
                "symbol": "GOOGL",
                "signal": "SELL",
                "confidence": 80.0,
                "trend_direction": "bearish",
                "risk_level": "low",
                "current_price": 2800.0,
                "signal_strength": 4
            },
            {
                "symbol": "MSFT",
                "signal": "HOLD",
                "confidence": 45.0,
                "trend_direction": "sideways",
                "risk_level": "high",
                "current_price": 300.0,
                "signal_strength": 2
            }
        ]
        
        with patch('app.services.analysis_service.compute_signal_bundle') as mock_compute:
            mock_compute.side_effect = mock_results
            
            result = await get_market_overview(symbols)
            
            assert result["total_symbols"] == 3
            assert result["successful_analyses"] == 3
            assert result["signals_summary"]["BUY"] == 1
            assert result["signals_summary"]["SELL"] == 1
            assert result["signals_summary"]["HOLD"] == 1
            assert len(result["strong_signals"]) == 2  # AAPL and GOOGL have strong signals
            
            # Check individual symbol data
            assert "AAPL" in result["symbols"]
            assert result["symbols"]["AAPL"]["signal"] == "BUY"
            assert result["symbols"]["AAPL"]["confidence"] == 75.0
    
    @pytest.mark.asyncio
    async def test_market_overview_with_errors(self):
        """Test market overview with some failures."""
        symbols = ["AAPL", "INVALID", "MSFT"]
        
        mock_results = [
            {
                "symbol": "AAPL",
                "signal": "BUY",
                "confidence": 75.0,
                "trend_direction": "bullish",
                "risk_level": "medium",
                "current_price": 150.0,
                "signal_strength": 4
            },
            Exception("No data available"),
            {
                "symbol": "MSFT",
                "signal": "HOLD",
                "confidence": 45.0,
                "trend_direction": "sideways",
                "risk_level": "high",
                "current_price": 300.0,
                "signal_strength": 2
            }
        ]
        
        with patch('app.services.analysis_service.compute_signal_bundle') as mock_compute:
            mock_compute.side_effect = mock_results
            
            result = await get_market_overview(symbols)
            
            assert result["total_symbols"] == 3
            assert result["successful_analyses"] == 2
            assert result["signals_summary"]["BUY"] == 1
            assert result["signals_summary"]["HOLD"] == 1
            
            # Check error handling
            assert "INVALID" in result["symbols"]
            assert "error" in result["symbols"]["INVALID"]


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_price_list(self):
        """Test handling of empty price lists."""
        assert simple_moving_average([], 5) is None
        assert exponential_moving_average([], 5) is None
        assert relative_strength_index([], 14) is None
        assert macd([], 12, 26, 9) is None
        assert bollinger_bands([], 20, 2.0) is None
    
    def test_single_price(self):
        """Test handling of single price value."""
        prices = [100.0]
        
        assert simple_moving_average(prices, 1) == 100.0
        assert exponential_moving_average(prices, 1) == 100.0
        assert relative_strength_index(prices, 14) is None
        assert macd(prices, 12, 26, 9) is None
    
    def test_negative_prices(self):
        """Test handling of negative prices."""
        prices = [-10, -8, -6, -4, -2, 0, 2, 4, 6, 8]
        
        sma = simple_moving_average(prices, 5)
        assert sma is not None
        
        rsi = relative_strength_index(prices, 5)
        assert rsi is not None
        assert 0 <= rsi <= 100


if __name__ == "__main__":
    pytest.main([__file__])

