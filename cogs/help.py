
import discord

from discord.ext import commands


class MyHelpCommand(commands.MinimalHelpCommand):

    def __init__(self, **options):

        super().__init__(**options, command_attrs=dict(help=""))

    def get_command_signature(self, command):

        return '**{0.clean_prefix}{1.qualified_name} {1.signature}**'.format(self, command)

    def get_opening_note(self):
        command_name = self.invoked_with

        string = """+ Use {0}{1} [command name/category name] for extra info.
+ Category names are case sensitive.
- < > refers to a required argument,
- [ ] is optional, do not type these.
- -- Denotes a flag for an argument eg. --flagname argument"""

        return f"```diff\n{string}```".format(self.clean_prefix, command_name)

    def get_ending_note(self):

        return "If you run into any issues/bugs support can be recieved at the" \
               " [support server](https://discord.gg/UXvy2Wevrp)."

    def add_subcommand_formatting(self, command):

        fmt = "→ **{0} {1}** \N{EN DASH} `{2}`" if command.short_doc else '→ **{0} {1}** \N{EN DASH} `no description`'

        self.paginator.add_line(fmt.format(command.full_parent_name, command.name, command.short_doc, ""))

    def add_bot_commands_formatting(self, commands, heading):

        if commands:
            self.paginator.add_line(f"__**{heading}**__:")
            command_list = []
            for c in commands:
                if len(c.name) > 10 and c.aliases:
                    command_list.append(f"{self.clean_prefix}{c.aliases[0]}")
                else:
                    command_list.append(f"{self.clean_prefix}{c.name}")

            command_list = " · ".join(command_list)
            self.paginator.add_line("%s" % command_list)

    def add_command_formatting(self, command):

        if command.description:
            self.paginator.add_line(command.description)

        signature = self.get_command_signature(command)

        if command.aliases:

            self.paginator.add_line(signature)

            self.add_aliases_formatting(command.aliases)

        else:

            self.paginator.add_line(signature)

        if command.help:

            try:

                self.paginator.add_line(f"```{command.help}\n```", empty=True)

            except RuntimeError:

                for line in command.help.splitlines():
                    self.paginator.add_line(line)

                self.paginator.add_line()

    async def send_pages(self):

        destination = self.get_destination()

        avatar_url = self.context.me.avatar_url_as(format="png")

        name = self.context.me.name

        for page in self.paginator.pages:
            embed = discord.Embed(description=page, color=self.context.bot.embed_colour)

            embed.set_author(name=name, icon_url=avatar_url)

            await destination.send(embed=embed)


class MyCog(commands.Cog, name="Help"):

    def __init__(self, bot):
        self.bot = bot

        self._original_help_command = bot.help_command

        bot.help_command = MyHelpCommand()

        bot.help_command.cog = self

    def cog_unload(self):
        self.bot.help_command = self._original_help_command


def setup(bot):
    bot.add_cog(MyCog(bot))

