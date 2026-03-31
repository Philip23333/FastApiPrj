import redis.asyncio as redis

REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
# 创建连接对象 参数: host:连接地址, port:连接端口, db:数据库索引, decode_responses:是否自动解码字符串
redis_client = redis.Redis(
    host=REDIS_HOST, 
    port=REDIS_PORT, 
    db=REDIS_DB,
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=0.2,  # 设置连接超时时间，单位为秒
    )




