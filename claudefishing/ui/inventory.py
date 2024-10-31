from typing import Dict
import discord
from discord.ui import Button, View
from collections import Counter
from .base import BaseView, ConfirmView
import logging

logger = logging.getLogger("red.fishing.inventory")

class InventoryView(BaseView):
    """Enhanced inventory view with proper button handling"""
    
    def __init__(self, cog, ctx, user_data: Dict):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.current_page = "main"
        logger.debug(f"Initializing InventoryView for {ctx.author.name}")
        # Don't call initialize_view in __init__ as it's an async method
        
    async def start(self):
        """Initialize and start the view"""
        await self.initialize_view()
        embed = await self.generate_embed()
        self.message = await self.ctx.send(embed=embed, view=self)
        return self

    async def initialize_view(self):
        """Initialize the view's buttons based on current page"""
        try:
            logger.debug(f"Initializing view for page: {self.current_page}")
            self.clear_items()  # Clear existing buttons
            
            if self.current_page == "main":
                # Main menu buttons
                self.add_item(Button(
                    label="View Rods",
                    style=discord.ButtonStyle.blurple,
                    custom_id="view_rods",
                    callback=self.view_rods
                ))
                
                self.add_item(Button(
                    label="View Bait",
                    style=discord.ButtonStyle.blurple,
                    custom_id="view_bait",
                    callback=self.view_bait
                ))
                
                self.add_item(Button(
                    label="View Fish",
                    style=discord.ButtonStyle.blurple,
                    custom_id="view_fish",
                    callback=self.view_fish
                ))
            
            else:  # Sub-pages
                # Back button
                self.add_item(Button(
                    label="Back",
                    style=discord.ButtonStyle.grey,
                    custom_id="back",
                    callback=self.back_to_main
                ))
                
                if self.current_page == "fish" and self.user_data.get("inventory"):
                    # Sell fish button
                    self.add_item(Button(
                        label="Sell All Fish",
                        style=discord.ButtonStyle.green,
                        custom_id="sell_all",
                        callback=self.sell_all_fish
                    ))
                
                elif self.current_page == "rods":
                    # Rod equip buttons
                    for rod in self.user_data.get("purchased_rods", {}):
                        if rod != self.user_data['rod']:
                            self.add_item(Button(
                                label=f"Equip {rod}",
                                style=discord.ButtonStyle.green,
                                custom_id=f"equip_rod_{rod}",
                                callback=self.equip_rod
                            ))
                
                elif self.current_page == "bait":
                    # Bait equip buttons
                    for bait_name in self.user_data.get("bait", {}):
                        if bait_name != self.user_data.get('equipped_bait'):
                            self.add_item(Button(
                                label=f"Equip {bait_name}",
                                style=discord.ButtonStyle.green,
                                custom_id=f"equip_bait_{bait_name}",
                                callback=self.equip_bait
                            ))
            
            logger.debug(f"Added {len(self.children)} buttons to view")
            
        except Exception as e:
            logger.error(f"Error initializing view: {e}", exc_info=True)
            raise

    # Button Callbacks
    async def view_rods(self, interaction: discord.Interaction):
        """Handle rod view button press"""
        try:
            self.current_page = "rods"
            await interaction.response.defer()
            await self.update_view()
        except Exception as e:
            logger.error(f"Error in view_rods: {e}", exc_info=True)
            await interaction.followup.send("Error viewing rods.", ephemeral=True)

    async def view_bait(self, interaction: discord.Interaction):
        """Handle bait view button press"""
        try:
            self.current_page = "bait"
            await interaction.response.defer()
            await self.update_view()
        except Exception as e:
            logger.error(f"Error in view_bait: {e}", exc_info=True)
            await interaction.followup.send("Error viewing bait.", ephemeral=True)

    async def view_fish(self, interaction: discord.Interaction):
        """Handle fish view button press"""
        try:
            self.current_page = "fish"
            await interaction.response.defer()
            await self.update_view()
        except Exception as e:
            logger.error(f"Error in view_fish: {e}", exc_info=True)
            await interaction.followup.send("Error viewing fish.", ephemeral=True)

    async def back_to_main(self, interaction: discord.Interaction):
        """Handle back button press"""
        try:
            self.current_page = "main"
            await interaction.response.defer()
            await self.update_view()
        except Exception as e:
            logger.error(f"Error in back_to_main: {e}", exc_info=True)
            await interaction.followup.send("Error returning to main menu.", ephemeral=True)

    async def equip_rod(self, interaction: discord.Interaction):
        """Handle rod equipment"""
        try:
            rod_name = interaction.data["custom_id"].replace("equip_rod_", "")
            success, msg = await self.cog._equip_rod(interaction.user, rod_name)
            
            if success:
                self.user_data["rod"] = rod_name
                await interaction.response.defer()
                await self.update_view()
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception as e:
            logger.error(f"Error equipping rod: {e}", exc_info=True)
            await interaction.response.send_message("Error equipping rod.", ephemeral=True)

    async def equip_bait(self, interaction: discord.Interaction):
        """Handle bait equipment"""
        try:
            bait_name = interaction.data["custom_id"].replace("equip_bait_", "")
            success, msg = await self.cog._equip_bait(interaction.user, bait_name)
            
            if success:
                self.user_data["equipped_bait"] = bait_name
                await interaction.response.defer()
                await self.update_view()
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception as e:
            logger.error(f"Error equipping bait: {e}", exc_info=True)
            await interaction.response.send_message("Error equipping bait.", ephemeral=True)

    async def sell_all_fish(self, interaction: discord.Interaction):
        """Handle fish selling"""
        try:
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
                success, amount, msg = await self.cog.sell_fish(self.ctx)
                if success:
                    self.user_data = await self.cog.config.user(self.ctx.author).all()
                    await self.update_view()
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.followup.send("Sale cancelled.", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error selling fish: {e}", exc_info=True)
            await interaction.followup.send("Error processing fish sale.", ephemeral=True)

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
            logger.error(f"Error updating view: {e}", exc_info=True)
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
