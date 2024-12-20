# ui/components.py

import discord
import asyncio
from discord.ui import Button, Select
from typing import Optional, Callable, Any
from ..utils.logging_config import get_logger

logger = get_logger('ui.components')

class ConfirmationButton(Button):
    def __init__(
        self,
        label: str,
        style: discord.ButtonStyle,
        callback: Callable,
        **kwargs
    ):
        super().__init__(label=label, style=style, **kwargs)
        self._callback = callback
        
    async def callback(self, interaction: discord.Interaction):
        await self._callback(interaction)

class NavigationButton(Button):
    def __init__(
        self,
        label: str,
        destination: str,
        style: discord.ButtonStyle = discord.ButtonStyle.grey,
        **kwargs
    ):
        super().__init__(
            label=label,
            custom_id=f"nav_{destination}",
            style=style,
            **kwargs
        )

class MessageManager:
    """Helper class for managing temporary messages"""
    @staticmethod
    async def send_temp_message(
        interaction: discord.Interaction,
        content: str,
        ephemeral: bool = True,
        duration: int = 2
    ):
        """Send a temporary message that auto-deletes"""
        try:
            if interaction.response.is_done():
                message = await interaction.followup.send(
                    content,
                    ephemeral=ephemeral,
                    wait=True
                )
            else:
                await interaction.response.send_message(
                    content,
                    ephemeral=ephemeral
                )
                message = await interaction.original_response()
                
            if not ephemeral:
                await asyncio.sleep(duration)
                try:
                    await message.delete()
                except discord.NotFound:
                    pass
                    
        except Exception as e:
            logger.error(f"Error sending temporary message: {e}")
