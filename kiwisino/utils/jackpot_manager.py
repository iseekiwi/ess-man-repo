# utils/jackpot_manager.py

from typing import Dict, Any
from .config_manager import ConfigManager, ConfigResult
from .logging_config import get_logger


class JackpotManager:
    """Manages the progressive slots jackpot (per-guild).

    The jackpot grows by a configurable percentage of each slots bet.
    Triggered by 3x Kiwi symbols. Resets to the seed amount after payout.
    """

    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.logger = get_logger('jackpot')

    async def contribute(self, guild_id: int, bet: int) -> ConfigResult[int]:
        """Add a contribution from a slots bet to the jackpot pool.

        Args:
            guild_id: Discord guild ID.
            bet: The slots bet amount.

        Returns:
            The contribution amount added.
        """
        try:
            result = await self.config.get_guild_setting(guild_id, "jackpot")
            if not result.success:
                return ConfigResult(False, error=result.error)

            jackpot = result.data
            rate = jackpot.get("contribution_rate", 0.02)
            contribution = max(1, int(bet * rate))

            jackpot["current_amount"] = jackpot.get("current_amount", 1000) + contribution

            await self.config.update_guild_setting(guild_id, "jackpot", jackpot)
            return ConfigResult(True, contribution)

        except Exception as e:
            self.logger.error(f"Error contributing to jackpot: {e}")
            return ConfigResult(False, error=str(e))

    async def get_current(self, guild_id: int) -> ConfigResult[int]:
        """Get the current jackpot amount for a guild."""
        try:
            result = await self.config.get_guild_setting(guild_id, "jackpot")
            if not result.success:
                return ConfigResult(False, error=result.error)
            return ConfigResult(True, result.data.get("current_amount", 1000))
        except Exception as e:
            self.logger.error(f"Error getting jackpot: {e}")
            return ConfigResult(False, error=str(e))

    async def award(self, guild_id: int) -> ConfigResult[int]:
        """Award the jackpot and reset to seed amount.

        Returns the jackpot amount that was awarded.
        """
        try:
            result = await self.config.get_guild_setting(guild_id, "jackpot")
            if not result.success:
                return ConfigResult(False, error=result.error)

            jackpot = result.data
            awarded = jackpot.get("current_amount", 1000)
            jackpot["current_amount"] = jackpot.get("seed_amount", 1000)

            await self.config.update_guild_setting(guild_id, "jackpot", jackpot)
            self.logger.info(f"Jackpot awarded in guild {guild_id}: ${awarded:,}")
            return ConfigResult(True, awarded)

        except Exception as e:
            self.logger.error(f"Error awarding jackpot: {e}")
            return ConfigResult(False, error=str(e))

    async def reset(self, guild_id: int) -> ConfigResult[bool]:
        """Reset the jackpot to its seed amount (admin action)."""
        try:
            result = await self.config.get_guild_setting(guild_id, "jackpot")
            if not result.success:
                return ConfigResult(False, error=result.error)

            jackpot = result.data
            jackpot["current_amount"] = jackpot.get("seed_amount", 1000)

            await self.config.update_guild_setting(guild_id, "jackpot", jackpot)
            return ConfigResult(True, True)

        except Exception as e:
            self.logger.error(f"Error resetting jackpot: {e}")
            return ConfigResult(False, error=str(e))

    async def set_seed(self, guild_id: int, seed: int) -> ConfigResult[bool]:
        """Set the jackpot seed amount (admin action)."""
        try:
            result = await self.config.get_guild_setting(guild_id, "jackpot")
            if not result.success:
                return ConfigResult(False, error=result.error)

            jackpot = result.data
            jackpot["seed_amount"] = seed

            await self.config.update_guild_setting(guild_id, "jackpot", jackpot)
            return ConfigResult(True, True)

        except Exception as e:
            self.logger.error(f"Error setting jackpot seed: {e}")
            return ConfigResult(False, error=str(e))
