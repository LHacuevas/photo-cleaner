"""
Simple in-memory caching layer for frequently accessed data
"""

from datetime import datetime, timedelta
import logging
import json
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)


class CacheEntry:
    """Represents a cached entry"""
    
    def __init__(self, key: str, value: Any, ttl: int = 3600):
        self.key = key
        self.value = value
        self.ttl = ttl
        self.created_at = datetime.utcnow()
        self.accessed_at = datetime.utcnow()
        self.access_count = 0
    
    def is_expired(self) -> bool:
        """Check if entry has expired"""
        age = (datetime.utcnow() - self.created_at).total_seconds()
        return age > self.ttl
    
    def access(self):
        """Record access"""
        self.accessed_at = datetime.utcnow()
        self.access_count += 1


class SimpleCache:
    """Simple in-memory cache with TTL support"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.cache = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache
        
        Returns:
            Value if exists and not expired, None otherwise
        """
        if key not in self.cache:
            self.misses += 1
            return None
        
        entry = self.cache[key]
        
        if entry.is_expired():
            del self.cache[key]
            self.misses += 1
            logger.debug(f"Cache entry expired: {key}")
            return None
        
        entry.access()
        self.hits += 1
        return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache"""
        if ttl is None:
            ttl = self.default_ttl
        
        # Evict if at max size
        if len(self.cache) >= self.max_size:
            self._evict_lru()
        
        self.cache[key] = CacheEntry(key, value, ttl)
        logger.debug(f"Cached: {key} (TTL: {ttl}s)")
    
    def delete(self, key: str) -> bool:
        """Delete entry from cache"""
        if key in self.cache:
            del self.cache[key]
            logger.debug(f"Cache deleted: {key}")
            return True
        return False
    
    def clear(self):
        """Clear all cache"""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def cleanup_expired(self):
        """Remove all expired entries"""
        expired_keys = [
            key for key, entry in self.cache.items()
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned {len(expired_keys)} expired cache entries")
    
    def _evict_lru(self):
        """Evict least recently used entry"""
        if not self.cache:
            return
        
        # Find LRU entry
        lru_key = min(
            self.cache.keys(),
            key=lambda k: self.cache[k].accessed_at
        )
        
        del self.cache[lru_key]
        logger.debug(f"Evicted LRU cache entry: {lru_key}")
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "total_requests": total_requests,
            "hit_rate": f"{hit_rate:.2f}%"
        }
    
    def memoize(self, ttl: int = 3600):
        """
        Decorator to memoize function results
        
        Usage:
            @cache.memoize(ttl=3600)
            def expensive_function(arg1, arg2):
                return result
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                # Create cache key from function name and args
                key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
                
                # Check cache
                result = self.get(key)
                if result is not None:
                    return result
                
                # Call function and cache result
                result = func(*args, **kwargs)
                self.set(key, result, ttl)
                
                return result
            
            return wrapper
        
        return decorator


# Global cache instances
metadata_cache = SimpleCache(max_size=1000, default_ttl=1800)  # 30 minutes
stats_cache = SimpleCache(max_size=100, default_ttl=300)  # 5 minutes
