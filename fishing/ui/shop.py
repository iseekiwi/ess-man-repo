# ui/shop.py

import discord
import logging
import asyncio
from typing import Dict, Optional, TypeVar, Type, Protocol, cast
from discord.ui import Button, Select, View
from redbot.core import bank
from .base import BaseView
from .components import MessageManager, QuantitySelector
from ..utils.logging_config import get_logger

T = TypeVar('T')

logger = get_logger('shop')

class PurchaseHandler(Protocol):
    """Protocol for purchase handling functions"""
    async def __call__(self, user: discord.Member, item_name: str, quantity: int, user_data: Dict) -> tuple[bool, str]: ...

class ShopCategory(Protocol):
    """Protocol for shop categories"""
    name: str
    items: Dict[str, Dict]
    handle_purchase: PurchaseHandler

class PurchaseConfirmView(BaseView):
    """Enhanced confirmation view with improved feedback and error handling"""
    
    def __init__(
        self,
        cog,
        ctx,
        item_name: str,
        quantity: int,
        cost_per_item: int,
        handler: PurchaseHandler
    ):
        super().__init__(cog, ctx, timeout=30)
        self.item_name = item_name
        self.quantity = quantity
        self.total_cost = cost_per_item * quantity
        self.handler = handler
        self.value = None
        self.message = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        """Handle purchase confirmation."""
        try:
            self.logger.debug(f"Processing purchase confirmation for {self.item_name}")
            self.value = True
            self.stop()
            
            # Disable buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(view=self)
            
            # Process purchase
            user_data = await self.cog.config_manager.get_user_data(interaction.user.id)
            if user_data.success:
                success, msg = await self.handler(
                    interaction.user,
                    self.item_name,
                    self.quantity,
                    user_data.data
                )
                
                if success:
                    self.logger.info(
                        f"Purchase successful: {self.quantity}x {self.item_name} "
                        f"by {interaction.user.name}"
                    )
                    
                confirm_msg = await interaction.followup.send(msg, ephemeral=True)
                self.cog.bot.loop.create_task(self._delete_after_delay(confirm_msg))
            
        except Exception as e:
            self.logger.error(f"Error in purchase confirmation: {e}", exc_info=True)
            error_msg = await interaction.followup.send(
                "An error occurred during purchase.",
                ephemeral=True
            )
            self.cog.bot.loop.create_task(self._delete_after_delay(error_msg))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        """Handle purchase cancellation."""
        try:
            self.logger.debug(f"Purchase cancelled for {self.item_name}")
            self.value = False
            self.stop()
            
            # Disable buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(view=self)
            
            cancel_msg = await interaction.followup.send(
                "Purchase cancelled.",
                ephemeral=True
            )
            self.cog.bot.loop.create_task(self._delete_after_delay(cancel_msg))
            
        except Exception as e:
            self.logger.error(f"Error in purchase cancellation: {e}", exc_info=True)
            error_msg = await interaction.followup.send(
                "An error occurred while cancelling.",
                ephemeral=True
            )
            self.cog.bot.loop.create_task(self._delete_after_delay(error_msg))

    async def _delete_after_delay(self, message: discord.Message, delay: float = 2.0):
        """Delete a message after a delay."""
        try:
            await asyncio.sleep(delay)
            await message.delete()
        except discord.NotFound:
            pass
        except Exception as e:
            self.logger.error(f"Error deleting message: {e}")

