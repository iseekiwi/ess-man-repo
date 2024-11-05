# utils/inventory_manager.py

import logging
from typing import Dict, Optional, Tuple, List, TypeVar, Union, Any
from redbot.core.bot import Red
from redbot.core import Config
from ..utils.logging_config import get_logger
from ..utils.config_manager import ConfigManager, ConfigResult

T = TypeVar('T')

class InventoryManager:
    """
    Centralized inventory management system.
    
    This class handles all inventory-related operations including:
    - Adding/removing items
    - Inventory verification
    - Summary generation
    - Transaction management
    
    Attributes:
        bot (Red): The Red Discord bot instance
        config_manager (ConfigManager): Configuration management system
        data (Dict): Game data containing item definitions
        logger (logging.Logger): Logger instance
    """
    
    def __init__(self, bot: Red, config_manager: ConfigManager, data: Dict):
        self.bot = bot
        self.config_manager = config_manager
        self.data = data
        self.logger = get_logger('inventory_manager')
        
    async def _verify_item_validity(self, item_type: str, item_name: str) -> Tuple[bool, str]:
        """
        Verify if an item exists in the game data.
        
        Args:
            item_type: Type of item (fish, bait, rod)
            item_name: Name of the item
            
        Returns:
            Tuple[bool, str]: Success status and message
        """
        type_mapping = {
            "fish": "fish",
            "bait": "bait",
            "rod": "rods"
        }
        
        if item_type not in type_mapping:
            return False, f"Invalid item type: {item_type}"
            
        data_key = type_mapping[item_type]
        if item_name not in self.data[data_key]:
            return False, f"Invalid {item_type}: {item_name}"
            
        return True, ""
        
    async def _update_inventory(
        self,
        user_id: int,
        item_type: str,
        item_name: str,
        amount: int,
        operation: str
    ) -> Tuple[bool, str]:
        """
        Core inventory update method handling both additions and removals.
        
        Args:
            user_id: Discord user ID
            item_type: Type of item (fish, bait, rod)
            item_name: Name of the item
            amount: Quantity to add/remove
            operation: Either "add" or "remove"
            
        Returns:
            Tuple[bool, str]: Success status and message
        """
        try:
            # Validate item
            valid, msg = await self._verify_item_validity(item_type, item_name)
            if not valid:
                return False, msg
                
            # Get current user data
            user_result = await self.config_manager.get_user_data(user_id)
            if not user_result.success:
                self.logger.error(f"Failed to get user data for {user_id}")
                return False, "Error accessing user data"
                
            user_data = user_result.data
            self.logger.debug(f"Current user data: {user_data}")
            
            async with self.config_manager.config_transaction() as transaction:
                updates = {}
                
                if item_type == "fish":
                    inventory = user_data.get("inventory", []).copy()
                    if operation == "add":
                        for _ in range(amount):
                            inventory.append(item_name)
                    else:  # remove
                        if inventory.count(item_name) < amount:
                            return False, "Not enough fish to remove"
                        for _ in range(amount):
                            inventory.remove(item_name)
                    updates["inventory"] = inventory
                    
                elif item_type == "bait":
                    bait_inventory = user_data.get("bait", {}).copy()
                    current_amount = bait_inventory.get(item_name, 0)
                    
                    if operation == "add":
                        new_amount = current_amount + amount
                    else:  # remove
                        if current_amount < amount:
                            return False, "Not enough bait to remove"
                        new_amount = current_amount - amount
                        
                    if new_amount <= 0:
                        bait_inventory.pop(item_name, None)
                        if user_data.get("equipped_bait") == item_name:
                            updates["equipped_bait"] = None
                    else:
                        bait_inventory[item_name] = new_amount
                    updates["bait"] = bait_inventory
                    
                elif item_type == "rod":
                    purchased_rods = user_data.get("purchased_rods", {"Basic Rod": True}).copy()
                    if operation == "add":
                        purchased_rods[item_name] = True
                    else:  # remove
                        if item_name not in purchased_rods:
                            return False, "Rod not owned"
                        del purchased_rods[item_name]
                        if user_data.get("rod") == item_name:
                            updates["rod"] = "Basic Rod"
                    updates["purchased_rods"] = purchased_rods
                
                # Store updates in transaction
                transaction[f"user_{user_id}"] = updates
                
            # Verify the update
            verify_result = await self.config_manager.get_user_data(user_id)
            if not verify_result.success:
                self.logger.error("Failed to verify inventory update")
                return False, "Error verifying inventory update"
                
            verified_data = verify_result.data
            self.logger.debug(f"Verification data: {verified_data}")
            
            # Verify specific update based on item type
            if item_type == "bait":
                verified_amount = verified_data.get("bait", {}).get(item_name, 0)
                expected_amount = max(0, current_amount + (amount if operation == "add" else -amount))
                if verified_amount != expected_amount:
                    self.logger.error(f"Verification failed - Expected: {expected_amount}, Got: {verified_amount}")
                    return False, "Error verifying inventory update"
                    
            elif item_type == "rod":
                if operation == "add" and item_name not in verified_data.get("purchased_rods", {}):
                    return False, "Error verifying inventory update"
                    
            elif item_type == "fish":
                verified_count = verified_data.get("inventory", []).count(item_name)
                expected_count = (user_data.get("inventory", []).count(item_name) + 
                                (amount if operation == "add" else -amount))
                if verified_count != expected_count:
                    return False, "Error verifying inventory update"
            
            action = "added to" if operation == "add" else "removed from"
            return True, f"Successfully {action} inventory: {amount}x {item_name}"
            
        except Exception as e:
            self.logger.error(f"Error in inventory update: {e}", exc_info=True)
            return False, "Error processing inventory update"
            
    async def add_item(
        self,
        user_id: int,
        item_type: str,
        item_name: str,
        amount: int = 1
    ) -> Tuple[bool, str]:
        """
        Add items to a user's inventory.
        
        Args:
            user_id: Discord user ID
            item_type: Type of item (fish, bait, rod)
            item_name: Name of the item
            amount: Quantity to add (default: 1)
            
        Returns:
            Tuple[bool, str]: Success status and message
        """
        return await self._update_inventory(user_id, item_type, item_name, amount, "add")
        
    async def remove_item(
        self,
        user_id: int,
        item_type: str,
        item_name: str,
        amount: int = 1
    ) -> Tuple[bool, str]:
        """
        Remove items from a user's inventory.
        
        Args:
            user_id: Discord user ID
            item_type: Type of item (fish, bait, rod)
            item_name: Name of the item
            amount: Quantity to remove (default: 1)
            
        Returns:
            Tuple[bool, str]: Success status and message
        """
        return await self._update_inventory(user_id, item_type, item_name, amount, "remove")
        
    async def get_inventory_summary(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a summary of user's inventory.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Optional[Dict[str, Any]]: Inventory summary or None if error
        """
        try:
            result = await self.config_manager.get_user_data(user_id)
            if not result.success:
                return None
                    
            user_data = result.data
            if not user_data:
                return None
                    
            inventory = user_data.get("inventory", [])
            fish_count = sum(1 for item in inventory if item in self.data["fish"])
            junk_count = sum(1 for item in inventory if item in self.data["junk"])
            total_items = fish_count + junk_count
            bait_count = sum(user_data.get("bait", {}).values())
            rod_count = len(user_data.get("purchased_rods", {}))
                
            # Calculate total value from both fish and junk items
            total_value = sum(
                self.data["fish"][item]["value"]
                for item in inventory
                if item in self.data["fish"]
            ) + sum(
                self.data["junk"][item]["value"]
                for item in inventory
                if item in self.data["junk"]
            )
                
            return {
                "fish_count": total_items,  # Total of both fish and junk for overall count
                "bait_count": bait_count,
                "rod_count": rod_count,
                "total_value": total_value,
                "equipped_rod": user_data.get("rod"),
                "equipped_bait": user_data.get("equipped_bait")
            }
                
        except Exception as e:
            self.logger.error(f"Error getting inventory summary: {e}", exc_info=True)
            return None
