# shop_manager.py

class ShopManager:
    def __init__(self):
        self.items = {
            "printer": {
                "name": "Money Printer",
                "price": 1000,
                "description": "Generates money over time",
                "category": "income"
            },
            "turret": {
                "name": "Defense Turret",
                "price": 2000,
                "description": "Automatic base defense",
                "category": "defense"
            },
            "shield": {
                "name": "Energy Shield",
                "price": 3000,
                "description": "Reduces incoming damage",
                "category": "defense"
            }
        }
    
    async def get_shop_items(self, category: str = None) -> Dict:
        """Get all items or items of a specific category"""
        if category:
            return {k: v for k, v in self.items.items() if v["category"] == category}
        return self.items
    
    async def get_item_price(self, item_id: str) -> int:
        """Get the price of a specific item"""
        return self.items.get(item_id, {}).get("price", 0)
