import re
import typing
import asyncio

from datetime import datetime

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

    def validate_filters(self, split, options):

        # ['model', 'ornate_exarchic_top_of_scouting', 'female', 'lalafell.png']
        # ['ornate_exarchic_coat_of_healing_icon.png']

        # the glam command was called if there's options
        if options:
            # we don't want to return an icons in that case
            if "icon" in split[0]:
                return False

            gender = options["g"]
            race = options["r"]
            # has race and gender if the list is this long
            # by default hyur is always passed for race

            # ignore race and gender for none icons aka accessories
            if len(split) == 2:
                return True

            if gender:
                return gender == split[-2].lower() and race in split[-1]

            return race in split[-1]
        # glam command wasn't called so allow it to pass
        return True

    def validate_fecth(self, item, options, results):

        entries = []
        for res in results:
            check = re.match(r"^(Model-.*)png$", res["name"], re.IGNORECASE)
            name = check.group(0).lower() if check else res["name"].lower()

            if item not in name:
                continue

            split = name.split("-")

            if self.validate_filters(split, options):
                entries.append(res)

        return entries

    async def start_menu_gs_source(self, ctx, item, options=None):

        entries = await self.get_image_rows(ctx, item, options)

        if entries == []:
            return await ctx.send(f":no_entry: | search failed for {item}")

        pages = ctx.menu(source=GSImageFindSource(entries), clear_reactions_after=True)
        await pages.start(ctx)

    async def start_menu_find_source(self, ctx, item):
        entries = await self.get_image_names(ctx, item)

        if entries == []:
            return await ctx.send(f":no_entry: | search failed for {item}")

        pages = ctx.menu(source=GamerScapeSource(item, entries), clear_reactions_after=True)
        await pages.start(ctx)

    async def get_image_rows(self, ctx, item, options):
        await ctx.acquire()

        item = item.replace(" ", "_")

        results = await ctx.db.fetch("SELECT * FROM gamerscape_images WHERE LOWER(name) like $1;",
                                     f"%{item.lower()}%")

        if not results:
            return await self.image_search(ctx, item, options)

        entries = self.validate_fecth(item, options, results)
        return entries

    async def get_image_names(self, ctx, item):
        await ctx.acquire()

        item = item.replace(" ", "_")
        results = await ctx.db.fetch("SELECT name FROM gamerscape_images WHERE LOWER(name) like $1;", f"%{item.lower()}%")

        if not results:
            return await self.find_image_names(ctx, item)

        entries = [res["name"] for res in results]
        return entries

    async def image_search(self, ctx, item, options):

        params = {"aisort": "name",
                  "action": "query",
                  "format": "json",
                  "list": "allimages",
                  "aiprefix": item,
                  "ailimit": 50}

        entries = []

        js = await ctx.bot.fetch(self.url, params=params)

        for js in js["query"]["allimages"]:

            check = re.match(r"^(Model-.*)png$", js["name"], re.IGNORECASE)
            name = check.group(0).lower() if check else js["name"].lower()

            if item not in name:
                continue

            split = name.split("-")

            if self.validate_filters(split, options):
                print(f"adding {name}....")
                # if it wasn't found in get_image_rows function it probably doesn't exist in the database
                await ctx.db.execute(
                    """INSERT INTO gamerscape_images 
                       (title, name, url, description_url, description_short_url, timestamp) 
                       VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT DO NOTHING""",
                    js["title"], js["name"], js["url"],
                    js["descriptionurl"], js["descriptionshorturl"],
                    datetime.strptime(js["timestamp"], "%Y-%m-%dT%H:%M:%SZ"))

                entries.append(js)

        return entries

    async def find_image_names(self, ctx, item):

        params = {

            "aisort": "name",

            "action": "query",

            "format": "json",

            "aiprop": "size",

            "list": "allimages",

            "aimime": "image/png",

            "aifrom": item,

            "ailimit": 60

        }

        results = await self.bot.fetch(self.url, params=params)

        entries = [result["name"] for result in results["query"]["allimages"]
                   if item.lower() in result["name"].lower()]

        return entries

    @commands.is_owner()
    @commands.command()
    async def add_images(self, ctx, delay=5):
        """add recently added or every image file's to the database on gamerscape"""
        # note this will take some time

        await ctx.acquire()
        # getting the most recent date if the table is already populated to attempt to get files added after that date
        timestamp_check = await ctx.db.fetchrow("SELECT MAX(timestamp) from gamerscape_images")
        aicontinue = True

        params = {

                "aisort": "name",

                "action": "query",

                "format": "json",

                "list": "allimages",

                "aimime": "image/png",

                # 500 is max for anonymous
                "ailimit": 500

            }
        if timestamp_check:

            params = {

                "aisort": "timestamp",

                "action": "query",

                "format": "json",

                "list": "allimages",

                "aimime": "image/png",
                # get recently added images
                "aidir": "older",

                # 500 is max for anonymous
                "ailimit": 500

            }

        while aicontinue:
            results = await self.bot.fetch(self.url, params=params)

            try:
                await asyncio.sleep(delay)

                for js in results["query"]["allimages"]:

                    if timestamp_check:
                        if js["timestamp"] < timestamp_check["timestamp"]:
                            return await ctx.send("> No more recent images available")

                    print(f"adding {js['name']}....")
                    await ctx.db.execute(
                        """INSERT INTO gamerscape_images 
                           (title, name, url, description_url, description_short_url) 
                           VALUES ($1, $2, $3, $4, $5, $6) 
                           ON CONFLICT DO UPDATE SET 
                           description_url = $4, url = $3, timestamp = $6""",
                        js["title"], js["name"], js["url"],
                        js["descriptionurl"], js["descriptionshorturl"],
                        datetime.strptime(js["timestamp"], "%Y-%m-%dT%H:%M:%SZ"))

                aicontinue = results["continue"]["aicontinue"]
                params["aicontinue"] = aicontinue
            except KeyError:
                # no more results available
                aicontinue = ""
        print("Finished.")
        await ctx.send(f"> Finished adding images {ctx.author.mention}")

    @commands.group(invoke_without_command=True, aliases=["gis"])
    async def gamerscape_image_search(self, ctx, *, item):
        """search for an image on gamerscape by filename
           file names are case sensitive
           -------------------------------------------------------------
           tataru gis image_name
        """
        item = item.lower()
        await self.start_menu_gs_source(ctx, item)

    @flags.add_flag("glam", nargs="+")
    @flags.add_flag("--r", default="hyur")
    @flags.add_flag("--g", default="")
    @gamerscape_image_search.group(cls=flags.FlagCommand)
    async def glam(self, ctx, **options):
        """retrieves images for glamour on gamerscape by filename
           with optional parameters for race and gender in flag notation
           file names are case sensitive
           note you'll have to set the gender for gender specific glamours
           and vice versa for race, valid races are as found in the base game
           and valid genders are only male/female
           -------------------------------------------------------------
           tataru gis glam name
           tataru gis glam name --r lalafell
           tataru gis glam name" -r lalafell --g female
        """

        item = " ".join(options["glam"]).lower().replace("model","").replace("model-", "")
        del options["glam"]

        await self.start_menu_gs_source(ctx, item, options)

    @commands.command(aliases=["gif"])
    async def gamerscape_image_find(self, ctx, *, item):
        """retrieves image names on gamerscape by filename
           file names are case sensitive
           -------------------------------------------------------------
           tataru gif image_name
        """
        await self.start_menu_find_source(ctx, item)

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
