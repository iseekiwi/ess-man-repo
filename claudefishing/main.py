import discord
import asyncio
import os
from .ui.inventory import InventoryView
from .ui.shop import ShopView, PurchaseConfirmView
from redbot.core import commands, Config, bank
from redbot.core.bot import Red
import random
import datetime
from collections import Counter
import logging
from .data.fishing_data import (
    FISH_TYPES,
    ROD_TYPES,
    BAIT_TYPES,
    LOCATIONS,
    WEATHER_TYPES,
    TIME_EFFECTS,
    EVENTS
)

import logging
import sys
from pathlib import Path

# Create logs directory if it doesn't exist
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)

# Define the log file path
log_file_path = log_dir / "fishing_game.log"

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Create logger for this module
logger = logging.getLogger('fishing.main')
logger.setLevel(logging.DEBUG)

# Test log message in cog initialization
class Fishing(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        logger.info("Initializing Fishing cog")

class Fishing(commands.Cog):
    """A fishing game cog for Redbot"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=123456789)
            
        # Default user settings
        default_user = {
            "inventory": [],
            "rod": "Basic Rod",
            "total_value": 0,
            "daily_quest": None,
            "bait": {},
            "purchased_rods": {"Basic Rod": True},
            "equipped_bait": None,
            "current_location": "Pond",
            "fish_caught": 0,
            "level": 1,
            "settings": {
                "notifications": True,
                "auto_sell": False
            }
        }
            
        # Default global settings
        default_global = {
            "bait_stock": {bait: data["daily_stock"] for bait, data in BAIT_TYPES.items()},
            "current_weather": "Sunny",
            "active_events": [],
            "settings": {
                "daily_reset_hour": 0,
                "weather_change_interval": 3600
            }
        }
            
        # Register defaults
        self.config.register_user(**default_user)
        self.config.register_global(**default_global)
    
        # Store data structures
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

    async def _ensure_user_data(self, user) -> dict:
        """Ensure user data exists and is properly initialized."""
        try:
            logger.debug(f"Ensuring user data for {user.name}")
            user_data = await self.config.user(user).all()
            
            # Initialize with default values if data is missing or empty
            default_user = {
                "inventory": [],
                "rod": "Basic Rod",
                "total_value": 0,
                "daily_quest": None,
                "bait": {},
                "purchased_rods": {"Basic Rod": True},
                "equipped_bait": None,
                "current_location": "Pond",
                "fish_caught": 0,
                "level": 1,
                "settings": {
                    "notifications": True,
                    "auto_sell": False
                }
            }
            
            if not user_data:
                logger.debug(f"Initializing new user data for {user.name}")
                await self.config.user(user).set_raw(value=default_user)
                return default_user

            # Check if any default keys are missing and add them
            modified = False
            for key, value in default_user.items():
                if key not in user_data:
                    user_data[key] = value
                    modified = True
                elif isinstance(value, dict):
                    # Check nested dictionaries
                    for subkey, subvalue in value.items():
                        if key not in user_data or subkey not in user_data[key]:
                            if key not in user_data:
                                user_data[key] = {}
                            user_data[key][subkey] = subvalue
                            modified = True

            if modified:
                logger.debug(f"Updating user data with missing defaults for {user.name}")
                await self.config.user(user).set_raw(value=user_data)

            return user_data

        except Exception as e:
            logger.error(f"Error ensuring user data for {user.name}: {e}", exc_info=True)
            await self.config.user(user).clear()  # Clear potentially corrupted data
            return None

    # Background Task Management
    def start_background_tasks(self):
        """Initialize and start background tasks."""
        try:
            if self.bg_tasks:  # Cancel any existing tasks
                for task in self.bg_tasks:
                    task.cancel()
            self.bg_tasks = []

            # Create new tasks
            self.bg_tasks.append(self.bot.loop.create_task(self.daily_stock_reset()))
            self.bg_tasks.append(self.bot.loop.create_task(self.weather_change_task()))
            logger.info("Background tasks started successfully")
        except Exception as e:
            logger.error(f"Error starting background tasks: {e}", exc_info=True)

    def cog_unload(self):
        """Clean up background tasks when cog is unloaded."""
        try:
            for task in self.bg_tasks:
                task.cancel()
            logger.info("Background tasks cleaned up successfully")
        except Exception as e:
            logger.error(f"Error in cog_unload: {e}", exc_info=True)

    async def weather_change_task(self):
        """Periodically change the weather."""
        while True:
            try:
                await asyncio.sleep(3600)  # Change weather every hour
                weather = random.choice(list(self.data["weather"].keys()))
                await self.config.current_weather.set(weather)
                logger.debug(f"Weather changed to {weather}")
                
            except asyncio.CancelledError:
                logger.info("Weather change task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in weather_change_task: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def daily_stock_reset(self):
        """Reset the daily stock of shop items at midnight."""
        try:
            while True:
                now = datetime.datetime.now()
                midnight = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), datetime.time())
                await asyncio.sleep((midnight - now).total_seconds())
                
                default_stock = {bait: data["daily_stock"] for bait, data in self.data["bait"].items()}
                await self.config.bait_stock.set(default_stock)
                logger.info("Daily stock reset completed")
        except asyncio.CancelledError:
            logger.info("Daily stock reset task cancelled")
            pass
        except Exception as e:
            logger.error(f"Error in daily_stock_reset: {e}", exc_info=True)
            
    # Location Commands
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

                user_data = await self._ensure_user_data(ctx.author)
                if not user_data:
                    logger.error(f"Failed to get user data for {ctx.author.name}")
                    await ctx.send("❌ Error accessing user data. Please try again.")
                    return

                location_data = self.data["locations"][new_location]
                
                meets_req, msg = await self.check_requirements(user_data, location_data["requirements"])
                if not meets_req:
                    await ctx.send(msg)
                    return

                await self.config.user(ctx.author).current_location.set(new_location)
                await ctx.send(f"🌍 {ctx.author.name} is now fishing at: {new_location}\n{location_data['description']}")
                logger.debug(f"User {ctx.author.name} moved to location: {new_location}")

        except Exception as e:
            logger.error(f"Error in location command: {e}", exc_info=True)
            await ctx.send(f"An error occurred: {str(e)}\nPlease try again or contact an administrator.")
            raise

    @location.command(name="list")
    async def location_list(self, ctx):
        """Display detailed information about all fishing locations."""
        try:
            user_data = await self._ensure_user_data(ctx.author)
            if not user_data:
                await ctx.send("❌ Error accessing user data. Please try again.")
                return

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
            logger.debug(f"Location list displayed for {ctx.author.name}")

        except Exception as e:
            logger.error(f"Error in location list command: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while displaying locations. Please try again.")

    @location.command(name="info")
    async def location_info(self, ctx, location_name: str = None):
        """Display detailed information about a specific location."""
        try:
            user_data = await self._ensure_user_data(ctx.author)
            if not user_data:
                await ctx.send("❌ Error accessing user data. Please try again.")
                return

            if not location_name:
                location_name = user_data["current_location"]
            elif location_name not in self.data["locations"]:
                await ctx.send("🚫 Invalid location name! Use `!location list` to see available locations.")
                return
                
            location_data = self.data["locations"][location_name]
            
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
            logger.debug(f"Location info displayed for {ctx.author.name}: {location_name}")
            
        except Exception as e:
            logger.error(f"Error in location info command: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while displaying location information. Please try again.")

    async def check_requirements(self, user_data: dict, requirements: dict) -> tuple[bool, str]:
        """Check if user meets requirements."""
        try:
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
        except Exception as e:
            logger.error(f"Error checking requirements: {e}", exc_info=True)
            return False, "❌ An error occurred while checking requirements."
            
    # Core Fishing Commands
    @commands.command(name="fish")
    async def fish(self, ctx):
        """Go fishing with a minigame challenge."""
        try:
            logger.debug(f"Starting fishing command for {ctx.author.name}")
            
            # Ensure user data is properly initialized
            user_data = await self._ensure_user_data(ctx.author)
            if not user_data:
                logger.error(f"Failed to initialize user data for {ctx.author.name}")
                await ctx.send("❌ Error initializing user data. Please try again.")
                return
            
            # Validate bait
            if not user_data["equipped_bait"]:
                await ctx.send(f"🚫 {ctx.author.name}, you need to equip bait first! Use `!equipbait` to equip some bait.")
                return

            bait = user_data.get("bait", {})
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
            
            logger.debug(f"Fishing conditions - Weather: {current_weather}, Time: {time_of_day}")

            # Run fishing minigame
            msg = await ctx.send("🎣 Fishing...")
            await asyncio.sleep(random.uniform(3, 7))
            
            keyword = random.choice(["catch", "grab", "snag", "hook", "reel"])
            await msg.edit(content=f"🎣 Quick! Type **{keyword}** to catch the fish!")

            try:
                await self.bot.wait_for(
                    'message',
                    check=lambda m: (
                        m.author == ctx.author and 
                        m.content.lower() == keyword and 
                        m.channel == ctx.channel
                    ),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                await ctx.send(f"⏰ {ctx.author.name}, you took too long! The fish got away!")
                return

            # Process catch
            logger.debug(f"Processing catch for {ctx.author.name}")
            catch = await self._catch_fish(
                user_data,
                equipped_bait,
                user_data["current_location"],
                current_weather,
                time_of_day
            )

            # Update bait inventory
            async with self.config.user(ctx.author).bait() as bait:
                bait[equipped_bait] = bait.get(equipped_bait, 0) - 1
                if bait[equipped_bait] <= 0:
                    del bait[equipped_bait]
                    await self.config.user(ctx.author).equipped_bait.set(None)
                    logger.debug(f"Bait {equipped_bait} depleted for {ctx.author.name}")

            if catch:
                fish_name = catch["name"]
                fish_value = catch["value"]
                variant = random.choice(self.data["fish"][fish_name]["variants"])
                
                # Update user data
                await self._add_to_inventory(ctx.author, fish_name)
                await self._update_total_value(ctx.author, fish_value)
                
                # Update fish count
                async with self.config.user(ctx.author).all() as user_data:
                    user_data["fish_caught"] += 1
                
                # Format message
                location = user_data["current_location"]
                weather_effect = self.data["weather"][current_weather]["description"]
                location_effect = self.data["locations"][location]["description"]
                
                await ctx.send(
                    f"🎣 {ctx.author.name} caught a {variant} ({fish_name}) worth {fish_value} coins!\n"
                    f"Location: {location} - {location_effect}\n"
                    f"Weather: {current_weather} - {weather_effect}"
                )
                logger.debug(f"Successful catch for {ctx.author.name}: {fish_name} ({variant})")
            else:
                await ctx.send(f"🎣 {ctx.author.name} went fishing but didn't catch anything this time.")
                logger.debug(f"Failed catch attempt for {ctx.author.name}")
                
        except Exception as e:
            logger.error(f"Error in fish command: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while fishing. Please try again.")

    async def _catch_fish(self, user_data: dict, bait_type: str, location: str, weather: str, time_of_day: str) -> dict:
        """Calculate catch results with all modifiers."""
        try:
            # Calculate catch chance
            base_chance = self.data["rods"][user_data["rod"]]["chance"]
            bait_bonus = self.data["bait"][bait_type]["catch_bonus"]
            weather_bonus = self.data["weather"][weather].get("catch_bonus", 0)
            time_bonus = self.data["time"][time_of_day].get("catch_bonus", 0)
            
            total_chance = base_chance + bait_bonus + weather_bonus + time_bonus
            logger.debug(f"Catch chances - Base: {base_chance}, Total: {total_chance}")
            
            if random.random() >= total_chance:
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
                # Validate fish data
                if "variants" not in data:
                    logger.warning(f"Fish type {fish} missing variants!")
                    continue
                    
                weight = data["chance"] * location_mods[fish]
                if weather_rare_bonus and data["rarity"] in ["rare", "legendary"]:
                    weight *= (1 + weather_rare_bonus)
                weighted_fish.append(fish)
                weights.append(weight)

            if not weighted_fish:
                logger.warning("No valid fish types found!")
                return None

            caught_fish = random.choices(weighted_fish, weights=weights, k=1)[0]
            logger.debug(f"Fish caught: {caught_fish}")
            return {"name": caught_fish, "value": self.data["fish"][caught_fish]["value"]}
            
        except Exception as e:
            logger.error(f"Error in _catch_fish: {e}", exc_info=True)
            return None

    async def _add_to_inventory(self, user, fish_name: str) -> bool:
        """Add fish to user's inventory."""
        try:
            async with self.config.user(user).inventory() as inventory:
                inventory.append(fish_name)
            logger.debug(f"Added {fish_name} to {user.name}'s inventory")
            return True
        except Exception as e:
            logger.error(f"Error adding to inventory: {e}", exc_info=True)
            return False

    async def _update_total_value(self, user, value: int) -> bool:
        """Update total value and check for level up."""
        try:
            async with self.config.user(user).all() as user_data:
                user_data["total_value"] += value
                old_level = user_data["level"]
                new_level = max(1, user_data["fish_caught"] // 50)
                user_data["level"] = new_level
                
                if new_level > old_level:
                    logger.info(f"User {user.name} leveled up from {old_level} to {new_level}")
            return True
        except Exception as e:
            logger.error(f"Error updating total value: {e}", exc_info=True)
            return False
            
    # Shop Commands
    @commands.command(name="shop")
    async def shop(self, ctx: commands.Context):
        """Browse and purchase fishing supplies"""
        try:
            logger.info(f"Shop command invoked by {ctx.author.name}")
            
            # Get user data
            user_data = await self.config.user(ctx.author).all()
            if not user_data:
                logger.error(f"No user data found for {ctx.author.name}")
                await ctx.send("Error: Please try fishing first to initialize your account.")
                return
                
            # Initialize bait stock if not exists
            if not hasattr(self, '_bait_stock'):
                logger.debug("Initializing bait stock")
                self._bait_stock = {
                    bait: data["daily_stock"] 
                    for bait, data in self.data["bait"].items()
                }
            
            # Verify required data is loaded
            if not hasattr(self, 'data'):
                logger.error("Cog data not initialized")
                await ctx.send("Error: Shop data not initialized. Please contact an administrator.")
                return
            
            # Create shop view
            try:
                view = await ShopView(self, ctx, user_data).setup()
                logger.debug("Shop view created successfully")
            except Exception as e:
                logger.error(f"Error creating shop view: {e}", exc_info=True)
                await ctx.send("Error: Unable to create shop interface. Please try again.")
                return
            
            try:
                # Generate initial embed
                embed = await view.generate_embed()
                logger.debug("Initial embed generated successfully")
                
                # Send the message and store it in the view
                view.message = await ctx.send(embed=embed, view=view)
                logger.info(f"Shop displayed successfully for {ctx.author.name}")
                
            except Exception as e:
                logger.error(f"Error displaying shop: {e}", exc_info=True)
                await ctx.send("Error: Unable to display shop information. Please try again later.")
                return
                
        except Exception as e:
            logger.error(f"Unexpected error in shop command: {e}", exc_info=True)
            await ctx.send("An unexpected error occurred. Please try again later.")
    
    async def _handle_bait_purchase(self, user, bait_name: str, amount: int, user_data: dict) -> tuple[bool, str]:
        """Handle bait purchase logic."""
        try:
            logger.debug(f"Starting bait purchase for {user.name}: {bait_name} x {amount}")
            
            bait_data = self.data["bait"][bait_name]
            total_cost = bait_data["cost"] * amount
            logger.debug(f"Total cost: {total_cost} coins")
            
            # Check stock
            bait_stock = await self.config.bait_stock()
            logger.debug(f"Current bait stock: {bait_stock}")
            if bait_stock[bait_name] < amount:
                logger.debug(f"Insufficient stock: {bait_name} x {amount}")
                return False, f"🚫 Not enough {bait_name} in stock! Available: {bait_stock[bait_name]}"
    
            # Check balance
            logger.debug(f"Checking balance for {user.name}")
            if not await self._can_afford(user, total_cost):
                logger.debug(f"Insufficient balance for {user.name}")
                return False, f"🚫 You don't have enough coins! Cost: {total_cost}"
    
            # Process purchase atomically
            async with self.config.user(user).bait() as user_bait:
                logger.debug(f"Processing purchase for {user.name}")
                
                # Verify stock again before finalizing
                current_stock = await self.config.bait_stock()
                if current_stock[bait_name] < amount:
                    logger.debug(f"Stock changed while processing for {user.name}")
                    return False, f"🚫 Stock changed while processing. Please try again."
                
                # Update stock
                current_stock[bait_name] -= amount
                await self.config.bait_stock.set(current_stock)
                logger.debug(f"Updated bait stock: {current_stock}")
                
                # Update user's bait
                user_bait[bait_name] = user_bait.get(bait_name, 0) + amount
                logger.debug(f"Updated user bait: {user_bait}")
                
                # Process payment
                await bank.withdraw_credits(user, total_cost)
                logger.debug(f"Payment processed for {user.name}: {total_cost} coins")
                
            logger.debug(f"Bait purchase completed for {user.name}: {bait_name} x {amount}")
            return True, f"✅ Purchased {amount} {bait_name} for {total_cost} coins!"
    
        except Exception as e:
            logger.exception(f"Error in bait purchase for {user.name}: {e}")
            return False, "❌ An error occurred while processing your purchase."
    
    async def _handle_rod_purchase(self, user, rod_name: str, user_data: dict) -> tuple[bool, str]:
        """Handle rod purchase logic."""
        try:
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
    
            # Process purchase atomically
            async with self.config.user(user).purchased_rods() as purchased_rods:
                # Verify not purchased during transaction
                if rod_name in purchased_rods:
                    return False, f"🚫 You already own this rod!"
                
                # Process payment
                await bank.withdraw_credits(user, rod_data["cost"])
                
                # Update user's rods
                purchased_rods[rod_name] = True
                
            return True, f"✅ Purchased {rod_name} for {rod_data['cost']} coins!"
    
        except Exception as e:
            logger.error(f"Error in rod purchase: {e}", exc_info=True)
            return False, "❌ An error occurred while processing your purchase."

    async def _can_afford(self, user, cost: int) -> bool:
        """Check if user can afford a purchase."""
        try:
            balance = await bank.get_balance(user)
            return balance >= cost
        except Exception as e:
            logger.error(f"Error checking balance: {e}", exc_info=True)
            return False

    @commands.command(name="inventory")
    async def inventory(self, ctx: commands.Context):
        """Display your fishing inventory"""
        try:
            logger.debug(f"Initializing inventory command for {ctx.author.name}")
            
            # Ensure user data exists and is properly initialized
            user_data = await self._ensure_user_data(ctx.author)
            if not user_data:
                logger.error(f"Failed to get user data for {ctx.author.name}")
                await ctx.send("❌ Error accessing user data. Please try again.")
                return
    
            # Create and start the inventory view
            try:
                view = await InventoryView(self, ctx, user_data).start()
                logger.debug(f"Inventory view created successfully for {ctx.author.name}")
                
            except Exception as e:
                logger.error(f"Error creating inventory view: {e}", exc_info=True)
                await ctx.send("❌ An error occurred while displaying your inventory. Please try again.")
                return
    
        except Exception as e:
            logger.error(f"Unexpected error in inventory command: {e}", exc_info=True)
            await ctx.send("❌ An unexpected error occurred. Please try again later.")

    async def _equip_rod(self, user: discord.Member, rod_name: str) -> tuple[bool, str]:
        """Helper method to equip a fishing rod"""
        try:
            user_data = await self.config.user(user).all()
            
            if rod_name not in user_data.get("purchased_rods", {}):
                return False, "You don't own this rod!"
                
            await self.config.user(user).rod.set(rod_name)
            logger.debug(f"User {user.name} equipped rod: {rod_name}")
            return True, f"Successfully equipped {rod_name}!"
            
        except Exception as e:
            logger.error(f"Error equipping rod: {e}", exc_info=True)
            return False, "An error occurred while equipping the rod."

    async def _equip_bait(self, user: discord.Member, bait_name: str) -> tuple[bool, str]:
        """Helper method to equip bait"""
        try:
            user_data = await self.config.user(user).all()
            
            if not user_data.get("bait", {}).get(bait_name, 0):
                return False, "You don't have any of this bait!"
                
            await self.config.user(user).equipped_bait.set(bait_name)
            logger.debug(f"User {user.name} equipped bait: {bait_name}")
            return True, f"Successfully equipped {bait_name}!"
            
        except Exception as e:
            logger.error(f"Error equipping bait: {e}", exc_info=True)
            return False, "An error occurred while equipping the bait."

    # Update the sell_fish command to return the amount sold
    async def sell_fish(self, ctx: commands.Context) -> tuple[bool, int, str]:
        """Sell all fish in inventory and return status, amount earned, and message"""
        try:
            user_data = await self._ensure_user_data(ctx.author)
            if not user_data:
                return False, 0, "Error accessing inventory data."

            inventory = user_data["inventory"]
            if not inventory:
                return False, 0, "You have no fish to sell."

            # Calculate total value with rod bonus
            user_rod = user_data["rod"]
            base_value = sum(self.data["fish"][fish]["value"] for fish in inventory)
            value_multiplier = 1 + (self.data["rods"][user_rod]["value_increase"] / 100)
            total_value = int(base_value * value_multiplier)

            try:
                # Process sale atomically
                async with self.config.user(ctx.author).inventory() as inventory:
                    if not inventory:
                        return False, 0, "You have no fish to sell."
                    
                    # Process payment first
                    await bank.deposit_credits(ctx.author, total_value)
                    
                    # Clear inventory after successful payment
                    inventory.clear()
                
                logger.info(f"User {ctx.author.name} sold fish for {total_value} coins")
                return True, total_value, f"Successfully sold all fish for {total_value} coins!"

            except Exception as e:
                logger.error(f"Error processing fish sale: {e}", exc_info=True)
                return False, 0, "Error processing sale."

        except Exception as e:
            logger.error(f"Error in sell_fish: {e}", exc_info=True)
            return False, 0, "An error occurred while selling fish."

    @commands.command(name="fisherboard")
    async def fisherboard(self, ctx):
        """Display fishing leaderboard."""
        try:
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
                try:
                    user = await self.bot.fetch_user(user_id)
                    if user:
                        board_entries.append(
                            f"{rank}. {user.name}\n"
                            f"   💰 {value:,} coins earned\n"
                            f"   🐟 {fish_caught:,} fish caught\n"
                        )
                except Exception as e:
                    logger.warning(f"Could not fetch user {user_id}: {e}")
                    continue
            
            if not board_entries:
                await ctx.send("🏆 No valid leaderboard entries found.")
                return

            await ctx.send("🏆 **Fishing Leaderboard:**\n\n" + "\n".join(board_entries))
            logger.debug("Leaderboard displayed successfully")

        except Exception as e:
            logger.error(f"Error displaying leaderboard: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while displaying the leaderboard. Please try again.")

    # Admin Commands
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
        try:
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
            
            if success:
                logger.info(f"Admin {ctx.author.name} added {amount}x {item_name} ({item_type}) to {member.name}")

        except Exception as e:
            logger.error(f"Error in add_item command: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while adding items. Please try again.")

    @manage.command(name="remove")
    @commands.is_owner()
    async def remove_item(self, ctx, item_type: str, member: discord.Member, item_name: str, amount: int = 1):
        """Remove items from a user's inventory."""
        try:
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
            
            if success:
                logger.info(f"Admin {ctx.author.name} removed {amount}x {item_name} ({item_type}) from {member.name}")

        except Exception as e:
            logger.error(f"Error in remove_item command: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while removing items. Please try again.")

    @manage.command(name="reset")
    @commands.is_owner()
    async def reset_user(self, ctx, member: discord.Member):
        """Reset a user's fishing data."""
        try:
            await self.config.user(member).clear()
            await self._ensure_user_data(member)  # Reinitialize with defaults
            await ctx.send(f"✅ Reset fishing data for {member.name}")
            logger.warning(f"Admin {ctx.author.name} reset fishing data for {member.name}")
        except Exception as e:
            logger.error(f"Error resetting user data: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while resetting user data. Please try again.")

    @manage.command(name="stock")
    @commands.is_owner()
    async def reset_stock(self, ctx):
        """Reset the shop's bait stock."""
        try:
            default_stock = {bait: data["daily_stock"] for bait, data in self.data["bait"].items()}
            await self.config.bait_stock.set(default_stock)
            await ctx.send("✅ Shop stock has been reset!")
            logger.info(f"Admin {ctx.author.name} reset shop stock")
        except Exception as e:
            logger.error(f"Error resetting shop stock: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while resetting shop stock. Please try again.")

    # Admin helper methods
    async def _add_fish(self, member: discord.Member, fish_name: str, amount: int) -> tuple[bool, str]:
        """Add fish to user's inventory."""
        try:
            if fish_name not in self.data["fish"]:
                return False, "🚫 Invalid fish type!"
                
            async with self.config.user(member).inventory() as inventory:
                for _ in range(amount):
                    inventory.append(fish_name)
                    
            return True, f"✅ Added {amount} {fish_name}(s) to {member.name}'s inventory."

        except Exception as e:
            logger.error(f"Error adding fish: {e}", exc_info=True)
            return False, "❌ An error occurred while adding fish."

    async def _add_bait(self, member: discord.Member, bait_name: str, amount: int) -> tuple[bool, str]:
        """Add bait to user's inventory."""
        try:
            if bait_name not in self.data["bait"]:
                return False, "🚫 Invalid bait type!"
                
            async with self.config.user(member).bait() as bait:
                bait[bait_name] = bait.get(bait_name, 0) + amount
                
            return True, f"✅ Added {amount} {bait_name}(s) to {member.name}'s bait inventory."

        except Exception as e:
            logger.error(f"Error adding bait: {e}", exc_info=True)
            return False, "❌ An error occurred while adding bait."

    async def _add_rod(self, member: discord.Member, rod_name: str, _: int) -> tuple[bool, str]:
        """Add rod to user's inventory."""
        try:
            if rod_name not in self.data["rods"]:
                return False, "🚫 Invalid rod type!"
                
            async with self.config.user(member).purchased_rods() as purchased_rods:
                purchased_rods[rod_name] = True
                
            return True, f"✅ Added {rod_name} to {member.name}'s purchased rods."

        except Exception as e:
            logger.error(f"Error adding rod: {e}", exc_info=True)
            return False, "❌ An error occurred while adding rod."

    async def _remove_fish(self, member: discord.Member, fish_name: str, amount: int) -> tuple[bool, str]:
        """Remove fish from user's inventory."""
        try:
            if fish_name not in self.data["fish"]:
                return False, "🚫 Invalid fish type!"
                
            async with self.config.user(member).inventory() as inventory:
                fish_count = inventory.count(fish_name)
                if fish_count < amount:
                    return False, f"🚫 {member.name} does not have enough {fish_name} to remove."
                    
                for _ in range(amount):
                    inventory.remove(fish_name)
                    
            return True, f"✅ Removed {amount} {fish_name}(s) from {member.name}'s inventory."

        except Exception as e:
            logger.error(f"Error removing fish: {e}", exc_info=True)
            return False, "❌ An error occurred while removing fish."

    async def _remove_bait(self, member: discord.Member, bait_name: str, amount: int) -> tuple[bool, str]:
        """Remove bait from user's inventory."""
        try:
            if bait_name not in self.data["bait"]:
                return False, "🚫 Invalid bait type!"
                
            async with self.config.user(member).bait() as bait:
                if bait.get(bait_name, 0) < amount:
                    return False, f"🚫 {member.name} does not have enough {bait_name} to remove."
                    
                bait[bait_name] -= amount
                if bait[bait_name] <= 0:
                    del bait[bait_name]
                    
            return True, f"✅ Removed {amount} {bait_name}(s) from {member.name}'s bait inventory."

        except Exception as e:
            logger.error(f"Error removing bait: {e}", exc_info=True)
            return False, "❌ An error occurred while removing bait."

    async def _remove_rod(self, member: discord.Member, rod_name: str, _: int) -> tuple[bool, str]:
        """Remove rod from user's inventory."""
        try:
            if rod_name not in self.data["rods"]:
                return False, "🚫 Invalid rod type!"
                
            async with self.config.user(member).purchased_rods() as purchased_rods:
                if rod_name not in purchased_rods:
                    return False, f"🚫 {member.name} does not have a {rod_name} to remove."
                    
                del purchased_rods[rod_name]
                    
            return True, f"✅ Removed {rod_name} from {member.name}'s purchased rods."

        except Exception as e:
            logger.error(f"Error removing rod: {e}", exc_info=True)
            return False, "❌ An error occurred while removing rod."

def setup(bot: Red):
    """Add the cog to the bot."""
    try:
        cog = Fishing(bot)
        bot.add_cog(cog)
        logger.info("Fishing cog loaded successfully")
    except Exception as e:
        logger.error(f"Error loading Fishing cog: {e}", exc_info=True)
        raise
