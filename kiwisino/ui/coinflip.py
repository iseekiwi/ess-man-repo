# ui/coinflip.py

import discord
from discord.ext import commands
from typing import Optional, Dict
from .base import BaseView
from .hub import BetModal
from .components import MessageManager
from ..games.coinflip import CoinflipGame
from ..utils.logging_config import get_logger

logger = get_logger('ui.coinflip')


class CoinflipView(BaseView):
    """Interactive coinflip game view.

    Flow: Place Bet -> bet modal -> Heads/Tails buttons -> result -> Play Again / Back.
    """

    def __init__(self, cog, ctx: commands.Context, user_data: dict, min_bet: int, max_bet: int):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.parent_menu_view = None
        self.min_bet = min_bet
        self.max_bet = max_bet
        self.coinflip_game = CoinflipGame()
        self.last_result: Optional[Dict] = None
        self.current_bet = 0
        self._phase = "betting"  # betting, choosing, result

    async def initialize_view(self):
        self.clear_items()
        if self._phase == "betting":
            self._build_betting_buttons()
        elif self._phase == "choosing":
            self._build_choosing_buttons()
        elif self._phase == "result":
            self._build_result_buttons()

    def _build_betting_buttons(self):
        bet_btn = discord.ui.Button(
            label="\U0001FA99 Place Bet", custom_id="place_bet",
            style=discord.ButtonStyle.green, row=0,
        )
        bet_btn.callback = self._handle_place_bet
        self.add_item(bet_btn)

        back_btn = discord.ui.Button(
            label="\u25C0 Back to Hub", custom_id="back",
            style=discord.ButtonStyle.grey, row=0,
        )
        back_btn.callback = self._handle_back
        self.add_item(back_btn)

    def _build_choosing_buttons(self):
        heads_btn = discord.ui.Button(
            label="Heads", custom_id="heads",
            style=discord.ButtonStyle.green, row=0,
            emoji="\U0001FA99",
        )
        heads_btn.callback = self._handle_heads
        self.add_item(heads_btn)

        tails_btn = discord.ui.Button(
            label="Tails", custom_id="tails",
            style=discord.ButtonStyle.blurple, row=0,
            emoji="\U0001FA99",
        )
        tails_btn.callback = self._handle_tails
        self.add_item(tails_btn)

    def _build_result_buttons(self):
        again_btn = discord.ui.Button(
            label=f"\U0001F503 Play Again (${self.current_bet:,})", custom_id="play_again",
            style=discord.ButtonStyle.green, row=0,
        )
        again_btn.callback = self._handle_play_again
        self.add_item(again_btn)

        change_btn = discord.ui.Button(
            label="\U0001F4B0 Change Bet", custom_id="change_bet",
            style=discord.ButtonStyle.blurple, row=0,
        )
        change_btn.callback = self._handle_change_bet
        self.add_item(change_btn)

        back_btn = discord.ui.Button(
            label="\u25C0 Back to Hub", custom_id="back",
            style=discord.ButtonStyle.grey, row=0,
        )
        back_btn.callback = self._handle_back
        self.add_item(back_btn)

    # ------------------------------------------------------------------
    # Embed
    # ------------------------------------------------------------------

    async def generate_embed(self) -> discord.Embed:
        if self._phase == "betting":
            return self._betting_embed()
        elif self._phase == "choosing":
            return self._choosing_embed()
        return self._result_embed()

    def _betting_embed(self) -> discord.Embed:
        return discord.Embed(
            title="\U0001FA99 Coinflip",
            description=(
                f"Place your bet, then choose Heads or Tails!\n"
                f"Bet range: **${self.min_bet:,}** - **${self.max_bet:,}**"
            ),
            color=discord.Color.blue(),
        )

    def _choosing_embed(self) -> discord.Embed:
        return discord.Embed(
            title="\U0001FA99 Coinflip",
            description=f"Bet: **${self.current_bet:,}**\n\nChoose **Heads** or **Tails**!",
            color=discord.Color.blue(),
        )

    def _result_embed(self) -> discord.Embed:
        r = self.last_result
        if not r:
            return discord.Embed(title="Coinflip")

        if r["won"]:
            color = discord.Color.green()
            title = "\U0001FA99 Coinflip - You Win!"
        else:
            color = discord.Color.red()
            title = "\U0001FA99 Coinflip - You Lose"

        embed = discord.Embed(title=title, color=color)

        result_display = r["result"].upper()
        choice_display = r["choice"].upper()

        embed.add_field(
            name="Result",
            value=f"**{result_display}**",
            inline=True,
        )
        embed.add_field(
            name="Your Pick",
            value=f"**{choice_display}**",
            inline=True,
        )

        if r["won"]:
            net = r["payout"] - r["bet"]
            embed.add_field(
                name="Payout",
                value=f"**${r['payout']:,}** (+${net:,})",
                inline=False,
            )
        else:
            embed.add_field(
                name="Lost",
                value=f"**${r['bet']:,}**",
                inline=False,
            )

        return embed

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    async def _handle_place_bet(self, interaction: discord.Interaction):
        modal = BetModal("Coinflip", self.min_bet, self.max_bet, self._set_bet)
        await interaction.response.send_modal(modal)

    async def _set_bet(self, interaction: discord.Interaction, bet: int):
        """Validate bet, withdraw, and move to choosing phase."""
        from redbot.core import bank

        valid, error = self.coinflip_game.validate_bet(bet, self.min_bet, self.max_bet)
        if not valid:
            await MessageManager.send_temp_message(interaction, error, ephemeral=False, duration=5)
            return

        try:
            balance = await bank.get_balance(self.ctx.author)
        except Exception:
            await MessageManager.send_temp_message(
                interaction, "Could not check your balance.", ephemeral=False, duration=5
            )
            return

        if balance < bet:
            await MessageManager.send_temp_message(
                interaction, f"You don't have enough. Balance: **${balance:,}**", ephemeral=False, duration=5
            )
            return

        try:
            await bank.withdraw_credits(self.ctx.author, bet)
        except Exception as e:
            await MessageManager.send_temp_message(
                interaction, f"Failed to withdraw bet: {e}", ephemeral=False, duration=5
            )
            return

        self.current_bet = bet
        self._phase = "choosing"
        await self.initialize_view()
        embed = await self.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _handle_heads(self, interaction: discord.Interaction):
        await self._do_flip(interaction, "heads")

    async def _handle_tails(self, interaction: discord.Interaction):
        await self._do_flip(interaction, "tails")

    async def _do_flip(self, interaction: discord.Interaction, choice: str):
        """Flip the coin and process the result."""
        from redbot.core import bank

        # Get payout multiplier from guild config
        payout_multi = 1.95
        gs = await self.cog.config_manager.get_guild_settings(self.ctx.guild.id)
        if gs.success:
            cf_payout = gs.data.get("payout_multipliers", {}).get("coinflip", 1.95)
            if isinstance(cf_payout, (int, float)):
                payout_multi = float(cf_payout)

        result = self.coinflip_game.flip(self.current_bet, choice, payout_multi)

        if result["won"] and result["payout"] > 0:
            try:
                await bank.deposit_credits(self.ctx.author, result["payout"])
            except Exception as e:
                logger.error(f"Failed to deposit coinflip win: {e}")

        await self.cog.stats_manager.record_game(
            user_id=self.ctx.author.id,
            game="coinflip",
            bet=self.current_bet,
            payout=result["payout"],
            won=result["won"],
        )

        if result["payout"] > 0:
            await self.cog.payout_log.log_payout(
                guild_id=self.ctx.guild.id,
                user_id=self.ctx.author.id,
                game="coinflip",
                bet=self.current_bet,
                payout=result["payout"],
                result="win",
            )

        self.last_result = result
        self._phase = "result"
        await self.initialize_view()
        embed = await self.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _handle_play_again(self, interaction: discord.Interaction):
        """Play again with the same bet — re-withdraw and go to choosing."""
        from redbot.core import bank

        try:
            balance = await bank.get_balance(self.ctx.author)
        except Exception:
            await MessageManager.send_temp_message(
                interaction, "Could not check your balance.", ephemeral=False, duration=5
            )
            return

        if balance < self.current_bet:
            await MessageManager.send_temp_message(
                interaction, f"You don't have enough. Balance: **${balance:,}**", ephemeral=False, duration=5
            )
            return

        try:
            await bank.withdraw_credits(self.ctx.author, self.current_bet)
        except Exception as e:
            await MessageManager.send_temp_message(
                interaction, f"Failed to withdraw bet: {e}", ephemeral=False, duration=5
            )
            return

        self._phase = "choosing"
        await self.initialize_view()
        embed = await self.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _handle_change_bet(self, interaction: discord.Interaction):
        self._phase = "betting"
        await self.initialize_view()
        embed = await self.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)

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
