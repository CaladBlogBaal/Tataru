# pylint: disable-msg=R0904
import os
import fnmatch
import glob
import re
import typing
import asyncio
import random

from urllib import parse
from datetime import datetime

import discord
from discord.ext import commands, flags

# from bs4 import BeautifulSoup
# for dungeons later

from cog_menus.pages_sources import GamerScapeSource, GSImageFindSource, GSSearch
from config.utils.converters import RaceAliasesConverter, GenderAliasesConverter
from config.utils.requests import RequestFailed
from config.utils.cache import cache
from config import config


class GamerScape(commands.Cog):
    """
    Gamer Scape related commands
    """

    def __init__(self, bot):
        self.url = "https://ffxiv.gamerescape.com/w/api.php"
        self.bot = bot
        self.image_root = config.IMAGE_ROOT
        self.domain_name = config.DOMAIN_NAME
        # image directory names
        self.CATEGORIES = ["weapons", "body", "head", "feet",
                           "shield", "hands", "legs", "armor",
                           "bracelets", "earrings", "armour",
                           "necklace", "rings", "accessories", "all"]

    def build_paths(self, category, race, gender):
        paths = []

        if category == "all":
            # traverse all directories if all is passed
            # Due to the way I structured my directories weapons and accessories,
            # have a different path so need to append them manually
            paths.append(f"{self.image_root}/*/*/{race}/{gender}")
            paths.append(f"{self.image_root}/weapons")
            paths.append(f"{self.image_root}/accessories")

        elif category in ("weapons", "accessories", "armour"):
            paths.append(f"{self.image_root}/{category}")

        else:
            paths.append(f"{self.image_root}/*/{category}/{race}/{gender}")

        return paths

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

            # ignore race and gender for none icons aka accessories and weapons
            if len(split) == 2 or len(split) == 1:
                return True

            if gender:
                return gender == split[-2].lower() and race in split[-1]

            return race in split[-1]
        # glam command wasn't called so allow it to pass
        return True

    def validate_fetch(self, item, options, results):

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

    @cache()
    def walk_path(self, path):
        # using glob to return paths that meet the pattern
        paths = glob.glob(path)
        if not paths:
            return []
        result = []
        for p in paths:
            # yields a tuple of dirpath, dirnames and filenames
            result.extend(os.walk(p))

        return result

    def get_files(self, pattern, path):
        for dirpath, _, filenames in self.walk_path(path):
            for f in filenames:
                if fnmatch.fnmatch(f, pattern):
                    yield os.path.join(dirpath, f), f

    def clean_files(self, files):

        for i, file in enumerate(files):
            url, name = file
            title = re.sub(r"(.png|.jpeg)", "", name)
            title = title.replace("_", " ")
            # serving these images through apache so need to get rid of the /var/www/
            url = url.replace('/var/www/', '')
            url = self.domain_name + url
            queryurl = "https://eu.finalfantasyxiv.com/lodestone/playguide/db/search?" \
                       + parse.urlencode({"q": title}, quote_via=parse.quote)

            files[i] = {"descriptionurl": queryurl, "url": url, "name": name, "title": title}

    async def download_gear_from_js(self, js):
        url = js["url"]
        filename = re.match(r"https:\/\/ffxiv\.gamerescape\.com\/w\/images.*Model-(.*)\.png", url)
        # not a piece of gear so ignore it
        if not filename:
            return

        filename = filename.group(1)
        filename = parse.unquote(filename)

        category = None
        result = await self.bot.pyxivapi.index_search(indexes=["item"],
                                                      name=filename.replace("_", " ").replace("-", ""),
                                                      columns=["ItemUICategory.Name"], language="en")
        if result["Results"]:
            category = result[0]['ItemUICategory']["Name"].lower()

        if not category:
            # not a piece of gear so ignore it
            return

        if "arms" in category or "tools" in category:
            # image_root/weapons/filename
            path = "{}/weapons/{}.png".format(self.image_root, filename)

        elif category == "shield":
            # image_root/shield/filename
            path = "{}/shield/{}.png".format(self.image_root, filename)

        elif any(category == x for x in ("bracelets", "necklace", "rings", "earrings")):
            # image_root/accessories/name/filename
            path = "{}/accessories/{}/{}.png".format(self.image_root, category, filename)
        else:
            gender = "male"
            url = js["url"].lower()

            if "female" in url:
                gender = "female"

            regex = re.compile("(hrothgar|lalafell|miqote|aura|viera|hyur|roe|elezen|roegadyn)")
            race = regex.search(url)

            if not race or not gender:
                return print(f"this url needs to be checked and manually added: {url}")

            race = race.group(1).lower()
            # gamer scape sometimes shortens roegadyn to roe
            if race == "roe":
                race = "roegadyn"
            filename = filename.replace(race, "").replace("-", "")
            # image_root/armour/category/gender/race/filename
            path = "{}/armour/{}/{}/{}/{}.png".format(self.image_root, category, gender, race, filename)

        try:
            print(f"downloading ... {url}")
            image_bytes = await self.bot.fetch(url)
            with open(path, "wb") as f:
                f.write(image_bytes)

        except RequestFailed:
            pass

    async def get_glam(self, ctx, item, options):
        # my files have spaces replaced with _
        fn = item.replace(" ", "_")
        # * stands for a wildcard, any characters
        gender = await GenderAliasesConverter().convert(ctx, options["g"]) or "*"
        race = await RaceAliasesConverter().convert(ctx, options["r"]) or "*"
        category = options["c"].lower()
        # using armor spelling can't relate
        category = category.replace("armor", "armour")
        if category not in self.CATEGORIES:
            prefix = ctx.prefix
            raise commands.BadArgument(f"invalid category was passed call ```{prefix}help gis cat``` "
                                       f"for valid categories.")
        # build the paths for the images based on options
        paths = self.build_paths(category, race, gender)

        files = []

        for p in paths:
            files.extend(list(self.get_files(f"{fn}*", p)))

        # if no files are found it may have not been locally added so fall back and search on gamerscape
        if not files:
            return await self.get_image_rows(ctx, item, options)

        # converting the list of tuples to dicts to pass to the menu source
        self.clean_files(files)
        return files

    async def start_menu_gs_source(self, ctx, item, options=None):

        if options:
            entries = await self.get_glam(ctx, item, options)
        else:
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

        entries = self.validate_fetch(item, options, results)
        return entries

    async def get_image_names(self, ctx, item):
        await ctx.acquire()

        item = item.replace(" ", "_")
        results = await ctx.db.fetch("SELECT name FROM gamerscape_images WHERE LOWER(name) like $1;",
                                     f"%{item.lower()}%")

        if not results:
            return await self.find_image_names(item)

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

    async def find_image_names(self, item):

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
    async def add_image(self, ctx, url, path, filename):
        """
        downloads an image and adds it to the specified path
        """
        if not filename.endswith((".png", ".jpeg")):
            return await ctx.send("Invalid filename.")

        if not re.match('https?://(?:[-\\w.]|(?:%[\\da-fA-F]{2}))+', url):
            return await ctx.send("Invalid url.")

        try:
            res = await self.bot.fetch(url)
            with open(path + "\\" + filename, "wb") as f:
                f.write(res)
        except (RequestFailed, FileNotFoundError) as e:
            if isinstance(e, RequestFailed):
                return await ctx.send("Failed to download file.")
            await ctx.send(e.strerror)

    @commands.is_owner()
    @commands.command()
    async def add_images(self, ctx, delay: typing.Optional[int] = 5, download=False):
        """add recently added or every image file's to the database on gamerscape
           optionally download found equipment to the drive to serve through http"""
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
                        if datetime.strptime(js["timestamp"], "%Y-%m-%dT%H:%M:%SZ") < timestamp_check["max"]:
                            return await ctx.send("> No more recent images available")

                    print(f"adding {js['name']}....")
                    await ctx.db.execute(
                        """INSERT INTO gamerscape_images 
                           (title, name, url, description_url, description_short_url, timestamp) 
                           VALUES ($1, $2, $3, $4, $5, $6) 
                           ON CONFLICT (name) DO UPDATE SET 
                           description_url = $4, url = $3, timestamp = $6""",
                        js["title"], js["name"], js["url"],
                        js["descriptionurl"], js["descriptionshorturl"],
                        datetime.strptime(js["timestamp"], "%Y-%m-%dT%H:%M:%SZ"))

                    if download:
                        await self.download_gear_from_js(js)

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
    @flags.add_flag("--c", default="all")
    @gamerscape_image_search.group(cls=flags.FlagGroup, invoke_without_command=True)
    async def glam(self, ctx, **options):
        """retrieves images for glamour on gamerscape by filename
           with optional parameters for race, gender and categories in flag notation
           file names are case insensitive valid races are as found
           in the game with some common nicknames, valid genders are male/female or m/f.
           For races like au ra and miqo'te will need to be encased in " " or
           you can call them as miqote and aura, valid category names are as found
           on lodestone, all arm's, tools fall under weapons
           -------------------------------------------------------------
           tataru gis glam name
           tataru gis glam name --r lalafell
           tataru gis glam name" -r lalafell --g female
        """

        item = " ".join(options["glam"]).lower().replace("model", "").replace("model-", "")
        del options["glam"]

        await self.start_menu_gs_source(ctx, item, options)

    @gamerscape_image_search.command(aliases=["cat", "c"])
    async def categories(self, ctx):
        """
        returns acceptable categories for the --c flag for the glam command
        """
        await ctx.send(" - ".join(self.CATEGORIES))

    @glam.group(aliases=["r", "ran"])
    async def random(self, ctx):
        """The main command for returning 10 random pieces of glamour
           subcommands act as optional filters
           -------------------------------------------------------------
           tat gis glam random
           tat gis glam random lalafell
        """

        if ctx.invoked_subcommand:
            race = ctx.invoked_subcommand.name
            path = f"{self.image_root}/*/*/{race}"
        else:
            # ** means match all characters including / this has the effective or transversing every directory
            path = f"{self.image_root}/**"
        # get all files
        files = list(self.get_files("*.png", path))
        try:
            # there should be at least 170k+ images locally added
            files = random.sample(files, 10)
        except ValueError:
            return await ctx.send("Sample too large, or no images have been locally added.")
        self.clean_files(files)
        pages = ctx.menu(source=GSImageFindSource(files), clear_reactions_after=True)
        await pages.start(ctx)

    @random.command(aliases=["lizzard", "lizzer", "liz"])
    async def aura(self, ctx):
        """return only random au ra pieces"""

    @random.command(aliases=["lala", "potato", "dwarf"])
    async def lalafell(self, ctx):
        """return only random lalafell pieces"""

    @random.command(aliases=["elf", "giraffe"])
    async def elezen(self, ctx):
        """return only random elezen pieces"""

    @random.command(aliases=["furry", "ronso"])
    async def hrothgar(self, ctx, gender: typing.Optional[str] = "male", size=1):
        """return only random hrothgar pieces"""

    @random.command(aliases=["roe", "galdjent"])
    async def roegadyn(self, ctx):
        """return only random roegadyn pieces"""

    @random.command(aliases=["bunny", "bunbun", "vii"])
    async def viera(self, ctx):
        """return only random viera pieces"""

    @random.command(aliases=["catgirl", "cat", "miqo", "uwukiteh"])
    async def miqote(self, ctx):
        """return only random miqo'te pieces"""

    @random.command(aliases=["hume"])
    async def hyur(self, ctx):
        """return only random hyur pieces"""

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
            return await ctx.send(f":no_entry: | search failed for {query}")

        pages = ctx.menu(source=GSSearch(entries), clear_reactions_after=True)
        await pages.start(ctx)


def setup(bot):
    bot.add_cog(GamerScape(bot))
