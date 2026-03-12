# data/casino_data.py

from typing import Dict, List, Optional, TypedDict, Union


# ---------------------------------------------------------------------------
# TypedDict definitions
# ---------------------------------------------------------------------------

class SlotSymbolData(TypedDict):
    emoji: str
    weight: int
    payout_2: float  # payout multiplier for 2-of-a-kind
    payout_3: float  # payout multiplier for 3-of-a-kind


class BlackjackPayouts(TypedDict):
    blackjack: float   # natural 21 payout multiplier (e.g. 1.5 = 3:2)
    win: float         # standard win multiplier
    push: float        # push return multiplier (1.0 = bet returned)
    insurance: float   # insurance payout multiplier
    surrender: float   # surrender return multiplier


class BetLimits(TypedDict):
    min: int
    max: int


class JackpotConfig(TypedDict):
    seed_amount: int
    contribution_rate: float  # fraction of each slots bet added to jackpot


class GameStatsData(TypedDict):
    games_played: int
    games_won: int
    games_lost: int
    total_wagered: int
    total_won: int
    biggest_win: int


class BlackjackStatsData(GameStatsData):
    games_pushed: int
    blackjacks_hit: int


class SlotsStatsData(GameStatsData):
    jackpots_won: int
    jackpot_total: int


class OverallStatsData(TypedDict):
    total_wagered: int
    total_won: int
    net_profit: int
    biggest_win: int
    biggest_win_game: str


# ---------------------------------------------------------------------------
# Blackjack configuration
# ---------------------------------------------------------------------------

BLACKJACK_CONFIG = {
    "deck_count": 6,
    "reshuffle_threshold": 0.25,  # reshuffle when <25% cards remain
    "dealer_stands_on_soft_17": True,
    "max_splits": 3,  # max number of splits (4 hands total)
    "double_after_split": True,
}

DEFAULT_BLACKJACK_PAYOUTS: BlackjackPayouts = {
    "blackjack": 1.5,   # 3:2
    "win": 1.0,         # 1:1
    "push": 0.0,        # bet returned, no profit
    "insurance": 2.0,   # 2:1
    "surrender": -0.5,  # lose half the bet
}


# ---------------------------------------------------------------------------
# Slots configuration — fishing-themed symbols
# ---------------------------------------------------------------------------

# Symbols ordered from lowest to highest value.
# Weight controls how often each symbol appears on a reel.
# 3x Kiwi is the jackpot trigger.
SLOTS_SYMBOLS: Dict[str, SlotSymbolData] = {
    "Seaweed": {
        "emoji": "\U0001F33F",   # 🌿
        "weight": 30,
        "payout_2": 0.5,
        "payout_3": 1.0,
    },
    "Shell": {
        "emoji": "\U0001F41A",   # 🐚
        "weight": 25,
        "payout_2": 1.0,
        "payout_3": 2.0,
    },
    "Crab": {
        "emoji": "\U0001F980",   # 🦀
        "weight": 20,
        "payout_2": 1.5,
        "payout_3": 4.0,
    },
    "Fish": {
        "emoji": "\U0001F41F",   # 🐟
        "weight": 15,
        "payout_2": 2.0,
        "payout_3": 8.0,
    },
    "Octopus": {
        "emoji": "\U0001F419",   # 🐙
        "weight": 7,
        "payout_2": 3.0,
        "payout_3": 15.0,
    },
    "Treasure": {
        "emoji": "\U0001F4B0",   # 💰
        "weight": 2,
        "payout_2": 5.0,
        "payout_3": 30.0,
    },
    "Kiwi": {
        "emoji": "\U0001F95D",   # 🥝
        "weight": 1,
        "payout_2": 10.0,
        "payout_3": 0.0,  # 3x Kiwi triggers jackpot, not a fixed payout
    },
}

# Number of reels
SLOTS_REEL_COUNT = 3


# ---------------------------------------------------------------------------
# Coinflip configuration
# ---------------------------------------------------------------------------

DEFAULT_COINFLIP_PAYOUT = 1.95  # <2.0 gives ~2.5% house edge per flip


