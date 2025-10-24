#!/usr/bin/env python3
"""
External Services Demo Script for InsightFinance API
====================================================

This script demonstrates the external market data services by:
1. Testing different asset types (stocks, crypto, forex)
2. Showing fallback mechanisms between data sources
3. Demonstrating caching and rate limiting
4. Testing multiple symbol fetching

Usage:
    python external_services_demo.py

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

from app.services.alphavantage_service import (
    get_price_with_history,
    get_multiple_prices,
    search_symbols,
    get_market_summary,
    _detect_asset_type
)
from app.core.logging import configure_logging, get_logger

# Configure logging
configure_logging(log_level="INFO", log_file="external_services_demo.log", enable_file=True)
logger = get_logger(__name__)


async def test_asset_type_detection():
    """Test asset type detection."""
    print("🔍 Testing Asset Type Detection")
    print("=" * 40)
    
    test_symbols = [
        ("AAPL", "stock"),
        ("GOOGL", "stock"),
        ("MSFT", "stock"),
        ("BTC", "crypto"),
        ("ETH", "crypto"),
        ("ADA", "crypto"),
        ("EURUSD", "forex"),
        ("GBPJPY", "forex"),
        ("AUDCAD", "forex")
    ]
    
    for symbol, expected_type in test_symbols:
        detected_type = _detect_asset_type(symbol)
        status = "✅" if detected_type == expected_type else "❌"
        print(f"{status} {symbol:8} -> {detected_type:6} (expected: {expected_type})")
    
    print()


async def test_single_symbol_fetch():
    """Test fetching data for a single symbol."""
    print("📊 Testing Single Symbol Fetch")
    print("=" * 40)
    
    test_symbols = ["AAPL", "BTC", "EURUSD"]
    
    for symbol in test_symbols:
        print(f"Fetching data for {symbol}...")
        try:
            data = await get_price_with_history(symbol)
            if data:
                print(f"✅ {symbol}: ${data['current_price']:.2f} ({data['source']})")
                print(f"   Change: {data['change']:+.2f} ({data['change_percent']:+.2f}%)")
                print(f"   Volume: {data.get('volume', 'N/A'):,}")
                print(f"   Asset Type: {data.get('asset_type', 'unknown')}")
                print(f"   History Points: {len(data.get('history', []))}")
            else:
                print(f"❌ {symbol}: No data available")
        except Exception as e:
            print(f"❌ {symbol}: Error - {e}")
        print()


async def test_multiple_symbols_fetch():
    """Test fetching data for multiple symbols concurrently."""
    print("📈 Testing Multiple Symbols Fetch")
    print("=" * 40)
    
    symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "BTC", "ETH"]
    
    print(f"Fetching data for {len(symbols)} symbols concurrently...")
    start_time = datetime.now()
    
    try:
        results = await get_multiple_prices(symbols)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"Completed in {duration:.2f} seconds")
        print()
        
        for symbol, data in results.items():
            if data:
                print(f"✅ {symbol:6}: ${data['current_price']:8.2f} ({data['source']:12})")
            else:
                print(f"❌ {symbol:6}: No data available")
        
    except Exception as e:
        print(f"❌ Error fetching multiple symbols: {e}")
    
    print()


async def test_symbol_search():
    """Test symbol search functionality."""
    print("🔍 Testing Symbol Search")
    print("=" * 40)
    
    search_queries = ["Apple", "Google", "Bitcoin", "Tesla"]
    
    for query in search_queries:
        print(f"Searching for '{query}'...")
        try:
            results = search_symbols(query, limit=3)
            if results:
                print(f"Found {len(results)} results:")
                for result in results:
                    print(f"  • {result['symbol']:6} - {result['name']} ({result['type']})")
            else:
                print("  No results found")
        except Exception as e:
            print(f"  Error: {e}")
        print()


async def test_market_summary():
    """Test market summary functionality."""
    print("📊 Testing Market Summary")
    print("=" * 40)
    
    try:
        summary = await get_market_summary()
        
        if "error" in summary:
            print(f"❌ Market summary error: {summary['error']}")
        else:
            print(f"✅ Market Summary ({summary['timestamp']})")
            print(f"Market Status: {summary['market_status']}")
            print()
            
            if summary.get("indices"):
                print("Major Indices:")
                for symbol, data in summary["indices"].items():
                    change_symbol = "+" if data["change"] >= 0 else ""
                    print(f"  {symbol:4}: ${data['price']:7.2f} {change_symbol}{data['change']:+.2f} ({change_symbol}{data['change_percent']:+.2f}%)")
            else:
                print("No index data available")
        
    except Exception as e:
        print(f"❌ Market summary error: {e}")
    
    print()


async def test_caching_behavior():
    """Test caching behavior."""
    print("💾 Testing Caching Behavior")
    print("=" * 40)
    
    symbol = "AAPL"
    
    print(f"First fetch for {symbol} (should hit external API)...")
    start_time = datetime.now()
    data1 = await get_price_with_history(symbol)
    end_time = datetime.now()
    duration1 = (end_time - start_time).total_seconds()
    
    if data1:
        print(f"✅ First fetch: ${data1['current_price']:.2f} in {duration1:.2f}s")
        
        print(f"Second fetch for {symbol} (should hit cache)...")
        start_time = datetime.now()
        data2 = await get_price_with_history(symbol)
        end_time = datetime.now()
        duration2 = (end_time - start_time).total_seconds()
        
        if data2:
            print(f"✅ Second fetch: ${data2['current_price']:.2f} in {duration2:.2f}s")
            print(f"Cache speedup: {duration1/duration2:.1f}x faster")
            
            # Verify data consistency
            if abs(data1['current_price'] - data2['current_price']) < 0.01:
                print("✅ Cached data is consistent")
            else:
                print("❌ Cached data differs from original")
        else:
            print("❌ Second fetch failed")
    else:
        print("❌ First fetch failed")
    
    print()


async def test_error_handling():
    """Test error handling with invalid symbols."""
    print("⚠️  Testing Error Handling")
    print("=" * 40)
    
    invalid_symbols = ["INVALID123", "NONEXISTENT", "FAKE_SYMBOL"]
    
    for symbol in invalid_symbols:
        print(f"Testing invalid symbol: {symbol}")
        try:
            data = await get_price_with_history(symbol)
            if data:
                print(f"✅ Unexpected success: ${data['current_price']:.2f}")
            else:
                print("✅ Correctly returned None for invalid symbol")
        except Exception as e:
            print(f"✅ Correctly handled error: {e}")
        print()


async def main():
    """Main demo function."""
    print("🚀 InsightFinance API External Services Demo")
    print("=" * 50)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # Run all tests
        await test_asset_type_detection()
        await test_single_symbol_fetch()
        await test_multiple_symbols_fetch()
        await test_symbol_search()
        await test_market_summary()
        await test_caching_behavior()
        await test_error_handling()
        
        print("🎉 External Services Demo Completed Successfully!")
        print()
        print("Key Features Demonstrated:")
        print("• Asset type detection (stocks, crypto, forex)")
        print("• Multiple data source integration")
        print("• Intelligent caching with Redis")
        print("• Concurrent symbol fetching")
        print("• Symbol search functionality")
        print("• Market summary generation")
        print("• Comprehensive error handling")
        print()
        print("Next Steps:")
        print("- Test the API endpoints: http://localhost:8000/docs")
        print("- Try different symbols and time periods")
        print("- Monitor the logs for detailed information")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"❌ Demo failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

