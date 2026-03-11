# ui/shop.py

import discord
import logging
import asyncio
import math
from typing import Dict, Optional, List
from discord.ui import Button, Select
from redbot.core import bank
from .base import BaseView
from ..utils.logging_config import get_logger
from ..data.fishing_data import GEAR_TYPES, MATERIAL_TYPES
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .menu import FishingMenuView

logger = get_logger('shop')

GEAR_ITEMS_PER_PAGE = 5


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

            cost = self.shop_view.cog.data["bait"][self.bait_name]["cost"]
            total_cost = cost * quantity

            if not await self.shop_view.cog._can_afford(interaction.user, total_cost):
                await interaction.response.send_message(
                    f"❌ You don't have enough coins! This purchase costs {total_cost} coins.",
                    ephemeral=True,
                    delete_after=2
                )
                return

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
                    await self.shop_view.cog.config_manager.invalidate_cache(f"user_{interaction.user.id}")
                    fresh_data = await self.shop_view.cog.config_manager.get_user_data(interaction.user.id)
                    if fresh_data.success:
                        self.shop_view.user_data = fresh_data.data

                        if hasattr(self.shop_view, 'parent_menu_view'):
                            self.shop_view.parent_menu_view.user_data = fresh_data.data

                        await self.shop_view.initialize_view()
                        await self.shop_view.update_view()

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
        self.success_message = None

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
            self.value = True
            self.stop()

            try:
                if self.message:
                    await self.message.delete()
            except discord.NotFound:
                pass
            except Exception as e:
                self.logger.error(f"Error deleting confirmation message: {e}", exc_info=True)

            await interaction.response.defer(ephemeral=True)

            confirmation_msg = await interaction.followup.send(
                "Purchase confirmed! Processing...",
                ephemeral=True
            )

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

            try:
                if self.message:
                    await self.message.delete()
            except discord.NotFound:
                pass
            except Exception as e:
                self.logger.error(f"Error deleting cancellation message: {e}", exc_info=True)

            await interaction.response.defer(ephemeral=True)

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

    async def on_timeout(self):
        """Handle view timeout."""
        self.logger.info(f"Purchase view timed out for {self.item_name}")
        try:
            if self.message:
                await self.message.delete()
        except discord.NotFound:
            pass
        except Exception as e:
            self.logger.error(f"Error handling timeout cleanup: {e}", exc_info=True)


