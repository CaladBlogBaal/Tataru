"""
This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
If a copy of the MPL was not distributed with this file,
You can obtain one at https://mozilla.org/MPL/2.0/.
"""
# code is taken from
# https://github.com/Rapptz/RoboDanny/blob/ac3a0ed64381050c37761d358d4af90b89ec1ca3/cogs/utils/context.py
from discord.ext import commands, menus


class _ContextDBAcquire:

    __slots__ = ('ctx', 'timeout')

    def __init__(self, ctx, timeout):
        self.ctx = ctx
        self.timeout = timeout

    def __await__(self):
        return self.ctx._acquire(self.timeout).__await__()

    async def __aenter__(self):
        await self.ctx._acquire(self.timeout)

        return self.ctx.pool

    async def __aexit__(self, *args):
        await self.ctx.release()


class Context(commands.Context):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pool = self.bot.pool
        self._db = None
        self.menu = menus.MenuPages

    @property
    def db(self):

        return self._db if self._db else self.pool

    async def _acquire(self, timeout):

        if self._db is None:
            self._db = await self.pool.acquire(timeout=timeout)

        return self._db

    def acquire(self, *, timeout=None):

        """Acquires a database connection from the pool. e.g. ::



            async with ctx.acquire():

                await ctx.db.execute(...)



        or: ::



            await ctx.acquire()

            try:

                await ctx.db.execute(...)

            finally:

                await ctx.release()

        """

        return _ContextDBAcquire(self, timeout)

    async def release(self):

        """Releases the database connection from the pool.



        Useful if needed for "long" interactive commands where

        we want to release the connection and re-acquire later.



        Otherwise, this is called automatically by the bot.

        """

        # from source digging asyncpg source, releasing an already

        # released connection does nothing

        if self._db is not None:
            await self.bot.pool.release(self._db)

            self._db = None


