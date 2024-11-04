# ui/shop.py

import discord
import logging
import asyncio
import time
from typing import Dict, Optional
from discord.ui import Button, Select
from redbot.core import bank
from .base import BaseView
from .components import MessageManager
from ..utils.logging_config import get_logger
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .menu import FishingMenuView

logger = get_logger('shop')

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

class PurchaseConfirmView(BaseView):
    def __init__(self, cog, ctx, item_name: str, quantity: int, cost_per_item: int):
        super().__init__(cog, ctx, timeout=60)
        self.item_name = item_name
        self.quantity = quantity
        self.total_cost = cost_per_item * quantity
        self.value = None
        self.message = None
        self.success_message = None  # Store the success message to return to handle_purchase

    async def start(self):
        """Start the confirmation view"""
        await super().start()
        return self

    async def cleanup(self):
        """Enhanced cleanup implementation"""
        try:
            for child in self.children:
                child.disabled = True
            if self.message:
                try:
                    await self.message.edit(view=self)
                except discord.NotFound:
                    pass
            await super().cleanup()
        except Exception as e:
            self.logger.error(f"Error in purchase view cleanup: {e}")
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.ctx.author.id:
            logger.debug(f"User {interaction.user.id} is authorized for interaction.")
            return True
        logger.warning(f"Unauthorized interaction attempt by user {interaction.user.id}")
        return False

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if not await self.interaction_check(interaction):
            return
            
        self.value = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if not await self.interaction_check(interaction):
            return
            
        self.value = False
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

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
        """Enhanced timeout handling"""
        try:
            if self.message:
                for child in self.children:
                    child.disabled = True
                await self.message.edit(view=self)
                await asyncio.sleep(1)
                await self.message.delete()
        except discord.NotFound:
            pass
        except Exception as e:
            self.logger.error(f"Error in purchase view timeout: {e}")
        finally:
            self.stop()

