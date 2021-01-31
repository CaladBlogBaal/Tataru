import discord

from discord.ext import menus


class SearchSource(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=10)

    async def format_page(self, menu, entries):
        embed = discord.Embed(title=f"Results - {len(self.entries)}",
                              color=0x00dcff)
        embed.description = "\n".join(entries)
        embed.set_footer(text=f"page {menu.current_page + 1} /{self.get_max_pages()}")
        return embed


class ParseSource(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=10)

    async def format_page(self, menu, entries):
        embed = discord.Embed(title=entries[0][0], url=entries[0][1],
                              color=0x00dcff)
        embed.description = f"".join(t[3] for t in entries)

        # for entry in entries:
        #    embed.add_field(name=u"\u200B", value=entry[3])
        embed.set_footer(text=f"page {menu.current_page + 1} /{self.get_max_pages()}")
        return embed


class GamerScapeSource(menus.ListPageSource):
    def __init__(self, model, data):
        self.item = model
        super().__init__(data, per_page=10)

    async def format_page(self, menu, entries):
        embed = discord.Embed(title=f"Image File names for `{self.item}`",
                              color=0x00dcff,
                              )
        embed.description = "\n".join(f"{name.replace('_', ' ')}" for name in entries)
        embed.description = "```\n" + embed.description + "\n```"
        embed.set_footer(text=f"page {menu.current_page + 1} /{self.get_max_pages()}")
        return embed


class GSImageFindSource(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=1)

    @staticmethod
    def get_url(entry, key):
        try:

            return entry[key]

        except KeyError:

            return entry["description_url"]

    async def format_page(self, menu, entry):
        embed = discord.Embed(title=entry["title"], url=self.get_url(entry, "descriptionurl"),
                              color=0x00dcff, description=f"[{entry['name']}]({entry['url']})")
        embed.set_image(url=entry["url"])
        embed.set_footer(text=f"page {menu.current_page + 1} /{self.get_max_pages()}")
        return embed


class GSSearch(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=1)

    async def format_page(self, menu, page):
        return page


class MirapiSource(menus.ListPageSource):
    def __init__(self, data, params, max_pages):
        self.params = params
        self.max_pages = max_pages
        self.current_glam_id = None
        super().__init__(data, per_page=1)

    async def format_page(self, menu, page):
        icon_url = "https://mirapri.com//assets/favicon-cca0445e9d3c8639927bff3cdbeee0cfbad125a9407df7eb690a6c3842a2d4a7.ico"
        embed = discord.Embed(title=page[1], url=f"https://mirapri.com//{page[0]}", colour=0x00dcff)
        embed.set_image(url=page[2])
        embed.set_author(name="MIRAPRI SNAP",
                         icon_url=icon_url)
        embed.set_footer(text=f"page {menu.page} - result {menu.current_page + 1}/{self.get_max_pages()}")
        return embed
