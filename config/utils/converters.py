import typing

import discord
from discord.ext import commands


# not releasing the connection to the pool to reuse in commands, in any of these converters


# might need this to use this alone as a converter in the future
class DiscordToCharacterConverter(commands.Converter):

    async def convert(self, ctx, argument: typing.Union[discord.User, None]):

        if not argument:
            argument = ctx.author

        data = await ctx.db.fetchrow("SELECT first_name, second_name, world_name "
                                     "as world from lodestone_user where user_id = $1"
                                     , argument.id)
        if data:
            return data
        raise commands.BadArgument(f"`{argument.name}` does not have a saved character.")


class CharacterAndWorldConverter(commands.Converter):
    async def convert(self, ctx, argument):

        await ctx.acquire()

        if isinstance(argument, str):
            args = argument.split(" ")

            check = await ctx.db.fetchval("SELECT name from world where LOWER(name) like $1", args[0].lower())

            if not check:
                raise commands.BadArgument(f"Invalid ffxiv world `{args[0]}` was passed.")

            if len(args) < 3:
                raise commands.BadArgument("character surname is a required argument that is missing.")

            # ensuring ffxiv naming conventions are met
            return {"world": args[0].capitalize(),
                    "first_name": args[1].lower().capitalize(),
                    "second_name": args[2].lower().capitalize()}

        return await DiscordToCharacterConverter().convert(ctx, argument)


def check_argument_against_alias_dict(argument, _dict, error_msg):

    if not argument:
        return argument

    argument = argument.lower()

    for k, v in _dict.items():
        if argument in v or argument == k:
            return k

    raise commands.BadArgument(error_msg)


def check_argument_against_dict(argument, _dict, error_msg):
    if not argument:
        return argument

    if argument.isnumeric():
        return argument

    argument = argument.lower()

    if argument in _dict:
        return _dict[argument]

    raise commands.BadArgument(error_msg.format(argument))


class GenderAliasesConverter(commands.Converter):
    async def convert(self, ctx, argument):
        genders = {"male": ["m"], "female": ["f"]}
        return check_argument_against_alias_dict(argument, genders, "invalid gender `{0}` was passed.")


class RaceAliasesConverter(commands.Converter):
    async def convert(self, ctx, argument):

        races = {"lalafell": ["potato", "drawf", "lal"],
                 "aura": ["lizzer", "lizzard", "liz", "au ra"],
                 "hyur": ["hume", "thighlander"],
                 "hrothgar": ["furry", "ronso"],
                 "elezen": ["elf", "giraffe"],
                 "roegadyn": ["roe", "galdjent"],
                 "viera": ["vii", "bunbun", "bunny"],
                 "miqote": ["catgirl", "cat", "uwukiteh", "miqo", "miqo'te"],
                 }

        return check_argument_against_alias_dict(argument, races, "invalid ffxiv race `{0}` was passed.")


class RaceConverter(commands.Converter):
    async def convert(self, ctx, argument):
        races = {"hyur": 1, "elezen": 2, "miqo'te": 3,
                 "lalafell": 4, "roegadyn": 5, "au ra": 6,
                 "viera": 7, "hrothgar": 8, "chocobo": 9,
                 "potato": 4, "lizard": 6, "bunny": 7,
                 "furry": 8, "lizzer": 6, "bunbun": 7,
                 "lala": 4, "roe": 5, "elf": 2, "dwarf": 4,
                 "viis": 7, "hume": 1, "drahn": 6, "galdjent": 5,
                 "ronso": 8, "choco": 9, "boco": 9, "bun": 7,
                 "cat": 3, "miqote": 3, "aura": 6, "miqo": 3,
                 "catgirl": 3, "uwukiteh": 3}

        return check_argument_against_dict(argument, races, "Invalid ffxiv race/(race id) `{0}` was passed.")


class JobConverter(commands.Converter):
    async def convert(self, ctx, argument):
        jobs = {"pld": 9, "war": 10, "drk": 11, "drg": 12,
                "mnk": 13, "nin": 14, "sam": 34, "brd": 15,
                "mch": 16, "blm": 17, "rdm": 45, "smn": 19,
                "whm": 20, "ast": 21, "blu": 36, "dnc": 37,
                "gnb": 38, "paladin": 9, "warrior": 10,
                "dark knight": 11, "dragoon": 12, "monk": 13,
                "ninja": 14, "samurai": 34, "bard": 15,
                "mechanic": 16, "black mage": 17, "red mage": 45,
                "summoner": 19, "white mage": 20, "astrologian": 21,
                "blue mage": 36, "dancer": 37, "gun breaker": 38}

        return check_argument_against_dict(argument, jobs, "Invalid ffxiv job/(job id) `{0}` was passed.")


class GenderConverter(commands.Converter):
    async def convert(self, ctx, argument):
        gender = {"m": 0, "f": 1, "male": 0, "female": 1}

        return check_argument_against_dict(argument, gender, "Invalid gender `{0}` was passed.")
