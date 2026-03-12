# utils/config_manager.py

from typing import Dict, Any, Optional, TypeVar, Generic, List
from dataclasses import dataclass
from contextlib import asynccontextmanager
from redbot.core import Config
from .logging_config import get_logger
from ..data.casino_data import DEFAULT_USER_DATA, DEFAULT_GUILD_SETTINGS, GAME_NAMES

T = TypeVar('T')


@dataclass
class ConfigResult(Generic[T]):
    """Wrapper for configuration operation results."""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


class ConfigManager:
    """Configuration management for the Kiwisino cog.

    Uses guild-level settings (bet limits, payouts, jackpot, toggles) rather
    than global settings, so each server can configure its own casino.
    User data (stats) is global (per-user across all guilds).
    """

    def __init__(self, bot, identifier: int):
        self.config = Config.get_conf(None, identifier=identifier, cog_name="Kiwisino")
        self.logger = get_logger('config')
        self._cache = {}
        self._register_defaults()

    def _register_defaults(self):
        self.config.register_user(**DEFAULT_USER_DATA)
        self.config.register_guild(**DEFAULT_GUILD_SETTINGS)
        self.logger.debug("Registered default configurations")

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    async def invalidate_cache(self, key: Optional[str] = None):
        try:
            if key:
                self._cache.pop(key, None)
            else:
                self._cache.clear()
        except Exception as e:
            self.logger.error(f"Error in invalidate_cache: {e}")

    # ------------------------------------------------------------------
    # User data (stats)
    # ------------------------------------------------------------------

    async def _validate_user_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and repair user stats structure."""
        try:
            if not data:
                return _deep_copy_defaults()

            validated = {}

            # Validate per-game stats
            stats = data.get("stats", {})
            if not isinstance(stats, dict):
                stats = {}

            validated_stats = {}
            for game in GAME_NAMES:
                game_defaults = DEFAULT_USER_DATA["stats"][game]
                game_stats = stats.get(game, {})
                if not isinstance(game_stats, dict):
                    game_stats = {}

                validated_game = {}
                for field, default_val in game_defaults.items():
                    try:
                        validated_game[field] = max(0, int(game_stats.get(field, default_val)))
                    except (ValueError, TypeError):
                        validated_game[field] = default_val
                validated_stats[game] = validated_game

            validated["stats"] = validated_stats

            # Validate overall stats
            overall = data.get("overall", {})
            if not isinstance(overall, dict):
                overall = {}

            validated_overall = {}
            for field, default_val in DEFAULT_USER_DATA["overall"].items():
                if field == "biggest_win_game":
                    validated_overall[field] = str(overall.get(field, default_val))
                elif field == "net_profit":
                    # net_profit can be negative
                    try:
                        validated_overall[field] = int(overall.get(field, default_val))
                    except (ValueError, TypeError):
                        validated_overall[field] = default_val
                else:
                    try:
                        validated_overall[field] = max(0, int(overall.get(field, default_val)))
                    except (ValueError, TypeError):
                        validated_overall[field] = default_val

            validated["overall"] = validated_overall
            return validated

        except Exception as e:
            self.logger.error(f"Error validating user data: {e}")
            return _deep_copy_defaults()

    async def get_user_data(self, user_id: int) -> ConfigResult[Dict[str, Any]]:
        try:
            cache_key = f"user_{user_id}"
            if cache_key in self._cache:
                return ConfigResult(True, self._cache[cache_key])

            data = await self.config.user_from_id(user_id).all()
            validated = await self._validate_user_data(data)
            self._cache[cache_key] = validated
            return ConfigResult(True, validated)
        except Exception as e:
            self.logger.error(f"Error in get_user_data: {e}")
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    async def update_user_data(
        self, user_id: int, updates: Dict[str, Any]
    ) -> ConfigResult[bool]:
        try:
            current_result = await self.get_user_data(user_id)
            if not current_result.success:
                return ConfigResult(False, error="Failed to get current data", error_code="GET_ERROR")

            merged = _deep_merge(current_result.data, updates)
            validated = await self._validate_user_data(merged)

            group = self.config.user_from_id(user_id)
            for key, value in validated.items():
                await group.set_raw(key, value=value)

            await self.invalidate_cache(f"user_{user_id}")
            return ConfigResult(True, True)
        except Exception as e:
            self.logger.error(f"Error in update_user_data: {e}", exc_info=True)
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    async def reset_user_data(self, user_id: int) -> ConfigResult[bool]:
        try:
            await self.config.user_from_id(user_id).clear()
            await self.invalidate_cache(f"user_{user_id}")
            return ConfigResult(True, True)
        except Exception as e:
            self.logger.error(f"Error in reset_user_data: {e}")
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    # ------------------------------------------------------------------
    # Guild settings
    # ------------------------------------------------------------------

    async def get_guild_settings(self, guild_id: int) -> ConfigResult[Dict[str, Any]]:
        try:
            cache_key = f"guild_{guild_id}"
            if cache_key in self._cache:
                return ConfigResult(True, self._cache[cache_key])

            data = await self.config.guild_from_id(guild_id).all()
            self._cache[cache_key] = data
            return ConfigResult(True, data)
        except Exception as e:
            self.logger.error(f"Error in get_guild_settings: {e}")
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    async def update_guild_setting(
        self, guild_id: int, key: str, value: Any
    ) -> ConfigResult[bool]:
        try:
            await self.config.guild_from_id(guild_id).set_raw(key, value=value)
            await self.invalidate_cache(f"guild_{guild_id}")
            return ConfigResult(True, True)
        except Exception as e:
            self.logger.error(f"Error in update_guild_setting: {e}")
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    async def get_guild_setting(self, guild_id: int, key: str) -> ConfigResult[Any]:
        """Get a single guild setting by key."""
        result = await self.get_guild_settings(guild_id)
        if not result.success:
            return result
        return ConfigResult(True, result.data.get(key))

    # ------------------------------------------------------------------
    # All users (for leaderboards)
    # ------------------------------------------------------------------

    async def all_users(self) -> ConfigResult[Dict[int, Dict[str, Any]]]:
        """Get all user data for leaderboard computation."""
        try:
            all_data = await self.config.all_users()
            return ConfigResult(True, all_data)
        except Exception as e:
            self.logger.error(f"Error in all_users: {e}")
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    # ------------------------------------------------------------------
    # Transaction support
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def config_transaction(self):
        transaction_cache = {}
        try:
            yield transaction_cache
            for key, value in transaction_cache.items():
                if key.startswith("user_"):
                    user_id = int(key.split("_", 1)[1])
                    await self.update_user_data(user_id, value)
                elif key.startswith("guild_"):
                    parts = key.split("_", 2)
                    guild_id = int(parts[1])
                    setting_key = parts[2]
                    await self.update_guild_setting(guild_id, setting_key, value)
        except Exception as e:
            self.logger.error(f"Transaction failed: {e}")
            raise
        finally:
            transaction_cache.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deep_copy_defaults() -> Dict[str, Any]:
    """Return a deep copy of DEFAULT_USER_DATA."""
    import copy
    return copy.deepcopy(DEFAULT_USER_DATA)


def _deep_merge(base: Dict, updates: Dict) -> Dict:
    """Recursively merge *updates* into *base* (non-destructive)."""
    result = base.copy()
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
