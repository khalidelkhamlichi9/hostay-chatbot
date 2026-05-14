import json
import logging
from typing import Any, Optional

import redis.asyncio as redis

from config import get_settings

logger = logging.getLogger(__name__)


class Cache:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None

    async def connect(self):
        if self.redis is None:
            try:
                s = get_settings()
                self.redis = redis.Redis(
                    host=s.redis_host,
                    port=s.redis_port,
                    db=s.redis_db,
                    password=s.redis_password,
                    decode_responses=True,
                    socket_connect_timeout=5.0,
                    socket_keepalive=True,
                    health_check_interval=30,
                    ssl=s.redis_ssl,
                )
                await self.redis.ping()
                logger.info("Connected to Redis (ssl=%s)", s.redis_ssl)
            except Exception as e:
                logger.error("Failed to connect to Redis: %s", e)
                self.redis = None

    async def close(self):
        if self.redis is None:
            return
        try:
            close = getattr(self.redis, "aclose", None)
            if close:
                await close()
            else:
                await self.redis.close()
        except Exception as e:
            logger.warning("Redis close: %s", e)
        finally:
            self.redis = None

    async def get(self, key: str) -> Optional[Any]:
        if not self.redis:
            return None
        try:
            data = await self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error("Redis get error: %s", e)
            return None

    async def set(self, key: str, value: Any, expire: int = 3600):
        if not self.redis:
            return
        try:
            await self.redis.set(key, json.dumps(value), ex=expire)
        except Exception as e:
            logger.error("Redis set error: %s", e)

    async def clear(self):
        if not self.redis:
            return
        try:
            await self.redis.flushdb()
            logger.info("Redis cache cleared")
        except Exception as e:
            logger.error("Redis clear error: %s", e)


cache = Cache()
