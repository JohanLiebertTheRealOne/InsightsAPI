"""
Redis Cache Management
=====================

This module handles Redis caching for the InsightFinance API.
It provides a centralized cache interface for storing and retrieving
financial data, API responses, and computed indicators.

Key Features:
- Async Redis client with connection pooling
- Automatic serialization/deserialization
- TTL (Time To Live) management
- Cache key generation and namespacing
- Error handling and fallback mechanisms
"""

import json
import pickle
from typing import Any, Optional, Union, Dict, List
import redis.asyncio as redis
import logging
from datetime import datetime, timedelta

from app.config import settings

logger = logging.getLogger(__name__)

# Global Redis client instance
redis_client: Optional[redis.Redis] = None


class CacheManager:
    """
    Redis cache manager for InsightFinance API.
    
    This class provides a high-level interface for caching operations
    including automatic serialization, TTL management, and error handling.
    """
    
    def __init__(self, redis_client: redis.Redis):
        """
        Initialize cache manager with Redis client.
        
        Args:
            redis_client: Async Redis client instance
        """
        self.redis = redis_client
        self.default_ttl = settings.CACHE_TTL
        self.key_prefix = "insightfinance:"
    
    def _generate_key(self, key: str, namespace: str = "") -> str:
        """
        Generate a namespaced cache key.
        
        Args:
            key: Base cache key
            namespace: Optional namespace for key organization
            
        Returns:
            str: Full cache key with prefix and namespace
        """
        if namespace:
            return f"{self.key_prefix}{namespace}:{key}"
        return f"{self.key_prefix}{key}"
    
    async def get(self, key: str, namespace: str = "", default: Any = None) -> Any:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            namespace: Optional namespace
            default: Default value if key not found
            
        Returns:
            Any: Cached value or default
        """
        try:
            full_key = self._generate_key(key, namespace)
            value = await self.redis.get(full_key)
            
            if value is None:
                return default
            
            # Try to deserialize as JSON first, then pickle
            try:
                return json.loads(value.decode('utf-8'))
            except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
                try:
                    return pickle.loads(value)
                except (pickle.PickleError, TypeError):
                    # Return raw string if deserialization fails
                    return value.decode('utf-8') if isinstance(value, bytes) else value
                    
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return default
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None, 
        namespace: str = ""
    ) -> bool:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if None)
            namespace: Optional namespace
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            full_key = self._generate_key(key, namespace)
            ttl = ttl or self.default_ttl
            
            # Serialize value
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value)
            elif isinstance(value, (str, int, float, bool)):
                serialized_value = json.dumps(value)
            else:
                # Use pickle for complex objects
                serialized_value = pickle.dumps(value)
            
            await self.redis.setex(full_key, ttl, serialized_value)
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str, namespace: str = "") -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key to delete
            namespace: Optional namespace
            
        Returns:
            bool: True if key was deleted, False otherwise
        """
        try:
            full_key = self._generate_key(key, namespace)
            result = await self.redis.delete(full_key)
            return bool(result)
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def exists(self, key: str, namespace: str = "") -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key to check
            namespace: Optional namespace
            
        Returns:
            bool: True if key exists, False otherwise
        """
        try:
            full_key = self._generate_key(key, namespace)
            return bool(await self.redis.exists(full_key))
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False
    
    async def get_or_set(
        self, 
        key: str, 
        factory_func, 
        ttl: Optional[int] = None, 
        namespace: str = ""
    ) -> Any:
        """
        Get value from cache or set it using factory function.
        
        Args:
            key: Cache key
            factory_func: Function to generate value if not cached
            ttl: Time to live in seconds
            namespace: Optional namespace
            
        Returns:
            Any: Cached or newly generated value
        """
        # Try to get from cache first
        cached_value = await self.get(key, namespace)
        if cached_value is not None:
            return cached_value
        
        # Generate new value using factory function
        try:
            if callable(factory_func):
                new_value = await factory_func() if hasattr(factory_func, '__await__') else factory_func()
            else:
                new_value = factory_func
            
            # Cache the new value
            await self.set(key, new_value, ttl, namespace)
            return new_value
            
        except Exception as e:
            logger.error(f"Cache get_or_set error for key {key}: {e}")
            raise
    
    async def clear_namespace(self, namespace: str) -> int:
        """
        Clear all keys in a namespace.
        
        Args:
            namespace: Namespace to clear
            
        Returns:
            int: Number of keys deleted
        """
        try:
            pattern = self._generate_key("*", namespace)
            keys = await self.redis.keys(pattern)
            if keys:
                return await self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache clear namespace error for {namespace}: {e}")
            return 0
    
    async def get_ttl(self, key: str, namespace: str = "") -> int:
        """
        Get remaining TTL for a key.
        
        Args:
            key: Cache key
            namespace: Optional namespace
            
        Returns:
            int: Remaining TTL in seconds (-1 if no expiry, -2 if key doesn't exist)
        """
        try:
            full_key = self._generate_key(key, namespace)
            return await self.redis.ttl(full_key)
        except Exception as e:
            logger.error(f"Cache TTL error for key {key}: {e}")
            return -2


# Global cache manager instance
cache_manager: Optional[CacheManager] = None


async def init_cache():
    """
    Initialize Redis cache connection.
    
    This function creates the Redis client and cache manager instances.
    It should be called during application startup.
    
    Raises:
        Exception: If cache initialization fails
    """
    global redis_client, cache_manager
    
    try:
        logger.info("Initializing Redis cache...")
        
        # Create Redis client with connection pooling
        redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=False,  # We handle encoding manually
            max_connections=20,
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options={},
        )
        
        # Test connection
        await redis_client.ping()
        logger.info("✅ Redis connection test successful")
        
        # Create cache manager
        cache_manager = CacheManager(redis_client)
        logger.info("✅ Cache manager initialized")
        
    except Exception as e:
        logger.error(f"❌ Cache initialization failed: {e}")
        raise


async def close_cache():
    """
    Close Redis cache connections.
    
    This function should be called during application shutdown
    to properly close all Redis connections.
    """
    global redis_client
    
    try:
        if redis_client:
            logger.info("Closing Redis connections...")
            await redis_client.close()
            logger.info("✅ Redis connections closed")
    except Exception as e:
        logger.error(f"❌ Error closing Redis connections: {e}")


def get_cache() -> CacheManager:
    """
    Get the global cache manager instance.
    
    Returns:
        CacheManager: The global cache manager
        
    Raises:
        RuntimeError: If cache is not initialized
    """
    if cache_manager is None:
        raise RuntimeError("Cache not initialized. Call init_cache() first.")
    return cache_manager


# Convenience functions for common cache operations
async def cache_price_data(symbol: str, data: Dict[str, Any], ttl: int = 300) -> bool:
    """
    Cache price data for a symbol.
    
    Args:
        symbol: Stock/crypto symbol
        data: Price data to cache
        ttl: Time to live in seconds
        
    Returns:
        bool: True if successful
    """
    cache = get_cache()
    return await cache.set(f"price:{symbol}", data, ttl, "market_data")


async def get_cached_price_data(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Get cached price data for a symbol.
    
    Args:
        symbol: Stock/crypto symbol
        
    Returns:
        Optional[Dict]: Cached price data or None
    """
    cache = get_cache()
    return await cache.get(f"price:{symbol}", "market_data")


async def cache_technical_indicator(symbol: str, indicator: str, data: Any, ttl: int = 600) -> bool:
    """
    Cache technical indicator data.
    
    Args:
        symbol: Stock/crypto symbol
        indicator: Indicator name (RSI, MACD, etc.)
        data: Indicator data to cache
        ttl: Time to live in seconds
        
    Returns:
        bool: True if successful
    """
    cache = get_cache()
    return await cache.set(f"indicator:{symbol}:{indicator}", data, ttl, "technical")


async def get_cached_indicator(symbol: str, indicator: str) -> Optional[Any]:
    """
    Get cached technical indicator data.
    
    Args:
        symbol: Stock/crypto symbol
        indicator: Indicator name
        
    Returns:
        Optional[Any]: Cached indicator data or None
    """
    cache = get_cache()
    return await cache.get(f"indicator:{symbol}:{indicator}", "technical")


async def health_check() -> bool:
    """
    Check Redis cache health.
    
    Returns:
        bool: True if cache is healthy, False otherwise
    """
    try:
        if redis_client:
            await redis_client.ping()
            return True
        return False
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        return False
