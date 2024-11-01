# utils/config_manager.py

from redbot.core import Config
from typing import Dict, Any
from .logging_config import get_logger

logger = get_logger('config_manager')

class ConfigManager:
    """Centralized configuration management"""
    def __init__(self, bot, identifier: int):
        self.config = Config.get_conf(None, identifier=identifier)
        self.logger = logger
        
        # Register defaults
        self._register_defaults()
        
    def _register_defaults(self):
        """Register default configurations"""
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
        
    async def get_user_data(self, user_id: int) -> Dict[str, Any]:
        """Get user data with validation"""
        try:
            data = await self.config.user_from_id(user_id).all()
            return await self._validate_user_data(data)
        except Exception as e:
            self.logger.error(f"Error getting user data: {e}")
            return None
            
    async def _validate_user_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and repair user data if needed"""
        try:
            if not data:
                return await self._get_default_user_data()
                
            # Ensure all required keys exist
            default_data = await self._get_default_user_data()
            for key, value in default_data.items():
                if key not in data:
                    data[key] = value
                elif isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        if key not in data or subkey not in data[key]:
                            if key not in data:
                                data[key] = {}
                            data[key][subkey] = subvalue
                            
            return data
            
        except Exception as e:
            self.logger.error(f"Error validating user data: {e}")
            return await self._get_default_user_data()
            
    async def _get_default_user_data(self) -> Dict[str, Any]:
        """Get default user data"""
        return await self.config.user_defaults()
        
    async def update_user_data(
        self,
        user_id: int,
        updates: Dict[str, Any]
    ) -> bool:
        """Update user data with validation"""
        try:
            async with self.config.user_from_id(user_id).all() as data:
                for key, value in updates.items():
                    if isinstance(value, dict) and key in data:
                        data[key].update(value)
                    else:
                        data[key] = value
            return True
        except Exception as e:
            self.logger.error(f"Error updating user data: {e}")
            return False
