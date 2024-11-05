# ui/menu.py

import discord
import logging
import asyncio
import random
import datetime
from redbot.core import bank
from typing import Dict, Optional
from discord.ui import Button
from .base import BaseView
from ..utils.logging_config import get_logger
from .shop import ShopView

logger = get_logger('menu')

class FishingMenuView(BaseView):
    """Main menu interface for the fishing cog"""
    
    def __init__(self, cog, ctx, user_data: Dict):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.current_page = "main"
        self.logger = get_logger('menu.view')
        self.shop_view = None
        self.inventory_view = None
        self.fishing_in_progress = False
        self.stored_buttons = []
        self.correct_action = None
        
    async def setup(self):
        """Async setup method to initialize the view"""
        try:
            self.logger.debug(f"Setting up FishingMenuView for user {self.ctx.author.name}")
            
            # Initialize timeout manager
            await self.timeout_manager.start()
            
            # Register this view with timeout manager
            await self.timeout_manager.add_view(self, self.timeout)
            self.logger.debug(f"FishingMenuView registered with timeout manager")
            
            # Verify user data
            if not self.user_data:
                self.logger.error(f"User data is empty for {self.ctx.author.name}")
                raise ValueError("User data is missing")
            
            await self.initialize_view()
            self.logger.debug("FishingMenuView setup completed successfully")
            return self
            
        except Exception as e:
            self.logger.error(f"Error in FishingMenuView setup: {str(e)}", exc_info=True)
            raise

    async def initialize_view(self):
        """Initialize the view based on current page"""
        try:
            self.logger.debug(f"Initializing view for page: {self.current_page}")
            self.clear_items()
            
            if self.current_page == "main":
                # Main menu buttons
                buttons = [
                    ("🎣 Fish", "fish", discord.ButtonStyle.green),
                    ("🏪 Shop", "shop", discord.ButtonStyle.blurple),
                    ("🎒 Inventory", "inventory", discord.ButtonStyle.blurple),
                    ("🗺️ Location", "location", discord.ButtonStyle.blurple),
                    ("🌤️ Weather", "weather", discord.ButtonStyle.blurple)
                ]
                
                for label, custom_id, style in buttons:
                    if self.fishing_in_progress and custom_id != "fish":
                        continue  # Skip non-fishing buttons during fishing
                        
                    button = Button(
                        label=label,
                        custom_id=custom_id,
                        style=style,
                        disabled=self.fishing_in_progress and custom_id == "fish"
                    )
                    button.callback = self.handle_button
                    self.add_item(button)
                    
            elif self.current_page == "location":
                # Location selection
                for location_name in self.cog.data["locations"].keys():
                    location_data = self.cog.data["locations"][location_name]
                    requirements = location_data.get("requirements", {})
                    
                    # Check if location is locked
                    is_locked = False
                    if requirements:
                        if (self.user_data["level"] < requirements.get("level", 0) or
                            self.user_data["fish_caught"] < requirements.get("fish_caught", 0)):
                            is_locked = True
                    
                    button = Button(
                        label=location_name,
                        custom_id=f"loc_{location_name}",
                        style=discord.ButtonStyle.green if not is_locked else discord.ButtonStyle.gray,
                        disabled=is_locked
                    )
                    button.callback = self.handle_location_select
                    self.add_item(button)
                    
                back_button = Button(label="Back", custom_id="back", style=discord.ButtonStyle.grey)
                back_button.callback = self.handle_button
                self.add_item(back_button)
                
            else:
                # Add back button for other pages
                back_button = Button(label="Back", custom_id="back", style=discord.ButtonStyle.grey)
                back_button.callback = self.handle_button
                self.add_item(back_button)

        except Exception as e:
            self.logger.error(f"Error in initialize_view: {str(e)}", exc_info=True)
            raise

    async def generate_embed(self) -> discord.Embed:
        """Generate the appropriate embed based on current page"""
        try:
            self.logger.debug(f"Generating embed for page: {self.current_page}")
            
            if self.current_page == "main":
                embed = discord.Embed(
                    title="🎣 Fishing Menu",
                    description="Welcome to the fishing menu! What would you like to do?",
                    color=discord.Color.blue()
                )
                
                # Get currency name
                try:
                    is_global = await bank.is_global()
                    if is_global:
                        currency_name = await bank.get_currency_name()
                    else:
                        currency_name = await bank.get_currency_name(self.ctx.guild)
                except Exception as e:
                    self.logger.error(f"Error getting currency name: {e}")
                    currency_name = "coins"
                
                # Get balance
                try:
                    balance = await bank.get_balance(self.ctx.author)
                except Exception as e:
                    self.logger.error(f"Error getting balance: {e}")
                    balance = 0
                
                # Add current status
                embed.add_field(
                    name="Current Status",
                    value=(
                        f"🎣 Rod: {self.user_data['rod']}\n"
                        f"🪱 Bait: {self.user_data.get('equipped_bait', 'None')}\n"
                        f"📍 Location: {self.user_data['current_location']}\n"
                        f"💰 Balance: {balance:,} {currency_name}"
                    ),
                    inline=False
                )
    
                # Get level progress
                progress = await self.cog.level_manager.get_level_progress(self.ctx.author.id)
                if progress:
                    xp_info = (
                        f"📊 Level: {progress['current_level']}\n"
                        f"🎯 Progress: {progress['progress']:.1f}%"
                    )
                    if progress['xp_for_next'] is not None:
                        xp_info += f"\n⭐ XP until next level: {progress['xp_for_next']:,}"
                else:
                    xp_info = f"📊 Level: {self.user_data['level']}"
                
                # Add statistics with enhanced XP info
                embed.add_field(
                    name="Statistics",
                    value=(
                        f"🐟 Fish Caught: {self.user_data['fish_caught']}\n"
                        f"{xp_info}"
                    ),
                    inline=False
                )
                
            elif self.current_page == "location":
                embed = discord.Embed(
                    title="🗺️ Select Location",
                    description="Choose a fishing location:",
                    color=discord.Color.blue()
                )
                
                for loc_name, loc_data in self.cog.data["locations"].items():
                    # Check if location is locked
                    requirements = loc_data.get("requirements", {})
                    is_locked = False
                    if requirements:
                        if (self.user_data["level"] < requirements.get("level", 0) or
                            self.user_data["fish_caught"] < requirements.get("fish_caught", 0)):
                            is_locked = True
                    
                    status = "🔒 Locked" if is_locked else "📍 Current" if loc_name == self.user_data["current_location"] else "✅ Available"
                    
                    # Format requirements if they exist
                    req_text = ""
                    if requirements:
                        req_text = f"\nRequires: Level {requirements['level']}, {requirements['fish_caught']} fish caught"
                    
                    embed.add_field(
                        name=f"{loc_name} ({status})",
                        value=f"{loc_data['description']}{req_text}",
                        inline=False
                    )
                    
            elif self.current_page == "weather":
                weather_result = await self.cog.config_manager.get_global_setting("current_weather")
                current_weather = weather_result.data if weather_result.success else "Sunny"

                # Get weather data from cog's data dictionary
                weather_data = self.cog.data["weather"][current_weather]

                # Calculate time until next weather change
                now = datetime.datetime.now()
                last_change = self.cog.bg_task_manager.last_weather_change
                if last_change is None:
                    time_remaining = "Unknown"
                else:
                    next_change = last_change + datetime.timedelta(hours=1)
                    remaining = next_change - now
                    if remaining.total_seconds() <= 0:
                        time_remaining = "Soon"
                    else:
                        minutes = int(remaining.total_seconds() // 60)
                        seconds = int(remaining.total_seconds() % 60)
                        time_remaining = f"{minutes}m {seconds}s"
                
                embed = discord.Embed(
                    title="🌤️ Current Weather",
                    description=(
                        f"**{current_weather}**\n"
                        f"{weather_data['description']}\n\n"
                        f"⏳ Next change in: {time_remaining}"
                    ),
                    color=discord.Color.blue()
                )
                
                # Add effects
                effects = []
                if "catch_bonus" in weather_data:
                    effects.append(f"Catch rate: {weather_data['catch_bonus']*100:+.0f}%")
                if "rare_bonus" in weather_data:
                    effects.append(f"Rare fish bonus: {weather_data['rare_bonus']*100:+.0f}%")
                
                if effects:
                    embed.add_field(
                        name="Current Effects",
                        value="\n".join(effects),
                        inline=False
                    )
                    
                # Add affected locations
                if weather_data.get("affects_locations"):
                    embed.add_field(
                        name="Affects Locations",
                        value="\n".join(f"• {loc}" for loc in weather_data["affects_locations"]),
                        inline=False
                    )
            
            return embed
            
        except Exception as e:
            self.logger.error(f"Error generating embed: {str(e)}", exc_info=True)
            raise

    async def handle_button(self, interaction: discord.Interaction):
        """Handle button interactions"""
        try:
            custom_id = interaction.data["custom_id"]
            
            if custom_id == "fish":
                if self.fishing_in_progress:
                    await interaction.response.send_message(
                        "You're already fishing!",
                        ephemeral=True,
                        delete_after=2
                    )
                    return
                    
                # Start fishing process immediately with the interaction
                self.fishing_in_progress = True
                await interaction.response.defer()  # Defer the response since we'll handle it in do_fishing

                # Ensure we have the current message reference
                if not self.message:
                    self.message = interaction.message
                    
                await self.initialize_view()
                await self.do_fishing(interaction)
                return
                
                # Create initial fishing embed
                fishing_embed = discord.Embed(
                    title="🎣 Fishing in Progress",
                    description="Casting line...",
                    color=discord.Color.blue()
                )
                
                # Initial response and store the message reference
                await interaction.response.edit_message(embed=fishing_embed, view=self)
                self.message = await interaction.original_response()
                await self.do_fishing(interaction)
                return
                
            elif custom_id == "menu":
                # Instead of importing FishingMenuView, use cog's create_menu method
                menu_view = await self.cog.create_menu(self.ctx, self.user_data)
                embed = await menu_view.generate_embed()
                await interaction.response.edit_message(embed=embed, view=menu_view)
                menu_view.message = await interaction.original_response()
                return
                
            elif custom_id in ["shop", "inventory"]:
                # Use dynamic import to avoid circular dependency
                if custom_id == "shop":
                    self.shop_view = await ShopView(self.cog, self.ctx, self.user_data).setup()
                    self.shop_view.parent_menu_view = self
                    embed = await self.shop_view.generate_embed()
                    
                    # Handle view transition with explicit timeout management
                    self.logger.debug("Transitioning to shop view")
                    await self.timeout_manager.handle_view_transition(self, self.shop_view)
                    
                    await interaction.response.edit_message(embed=embed, view=self.shop_view)
                    self.shop_view.message = await interaction.original_response()
                    self.logger.debug("Shop view transition complete")
                else:  # Inventory
                    self.logger.debug("Transitioning to inventory view")
                    from .inventory import InventoryView
                    self.inventory_view = InventoryView(self.cog, self.ctx, self.user_data)
                    await self.inventory_view.initialize_view()
                    embed = await self.inventory_view.generate_embed()
                    
                    # Handle view transition with explicit timeout management
                    await self.timeout_manager.handle_view_transition(self, self.inventory_view)
                    
                    await interaction.response.edit_message(embed=embed, view=self.inventory_view)
                    self.inventory_view.message = await interaction.original_response()
                    self.logger.debug("Inventory view transition complete")
                
            elif custom_id in ["location", "weather"]:
                self.current_page = custom_id
                await self.initialize_view()
                embed = await self.generate_embed()
                await interaction.response.edit_message(embed=embed, view=self)
                self.message = await interaction.original_response()
                
            elif custom_id == "back":
                self.current_page = "main"
                await self.initialize_view()
                embed = await self.generate_embed()
                await interaction.response.edit_message(embed=embed, view=self)
                self.message = await interaction.original_response()
                
        except Exception as e:
            self.logger.error(f"Error handling button: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred. Please try again.",
                    ephemeral=True,
                    delete_after=2
                )

    def get_time_of_day(self) -> str:
        """Helper method to get current time of day"""
        hour = datetime.datetime.now().hour
        if 5 <= hour < 7:
            return "Dawn"
        elif 7 <= hour < 17:
            return "Day"
        elif 17 <= hour < 19:
            return "Dusk"
        else:
            return "Night"

    async def do_fishing(self, interaction: discord.Interaction):
        """Handle the fishing process after initial interaction"""
        try:
            # Get fresh user data to ensure accurate equipment check
            user_data_result = await self.cog.config_manager.get_user_data(self.ctx.author.id)
            if user_data_result.success:
                self.user_data = user_data_result.data
    
            # Ensure we have the message reference
            if not self.message:
                self.message = interaction.message
            
            # Check for equipped bait first
            if not self.user_data["equipped_bait"]:
                self.fishing_in_progress = False
                await self.initialize_view()
                message = await interaction.followup.send(
                    "🚫 You need to equip bait first! Use the Inventory menu to equip some bait.",
                    ephemeral=True,
                    wait=True
                )
                self.cog.bot.loop.create_task(self.delete_after_delay(message))
                main_embed = await self.generate_embed()
                if self.message:
                    await self.message.edit(embed=main_embed, view=self)
                return
    
            # Clear UI of menu buttons during fishing
            self.stored_buttons = self.children.copy()
            self.clear_items()
                
            # Initial response showing casting
            fishing_embed = discord.Embed(
                title="🎣 Fishing in Progress",
                description="Casting line...",
                color=discord.Color.blue()
            )
            
            # Since interaction was already responded to, use message edit directly
            if self.message:
                await self.message.edit(embed=fishing_embed, view=self)
                
            # Wait for fish to bite
            await asyncio.sleep(random.uniform(2, 5))
                
            # Set up catch attempt buttons
            catch_actions = ["catch", "grab", "snag", "hook", "reel"]
            self.correct_action = random.choice(catch_actions)
                
            # Create all catch attempt buttons
            for action in catch_actions:
                button = Button(
                    label=action.capitalize(),
                    custom_id=f"catch_{action}",
                    style=discord.ButtonStyle.primary
                )
                button.callback = self.handle_catch_attempt
                self.add_item(button)
                
            fishing_embed = discord.Embed(
                title="🎣 Fishing in Progress",
                description=f"Quick! Click **{self.correct_action}** to catch the fish!",
                color=discord.Color.blue()
            )
            await self.message.edit(embed=fishing_embed, view=self)
    
            # Add a catch_attempted flag
            self.catch_attempted = False
                
            # Set up timeout for catch attempt
            await asyncio.sleep(5.0)
                
            # Only handle timeout if no catch attempt was made
            if not self.catch_attempted and not self.children[0].disabled:
                # Consume bait on timeout
                update_data = {"bait": self.user_data.get("bait", {})}
                equipped_bait = self.user_data.get("equipped_bait")
                if equipped_bait:
                    update_data["bait"][equipped_bait] = update_data["bait"].get(equipped_bait, 0) - 1
                    if update_data["bait"][equipped_bait] <= 0:
                        del update_data["bait"][equipped_bait]
                        update_data["equipped_bait"] = None
                    await self.cog.config_manager.update_user_data(self.ctx.author.id, update_data)
                    self.logger.debug("Bait consumed on timeout")
    
                fishing_embed = discord.Embed(
                    title="🎣 Too Slow!",
                    description="The fish got away!\n\nReturning to menu...",
                    color=discord.Color.red()
                )
                await self.message.edit(embed=fishing_embed)
                await asyncio.sleep(2)
    
                # Reset fishing state and get fresh user data
                self.fishing_in_progress = False
                user_data_result = await self.cog.config_manager.get_user_data(self.ctx.author.id)
                if user_data_result.success:
                    self.user_data = user_data_result.data
                    self.current_page = "main"  # Reset to main page
                    await self.initialize_view()  # Reinitialize the view with updated data
                    main_embed = await self.generate_embed()  # Generate new embed
                    await self.message.edit(embed=main_embed, view=self)  # Update the message
                else:
                    self.fishing_in_progress = False
                    await self.initialize_view()
                    message = await interaction.followup.send(
                        "Error accessing user data. Please try again.",
                        ephemeral=True,
                        wait=True
                    )
                    self.cog.bot.loop.create_task(self.delete_after_delay(message))
                    main_embed = await self.generate_embed()
                    await self.message.edit(embed=main_embed, view=self)
                    return
    
        except Exception as e:
            self.logger.error(f"Error in fishing process: {e}", exc_info=True)
            self.fishing_in_progress = False
            await self.initialize_view()
            message = await interaction.followup.send(
                "An error occurred while fishing. Please try again.",
                ephemeral=True,
                wait=True
            )
            self.cog.bot.loop.create_task(self.delete_after_delay(message))
            main_embed = await self.generate_embed()
            if self.message:  # Add null check here too
                await self.message.edit(embed=main_embed, view=self)

    async def handle_catch_attempt(self, interaction: discord.Interaction):
        """Handle fishing catch attempt button press"""
        try:
            # Set catch_attempted flag
            self.catch_attempted = True
            self.logger.debug(f"Starting catch attempt for user {interaction.user.id}")
            
            # Get the button that was pressed
            button_id = interaction.data["custom_id"]
            action = button_id.replace("catch_", "")
            self.logger.debug(f"Catch action attempted: {action}")
            
            # Disable all buttons immediately
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(view=self)
    
            # Always consume bait on attempt
            user_data_result = await self.cog.config_manager.get_user_data(interaction.user.id)
            if user_data_result.success:
                update_data = {"bait": user_data_result.data.get("bait", {})}
                equipped_bait = user_data_result.data.get("equipped_bait")
                if equipped_bait:
                    update_data["bait"][equipped_bait] = update_data["bait"].get(equipped_bait, 0) - 1
                    if update_data["bait"][equipped_bait] <= 0:
                        del update_data["bait"][equipped_bait]
                        update_data["equipped_bait"] = None
                    await self.cog.config_manager.update_user_data(interaction.user.id, update_data)
                    self.logger.debug("Bait consumed")
            
            # Check if correct button was pressed
            if action == self.correct_action:
                self.logger.debug("Correct action selected, processing catch")
                
                # Get weather first
                weather_result = await self.cog.config_manager.get_global_setting("current_weather")
                current_weather = weather_result.data if weather_result.success else "Sunny"
                
                # Process catch
                catch = await self.cog._catch_fish(
                    interaction.user,
                    self.user_data,
                    self.user_data["equipped_bait"],
                    self.user_data["current_location"],
                    current_weather,
                    self.get_time_of_day()
                )
                
                if catch:
                    item_type = catch.get("type", "fish")
                    item_name = catch["name"]
                    item_value = catch["value"]
                    xp_gained = catch.get("xp_gained", 0)
                    
                    # Get appropriate variant based on type
                    if item_type == "fish":
                        variant = random.choice(self.cog.data["fish"][item_name]["variants"])
                        catch_emoji = "🐟"
                    else:  # junk
                        variant = random.choice(self.cog.data["junk"][item_name]["variants"])
                        catch_emoji = "📦"
                    
                    self.logger.debug(f"Processing {item_type} catch with XP gain: {xp_gained}")
                    self.logger.debug(f"Current user data before XP award: {self.user_data}")
                    
                    # Update user data
                    await self.cog._update_total_value(interaction.user, item_value)
                    
                    # Award XP and check for level up
                    xp_success, old_level, new_level = await self.cog.level_manager.award_xp(
                        interaction.user.id,
                        xp_gained
                    )
                    
                    self.logger.debug(
                        f"XP award result - Success: {xp_success}, "
                        f"Old Level: {old_level}, New Level: {new_level}"
                    )
                    
                    # Force refresh the cache to get updated XP data
                    await self.cog.config_manager.refresh_cache(interaction.user.id)
                    self.logger.debug("Cache refreshed after XP award")
                    
                    # Get fresh user data after XP update
                    fresh_data_result = await self.cog.config_manager.get_user_data(interaction.user.id)
                    if fresh_data_result.success:
                        self.user_data = fresh_data_result.data
                        self.logger.debug(f"Fresh user data after XP: {fresh_data_result.data}")
                    else:
                        self.logger.error("Failed to get fresh data after XP award")
                    
                    if xp_success and old_level and new_level:
                        catch["level_up"] = {
                            "old_level": old_level,
                            "new_level": new_level
                        }
                    
                    # Get level progress with fresh data
                    progress = await self.cog.level_manager.get_level_progress(interaction.user.id)
                    self.logger.debug(f"Level progress after catch: {progress}")
                    
                    # Create dynamic catch message based on item type
                    catch_msg = (
                        f"You caught a {variant} ({item_name}) worth {item_value} coins!"
                        if item_type == "fish" else
                        f"You found a {variant} ({item_name}) worth {item_value} coins!"
                    )
                    
                    description = [
                        catch_msg,
                        f"Gained {xp_gained} XP!",
                        f"\nLocation: {self.user_data['current_location']}",
                        f"Weather: {current_weather}"
                    ]
                    
                    if "level_up" in catch:
                        level_up = catch["level_up"]
                        description.append(
                            f"\n🎉 **LEVEL UP!** 🎉\n"
                            f"Level {level_up['old_level']} → {level_up['new_level']}"
                        )
                    elif progress:
                        description.append(
                            f"\nLevel {progress['current_level']} "
                            f"({progress['progress']:.1f}% to next level)"
                        )
                    
                    fishing_embed = discord.Embed(
                        title=f"{catch_emoji} Successful Catch!",
                        description="\n".join(description),
                        color=discord.Color.green()
                    )
                    
                    # Update fish count
                    update_result = await self.cog.config_manager.update_user_data(
                        interaction.user.id,
                        {"fish_caught": self.user_data["fish_caught"] + 1},
                        fields=["fish_caught"]
                    )
                    if not update_result.success:
                        self.logger.error("Failed to update fish_caught count")
                else:
                    fishing_embed = discord.Embed(
                        title="🎣 Nothing!",
                        description="You didn't catch anything this time!\n\nReturning to menu...",
                        color=discord.Color.red()
                    )
            else:
                # Wrong button pressed
                fishing_embed = discord.Embed(
                    title="🎣 Wrong Move!",
                    description="Whatever was on the line got away!\n\nReturning to menu...",
                    color=discord.Color.red()
                )
            
            await self.message.edit(embed=fishing_embed)
            await asyncio.sleep(4)  # Brief pause to show result
            
            # Reset fishing state and get fresh user data
            self.fishing_in_progress = False
            user_data_result = await self.cog.config_manager.get_user_data(interaction.user.id)
            if user_data_result.success:
                self.user_data = user_data_result.data
                self.logger.debug(f"Final user data update: {self.user_data}")
                self.current_page = "main"  # Reset to main page
                await self.initialize_view()  # Reinitialize the view with updated data
                main_embed = await self.generate_embed()  # Generate new embed
                await self.message.edit(embed=main_embed, view=self)  # Update the message
                self.logger.debug("Menu view updated with final data")
            else:
                self.logger.error("Failed to get final user data update")
                
        except Exception as e:
            self.logger.error(f"Error in catch attempt: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while processing your catch. Please try again.",
                ephemeral=True
            )
    
    async def handle_location_select(self, interaction: discord.Interaction):
        """Handle location selection button interactions"""
        try:
            custom_id = interaction.data["custom_id"]
            location_name = custom_id.replace("loc_", "")
            
            # Verify location exists
            if location_name not in self.cog.data["locations"]:
                await interaction.response.send_message(
                    "Invalid location selection.",
                    ephemeral=True,
                    delete_after=2
                )
                return
                
            location_data = self.cog.data["locations"][location_name]
            
            # Check requirements
            meets_req, msg = await self.cog.check_requirements(
                self.user_data,
                location_data["requirements"]
            )
            if not meets_req:
                await interaction.response.send_message(
                    msg, 
                    ephemeral=True,
                    delete_after=2
                )
                return
                
            # Update location using ConfigManager
            update_result = await self.cog.config_manager.update_user_data(
                self.ctx.author.id,
                {"current_location": location_name},
                fields=["current_location"]
            )
            
            if not update_result.success:
                await interaction.response.send_message(
                    "Error updating location. Please try again.",
                    ephemeral=True,
                    delete_after=2
                )
                return
                
            # Update local user data
            self.user_data["current_location"] = location_name
            
            # Return to main menu
            self.current_page = "main"
            await interaction.response.defer()
            await self.update_view()
            
            # Send confirmation with manual deletion
            message = await interaction.followup.send(
                f"🌍 Now fishing at: {location_name}\n{location_data['description']}",
                ephemeral=True,
                wait=True
            )
            self.cog.bot.loop.create_task(self.delete_after_delay(message))
            
        except Exception as e:
            self.logger.error(f"Error in handle_location_select: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while changing location. Please try again.",
                    ephemeral=True,
                    delete_after=2
                )

    async def consume_bait(self, interaction: discord.Interaction):
        """Helper method to consume bait"""
        try:
            user_data_result = await self.cog.config_manager.get_user_data(interaction.user.id)
            if user_data_result.success:
                update_data = {"bait": user_data_result.data.get("bait", {})}
                equipped_bait = user_data_result.data.get("equipped_bait")
                if equipped_bait:
                    update_data["bait"][equipped_bait] = update_data["bait"].get(equipped_bait, 0) - 1
                    if update_data["bait"][equipped_bait] <= 0:
                        del update_data["bait"][equipped_bait]
                        update_data["equipped_bait"] = None
                    await self.cog.config_manager.update_user_data(interaction.user.id, update_data)
                    self.logger.debug("Bait consumed")
        except Exception as e:
            self.logger.error(f"Error consuming bait: {e}")
    
    async def delete_after_delay(self, message):
        """Helper method to delete a message after a delay"""
        try:
            await asyncio.sleep(2)  # Wait 2 seconds
            await message.delete()
        except discord.NotFound:
            pass  # Message already deleted
        except Exception as e:
            self.logger.error(f"Error in delete_after_delay: {e}")
    
    async def update_view(self):
        """Update the message with current embed and view"""
        try:
            await self.initialize_view()
            embed = await self.generate_embed()
            await self.message.edit(embed=embed, view=self)
        except Exception as e:
            self.logger.error(f"Error updating view: {e}", exc_info=True)
            await self.ctx.send("Error updating menu view. Please try again.")
    
    async def start(self):
        """Start the menu view"""
        embed = await self.generate_embed()
        self.message = await self.ctx.send(embed=embed, view=self)
        return self
