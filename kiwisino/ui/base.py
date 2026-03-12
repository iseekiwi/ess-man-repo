# ui/base.py

import discord
import asyncio
from discord.ext import commands
from discord.ui import View, Button
from typing import Optional
from ..utils.logging_config import get_logger
from ..utils.timeout_manager import KiwisinoTimeoutManager
from .components import MessageManager


class BaseView(View):
    """Base view for all Kiwisino UI views.

    Mirrors the fishing cog's BaseView pattern:
    - Discord's built-in timeout is disabled (timeout=None).
    - All expiry is managed by KiwisinoTimeoutManager.
    - Only the command author can interact.
    - Child views delegate timeout to their parent.
    """

    def __init__(self, cog, ctx: commands.Context, timeout: int = 600):
        super().__init__(timeout=None)
        self.cog = cog
        self.ctx = ctx
        self._custom_timeout = timeout
        self.message: Optional[discord.Message] = None
        self.logger = get_logger('base.view')
        self.timeout_manager = KiwisinoTimeoutManager()
        self._timeout_task = None

    async def _refresh_user_data(self):
        """Refresh user_data from ConfigManager."""
        if not hasattr(self, 'user_data'):
            return
        try:
            result = await self.cog.config_manager.get_user_data(self.ctx.author.id)
            if result.success:
                self.user_data = result.data
                if hasattr(self, 'parent_menu_view') and self.parent_menu_view:
                    self.parent_menu_view.user_data = result.data
        except Exception as e:
            self.logger.error(f"Error refreshing user data: {e}")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        try:
            is_author = interaction.user.id == self.ctx.author.id
            if not is_author:
                await MessageManager.send_temp_message(
                    interaction, "This menu is not for you!", ephemeral=True
                )
                return False
            if self._custom_timeout is not None:
                await self.timeout_manager.reset_timeout(self)
            return True
        except Exception as e:
            self.logger.error(f"Error in interaction check: {e}")
            return False

    async def on_timeout(self):
        """Handle timeout — delegates to parent if this is a child view."""
        try:
            if hasattr(self, 'parent_menu_view') and self.parent_menu_view:
                await self.timeout_manager.remove_view(self)
                await self.parent_menu_view.on_timeout()
                return

            self.clear_items()
            if self.message:
                try:
                    embed = discord.Embed(
                        title="Session Ended",
                        description="Your casino session has expired.",
                        color=discord.Color.greyple(),
                    )
                    await self.message.edit(embed=embed, view=self)
                except discord.NotFound:
                    pass

            await self.timeout_manager.remove_view(self)
            self._release_session()
        except Exception as e:
            self.logger.error(f"Error in timeout handler: {e}")
            self._release_session()

    async def cleanup(self):
        """Clean up view resources."""
        try:
            for item in self.children:
                item.disabled = True
            if self.message:
                try:
                    await self.message.edit(view=self)
                except discord.NotFound:
                    pass
            await self.timeout_manager.remove_view(self)
            self._release_session()
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
        except Exception as e:
            self.logger.error(f"Error releasing session: {e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        self.logger.error(f"Error in view interaction: {error}", exc_info=True)
        await MessageManager.send_temp_message(
            interaction, "An error occurred while processing your request.", ephemeral=True
        )

    async def delete_after_delay(self, message, delay: int = 2):
        try:
            await asyncio.sleep(delay)
            await message.delete()
        except discord.NotFound:
            pass
        except Exception as e:
            self.logger.error(f"Error in delete_after_delay: {e}")

    async def update_message(self, **kwargs):
        try:
            if self.message:
                await self.message.edit(**kwargs)
        except discord.NotFound:
            self.logger.warning("Message not found when updating")
        except Exception as e:
            self.logger.error(f"Error updating message: {e}")


class ConfirmView(BaseView):
    """Simple confirmation view."""

    def __init__(self, cog, ctx, timeout: int = 30):
        super().__init__(cog, ctx, timeout=timeout)
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        self.value = True
        await self.cleanup()
        await MessageManager.send_temp_message(interaction, "Confirmed!", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        self.value = False
        await self.cleanup()
        await MessageManager.send_temp_message(interaction, "Cancelled!", ephemeral=True)
        self.stop()
