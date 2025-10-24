"""
External Services Tests
======================

This module contains comprehensive tests for external market data services
including Alpha Vantage, Yahoo Finance, and CoinGecko integrations.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.alphavantage_service import (
    get_price_with_history,
    get_multiple_prices,
    search_symbols,
    get_market_summary,
    _detect_asset_type,
    _fetch_alpha_vantage_price,
    _fetch_yahoo_finance_price,
    _fetch_coingecko_price,
    MarketDataError,
    RateLimitError
)


class TestAssetTypeDetection:
    """Test asset type detection functionality."""
    
    def test_detect_stock(self):
        """Test stock symbol detection."""
        assert _detect_asset_type("AAPL") == "stock"
        assert _detect_asset_type("GOOGL") == "stock"
        assert _detect_asset_type("MSFT") == "stock"
    
    def test_detect_crypto(self):
        """Test cryptocurrency symbol detection."""
        assert _detect_asset_type("BTC") == "crypto"
        assert _detect_asset_type("ETH") == "crypto"
        assert _detect_asset_type("ADA") == "crypto"
        assert _detect_asset_type("BTCUSD") == "crypto"  # Contains BTC
    
    def test_detect_forex(self):
        """Test forex pair detection."""
        assert _detect_asset_type("EURUSD") == "forex"
        assert _detect_asset_type("GBPJPY") == "forex"
        assert _detect_asset_type("AUDCAD") == "forex"


class TestAlphaVantageIntegration:
    """Test Alpha Vantage API integration."""
    
    @pytest.mark.asyncio
    async def test_successful_price_fetch(self):
        """Test successful price fetch from Alpha Vantage."""
        mock_response_data = {
            "Global Quote": {
                "01. symbol": "AAPL",
                "02. open": "150.00",
                "03. high": "155.00",
                "04. low": "149.00",
                "05. price": "152.50",
                "06. volume": "1000000",
                "08. previous close": "150.00",
                "09. change": "2.50",
                "10. change percent": "1.67%"
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await _fetch_alpha_vantage_price("AAPL")
            
            assert result is not None
            assert result["symbol"] == "AAPL"
            assert result["current_price"] == 152.50
            assert result["change"] == 2.50
            assert result["change_percent"] == 1.67
            assert result["source"] == "alpha_vantage"
    
    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """Test Alpha Vantage API error handling."""
        mock_response_data = {
            "Error Message": "Invalid API call"
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await _fetch_alpha_vantage_price("INVALID")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_rate_limit_handling(self):
        """Test Alpha Vantage rate limit handling."""
        mock_response_data = {
            "Note": "Thank you for using Alpha Vantage! Our standard API call frequency is 25 requests per day and 5 requests per minute."
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await _fetch_alpha_vantage_price("AAPL")
            
            assert result is None


class TestYahooFinanceIntegration:
    """Test Yahoo Finance API integration."""
    
    @pytest.mark.asyncio
    async def test_successful_price_fetch(self):
        """Test successful price fetch from Yahoo Finance."""
        mock_response_data = {
            "chart": {
                "result": [{
                    "meta": {
                        "regularMarketPrice": 152.50,
                        "previousClose": 150.00,
                        "regularMarketVolume": 1000000,
                        "regularMarketDayHigh": 155.00,
                        "regularMarketDayLow": 149.00,
                        "regularMarketOpen": 150.00
                    }
                }]
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await _fetch_yahoo_finance_price("AAPL")
            
            assert result is not None
            assert result["symbol"] == "AAPL"
            assert result["current_price"] == 152.50
            assert result["change"] == 2.50
            assert result["change_percent"] == pytest.approx(1.67, rel=1e-2)
            assert result["source"] == "yahoo_finance"
    
    @pytest.mark.asyncio
    async def test_no_data_handling(self):
        """Test handling when no data is available."""
        mock_response_data = {
            "chart": {
                "result": []
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await _fetch_yahoo_finance_price("INVALID")
            
            assert result is None


class TestCoinGeckoIntegration:
    """Test CoinGecko API integration."""
    
    @pytest.mark.asyncio
    async def test_successful_crypto_fetch(self):
        """Test successful crypto price fetch from CoinGecko."""
        mock_response_data = {
            "bitcoin": {
                "usd": 45000.00,
                "usd_24h_change": 2.5,
                "usd_24h_vol": 1000000000
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await _fetch_coingecko_price("BTC")
            
            assert result is not None
            assert result["symbol"] == "BTC"
            assert result["current_price"] == 45000.00
            assert result["change_percent"] == 2.5
            assert result["change"] == pytest.approx(1125.0, rel=1e-2)
            assert result["source"] == "coingecko"
    
    @pytest.mark.asyncio
    async def test_unsupported_crypto(self):
        """Test handling of unsupported crypto symbols."""
        result = await _fetch_coingecko_price("UNSUPPORTED")
        assert result is None


class TestMainServiceFunctions:
    """Test main service functions with caching and fallbacks."""
    
    @pytest.mark.asyncio
    async def test_get_price_with_caching(self):
        """Test price fetching with caching."""
        with patch('app.services.alphavantage_service.get_cached_price_data') as mock_cache:
            mock_cache.return_value = {
                "symbol": "AAPL",
                "current_price": 152.50,
                "source": "cached"
            }
            
            result = await get_price_with_history("AAPL")
            
            assert result is not None
            assert result["symbol"] == "AAPL"
            assert result["current_price"] == 152.50
            assert result["source"] == "cached"
    
    @pytest.mark.asyncio
    async def test_get_price_with_fallback(self):
        """Test price fetching with fallback mechanisms."""
        with patch('app.services.alphavantage_service.get_cached_price_data') as mock_cache, \
             patch('app.services.alphavantage_service._fetch_alpha_vantage_price') as mock_av, \
             patch('app.services.alphavantage_service._fetch_yahoo_finance_price') as mock_yf, \
             patch('app.services.alphavantage_service.cache_price_data') as mock_cache_set:
            
            mock_cache.return_value = None
            mock_av.return_value = None
            mock_yf.return_value = {
                "symbol": "AAPL",
                "current_price": 152.50,
                "source": "yahoo_finance"
            }
            
            result = await get_price_with_history("AAPL")
            
            assert result is not None
            assert result["symbol"] == "AAPL"
            assert result["current_price"] == 152.50
            assert result["source"] == "yahoo_finance"
            mock_cache_set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_multiple_prices(self):
        """Test fetching multiple prices concurrently."""
        with patch('app.services.alphavantage_service.get_price_with_history') as mock_get_price:
            mock_get_price.side_effect = [
                {"symbol": "AAPL", "current_price": 152.50},
                {"symbol": "GOOGL", "current_price": 2800.00},
                None  # Third symbol fails
            ]
            
            result = await get_multiple_prices(["AAPL", "GOOGL", "INVALID"])
            
            assert "AAPL" in result
            assert "GOOGL" in result
            assert "INVALID" in result
            assert result["AAPL"]["current_price"] == 152.50
            assert result["GOOGL"]["current_price"] == 2800.00
            assert result["INVALID"] is None
    
    def test_search_symbols(self):
        """Test symbol search functionality."""
        result = search_symbols("Apple")
        assert len(result) > 0
        assert any(symbol["symbol"] == "AAPL" for symbol in result)
        
        result = search_symbols("BTC")
        assert len(result) > 0
        assert any(symbol["symbol"] == "BTC" for symbol in result)
    
    @pytest.mark.asyncio
    async def test_get_market_summary(self):
        """Test market summary functionality."""
        with patch('app.services.alphavantage_service.get_multiple_prices') as mock_prices:
            mock_prices.return_value = {
                "SPY": {"current_price": 400.00, "change": 2.00, "change_percent": 0.5},
                "QQQ": {"current_price": 350.00, "change": -1.00, "change_percent": -0.3},
                "IWM": None,  # Failed to fetch
                "DIA": {"current_price": 300.00, "change": 1.50, "change_percent": 0.5}
            }
            
            result = await get_market_summary()
            
            assert "timestamp" in result
            assert "indices" in result
            assert "market_status" in result
            assert "SPY" in result["indices"]
            assert "QQQ" in result["indices"]
            assert "DIA" in result["indices"]
            assert "IWM" not in result["indices"]  # Failed fetch excluded


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_network_timeout(self):
        """Test handling of network timeouts."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = httpx.TimeoutException("Timeout")
            
            result = await _fetch_alpha_vantage_price("AAPL")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_invalid_json_response(self):
        """Test handling of invalid JSON responses."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = ValueError("Invalid JSON")
            
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await _fetch_alpha_vantage_price("AAPL")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_all_sources_fail(self):
        """Test behavior when all data sources fail."""
        with patch('app.services.alphavantage_service.get_cached_price_data') as mock_cache, \
             patch('app.services.alphavantage_service._fetch_alpha_vantage_price') as mock_av, \
             patch('app.services.alphavantage_service._fetch_yahoo_finance_price') as mock_yf, \
             patch('app.services.alphavantage_service._fetch_coingecko_price') as mock_cg:
            
            mock_cache.return_value = None
            mock_av.return_value = None
            mock_yf.return_value = None
            mock_cg.return_value = None
            
            result = await get_price_with_history("INVALID")
            assert result is None


if __name__ == "__main__":
    pytest.main([__file__])

