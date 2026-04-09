import json
import logging

from config.cache_config import create_redis_client, redis_client


logger = logging.getLogger(__name__)


class AIMemoryService:
    def __init__(self):
        self.history_ttl_seconds = 1800
        self.memory_ttl_seconds = 3600
        self._redis = redis_client
        self._noauth_fallback_enabled = False

    @staticmethod
    def _is_noauth_error(exc: Exception) -> bool:
        message = str(exc or "").lower()
        return "auth <password> called without any password configured" in message

    def _switch_to_noauth_client(self):
        if self._noauth_fallback_enabled:
            return
        self._redis = create_redis_client(force_noauth=True)
        self._noauth_fallback_enabled = True
        logger.warning("redis auth mismatch detected, fallback to no-auth redis client")

    async def _retry_on_auth_error(self, op):
        try:
            return await op(self._redis)
        except Exception as exc:
            if not self._is_noauth_error(exc):
                raise
            self._switch_to_noauth_client()
            return await op(self._redis)

    @staticmethod
    def _history_key(user_id: int) -> str:
        return f"ai:qa:history:u:{user_id}:v1"

    @staticmethod
    def _memory_key(user_id: int) -> str:
        return f"ai:qa:memory:u:{user_id}:v1"

    async def get_cached_history(self, user_id: int) -> list[dict] | None:
        key = self._history_key(user_id)
        try:
            value = await self._retry_on_auth_error(lambda client: client.get(key))
            if not value:
                return None
            data = json.loads(value)
            return data if isinstance(data, list) else None
        except Exception as exc:
            logger.warning("redis read history cache failed, key=%s, error=%s", key, exc)
            return None

    async def set_cached_history(self, user_id: int, history_items: list[dict]):
        key = self._history_key(user_id)
        try:
            await self._retry_on_auth_error(
                lambda client: client.setex(key, self.history_ttl_seconds, json.dumps(history_items, ensure_ascii=False))
            )
        except Exception as exc:
            logger.warning("redis write history cache failed, key=%s, error=%s", key, exc)

    async def get_cached_memory(self, user_id: int) -> str | None:
        key = self._memory_key(user_id)
        try:
            return await self._retry_on_auth_error(lambda client: client.get(key))
        except Exception as exc:
            logger.warning("redis read memory cache failed, key=%s, error=%s", key, exc)
            return None

    async def set_cached_memory(self, user_id: int, memory_text: str):
        key = self._memory_key(user_id)
        try:
            await self._retry_on_auth_error(lambda client: client.setex(key, self.memory_ttl_seconds, memory_text))
        except Exception as exc:
            logger.warning("redis write memory cache failed, key=%s, error=%s", key, exc)

    async def invalidate_user_cache(self, user_id: int):
        keys = [self._history_key(user_id), self._memory_key(user_id)]
        try:
            await self._retry_on_auth_error(lambda client: client.delete(*keys))
        except Exception as exc:
            logger.warning("redis invalidate user cache failed, user_id=%s, error=%s", user_id, exc)


ai_memory_service = AIMemoryService()