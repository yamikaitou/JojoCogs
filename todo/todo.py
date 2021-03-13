"""
MIT License

Copyright (c) 2020-2021 Jojo#7711

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import asyncio
import logging
import typing

import discord
from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import box, pagify
from redbot.core.utils.predicates import MessagePredicate

from . import menus

log = logging.getLogger("red.JojoCogs.todo")

# f-strings cannot contain backslashes...
_new_line = "\n"
_config_structure = {
    "todos": [],
    "assign": {},
    "use_md": True,
    "detailed_pop": False,
    "use_embeds": True,
    "autosort": False,
    "reverse_sort": False,
    "completed": [],
    "replies": True,
    "combine_lists": False,
    "private": False,
}
_about = """ToDo is a cog designed by Jojo#7791 for keeping track of different tasks you need to do

It has a simple add, list, and complete to make sure your tasks get done!
"""
# This is... hard to read LOL
# Read at your own peril
_comic_link = "https://raw.githubusercontent.com/Just-Jojo/JojoCog-Assets/main/data/todo_comic.jpg"


def positive_int(arg: str) -> int:
    """Returns a positive int"""
    try:
        ret = int(arg)
    except ValueError:
        raise commands.BadArgument(f"{arg} is not a integer.")
    if ret <= 0:
        raise commands.BadArgument(f"{arg} is not a positive integer.")
    return ret


class ToDo(commands.Cog):
    """A simple, highly customizable todo list for Discord"""

    __version__ = "1.0.2"
    __author__ = [
        "Jojo",
    ]

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 19924714019, force_registration=True)
        self.config.register_user(**_config_structure)

    def format_help_for_context(self, ctx):
        """Thankie thankie Sinbad"""
        return (
            f"{super().format_help_for_context(ctx)}"
            f"\n\n__Current Version:__ `{self.__version__}`\n"
            f"__Author:__ `{', '.join(self.__author__)}`"
        )

    async def red_delete_data_for_user(
        self,
        requester: typing.Literal["discord", "owner", "user", "user_strict"],
        user_id: int,
    ) -> None:
        await self.config.user_from_id(user_id).clear()

    ### Setting commands ###

    @commands.group()
    async def todoset(self, ctx):
        """Base settings command for customizing todo lists"""
        pass  # Passing in subcommands isn't needed but okay

    @todoset.command()
    async def detailed(self, ctx, toggle: bool):
        """Log popped todo reminders"""
        await self._toggler(
            ctx=ctx,
            item="Detailed creation/removing",
            key="detailed_pop",
            toggle=toggle,
        )

    @todoset.command()
    async def md(self, ctx, toggle: bool):
        """Toggle whether or not the list should use markdown"""
        await self._toggler(
            ctx=ctx, item="Fancy todo listing", key="use_md", toggle=toggle
        )

    @todoset.command(name="embed")
    async def use_embeds(self, ctx, toggle: bool):
        """Toggle whether or not to use embeds for todo lists"""
        await self._toggler(
            ctx=ctx, item="Embedded todo listing", key="use_embeds", toggle=toggle
        )

    @todoset.command()
    async def autosort(self, ctx, toggle: bool):
        """Toggle if todos should be autosorted"""
        await self._toggler(ctx=ctx, item="Autosorting", key="autosort", toggle=toggle)

    @todoset.command()
    async def reply(self, ctx, toggle: bool):
        """Toggle replies"""
        await self._toggler(ctx=ctx, item="Replies", key="replies", toggle=toggle)

    @todoset.command()
    async def combine(self, ctx, toggle: bool):
        """Toggle if the completed list and the todo list should be combined"""
        await self._toggler(
            ctx=ctx, item="Combining lists", key="combine_lists", toggle=toggle
        )

    @todoset.command()
    async def private(self, ctx, toggle: bool):
        """Toggle if the todo lists should be DMd to you or not"""
        if toggle is False:
            if await self.config.user(ctx.author).private() is False:
                return await ctx.send("Public todo listing is already enabled!")
        try:
            if ctx.channel.permissions_for(ctx.me).add_reactions:
                await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
            else:
                await ctx.author.send(
                    "Testing if I can dm you. Apologies!", delete_after=5.0
                )
        except discord.Forbidden:
            await ctx.send("I can't dm you!'")
        else:
            await ctx.author.create_dm()
            await self._toggler(ctx, "Private listing", "private", toggle)

    async def _toggler(self, ctx: commands.Context, item: str, key: str, toggle: bool):
        toggled = "enabled!" if toggle else "disabled!"
        setting = await self.config.user(ctx.author).get_raw(key)
        if setting == toggle:
            await ctx.send(f"{item} is already {toggled}")
        else:
            await ctx.send(f"{item} is now {toggled}")
            await self.config.user(ctx.author).set_raw(key, value=toggle)

    @todoset.command()
    async def showsettings(self, ctx):
        """Show your todo settings"""
        conf = self.config.user(ctx.author)
        settings = {
            "Markdown": await conf.use_md(),
            "Embedded": await conf.use_embeds(),
            "Detailed": await conf.detailed_pop(),
            "Autosorting": await conf.autosort(),
            "Reverse sort": await conf.reverse_sort(),
            "Replies": await conf.replies(),
            "Combined lists": await conf.combine_lists(),
            "Private lists": await conf.private(),
        }
        embed = discord.Embed(
            title=f"{ctx.author.display_name}'s todo settings",
            colour=await ctx.embed_colour(),
        )
        for key, value in settings.items():
            embed.add_field(name=key, value=value, inline=True)
        await self.maybe_reply(ctx, embed=embed)

    ### Listing commands ###

    @commands.group()
    async def todo(self, ctx):
        """Base todo reminder command"""
        pass

    @todo.group(invoke_without_command=True)
    async def complete(self, ctx, *indexes: positive_int):
        """Complete todo reminders"""
        # Thanks to Blackie#0001 on Red for the idea
        # :D
        if not len(indexes):
            return await ctx.send_help(ctx.command)
        indexes = self.sort_lists(items=indexes)
        passes, fails = 0, 0
        completed = []
        async with ctx.typing():
            async with self.config.user(ctx.author).todos() as todos:
                for index in indexes:
                    try:
                        _ = todos.pop(index)
                    except IndexError:
                        fails += 1
                    else:
                        passes += 1
                        completed.append(_)
            # This stuff doesn't need to be in
            # the `async with` part
            msg = ""
            detailed = await self.config.user(ctx.author).detailed_pop()
            if passes:
                if detailed:
                    comp = [f"`{x}`" for x in completed]
                    msg += f"Completed {passes} todos:\n{', '.join(comp)}\n"
                else:
                    msg += f"Completed {passes} todos\n"
            if fails:
                msg += f"Failed to complete {fails} todos"
            if not msg:
                msg = "Hm, something went wrong"
        await self.maybe_reply(ctx, content=msg)
        async with self.config.user(ctx.author).completed() as complete:
            for item in completed:
                complete.append(item)
        # Call maybe sort here
        await self._maybe_auto_sort(ctx.author)

    @complete.command(name="list")
    async def complete_list(self, ctx):
        """List your completed todos!"""
        if len((completed := await self.config.user(ctx.author).completed())):
            md = await self.config.user(ctx.author).use_md()
            if not md:
                completed = await self.cross_lists(completed)
            completed = await self.number(completed)
            await self.page_logic(
                ctx,
                completed,
                "Completed Todo List",
            )
        else:
            await ctx.send("You don't have any completed todos yet!")

    @todo.command()
    async def add(self, ctx, *, todo: str):
        """Add a todo reminder!"""
        async with self.config.user(ctx.author).todos() as todos:
            todos.append(todo)
        if await self.config.user(ctx.author).detailed_pop():
            await ctx.send(f"Added this as a todo reminder!\n`{todo}`")
        else:
            await ctx.send("Added that todo reminder!")
        await self._maybe_auto_sort(author=ctx.author)

    async def _maybe_auto_sort(self, author: discord.Member):
        if not (autosort := await self.config.user(author).autosort()):
            return
        reversed = await self.config.user(author).reverse_sort()
        async with self.config.user(author).todos() as todos:
            todos.sort(reverse=reversed)  # Fairly simple
        async with self.config.user(author).completed() as completed:
            completed.sort(reverse=reversed)

    # `pop` because you're basically using list.pop(index) :p
    @todo.command(aliases=["del", "delete", "pop"])
    async def remove(self, ctx, *to_del: positive_int):
        """Remove a todo reminder"""
        async with ctx.typing():
            async with self.config.user(ctx.author).todos() as todos:
                if not len(todos):
                    return await ctx.send(
                        (
                            "You don't have any todos yet!"
                            f"\nUse `{ctx.clean_prefix}todo add <todo>` to add one!"
                        )
                    )
                if not len(to_del):
                    sending = await self.number(item=todos)
                    await self.page_logic(ctx, sending)
                    return
                else:
                    todo = self.sort_lists(to_del)
                popped_todos = []
                failed = []
                for to in todo:
                    try:
                        popped_todos.append(f"`{todos.pop(to)}`")
                    except IndexError:
                        await ctx.send("That was an invalid todo index!")
                        failed.append(f"`{to}`")
        msg = ""
        if await self.config.user(ctx.author).detailed_pop():
            if len(popped_todos) > 1:
                popped_todos = "\n".join(popped_todos)
                msg += f"Removed these todo reminders!\n{popped_todos}"
            # Since this is gonna be `1` I don't have to check for it
            elif len(popped_todos):
                popped_todos = popped_todos[0]
                msg += f"Removed this todo reminder!\n{popped_todos}"
            if len(failed) > 1:
                failed = "\n".join(failed)
                msg += f"\nCould not remove todos at these indexes\n{failed}"
            elif len(failed):
                failed = failed[0]
                msg += f"\nCould not remove a todo at this index\n{failed}"
        else:
            if len(popped_todos) > 1:
                msg += "Removed those todos!"
            elif len(popped_todos):
                msg += "Removed that todo!"
            if len(failed):
                msg += "\nFailed to remove some todos!"
        if not msg:
            msg = "Hm, something went wrong"
        await ctx.send(msg)
        await self._maybe_auto_sort(author=ctx.author)

    @todo.command(name="list")
    async def todo_list(self, ctx):
        """List your todo reminders"""
        todos = await self.config.user(ctx.author).todos()
        md = await self.config.user(ctx.author).use_md()
        if len(todos):
            todos = await self.number(item=todos)
            if await self.config.user(ctx.author).combine_lists():
                if not (comp := await self.config.user(ctx.author).completed()):
                    pass
                else:
                    if not md:
                        comp = await self.cross_lists(items=comp)
                    completed = await self.number(comp)
                    completed.insert(0, "❎ Completed todos")
                    todos.extend(completed)
            await self.page_logic(ctx, todos)
        else:
            await ctx.send(
                (
                    f"You don't have any todos!"
                    f"\nYou can add one using "
                    f"`{ctx.clean_prefix}todo add <todo>`"
                )
            )

    @todo.command()
    async def sort(self, ctx: commands.Context):
        """Sort your todos alphabetically"""
        if not len(await self.config.user(ctx.author).todos()):
            return await ctx.send("You don't have any todos!")
        msg = await ctx.send("Would you like to sort your todos in reverse?")
        try:
            pred = MessagePredicate.yes_or_no(ctx)
            result = await self.bot.wait_for("message", check=pred, timeout=15.0)
        except asyncio.TimeoutError:
            await ctx.send("Alright!")
            reverse = True
        else:
            reverse = pred.result
        await self.config.user(ctx.author).reverse_sort.set(reverse)
        async with self.config.user(ctx.author).todos() as items:
            items.sort(reverse=reverse)
            await ctx.send("Okay! I've sorted your todos!")
            await self.page_logic(
                ctx=ctx, things=[f"{num}. {i}" for num, i in enumerate(items, 1)]
            )

    @todo.command(
        aliases=[
            "move",
        ]
    )
    async def rearrange(self, ctx, index: positive_int, new_index: positive_int):
        """Rearrange a todo!"""
        index -= 1
        new_index -= 1
        async with self.config.user(ctx.author).todos() as items:
            if new_index > (leng := len(items)):
                new_index = leng - 1
            try:
                item = items.pop(index)
            except IndexError:
                await ctx.send("Hm, there doesn't seem to be a todo there")
            else:
                items.insert(new_index, item)
        await ctx.send(f"Moved todo reminder `{item}`")
        await self.config.user(ctx.author).autosort.set(False)

    @todo.command()
    async def show(self, ctx, index: positive_int):
        """Show a todo reminder by index!"""
        act_index = index - 1
        try:
            todo = await self.config.user(ctx.author).todos()[act_index]
        except IndexError:
            return await ctx.send("Hm, that doesn't seem to be a todo!")

        todo = f"{index}. {todo}"
        md = await self.config.user(ctx.author).use_md()
        embedded = await self.config.user(ctx.author).use_embeds()

        if md:
            todo = box(todo, "md")
        if embedded:
            sending = discord.Embed(
                title=f"{ctx.author.name}'s ToDos",
                description=todo,
                colour=await ctx.embed_colour(),
            )
            sending.set_footer(text="ToDo list")
            key = "embed"
        else:
            sending = todo
            key = "content"
        channel = await self.get_destination(ctx)
        await channel.send(**{key: sending})

    @todo.command()
    async def explain(self, ctx, comic: bool = False):
        """Explain what a todo is and why this cog exists!"""
        if comic:
            if await ctx.embed_requested():
                embed = discord.Embed(
                    title="About ToDo", colour=await ctx.embed_colour()
                )
                embed.set_footer(text="Jojo's ToDo Cog")
                embed.set_image(url=_comic_link)
                kwargs = {"embed": embed}
            else:
                kwargs = {"content": _comic_link}
            await ctx.send(**kwargs)
        else:
            await self.maybe_send_embed(
                ctx=ctx, message=_about, title="About ToDo", footer="Jojo's Todo Cog"
            )

    @todo.command()
    async def version(self, ctx):
        """Check what version ToDo is on!"""
        title = "ToDo Version"
        description = f"Todo, a {self.description[1:]}\n**Author**: {', '.join(self.__author__)}\n**Current Version**: {self.__version__}"
        await self.maybe_send_embed(ctx, description, title)

    ### Utilities ###

    async def maybe_send_embed(
        self, ctx: commands.Context, message: str, title: str = None, footer: str = None
    ) -> discord.Message:
        if await ctx.embed_requested():
            embed = discord.Embed(
                title=title, description=message, colour=await ctx.embed_color()
            )
            if footer:
                embed.set_footer(text=footer)
            kwargs = {"embed": embed}
        else:
            if not title:
                title = ""
            if not footer:
                footer = ""
            kwargs = {"content": f"{title}\n\n{message}\n{footer}"}

        return await ctx.send(**kwargs)

    async def maybe_reply(
        self, ctx: commands.Context, content: str = None, embed: discord.Embed = None
    ) -> discord.Message:
        mreply = await self.config.user(ctx.author).replies()
        channel = await self.get_destination(ctx)
        kwargs = {"content": content, "embed": embed}
        if mreply:
            kwargs["mention_author"] = False
        return await channel.send(**kwargs)

    async def get_destination(self, ctx: commands.Context):
        if await self.config.user(ctx.author).private():
            return ctx.author.dm_channel
        return ctx.channel

    async def page_logic(
        self, ctx: commands.Context, things: list, title: str = "Todo List"
    ):
        things = "\n".join(things)
        use_md = await self.config.user(ctx.author).use_md()
        use_embeds = await self.config.user(ctx.author).use_embeds()
        menu = menus.TodoMenu(
            source=menus.TodoPages(
                data=list(pagify(things, page_length=400)),
                use_md=use_md,
                use_embeds=use_embeds,
                title=title,
            ),
            timeout=15.0,
            delete_message_after=False,
            clear_reactions_after=True,
        )
        channel = await self.get_destination(ctx)
        await menu.start(ctx=ctx, channel=channel)

    async def number(self, item: list) -> list:
        return [f"{num}. {act}" for num, act in enumerate(item, 1)]

    def sort_lists(self, items: typing.List[int]) -> list:
        items = [v - 1 for v in items]
        items.sort(reverse=True)
        return items

    async def cross_lists(self, items: list) -> list:
        return [f"~~{item}~~" for item in items]
