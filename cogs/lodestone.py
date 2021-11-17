import re
import typing

import discord
from discord.ext import commands
from bs4 import BeautifulSoup
from pyxivapi import exceptions

from config.utils.converters import CharacterAndWorldConverter
from config.utils.cache import cache, Strategy
from config.utils.requests import RequestFailed


class LodeStone(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.url = "https://xivapi.com"

    async def add_character(self, ctx, avatar_url, data: typing.Tuple):

        await ctx.db.execute("""
            INSERT INTO lodestone_user (user_id, first_name, second_name, world_name, region, lodestone_id) 
            VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT (user_id) 
            DO UPDATE SET (first_name, second_name, world_name, region, lodestone_id) = ($2,$3,$4,$5,$6)
            """, *data)

        name = f"{data[1]} {data[2]}"

        embed = discord.Embed(title=f"Character successfully saved",
                              color=self.bot.embed_colour,
                              )
        embed.set_author(name=name, icon_url=avatar_url)
        await ctx.send(embed=embed)

    @cache(maxsize=60, strategy=Strategy.timed)
    async def get_extended_results(self, character):
        url = None
        world = character["world"]
        first_name = character["first_name"]
        second_name = character["second_name"]

        lod_id = character.get("lodestone_id")

        try:

            if not lod_id:
                results = await self.bot.pyxivapi.character_search(world=world,
                                                                   forename=first_name,
                                                                   surname=second_name)

                if not results["Results"]:
                    return None

                lod_id = results["Results"][0]["ID"]

            results = await self.bot.pyxivapi.character_by_id(lodestone_id=lod_id, extended=True)
            url = results["Character"]["Portrait"]

        except exceptions.XIVAPIError:
            # fallback to scraping if XIVAPI is having issues
            if lod_id:
                response = await self.bot.fetch(f"https://eu.finalfantasyxiv.com/lodestone/character/{lod_id}")
                soup = BeautifulSoup(response, "html.parser")
                url = soup.find("div", class_="character__detail__image").find("img")["src"]

        return url

    @commands.group(invoke_without_command=True)
    async def iam(self, ctx, world, forename, surname):
        """Save a character
           which allows you to use other commands without providing character parameters
           -------------------------------------------------------------
           tataru iam World Forename Surname
        """

        await ctx.trigger_typing()

        async with ctx.acquire():
            data = await ctx.db.fetchrow("SELECT * from world where LOWER(name) like $1", world.lower())

            if not data:
                return await ctx.send("Invalid world was passed.")

            world = data["name"]

            results = await self.bot.pyxivapi.character_search(world=world, forename=forename, surname=surname)

            if not results["Results"]:
                return await ctx.send("No results were found for that character name.")

            character_id = results["Results"][0]["ID"]
            results = await self.bot.pyxivapi.character_by_id(lodestone_id=character_id, extended=True)
            await self.add_character(ctx, results["Character"]["Avatar"],
                                     (ctx.author.id, forename, surname, data["name"], data["region"], character_id))

    @iam.error
    async def iam_error(self, ctx, error):

        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        if isinstance(error, exceptions.XIVAPIError):
            return await ctx.send(f"XIVAPI seems to be running issues for this command, try using "
                                  f"`{ctx.prefix}iam url` with your character's lodestone url or running the command "
                                  f"later.")

    @iam.command()
    async def url(self, ctx, lodestone_url):
        """Save a character through a lodestone url
           -------------------------------------------------------------
           tataru iam url https://eu.finalfantasyxiv.com/lodestone/character/27652538
           """
        match = re.match(r"http[s]?://(jp|eu|fr|na|de)\.finalfantasyxiv\.com/lodestone/character/([0-9]+)/?",
                         lodestone_url, re.IGNORECASE)

        if not match:
            return await ctx.send(":no_entry: | an invalid lodestone url was passed.", delete_after=10)

        lodestone_id = int(match.group(2))

        try:
            response = await self.bot.fetch(lodestone_url)
        except RequestFailed as e:
            return await ctx.send(f":no_entry: | {e}")

        soup = BeautifulSoup(response, "html.parser")

        forename, surname = soup.find("p", class_="frame__chara__name").text.split(" ")
        world = soup.find("p", class_="frame__chara__world").text.split(" ")[0]

        region = await ctx.db.fetchval("SELECT region FROM world WHERE name like $1", world)
        avatar = soup.find("div", class_="frame__chara__face").find("img")["src"]

        await self.add_character(ctx, avatar, (ctx.author.id, forename, surname, world, region, lodestone_id))

    @commands.command(aliases=["por"])
    async def portrait(self, ctx, *, character: typing.Union[discord.User, str] = None):
        """returns a character's lodestone portrait
           If you don't provide a Discord user or character parameters, your own saved character will be used.
           -------------------------------------------------------------
           tataru portrait World Forename Surname
           tataru portrait @User or user_id or name
        """

        character = await CharacterAndWorldConverter().convert(ctx, character)

        async with ctx.typing():
            url = await self.get_extended_results(character)

            if not url:
                self.get_extended_results.invalidate(character)
                return await ctx.send("> Couldn't find that character's portrait.")

            await ctx.send(url)


def setup(bot):
    bot.add_cog(LodeStone(bot))
