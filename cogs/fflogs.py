import asyncio
import re
import difflib
import typing

from collections import namedtuple

import discord

from discord.ext import commands

from bs4 import BeautifulSoup

from asyncpg import Record

from oauthlib.oauth2 import BackendApplicationClient
from oauthlib.oauth2.rfc6749.errors import MissingTokenError

from async_oauthlib import OAuth2Session

from python_graphql_client import GraphqlClient

from config import config
from config.utils.converters import CharacterAndWorldConverter
from config.utils.emojis import ICONS
from config.utils import cache
from config.utils import context

from cog_menus.pages_sources import ParseSource, SearchSource

from cogs.error_handler import ParsesNotFound, CharacterNotFound

FFLOGS_OAUTH_URL = "https://www.fflogs.com/oauth/token"
FFLOGS_URL = "https://www.fflogs.com/api/v2/client"


class FFlogsAPI:
    def __init__(self):
        self.client = GraphqlClient(FFLOGS_URL)
        token_client = BackendApplicationClient(client_id=config.__fflogs_client_id__)
        self.oauth = OAuth2Session(client=token_client)

    async def get_bearer_token(self):
        # access tokens for OAuth 2.0
        token = await self.oauth.fetch_token(token_url=FFLOGS_OAUTH_URL, client_id=config.__fflogs_client_id__,
                                             client_secret=config.__fflogs_client_secret__)
        return token

    async def call_fflogs_api(self, query, variables, token):
        # making a request with query defined variables and access token
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token['access_token']}"
        }
        data = await self.client.execute_async(query=query, variables=variables, headers=headers)

        return data


