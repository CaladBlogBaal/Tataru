import re
import asyncio

import discord
from discord.ext import commands, flags, menus

from bs4 import BeautifulSoup

from cog_menus.pages_sources import MirapiSource
from config.utils.cache import cache, Strategy
from config.utils.converters import RaceConverter, JobConverter, GenderConverter


def get_links(soup):
    links = []
    for link in soup.find_all("a"):
        links.append((link.get("href"), link.img.get("alt"), link.img.get("src")))
    return links


@cache(maxsize=10, strategy=Strategy.timed)
# outside function to make caching easier
# passing the request function to continue sharing the current aiohttp session
async def get_soup(url, params, request_func):
    results = await request_func(url, params=params)
    soup = BeautifulSoup(results, "html.parser")
    return soup


class MirapiMenuPages(menus.MenuPages):
    def __init__(self, source, **kwargs):
        super().__init__(source, **kwargs)
        self.page = 1
        self.current_bookmark = None

    def increment_page(self, num, max_num):

        res = self.page + num

        if 1 <= res <= max_num:
            self.page += num
            return True

        return False

    async def loading_embed(self):
        embed = discord.Embed(title="Getting results....", colour=0x00dcff)
        embed.set_image(url="https://media1.tenor.com/images/37672d9e1ca24e234dc1864df3d8ab25/tenor.gif")
        await self.message.edit(embed=embed)

    async def generate_new_source(self, increment=1):

        params = self.source.params
        url = params[0]
        url_params = params[1]
        max_pages = self.source.max_pages
        check = self.increment_page(increment, max_pages)

        if check is False:
            return self.source

        params[1]["page"] = self.page

        soup = await get_soup(url, url_params, self.ctx.bot.fetch)
        soup = soup.find("div", {"id": "gallery"})

        source = MirapiSource(get_links(soup), params, max_pages)
        return source

    @menus.button("⏫", position=menus.Last(3))
    async def page_up(self, payload):
        await self.loading_embed()
        source = await self.generate_new_source()
        await self.change_source(source)

    @menus.button("⏬", position=menus.Last(4))
    async def page_down(self, payload):
        await self.loading_embed()
        source = await self.generate_new_source(-1)
        await self.change_source(source)

    @menus.button("🔖", position=menus.Last(5))
    async def bookmark(self, payload):
        page = await self.source.get_page(self.current_page)
        kwargs = await self._get_kwargs_from_page(page)
        self.current_bookmark = kwargs

    @menus.button("📖", position=menus.Last(6))
    async def jump_to_bookmark(self, payload):
        # good chance that the bookmarked page footer will not match the current footer
        current_footer = f"page {self.page} - result {self.current_page + 1}/{self.source.get_max_pages()}"
        embed = self.current_bookmark["embed"]
        embed.set_footer(text=current_footer)
        self.current_bookmark["embed"] = embed
        await self.message.edit(**self.current_bookmark)

    @menus.button("ℹ️", position=menus.Last(7))
    async def menu_help(self, payload):
        embed = discord.Embed(title="Menu help", colour=0x00dcff)
        description = "🔖 - bookmark the current page\n"
        description += "📖 - jump to the bookmarked page\n"
        description += "◀️ - go back\n"
        description += "▶️ - go forward\n"
        description += "⏹️ - terminate the menu\n"
        description += "⏩ - go to last page\n"
        description += "⏪ - go to first page\n"
        description += "⏫ - go up a page\n"
        description += "⏬ - go down a page\n"
        description += "ℹ️ - shows this message"
        #embed.add_field(name="🔖", value="bookmark the current page", inline=False)
        #embed.add_field(name="📖", value="jump to the bookmarked page", inline=False)
        #embed.add_field(name="◀️", value="go back", inline=False)
        #embed.add_field(name="▶️", value="go forward", inline=False)
        #embed.add_field(name="⏹️", value="terminate the menu", inline=False)
        #embed.add_field(name="\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\ufe0f",
        #                value="go to first result", inline=False)
        #embed.add_field(name="\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\ufe0f",
        #                value="go to last result", inline=False)
        #embed.add_field(name="⏫", value="go up a page", inline=False)
        #embed.add_field(name="⏬", value="go down a page", inline=False)
        #embed.add_field(name="ℹ️", value="shows this message", inline=False)
        embed.description = description
        await self.message.edit(embed=embed)
        await asyncio.sleep(10)
        await self.show_current_page()


