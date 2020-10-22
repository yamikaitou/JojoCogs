from redbot.core import commands, bank, Config, modlog
from redbot.core import checks
import discord
from .embed_maker import Embed


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 13814755994)
        self.config.register_guild(
            items={
                "coffee": 10,
                "scone": 15,
                "tea": 10
            },
            roles={}
        )
        self.config.register_user(items={})
        self.embed = Embed(self)

    def readable_dict(self, dictionary: dict) -> str:
        """Convert a dictionary into something a regular person could read"""
        x = []
        for key, item in dictionary.items():
            y = "{0}: {1}".format(key, item)
            x.append(y)
        return "\n".join(x)

    async def bank_utils(self, ctx: commands.Context, user: discord.Member = None):
        """Returns the name of the bank's currency and can optionally return the balance of a member

        Args:
            ctx (commands.Context): Needed for the guild to get the bank credit
            user (Member, optional): Optional to get the balance of a user. Defaults to None.

        Returns:
            str, int (optional)
        """
        name = await bank.get_currency_name(ctx.guild)
        if user is not None:
            balance = await bank.get_balance(ctx.author)
            return name, balance
        return name

    @commands.group()
    async def store(self, ctx):
        """Store commmands"""

    @store.command()
    @checks.admin()
    async def add(self, ctx, cost: int = 50, item: str = None):
        if item is None:
            return await ctx.send("Please name the item you would like to add")
        await self.config.guild(ctx.guild).set_raw(item, value=cost)

    @store.command(name="buy")
    async def _buy(self, ctx, item: str = None):
        """Purchase an item from the store"""
        if item is not None:
            try:
                cost = await self.config.guild(ctx.guild).items.get_raw(item)
            except KeyError:
                await ctx.send("I could not find that item!")
                return

            if await bank.can_spend(ctx.author, cost):
                try:
                    item_lists = await self.config.user(ctx.author).items.get_raw(item)
                except KeyError:
                    item_lists = 0
                item_lists += 1
                cur_name, old_bal = await self.bank_utils(ctx, ctx.author)
                await self.config.user(ctx.author).items.set_raw(item, value=item_lists)
                if item_lists != 1:
                    msg = "You bought a {0} for {1} {2}!\nYou have {3} {0}s!".format(
                        item, cost, cur_name, item_lists)
                else:
                    msg = "You bought a {0} for {1} {2}!\nYou have 1 {0}!".format(
                        item, cost, cur_name)

                await ctx.send(msg)
                await bank.set_balance(ctx.author, old_bal - cost)
            else:
                await ctx.send("You can't buy {0}! You don't have enough {1} to buy it!".format(item, cur_name))
        else:
            item_list = await self.config.guild(ctx.guild).items.get_raw()
            item_list_embed = self.embed.embed_make(ctx, title="{0}'s Store".format(
                ctx.guild.name), description="Item listing", footer="Store | Ye Ole Store")

            for key, item in item_list.items():
                item_list_embed.add_field(name=key, inline=False, value=item)
            await ctx.send(embed=item_list_embed)

    @commands.command()
    @commands.is_owner()
    async def check(self, ctx, item: str = "coffee"):
        try:
            _item = await self.config.user(ctx.author).items.get_raw(item)
            await ctx.send(_item)
        except KeyError:
            await ctx.send("That item doesn't exist for you.")

    @commands.command(name="storeclear")
    @checks.is_owner()
    async def clear_store(self, ctx):
        """Clear out the store of items"""
        await self.config.clear()
        await ctx.send("Cleared the store")

    @commands.command()
    async def use(self, ctx, item: str):
        try:
            check_item = await self.config.user(ctx.author).items.get_raw(item)
            if check_item > 0:
                check_item -= 1
                await self.config.user(ctx.author).items.set_raw(item, value=check_item)
                await ctx.send("You used a {0}!\nYou have {1} remaining!".format(item, check_item))
            else:
                await ctx.send("You do not have that item!")
        except KeyError:
            await ctx.send("You could not use that item!")

    @commands.command()
    async def items(self, ctx):
        items_ = await self.config.user(ctx.author).items.get_raw()
        if items_:
            embed = self.embed.embed_make(
                ctx, title="{0.display_name}'s Items".format(ctx.author), description=self.readable_dict(items_)
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("You do not have any items!\nYou can buy some using `[p]store buy`")

    @commands.command(name="paidkick")
    @bank.cost(5000)
    async def kick_fun(self, ctx, user: discord.Member = None):
        if user is None:
            raise bank.AbortPurchase
        if user is ctx.author:
            await ctx.send("I cannot let you do that. Self-harm is bad :pensive:")
            raise bank.AbortPurchase
        try:
            await ctx.guild.kick(user)
            _ = await modlog.create_case(
                ctx.bot, ctx.guild, ctx.message.created_at, action_type="kick",
                user=user, moderator=ctx.author, reason="{0.display_name} has redeemed a kick command and used it on {1}!".format(
                    ctx.author, user)
            )
            await ctx.send("Done. It was about time")
        except discord.Forbidden:
            await ctx.send("I could not kick that member!")
            raise bank.AbortPurchase

    @commands.group()
    async def role(self, ctx):
        """Base role command

        This allows you to buy certain roles for credits"""

    @role.command(name="add")
    @checks.admin()
    async def _add(self, ctx, role: discord.Role, cost: int = 3000):
        """Add a purchasable role"""
        await self.config.guild(ctx.guild).roles.set_raw(role, value=cost)
        await ctx.send("That role can now be bought for {}".format(cost))

    @role.comamnd(aliases=["del", ])
    async def remove(self, ctx, *, role):
        try:
            await self.config.guild(ctx.guild).roles.clear_raw(role)
            await ctx.send("Removed that role from the store")
        except KeyError:
            await ctx.send("I couldn't find that role")

    @role.command()
    async def buy(self, ctx, *, role: discord.Role):
        """Buy a role with credits"""
        try:
            role_cost = await self.config.guild(ctx.guild).roles.get_raw(role)
        except KeyError:
            return await ctx.send("I could not find that role!")

        if await bank.can_spend(ctx.author, role_cost):
            try:
                await ctx.author.add_roles(role)
                await bank.withdraw_credits(ctx.author, role_cost)
                await ctx.send("You have sucessfully bought that role!")
            except discord.Forbidden:
                await ctx.send("I could not attach that role!")
