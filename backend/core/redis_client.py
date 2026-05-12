import redis.asyncio as redis

from .config import settings


class RedisClient:
    def __init__(self):
        self.client = redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def get(self, key: str):
        return await self.client.get(key)

    async def hget(self, name: str, key: str):
        return await self.client.hget(name, key)

    async def hset(self, name: str, key: str, value: str):
        await self.client.hset(name, key, value)

    async def close(self):
        await self.client.close()


redis_client = RedisClient()


async def get_redis():
    return redis_client
