# data/fishing_data.py

from typing import Dict, Any, TypedDict

class FishData(TypedDict):
    rarity: str
    value: int
    chance: float

class RodData(TypedDict):
    chance: float
    cost: int
    description: str

class BaitData(TypedDict):
    value: int
    catch_bonus: float
    cost: int
    description: str
    daily_stock: int

# Fish types with expanded details
FISH_TYPES: Dict[str, FishData] = {
    "Common Fish": {
        "rarity": "common",
        "value": 3,
        "chance": 0.6,
        "variants": [
            "Bluegill",
            "Bass",
            "Perch",
            "Carp",
            "Catfish"
        ]
    },
    "Uncommon Fish": {
        "rarity": "uncommon",
        "value": 7,
        "chance": 0.25,
        "variants": [
            "Salmon",
            "Trout",
            "Pike",
            "Walleye",
            "Tuna"
        ]
    },
    "Rare Fish": {
        "rarity": "rare",
        "value": 12,
        "chance": 0.1,
        "variants": [
            "Swordfish",
            "Marlin",
            "Sturgeon",
            "Mahi-mahi",
            "Barracuda"
        ]
    },
    "Legendary Fish": {
        "rarity": "legendary",
        "value": 50,
        "chance": 0.05,
        "variants": [
            "Golden Koi",
            "Giant Tuna",
            "Megalodon",
            "Rainbow Trout",
            "Ancient Sturgeon"
        ]
    }
}

# Rod types with expanded details
ROD_TYPES: Dict[str, RodData] = {
    "Basic Rod": {
        "chance": 0.0,
        "cost": 0,
        "durability": 100,
        "description": "A simple fishing rod. Gets the job done.",
        "requirements": None
    },
    "Intermediate Rod": {
        "chance": 0.1,
        "cost": 50,
        "durability": 200,
        "description": "Better quality rod with improved catch rates.",
        "requirements": {
            "level": 5,
            "fish_caught": 50
        }
    },
    "Advanced Rod": {
        "chance": 0.2,
        "cost": 100,
        "durability": 300,
        "description": "Professional grade rod with excellent catch rates.",
        "requirements": {
            "level": 10,
            "fish_caught": 200
        }
    }
}

# Bait types with expanded details
BAIT_TYPES: Dict[str, BaitData] = {
    "Worm": {
        "value": 1,
        "catch_bonus": 0.1,
        "cost": 1,
        "description": "Basic bait that attracts common fish.",
        "daily_stock": 10,
        "preferred_by": ["Common Fish"],
        "effectiveness": {
            "Pond": 1.2,
            "Ocean": 0.8
        }
    },
    "Shrimp": {
        "value": 2,
        "catch_bonus": 0.2,
        "cost": 3,
        "description": "Medium-grade bait, good for various fish types.",
        "daily_stock": 10,
        "preferred_by": ["Uncommon Fish"],
        "effectiveness": {
            "Pond": 0.8,
            "Ocean": 1.2
        }
    },
    "Cricket": {
        "value": 3,
        "catch_bonus": 0.3,
        "cost": 5,
        "description": "Premium bait with high catch bonus.",
        "daily_stock": 10,
        "preferred_by": ["Rare Fish"],
        "effectiveness": {
            "Pond": 1.5,
            "Ocean": 0.7
        }
    }
}

# Fishing locations with specific characteristics
LOCATIONS = {
    "Pond": {
        "description": "A peaceful freshwater pond.",
        "fish_modifiers": {
            "Common Fish": 1.2,
            "Uncommon Fish": 1.0,
            "Rare Fish": 0.8,
            "Legendary Fish": 0.5
        },
        "weather_effects": True,
        "requirements": None
    },
    "Ocean": {
        "description": "Vast open waters with diverse fish.",
        "fish_modifiers": {
            "Common Fish": 0.8,
            "Uncommon Fish": 1.2,
            "Rare Fish": 1.2,
            "Legendary Fish": 1.0
        },
        "weather_effects": True,
        "requirements": {
            "level": 5,
            "fish_caught": 50
        }
    },
    "Deep Sea": {
        "description": "Mysterious deep waters with rare catches.",
        "fish_modifiers": {
            "Common Fish": 0.5,
            "Uncommon Fish": 0.8,
            "Rare Fish": 1.5,
            "Legendary Fish": 2.0
        },
        "weather_effects": True,
        "requirements": {
            "level": 10,
            "fish_caught": 200
        }
    }
}

# Weather effects on fishing
WEATHER_TYPES = {
    "Sunny": {
        "catch_bonus": 0.1,
        "description": "Perfect weather for fishing!",
        "affects_locations": ["Pond", "Ocean"]
    },
    "Rainy": {
        "catch_bonus": 0.2,
        "description": "Fish are more active in the rain.",
        "affects_locations": ["Pond", "Ocean", "Deep Sea"]
    },
    "Stormy": {
        "catch_bonus": -0.1,
        "rare_bonus": 0.15,
        "description": "Dangerous conditions, but rare fish are about!",
        "affects_locations": ["Ocean", "Deep Sea"]
    },
    "Foggy": {
        "catch_bonus": 0.05,
        "description": "Mysterious conditions that bring unique opportunities.",
        "affects_locations": ["Pond", "Deep Sea"]
    }
}

# Time of day effects
TIME_EFFECTS = {
    "Dawn": {
        "catch_bonus": 0.15,
        "description": "Early morning feeding time.",
        "duration_hours": 2
    },
    "Day": {
        "catch_bonus": 0.0,
        "description": "Standard fishing conditions.",
        "duration_hours": 8
    },
    "Dusk": {
        "catch_bonus": 0.15,
        "description": "Evening feeding time.",
        "duration_hours": 2
    },
    "Night": {
        "catch_bonus": -0.1,
        "rare_bonus": 0.2,
        "description": "Harder to catch fish, but rare ones are active.",
        "duration_hours": 12
    }
}