# ---------------------------------------------------------------------------
# Bet limits (per game, configurable by admins)
# ---------------------------------------------------------------------------

DEFAULT_BET_LIMITS: Dict[str, BetLimits] = {
    "blackjack": {"min": 10, "max": 5000},
    "slots": {"min": 5, "max": 1000},
    "coinflip": {"min": 10, "max": 10000},
}


# ---------------------------------------------------------------------------
# Payout multipliers (per game, configurable by admins)
# ---------------------------------------------------------------------------

DEFAULT_PAYOUT_MULTIPLIERS = {
    "blackjack": DEFAULT_BLACKJACK_PAYOUTS,
    "coinflip": DEFAULT_COINFLIP_PAYOUT,
    # Slots payouts are defined per-symbol in SLOTS_SYMBOLS and are not
    # individually configurable. An overall slots payout scalar is provided.
    "slots": 1.0,  # multiplier applied to all slots winnings
}


# ---------------------------------------------------------------------------
# Progressive jackpot defaults
# ---------------------------------------------------------------------------

DEFAULT_JACKPOT_CONFIG: JackpotConfig = {
    "seed_amount": 1000,
    "contribution_rate": 0.05,  # 2% of each slots bet feeds the jackpot
}

# Jackpot odds — 1 in N chance per spin (independent of symbol weights)
JACKPOT_ODDS = 1_800


# ---------------------------------------------------------------------------
# Card constants (for blackjack display)
# ---------------------------------------------------------------------------

CARD_SUITS = ["\u2660", "\u2665", "\u2666", "\u2663"]  # ♠ ♥ ♦ ♣
CARD_RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

CARD_VALUES = {
    "A": 11,  # adjusted to 1 when hand > 21
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
    "J": 10, "Q": 10, "K": 10,
}


# ---------------------------------------------------------------------------
# Game names (canonical list)
# ---------------------------------------------------------------------------

GAME_NAMES = ["blackjack", "slots", "coinflip"]


# ---------------------------------------------------------------------------
# Default user data schema (per-user stats, registered via config.register_user)
# ---------------------------------------------------------------------------

DEFAULT_USER_DATA = {
    "stats": {
        "blackjack": {
            "games_played": 0,
            "games_won": 0,
            "games_lost": 0,
            "games_pushed": 0,
            "blackjacks_hit": 0,
            "total_wagered": 0,
            "total_won": 0,
            "biggest_win": 0,
        },
        "slots": {
            "games_played": 0,
            "games_won": 0,
            "games_lost": 0,
            "total_wagered": 0,
            "total_won": 0,
            "biggest_win": 0,
            "jackpots_won": 0,
            "jackpot_total": 0,
        },
        "coinflip": {
            "games_played": 0,
            "games_won": 0,
            "games_lost": 0,
            "total_wagered": 0,
            "total_won": 0,
            "biggest_win": 0,
        },
    },
    "overall": {
        "total_wagered": 0,
        "total_won": 0,
        "net_profit": 0,
        "biggest_win": 0,
        "biggest_win_game": "",
    },
}


# ---------------------------------------------------------------------------
# Default guild settings (registered via config.register_guild)
# ---------------------------------------------------------------------------

DEFAULT_GUILD_SETTINGS = {
    "games_enabled": {
        "blackjack": True,
        "slots": True,
        "coinflip": True,
    },
    "bet_limits": {
        "blackjack": {"min": 10, "max": 5000},
        "slots": {"min": 5, "max": 1000},
        "coinflip": {"min": 10, "max": 10000},
    },
    "payout_multipliers": {
        "blackjack": {
            "blackjack": 1.5,
            "win": 1.0,
            "push": 0.0,
            "insurance": 2.0,
            "surrender": -0.5,
        },
        "coinflip": 1.95,
        "slots": 1.0,
    },
    "jackpot": {
        "current_amount": 1000,
        "seed_amount": 1000,
        "contribution_rate": 0.05,
    },
    "payout_log": [],
    "payout_log_max": 500,
}
