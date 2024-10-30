import discord
import asyncio
from redbot.core import commands, Config, bank
from redbot.core.bot import Red
import random
import datetime
from collections import Counter
from .data.fishing_data import (
    FISH_TYPES,
    ROD_TYPES,
    BAIT_TYPES,
    LOCATIONS,
    WEATHER_TYPES,
    TIME_EFFECTS,
    EVENTS
)

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
            bait={},
            purchased_rods={},
            equipped_bait=None,
            current_location="Pond",  # Added default location
            fish_caught=0,  # Added for rod requirements
            level=1  # Added for location/rod requirements
        )
        self.config.register_global(
            bait_stock={bait: data["daily_stock"] for bait, data in BAIT_TYPES.items()},
            current_weather="Sunny",
            active_events=[]
        )

        # Use imported data structures
        self.fish_types = FISH_TYPES
        self.rod_types = ROD_TYPES
        self.bait_types = BAIT_TYPES
        self.locations = LOCATIONS
        self.weather_types = WEATHER_TYPES
        self.time_effects = TIME_EFFECTS
        self.events = EVENTS

        # Start daily tasks
        self.bot.loop.create_task(self.daily_stock_reset())
        self.bot.loop.create_task(self.weather_change_task())

    async def weather_change_task(self):
        """Periodically change the weather."""
        while True:
            await asyncio.sleep(3600)  # Change weather every hour
            weather = random.choice(list(self.weather_types.keys()))
            await self.config.current_weather.set(weather)

    async def daily_stock_reset(self):
        """Reset the daily stock of shop items at midnight each day."""
        while True:
            now = datetime.datetime.now()
            midnight = datetime.datetime.combine(now.date(), datetime.time(0, 0)) + datetime.timedelta(days=1)
            seconds_until_midnight = (midnight - now).total_seconds()

            await asyncio.sleep(seconds_until_midnight)

            default_stock = {bait: data["daily_stock"] for bait, data in self.bait_types.items()}
            await self.config.bait_stock.set(default_stock)

    @commands.command(name="location")
    async def change_location(self, ctx, new_location: str):
        """Change your fishing location."""
        if new_location not in self.locations:
            available_locations = "\n".join(f"- {loc}" for loc in self.locations.keys())
            await ctx.send(f"🌍 Available locations:\n{available_locations}")
            return

        user = ctx.author
        user_data = await self.config.user(user).all()
        location_data = self.locations[new_location]

        # Check requirements
        if location_data["requirements"]:
            if user_data["level"] < location_data["requirements"]["level"]:
                await ctx.send(f"🚫 You need to be level {location_data['requirements']['level']} to fish here!")
                return
            if user_data["fish_caught"] < location_data["requirements"]["fish_caught"]:
                await ctx.send(f"🚫 You need to catch {location_data['requirements']['fish_caught']} fish first!")
                return

        await self.config.user(user).current_location.set(new_location)
        await ctx.send(f"🌍 {user.name} is now fishing at: {new_location}\n{location_data['description']}")

    @commands.command(name="equipbait")
    async def equip_bait(self, ctx, bait_name: str):
        """Equip a specific bait for fishing."""
        user = ctx.author
        bait = await self.config.user(user).bait()

        # Convert the bait_name to title case for standardization
        bait_name = bait_name.title()

        if bait_name not in self.bait_types:
            await ctx.send(f"🚫 {bait_name} is not a valid bait type.")
            return

        if bait_name not in bait or bait[bait_name] <= 0:
            await ctx.send(f"🚫 {user.name}, you don't have any {bait_name} to equip.")
            return

        await self.config.user(user).equipped_bait.set(bait_name)
        await ctx.send(f"✅ {user.name} equipped {bait_name}!")

    @commands.command(name="fish")
    async def fish(self, ctx):
        """Go fishing and try to catch a fish using a minigame!"""
        user = ctx.author
        user_data = await self.config.user(user).all()
        current_weather = await self.config.current_weather()

        if not user_data["equipped_bait"]:
            await ctx.send(f"🚫 {user.name}, you need to equip bait first! Use `!equipbait` to equip some bait.")
            return

        bait = user_data["bait"]
        equipped_bait = user_data["equipped_bait"]
        current_location = user_data["current_location"]

        if not bait or equipped_bait not in bait or bait[equipped_bait] <= 0:
            await ctx.send(f"🚫 {user.name}, you need bait to fish! Visit the `!shop` to purchase some.")
            return

        # Calculate time of day
        hour = datetime.datetime.now().hour
        time_of_day = "Dawn" if 5 <= hour < 7 else "Day" if 7 <= hour < 17 else "Dusk" if 17 <= hour < 19 else "Night"

        # Send the initial message
        fishing_message = await ctx.send("🎣 Fishing...")

        # Randomized delay between 3 to 7 seconds
        delay = random.uniform(3, 7)
        await asyncio.sleep(delay)

        # Define the acceptable keywords
        catch_keywords = ["catch", "grab", "snag", "hook", "reel"]
        selected_keyword = random.choice(catch_keywords)

        await fishing_message.edit(content=f"🎣 Quick! Type **{selected_keyword}** to catch the fish!")

        def check(m):
            return m.author == user and m.content.lower() == selected_keyword and m.channel == ctx.channel

        try:
            await self.bot.wait_for('message', check=check, timeout=5.0)
        except asyncio.TimeoutError:
            await ctx.send(f"⏰ {user.name}, you took too long! The fish got away!")
            return

        # Calculate catch with all modifiers
        catch = await self._catch_fish(user, equipped_bait, current_location, current_weather, time_of_day)

        # Update bait inventory
        bait[equipped_bait] -= 1
        if bait[equipped_bait] <= 0:
            del bait[equipped_bait]
        await self.config.user(user).bait.set(bait)

        if catch:
            fish_name = catch["name"]
            fish_value = catch["value"]
            variant = random.choice(self.fish_types[fish_name]["variants"])
            
            await self._add_to_inventory(user, fish_name)
            await self._update_total_value(user, fish_value)
            
            # Update fish_caught count
            fish_caught = user_data["fish_caught"] + 1
            await self.config.user(user).fish_caught.set(fish_caught)

            # Format message with all relevant info
            weather_effect = self.weather_types[current_weather]["description"]
            location_effect = self.locations[current_location]["description"]
            
            message = (
                f"🎣 {user.name} caught a {variant} ({fish_name}) worth {fish_value} coins!\n"
                f"Location: {current_location} - {location_effect}\n"
                f"Weather: {current_weather} - {weather_effect}"
            )
            await ctx.send(message)
        else:
            await ctx.send(f"🎣 {user.name} went fishing but didn't catch anything this time.")

    @commands.group(name="shop", invoke_without_command=True)
    async def shop(self, ctx):
        """Check the shop for available items."""
        bait_stock = await self.config.bait_stock()
        
        shop_str = "🛒 **Fishing Shop:**\n\n__Bait:__\n"
        
        # List bait
        for i, (bait_name, bait_data) in enumerate(self.bait_types.items(), 1):
            stock = bait_stock.get(bait_name, 0)
            shop_str += (f"**{i}.** {bait_name} - {bait_data['cost']} coins\n"
                        f"   Stock: {stock} | Bonus: +{bait_data['catch_bonus']*100}%\n"
                        f"   {bait_data['description']}\n")

        # List rods
        shop_str += "\n__Fishing Rods:__\n"
        for i, (rod_name, rod_data) in enumerate(self.rod_types.items(), len(self.bait_types) + 1):
            if rod_name != "Basic Rod":  # Don't show Basic Rod in shop
                req = rod_data['requirements']
                req_str = f"(Requires Level {req['level']}, {req['fish_caught']} fish caught)" if req else ""
                shop_str += (f"**{i}.** {rod_name} - {rod_data['cost']} coins\n"
                            f"   Bonus: +{rod_data['chance']*100}% catch rate\n"
                            f"   {rod_data['description']} {req_str}\n")

        await ctx.send(shop_str)

    @shop.command(name="buy")
    async def buy(self, ctx, item_index: int, amount: int = 1):
        """Buy an item from the shop by index."""
        user = ctx.author
        user_data = await self.config.user(user).all()

        # Create a combined list of purchasable items
        shop_items = list(self.bait_types.keys()) + [rod for rod in self.rod_types.keys() if rod != "Basic Rod"]
        
        if item_index < 1 or item_index > len(shop_items):
            await ctx.send("🚫 Invalid item index!")
            return

        item_name = shop_items[item_index - 1]

        # Handle bait purchase
        if item_name in self.bait_types:
            bait_data = self.bait_types[item_name]
            total_cost = bait_data["cost"] * amount
            
            # Check stock
            bait_stock = await self.config.bait_stock()
            if bait_stock[item_name] < amount:
                await ctx.send(f"🚫 Not enough {item_name} in stock! Available: {bait_stock[item_name]}")
                return

        # Handle rod purchase
        elif item_name in self.rod_types:
            rod_data = self.rod_types[item_name]
            total_cost = rod_data["cost"]
            amount = 1  # Can only buy one rod

            # Check requirements
            if rod_data["requirements"]:
                if user_data["level"] < rod_data["requirements"]["level"]:
                    await ctx.send(f"🚫 You need to be level {rod_data['requirements']['level']} to buy this rod!")
                    return
                if user_data["fish_caught"] < rod_data["requirements"]["fish_caught"]:
                    await ctx.send(f"🚫 You need to catch {rod_data['requirements']['fish_caught']} fish first!")
                    return

            # Check if already owned
            if item_name in user_data["purchased_rods"]:
                await ctx.send(f"🚫 You already own a {item_name}!")
                return

        # Check if user has enough money
        balance = await bank.get_balance(user)
        if balance < total_cost:
            await ctx.send(f"🚫 You don't have enough coins! Cost: {total_cost}")
            return

        # Process purchase
        await bank.withdraw_credits(user, total_cost)

        if item_name in self.bait_types:
            # Update stock
            bait_stock[item_name] -= amount
            await self.config.bait_stock.set(bait_stock)
            
            # Update user's bait
            user_bait = user_data["bait"]
            user_bait[item_name] = user_bait.get(item_name, 0) + amount
            await self.config.user(user).bait.set(user_bait)
        else:
            # Update user's rods
            purchased_rods = user_data["purchased_rods"]
            purchased_rods[item_name] = True
            await self.config.user(user).purchased_rods.set(purchased_rods)

        await ctx.send(f"✅ Purchased {amount} {item_name} for {total_cost} coins!")

    @commands.command(name="inventory")
    async def inventory(self, ctx):
        """Check your fishing inventory."""
        user = ctx.author
        user_data = await self.config.user(user).all()
        
        # Count fish by rarity
        fish_counts = Counter(user_data["inventory"])
        
        inventory_str = "🎒 **Your Inventory:**\n\n"
        
        # Display fish by rarity
        for rarity in ["common", "uncommon", "rare", "legendary"]:
            rarity_fish = [fish for fish in fish_counts.keys() 
                          if self.fish_types[fish]["rarity"] == rarity]
            if rarity_fish:
                inventory_str += f"__{rarity.title()} Fish:__\n"
                for fish in rarity_fish:
                    inventory_str += f"- {fish}: {fish_counts[fish]}\n"
                inventory_str += "\n"
        
        # Display bait
        bait = user_data["bait"]
        if bait:
            inventory_str += "__Bait:__\n"
            for bait_name, amount in bait.items():
                inventory_str += f"- {bait_name}: {amount}\n"
        else:
            inventory_str += "__Bait:__ None\n"
        
        # Display rods
        inventory_str += "\n__Fishing Rods:__\n"
        purchased_rods = user_data["purchased_rods"]
        current_rod = user_data["rod"]
        
        for rod_name in self.rod_types.keys():
            if rod_name == "Basic Rod" or rod_name in purchased_rods:
                equipped = "📌 " if rod_name == current_rod else "  "
                inventory_str += f"{equipped}{rod_name}\n"

        # Display stats
        inventory_str += f"\n__Stats:__\n"
        inventory_str += f"Total Fish Caught: {user_data['fish_caught']}\n"
        inventory_str += f"Level: {user_data['level']}\n"
        inventory_str += f"Current Location: {user_data['current_location']}\n"
        
        await ctx.send(inventory_str)

    @commands.command(name="sellfish")
    async def sell_fish(self, ctx):
        """Sell all fish in your inventory for currency."""
        user = ctx.author
        inventory = await self.config.user(user).inventory()

        if not inventory:
            await ctx.send(f"💰 {user.name}, you have no fish to sell.")
            return

        total_value = sum(self.fish_types[fish]["value"] for fish in inventory)
        
        # Add value multiplier from rod
        user_rod = await self.config.user(user).rod()
        value_increase = self.rod_types[user_rod]["value_increase"]
        total_value = int(total_value * (1 + value_increase / 100))

        await bank.deposit_credits(user, total_value)
        await self.config.user(user).inventory.set([])

        await ctx.send(f"💰 {user.name} sold all their fish for {total_value} coins!")

    @commands.command(name="fisherboard")
    async def fisherboard(self, ctx):
        """Show the fisherboard for fishing earnings."""
        all_users = await self.config.all_users()
        
        # Create list of (user_id, total_value, fish_caught) tuples
        fisher_stats = []
        for user_id, data in all_users.items():
            if data["total_value"] > 0:
                fisher_stats.append((user_id, data["total_value"], data["fish_caught"]))

        if not fisher_stats:
            await ctx.send("🏆 The fisherboard is empty!")
            return

        # Sort by total value
        fisher_stats.sort(key=lambda x: x[1], reverse=True)

        board_str = "🏆 **Fishing Leaderboard:**\n\n"
        for rank, (user_id, value, fish_caught) in enumerate(fisher_stats[:10], 1):
            user = await self.bot.fetch_user(user_id)
            board_str += f"{rank}. {user.name}\n"
            board_str += f"   💰 {value} coins earned\n"
            board_str += f"   🐟 {fish_caught} fish caught\n\n"

        await ctx.send(board_str)

    async def _catch_fish(self, user, bait_type, location, weather, time_of_day):
        """Calculate catch results with all modifiers."""
        user_data = await self.config.user(user).all()
        rod = user_data["rod"]
        
        # Base chance from rod
        base_chance = self.rod_types[rod]["chance"]
        
        # Add bait bonus
        bait_bonus = self.bait_types[bait_type]["catch_bonus"]
        
        # Add location modifier
        location_mods = self.locations[location]["fish_modifiers"]
        
        # Add weather bonus
        weather_bonus = self.weather_types[weather].get("catch_bonus", 0)
        
        # Add time of day bonus
        time_bonus = self.time_effects[time_of_day].get("catch_bonus", 0)
        
        # Calculate final chance
        final_chance = base_chance + bait_bonus + weather_bonus + time_bonus

        if random.random() < final_chance:
            # Select fish type with location modifiers
            weighted_fish = []
            weights = []
            
            for fish, data in self.fish_types.items():
                weight = data["chance"] * location_mods[fish]
                if weather in self.weather_types and "rare_bonus" in self.weather_types[weather] and data["rarity"] in ["rare", "legendary"]:
                    weight *= (1 + self.weather_types[weather]["rare_bonus"])
                weighted_fish.append(fish)
                weights.append(weight)

            caught_fish = random.choices(weighted_fish, weights=weights, k=1)[0]
            return {"name": caught_fish, "value": self.fish_types[caught_fish]["value"]}
            
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
        
        # Check for level up
        fish_caught = await self.config.user(user).fish_caught()
        new_level = max(1, fish_caught // 50)  # Level up every 50 fish
        await self.config.user(user).level.set(new_level)

    @commands.group(name="manage", invoke_without_command=True)
    @commands.is_owner()
    async def manage(self, ctx):
        """Administrative management commands."""
        await ctx.send("Use `!manage add` or `!manage remove` followed by `fish`, `bait`, or `rod`.")

    @manage.command(name="add")
    @commands.is_owner()
    async def add_item(self, ctx, item_type: str, member: discord.Member, item_name: str, amount: int = 1):
        """Add an item to a user's inventory."""
        if item_type.lower() == "fish":
            if item_name not in self.fish_types:
                await ctx.send("🚫 Invalid fish type!")
                return
            inventory = await self.config.user(member).inventory()
            for _ in range(amount):
                inventory.append(item_name)
            await self.config.user(member).inventory.set(inventory)
            await ctx.send(f"✅ Added {amount} {item_name}(s) to {member.name}'s inventory.")
        
        elif item_type.lower() == "bait":
            if item_name not in self.bait_types:
                await ctx.send("🚫 Invalid bait type!")
                return
            bait = await self.config.user(member).bait()
            bait[item_name] = bait.get(item_name, 0) + amount
            await self.config.user(member).bait.set(bait)
            await ctx.send(f"✅ Added {amount} {item_name}(s) to {member.name}'s bait inventory.")
        
        elif item_type.lower() == "rod":
            if item_name not in self.rod_types:
                await ctx.send("🚫 Invalid rod type!")
                return
            purchased_rods = await self.config.user(member).purchased_rods()
            purchased_rods[item_name] = True
            await self.config.user(member).purchased_rods.set(purchased_rods)
            await ctx.send(f"✅ Added {item_name} to {member.name}'s purchased rods.")
        
        else:
            await ctx.send("🚫 Invalid item type. Use `fish`, `bait`, or `rod`.")

    @manage.command(name="remove")
    @commands.is_owner()
    async def remove_item(self, ctx, item_type: str, member: discord.Member, item_name: str, amount: int = 1):
        """Remove an item from a user's inventory."""
        if item_type.lower() == "fish":
            if item_name not in self.fish_types:
                await ctx.send("🚫 Invalid fish type!")
                return
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
            if item_name not in self.bait_types:
                await ctx.send("🚫 Invalid bait type!")
                return
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
            if item_name not in self.rod_types:
                await ctx.send("🚫 Invalid rod type!")
                return
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
