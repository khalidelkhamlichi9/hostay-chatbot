import os
import json
import redis.asyncio as redis
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

class Cache:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None

    async def connect(self):
        if self.redis is None:
            try:
                self.redis = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    db=REDIS_DB,
                    password=REDIS_PASSWORD,
                    decode_responses=True
                )
                await self.redis.ping()
                logger.info("✅ Connected to Redis")
            except Exception as e:
                logger.error(f"❌ Failed to connect to Redis: {e}")
                self.redis = None

    async def get(self, key: str) -> Optional[Any]:
        if not self.redis:
            return None
        try:
            data = await self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    async def set(self, key: str, value: Any, expire: int = 3600):
        if not self.redis:
            return
        try:
            await self.redis.set(key, json.dumps(value), ex=expire)
        except Exception as e:
            logger.error(f"Redis set error: {e}")

    async def clear(self):
        if not self.redis:
            return
        try:
            await self.redis.flushdb()
            logger.info("🧹 Redis cache cleared")
        except Exception as e:
            logger.error(f"Redis clear error: {e}")

# Global cache instance
cache = Cache()
