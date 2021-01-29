import enum
import asyncio

from functools import wraps
from datetime import datetime, timedelta
from lru import LRU


class Strategy(enum.Enum):

    lru = 1

    timed = 2


def _wrap_coroutine_in_dict(cache_dict, key, future):

    async def wrapper():

        val = await future
        cache_dict[key] = val

        return val

    return wrapper()


def _wrap_value_in_coroutine(val):

    async def wrapper():

        return val

    return wrapper()


class ExpirngCache(dict):
    def __init__(self, minutes):
        self._ttl = timedelta(minutes=minutes)
        self._ttl_dict = {}
        super().__init__()

    def __verify_cache(self):

        d = (k for k in self if datetime.utcnow() >= self._ttl_dict.get(k))

        for k in d:
            del self._ttl_dict[k]
            del self[k]

    def setitem_ttl_dict(self, key, ttl):
        self._ttl_dict[key] = ttl

    def __contains__(self, item):
        self.__verify_cache()
        return super().__contains__(item)

    def __setitem__(self, key, value):

        if key not in self._ttl_dict:
            ttl = datetime.utcnow() + self._ttl
            self.setitem_ttl_dict(key, ttl)

        super().__setitem__(key, value)


def cache(maxsize=256, strategy=Strategy.lru):
    def memoize(f):
        if strategy is Strategy.lru:
            __cache = LRU(maxsize)
            __stats = __cache.items

        elif strategy is Strategy.timed:
            __cache = ExpirngCache(maxsize)
            __stats = __cache.items

        def make_key(*args, **kwargs):
            key = f"{f.__module__}#{f.__name__}#{repr((args, kwargs))}"
            return key

        @wraps(f)
        def wrapper(*args, **kwargs):

            key = make_key(*args, **kwargs)

            try:

                val = __cache[key]

            except KeyError:

                val = f(*args, **kwargs)

                if asyncio.iscoroutine(val):

                    return _wrap_coroutine_in_dict(__cache, key, val)

                __cache[key] = val

                return val

            else:

                if asyncio.iscoroutinefunction(f):

                    return _wrap_value_in_coroutine(val)

                return val

        def __invalidate(*args, **kwargs):
            key = make_key(*args, **kwargs)

            try:
                del __cache[key]

            except KeyError:
                pass

        def __clear():
            __cache.clear()

        wrapper.get_stats = __stats
        wrapper.invalidate = __invalidate
        wrapper.clear = __clear
        return wrapper

    return memoize
