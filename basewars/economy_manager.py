# economy_manager.py
class EconomyManager:
    def __init__(self):
        self.balances = {}
        
    async def get_balance(self, user_id: int) -> int:
        """Get a player's balance"""
        return self.balances.get(user_id, 0)
        
    async def add_money(self, user_id: int, amount: int) -> bool:
        """Add money to a player's balance"""
        if user_id not in self.balances:
            self.balances[user_id] = 0
            
        self.balances[user_id] += amount
        return True
        
    async def remove_money(self, user_id: int, amount: int) -> bool:
        """Remove money from a player's balance"""
        if user_id not in self.balances:
            return False
            
        if self.balances[user_id] < amount:
            return False
            
        self.balances[user_id] -= amount
        return True
