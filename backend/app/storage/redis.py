import logging
import redis
class RedisConnection:
    def __init__(self,url): self.client=redis.Redis.from_url(url,decode_responses=True,socket_timeout=1,socket_connect_timeout=1) if url else None
    def close(self):
        if self.client: self.client.close()
