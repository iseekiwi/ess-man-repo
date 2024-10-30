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
        self.config.register_user(
            inventory=[],
            rod="Basic Rod",
            total_value=0,
            daily_quest=None,
            bait={},  # Register bait inventory as a dictionary
        )
        self.fish_types = {
            "Common Fish": {"rarity": "common", "value": 10, "chance": 0.6},
            "Uncommon Fish": {"rarity": "uncommon", "value": 20, "chance": 0.25},
            "Rare Fish": {"rarity": "rare", "value": 50, "chance": 0.1},
            "Legendary Fish": {"rarity": "legendary", "value": 100, "chance": 0.05},
        }
        self.rod_upgrades = {
            "Basic Rod": {"chance": 0.0, "value_increase": 0, "cost": 0},
            "Intermediate Rod": {"chance": 0.1, "value_increase": 5, "cost": 100},
            "Advanced Rod": {"chance": 0.2, "value_increase": 10, "cost": 200},
        }
        self.bait_types = {
            "Worm": {"value": 1, "catch_bonus": 0.1, "cost": 10},
            "Shrimp": {"value": 2, "catch_bonus": 0.2, "cost": 20},
            "Cricket": {"value": 3, "catch_bonus": 0.3, "cost": 30},
        }

    @commands.command(name="fish")
    async def fish(self, ctx):
        """Go fishing and try to catch a fish!"""
        user = ctx.author
        bait = await self.config.user(user).bait()  # Get user's bait inventory

        # Check if user has any bait
        if not bait or sum(bait.values()) == 0:
            await ctx.send(f"🚫 {user.name}, you need bait to fish! Use `!shop` to purchase some.")
            return

        # Select a bait type (for this example, we'll just use the first available bait)
        bait_type = next((bait_name for bait_name in bait if bait[bait_name] > 0), None)

        # Catch fish
        catch = await self._catch_fish(user, bait_type)

        # Use one bait item
        if bait_type:
            bait[bait_type] -= 1
            if bait[bait_type] <= 0:
                del bait[bait_type]
            await self.config.user(user).bait.set(bait)  # Update user's bait inventory

        if catch:
            fish_name = catch["name"]
            fish_value = catch["value"]
            await self._add_to_inventory(user, fish_name)
            await self._update_total_value(user, fish_value)
            await ctx.send(f"🎣 {user.name} caught a {fish_name} worth {fish_value} coins using {bait_type}!")
        else:
            await ctx.send(f"🎣 {user.name} went fishing but didn't catch anything this time.")

    @commands.command(name="shop")
    async def shop(self, ctx):
        """View the fishing shop to purchase bait and upgrades."""
        shop_items = []
        
        # Bait items
        for bait_name, bait_info in self.bait_types.items():
            shop_items.append(f"{bait_name}: {bait_info['cost']} coins (Catch bonus: +{bait_info['catch_bonus'] * 100}%)")

        # Rod upgrades
        for rod_name, rod_info in self.rod_upgrades.items():
            shop_items.append(f"{rod_name}: {rod_info['cost']} coins (Chance increase: +{rod_info['chance'] * 100}%)")

        shop_list = "\n".join(shop_items)
        await ctx.send(f"🛒 Fishing Shop:\n{shop_list}")

    @commands.command(name="buybait")
    async def buy_bait(self, ctx, bait_type: str, amount: int):
        """Purchase bait from the shop."""
        user = ctx.author

        if bait_type not in self.bait_types:
            await ctx.send(f"🚫 {user.name}, that's not a valid bait type.")
            return
        
        cost = self.bait_types[bait_type]["cost"] * amount
        user_balance = await bank.get_balance(user)

        if user_balance < cost:
            await ctx.send(f"🚫 {user.name}, you don't have enough coins to buy {amount} {bait_type}(s).")
            return

        # Deduct the cost from user's balance and add bait to inventory
        await bank.withdraw_credits(user, cost)

        bait = await self.config.user(user).bait()
        bait[bait_type] = bait.get(bait_type, 0) + amount
        await self.config.user(user).bait.set(bait)  # Update user's bait inventory
        await ctx.send(f"🎣 {user.name} purchased {amount} {bait_type}(s) for {cost} coins!")

    @commands.command(name="buyrod")
    async def buy_rod(self, ctx, rod_name: str):
        """Purchase a rod upgrade from the shop."""
        user = ctx.author
        if rod_name not in self.rod_upgrades:
            await ctx.send(f"🚫 {user.name}, that's not a valid rod name.")
            return
        
        cost = self.rod_upgrades[rod_name]["cost"]
        user_balance = await bank.get_balance(user)

        if user_balance < cost:
            await ctx.send(f"🚫 {user.name}, you don't have enough coins to buy the {rod_name}.")
            return
        
        # Deduct the cost from user's balance and set the new rod
        await bank.withdraw_credits(user, cost)
        await self.config.user(user).rod.set(rod_name)
        await ctx.send(f"🔧 {user.name} purchased the {rod_name} for {cost} coins!")

    @commands.command(name="inventory")
    async def inventory(self, ctx):
        """Check your fishing inventory."""
        user = ctx.author
        inventory = await self.config.user(user).inventory()
        bait = await self.config.user(user).bait()

        inventory_str = "\n".join(f"- {fish} x {count}" for fish, count in Counter(inventory).items()) if inventory else "empty"
        bait_str = "\n".join(f"- {bait_name} x {amount}" for bait_name, amount in bait.items()) if bait else "no bait"

        await ctx.send(f"🎒 {user.name}'s Inventory:\nFish:\n{inventory_str}\nBait:\n{bait_str}")

    @commands.command(name="sellfish")
    async def sell_fish(self, ctx):
        """Sell all fish in your inventory for currency."""
        user = ctx.author
        inventory = await self.config.user(user).inventory()

        if not inventory:
            await ctx.send(f"💰 {user.name}, you have no fish to sell.")
            return

        total_value = sum(self.fish_types[fish]["value"] for fish in inventory if fish in self.fish_types)
        await bank.deposit_credits(user, total_value)
        await self.config.user(user).inventory.set([])  # Clear inventory after selling

        await ctx.send(f"💰 {user.name} sold all their fish for {total_value} coins!")

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
            await ctx.send(f"🎯 {user.name}, your new daily quest is to catch a **Legendary Fish**!")
        elif last_quest:
            await ctx.send(f"🎯 {user.name}, you have already completed your daily quest. Come back tomorrow!")
        else:
            await self.config.user(user).daily_quest.set(datetime.datetime.now().isoformat())
            await ctx.send(f"🎯 {user.name}, your new daily quest is to catch a **Legendary Fish**!")

    async def _catch_fish(self, user, bait_type):
        """Determines the fish catch based on rarity chances, including bait bonuses."""
        roll = random.random()
        cumulative = 0.0
        rod = await self.config.user(user).rod()  # Corrected to be awaitable
        rod_bonus = self.rod_upgrades[rod]["chance"]
        bait_bonus = self.bait_types[bait_type]["catch_bonus"] if bait_type and bait_type in self.bait_types else 0

        for fish_name, fish_data in self.fish_types.items():
            cumulative += fish_data["chance"] + rod_bonus + bait_bonus
            if roll < cumulative:
                return {"name": fish_name, "value": fish_data["value"] + self.rod_upgrades[rod]["value_increase"]}
        return None

    async def _add_to_inventory(self, user, fish_name):
        """Adds a fish to the user's inventory."""
        inventory = await self.config.user(user).inventory()
        inventory.append(fish_name)
        await self.config.user(user).inventory.set(inventory)

    async def _update_total_value(self, user, value):
        """Updates the user's total value of caught fish."""
        total_value = await self.config.user(user).total_value()
        total_value += value
        await self.config.user(user).total_value.set(total_value)

def setup(bot: Red):
    bot.add_cog(Fishing(bot))
