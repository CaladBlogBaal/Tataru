import discord
from discord.ext import commands
from config.config import EVENT_CHANNEL_ID


class Events(commands.Cog, command_attrs=dict(hidden=True)):
    """
    Bot event tracker
    """

    def __init__(self, bot):
        self.bot = bot

    async def embed(self, guild, title):
        embed = discord.Embed(title=title, color=0x00dcff)
        embed.add_field(name="Guild Name", value=f"`{guild.name}`", inline=False)
        embed.add_field(name="Guild ID", value=f"`{guild.id}`", inline=False)
        embed.add_field(name="Owner", value=f"`{guild.owner}` • `{guild.owner.id}`", inline=False)
        embed.add_field(name="Member Count", value=f"`{len(guild.members)}`", inline=False)
        embed.add_field(name="Bot Count", value=f"`{sum(m.bot for m in guild.members)}`", inline=False)
        channel = self.bot.get_channel(EVENT_CHANNEL_ID)
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.embed(guild, f"{guild.me.name} Joined a new guild")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        await self.embed(guild, f"{guild.me.name} Left a guild")


def setup(bot):
    bot.add_cog(Events(bot))

