# utils/inventory_manager.py

import logging
from typing import Dict, Optional, Tuple, List
from redbot.core.bot import Red
from redbot.core import Config
from ..utils.logging_config import get_logger
from ..utils.config_manager import ConfigManager

logger = get_logger('inventory_manager')

class InventoryManager:
    """Centralized inventory management system"""
    def __init__(self, bot: Red, config_manager: ConfigManager, data: Dict):
        self.bot = bot
        self.config_manager = config_manager
        self.data = data
        self.logger = logger
        
    async def add_item(self, user_id: int, item_type: str, item_name: str, amount: int = 1) -> Tuple[bool, str]:
        """Add any type of item to user inventory"""
        try:
            self.logger.debug(f"Adding item - Type: {item_type}, Name: {item_name}, Amount: {amount}, User: {user_id}")
            
            # Get current user data
            user_result = await self.config_manager.get_user_data(user_id)
            if not user_result.success:
                self.logger.error(f"Failed to get user data for {user_id}")
                return False, "Error accessing user data"
                
            user_data = user_result.data
            self.logger.debug(f"Current user data: {user_data}")
            updates = {}
    
            if item_type == "fish":
                if item_name not in self.data["fish"]:
                    return False, "Invalid fish type"
                if "inventory" not in user_data:
                    user_data["inventory"] = []
                inventory = user_data["inventory"].copy()
                for _ in range(amount):
                    inventory.append(item_name)
                updates["inventory"] = inventory
    
            elif item_type == "bait":
                if item_name not in self.data["bait"]:
                    self.logger.error(f"Invalid bait type: {item_name}")
                    return False, "Invalid bait type"
                if "bait" not in user_data:
                    user_data["bait"] = {}
                elif not isinstance(user_data["bait"], dict):
                    user_data["bait"] = {}
                
                bait_inventory = user_data.get("bait", {}).copy()
                current_amount = bait_inventory.get(item_name, 0)
                bait_inventory[item_name] = bait_inventory.get(item_name, 0) + amount
                updates["bait"] = bait_inventory
                
                self.logger.debug(f"Updating bait inventory: {updates}")
    
            elif item_type == "rod":
                if item_name not in self.data["rods"]:
                    return False, "Invalid rod type"
                purchased_rods = user_data.get("purchased_rods", {"Basic Rod": True}).copy()
                purchased_rods[item_name] = True
                updates["purchased_rods"] = purchased_rods
    
            else:
                return False, "Invalid item type"
    
            # Update user data with changes
            self.logger.debug(f"Applying updates: {updates}")
            update_result = await self.config_manager.update_user_data(
                user_id,
                updates,
                fields=list(updates.keys())
            )
    
            if not update_result.success:
                self.logger.error(f"Failed to update inventory: {update_result.error}")
                return False, "Error updating inventory"

            # Verify the update
            verify_result = await self.config_manager.get_user_data(user_id)
            if verify_result.success:
                self.logger.debug(f"Updated user data state: {verify_result.data}")
            
            return True, f"Successfully added {amount}x {item_name}"
    
        except Exception as e:
            self.logger.error(f"Error adding item: {e}", exc_info=True)
            return False, "Error processing inventory update"
            
    async def remove_item(self, user_id: int, item_type: str, item_name: str, amount: int = 1) -> Tuple[bool, str]:
        """Remove any type of item from user inventory"""
        try:
            # Get current user data
            user_result = await self.config_manager.get_user_data(user_id)
            if not user_result.success:
                return False, "Error accessing user data"
                
            user_data = user_result.data
            updates = {}
    
            if item_type == "fish":
                if item_name is None:
                    # Special case: remove all fish
                    if not user_data.get("inventory", []):
                        return False, "No fish to remove"
                    updates["inventory"] = []
                else:
                    # Remove specific fish
                    inventory = user_data.get("inventory", []).copy()
                    if inventory.count(item_name) < amount:
                        return False, "Not enough fish to remove"
                    for _ in range(amount):
                        inventory.remove(item_name)
                    updates["inventory"] = inventory
    
            elif item_type == "bait":
                bait_inventory = user_data.get("bait", {}).copy()
                if bait_inventory.get(item_name, 0) < amount:
                    return False, "Not enough bait to remove"
                bait_inventory[item_name] = bait_inventory[item_name] - amount
                if bait_inventory[item_name] <= 0:
                    del bait_inventory[item_name]
                    if user_data.get("equipped_bait") == item_name:
                        updates["equipped_bait"] = None
                updates["bait"] = bait_inventory
    
            elif item_type == "rod":
                purchased_rods = user_data.get("purchased_rods", {}).copy()
                if item_name not in purchased_rods:
                    return False, "Rod not owned"
                del purchased_rods[item_name]
                updates["purchased_rods"] = purchased_rods
                if user_data.get("rod") == item_name:
                    updates["rod"] = "Basic Rod"
    
            else:
                return False, "Invalid item type"
    
            # Update user data with changes
            update_result = await self.config_manager.update_user_data(
                user_id,
                updates,
                fields=list(updates.keys())
            )
    
            if not update_result.success:
                return False, "Error updating inventory"
    
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
