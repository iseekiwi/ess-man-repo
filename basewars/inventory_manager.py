# inventory_manager.py

class InventoryManager:
    def __init__(self):
        self.inventories = {}
        
    async def get_inventory(self, user_id: int) -> Dict:
        """Get a player's inventory"""
        return self.inventories.get(user_id, {})
        
    async def add_item(self, user_id: int, item_id: str, amount: int = 1) -> bool:
        """Add an item to player's inventory"""
        if user_id not in self.inventories:
            self.inventories[user_id] = {}
            
        if item_id not in self.inventories[user_id]:
            self.inventories[user_id][item_id] = 0
            
        self.inventories[user_id][item_id] += amount
        return True
        
    async def remove_item(self, user_id: int, item_id: str, amount: int = 1) -> bool:
        """Remove an item from player's inventory"""
        if user_id not in self.inventories:
            return False
            
        if item_id not in self.inventories[user_id]:
            return False
            
        if self.inventories[user_id][item_id] < amount:
            return False
            
        self.inventories[user_id][item_id] -= amount
        return True
