# utils/profit_simulator.py

import random
from dataclasses import dataclass
from typing import Dict, List, Optional
from ..utils.logging_config import get_logger

# XP values per rarity (mirrored from LevelManager to avoid circular import)
RARITY_XP = {
    "common": 15,
    "uncommon": 35,
    "rare": 100,
    "legendary": 250,
}

JUNK_RARITY_XP_MODIFIER = 0.5


@dataclass
class CatchResult:
    fish_name: str
    value: int
    rarity: str


class ProfitSimulator:
    """Fishing profit simulation system for economy analysis.

    Mirrors the catch logic in Fishing._catch_fish so that simulation results
    match real gameplay as closely as possible.
    """

    def __init__(self, game_data: Dict):
        self.logger = get_logger('profit_simulator')
        self.data = game_data

    # ------------------------------------------------------------------
    # Core simulation — matches _catch_fish logic in main.py
    # ------------------------------------------------------------------

    def _compute_modifiers(
        self, rod: str, bait: str, location: str, weather: str, time_of_day: str
    ) -> Dict:
        """Compute all catch-chance and rarity modifiers for a setup."""
        rod_bonus = self.data["rods"][rod]["chance"]
        bait_base = self.data["bait"][bait]["catch_bonus"]
        bait_effectiveness = self.data["bait"][bait].get("effectiveness", {}).get(location, 1.0)
        bait_bonus = bait_base * bait_effectiveness

        weather_data = self.data["weather"][weather]
        time_data = self.data["time"][time_of_day]

        weather_applies = location in weather_data.get("affects_locations", [])

        weather_bonus = 0.0
        weather_rare_bonus = 0.0
        if weather_applies:
            weather_bonus = weather_data.get("catch_bonus", 0)
            weather_bonus += weather_data.get("location_bonus", {}).get(location, 0)
            weather_bonus += weather_data.get("time_multiplier", {}).get(time_of_day, 0)
            weather_rare_bonus = weather_data.get("rare_bonus", 0)

        time_bonus = time_data.get("catch_bonus", 0)
        time_rare_bonus = time_data.get("rare_bonus", 0)

        total_chance = rod_bonus + bait_bonus + weather_bonus + time_bonus

        return {
            "rod_bonus": rod_bonus,
            "bait_bonus": bait_bonus,
            "bait_effectiveness": bait_effectiveness,
            "weather_bonus": weather_bonus,
            "weather_rare_bonus": weather_rare_bonus,
            "weather_applies": weather_applies,
            "time_bonus": time_bonus,
            "time_rare_bonus": time_rare_bonus,
            "total_chance": total_chance,
            "weather_data": weather_data,
        }

    def _build_fish_weights(self, location: str, mods: Dict) -> tuple:
        """Build weighted fish selection pool. Returns (fish_names, weights)."""
        location_mods = self.data["locations"][location]["fish_modifiers"]
        weather_data = mods["weather_data"]
        weather_applies = mods["weather_applies"]
        weather_rare_bonus = mods["weather_rare_bonus"]
        time_rare_bonus = mods["time_rare_bonus"]

        fish_names = []
        weights = []

        for fish, fdata in self.data["fish"].items():
            weight = fdata["chance"] * location_mods[fish]

            if weather_applies and fdata["rarity"] in ("rare", "legendary"):
                weight *= 1 + weather_rare_bonus + time_rare_bonus
                specific = weather_data.get("specific_rarity_bonus", {}).get(fish, 0)
                if specific:
                    weight *= 1 + specific

            fish_names.append(fish)
            weights.append(weight)

        return fish_names, weights

    def _build_junk_weights(self) -> tuple:
        """Build weighted junk selection pool."""
        junk_names = []
        weights = []
        for junk, jdata in self.data["junk"].items():
            junk_names.append(junk)
            weights.append(jdata["chance"])
        return junk_names, weights

    def _simulate_single(
        self, mods: Dict, fish_names: List, fish_weights: List,
        junk_names: List, junk_weights: List, location: str
    ) -> Dict:
        """Simulate a single fishing attempt (assumes player pressed the button).

        Returns a result dict (fish or junk) or None if nothing was caught.
        Mirrors the RNG flow in _catch_fish: failed fish roll has a 75%
        chance of junk and 25% chance of nothing (pure RNG, not user error).
        """
        catch_roll = random.random()

        if catch_roll < mods["total_chance"]:
            # Successful fish catch
            caught = random.choices(fish_names, weights=fish_weights, k=1)[0]
            fdata = self.data["fish"][caught]
            result = {
                "type": "fish",
                "name": caught,
                "value": fdata["value"],
                "rarity": fdata["rarity"],
            }

            # Bonus catch from weather
            if mods["weather_applies"]:
                cq = mods["weather_data"].get("catch_quantity", 0)
                if cq and random.random() < cq:
                    bonus = random.choices(fish_names, weights=fish_weights, k=1)[0]
                    bonus_data = self.data["fish"][bonus]
                    result["bonus"] = {
                        "name": bonus,
                        "value": bonus_data["value"],
                        "rarity": bonus_data["rarity"],
                    }
            return result

        # Failed fish roll — 75% chance for junk, 25% nothing (RNG)
        if random.random() < 0.75:
            caught = random.choices(junk_names, weights=junk_weights, k=1)[0]
            jdata = self.data["junk"][caught]
            return {
                "type": "junk",
                "name": caught,
                "value": jdata["value"],
                "rarity": jdata["rarity"],
            }

        return None  # nothing caught (RNG, not user error)

    # ------------------------------------------------------------------
    # Full setup analysis — used by the simulation menu
    # ------------------------------------------------------------------

    def analyze_full_setup(
        self,
        rod: str,
        bait: str,
        location: str,
        weather: str,
        time_of_day: str,
        duration_hours: int = 1,
        catches_per_hour: int = 360,
    ) -> Dict:
        """Run a complete simulation with all variables configurable.

        Returns a dict with rarity breakdown, financials, modifiers,
        bonus catches, junk stats, and XP estimate.
        """
        mods = self._compute_modifiers(rod, bait, location, weather, time_of_day)
        fish_names, fish_weights = self._build_fish_weights(location, mods)
        junk_names, junk_weights = self._build_junk_weights()

        # Compute expected rarity distribution from normalized weights
        expected_rarity = {"common": 0.0, "uncommon": 0.0, "rare": 0.0, "legendary": 0.0}
        total_weight = sum(fish_weights)
        if total_weight > 0:
            for name, weight in zip(fish_names, fish_weights):
                rarity = self.data["fish"][name]["rarity"]
                expected_rarity[rarity] += (weight / total_weight) * 100

        total_attempts = duration_hours * catches_per_hour
        bait_cost_per = self.data["bait"][bait]["cost"]

        rarity_counts = {"common": 0, "uncommon": 0, "rare": 0, "legendary": 0}
        gross_value = 0
        bonus_catches = 0
        junk_caught = 0
        junk_value = 0
        nothing_caught = 0  # RNG "nothing" (failed fish + failed junk roll)
        total_xp = 0

        for _ in range(total_attempts):
            result = self._simulate_single(
                mods, fish_names, fish_weights, junk_names, junk_weights, location
            )

            if result is None:
                nothing_caught += 1
                continue

            if result["type"] == "fish":
                rarity_counts[result["rarity"]] += 1
                gross_value += result["value"]
                total_xp += RARITY_XP.get(result["rarity"], 0)

                if "bonus" in result:
                    bonus_catches += 1
                    rarity_counts[result["bonus"]["rarity"]] += 1
                    gross_value += result["bonus"]["value"]
                    total_xp += RARITY_XP.get(result["bonus"]["rarity"], 0)

            elif result["type"] == "junk":
                junk_caught += 1
                junk_value += result["value"]
                total_xp += int(RARITY_XP.get(result["rarity"], 0) * JUNK_RARITY_XP_MODIFIER)

        # Bait is consumed on every attempt, including misses
        total_bait_cost = total_attempts * bait_cost_per
        total_gross = gross_value + junk_value
        net_profit = total_gross - total_bait_cost

        return {
            "rod": rod,
            "bait": bait,
            "location": location,
            "weather": weather,
            "time_of_day": time_of_day,
            "duration_hours": duration_hours,
            "catches_per_hour": catches_per_hour,
            "rarity_breakdown": rarity_counts,
            "expected_rarity": expected_rarity,
            "bonus_catches": bonus_catches,
            "junk_caught": junk_caught,
            "junk_value": junk_value,
            "nothing_caught": nothing_caught,
            "gross_profit": total_gross,
            "bait_cost": total_bait_cost,
            "net_profit": net_profit,
            "estimated_xp": total_xp,
            "modifiers": {
                "rod_bonus": mods["rod_bonus"],
                "bait_bonus": mods["bait_bonus"],
                "bait_effectiveness": mods["bait_effectiveness"],
                "weather_bonus": mods["weather_bonus"],
                "weather_rare_bonus": mods["weather_rare_bonus"],
                "weather_applies": mods["weather_applies"],
                "time_bonus": mods["time_bonus"],
                "time_rare_bonus": mods["time_rare_bonus"],
                "total_chance": mods["total_chance"],
            },
        }
