# ui/slots.py

import discord
from discord.ext import commands
from typing import Optional, Dict
from .base import BaseView
from .hub import BetModal
from .components import MessageManager
from ..games.slots import SlotsGame
from ..utils.logging_config import get_logger

logger = get_logger('ui.slots')


class SlotsView(BaseView):
    """Interactive slots game view.

    Flow: Place Bet -> bet modal -> spin -> result -> Spin Again / Change Bet / Back.
    """

    def __init__(self, cog, ctx: commands.Context, user_data: dict, min_bet: int, max_bet: int):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.parent_menu_view = None
        self.min_bet = min_bet
        self.max_bet = max_bet
        self.slots_game = SlotsGame()
        self.last_result: Optional[Dict] = None
        self.current_bet = 0
        self._phase = "betting"  # betting, result

    async def initialize_view(self):
        self.clear_items()
        if self._phase == "betting":
            self._build_betting_buttons()
        elif self._phase == "result":
            self._build_result_buttons()

    def _build_betting_buttons(self):
        bet_btn = discord.ui.Button(
            label="\U0001F3B0 Place Bet & Spin", custom_id="place_bet",
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

    def _build_result_buttons(self):
        again_btn = discord.ui.Button(
            label=f"\U0001F503 Spin Again (${self.current_bet:,})", custom_id="spin_again",
            style=discord.ButtonStyle.green, row=0,
        )
        again_btn.callback = self._handle_spin_again
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
            return await self._betting_embed()
        return await self._result_embed()

    async def _betting_embed(self) -> discord.Embed:
        jackpot = await self._get_jackpot()
        embed = discord.Embed(
            title="\U0001F3B0 Slots",
            description=(
                f"Place your bet and spin the reels!\n"
                f"Bet range: **${self.min_bet:,}** - **${self.max_bet:,}**\n\n"
                f"\U0001F3B0 **Progressive Jackpot: ${jackpot:,}**\n"
                f"Hit 3x \U0001F95D to win!"
            ),
            color=discord.Color.purple(),
        )
        return embed

    async def _result_embed(self) -> discord.Embed:
        r = self.last_result
        if not r:
            return discord.Embed(title="Slots")

        jackpot_won = r.get("jackpot_trigger", False)

        if jackpot_won:
            color = discord.Color.gold()
            title = "\U0001F3B0 JACKPOT!!! \U0001F3B0"
        elif r["won"]:
            color = discord.Color.green()
            title = "\U0001F3B0 Slots - Winner!"
        else:
            color = discord.Color.red()
            title = "\U0001F3B0 Slots - No Luck"

        embed = discord.Embed(title=title, color=color)

        # ASCII slot machine
        machine = self.slots_game.get_ascii_display(r["emojis"])
        embed.description = machine

        if jackpot_won:
            jackpot_amount = r.get("jackpot_amount", 0)
            embed.add_field(
                name="\U0001F31F JACKPOT WINNER! \U0001F31F",
                value=f"You won the progressive jackpot!\n**${jackpot_amount:,}**",
                inline=False,
            )
        elif r["won"]:
            embed.add_field(
                name="Payout",
                value=f"**${r['payout']:,}** ({r['multiplier']:.1f}x)",
                inline=True,
            )
            net = r["payout"] - r["bet"]
            embed.add_field(
                name="Profit",
                value=f"+${net:,}",
                inline=True,
            )
        else:
            embed.add_field(
                name="Result",
                value=f"Lost **${r['bet']:,}**",
                inline=True,
            )

        # Show current jackpot
        jackpot = await self._get_jackpot()
        embed.set_footer(text=f"Bet: ${r['bet']:,} | Jackpot: ${jackpot:,}")
        return embed

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    async def _handle_place_bet(self, interaction: discord.Interaction):
        modal = BetModal("Slots", self.min_bet, self.max_bet, self._do_spin)
        await interaction.response.send_modal(modal)

    async def _handle_spin_again(self, interaction: discord.Interaction):
        """Spin again with the same bet."""
        await self._do_spin(interaction, self.current_bet)

    async def _handle_change_bet(self, interaction: discord.Interaction):
        modal = BetModal("Slots", self.min_bet, self.max_bet, self._do_spin)
        await interaction.response.send_modal(modal)

    async def _do_spin(self, interaction: discord.Interaction, bet: int):
        """Validate, withdraw, spin, process result."""
        from redbot.core import bank

        valid, error = self.slots_game.validate_bet(bet, self.min_bet, self.max_bet)
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

        # Get slots payout multiplier from guild settings
        slots_multi = 1.0
        gs = await self.cog.config_manager.get_guild_settings(self.ctx.guild.id)
        if gs.success:
            slots_multi = gs.data.get("payout_multipliers", {}).get("slots", 1.0)

        result = self.slots_game.spin(bet, slots_multi)

        # Contribute to jackpot
        await self.cog.jackpot_manager.contribute(self.ctx.guild.id, bet)

        # Handle jackpot trigger
        if result["jackpot_trigger"]:
            jp_result = await self.cog.jackpot_manager.award(self.ctx.guild.id)
            if jp_result.success:
                jackpot_amount = jp_result.data
                result["jackpot_amount"] = jackpot_amount
                result["payout"] = jackpot_amount
                result["won"] = True
                try:
                    await bank.deposit_credits(self.ctx.author, jackpot_amount)
                except Exception as e:
                    logger.error(f"Failed to deposit jackpot: {e}")

                await self.cog.stats_manager.record_game(
                    user_id=self.ctx.author.id,
                    game="slots",
                    bet=bet,
                    payout=jackpot_amount,
                    won=True,
                    is_jackpot=True,
                    jackpot_amount=jackpot_amount,
                )
                await self.cog.payout_log.log_payout(
                    guild_id=self.ctx.guild.id,
                    user_id=self.ctx.author.id,
                    game="slots",
                    bet=bet,
                    payout=jackpot_amount,
                    result="jackpot",
                    jackpot=True,
                )
        else:
            # Normal result
            if result["payout"] > 0:
                try:
                    await bank.deposit_credits(self.ctx.author, result["payout"])
                except Exception as e:
                    logger.error(f"Failed to deposit slots win: {e}")

            await self.cog.stats_manager.record_game(
                user_id=self.ctx.author.id,
                game="slots",
                bet=bet,
                payout=result["payout"],
                won=result["won"],
            )

            if result["payout"] > 0:
                await self.cog.payout_log.log_payout(
                    guild_id=self.ctx.guild.id,
                    user_id=self.ctx.author.id,
                    game="slots",
                    bet=bet,
                    payout=result["payout"],
                    result="win",
                )

        self.last_result = result
        self._phase = "result"

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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_jackpot(self) -> int:
        result = await self.cog.jackpot_manager.get_current(self.ctx.guild.id)
        return result.data if result.success else 0
