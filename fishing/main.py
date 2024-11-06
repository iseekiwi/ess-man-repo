# main.py

import discord
import asyncio
import os
import random
import datetime
from .ui.inventory import InventoryView
from .ui.shop import ShopView, PurchaseConfirmView
from .ui.menu import FishingMenuView
from .utils.inventory_manager import InventoryManager
from .utils.task_manager import TaskManager
from .utils.logging_config import get_logger
from .utils.config_manager import ConfigManager, ConfigResult
from .utils.level_manager import LevelManager
from .utils.profit_simulator import ProfitSimulator
from redbot.core import commands, Config, bank
from redbot.core.bot import Red
from collections import Counter
from .data.fishing_data import (
    FISH_TYPES,
    ROD_TYPES,
    BAIT_TYPES,
    LOCATIONS,
    WEATHER_TYPES,
    TIME_EFFECTS,
    JUNK_TYPES,
)

class Fishing(commands.Cog):
    """A fishing game cog for Redbot"""

    def __init__(self, bot: Red):
        self.bot = bot
        # Set up logging first
        self.logger = get_logger('main')
        self.logger.info("Initializing Fishing cog")
        
        # Initialize config manager
        self.config_manager = ConfigManager(bot, identifier=123456789)

        # Initialize level manager
        self.level_manager = LevelManager(self.config_manager)
        
        # Store data structures
        self.data = {
            "fish": FISH_TYPES,
            "rods": ROD_TYPES,
            "bait": BAIT_TYPES,
            "locations": LOCATIONS,
            "weather": WEATHER_TYPES,
            "time": TIME_EFFECTS,
            "junk": JUNK_TYPES,
        }
        
        # Initialize inventory manager
        self.inventory = InventoryManager(bot, self.config_manager, self.data)
        self.logger.debug("Inventory manager initialized")
        
        # Initialize background tasks
        self.bg_task_manager = TaskManager(bot, self.config_manager, self.data)

    def get_time_of_day(self) -> str:
        """Get the current time of day for fishing effects"""
        hour = datetime.datetime.now().hour
        if 5 <= hour < 7:
            return "Dawn"
        elif 7 <= hour < 17:
            return "Day"
        elif 17 <= hour < 19:
            return "Dusk"
        else:
            return "Night"
    
    async def create_menu(self, ctx, user_data):
        """Create and setup a new menu view"""
        from .ui.menu import FishingMenuView
        menu_view = await FishingMenuView(self, ctx, user_data).setup()
        return menu_view
    
    async def _ensure_user_data(self, user) -> dict:
        """Ensure user data exists and is properly initialized."""
        try:
            self.logger.debug(f"Ensuring user data for {user.name}")
            result = await self.config_manager.get_user_data(user.id)
            
            if not result.success:
                self.logger.error(f"Failed to get user data: {result.error}")
                return None
                
            return result.data
            
        except Exception as e:
            self.logger.error(f"Error ensuring user data for {user.name}: {e}", exc_info=True)
            return None

    async def cog_load(self):
        """Run setup after cog is loaded."""
        try:
            # Verify and initialize stock if needed
            stock_result = await self.config_manager.get_global_setting("bait_stock")
            self.logger.debug(f"Current bait stock on load: {stock_result.data if stock_result.success else 'None'}")
            
            if not stock_result.success or not stock_result.data:
                self.logger.warning("No bait stock found, initializing defaults")
                initial_stock = {
                    bait: data["daily_stock"] 
                    for bait, data in self.data["bait"].items()
                }
                await self.config_manager.update_global_setting("bait_stock", initial_stock)
                self.logger.debug(f"Initialized bait stock: {initial_stock}")

            # Initialize last weather change time
            self.bg_task_manager.last_weather_change = datetime.datetime.now()
            
            # Start background tasks
            await self.bg_task_manager.start()
            
        except Exception as e:
            self.logger.error(f"Error in cog_load: {e}", exc_info=True)
            raise
    
    def cog_unload(self):
        """Clean up when cog is unloaded."""
        try:
            # Stop background tasks
            asyncio.create_task(self.bg_task_manager.stop())
            
            # Clean up timeout manager
            timeout_manager = TimeoutManager()
            asyncio.create_task(timeout_manager.cleanup())
            
            self.logger.info("Cog unloaded, background tasks cancelled")
        except Exception as e:
            self.logger.error(f"Error in cog_unload: {e}")

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
            self.logger.error(f"Error checking requirements: {e}", exc_info=True)
            return False, "❌ An error occurred while checking requirements."

    # Core Fishing Commands
    @commands.command(name="fish")
    async def fish_command(self, ctx):
        """Open the fishing menu interface"""
        try:
            self.logger.debug(f"Opening fishing menu for {ctx.author.name}")
            
            # Ensure user data is properly initialized
            user_data = await self._ensure_user_data(ctx.author)
            if not user_data:
                await ctx.send("❌ Error initializing user data. Please try again.")
                return
            
            # Create and start the menu view
            try:
                view = await FishingMenuView(self, ctx, user_data).setup()
                result = await view.start()
                if not result:
                    self.logger.error(f"Failed to start menu view for {ctx.author.name}")
                    return
            except Exception as e:
                self.logger.error(f"Error creating menu view: {e}", exc_info=True)
                await ctx.send("❌ Error displaying menu. Please try again.")
                return
                
        except Exception as e:
            self.logger.error(f"Error in fish command: {e}", exc_info=True)
            await ctx.send("❌ An error occurred. Please try again.")

    async def _catch_fish(
        self,
        user: discord.Member,
        user_data: dict,
        bait_type: str,
        location: str,
        weather: str,
        time_of_day: str
    ) -> dict:
        """Calculate catch results with all modifiers."""
        try:
            # Get weather data
            weather_data = self.data["weather"][weather]
            self.logger.debug(
                f"Starting catch calculation:\n"
                f"Location: {location}\n"
                f"Weather: {weather}\n"
                f"Time: {time_of_day}\n"
                f"Bait: {bait_type}"
            )
            
            # Calculate catch chance
            base_chance = self.data["rods"][user_data["rod"]]["chance"]
            bait_bonus = self.data["bait"][bait_type]["catch_bonus"]
            weather_bonus = weather_data.get("catch_bonus", 0)
            time_bonus = self.data["time"][time_of_day].get("catch_bonus", 0)
            
            # Apply location-specific weather bonus if exists
            location_bonus = weather_data.get("location_bonus", {}).get(location, 0)
            weather_bonus += location_bonus
            
            # Apply time-based weather multiplier if exists
            time_multiplier = weather_data.get("time_multiplier", {}).get(time_of_day, 0)
            weather_bonus += time_multiplier
            
            total_chance = base_chance + bait_bonus + weather_bonus + time_bonus
            
            self.logger.debug(
                f"Catch chance breakdown:\n"
                f"Base (Rod): {base_chance}\n"
                f"Bait Bonus: {bait_bonus}\n"
                f"Weather Bonus: {weather_bonus}\n"
                f"Location Bonus: {location_bonus}\n"
                f"Time Bonus: {time_bonus}\n"
                f"Time Multiplier: {time_multiplier}\n"
                f"Total: {total_chance}"
            )
    
            # First roll for fish catch
            catch_roll = random.random()
            if catch_roll < total_chance:
                self.logger.debug(f"Catch roll succeeded: {catch_roll} < {total_chance}")
                # Fish catch logic
                location_mods = self.data["locations"][location]["fish_modifiers"]
                weather_rare_bonus = weather_data.get("rare_bonus", 0)
    
                weighted_fish = []
                weights = []
                
                # Calculate weights for each fish type
                for fish, data in self.data["fish"].items():
                    if "variants" not in data:
                        self.logger.warning(f"Fish type {fish} missing variants!")
                        continue
                        
                    weight = data["chance"] * location_mods[fish]
                    
                    # Apply weather rare bonus to rare/legendary fish
                    if weather_rare_bonus and data["rarity"] in ["rare", "legendary"]:
                        rare_multiplier = 1 + weather_rare_bonus
                        weight *= rare_multiplier
                        self.logger.debug(f"Applied rare bonus to {fish}: {rare_multiplier}x")
                    
                    # Apply specific rarity bonus if exists
                    specific_bonus = weather_data.get("specific_rarity_bonus", {}).get(data["rarity"], 0)
                    if specific_bonus:
                        specific_multiplier = 1 + specific_bonus
                        weight *= specific_multiplier
                        self.logger.debug(f"Applied specific bonus to {fish}: {specific_multiplier}x")
                    
                    weighted_fish.append(fish)
                    weights.append(weight)
                    self.logger.debug(f"Fish weight for {fish}: {weight}")
    
                if not weighted_fish:
                    self.logger.warning("No valid fish types found!")
                    return None
    
                caught_fish = random.choices(weighted_fish, weights=weights, k=1)[0]
                fish_data = self.data["fish"][caught_fish]
    
                # Calculate XP reward with location modifier
                location_data = self.data["locations"][location]
                xp_reward = self.level_manager.calculate_xp_reward(
                    fish_data["rarity"],
                    location_mods[caught_fish]
                )
    
                self.logger.debug(f"Fish caught: {caught_fish}, XP reward: {xp_reward}")
                success = await self._add_to_inventory(user, caught_fish)
                self.logger.debug(f"Added {caught_fish} to inventory: {success}")
                
                result = {
                    "name": caught_fish,
                    "value": fish_data["value"],
                    "xp_gained": xp_reward,
                    "type": "fish"
                }
                
                # Check for additional catches from weather effect
                catch_quantity_bonus = weather_data.get("catch_quantity", 0)
                if catch_quantity_bonus:
                    bonus_roll = random.random()
                    self.logger.debug(f"Bonus catch roll: {bonus_roll} vs {catch_quantity_bonus}")
                    if bonus_roll < catch_quantity_bonus:
                        # Roll for an additional fish
                        bonus_catch = random.choices(weighted_fish, weights=weights, k=1)[0]
                        bonus_fish_data = self.data["fish"][bonus_catch]
                        # Add bonus fish to inventory
                        await self._add_to_inventory(user, bonus_catch)
                        self.logger.debug(f"Bonus fish caught: {bonus_catch}")
                        
                        # Add bonus catch info to result
                        result["bonus_catch"] = {
                            "name": bonus_catch,
                            "value": bonus_fish_data["value"]
                        }
                
                return result
                
            else:
                self.logger.debug(f"Catch roll failed: {catch_roll} >= {total_chance}")
                # If fish catch fails, roll for junk (75% chance to find junk on failed fish catch)
                if random.random() < 0.75:
                    self.logger.debug(f"Rolling for junk - Current junk count: {user_data.get('junk_caught', 0)}")
                    weighted_junk = []
                    weights = []
                    
                    for junk, data in self.data["junk"].items():
                        if "variants" not in data:
                            self.logger.warning(f"Junk type {junk} missing variants!")
                            continue
                            
                        weighted_junk.append(junk)
                        weights.append(data["chance"])
    
                    if not weighted_junk:
                        self.logger.warning("No valid junk types found!")
                        return None
    
                    caught_junk = random.choices(weighted_junk, weights=weights, k=1)[0]
                    junk_data = self.data["junk"][caught_junk]
    
                    # Calculate reduced XP reward for junk
                    xp_reward = self.level_manager.calculate_xp_reward(
                        junk_data["rarity"],
                        0.5  # 50% XP modifier for junk items
                    )
    
                    self.logger.debug(f"Junk caught: {caught_junk}, XP reward: {xp_reward}")
                    success = await self._add_to_inventory(user, caught_junk)
                    self.logger.debug(f"Added {caught_junk} to inventory: {success}")
    
                    # Update junk count
                    current_junk = user_data.get("junk_caught", 0)
                    self.logger.debug(f"Updating junk count from {current_junk} to {current_junk + 1}")
                    
                    update_result = await self.config_manager.update_user_data(
                        user.id,
                        {"junk_caught": current_junk + 1},
                        fields=["junk_caught"]
                    )
                    
                    if update_result.success:
                        self.logger.debug("Junk count update successful")
                        # Verify the update
                        verify_result = await self.config_manager.get_user_data(user.id)
                        if verify_result.success:
                            self.logger.debug(f"Verified junk count after update: {verify_result.data.get('junk_caught', 0)}")
                    else:
                        self.logger.error("Failed to update junk count")
    
                    return {
                        "name": caught_junk,
                        "value": junk_data["value"],
                        "xp_gained": xp_reward,
                        "type": "junk"
                    }
                
            return None
            
        except Exception as e:
            self.logger.error(f"Error in _catch_fish: {e}", exc_info=True)
            return None

    async def _add_to_inventory(self, user: discord.Member, item_name: str) -> bool:
        """Add fish or junk to user's inventory."""
        if item_name in self.data["fish"] or item_name in self.data["junk"]:
            success, _ = await self.inventory.add_item(user.id, "inventory", item_name)
            self.logger.debug(f"Added {item_name} to inventory: {success}")
            return success
        self.logger.warning(f"Invalid item attempted to add to inventory: {item_name}")
        return False

    async def _update_total_value(self, user, value: int, *, item_type: str = "fish") -> bool:
        """Update total value and check for level up."""
        try:
            self.logger.debug(f"Starting total value update for user {user.id} with value {value} and type {item_type}")
            
            user_data_result = await self.config_manager.get_user_data(user.id)
            if not user_data_result.success:
                self.logger.error(f"Failed to get user data in _update_total_value: {user_data_result.error}")
                return False
                
            user_data = user_data_result.data
            self.logger.debug(f"Current user data: {user_data}")
            old_level = user_data["level"]
            
            # Calculate new level based on current fish count - don't increment here
            fish_caught = user_data["fish_caught"]
            new_level = max(1, fish_caught // 50)
            
            # Prepare base updates
            updates = {
                "total_value": user_data["total_value"] + value,
                "level": new_level,
                "experience": user_data.get("experience", 0)
            }
            
            # Set base fields
            fields = ["total_value", "level", "experience"]
            
            # Only update fish_caught if this is actually a fish
            if item_type == "fish":
                updates["fish_caught"] = fish_caught + 1
                fields.append("fish_caught")
                
            update_result = await self.config_manager.update_user_data(
                user.id,
                updates,
                fields=fields
            )
            
            if not update_result.success:
                self.logger.error(f"Failed to update user data in _update_total_value: {update_result.error}")
                return False
                
            # Verify the update
            verify_result = await self.config_manager.get_user_data(user.id)
            if not verify_result.success:
                self.logger.error(f"Failed to verify data update: {verify_result.error}")
                return False
                
            self.logger.debug(f"Updated user data: {verify_result.data}")
            
            if new_level > old_level:
                self.logger.info(f"User {user.name} leveled up from {old_level} to {new_level}")
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating total value: {e}", exc_info=True)
            return False
    
    async def _handle_bait_purchase(self, user, bait_name: str, amount: int, user_data: dict) -> tuple[bool, str]:
        """Handle bait purchase logic with proper inventory management."""
        try:
            self.logger.debug(f"Starting bait purchase for {user.name}: {bait_name} x {amount}")
            
            if bait_name not in self.data["bait"]:
                return False, "Invalid bait type!"
                
            bait_data = self.data["bait"][bait_name]
            total_cost = bait_data["cost"] * amount
            
            # Check balance first to fail fast
            if not await self._can_afford(user, total_cost):
                return False, f"🚫 You don't have enough coins! Cost: {total_cost}"
            
            # Get current stock
            stock_result = await self.config_manager.get_global_setting("bait_stock")
            if not stock_result.success:
                return False, "Error checking stock."
                
            current_stock = stock_result.data.get(bait_name, 0)
            if current_stock < amount:
                return False, f"🚫 Not enough {bait_name} in stock! Available: {current_stock}"
            
            # Update stock first
            new_stock = stock_result.data.copy()
            new_stock[bait_name] = current_stock - amount
            stock_update = await self.config_manager.update_global_setting("bait_stock", new_stock)
            if not stock_update.success:
                return False, "Error updating stock."
    
            # Use inventory manager to add bait
            success, msg = await self.inventory.add_item(user.id, "bait", bait_name, amount)
            if not success:
                # Rollback stock if inventory update fails
                await self.config_manager.update_global_setting("bait_stock", stock_result.data)
                return False, "Error updating inventory."

            # Verify the inventory update
            verify_result = await self.config_manager.get_user_data(user.id)
            if verify_result.success:
                self.logger.debug(f"Full user data after purchase: {verify_result.data}")
                
                bait_data = verify_result.data.get("bait", {})
                self.logger.debug(f"Bait inventory after purchase: {bait_data}")
                
                updated_bait = bait_data.get(bait_name, 0)
                self.logger.debug(f"Attempting to verify purchase of {amount} {bait_name}, found {updated_bait}")
                
                if updated_bait < amount:
                    self.logger.error(f"Bait amount verification failed: Expected at least {amount}, got {updated_bait}")
                    # Let's also check the raw config data
                    raw_data = await self.config.user(user).all()
                    self.logger.debug(f"Raw config data: {raw_data}")
                    return False, "Error verifying inventory update."
            
            # Process payment last to minimize need for rollbacks
            try:
                await bank.withdraw_credits(user, total_cost)
            except Exception as e:
                # Rollback both stock and inventory if payment fails
                await self.config_manager.update_global_setting("bait_stock", stock_result.data)
                await self.inventory.remove_item(user.id, "bait", bait_name, amount)
                self.logger.error(f"Payment failed for bait purchase: {e}")
                return False, "Error processing payment."
    
            return True, f"✅ Purchased {amount} {bait_name} for {total_cost} coins!"
            
        except Exception as e:
            self.logger.error(f"Error in bait purchase: {e}", exc_info=True)
            return False, "❌ An error occurred while processing your purchase."
    
    async def _handle_rod_purchase(self, user, rod_name: str, user_data: dict) -> tuple[bool, str]:
        """Handle rod purchase logic using inventory manager."""
        try:
            self.logger.debug(f"Starting rod purchase for {user.name}: {rod_name}")
            
            if rod_name not in self.data["rods"]:
                return False, "Invalid rod type!"
                
            rod_data = self.data["rods"][rod_name]
            
            # Check requirements
            meets_req, msg = await self.check_requirements(user_data, rod_data["requirements"])
            if not meets_req:
                return False, msg
    
            # Check if already owned
            if rod_name in user_data.get("purchased_rods", {}):
                return False, f"🚫 You already own a {rod_name}!"
    
            # Check balance
            if not await self._can_afford(user, rod_data["cost"]):
                return False, f"🚫 You don't have enough coins! Cost: {rod_data['cost']}"
    
            # Use inventory manager to add rod
            success, msg = await self.inventory.add_item(user.id, "rod", rod_name)
            if not success:
                return False, "Error updating inventory."
    
            # Process payment last to minimize need for rollbacks
            try:
                await bank.withdraw_credits(user, rod_data["cost"])
            except Exception as e:
                # Rollback inventory if payment fails
                await self.inventory.remove_item(user.id, "rod", rod_name)
                self.logger.error(f"Payment failed for rod purchase: {e}")
                return False, "Error processing payment."
    
            return True, f"✅ Purchased {rod_name} for {rod_data['cost']} coins!"
            
        except Exception as e:
            self.logger.error(f"Error in rod purchase: {e}", exc_info=True)
            return False, "❌ An error occurred while processing your purchase."

    async def _can_afford(self, user, cost: int) -> bool:
        """Check if user can afford a purchase."""
        try:
            balance = await bank.get_balance(user)
            return balance >= cost
        except Exception as e:
            self.logger.error(f"Error checking balance: {e}", exc_info=True)
            return False

    async def _equip_rod(self, user: discord.Member, rod_name: str) -> tuple[bool, str]:
        """Helper method to equip a fishing rod"""
        try:
            result = await self.config_manager.get_user_data(user.id)
            if not result.success:
                return False, "Error accessing user data."
                
            user_data = result.data
            if rod_name not in user_data.get("purchased_rods", {}):
                return False, "You don't own this rod!"
                
            update_result = await self.config_manager.update_user_data(
                user.id,
                {"rod": rod_name},
                fields=["rod"]
            )
            
            if not update_result.success:
                return False, "Error equipping rod."
                
            self.logger.debug(f"User {user.name} equipped rod: {rod_name}")
            return True, f"Successfully equipped {rod_name}!"
            
        except Exception as e:
            self.logger.error(f"Error equipping rod: {e}", exc_info=True)
            return False, "An error occurred while equipping the rod."

    async def _equip_bait(self, user: discord.Member, bait_name: str) -> tuple[bool, str]:
        """Helper method to equip bait"""
        try:
            result = await self.config_manager.get_user_data(user.id)
            if not result.success:
                return False, "Error accessing user data."
                
            user_data = result.data
            if not user_data.get("bait", {}).get(bait_name, 0):
                return False, "You don't have any of this bait!"
                
            update_result = await self.config_manager.update_user_data(
                user.id,
                {"equipped_bait": bait_name},
                fields=["equipped_bait"]
            )
            
            if not update_result.success:
                return False, "Error equipping bait."
                
            self.logger.debug(f"User {user.name} equipped bait: {bait_name}")
            return True, f"Successfully equipped {bait_name}!"
            
        except Exception as e:
            self.logger.error(f"Error equipping bait: {e}", exc_info=True)
            return False, "An error occurred while equipping the bait."

    async def sell_fish(self, ctx: commands.Context) -> tuple[bool, int, str]:
        """Sell all fish in inventory and return status, amount earned, and message"""
        try:
            # Get inventory summary first
            summary = await self.inventory.get_inventory_summary(ctx.author.id)
            if not summary:
                return False, 0, "Error accessing inventory data."
            
            if summary["fish_count"] == 0:
                return False, 0, "You have no fish to sell."
            
            total_value = summary["total_value"]
            
            # Process sale using transaction
            async with self.config_manager.config_transaction() as transaction:
                try:
                    # Clear inventory
                    transaction[f"user_{ctx.author.id}"] = {"inventory": []}
                    
                    # Process payment
                    await bank.deposit_credits(ctx.author, total_value)
                    
                    self.logger.info(f"User {ctx.author.name} sold fish for {total_value} coins")
                    return True, total_value, f"Successfully sold all fish for {total_value} coins!"
                    
                except Exception as e:
                    self.logger.error(f"Error processing sale: {e}")
                    raise
            
        except Exception as e:
                self.logger.error(f"Error processing sale: {e}")
                raise

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
            success, msg = await self.inventory.add_item(member.id, item_type.lower(), item_name, amount)
            await ctx.send(msg)
            
            if success:
                self.logger.info(f"Admin {ctx.author.name} added {amount}x {item_name} ({item_type}) to {member.name}")
                
        except Exception as e:
            self.logger.error(f"Error in add_item command: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while adding items. Please try again.")

    @manage.command(name="remove")
    @commands.is_owner()
    async def remove_item(self, ctx, item_type: str, member: discord.Member, item_name: str, amount: int = 1):
        """Remove items from a user's inventory."""
        try:
            success, msg = await self.inventory.remove_item(member.id, item_type.lower(), item_name, amount)
            await ctx.send(msg)
            
            if success:
                self.logger.info(f"Admin {ctx.author.name} removed {amount}x {item_name} ({item_type}) from {member.name}")
                
        except Exception as e:
            self.logger.error(f"Error in remove_item command: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while removing items. Please try again.")

    @manage.command(name="reset")
    @commands.is_owner()
    async def reset_user(self, ctx, member: discord.Member):
        """Reset a user's fishing data."""
        try:
            # Get current data for comparison
            before_result = await self.config_manager.get_user_data(member.id)
            if before_result.success:
                before_data = before_result.data
            
            # Perform reset
            result = await self.config_manager.reset_user_data(member.id)
            if result.success:
                # Get new data for verification
                after_result = await self.config_manager.get_user_data(member.id)
                if after_result.success:
                    after_data = after_result.data
                    
                    # Verify key stats were reset
                    verification = [
                        f"Fish Caught: {before_data.get('fish_caught', '?')} → {after_data.get('fish_caught', 0)}",
                        f"Level: {before_data.get('level', '?')} → {after_data.get('level', 1)}",
                        f"Experience: {before_data.get('experience', '?')} → {after_data.get('experience', 0)}",
                        f"Total Value: {before_data.get('total_value', '?')} → {after_data.get('total_value', 0)}"
                    ]
                    
                    embed = discord.Embed(
                        title="✅ Reset Complete",
                        description=f"Reset fishing data for {member.name}",
                        color=discord.Color.green()
                    )
                    embed.add_field(
                        name="Verification",
                        value="\n".join(verification),
                        inline=False
                    )
                    
                    await ctx.send(embed=embed)
                    self.logger.warning(f"Admin {ctx.author.name} reset fishing data for {member.name}")
                else:
                    await ctx.send("✅ Reset completed but verification failed. Please check the data manually.")
            else:
                await ctx.send(f"❌ Error resetting user data: {result.error}")
        except Exception as e:
            self.logger.error(f"Error resetting user data: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while resetting user data. Please try again.")

    @manage.command(name="stock")
    @commands.is_owner()
    async def reset_stock(self, ctx):
        """Reset the shop's bait stock."""
        try:
            default_stock = {bait: data["daily_stock"] for bait, data in self.data["bait"].items()}
            result = await self.config_manager.update_global_setting("bait_stock", default_stock)
            
            if result.success:
                await ctx.send("✅ Shop stock has been reset!")
                self.logger.info(f"Admin {ctx.author.name} reset shop stock")
            else:
                await ctx.send("❌ Error resetting shop stock.")
        except Exception as e:
            self.logger.error(f"Error resetting shop stock: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while resetting shop stock. Please try again.")

    @manage.command(name="level")
    @commands.is_owner()
    async def set_level(self, ctx, member: discord.Member, level: int):
        """Set a player's fishing level.
        
        Args:
            member: The member to update
            level: The new level to set
        """
        try:
            # Validate level input
            if level < 1:
                await ctx.send("❌ Level must be 1 or higher!")
                return
    
            # Get current user data for verification
            user_data_result = await self.config_manager.get_user_data(member.id)
            if not user_data_result.success:
                await ctx.send("❌ Error accessing user data.")
                return
                
            # Store old level for logging
            old_level = user_data_result.data.get("level", 1)
                
            # Update the level
            update_result = await self.config_manager.update_user_data(
                member.id,
                {"level": level},
                fields=["level"]
            )
            
            if not update_result.success:
                await ctx.send("❌ Error updating level.")
                return
                
            # Verify the update
            verify_result = await self.config_manager.get_user_data(member.id)
            if verify_result.success and verify_result.data.get("level") == level:
                # Create embed for response
                embed = discord.Embed(
                    title="✅ Level Updated",
                    description=f"Updated level for {member.display_name}",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Change Details",
                    value=f"Level {old_level} → {level}",
                    inline=False
                )
                
                # Log the change
                self.logger.warning(
                    f"Admin {ctx.author.name} changed {member.name}'s level "
                    f"from {old_level} to {level}"
                )
                
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Error verifying level update.")
                
        except Exception as e:
            self.logger.error(f"Error in set_level command: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while updating the level.")
    
    @commands.command(name="stockstatus")
    @commands.is_owner()
    async def stock_status(self, ctx):
        """Check the current status of bait stock."""
        try:
            stock_result = await self.config_manager.get_global_setting("bait_stock")
            if not stock_result.success:
                await ctx.send("❌ Error accessing stock data.")
                return
                
            current_stock = stock_result.data
            
            embed = discord.Embed(
                title="🏪 Bait Stock Status",
                color=discord.Color.blue()
            )
            
            # Add current stock levels
            stock_text = "\n".join(
                f"{bait}: {amount}" for bait, amount in current_stock.items()
            )
            embed.add_field(
                name="Current Stock",
                value=stock_text or "No stock data",
                inline=False
            )
            
            # Add background task status
            tasks_status = self.bg_task_manager.status
            status_text = "\n".join(
                f"{name}: {'✅ Running' if status['running'] else '❌ Stopped'}"
                for name, status in tasks_status.items()
            )
            
            embed.add_field(
                name="Background Tasks",
                value=status_text or "No tasks running",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in stock_status command: {e}", exc_info=True)
            await ctx.send("Error checking stock status.")

    @commands.group(name="weathertest")
    @commands.is_owner()
    async def weather_test(self, ctx):
        """Weather testing commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Available commands: simulate, info, set")
    
    @weather_test.command(name="simulate")
    async def simulate_catches(self, ctx, weather: str, location: str = None, trials: int = 100):
        """Simulate catches with specific weather conditions."""
        try:
            if weather not in self.data["weather"]:
                await ctx.send(f"Invalid weather type. Available types: {', '.join(self.data['weather'].keys())}")
                return
                
            if location and location not in self.data["locations"]:
                await ctx.send(f"Invalid location. Available locations: {', '.join(self.data['locations'].keys())}")
                return
                
            user_data_result = await self.config_manager.get_user_data(ctx.author.id)
            if not user_data_result.success:
                await ctx.send("Error accessing user data.")
                return
                
            user_data = user_data_result.data
            location = location or user_data["current_location"]
            time_of_day = self.get_time_of_day()

            # Use "Worm" as default bait for simulations if none is equipped
            default_bait = user_data.get("equipped_bait", "Worm")
            
            # Initialize counters
            catches = {
                "common": 0,
                "uncommon": 0,
                "rare": 0,
                "legendary": 0,
                "bonus_catches": 0
            }
            
            # Run simulation
            embed = discord.Embed(
                title="🌤️ Weather Test Simulation",
                description=f"Running {trials} trials with {weather} weather at {location}",
                color=discord.Color.blue()
            )
            progress_msg = await ctx.send(embed=embed)
            
            for i in range(trials):
                if i % 20 == 0:  # Update progress every 20 trials
                    embed.description = f"Running {trials} trials with {weather} weather at {location}\n\nProgress: {i}/{trials}"
                    await progress_msg.edit(embed=embed)
                    
                result = await self._catch_fish(
                    ctx.author,
                    user_data,
                    user_data.get("equipped_bait", "Worm"),
                    location,
                    weather,
                    time_of_day
                )
                
                if result and result["type"] == "fish":
                    fish_data = self.data["fish"][result["name"]]
                    catches[fish_data["rarity"]] += 1
                    if "bonus_catch" in result:
                        catches["bonus_catches"] += 1
            
            # Calculate percentages
            total_catches = sum(catches.values()) - catches["bonus_catches"]
            percentages = {
                rarity: (count / trials * 100) if trials > 0 else 0
                for rarity, count in catches.items()
            }
            
            # Create result embed
            embed = discord.Embed(
                title=f"🌤️ Weather Test Results: {weather}",
                description=(
                    f"Location: {location}\n"
                    f"Time of Day: {time_of_day}\n"
                    f"Trials: {trials}"
                ),
                color=discord.Color.blue()
            )
            
            # Add catch statistics
            stats_text = "\n".join([
                f"{rarity.title()}: {counts} ({percentages[rarity]:.1f}%)"
                for rarity, counts in catches.items()
                if rarity != "bonus_catches"
            ])
            embed.add_field(
                name="Catch Statistics",
                value=stats_text,
                inline=False
            )
            
            if catches["bonus_catches"] > 0:
                embed.add_field(
                    name="Bonus Catches",
                    value=f"{catches['bonus_catches']} ({catches['bonus_catches']/trials*100:.1f}%)",
                    inline=False
                )
                
            # Add weather effect details
            weather_data = self.data["weather"][weather]
            effects = [
                f"Catch Bonus: {weather_data['catch_bonus']:+.0%}",
                f"Rare Bonus: {weather_data['rare_bonus']:+.0%}"
            ]
            
            if "location_bonus" in weather_data:
                for loc, bonus in weather_data["location_bonus"].items():
                    effects.append(f"{loc} Bonus: {bonus:+.0%}")
                    
            if "time_multiplier" in weather_data:
                for time, bonus in weather_data["time_multiplier"].items():
                    effects.append(f"{time} Multiplier: {bonus:+.0%}")
                    
            if "catch_quantity" in weather_data:
                effects.append(f"Extra Catch Chance: {weather_data['catch_quantity']:.0%}")
                
            embed.add_field(
                name="Weather Effects",
                value="\n".join(effects),
                inline=False
            )
            
            await progress_msg.edit(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in weather simulation: {e}", exc_info=True)
            await ctx.send(f"An error occurred: {str(e)}")
    
    @weather_test.command(name="info")
    async def weather_info(self, ctx, weather: str = None):
        """Display detailed information about weather effects."""
        try:
            if weather and weather not in self.data["weather"]:
                await ctx.send(f"Invalid weather type. Available types: {', '.join(self.data['weather'].keys())}")
                return
                
            if weather:
                # Show specific weather info
                weather_data = self.data["weather"][weather]
                embed = discord.Embed(
                    title=f"🌤️ Weather Info: {weather}",
                    description=weather_data["description"],
                    color=discord.Color.blue()
                )
                
                # Base effects
                effects = [
                    f"Catch Bonus: {weather_data['catch_bonus']:+.0%}",
                    f"Rare Bonus: {weather_data['rare_bonus']:+.0%}"
                ]
                
                # Additional effects
                if "location_bonus" in weather_data:
                    for loc, bonus in weather_data["location_bonus"].items():
                        effects.append(f"{loc} Bonus: {bonus:+.0%}")
                        
                if "time_multiplier" in weather_data:
                    for time, bonus in weather_data["time_multiplier"].items():
                        effects.append(f"{time} Multiplier: {bonus:+.0%}")
                        
                if "catch_quantity" in weather_data:
                    effects.append(f"Extra Catch Chance: {weather_data['catch_quantity']:.0%}")
                    
                if "specific_rarity_bonus" in weather_data:
                    for rarity, bonus in weather_data["specific_rarity_bonus"].items():
                        effects.append(f"{rarity} Bonus: {bonus:+.0%}")
                        
                embed.add_field(
                    name="Effects",
                    value="\n".join(effects),
                    inline=False
                )
                
                embed.add_field(
                    name="Affected Locations",
                    value="\n".join(weather_data["affects_locations"]),
                    inline=False
                )
                
                if "duration_hours" in weather_data:
                    embed.add_field(
                        name="Duration",
                        value=f"{weather_data['duration_hours']} hour(s)",
                        inline=False
                    )
                    
            else:
                # Show overview of all weather types
                embed = discord.Embed(
                    title="🌤️ Weather System Overview",
                    description="Current available weather types and their basic effects",
                    color=discord.Color.blue()
                )
                
                for weather_name, data in self.data["weather"].items():
                    effects = [
                        f"Catch: {data['catch_bonus']:+.0%}",
                        f"Rare: {data['rare_bonus']:+.0%}"
                    ]
                    
                    if "catch_quantity" in data:
                        effects.append(f"Extra Catch: {data['catch_quantity']:.0%}")
                        
                    embed.add_field(
                        name=weather_name,
                        value=f"{data['description']}\n{' | '.join(effects)}",
                        inline=False
                    )
                    
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in weather info: {e}", exc_info=True)
            await ctx.send(f"An error occurred: {str(e)}")
    
    @weather_test.command(name="set")
    @commands.is_owner()
    async def set_weather(self, ctx, weather: str):
        """Manually set the current weather (Owner only)."""
        try:
            if weather not in self.data["weather"]:
                await ctx.send(f"Invalid weather type. Available types: {', '.join(self.data['weather'].keys())}")
                return
                
            result = await self.config_manager.update_global_setting("current_weather", weather)
            if result.success:
                self.bg_task_manager.last_weather_change = datetime.datetime.now()
                
                embed = discord.Embed(
                    title="🌤️ Weather Changed",
                    description=f"Weather set to: {weather}\n{self.data['weather'][weather]['description']}",
                    color=discord.Color.green()
                )
                
                # Add effects summary
                weather_data = self.data["weather"][weather]
                effects = [
                    f"Catch Bonus: {weather_data['catch_bonus']:+.0%}",
                    f"Rare Bonus: {weather_data['rare_bonus']:+.0%}"
                ]
                
                if "catch_quantity" in weather_data:
                    effects.append(f"Extra Catch Chance: {weather_data['catch_quantity']:.0%}")
                    
                embed.add_field(
                    name="Effects",
                    value="\n".join(effects),
                    inline=False
                )
                
                # Show duration if custom
                if "duration_hours" in weather_data:
                    embed.add_field(
                        name="Duration",
                        value=f"{weather_data['duration_hours']} hour(s)",
                        inline=False
                    )
                
                await ctx.send(embed=embed)
            else:
                await ctx.send("Failed to update weather.")
                
        except Exception as e:
            self.logger.error(f"Error setting weather: {e}", exc_info=True)
            await ctx.send(f"An error occurred: {str(e)}")

    @commands.group(name="simulate")
    @commands.is_owner()
    async def simulate(self, ctx):
        """Simulation commands for fishing analysis."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Available commands: profits, setup")
        
    @simulate.command(name="profits")
    async def simulate_profits(self, ctx):
        """Simulate fishing profits across all progression tiers."""
        try:
            # Create embed for results
            embed = discord.Embed(
                title="🎣 Fishing Profit Analysis",
                description="Simulated profits for 1 hour of fishing at each tier",
                color=discord.Color.blue()
            )
                
            # Initialize simulator
            simulator = ProfitSimulator(self.data)
            results = simulator.analyze_all_tiers()
                
            for result in results:
                field_name = f"Level {result['level']} - {result['location']}"
                rarity_text = []
                for rarity, count in result['rarity_breakdown'].items():
                    percentage = (count / result['catches_per_hour']) * 100
                    rarity_text.append(f"{rarity.title()}: {count} ({percentage:.1f}%)")
                    
                field_value = (
                    f"**Setup**: {result['rod']} with {result['bait']}\n"
                    f"**Catches**: {result['catches_per_hour']}/hour\n"
                    f"**Rarity Breakdown**:\n" + "\n".join(rarity_text) + "\n"
                    f"**Financial**:\n"
                    f"• Bait Cost: {result['bait_cost']:,} coins\n"
                    f"• Gross Profit: {result['gross_profit']:,} coins\n"
                    f"• Net Profit: {result['net_profit']:,} coins\n"
                    f"• Per Catch: {result['net_profit']/result['catches_per_hour']:.1f} coins"
                )
                    
                embed.add_field(
                    name=field_name,
                    value=field_value,
                    inline=False
                )
                
            await ctx.send(embed=embed)
                
        except Exception as e:
            self.logger.error(f"Error in profit simulation: {e}")
            await ctx.send("An error occurred while running the simulation.")
        
    @simulate.command(name="setup")
    async def simulate_setup(self, ctx, rod: str, bait: str, location: str):
        """Simulate fishing profits with a specific setup."""
        try:
            # Validate inputs
            if rod not in self.data["rods"]:
                await ctx.send(f"Invalid rod. Available rods: {', '.join(self.data['rods'].keys())}")
                return
                    
            if bait not in self.data["bait"]:
                await ctx.send(f"Invalid bait. Available bait: {', '.join(self.data['bait'].keys())}")
                return
                    
            if location not in self.data["locations"]:
                await ctx.send(f"Invalid location. Available locations: {', '.join(self.data['locations'].keys())}")
                return
                
            # Constants
            ATTEMPTS_PER_HOUR = 360
            SUCCESS_RATE = 0.80  # 80% of attempts result in catches
            successful_catches = int(ATTEMPTS_PER_HOUR * SUCCESS_RATE)
                
            # Get equipment modifiers
            rod_bonus = self.data["rods"][rod]["chance"]
            bait_bonus = self.data["bait"][bait]["catch_bonus"]
            location_mods = self.data["locations"][location]["fish_modifiers"]
            weather_bonus = 0.05  # Base sunny weather bonus
                
            # Calculate catch distribution
            catch_counts = {"common": 0, "uncommon": 0, "rare": 0, "legendary": 0}
            total_value = 0
                
            for _ in range(successful_catches):
                # Calculate weighted chances based on location modifiers
                weights = []
                fish_types = []
                    
                for fish_name, fish_data in self.data["fish"].items():
                    base_chance = fish_data["chance"]
                    loc_modifier = location_mods[fish_name]
                    modified_chance = base_chance * loc_modifier * (1 + rod_bonus + bait_bonus + weather_bonus)
                        
                    weights.append(modified_chance)
                    fish_types.append(fish_name)
                    
                # Normalize weights
                weight_sum = sum(weights)
                weights = [w/weight_sum for w in weights]
                    
                # Determine catch
                caught_fish = random.choices(fish_types, weights=weights)[0]
                fish_data = self.data["fish"][caught_fish]
                    
                catch_counts[fish_data["rarity"]] += 1
                total_value += fish_data["value"]
                
            # Calculate costs and profits
            bait_cost = successful_catches * self.data["bait"][bait]["cost"]
            net_profit = total_value - bait_cost
                
            # Create embed for results
            embed = discord.Embed(
                title="🎣 Custom Setup Analysis",
                description=f"Simulated profits for 1 hour of fishing",
                color=discord.Color.blue()
            )
                
            # Add catch statistics
            rarity_text = []
            total_catches = sum(catch_counts.values())
            for rarity, count in catch_counts.items():
                percentage = (count / total_catches * 100) if total_catches > 0 else 0
                rarity_text.append(f"{rarity.title()}: {count} ({percentage:.1f}%)")
                
            embed.add_field(
                name="Catch Statistics",
                value=(
                    f"**Setup**: {rod} with {bait}\n"
                    f"**Location**: {location}\n"
                    f"**Catches**: {successful_catches}/hour\n"
                    f"**Rarity Breakdown**:\n" + "\n".join(rarity_text)
                ),
                inline=False
            )
                
            embed.add_field(
                name="Financial Breakdown",
                value=(
                    f"• Bait Cost: {bait_cost:,} coins\n"
                    f"• Gross Profit: {total_value:,} coins\n"
                    f"• Net Profit: {net_profit:,} coins\n"
                    f"• Per Catch: {net_profit/successful_catches:.1f} coins"
                ),
                inline=False
            )
                
            await ctx.send(embed=embed)
                
        except Exception as e:
            self.logger.error(f"Error in setup simulation: {e}")
            await ctx.send("An error occurred while running the simulation.")

def setup(bot: Red):
    """Add the cog to the bot."""
    try:
        cog = Fishing(bot)
        bot.add_cog(cog)
        logger = get_logger('setup')
        logger.info("Fishing cog loaded successfully")
    except Exception as e:
        logger = get_logger('setup')
        logger.error(f"Error loading Fishing cog: {e}", exc_info=True)
        raise

