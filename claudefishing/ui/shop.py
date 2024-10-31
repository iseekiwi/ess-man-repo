from typing import Dict, Optional
import discord
import logging
from discord.ui import Button, Select
from redbot.core import bank
from .base import BaseView

logger = logging.getLogger("red.fishing")

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

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.ctx.author.id:
            logger.debug(f"User {interaction.user.id} is authorized for interaction.")
            return True
        logger.warning(f"Unauthorized interaction attempt by user {interaction.user.id}")
        return False

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        logger.debug(f"Confirm button pressed by user {interaction.user.id} for {self.item_name}.")
        
        try:
            # Step 1: Check bank and config readiness
            try:
                if not await bank.is_global():
                    raise ValueError("Bank is not configured globally")
                logger.debug("Bank system ready and global.")
            except Exception as e:
                logger.error(f"Configuration error: {e}")
                await interaction.response.send_message("Configuration error. Please contact an admin.", ephemeral=True)
                return

            # Verify the user can afford the purchase
            if not await bank.can_spend(self.ctx.author, self.total_cost):
                currency_name = await bank.get_currency_name(self.ctx.guild)
                await interaction.response.send_message(
                    f"You don't have enough {currency_name} for this purchase!", 
                    ephemeral=True
                )
                return

            # Set the confirmation value and stop the view
            self.value = True
            self.stop()
            
            # Defer the response to prevent interaction timeout
            await interaction.response.defer()

        except Exception as e:
            logger.error(f"Error in purchase confirmation: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred during purchase confirmation. Please try again.",
                ephemeral=True
            )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        logger.debug(f"Cancel button pressed by user {interaction.user.id} for {self.item_name}")
        self.value = False
        self.stop()
        await interaction.response.send_message("Purchase cancelled.", ephemeral=True)

    async def on_timeout(self):
        logger.info(f"Purchase view timed out for {self.item_name}")
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)

