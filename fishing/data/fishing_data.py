from typing import Dict, Any, TypedDict, List, Union, Literal, Optional

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
    requirements: Union[None, Dict[str, int]]

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
    location_bonus: Optional[Dict[str, float]]
    time_multiplier: Optional[Dict[str, float]]
    catch_quantity: Optional[float]
    specific_rarity_bonus: Optional[Dict[str, float]]
    duration_hours: Optional[int]

class TimeData(TypedDict):
    catch_bonus: float
    description: str
    duration_hours: int
    rare_bonus: float

# Fish types
FISH_TYPES = {
    "Common Fish": {
        "rarity": "common",
        "value": 5,
        "chance": 0.65,
        "variants": ["Bluegill", "Bass", "Perch", "Carp", "Catfish"]
    },
    "Uncommon Fish": {
        "rarity": "uncommon",
        "value": 12,
        "chance": 0.22,
        "variants": ["Salmon", "Trout", "Pike", "Walleye", "Tuna"]
    },
    "Rare Fish": {
        "rarity": "rare",
        "value": 45,
        "chance": 0.11,
        "variants": ["Swordfish", "Marlin", "Sturgeon", "Mahi-mahi", "Barracuda"]
    },
    "Legendary Fish": {
        "rarity": "legendary",
        "value": 150,
        "chance": 0.02,
        "variants": ["Golden Koi", "Giant Tuna", "Megalodon", "Rainbow Trout", "Ancient Sturgeon"]
    }
}

JUNK_TYPES = {
    "Common Junk": {
        "rarity": "common",
        "value": 2,
        "chance": 0.7,
        "variants": ["Old Boot", "Tin Can", "Seaweed", "Broken Bottle", "Plastic Bag"]
    },
    "Uncommon Junk": {
        "rarity": "uncommon",
        "value": 4,
        "chance": 0.15,
        "variants": ["Rusty Chain", "Waterlogged Book", "Old Fishing Line", "Broken Fishing Rod", "Tattered Net"]
    },
    "Rare Junk": {
        "rarity": "rare",
        "value": 10,
        "chance": 0.1,
        "variants": ["Ancient Pottery", "Ship's Compass", "Lost Jewelry", "Antique Bottle", "Weather-Worn Map"]
    },
    "Legendary Junk": {
        "rarity": "legendary",
        "value": 30,
        "chance": 0.05,
        "variants": ["Sunken Treasure", "Ancient Artifact", "Lost Technology", "Time Capsule", "Mysterious Device"]
    }
}

# Rod types
ROD_TYPES = {
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
    },
    "Expert Rod": {
        "chance": 0.3,
        "cost": 250,
        "durability": 400,
        "description": "Masterfully crafted rod for serious anglers.",
        "requirements": {
            "level": 15,
            "fish_caught": 500
        }
    },
    "Master Rod": {
        "chance": 0.4,
        "cost": 500,
        "durability": 500,
        "description": "Legendary rod with exceptional catch rates.",
        "requirements": {
            "level": 20,
            "fish_caught": 1000
        }
    }
}

