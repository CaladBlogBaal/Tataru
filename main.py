import aiohttp

import asyncpg

import pyxivapi

import sys

import platform

import psutil

import humanize as h

import discord

from discord.ext import commands

from config.cogs import __cogs__
from config.utils import requests
from config.utils.context import Context
from config import config


class Tataru(commands.Bot):
    def __init__(self, *args, **kwargs):
        self.embed_colour = 0x00dcff
        super().__init__(*args, **kwargs)
        self.loop.run_until_complete(self.__ainit__(self, *args, **kwargs))

    async def __ainit__(self, *args, **kwargs):
        self.session = aiohttp.ClientSession()
        self.request = requests.Request(self, self.session)
        db = await asyncpg.create_pool(config.__credentials__)
        self.pool = db
        self.pyxivapi = pyxivapi.XIVAPIClient(api_key=config.__xivapikey__)

        with open("schema.sql") as f:
            await self.pool.execute(f.read())

    async def fetch(self, url, **kwargs):
        return await self.request.fetch(url, **kwargs)

    async def post(self, url, data, **kwargs):
        return await self.request.post(url, data, **kwargs)

    async def get_context(self, message, *, cls=None):
        return await super().get_context(message, cls=Context)

    async def update_users(self, user=None, guild=None):
        async with self.pool.acquire() as con:
            statement = "INSERT INTO users (user_id, name) VALUES ($1,$2) ON CONFLICT DO NOTHING;"

            if guild:
                data = ((m.id, m.name) for m in guild.members if not m.bot)
                await con.executemany(statement, data)
            else:
                await con.execute(statement, user.id, user.name)


intents = discord.Intents.default()  # All but the privileged ones
# need this for discord.User to work as intended
intents.members = True

bot = Tataru(command_prefix=commands.when_mentioned_or(*config.__prefixes__), case_insensitive=True, intents=intents)


@bot.after_invoke
async def after_invoke(ctx):
    await ctx.release()


@bot.event
async def on_guild_join(guild):
    await bot.update_users(guild=guild)


@bot.event
async def on_member_join(member):
    if member.bot:
        return
    await bot.update_users(user=member)


@bot.event
async def on_ready():
    print(f"Successfully logged in and booted...!")
    print(f"\nLogged in as: {bot.user.name} - {bot.user.id}\nDiscord.py version: {discord.__version__}\n")
    for guild in bot.guilds:
        await bot.update_users(guild=guild)


if __name__ == "__main__":

    for cog in __cogs__:

        try:

            bot.load_extension(cog)

        except Exception as e:
            print(f"{cog} could not be loaded.")
            raise e


@bot.command()
async def source(ctx):
    await ctx.send("https://github.com/CaladBlogBaal/Tataru")


@bot.command()
async def say(ctx, *, mesasage):
    """
    Echo a message
    -------------------------------------------------------------
    tataru say message
    """
    await ctx.send(mesasage)


@bot.command()
async def ping(ctx):
    """
    Check how long the bot takes to
    -------------------------------------------------------------
    tataru ping
    """

    await ctx.send(f":information_source: | :ping_pong: **{ctx.bot.latency * 1000:.0f}**ms")


@bot.command()
async def prefix(ctx):
    """
    returns the bot current prefixes
    -------------------------------------------------------------
    tataru prefix
    """
    prefixes = ", ".join(config.__prefixes__)
    await ctx.send(f"The prefixes for this bot is {prefixes}")


@bot.command()
async def about(ctx):
    """Get info about the bot."""

    invite_url = f"[invite url]({discord.utils.oauth_url(ctx.me.id, discord.Permissions(18496))})"
    proc = psutil.Process()
    mem = proc.memory_full_info()
    command_count = len({command for command in ctx.bot.walk_commands() if "jishaku" not in
                         command.name and "jishaku" not in command.qualified_name})
    py_version = ".".join(str(n) for n in sys.version_info[:3])
    embed = discord.Embed(color=bot.embed_colour, title="", description=f"")
    embed.add_field(name="Basic:", value=f"**OS**: {platform.platform()}\n**Hostname: **OVH\n**Python Version: **"
                                         f"{py_version}\n**Links**: {invite_url}")
    embed.add_field(name="Dev:", value="CaladWoDestroyer#9313")
    embed.add_field(name="Library:", value=f"Discord.py {discord.__version__}")
    embed.add_field(name="Commands:", value=str(command_count))
    embed.add_field(name="RAM:", value=f"Using {h.naturalsize(mem.rss)}")
    embed.add_field(name="VRAM:", value=str(h.naturalsize(mem.vms) + f" of which {str(h.naturalsize(mem.uss))}"
                                                                     f"\nis unique to this process"))
    embed.add_field(name="Web socket ping", value=round(ctx.bot.latency * 1000, 2))
    await ctx.send(embed=embed)


if __name__ == "__main__":
    bot.load_extension("jishaku")
    bot.run(config.__bot_token__, bot=True, reconnect=True)
