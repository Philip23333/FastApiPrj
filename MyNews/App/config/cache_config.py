import os

import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "").strip()
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_CONNECT_TIMEOUT = float(os.getenv("REDIS_CONNECT_TIMEOUT", "1"))
REDIS_SOCKET_TIMEOUT = float(os.getenv("REDIS_SOCKET_TIMEOUT", "0.2"))

def create_redis_client(force_noauth: bool = False):
    # 创建连接对象 参数: host:连接地址, port:连接端口, db:数据库索引, decode_responses:是否自动解码字符串
    if REDIS_URL:
        if force_noauth:
            fallback_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
            return redis.from_url(
                fallback_url,
                decode_responses=True,
                socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
                socket_timeout=REDIS_SOCKET_TIMEOUT,
            )
        return redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
        )

    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=None if force_noauth else (REDIS_PASSWORD or None),
        decode_responses=True,
        socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
        socket_timeout=REDIS_SOCKET_TIMEOUT,  # 设置连接超时时间，单位为秒
    )


redis_client = create_redis_client()




