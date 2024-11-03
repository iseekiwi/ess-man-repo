# ui/base.py

import discord
import logging
import asyncio
from discord.ext import commands
from discord.ui import View, Button
from typing import Optional
from ..utils.logging_config import get_logger
from .components import MessageManager

class BaseView(View):
    """Enhanced base view class with improved error handling, logging and timeout management"""
    
    def __init__(self, cog, ctx: commands.Context, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.message: Optional[discord.Message] = None
        self.logger = get_logger('base.view')
        self.logger.debug(f"Initializing BaseView for {ctx.author.name}")
        self._timeout_task: Optional[asyncio.Task] = None
        self._timeout_expiry: Optional[float] = None
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Enhanced interaction check with logging and timeout management"""
        is_author = interaction.user.id == self.ctx.author.id
        if not is_author:
            self.logger.warning(
                f"Unauthorized interaction attempt by {interaction.user.id} "
                f"on view owned by {self.ctx.author.id}"
            )
            await MessageManager.send_temp_message(
                interaction,
                "This menu is not for you!",
                ephemeral=True
            )
            return False
            
        # Reset timeout on valid interaction
        if self.timeout is not None:
            if self._timeout_task:
                self._timeout_task.cancel()
            self._timeout_task = self.cog.bot.loop.create_task(self._handle_timeout())
            
        return True

    async def _handle_timeout(self):
        """Handle view timeout with delay from last interaction"""
        try:
            await asyncio.sleep(self.timeout)
            await self.on_timeout()
        except asyncio.CancelledError:
            pass
        
    async def on_timeout(self):
        """Enhanced timeout handler with logging"""
        self.logger.info(f"View timed out for user {self.ctx.author.id}")
        await self.cleanup()

    async def cleanup(self):
        """Clean up view resources"""
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                self.logger.warning("Message not found when handling cleanup")
            except Exception as e:
                self.logger.error(f"Error handling cleanup: {e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        """Global error handler for view interactions"""
        self.logger.error(f"Error in view interaction: {error}", exc_info=True)
        await MessageManager.send_temp_message(
            interaction,
            "An error occurred while processing your request.",
            ephemeral=True
        )

    async def update_message(self, **kwargs):
        """Update view message with error handling"""
        try:
            if self.message:
                await self.message.edit(**kwargs)
        except discord.NotFound:
            self.logger.warning("Message not found when updating")
        except Exception as e:
            self.logger.error(f"Error updating message: {e}")

class ConfirmView(BaseView):
    """Enhanced confirmation view with improved feedback and error handling"""
    
    def __init__(self, cog, ctx, timeout: int = 30):
        super().__init__(cog, ctx, timeout=timeout)
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        """Handle confirmation"""
        self.value = True
        await self.cleanup()
        await MessageManager.send_temp_message(
            interaction,
            "Confirmed!",
            ephemeral=True
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        """Handle cancellation"""
        self.value = False
        await self.cleanup()
        await MessageManager.send_temp_message(
            interaction,
            "Cancelled!",
            ephemeral=True
        )
        self.stop()
