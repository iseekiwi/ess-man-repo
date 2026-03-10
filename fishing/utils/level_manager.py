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
        # Gap between levels grows by ~350 XP per level, with slight
        # acceleration after level 50 (+100) and level 75 (+150).
        self.xp_thresholds = {
            1: 0,
            2: 100,
            3: 400,
            4: 1000,
            5: 1900,
            6: 3100,
            7: 4600,
            8: 6400,
            9: 8500,
            10: 11000,
            11: 13800,
            12: 16900,
            13: 20300,
            14: 24000,
            15: 28000,
            16: 32300,
            17: 36900,
            18: 41800,
            19: 47000,
            20: 52500,
            21: 58350,
            22: 64550,
            23: 71100,
            24: 78000,
            25: 85250,
            26: 92850,
            27: 100800,
            28: 109100,
            29: 117750,
            30: 126750,
            31: 136100,
            32: 145800,
            33: 155850,
            34: 166250,
            35: 177000,
            36: 188100,
            37: 199550,
            38: 211350,
            39: 223500,
            40: 236000,
            41: 248850,
            42: 262050,
            43: 275600,
            44: 289500,
            45: 303750,
            46: 318350,
            47: 333300,
            48: 348600,
            49: 364250,
            50: 380250,
            51: 396700,
            52: 413600,
            53: 430950,
            54: 448750,
            55: 467000,
            56: 485700,
            57: 504850,
            58: 524450,
            59: 544500,
            60: 565000,
            61: 585950,
            62: 607350,
            63: 629200,
            64: 651500,
            65: 674250,
            66: 697450,
            67: 721100,
            68: 745200,
            69: 769750,
            70: 794750,
            71: 820200,
            72: 846100,
            73: 872450,
            74: 899250,
            75: 926500,
            76: 954350,
            77: 982800,
            78: 1011850,
            79: 1041500,
            80: 1071750,
            81: 1102600,
            82: 1134050,
            83: 1166100,
            84: 1198750,
            85: 1232000,
            86: 1265850,
            87: 1300300,
            88: 1335350,
            89: 1371000,
            90: 1407250,
            91: 1444100,
            92: 1481550,
            93: 1519600,
            94: 1558250,
            95: 1597500,
            96: 1637350,
            97: 1677800,
            98: 1718850,
            99: 1760500,
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
