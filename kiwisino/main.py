# main.py

import discord
from redbot.core import commands, bank
from redbot.core.bot import Red
from .utils.logging_config import get_logger, KiwisinoLoggerManager
from .utils.config_manager import ConfigManager
from .utils.timeout_manager import KiwisinoTimeoutManager
from .utils.stats_manager import StatsManager
from .utils.jackpot_manager import JackpotManager
from .utils.payout_log import PayoutLog
from .data.casino_data import GAME_NAMES


class Kiwisino(commands.Cog):
    """A casino gambling cog for Red-DiscordBot."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.logger = get_logger('main')
        self.logger.info("Initializing Kiwisino cog")

        # Config — unique identifier, separate from fishing cog
        self.config_manager = ConfigManager(bot, identifier=987654321)

        # Managers
        self.stats_manager = StatsManager(self.config_manager)
        self.jackpot_manager = JackpotManager(self.config_manager)
        self.payout_log = PayoutLog(self.config_manager)

        # Track active sessions (user_id -> view)
        self._active_sessions = {}

        # Persistent blackjack decks per guild
        self._blackjack_decks = {}

    def cog_unload(self):
        """Clean up singletons on cog unload to avoid stale state on reload."""
        self.logger.info("Unloading Kiwisino cog")
        KiwisinoTimeoutManager.reset()
        KiwisinoLoggerManager.reset()
        self._active_sessions.clear()
        self._blackjack_decks.clear()

    # ------------------------------------------------------------------
    # Hub factory
    # ------------------------------------------------------------------

    def create_hub(self, ctx: commands.Context, user_data: dict):
        """Create a CasinoHubView and register it as the active session."""
        from .ui.hub import CasinoHubView
        view = CasinoHubView(self, ctx, user_data)
        self._active_sessions[ctx.author.id] = view
        return view

    # ------------------------------------------------------------------
    # User command
    # ------------------------------------------------------------------

    @commands.command(name="casino")
    @commands.guild_only()
    async def kiwisino_cmd(self, ctx: commands.Context):
        """Open the Kiwisino casino hub."""
        user_id = ctx.author.id

        # Active session guard
        if user_id in self._active_sessions:
            msg = await ctx.send("You already have an active casino session!")
            try:
                await msg.delete(delay=5)
            except discord.NotFound:
                pass
            return

        # Ensure user data exists
        result = await self.config_manager.get_user_data(user_id)
        if not result.success:
            await ctx.send("Failed to load your casino data. Please try again.")
            return

        hub = self.create_hub(ctx, result.data)
        await hub.setup()
        await hub.start()

    # ------------------------------------------------------------------
    # Admin commands
    # ------------------------------------------------------------------

    @commands.group(name="casinoadmin", aliases=["cadmin"])
    @commands.admin_or_permissions(manage_guild=True)
    @commands.guild_only()
    async def casinoadmin(self, ctx: commands.Context):
        """Kiwisino admin commands."""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="Kiwisino Admin",
                description=(
                    "**Available subcommands:**\n"
                    "`toggle <game>` — Enable/disable a game\n"
                    "`betlimit <game> <min> <max>` — Set bet limits\n"
                    "`payout <game> <type> <multiplier>` — Set payout multiplier\n"
                    "`jackpot view` — View current jackpot\n"
                    "`jackpot reset` — Reset jackpot to seed\n"
                    "`jackpot seed <amount>` — Set jackpot seed\n"
                    "`payoutlog [count]` — View payout log\n"
                    "`payoutlog user <member> [count]` — View user's log\n"
                    "`stats <member>` — View a user's stats\n"
                    "`resetstats <member>` — Reset a user's stats"
                ),
                color=discord.Color.gold(),
            )
            await ctx.send(embed=embed)

    @casinoadmin.command(name="toggle")
    async def toggle_game(self, ctx: commands.Context, game: str):
        """Enable or disable a game."""
        game = game.lower()
        if game not in GAME_NAMES:
            await ctx.send(f"Unknown game. Valid games: {', '.join(GAME_NAMES)}")
            return

        result = await self.config_manager.get_guild_settings(ctx.guild.id)
        if not result.success:
            await ctx.send("Failed to load settings.")
            return

        games_enabled = result.data.get("games_enabled", {})
        current = games_enabled.get(game, True)
        games_enabled[game] = not current

        await self.config_manager.update_guild_setting(ctx.guild.id, "games_enabled", games_enabled)
        status = "enabled" if games_enabled[game] else "disabled"
        await ctx.send(f"**{game.title()}** has been **{status}**.")

    @casinoadmin.command(name="betlimit")
    async def set_bet_limit(self, ctx: commands.Context, game: str, min_bet: int, max_bet: int):
        """Set the bet limits for a game."""
        game = game.lower()
        if game not in GAME_NAMES:
            await ctx.send(f"Unknown game. Valid games: {', '.join(GAME_NAMES)}")
            return

        if min_bet < 1:
            await ctx.send("Minimum bet must be at least 1.")
            return
        if max_bet < min_bet:
            await ctx.send("Maximum bet must be greater than or equal to minimum bet.")
            return

        result = await self.config_manager.get_guild_settings(ctx.guild.id)
        if not result.success:
            await ctx.send("Failed to load settings.")
            return

        bet_limits = result.data.get("bet_limits", {})
        bet_limits[game] = {"min": min_bet, "max": max_bet}

        await self.config_manager.update_guild_setting(ctx.guild.id, "bet_limits", bet_limits)
        await ctx.send(f"**{game.title()}** bet limits set to **${min_bet:,}** - **${max_bet:,}**.")

    @casinoadmin.command(name="payout")
    async def set_payout(self, ctx: commands.Context, game: str, payout_type: str, multiplier: float):
        """Set a payout multiplier for a game.

        For blackjack: `payout blackjack blackjack 1.5` (natural 21 pays 3:2)
        For coinflip: `payout coinflip win 1.95`
        For slots: `payout slots scale 1.0` (overall slots payout scalar)
        """
        game = game.lower()
        if game not in GAME_NAMES:
            await ctx.send(f"Unknown game. Valid games: {', '.join(GAME_NAMES)}")
            return

        if multiplier < 0:
            await ctx.send("Multiplier must be non-negative.")
            return

        result = await self.config_manager.get_guild_settings(ctx.guild.id)
        if not result.success:
            await ctx.send("Failed to load settings.")
            return

        payouts = result.data.get("payout_multipliers", {})

        if game == "blackjack":
            bj_payouts = payouts.get("blackjack", {})
            if not isinstance(bj_payouts, dict):
                bj_payouts = {}
            valid_types = ["blackjack", "win", "push", "insurance", "surrender"]
            if payout_type not in valid_types:
                await ctx.send(f"Valid blackjack payout types: {', '.join(valid_types)}")
                return
            bj_payouts[payout_type] = multiplier
            payouts["blackjack"] = bj_payouts
        elif game == "coinflip":
            payouts["coinflip"] = multiplier
        elif game == "slots":
            payouts["slots"] = multiplier

        await self.config_manager.update_guild_setting(ctx.guild.id, "payout_multipliers", payouts)
        await ctx.send(f"**{game.title()}** payout `{payout_type}` set to **{multiplier}x**.")

    @casinoadmin.group(name="jackpot")
    async def jackpot_group(self, ctx: commands.Context):
        """Jackpot management commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Use `jackpot view`, `jackpot reset`, or `jackpot seed <amount>`.")

    @jackpot_group.command(name="view")
    async def jackpot_view(self, ctx: commands.Context):
        """View the current jackpot amount."""
        result = await self.jackpot_manager.get_current(ctx.guild.id)
        if result.success:
            await ctx.send(f"\U0001F3B0 Current jackpot: **${result.data:,}**")
        else:
            await ctx.send("Failed to load jackpot data.")

    @jackpot_group.command(name="reset")
    async def jackpot_reset(self, ctx: commands.Context):
        """Reset the jackpot to its seed amount."""
        result = await self.jackpot_manager.reset(ctx.guild.id)
        if result.success:
            seed_result = await self.config_manager.get_guild_setting(ctx.guild.id, "jackpot")
            seed = seed_result.data.get("seed_amount", 1000) if seed_result.success else 1000
            await ctx.send(f"Jackpot reset to seed amount: **${seed:,}**")
        else:
            await ctx.send("Failed to reset jackpot.")

    @jackpot_group.command(name="seed")
    async def jackpot_seed(self, ctx: commands.Context, amount: int):
        """Set the jackpot seed amount."""
        if amount < 0:
            await ctx.send("Seed amount must be non-negative.")
            return
        result = await self.jackpot_manager.set_seed(ctx.guild.id, amount)
        if result.success:
            await ctx.send(f"Jackpot seed set to **${amount:,}**.")
        else:
            await ctx.send("Failed to set jackpot seed.")

    @casinoadmin.command(name="payoutlog")
    async def view_payout_log(self, ctx: commands.Context, count: int = 20):
        """View the recent payout log."""
        result = await self.payout_log.get_recent(ctx.guild.id, limit=count)
        if not result.success or not result.data:
            await ctx.send("No payout log entries.")
            return

        lines = []
        for entry in result.data[:20]:  # cap display at 20
            import datetime
            ts = datetime.datetime.fromtimestamp(entry["timestamp"]).strftime("%m/%d %H:%M")
            net = entry.get("net", entry["payout"] - entry["bet"])
            net_str = f"+${net:,}" if net >= 0 else f"-${abs(net):,}"
            jp = " \U0001F31F" if entry.get("jackpot") else ""
            lines.append(
                f"`{ts}` {entry['game']} | <@{entry['user_id']}> | "
                f"Bet ${entry['bet']:,} | Net {net_str}{jp}"
            )

        embed = discord.Embed(
            title="Payout Log",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await ctx.send(embed=embed)

    @casinoadmin.command(name="stats")
    async def view_user_stats(self, ctx: commands.Context, member: discord.Member):
        """View a user's casino stats."""
        result = await self.stats_manager.get_user_stats(member.id)
        if not result.success:
            await ctx.send("Failed to load user stats.")
            return

        data = result.data
        overall = data.get("overall", {})
        net = overall.get("net_profit", 0)
        net_display = f"+${net:,}" if net >= 0 else f"-${abs(net):,}"

        embed = discord.Embed(
            title=f"Casino Stats — {member.display_name}",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Overall",
            value=(
                f"Wagered: ${overall.get('total_wagered', 0):,}\n"
                f"Returned: ${overall.get('total_won', 0):,}\n"
                f"Net: {net_display}\n"
                f"Biggest Win: ${overall.get('biggest_win', 0):,}"
            ),
            inline=False,
        )

        for game in GAME_NAMES:
            gs = data.get("stats", {}).get(game, {})
            played = gs.get("games_played", 0)
            won = gs.get("games_won", 0)
            embed.add_field(
                name=game.title(),
                value=f"Played: {played} | Won: {won}",
                inline=True,
            )

        await ctx.send(embed=embed)

    @casinoadmin.command(name="resetstats")
    @commands.is_owner()
    async def reset_user_stats(self, ctx: commands.Context, member: discord.Member):
        """Reset a user's casino stats (bot owner only)."""
        result = await self.config_manager.reset_user_data(member.id)
        if result.success:
            await ctx.send(f"Casino stats for **{member.display_name}** have been reset.")
        else:
            await ctx.send("Failed to reset stats.")
