# ui/inventory.py

import discord
import asyncio
import logging
from collections import Counter
from redbot.core import bank
from typing import Dict
from discord.ui import Button, View
from collections import Counter
from .base import BaseView, ConfirmView
from ..utils.logging_config import get_logger
from ..utils.timeout_manager import TimeoutManager


logger = get_logger('inventory')

class InventoryView(BaseView):
    """View for the inventory interface"""
    
    def __init__(self, cog, ctx, user_data: Dict):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.current_page = "main"
        self.logger = get_logger('inventory.view')

    async def generate_embed(self) -> discord.Embed:
        """Generate the appropriate embed based on current page"""
        try:         
            # Get user's balance and currency name
            try:
                balance = await bank.get_balance(self.ctx.author)
                currency_name = await bank.get_currency_name(self.ctx.guild)
            except Exception as e:
                self.logger.error(f"Error getting balance: {e}")
                balance = 0
                currency_name = "coins"
                
            if self.current_page == "main":
                summary = await self.cog.inventory.get_inventory_summary(self.ctx.author.id)
                self.logger.debug(f"Inventory summary for {self.ctx.author.id}: {summary}")
                
                if not summary:
                    self.logger.error(f"Failed to get inventory summary for user {self.ctx.author.id}")
                    return discord.Embed(
                        title="❌ Inventory Error",
                        description="Failed to load inventory data. Please try again later.",
                        color=discord.Color.red()
                    )
                    
                embed = discord.Embed(
                    title=f"🎒 {self.ctx.author.display_name}'s Inventory",
                    color=discord.Color.blue()
                )
                
                # Currently equipped section
                embed.add_field(
                    name="Currently Equipped",
                    value=(
                        f"🎣 Rod: `{summary['equipped_rod']}`\n"
                        f"🪱 Bait: `{summary['equipped_bait'] or 'None'}`"
                    ),
                    inline=False
                )
                
                # Inventory summary section
                embed.add_field(
                    name="Summary",
                    value=(
                        f"🎣 Rods Owned: `{summary['rod_count']}`\n"
                        f"🪱 Bait Available: `{summary['bait_count']}`\n"
                        f"🐟 Fish & Items: `{summary['fish_count']}`\n"
                        f"💰 Total Value: `{summary['total_value']}` *{currency_name}*\n"
                        f"💰 Current Balance: `{balance}` *{currency_name}*"
                    ),
                    inline=False
                )
                
            elif self.current_page == "rods":
                embed = discord.Embed(
                    title="🎣 Your Fishing Rods",
                    color=discord.Color.blue()
                )
                
                rods_text = []
                for rod in self.user_data.get("purchased_rods", {}):
                    rod_data = self.cog.data["rods"][rod]
                    stats = f"Catch Bonus: `+{rod_data['chance']*100}%`"
                    
                    if rod == self.user_data['rod']:
                        rods_text.append(f"**{rod}** *(Equipped)*\n{stats}")
                    else:
                        rods_text.append(f"{rod}\n{stats}")
                
                embed.description = "\n\n".join(rods_text) or "No rods owned!"
                embed.set_footer(text=f"Balance: {balance} {currency_name}")
                
            elif self.current_page == "bait":
                embed = discord.Embed(
                    title="🪱 Your Bait",
                    color=discord.Color.blue()
                )
                
                bait_text = []
                for bait_name, amount in self.user_data.get("bait", {}).items():
                    if amount > 0:
                        bait_data = self.cog.data["bait"][bait_name]
                        stats = f"Catch Bonus: `+{bait_data['catch_bonus']*100}%`"
                        
                        if bait_name == self.user_data.get('equipped_bait'):
                            bait_text.append(f"**{bait_name}** (x{amount}) *(Equipped)*\n{stats}")
                        else:
                            bait_text.append(f"{bait_name} (x{amount})\n{stats}")
                
                embed.description = "\n\n".join(bait_text) or "No bait available!"
                embed.set_footer(text=f"Balance: {balance} {currency_name}")
                
            elif self.current_page == "fish":
                embed = discord.Embed(
                    title="🐟 Your Caught Items",
                    color=discord.Color.blue()
                )
                
                if not self.user_data.get("inventory"):
                    embed.description = "No items caught yet!"
                else:
                    item_counts = Counter(self.user_data["inventory"])
                    fish_text = []
                    junk_text = []
                    fish_total = 0
                    junk_total = 0
                    
                    for item, count in item_counts.most_common():
                        if item in self.cog.data["fish"]:
                            value = self.cog.data["fish"][item]["value"] * count
                            fish_total += value
                            fish_text.append(f"{item}: x{count} (Worth: {value} {currency_name})")
                        elif item in self.cog.data["junk"]:
                            value = self.cog.data["junk"][item]["value"] * count
                            junk_total += value
                            junk_text.append(f"{item}: x{count} (Worth: {value} {currency_name})")
                    
                    if fish_text:
                        embed.add_field(
                            name="🐟 Fish", 
                            value="\n".join(fish_text), 
                            inline=False
                        )
                    if junk_text:
                        embed.add_field(
                            name="📦 Junk Items", 
                            value="\n".join(junk_text), 
                            inline=False
                        )
                    
                    total_value = fish_total + junk_total
                    embed.set_footer(
                        text=f"Total Value: {total_value} {currency_name} "
                        f"(Fish: {fish_total}, Junk: {junk_total}) | "
                        f"Balance: {balance} {currency_name}"
                    )
            
            return embed
            
        except Exception as e:
            self.logger.error(f"Error generating embed: {e}", exc_info=True)
            return discord.Embed(
                title="Error",
                description="An error occurred while loading the inventory. Please try again.",
                color=discord.Color.red()
            )
    
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
                    ("🐟 View Inventory", "fish", discord.ButtonStyle.blurple),
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
                menu_view = await self.cog.create_menu(self.ctx, self.user_data)
                embed = await menu_view.generate_embed()
                
                # Resume parent menu timeout
                await self.timeout_manager.resume_parent_view(self)
                
                await interaction.response.edit_message(embed=embed, view=menu_view)
                menu_view.message = await interaction.original_response()
                return
                
            if custom_id == "back":
                self.current_page = "main"
                await interaction.response.defer()
                await self.update_view()
                
            elif custom_id == "sell_all":
                success, amount, msg = await self.cog.sell_fish(self.ctx)
                if success:
                    # Get fresh user data after sale
                    user_data_result = await self.cog.config_manager.get_user_data(self.ctx.author.id)
                    if user_data_result.success:
                        self.user_data = user_data_result.data  # Update the view's user data
                        await self.update_view()
                
                # Send ephemeral message and schedule deletion
                message = await interaction.followup.send(msg, ephemeral=True, wait=True)
                self.cog.bot.loop.create_task(self.delete_after_delay(message))
                
            elif custom_id.startswith("equip_rod_"):
                rod_name = custom_id.replace("equip_rod_", "")
                success, msg = await self.cog._equip_rod(interaction.user, rod_name)
                
                if success:
                    self.user_data["rod"] = rod_name
                    await interaction.response.defer()
                    await self.update_view()
                    message = await interaction.followup.send(msg, ephemeral=True, wait=True)
                    self.cog.bot.loop.create_task(self.delete_after_delay(message))
                else:
                    await interaction.response.send_message(msg, ephemeral=True, delete_after=2)
                    
            elif custom_id.startswith("equip_bait_"):
                bait_name = custom_id.replace("equip_bait_", "")
                success, msg = await self.cog._equip_bait(interaction.user, bait_name)
                
                if success:
                    self.user_data["equipped_bait"] = bait_name
                    await interaction.response.defer()
                    await self.update_view()
                    message = await interaction.followup.send(msg, ephemeral=True, wait=True)
                    self.cog.bot.loop.create_task(self.delete_after_delay(message))
                else:
                    await interaction.response.send_message(msg, ephemeral=True, delete_after=2)
                    
            elif custom_id in ["rods", "bait", "fish"]:
                self.current_page = custom_id
                await interaction.response.defer()
                await self.update_view()
                
        except Exception as e:
            self.logger.error(f"Error in handle_button: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred. Please try again.",
                    ephemeral=True,
                    delete_after=2
                )

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
            await self.ctx.send(f"Error updating inventory view: {str(e)}")