class FFlogs(commands.Cog):
    """
    FFlogs related commands
    """

    def __init__(self, bot):
        self.bot = bot
        self.api = FFlogsAPI()
        self.metric = "rdps"
        self.job_dict = ICONS
        self.current_dungeons = None
        self.current_tier_id = None
        self.encounter_regex = None
        bot.loop.create_task(self.__ainit__())

    def cog_unload(self):
        asyncio.ensure_future(self.api.oauth.close())

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, MissingTokenError):
            # if this is called an invalid client details was passed or FFlogs is down
            return await ctx.send("> FFlogs seems to be down", delete_after=4)

    async def __ainit__(self):
        # getting the current zone id by passing nothing to zoneRankings
        # doing this since zoneRanking inherently does not return all reports as it's a 1-1
        # to the default character page on fflogs as shown here
        # https://www.fflogs.com/character/eu/spriggan/calad%20baal
        query = """
                  query {
                    characterData{
                      character(name: "Calad Baal"
                                serverSlug:"Spriggan"
                                serverRegion: "EU"
                      ) {
                        zoneRankings(zoneID: 0)
                      }
                    }

                  }
              """
        token = await self.api.get_bearer_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token['access_token']}"
        }

        data = await self.api.client.execute_async(query=query, headers=headers)
        self.current_tier_id = data["data"]["characterData"]["character"]["zoneRankings"]["zone"]

        async with self.bot.pool.acquire() as con:
            names = await con.fetch("SELECT DISTINCT name from difficulties")
            # building a regex to match difficulty name followed by it's respective id
            self.encounter_regex = re.compile(r"(%s)" % "|".join(n["name"] + r"\d*" for n in names))
            dungeons = await con.fetch("SELECT id, expansion_name FROM zone WHERE name like 'Dungeon%'")
            dungeons = [x["id"] for x in dungeons]
            self.current_dungeons = dungeons

    async def cog_after_invoke(self, ctx):
        # set the metric back rdps
        self.metric = "rdps"

    @staticmethod
    async def get_difficulties_ids_by_zone(ctx, zone_id):
        return await ctx.db.fetch("SELECT name, diff_id FROM difficulties WHERE zone_id = $1", zone_id)

    @staticmethod
    async def get_encounters_by_zone(ctx, zone_id):
        return await ctx.db.fetch("""SELECT e.id from encounter e INNER JOIN zone z ON e.zone_id  = z.id
                                     WHERE e.zone_id = $1 """, zone_id)

    #  @staticmethod
    #  async def get_trials_zone(ctx, expansion_name):
    #
    #      data = await ctx.db.fetch("Select id from zone where lower(expansion_name) like $1 and name like $2",
    #                                expansion_name.lower(), "Trials % (Extreme)")
    #      return data
    @staticmethod
    def sub_difficulty(key):
        return re.sub(r"\d", "", key)

    @staticmethod
    def validate_savage(ranks):

        return any(x[1].get("bestPerformanceAverage") or x[1].get("bestAmount")
                   for x in ranks
                   if "Savage" in x[0] or "Dungeon" in x[0])

    @staticmethod
    def check_parse(parse):
        return parse.get("bestAmount") or parse.get("amount")

    @staticmethod
    def filter_out_parses(ranks, difficulty: int):
        # 100 = normal/extreme, 101 = savage
        # editing the list passed in
        ranks[:] = [(x, p) for x, p in ranks if not p["difficulty"] == difficulty]

    @staticmethod
    def build_time(milliseconds):
        minutes, seconds = divmod(milliseconds / 1000, 60)

        time = f"{minutes:0>2.0f}:{seconds:0>2.0f}"
        return time

    def savage_only(self, ranks, character: Record):
        if not self.validate_savage(ranks):
            name = character["first_name"] + " " + character["second_name"]
            raise ParsesNotFound(f"The character `{name}` of world `{character['world']}` only has normal mode logs.")

        self.filter_out_parses(ranks, 100)

    def build_sub_fields(self, rtype, difficulties: typing.Union[list, Record], ranking_ids):
        base = ""

        for rid in ranking_ids:
            frame = "timeframe: Historical"
            # for multiple encounter/zoneRankings an alias is needed so opting to use it's id suffixed with it's
            # difficulty name
            for r in difficulties:
                base += f"{r['name']}{rid}: {rtype}Rankings(difficulty: {r['diff_id']} " \
                        f"{rtype}ID: {rid} metric: {self.metric} {frame})\n"

        sub_fields = f"""
                  {{canonicalID
                    name
                    server{{name}}
                    {base}
                 }}
                  """
        return sub_fields

    def get_job_emote(self, spec: str):
        return self.job_dict[spec]

    async def get_zone(self, ctx, name):

        zone = await ctx.db.fetchval("SELECT id FROM zone WHERE LOWER(name) like $1", name.lower() + "%")

        if zone in self.current_dungeons:
            current_dungeon = await ctx.db.fetchval("""SELECT z.id from zone z
                                                       INNER JOIN bracket b on b.expansion_name = z.expansion_name
                                                       WHERE z.id = ANY($1::INT[]) ORDER BY b.max DESC"""
                                                    , self.current_dungeons)
            return current_dungeon

        return zone

    async def invoke_best(self, ctx, command_name, *args, **kwargs):
        # set the metric to adps
        self.metric = "dps"
        # optional string args followed by a subcommand doesn't work well if you invoke the main group
        cmd = self.bot.get_command(command_name)

        await cmd(ctx, *args, **kwargs)

    @cache.cache()
    # caching because it's slightly faster and build_zone_string adds up with many encounters
    async def get_encounter_name_by_id(self, ctx, encounter_id):
        return await ctx.db.fetchval("SELECT name FROM encounter WHERE id = $1", encounter_id)

    async def get_character_data(self, character, region, difficulties, encounters: list = None, zones: list = None):

        name = character["first_name"] + " " + character["second_name"]

        if encounters:
            sub_fields = self.build_sub_fields("encounter", difficulties, encounters)
        elif zones:
            sub_fields = self.build_sub_fields("zone", difficulties, zones)
        else:
            raise commands.BadArgument("An encounter id(s) or zone id(s) needs to be passed.")

        token = await self.api.get_bearer_token()

        variables = {
            "name": name,
            "serverSlug": character["world"],
            "serverRegion": region,
        }

        query = f"""
        query ($name: String!, $serverSlug: String!, $serverRegion: String!) {{
          characterData{{
            character(
              name: $name
              serverSlug: $serverSlug
              serverRegion: $serverRegion
            )
            {sub_fields}
          }}
        }}"""

        data = await self.api.call_fflogs_api(query=query, variables=variables, token=token)

        world = character["world"]

        if not data["data"]["characterData"]["character"]:
            raise CharacterNotFound(f"The **character** \"{name}\" for world **{world}** does not exist on fflogs.")

        ranks = []
        for key in data["data"]["characterData"]["character"].keys():
            # encounterRankings or zoneRankings are aliased as difficulty name followed by their respective id
            # \d* matches any digit
            if self.encounter_regex.match(key):
                ranks.append((key, data["data"]["characterData"]["character"][key]))

        if not ranks:
            raise ParsesNotFound(f"No parses were found for the **character** \"{name}\" for world **{world}**.")

        return data, ranks

    async def paginate(self, ctx, entries, embed_tuple):
        pages = ctx.reply_menu(source=ParseSource(embed_tuple, entries), clear_reactions_after=True)
        await pages.start(ctx)

    async def build_embed_tuple(self, ctx, data, ranks):
        embed = namedtuple("Embed", "title url zone_name")
        zone_id = data["data"]["characterData"]["character"][ranks[0][0]]["zone"]
        zone_name = await ctx.db.fetchval("""SELECT name from zone WHERE id = $1 """, zone_id)
        char_id = data["data"]["characterData"]["character"]["canonicalID"]
        char_name = data["data"]["characterData"]["character"]["name"]
        char_world = data["data"]["characterData"]["character"]["server"]["name"]
        url = f"https://www.fflogs.com/character/id/{char_id}?zone={zone_id}"
        title = f"{char_name} of {char_world}"
        return embed(title, url, zone_name)

    async def build_zone_string(self, ctx, key, parse):
        length = await ctx.db.fetchval("SELECT LENGTH(name) FROM encounter ORDER BY LENGTH(name) desc")
        time = self.build_time(parse["fastestKill"])
        percentile = parse["rankPercent"]
        dps = parse["bestAmount"]
        job = self.get_job_emote(parse["bestSpec"].lower())
        name = parse["encounter"]["name"]
        total_kills = parse["totalKills"]
        difficulty = self.sub_difficulty(key)
        result = f"{job} **`{name.ljust(length)}`** `{dps:5.0f}` {self.metric} `{percentile:3.0f}` • `{time}` • `" \
                 f"{total_kills}` kills **({difficulty})**\n"

        return result

    async def build_encounter_string(self, ctx, key, parse):
        length = await ctx.db.fetchval("SELECT LENGTH(name) FROM encounter ORDER BY LENGTH(name) desc")
        time = self.build_time(parse['duration'])
        percentile = parse["rankPercent"]
        dps = parse["amount"]
        job = self.get_job_emote(parse["spec"].lower())
        report_id = parse["report"]["code"]
        fight_id = parse["report"]["fightID"]
        # getting rid of the difficulty name
        name = await self.get_encounter_name_by_id(ctx, int(re.sub(r"[a-zA-Z]", "", key)))
        url = "https://www.fflogs.com/reports/"
        # getting rid of the difficulty id
        difficulty = self.sub_difficulty(key)

        result = f"{job} **`{name.ljust(length)}`** [`{dps:5.0f}`]({url}{report_id}#fight={fight_id}) {self.metric} " \
                 f"`{percentile:3.0f}` • `{time}` **({difficulty})**\n"

        return result

    async def start_menu(self, ctx, data, ranks,
                         func: typing.Callable[[context.Context, str, dict], typing.Awaitable[str]],
                         ranking_key):

        embed_tuple = await self.build_embed_tuple(ctx, data, ranks)

        # list comps that are faster then appending for some reason

        # build zone string/build encounter string
        # unpacking ranks as I iterate over it then iterating over another list accessed from the value dictionary
        # checking for parses that pass the conditional to build the zone/encounter string
        entries = [await func(ctx, key, parse)
                   for key, value in ranks for parse in value[ranking_key]
                   if self.check_parse(parse)]

        await self.paginate(ctx, entries, embed_tuple)

    async def get_close_matches(self, ctx, name, data: Record) -> None:
        words = difflib.get_close_matches(name, (e["name"] for e in data))

        if words:
            # drop duplicates
            words = list(dict.fromkeys(words))
            await ctx.send(f"> Search failed for \"{name}\"\n> Did you mean.... \n> {', '.join(words)}?")

        else:

            await ctx.send(f"> search failed for \"{name}\"")

    async def best_encounter(self, ctx, data, ranks) -> None:
        entries = []
        embed_tuple = await self.build_embed_tuple(ctx, data, ranks)
        for t in ranks:
            key, val = t
            total_kills = val["totalKills"]
            string = await self.build_encounter_string(ctx, key, val["ranks"][0])
            difficulty = self.sub_difficulty(key)
            string = string.replace(f"**({difficulty})**", f"`{total_kills}` kills **({difficulty})**\n")
            entries.append(string)

        await self.paginate(ctx, entries, embed_tuple)

    async def get_encounter_logs(self, ctx, savage_only: typing.Optional[bool],
                                 name, character: typing.Optional[typing.Union[discord.User, str]] = None,
                                 best=False):
        encounter = await ctx.db.fetchval("""SELECT id FROM encounter
                                             WHERE lower(name) LIKE $1 or LOWER(alias_s)
                                             LIKE $1 or LOWER(alias_n) LIKE $1""",
                                          name.lower() + "%")
        if not encounter:
            return await self.get_close_matches(ctx, name, await ctx.db.fetch("SELECT name FROM encounter"))

        # dungeons and alliance raid encounters only accept dps as a metric
        if encounter > 2000:
            self.metric = "dps"

        character = await CharacterAndWorldConverter().convert(ctx, character)
        async with ctx.typing():
            region = await ctx.db.fetchval("SELECT region from world where name like $1", character["world"])
            # full join then a inner join, yeah don't ask
            difficulties = await ctx.db.fetch("""SELECT d.name, diff_id FROM difficulties d, encounter e
                                                 INNER JOIN zone z ON e.zone_id  = z.id
                                                 WHERE e.id = $1 and z.id = d.zone_id """, encounter)

            data, ranks = await self.get_character_data(character, region, difficulties, encounters=[encounter])

            if savage_only:
                self.savage_only(ranks, character)

            if best:
                return await self.best_encounter(ctx, data, ranks)

            await self.start_menu(ctx, data, ranks, self.build_encounter_string, "ranks")

    @commands.group(invoke_without_command=True, aliases=["tl"])
    async def tierlogs(self, ctx, savage_only: typing.Optional[bool], *,
                       character: typing.Optional[typing.Union[discord.User, str]] = None):
        """Displays raid parses with a hyperlink for the current expansion raid tier
           If you don't provide a Discord user or character parameters, your own saved character will be used.
           The savage_only parameter takes arguments like yes/no
           -------------------------------------------------------------
           tataru tierlogs
           tataru tierlogs y
           tataru tierlogs @User or user_id or name
           tataru tierlogs World Forename Surname"""

        character = await CharacterAndWorldConverter().convert(ctx, character)
        async with ctx.typing():
            region = await ctx.db.fetchval("SELECT region from world where name like $1", character["world"])

            difficulties = await self.get_difficulties_ids_by_zone(ctx, self.current_tier_id)

            encounters = [res["id"] for res in await self.get_encounters_by_zone(ctx, self.current_tier_id)]

            data, ranks = await self.get_character_data(character, region, difficulties, encounters=encounters)

            if savage_only:
                self.savage_only(ranks, character)

            await self.start_menu(ctx, data, ranks, self.build_encounter_string, "ranks")

    @tierlogs.group(aliases=["b"], invoke_without_command=True)
    async def best(self, ctx, savage_only: typing.Optional[bool], *,
                   character: typing.Optional[typing.Union[discord.User, str]] = None):
        """Displays best raid parses
           The savage_only parameter takes arguments like yes/no
           -------------------------------------------------------------
           tataru tierlogs best
           tataru tierlogs best y
           tataru tierlogs best @User or user_id or name
           tataru tierlogs best World Forename Surname
        """

        character = await CharacterAndWorldConverter().convert(ctx, character)

        region = await ctx.db.fetchval("SELECT region from world where name like $1", character["world"])

        difficulties = await self.get_difficulties_ids_by_zone(ctx, self.current_tier_id)

        data, ranks = await self.get_character_data(character, region, difficulties, zones=[self.current_tier_id])

        if savage_only:
            self.savage_only(ranks, character)

        await self.start_menu(ctx, data, ranks, self.build_zone_string, "rankings")

    @best.command(name="adps")
    async def actual_dps(self, ctx, savage_only: typing.Optional[bool], *,
                         character: typing.Optional[typing.Union[discord.User, str]] = None):
        """sets the metric for rankings to adps
           The savage_only parameter takes arguments like yes/no
           -------------------------------------------------------------
           tataru tierlogs best adps
           tataru tierlogs best adps y
           tataru tierlogs best adps @User or user_id or name
           tataru tierlogs best adps World Forename Surname
           """
        await self.invoke_best(ctx, "tierlogs best", savage_only=savage_only, character=character)

    @commands.group(aliases=["log", "l"], invoke_without_command=True)
    async def logs(self, ctx, savage_only: typing.Optional[bool], name, *,
                   character: typing.Optional[typing.Union[discord.User, str]] = None):
        """returns all parses for a zone by name as found on fflogs
           If you don't provide a Discord user or character parameters, your own saved character will be used.
           The savage_only parameter takes arguments like yes/no
           -------------------------------------------------------------
           tataru logs "Eden's Promise"
           tataru logs y "Eden's Promise"
           tataru logs "Eden's Promise" @User or user_id or name
           tataru logs "Eden's Promise" World Forename Surname
        """

        character = await CharacterAndWorldConverter().convert(ctx, character)
        async with ctx.typing():
            region = await ctx.db.fetchval("SELECT region from world where name like $1", character["world"])
            zone = await self.get_zone(ctx, name.lower() + "%")

            if not zone:
                return await self.get_close_matches(ctx, name, await ctx.db.fetch("SELECT name FROM zone"))

            difficulties = await self.get_difficulties_ids_by_zone(ctx, zone)

            encounters = [res["id"] for res in await self.get_encounters_by_zone(ctx, zone)]

            if any(e > 2000 for e in encounters):
                # dungeons and alliance raid encounters only accept dps as a metric
                self.metric = "dps"

            data, ranks = await self.get_character_data(character, region, difficulties, encounters=encounters)

            if savage_only:
                self.savage_only(ranks, character)

            await self.start_menu(ctx, data, ranks, self.build_encounter_string, "ranks")

    @logs.group(aliases=["b"], name="best", invoke_without_command=True)
    async def best_logs(self, ctx, savage_only: typing.Optional[bool], name, *,
                        character: typing.Optional[typing.Union[discord.User, str]] = None):
        """Displays best parses
           The savage_only parameter takes arguments like yes/no
           -------------------------------------------------------------
           tataru logs best "Eden's Promise"
           tataru logs best y "Eden's Promise"
           tataru logs best @User or user_id or name "Eden's Promise"
           tataru logs best World Forename Surname "Eden's Promise"
        """
        character = await CharacterAndWorldConverter().convert(ctx, character)

        region = await ctx.db.fetchval("SELECT region from world where name like $1", character["world"])
        zone = await self.get_zone(ctx, name.lower() + "%")

        if not zone:
            return await self.get_close_matches(ctx, name, await ctx.db.fetch("SELECT name FROM zone"))

        check = await ctx.db.fetchval("SELECT id FROM encounter WHERE zone_id = $1", zone)

        if check > 2000:
            self.metric = "dps"
        difficulties = await self.get_difficulties_ids_by_zone(ctx, zone)

        data, ranks = await self.get_character_data(character, region, difficulties, zones=[zone])

        if savage_only:
            self.savage_only(ranks, character)

        await self.start_menu(ctx, data, ranks, self.build_zone_string, "rankings")

    @best_logs.command(name="adps")
    async def best_logs_adps(self, ctx, savage_only: typing.Optional[bool], zone, *,
                             character: typing.Optional[typing.Union[discord.User, str]] = None):
        """sets the metric for rankings to adps
           The savage_only parameter takes arguments like yes/no
           -------------------------------------------------------------
           tataru logs best adps
           tataru logs y best adps
           tataru logs best adps @User or user_id or name
           tataru logs best adps World Forename Surname
           """

        await self.invoke_best(ctx, "logs best", savage_only, zone, character=character)

    @commands.group(aliases=["encounter", "el"], invoke_without_command=True)
    async def encounterlogs(self, ctx, savage_only: typing.Optional[bool],
                            name, *, character: typing.Optional[typing.Union[discord.User, str]] = None):
        """returns all parses for an encounter by name as found on fflogs
           If you don't provide a Discord user or character parameters, your own saved character will be used.
           encounter acronyms are also accepted valid ones are (e1-x,o1-x,a1-x)
           eg. tataru e6s or tataru e6n or tataru e6, with a savage check
           The savage_only parameter takes arguments like yes/no
           -------------------------------------------------------------
           tataru el "encounter name"
           tataru el y "encounter name"
           tataru el "encounter name" @User or user_id or name
           tataru el "encounter name" World Forename Surname
        """
        await self.get_encounter_logs(ctx, savage_only, name, character)

    @encounterlogs.group(name="best", aliases=["b"], invoke_without_command=True)
    async def best_encounter_logs(self, ctx, savage_only: typing.Optional[bool],
                                  name, *, character: typing.Optional[typing.Union[discord.User, str]] = None):
        """Displays best encounter parse
           The savage_only parameter takes arguments like yes/no
           -------------------------------------------------------------
           tataru el best "Cloud of Darkness"
           tataru el best y "Cloud of Darkness"
           tataru el best @User or user_id or name "Cloud of Darkness"
           tataru el best World Forename Surname "Cloud of Darkness"
        """
        await self.get_encounter_logs(ctx, savage_only, name, character, True)

    @best_encounter_logs.command(name="adps")
    async def best_encounter_adps(self, ctx, savage_only: typing.Optional[bool],
                                  name, *, character: typing.Optional[typing.Union[discord.User, str]] = None):
        """sets the metric for rankings to adps
           The savage_only parameter takes arguments like yes/no
           -------------------------------------------------------------
           tataru el best adps "Cloud of Darkness"
           tataru el best adps y "Cloud of Darkness"
           tataru el best adps @User or user_id or name "Cloud of Darkness"
           tataru el best adps World Forename Surname "Cloud of Darkness"
        """
        await self.invoke_best(ctx, "encounterlogs best", savage_only, name, character=character)

    @commands.is_owner()
    @commands.command(aliases=["scz"])
    async def set_current_zone(self, ctx, zone_id: int):
        """
        set the current raid zone for the fflogs cog
        """

        check = await ctx.db.fetchval("SELECT * FROM zone where id = $1", zone_id)

        if not check:
            return await ctx.send(f"> A zone with id {zone_id}, does not exist.")

        self.current_tier_id = zone_id
        await ctx.send("> Successfully updated the zone id :white_check_mark:.")

    @commands.is_owner()
    @commands.command()
    async def add_zones(self, ctx):
        """Add zones and encounters to the database
        -------------------------------------------------------------
        tataru add_zones"""

        query = """
                query {
                  worldData{
                   expansions{
                    zones {
                     difficulties{id, name}
                     id
                     name
                     frozen
                     brackets {
                     min
                     max
                     }
                     encounters {
                      id
                      name
                     }
                    }
                   }
                  }
               }      
        """
        async with ctx.typing():
            token = await self.api.get_bearer_token()
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token['access_token']}"
            }

            data = await self.api.client.execute_async(query=query, headers=headers)

            for expansion in data["data"]["worldData"]["expansions"]:
                for zone in expansion["zones"]:

                    min_b = zone["brackets"]["min"]

                    async with ctx.acquire():
                        expansion_name = await ctx.db.fetchval("SELECT name from expansion where patch_number = $1",
                                                               min_b)

                        await ctx.db.execute("""INSERT INTO "zone" (id,name,frozen,expansion_name)
                                                VALUES ($1,$2,$3,$4)
                                                ON CONFLICT (id) DO UPDATE
                                                SET id = $1, name = $2, frozen = $3, expansion_name = $4""",
                                             zone["id"], zone["name"], zone["frozen"], expansion_name)

                        for diff in zone["difficulties"]:
                            await ctx.db.execute("""INSERT INTO difficulties (diff_id, name, zone_id)
                                                    VALUES ($1, $2, $3)""",
                                                 diff["id"], diff["name"], zone["id"])

                        await ctx.db.execute("""INSERT INTO bracket (min, expansion_name, max)
                                                VALUES ($1,$2,$3)
                                                ON CONFLICT (min) DO UPDATE
                                                SET min = $1, expansion_name = $2, max = $3""",
                                             min_b, expansion_name, zone["brackets"]["max"])

                        for encounter in zone["encounters"]:
                            await ctx.db.execute("""INSERT INTO encounter (id,name,expansion_name)
                                                    VALUES ($1,$2,$3)
                                                    ON CONFLICT (id) DO UPDATE 
                                                    SET id = $1, name = $2, expansion_name = $3""",
                                                 encounter["id"], encounter["name"], expansion_name)

            await ctx.send("successfully added/updated zones and encounters :white_check_mark:")

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

    @commands.group(aliases=["sa"], invoke_without_command=True)
    @commands.is_owner()
    async def set_alias(self, ctx, alias, *, encounter):
        """
        the main command for setting  aliases by default sets aliases for raid encounters
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

    @set_alias.command(aliases=["ult"])
    async def ultimate(self, ctx, alias, *, encounter):
        """
        set the aliases for an ultimate raid
        """

        if len(alias) < 2 or len(alias) > 4:
            return await ctx.send("Invalid alias was passed.")

        async with ctx.acquire():
            data = await ctx.db.fetchrow("SELECT * from encounter where lower(name) like $1", encounter.lower() + "%")

            if not data:
                return await ctx.send(f"> search failed for {encounter}")

            zone = await ctx.db.fetchval("SELECT name from zone where id = $1", data["zone_id"])

            if "Ultimates" not in zone:
                return await ctx.send("passed in an encounter that is not an ultimate.")

            check = await ctx.db.execute("UPDATE encounter SET alias_n = $1, alias_s = alias_n where id = $2",
                                         alias, data["id"])
            if check == "UPDATE 0":
                return await ctx.send("> update failed")

            await ctx.send(check)


def setup(bot):
    bot.add_cog(FFlogs(bot))
