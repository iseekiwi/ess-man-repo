# ui/menu.py

import discord
import logging
import asyncio
import random
import datetime
from redbot.core import bank
from typing import Dict, Optional
from discord.ui import Button, Select
from .base import BaseView
from ..utils.logging_config import get_logger
from .shop import ShopView

logger = get_logger('menu')

class FishingMenuView(BaseView):
    """Main menu interface for the fishing cog"""
    
    def __init__(self, cog, ctx, user_data: Dict):
        super().__init__(cog, ctx, timeout=300)  # 5 minute inactivity timeout
        self.user_data = user_data
        self.current_page = "main"
        self.logger = get_logger('menu.view')
        self.shop_view = None
        self.inventory_view = None
        self.fishing_in_progress = False
        self.location_tab = "normal"  # "normal" or "specialized"
        self.stored_buttons = []
        self.correct_action = None
        self._catch_event = asyncio.Event()
        self._catch_processed = asyncio.Event()
        self._stop_fishing_event = asyncio.Event()
        
    async def setup(self):
        """Async setup method to initialize the view"""
        try:
            self.logger.debug(f"Setting up FishingMenuView for user {self.ctx.author.name}")
            
            # Initialize timeout manager
            await self.timeout_manager.start()
            
            # Register this view with timeout manager
            await self.timeout_manager.add_view(self, self._custom_timeout)
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

    async def on_timeout(self):
        """Show a clean session-ended embed when the menu times out."""
        try:
            self.logger.info(f"FishingMenuView timed out for user {self.ctx.author.id}")
            # Stop any in-progress fishing loop
            self.fishing_in_progress = False
            self._stop_fishing_event.set()

            self.clear_items()
            embed = discord.Embed(
                title="🎣 Session Ended",
                description="Your fishing session has expired due to inactivity.",
                color=discord.Color.greyple()
            )
            if self.message:
                try:
                    await self.message.edit(embed=embed, view=self)
                except discord.NotFound:
                    pass

            await self.timeout_manager.remove_view(self)
            self._release_session()

        except Exception as e:
            self.logger.error(f"Error in FishingMenuView on_timeout: {e}", exc_info=True)
            self._release_session()

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

                # Stop button — always available on main menu
                if not self.fishing_in_progress:
                    stop_btn = Button(
                        label="Stop Fishing",
                        custom_id="stop",
                        style=discord.ButtonStyle.red
                    )
                    stop_btn.callback = self.handle_button
                    self.add_item(stop_btn)

            elif self.current_page == "location":
                specialist_names = {"Shallow Creek", "Marshlands", "Coral Reef", "Abyssal Trench"}
                is_specialist = self.location_tab == "specialized"

                # Back button
                back_button = Button(label="Back", custom_id="back", style=discord.ButtonStyle.grey)
                back_button.callback = self.handle_button
                self.add_item(back_button)

                # Location tab navigation buttons
                prev_btn = Button(
                    label="<",
                    style=discord.ButtonStyle.grey,
                    custom_id="loc_prev",
                    disabled=(self.location_tab == "normal")
                )
                prev_btn.callback = self.handle_button
                self.add_item(prev_btn)

                tab_label = "Normal" if self.location_tab == "normal" else "Specialized"
                tab_btn = Button(
                    label=tab_label,
                    style=discord.ButtonStyle.grey,
                    custom_id="loc_tab_indicator",
                    disabled=True
                )
                self.add_item(tab_btn)

                next_btn = Button(
                    label=">",
                    style=discord.ButtonStyle.grey,
                    custom_id="loc_next",
                    disabled=(self.location_tab == "specialized")
                )
                next_btn.callback = self.handle_button
                self.add_item(next_btn)

                # Location select dropdown (filtered by tab)
                location_options = []
                for loc_name, loc_data in self.cog.data["locations"].items():
                    # Filter by current tab
                    if is_specialist != (loc_name in specialist_names):
                        continue

                    requirements = loc_data.get("requirements")
                    is_locked = False
                    if requirements:
                        if (self.user_data["level"] < requirements.get("level", 0) or
                            self.user_data["fish_caught"] < requirements.get("fish_caught", 0)):
                            is_locked = True
                    if is_locked:
                        continue
                    location_options.append(discord.SelectOption(
                        label=loc_name,
                        value=loc_name,
                        description=loc_data["description"][:100],
                        default=(loc_name == self.user_data.get("current_location"))
                    ))

                if location_options:
                    location_select = Select(
                        placeholder="Select a location...",
                        options=location_options,
                        custom_id="location_select"
                    )
                    location_select.callback = self.handle_location_dropdown
                    self.add_item(location_select)

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
                    title=f"🎣 {self.ctx.author.display_name}'s Fishing Menu",
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
                inventory_count = len(self.user_data.get("inventory", []))
                inventory_capacity = self.user_data.get("inventory_capacity", 5)
                embed.add_field(
                    name="Current Status",
                    value=(
                        f"🎣 Rod: `{self.user_data['rod']}`\n"
                        f"🪱 Bait: `{self.user_data.get('equipped_bait', 'None')}`\n"
                        f"📍 Location: `{self.user_data['current_location']}`\n"
                        f"🎒 Inventory: `{inventory_count}/{inventory_capacity}`\n"
                        f"💰 Balance: `{balance:,}` {currency_name}"
                    ),
                    inline=False
                )
    
                # Add catch chance calculation
                current_rod = self.user_data['rod']
                equipped_bait = self.user_data.get('equipped_bait')
                location = self.user_data['current_location']
    
                # Get current weather
                weather_result = await self.cog.config_manager.get_global_setting("current_weather")
                current_weather = weather_result.data if weather_result.success else "Sunny"
                weather_data = self.cog.data["weather"][current_weather]
                
                # Calculate base chances
                base_chance = self.cog.data["rods"][current_rod]["chance"]
                if equipped_bait:
                    bait_base = self.cog.data["bait"][equipped_bait]["catch_bonus"]
                    bait_effectiveness = self.cog.data["bait"][equipped_bait].get("effectiveness", {}).get(location, 1.0)
                    bait_bonus = bait_base * bait_effectiveness
                else:
                    bait_bonus = 0
                
                # Only apply weather bonuses if location is affected
                weather_bonus = 0
                if location in weather_data.get("affects_locations", []):
                    weather_bonus = weather_data.get("catch_bonus", 0)
                    location_bonus = weather_data.get("location_bonus", {}).get(location, 0)
                    weather_bonus += location_bonus
                    time_multiplier = weather_data.get("time_multiplier", {}).get(self.get_time_of_day(), 0)
                    weather_bonus += time_multiplier
                    
                time_bonus = self.cog.data["time"][self.get_time_of_day()].get("catch_bonus", 0)
                
                total_chance = (base_chance + bait_bonus + weather_bonus + time_bonus) * 100
                
                # Add catch chance breakdown
                chance_breakdown = [
                    f"📊 Total Chance: `{total_chance:.1f}%`\n",
                    f"└─ Rod Bonus: `{base_chance*100:+.1f}%`\n",
                    f"└─ Bait Bonus: `{bait_bonus*100:+.1f}%`\n"
                ]
                
                # Only show weather bonus if location is affected
                if location in weather_data.get("affects_locations", []):
                    chance_breakdown.append(f"└─ Weather Bonus: `{weather_bonus*100:+.1f}%`\n")
                else:
                    chance_breakdown.append("└─ Weather Bonus: `+0.0%` (Location not affected)\n")
                    
                chance_breakdown.append(f"└─ Time Bonus: `{time_bonus*100:+.1f}%`")
                
                embed.add_field(
                    name="Catch Chances",
                    value="".join(chance_breakdown),
                    inline=False
                )
    
                # Calculate rarity chances
                location_mods = self.cog.data["locations"][location]["fish_modifiers"]
                weather_rare_bonus = 0
                if location in weather_data.get("affects_locations", []):
                    weather_rare_bonus = weather_data.get("rare_bonus", 0)
                time_rare_bonus = self.cog.data["time"][self.get_time_of_day()].get("rare_bonus", 0)
                
                # Calculate final chances for each rarity
                rarity_chances = {}
                for fish_type, data in self.cog.data["fish"].items():
                    base_chance = data["chance"]
                    location_mod = location_mods[fish_type]
                    
                    # Apply weather rare bonus to rare/legendary fish only if location is affected
                    rare_multiplier = 1.0
                    if location in weather_data.get("affects_locations", []):
                        if data["rarity"] in ["rare", "legendary"]:
                            rare_multiplier += weather_rare_bonus + time_rare_bonus
                        
                        # Apply specific rarity bonus if it exists in weather
                        specific_bonus = weather_data.get("specific_rarity_bonus", {}).get(data["rarity"], 0)
                        if specific_bonus:
                            rare_multiplier += specific_bonus
                    
                    final_chance = base_chance * location_mod * rare_multiplier * 100
                    rarity_chances[fish_type] = final_chance
    
                # Add rarity chance breakdown
                rarity_text = ["📊 Chances by Type:"]
                for fish_type, chance in rarity_chances.items():
                    location_effect = location_mods[fish_type]
                    base_text = f"└─ {fish_type}: `{chance:.1f}%`"
                    
                    # Add modifiers if they exist
                    mods = []
                    if location_effect != 1.0:
                        mods.append(f"Location: {location_effect:+.1f}x")
                    
                    # Only show weather effects if location is affected
                    if location in weather_data.get("affects_locations", []):
                        fish_data = self.cog.data["fish"][fish_type]
                        if fish_data["rarity"] in ["rare", "legendary"] and weather_rare_bonus:
                            mods.append(f"Weather: {weather_rare_bonus:+.1f}x")
                            if time_rare_bonus:
                                mods.append(f"Time: {time_rare_bonus:+.1f}x")
                        
                        specific_bonus = weather_data.get("specific_rarity_bonus", {}).get(fish_data["rarity"], 0)
                        if specific_bonus:
                            mods.append(f"Special: {specific_bonus:+.1f}x")
                    
                    if mods:
                        base_text += f" ({', '.join(mods)})"
                    
                    rarity_text.append(base_text)
                
                embed.add_field(
                    name="Rarity Chances",
                    value="\n".join(rarity_text),
                    inline=False
                )
                
                # Get level progress
                progress = await self.cog.level_manager.get_level_progress(self.ctx.author.id)
                if progress:
                    xp_info = (
                        f"📊 Level: `{progress['current_level']}`\n"
                        f"🎯 Progress: `{progress['progress']:.1f}%`"
                    )
                    if progress['xp_for_next'] is not None:
                        xp_info += f"\n⭐ XP until next level: `{progress['xp_for_next']:,}`"
                else:
                    xp_info = f"📊 Level: `{self.user_data['level']}`"

                self.logger.debug(f"Displaying stats - Fish: {self.user_data['fish_caught']}, Junk: {self.user_data.get('junk_caught', 0)}")
                
                # Add statistics with both fish and junk counts
                embed.add_field(
                    name="Statistics",
                    value=(
                        f"🐟 Fish Caught: `{self.user_data['fish_caught']}`\n"
                        f"📦 Junk Found: `{self.user_data.get('junk_caught', 0)}`\n"
                        f"{xp_info}"
                    ),
                    inline=False
                )
                
                return embed
                
            elif self.current_page == "location":
                specialist_names = {"Shallow Creek", "Marshlands", "Coral Reef", "Abyssal Trench"}
                is_specialist = self.location_tab == "specialized"

                if is_specialist:
                    embed = discord.Embed(
                        title="╔══ ⭐ Specialized Locations ══╗",
                        description="Locations that heavily favor one fish rarity.",
                        color=discord.Color.blue()
                    )
                else:
                    embed = discord.Embed(
                        title="╔══ 🗺️ Normal Locations ══╗",
                        description="Balanced locations for general fishing.",
                        color=discord.Color.blue()
                    )

                for loc_name, loc_data in self.cog.data["locations"].items():
                    # Filter by current tab
                    if is_specialist != (loc_name in specialist_names):
                        continue

                    requirements = loc_data.get("requirements", {})
                    is_locked = False
                    if requirements:
                        if (self.user_data["level"] < requirements.get("level", 0) or
                            self.user_data["fish_caught"] < requirements.get("fish_caught", 0)):
                            is_locked = True

                    status = "🔒 Locked" if is_locked else "📍 Current" if loc_name == self.user_data["current_location"] else "✅ Available"

                    modifier_text = []
                    for fish_type, modifier in loc_data["fish_modifiers"].items():
                        if modifier != 1.0:
                            modifier_text.append(f"• {fish_type}: {modifier:+.1f}x")

                    req_text = ""
                    if requirements:
                        req_text = f"\n**Requirements**\n• Level {requirements.get('level', 1)}"

                    embed.add_field(
                        name=f"{loc_name} ({status})",
                        value=(
                            f"{loc_data['description']}\n\n"
                            f"**Location Effects**\n{chr(10).join(modifier_text)}"
                            f"{req_text}"
                        ),
                        inline=False
                    )

            elif self.current_page == "weather":
                weather_result = await self.cog.config_manager.get_global_setting("current_weather")
                current_weather = weather_result.data if weather_result.success else "Sunny"
                weather_data = self.cog.data["weather"][current_weather]
    
                # Calculate time until next weather change
                now = datetime.datetime.now()
                last_change = self.cog.bg_task_manager.last_weather_change
                duration_hours = weather_data.get("duration_hours", 1)
                if last_change is None:
                    time_remaining = "Unknown"
                else:
                    next_change = last_change + datetime.timedelta(hours=duration_hours)
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
                
                # Add base effects
                base_effects = []
                if "catch_bonus" in weather_data:
                    base_effects.append(f"• Catch rate: `{weather_data['catch_bonus']*100:+.0f}%`")
                if "rare_bonus" in weather_data:
                    base_effects.append(f"• Rare fish bonus: `{weather_data['rare_bonus']*100:+.0f}%`")
                
                if base_effects:
                    embed.add_field(
                        name="Base Effects",
                        value="\n".join(base_effects),
                        inline=False
                    )
                
                # Add location-specific bonuses
                location_effects = []
                if "location_bonus" in weather_data:
                    for location, bonus in weather_data["location_bonus"].items():
                        location_effects.append(f"• {location}: `{bonus*100:+.0f}%`")
                
                if location_effects:
                    embed.add_field(
                        name="Location Bonuses",
                        value="\n".join(location_effects),
                        inline=False
                    )
                
                # Add time-based effects
                time_effects = []
                if "time_multiplier" in weather_data:
                    for time, multiplier in weather_data["time_multiplier"].items():
                        time_effects.append(f"• {time}: `{multiplier*100:+.0f}%`")
                
                if time_effects:
                    embed.add_field(
                        name="Time Bonuses",
                        value="\n".join(time_effects),
                        inline=False
                    )
                
                # Add rarity-specific bonuses
                rarity_effects = []
                if "specific_rarity_bonus" in weather_data:
                    for rarity, bonus in weather_data["specific_rarity_bonus"].items():
                        rarity_effects.append(f"• {rarity}: `{bonus*100:+.0f}%`")
                
                if rarity_effects:
                    embed.add_field(
                        name="Rarity Bonuses",
                        value="\n".join(rarity_effects),
                        inline=False
                    )
                
                # Add extra catch chance if present
                if "catch_quantity" in weather_data:
                    embed.add_field(
                        name="Extra Catch Chance",
                        value=f"`{weather_data['catch_quantity']*100:.0f}%` chance for bonus catch",
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
            
            if custom_id == "stop":
                await interaction.response.defer()
                embed = discord.Embed(
                    title="🎣 Session Ended",
                    description="You packed up your fishing gear. See you next time!",
                    color=discord.Color.greyple()
                )
                self.clear_items()
                for item in self.children:
                    item.disabled = True
                await self.message.edit(embed=embed, view=self)
                self._release_session()
                self.stop()
                return

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
                    self.inventory_view.parent_menu_view = self
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
                
            elif custom_id == "loc_prev":
                self.location_tab = "normal"
                await self.initialize_view()
                embed = await self.generate_embed()
                await interaction.response.edit_message(embed=embed, view=self)
                self.message = await interaction.original_response()

            elif custom_id == "loc_next":
                self.location_tab = "specialized"
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
        return self.cog.get_time_of_day()

    async def _return_to_menu(self, interaction: discord.Interaction):
        """Reset fishing state and return to the main menu."""
        self.fishing_in_progress = False
        user_data_result = await self.cog.config_manager.get_user_data(self.ctx.author.id)
        if user_data_result.success:
            self.user_data = user_data_result.data
        self.current_page = "main"
        await self.initialize_view()
        main_embed = await self.generate_embed()
        if self.message:
            await self.message.edit(embed=main_embed, view=self)

    async def do_fishing(self, interaction: discord.Interaction):
        """Continuous fishing loop — keeps casting until stopped."""
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
                    "🚫 You need to equip bait first! Use the `Inventory` menu to equip some bait.",
                    ephemeral=True,
                    wait=True
                )
                self.cog.bot.loop.create_task(self.delete_after_delay(message))
                main_embed = await self.generate_embed()
                if self.message:
                    await self.message.edit(embed=main_embed, view=self)
                return

            # Check inventory capacity
            inventory = self.user_data.get("inventory", [])
            capacity = self.user_data.get("inventory_capacity", 5)
            if len(inventory) >= capacity:
                self.fishing_in_progress = False
                await self.initialize_view()
                message = await interaction.followup.send(
                    f"🎒 Your inventory is full! ({len(inventory)}/{capacity})\n"
                    "Sell your items from the Inventory menu to make room.",
                    ephemeral=True,
                    wait=True
                )
                self.cog.bot.loop.create_task(self.delete_after_delay(message))
                main_embed = await self.generate_embed()
                if self.message:
                    await self.message.edit(embed=main_embed, view=self)
                return

            self._stop_fishing_event.clear()

            # ---- Fishing loop ----
            while self.fishing_in_progress:
                # --- Casting phase: show "Casting line..." with Stop button ---
                self.clear_items()
                stop_btn = Button(
                    label="Stop Fishing",
                    custom_id="stop_fishing_loop",
                    style=discord.ButtonStyle.red
                )
                stop_btn.callback = self._handle_stop_fishing
                self.add_item(stop_btn)

                inv_count = len(self.user_data.get("inventory", []))
                inv_cap = self.user_data.get("inventory_capacity", 5)

                fishing_embed = discord.Embed(
                    title="🎣 Fishing in Progress",
                    description=f"Casting line...\n\n🎒 Inventory: `{inv_count}/{inv_cap}`",
                    color=discord.Color.blue()
                )

                if self.message:
                    await self.message.edit(embed=fishing_embed, view=self)

                # Wait for fish to bite (or stop button)
                self._stop_fishing_event.clear()
                bite_delay = random.uniform(2, 5)
                try:
                    await asyncio.wait_for(self._stop_fishing_event.wait(), timeout=bite_delay)
                except asyncio.TimeoutError:
                    pass  # Normal — fish is biting

                if self._stop_fishing_event.is_set():
                    # Player pressed Stop during casting
                    break

                # --- Minigame phase: 5 catch buttons only ---
                self.clear_items()
                catch_actions = ["catch", "grab", "snag", "hook", "reel"]
                self.correct_action = random.choice(catch_actions)

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
                    description=f"Quick! Click `{self.correct_action.capitalize()}` to catch the fish!",
                    color=discord.Color.blue()
                )

                await self.message.edit(embed=fishing_embed, view=self)

                # Wait for catch attempt or timeout
                self._catch_event.clear()
                self._catch_processed.clear()
                try:
                    await asyncio.wait_for(self._catch_event.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass

                # Timeout — no button pressed: consume bait and exit loop
                if not self._catch_event.is_set():
                    await self.consume_bait(self.ctx.author.id)

                    fishing_embed = discord.Embed(
                        title="🎣 Too Slow!",
                        description="The fish got away!\n\nReturning to menu...",
                        color=discord.Color.red()
                    )
                    self.clear_items()
                    await self.message.edit(embed=fishing_embed, view=self)
                    await asyncio.sleep(2)
                    await self._return_to_menu(interaction)
                    return

                # Wait for handle_catch_attempt to finish processing
                try:
                    await asyncio.wait_for(self._catch_processed.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    self.logger.error("Catch processing timed out")

                # Show the result embed
                if hasattr(self, '_catch_result_embed') and self._catch_result_embed:
                    self.clear_items()
                    await self.message.edit(embed=self._catch_result_embed, view=self)
                    self._catch_result_embed = None
                    await asyncio.sleep(3)

                # Refresh user data for next iteration checks
                user_data_result = await self.cog.config_manager.get_user_data(self.ctx.author.id)
                if user_data_result.success:
                    self.user_data = user_data_result.data

                # Check if bait ran out
                if not self.user_data.get("equipped_bait"):
                    self.clear_items()
                    fishing_embed = discord.Embed(
                        title="🪱 Out of Bait!",
                        description="You've run out of bait!\n\nReturning to menu...",
                        color=discord.Color.orange()
                    )
                    await self.message.edit(embed=fishing_embed, view=self)
                    await asyncio.sleep(2)
                    await self._return_to_menu(interaction)
                    return

                # Check if inventory is now full
                inv_count = len(self.user_data.get("inventory", []))
                inv_cap = self.user_data.get("inventory_capacity", 5)
                if inv_count >= inv_cap:
                    self.clear_items()
                    fishing_embed = discord.Embed(
                        title="🎒 Inventory Full!",
                        description=f"Your inventory is full! ({inv_count}/{inv_cap})\n"
                                    "Sell your items to make room.\n\nReturning to menu...",
                        color=discord.Color.orange()
                    )
                    await self.message.edit(embed=fishing_embed, view=self)
                    await asyncio.sleep(2)
                    await self._return_to_menu(interaction)
                    return

            # Loop exited via stop button or fishing_in_progress set to False
            fishing_embed = discord.Embed(
                title="🎣 Session Ended",
                description="You stopped fishing.\n\nReturning to menu...",
                color=discord.Color.greyple()
            )
            self.clear_items()
            await self.message.edit(embed=fishing_embed, view=self)
            await asyncio.sleep(2)
            await self._return_to_menu(interaction)

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
            if self.message:
                await self.message.edit(embed=main_embed, view=self)

    async def _handle_stop_fishing(self, interaction: discord.Interaction):
        """Handle the Stop Fishing button during casting phase."""
        self._stop_fishing_event.set()
        self.fishing_in_progress = False
        await interaction.response.defer()

    async def handle_catch_attempt(self, interaction: discord.Interaction):
        """Handle fishing catch attempt button press"""
        try:
            # Signal the catch event to cancel the timeout
            self._catch_event.set()
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
            await self.consume_bait(interaction.user.id)

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

                self.logger.debug(f"Received catch data: {catch}")

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

                    # Update user data with correct item type
                    await self.cog._update_total_value(interaction.user, item_value, item_type=item_type)

                    # Award XP and check for level up
                    xp_success, old_level, new_level = await self.cog.level_manager.award_xp(
                        interaction.user.id,
                        xp_gained
                    )

                    # Force refresh the cache to get updated XP data
                    await self.cog.config_manager.refresh_cache(interaction.user.id)

                    # Get fresh user data after XP update
                    fresh_data_result = await self.cog.config_manager.get_user_data(interaction.user.id)
                    if fresh_data_result.success:
                        self.user_data = fresh_data_result.data

                    if xp_success and old_level and new_level:
                        catch["level_up"] = {
                            "old_level": old_level,
                            "new_level": new_level
                        }

                    # Get level progress with fresh data
                    progress = await self.cog.level_manager.get_level_progress(interaction.user.id)

                    # Create dynamic catch message based on item type
                    catch_msg = (
                        f"You caught a {variant} ({item_name}) worth {item_value} coins!"
                        if item_type == "fish" else
                        f"You found a {variant} ({item_name}) worth {item_value} coins!"
                    )

                    description = [
                        catch_msg,
                        f"Gained {xp_gained} XP!"
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

                    self._catch_result_embed = discord.Embed(
                        title=f"{catch_emoji} Successful Catch!",
                        description="\n".join(description),
                        color=discord.Color.green()
                    )

                else:
                    self._catch_result_embed = discord.Embed(
                        title="🎣 Nothing!",
                        description="You didn't catch anything this time!",
                        color=discord.Color.red()
                    )
            else:
                # Wrong button pressed
                self._catch_result_embed = discord.Embed(
                    title="🎣 Wrong Move!",
                    description="Whatever was on the line got away!",
                    color=discord.Color.red()
                )

        except Exception as e:
            self.logger.error(f"Error in catch attempt: {e}", exc_info=True)
            self._catch_result_embed = discord.Embed(
                title="❌ Error",
                description="An error occurred. Returning to menu...",
                color=discord.Color.red()
            )
            self.fishing_in_progress = False
        finally:
            self._catch_processed.set()

    async def handle_location_dropdown(self, interaction: discord.Interaction):
        """Handle location selection from dropdown"""
        try:
            location_name = interaction.data["values"][0]

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

            # Stay on location page so user can see updated status
            await interaction.response.defer()
            await self.update_view()

            # Send confirmation with manual deletion
            message = await interaction.followup.send(
                f"📍 Now fishing at: **{location_name}**",
                ephemeral=True,
                wait=True
            )
            self.cog.bot.loop.create_task(self.delete_after_delay(message))
            
        except Exception as e:
            self.logger.error(f"Error in handle_location_dropdown: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while changing location. Please try again.",
                    ephemeral=True,
                    delete_after=2
                )

    async def consume_bait(self, user_id: int):
        """Consume one unit of the user's equipped bait. Updates user_data in place."""
        try:
            user_data_result = await self.cog.config_manager.get_user_data(user_id)
            if not user_data_result.success:
                return
            data = user_data_result.data
            equipped_bait = data.get("equipped_bait")
            if not equipped_bait:
                return
            bait_inv = data.get("bait", {}).copy()
            bait_inv[equipped_bait] = bait_inv.get(equipped_bait, 0) - 1
            updates = {"bait": bait_inv}
            if bait_inv[equipped_bait] <= 0:
                del bait_inv[equipped_bait]
                updates["equipped_bait"] = None
            await self.cog.config_manager.update_user_data(user_id, updates)
            self.logger.debug("Bait consumed")
        except Exception as e:
            self.logger.error(f"Error consuming bait: {e}")
    
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
