from typing import Dict, Any, TypedDict, List, Union, Literal

# Enhanced type definitions
class FishData(TypedDict):
    rarity: Literal["common", "uncommon", "rare", "legendary"]
    value: int
    chance: float
    variants: List[str]

class RodData(TypedDict):
    chance: float
    cost: int
    durability: int
    description: str
    requirements: Union[None, Dict[str, int]]

class BaitData(TypedDict):
    value: int
    catch_bonus: float
    cost: int
    description: str
    daily_stock: int
    preferred_by: List[str]
    effectiveness: Dict[str, float]

class LocationData(TypedDict):
    description: str
    fish_modifiers: Dict[str, float]
    weather_effects: bool
    requirements: Union[None, Dict[str, int]]

class WeatherData(TypedDict):
    catch_bonus: float
    description: str
    affects_locations: List[str]
    rare_bonus: float

class TimeData(TypedDict):
    catch_bonus: float
    description: str
    duration_hours: int
    rare_bonus: float

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
    },
}

JUNK_TYPES: Dict[str, FishData] = {
    "Common Junk": {
        "rarity": "common",
        "value": 1,
        "chance": 0.7,
        "variants": [
            "Old Boot",
            "Tin Can",
            "Seaweed",
            "Broken Bottle",
            "Plastic Bag"
        ]
    },
    "Uncommon Junk": {
        "rarity": "uncommon",
        "value": 2,
        "chance": 0.15,
        "variants": [
            "Rusty Chain",
            "Waterlogged Book",
            "Old Fishing Line",
            "Broken Fishing Rod",
            "Tattered Net"
        ]
    },
    "Rare Junk": {
        "rarity": "rare",
        "value": 5,
        "chance": 0.1,
        "variants": [
            "Ancient Pottery",
            "Ship's Compass",
            "Lost Jewelry",
            "Antique Bottle",
            "Weather-Worn Map"
        ]
    },
    "Legendary Junk": {
        "rarity": "legendary",
        "value": 15,
        "chance": 0.05,
        "variants": [
            "Sunken Treasure",
            "Ancient Artifact",
            "Lost Technology",
            "Time Capsule",
            "Mysterious Device"
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
        "daily_stock": 1000,
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
        "daily_stock": 500,
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
        "daily_stock": 250,
        "preferred_by": ["Rare Fish"],
        "effectiveness": {
            "Pond": 1.5,
            "Ocean": 0.7
        }
    },
    "Nightcrawler": {
        "value": 4,
        "catch_bonus": 0.4,
        "cost": 8,
        "description": "A fat worm even Legendary fish can't resist.",
        "daily_stock": 100,
        "preferred_by": ["Legendary Fish"],
        "effectiveness": {
            "Pond": 1.5,
            "Ocean": 0.7
        }
    },
        "Dev Bait": {
        "value": 5,
        "catch_bonus": 1,
        "cost": 999999,
        "description": "A bait guaranteed to catch fish, designed by the Ancient Immortal",
        "daily_stock": 0,
        "preferred_by": ["Legendary Fish"],
        "effectiveness": {}
    }
}

# Fishing locations with specific characteristics
LOCATIONS: Dict[str, LocationData] = {
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
WEATHER_TYPES: Dict[str, WeatherData] = {
    "Sunny": {
        "catch_bonus": 0.1,
        "description": "Perfect weather for fishing!",
        "affects_locations": ["Pond", "Ocean"],
        "rare_bonus": 0.0
    },
    "Rainy": {
        "catch_bonus": 0.2,
        "description": "Fish are more active in the rain.",
        "affects_locations": ["Pond", "Ocean", "Deep Sea"],
        "rare_bonus": 0.1
    },
    "Stormy": {
        "catch_bonus": -0.1,
        "description": "Dangerous conditions, but rare fish are about!",
        "affects_locations": ["Ocean", "Deep Sea"],
        "rare_bonus": 0.15
    },
    "Foggy": {
        "catch_bonus": 0.05,
        "description": "Mysterious conditions that bring unique opportunities.",
        "affects_locations": ["Pond", "Deep Sea"],
        "rare_bonus": 0.05
    }
}

# Time of day effects
TIME_EFFECTS: Dict[str, TimeData] = {
    "Dawn": {
        "catch_bonus": 0.15,
        "description": "Early morning feeding time.",
        "duration_hours": 2,
        "rare_bonus": 0.05
    },
    "Day": {
        "catch_bonus": 0.0,
        "description": "Standard fishing conditions.",
        "duration_hours": 8,
        "rare_bonus": 0.0
    },
    "Dusk": {
        "catch_bonus": 0.15,
        "description": "Evening feeding time.",
        "duration_hours": 2,
        "rare_bonus": 0.05
    },
    "Night": {
        "catch_bonus": -0.1,
        "description": "Harder to catch fish, but rare ones are active.",
        "duration_hours": 12,
        "rare_bonus": 0.2
    }
}

# Default user data structure
DEFAULT_USER_DATA = {
    "inventory": [],
    "rod": "Basic Rod",
    "total_value": 0,
    "daily_quest": None,
    "bait": {},
    "purchased_rods": {"Basic Rod": True},
    "equipped_bait": None,
    "current_location": "Pond",
    "fish_caught": 0,
    "level": 1,
    "settings": {
        "notifications": True,
        "auto_sell": False
    }
}

# Default global settings
DEFAULT_GLOBAL_SETTINGS = {
    "bait_stock": {
        bait: data["daily_stock"]
        for bait, data in BAIT_TYPES.items()
    },
    "current_weather": "Sunny",
    "active_events": [],
    "settings": {
        "daily_reset_hour": 0,
        "weather_change_interval": 3600
    }
}
