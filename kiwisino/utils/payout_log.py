# utils/payout_log.py

import time
from typing import Dict, Any, List, Optional
from .config_manager import ConfigManager, ConfigResult
from .logging_config import get_logger


class PayoutLog:
    """Admin audit trail for casino payouts (per-guild).

    Stores the most recent entries (capped at ``payout_log_max``) in the
    guild config.  Each entry records the game, player, bet, payout, and
    whether a jackpot was involved.
    """

    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.logger = get_logger('payout_log')

    async def log_payout(
        self,
        guild_id: int,
        user_id: int,
        game: str,
        bet: int,
        payout: int,
        result: str,
        jackpot: bool = False,
    ) -> ConfigResult[bool]:
        """Append a payout entry to the log.

        Args:
            guild_id: Discord guild ID.
            user_id: Discord user ID.
            game: Game name.
            bet: Amount wagered.
            payout: Amount returned to player.
            result: Outcome string (e.g. "win", "blackjack", "jackpot").
            jackpot: Whether this was a jackpot win.
        """
        try:
            entry = {
                "timestamp": int(time.time()),
                "user_id": user_id,
                "game": game,
                "bet": bet,
                "payout": payout,
                "net": payout - bet,
                "result": result,
                "jackpot": jackpot,
            }

            settings = await self.config.get_guild_settings(guild_id)
            if not settings.success:
                return ConfigResult(False, error=settings.error)

            log = settings.data.get("payout_log", [])
            max_entries = settings.data.get("payout_log_max", 500)

            log.append(entry)
            # Trim to max size
            if len(log) > max_entries:
                log = log[-max_entries:]

            await self.config.update_guild_setting(guild_id, "payout_log", log)
            return ConfigResult(True, True)

        except Exception as e:
            self.logger.error(f"Error logging payout: {e}")
            return ConfigResult(False, error=str(e))

    async def get_recent(
        self, guild_id: int, limit: int = 50
    ) -> ConfigResult[List[Dict[str, Any]]]:
        """Get the most recent payout log entries."""
        try:
            result = await self.config.get_guild_setting(guild_id, "payout_log")
            if not result.success:
                return ConfigResult(False, error=result.error)

            log = result.data or []
            # Return newest first
            return ConfigResult(True, list(reversed(log[-limit:])))

        except Exception as e:
            self.logger.error(f"Error getting payout log: {e}")
            return ConfigResult(False, error=str(e))

    async def get_user_log(
        self, guild_id: int, user_id: int, limit: int = 20
    ) -> ConfigResult[List[Dict[str, Any]]]:
        """Get recent payout log entries for a specific user."""
        try:
            result = await self.config.get_guild_setting(guild_id, "payout_log")
            if not result.success:
                return ConfigResult(False, error=result.error)

            log = result.data or []
            user_entries = [e for e in log if e.get("user_id") == user_id]
            return ConfigResult(True, list(reversed(user_entries[-limit:])))

        except Exception as e:
            self.logger.error(f"Error getting user payout log: {e}")
            return ConfigResult(False, error=str(e))
