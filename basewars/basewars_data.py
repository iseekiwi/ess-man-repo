# basewars_data.py

# Money Printer Tiers
PRINTERS = {
    "basic_printer": {
        "name": "Basic Money Printer",
        "tier": 1,
        "cost": 5000,
        "daily_income": 1000,
        "upgrade_cost": 7500,
        "upgrade_to": "advanced_printer",
        "description": "A simple money printer that generates a modest income."
    },
    "advanced_printer": {
        "name": "Advanced Money Printer",
        "tier": 2,
        "cost": 15000,
        "daily_income": 3000,
        "upgrade_cost": 25000,
        "upgrade_to": "premium_printer",
        "description": "An improved printer with better reliability and output."
    },
    "premium_printer": {
        "name": "Premium Money Printer",
        "tier": 3,
        "cost": 50000,
        "daily_income": 7500,
        "upgrade_cost": 75000,
        "upgrade_to": "elite_printer",
        "description": "High-quality printer with advanced security features."
    },
    "elite_printer": {
        "name": "Elite Money Printer",
        "tier": 4,
        "cost": 150000,
        "daily_income": 20000,
        "upgrade_cost": 250000,
        "upgrade_to": "quantum_printer",
        "description": "Military-grade printer with exceptional output."
    },
    "quantum_printer": {
        "name": "Quantum Money Printer",
        "tier": 5,
        "cost": 500000,
        "daily_income": 50000,
        "upgrade_cost": None,  # Max tier
        "upgrade_to": None,
        "description": "State-of-the-art quantum printing technology."
    }
}

# Base Upgrades
BASE_UPGRADES = {
    "walls": {
        "tier_1": {
            "name": "Basic Walls",
            "cost": 2500,
            "defense_bonus": 10,
            "health_bonus": 100,
            "upgrade_cost": 5000,
            "description": "Simple reinforced walls."
        },
        "tier_2": {
            "name": "Reinforced Walls",
            "cost": 7500,
            "defense_bonus": 25,
            "health_bonus": 250,
            "upgrade_cost": 15000,
            "description": "Strengthened walls with better durability."
        },
        "tier_3": {
            "name": "Blast Walls",
            "cost": 25000,
            "defense_bonus": 50,
            "health_bonus": 500,
            "upgrade_cost": None,
            "description": "Military-grade blast-resistant walls."
        }
    },
    "security": {
        "tier_1": {
            "name": "Basic Security System",
            "cost": 5000,
            "raid_alert": True,  # Notifies when raid starts
            "defense_bonus": 5,
            "upgrade_cost": 10000,
            "description": "Basic alarm system that alerts you of raids."
        },
        "tier_2": {
            "name": "Advanced Security System",
            "cost": 15000,
            "raid_alert": True,
            "auto_defense": True,  # Automatic defense during raids
            "defense_bonus": 15,
            "upgrade_cost": 30000,
            "description": "Advanced system with automated defense capabilities."
        },
        "tier_3": {
            "name": "Elite Security Grid",
            "cost": 50000,
            "raid_alert": True,
            "auto_defense": True,
            "shield_generator": True,  # Temporary immunity after successful raid defense
            "defense_bonus": 30,
            "upgrade_cost": None,
            "description": "Elite security with shield generator technology."
        }
    }
}

# Base Stats Per Level
BASE_STATS = {
    1: {"max_printers": 1, "max_defenses": 1, "base_health": 100},
    2: {"max_printers": 2, "max_defenses": 2, "base_health": 200},
    3: {"max_printers": 3, "max_defenses": 3, "base_health": 350},
    4: {"max_printers": 4, "max_defenses": 4, "base_health": 500},
    5: {"max_printers": 5, "max_defenses": 5, "base_health": 750},
}

# Raid Configuration
RAID_CONFIG = {
    "cooldown_hours": 24,  # Hours between allowing raids on the same base
    "minimum_level": 2,    # Minimum base level to participate in raids
    "reward_percentage": 0.25,  # Percentage of target's money that can be stolen
    "max_raid_duration": 300,  # Maximum raid duration in seconds
    "base_raid_duration": 180,  # Base raid duration in seconds
}
