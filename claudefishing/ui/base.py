from discord.ext import commands
from discord.ui import View, Button
import discord
from typing import Optional
import logging

class BaseView(View):
    """Base view class with common functionality"""
    def __init__(self, cog, ctx: commands.Context, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.message: Optional[discord.Message] = None
        self.logger = logging.getLogger('fishing.views')
        self.logger.debug(f"Initializing BaseView for {ctx.author.name}")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can interact with the view"""
        is_author = interaction.user.id == self.ctx.author.id
        if not is_author:
            self.logger.warning(f"Unauthorized interaction attempt by {interaction.user.name}")
            await interaction.response.send_message(
                "You cannot interact with this menu.", 
                ephemeral=True
            )
        return is_author

    async def on_timeout(self):
        """Disable all buttons when the view times out"""
        try:
            self.logger.debug(f"View timed out for {self.ctx.author.name}")
            for item in self.children:
                item.disabled = True
            if self.message:
                await self.message.edit(view=self)
        except Exception as e:
            self.logger.error(f"Error in timeout handling: {e}", exc_info=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
        """Handle errors in view interactions"""
        self.logger.error(f"Error in view interaction: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "An error occurred. Please try again.", 
                ephemeral=True
            )

class ConfirmView(View):
    """Generic confirmation view"""
    def __init__(self, owner: discord.Member, timeout: int = 30):
        super().__init__(timeout=timeout)
        self.owner = owner
        self.value = None
        self.logger = logging.getLogger('fishing.views.confirm')
        self.logger.debug(f"Initializing ConfirmView for {owner.name}")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Verify interaction is from the view owner"""
        is_owner = interaction.user.id == self.owner.id
        if not is_owner:
            self.logger.warning(f"Unauthorized confirmation attempt by {interaction.user.name}")
            await interaction.response.send_message(
                "You cannot interact with this confirmation.", 
                ephemeral=True
            )
        return is_owner

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle confirmation button press"""
        try:
            self.logger.debug(f"Confirmation received from {self.owner.name}")
            self.value = True
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(view=self)
            self.stop()
        except Exception as e:
            self.logger.error(f"Error in confirm button: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while confirming. Please try again.",
                ephemeral=True
            )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle cancellation button press"""
        try:
            self.logger.debug(f"Cancellation received from {self.owner.name}")
            self.value = False
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(view=self)
            self.stop()
        except Exception as e:
            self.logger.error(f"Error in cancel button: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while cancelling. Please try again.",
                ephemeral=True
            )

    async def on_timeout(self):
        """Handle view timeout"""
        try:
            self.logger.debug(f"Confirmation view timed out for {self.owner.name}")
            self.value = False
            for item in self.children:
                item.disabled = True
            if self.message:
                await self.message.edit(view=self)
        except Exception as e:
            self.logger.error(f"Error in confirmation timeout: {e}", exc_info=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
        """Handle errors in confirmation interactions"""
        self.logger.error(f"Error in confirmation interaction: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "An error occurred. Please try again.", 
                ephemeral=True
            )
