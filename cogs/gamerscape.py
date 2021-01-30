import re
import typing

import discord
from discord.ext import commands, flags

from cog_menus.pages_sources import GamerScapeSource, GSImageFindSource, GSSearch


class GamerScape(commands.Cog):
    """
    Gamer Scape related commands
    """

    def __init__(self, bot):
        self.url = "https://ffxiv.gamerescape.com/w/api.php"
        self.bot = bot

    async def image_search(self, ctx, item, options):

        item = item.replace(" ", "_")
        regex = rf"^{item}.*?{options.get('g')}-?{options.get('r')}"
        params = {"aisort": "name",
                  "action": "query",
                  "format": "json",
                  "list": "allimages",
                  "aiprefix": item,
                  "ailimit": 50}

        entries = []

        js = await ctx.bot.fetch(self.url, params=params)

        for js in js["query"]["allimages"]:

            if re.match(regex, js["name"], re.IGNORECASE) or options["glam"] is False:
                entries.append(js)

        if entries == []:
            return await ctx.send(f":no_entry: | search failed for {item}")

        pages = ctx.menu(source=GSImageFindSource(entries), clear_reactions_after=True)
        await pages.start(ctx)

    async def find_image_names(self, ctx, model):

        params = {

            "aisort": "name",

            "action": "query",

            "format": "json",

            "aiprop": "size",

            "list": "allimages",

            "aimime": "image/png",

            "aifrom": model,

            "ailimit": 60

        }

        results = await self.bot.fetch(self.url, params=params)

        entries = [result["name"] for result in results["query"]["allimages"]
                   if model.lower() in result["name"].lower()]

        if not entries:
            return await ctx.send(f":no_entry: | no images for {model} were found.")

        pages = ctx.menu(source=GamerScapeSource(model, entries), clear_reactions_after=True)
        await pages.start(ctx)

    @commands.group(invoke_without_command=True, aliases=["gis"])
    async def gamerscape_image_search(self, ctx, *, item):
        """search for an image on gamerscape by filename
           file names are case sensitive
           -------------------------------------------------------------
           tataru gis image_name
        """
        options = {"glam": False}
        await self.image_search(ctx, item, options)

    @flags.add_flag("glam", nargs="+")
    @flags.add_flag("--r", default="hyur")
    @flags.add_flag("--g", default="")
    @gamerscape_image_search.group(cls=flags.FlagCommand)
    async def glam(self, ctx, **options):
        """retrieves images for glamour on gamerscape by filename
           with optional parameters for race and gender in flag notation
           file names are case sensitive
           note you'll have to set the gender for gender specific glamours
           and vice versa for race
           -------------------------------------------------------------
           tataru gis glam name
           tataru gis glam name --r lalafell
           tataru gis glam name" -r lalafell --g female
        """

        item = " ".join(options["glam"])

        if not item.lower().startswith("model") and not item.lower().startswith("model-"):
            item = "Model-" + item

        await self.image_search(ctx, item, options)

    @commands.command(aliases=["gif"])
    async def gamerscape_image_find(self, ctx, *, item):
        """retrieves image names on gamerscape by filename
           file names are case sensitive
           -------------------------------------------------------------
           tataru gif image_name
        """
        await self.find_image_names(ctx, item)

    @commands.command(aliases=["gs"])
    async def gamerscape_search(self, ctx, amount: typing.Optional[int] = 10, *, query):
        """retrieves pages on gamerscape based on the query
           -------------------------------------------------------------
           tataru gs query
        """

        if amount < 1 or amount > 500:
            amount = 1

        count = 1
        params = {"search": query,
                  "action": "opensearch",
                  "limit": amount,
                  "profile": "engine_autoselect"}

        entries = []

        results = await self.bot.fetch(self.url, params=params)

        for result in results:

            for url in result:

                if re.findall('https?://(?:[-\\w.]|(?:%[\\da-fA-F]{2}))+', url):
                    embed = discord.Embed(title=f"Search results for {query}", color=self.bot.embed_colour)
                    embed.add_field(name=f"Search result: {count}", value=url, inline=False)
                    count += 1
                    entries.append(embed)

        if entries == []:
            await ctx.send(f":no_entry: | search failed for {query}")

        pages = ctx.menu(source=GSSearch(entries), clear_reactions_after=True)
        await pages.start(ctx)


def setup(bot):
    bot.add_cog(GamerScape(bot))
