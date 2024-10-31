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
    """View for the fishing shop interface"""
    
    def __init__(self, cog, ctx, user_data: Dict):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.current_page = "main"
        self.selected_quantity = 1
        self.current_balance = 0
        self.logger = logging.getLogger('fishing.shop')
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
                
            # Initialize bait stock if needed
            if not hasattr(self.cog, '_bait_stock'):
                self.logger.debug("Initializing bait stock")
                self.cog._bait_stock = {
                    bait: data["daily_stock"] 
                    for bait, data in self.cog.data["bait"].items()
                }
            
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
                self.logger.debug("Setting up back button")
                back_button = discord.ui.Button(
                    label="Back",
                    style=discord.ButtonStyle.grey,
                    custom_id="back"
                )
                back_button.callback = self.handle_button
                self.add_item(back_button)
                
                if self.current_page == "bait":
                    self.logger.debug("Setting up bait page")
                    quantity_select = QuantitySelect()
                    quantity_select.callback = self.handle_select
                    self.add_item(quantity_select)

                    for bait_name, bait_data in self.cog.data["bait"].items():
                        stock = self.cog._bait_stock.get(bait_name, 0)
                        self.logger.debug(f"Bait {bait_name} stock: {stock}")
                        if stock > 0:
                            purchase_button = discord.ui.Button(
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
                            purchase_button = discord.ui.Button(
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
                self.logger.debug(f"User balance: {self.current_balance} {currency_name}")
            except Exception as e:
                self.logger.error(f"Error getting balance: {e}")
                self.current_balance = 0
                currency_name = "coins"

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
                    stock = self.cog._bait_stock.get(bait_name, 0)
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
        """Handle navigation button interactions"""
        try:
            self.logger.debug(f"Handling button interaction: {interaction.data['custom_id']}")
            custom_id = interaction.data["custom_id"]
            
            if custom_id == "bait":
                self.current_page = "bait"
            elif custom_id == "rods":
                self.current_page = "rods"
            elif custom_id == "back":
                self.current_page = "main"
                self.selected_quantity = 1
            
            await self.initialize_view()
            await interaction.response.defer()
            await self.update_view()
            
        except Exception as e:
            self.logger.error(f"Error in handle_button: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while navigating the shop. Please try again.",
                ephemeral=True
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
            await interaction.response.send_message(
                "An error occurred while selecting quantity. Please try again.",
                ephemeral=True
            )

    async def handle_purchase(self, interaction: discord.Interaction):
        """Handle purchase button interactions"""
        try:
            self.logger.debug(f"Starting purchase process for interaction: {interaction.data['custom_id']}")
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
            
            total_cost = cost * quantity
            
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
                f"Confirm purchase of {quantity}x {item_name} for {total_cost} coins?",
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
                    await self.initialize_view()
                    await self.update_view()
                
                await interaction.followup.send(msg, ephemeral=True)
            
        except Exception as e:
            self.logger.error(f"Error in handle_purchase: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while processing your purchase. Please try again.",
                ephemeral=True
            )

    async def update_view(self):
        """Update the message with current embed and view"""
        try:
            self.logger.debug("Updating view")
            embed = await self.generate_embed()
            await self.message.edit(embed=embed, view=self)
            self.logger.debug("View updated successfully")
        except Exception as e:
            self.logger.error(f"Error updating view: {e}", exc_info=True)
            raise