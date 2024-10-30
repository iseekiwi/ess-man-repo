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
        shop_str = "🛒 **Shop:**\n"
    
        for index, item in shop_items.items():
            if item['name'] in bait_stock:
                stock_info = f"(Stock: {bait_stock[item['name']]})"
            else:
                stock_info = "(No stock info)"  # Or you can skip this line for rods

            shop_str += f"**{index}.** {item['name']} - {item['cost']} coins {stock_info}\n"

        await ctx.send(shop_str)

    @shop.command(name="buy")
    async def buy(self, ctx, item_index: int, amount: int = 1):
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
        if item["name"] in bait_stock and bait_stock[item["name"]] < amount:
            await ctx.send(f"🚫 {user.name}, not enough stock for {item['name']}. Available: {bait_stock[item['name']]}.")
            return

        if item["name"] in ["Intermediate Rod", "Advanced Rod"]:
            purchased_rods = await self.config.user(user).purchased_rods()
            if item["name"] in purchased_rods:
                await ctx.send(f"🚫 {user.name}, you already purchased a {item['name']}.")
                return

        total_cost = item["cost"] * amount
        balance = await bank.get_balance(user)
        if balance < total_cost:
            await ctx.send(f"🚫 {user.name}, you don't have enough coins to buy {amount} {item['name']}(s).")
            return

        await bank.withdraw_credits(user, total_cost)

        # Update bait stock
        if item["name"] in bait_stock:
            bait_stock[item["name"]] -= amount
            await self.config.bait_stock.set(bait_stock)

        if item["name"] in ["Intermediate Rod", "Advanced Rod"]:
            purchased_rods[item["name"]] = True
            await self.config.user(user).purchased_rods.set(purchased_rods)  # Update purchased rods

        if item["name"] in self.bait_types:
            bait = await self.config.user(user).bait()
            bait[item["name"]] = bait.get(item["name"], 0) + amount
            await self.config.user(user).bait.set(bait)  # Update user's bait inventory

        await ctx.send(f"✅ {user.name} bought {amount} {item['name']}(s)!")

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
                user = await self.bot.fetch_user(user_id)
                fisherboard[user.name] = total_value  # Store user name and total value

        sorted_fisherboard = sorted(fisherboard.items(), key=lambda x: x[1], reverse=True)

        if not sorted_fisherboard:
            await ctx.send("🏆 The fisherboard is empty!")
            return

        fisherboard_str = "\n".join(f"**{name}:** {value} coins" for name, value in sorted_fisherboard)
        await ctx.send(f"🏆 **Fisherboard:**\n{fisherboard_str}")
    
    @commands.command(name="dailyquest")
    async def daily_quest(self, ctx):
        """Get a daily quest."""
        user = ctx.author
        now = datetime.datetime.utcnow()

        # Check if user has a daily quest set
        daily_quest = await self.config.user(user).daily_quest()
        if daily_quest and daily_quest["date"] == now.date().isoformat():
            await ctx.send(f"🎯 {user.name}, you already have a daily quest: {daily_quest['task']}.")
            return

        # Set a new daily quest
        tasks = ["Catch 5 Common Fish", "Sell 2 Rare Fish", "Catch 1 Legendary Fish"]
        task = random.choice(tasks)
        await self.config.user(user).daily_quest.set({"task": task, "date": now.date().isoformat()})

        await ctx.send(f"🎯 {user.name}, your new daily quest is: **{task}**!")

    async def _catch_fish(self, user, bait_type):
        """Internal method to determine if a fish is caught and its type."""
        rod = await self.config.user(user).rod()
        chance = self.rod_upgrades[rod]["chance"] + self.bait_types[bait_type]["catch_bonus"]
        
        if random.random() < chance:
            fish = random.choices(
                list(self.fish_types.keys()),
                weights=[self.fish_types[f]["chance"] for f in self.fish_types],
                k=1
            )[0]
            return {"name": fish, "value": self.fish_types[fish]["value"]}
        return None

    async def _add_to_inventory(self, user, fish_name):
        """Add fish to user's inventory."""
        inventory = await self.config.user(user).inventory()
        inventory.append(fish_name)
        await self.config.user(user).inventory.set(inventory)

    async def _update_total_value(self, user, value):
        """Update total value of user's caught fish."""
        total_value = await self.config.user(user).total_value()
        total_value += value
        await self.config.user(user).total_value.set(total_value)

    @commands.group(name="manage", invoke_without_command=True)
    @commands.is_owner()
    async def manage(self, ctx):
        """Administrative management commands."""
        await ctx.send("Use `!manage add` or `!manage remove` followed by `fish`, `bait`, or `rod`.")

    @manage.command(name="add")
    @commands.is_owner()
    async def add_item(self, ctx, item_type: str, member: discord.Member, item_name: str, amount: int):
        """Add an item to a user's inventory."""
        if item_type.lower() == "fish":
            inventory = await self.config.user(member).inventory()
            for _ in range(amount):
                inventory.append(item_name)
            await self.config.user(member).inventory.set(inventory)
            await ctx.send(f"✅ Added {amount} {item_name}(s) to {member.name}'s inventory.")
        
        elif item_type.lower() == "bait":
            bait = await self.config.user(member).bait()
            bait[item_name] = bait.get(item_name, 0) + amount
            await self.config.user(member).bait.set(bait)
            await ctx.send(f"✅ Added {amount} {item_name}(s) to {member.name}'s bait inventory.")
        
        elif item_type.lower() == "rod":
            purchased_rods = await self.config.user(member).purchased_rods()
            purchased_rods[item_name] = True
            await self.config.user(member).purchased_rods.set(purchased_rods)
            await ctx.send(f"✅ Added {item_name} to {member.name}'s purchased rods.")
        
        else:
            await ctx.send("🚫 Invalid item type. Use `fish`, `bait`, or `rod`.")

    @manage.command(name="remove")
    @commands.is_owner()
    async def remove_item(self, ctx, item_type: str, member: discord.Member, item_name: str, amount: int):
        """Remove an item from a user's inventory."""
        if item_type.lower() == "fish":
            inventory = await self.config.user(member).inventory()
            fish_count = inventory.count(item_name)

            if fish_count < amount:
                await ctx.send(f"🚫 {member.name} does not have enough {item_name} to remove.")
                return

            for _ in range(amount):
                inventory.remove(item_name)
            await self.config.user(member).inventory.set(inventory)
            await ctx.send(f"✅ Removed {amount} {item_name}(s) from {member.name}'s inventory.")

        elif item_type.lower() == "bait":
            bait = await self.config.user(member).bait()
            if bait.get(item_name, 0) < amount:
                await ctx.send(f"🚫 {member.name} does not have enough {item_name} to remove.")
                return

            bait[item_name] -= amount
            if bait[item_name] <= 0:
                del bait[item_name]
            await self.config.user(member).bait.set(bait)
            await ctx.send(f"✅ Removed {amount} {item_name}(s) from {member.name}'s bait inventory.")
        
        elif item_type.lower() == "rod":
            purchased_rods = await self.config.user(member).purchased_rods()
            if item_name not in purchased_rods:
                await ctx.send(f"🚫 {member.name} does not have a {item_name} to remove.")
                return

            del purchased_rods[item_name]
            await self.config.user(member).purchased_rods.set(purchased_rods)
            await ctx.send(f"✅ Removed {item_name} from {member.name}'s purchased rods.")
        
        else:
            await ctx.send("🚫 Invalid item type. Use `fish`, `bait`, or `rod`.")

def setup(bot: Red):
    bot.add_cog(Fishing(bot))
