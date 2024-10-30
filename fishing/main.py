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
        self.config.register_user(inventory=[], rod="Basic Rod", total_value=0, daily_quest=None, bait=0)
        self.fish_types = {
            "Common Fish": {"rarity": "common", "value": 10, "chance": 0.6},
            "Uncommon Fish": {"rarity": "uncommon", "value": 20, "chance": 0.25},
            "Rare Fish": {"rarity": "rare", "value": 50, "chance": 0.1},
            "Legendary Fish": {"rarity": "legendary", "value": 100, "chance": 0.05},
        }
        self.rod_upgrades = {
            "Basic Rod": {"chance": 0.0, "value_increase": 0, "cost": 0},
            "Intermediate Rod": {"chance": 0.1, "value_increase": 5, "cost": 50},
            "Advanced Rod": {"chance": 0.2, "value_increase": 10, "cost": 100},
        }
        self.bait_cost = 10  # Cost of each bait
        self.event_fish = ["Legendary Fish"]
        self.current_event = None

    @commands.command(name="fish")
    async def fish(self, ctx):
        """Go fishing and try to catch a fish!"""
        user = ctx.author
        bait = await self.config.user(user).bait()
        
        if bait <= 0:
            await ctx.send(f"🎣 {user.mention}, you need bait to fish! Buy some from the shop.")
            return
        
        catch = await self._catch_fish(user)

        if catch:
            fish_name = catch["name"]
            fish_value = catch["value"]
            await self._add_to_inventory(user, fish_name)
            await self._update_total_value(user, fish_value)
            await self.config.user(user).bait.set(bait - 1)  # Use 1 bait
            await ctx.send(f"🎣 {user.mention} caught a {fish_name} worth {fish_value} coins!")
        else:
            await ctx.send(f"🎣 {user.mention} went fishing but didn't catch anything this time.")

    @commands.command(name="shop")
    async def shop(self, ctx):
        """View the fishing shop."""
        user = ctx.author
        shop_items = "🛒 **Fishing Shop** 🛒\n\n"
        
        # Display bait for purchase
        shop_items += f"Bait (Cost: {self.bait_cost} coins each)\n"
        shop_items += "Upgrade Options:\n"
        
        for rod_name, rod_data in self.rod_upgrades.items():
            cost = rod_data["cost"]
            shop_items += f"- {rod_name} (Cost: {cost} coins)\n"

        await ctx.send(shop_items)

    @commands.command(name="buybait")
    async def buy_bait(self, ctx, amount: int):
        """Buy bait from the shop."""
        user = ctx.author
        cost = self.bait_cost * amount
        
        if cost <= 0:
            await ctx.send("🚫 You need to buy at least one bait.")
            return
        
        user_balance = await bank.get_balance(user)

        if user_balance < cost:
            await ctx.send(f"💰 {user.mention}, you don't have enough coins to buy {amount} bait.")
            return

        await bank.withdraw_credits(user, cost)
        current_bait = await self.config.user(user).bait()
        await self.config.user(user).bait.set(current_bait + amount)
        
        await ctx.send(f"🎉 {user.mention} bought {amount} bait for {cost} coins!")

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

        cost = self.rod_upgrades[rod_name]["cost"]
        user_balance = await bank.get_balance(user)

        if user_balance < cost:
            await ctx.send(f"💰 {user.mention}, you don't have enough coins to upgrade to {rod_name}.")
            return

        await bank.withdraw_credits(user, cost)
        await self.config.user(user).rod.set(rod_name)
        await ctx.send(f"🔧 {user.mention} upgraded to a {rod_name} for {cost} coins!")

    @commands.command(name="fisherboard")
    async def fisherboard(self, ctx):
        """Show the fisherboard for fishing earnings."""
        fisherboard = {}

        # Fetch all user configurations
        users = await self.config.all_users()  # Await here to get all user data

        for user_id, user_data in users.items():
            total_value = user_data.get("total_value", 0)
            if total_value > 0:
                fisherboard[user_id] = total_value  # Store user ID and total value

        sorted_fisherboard = sorted(fisherboard.items(), key=lambda x: x[1], reverse=True)

        if not sorted_fisherboard:
            await ctx.send("📊 The fisherboard is empty.")
            return

        fisherboard_str = "\n".join(f"{ctx.guild.get_member(user_id).name}: {value} coins" for user_id, value in sorted_fisherboard)
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
