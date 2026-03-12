# ui/stats.py

import discord
from discord.ext import commands
from .base import BaseView
from ..data.casino_data import GAME_NAMES
from ..utils.logging_config import get_logger

logger = get_logger('ui.stats')


class StatsView(BaseView):
    """View showing detailed player stats across all games."""

    def __init__(self, cog, ctx: commands.Context, user_data: dict):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.parent_menu_view = None

    async def initialize_view(self):
        self.clear_items()
        await self._refresh_user_data()

        back_btn = discord.ui.Button(
            label="\u25C0 Back to Hub", custom_id="back",
            style=discord.ButtonStyle.grey, row=0,
        )
        back_btn.callback = self._handle_back
        self.add_item(back_btn)

    async def generate_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="\U0001F4CA Your Casino Stats",
            color=discord.Color.blue(),
        )

        stats = self.user_data.get("stats", {})
        overall = self.user_data.get("overall", {})

        # Overall summary
        net = overall.get("net_profit", 0)
        net_display = f"+${net:,}" if net >= 0 else f"-${abs(net):,}"
        biggest = overall.get("biggest_win", 0)
        biggest_game = overall.get("biggest_win_game", "")
        biggest_str = f"${biggest:,}"
        if biggest_game:
            biggest_str += f" ({biggest_game})"

        embed.add_field(
            name="Overall",
            value=(
                f"Total Wagered: **${overall.get('total_wagered', 0):,}**\n"
                f"Total Returned: **${overall.get('total_won', 0):,}**\n"
                f"Net Profit: **{net_display}**\n"
                f"Biggest Win: **{biggest_str}**"
            ),
            inline=False,
        )

        # Per-game stats
        game_display = {
            "blackjack": "\U0001F0CF Blackjack",
            "slots": "\U0001F3B0 Slots",
            "coinflip": "\U0001FA99 Coinflip",
        }

        for game in GAME_NAMES:
            gs = stats.get(game, {})
            played = gs.get("games_played", 0)
            won = gs.get("games_won", 0)
            lost = gs.get("games_lost", 0)
            wagered = gs.get("total_wagered", 0)
            returned = gs.get("total_won", 0)
            game_net = returned - wagered
            game_net_display = f"+${game_net:,}" if game_net >= 0 else f"-${abs(game_net):,}"
            win_rate = f"{won / played * 100:.1f}%" if played > 0 else "N/A"

            lines = [
                f"Played: **{played}** | Won: **{won}** | Lost: **{lost}**",
                f"Win Rate: **{win_rate}**",
                f"Wagered: **${wagered:,}** | Net: **{game_net_display}**",
            ]

            # Game-specific extras
            if game == "blackjack":
                pushed = gs.get("games_pushed", 0)
                bjs = gs.get("blackjacks_hit", 0)
                lines.insert(1, f"Pushed: **{pushed}** | Blackjacks: **{bjs}**")
            elif game == "slots":
                jackpots = gs.get("jackpots_won", 0)
                jp_total = gs.get("jackpot_total", 0)
                if jackpots > 0:
                    lines.append(f"Jackpots Won: **{jackpots}** (${jp_total:,})")

            embed.add_field(
                name=game_display.get(game, game),
                value="\n".join(lines),
                inline=False,
            )

        return embed

    async def _handle_back(self, interaction: discord.Interaction):
        if self.parent_menu_view:
            await self.timeout_manager.resume_parent_view(self)
            parent = self.parent_menu_view
            parent.current_page = "main"
            await parent.initialize_view()
            embed = await parent.generate_embed()
            await interaction.response.edit_message(embed=embed, view=parent)
        else:
            await self.cleanup()
