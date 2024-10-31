from typing import Dict, Optional
import discord
from discord.ui import Button, Select
from redbot.core import bank
from .base import BaseView

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
        super().__init__(cog, ctx, timeout=30)
        self.item_name = item_name
        self.quantity = quantity
        self.total_cost = cost_per_item * quantity
        self.value = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.ctx.author.id

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        try:
            currency_name = await bank.get_currency_name(self.ctx.guild)
            
            # Check if user can afford
            if not await bank.can_spend(self.ctx.author, self.total_cost):
                await interaction.response.send_message(
                    f"You don't have enough {currency_name} for this purchase!",
                    ephemeral=True
                )
                return

            # Check stock for bait
            if self.item_name in self.cog.BAIT_TYPES:
                if self.cog._bait_stock[self.item_name] < self.quantity:
                    await interaction.response.send_message(
                        "Not enough stock available!",
                        ephemeral=True
                    )
                    return
                
                # Process bait purchase
                async with self.cog.config.user(self.ctx.author).bait() as user_bait:
                    user_bait[self.item_name] = user_bait.get(self.item_name, 0) + self.quantity
                self.cog._bait_stock[self.item_name] -= self.quantity

            # Process rod purchase
            elif self.item_name in self.cog.ROD_TYPES:
                if self.item_name in (await self.cog.config.user(self.ctx.author).purchased_rods()):
                    await interaction.response.send_message(
                        "You already own this rod!",
                        ephemeral=True
                    )
                    return
                
                # Check requirements
                requirements = self.cog.ROD_TYPES[self.item_name].get("requirements")
                if requirements:
                    user_data = await self.cog.config.user(self.ctx.author).all()
                    if (user_data.get("level", 1) < requirements["level"] or 
                        user_data.get("fish_caught", 0) < requirements["fish_caught"]):
                        await interaction.response.send_message(
                            "You don't meet the requirements for this rod!",
                            ephemeral=True
                        )
                        return

                # Add rod to user's inventory
                async with self.cog.config.user(self.ctx.author).purchased_rods() as rods:
                    rods[self.item_name] = True

            # Withdraw money
            await bank.withdraw_credits(self.ctx.author, self.total_cost)
            
            await interaction.response.send_message(
                f"Successfully purchased {self.quantity}x {self.item_name} for {self.total_cost} {currency_name}!",
                ephemeral=True
            )
            self.value = True
            self.stop()

        except Exception as e:
            await interaction.response.send_message(
                "An error occurred while processing your purchase.",
                ephemeral=True
            )
            self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Purchase cancelled.", ephemeral=True)
        self.value = False
        self.stop()

