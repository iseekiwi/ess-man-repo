# utils/config_manager.py

import logging
from typing import Dict, Any, Optional, TypeVar, Generic
from dataclasses import dataclass
from contextlib import asynccontextmanager
from redbot.core import Config
from .logging_config import get_logger

T = TypeVar('T')

@dataclass
class ConfigResult(Generic[T]):
    """Wrapper for configuration operation results"""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None

class ConfigManager:
    """Enhanced configuration management system"""
    def __init__(self, bot, identifier: int):
        self.config = Config.get_conf(None, identifier=identifier)
        self.logger = get_logger('config')
        self._cache = {}
        self._register_defaults()
        
    def _register_defaults(self):
        """Register default configurations"""
        from ..data.fishing_data import BAIT_TYPES
        
        default_user = {
            "inventory": [],
            "rod": "Basic Rod",
            "total_value": 0,
            "daily_quest": None,
            "bait": {},
            "purchased_rods": {"Basic Rod": True},
            "equipped_bait": None,
            "current_location": "Pond",
            "fish_caught": 0,
            "level": 1,
            "settings": {
                "notifications": True,
                "auto_sell": False
            }
        }
    
        default_global = {
            "bait_stock": {
                bait: data["daily_stock"]
                for bait, data in BAIT_TYPES.items()
            },
            "current_weather": "Sunny",
            "active_events": [],
            "settings": {
                "daily_reset_hour": 0,
                "weather_change_interval": 3600
            }
        }
        
        self.config.register_user(**default_user)
        self.config.register_global(**default_global)

    async def _get_default_user_data(self) -> Dict[str, Any]:
        """Get default user data structure"""
        try:
            default_data = {
                "inventory": [],
                "rod": "Basic Rod",
                "total_value": 0,
                "daily_quest": None,
                "bait": {},
                "purchased_rods": {"Basic Rod": True},
                "equipped_bait": None,
                "current_location": "Pond",
                "fish_caught": 0,
                "level": 1,
                "settings": {
                    "notifications": True,
                    "auto_sell": False
                }
            }
            
            self.logger.debug("Generated default user data structure")
            return default_data
            
        except Exception as e:
            self.logger.error(f"Error generating default user data: {e}")
            # Return minimal default structure to prevent further errors
            return {
                "inventory": [],
                "rod": "Basic Rod",
                "total_value": 0,
                "bait": {},
                "purchased_rods": {"Basic Rod": True},
                "equipped_bait": None,
                "current_location": "Pond",
                "fish_caught": 0,
                "level": 1,
                "settings": {}
            }
    
    async def _validate_user_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and repair user data if needed"""
        try:
            # If data is None or empty, return default data
            if not data:
                self.logger.debug("User data is empty, returning default data")
                return await self._get_default_user_data()
                
            default_data = await self._get_default_user_data()
            validated_data = {}
            
            # Ensure all required keys exist with correct types
            for key, default_value in default_data.items():
                if key not in data:
                    validated_data[key] = default_value
                elif isinstance(default_value, dict):
                    if not isinstance(data[key], dict):
                        validated_data[key] = default_value
                    else:
                        validated_data[key] = {}
                        # Recursively validate nested dictionary
                        for subkey, subvalue in default_value.items():
                            if subkey not in data[key]:
                                validated_data[key][subkey] = subvalue
                            else:
                                validated_data[key][subkey] = data[key][subkey]
                else:
                    validated_data[key] = data[key]
                    
            return validated_data
                
        except Exception as e:
            self.logger.error(f"Error validating user data: {e}")
            self.logger.debug("Returning default user data due to validation error")
            return await self._get_default_user_data()
            
    async def get_user_data(self, user_id: int) -> ConfigResult[Dict[str, Any]]:
        """Get user data with validation and caching"""
        try:
            # Check cache first
            cache_key = f"user_{user_id}"
            if cache_key in self._cache:
                return ConfigResult(True, self._cache[cache_key])
                
            try:
                data = await self.config.user_from_id(user_id).all()
            except Exception as e:
                self.logger.error(f"Error fetching user data from config: {e}")
                data = None
                
            validated_data = await self._validate_user_data(data)
            
            # Update cache
            self._cache[cache_key] = validated_data
            
            return ConfigResult(True, validated_data)
            
        except Exception as e:
            self.logger.error(f"Error getting user data: {e}")
            return ConfigResult(False, error=str(e))
        
    async def update_user_data(
        self,
        user_id: int,
        updates: Dict[str, Any],
        fields: Optional[list] = None
    ) -> ConfigResult[bool]:
        """Update user data with validation and field filtering"""
        try:
            self.logger.debug(f"Updating user data for {user_id}")
            self.logger.debug(f"Update content: {updates}")
            self.logger.debug(f"Specified fields: {fields}")
    
            group = self.config.user_from_id(user_id)
            current_data = await group.all()
            self.logger.debug(f"Current data from config: {current_data}")
    
            # Ensure we have a valid data structure
            if not current_data:
                current_data = await self._get_default_user_data()
    
            # Create a working copy
            data = current_data.copy()
    
            if fields:
                # Only update specified fields
                for field in fields:
                    if field in updates:
                        if field == "bait":
                            # Special handling for bait dictionary
                            current_bait = data.get("bait", {})
                            new_bait = updates["bait"]
                            # Merge the dictionaries instead of replacing
                            merged_bait = current_bait.copy()
                            merged_bait.update(new_bait)
                            self.logger.debug(f"Updating bait data from {current_bait} to {merged_bait}")
                            data["bait"] = merged_bait
                        elif isinstance(updates[field], dict):
                            if not isinstance(data.get(field), dict):
                                data[field] = {}
                            data[field].update(updates[field])
                        else:
                            data[field] = updates[field]
            else:
                # Update all fields
                for key, value in updates.items():
                    if key == "bait":
                        current_bait = data.get("bait", {})
                        merged_bait = current_bait.copy()
                        merged_bait.update(value)
                        data["bait"] = merged_bait
                    elif isinstance(value, dict):
                        if not isinstance(data.get(key), dict):
                            data[key] = {}
                        data[key].update(value)
                    else:
                        data[key] = value
    
            self.logger.debug(f"Updated data before save: {data}")
            
            # Save data using set_raw for each field
            for key, value in data.items():
                if key in updates or not fields:
                    self.logger.debug(f"Setting {key} to {value}")
                    await group.set_raw(key, value=value)
    
            # Invalidate cache
            await self.invalidate_cache(f"user_{user_id}")
            
            # Verify the update
            verify_data = await group.all()
            self.logger.debug(f"Verification data from config: {verify_data}")
            
            if "bait" in verify_data:
                self.logger.debug(f"Verified bait data: {verify_data['bait']}")
    
            return ConfigResult(True, True)
            
        except Exception as e:
            self.logger.error(f"Error updating user data: {e}", exc_info=True)
            return ConfigResult(False, error=str(e))
            
    async def get_global_setting(self, key: str) -> ConfigResult[Any]:
        """Get global setting with caching"""
        try:
            cache_key = f"global_{key}"
            if cache_key in self._cache:
                return ConfigResult(True, self._cache[cache_key])
                
            value = await self.config.get_raw(key)
            self._cache[cache_key] = value
            return ConfigResult(True, value)
        except Exception as e:
            self.logger.error(f"Error getting global setting: {e}")
            return ConfigResult(False, error=str(e))
            
    async def update_global_setting(self, key: str, value: Any) -> ConfigResult[bool]:
        """Update global setting with cache invalidation"""
        try:
            await self.config.set_raw(key, value=value)
            await self.invalidate_cache(f"global_{key}")
            return ConfigResult(True, True)
        except Exception as e:
            self.logger.error(f"Error updating global setting: {e}")
            return ConfigResult(False, error=str(e))
            
    async def get_all_global_settings(self) -> ConfigResult[Dict[str, Any]]:
        """Get all global settings"""
        try:
            if "global_all" in self._cache:
                return ConfigResult(True, self._cache["global_all"])
                
            data = await self.config.all()
            self._cache["global_all"] = data
            return ConfigResult(True, data)
        except Exception as e:
            self.logger.error(f"Error getting all global settings: {e}")
            return ConfigResult(False, error=str(e))
            
    async def reset_user_data(self, user_id: int) -> ConfigResult[bool]:
        """Reset user data to defaults"""
        try:
            await self.config.user_from_id(user_id).clear()
            default_data = await self._get_default_user_data()
            await self.config.user_from_id(user_id).set(default_data)
            
            # Invalidate cache
            await self.invalidate_cache(f"user_{user_id}")
            
            return ConfigResult(True, True)
            
        except Exception as e:
            self.logger.error(f"Error resetting user data: {e}")
            return ConfigResult(False, error=str(e))
            
    async def invalidate_cache(self, key: Optional[str] = None):
        """Invalidate specific cache key or entire cache"""
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()
            
    async def refresh_cache(self, user_id: int) -> ConfigResult[bool]:
        """Force refresh of user data cache"""
        try:
            cache_key = f"user_{user_id}"
            data = await self.config.user_from_id(user_id).all()
            validated_data = await self._validate_user_data(data)
            self._cache[cache_key] = validated_data
            return ConfigResult(True, True)
        except Exception as e:
            self.logger.error(f"Error refreshing cache: {e}")
            return ConfigResult(False, error=str(e))
            
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
            # Clear transaction cache
            transaction_cache.clear()

    async def process_complex_update(self, user_id: int, updates: Dict[str, Any]):
        """Process multiple updates in a single transaction"""
        async with self.config_transaction() as transaction:
            # Update user data
            transaction[f"user_{user_id}"] = updates
            
            # Update global settings if needed
            if "bait_stock" in updates:
                transaction["global_bait_stock"] = updates["bait_stock"]
