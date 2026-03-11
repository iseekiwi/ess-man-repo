# ui/inventory.py

import discord
from collections import Counter
from redbot.core import bank
from typing import Dict
from discord.ui import Button, View, Select
from .base import BaseView, ConfirmView
from ..utils.logging_config import get_logger
from ..data.fishing_data import MATERIAL_TYPES, CONSUMABLE_TOOL_TYPES


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
                capacity = self.user_data.get("inventory_capacity", 5)
                embed.add_field(
                    name="Summary",
                    value=(
                        f"🎣 Rods Owned: `{summary['rod_count']}`\n"
                        f"🪱 Bait Available: `{summary['bait_count']}`\n"
                        f"🐟 Fish & Items: `{summary['fish_count']}/{capacity}`\n"
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
                capacity = self.user_data.get("inventory_capacity", 5)
                inv_count = len(self.user_data.get("inventory", []))
                embed = discord.Embed(
                    title=f"🐟 Your Caught Items ({inv_count}/{capacity})",
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

            elif self.current_page == "materials":
                embed = discord.Embed(
                    title="🧱 Your Materials",
                    color=discord.Color.blue()
                )
                user_materials = self.user_data.get("materials", {})
                if not user_materials:
                    embed.description = "No materials collected yet!\nMaterials are rare drops used to upgrade gear."
                else:
                    mat_text = []
                    for mat_name, amount in user_materials.items():
                        mat_info = MATERIAL_TYPES.get(mat_name, {})
                        emoji = mat_info.get("emoji", "")
                        rarity = mat_info.get("rarity", "unknown")
                        value = mat_info.get("value", 0)
                        mat_text.append(
                            f"{emoji} **{mat_name}** x{amount}\n"
                            f"*{rarity.capitalize()}* — Sell value: {value} {currency_name} each"
                        )
                    embed.description = "\n\n".join(mat_text)
                embed.set_footer(text=f"Balance: {balance} {currency_name}")

            elif self.current_page == "tools":
                embed = discord.Embed(
                    title="🔧 Your Consumable Tools",
                    color=discord.Color.blue()
                )
                user_tools = self.user_data.get("tools", {})
                if not user_tools:
                    embed.description = "No tools owned!\nBuy consumable tools from the shop to find materials while fishing."
                else:
                    tool_text = []
                    for tool_name, quantity in user_tools.items():
                        tool_info = CONSUMABLE_TOOL_TYPES.get(tool_name, {})
                        triggers = ", ".join(tool_info.get("triggers_on", []))
                        tool_text.append(
                            f"🔧 **{tool_name}** x{quantity}\n"
                            f"{tool_info.get('description', '')}\n"
                            f"Triggers on: {triggers} catches"
                        )
                    embed.description = "\n\n".join(tool_text)
                embed.set_footer(text=f"Balance: {balance} {currency_name}")

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
            await self._refresh_user_data()
            self.clear_items()

            if self.current_page == "main":
                buttons = [
                    ("🎣 View Rods", "rods", discord.ButtonStyle.blurple),
                    ("🪱 View Bait", "bait", discord.ButtonStyle.blurple),
                    ("🐟 View Inventory", "fish", discord.ButtonStyle.blurple),
                    ("🧱 Materials", "materials", discord.ButtonStyle.blurple),
                    ("🔧 Tools", "tools", discord.ButtonStyle.blurple),
                    ("↩️ Back to Menu", "menu", discord.ButtonStyle.grey)
                ]

                for label, custom_id, style in buttons:
                    button = Button(label=label, custom_id=custom_id, style=style)
                    button.callback = self.handle_button
                    self.add_item(button)

            else:
                # Back button for all sub-pages
                back_button = Button(label="Back", custom_id="back", style=discord.ButtonStyle.grey)
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
                    rod_options = []
                    for rod in self.user_data.get("purchased_rods", {}):
                        rod_data = self.cog.data["rods"].get(rod, {})
                        is_equipped = (rod == self.user_data.get("rod"))
                        desc = f"Catch Bonus: +{rod_data.get('chance', 0)*100:.0f}%"
                        if is_equipped:
                            desc += " (Equipped)"
                        rod_options.append(discord.SelectOption(
                            label=rod,
                            value=rod,
                            description=desc[:100],
                            default=is_equipped
                        ))

                    if rod_options:
                        rod_select = Select(
                            placeholder="Select a rod to equip...",
                            options=rod_options,
                            custom_id="equip_rod_select"
                        )
                        rod_select.callback = self.handle_rod_equip
                        self.add_item(rod_select)

                elif self.current_page == "bait":
                    bait_options = []
                    for bait_name, amount in self.user_data.get("bait", {}).items():
                        if amount > 0:
                            bait_data = self.cog.data["bait"].get(bait_name, {})
                            is_equipped = (bait_name == self.user_data.get("equipped_bait"))
                            desc = f"x{amount} | +{bait_data.get('catch_bonus', 0)*100:.0f}% catch"
                            if is_equipped:
                                desc += " (Equipped)"
                            bait_options.append(discord.SelectOption(
                                label=bait_name,
                                value=bait_name,
                                description=desc[:100],
                                default=is_equipped
                            ))

                    if bait_options:
                        bait_select = Select(
                            placeholder="Select bait to equip...",
                            options=bait_options,
                            custom_id="equip_bait_select"
                        )
                        bait_select.callback = self.handle_bait_equip
                        self.add_item(bait_select)

                elif self.current_page == "materials":
                    user_materials = self.user_data.get("materials", {})
                    if user_materials:
                        mat_options = []
                        for mat_name, amount in user_materials.items():
                            mat_info = MATERIAL_TYPES.get(mat_name, {})
                            emoji = mat_info.get("emoji", "")
                            value = mat_info.get("value", 0)
                            mat_options.append(discord.SelectOption(
                                label=f"{mat_name} (x{amount})",
                                value=mat_name,
                                description=f"Sell 1 for {value} coins",
                            ))
                        if mat_options:
                            mat_select = Select(
                                placeholder="Select material to sell...",
                                options=mat_options,
                                custom_id="sell_material_select"
                            )
                            mat_select.callback = self.handle_material_sell
                            self.add_item(mat_select)

        except Exception as e:
            self.logger.error(f"Error in initialize_view: {str(e)}", exc_info=True)
            raise

    async def handle_button(self, interaction: discord.Interaction):
        """Handle button interactions"""
        try:
            custom_id = interaction.data["custom_id"]
            
            if custom_id == "menu":
                if hasattr(self, 'parent_menu_view') and self.parent_menu_view:
                    parent = self.parent_menu_view
                    parent.user_data = self.user_data
                    await self.timeout_manager.resume_parent_view(self)
                    parent.current_page = "main"
                    await parent.initialize_view()
                    embed = await parent.generate_embed()
                    await interaction.response.edit_message(embed=embed, view=parent)
                    parent.message = await interaction.original_response()
                else:
                    menu_view = await self.cog.create_menu(self.ctx, self.user_data)
                    embed = await menu_view.generate_embed()
                    await interaction.response.edit_message(embed=embed, view=menu_view)
                    menu_view.message = await interaction.original_response()
                return
                
            if custom_id == "back":
                self.current_page = "main"
                await interaction.response.defer()
                await self.update_view()
                
            elif custom_id == "sell_all":
                await interaction.response.defer()
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
                
            elif custom_id in ["rods", "bait", "fish", "materials", "tools"]:
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

    async def update_view(self):
        """Update the message with current embed and view"""
        try:
            await self.initialize_view()
            embed = await self.generate_embed()
            await self.message.edit(embed=embed, view=self)
        except Exception as e:
            self.logger.error(f"Error updating view: {e}", exc_info=True)
            await self.ctx.send(f"Error updating inventory view: {str(e)}")

    async def handle_rod_equip(self, interaction: discord.Interaction):
        """Handle rod equip from dropdown selection"""
        try:
            rod_name = interaction.data["values"][0]
            success, msg = await self.cog._equip_rod(interaction.user, rod_name)

            if success:
                self.user_data["rod"] = rod_name
                await interaction.response.defer()
                await self.update_view()
                message = await interaction.followup.send(msg, ephemeral=True, wait=True)
                self.cog.bot.loop.create_task(self.delete_after_delay(message))
            else:
                await interaction.response.send_message(msg, ephemeral=True, delete_after=2)

        except Exception as e:
            self.logger.error(f"Error in handle_rod_equip: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred. Please try again.",
                    ephemeral=True, delete_after=2
                )

    async def handle_bait_equip(self, interaction: discord.Interaction):
        """Handle bait equip from dropdown selection"""
        try:
            bait_name = interaction.data["values"][0]
            success, msg = await self.cog._equip_bait(interaction.user, bait_name)

            if success:
                self.user_data["equipped_bait"] = bait_name
                await interaction.response.defer()
                await self.update_view()
                message = await interaction.followup.send(msg, ephemeral=True, wait=True)
                self.cog.bot.loop.create_task(self.delete_after_delay(message))
            else:
                await interaction.response.send_message(msg, ephemeral=True, delete_after=2)

        except Exception as e:
            self.logger.error(f"Error in handle_bait_equip: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred. Please try again.",
                    ephemeral=True, delete_after=2
                )

    async def handle_material_sell(self, interaction: discord.Interaction):
        """Handle selling a material from dropdown selection"""
        try:
            mat_name = interaction.data["values"][0]
            mat_info = MATERIAL_TYPES.get(mat_name, {})
            value = mat_info.get("value", 0)

            if value <= 0:
                await interaction.response.send_message(
                    "This material has no sell value!",
                    ephemeral=True, delete_after=2
                )
                return

            # Remove 1 material
            success, msg = await self.cog.inventory.remove_item(
                interaction.user.id, "material", mat_name, 1
            )
            if not success:
                await interaction.response.send_message(
                    f"Failed to sell: {msg}",
                    ephemeral=True, delete_after=2
                )
                return

            # Deposit credits
            await bank.deposit_credits(interaction.user, value)

            # Refresh user data
            await self.cog.config_manager.invalidate_cache(f"user_{interaction.user.id}")
            fresh_data = await self.cog.config_manager.get_user_data(interaction.user.id)
            if fresh_data.success:
                self.user_data = fresh_data.data
                if hasattr(self, 'parent_menu_view') and self.parent_menu_view:
                    self.parent_menu_view.user_data = fresh_data.data

            await interaction.response.defer()
            await self.update_view()

            emoji = mat_info.get("emoji", "")
            message = await interaction.followup.send(
                f"Sold {emoji} **{mat_name}** for {value} coins!",
                ephemeral=True, wait=True
            )
            self.cog.bot.loop.create_task(self.delete_after_delay(message))

        except Exception as e:
            self.logger.error(f"Error in handle_material_sell: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred. Please try again.",
                    ephemeral=True, delete_after=2
                )
