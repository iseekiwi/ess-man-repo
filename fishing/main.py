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
            purchased_rods={}  # Track purchased rods
        )
        self.config.register_global(
            bait_stock={"Worm": 10, "Shrimp": 10, "Cricket": 10}  # Daily stock for each bait type
        )
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
        self.bait_types = {
            "Worm": {"value": 1, "catch_bonus": 0.1},
            "Shrimp": {"value": 2, "catch_bonus": 0.2},
            "Cricket": {"value": 3, "catch_bonus": 0.3},
        }

    @commands.command(name="fish")
    async def fish(self, ctx):
        """Go fishing and try to catch a fish!"""
        user = ctx.author
        bait = await self.config.user(user).bait()  # Get user's bait inventory

        # Check if user has any bait
        if not bait or sum(bait.values()) == 0:
            await ctx.send(f"🚫 {user.name}, you need bait to fish! Visit the (!)shop to purchase some.")
            return

        # Select a bait type
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

    @commands.group(name="shop", invoke_without_command=True)
    async def shop(self, ctx):
        """Check the shop for available items."""
        shop_items = {
            "1": {"name": "Worm", "cost": 1},
            "2": {"name": "Shrimp", "cost": 2},
            "3": {"name": "Cricket", "cost": 3},
            "4": {"name": "Intermediate Rod", "cost": 50},
            "5": {"name": "Advanced Rod", "cost": 100},
        }

        bait_stock = await self.config.bait_stock.all()  # Get current bait stock
        shop_str = "🛒 **Shop:**\n" + "\n".join(
            f"**{index}.** {item['name']} - {item['cost']} coins (Stock: {bait_stock[item['name']]})"
            for index, item in shop_items.items()
        )
        await ctx.send(shop_str)

    @shop.command(name="buy")
    async def buy(self, ctx, item_index: int):
        """Buy an item from the shop by index."""
        user = ctx.author
        shop_items = {
            1: {"name": "Worm", "cost": 1},
            2: {"name": "Shrimp", "cost": 2},
            3: {"name": "Cricket", "cost": 3},
            4: {"name": "Intermediate Rod", "cost": 50},
            5: {"name": "Advanced Rod", "cost": 100},
        }

        if item_index not in shop_items:
            await ctx.send(f"🚫 {user.name}, that's not a valid item index.")
            return
        
        item = shop_items[item_index]
        bait_stock = await self.config.bait_stock()  # Get current bait stock

        # Check stock
        if item["name"] in bait_stock and bait_stock[item["name"]] <= 0:
            await ctx.send(f"🚫 {user.name}, the {item['name']} is out of stock.")
            return

        if item["name"] in ["Intermediate Rod", "Advanced Rod"]:
            purchased_rods = await self.config.user(user).purchased_rods()
            if item["name"] in purchased_rods:
                await ctx.send(f"🚫 {user.name}, you already purchased a {item['name']}.")
                return

        balance = await bank.get_balance(user)
        if balance < item["cost"]:
            await ctx.send(f"🚫 {user.name}, you don't have enough coins to buy a {item['name']}.")
            return

        await bank.withdraw_credits(user, item["cost"])

        # Update bait stock
        if item["name"] in bait_stock:
            bait_stock[item["name"]] -= 1
            await self.config.bait_stock.set(bait_stock)

        if item["name"] in ["Intermediate Rod", "Advanced Rod"]:
            purchased_rods[item["name"]] = True
            await self.config.user(user).purchased_rods.set(purchased_rods)  # Update purchased rods

        if item["name"] in self.bait_types:
            bait = await self.config.user(user).bait()
            bait[item["name"]] = bait.get(item["name"], 0) + 1
            await self.config.user(user).bait.set(bait)  # Update user's bait inventory

        await ctx.send(f"✅ {user.name} bought a {item['name']}!")

    @commands.command(name="inventory")
    async def inventory(self, ctx):
        """Check your fishing inventory."""
        user = ctx.author
        inventory = await self.config.user(user).inventory()
        bait = await self.config.user(user).bait()

        inventory_str = "\n".join(f"- {fish} x {count}" for fish, count in Counter(inventory).items()) if inventory else "empty"
        bait_str = "\n".join(f"- {bait_name} x {amount}" for bait_name, amount in bait.items()) if bait else "no bait"

        await ctx.send(f"🎒 **{user.name}'s Inventory:**\n**Fish:**\n{inventory_str}\n**Bait:**\n{bait_str}")

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
        await ctx.send(f"📊 Fisherboard:\n{fisherboard_str}")

    @commands.command(name="setbaitstock")
    @commands.is_owner()
    async def set_bait_stock(self, ctx, bait_name: str, amount: int):
        """Set the stock for a specific bait type."""
        bait_stock = await self.config.bait_stock()  # Get current bait stock

        if bait_name not in bait_stock:
            await ctx.send(f"🚫 {bait_name} is not a valid bait type.")
            return

        bait_stock[bait_name] = amount
        await self.config.bait_stock.set(bait_stock)  # Update the bait stock
        await ctx.send(f"✅ {bait_name} stock has been set to {amount}.")

    @commands.command(name="resetbaitstock")
    @commands.is_owner()
    async def reset_bait_stock(self, ctx):
        """Reset the bait stock to the default values."""
        default_stock = {"Worm": 10, "Shrimp": 10, "Cricket": 10}
        await self.config.bait_stock.set(default_stock)  # Reset the bait stock
        await ctx.send("✅ Bait stock has been reset to the default values.")

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
