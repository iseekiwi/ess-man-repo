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
    preference_bonus: Optional[float]
    effectiveness: Dict[str, float]
    requirements: Union[None, Dict[str, int]]

class MaterialData(TypedDict):
    description: str
    rarity: Literal["common", "uncommon", "rare", "legendary"]
    emoji: str
    value: int

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
        "value": 10,
        "chance": 0.70,
        "variants": ["Bluegill", "Bass", "Perch", "Carp", "Catfish"]
    },
    "Uncommon Fish": {
        "rarity": "uncommon",
        "value": 25,
        "chance": 0.20,
        "variants": ["Salmon", "Trout", "Pike", "Walleye", "Tuna"]
    },
    "Rare Fish": {
        "rarity": "rare",
        "value": 65,
        "chance": 0.08,
        "variants": ["Swordfish", "Marlin", "Sturgeon", "Mahi-mahi", "Barracuda"]
    },
    "Legendary Fish": {
        "rarity": "legendary",
        "value": 200,
        "chance": 0.02,
        "variants": ["Golden Koi", "Giant Tuna", "Megalodon", "Rainbow Trout", "Ancient Sturgeon"]
    }
}

JUNK_TYPES = {
    "Common Junk": {
        "rarity": "common",
        "value": 1,
        "chance": 0.70,
        "variants": ["Old Boot", "Tin Can", "Seaweed", "Broken Bottle", "Plastic Bag"]
    },
    "Uncommon Junk": {
        "rarity": "uncommon",
        "value": 2,
        "chance": 0.15,
        "variants": ["Rusty Chain", "Waterlogged Book", "Old Fishing Line", "Broken Fishing Rod", "Tattered Net"]
    },
    "Rare Junk": {
        "rarity": "rare",
        "value": 5,
        "chance": 0.10,
        "variants": ["Ancient Pottery", "Ship's Compass", "Lost Jewelry", "Antique Bottle", "Weather-Worn Map"]
    },
    "Legendary Junk": {
        "rarity": "legendary",
        "value": 15,
        "chance": 0.05,
        "variants": ["Sunken Treasure", "Ancient Artifact", "Lost Technology", "Time Capsule", "Mysterious Device"]
    }
}

ROD_TYPES = {
    "Basic Rod": {
        "chance": 0.0,
        "cost": 0,
        "durability": 100,
        "description": "A simple fishing rod. Gets the job done.",
        "requirements": None
    },
    "Intermediate Rod": {
        "chance": 0.08,
        "cost": 250,
        "durability": 200,
        "description": "Better quality rod with improved catch rates.",
        "requirements": {
            "level": 5
        }
    },
    "Advanced Rod": {
        "chance": 0.16,
        "cost": 500,
        "durability": 300,
        "description": "Professional grade rod with excellent catch rates.",
        "requirements": {
            "level": 10
        }
    },
    "Expert Rod": {
        "chance": 0.24,
        "cost": 750,
        "durability": 400,
        "description": "Masterfully crafted rod for serious anglers.",
        "requirements": {
            "level": 15
        }
    },
    "Master Rod": {
        "chance": 0.32,
        "cost": 1000,
        "durability": 500,
        "description": "Legendary rod with exceptional catch rates.",
        "requirements": {
            "level": 20
        }
    }
}

