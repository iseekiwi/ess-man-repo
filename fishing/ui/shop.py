# ui/shop.py

import discord
import logging
import asyncio
from typing import Dict, Optional
from discord.ui import Button, Select
from redbot.core import bank
from .base import BaseView
from ..utils.logging_config import get_logger
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .menu import FishingMenuView

logger = get_logger('shop')

class BaitQuantityModal(discord.ui.Modal):
    def __init__(self, shop_view, bait_name: str):
        super().__init__(title=f"Purchase {bait_name}")
        self.shop_view = shop_view
        self.bait_name = bait_name
        
        self.quantity_input = discord.ui.TextInput(
            label="How many would you like to purchase?",
            placeholder="Enter a number...",
            min_length=1,
            max_length=4,
            required=True
        )
        self.add_item(self.quantity_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate input is a number
            try:
                quantity = int(self.quantity_input.value)
                if quantity <= 0:
                    raise ValueError("Quantity must be positive")
            except ValueError:
                await interaction.response.send_message(
                    "Please enter a valid positive number!",
                    ephemeral=True,
                    delete_after=2
                )
                return

            # Get cost information
            cost = self.shop_view.cog.data["bait"][self.bait_name]["cost"]
            total_cost = cost * quantity

            # Check if user can afford
            if not await self.shop_view.cog._can_afford(interaction.user, total_cost):
                await interaction.response.send_message(
                    f"❌ You don't have enough coins! This purchase costs {total_cost} coins.",
                    ephemeral=True,
                    delete_after=2
                )
                return

            # Create confirmation view
            confirm_view = PurchaseConfirmView(
                self.shop_view.cog,
                self.shop_view.ctx,
                self.bait_name,
                quantity,
                cost
            )

            await interaction.response.send_message(
                f"Confirm purchase of {quantity}x {self.bait_name} for {total_cost} coins?",
                view=confirm_view,
                ephemeral=True
            )
            
            confirm_view.message = await interaction.original_response()
            await confirm_view.wait()

            if confirm_view.value:
                success, msg = await self.shop_view.cog._handle_bait_purchase(
                    interaction.user,
                    self.bait_name,
                    quantity,
                    self.shop_view.user_data
                )

                if success:
                    # Refresh user data
                    user_data_result = await self.shop_view.cog.config_manager.get_user_data(interaction.user.id)
                    if user_data_result.success:
                        self.shop_view.user_data = user_data_result.data
                        await self.shop_view.cog.config_manager.refresh_cache(interaction.user.id)
                        
                        fresh_data = await self.shop_view.cog.config_manager.get_user_data(interaction.user.id)
                        if fresh_data.success:
                            self.shop_view.user_data = fresh_data.data
                            
                            # Update parent menu view if it exists
                            if hasattr(self.shop_view, 'parent_menu_view'):
                                self.shop_view.parent_menu_view.user_data = fresh_data.data
                                await self.shop_view.parent_menu_view.initialize_view()
                                menu_embed = await self.shop_view.parent_menu_view.generate_embed()
                                await self.shop_view.parent_menu_view.message.edit(
                                    embed=menu_embed,
                                    view=self.shop_view.parent_menu_view
                                )
                                await self.shop_view.parent_menu_view.setup()

                            await self.shop_view.initialize_view()
                            await self.shop_view.update_view()

                # Show result message
                result_msg = await interaction.followup.send(msg, ephemeral=True, wait=True)
                self.shop_view.cog.bot.loop.create_task(self.shop_view.delete_after_delay(result_msg))

        except Exception as e:
            self.shop_view.logger.error(f"Error in quantity modal: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while processing your purchase. Please try again.",
                ephemeral=True,
                delete_after=2
            )

class PurchaseConfirmView(BaseView):
    def __init__(self, cog, ctx, item_name: str, quantity: int, cost_per_item: int):
        super().__init__(cog, ctx, timeout=60)
        self.item_name = item_name
        self.quantity = quantity
        self.total_cost = cost_per_item * quantity
        self.value = None
        self.message = None
        self.success_message = None  # Store the success message to return to handle_purchase

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.ctx.author.id:
            logger.debug(f"User {interaction.user.id} is authorized for interaction.")
            return True
        logger.warning(f"Unauthorized interaction attempt by user {interaction.user.id}")
        return False

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        """Handle purchase confirmation."""
        self.logger.debug(f"Confirm button pressed by user {interaction.user.id} for {self.item_name}")
        
        try:
            # Set confirmation value
            self.value = True
            self.stop()
            
            # Delete confirmation prompt
            try:
                if self.message:
                    await self.message.delete()
            except discord.NotFound:
                pass  # Message was already deleted
            except Exception as e:
                self.logger.error(f"Error deleting confirmation message: {e}", exc_info=True)
            
            # First defer the response
            await interaction.response.defer(ephemeral=True)
            
            # Then send the confirmation message
            confirmation_msg = await interaction.followup.send(
                "Purchase confirmed! Processing...",
                ephemeral=True
            )
            
            # Schedule deletion using the cog's bot loop
            self.cog.bot.loop.create_task(self.delete_after_delay(confirmation_msg))
            
        except Exception as e:
            self.logger.error(f"Error in purchase confirmation: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred during purchase confirmation.",
                    ephemeral=True
                )
            else:
                error_msg = await interaction.followup.send(
                    "An error occurred during purchase confirmation.",
                    ephemeral=True
                )
                self.cog.bot.loop.create_task(self.delete_after_delay(error_msg))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        """Handle purchase cancellation."""
        try:
            self.logger.debug(f"Cancel button pressed by user {interaction.user.id} for {self.item_name}")
            self.value = False
            self.stop()
            
            # Delete confirmation prompt
            try:
                if self.message:
                    await self.message.delete()
            except discord.NotFound:
                pass  # Message was already deleted
            except Exception as e:
                self.logger.error(f"Error deleting cancellation message: {e}", exc_info=True)
            
            # First defer the response
            await interaction.response.defer(ephemeral=True)
            
            # Then send the cancellation message
            cancel_msg = await interaction.followup.send(
                "Purchase cancelled.",
                ephemeral=True
            )
            self.cog.bot.loop.create_task(self.delete_after_delay(cancel_msg))
                
        except Exception as e:
            self.logger.error(f"Error in purchase cancellation: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while cancelling the purchase.",
                    ephemeral=True
                )
            else:
                error_msg = await interaction.followup.send(
                    "An error occurred while cancelling the purchase.",
                    ephemeral=True
                )
                self.cog.bot.loop.create_task(self.delete_after_delay(error_msg))

    async def delete_after_delay(self, message):
        """Helper method to delete a message after a delay"""
        try:
            await asyncio.sleep(2)  # Wait 2 seconds
            await message.delete()
        except discord.NotFound:
            pass  # Message was already deleted
        except Exception as e:
            self.logger.error(f"Error in delete_after_delay: {e}")

    async def on_timeout(self):
        """Handle view timeout."""
        self.logger.info(f"Purchase view timed out for {self.item_name}")
        try:
            if self.message:
                await self.message.delete()
        except discord.NotFound:
            pass  # Message was already deleted
        except Exception as e:
            self.logger.error(f"Error handling timeout cleanup: {e}", exc_info=True)

class ShopView(BaseView):
    """View for the fishing shop interface"""
    
    def __init__(self, cog, ctx, user_data: Dict):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.current_page = "main"
        self.current_balance = 0
        self.logger = get_logger('shop.view')
        self.logger.debug(f"Initializing ShopView for user {ctx.author.name}")

    async def setup(self):
        """Async setup method to initialize the view"""
        try:
            self.logger.debug(f"Setting up ShopView for user {self.ctx.author.name}")
            
            # Verify user data
            if not self.user_data:
                self.logger.error(f"User data is empty for {self.ctx.author.name}")
                raise ValueError("User data is missing")
                
            # Verify cog data is accessible
            if not hasattr(self.cog, 'data'):
                self.logger.error("Cog data not accessible")
                raise ValueError("Cog data not accessible")
            
            await self.initialize_view()
            self.logger.debug("ShopView setup completed successfully")
            return self
            
        except Exception as e:
            self.logger.error(f"Error in ShopView setup: {str(e)}", exc_info=True)
            raise

    async def initialize_view(self):
        """Initialize the view based on current page"""
        try:
            self.logger.debug(f"Initializing view for page: {self.current_page}")
            self.clear_items()
            
            if self.current_page == "main":
                self.logger.debug("Setting up main page buttons")
                bait_button = Button(
                    label="Buy Bait",
                    style=discord.ButtonStyle.blurple,
                    custom_id="bait"
                )
                bait_button.callback = self.handle_button
                self.add_item(bait_button)
    
                rod_button = Button(
                    label="Buy Rods",
                    style=discord.ButtonStyle.blurple,
                    custom_id="rods"
                )
                rod_button.callback = self.handle_button
                self.add_item(rod_button)
                
                # Add back button to main shop page
                back_button = Button(
                    label="Back to Menu",
                    style=discord.ButtonStyle.grey,
                    custom_id="menu"
                )
                back_button.callback = self.handle_button
                self.add_item(back_button)
                
            else:
                self.logger.debug("Setting up back button")
                back_button = Button(
                    label="Back",
                    style=discord.ButtonStyle.grey,
                    custom_id="back"
                )
                back_button.callback = self.handle_button
                self.add_item(back_button)
                
                if self.current_page == "bait":
                    self.logger.debug("Setting up bait page")
                    
                    # Get current stock
                    stock_result = await self.cog.config_manager.get_global_setting("bait_stock")
                    if not stock_result.success:
                        bait_stock = {}
                    else:
                        bait_stock = stock_result.data
    
                    user_level = self.user_data.get("level", 1)
                    for bait_name, bait_data in self.cog.data["bait"].items():
                        stock = bait_stock.get(bait_name, 0)
                        requirements = bait_data.get("requirements", {})
                        level_req = requirements.get("level", 1) if requirements else 1
                        
                        # Check if bait is available and user meets level requirement
                        if stock > 0 and user_level >= level_req:
                            purchase_button = Button(
                                label=f"Buy {bait_name}",
                                style=discord.ButtonStyle.green,
                                custom_id=f"buy_{bait_name}"
                            )
                            purchase_button.callback = self.handle_purchase
                            self.add_item(purchase_button)
    
                elif self.current_page == "rods":
                    self.logger.debug("Setting up rods page")
                    for rod_name, rod_data in self.cog.data["rods"].items():
                        if rod_name == "Basic Rod":
                            continue
                            
                        if rod_name in self.user_data.get("purchased_rods", {}):
                            self.logger.debug(f"Rod {rod_name} already owned")
                            continue
    
                        requirements = rod_data.get("requirements", {})
                        level_req = requirements.get("level", 1)
                        fish_req = requirements.get("fish_caught", 0)
                        
                        user_level = self.user_data.get("level", 1)
                        user_fish = self.user_data.get("fish_caught", 0)
                        
                        self.logger.debug(f"Checking requirements for {rod_name}: "
                                        f"Level {user_level}/{level_req}, "
                                        f"Fish {user_fish}/{fish_req}")
                        
                        if user_level >= level_req and user_fish >= fish_req:
                            purchase_button = Button(
                                label=f"Buy {rod_name}",
                                style=discord.ButtonStyle.green,
                                custom_id=f"buy_{rod_name}"
                            )
                            purchase_button.callback = self.handle_purchase
                            self.add_item(purchase_button)

            self.logger.debug("View initialization completed successfully")
            
        except Exception as e:
            self.logger.error(f"Error in initialize_view: {str(e)}", exc_info=True)
            raise

    async def generate_embed(self) -> discord.Embed:
        """Generate the appropriate embed based on current page"""
        try:
            self.logger.debug(f"Generating embed for page: {self.current_page}")
            embed = discord.Embed(color=discord.Color.green())
            
            # Get current balance
            try:
                self.current_balance = await bank.get_balance(self.ctx.author)
                currency_name = await bank.get_currency_name(self.ctx.guild)
                stock_result = await self.cog.config_manager.get_global_setting("bait_stock")
                current_stock = stock_result.data if stock_result.success else {}
                self.logger.debug(f"User balance: {self.current_balance} {currency_name}")
                self.logger.debug(f"Current bait stock: {current_stock}")
            except Exception as e:
                self.logger.error(f"Error getting balance or stock: {e}")
                self.current_balance = 0
                currency_name = "coins"
                current_stock = {}

            if self.current_page == "main":
                self.logger.debug("Generating main page embed")
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

            elif self.current_page == "bait":
                self.logger.debug("Generating bait page embed")
                embed.title = "🪱 Bait Shop"
                bait_list = []
                user_level = self.user_data.get("level", 1)
                
                for bait_name, bait_data in self.cog.data["bait"].items():
                    stock = current_stock.get(bait_name, 0)
                    requirements = bait_data.get("requirements", {})
                    level_req = requirements.get("level", 1) if requirements else 1
                    
                    if level_req > user_level:
                        status = f"🔒 Requires Level {level_req}"
                    else:
                        status = "📦 Stock: `{}`".format(stock) if stock > 0 else "❌ Out of stock!"
                    
                    bait_entry = (
                        f"**{bait_name}** - {bait_data['cost']} {currency_name}\n"
                        f"{bait_data['description']}\n"
                        f"{status}\n"
                    )
                    bait_list.append(bait_entry)
                
                embed.description = "\n".join(bait_list) if bait_list else "No bait available!"

            elif self.current_page == "rods":
                self.logger.debug("Generating rods page embed")
                embed.title = "🎣 Rod Shop"
                rod_list = []
                
                for rod_name, rod_data in self.cog.data["rods"].items():
                    if rod_name == "Basic Rod":
                        continue
                    
                    owned = rod_name in self.user_data.get("purchased_rods", {})
                    status = "✅ Owned" if owned else f"💰 *Cost*: {rod_data['cost']} {currency_name}"
                    
                    requirements = rod_data.get("requirements")
                    req_text = ""
                    if requirements:
                        req_text = f"\n*Requires*: Level {requirements['level']}"
                    else:
                        req_text = ""
                    
                    rod_entry = (
                        f"**{rod_name}**\n"
                        f"{rod_data['description']}\n"
                        f"{status}{req_text}\n"
                    )
                    rod_list.append(rod_entry)
                
                embed.description = "\n".join(rod_list) if rod_list else "No rods available!"

            # Add footer with balance
            embed.set_footer(text=f"Your balance: {self.current_balance} {currency_name}")
            
            self.logger.debug("Embed generated successfully")
            return embed
    
        except Exception as e:
            self.logger.error(f"Error generating embed: {str(e)}", exc_info=True)
            raise

    async def handle_button(self, interaction: discord.Interaction):
        """Handle navigation button interactions"""
        try:
            custom_id = interaction.data["custom_id"]
            
            if custom_id == "menu":
                # Import here to avoid circular import
                from .menu import FishingMenuView
                menu_view = await FishingMenuView(self.cog, self.ctx, self.user_data).setup()
                embed = await menu_view.generate_embed()
                await interaction.response.edit_message(embed=embed, view=menu_view)
                menu_view.message = await interaction.original_response()
                return
                
            if custom_id == "bait":
                self.current_page = "bait"
                await self.initialize_view()
                embed = await self.generate_embed()
                await interaction.response.edit_message(embed=embed, view=self)
                self.message = await interaction.original_response()
                
            elif custom_id == "rods":
                self.current_page = "rods"
                await self.initialize_view()
                embed = await self.generate_embed()
                await interaction.response.edit_message(embed=embed, view=self)
                self.message = await interaction.original_response()
                
            elif custom_id == "back":
                self.current_page = "main"
                self.selected_quantity = 1
                await self.initialize_view()
                embed = await self.generate_embed()
                await interaction.response.edit_message(embed=embed, view=self)
                self.message = await interaction.original_response()
                
        except Exception as e:
            self.logger.error(f"Error in handle_button: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while navigating the shop. Please try again.",
                ephemeral=True,
                delete_after=2
            )
            
    async def handle_select(self, interaction: discord.Interaction):
        """Handle quantity selection"""
        try:
            self.logger.debug(f"Handling quantity selection: {interaction.data['values'][0]}")
            self.selected_quantity = int(interaction.data["values"][0])
            await interaction.response.defer()
            await self.update_view()
        except Exception as e:
            self.logger.error(f"Error in handle_select: {e}", exc_info=True)
            message = await interaction.response.send_message(
                "An error occurred while selecting quantity. Please try again.",
                ephemeral=True,
                wait=True
            )
            self.cog.bot.loop.create_task(self.delete_after_delay(message))
    
    async def handle_purchase(self, interaction: discord.Interaction):
        """Handle purchase button interactions"""
        try:
            self.logger.debug(f"Starting purchase process for interaction: {interaction.data['custom_id']}")
            custom_id = interaction.data["custom_id"]
            item_name = custom_id.replace("buy_", "")
            
            # Handle rod purchases
            if item_name in self.cog.data["rods"]:
                cost = self.cog.data["rods"][item_name]["cost"]
    
                # Add balance check here
                if not await self.cog._can_afford(self.ctx.author, cost):
                    await interaction.response.send_message(
                        f"❌ You don't have enough coins! This purchase costs {cost} coins.",
                        ephemeral=True,
                        delete_after=2
                    )
                    return
                
                confirm_view = PurchaseConfirmView(
                    self.cog,
                    self.ctx,
                    item_name,
                    1,  # Quantity is always 1 for rods
                    cost
                )
        
                await interaction.response.send_message(
                    f"Confirm purchase of {item_name} for {cost} coins?",
                    view=confirm_view,
                    ephemeral=True
                )
                
                confirm_view.message = await interaction.original_response()
                await confirm_view.wait()
                
                if confirm_view.value:
                    success, msg = await self.cog._handle_rod_purchase(
                        self.ctx.author,
                        item_name,
                        self.user_data
                    )
        
                    if success:
                        # Refresh user data from config
                        user_data_result = await self.cog.config_manager.get_user_data(self.ctx.author.id)
                        if user_data_result.success:
                            # Update the view's user data
                            self.user_data = user_data_result.data
                            
                            # Force refresh the cache
                            await self.cog.config_manager.refresh_cache(self.ctx.author.id)
                            
                            # Get fresh data after cache refresh
                            fresh_data = await self.cog.config_manager.get_user_data(self.ctx.author.id)
                            if fresh_data.success:
                                self.user_data = fresh_data.data
                                
                                # Update parent menu view if it exists
                                if hasattr(self, 'parent_menu_view'):
                                    self.parent_menu_view.user_data = fresh_data.data
                                    await self.parent_menu_view.initialize_view()
                                    menu_embed = await self.parent_menu_view.generate_embed()
                                    await self.parent_menu_view.message.edit(embed=menu_embed, view=self.parent_menu_view)
                                    await self.parent_menu_view.setup()
                                
                                # Reinitialize the view with new data
                                await self.initialize_view()
                                await self.update_view()
                    
                    # Always show the result message
                    message = await interaction.followup.send(msg, ephemeral=True, wait=True)
                    self.cog.bot.loop.create_task(self.delete_after_delay(message))
                    
            # Handle bait purchases with modal
            else:
                modal = BaitQuantityModal(self, item_name)
                await interaction.response.send_modal(modal)
                
        except Exception as e:
            self.logger.error(f"Error in handle_purchase: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while processing your purchase. Please try again.",
                    ephemeral=True,
                    delete_after=2
                )
            else:
                message = await interaction.followup.send(
                    "An error occurred while processing your purchase. Please try again.",
                    ephemeral=True,
                    wait=True
                )
                self.cog.bot.loop.create_task(self.delete_after_delay(message))
    
    # Add delete_after_delay method to both classes
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
            self.logger.debug("Updating view")
            # Refresh user data before updating
            user_data_result = await self.cog.config_manager.get_user_data(self.ctx.author.id)
            if user_data_result.success:
                self.user_data = user_data_result.data
            
            embed = await self.generate_embed()
            await self.message.edit(embed=embed, view=self)
            self.logger.debug("View updated successfully")
        except Exception as e:
            self.logger.error(f"Error updating view: {e}", exc_info=True)
            raise
