import discord
from discord.ui import View
from typing import Optional, Any, Dict
from ..utils.logging_config import get_logger
from .components import MessageManager

class BaseView(View):
    """Enhanced base view with common functionality"""
    def __init__(self, cog, ctx, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.message: Optional[discord.Message] = None
        self.logger = get_logger('ui.base')
        
    async def update_message(self, **kwargs):
        """Update view message with error handling"""
        try:
            if self.message:
                await self.message.edit(**kwargs)
        except discord.NotFound:
            self.logger.warning("Message not found when updating")
        except Exception as e:
            self.logger.error(f"Error updating message: {e}")
            
    async def cleanup(self):
        """Clean up view resources"""
        for item in self.children:
            item.disabled = True
        await self.update_message(view=self)
        
    async def on_timeout(self):
        """Handle view timeout"""
        await self.cleanup()
        
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        """Global error handler"""
        self.logger.error(f"Error in view interaction: {error}", exc_info=True)
        await MessageManager.send_temp_message(
            interaction,
            "An error occurred while processing your request.",
            ephemeral=True
        )

class ConfirmationView(BaseView):
    """View for confirmation dialogs"""
    def __init__(self, cog, ctx, title: str, description: str):
        super().__init__(cog, ctx, timeout=30)
        self.title = title
        self.description = description
        self.result = None
        
    async def setup(self):
        """Initialize view components"""
        from .components import ConfirmationButton
        
        confirm = ConfirmationButton(
            label="Confirm",
            style=discord.ButtonStyle.green,
            callback=self.on_confirm
        )
        cancel = ConfirmationButton(
            label="Cancel",
            style=discord.ButtonStyle.red,
            callback=self.on_cancel
        )
        
        self.add_item(confirm)
        self.add_item(cancel)
        return self
        
    async def on_confirm(self, interaction: discord.Interaction):
        """Handle confirmation"""
        self.result = True
        await self.cleanup()
        await MessageManager.send_temp_message(
            interaction,
            "Confirmed!",
            ephemeral=True
        )
        
    async def on_cancel(self, interaction: discord.Interaction):
        """Handle cancellation"""
        self.result = False
        await self.cleanup()
        await MessageManager.send_temp_message(
            interaction,
            "Cancelled!",
            ephemeral=True
        )
