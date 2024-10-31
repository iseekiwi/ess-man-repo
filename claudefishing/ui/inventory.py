from typing import Dict
import discord
from discord.ui import Button
from collections import Counter

from .base import BaseView, ConfirmView

class InventoryView(BaseView):
    def __init__(self, cog, ctx, user_data: Dict):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.current_page = "main"  # main, rods, bait, fish
        
        # Add default buttons
        self.initialize_buttons()

    def initialize_buttons(self):
        """Initialize the main menu buttons"""
        self.clear_items()
        
        if self.current_page == "main":
            self.add_item(Button(
                label="View Rods", 
                style=discord.ButtonStyle.blurple, 
                custom_id="view_rods"
            ))
            self.add_item(Button(
                label="View Bait", 
                style=discord.ButtonStyle.blurple, 
                custom_id="view_bait"
            ))
            self.add_item(Button(
                label="View Fish", 
                style=discord.ButtonStyle.blurple, 
                custom_id="view_fish"
            ))
        else:
            self.add_item(Button(
                label="Back", 
                style=discord.ButtonStyle.grey, 
                custom_id="back"
            ))

            if self.current_page == "fish":
                self.add_item(Button(
                    label="Sell All Fish", 
                    style=discord.ButtonStyle.green, 
                    custom_id="sell_all"
                ))

    async def generate_embed(self) -> discord.Embed:
        """Generate the appropriate embed based on current page"""
        embed = discord.Embed(color=discord.Color.blue())
        
        if self.current_page == "main":
            embed.title = f"{self.ctx.author.display_name}'s Inventory"
            embed.add_field(
                name="Currently Equipped",
                value=(
                    f"Rod: {self.user_data['rod']}\n"
                    f"Bait: {self.user_data.get('equipped_bait', 'None')}"
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

        elif self.current_page == "rods":
            embed.title = "Your Fishing Rods"
            rods_text = ""
            for rod in self.user_data.get("purchased_rods", {}):
                if rod == self.user_data['rod']:
                    rods_text += f"**{rod}** *(Equipped)*\n"
                else:
                    rods_text += f"{rod}\n"
            embed.description = rods_text or "No rods owned!"

        elif self.current_page == "bait":
            embed.title = "Your Bait"
            bait_text = ""
            for bait_name, amount in self.user_data.get("bait", {}).items():
                if bait_name == self.user_data.get('equipped_bait'):
                    bait_text += f"**{bait_name}** (x{amount}) *(Equipped)*\n"
                else:
                    bait_text += f"{bait_name} (x{amount})\n"
            embed.description = bait_text or "No bait available!"

        elif self.current_page == "fish":
            embed.title = "Your Caught Fish"
            if not self.user_data.get("inventory"):
                embed.description = "No fish caught yet!"
            else:
                fish_counts = Counter(self.user_data["inventory"])
                fish_text = ""
                for fish, count in fish_counts.most_common():
                    fish_text += f"{fish}: x{count}\n"
                embed.description = fish_text

        return embed

    async def update_view(self):
        """Update the message with current embed and view"""
        embed = await self.generate_embed()
        await self.message.edit(embed=embed, view=self)

    # Button callbacks
    @discord.ui.button(label="View Rods", custom_id="view_rods", style=discord.ButtonStyle.blurple)
    async def view_rods(self, interaction: discord.Interaction, button: Button):
        self.current_page = "rods"
        self.initialize_buttons()
        await interaction.response.defer()
        await self.update_view()

    @discord.ui.button(label="View Bait", custom_id="view_bait", style=discord.ButtonStyle.blurple)
    async def view_bait(self, interaction: discord.Interaction, button: Button):
        self.current_page = "bait"
        self.initialize_buttons()
        await interaction.response.defer()
        await self.update_view()

    @discord.ui.button(label="View Fish", custom_id="view_fish", style=discord.ButtonStyle.blurple)
    async def view_fish(self, interaction: discord.Interaction, button: Button):
        self.current_page = "fish"
        self.initialize_buttons()
        await interaction.response.defer()
        await self.update_view()

    @discord.ui.button(label="Back", custom_id="back", style=discord.ButtonStyle.grey)
    async def back_to_main(self, interaction: discord.Interaction, button: Button):
        self.current_page = "main"
        self.initialize_buttons()
        await interaction.response.defer()
        await self.update_view()

    @discord.ui.button(label="Sell All Fish", custom_id="sell_all", style=discord.ButtonStyle.green)
    async def sell_all_fish(self, interaction: discord.Interaction, button: Button):
        if not self.user_data.get("inventory"):
            await interaction.response.send_message("You have no fish to sell!", ephemeral=True)
            return

        confirm_view = ConfirmView(self.ctx.author)
        await interaction.response.send_message(
            "Are you sure you want to sell all your fish?", 
            view=confirm_view,
            ephemeral=True
        )

        await confirm_view.wait()
        if confirm_view.value:
            # Call the cog's sell_fish method
            self.user_data["inventory"] = []
            await self.update_view()
            await interaction.followup.send("Successfully sold all fish!", ephemeral=True)
        else:
            await interaction.followup.send("Sale cancelled.", ephemeral=True)
