import discord
import logging
from typing import Dict
from discord.ui import Button, View
from collections import Counter
from .base import BaseView, ConfirmView
from ..utils.logging_config import setup_logging


logger = setup_logging('inventory')

class InventoryView(BaseView):
    """View for the inventory interface"""
    
    def __init__(self, cog, ctx, user_data: Dict):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.current_page = "main"
        self.logger = setup_logging('inventory.view')
        
    async def start(self):
        """Start the inventory view"""
        try:
            self.logger.debug(f"Starting inventory view for {self.ctx.author.name}")
            await self.initialize_view()
            embed = await self.generate_embed()
            self.message = await self.ctx.send(embed=embed, view=self)
            return self
        except Exception as e:
            self.logger.error(f"Error starting inventory view: {e}", exc_info=True)
            return None
        
    async def initialize_view(self):
        """Initialize the view's buttons based on current page"""
        try:
            self.logger.debug(f"Initializing view for page: {self.current_page}")
            self.clear_items()
            
            if self.current_page == "main":
                # Main menu buttons
                buttons = [
                    ("🎣 View Rods", "rods", discord.ButtonStyle.blurple),
                    ("🪱 View Bait", "bait", discord.ButtonStyle.blurple),
                    ("🐟 View Fish", "fish", discord.ButtonStyle.blurple),
                    ("↩️ Back to Menu", "menu", discord.ButtonStyle.grey)
                ]
                
                for label, custom_id, style in buttons:
                    button = Button(label=label, custom_id=custom_id, style=style)
                    button.callback = self.handle_button
                    self.add_item(button)
                    
            else:
                # Back button for sub-pages
                back_button = Button(
                    label="Back",
                    custom_id="back",
                    style=discord.ButtonStyle.grey
                )
                back_button.callback = self.handle_button
                self.add_item(back_button)
                
                if self.current_page == "fish" and self.user_data.get("inventory"):
                    sell_button = Button(
                        label="Sell All Fish",
                        custom_id="sell_all",
                        style=discord.ButtonStyle.green
                    )
                    sell_button.callback = self.handle_button
                    self.add_item(sell_button)
                    
                elif self.current_page == "rods":
                    # Add equip buttons for owned rods
                    for rod in self.user_data.get("purchased_rods", {}):
                        if rod != self.user_data['rod']:  # Don't show for currently equipped rod
                            equip_button = Button(
                                label=f"Equip {rod}",
                                custom_id=f"equip_rod_{rod}",
                                style=discord.ButtonStyle.green
                            )
                            equip_button.callback = self.handle_button
                            self.add_item(equip_button)
                            
                elif self.current_page == "bait":
                    # Add equip buttons for available bait
                    for bait_name, amount in self.user_data.get("bait", {}).items():
                        if amount > 0 and bait_name != self.user_data.get('equipped_bait'):
                            equip_button = Button(
                                label=f"Equip {bait_name}",
                                custom_id=f"equip_bait_{bait_name}",
                                style=discord.ButtonStyle.green
                            )
                            equip_button.callback = self.handle_button
                            self.add_item(equip_button)

        except Exception as e:
            self.logger.error(f"Error in initialize_view: {str(e)}", exc_info=True)
            raise

    async def handle_button(self, interaction: discord.Interaction):
        """Handle button interactions"""
        try:
            custom_id = interaction.data["custom_id"]
            
            if custom_id == "menu":
                # Import here to avoid circular import
                from .menu import FishingMenuView
                menu_view = await FishingMenuView(self.cog, self.ctx, self.user_data).setup()
                embed = await menu_view.generate_embed()
                await interaction.response.edit_message(embed=embed, view=menu_view)
                return
                
            if custom_id == "back":
                self.current_page = "main"
                await interaction.response.defer()
                await self.update_view()
                
            elif custom_id == "sell_all":
                success, amount, msg = await self.cog.sell_fish(self.ctx)
                if success:
                    self.user_data = await self.cog.config.user(self.ctx.author).all()
                    await interaction.response.defer()
                    await self.update_view()
                await interaction.followup.send(msg, ephemeral=True)
                
            elif custom_id.startswith("equip_rod_"):
                rod_name = custom_id.replace("equip_rod_", "")
                success, msg = await self.cog._equip_rod(interaction.user, rod_name)
                
                if success:
                    self.user_data["rod"] = rod_name
                    await interaction.response.defer()
                    await self.update_view()
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
                    
            elif custom_id.startswith("equip_bait_"):
                bait_name = custom_id.replace("equip_bait_", "")
                success, msg = await self.cog._equip_bait(interaction.user, bait_name)
                
                if success:
                    self.user_data["equipped_bait"] = bait_name
                    await interaction.response.defer()
                    await self.update_view()
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
                    
            elif custom_id in ["rods", "bait", "fish"]:
                self.current_page = custom_id
                await interaction.response.defer()
                await self.update_view()
                
        except Exception as e:
            self.logger.error(f"Error in handle_button: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred. Please try again.",
                ephemeral=True
            )

    async def update_view(self):
        """Update the message with current embed and view"""
        try:
            await self.initialize_view()
            embed = await self.generate_embed()
            await self.message.edit(embed=embed, view=self)
        except Exception as e:
            self.logger.error(f"Error updating view: {e}", exc_info=True)
            await self.ctx.send(f"Error updating inventory view: {str(e)}")
