from discord.ext import commands
from discord.ui import View, Button
import discord
from typing import Optional

class BaseView(View):
    """Base view class with common functionality"""
    def __init__(self, cog, ctx: commands.Context, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can interact with the view"""
        return interaction.user.id == self.ctx.author.id

    async def on_timeout(self):
        """Disable all buttons when the view times out"""
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)

class ConfirmView(View):
    """Generic confirmation view"""
    def __init__(self, owner: discord.Member, timeout: int = 30):
        super().__init__(timeout=timeout)
        self.owner = owner
        self.value = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner.id

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.defer()
