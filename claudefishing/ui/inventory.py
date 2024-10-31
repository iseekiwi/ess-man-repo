from typing import Dict
import discord
from discord.ui import Button, View
from collections import Counter
from .base import BaseView, ConfirmView
import logging

logger = logging.getLogger("red.fishing.inventory")

class InventoryView(BaseView):
    """Simplified inventory view for debugging"""
    
    def __init__(self, cog, ctx, user_data: Dict):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.current_page = "main"
        
    async def initialize_view(self):
        """Initialize the view's buttons"""
        self.clear_items()
        
        # Add main menu buttons
        rods_button = Button(
            label="View Rods",
            style=discord.ButtonStyle.blurple,
            custom_id="view_rods"
        )
        rods_button.callback = self.view_rods
        self.add_item(rods_button)
        
        bait_button = Button(
            label="View Bait",
            style=discord.ButtonStyle.blurple,
            custom_id="view_bait"
        )
        bait_button.callback = self.view_bait
        self.add_item(bait_button)
        
        fish_button = Button(
            label="View Fish",
            style=discord.ButtonStyle.blurple,
            custom_id="view_fish"
        )
        fish_button.callback = self.view_fish
        self.add_item(fish_button)

    async def start(self):
        """Start the view"""
        await self.initialize_view()
        embed = await self.generate_embed()
        self.message = await self.ctx.send(embed=embed, view=self)
        return self

    async def generate_embed(self) -> discord.Embed:
        """Generate the embed for the current page"""
        embed = discord.Embed(color=discord.Color.blue())
        embed.title = f"{self.ctx.author.display_name}'s Inventory"
        
        # Add currently equipped items
        embed.add_field(
            name="Currently Equipped",
            value=(
                f"🎣 Rod: {self.user_data['rod']}\n"
                f"🪱 Bait: {self.user_data.get('equipped_bait', 'None')}"
            ),
            inline=False
        )
        
        # Add summary counts
        rod_count = len(self.user_data.get("purchased_rods", {}))
        bait_count = sum(self.user_data.get("bait", {}).values())
        fish_count = len(self.user_data.get("inventory", []))
        
        embed.add_field(
            name="Summary",
            value=(
                f"🎣 Rods Owned: {rod_count}\n"
                f"🪱 Bait Available: {bait_count}\n"
                f"🐟 Fish Caught: {fish_count}"
            ),
            inline=False
        )
        
        return embed

    # Button Callbacks
    async def view_rods(self, interaction: discord.Interaction):
        await interaction.response.send_message("Rods view coming soon!", ephemeral=True)

    async def view_bait(self, interaction: discord.Interaction):
        await interaction.response.send_message("Bait view coming soon!", ephemeral=True)

    async def view_fish(self, interaction: discord.Interaction):
        await interaction.response.send_message("Fish view coming soon!", ephemeral=True)

    async def update_view(self):
        """Update the message with current embed and view"""
        try:
            await self.initialize_view()
            embed = await self.generate_embed()
            await self.message.edit(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Error updating view: {e}", exc_info=True)
            await self.ctx.send(f"Error updating inventory view: {str(e)}")