class ShopView(BaseView):
    def __init__(self, cog, ctx, user_data: Dict):
        super().__init__(cog, ctx)
        logger.debug(f"Initializing ShopView for user {ctx.author.name}")
        self.user_data = user_data
        self.current_page = "main"
        self.selected_quantity = 1

    async def setup(self):
        """Async setup method to initialize the view"""
        try:
            logger.debug(f"Setting up ShopView for user {self.ctx.author.name}")
            
            # Verify user data
            if not self.user_data:
                logger.error(f"User data is empty for {self.ctx.author.name}")
                raise ValueError("User data is missing")
                
            # Verify cog data is accessible
            if not hasattr(self.cog, 'data'):
                logger.error("Cog data not accessible")
                raise ValueError("Cog data not accessible")
                
            # Initialize bait stock if needed
            if not hasattr(self.cog, '_bait_stock'):
                logger.debug("Initializing bait stock")
                self.cog._bait_stock = {
                    bait: data["daily_stock"] 
                    for bait, data in self.cog.data["bait"].items()
                }
            
            await self.initialize_view()
            logger.debug("ShopView setup completed successfully")
            return self
            
        except Exception as e:
            logger.error(f"Error in ShopView setup: {str(e)}", exc_info=True)
            raise

    async def initialize_view(self):
        """Initialize the view based on current page"""
        try:
            logger.debug(f"Initializing view for page: {self.current_page}")
            self.clear_items()
            
            if self.current_page == "main":
                logger.debug("Setting up main page buttons")
                bait_button = discord.ui.Button(
                    label="Buy Bait",
                    style=discord.ButtonStyle.blurple,
                    custom_id="bait"
                )
                bait_button.callback = self.handle_button
                self.add_item(bait_button)

                rod_button = discord.ui.Button(
                    label="Buy Rods",
                    style=discord.ButtonStyle.blurple,
                    custom_id="rods"
                )
                rod_button.callback = self.handle_button
                self.add_item(rod_button)
                
            else:
                logger.debug("Setting up back button")
                back_button = discord.ui.Button(
                    label="Back",
                    style=discord.ButtonStyle.grey,
                    custom_id="back"
                )
                back_button.callback = self.handle_button
                self.add_item(back_button)
                
                if self.current_page == "bait":
                    logger.debug("Setting up bait page")
                    quantity_select = QuantitySelect()
                    quantity_select.callback = self.handle_select
                    self.add_item(quantity_select)

                    for bait_name, bait_data in self.cog.data["bait"].items():
                        stock = self.cog._bait_stock.get(bait_name, 0)
                        logger.debug(f"Bait {bait_name} stock: {stock}")
                        if stock > 0:
                            purchase_button = discord.ui.Button(
                                label=f"Buy {bait_name}",
                                style=discord.ButtonStyle.green,
                                custom_id=f"buy_{bait_name}"
                            )
                            purchase_button.callback = self.handle_purchase
                            self.add_item(purchase_button)

                elif self.current_page == "rods":
                    logger.debug("Setting up rods page")
                    for rod_name, rod_data in self.cog.data["rods"].items():
                        if rod_name == "Basic Rod":
                            continue
                            
                        if rod_name in self.user_data.get("purchased_rods", {}):
                            logger.debug(f"Rod {rod_name} already owned")
                            continue

                        requirements = rod_data.get("requirements", {})
                        level_req = requirements.get("level", 1)
                        fish_req = requirements.get("fish_caught", 0)
                        
                        user_level = self.user_data.get("level", 1)
                        user_fish = self.user_data.get("fish_caught", 0)
                        
                        logger.debug(f"Checking requirements for {rod_name}: "
                                   f"Level {user_level}/{level_req}, "
                                   f"Fish {user_fish}/{fish_req}")
                        
                        if user_level >= level_req and user_fish >= fish_req:
                            purchase_button = discord.ui.Button(
                                label=f"Buy {rod_name}",
                                style=discord.ButtonStyle.green,
                                custom_id=f"buy_{rod_name}"
                            )
                            purchase_button.callback = self.handle_purchase
                            self.add_item(purchase_button)

            logger.debug("View initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Error in initialize_view: {str(e)}", exc_info=True)
            raise

    async def handle_purchase(self, interaction: discord.Interaction):
        """Handle purchase button interactions"""
        try:
            custom_id = interaction.data["custom_id"]
            item_name = custom_id.replace("buy_", "")
            
            # Determine item type and cost
            if item_name in self.cog.data["bait"]:
                cost = self.cog.data["bait"][item_name]["cost"]
                quantity = self.selected_quantity
                stock = self.cog._bait_stock.get(item_name, 0)
                
                # Check stock availability
                if stock < quantity:
                    await interaction.response.send_message(
                        f"Not enough {item_name} in stock! Available: {stock}",
                        ephemeral=True
                    )
                    return
            else:  # Rod purchase
                cost = self.cog.data["rods"][item_name]["cost"]
                quantity = 1
            
            # Create confirmation view
            confirm_view = PurchaseConfirmView(
                self.cog,
                self.ctx,
                item_name,
                quantity,
                cost
            )

            # Send confirmation message
            await interaction.response.send_message(
                f"Confirm purchase of {quantity}x {item_name} for {cost * quantity} coins?",
                view=confirm_view,
                ephemeral=True
            )
            
            # Wait for confirmation
            await confirm_view.wait()
            
            if confirm_view.value:
                # Process the purchase based on item type
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
                    # Refresh user data and view after successful purchase
                    self.user_data = await self.cog.config.user(self.ctx.author).all()
                    self.initialize_view()
                    await self.update_view()
                
                await interaction.followup.send(msg, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in handle_purchase: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while processing your purchase. Please try again.",
                ephemeral=True
            )

    async def handle_button(self, interaction: discord.Interaction):
        """Handle navigation button interactions"""
        try:
            custom_id = interaction.data["custom_id"]
            
            if custom_id == "bait":
                self.current_page = "bait"
            elif custom_id == "rods":
                self.current_page = "rods"
            elif custom_id == "back":
                self.current_page = "main"
                self.selected_quantity = 1
            
            self.initialize_view()
            await interaction.response.defer()
            await self.update_view()
            
        except Exception as e:
            logger.error(f"Error in handle_button: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while navigating the shop. Please try again.",
                ephemeral=True
            )
    
    async def handle_select(self, interaction: discord.Interaction):
        """Handle quantity selection"""
        try:
            self.selected_quantity = int(interaction.data["values"][0])
            await interaction.response.defer()
            await self.update_view()
        except Exception as e:
            logger.error(f"Error in handle_select: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while selecting quantity. Please try again.",
                ephemeral=True
            )

    async def update_view(self):
        """Update the message with current embed and view"""
        embed = await self.generate_embed()
        await self.message.edit(embed=embed, view=self)
