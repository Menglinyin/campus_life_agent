import json, logging
from redis.exceptions import RedisError
class SessionStore:
    def __init__(self, redis, conversations, ttl): self.redis=redis.client; self.repo=conversations; self.ttl=ttl
    def get(self,user,sid):
        # SQL checks ownership/version even on cache hits; SQL remains canonical.
        snapshot=self.repo.snapshot(user,sid)
        if self.redis:
            try:
                key=f"campus:session:{user}:{sid}"
                raw=self.redis.get(key)
                cached=json.loads(raw) if raw else None
                if cached and cached.get("version")==snapshot["version"]: return cached
                self.redis.setex(key,self.ttl,json.dumps(snapshot,ensure_ascii=False))
            except (RedisError,ValueError,TypeError): logging.getLogger(__name__).warning("Session cache unavailable")
        return snapshot
    def invalidate(self,user,sid):
        if self.redis:
            try: self.redis.delete(f"campus:session:{user}:{sid}")
            except RedisError: logging.getLogger(__name__).warning("Cache invalidation unavailable")
