import traceback
import sys

import discord
from discord.ext import commands
from discord.ext.flags import ArgumentParsingError

from pyxivapi import XIVAPIForbidden

from config.utils.requests import RequestFailed


class ParsesNotFound(Exception):
    pass


class CharacterNotFound(Exception):
    pass


class CommandErrorHandler(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        owner_id = (await self.bot.application_info()).owner.id
        owner = ctx.bot.get_user(owner_id)

        if hasattr(ctx.command, 'on_error'):
            return

        if isinstance(error, commands.CommandInvokeError):

            error = error.original

        ignored = commands.CommandNotFound

        accounted_for = (commands.BotMissingPermissions, commands.MissingRequiredArgument,

                         commands.MissingPermissions, commands.CommandOnCooldown, commands.NoPrivateMessage,

                         commands.NotOwner, commands.CommandNotFound, commands.TooManyArguments,

                         commands.DisabledCommand, commands.BadArgument, commands.BadUnionArgument,

                         commands.UnexpectedQuoteError,

                         RequestFailed, ArgumentParsingError, XIVAPIForbidden, CharacterNotFound,

                         ParsesNotFound)

        error = getattr(error, 'original', error)

        if isinstance(error, discord.errors.ClientException):
            return

        if isinstance(error, ignored):

            return

        if isinstance(error, accounted_for):

            return await ctx.send(f"> :no_entry: | {error}", delete_after=10)

        accounted_for += (commands.CheckFailure,)

        error_messsage = traceback.format_exception(type(error), error, error.__traceback__)
        error_messsage = "".join(c for c in error_messsage)

        try:

            if not isinstance(error, accounted_for):

                await ctx.send(f"The command `{ctx.command.name}` has ran into an unexpected error, "
                               f"the bot owner has been notified.", delete_after=8)

                await owner.send("```Python\n" + error_messsage + "```")

        except discord.errors.HTTPException:

            pass

        else:

            print("Ignoring exception in command {}:".format(ctx.command), file=sys.stderr)

            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


def setup(bot):

    bot.add_cog(CommandErrorHandler(bot))
