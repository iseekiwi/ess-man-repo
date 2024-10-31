from typing import Dict
import discord
from discord.ui import Button, View
from collections import Counter
from .base import BaseView, ConfirmView

class InventoryView(BaseView):
    """Enhanced inventory view with proper button management"""
    
    def __init__(self, cog, ctx, user_data: Dict):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.current_page = "main"  # main, rods, bait, fish
        self.initialize_view()

    async def initialize_view(self):
        """Initialize the view based on current page"""
        self.clear_items()
        
        if self.current_page == "main":
            # Main menu buttons
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
        else:
            # Back button for sub-pages
            back_button = Button(
                label="Back",
                style=discord.ButtonStyle.grey,
                custom_id="back"
            )
            back_button.callback = self.back_to_main
            self.add_item(back_button)

            # Additional buttons for specific pages
            if self.current_page == "fish" and self.user_data.get("inventory"):
                sell_button = Button(
                    label="Sell All Fish",
                    style=discord.ButtonStyle.green,
                    custom_id="sell_all"
                )
                sell_button.callback = self.sell_all_fish
                self.add_item(sell_button)
            
            elif self.current_page == "rods":
                equip_buttons = []
                for rod in self.user_data.get("purchased_rods", {}):
                    if rod != self.user_data['rod']:  # Don't show equip button for currently equipped rod
                        equip_button = Button(
                            label=f"Equip {rod}",
                            style=discord.ButtonStyle.green,
                            custom_id=f"equip_rod_{rod}"
                        )
                        equip_button.callback = self.equip_rod
                        equip_buttons.append(equip_button)
                
                # Add up to 4 equip buttons (Discord has a 5 button per row limit)
                for button in equip_buttons[:4]:
                    self.add_item(button)
            
            elif self.current_page == "bait":
                equip_buttons = []
                for bait_name in self.user_data.get("bait", {}):
                    if bait_name != self.user_data.get('equipped_bait'):
                        equip_button = Button(
                            label=f"Equip {bait_name}",
                            style=discord.ButtonStyle.green,
                            custom_id=f"equip_bait_{bait_name}"
                        )
                        equip_button.callback = self.equip_bait
                        equip_buttons.append(equip_button)
                
                # Add up to 4 equip buttons
                for button in equip_buttons[:4]:
                    self.add_item(button)

    async def generate_embed(self) -> discord.Embed:
        """Generate the appropriate embed based on current page"""
        embed = discord.Embed(color=discord.Color.blue())
        
        if self.current_page == "main":
            embed.title = f"{self.ctx.author.display_name}'s Inventory"
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
            
            total_value = sum(
                self.cog.data["fish"][fish]["value"]
                for fish in self.user_data.get("inventory", [])
            )
            
            embed.add_field(
                name="Summary",
                value=(
                    f"🎣 Rods Owned: {rod_count}\n"
                    f"🪱 Bait Available: {bait_count}\n"
                    f"🐟 Fish Caught: {fish_count}\n"
                    f"💰 Total Fish Value: {total_value} coins"
                ),
                inline=False
            )

        elif self.current_page == "rods":
            embed.title = "🎣 Your Fishing Rods"
            rods_text = []
            for rod in self.user_data.get("purchased_rods", {}):
                rod_data = self.cog.data["rods"][rod]
                stats = (
                    f"Catch Bonus: +{rod_data['chance']*100}%\n"
                    f"Value Bonus: +{rod_data['value_increase']}%"
                )
                if rod == self.user_data['rod']:
                    rods_text.append(f"**{rod}** *(Equipped)*\n{stats}\n")
                else:
                    rods_text.append(f"{rod}\n{stats}\n")
            embed.description = "\n".join(rods_text) or "No rods owned!"

        elif self.current_page == "bait":
            embed.title = "🪱 Your Bait"
            bait_text = []
            for bait_name, amount in self.user_data.get("bait", {}).items():
                bait_data = self.cog.data["bait"][bait_name]
                stats = f"Catch Bonus: +{bait_data['catch_bonus']*100}%"
                if bait_name == self.user_data.get('equipped_bait'):
                    bait_text.append(f"**{bait_name}** (x{amount}) *(Equipped)*\n{stats}\n")
                else:
                    bait_text.append(f"{bait_name} (x{amount})\n{stats}\n")
            embed.description = "\n".join(bait_text) or "No bait available!"

        elif self.current_page == "fish":
            embed.title = "🐟 Your Caught Fish"
            if not self.user_data.get("inventory"):
                embed.description = "No fish caught yet!"
            else:
                fish_counts = Counter(self.user_data["inventory"])
                fish_text = []
                total_value = 0
                for fish, count in fish_counts.most_common():
                    value = self.cog.data["fish"][fish]["value"] * count
                    total_value += value
                    fish_text.append(f"{fish}: x{count} (Worth: {value} coins)")
                embed.description = "\n".join(fish_text)
                embed.set_footer(text=f"Total Value: {total_value} coins")

        return embed

    async def update_view(self):
        """Update the message with current embed and view"""
        try:
            await self.initialize_view()
            embed = await self.generate_embed()
            await self.message.edit(embed=embed, view=self)
        except Exception as e:
            await self.ctx.send(f"Error updating inventory view: {str(e)}")

    # Button Callbacks
    async def view_rods(self, interaction: discord.Interaction):
        self.current_page = "rods"
        await interaction.response.defer()
        await self.update_view()

    async def view_bait(self, interaction: discord.Interaction):
        self.current_page = "bait"
        await interaction.response.defer()
        await self.update_view()

    async def view_fish(self, interaction: discord.Interaction):
        self.current_page = "fish"
        await interaction.response.defer()
        await self.update_view()

    async def back_to_main(self, interaction: discord.Interaction):
        self.current_page = "main"
        await interaction.response.defer()
        await self.update_view()

    async def sell_all_fish(self, interaction: discord.Interaction):
        if not self.user_data.get("inventory"):
            await interaction.response.send_message("You have no fish to sell!", ephemeral=True)
            return

        confirm_view = ConfirmView(self.ctx.author)
        total_value = sum(
            self.cog.data["fish"][fish]["value"]
            for fish in self.user_data["inventory"]
        )
        
        await interaction.response.send_message(
            f"Are you sure you want to sell all your fish for {total_value} coins?",
            view=confirm_view,
            ephemeral=True
        )

        await confirm_view.wait()
        if confirm_view.value:
            await self.cog.sell_fish(self.ctx)
            self.user_data = await self.cog.config.user(self.ctx.author).all()
            await self.update_view()
            await interaction.followup.send(
                f"Successfully sold all fish for {total_value} coins!",
                ephemeral=True
            )
        else:
            await interaction.followup.send("Sale cancelled.", ephemeral=True)

    async def equip_rod(self, interaction: discord.Interaction):
        rod_name = interaction.data["custom_id"].replace("equip_rod_", "")
        await self.cog.config.user(self.ctx.author).rod.set(rod_name)
        self.user_data["rod"] = rod_name
        await interaction.response.send_message(f"Equipped {rod_name}!", ephemeral=True)
        await self.update_view()

    async def equip_bait(self, interaction: discord.Interaction):
        bait_name = interaction.data["custom_id"].replace("equip_bait_", "")
        await self.cog.config.user(self.ctx.author).equipped_bait.set(bait_name)
        self.user_data["equipped_bait"] = bait_name
        await interaction.response.send_message(f"Equipped {bait_name}!", ephemeral=True)
        await self.update_view()
