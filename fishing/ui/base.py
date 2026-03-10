# ui/base.py

import discord
import logging
import asyncio
from discord.ext import commands
from discord.ui import View, Button
from typing import Optional
from ..utils.logging_config import get_logger
from ..utils.timeout_manager import TimeoutManager
from .components import MessageManager

class BaseView(View):
    """Enhanced base view class with improved error handling, logging and timeout management"""
    
    def __init__(self, cog, ctx: commands.Context, timeout: int = 600):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.message: Optional[discord.Message] = None
        self.logger = get_logger('base.view')
        self.timeout_manager = TimeoutManager()
        self._timeout_task = None
        self.logger.debug(f"Initializing BaseView for {ctx.author.name} with timeout {timeout}")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Verify interaction and manage timeouts"""
        try:
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
                self.logger.debug(
                    f"Processing interaction in {self.__class__.__name__} "
                    f"for user {self.ctx.author.name}"
                )
                await self.timeout_manager.reset_timeout(self)
                self.logger.debug(f"Timeout reset completed for {self.__class__.__name__}")
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error in interaction check: {e}")
            return False
            
    async def _handle_timeout(self):
        """Handle view timeout with delay from last interaction"""
        try:
            if self.timeout is not None:
                await asyncio.sleep(self.timeout)
                await self.on_timeout()
        except asyncio.CancelledError:
            # Task was cancelled due to new interaction
            pass
        except Exception as e:
            self.logger.error(f"Error in timeout handler: {e}")
        
    async def on_timeout(self):
        """Enhanced timeout handler"""
        try:
            self.logger.info(
                f"View timed out for user {self.ctx.author.id} "
                f"in {self.__class__.__name__}"
            )
            await self.cleanup()
            await self.timeout_manager.remove_view(self)

            # Disable all components
            for item in self.children:
                item.disabled = True
            if self.message:
                try:
                    await self.message.edit(view=self)
                except discord.NotFound:
                    pass

        except Exception as e:
            self.logger.error(f"Error in timeout handler: {e}")
            self._release_session()  # ensure session is freed even if cleanup failed

    async def cleanup(self):
        """Clean up view resources and handle timeout hierarchy"""
        try:
            self.logger.debug(f"Cleaning up view for {self.ctx.author.name}")
            for item in self.children:
                item.disabled = True

            # Update message if it exists
            if self.message:
                try:
                    await self.message.edit(view=self)
                    # Remove from timeout manager
                    await self.timeout_manager.remove_view(self)

                    # Signal parent view if this was a child view
                    if hasattr(self, 'parent_menu_view'):
                        await self.timeout_manager.resume_parent_view(self)
                except discord.NotFound:
                    pass

            # Release active session if this view owns one
            self._release_session()

            self.logger.debug(f"View cleanup completed for {self.ctx.author.name}")
        except Exception as e:
            self.logger.error(f"Error in cleanup: {e}")

    def _release_session(self):
        """Remove this view from the cog's active sessions if it owns the slot."""
        try:
            sessions = getattr(self.cog, '_active_sessions', None)
            if sessions is not None:
                user_id = self.ctx.author.id
                if sessions.get(user_id) is self:
                    sessions.pop(user_id, None)
                    self.logger.debug(f"Released active session for {self.ctx.author.name}")
        except Exception as e:
            self.logger.error(f"Error releasing session: {e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        """Global error handler for view interactions"""
        self.logger.error(f"Error in view interaction: {error}", exc_info=True)
        await MessageManager.send_temp_message(
            interaction,
            "An error occurred while processing your request.",
            ephemeral=True
        )

    async def delete_after_delay(self, message, delay: int = 2):
        """Delete a message after a delay"""
        try:
            await asyncio.sleep(delay)
            await message.delete()
        except discord.NotFound:
            pass
        except Exception as e:
            self.logger.error(f"Error in delete_after_delay: {e}")

    async def update_message(self, **kwargs):
        """Update view message with error handling"""
        try:
            if self.message:
                await self.message.edit(**kwargs)
        except discord.NotFound:
            self.logger.warning("Message not found when updating")
        except Exception as e:
            self.logger.error(f"Error updating message: {e}")

    @staticmethod
    def pad_embed(embed: discord.Embed, min_lines: int = 16):
        """Pad an embed's description with blank lines to maintain consistent UI height.

        Counts visible content lines across description and all fields,
        then appends zero-width-space lines to the description until
        the embed reaches ``min_lines``.
        """
        current = 0
        if embed.description:
            current += embed.description.count("\n") + 1
        for field in embed.fields:
            current += str(field.value).count("\n") + 1
            current += 1  # field name line

        if current < min_lines:
            padding = "\n\u200b" * (min_lines - current)
            embed.description = (embed.description or "") + padding

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