class ShopView(BaseView):
    def __init__(self, cog, ctx, user_data: Dict):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.current_page = "main"
        self.selected_quantity = 1
        self.current_selected_item = None
        self.initialize_view()

    def initialize_view(self):
        """Initialize the view based on current page"""
        self.clear_items()
        
        if self.current_page == "main":
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
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.grey,
                custom_id="back"
            )
            back_button.callback = self.handle_button
            self.add_item(back_button)
            
            if self.current_page == "bait":
                quantity_select = QuantitySelect()
                quantity_select.callback = self.handle_select
                self.add_item(quantity_select)

                # Add purchase buttons for each bait type
                for bait_name, bait_data in self.cog.data["bait"].items():
                    if self.cog._bait_stock.get(bait_name, 0) > 0:
                        purchase_button = discord.ui.Button(
                            label=f"Buy {bait_name}",
                            style=discord.ButtonStyle.green,
                            custom_id=f"buy_{bait_name}"
                        )
                        purchase_button.callback = self.handle_purchase
                        self.add_item(purchase_button)

            elif self.current_page == "rods":
                # Add purchase buttons for rods
                for rod_name, rod_data in self.cog.data["rods"].items():
                    if rod_name != "Basic Rod" and rod_name not in self.user_data.get("purchased_rods", {}):
                        purchase_button = discord.ui.Button(
                            label=f"Buy {rod_name}",
                            style=discord.ButtonStyle.green,
                            custom_id=f"buy_{rod_name}"
                        )
                        purchase_button.callback = self.handle_purchase
                        self.add_item(purchase_button)

    async def generate_embed(self) -> discord.Embed:
        """Generate the appropriate embed based on current page"""
        embed = discord.Embed(color=discord.Color.green())
        
        # Get current balance using RedBot's bank system
        try:
            self.current_balance = await bank.get_balance(self.ctx.author)
            currency_name = await bank.get_currency_name(self.ctx.guild)
        except Exception as e:
            self.current_balance = 0
            currency_name = "coins"

        if self.current_page == "main":
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
            embed.title = "🪱 Bait Shop"
            bait_list = ""
            for bait_name, bait_data in self.cog.data["bait"].items():
                stock = self.cog._bait_stock.get(bait_name, 0)
                if stock <= 0:
                    status = "❌ Out of stock!"
                else:
                    status = f"📦 Stock: {stock}"
                
                bait_list += (
                    f"**{bait_name}** - {bait_data['cost']} {currency_name}\n"
                    f"{bait_data['description']}\n"
                    f"{status}\n\n"
                )
            embed.description = bait_list
            if self.selected_quantity > 1:
                embed.set_footer(text=f"Your balance: {self.current_balance} {currency_name} | Quantity: {self.selected_quantity}")
            else:
                embed.set_footer(text=f"Your balance: {self.current_balance} {currency_name}")

        elif self.current_page == "rods":
            embed.title = "🎣 Rod Shop"
            rod_list = ""
            for rod_name, rod_data in self.cog.data["rods"].items():
                if rod_name == "Basic Rod":
                    continue
                
                owned = rod_name in self.user_data.get("purchased_rods", {})
                status = "✅ Owned" if owned else f"💰 Cost: {rod_data['cost']} {currency_name}"
                
                requirements = rod_data.get("requirements")
                if requirements:
                    req_text = f"\nRequires: Level {requirements['level']}, {requirements['fish_caught']} fish caught"
                else:
                    req_text = ""
                
                rod_list += (
                    f"**{rod_name}**\n"
                    f"{rod_data['description']}\n"
                    f"{status}{req_text}\n\n"
                )
            embed.description = rod_list
            embed.set_footer(text=f"Your balance: {self.current_balance} {currency_name}")

        return embed

    async def handle_purchase(self, interaction: discord.Interaction):
        """Handle purchase button interactions"""
        custom_id = interaction.data["custom_id"]
        item_name = custom_id.replace("buy_", "")
        
        if item_name in self.cog.data["bait"]:
            cost = self.cog.data["bait"][item_name]["cost"]
            quantity = self.selected_quantity
            success, msg = await self.cog._handle_bait_purchase(self.ctx.author, item_name, quantity, self.user_data)
        else:  # Rod purchase
            cost = self.cog.data["rods"][item_name]["cost"]
            quantity = 1  # Can only buy one rod at a time
            success, msg = await self.cog._handle_rod_purchase(self.ctx.author, item_name, self.user_data)
            
        if success:
            # Refresh the shop view after successful purchase
            self.user_data = await self.cog.config.user(self.ctx.author).all()
            self.initialize_view()
            await self.update_view()
        
        await interaction.response.send_message(msg, ephemeral=True)

    async def handle_select(self, interaction: discord.Interaction):
        """Handle quantity selection"""
        self.selected_quantity = int(interaction.data["values"][0])
        await interaction.response.defer()
        await self.update_view()

    async def handle_purchase(self, interaction: discord.Interaction):
        """Handle purchase button interactions"""
        custom_id = interaction.data["custom_id"]
        item_name = custom_id.replace("buy_", "")
        
        if item_name in self.cog.data["bait"]:
            cost = self.cog.data["bait"][item_name]["cost"]
            quantity = self.selected_quantity
        else:  # Rod purchase
            cost = self.cog.data["rods"][item_name]["cost"]
            quantity = 1  # Can only buy one rod at a time
            
        confirm_view = PurchaseConfirmView(self.cog, self.ctx, item_name, quantity, cost)
        await interaction.response.send_message(
            f"Confirm purchase of {quantity}x {item_name}?",
            view=confirm_view,
            ephemeral=True
        )
        
        await confirm_view.wait()
        if confirm_view.value:
            # Refresh the shop view after successful purchase
            self.user_data = await self.cog.config.user(self.ctx.author).all()
            self.initialize_view()
            await self.update_view()

    async def update_view(self):
        """Update the message with current embed and view"""
        embed = await self.generate_embed()
        await self.message.edit(embed=embed, view=self)
