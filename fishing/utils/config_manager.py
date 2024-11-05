import logging
from typing import Dict, Any, Optional, TypeVar, Generic, List, Union
from dataclasses import dataclass
from contextlib import asynccontextmanager
from redbot.core import Config
from .logging_config import get_logger
from ..data.fishing_data import DEFAULT_USER_DATA, DEFAULT_GLOBAL_SETTINGS

T = TypeVar('T')

@dataclass
class ConfigResult(Generic[T]):
    """Wrapper for configuration operation results with enhanced error tracking"""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    error_code: Optional[str] = None

class ConfigManager:
    """Enhanced configuration management system with improved validation"""
    
    def __init__(self, bot, identifier: int):
        self.config = Config.get_conf(None, identifier=identifier)
        self.logger = get_logger('config')
        self._cache = {}
        self._register_defaults()
        
    def _register_defaults(self):
        """Register default configurations using constants from fishing_data"""
        self.config.register_user(**DEFAULT_USER_DATA)
        self.config.register_global(**DEFAULT_GLOBAL_SETTINGS)
        self.logger.debug("Registered default configurations")

    async def invalidate_cache(self, key: Optional[str] = None):
        """
        Invalidate specific cache key or entire cache.
        
        Args:
            key: Optional specific cache key to invalidate. If None, clears entire cache.
        """
        try:
            self.logger.debug(f"Invalidating cache{'key: ' + key if key else ' (all)'}")
            if key:
                self._cache.pop(key, None)
            else:
                self._cache.clear()
                
        except Exception as e:
            self.logger.error(f"Error in invalidate_cache: {e}")
    
    async def refresh_cache(self, user_id: int) -> ConfigResult[bool]:
        """
        Force refresh of user data cache.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            ConfigResult[bool]: Success status
        """
        try:
            self.logger.debug(f"Refreshing cache for user {user_id}")
            cache_key = f"user_{user_id}"
            
            # Get fresh data from config
            data = await self.config.user_from_id(user_id).all()
            
            # Validate the data
            validated_data = await self._validate_user_data(data)
            
            # Update cache
            self._cache[cache_key] = validated_data
            
            self.logger.debug(f"Cache refreshed for user {user_id}")
            return ConfigResult(True, True)
            
        except Exception as e:
            self.logger.error(f"Error in refresh_cache: {e}")
            return ConfigResult(False, error=str(e), error_code="CACHE_ERROR")
    
    async def _validate_dictionary_merge(
        self,
        current: Dict[str, Any],
        updates: Dict[str, Any],
        path: str = ""
    ) -> Dict[str, Any]:
        """
        Recursively merge dictionaries while validating types and structures.
        
        Args:
            current: Current dictionary
            updates: Dictionary with updates
            path: Current path for logging
            
        Returns:
            Dict[str, Any]: Merged dictionary
        """
        try:
            result = current.copy()
            
            for key, new_value in updates.items():
                current_path = f"{path}.{key}" if path else key
                
                if key not in current:
                    self.logger.warning(f"Adding new key at {current_path}")
                    result[key] = new_value
                    continue
                    
                current_value = current[key]
                
                # Handle nested dictionaries
                if isinstance(current_value, dict) and isinstance(new_value, dict):
                    result[key] = await self._validate_dictionary_merge(
                        current_value,
                        new_value,
                        current_path
                    )
                    continue
                    
                # Handle lists
                if isinstance(current_value, list) and isinstance(new_value, list):
                    result[key] = new_value
                    continue
                    
                # Handle type mismatches
                if type(current_value) != type(new_value):
                    self.logger.error(
                        f"Type mismatch at {current_path}: "
                        f"Expected {type(current_value)}, got {type(new_value)}"
                    )
                    continue
                    
                result[key] = new_value
                
            return result
            
        except Exception as e:
            self.logger.error(f"Error in dictionary merge: {e}")
            raise

    async def _validate_user_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and repair user data structure with enhanced error handling.
        
        Args:
            data: User data to validate
            
        Returns:
            Dict[str, Any]: Validated and repaired data
        """
        try:
            if not data:
                self.logger.debug("Empty user data, returning defaults")
                return DEFAULT_USER_DATA.copy()
                
            validated = {}
            
            # Validate inventory
            if not isinstance(data.get("inventory", []), list):
                self.logger.warning("Invalid inventory format, resetting to default")
                validated["inventory"] = []
            else:
                validated["inventory"] = data["inventory"]
                
            # Validate bait dictionary
            if not isinstance(data.get("bait", {}), dict):
                self.logger.warning("Invalid bait format, resetting to default")
                validated["bait"] = {}
            else:
                validated["bait"] = {
                    str(k): int(v)
                    for k, v in data["bait"].items()
                    if isinstance(v, (int, float)) and v > 0
                }
                
            # Validate purchased rods
            if not isinstance(data.get("purchased_rods", {}), dict):
                self.logger.warning("Invalid purchased_rods format, resetting to default")
                validated["purchased_rods"] = {"Basic Rod": True}
            else:
                validated["purchased_rods"] = {
                    str(k): bool(v)
                    for k, v in data["purchased_rods"].items()
                }
                
            # Ensure Basic Rod is always available
            validated["purchased_rods"]["Basic Rod"] = True
            
            # Validate numeric fields
            for field in ["total_value", "fish_caught", "junk_caught", "level", "experience"]:
                try:
                    if field == "experience":
                        validated[field] = max(0, int(data.get(field, 0)))
                        self.logger.debug(f"Validated experience value: {validated[field]}")
                    else:
                        validated[field] = max(0, int(data.get(field, 0)))
                except (ValueError, TypeError):
                    self.logger.warning(f"Invalid {field} value, resetting to 0")
                    validated[field] = 0
                    
            # Validate string fields with defaults
            validated["rod"] = str(data.get("rod", "Basic Rod"))
            validated["current_location"] = str(data.get("current_location", "Pond"))
            validated["equipped_bait"] = data.get("equipped_bait")
            
            # Validate settings
            settings = data.get("settings", {})
                    
            if not isinstance(settings, dict):
                self.logger.warning("Invalid settings format, resetting to default")
                validated["settings"] = DEFAULT_USER_DATA["settings"].copy()
            else:
                validated["settings"] = {
                    "notifications": bool(settings.get("notifications", True)),
                    "auto_sell": bool(settings.get("auto_sell", False))
                }
                
            # Validate equipped bait exists in inventory
            if validated["equipped_bait"] and validated["equipped_bait"] not in validated["bait"]:
                self.logger.warning("Equipped bait not in inventory, resetting")
                validated["equipped_bait"] = None
                
            # Validate rod exists in purchased rods
            if validated["rod"] not in validated["purchased_rods"]:
                self.logger.warning("Invalid rod equipped, resetting to Basic Rod")
                validated["rod"] = "Basic Rod"
                
            # Log the final validated experience value
            self.logger.debug(f"Final validated experience value: {validated.get('experience', 0)}")
                
            return validated
            
        except Exception as e:
            self.logger.error(f"Error in user data validation: {e}")
            return DEFAULT_USER_DATA.copy()

    async def get_user_data(self, user_id: int) -> ConfigResult[Dict[str, Any]]:
        """
        Get user data with enhanced validation and caching.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            ConfigResult containing user data or error information
        """
        try:
            cache_key = f"user_{user_id}"
            
            # Check cache first
            if cache_key in self._cache:
                return ConfigResult(True, self._cache[cache_key])
                
            # Fetch data from config
            try:
                data = await self.config.user_from_id(user_id).all()
            except Exception as e:
                self.logger.error(f"Error fetching user data: {e}")
                return ConfigResult(False, error=str(e), error_code="FETCH_ERROR")
                
            # Validate and repair data
            try:
                validated_data = await self._validate_user_data(data)
            except Exception as e:
                self.logger.error(f"Error validating user data: {e}")
                return ConfigResult(False, error=str(e), error_code="VALIDATION_ERROR")
                
            # Update cache
            self._cache[cache_key] = validated_data
            
            return ConfigResult(True, validated_data)
            
        except Exception as e:
            self.logger.error(f"Error in get_user_data: {e}")
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    async def update_user_data(
        self,
        user_id: int,
        updates: Dict[str, Any],
        fields: Optional[List[str]] = None
    ) -> ConfigResult[bool]:
        """
        Update user data with enhanced validation and field filtering.
        
        Args:
            user_id: Discord user ID
            updates: Dictionary of updates
            fields: Optional list of fields to update
            
        Returns:
            ConfigResult indicating success or failure
        """
        try:
            self.logger.debug(f"Updating user data for {user_id}")
            self.logger.debug(f"Updates: {updates}")
            self.logger.debug(f"Fields: {fields}")
            
            # Get current data
            current_result = await self.get_user_data(user_id)
            if not current_result.success:
                self.logger.error(f"Failed to get current data: {current_result.error}")
                return ConfigResult(False, error="Failed to get current data", error_code="GET_ERROR")
                
            current_data = current_result.data
            self.logger.debug(f"Current data: {current_data}")
            
            # Create working copy
            update_data = current_data.copy()
            
            # Process updates
            if fields:
                # Update only specified fields
                for field in fields:
                    if field not in updates:
                        continue
                        
                    if field == "experience":
                        # Special handling for experience to ensure it's numeric
                        try:
                            update_data["experience"] = int(updates["experience"])
                            self.logger.debug(f"Updated experience to: {update_data['experience']}")
                        except (ValueError, TypeError) as e:
                            self.logger.error(f"Invalid experience value: {updates['experience']}: {e}")
                            return ConfigResult(False, error="Invalid experience value", error_code="VALIDATION_ERROR")
                    elif field == "bait":
                        # Special handling for bait dictionary
                        current_bait = update_data.get("bait", {})
                        new_bait = updates["bait"]
                        if isinstance(new_bait, dict):
                            merged_bait = await self._validate_dictionary_merge(
                                current_bait,
                                new_bait,
                                "bait"
                            )
                            update_data["bait"] = merged_bait
                    elif isinstance(updates[field], dict):
                        if not isinstance(update_data.get(field), dict):
                            update_data[field] = {}
                        update_data[field] = await self._validate_dictionary_merge(
                            update_data[field],
                            updates[field],
                            field
                        )
                    else:
                        update_data[field] = updates[field]
            else:
                # Update all fields
                for key, value in updates.items():
                    if isinstance(value, dict):
                        if not isinstance(update_data.get(key), dict):
                            update_data[key] = {}
                        update_data[key] = await self._validate_dictionary_merge(
                            update_data[key],
                            value,
                            key
                        )
                    else:
                        update_data[key] = value
                        
            # Validate updated data
            validated_data = await self._validate_user_data(update_data)
            self.logger.debug(f"Validated data: {validated_data}")
            
            # Save to config
            group = self.config.user_from_id(user_id)
            for key, value in validated_data.items():
                if key in updates or not fields:
                    try:
                        await group.set_raw(key, value=value)
                        self.logger.debug(f"Saved {key}: {value}")
                    except Exception as e:
                        self.logger.error(f"Error saving {key}: {e}")
                        return ConfigResult(False, error=f"Failed to save {key}", error_code="SAVE_ERROR")
                        
            # Invalidate cache
            await self.invalidate_cache(f"user_{user_id}")
            
            # Verify update
            verify_result = await self.get_user_data(user_id)
            if not verify_result.success:
                self.logger.error("Failed to verify update")
                return ConfigResult(False, error="Failed to verify update", error_code="VERIFY_ERROR")
                
            self.logger.debug(f"Successfully updated user data: {verify_result.data}")
            return ConfigResult(True, True)
            
        except Exception as e:
            self.logger.error(f"Error in update_user_data: {e}", exc_info=True)
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    async def get_global_setting(self, key: str) -> ConfigResult[Any]:
        """Get global setting with caching"""
        try:
            cache_key = f"global_{key}"
            if cache_key in self._cache:
                return ConfigResult(True, self._cache[cache_key])
                
            try:
                value = await self.config.get_raw(key)
                self._cache[cache_key] = value
                return ConfigResult(True, value)
            except Exception as e:
                return ConfigResult(False, error=str(e), error_code="FETCH_ERROR")
                
        except Exception as e:
            self.logger.error(f"Error in get_global_setting: {e}")
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    async def update_global_setting(self, key: str, value: Any) -> ConfigResult[bool]:
        """Update global setting with validation"""
        try:
            # Validate value based on key
            if key == "bait_stock" and not isinstance(value, dict):
                return ConfigResult(False, error="Invalid bait stock format", error_code="VALIDATION_ERROR")
                
            await self.config.set_raw(key, value=value)
            await self.invalidate_cache(f"global_{key}")
            return ConfigResult(True, True)
            
        except Exception as e:
            self.logger.error(f"Error in update_global_setting: {e}")
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    async def get_all_global_settings(self) -> ConfigResult[Dict[str, Any]]:
        """Get all global settings with caching"""
        try:
            if "global_all" in self._cache:
                return ConfigResult(True, self._cache["global_all"])
                
            data = await self.config.all()
            self._cache["global_all"] = data
            return ConfigResult(True, data)
            
        except Exception as e:
            self.logger.error(f"Error in get_all_global_settings: {e}")
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    async def reset_user_data(self, user_id: int) -> ConfigResult[bool]:
        """Reset user data to defaults with validation"""
        try:
            self.logger.debug(f"Resetting user data for {user_id}")
            
            # Clear existing data first
            await self.config.user_from_id(user_id).clear()
            
            # Create fresh default data and validate it
            default_data = DEFAULT_USER_DATA.copy()
            validated_data = await self._validate_user_data(default_data)
            
            # Set the validated data
            group = self.config.user_from_id(user_id)
            for key, value in validated_data.items():
                try:
                    await group.set_raw(key, value=value)
                    self.logger.debug(f"Reset {key} to default: {value}")
                except Exception as e:
                    self.logger.error(f"Error resetting {key}: {e}")
                    return ConfigResult(False, error=f"Failed to reset {key}", error_code="RESET_ERROR")
            
            # Invalidate cache
            await self.invalidate_cache(f"user_{user_id}")
            
            # Verify reset
            verify_result = await self.get_user_data(user_id)
            if not verify_result.success:
                self.logger.error("Failed to verify reset")
                return ConfigResult(False, error="Failed to verify reset", error_code="VERIFY_ERROR")
                
            self.logger.debug(f"Successfully reset user data: {verify_result.data}")
            return ConfigResult(True, True)
            
        except Exception as e:
            self.logger.error(f"Error in reset_user_data: {e}", exc_info=True)
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    async def refresh_cache(self, user_id: int) -> ConfigResult[bool]:
        """Force refresh of user data cache"""
        try:
            cache_key = f"user_{user_id}"
            data = await self.config.user_from_id(user_id).all()
            validated_data = await self._validate_user_data(data)
            self._cache[cache_key] = validated_data
            return ConfigResult(True, True)
            
        except Exception as e:
            self.logger.error(f"Error in refresh_cache: {e}")
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    @asynccontextmanager
    async def config_transaction(self):
        """Context manager for handling configuration transactions"""
        transaction_cache = {}
        try:
            yield transaction_cache
            # On successful completion, apply changes
            for key, value in transaction_cache.items():
                if key.startswith("user_"):
                    user_id = int(key.split("_")[1])
                    await self.update_user_data(user_id, value)
                elif key.startswith("global_"):
                    setting_key = key.replace("global_", "")
                    await self.update_global_setting(setting_key, value)
        except Exception as e:
            self.logger.error(f"Transaction failed: {e}")
            raise
        finally:
            transaction_cache.clear()
