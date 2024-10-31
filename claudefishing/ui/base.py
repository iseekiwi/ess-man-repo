# base.py

import discord
from discord.ext import commands
from discord.ui import View, Button
from typing import Optional
import logging

logger = logging.getLogger("red.fishing.views")

class BaseView(View):
    """Enhanced base view class with improved error handling and logging"""
    
    def __init__(self, cog, ctx: commands.Context, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.message: Optional[discord.Message] = None
        self.logger = logging.getLogger("red.fishing.views")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Enhanced interaction check with logging"""
        is_author = interaction.user.id == self.ctx.author.id
        if not is_author:
            self.logger.warning(
                f"Unauthorized interaction attempt by {interaction.user.id} "
                f"on view owned by {self.ctx.author.id}"
            )
            await interaction.response.send_message(
                "This menu is not for you!", 
                ephemeral=True
            )
        return is_author

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        """Global error handler for view interactions"""
        self.logger.error(f"Error in view interaction: {error}", exc_info=True)
        
        error_message = "An error occurred while processing your request."
        if not interaction.response.is_done():
            await interaction.response.send_message(
                error_message,
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                error_message,
                ephemeral=True
            )

    async def on_timeout(self):
        """Enhanced timeout handler with logging"""
        self.logger.info(f"View timed out for user {self.ctx.author.id}")
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.errors.NotFound:
                self.logger.warning("Message not found when handling timeout")
            except Exception as e:
                self.logger.error(f"Error handling timeout: {e}", exc_info=True)

class ConfirmView(View):
    """Enhanced confirmation view with improved feedback and error handling"""
    
    def __init__(self, owner: discord.Member, timeout: int = 30):
        super().__init__(timeout=timeout)
        self.owner = owner
        self.value = None
        self.logger = logging.getLogger("red.fishing.views")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        is_owner = interaction.user.id == self.owner.id
        if not is_owner:
            await interaction.response.send_message(
                "This confirmation is not for you!", 
                ephemeral=True
            )
        return is_owner

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        self.logger.error(f"Error in confirmation view: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "An error occurred while processing your response.",
                ephemeral=True
            )

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            self.value = True
            self.stop()
            
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(view=self)
            self.logger.debug(f"User {interaction.user.id} confirmed action")
            
        except Exception as e:
            self.logger.error(f"Error in confirm button: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while confirming your choice.",
                ephemeral=True
            )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            self.value = False
            self.stop()
            
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(view=self)
            self.logger.debug(f"User {interaction.user.id} cancelled action")
            
        except Exception as e:
            self.logger.error(f"Error in cancel button: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while cancelling your choice.",
                ephemeral=True
            )

    async def on_timeout(self):
        self.value = False
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
            self.logger.info("Confirmation view timed out")
        except Exception as e:
            self.logger.error(f"Error handling confirmation timeout: {e}", exc_info=True)
