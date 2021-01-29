import typing

import discord
from discord.ext import commands
from config.utils.converters import CharacterAndWorldConverter


class LodeStone(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.url = "https://xivapi.com"

    async def get_extended_results(self, character):
        world = character["world"]
        first_name = character["first_name"]
        second_name = character["second_name"]

        lod_id = character.get("lodestone_id")

        if not lod_id:
            results = await self.bot.pyxivapi.character_search(world=world, forename=first_name, surname=second_name)

            if not results["Results"]:
                return None

            lod_id = results["Results"][0]["ID"]

        results = await self.bot.pyxivapi.character_by_id(lodestone_id=lod_id, extended=True)
        return results

    @commands.command()
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

            results = await self.bot.pyxivapi.character_search(world=world, forename=forename, surname=surname)

            if not results["Results"]:
                return await ctx.send("Invalid character nane.")

            character_id = results["Results"][0]["ID"]
            results = await self.bot.pyxivapi.character_by_id(lodestone_id=character_id, extended=True)

            await ctx.db.execute("""
            INSERT INTO lodestone_user (user_id, first_name, second_name, world_name, region, lodestone_id) 
            VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT (user_id) 
            DO UPDATE SET (first_name, second_name, world_name, region, lodestone_id) = ($2,$3,$4,$5,$6)
            """, ctx.author.id, forename, surname, world, data["region"], character_id)

            name = results["Character"]["Name"]
            avatar = results["Character"]["Avatar"]

            embed = discord.Embed(title=f"Character successfully saved",
                                  color=self.bot.embed_colour,
                                  )
            embed.set_author(name=name, icon_url=avatar)
            await ctx.send(embed=embed)

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
            results = await self.get_extended_results(character)

            if not results:
                return await ctx.send("> Couldn't find that character's portrait.")

            await ctx.send(results["Character"]["Portrait"])


def setup(bot):
    bot.add_cog(LodeStone(bot))