class ShopView(BaseView):
    """Enhanced view for the fishing shop interface"""
    
    def __init__(self, cog, ctx, user_data: Dict):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.current_page = "main"
        self.selected_quantity = 1
        self.current_balance = 0
        self.currency_name = "coins"
        self.logger = get_logger('shop.view')
        
    async def setup(self) -> 'ShopView':
        """Initialize the shop view."""
        try:
            self.logger.debug(f"Setting up ShopView for {self.ctx.author.name}")
            
            if not self.user_data:
                raise ValueError("User data is missing")
            
            if not hasattr(self.cog, 'data'):
                raise ValueError("Cog data not accessible")
            
            # Get currency name
            try:
                self.currency_name = await bank.get_currency_name(self.ctx.guild)
            except Exception as e:
                self.logger.error(f"Error getting currency name: {e}")
            
            await self.initialize_view()
            return self
            
        except Exception as e:
            self.logger.error(f"Error in ShopView setup: {e}", exc_info=True)
            raise

    async def initialize_view(self):
        """Initialize view components based on current page."""
        try:
            self.clear_items()
            
            if self.current_page == "main":
                await self._setup_main_page()
            else:
                await self._setup_category_page()
                
        except Exception as e:
            self.logger.error(f"Error initializing view: {e}", exc_info=True)
            raise

    async def _setup_main_page(self):
        """Set up main shop page."""
        categories = [
            ("Buy Bait", "bait", discord.ButtonStyle.blurple),
            ("Buy Rods", "rods", discord.ButtonStyle.blurple)
        ]
        
        for label, custom_id, style in categories:
            button = Button(label=label, custom_id=custom_id, style=style)
            button.callback = self.handle_button
            self.add_item(button)
        
        back_button = Button(
            label="Back to Menu",
            custom_id="menu",
            style=discord.ButtonStyle.grey
        )
        back_button.callback = self.handle_button
        self.add_item(back_button)

    async def _setup_category_page(self):
        """Set up category-specific shop page."""
        back_button = Button(
            label="Back",
            custom_id="back",
            style=discord.ButtonStyle.grey
        )
        back_button.callback = self.handle_button
        self.add_item(back_button)
        
        if self.current_page == "bait":
            await self._setup_bait_page()
        elif self.current_page == "rods":
            await self._setup_rods_page()

    async def _setup_bait_page(self):
        """Set up bait shop page."""
        # Add quantity selector
        quantity_select = QuantitySelector(self.handle_quantity_select)
        self.add_item(quantity_select)
        
        # Get current stock
        stock_result = await self.cog.config_manager.get_global_setting("bait_stock")
        current_stock = stock_result.data if stock_result.success else {}
        
        for bait_name, bait_data in self.cog.data["bait"].items():
            if current_stock.get(bait_name, 0) > 0:
                purchase_button = Button(
                    label=f"Buy {bait_name}",
                    custom_id=f"buy_{bait_name}",
                    style=discord.ButtonStyle.green
                )
                purchase_button.callback = self.handle_purchase
                self.add_item(purchase_button)

    async def _setup_rods_page(self):
        """Set up rods shop page."""
        for rod_name, rod_data in self.cog.data["rods"].items():
            if (rod_name != "Basic Rod" and 
                rod_name not in self.user_data.get("purchased_rods", {}) and
                await self._meets_requirements(rod_data.get("requirements", {}))):
                
                purchase_button = Button(
                    label=f"Buy {rod_name}",
                    custom_id=f"buy_{rod_name}",
                    style=discord.ButtonStyle.green
                )
                purchase_button.callback = self.handle_purchase
                self.add_item(purchase_button)

    async def _meets_requirements(self, requirements: Dict) -> bool:
        """Check if user meets item requirements."""
        if not requirements:
            return True
            
        return (
            self.user_data.get("level", 1) >= requirements.get("level", 1) and
            self.user_data.get("fish_caught", 0) >= requirements.get("fish_caught", 0)
        )

    async def generate_embed(self) -> discord.Embed:
        """Generate shop embed based on current page."""
        try:
            self.current_balance = await bank.get_balance(self.ctx.author)
            embed = discord.Embed(color=discord.Color.green())
            
            if self.current_page == "main":
                await self._generate_main_embed(embed)
            elif self.current_page == "bait":
                await self._generate_bait_embed(embed)
            elif self.current_page == "rods":
                await self._generate_rods_embed(embed)
            
            # Add footer with balance
            footer_text = f"Your balance: {self.current_balance} {self.currency_name}"
            if self.current_page == "bait" and self.selected_quantity > 1:
                footer_text += f" | Quantity: {self.selected_quantity}"
            embed.set_footer(text=footer_text)
            
            return embed
            
        except Exception as e:
            self.logger.error(f"Error generating embed: {e}", exc_info=True)
            raise

    async def _generate_main_embed(self, embed: discord.Embed):
        """Generate main shop page embed."""
        embed.title = "🏪 Fishing Shop"
        embed.description = "Welcome! What would you like to buy?"
        embed.add_field(
            name="Categories",
            value=(
                "🪱 **Bait** - Various baits for fishing\n"
                "🎣 **Rods** - Better rods, better catches!"
            ),
            inline=False
        )

    async def _generate_bait_embed(self, embed: discord.Embed):
        """Generate bait shop page embed."""
        embed.title = "🪱 Bait Shop"
        stock_result = await self.cog.config_manager.get_global_setting("bait_stock")
        current_stock = stock_result.data if stock_result.success else {}
        
        bait_entries = []
        for bait_name, bait_data in self.cog.data["bait"].items():
            stock = current_stock.get(bait_name, 0)
            status = f"📦 Stock: {stock}" if stock > 0 else "❌ Out of stock!"
            
            entry = (
                f"**{bait_name}** - {bait_data['cost']} {self.currency_name}\n"
                f"{bait_data['description']}\n"
                f"{status}\n"
            )
            bait_entries.append(entry)
            
        embed.description = "\n".join(bait_entries) if bait_entries else "No bait available!"

    async def _generate_rods_embed(self, embed: discord.Embed):
        """Generate rods shop page embed."""
        embed.title = "🎣 Rod Shop"
        rod_entries = []
        
        for rod_name, rod_data in self.cog.data["rods"].items():
            if rod_name == "Basic Rod":
                continue
                
            owned = rod_name in self.user_data.get("purchased_rods", {})
            status = "✅ Owned" if owned else f"💰 Cost: {rod_data['cost']} {self.currency_name}"
            
            requirements = rod_data.get("requirements", {})
            req_text = (
                f"\nRequires: Level {requirements['level']}, "
                f"{requirements['fish_caught']} fish caught"
            ) if requirements else ""
            
            entry = (
                f"**{rod_name}**\n"
                f"{rod_data['description']}\n"
                f"{status}{req_text}\n"
            )
            rod_entries.append(entry)
            
        embed.description = "\n".join(rod_entries) if rod_entries else "No rods available!"

    async def handle_button(self, interaction: discord.Interaction):
        """Handle button interactions."""
        try:
            custom_id = interaction.data["custom_id"]
            
            if custom_id == "menu":
                menu_view = await self.cog.create_menu(self.ctx, self.user_data)
                embed = await menu_view.generate_embed()
                await interaction.response.edit_message(embed=embed, view=menu_view)
                menu_view.message = await interaction.original_response()
                return
                
            if custom_id in ["bait", "rods"]:
                self.current_page = custom_id
            elif custom_id == "back":
                self.current_page = "main"
                self.selected_quantity = 1
                
            await self.initialize_view()
            embed = await self.generate_embed()
            await interaction.response.edit_message(embed=embed, view=self)
            self.message = await interaction.original_response()
            
        except Exception as e:
            self.logger.error(f"Error handling button: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred. Please try again.",
                ephemeral=True
            )

    async def handle_quantity_select(self, interaction: discord.Interaction, quantity: int):
        """Handle quantity selection."""
        try:
            self.selected_quantity = quantity
            await interaction.response.defer()
            embed = await self.generate_embed()
            await self.message.edit(embed=embed, view=self)
        except Exception as e:
            self.logger.error(f"Error handling quantity selection: {e}", exc_info=True)
            await MessageManager.send_temp_message(
                interaction,
                "Error processing selection.",
                ephemeral=True
            )

    async def handle_purchase(self, interaction: discord.Interaction):
            """Handle purchase button interactions."""
            try:
                custom_id = interaction.data["custom_id"]
                item_name = custom_id.replace("buy_", "")
                
                # Get item data and cost
                if item_name in self.cog.data["bait"]:
                    item_data = self.cog.data["bait"][item_name]
                    cost = item_data["cost"]
                    quantity = self.selected_quantity
                    handler = self.cog._handle_bait_purchase
                else:
                    item_data = self.cog.data["rods"][item_name]
                    cost = item_data["cost"]
                    quantity = 1
                    handler = self.cog._handle_rod_purchase
                
                total_cost = cost * quantity
                
                # Create confirmation view
                confirm_view = PurchaseConfirmView(
                    self.cog,
                    self.ctx,
                    item_name,
                    quantity,
                    cost,
                    handler
                )
                
                await interaction.response.send_message(
                    f"Confirm purchase of {quantity}x {item_name} for {total_cost} {self.currency_name}?",
                    view=confirm_view,
                    ephemeral=True
                )
                
                confirm_view.message = await interaction.original_response()
                await confirm_view.wait()
                
                if confirm_view.value:
                    # Refresh user data and view
                    user_data_result = await self.cog.config_manager.get_user_data(self.ctx.author.id)
                    if user_data_result.success:
                        self.user_data = user_data_result.data
                        await self.initialize_view()
                        embed = await self.generate_embed()
                        await self.message.edit(embed=embed, view=self)
                
            except Exception as e:
                self.logger.error(f"Error in handle_purchase: {e}", exc_info=True)
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "An error occurred. Please try again.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "An error occurred. Please try again.",
                        ephemeral=True
                    )
    
    async def update_view(self):
        """Update the message with current embed and view."""
        try:
            # Refresh user data
            user_data_result = await self.cog.config_manager.get_user_data(self.ctx.author.id)
            if user_data_result.success:
                self.user_data = user_data_result.data
                
            embed = await self.generate_embed()
            await self.message.edit(embed=embed, view=self)
                
        except Exception as e:
            self.logger.error(f"Error updating view: {e}", exc_info=True)
            raise
