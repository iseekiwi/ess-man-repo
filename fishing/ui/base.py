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
        # Disable Discord's built-in timeout — the custom TimeoutManager handles all expiry.
        # This prevents Discord from firing on_timeout independently during view transitions.
        super().__init__(timeout=None)
        self.cog = cog
        self.ctx = ctx
        self._custom_timeout = timeout
        self.message: Optional[discord.Message] = None
        self.logger = get_logger('base.view')
        self.timeout_manager = TimeoutManager()
        self._timeout_task = None
        self.logger.debug(f"Initializing BaseView for {ctx.author.name} with timeout {timeout}")

    async def _refresh_user_data(self):
        """Refresh user_data from ConfigManager to pick up external changes (e.g. admin commands, XP gains)."""
        if not hasattr(self, 'user_data'):
            return
        try:
            result = await self.cog.config_manager.get_user_data(self.ctx.author.id)
            if result.success:
                self.user_data = result.data
                # Keep parent menu view in sync if this is a child view
                if hasattr(self, 'parent_menu_view') and self.parent_menu_view:
                    self.parent_menu_view.user_data = result.data
        except Exception as e:
            self.logger.error(f"Error refreshing user data: {e}")

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
            if self._custom_timeout is not None:
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
            if self._custom_timeout is not None:
                await asyncio.sleep(self._custom_timeout)
                await self.on_timeout()
        except asyncio.CancelledError:
            # Task was cancelled due to new interaction
            pass
        except Exception as e:
            self.logger.error(f"Error in timeout handler: {e}")
        
    async def on_timeout(self):
        """Handle view timeout.

        If this is a child view (has parent_menu_view), delegates to the parent's
        on_timeout so the parent can show the "Session Ended" embed and release the
        session. Otherwise, disables components and releases the session directly.
        """
        try:
            self.logger.info(
                f"View timed out for user {self.ctx.author.id} "
                f"in {self.__class__.__name__}"
            )

            # Child view → delegate timeout to parent (e.g. FishingMenuView)
            if hasattr(self, 'parent_menu_view') and self.parent_menu_view:
                self.logger.debug(
                    f"Delegating timeout from {self.__class__.__name__} "
                    f"to parent {self.parent_menu_view.__class__.__name__}"
                )
                await self.timeout_manager.remove_view(self)
                await self.parent_menu_view.on_timeout()
                return

            # Root view timeout: disable components and edit message
            self.clear_items()
            if self.message:
                try:
                    await self.message.edit(view=self)
                except discord.NotFound:
                    pass

            await self.timeout_manager.remove_view(self)
            self._release_session()

        except Exception as e:
            self.logger.error(f"Error in timeout handler: {e}")
            self._release_session()  # ensure session is freed even if cleanup failed

    async def cleanup(self):
        """Clean up view resources.

        Disables all components, edits the message, removes from timeout manager,
        and releases the active session. Does NOT resume parent views — that is
        handled explicitly by navigation code (e.g. "Back to Menu" buttons).
        """
        try:
            self.logger.debug(f"Cleaning up view for {self.ctx.author.name}")
            for item in self.children:
                item.disabled = True

            if self.message:
                try:
                    await self.message.edit(view=self)
                except discord.NotFound:
                    pass

            await self.timeout_manager.remove_view(self)
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