BAIT_TYPES = {
    # --- Generalist baits: higher catch bonus, no rarity preference ---
    "Worm": {
        "value": 1,
        "catch_bonus": 0.12,
        "cost": 1,
        "description": "Basic bait that gets the job done.",
        "daily_stock": 1000,
        "preferred_by": [],
        "effectiveness": {
            "Pond": 1.2,
            "Shallow Creek": 1.1,
            "River": 0.8,
            "Lake": 1.0
        },
        "requirements": None
    },
    "Cricket": {
        "value": 4,
        "catch_bonus": 0.22,
        "cost": 6,
        "description": "Reliable bait favored by freshwater anglers.",
        "daily_stock": 400,
        "preferred_by": [],
        "effectiveness": {
            "Pond": 1.4,
            "Shallow Creek": 1.3,
            "River": 1.2,
            "Marshlands": 1.1,
            "Lake": 1.3,
            "Ocean": 0.7
        },
        "requirements": {
            "level": 15
        }
    },
    "Nightcrawler": {
        "value": 6,
        "catch_bonus": 0.30,
        "cost": 15,
        "description": "A fat worm that works well anywhere.",
        "daily_stock": 250,
        "preferred_by": [],
        "effectiveness": {
            "Pond": 1.2,
            "Shallow Creek": 1.0,
            "River": 1.2,
            "Marshlands": 1.1,
            "Lake": 1.2,
            "Coral Reef": 1.0,
            "Ocean": 1.0,
            "Deep Sea": 1.0
        },
        "requirements": {
            "level": 30
        }
    },
    "Anchovy": {
        "value": 10,
        "catch_bonus": 0.36,
        "cost": 30,
        "description": "Small fish bait that excels in deep waters.",
        "daily_stock": 150,
        "preferred_by": [],
        "effectiveness": {
            "Pond": 0.5,
            "Shallow Creek": 0.4,
            "River": 0.6,
            "Marshlands": 0.5,
            "Lake": 0.8,
            "Coral Reef": 1.4,
            "Ocean": 1.6,
            "Abyssal Trench": 1.5,
            "Deep Sea": 1.5
        },
        "requirements": {
            "level": 50
        }
    },
    "Leech": {
        "value": 12,
        "catch_bonus": 0.42,
        "cost": 45,
        "description": "Premium bait that works in any waters.",
        "daily_stock": 100,
        "preferred_by": [],
        "effectiveness": {
            "Pond": 1.3,
            "Shallow Creek": 1.3,
            "River": 1.3,
            "Marshlands": 1.3,
            "Lake": 1.3,
            "Coral Reef": 1.3,
            "Ocean": 1.3,
            "Abyssal Trench": 1.3,
            "Deep Sea": 1.3
        },
        "requirements": {
            "level": 65
        }
    },
    # --- Specialist baits: lower catch bonus, but boost targeted rarity weight ---
    "Shrimp": {
        "value": 2,
        "catch_bonus": 0.14,
        "cost": 3,
        "description": "Common fish can't resist fresh shrimp.",
        "daily_stock": 600,
        "preferred_by": ["Common Fish"],
        "preference_bonus": 2.0,
        "effectiveness": {
            "Pond": 1.3,
            "Shallow Creek": 1.5,
            "River": 1.1,
            "Marshlands": 0.8,
            "Lake": 1.0,
            "Ocean": 0.8
        },
        "requirements": {
            "level": 8
        }
    },
    "Firefly": {
        "value": 5,
        "catch_bonus": 0.20,
        "cost": 10,
        "description": "Glowing bait that lures uncommon species from hiding.",
        "daily_stock": 300,
        "preferred_by": ["Uncommon Fish"],
        "preference_bonus": 2.0,
        "effectiveness": {
            "Pond": 1.0,
            "Shallow Creek": 0.8,
            "River": 1.4,
            "Marshlands": 1.5,
            "Lake": 1.5,
            "Coral Reef": 0.9,
            "Ocean": 1.0
        },
        "requirements": {
            "level": 20
        }
    },
    "Squid": {
        "value": 8,
        "catch_bonus": 0.26,
        "cost": 22,
        "description": "Squid strips that rare fish find irresistible.",
        "daily_stock": 200,
        "preferred_by": ["Rare Fish"],
        "preference_bonus": 2.0,
        "effectiveness": {
            "Pond": 0.6,
            "River": 0.8,
            "Marshlands": 0.7,
            "Lake": 1.2,
            "Coral Reef": 1.5,
            "Ocean": 1.5,
            "Abyssal Trench": 1.2,
            "Deep Sea": 1.4
        },
        "requirements": {
            "level": 40
        }
    },
    "Glowworm": {
        "value": 15,
        "catch_bonus": 0.32,
        "cost": 40,
        "description": "Bioluminescent bait that calls to legendary fish.",
        "daily_stock": 80,
        "preferred_by": ["Legendary Fish"],
        "preference_bonus": 2.5,
        "effectiveness": {
            "Pond": 0.7,
            "River": 0.8,
            "Marshlands": 0.6,
            "Lake": 1.2,
            "Coral Reef": 1.1,
            "Ocean": 1.4,
            "Abyssal Trench": 1.8,
            "Deep Sea": 1.8
        },
        "requirements": {
            "level": 75
        }
    },
}

