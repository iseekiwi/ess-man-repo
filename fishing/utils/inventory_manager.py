# utils/inventory_manager.py

import logging
from typing import Dict, Optional, Tuple, List
from redbot.core.bot import Red
from redbot.core import Config
from ..utils.logging_config import get_logger

logger = get_logger('inventory_manager')

class InventoryManager:
    """Centralized inventory management system"""
    def __init__(self, bot: Red, config: Config, data: Dict):
        self.bot = bot
        self.config_manager = config_manager
        self.data = data
        self.logger = logger
        
    async def add_item(self, user_id: int, item_type: str, item_name: str, amount: int = 1) -> Tuple[bool, str]:
        """Add any type of item to user inventory"""
        try:
            async with self.config.user_from_id(user_id).all() as user_data:
                if item_type == "fish":
                    if item_name not in self.data["fish"]:
                        return False, "Invalid fish type"
                    if "inventory" not in user_data:
                        user_data["inventory"] = []
                    for _ in range(amount):
                        user_data["inventory"].append(item_name)
                        
                elif item_type == "bait":
                    if item_name not in self.data["bait"]:
                        return False, "Invalid bait type"
                    if "bait" not in user_data:
                        user_data["bait"] = {}
                    user_data["bait"][item_name] = user_data["bait"].get(item_name, 0) + amount
                    
                elif item_type == "rod":
                    if item_name not in self.data["rods"]:
                        return False, "Invalid rod type"
                    if "purchased_rods" not in user_data:
                        user_data["purchased_rods"] = {"Basic Rod": True}
                    user_data["purchased_rods"][item_name] = True
                    
                else:
                    return False, "Invalid item type"
                    
                return True, f"Successfully added {amount}x {item_name}"
                
        except Exception as e:
            logger.error(f"Error adding item: {e}", exc_info=True)
            return False, "Error processing inventory update"
            
    async def remove_item(self, user_id: int, item_type: str, item_name: str, amount: int = 1) -> Tuple[bool, str]:
        """Remove any type of item from user inventory"""
        try:
            async with self.config.user_from_id(user_id).all() as user_data:
                if item_type == "fish":
                    if item_name is None:
                        # Special case: remove all fish
                        if not user_data.get("inventory", []):
                            return False, "No fish to remove"
                        user_data["inventory"] = []
                        return True, "Successfully removed all fish"
                    else:
                        # Remove specific fish
                        if not user_data.get("inventory", []).count(item_name) >= amount:
                            return False, "Not enough fish to remove"
                        for _ in range(amount):
                            user_data["inventory"].remove(item_name)
                            
                elif item_type == "bait":
                    if user_data.get("bait", {}).get(item_name, 0) < amount:
                        return False, "Not enough bait to remove"
                    user_data["bait"][item_name] -= amount
                    if user_data["bait"][item_name] <= 0:
                        del user_data["bait"][item_name]
                        if user_data.get("equipped_bait") == item_name:
                            user_data["equipped_bait"] = None
                            
                elif item_type == "rod":
                    if item_name not in user_data.get("purchased_rods", {}):
                        return False, "Rod not owned"
                    del user_data["purchased_rods"][item_name]
                    if user_data.get("rod") == item_name:
                        user_data["rod"] = "Basic Rod"
                        
                else:
                    return False, "Invalid item type"
                    
                return True, f"Successfully removed {amount}x {item_name}" if item_name else "Successfully removed items"
                    
        except Exception as e:
            self.logger.error(f"Error removing item: {e}", exc_info=True)
            return False, "Error processing inventory update"
            
    async def get_inventory_summary(self, user_id: int) -> Optional[Dict]:
        """Get a summary of user's inventory"""
        try:
            result = await self.config_manager.get_user_data(user_id)
            if not result.success:
                return None
                    
                user_data = result.data
                if not user_data:
                    return None
                    
                fish_count = len(user_data.get("inventory", []))
                bait_count = sum(user_data.get("bait", {}).values())
                rod_count = len(user_data.get("purchased_rods", {}))
                
                total_value = sum(
                    self.data["fish"][fish]["value"]
                    for fish in user_data.get("inventory", [])
                )
                
                return {
                    "fish_count": fish_count,
                    "bait_count": bait_count,
                    "rod_count": rod_count,
                    "total_value": total_value,
                    "equipped_rod": user_data.get("rod"),
                    "equipped_bait": user_data.get("equipped_bait")
                }
                
        except Exception as e:
            self.logger.error(f"Error getting inventory summary: {e}", exc_info=True)
            return None
            
        except Exception as e:
            logger.error(f"Error getting inventory summary: {e}", exc_info=True)
            return None
