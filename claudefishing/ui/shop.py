from typing import Dict, Optional
import discord
from discord.ui import Button, Select, View
from .base import BaseView, ConfirmView

class QuantitySelect(Select):
    def __init__(self, max_quantity: int = 10):
        options = [
            discord.SelectOption(label=str(i), value=str(i)) 
            for i in [1, 5, 10, 25, 50, 100][:max_quantity]
        ]
        super().__init__(
            placeholder="Select quantity...",
            options=options,
            custom_id="quantity_select"
        )

class ShopView(BaseView):
    def __init__(self, cog, ctx, user_data: Dict):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.current_page = "main"  # main, bait, rods
        self.selected_quantity = 1
        self.current_balance = 0  # Will be updated when view is created
        
        self.initialize_buttons()

    def initialize_buttons(self):
        """Initialize the buttons based on current page"""
        self.clear_items()
        
        if self.current_page == "main":
            self.add_item(Button(
                label="Buy Bait",
                style=discord.ButtonStyle.blurple,
                custom_id="view_bait"
            ))
            self.add_item(Button(
                label="Buy Rods",
                style=discord.ButtonStyle.blurple,
                custom_id="view_rods"
            ))
        else:
            self.add_item(Button(
                label="Back",
                style=discord.ButtonStyle.grey,
                custom_id="back"
            ))
            
            if self.current_page == "bait":
                quantity_select = QuantitySelect()
                quantity_select.callback = self.quantity_callback
                self.add_item(quantity_select)

    async def generate_embed(self) -> discord.Embed:
        """Generate the appropriate embed based on current page"""
        embed = discord.Embed(color=discord.Color.green())
        
        # Get current balance
        try:
            self.current_balance = await self.cog.bot.get_cog("Bank").get_balance(self.ctx.author)
        except Exception:
            self.current_balance = 0

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
            for bait_name, bait_data in self.cog.BAIT_TYPES.items():
                stock = self.cog._bait_stock.get(bait_name, 0)
                if stock <= 0:
                    status = "❌ Out of stock!"
                else:
                    status = f"📦 Stock: {stock}"
                
                bait_list += (
                    f"**{bait_name}** - {bait_data['cost']} coins\n"
                    f"{bait_data['description']}\n"
                    f"{status}\n\n"
                )
            embed.description = bait_list

        elif self.current_page == "rods":
            embed.title = "🎣 Rod Shop"
            rod_list = ""
            for rod_name, rod_data in self.cog.ROD_TYPES.items():
                if rod_name == "Basic Rod":
                    continue
                
                owned = rod_name in self.user_data.get("purchased_rods", {})
                status = "✅ Owned" if owned else f"💰 Cost: {rod_data['cost']} coins"
                
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

        embed.set_footer(text=f"Your balance: {self.current_balance} coins")
        return embed

    async def update_view(self):
        """Update the message with current embed and view"""
        embed = await self.generate_embed()
        await self.message.edit(embed=embed, view=self)

    async def quantity_callback(self, interaction: discord.Interaction):
        """Handle quantity selection"""
        self.selected_quantity = int(interaction.data["values"][0])
        await interaction.response.defer()

    # Button callbacks
    @discord.ui.button(label="Buy Bait", custom_id="view_bait", style=discord.ButtonStyle.blurple)
    async def view_bait(self, interaction: discord.Interaction, button: Button):
        self.current_page = "bait"
        self.initialize_buttons()
        await interaction.response.defer()
        await self.update_view()

    @discord.ui.button(label="Buy Rods", custom_id="view_rods", style=discord.ButtonStyle.blurple)
    async def view_rods(self, interaction: discord.Interaction, button: Button):
        self.current_page = "rods"
        self.initialize_buttons()
        await interaction.response.defer()
        await self.update_view()

    @discord.ui.button(label="Back", custom_id="back", style=discord.ButtonStyle.grey)
    async def back_to_main(self, interaction: discord.Interaction, button: Button):
        self.current_page = "main"
        self.selected_quantity = 1
        self.initialize_buttons()
        await interaction.response.defer()
        await self.update_view()

class BaitPurchaseView(BaseView):
    def __init__(self, cog, ctx, bait_name: str, quantity: int, cost: int):
        super().__init__(cog, ctx, timeout=30)
        self.bait_name = bait_name
        self.quantity = quantity
        self.total_cost = cost * quantity
        
    async def generate_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Confirm Purchase",
            description=(
                f"Are you sure you want to buy {self.quantity}x {self.bait_name} "
                f"for {self.total_cost} coins?"
            ),
            color=discord.Color.green()
        )
        return embed

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        try:
            # Check balance
            if not await self.cog._can_afford(self.ctx.author, self.total_cost):
                await interaction.response.send_message(
                    "You don't have enough coins for this purchase!",
                    ephemeral=True
                )
                return

            # Check stock
            if self.cog._bait_stock[self.bait_name] < self.quantity:
                await interaction.response.send_message(
                    "Not enough stock available!",
                    ephemeral=True
                )
                return

            # Process purchase
            async with self.cog.config.user(self.ctx.author).bait() as user_bait:
                user_bait[self.bait_name] = user_bait.get(self.bait_name, 0) + self.quantity

            # Update stock
            self.cog._bait_stock[self.bait_name] -= self.quantity

            # Withdraw coins
            await self.cog.bot.get_cog("Bank").withdraw_credits(self.ctx.author, self.total_cost)

            await interaction.response.send_message(
                f"Successfully purchased {self.quantity}x {self.bait_name}!",
                ephemeral=True
            )
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
        self.stop()
