import re
import itertools
import typing

from bs4 import BeautifulSoup

from discord.ext import commands

from config import config
from config.utils.converters import CharacterAndWorldConverter
from config.utils.emojis import ICONS
from config.utils.requests import RequestFailed

from cog_menus.pages_sources import *


class Fflogs(commands.Cog):
    """
    Gamer Scape related commands
    """

    def __init__(self, bot):
        self.key = config.__fflogs_api_key__
        self.url = "https://www.fflogs.com/v1"
        self.bot = bot
        self.metric = "rdps"
        self.job_icons = ICONS

    async def cog_after_invoke(self, ctx):
        # set the metric back rdps
        self.metric = "rdps"

    @staticmethod
    async def get_zone_name_by_encounter(ctx, encounter_id):
        return await ctx.db.fetchval("""SELECT zone.name from zone INNER JOIN encounter e on zone.id = e.zone_id
                                        where e.id = $1 """, encounter_id)

    @staticmethod
    async def get_trial_zone(ctx, expansion_name):

        data = await ctx.db.fetchval("Select id from zone where lower(expansion_name) like $1 and name like $2",
                                     expansion_name.lower(), "Trials (Extreme)")
        if data:
            return data
        return None

    @staticmethod
    async def get_bracket(ctx, expansion):
        data = await ctx.db.fetchval("Select min from bracket where lower(expansion_name) like $1", expansion.lower())
        return data

    @staticmethod
    async def get_zones(ctx, expansion):
        data = await ctx.db.fetch("Select id from zone where lower(expansion_name) like $1 and blacklist = false",
                                  expansion.lower())
        return data

    @staticmethod
    def savage_check(parses):

        for parse in parses:
            if parse["difficulty"] == 101:
                return True
        return False

    @staticmethod
    def best_parses_only(parses: list):

        best_parses = [max(g[1], key=lambda x: x["percentile"])
                       for g in itertools.groupby(parses, lambda o: o["encounterID"])]
        return best_parses

    @staticmethod
    def filter_out_logs(parses, difficulty):
        # 100 = normal/exteme, 101 = savage
        # editing the list passed in
        parses[:] = [p for p in parses if not p["difficulty"] == difficulty]#

    def construct_url(self, name, world, region, ranking=False):
        if ranking:
            return self.url + "/rankings/character/{}/{}/{}".format(name, world, region)

        return self.url + "/parses/character/{}/{}/{}".format(name, world, region)

    async def get_parses(self, character, region, zone=None, ranking=False, encounter=None):

        name = character["first_name"] + " " + character["second_name"]

        params = {
            "zone": zone,
            "timeframe": "historical",
            "api_key": self.key,
            "metric": self.metric
        }

        if not zone:
            del params["zone"]

        if encounter:
            params["encounter"] = encounter

        url = self.construct_url(name, character["world"], region, ranking)

        result = await self.bot.fetch(url, params=params)

        # fflogs site is probably down and returning a string if bytes get returned
        if isinstance(result, bytes):
            raise commands.BadArgument(result.decode("utf-8"))

        if not result:
            raise commands.BadArgument(f"> No parses were found for the **character** \"{name}\" "
                                       f"for world **{character['world']}**.")
        return result

    async def embed_parses_build_description(self, parse, view=False):
        seconds = (parse['duration'] / 1000) % 60
        seconds = round(seconds)

        if seconds < 10:
            seconds = f"0{seconds}"

        minutes = (parse['duration'] / (1000 * 60)) % 60
        minutes = round(int(minutes), 2)

        time = f"{minutes}:{seconds}"
        percentile = round(parse["percentile"])
        dps = round(parse["total"])
        job = ""
        difficulty = "normal/ex"

        if parse["difficulty"] == 101:
            difficulty = "savage"

        for e in self.job_icons:
            # if the job name is equal to the emote name, send the emote representation
            if parse["spec"].replace(" ", "").lower() == e.name:
                job = str(e)

        report_id = parse["reportID"]
        name = parse["encounterName"]
        url = "https://www.fflogs.com/reports/"
        result = f"{job} **{name}** [{dps}]({url + report_id}) dps {percentile} % • {time} **({difficulty})**\n"

        if view:
            view, value = await self.get_view(view, parse)
            result = result.replace("\n", "") + f" • {view} {value}"

        return result

    async def get_view(self, view, parse):
        params = {"targetclass": parse[0]["spec"],
                  "end": parse[0]["duration"],
                  }
        url = self.url + "/report/events/{}/{}".format(view, parse[0]["reportID"])
        results = await self.bot.fetch(url, params=params)

    async def embed_parses(self, ctx, parses):

        zone_name = await self.get_zone_name_by_encounter(ctx, parses[0]["encounterID"])

        url = "https://www.fflogs.com/character/id/" + str(parses[0]["characterID"])

        title = f"{parses[0]['characterName']} of {parses[0]['server']}"

        entries = []

        for parse in parses:
            entries.append((title, url, zone_name, await self.embed_parses_build_description(parse)))

        pages = ctx.menu(source=ParseSource(entries), clear_reactions_after=True)
        await pages.start(ctx)

    @commands.group(invoke_without_command=True, aliases=["tl"])
    async def tierlogs(self, ctx, *, character: typing.Optional[typing.Union[discord.User, str]] = None):
        """Displays raid parses for the current expansion raid tier
           If you don't provide a Discord user or character parameters, your own saved character will be used.
           -------------------------------------------------------------
           tataru tierlogs
           tataru tierlogs @User or user_id or name
           tataru tierlogs World Forename Surname"""

        character = await CharacterAndWorldConverter().convert(ctx, character)

        region = await ctx.db.fetchval("SELECT region from world where name like $1", character["world"])

        parses = await self.get_parses(character, region)

        await self.embed_parses(ctx, parses)

    @tierlogs.group(aliases=["b"], invoke_without_command=True)
    async def best(self, ctx, *, character: typing.Optional[typing.Union[discord.User, str]] = None):
        """Displays best raid/trial parses for the current expansion's content
           Expansions StB/Hw/ShB or Shadowbringers/Heavensward/Stormblood
           If you don't provide a Discord user or character parameters, your own saved character will be used.
           -------------------------------------------------------------
           tataru tierlogs
           tataru tierlogs @User or user_id or name
           tataru tierlogs World Forename Surname"""

        character = await CharacterAndWorldConverter().convert(ctx, character)

        region = await ctx.db.fetchval("SELECT region from world where name like $1", character["world"])
        parses = await self.get_parses(character, region, ranking=True)
        # if the player has savage logs remove all normal logs

        if self.savage_check(parses):
            self.filter_out_logs(parses, 100)

        parses = self.best_parses_only(parses)

        await self.embed_parses(ctx, parses)

    @best.command(name="adps")
    async def actual_dps(self, ctx, trials: typing.Optional[bool] = False, *,
                         character: typing.Optional[typing.Union[discord.User, str]] = None):
        """sets the metric for rankings to adps"""
        self.metric = "dps"
        await ctx.invoke(self.bot.get_command("tierlogs best"), trials=trials, character=character)

    @commands.group(aliases=["log", "l"], hidden=True)
    # @commands.cooldown(1, 5, commands.BucketType.member)
    async def logs(self, ctx):
        """The main command for logs by itself does nothing functionality is implemented in it's sub commands"""

    @commands.command(aliases=["encounter", "el"])
    async def encounterlogs(self, ctx, savage_only: typing.Optional[bool],
                            name, *, character: typing.Optional[typing.Union[discord.User, str]] = None):
        """returns all parses for an encounter by name as found on fflogs
           If you don't provide a Discord user or character parameters, your own saved character will be used.
           encounter acronyms are also accepted valid ones are (e1-x,o1-x,a1-x)
           eg. tataru e6s or tataru e6n or tataru e6, with a savage check
           -------------------------------------------------------------
           tataru "encounter name"
           tataru y "encounter name"
           tataru "encounter name" @User or user_id or name
           tataru "encounter name" World Forename Surname
        """
        parses = []
        data = await ctx.db.fetch("""Select id, zone_id from encounter 
                                     where lower(name) like $1 or lower(alias_s) like $1 or lower(alias_n) like $1""",
                                  name.lower() + "%")

        if not data:
            return await ctx.send(f"> search failed for \"{name}\"")

        character = await CharacterAndWorldConverter().convert(ctx, character)
        region = await ctx.db.fetchval("SELECT region from world where name like $1", character["world"])

        for enc in data:
            parses.extend(await self.get_parses(character, region, zone=enc["zone_id"], encounter=enc["id"]))

        if savage_only:
            self.filter_out_logs(parses, 100)
            if parses == []:
                return await ctx.send(f"> you only have nomal mode logs for encounter `{name}`")

        await self.embed_parses(ctx, parses)

    @commands.is_owner()
    @commands.command()
    async def add_zones(self, ctx):
        """Add zones and encounters to the database
        -------------------------------------------------------------
        tataru add_zones"""
        zones = await self.bot.fetch(self.url + "/zones", params={"api_key": self.key})
        for zone in zones:
            zone_id = zone["id"]
            name = zone["name"]
            frozen = zone["frozen"]
            min_b = zone["brackets"]["min"]
            max_b = zone["brackets"]["max"]

            async with ctx.acquire():
                expansion_name = await ctx.db.fetchval("SELECT name from expansion where patch_number = $1", min_b)

                await ctx.db.execute("""INSERT INTO bracket (min, expansion_name, max) VALUES ($1,$2,$3) 
                                        ON CONFLICT DO NOTHING""", min_b, max_b)

                await ctx.db.execute("""INSERT INTO "zone" (id,name,frozen,expansion_name) values ($1,$2,$3,$4)
                                        ON CONFLICT DO NOTHING""",
                                     zone_id, name, frozen, expansion_name)

                for encounter in zone["encounters"]:
                    await ctx.db.execute("""INSERT INTO encounter (id,name,expansion_name,zone_id) values ($1,$2,$3,$4)
                                            ON CONFLICT DO NOTHING """,
                                         encounter["id"], encounter["name"], expansion_name, zone_id)

        await ctx.send("successfully added zones and encounters :white_check_mark:")

    @commands.is_owner()
    @commands.group()
    async def blacklist(self, ctx, *, zone_name):
        """blacklist zones by name in the database
        -------------------------------------------------------------
        tataru blacklist zone_name
        """
        # dungeons and alliance raids
        # tensai blacklist dungeons
        # tensai blacklist The Copied Factory
        # tensai blacklist void
        # tensai blackist the weeping city
        # tensai blacklist the ridorana
        # tensai blacklist the orbonne
        # tensai blacklist the royal
        async with ctx.acquire():
            check = await ctx.db.execute("UPDATE zone set blacklist = True where lower(name) like $1",
                                         f"{zone_name.lower()}%")

        if check == "UPDATE 0":
            return await ctx.send("> update failed")

        await ctx.send(check)

    @blacklist.command()
    async def remove(self, ctx, *, zone_name):
        """remove a zone by name from the blacklist in the database
        -------------------------------------------------------------
        tataru blacklist remove zone_name
        """
        async with ctx.acquire():
            check = await ctx.db.execute("UPDATE zone set blacklist = False where lower(name) like $1",
                                         f"{zone_name.lower()}%")

        if check == "UPDATE 0":
            return await ctx.send("> update failed")

        await ctx.send(check)

    @commands.command()
    async def search(self, ctx, *, term):
        """
        search for a player or free company and retrieve their fflogs page
        -------------------------------------------------------------
        tataru search term
        """
        params = {"term": term}
        results = await self.bot.fetch("https://www.fflogs.com/search", params=params)
        soup = BeautifulSoup(results, "html.parser")
        results = soup.find("div", {"class": "result-list"})
        entries = []
        if not results:
            return await ctx.send(f"> Search failed for {term}")

        worlds = results.find_all("div", {"class": "server"})
        for i, a in enumerate(results.find_all("a")):
            world = worlds[i].get_text()
            result = f"[{a.get_text()}]({a.get('href')}) of {world}"
            entries.append(result)

        pages = ctx.menu(source=SearchSource(entries), clear_reactions_after=True)
        await pages.start(ctx)

    @commands.command()
    @commands.is_owner()
    async def set_alias(self, ctx, alias, *, encounter):
        """
        sets the aliases for encounters
        -------------------------------------------------------------
        tataru set_aliass alias encounter
        valid aliases are as follow, encounter number followed by difficulty n for normal s for savage
        """
        if not re.search(r"^[1-9]|1[0-2]", alias) and not re.search(r"[ns]", alias):
            return await ctx.send("Invalid alias was passed.")

        async with ctx.acquire():
            data = await ctx.db.fetchrow("SELECT * from encounter where lower(name) like $1", encounter.lower() + "%")

            if not data:
                return await ctx.send(f"> search failed for {encounter}")

            zone_name = await ctx.db.fetchval("SELECT name from zone where id = $1", data["zone_id"])

            first_character = zone_name[0]
            alias = first_character + alias

            if alias[2].lower() == "s":
                check = await ctx.db.execute("UPDATE encounter SET alias_s = $1 where id = $2",
                                             alias, data["id"])
            else:
                check = await ctx.db.execute("UPDATE encounter SET alias_n = $1 where id = $2",
                                             alias, data["id"])
            if check == "UPDATE 0":
                return await ctx.send("> update failed")

            await ctx.send(check)

    @tierlogs.error
    @best.error
    async def log_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        if isinstance(error, RequestFailed):
            await ctx.send("Invalid character name/server/region specified.")

        elif isinstance(error, commands.BadArgument):
            await ctx.send(error)


def setup(bot):
    bot.add_cog(Fflogs(bot))
