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
        self._closed = False
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Enhanced interaction check with improved timeout management"""
        try:
            if self._closed:
                return False
                
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
                return False
                
            # Reset timeout on valid interaction
            if self.timeout is not None:
                # Cancel existing timeout task if it exists
                if self._timeout_task and not self._timeout_task.done():
                    self._timeout_task.cancel()
                    try:
                        await self._timeout_task
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        self.logger.error(f"Error cancelling timeout task: {e}")
                
                # Create new timeout task
                self._timeout_task = asyncio.create_task(self._handle_timeout())
                self._timeout_expiry = time.time() + self.timeout
                self.logger.debug(f"Reset timeout for view owned by {self.ctx.author.id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in interaction check: {e}")
            return False
            
    async def _handle_timeout(self):
        """Handle view timeout with delay from last interaction"""
        try:
            if self.timeout is not None:
                await asyncio.sleep(self.timeout)
                if not self._closed:
                    await self.on_timeout()
        except asyncio.CancelledError:
            # Task was cancelled due to new interaction
            pass
        except Exception as e:
            self.logger.error(f"Error in timeout handler: {e}")
            
    async def cleanup(self):
        """Enhanced cleanup with proper task management"""
        if self._closed:
            return
            
        self._closed = True
        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                self.logger.error(f"Error cleaning up timeout task: {e}")
                
        for item in self.children:
            item.disabled = True
            
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                self.logger.warning("Message not found during cleanup")
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")
                
    async def on_timeout(self):
        """Enhanced timeout handler"""
        self.logger.info(f"View timed out for user {self.ctx.author.id}")
        await self.cleanup()
        
    def stop(self):
        """Override stop to ensure proper cleanup"""
        asyncio.create_task(self.cleanup())
        super().stop()

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