# Bait types
BAIT_TYPES = {
    "Worm": {
        "value": 1,
        "catch_bonus": 0.1,
        "cost": 1,
        "description": "Basic bait that attracts common fish.",
        "daily_stock": 1000,
        "preferred_by": ["Common Fish"],
        "effectiveness": {
            "Pond": 1.2,
            "River": 0.8,
            "Lake": 1.0
        },
        "requirements": None
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
            "River": 1.2,
            "Lake": 1.0,
            "Ocean": 1.2
        },
        "requirements": {
            "level": 5
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
            "River": 1.2,
            "Lake": 1.3,
            "Ocean": 0.7
        },
        "requirements": {
            "level": 10
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
            "River": 1.3,
            "Lake": 1.4,
            "Ocean": 0.7,
            "Deep Sea": 1.0
        },
        "requirements": {
            "level": 15
        }
    },
    "Firefly": {
        "value": 5,
        "catch_bonus": 0.35,
        "cost": 10,
        "description": "Glowing bait that attracts exotic fish at night.",
        "daily_stock": 150,
        "preferred_by": ["Rare Fish", "Legendary Fish"],
        "effectiveness": {
            "Pond": 1.8,
            "River": 1.5,
            "Lake": 1.6,
            "Ocean": 0.5
        },
        "requirements": {
            "level": 12
        }
    },
    "Anchovy": {
        "value": 6,
        "catch_bonus": 0.45,
        "cost": 12,
        "description": "Small fish bait perfect for ocean fishing.",
        "daily_stock": 80,
        "preferred_by": ["Rare Fish", "Legendary Fish"],
        "effectiveness": {
            "Ocean": 1.8,
            "Deep Sea": 1.5,
            "Pond": 0.5,
            "River": 0.5
        },
        "requirements": {
            "level": 18
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
    "River": {
        "description": "Fast-flowing waters with active fish.",
        "fish_modifiers": {
            "Common Fish": 1.0,
            "Uncommon Fish": 1.2,
            "Rare Fish": 1.0,
            "Legendary Fish": 0.8
        },
        "weather_effects": True,
        "requirements": {
            "level": 3,
            "fish_caught": 25
        }
    },
    "Lake": {
        "description": "Deep, calm waters with diverse species.",
        "fish_modifiers": {
            "Common Fish": 0.8,
            "Uncommon Fish": 1.1,
            "Rare Fish": 1.2,
            "Legendary Fish": 1.0
        },
        "weather_effects": True,
        "requirements": {
            "level": 8,
            "fish_caught": 100
        }
    },
    "Ocean": {
        "description": "Vast open waters with diverse fish.",
        "fish_modifiers": {
            "Common Fish": 0.6,
            "Uncommon Fish": 1.0,
            "Rare Fish": 1.4,
            "Legendary Fish": 1.2
        },
        "weather_effects": True,
        "requirements": {
            "level": 12,
            "fish_caught": 250
        }
    },
    "Deep Sea": {
        "description": "Mysterious deep waters with rare catches.",
        "fish_modifiers": {
            "Common Fish": 0.4,
            "Uncommon Fish": 0.8,
            "Rare Fish": 1.6,
            "Legendary Fish": 2.0
        },
        "weather_effects": True,
        "requirements": {
            "level": 18,
            "fish_caught": 500
        }
    }
}

# Weather effects on fishing
WEATHER_TYPES = {
    "Sunny": {
        "catch_bonus": 0.1,
        "description": "Perfect weather for fishing!",
        "affects_locations": ["Pond", "River", "Lake", "Ocean"],
        "rare_bonus": 0.0
    },
    "Rainy": {
        "catch_bonus": 0.2,
        "description": "Fish are more active in the rain.",
        "affects_locations": ["Pond", "River", "Lake", "Ocean", "Deep Sea"],
        "rare_bonus": 0.1
    },
    "Stormy": {
        "catch_bonus": -0.15,
        "description": "Dangerous conditions, but rare fish are about!",
        "affects_locations": ["Ocean", "Deep Sea"],
        "rare_bonus": 0.25
    },
    "Foggy": {
        "catch_bonus": 0.05,
        "description": "Mysterious conditions that bring unique opportunities.",
        "affects_locations": ["Pond", "Lake", "Deep Sea"],
        "rare_bonus": 0.15
    },
    "Windy": {
        "catch_bonus": -0.05,
        "description": "Strong winds make fishing challenging but rewarding.",
        "affects_locations": ["River", "Ocean", "Deep Sea"],
        "rare_bonus": 0.2
    },
    "Clear": {
        "catch_bonus": 0.15,
        "description": "Crystal clear waters improve visibility.",
        "affects_locations": ["Pond", "River", "Lake"],
        "rare_bonus": -0.05
    },
    "Overcast": {
        "catch_bonus": 0.1,
        "description": "Dim conditions make fish less cautious.",
        "affects_locations": ["Pond", "River", "Lake", "Ocean"],
        "rare_bonus": 0.1
    },
    "Heat Wave": {
        "catch_bonus": -0.1,
        "description": "Extreme heat makes fish sluggish but they gather in deeper waters.",
        "affects_locations": ["Lake", "Deep Sea"],
        "rare_bonus": 0.2,
        "location_bonus": {
            "Deep Sea": 0.3,
            "Lake": 0.15
        }
    },
    "Full Moon": {
        "catch_bonus": 0.2,
        "description": "Moonlight brings out nocturnal species.",
        "affects_locations": ["Ocean", "Deep Sea", "Lake"],
        "rare_bonus": 0.15,
        "time_multiplier": {
            "Night": 0.3  # Additional bonus at night
        }
    },
    "Migration": {
        "catch_bonus": 0.25,
        "description": "Schools of fish are migrating through the area!",
        "affects_locations": ["River", "Ocean"],
        "rare_bonus": 0.1,
        "catch_quantity": 0.2  # 20% chance to catch additional fish
    },
    "Drought": {
        "catch_bonus": -0.2,
        "description": "Low water levels concentrate fish but make them cautious.",
        "affects_locations": ["Pond", "River"],
        "rare_bonus": 0.3,
        "specific_rarity_bonus": {
            "Legendary Fish": 0.4  # Extra bonus for legendary fish
        }
    },
    "Red Tide": {
        "catch_bonus": -0.15,
        "description": "Algal bloom brings unusual deep-sea creatures to the surface.",
        "affects_locations": ["Ocean", "Deep Sea"],
        "rare_bonus": 0.35,
        "specific_rarity_bonus": {
            "Rare Fish": 0.2,
            "Legendary Fish": 0.3
        }
    },
    "Spring Flood": {
        "catch_bonus": 0.1,
        "description": "High waters bring fish upstream and increase activity.",
        "affects_locations": ["River", "Lake"],
        "rare_bonus": 0.15,
        "location_bonus": {
            "River": 0.25
        }
    },
    "Aurora": {
        "catch_bonus": 0.15,
        "description": "The mystical lights seem to affect fish behavior.",
        "affects_locations": ["Lake", "Deep Sea"],
        "rare_bonus": 0.2,
        "time_multiplier": {
            "Night": 0.25,
            "Dusk": 0.15
        }
    },
    "School": {
        "catch_bonus": 0.3,
        "description": "A large school of fish is passing through!",
        "affects_locations": ["Ocean", "Deep Sea", "River"],
        "rare_bonus": 0.0,
        "duration_hours": 1,  # Special short duration weather
        "catch_quantity": 0.3  # 30% chance to catch additional fish
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
    "junk_caught": 0,
    "level": 1,
    "experience": 0,
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
