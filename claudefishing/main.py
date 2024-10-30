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
            
            # Consolidated default user settings
            default_user = {
                "inventory": [],
                "rod": "Basic Rod",
                "total_value": 0,
                "daily_quest": None,
                "bait": {},
                "purchased_rods": {"Basic Rod": True},  # Ensure Basic Rod is always available
                "equipped_bait": None,
                "current_location": "Pond",
                "fish_caught": 0,
                "level": 1,
                "settings": {  # Nested settings to prevent None issues
                    "notifications": True,
                    "auto_sell": False
                }
            }
            
            # Consolidated default global settings
            default_global = {
                "bait_stock": {bait: data["daily_stock"] for bait, data in BAIT_TYPES.items()},
                "current_weather": "Sunny",
                "active_events": [],
                "settings": {  # Nested settings to prevent None issues
                    "daily_reset_hour": 0,
                    "weather_change_interval": 3600
                }
            }
            
            # Register defaults before accessing any config values
            self.config.register_user(**default_user)
            self.config.register_global(**default_global)
    
            # Store data structures as instance variables
            self.data = {
                "fish": FISH_TYPES,
                "rods": ROD_TYPES,
                "bait": BAIT_TYPES,
                "locations": LOCATIONS,
                "weather": WEATHER_TYPES,
                "time": TIME_EFFECTS,
                "events": EVENTS
            }
    
            # Initialize background tasks
            self.bg_tasks = []
            self.start_background_tasks()

    def start_background_tasks(self):
        """Initialize and start background tasks."""
        if self.bg_tasks:  # Cancel any existing tasks
            for task in self.bg_tasks:
                task.cancel()
            self.bg_tasks = []

        # Create new tasks
        self.bg_tasks.append(self.bot.loop.create_task(self.daily_stock_reset()))
        self.bg_tasks.append(self.bot.loop.create_task(self.weather_change_task()))

    def cog_unload(self):
        """Clean up background tasks when cog is unloaded."""
        for task in self.bg_tasks:
            task.cancel()

    async def weather_change_task(self):
        """Periodically change the weather."""
        try:
            while True:
                await asyncio.sleep(3600)  # Change weather every hour
                weather = random.choice(list(self.data["weather"].keys()))
                await self.config.current_weather.set(weather)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in weather_change_task: {e}")

    async def daily_stock_reset(self):
        """Reset the daily stock of shop items at midnight."""
        try:
            while True:
                now = datetime.datetime.now()
                midnight = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), datetime.time())
                await asyncio.sleep((midnight - now).total_seconds())
                
                default_stock = {bait: data["daily_stock"] for bait, data in self.data["bait"].items()}
                await self.config.bait_stock.set(default_stock)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in daily_stock_reset: {e}")

    @commands.group(name="location", invoke_without_command=True)
    async def location(self, ctx, new_location: str = None):
        """Commands for managing fishing locations."""
        try:
            if ctx.invoked_subcommand is None:
                if new_location is None:
                    await ctx.send("📍 Please specify a location or use `!location list` to see available locations.")
                    return

                if new_location not in self.data["locations"]:
                    locations = "\n".join(f"- {loc}" for loc in self.data["locations"].keys())
                    await ctx.send(f"🌍 Available locations:\n{locations}")
                    return

                user_data = await self.config.user(ctx.author).all()
                if not user_data:
                    await self.config.user(ctx.author).clear()
                    user_data = await self.config.user(ctx.author).all()

                location_data = self.data["locations"][new_location]
                
                meets_req, msg = await self.check_requirements(user_data, location_data["requirements"])
                if not meets_req:
                    await ctx.send(msg)
                    return

                await self.config.user(ctx.author).current_location.set(new_location)
                await ctx.send(f"🌍 {ctx.author.name} is now fishing at: {new_location}\n{location_data['description']}")
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}\nPlease try again or contact an administrator.")
            raise

    @location.command(name="list")
    async def location_list(self, ctx):
        """Display detailed information about all fishing locations."""
        user_data = await self.config.user(ctx.author).all()
        current_location = user_data["current_location"]
        
        embed = discord.Embed(
            title="🗺️ Fishing Locations",
            description="Detailed information about available fishing spots",
            color=discord.Color.blue()
        )
        
        for location_name, location_data in self.data["locations"].items():
            # Format requirements
            if location_data["requirements"]:
                req = location_data["requirements"]
                req_text = f"Level {req['level']}, {req['fish_caught']} fish caught"
            else:
                req_text = "No requirements"
            
            # Format fish modifiers
            modifiers = []
            for fish_type, modifier in location_data["fish_modifiers"].items():
                percentage = int((modifier - 1) * 100) if modifier > 1 else int((1 - modifier) * -100)
                if percentage != 0:
                    modifiers.append(f"{fish_type}: {percentage:+d}%")
            
            # Determine if location is locked or current
            status = ""
            if location_name == current_location:
                status = "📍 Currently here"
            elif location_data["requirements"] and (
                user_data["level"] < location_data["requirements"]["level"] or
                user_data["fish_caught"] < location_data["requirements"]["fish_caught"]
            ):
                status = "🔒 Locked"
            
            # Build location description
            description = [
                f"**Description:** {location_data['description']}",
                f"**Requirements:** {req_text}",
                f"**Fish Chances:**\n" + "\n".join(f"• {mod}" for mod in modifiers)
            ]
            if status:
                description.append(f"**Status:** {status}")
            
            embed.add_field(
                name=f"📍 {location_name}",
                value="\n".join(description),
                inline=False
            )
        
        embed.set_footer(text="Use !location <name> to travel to a location")
        await ctx.send(embed=embed)

    @location.command(name="info")
    async def location_info(self, ctx, location_name: str = None):
        """Display detailed information about a specific location."""
        if not location_name:
            location_name = await self.config.user(ctx.author).current_location()
        elif location_name not in self.data["locations"]:
            await ctx.send("🚫 Invalid location name! Use `!location list` to see available locations.")
            return
            
        location_data = self.data["locations"][location_name]
        user_data = await self.config.user(ctx.author).all()
        
        embed = discord.Embed(
            title=f"📍 {location_name}",
            description=location_data["description"],
            color=discord.Color.blue()
        )
        
        # Requirements section
        if location_data["requirements"]:
            req = location_data["requirements"]
            req_met = (
                user_data["level"] >= req["level"] and 
                user_data["fish_caught"] >= req["fish_caught"]
            )
            status = "✅ Met" if req_met else "❌ Not Met"
            
            embed.add_field(
                name="Requirements",
                value=f"Level {req['level']}\n{req['fish_caught']} fish caught\nStatus: {status}",
                inline=False
            )
        else:
            embed.add_field(
                name="Requirements",
                value="None",
                inline=False
            )
        
        # Fish chances section
        chances = []
        for fish_type, modifier in location_data["fish_modifiers"].items():
            base_chance = self.data["fish"][fish_type]["chance"] * 100
            modified_chance = base_chance * modifier
            difference = modified_chance - base_chance
            
            chances.append(
                f"**{fish_type}**\n"
                f"Base: {base_chance:.1f}%\n"
                f"Modified: {modified_chance:.1f}% ({difference:+.1f}%)"
            )
        
        embed.add_field(
            name="Fish Chances",
            value="\n\n".join(chances),
            inline=False
        )
        
        # Weather effects section
        if location_data["weather_effects"]:
            weather_info = []
            for weather, data in self.data["weather"].items():
                if location_name in data.get("affects_locations", []):
                    effects = []
                    if "catch_bonus" in data:
                        effects.append(f"Catch rate: {data['catch_bonus']*100:+.0f}%")
                    if "rare_bonus" in data:
                        effects.append(f"Rare fish bonus: {data['rare_bonus']*100:+.0f}%")
                    weather_info.append(f"**{weather}**\n{', '.join(effects)}")
            
            embed.add_field(
                name="Weather Effects",
                value="\n\n".join(weather_info) if weather_info else "No specific weather effects",
                inline=False
            )
        
        await ctx.send(embed=embed)

    async def check_requirements(self, user_data: dict, requirements: dict) -> tuple[bool, str]:
        """Check if user meets requirements."""
        if not requirements:
            return True, ""
            
        # Ensure user_data has required fields
        level = user_data.get("level", 1)
        fish_caught = user_data.get("fish_caught", 0)
            
        if level < requirements["level"]:
            return False, f"🚫 You need to be level {requirements['level']}!"
        if fish_caught < requirements["fish_caught"]:
            return False, f"🚫 You need to catch {requirements['fish_caught']} fish first!"
            
        return True, ""

    async def _ensure_user_data(self, user):
        """Ensure user data exists and is properly initialized."""
        user_data = await self.config.user(user).all()
        if not user_data:
            await self.config.user(user).clear()
            user_data = await self.config.user(user).all()
        return user_data

    @commands.command(name="equipbait")
    async def equip_bait(self, ctx, bait_name: str):
        """Equip a specific bait for fishing."""
        bait_name = bait_name.title()
        user_data = await self.config.user(ctx.author).all()

        if bait_name not in self.data["bait"]:
            await ctx.send(f"🚫 {bait_name} is not a valid bait type.")
            return

        if bait_name not in user_data["bait"] or user_data["bait"][bait_name] <= 0:
            await ctx.send(f"🚫 {ctx.author.name}, you don't have any {bait_name} to equip.")
            return

        await self.config.user(ctx.author).equipped_bait.set(bait_name)
        await ctx.send(f"✅ {ctx.author.name} equipped {bait_name}!")

    @commands.command(name="fish")
    async def fish(self, ctx):
        """Go fishing with a minigame challenge."""
        user_data = await self.config.user(ctx.author).all()
        
        # Validate bait
        if not user_data["equipped_bait"]:
            await ctx.send(f"🚫 {ctx.author.name}, you need to equip bait first! Use `!equipbait` to equip some bait.")
            return

        bait = user_data["bait"]
        equipped_bait = user_data["equipped_bait"]
        
        if not bait.get(equipped_bait, 0):
            await ctx.send(f"🚫 {ctx.author.name}, you need bait to fish! Visit the `!shop` to purchase some.")
            return

        # Get current conditions
        current_weather = await self.config.current_weather()
        hour = datetime.datetime.now().hour
        time_of_day = (
            "Dawn" if 5 <= hour < 7 
            else "Day" if 7 <= hour < 17 
            else "Dusk" if 17 <= hour < 19 
            else "Night"
        )

        # Run fishing minigame
        msg = await ctx.send("🎣 Fishing...")
        await asyncio.sleep(random.uniform(3, 7))
        
        keyword = random.choice(["catch", "grab", "snag", "hook", "reel"])
        await msg.edit(content=f"🎣 Quick! Type **{keyword}** to catch the fish!")

        try:
            await self.bot.wait_for(
                'message',
                check=lambda m: m.author == ctx.author and m.content.lower() == keyword and m.channel == ctx.channel,
                timeout=5.0
            )
        except asyncio.TimeoutError:
            await ctx.send(f"⏰ {ctx.author.name}, you took too long! The fish got away!")
            return

        # Process catch
        catch = await self._catch_fish(
            user_data,
            equipped_bait,
            user_data["current_location"],
            current_weather,
            time_of_day
        )

        # Update bait inventory
        bait[equipped_bait] -= 1
        if bait[equipped_bait] <= 0:
            del bait[equipped_bait]
        await self.config.user(ctx.author).bait.set(bait)

        if catch:
            fish_name = catch["name"]
            fish_value = catch["value"]
            variant = random.choice(self.data["fish"][fish_name]["variants"])
            
            # Update user data
            await self._add_to_inventory(ctx.author, fish_name)
            await self._update_total_value(ctx.author, fish_value)
            
            fish_caught = user_data["fish_caught"] + 1
            await self.config.user(ctx.author).fish_caught.set(fish_caught)

            # Format message
            location = user_data["current_location"]
            weather_effect = self.data["weather"][current_weather]["description"]
            location_effect = self.data["locations"][location]["description"]
            
            await ctx.send(
                f"🎣 {ctx.author.name} caught a {variant} ({fish_name}) worth {fish_value} coins!\n"
                f"Location: {location} - {location_effect}\n"
                f"Weather: {current_weather} - {weather_effect}"
            )
        else:
            await ctx.send(f"🎣 {ctx.author.name} went fishing but didn't catch anything this time.")

    @commands.group(name="shop", invoke_without_command=True)
    async def shop(self, ctx):
        """Display available shop items."""
        bait_stock = await self.config.bait_stock()
        
        # Build shop display
        sections = []
        
        # Bait section
        bait_items = []
        for i, (name, data) in enumerate(self.data["bait"].items(), 1):
            stock = bait_stock.get(name, 0)
            bait_items.append(
                f"**{i}.** {name} - {data['cost']} coins\n"
                f"   Stock: {stock} | Bonus: +{data['catch_bonus']*100}%\n"
                f"   {data['description']}"
            )
        sections.append(("__Bait:__", "\n".join(bait_items)))
        
        # Rod section
        rod_items = []
        for i, (name, data) in enumerate(self.data["rods"].items(), len(self.data["bait"]) + 1):
            if name != "Basic Rod":
                req = data['requirements']
                req_str = f"(Requires Level {req['level']}, {req['fish_caught']} fish caught)" if req else ""
                rod_items.append(
                    f"**{i}.** {name} - {data['cost']} coins\n"
                    f"   Bonus: +{data['chance']*100}% catch rate\n"
                    f"   {data['description']} {req_str}"
                )
        sections.append(("__Fishing Rods:__", "\n".join(rod_items)))
        
        # Combine sections
        shop_display = "🛒 **Fishing Shop:**\n\n"
        shop_display += "\n\n".join(f"{header}\n{content}" for header, content in sections)
        
        await ctx.send(shop_display)

    @shop.command(name="buy")
    async def buy(self, ctx, item_index: int, amount: int = 1):
        """Purchase items from the shop."""
        shop_items = list(self.data["bait"].keys()) + [rod for rod in self.data["rods"].keys() if rod != "Basic Rod"]
        
        if not 1 <= item_index <= len(shop_items):
            await ctx.send("🚫 Invalid item index!")
            return

        item_name = shop_items[item_index - 1]
        user_data = await self.config.user(ctx.author).all()

        # Handle purchase logic based on item type
        if item_name in self.data["bait"]:
            success, msg = await self._handle_bait_purchase(ctx.author, item_name, amount, user_data)
        else:
            success, msg = await self._handle_rod_purchase(ctx.author, item_name, user_data)
            
        await ctx.send(msg)

    async def _handle_bait_purchase(self, user, bait_name: str, amount: int, user_data: dict) -> tuple[bool, str]:
        """Handle bait purchase logic."""
        bait_data = self.data["bait"][bait_name]
        total_cost = bait_data["cost"] * amount
        
        # Check stock
        bait_stock = await self.config.bait_stock()
        if bait_stock[bait_name] < amount:
            return False, f"🚫 Not enough {bait_name} in stock! Available: {bait_stock[bait_name]}"

        # Check balance
        if not await self._can_afford(user, total_cost):
            return False, f"🚫 You don't have enough coins! Cost: {total_cost}"

        # Process purchase
        await bank.withdraw_credits(user, total_cost)
        
        # Update stock
        bait_stock[bait_name] -= amount
        await self.config.bait_stock.set(bait_stock)
        
        # Update user's bait
        user_bait = user_data["bait"]
        user_bait[bait_name] = user_bait.get(bait_name, 0) + amount
        await self.config.user(user).bait.set(user_bait)
        
        return True, f"✅ Purchased {amount} {bait_name} for {total_cost} coins!"

    async def _handle_rod_purchase(self, user, rod_name: str, user_data: dict) -> tuple[bool, str]:
        """Handle rod purchase logic."""
        rod_data = self.data["rods"][rod_name]
        
        # Check requirements
        meets_req, msg = await self.check_requirements(user_data, rod_data["requirements"])
        if not meets_req:
            return False, msg

        # Check if already owned
        if rod_name in user_data["purchased_rods"]:
            return False, f"🚫 You already own a {rod_name}!"

        # Check balance
        if not await self._can_afford(user, rod_data["cost"]):
            return False, f"🚫 You don't have enough coins! Cost: {rod_data['cost']}"

        # Process purchase
        await bank.withdraw_credits(user, rod_data["cost"])
        
        # Update user's rods
        purchased_rods = user_data["purchased_rods"]
        purchased_rods[rod_name] = True
        await self.config.user(user).purchased_rods.set(purchased_rods)
        
        return True, f"✅ Purchased {rod_name} for {rod_data['cost']} coins!"

    async def _can_afford(self, user, cost: int) -> bool:
        """Check if user can afford a purchase."""
        return await bank.get_balance(user) >= cost

    @commands.command(name="inventory")
    async def inventory(self, ctx):
        """Display user's inventory."""
        user_data = await self.config.user(ctx.author).all()
        fish_counts = Counter(user_data["inventory"])
        
        sections = []
        
        # Fish section
        for rarity in ["common", "uncommon", "rare", "legendary"]:
            rarity_fish = [
                f"- {fish}: {fish_counts[fish]}"
                for fish in fish_counts.keys()
                if self.data["fish"][fish]["rarity"] == rarity
            ]
            if rarity_fish:
                sections.append((f"__{rarity.title()} Fish:__", "\n".join(rarity_fish)))
        
        # Bait section
        if user_data["bait"]:
            bait_items = [f"- {name}: {amount}" for name, amount in user_data["bait"].items()]
            sections.append(("__Bait:__", "\n".join(bait_items)))
        else:
            sections.append(("__Bait:__", "None"))
        
        # Rods section
        rod_items = []
        for rod_name in self.data["rods"].keys():
            if rod_name == "Basic Rod" or rod_name in user_data["purchased_rods"]:
                equipped = "📌 " if rod_name == user_data["rod"] else "  "
                rod_items.append(f"{equipped}{rod_name}")
        sections.append(("__Fishing Rods:__", "\n".join(rod_items)))

        # Stats section
        stats = [
            f"Total Fish Caught: {user_data['fish_caught']}",
            f"Level: {user_data['level']}",
            f"Current Location: {user_data['current_location']}"
        ]
        sections.append(("__Stats:__", "\n".join(stats)))

        # Combine all sections
        inventory_display = "🎒 **Your Inventory:**\n\n"
        inventory_display += "\n\n".join(f"{header}\n{content}" for header, content in sections)
        
        await ctx.send(inventory_display)

    @commands.command(name="sellfish")
    async def sell_fish(self, ctx):
        """Sell all fish in inventory."""
        user = ctx.author
        inventory = await self.config.user(user).inventory()

        if not inventory:
            await ctx.send(f"💰 {user.name}, you have no fish to sell.")
            return

        # Calculate total value with rod bonus
        user_rod = await self.config.user(user).rod()
        base_value = sum(self.data["fish"][fish]["value"] for fish in inventory)
        value_multiplier = 1 + (self.data["rods"][user_rod]["value_increase"] / 100)
        total_value = int(base_value * value_multiplier)

        # Process sale
        await bank.deposit_credits(user, total_value)
        await self.config.user(user).inventory.set([])
        await ctx.send(f"💰 {user.name} sold all their fish for {total_value} coins!")

    @commands.command(name="fisherboard")
    async def fisherboard(self, ctx):
        """Display fishing leaderboard."""
        all_users = await self.config.all_users()
        
        # Filter and sort users
        fisher_stats = [
            (user_id, data["total_value"], data["fish_caught"])
            for user_id, data in all_users.items()
            if data["total_value"] > 0
        ]
        
        if not fisher_stats:
            await ctx.send("🏆 The fisherboard is empty!")
            return

        fisher_stats.sort(key=lambda x: x[1], reverse=True)
        
        # Build leaderboard display
        board_entries = []
        for rank, (user_id, value, fish_caught) in enumerate(fisher_stats[:10], 1):
            user = await self.bot.fetch_user(user_id)
            board_entries.append(
                f"{rank}. {user.name}\n"
                f"   💰 {value} coins earned\n"
                f"   🐟 {fish_caught} fish caught\n"
            )
        
        await ctx.send("🏆 **Fishing Leaderboard:**\n\n" + "\n".join(board_entries))

    async def _catch_fish(self, user_data: dict, bait_type: str, location: str, weather: str, time_of_day: str) -> dict:
        """Calculate catch results with all modifiers."""
        # Calculate catch chance
        base_chance = self.data["rods"][user_data["rod"]]["chance"]
        bait_bonus = self.data["bait"][bait_type]["catch_bonus"]
        weather_bonus = self.data["weather"][weather].get("catch_bonus", 0)
        time_bonus = self.data["time"][time_of_day].get("catch_bonus", 0)
        
        if random.random() >= (base_chance + bait_bonus + weather_bonus + time_bonus):
            return None

        # Calculate fish weights with modifiers
        location_mods = self.data["locations"][location]["fish_modifiers"]
        weather_rare_bonus = (
            self.data["weather"][weather].get("rare_bonus", 0)
            if weather in self.data["weather"]
            else 0
        )

        weighted_fish = []
        weights = []
        
        for fish, data in self.data["fish"].items():
            weight = data["chance"] * location_mods[fish]
            if weather_rare_bonus and data["rarity"] in ["rare", "legendary"]:
                weight *= (1 + weather_rare_bonus)
            weighted_fish.append(fish)
            weights.append(weight)

        caught_fish = random.choices(weighted_fish, weights=weights, k=1)[0]
        return {"name": caught_fish, "value": self.data["fish"][caught_fish]["value"]}

    async def _add_to_inventory(self, user, fish_name: str):
        """Add fish to user's inventory."""
        async with self.config.user(user).inventory() as inventory:
            inventory.append(fish_name)

    async def _update_total_value(self, user, value: int):
        """Update total value and check for level up."""
        async with self.config.user(user).all() as user_data:
            user_data["total_value"] += value
            user_data["level"] = max(1, user_data["fish_caught"] // 50)

    @commands.group(name="manage")
    @commands.is_owner()
    async def manage(self, ctx):
        """Administrative management commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Use `!manage add` or `!manage remove` followed by `fish`, `bait`, or `rod`.")

    @manage.command(name="add")
    @commands.is_owner()
    async def add_item(self, ctx, item_type: str, member: discord.Member, item_name: str, amount: int = 1):
        """Add items to a user's inventory."""
        item_type = item_type.lower()
        
        handlers = {
            "fish": self._add_fish,
            "bait": self._add_bait,
            "rod": self._add_rod
        }
        
        if item_type not in handlers:
            await ctx.send("🚫 Invalid item type. Use `fish`, `bait`, or `rod`.")
            return
            
        success, msg = await handlers[item_type](member, item_name, amount)
        await ctx.send(msg)

    @manage.command(name="remove")
    @commands.is_owner()
    async def remove_item(self, ctx, item_type: str, member: discord.Member, item_name: str, amount: int = 1):
        """Remove items from a user's inventory."""
        item_type = item_type.lower()
        
        handlers = {
            "fish": self._remove_fish,
            "bait": self._remove_bait,
            "rod": self._remove_rod
        }
        
        if item_type not in handlers:
            await ctx.send("🚫 Invalid item type. Use `fish`, `bait`, or `rod`.")
            return
            
        success, msg = await handlers[item_type](member, item_name, amount)
        await ctx.send(msg)

    async def _add_fish(self, member: discord.Member, fish_name: str, amount: int) -> tuple[bool, str]:
        """Add fish to user's inventory."""
        if fish_name not in self.data["fish"]:
            return False, "🚫 Invalid fish type!"
            
        async with self.config.user(member).inventory() as inventory:
            for _ in range(amount):
                inventory.append(fish_name)
                
        return True, f"✅ Added {amount} {fish_name}(s) to {member.name}'s inventory."

    async def _add_bait(self, member: discord.Member, bait_name: str, amount: int) -> tuple[bool, str]:
        """Add bait to user's inventory."""
        if bait_name not in self.data["bait"]:
            return False, "🚫 Invalid bait type!"
            
        async with self.config.user(member).bait() as bait:
            bait[bait_name] = bait.get(bait_name, 0) + amount
            
        return True, f"✅ Added {amount} {bait_name}(s) to {member.name}'s bait inventory."

    async def _add_rod(self, member: discord.Member, rod_name: str, _: int) -> tuple[bool, str]:
        """Add rod to user's inventory."""
        if rod_name not in self.data["rods"]:
            return False, "🚫 Invalid rod type!"
            
        async with self.config.user(member).purchased_rods() as purchased_rods:
            purchased_rods[rod_name] = True
            
        return True, f"✅ Added {rod_name} to {member.name}'s purchased rods."

    async def _remove_fish(self, member: discord.Member, fish_name: str, amount: int) -> tuple[bool, str]:
        """Remove fish from user's inventory."""
        if fish_name not in self.data["fish"]:
            return False, "🚫 Invalid fish type!"
            
        async with self.config.user(member).inventory() as inventory:
            fish_count = inventory.count(fish_name)
            if fish_count < amount:
                return False, f"🚫 {member.name} does not have enough {fish_name} to remove."
                
            for _ in range(amount):
                inventory.remove(fish_name)
                
        return True, f"✅ Removed {amount} {fish_name}(s) from {member.name}'s inventory."

    async def _remove_bait(self, member: discord.Member, bait_name: str, amount: int) -> tuple[bool, str]:
        """Remove bait from user's inventory."""
        if bait_name not in self.data["bait"]:
            return False, "🚫 Invalid bait type!"
            
        async with self.config.user(member).bait() as bait:
            if bait.get(bait_name, 0) < amount:
                return False, f"🚫 {member.name} does not have enough {bait_name} to remove."
                
            bait[bait_name] -= amount
            if bait[bait_name] <= 0:
                del bait[bait_name]
                
        return True, f"✅ Removed {amount} {bait_name}(s) from {member.name}'s bait inventory."

    async def _remove_rod(self, member: discord.Member, rod_name: str, _: int) -> tuple[bool, str]:
        """Remove rod from user's inventory."""
        if rod_name not in self.data["rods"]:
            return False, "🚫 Invalid rod type!"
            
        async with self.config.user(member).purchased_rods() as purchased_rods:
            if rod_name not in purchased_rods:
                return False, f"🚫 {member.name} does not have a {rod_name} to remove."
                
            del purchased_rods[rod_name]
                
        return True, f"✅ Removed {rod_name} from {member.name}'s purchased rods."

def setup(bot: Red):
    bot.add_cog(Fishing(bot))