class Mirapi(commands.Cog):
    """
    Eorzea collection related commands
    """

    def __init__(self, bot):
        self.url = "https://mirapri.com/"
        self.bot = bot

    @staticmethod
    async def convert_flags(ctx, options):
        for k, v in options.items():

            if not v:
                continue

            if k == "r":
                options[k] = await RaceConverter().convert(ctx, options[k])

            elif k == "g":
                options[k] = await GenderConverter().convert(ctx, options[k])

            elif k == "j":
                options[k] = await JobConverter().convert(ctx, options[k])

    @cache()
    async def index_search_item(self, name, language=""):

        js = await self.bot.pyxivapi.index_search(
            name=name,
            indexes=["item"],
            columns=["Name"],
            language=language
        )

        if not js["Results"]:
            return False

        return js["Results"][0]["Name"]

    async def search_mirapi(self, ctx, options):
        params = options

        soup = await get_soup(self.url, params, ctx.bot.fetch)

        if soup.find("img", {"alt": "Nopost"}):
            raise commands.BadArgument(f"search failed for `{options['keyword']}`")

        max_pages = len(soup.find("ul", {"id": "pager-wrap"}).find_all("li"))
        soup = soup.find("div", {"id": "gallery"})
        pages = MirapiMenuPages(source=MirapiSource(get_links(soup), (self.url, params), max_pages),
                                clear_reactions_after=True)
        await pages.start(ctx)

    @commands.group(invoke_without_command=True, aliases=["mi"], ignore_extra=False)
    async def mirapi(self, ctx):
        """
        the main command for mirapi by itself returns glamours on the main page
        """
        await ctx.trigger_typing()
        await self.search_mirapi(ctx, {"page": 1})

    @mirapi.error
    async def on_mirapi_error(self, ctx, error):
        if isinstance(error, discord.ext.commands.errors.TooManyArguments):
            return await ctx.send("⛔ | Invalid subcommand was passed, valid subcommands are `filter, search`",
                                  delete_after=5)

    @flags.add_flag("--j", default="")
    @flags.add_flag("--g", default="")
    @flags.add_flag("--r", default="")
    @mirapi.command(cls=flags.FlagCommand, name="filters", aliases=["filter", "f"])
    async def mirapi_filter(self, ctx, **options):
        """
        returns glamours based on flags
        --j = job, --g = gender, --r = race

        tatary filters -j warrior
        tatary filters --r lalafell
        tatary filters --g male --r lalafell
        """

        if all(v == "" for k, v in options.items()):
            raise commands.BadArgument("No flags were passed.")

        await self.convert_flags(ctx, options)
        options["page"] = 1
        await ctx.trigger_typing()
        await self.search_mirapi(ctx, options)

    @mirapi.group(invoke_without_command=True, aliases=["se", "s"])
    async def search(self, ctx, *, query):
        """
        the main command for retrieving glamours on mirapi based on a keyword

        tataru mirapi search query
        """
        await ctx.trigger_typing()
        await self.search_mirapi(ctx, {"keyword": query, "page": 1})

    @flags.add_flag("keyword", nargs="+")
    @flags.add_flag("--j", default="")
    @flags.add_flag("--g", default="")
    @flags.add_flag("--r", default="")
    @search.group(cls=flags.FlagCommand, name="filters", aliases=["filter", "f"])
    async def search_filters(self, ctx, **options):
        """
        returns glamours based on a keyword with optional flags
        --j = job, --g = gender, --r = race

        tatary mirapi search filters <query here>
        tatary mirapi search filters <query here> --r lalafell
        tatary mirapi search filters <query here> --g male --r lalafell
        """

        await self.convert_flags(ctx, options)
        options["keyword"] = " ".join(options["keyword"])
        options["page"] = 1
        await ctx.trigger_typing()
        await self.search_mirapi(ctx, options)

    @flags.add_flag("keyword", nargs="+")
    @flags.add_flag("--j", default="")
    @flags.add_flag("--g", default="")
    @flags.add_flag("--r", default="")
    @search.group(cls=flags.FlagCommand, aliases=["eq"])
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def equipment(self, ctx, **options):
        """
        returns glamours based on equipment name with optional flags
        --j = job, --g = gender, --r = race

        tataru mirapi search equipment <equipment name>
        tataru mirapi search equipment <equipment name> --r lalafell
        tataru mirapi search equipment <equipment name> --g male --r lalafell
        """
        await self.convert_flags(ctx, options)

        # lowercase the name to standardize it for cache
        name = " ".join(options["keyword"]).lower()

        # if the equipment contains alpha characters attempt to get the japanese name

        if re.match(r"[a-zA-Z]", name):

            name = await self.index_search_item(" ".join(options["keyword"]).lower(), "ja")

            if not name:

                return await ctx.send(f"> search failed for {' '.join(options['keyword'])}")

        options["keyword"] = name
        options["page"] = 1

        await ctx.trigger_typing()
        await self.search_mirapi(ctx, options)

    @commands.command(aliases=["af"])
    async def acceptable_flags(self, ctx):
        """
        returns acceptable arguments that can be passed as flags for equipment and filters commands
        tataru acceptable_flags
        """

        s = "> For **--j** acceptable arguments are the **job names** or **acronyms** "
        s += "as found in game and **job id** as found on mirapi eg. war, warrior, 10"
        s += "\n> For **--r** acceptable arguments are the **race names** "
        s += "as found in game and race id as found on mirapi eg. lalafell, 4 with some race nicknames like potato"
        s += "\n> For **--g** acceptable arguments are **male, female, m, f** and **0** for male and **1** for female"

        await ctx.send(s)

    @commands.command(name="getraceids", aliases=["gri"])
    async def get_race_ids(self, ctx):
        """
        returns acceptable race ids for the --r flag
        """

        s = "hyur = 1, elezen = 2, miqo'te = 3, lalafell = 4, roegadyn = 5, au ra = 6, viera = 7, 8 = hrothgar, 9 " \
            "= chocobo"
        await ctx.send(s)

    @commands.command(name="getjobids", aliases=["gji"])
    async def get_job_ids(self, ctx):
        """
        returns acceptable job ids for the --j flag
        """
        s = "> pld = 9, war = 10, drk = 11, drg = 12, mnk = 13, nin = 14, sam = 34, brd = 15, mch = " \
            "16, blm = 17 rdm = 35, smn = 18, sch = 19, whm = 20, ast = 21, blu = 36, dnc = 37, gnb = 38"
        await ctx.send(s)


def setup(bot):
    bot.add_cog(Mirapi(bot))
