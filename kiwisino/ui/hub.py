# ui/hub.py

import discord
from discord.ext import commands
from typing import Optional
from .base import BaseView
from .components import MessageManager
from ..utils.logging_config import get_logger

logger = get_logger('ui.hub')


class BetModal(discord.ui.Modal):
    """Modal for entering a bet amount."""

    bet_input = discord.ui.TextInput(
        label="Bet Amount",
        placeholder="Enter your bet...",
        min_length=1,
        max_length=10,
    )

    def __init__(self, game_name: str, min_bet: int, max_bet: int, callback):
        super().__init__(title=f"{game_name} - Place Your Bet")
        self.bet_input.placeholder = f"${min_bet:,} - ${max_bet:,}"
        self.min_bet = min_bet
        self.max_bet = max_bet
        self._callback = callback

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet = int(self.bet_input.value.replace(",", "").replace("$", "").strip())
        except ValueError:
            await MessageManager.send_temp_message(
                interaction, "Please enter a valid number.", ephemeral=False, duration=5
            )
            return
        await self._callback(interaction, bet)


class CasinoHubView(BaseView):
    """Main casino hub menu — the root view for [p]kiwisino.

    Shows the player's balance, quick stats, and buttons for each game.
    Mirrors the FishingMenuView pattern from the fishing cog.
    """

    def __init__(self, cog, ctx: commands.Context, user_data: dict):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.parent_menu_view = None  # root view has no parent
        self.current_page = "main"

    async def setup(self):
        """Async initialization — register with timeout manager."""
        await self.timeout_manager.add_view(self, self._custom_timeout)
        await self.initialize_view()
        return self

    async def start(self):
        """Send the initial hub message."""
        embed = await self.generate_embed()
        self.message = await self.ctx.send(embed=embed, view=self)

    async def initialize_view(self):
        """Build buttons for the current page."""
        self.clear_items()
        await self._refresh_user_data()

        if self.current_page == "main":
            await self._build_main_page()
        elif self.current_page == "leaderboard":
            await self._build_leaderboard_page()

    async def _build_main_page(self):
        """Add game buttons and utility buttons."""
        guild_settings = await self._get_guild_settings()
        games_enabled = guild_settings.get("games_enabled", {})

        # Game buttons — row 1
        games = [
            ("\U0001F0CF Blackjack", "blackjack", discord.ButtonStyle.green),
            ("\U0001F3B0 Slots", "slots", discord.ButtonStyle.green),
            ("\U0001FA99 Coinflip", "coinflip", discord.ButtonStyle.green),
        ]
        for label, game_id, style in games:
            enabled = games_enabled.get(game_id, True)
            btn = discord.ui.Button(
                label=label,
                custom_id=game_id,
                style=style,
                disabled=not enabled,
                row=0,
            )
            btn.callback = self._make_game_callback(game_id)
            self.add_item(btn)

        # Utility buttons — row 2
        stats_btn = discord.ui.Button(
            label="\U0001F4CA My Stats", custom_id="stats",
            style=discord.ButtonStyle.blurple, row=1,
        )
        stats_btn.callback = self._handle_stats
        self.add_item(stats_btn)

        lb_btn = discord.ui.Button(
            label="\U0001F3C6 Leaderboard", custom_id="leaderboard",
            style=discord.ButtonStyle.blurple, row=1,
        )
        lb_btn.callback = self._handle_leaderboard
        self.add_item(lb_btn)

        close_btn = discord.ui.Button(
            label="\u274C Close", custom_id="close",
            style=discord.ButtonStyle.red, row=1,
        )
        close_btn.callback = self._handle_close
        self.add_item(close_btn)

    async def _build_leaderboard_page(self):
        """Add back button for leaderboard page."""
        back_btn = discord.ui.Button(
            label="\u25C0 Back to Menu", custom_id="back",
            style=discord.ButtonStyle.grey, row=0,
        )
        back_btn.callback = self._handle_back
        self.add_item(back_btn)

    # ------------------------------------------------------------------
    # Embed generation
    # ------------------------------------------------------------------

    async def generate_embed(self) -> discord.Embed:
        if self.current_page == "leaderboard":
            return await self._generate_leaderboard_embed()
        return await self._generate_main_embed()

    async def _generate_main_embed(self) -> discord.Embed:
        from redbot.core import bank
        try:
            balance = await bank.get_balance(self.ctx.author)
        except Exception:
            balance = 0

        overall = self.user_data.get("overall", {})
        net = overall.get("net_profit", 0)
        net_display = f"+${net:,}" if net >= 0 else f"-${abs(net):,}"

        guild_settings = await self._get_guild_settings()
        bet_limits = guild_settings.get("bet_limits", {})

        # Jackpot amount
        jackpot_data = guild_settings.get("jackpot", {})
        jackpot = jackpot_data.get("current_amount", 1000)

        embed = discord.Embed(
            title="\U0001F3B0 Welcome to the Kiwisino! \U0001F3B0",
            color=discord.Color.gold(),
        )

        embed.add_field(
            name="Balance",
            value=f"**${balance:,}**",
            inline=True,
        )
        embed.add_field(
            name="Net Profit",
            value=f"**{net_display}**",
            inline=True,
        )
        embed.add_field(
            name="\U0001F3B0 Jackpot",
            value=f"**${jackpot:,}**",
            inline=True,
        )

        # Game info
        games_enabled = guild_settings.get("games_enabled", {})
        game_lines = []
        for game_id, display in [("blackjack", "\U0001F0CF Blackjack"), ("slots", "\U0001F3B0 Slots"), ("coinflip", "\U0001FA99 Coinflip")]:
            enabled = games_enabled.get(game_id, True)
            limits = bet_limits.get(game_id, {"min": 0, "max": 0})
            status = "" if enabled else " *(disabled)*"
            game_lines.append(
                f"{display}: ${limits['min']:,} - ${limits['max']:,}{status}"
            )

        embed.add_field(
            name="Games",
            value="\n".join(game_lines),
            inline=False,
        )

        embed.set_footer(text=f"Total wagered: ${overall.get('total_wagered', 0):,}")
        return embed

    async def _generate_leaderboard_embed(self) -> discord.Embed:
        result = await self.cog.stats_manager.get_leaderboard("net_profit", limit=10)

        embed = discord.Embed(
            title="\U0001F3C6 Kiwisino Leaderboard",
            description="Top 10 players by net profit",
            color=discord.Color.gold(),
        )

        if not result.success or not result.data:
            embed.add_field(name="No data", value="No players have gambled yet.")
            return embed

        lines = []
        medals = ["\U0001F947", "\U0001F948", "\U0001F949"]
        for i, (user_id, net_profit) in enumerate(result.data):
            prefix = medals[i] if i < 3 else f"**{i + 1}.**"
            try:
                user = await self.cog.bot.fetch_user(user_id)
                name = user.display_name
            except Exception:
                name = f"User {user_id}"

            profit_display = f"+${net_profit:,}" if net_profit >= 0 else f"-${abs(net_profit):,}"
            lines.append(f"{prefix} {name}: {profit_display}")

        embed.description = "\n".join(lines)
        return embed

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _make_game_callback(self, game_id: str):
        async def callback(interaction: discord.Interaction):
            await self._open_game(interaction, game_id)
        return callback

    async def _open_game(self, interaction: discord.Interaction, game_id: str):
        """Navigate to a game view."""
        guild_settings = await self._get_guild_settings()
        games_enabled = guild_settings.get("games_enabled", {})
        if not games_enabled.get(game_id, True):
            await MessageManager.send_temp_message(
                interaction, f"{game_id.title()} is currently disabled.", ephemeral=False, duration=5
            )
            return

        bet_limits = guild_settings.get(game_id, guild_settings.get("bet_limits", {}).get(game_id, {"min": 10, "max": 5000}))
        if isinstance(bet_limits, dict) and "min" in bet_limits:
            min_bet = bet_limits["min"]
            max_bet = bet_limits["max"]
        else:
            bl = guild_settings.get("bet_limits", {}).get(game_id, {"min": 10, "max": 5000})
            min_bet = bl["min"]
            max_bet = bl["max"]

        if game_id == "blackjack":
            from .blackjack import BlackjackView
            child = BlackjackView(self.cog, self.ctx, self.user_data, min_bet, max_bet)
        elif game_id == "slots":
            from .slots import SlotsView
            child = SlotsView(self.cog, self.ctx, self.user_data, min_bet, max_bet)
        elif game_id == "coinflip":
            from .coinflip import CoinflipView
            child = CoinflipView(self.cog, self.ctx, self.user_data, min_bet, max_bet)
        else:
            return

        child.parent_menu_view = self
        child.message = self.message
        await self.timeout_manager.handle_view_transition(self, child)

        await child.initialize_view()
        embed = await child.generate_embed()
        await interaction.response.edit_message(embed=embed, view=child)

    async def _handle_stats(self, interaction: discord.Interaction):
        from .stats import StatsView
        child = StatsView(self.cog, self.ctx, self.user_data)
        child.parent_menu_view = self
        child.message = self.message
        await self.timeout_manager.handle_view_transition(self, child)

        await child.initialize_view()
        embed = await child.generate_embed()
        await interaction.response.edit_message(embed=embed, view=child)

    async def _handle_leaderboard(self, interaction: discord.Interaction):
        self.current_page = "leaderboard"
        await self.initialize_view()
        embed = await self.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _handle_back(self, interaction: discord.Interaction):
        self.current_page = "main"
        await self.initialize_view()
        embed = await self.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _handle_close(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Thanks for visiting the Kiwisino!",
            description="Come back anytime.",
            color=discord.Color.greyple(),
        )
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)
        await self.timeout_manager.remove_view(self)
        self._release_session()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_guild_settings(self) -> dict:
        result = await self.cog.config_manager.get_guild_settings(self.ctx.guild.id)
        if result.success:
            return result.data
        return {}
