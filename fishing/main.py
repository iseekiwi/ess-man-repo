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
            purchased_rods=[],  # Track purchased rods
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
            await ctx.send(f"🚫 {user.name}, you need bait to fish!")
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

    @commands.group(name="shop", invoke_without_command=True)
    async def shop(self, ctx):
        """View available items in the shop."""
        items = ["1. Worm - 1 coin", "2. Shrimp - 2 coins", "3. Cricket - 3 coins",
                 "4. Intermediate Rod - 50 coins", "5. Advanced Rod - 100 coins"]
        items_list = "\n".join(items)
        await ctx.send(f"🛒 **Shop Items:**\n{items_list}\nUse `!shop buy <index>` to purchase an item.")

    @shop.command(name="buy")
    async def shop_buy(self, ctx, index: int):
        """Buy an item from the shop by index."""
        user = ctx.author
        purchased_rods = await self.config.user(user).purchased_rods()
        user_balance = await bank.get_balance(user)

        # Check if the index is valid
        if index < 1 or index > 5:
            await ctx.send("🚫 Invalid item index. Please choose a valid item.")
            return

        # Determine the item being purchased
        if index == 1:  # Worm
            item_cost = self.bait_types["Worm"]["value"]
            item_name = "Worm"
        elif index == 2:  # Shrimp
            item_cost = self.bait_types["Shrimp"]["value"]
            item_name = "Shrimp"
        elif index == 3:  # Cricket
            item_cost = self.bait_types["Cricket"]["value"]
            item_name = "Cricket"
        elif index == 4:  # Intermediate Rod
            item_cost = 50
            item_name = "Intermediate Rod"
            if item_name in purchased_rods:
                await ctx.send(f"🚫 You already own a {item_name}.")
                return
            purchased_rods.append(item_name)
            await self.config.user(user).purchased_rods.set(purchased_rods)
        elif index == 5:  # Advanced Rod
            item_cost = 100
            item_name = "Advanced Rod"
            if item_name in purchased_rods:
                await ctx.send(f"🚫 You already own a {item_name}.")
                return
            purchased_rods.append(item_name)
            await self.config.user(user).purchased_rods.set(purchased_rods)
        else:
            await ctx.send("🚫 Invalid item index. Please choose a valid item.")
            return

        # Check if the user has enough currency
        if user_balance < item_cost:
            await ctx.send(f"🚫 {user.name}, you do not have enough coins to buy a {item_name}.")
            return

        # Deduct the cost and add the item to the user's inventory
        await bank.withdraw_credits(user, item_cost)

        if item_name in self.bait_types:
            bait = await self.config.user(user).bait()
            bait[item_name] = bait.get(item_name, 0) + 1
            await self.config.user(user).bait.set(bait)  # Update bait inventory

        await ctx.send(f"✅ {user.name} bought a {item_name}!")

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
        else:
            await ctx.send("🎯 You can claim a new daily quest after 24 hours.")

    async def _catch_fish(self, user, bait_type):
        """Determine if the user catches a fish and return its details."""
        bait_bonus = self.bait_types[bait_type]["catch_bonus"] if bait_type in self.bait_types else 0
        catch_chance = random.random() + bait_bonus  # Adjust chance based on bait
        for fish_name, fish_data in self.fish_types.items():
            if catch_chance <= fish_data["chance"]:
                return {"name": fish_name, "value": fish_data["value"]}
        return None

    async def _add_to_inventory(self, user, fish_name):
        """Add caught fish to the user's inventory."""
        inventory = await self.config.user(user).inventory()
        inventory.append(fish_name)
        await self.config.user(user).inventory.set(inventory)

    async def _update_total_value(self, user, fish_value):
        """Update the user's total value from fish sold."""
        total_value = await self.config.user(user).total_value()
        total_value += fish_value
        await self.config.user(user).total_value.set(total_value)

def setup(bot: Red):
    bot.add_cog(Fishing(bot))
