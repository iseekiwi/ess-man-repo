# utils/level_manager.py

from typing import Dict, Tuple, Optional
from .logging_config import get_logger
from .config_manager import ConfigManager, ConfigResult

class LevelManager:
    """
    Manages experience and leveling mechanics for the fishing system.
    
    Attributes:
        config_manager (ConfigManager): Configuration management system
        logger (logging.Logger): Logger instance
        xp_thresholds (Dict[int, int]): XP required for each level
        rarity_xp (Dict[str, int]): Base XP rewards for each fish rarity
    """
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.logger = get_logger('level_manager')
        
        # Define XP thresholds for each level (1-99)
        # RuneScape-style exponential curve: gap(L) = 50 + 3350 * (2^(L/24.5) - 2^(2/24.5))
        # Halfway point (50% of total XP) falls at level 80.
        # Total XP to 99: ~1,510,510
        self.xp_thresholds = {
            1: 0,
            2: 50,
            3: 201,
            4: 457,
            5: 821,
            6: 1295,
            7: 1883,
            8: 2588,
            9: 3414,
            10: 4364,
            11: 5441,
            12: 6650,
            13: 7994,
            14: 9477,
            15: 11102,
            16: 12874,
            17: 14798,
            18: 16877,
            19: 19116,
            20: 21520,
            21: 24093,
            22: 26840,
            23: 29766,
            24: 32876,
            25: 36176,
            26: 39671,
            27: 43367,
            28: 47269,
            29: 51383,
            30: 55716,
            31: 60273,
            32: 65061,
            33: 70087,
            34: 75357,
            35: 80879,
            36: 86660,
            37: 92707,
            38: 99028,
            39: 105630,
            40: 112522,
            41: 119712,
            42: 127209,
            43: 135021,
            44: 143158,
            45: 151629,
            46: 160443,
            47: 169610,
            48: 179141,
            49: 189045,
            50: 199334,
            51: 210019,
            52: 221110,
            53: 232620,
            54: 244561,
            55: 256945,
            56: 269784,
            57: 283092,
            58: 296882,
            59: 311168,
            60: 325964,
            61: 341285,
            62: 357146,
            63: 373563,
            64: 390551,
            65: 408127,
            66: 426308,
            67: 445111,
            68: 464554,
            69: 484655,
            70: 505433,
            71: 526907,
            72: 549098,
            73: 572026,
            74: 595712,
            75: 620178,
            76: 645447,
            77: 671541,
            78: 698484,
            79: 726301,
            80: 755016,
            81: 784655,
            82: 815245,
            83: 846813,
            84: 879388,
            85: 912998,
            86: 947672,
            87: 983442,
            88: 1020338,
            89: 1058394,
            90: 1097642,
            91: 1138116,
            92: 1179852,
            93: 1222886,
            94: 1267255,
            95: 1312998,
            96: 1360154,
            97: 1408763,
            98: 1458867,
            99: 1510510,
        }
        
        # Define base XP rewards for each rarity
        self.rarity_xp = {
            "common": 15,     # 15 XP per common fish
            "uncommon": 35,   # 35 XP per uncommon fish
            "rare": 100,      # 100 XP per rare fish
            "legendary": 250  # 250 XP per legendary fish
        }
        
    async def initialize_user_xp(self, user_id: int) -> None:
        """Initialize or verify XP data structure for user."""
        try:
            result = await self.config_manager.get_user_data(user_id)
            if not result.success:
                self.logger.error(f"Failed to get user data for XP initialization: {result.error}")
                return
                
            user_data = result.data
            if "experience" not in user_data:
                update_result = await self.config_manager.update_user_data(
                    user_id,
                    {"experience": 0},
                    fields=["experience"]
                )
                if not update_result.success:
                    self.logger.error(f"Failed to initialize user XP: {update_result.error}")
                    
        except Exception as e:
            self.logger.error(f"Error in initialize_user_xp: {e}")

    def calculate_xp_reward(self, fish_rarity: str, location_mod: float = 1.0) -> int:
        """
        Calculate XP reward for catching a fish.
        
        Args:
            fish_rarity: Rarity of the caught fish
            location_mod: Location-based XP modifier
            
        Returns:
            int: XP reward amount
        """
        base_xp = self.rarity_xp.get(fish_rarity, 0)
        return int(base_xp * location_mod)

    def get_level_for_xp(self, xp: int) -> int:
        """Determine level based on total XP."""
        for level, threshold in sorted(self.xp_thresholds.items(), reverse=True):
            if xp >= threshold:
                return level
        return 1

    async def award_xp(self, user_id: int, xp_amount: int) -> Tuple[bool, Optional[int], Optional[int]]:
        """
        Award XP to user and check for level up.
        
        Args:
            user_id: Discord user ID
            xp_amount: Amount of XP to award
            
        Returns:
            Tuple[bool, Optional[int], Optional[int]]: 
                - Success status
                - Old level (if leveled up)
                - New level (if leveled up)
        """
        try:
            self.logger.debug(f"Awarding {xp_amount} XP to user {user_id}")
            
            # Get current user data
            result = await self.config_manager.get_user_data(user_id)
            if not result.success:
                self.logger.error(f"Failed to get user data for XP award: {result.error}")
                return False, None, None
                
            user_data = result.data
            current_xp = user_data.get("experience", 0)
            old_level = self.get_level_for_xp(current_xp)
            
            self.logger.debug(f"Current XP: {current_xp}, Current Level: {old_level}")
            
            # Calculate new XP and level
            new_xp = current_xp + xp_amount
            new_level = self.get_level_for_xp(new_xp)
            
            self.logger.debug(f"New XP: {new_xp}, New Level: {new_level}")
            
            # Update user data
            update_result = await self.config_manager.update_user_data(
                user_id,
                {
                    "experience": new_xp,
                    "level": new_level
                },
                fields=["experience", "level"]
            )
            
            if not update_result.success:
                self.logger.error(f"Failed to update user XP: {update_result.error}")
                return False, None, None

            # Return level up information if applicable
            if new_level > old_level:
                self.logger.info(f"User {user_id} leveled up from {old_level} to {new_level}")
                return True, old_level, new_level
                
            self.logger.debug(f"XP awarded successfully. New XP: {new_xp}, Level: {new_level}")
            return True, None, None
            
        except Exception as e:
            self.logger.error(f"Error in award_xp: {e}", exc_info=True)
            return False, None, None

    async def get_level_progress(self, user_id: int) -> Optional[Dict]:
        """
        Get detailed level progress information.
        
        Returns:
            Optional[Dict]: Dictionary containing:
                - current_level: Current level
                - current_xp: Total XP
                - xp_for_next: XP needed for next level
                - progress: Progress percentage to next level
        """
        try:
            self.logger.debug(f"Getting level progress for user {user_id}")
            
            result = await self.config_manager.get_user_data(user_id)
            if not result.success:
                self.logger.error(f"Failed to get user data for level progress: {result.error}")
                return None
                
            current_xp = result.data.get("experience", 0)
            current_level = self.get_level_for_xp(current_xp)
            
            self.logger.debug(f"Current XP: {current_xp}, Current Level: {current_level}")
            
            # Find next level threshold
            next_level = current_level + 1
            if next_level not in self.xp_thresholds:
                progress = 100
                xp_for_next = None
                self.logger.debug("Max level reached")
            else:
                current_threshold = self.xp_thresholds[current_level]
                next_threshold = self.xp_thresholds[next_level]
                xp_for_next = next_threshold - current_xp
                progress = ((current_xp - current_threshold) / 
                           (next_threshold - current_threshold) * 100)
                
                self.logger.debug(
                    f"Progress calculation - Current Threshold: {current_threshold}, "
                    f"Next Threshold: {next_threshold}, XP for next: {xp_for_next}, "
                    f"Progress: {progress}%"
                )
                
            progress_data = {
                "current_level": current_level,
                "current_xp": current_xp,
                "xp_for_next": xp_for_next,
                "progress": min(100, max(0, progress))
            }
            
            self.logger.debug(f"Returning progress data: {progress_data}")
            return progress_data
            
        except Exception as e:
            self.logger.error(f"Error in get_level_progress: {e}", exc_info=True)
            return None