class ShopView(BaseView):
    """View for the fishing shop interface"""
    
    def __init__(self, cog, ctx, user_data: Dict):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.current_page = "main"
        self.selected_quantity = 1
        self.current_balance = 0
        self.logger = get_logger('shop.view')
        self.logger.debug(f"Initializing ShopView for user {ctx.author.name}")

    async def start(self):
        """Start the shop view"""
        try:
            embed = await self.generate_embed()
            self.message = await self.ctx.send(embed=embed, view=self)
            await super().start()
            return self
        except Exception as e:
            self.logger.error(f"Error starting shop view: {e}", exc_info=True)
            return None
    
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
                bait_button.callback = self.handle_button  # Use the new handler
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
                    
                    quantity_select = QuantitySelect()
                    quantity_select.callback = self.handle_select
                    self.add_item(quantity_select)
    
                    for bait_name, bait_data in self.cog.data["bait"].items():
                        stock = bait_stock.get(bait_name, 0)
                        if stock > 0:
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
                bait_stock = {}

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
                
                for bait_name, bait_data in self.cog.data["bait"].items():
                    stock = current_stock.get(bait_name, 0)
                    status = "📦 Stock: {}".format(stock) if stock > 0 else "❌ Out of stock!"
                    
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
                    status = "✅ Owned" if owned else f"💰 Cost: {rod_data['cost']} {currency_name}"
                    
                    requirements = rod_data.get("requirements")
                    req_text = ""
                    if requirements:
                        req_text = f"\nRequires: Level {requirements['level']}, {requirements['fish_caught']} fish caught"
                    
                    rod_entry = (
                        f"**{rod_name}**\n"
                        f"{rod_data['description']}\n"
                        f"{status}{req_text}\n"
                    )
                    rod_list.append(rod_entry)
                
                embed.description = "\n".join(rod_list) if rod_list else "No rods available!"

            # Add footer with balance
            if self.current_page == "bait" and self.selected_quantity > 1:
                embed.set_footer(text=f"Your balance: {self.current_balance} {currency_name} | Quantity: {self.selected_quantity}")
            else:
                embed.set_footer(text=f"Your balance: {self.current_balance} {currency_name}")
            
            self.logger.debug("Embed generated successfully")
            return embed
    
        except Exception as e:
            self.logger.error(f"Error generating embed: {str(e)}", exc_info=True)
            raise

    async def handle_button(self, interaction: discord.Interaction):
        try:
            custom_id = interaction.data["custom_id"]
            
            if not await self.interaction_check(interaction):
                return
            
            if custom_id == "menu" or (custom_id == "back" and self.current_page == "main"):
                # Return to parent menu if it exists
                if hasattr(self, 'parent_view') and self.parent_view:
                    await self.cleanup()  # Clean up this view
                    self.parent_view.current_page = "main"
                    await self.parent_view.initialize_view()
                    embed = await self.parent_view.generate_embed()
                    await interaction.response.edit_message(embed=embed, view=self.parent_view)
                    self.parent_view.message = await interaction.original_response()
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
            self.logger.error(f"Error in handle_button: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred. Please try again.",
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
            custom_id = interaction.data["custom_id"]
            item_name = custom_id.replace("buy_", "")
            
            if item_name in self.cog.data["bait"]:
                cost = self.cog.data["bait"][item_name]["cost"]
                quantity = self.selected_quantity
            else:
                cost = self.cog.data["rods"][item_name]["cost"]
                quantity = 1
            
            # Create confirmation view with 30s timeout
            confirm_view = PurchaseConfirmView(
                self.cog,
                self.ctx,
                item_name,
                quantity,
                cost
            )
            
            await interaction.response.send_message(
                f"Confirm purchase of {quantity}x {item_name} for {cost * quantity} coins?",
                view=confirm_view,
                ephemeral=True
            )
            
            confirm_view.message = await interaction.original_response()
            await confirm_view.start()
    
            # Use an event to handle immediate confirmation
            confirmation_event = asyncio.Event()
            
            # Add a callback for when user confirms/cancels
            async def on_response(confirmed: bool):
                confirm_view.value = confirmed
                confirmation_event.set()
                
            confirm_view.confirm.callback = lambda i: on_response(True)
            confirm_view.cancel.callback = lambda i: on_response(False)
            
            # Wait for either confirmation or timeout
            try:
                done, pending = await asyncio.wait(
                    [confirmation_event.wait(), confirm_view.wait()],
                    timeout=30,
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel any pending tasks
                for task in pending:
                    task.cancel()
                    
                if not done:  # Timeout occurred
                    self.logger.debug(f"Purchase confirmation timed out for {item_name}")
                    await confirm_view.cleanup()
                    return
                    
            except asyncio.TimeoutError:
                self.logger.debug(f"Purchase confirmation timed out for {item_name}")
                await confirm_view.cleanup()
                return
                
            if confirm_view.value:  # User confirmed purchase
                if item_name in self.cog.data["bait"]:
                    success, msg = await self.cog._handle_bait_purchase(
                        self.ctx.author,
                        item_name,
                        quantity,
                        self.user_data
                    )
                else:
                    success, msg = await self.cog._handle_rod_purchase(
                        self.ctx.author,
                        item_name,
                        self.user_data
                    )
    
                if success:
                    # Refresh user data immediately
                    user_data_result = await self.cog.config_manager.get_user_data(self.ctx.author.id)
                    if user_data_result.success:
                        self.user_data = user_data_result.data
                        await self.cog.config_manager.refresh_cache(self.ctx.author.id)
                        
                        fresh_data = await self.cog.config_manager.get_user_data(self.ctx.author.id)
                        if fresh_data.success:
                            self.user_data = fresh_data.data
                            
                            # Update parent menu view if it exists
                            if hasattr(self, 'parent_view'):
                                from .menu import FishingMenuView
                                if isinstance(self.parent_view, FishingMenuView):
                                    self.parent_view.user_data = fresh_data.data
                                    await self.parent_view.initialize_view()
                                    menu_embed = await self.parent_view.generate_embed()
                                    await self.parent_view.message.edit(
                                        embed=menu_embed,
                                        view=self.parent_view
                                    )
                            
                            # Update current view
                            await self.initialize_view()
                            await self.update_view()
                
                # Send feedback using followup since we can't reuse the original interaction
                if interaction.response.is_done():
                    feedback_msg = await interaction.followup.send(
                        msg,
                        ephemeral=True,
                        wait=True
                    )
                    # Schedule deletion after 2 seconds
                    self.cog.bot.loop.create_task(self.delete_after_delay(feedback_msg))
                else:
                    await interaction.response.send_message(
                        msg,
                        ephemeral=True,
                        delete_after=2
                    )
                
            else:  # User cancelled
                if interaction.response.is_done():
                    cancel_msg = await interaction.followup.send(
                        "Purchase cancelled.",
                        ephemeral=True,
                        wait=True
                    )
                    self.cog.bot.loop.create_task(self.delete_after_delay(cancel_msg))
                else:
                    await interaction.response.send_message(
                        "Purchase cancelled.",
                        ephemeral=True,
                        delete_after=2
                    )
            
            # Cleanup the confirmation view
            await confirm_view.cleanup()
                
        except Exception as e:
            self.logger.error(f"Error in handle_purchase: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while processing your purchase. Please try again.",
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
