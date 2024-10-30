import discord
from redbot.core import commands, Config, bank
from redbot.core.bot import Red
import random
import datetime
from collections import Counter

class Fishing(commands.Cog):
    """A fishing game cog for Redbot"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=123456789)
        self.config.register_user(inventory=[], rod="Basic Rod", total_value=0, daily_quest=None)
        self.fish_types = {
            "Common Fish": {"rarity": "common", "value": 10, "chance": 0.6},
            "Uncommon Fish": {"rarity": "uncommon", "value": 20, "chance": 0.25},
            "Rare Fish": {"rarity": "rare", "value": 50, "chance": 0.1},
            "Legendary Fish": {"rarity": "legendary", "value": 100, "chance": 0.05},
        }
        self.rod_upgrades = {
            "Basic Rod": {"chance": 0.0, "value_increase": 0},
            "Intermediate Rod": {"chance": 0.1, "value_increase": 5},
            "Advanced Rod": {"chance": 0.2, "value_increase": 10},
        }
        self.event_fish = ["Legendary Fish"]
        self.current_event = None

    @commands.command(name="fish")
    async def fish(self, ctx):
        """Go fishing and try to catch a fish!"""
        user = ctx.author
        catch = await self._catch_fish(user)

        if catch:
            fish_name = catch["name"]
            fish_value = catch["value"]
            await self._add_to_inventory(user, fish_name)
            await self._update_total_value(user, fish_value)
            await ctx.send(f"🎣 {user.mention} caught a {fish_name} worth {fish_value} coins!")
        else:
            await ctx.send(f"🎣 {user.mention} went fishing but didn't catch anything this time.")

    @commands.command(name="inventory")
    async def inventory(self, ctx):
        """Check your fishing inventory."""
        user = ctx.author
        inventory = await self.config.user(user).inventory()

        if inventory:
            fish_counts = Counter(inventory)
            inventory_str = "\n".join(f"- {fish} x {count}" for fish, count in fish_counts.items())
            await ctx.send(f"🎒 {user.mention}'s Inventory:\n{inventory_str}")
        else:
            await ctx.send(f"🎒 {user.mention}, your inventory is empty. Go catch some fish!")

    @commands.command(name="sellfish")
    async def sell_fish(self, ctx):
        """Sell all fish in your inventory for currency."""
        user = ctx.author
        inventory = await self.config.user(user).inventory()

        if not inventory:
            await ctx.send(f"💰 {user.mention}, you have no fish to sell.")
            return

        total_value = sum(self.fish_types[fish]["value"] for fish in inventory if fish in self.fish_types)
        await bank.deposit_credits(user, total_value)
        await self.config.user(user).inventory.set([])  # Clear inventory after selling

        await ctx.send(f"💰 {user.mention} sold all their fish for {total_value} coins!")

    @commands.command(name="upgrade")
    async def upgrade_rod(self, ctx, rod_name: str):
        """Upgrade your fishing rod to increase catch chances."""
        user = ctx.author
        current_rod = await self.config.user(user).rod()

        if rod_name not in self.rod_upgrades:
            await ctx.send(f"🚫 {user.mention}, that's not a valid rod name.")
            return
        
        if current_rod == rod_name:
            await ctx.send(f"🚫 {user.mention}, you already have the {rod_name}.")
            return
        
        await self.config.user(user).rod.set(rod_name)
        await ctx.send(f"🔧 {user.mention} upgraded to a {rod_name}!")

    @commands.command(name="fisherboard")
    async def fisherboard(self, ctx):
        """Show the fisherboard for fishing earnings."""
        fisherboard = {}
        for member in await self.config.all_users():
            total_value = member.get("total_value", 0)
            if total_value > 0:
                fisherboard[member["user"]] = total_value
        
        sorted_fisherboard = sorted(fisherboard.items(), key=lambda x: x[1], reverse=True)
        if not sorted_fisherboard:
            await ctx.send("📊 The fisherboard is empty.")
            return

        fisherboard_str = "\n".join(f"{ctx.guild.get_member(user_id).mention}: {value} coins" for user_id, value in sorted_fisherboard)
        await ctx.send(f"📊 Fishing Fisherboard:\n{fisherboard_str}")

    @commands.command(name="dailyquest")
    async def daily_quest(self, ctx):
        """Check or claim your daily fishing quest."""
        user = ctx.author
        last_quest = await self.config.user(user).daily_quest()

        if last_quest:
            last_quest = datetime.datetime.fromisoformat(last_quest)

        if last_quest and (datetime.datetime.now() - last_quest).days > 0:
            await self.config.user(user).daily_quest.set(datetime.datetime.now().isoformat())
            await ctx.send(f"🎯 {user.mention}, your new daily quest is to catch a **Legendary Fish**!")
        elif last_quest:
            await ctx.send(f"🎯 {user.mention}, you have already completed your daily quest. Come back tomorrow!")
        else:
            await self.config.user(user).daily_quest.set(datetime.datetime.now().isoformat())
            await ctx.send(f"🎯 {user.mention}, your new daily quest is to catch a **Legendary Fish**!")

    async def _catch_fish(self, user):
        """Determines the fish catch based on rarity chances."""
        roll = random.random()
        cumulative = 0.0
        rod = await self.config.user(user).rod()  # Corrected to be awaitable
        rod_bonus = self.rod_upgrades[rod]["chance"]

        for fish_name, fish_data in self.fish_types.items():
            cumulative += fish_data["chance"] + rod_bonus
            if roll < cumulative:
                return {"name": fish_name, "value": fish_data["value"] + self.rod_upgrades[rod]["value_increase"]}
        return None

    async def _add_to_inventory(self, user, fish_name):
        """Adds a fish to the user's inventory."""
        inventory = await self.config.user(user).inventory()
        inventory.append(fish_name)
        await self.config.user(user).inventory.set(inventory)

    async def _update_total_value(self, user, fish_value):
        """Updates the user's total value of fish caught."""
        current_total = await self.config.user(user).total_value()
        await self.config.user(user).total_value.set(current_total + fish_value)

# The setup function to load the cog
async def setup(bot: Red):
    bot.add_cog(Fishing(bot))