class ShopView(BaseView):
    """View for the fishing shop interface"""

    # Map page IDs to GEAR_TYPES category keys
    CATEGORY_PAGE_MAP = {
        "gear": "Inventory",
        "outfits": "Outfits",
        "tools": "Tools",
    }
    CATEGORY_ICONS = {
        "Inventory": "🎒",
        "Outfits": "🧥",
        "Tools": "🔧",
    }

    def __init__(self, cog, ctx, user_data: Dict):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.current_page = "main"
        self.current_balance = 0
        self.gear_page = 0
        self.gear_category = "Inventory"  # Active GEAR_TYPES category
        self.logger = get_logger('shop.view')
        self.logger.debug(f"Initializing ShopView for user {ctx.author.name}")

    async def setup(self):
        """Async setup method to initialize the view"""
        try:
            self.logger.debug(f"Setting up ShopView for user {self.ctx.author.name}")

            if not self.user_data:
                self.logger.error(f"User data is empty for {self.ctx.author.name}")
                raise ValueError("User data is missing")

            if not hasattr(self.cog, 'data'):
                self.logger.error("Cog data not accessible")
                raise ValueError("Cog data not accessible")

            await self.initialize_view()
            self.logger.debug("ShopView setup completed successfully")
            return self

        except Exception as e:
            self.logger.error(f"Error in ShopView setup: {str(e)}", exc_info=True)
            raise

    def _get_category_items(self) -> List[tuple]:
        """Get items from the active gear category as (gear_name, gear_data, category) tuples."""
        items = []
        category_items = GEAR_TYPES.get(self.gear_category, {})
        for gear_name, gear_data in category_items.items():
            items.append((gear_name, gear_data, self.gear_category))
        return items

    def _get_category_page_count(self) -> int:
        """Get total number of pages for the active gear category."""
        total_items = len(self._get_category_items())
        return max(1, math.ceil(total_items / GEAR_ITEMS_PER_PAGE))

    async def initialize_view(self):
        """Initialize the view based on current page"""
        try:
            self.logger.debug(f"Initializing view for page: {self.current_page}")
            self.clear_items()

            if self.current_page == "main":
                self.logger.debug("Setting up main page buttons")
                for label, custom_id in [
                    ("Buy Bait", "bait"),
                    ("Buy Rods", "rods"),
                    ("Buy Storage", "gear"),
                    ("Buy Outfits", "outfits"),
                    ("Buy Tools", "tools"),
                ]:
                    btn = Button(label=label, style=discord.ButtonStyle.blurple, custom_id=custom_id)
                    btn.callback = self.handle_button
                    self.add_item(btn)

                back_button = Button(label="Back to Menu", style=discord.ButtonStyle.grey, custom_id="menu")
                back_button.callback = self.handle_button
                self.add_item(back_button)

            else:
                # Back button for all sub-pages
                back_button = Button(label="Back", style=discord.ButtonStyle.grey, custom_id="back")
                back_button.callback = self.handle_button
                self.add_item(back_button)

                if self.current_page == "bait":
                    self.logger.debug("Setting up bait page")
                    stock_result = await self.cog.config_manager.get_global_setting("bait_stock")
                    bait_stock = stock_result.data if stock_result.success else {}

                    user_level = self.user_data.get("level", 1)
                    options = []
                    for bait_name, bait_data in self.cog.data["bait"].items():
                        stock = bait_stock.get(bait_name, 0)
                        requirements = bait_data.get("requirements", {})
                        level_req = requirements.get("level", 1) if requirements else 1

                        if stock > 0 and user_level >= level_req:
                            desc = f"{bait_data['cost']} coins | +{bait_data['catch_bonus']*100:.0f}% catch | Stock: {stock}"
                            options.append(discord.SelectOption(
                                label=bait_name,
                                value=bait_name,
                                description=desc[:100],
                            ))

                    if options:
                        bait_select = Select(
                            placeholder="Select bait to purchase...",
                            options=options,
                            custom_id="bait_select"
                        )
                        bait_select.callback = self.handle_bait_select
                        self.add_item(bait_select)

                elif self.current_page == "rods":
                    self.logger.debug("Setting up rods page")
                    user_level = self.user_data.get("level", 1)
                    user_fish = self.user_data.get("fish_caught", 0)
                    options = []

                    for rod_name, rod_data in self.cog.data["rods"].items():
                        if rod_name == "Basic Rod":
                            continue
                        if rod_name in self.user_data.get("purchased_rods", {}):
                            continue

                        requirements = rod_data.get("requirements", {})
                        level_req = requirements.get("level", 1)
                        fish_req = requirements.get("fish_caught", 0)

                        # Check sequential prerequisite
                        has_prereq, _ = self.cog.check_rod_prerequisite(self.user_data, rod_name)

                        if user_level >= level_req and user_fish >= fish_req and has_prereq:
                            desc = f"{rod_data['cost']} coins | +{rod_data['chance']*100:.0f}% catch bonus"
                            options.append(discord.SelectOption(
                                label=rod_name,
                                value=rod_name,
                                description=desc[:100],
                            ))

                    if options:
                        rod_select = Select(
                            placeholder="Select rod to purchase...",
                            options=options,
                            custom_id="rod_select"
                        )
                        rod_select.callback = self.handle_rod_select
                        self.add_item(rod_select)

                elif self.current_page == "gear":
                    self.logger.debug(f"Setting up gear page for category: {self.gear_category}")
                    user_level = self.user_data.get("level", 1)
                    purchased_gear = self.user_data.get("purchased_gear", [])

                    # Build select options for purchasable items in this category
                    cat_items = self._get_category_items()
                    start = self.gear_page * GEAR_ITEMS_PER_PAGE
                    end = start + GEAR_ITEMS_PER_PAGE
                    page_items = cat_items[start:end]

                    options = []
                    for gear_name, gear_data, category in page_items:
                        if gear_name in purchased_gear:
                            continue
                        requirements = gear_data.get("requirements", {})
                        level_req = requirements.get("level", 1) if requirements else 1
                        # Check sequential prerequisite
                        has_prereq, _ = self.cog.check_gear_prerequisite(self.user_data, gear_name)
                        if user_level >= level_req and has_prereq:
                            effects = gear_data.get("effect", {})
                            desc = f"{gear_data['cost']} coins"
                            if "inventory_capacity" in effects:
                                bonus = effects["inventory_capacity"] - 5
                                desc += f" | +{bonus} slots ({effects['inventory_capacity']} total)"
                            if gear_data.get("material_cost"):
                                mat_names = ", ".join(gear_data["material_cost"].keys())
                                desc += f" | Needs: {mat_names}"
                            options.append(discord.SelectOption(
                                label=gear_name,
                                value=gear_name,
                                description=desc[:100],
                            ))

                    if options:
                        icon = self.CATEGORY_ICONS.get(self.gear_category, "📦")
                        gear_select = Select(
                            placeholder=f"Select {self.gear_category.lower()} to purchase...",
                            options=options,
                            custom_id="gear_select"
                        )
                        gear_select.callback = self.handle_gear_select
                        self.add_item(gear_select)

                    # Pagination buttons
                    total_pages = self._get_category_page_count()
                    if total_pages > 1:
                        prev_btn = Button(
                            label="<",
                            style=discord.ButtonStyle.grey,
                            custom_id="gear_prev",
                            disabled=(self.gear_page == 0)
                        )
                        prev_btn.callback = self.handle_button
                        self.add_item(prev_btn)

                        page_btn = Button(
                            label=f"{self.gear_page + 1}/{total_pages}",
                            style=discord.ButtonStyle.grey,
                            custom_id="gear_page_indicator",
                            disabled=True
                        )
                        self.add_item(page_btn)

                        next_btn = Button(
                            label=">",
                            style=discord.ButtonStyle.grey,
                            custom_id="gear_next",
                            disabled=(self.gear_page >= total_pages - 1)
                        )
                        next_btn.callback = self.handle_button
                        self.add_item(next_btn)

            self.logger.debug("View initialization completed successfully")

        except Exception as e:
            self.logger.error(f"Error in initialize_view: {str(e)}", exc_info=True)
            raise

    async def generate_embed(self) -> discord.Embed:
        """Generate the appropriate embed based on current page"""
        try:
            self.logger.debug(f"Generating embed for page: {self.current_page}")
            embed = discord.Embed(color=discord.Color.green())

            try:
                self.current_balance = await bank.get_balance(self.ctx.author)
                currency_name = await bank.get_currency_name(self.ctx.guild)
                stock_result = await self.cog.config_manager.get_global_setting("bait_stock")
                current_stock = stock_result.data if stock_result.success else {}
            except Exception as e:
                self.logger.error(f"Error getting balance or stock: {e}")
                self.current_balance = 0
                currency_name = "coins"
                current_stock = {}

            if self.current_page == "main":
                embed.title = "🏪 Fishing Shop"
                embed.description = "Welcome! What would you like to buy?"
                embed.add_field(
                    name="Categories",
                    value=(
                        "🪱 **Bait** - Various baits for fishing\n"
                        "🎣 **Rods** - Better rods, better catches!\n"
                        "🎒 **Storage** - Inventory upgrades\n"
                        "🧥 **Outfits** - Wearable gear\n"
                        "🔧 **Tools** - Useful fishing tools"
                    ),
                    inline=False
                )

            elif self.current_page == "bait":
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

                    stats = f"📊 Catch Bonus: `+{bait_data['catch_bonus']*100:.0f}%`"
                    if bait_data.get("preferred_by"):
                        bonus = bait_data.get("preference_bonus", 1.0)
                        stats += f"\n⭐ Specialist: `{bonus}x` weight for {', '.join(bait_data['preferred_by'])}"

                    eff = bait_data.get("effectiveness", {})
                    if eff:
                        eff_parts = []
                        for loc, mult in eff.items():
                            if mult > 1.0:
                                eff_parts.append(f"{loc} `{mult}x`")
                            elif mult < 1.0:
                                eff_parts.append(f"~~{loc}~~ `{mult}x`")
                        if eff_parts:
                            stats += f"\n🗺️ {', '.join(eff_parts)}"

                    bait_entry = (
                        f"**{bait_name}** - {bait_data['cost']} {currency_name}\n"
                        f"{bait_data['description']}\n"
                        f"{stats}\n"
                        f"{status}\n"
                    )
                    bait_list.append(bait_entry)

                embed.description = "\n".join(bait_list) if bait_list else "No bait available!"

            elif self.current_page == "gear":
                purchased_gear = self.user_data.get("purchased_gear", [])
                user_level = self.user_data.get("level", 1)
                total_pages = self._get_category_page_count()

                icon = self.CATEGORY_ICONS.get(self.gear_category, "📦")
                # Use "Storage" as display name for "Inventory" category
                display_name = "Storage" if self.gear_category == "Inventory" else self.gear_category
                page_suffix = f" (Page {self.gear_page + 1}/{total_pages})" if total_pages > 1 else ""
                embed.title = f"{icon} {display_name} Shop{page_suffix}"

                # Get items for current page in this category
                cat_items = self._get_category_items()
                start = self.gear_page * GEAR_ITEMS_PER_PAGE
                end = start + GEAR_ITEMS_PER_PAGE
                page_items = cat_items[start:end]

                item_entries = []
                for gear_name, gear_data, category in page_items:
                    owned = gear_name in purchased_gear
                    requirements = gear_data.get("requirements", {})
                    level_req = requirements.get("level", 1) if requirements else 1
                    has_prereq, _ = self.cog.check_gear_prerequisite(self.user_data, gear_name)

                    if owned:
                        status = "✅ Owned"
                    elif level_req > user_level:
                        status = f"🔒 Requires Level {level_req}"
                    elif not has_prereq:
                        cat_keys = list(GEAR_TYPES[category].keys())
                        prev_item = cat_keys[cat_keys.index(gear_name) - 1]
                        status = f"🔒 Requires **{prev_item}**"
                    else:
                        status = f"💰 Cost: {gear_data['cost']} {currency_name}"

                    effects = gear_data.get("effect", {})
                    effect_text = ""
                    if "inventory_capacity" in effects:
                        bonus = effects["inventory_capacity"] - 5
                        effect_text = f"📊 +{bonus} slots ({effects['inventory_capacity']} total)"

                    # Material requirements display
                    mat_text = ""
                    mat_cost = gear_data.get("material_cost")
                    if mat_cost and not owned:
                        user_materials = self.user_data.get("materials", {})
                        mat_parts = []
                        for mat_name, qty in mat_cost.items():
                            owned_qty = user_materials.get(mat_name, 0)
                            check = "✅" if owned_qty >= qty else "❌"
                            mat_parts.append(f"{check} {mat_name} ({owned_qty}/{qty})")
                        mat_text = f"🧱 {', '.join(mat_parts)}"

                    entry_lines = [f"**{gear_name}**", gear_data['description']]
                    if effect_text:
                        entry_lines.append(effect_text)
                    if mat_text:
                        entry_lines.append(mat_text)
                    entry_lines.append(status)

                    item_entries.append("\n".join(entry_lines))

                if item_entries:
                    embed.description = "\n\n".join(item_entries)
                else:
                    embed.description = f"No {display_name.lower()} items available yet!"

            elif self.current_page == "rods":
                embed.title = "🎣 Rod Shop"
                rod_list = []
                user_level = self.user_data.get("level", 1)

                for rod_name, rod_data in self.cog.data["rods"].items():
                    if rod_name == "Basic Rod":
                        continue

                    owned = rod_name in self.user_data.get("purchased_rods", {})
                    requirements = rod_data.get("requirements")
                    level_req = requirements.get("level", 1) if requirements else 1
                    has_prereq, prereq_msg = self.cog.check_rod_prerequisite(self.user_data, rod_name)

                    if owned:
                        status = "✅ Owned"
                    elif level_req > user_level:
                        status = f"🔒 Requires Level {level_req}"
                    elif not has_prereq:
                        # Extract previous rod name from the message
                        rod_names = list(self.cog.data["rods"].keys())
                        prev_rod = rod_names[rod_names.index(rod_name) - 1]
                        status = f"🔒 Requires **{prev_rod}**"
                    else:
                        status = f"💰 *Cost*: {rod_data['cost']} {currency_name}"

                    req_text = ""
                    if requirements:
                        req_text = f"\n*Requires*: Level {requirements['level']}"

                    stats = f"📊 Catch Bonus: `+{rod_data['chance']*100:.0f}%`"

                    rod_entry = (
                        f"**{rod_name}**\n"
                        f"{rod_data['description']}\n"
                        f"{stats}\n"
                        f"{status}{req_text}\n"
                    )
                    rod_list.append(rod_entry)

                embed.description = "\n".join(rod_list) if rod_list else "No rods available!"

            embed.set_footer(text=f"Your balance: {self.current_balance} {currency_name}")
            return embed

        except Exception as e:
            self.logger.error(f"Error generating embed: {str(e)}", exc_info=True)
            raise

    async def handle_button(self, interaction: discord.Interaction):
        """Handle navigation button interactions"""
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

            if custom_id == "bait":
                self.current_page = "bait"
            elif custom_id == "rods":
                self.current_page = "rods"
            elif custom_id in self.CATEGORY_PAGE_MAP:
                self.current_page = "gear"
                self.gear_category = self.CATEGORY_PAGE_MAP[custom_id]
                self.gear_page = 0
            elif custom_id == "back":
                self.current_page = "main"
                self.gear_page = 0
            elif custom_id == "gear_prev":
                self.gear_page = max(0, self.gear_page - 1)
            elif custom_id == "gear_next":
                self.gear_page = min(self._get_category_page_count() - 1, self.gear_page + 1)

            await self.initialize_view()
            embed = await self.generate_embed()
            await interaction.response.edit_message(embed=embed, view=self)
            self.message = await interaction.original_response()

        except Exception as e:
            self.logger.error(f"Error in handle_button: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while navigating the shop. Please try again.",
                    ephemeral=True,
                    delete_after=2
                )

    async def handle_bait_select(self, interaction: discord.Interaction):
        """Handle bait dropdown selection — opens quantity modal."""
        try:
            bait_name = interaction.data["values"][0]
            modal = BaitQuantityModal(self, bait_name)
            await interaction.response.send_modal(modal)
        except Exception as e:
            self.logger.error(f"Error in handle_bait_select: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred. Please try again.",
                    ephemeral=True,
                    delete_after=2
                )

    async def handle_rod_select(self, interaction: discord.Interaction):
        """Handle rod dropdown selection — shows purchase confirmation."""
        try:
            rod_name = interaction.data["values"][0]
            rod_data = self.cog.data["rods"].get(rod_name)
            if not rod_data:
                await interaction.response.send_message("Rod not found!", ephemeral=True, delete_after=2)
                return

            # Check sequential prerequisite
            has_prereq, prereq_msg = self.cog.check_rod_prerequisite(self.user_data, rod_name)
            if not has_prereq:
                await interaction.response.send_message(prereq_msg, ephemeral=True, delete_after=5)
                return

            cost = rod_data["cost"]
            if not await self.cog._can_afford(self.ctx.author, cost):
                await interaction.response.send_message(
                    f"❌ You don't have enough coins! This costs {cost} coins.",
                    ephemeral=True,
                    delete_after=2
                )
                return

            confirm_view = PurchaseConfirmView(self.cog, self.ctx, rod_name, 1, cost)
            await interaction.response.send_message(
                f"Confirm purchase of **{rod_name}** for {cost} coins?",
                view=confirm_view,
                ephemeral=True
            )

            confirm_view.message = await interaction.original_response()
            await confirm_view.wait()

            if confirm_view.value:
                success, msg = await self.cog._handle_rod_purchase(
                    self.ctx.author,
                    rod_name,
                    self.user_data
                )

                if success:
                    await self.cog.config_manager.invalidate_cache(f"user_{self.ctx.author.id}")
                    fresh_data = await self.cog.config_manager.get_user_data(self.ctx.author.id)
                    if fresh_data.success:
                        self.user_data = fresh_data.data
                        if hasattr(self, 'parent_menu_view'):
                            self.parent_menu_view.user_data = fresh_data.data
                        await self.initialize_view()
                        await self.update_view()

                message = await interaction.followup.send(msg, ephemeral=True, wait=True)
                self.cog.bot.loop.create_task(self.delete_after_delay(message))

        except Exception as e:
            self.logger.error(f"Error in handle_rod_select: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred. Please try again.",
                    ephemeral=True,
                    delete_after=2
                )

    async def handle_gear_select(self, interaction: discord.Interaction):
        """Handle gear dropdown selection — shows purchase confirmation."""
        try:
            gear_name = interaction.data["values"][0]
            gear_data = self._get_gear_data(gear_name)
            if not gear_data:
                await interaction.response.send_message("Item not found!", ephemeral=True, delete_after=2)
                return

            # Check sequential prerequisite
            has_prereq, prereq_msg = self.cog.check_gear_prerequisite(self.user_data, gear_name)
            if not has_prereq:
                await interaction.response.send_message(prereq_msg, ephemeral=True, delete_after=5)
                return

            cost = gear_data["cost"]
            if not await self.cog._can_afford(self.ctx.author, cost):
                await interaction.response.send_message(
                    f"❌ You don't have enough coins! This costs {cost} coins.",
                    ephemeral=True,
                    delete_after=2
                )
                return

            # Check material requirements
            material_cost = gear_data.get("material_cost")
            if material_cost:
                has_mats, mat_msg = self.cog.check_material_cost(self.user_data, material_cost)
                if not has_mats:
                    await interaction.response.send_message(
                        f"❌ {mat_msg}",
                        ephemeral=True,
                        delete_after=5
                    )
                    return

            # Build confirmation message with material info
            confirm_text = f"Confirm purchase of **{gear_name}** for {cost} coins?"
            if material_cost:
                mat_parts = [f"{qty}x {mat_name}" for mat_name, qty in material_cost.items()]
                confirm_text += f"\n🧱 Materials consumed: {', '.join(mat_parts)}"

            confirm_view = PurchaseConfirmView(self.cog, self.ctx, gear_name, 1, cost)
            await interaction.response.send_message(
                confirm_text,
                view=confirm_view,
                ephemeral=True
            )

            confirm_view.message = await interaction.original_response()
            await confirm_view.wait()

            if confirm_view.value:
                success, msg = await self._handle_gear_purchase(interaction.user, gear_name, gear_data)

                if success:
                    await self.cog.config_manager.invalidate_cache(f"user_{interaction.user.id}")
                    fresh_data = await self.cog.config_manager.get_user_data(interaction.user.id)
                    if fresh_data.success:
                        self.user_data = fresh_data.data
                        if hasattr(self, 'parent_menu_view'):
                            self.parent_menu_view.user_data = fresh_data.data
                        await self.initialize_view()
                        await self.update_view()

                message = await interaction.followup.send(msg, ephemeral=True, wait=True)
                self.cog.bot.loop.create_task(self.delete_after_delay(message))

        except Exception as e:
            self.logger.error(f"Error in handle_gear_select: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred. Please try again.",
                    ephemeral=True,
                    delete_after=2
                )

    def _get_gear_data(self, item_name: str) -> Optional[Dict]:
        """Get gear data by item name across all categories"""
        for category, items in GEAR_TYPES.items():
            if item_name in items:
                return items[item_name]
        return None

    async def _handle_gear_purchase(self, user, gear_name: str, gear_data: Dict):
        """Process a gear purchase"""
        try:
            cost = gear_data["cost"]
            material_cost = gear_data.get("material_cost")

            # Consume materials first (if required)
            if material_cost:
                success, msg = await self.cog.consume_materials(user.id, material_cost)
                if not success:
                    return False, f"❌ {msg}"

            try:
                await bank.withdraw_credits(user, cost)
            except Exception as e:
                self.logger.error(f"Error withdrawing credits for gear: {e}")
                return False, f"❌ Failed to process payment: {e}"

            # Update user data: add gear + apply effects
            result = await self.cog.config_manager.get_user_data(user.id)
            if not result.success:
                return False, "❌ Failed to get user data."

            user_data = result.data
            purchased_gear = user_data.get("purchased_gear", [])
            purchased_gear.append(gear_name)

            updates = {"purchased_gear": purchased_gear}
            fields = ["purchased_gear"]

            effects = gear_data.get("effect", {})
            if "inventory_capacity" in effects:
                updates["inventory_capacity"] = effects["inventory_capacity"]
                fields.append("inventory_capacity")

            update_result = await self.cog.config_manager.update_user_data(
                user.id, updates, fields=fields
            )
            if not update_result.success:
                return False, "❌ Failed to save purchase."

            if "inventory_capacity" in effects:
                return True, f"✅ Purchased **{gear_name}**! Inventory capacity is now **{effects['inventory_capacity']}**."
            return True, f"✅ Purchased **{gear_name}**! {gear_data['description']}"

        except Exception as e:
            self.logger.error(f"Error handling gear purchase: {e}", exc_info=True)
            return False, f"❌ An error occurred: {e}"

    async def update_view(self):
        """Update the message with current embed and view"""
        try:
            self.logger.debug("Updating view")
            user_data_result = await self.cog.config_manager.get_user_data(self.ctx.author.id)
            if user_data_result.success:
                self.user_data = user_data_result.data

            embed = await self.generate_embed()
            await self.message.edit(embed=embed, view=self)
            self.logger.debug("View updated successfully")
        except Exception as e:
            self.logger.error(f"Error updating view: {e}", exc_info=True)
            raise
