# base_manager.py

from typing import Dict, List
import json

class BaseManager:
    def __init__(self):
        self.bases = {}  # Dictionary to store player bases
        
    async def create_base(self, user_id: int) -> bool:
        """Create a new base for a player"""
        if user_id in self.bases:
            return False
        
        self.bases[user_id] = {
            "level": 1,
            "health": 100,
            "defense": 10,
            "modules": [],
            "last_attack": None
        }
        return True
    
    async def get_base(self, user_id: int) -> Dict:
        """Get base information for a player"""
        return self.bases.get(user_id, None)
    
    async def upgrade_base(self, user_id: int) -> bool:
        """Upgrade a player's base level"""
        if user_id not in self.bases:
            return False
            
        self.bases[user_id]["level"] += 1
        self.bases[user_id]["health"] += 50
        self.bases[user_id]["defense"] += 5
        return True
