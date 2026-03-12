# ui/blackjack.py

import discord
from discord.ext import commands
from typing import Optional, Dict
from .base import BaseView
from .hub import BetModal
from .components import MessageManager
from ..games.blackjack import BlackjackGame
from ..utils.logging_config import get_logger

logger = get_logger('ui.blackjack')


class BlackjackView(BaseView):
    """Interactive blackjack game view.

    Flow: Place Bet -> bet modal -> game plays out with Hit/Stand/Double/Split/Surrender
    -> result -> Play Again / Back to Hub.
    """

    def __init__(self, cog, ctx: commands.Context, user_data: dict, min_bet: int, max_bet: int):
        super().__init__(cog, ctx)
        self.user_data = user_data
        self.parent_menu_view = None
        self.min_bet = min_bet
        self.max_bet = max_bet
        self.game: Optional[BlackjackGame] = None
        self.game_state: Optional[Dict] = None
        self.current_bet = 0
        self._phase = "betting"  # betting, playing, resolved

        # Get or create persistent deck from the cog
        if not hasattr(cog, '_blackjack_decks'):
            cog._blackjack_decks = {}
        guild_id = ctx.guild.id
        if guild_id not in cog._blackjack_decks:
            from ..games.blackjack import Deck
            cog._blackjack_decks[guild_id] = Deck()
        self._deck = cog._blackjack_decks[guild_id]

    async def initialize_view(self):
        self.clear_items()
        if self._phase == "betting":
            self._build_betting_buttons()
        elif self._phase == "playing":
            self._build_playing_buttons()
        elif self._phase == "resolved":
            self._build_resolved_buttons()

    def _build_betting_buttons(self):
        bet_btn = discord.ui.Button(
            label="Place Bet", custom_id="place_bet",
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

    def _build_playing_buttons(self):
        actions = self.game_state.get("actions", []) if self.game_state else []

        action_map = [
            ("hit", "Hit", discord.ButtonStyle.green),
            ("stand", "Stand", discord.ButtonStyle.blurple),
            ("double_down", "Double Down", discord.ButtonStyle.blurple),
            ("split", "Split", discord.ButtonStyle.blurple),
            ("surrender", "Surrender", discord.ButtonStyle.red),
        ]

        for action_id, label, style in action_map:
            btn = discord.ui.Button(
                label=label, custom_id=action_id,
                style=style, row=0,
                disabled=action_id not in actions,
            )
            btn.callback = self._make_action_callback(action_id)
            self.add_item(btn)

    def _build_resolved_buttons(self):
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
        elif self._phase == "playing":
            return self._playing_embed()
        elif self._phase == "resolved":
            return await self._resolved_embed()
        return discord.Embed(title="Blackjack")

    def _betting_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="\U0001F0CF Blackjack",
            description=f"Place your bet to start a hand.\nBet range: **${self.min_bet:,}** - **${self.max_bet:,}**",
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Cards remaining in shoe: {self._deck.remaining}")
        return embed

    def _playing_embed(self) -> discord.Embed:
        gs = self.game_state
        embed = discord.Embed(
            title="\U0001F0CF Blackjack",
            color=discord.Color.green(),
        )

        # Dealer
        dealer = gs["dealer"]
        embed.add_field(
            name="Dealer",
            value=f"```{dealer['display']}```",
            inline=False,
        )

        # Player hand(s)
        for hand in gs["hands"]:
            marker = " \u25C0" if hand["is_current"] else ""
            doubled = " (Doubled)" if hand["is_doubled"] else ""
            hand_num = f" #{hand['index'] + 1}" if len(gs["hands"]) > 1 else ""
            name = f"Your Hand{hand_num}{doubled}{marker}"

            status = ""
            if hand["is_bust"]:
                status = " - **BUST**"
            elif hand["is_blackjack"]:
                status = " - **BLACKJACK!**"

            embed.add_field(
                name=name,
                value=f"```{hand['display']}```{status}",
                inline=False,
            )

        embed.set_footer(text=f"Bet: ${self.current_bet:,}")
        return embed

    async def _resolved_embed(self) -> discord.Embed:
        gs = self.game_state
        results = gs.get("results", [])

        embed = discord.Embed(
            title="\U0001F0CF Blackjack - Result",
            color=discord.Color.gold(),
        )

        # Show full dealer hand
        embed.add_field(
            name="Dealer",
            value=f"```{gs['dealer']['full_display']}```",
            inline=False,
        )

        # Show each hand result
        total_net = 0
        for result in results:
            outcome = result["outcome"]
            bet = result["bet"]
            multiplier = result.get("payout_multiplier", 0)
            payout = self.game.calculate_payout(bet, multiplier) if multiplier >= 0 else max(0, int(bet + bet * multiplier))
            net = payout - bet

            # Apply guild payout overrides for wins/blackjacks
            if outcome == "blackjack":
                guild_multi = await self._get_payout_multiplier("blackjack")
                payout = self.game.calculate_payout(bet, guild_multi)
                net = payout - bet
            elif outcome == "win":
                guild_multi = await self._get_payout_multiplier("win")
                payout = self.game.calculate_payout(bet, guild_multi)
                net = payout - bet

            total_net += net

            outcome_display = {
                "blackjack": "\U0001F31F BLACKJACK!",
                "win": "\u2705 Win!",
                "lose": "\u274C Loss",
                "bust": "\U0001F4A5 Bust!",
                "push": "\U0001F91D Push",
                "surrender": "\U0001F3F3 Surrender",
                "dealer_blackjack": "\u274C Dealer Blackjack",
            }.get(outcome, outcome)

            doubled = " (Doubled)" if result.get("is_doubled") else ""
            net_str = f"+${net:,}" if net > 0 else (f"-${abs(net):,}" if net < 0 else "$0")

            embed.add_field(
                name=f"{outcome_display}{doubled}",
                value=f"```{result['player_hand']}```Bet: ${bet:,} | Net: {net_str}",
                inline=False,
            )

        total_display = f"+${total_net:,}" if total_net > 0 else (f"-${abs(total_net):,}" if total_net < 0 else "$0")
        embed.set_footer(text=f"Total: {total_display}")

        return embed

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    async def _handle_place_bet(self, interaction: discord.Interaction):
        modal = BetModal("Blackjack", self.min_bet, self.max_bet, self._start_game)
        await interaction.response.send_modal(modal)

    async def _start_game(self, interaction: discord.Interaction, bet: int):
        """Validate bet, withdraw from bank, and deal."""
        from redbot.core import bank

        # Validate bet
        game = BlackjackGame(self._deck)
        valid, error = game.validate_bet(bet, self.min_bet, self.max_bet)
        if not valid:
            await MessageManager.send_temp_message(interaction, error, ephemeral=False, duration=5)
            return

        # Check balance
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

        # Withdraw bet
        try:
            await bank.withdraw_credits(self.ctx.author, bet)
        except Exception as e:
            await MessageManager.send_temp_message(
                interaction, f"Failed to withdraw bet: {e}", ephemeral=False, duration=5
            )
            return

        self.game = game
        self.current_bet = bet
        self.game_state = game.new_hand(bet)

        if self.game_state["state"] == BlackjackGame.RESOLVED:
            self._phase = "resolved"
            await self._process_results()
        else:
            self._phase = "playing"

        await self.initialize_view()
        embed = await self.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    def _make_action_callback(self, action_id: str):
        async def callback(interaction: discord.Interaction):
            await self._handle_action(interaction, action_id)
        return callback

    async def _handle_action(self, interaction: discord.Interaction, action: str):
        if not self.game or self._phase != "playing":
            return

        # For double down, withdraw additional bet
        if action == "double_down":
            from redbot.core import bank
            try:
                balance = await bank.get_balance(self.ctx.author)
                if balance < self.current_bet:
                    await MessageManager.send_temp_message(
                        interaction, f"Not enough to double. Need **${self.current_bet:,}** more.",
                        ephemeral=False, duration=5,
                    )
                    return
                await bank.withdraw_credits(self.ctx.author, self.current_bet)
            except Exception as e:
                await MessageManager.send_temp_message(
                    interaction, f"Failed to withdraw for double: {e}", ephemeral=False, duration=5
                )
                return

        # For split, withdraw additional bet for the new hand
        if action == "split":
            from redbot.core import bank
            try:
                balance = await bank.get_balance(self.ctx.author)
                if balance < self.current_bet:
                    await MessageManager.send_temp_message(
                        interaction, f"Not enough to split. Need **${self.current_bet:,}** more.",
                        ephemeral=False, duration=5,
                    )
                    return
                await bank.withdraw_credits(self.ctx.author, self.current_bet)
            except Exception as e:
                await MessageManager.send_temp_message(
                    interaction, f"Failed to withdraw for split: {e}", ephemeral=False, duration=5
                )
                return

        action_methods = {
            "hit": self.game.hit,
            "stand": self.game.stand,
            "double_down": self.game.double_down,
            "split": self.game.split,
            "surrender": self.game.surrender,
        }

        method = action_methods.get(action)
        if method:
            self.game_state = method()

        if self.game_state["state"] == BlackjackGame.RESOLVED:
            self._phase = "resolved"
            await self._process_results()

        await self.initialize_view()
        embed = await self.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _handle_play_again(self, interaction: discord.Interaction):
        """Play again with the same bet — re-withdraw and deal."""
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
                interaction, f"You don't have enough. Balance: **${balance:,}**",
                ephemeral=False, duration=5,
            )
            return

        try:
            await bank.withdraw_credits(self.ctx.author, self.current_bet)
        except Exception as e:
            await MessageManager.send_temp_message(
                interaction, f"Failed to withdraw bet: {e}", ephemeral=False, duration=5
            )
            return

        self.game = BlackjackGame(self._deck)
        self.game_state = self.game.new_hand(self.current_bet)

        if self.game_state["state"] == BlackjackGame.RESOLVED:
            self._phase = "resolved"
            await self._process_results()
        else:
            self._phase = "playing"

        await self.initialize_view()
        embed = await self.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _handle_change_bet(self, interaction: discord.Interaction):
        self._phase = "betting"
        self.game = None
        self.game_state = None
        await self.initialize_view()
        embed = await self.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _handle_back(self, interaction: discord.Interaction):
        """Return to the casino hub."""
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
    # Result processing
    # ------------------------------------------------------------------

    async def _process_results(self):
        """Process game results — deposit winnings and record stats."""
        from redbot.core import bank

        if not self.game_state:
            return

        results = self.game_state.get("results", [])
        total_payout = 0
        any_won = False
        any_push = False
        any_blackjack = False

        for result in results:
            outcome = result["outcome"]
            bet = result["bet"]
            multiplier = result.get("payout_multiplier", 0)

            # Apply guild payout overrides
            if outcome == "blackjack":
                multiplier = await self._get_payout_multiplier("blackjack")
                any_blackjack = True
                any_won = True
            elif outcome == "win":
                multiplier = await self._get_payout_multiplier("win")
                any_won = True
            elif outcome == "push":
                any_push = True
            elif outcome == "surrender":
                pass  # surrender multiplier is fixed at -0.5

            payout = self.game.calculate_payout(bet, multiplier)
            total_payout += payout

        # Deposit total payout back to player
        if total_payout > 0:
            try:
                await bank.deposit_credits(self.ctx.author, total_payout)
            except Exception as e:
                logger.error(f"Failed to deposit blackjack payout: {e}")

        # Record stats
        total_bet = sum(r["bet"] for r in results)
        await self.cog.stats_manager.record_game(
            user_id=self.ctx.author.id,
            game="blackjack",
            bet=total_bet,
            payout=total_payout,
            won=any_won,
            is_push=any_push and not any_won,
            is_blackjack=any_blackjack,
        )

        # Log payout
        net = total_payout - total_bet
        if abs(net) > 0:
            outcome_str = "blackjack" if any_blackjack else ("win" if any_won else ("push" if any_push else "loss"))
            await self.cog.payout_log.log_payout(
                guild_id=self.ctx.guild.id,
                user_id=self.ctx.author.id,
                game="blackjack",
                bet=total_bet,
                payout=total_payout,
                result=outcome_str,
            )

    async def _get_payout_multiplier(self, outcome: str) -> float:
        """Get the guild-configured payout multiplier for a blackjack outcome."""
        guild_settings = await self.cog.config_manager.get_guild_settings(self.ctx.guild.id)
        if guild_settings.success:
            bj_payouts = guild_settings.data.get("payout_multipliers", {}).get("blackjack", {})
            if isinstance(bj_payouts, dict):
                return bj_payouts.get(outcome, 1.0)
        return 1.0