LOCATIONS = {
    # --- General locations: balanced modifiers, progressively better ---
    "Pond": {
        "description": "A peaceful freshwater pond.",
        "fish_modifiers": {
            "Common Fish": 1.2,
            "Uncommon Fish": 0.9,
            "Rare Fish": 0.7,
            "Legendary Fish": 0.4
        },
        "weather_effects": True,
        "requirements": None
    },
    "River": {
        "description": "Fast-flowing waters with active fish.",
        "fish_modifiers": {
            "Common Fish": 1.0,
            "Uncommon Fish": 1.1,
            "Rare Fish": 0.8,
            "Legendary Fish": 0.5
        },
        "weather_effects": True,
        "requirements": {
            "level": 10
        }
    },
    "Lake": {
        "description": "Deep, calm waters with diverse species.",
        "fish_modifiers": {
            "Common Fish": 0.9,
            "Uncommon Fish": 1.1,
            "Rare Fish": 1.0,
            "Legendary Fish": 0.7
        },
        "weather_effects": True,
        "requirements": {
            "level": 25
        }
    },
    "Ocean": {
        "description": "Vast open waters with diverse fish.",
        "fish_modifiers": {
            "Common Fish": 0.8,
            "Uncommon Fish": 1.0,
            "Rare Fish": 1.1,
            "Legendary Fish": 0.9
        },
        "weather_effects": True,
        "requirements": {
            "level": 45
        }
    },
    "Deep Sea": {
        "description": "Mysterious deep waters — the best all-around fishing spot.",
        "fish_modifiers": {
            "Common Fish": 0.7,
            "Uncommon Fish": 1.0,
            "Rare Fish": 1.2,
            "Legendary Fish": 1.1
        },
        "weather_effects": True,
        "requirements": {
            "level": 60
        }
    },
    # --- Specialist locations: heavily favor one rarity, penalize others ---
    "Shallow Creek": {
        "description": "A quiet, shallow creek teeming with common fish.",
        "fish_modifiers": {
            "Common Fish": 1.8,
            "Uncommon Fish": 0.6,
            "Rare Fish": 0.3,
            "Legendary Fish": 0.1
        },
        "weather_effects": True,
        "requirements": {
            "level": 3
        }
    },
    "Marshlands": {
        "description": "Murky wetlands where uncommon species thrive.",
        "fish_modifiers": {
            "Common Fish": 0.7,
            "Uncommon Fish": 1.8,
            "Rare Fish": 0.5,
            "Legendary Fish": 0.2
        },
        "weather_effects": True,
        "requirements": {
            "level": 12
        }
    },
    "Coral Reef": {
        "description": "Vibrant reef waters hiding rare and exotic fish.",
        "fish_modifiers": {
            "Common Fish": 0.5,
            "Uncommon Fish": 0.7,
            "Rare Fish": 1.8,
            "Legendary Fish": 0.4
        },
        "weather_effects": True,
        "requirements": {
            "level": 30
        }
    },
    "Abyssal Trench": {
        "description": "The deepest waters where legendary creatures lurk.",
        "fish_modifiers": {
            "Common Fish": 0.3,
            "Uncommon Fish": 0.5,
            "Rare Fish": 0.8,
            "Legendary Fish": 2.0
        },
        "weather_effects": True,
        "requirements": {
            "level": 55
        }
    },
}

