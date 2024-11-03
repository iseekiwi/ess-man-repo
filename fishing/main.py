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
        }

        # Initialize inventory manager
        self.inventory = InventoryManager(bot, self.config_manager, self.data)
        self.logger.debug("Inventory manager initialized")
        
        # Initialize background tasks
        self.bg_task_manager = TaskManager(bot, self.config_manager, self.data)

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
        asyncio.create_task(self.bg_task_manager.stop())
        self.logger.info("Cog unloaded, background tasks cancelled")

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
        user_data: dict,
        bait_type: str,
        location: str,
        weather: str,
        time_of_day: str
    ) -> dict:
        """Calculate catch results with all modifiers."""
        try:
            # Calculate catch chance
            base_chance = self.data["rods"][user_data["rod"]]["chance"]
            bait_bonus = self.data["bait"][bait_type]["catch_bonus"]
            weather_bonus = self.data["weather"][weather].get("catch_bonus", 0)
            time_bonus = self.data["time"][time_of_day].get("catch_bonus", 0)
            
            total_chance = base_chance + bait_bonus + weather_bonus + time_bonus
            self.logger.debug(f"Catch chances - Base: {base_chance}, Total: {total_chance}")
            
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
                    self.logger.warning(f"Fish type {fish} missing variants!")
                    continue
                    
                weight = data["chance"] * location_mods[fish]
                if weather_rare_bonus and data["rarity"] in ["rare", "legendary"]:
                    weight *= (1 + weather_rare_bonus)
                weighted_fish.append(fish)
                weights.append(weight)

            if not weighted_fish:
                self.logger.warning("No valid fish types found!")
                return None

            caught_fish = random.choices(weighted_fish, weights=weights, k=1)[0]
            fish_data = self.data["fish"][caught_fish]
            self.logger.debug(f"Fish caught: {caught_fish}")
            return {"name": caught_fish, "value": self.data["fish"][caught_fish]["value"]}

            # Calculate XP reward
            location_data = self.data["locations"][location]
            xp_reward = self.level_manager.calculate_xp_reward(
                fish_data["rarity"],
                location_mods[caught_fish]  # Use location modifier as XP modifier
            )
    
            self.logger.debug(f"Fish caught: {caught_fish}, XP reward: {xp_reward}")
            return {
                "name": caught_fish,
                "value": fish_data["value"],
                "xp_gained": xp_reward
            }
        
        except Exception as e:
            self.logger.error(f"Error in _catch_fish: {e}", exc_info=True)
            return None

    async def _add_to_inventory(self, user, fish_name: str) -> bool:
        """Add fish to user's inventory."""
        success, _ = await self.inventory.add_item(user.id, "fish", fish_name)
        return success

    async def _update_total_value(self, user, value: int) -> bool:
        """Update total value and check for level up."""
        try:
            user_data_result = await self.config_manager.get_user_data(user.id)
            if not user_data_result.success:
                return False
                
            user_data = user_data_result.data
            old_level = user_data["level"]
            
            # Calculate new level
            fish_caught = user_data["fish_caught"] + 1  # Increment fish count
            new_level = max(1, fish_caught // 50)
            
            # Prepare updates
            updates = {
                "total_value": user_data["total_value"] + value,
                "fish_caught": fish_caught,
                "level": new_level
            }
            
            # Update user data
            update_result = await self.config_manager.update_user_data(
                user.id,
                updates,
                fields=["total_value", "fish_caught", "level"]
            )
            
            if not update_result.success:
                return False
                
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
            
    @commands.command(name="fisherboard")
    async def fisherboard(self, ctx):
        """Display detailed fishing leaderboard in an embed."""
        try:
            all_users_result = await self.config_manager.get_all_global_settings()
            if not all_users_result.success:
                await ctx.send("❌ Error accessing leaderboard data. Please try again.")
                return
                
            all_users = all_users_result.data.get("users", {})
            
            # Filter and sort users
            fisher_stats = [
                (user_id, data["total_value"], data["fish_caught"])
                for user_id, data in all_users.items()
                if data["total_value"] > 0 or data["fish_caught"] > 0
            ]
            
            if not fisher_stats:
                await ctx.send("🏆 The fisherboard is empty!")
                return
    
            # Sort by total value (career earnings)
            fisher_stats.sort(key=lambda x: x[1], reverse=True)
            
            embed = discord.Embed(
                title="🎣 Fishing Leaderboard",
                description="Top fishers ranked by career earnings",
                color=discord.Color.blue()
            )
    
            # Process top 10 users
            for rank, (user_id, value, fish_caught) in enumerate(fisher_stats[:10], 1):
                try:
                    user = await self.bot.fetch_user(user_id)
                    if user:
                        # Calculate catch rate
                        total_casts = all_users[user_id].get("total_casts", fish_caught)
                        catch_rate = (fish_caught / total_casts * 100) if total_casts > 0 else 0
                        
                        # Format stats with thousands separators
                        value_formatted = "{:,}".format(value)
                        fish_formatted = "{:,}".format(fish_caught)
                        
                        embed.add_field(
                            name=f"#{rank} {user.name}",
                            value=(
                                f"💰 **{value_formatted}** coins\n"
                                f"🐟 {fish_formatted} catches\n"
                                f"📊 {catch_rate:.1f}% success rate"
                            ),
                            inline=False
                        )
                except Exception as e:
                    self.logger.warning(f"Could not fetch user {user_id}: {e}")
                    continue
    
            embed.set_footer(text=f"Total Registered Fishers: {len(fisher_stats)}")
            await ctx.send(embed=embed)
            self.logger.debug("Leaderboard displayed successfully")
    
        except Exception as e:
            self.logger.error(f"Error displaying leaderboard: {e}", exc_info=True)
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
            result = await self.config_manager.reset_user_data(member.id)
            if result.success:
                await ctx.send(f"✅ Reset fishing data for {member.name}")
                self.logger.warning(f"Admin {ctx.author.name} reset fishing data for {member.name}")
            else:
                await ctx.send("❌ Error resetting user data.")
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
