import asyncio

import discord
from discord.ext import menus

# base menu that'll have custom emojis later


class BaseMenu(menus.MenuPages):
    def __init__(self, source, **kwargs):
        # to not allow spamming of certain buttons
        self.lock = asyncio.Lock()
        super(BaseMenu, self).__init__(source, **kwargs)


class ReplyMenu(BaseMenu):
    async def send_initial_message(self, ctx, channel):
        page = await self._source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        return await ctx.reply(**kwargs)


class MenuRemoveReactions(BaseMenu):
    async def update(self, payload):
        if self._can_remove_reactions:
            if payload.event_type == 'REACTION_ADD':
                await self.bot.http.remove_reaction(
                    payload.channel_id, payload.message_id,
                    discord.Message._emoji_reaction(payload.emoji), payload.member.id
                )
        await super().update(payload)
