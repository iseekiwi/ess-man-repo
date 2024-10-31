# ui/menu.py

import discord
import logging
from typing import Dict, Optional
from discord.ui import Button
from .base import BaseView
from .shop import ShopView
from .inventory import InventoryView
from ..utils.logging_config import setup_logging

logger = setup_logging('menu')

class FishingMenuView(BaseView):
    """Main menu interface for the fishing cog"""
    
    def __init__(self, cog, ctx, user_data: Dict):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.current_page = "main"
        self.logger = setup_logging('menu.view')
        self.shop_view = None
        self.inventory_view = None
        self.fishing_in_progress = False
        
    async def setup(self):
        """Async setup method to initialize the view"""
        try:
            self.logger.debug(f"Setting up FishingMenuView for user {self.ctx.author.name}")
            
            # Verify user data
            if not self.user_data:
                self.logger.error(f"User data is empty for {self.ctx.author.name}")
                raise ValueError("User data is missing")
            
            # Initialize shop stock if needed
            if not hasattr(self.cog, '_bait_stock'):
                self.logger.debug("Initializing bait stock")
                self.cog._bait_stock = {
                    bait: data["daily_stock"] 
                    for bait, data in self.cog.data["bait"].items()
                }
            
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
                    currency_name = await self.cog.bot.get_currency_name(self.ctx.guild)
                except:
                    currency_name = "coins"
                
                # Get balance
                try:
                    balance = await self.cog.bot.get_balance(self.ctx.author)
                except:
                    balance = 0
                
                # Add current status
                embed.add_field(
                    name="Current Status",
                    value=(
                        f"🎣 Rod: {self.user_data['rod']}\n"
                        f"🪱 Bait: {self.user_data.get('equipped_bait', 'None')}\n"
                        f"📍 Location: {self.user_data['current_location']}\n"
                        f"💰 Balance: {balance} {currency_name}"
                    ),
                    inline=False
                )
                
                # Add statistics
                embed.add_field(
                    name="Statistics",
                    value=(
                        f"🐟 Fish Caught: {self.user_data['fish_caught']}\n"
                        f"📊 Level: {self.user_data['level']}"
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
                current_weather = await self.cog.config.current_weather()
                weather_data = self.cog.data["weather"][current_weather]
                
                embed = discord.Embed(
                    title="🌤️ Current Weather",
                    description=f"**{current_weather}**\n{weather_data['description']}",
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
            
            if custom_id == "back":
                self.current_page = "main"
                await self.initialize_view()
                embed = await self.generate_embed()
                await interaction.response.edit_message(embed=embed, view=self)
                
            elif custom_id == "fish":
                if self.fishing_in_progress:
                    await interaction.response.send_message(
                        "You're already fishing!",
                        ephemeral=True
                    )
                    return
                    
                # Start fishing process
                await interaction.response.defer()
                await self.start_fishing(interaction)
                
            elif custom_id in ["shop", "inventory"]:
                # Initialize respective view
                if custom_id == "shop":
                    self.shop_view = await ShopView(self.cog, self.ctx, self.user_data).setup()
                    embed = await self.shop_view.generate_embed()
                    await interaction.response.edit_message(embed=embed, view=self.shop_view)
                else:
                    self.inventory_view = InventoryView(self.cog, self.ctx, self.user_data)
                    embed = await self.inventory_view.generate_embed()
                    await interaction.response.edit_message(embed=embed, view=self.inventory_view)
                    
            elif custom_id in ["location", "weather"]:
                self.current_page = custom_id
                await self.initialize_view()
                embed = await self.generate_embed()
                await interaction.response.edit_message(embed=embed, view=self)
                
        except Exception as e:
            self.logger.error(f"Error handling button: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred. Please try again.",
                ephemeral=True
            )

    async def handle_location_select(self, interaction: discord.Interaction):
        """Handle location selection"""
        try:
            location_name = interaction.data["custom_id"].replace("loc_", "")
            
            # Check requirements
            location_data = self.cog.data["locations"][location_name]
            meets_req, msg = await self.cog.check_requirements(
                self.user_data,
                location_data["requirements"]
            )
            
            if not meets_req:
                await interaction.response.send_message(msg, ephemeral=True)
                return
            
            # Update location
            await self.cog.config.user(self.ctx.author).current_location.set(location_name)
            self.user_data["current_location"] = location_name
            
            # Return to main menu
            self.current_page = "main"
            await self.initialize_view()
            embed = await self.generate_embed()
            await interaction.response.edit_message(
                content=f"📍 Moved to {location_name}!",
                embed=embed,
                view=self
            )
            
        except Exception as e:
            self.logger.error(f"Error handling location select: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while changing location. Please try again.",
                ephemeral=True
            )

    async def start_fishing(self, interaction: discord.Interaction):
        """Start the fishing process"""
        try:
            # Check bait
            if not self.user_data["equipped_bait"]:
                await interaction.followup.send(
                    "🚫 You need to equip bait first! Use the Inventory menu to equip some bait.",
                    ephemeral=True
                )
                return
    
            # Set fishing in progress
            self.fishing_in_progress = True
            await self.initialize_view()  # Update view to disable fishing button
            embed = await self.generate_embed()
            await self.message.edit(view=self)
    
            # Create initial fishing message
            fishing_msg = await interaction.followup.send("🎣 Starting fishing...", wait=True)
            
            # Start fishing process using the new method
            success, result_message = await self.cog.do_fishing(self.ctx, fishing_msg)
            
            # Send result
            if fishing_msg:
                try:
                    await fishing_msg.edit(content=result_message)
                except discord.NotFound:
                    await self.ctx.send(result_message)
            
            # Reset fishing status
            self.fishing_in_progress = False
            await self.initialize_view()
            
            # Update user data after fishing
            self.user_data = await self.cog.config.user(self.ctx.author).all()
            embed = await self.generate_embed()
            await self.message.edit(embed=embed, view=self)
            
        except Exception as e:
            self.logger.error(f"Error starting fishing: {e}", exc_info=True)
            self.fishing_in_progress = False
            await self.initialize_view()
            await interaction.followup.send(
                "An error occurred while fishing. Please try again.",
                ephemeral=True
            )

    async def start(self):
        """Start the menu view"""
        embed = await self.generate_embed()
        self.message = await self.ctx.send(embed=embed, view=self)
        return self
