# utils/stats_manager.py

from typing import Dict, Any, List, Optional, Tuple
from .config_manager import ConfigManager, ConfigResult
from .logging_config import get_logger
from ..data.casino_data import GAME_NAMES


class StatsManager:
    """Sole authority for recording game outcomes and querying player stats.

    All stat mutations flow through ``record_game()``. Do not write stats
    elsewhere.
    """

    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.logger = get_logger('stats')

    async def record_game(
        self,
        user_id: int,
        game: str,
        bet: int,
        payout: int,
        won: bool,
        is_push: bool = False,
        is_blackjack: bool = False,
        is_jackpot: bool = False,
        jackpot_amount: int = 0,
    ) -> ConfigResult[bool]:
        """Record a completed game outcome.

        Args:
            user_id: Discord user ID.
            game: Game name (must be in GAME_NAMES).
            bet: Amount wagered.
            payout: Amount returned to player (0 if lost, bet+winnings if won).
            won: Whether the player won.
            is_push: Blackjack push (bet returned, no win/loss).
            is_blackjack: Player hit a natural blackjack.
            is_jackpot: Player hit the slots jackpot.
            jackpot_amount: Amount won from jackpot (if applicable).
        """
        if game not in GAME_NAMES:
            return ConfigResult(False, error=f"Unknown game: {game}", error_code="INVALID_GAME")

        try:
            result = await self.config.get_user_data(user_id)
            if not result.success:
                return ConfigResult(False, error=result.error, error_code="GET_ERROR")

            data = result.data
            game_stats = data["stats"][game]
            overall = data["overall"]

            net = payout - bet  # can be negative (loss) or positive (win)
            winnings = max(0, net)  # profit portion only

            # Per-game stats
            game_stats["games_played"] += 1
            game_stats["total_wagered"] += bet
            game_stats["total_won"] += payout

            if is_push:
                if game == "blackjack":
                    game_stats["games_pushed"] = game_stats.get("games_pushed", 0) + 1
            elif won:
                game_stats["games_won"] += 1
            else:
                game_stats["games_lost"] += 1

            if winnings > game_stats["biggest_win"]:
                game_stats["biggest_win"] = winnings

            # Game-specific fields
            if game == "blackjack" and is_blackjack:
                game_stats["blackjacks_hit"] = game_stats.get("blackjacks_hit", 0) + 1

            if game == "slots":
                if is_jackpot:
                    game_stats["jackpots_won"] = game_stats.get("jackpots_won", 0) + 1
                    game_stats["jackpot_total"] = game_stats.get("jackpot_total", 0) + jackpot_amount

            # Overall stats
            overall["total_wagered"] += bet
            overall["total_won"] += payout
            overall["net_profit"] += net

            if winnings > overall["biggest_win"]:
                overall["biggest_win"] = winnings
                overall["biggest_win_game"] = game

            updates = {"stats": data["stats"], "overall": overall}
            return await self.config.update_user_data(user_id, updates)

        except Exception as e:
            self.logger.error(f"Error recording game: {e}", exc_info=True)
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    async def get_user_stats(self, user_id: int) -> ConfigResult[Dict[str, Any]]:
        """Get full stats for a user."""
        return await self.config.get_user_data(user_id)

    async def get_leaderboard(
        self,
        stat_key: str = "net_profit",
        limit: int = 10,
    ) -> ConfigResult[List[Tuple[int, int]]]:
        """Get the top players by a given overall stat.

        Args:
            stat_key: Key from the ``overall`` stats dict (e.g. "net_profit",
                      "total_wagered", "biggest_win").
            limit: Number of entries to return.

        Returns:
            List of (user_id, stat_value) tuples, sorted descending.
        """
        try:
            result = await self.config.all_users()
            if not result.success:
                return ConfigResult(False, error=result.error)

            entries = []
            for user_id, user_data in result.data.items():
                overall = user_data.get("overall", {})
                value = overall.get(stat_key, 0)
                if isinstance(value, (int, float)):
                    entries.append((int(user_id), int(value)))

            entries.sort(key=lambda x: x[1], reverse=True)
            return ConfigResult(True, entries[:limit])

        except Exception as e:
            self.logger.error(f"Error getting leaderboard: {e}")
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")
