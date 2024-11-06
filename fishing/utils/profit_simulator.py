#ui/profit_simulator.py

import random
import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional
from ..utils.logging_config import get_logger

@dataclass
class GearTier:
    level: int
    rod: str
    bait: str
    location: str
    unlocked_weather: List[str]
    fish_per_hour: int = 360  # Based on 6 catches per minute average

@dataclass
class CatchResult:
    fish_name: str
    value: int
    rarity: str

class ProfitSimulator:
    """Fishing profit simulation system for economy analysis"""
    
    def __init__(self, game_data: Dict):
        self.logger = get_logger('profit_simulator')
        self.data = game_data
        self.logger.debug("Initializing profit simulator")
        
        # Define progression tiers
        self.tiers = [
            GearTier(1, "Basic Rod", "Worm", "Pond", 
                    ["Sunny", "Rainy", "Clear", "Overcast"]),
            GearTier(5, "Intermediate Rod", "Shrimp", "River", 
                    ["Sunny", "Rainy", "Clear", "Overcast", "Foggy"]),
            GearTier(8, "Intermediate Rod", "Cricket", "Lake", 
                    ["Sunny", "Rainy", "Clear", "Overcast", "Foggy", "Windy"]),
            GearTier(12, "Advanced Rod", "Firefly", "Ocean", 
                    ["Sunny", "Rainy", "Clear", "Overcast", "Foggy", "Windy", "Stormy"]),
            GearTier(15, "Expert Rod", "Nightcrawler", "Ocean", 
                    ["Sunny", "Rainy", "Clear", "Overcast", "Foggy", "Windy", "Stormy", "Heat Wave"]),
            GearTier(18, "Master Rod", "Anchovy", "Deep Sea", 
                    ["Sunny", "Rainy", "Clear", "Overcast", "Foggy", "Windy", "Stormy", "Heat Wave", "Red Tide"])
        ]

    def simulate_catch(self, tier: GearTier) -> CatchResult:
        """Simulate a single catch with given gear setup"""
        try:
            # Calculate base catch chance
            rod_bonus = self.data["rods"][tier.rod]["chance"]
            bait_bonus = self.data["bait"][tier.bait]["catch_bonus"]
            location_mods = self.data["locations"][tier.location]["fish_modifiers"]
            
            # Simulate weather effects
            weather_effects = []
            for weather in tier.unlocked_weather:
                if weather in self.data["weather"]:
                    weather_effects.append(self.data["weather"][weather]["catch_bonus"])
            
            weather_bonus = statistics.mean(weather_effects) if weather_effects else 0
            
            # Calculate final catch modifiers
            total_catch_mod = rod_bonus + bait_bonus + weather_bonus
            
            # Determine catch rarity
            weights = []
            fish_types = []
            for fish, data in self.data["fish"].items():
                modified_chance = data["chance"] * location_mods[fish]
                weights.append(modified_chance)
                fish_types.append(fish)
                
            caught_fish = random.choices(fish_types, weights=weights)[0]
            fish_data = self.data["fish"][caught_fish]
            
            self.logger.debug(f"Simulated catch: {caught_fish} with modifier {total_catch_mod}")
            return CatchResult(caught_fish, fish_data["value"], fish_data["rarity"])
            
        except Exception as e:
            self.logger.error(f"Error in catch simulation: {e}")
            return None

    def analyze_tier(self, tier: GearTier) -> Dict:
        """Analyze fishing profits for a specific gear tier"""
        try:
            total_catches = 0
            total_value = 0
            rarity_counts = {"common": 0, "uncommon": 0, "rare": 0, "legendary": 0}
            bait_cost = self.data["bait"][tier.bait]["cost"] * tier.fish_per_hour
            
            self.logger.debug(f"Analyzing tier: Level {tier.level} with {tier.rod} at {tier.location}")
            
            # Simulate one hour of fishing
            for _ in range(tier.fish_per_hour):
                catch = self.simulate_catch(tier)
                if catch:
                    total_catches += 1
                    total_value += catch.value
                    rarity_counts[catch.rarity] += 1
                
            # Calculate statistics
            gross_profit = total_value
            net_profit = total_value - bait_cost
            
            result = {
                "level": tier.level,
                "rod": tier.rod,
                "bait": tier.bait,
                "location": tier.location,
                "catches_per_hour": total_catches,
                "bait_cost": bait_cost,
                "gross_profit": gross_profit,
                "net_profit": net_profit,
                "rarity_breakdown": rarity_counts
            }
            
            self.logger.debug(f"Analysis complete: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error in tier analysis: {e}")
            return None

    def analyze_all_tiers(self) -> List[Dict]:
        """Analyze all progression tiers"""
        try:
            results = []
            for tier in self.tiers:
                result = self.analyze_tier(tier)
                if result:
                    results.append(result)
            return results
        except Exception as e:
            self.logger.error(f"Error in full analysis: {e}")
            return []

    def analyze_custom_setup(self, rod: str, bait: str, location: str, 
                           weather_types: Optional[List[str]] = None) -> Dict:
        """Analyze a custom gear setup"""
        try:
            if not weather_types:
                weather_types = ["Sunny", "Clear"]  # Default weather types
                
            custom_tier = GearTier(
                level=1,  # Level doesn't affect simulation
                rod=rod,
                bait=bait,
                location=location,
                unlocked_weather=weather_types
            )
            
            return self.analyze_tier(custom_tier)
            
        except Exception as e:
            self.logger.error(f"Error in custom setup analysis: {e}")
            return None