# Weather effects on fishing
WEATHER_TYPES = {
    "Sunny": {
        "catch_bonus": 0.1,
        "description": "Perfect weather for fishing!",
        "affects_locations": ["Pond", "Shallow Creek", "River", "Marshlands", "Lake", "Ocean"],
        "rare_bonus": 0.0
    },
    "Rainy": {
        "catch_bonus": 0.2,
        "description": "Fish are more active in the rain.",
        "affects_locations": ["Pond", "Shallow Creek", "River", "Marshlands", "Lake", "Coral Reef", "Ocean", "Abyssal Trench", "Deep Sea"],
        "rare_bonus": 0.1
    },
    "Stormy": {
        "catch_bonus": -0.15,
        "description": "Dangerous conditions, but rare fish are about!",
        "affects_locations": ["Ocean", "Coral Reef", "Abyssal Trench", "Deep Sea"],
        "rare_bonus": 0.25
    },
    "Foggy": {
        "catch_bonus": 0.05,
        "description": "Mysterious conditions that bring unique opportunities.",
        "affects_locations": ["Pond", "Marshlands", "Lake", "Abyssal Trench", "Deep Sea"],
        "rare_bonus": 0.15
    },
    "Windy": {
        "catch_bonus": -0.05,
        "description": "Strong winds make fishing challenging but rewarding.",
        "affects_locations": ["River", "Ocean", "Coral Reef", "Abyssal Trench", "Deep Sea"],
        "rare_bonus": 0.2
    },
    "Clear": {
        "catch_bonus": 0.15,
        "description": "Crystal clear waters improve visibility.",
        "affects_locations": ["Pond", "Shallow Creek", "River", "Lake", "Coral Reef"],
        "rare_bonus": -0.05
    },
    "Overcast": {
        "catch_bonus": 0.1,
        "description": "Dim conditions make fish less cautious.",
        "affects_locations": ["Pond", "Shallow Creek", "River", "Marshlands", "Lake", "Ocean"],
        "rare_bonus": 0.1
    },
    "Heat Wave": {
        "catch_bonus": -0.1,
        "description": "Extreme heat makes fish sluggish but they gather in deeper waters.",
        "affects_locations": ["Lake", "Abyssal Trench", "Deep Sea"],
        "rare_bonus": 0.2,
        "location_bonus": {
            "Deep Sea": 0.3,
            "Abyssal Trench": 0.25,
            "Lake": 0.15
        }
    },
    "Full Moon": {
        "catch_bonus": 0.2,
        "description": "Moonlight brings out nocturnal species.",
        "affects_locations": ["Ocean", "Abyssal Trench", "Deep Sea", "Lake", "Marshlands"],
        "rare_bonus": 0.15,
        "time_multiplier": {
            "Night": 0.3  # Additional bonus at night
        }
    },
    "Migration": {
        "catch_bonus": 0.25,
        "description": "Schools of fish are migrating through the area!",
        "affects_locations": ["River", "Marshlands", "Ocean", "Coral Reef"],
        "rare_bonus": 0.1,
        "catch_quantity": 0.2  # 20% chance to catch additional fish
    },
    "Drought": {
        "catch_bonus": -0.2,
        "description": "Low water levels concentrate fish but make them cautious.",
        "affects_locations": ["Pond", "Shallow Creek", "River", "Marshlands"],
        "rare_bonus": 0.3,
        "specific_rarity_bonus": {
            "Legendary Fish": 0.4  # Extra bonus for legendary fish
        }
    },
    "Red Tide": {
        "catch_bonus": -0.15,
        "description": "Algal bloom brings unusual deep-sea creatures to the surface.",
        "affects_locations": ["Ocean", "Coral Reef", "Abyssal Trench", "Deep Sea"],
        "rare_bonus": 0.35,
        "specific_rarity_bonus": {
            "Rare Fish": 0.2,
            "Legendary Fish": 0.3
        }
    },
    "Spring Flood": {
        "catch_bonus": 0.1,
        "description": "High waters bring fish upstream and increase activity.",
        "affects_locations": ["River", "Shallow Creek", "Marshlands", "Lake"],
        "rare_bonus": 0.15,
        "location_bonus": {
            "River": 0.25,
            "Marshlands": 0.15
        }
    },
    "Aurora": {
        "catch_bonus": 0.15,
        "description": "The mystical lights seem to affect fish behavior.",
        "affects_locations": ["Lake", "Abyssal Trench", "Deep Sea"],
        "rare_bonus": 0.2,
        "time_multiplier": {
            "Night": 0.25,
            "Dusk": 0.15
        }
    },
    "School": {
        "catch_bonus": 0.3,
        "description": "A large school of fish is passing through!",
        "affects_locations": ["Ocean", "Coral Reef", "Deep Sea", "River"],
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

# Material types — rare drops used as crafting requirements for gear upgrades
MATERIAL_TYPES = {
    "Iron Hinge": {
        "description": "A sturdy iron hinge, salvaged from the depths.",
        "rarity": "uncommon",
        "emoji": "🔩",
        "value": 15,
    },
    "Steel Hinge": {
        "description": "A reinforced steel hinge forged with care.",
        "rarity": "rare",
        "emoji": "⚙️",
        "value": 50,
    },
    "Magic Scale": {
        "description": "A shimmering scale pulsing with arcane energy.",
        "rarity": "rare",
        "emoji": "✨",
        "value": 50,
    },
    "Magic Fish": {
        "description": "A tiny enchanted fish that glows faintly.",
        "rarity": "legendary",
        "emoji": "🐠",
        "value": 150,
    },
    "Void Scale": {
        "description": "A scale from something that should not exist.",
        "rarity": "legendary",
        "emoji": "🕳️",
        "value": 150,
    },
}

DEFAULT_INVENTORY_CAPACITY = 5

# Gear types - organized by category
GEAR_TYPES = {
    "Inventory": {
        "Fanny Pack": {
            "cost": 25,
            "description": "A small pouch that clips to your belt.",
            "effect": {"inventory_capacity": 6},
            "requirements": {"level": 3},
        },
        "Satchel": {
            "cost": 75,
            "description": "A leather bag slung over the shoulder.",
            "effect": {"inventory_capacity": 8},
            "requirements": {"level": 5},
        },
        "Basket": {
            "cost": 200,
            "description": "A woven basket for carrying your catch.",
            "effect": {"inventory_capacity": 10},
            "requirements": {"level": 8},
        },
        "Bucket": {
            "cost": 400,
            "description": "A sturdy bucket that holds a decent haul.",
            "effect": {"inventory_capacity": 12},
            "requirements": {"level": 12},
        },
        "Crate": {
            "cost": 750,
            "description": "A wooden crate with plenty of room.",
            "effect": {"inventory_capacity": 15},
            "requirements": {"level": 20},
        },
        "Creel": {
            "cost": 1500,
            "description": "A traditional fishing creel built for serious anglers.",
            "effect": {"inventory_capacity": 19},
            "requirements": {"level": 30},
        },
        "Large Crate": {
            "cost": 2500,
            "description": "An oversized crate reinforced with iron bands.",
            "effect": {"inventory_capacity": 21},
            "requirements": {"level": 35},
        },
        "Small Chest": {
            "cost": 4000,
            "description": "A compact chest with a secure latch.",
            "effect": {"inventory_capacity": 24},
            "requirements": {"level": 40},
        },
        "Medium Chest": {
            "cost": 6000,
            "description": "A proper storage chest with brass fittings.",
            "effect": {"inventory_capacity": 27},
            "requirements": {"level": 47},
            "material_cost": {"Iron Hinge": 1},
        },
        "Fishing Barrel": {
            "cost": 10000,
            "description": "A massive barrel that holds an impressive catch.",
            "effect": {"inventory_capacity": 37},
            "requirements": {"level": 65},
        },
        "Large Chest": {
            "cost": 16000,
            "description": "A heavy chest that takes two hands to carry.",
            "effect": {"inventory_capacity": 43},
            "requirements": {"level": 73},
            "material_cost": {"Steel Hinge": 1},
        },
        "Magic Fanny Pack": {
            "cost": 25000,
            "description": "A tiny pack enchanted to hold far more than it should.",
            "effect": {"inventory_capacity": 50},
            "requirements": {"level": 80},
        },
        "Almost Bottomless Bucket": {
            "cost": 40000,
            "description": "You can't quite see the bottom. Almost.",
            "effect": {"inventory_capacity": 70},
            "requirements": {"level": 85},
            "material_cost": {"Magic Scale": 1},
        },
        "Magic Satchel": {
            "cost": 60000,
            "description": "Woven with arcane thread — it defies physics.",
            "effect": {"inventory_capacity": 80},
            "requirements": {"level": 90},
        },
        "Nearly Bottomless Bucket": {
            "cost": 85000,
            "description": "Seriously, where does it all go?",
            "effect": {"inventory_capacity": 100},
            "requirements": {"level": 99},
            "material_cost": {"Magic Fish": 1},
        },
        "Void Satchel of Hell": {
            "cost": 150000,
            "description": "Forged in the abyss. Holds everything. Smells faintly of brimstone.",
            "effect": {"inventory_capacity": 200},
            "requirements": {"level": 100},
            "material_cost": {"Void Scale": 1},
        },
    },
    "Outfits": {},
    "Tools": {},
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
    "inventory_capacity": DEFAULT_INVENTORY_CAPACITY,
    "purchased_gear": [],
    "materials": {},
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
