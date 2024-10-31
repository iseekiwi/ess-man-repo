from typing import Dict, Optional
import discord
from discord.ui import Button, Select, View
from redbot.core import bank

class ShopView(BaseView):
    def __init__(self, cog, ctx, user_data: Dict):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.current_page = "main"
        self.selected_quantity = 1
        self.initialize_view()

    def initialize_view(self):
        """Initialize the view based on current page"""
        self.clear_items()
        
        if self.current_page == "main":
            self.add_item(discord.ui.Button(
                label="Buy Bait",
                style=discord.ButtonStyle.blurple,
                custom_id="bait"
            ))
            self.add_item(discord.ui.Button(
                label="Buy Rods",
                style=discord.ButtonStyle.blurple,
                custom_id="rods"
            ))
        else:
            self.add_item(discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.grey,
                custom_id="back"
            ))
            
            if self.current_page == "bait":
                self.add_item(QuantitySelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Verify that only the command user can interact"""
        return interaction.user.id == self.ctx.author.id

    async def on_timeout(self):
        """Disable buttons when view times out"""
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)

    async def handle_button(self, interaction: discord.Interaction):
        """Handle button interactions"""
        custom_id = interaction.data["custom_id"]
        
        if custom_id == "bait":
            self.current_page = "bait"
        elif custom_id == "rods":
            self.current_page = "rods"
        elif custom_id == "back":
            self.current_page = "main"
        
        self.initialize_view()
        await self.update_view()
        await interaction.response.defer()

    async def handle_select(self, interaction: discord.Interaction):
        """Handle select menu interactions"""
        self.selected_quantity = int(interaction.data["values"][0])
        await interaction.response.defer()

    async def update_view(self):
        """Update the message with current embed and view"""
        embed = await self.generate_embed()
        await self.message.edit(embed=embed, view=self)

    # Add other methods (generate_embed etc.) as before...

class QuantitySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=str(i), value=str(i))
            for i in [1, 5, 10, 25, 50, 100]
        ]
        super().__init__(
            placeholder="Select quantity...",
            options=options,
            custom_id="quantity"
        )
