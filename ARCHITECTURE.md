# ARCHITECTURE.md -- AI Agent Reference Document

> **Purpose**: This document is designed for AI agent consumption. It provides a comprehensive, structured reference of the entire Fishing cog codebase. All file paths, method signatures, data schemas, and inter-module relationships are documented for efficient parsing and code navigation.

> **Last updated**: 2026-03-09

---

## 1. Project Overview

This repository (`ess-man-repo`) is a **Red-DiscordBot cog repository** by `iseekiwi`. The primary cog is **Fishing** -- a fully interactive fishing game for Discord servers. It features:

- A button-driven interactive menu system (discord.py Views)
- An economy system integrated with Red-DiscordBot's bank
- A leveling/XP progression system (99 levels)
- Inventory management for fish, bait, and rods
- A shop with daily restocking bait and purchasable rods
- A weather system that rotates hourly and affects catch rates
- Time-of-day effects on fishing
- Multiple fishing locations unlocked by level progression
- A fishing minigame with a timed button-press mechanic
- Admin/owner commands for managing users, stock, weather, and running economy simulations
- Junk item catches as a secondary loot table

The cog is installed into a Red-DiscordBot instance via `[p]cog install <repo_url>` and loaded with `[p]load fishing`. There is no standalone build, test, or CI system. The cog runs exclusively inside a Red bot process.

A secondary **Basewars** cog exists in `basewars/` but is non-functional and not documented here.

---

## 2. Technology Stack

| Component | Details |
|-----------|---------|
| Runtime | Python 3.10+ |
| Bot Framework | [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot) (extends discord.py) |
| UI Framework | `discord.py` Views, Buttons, Modals |
| Persistence | `redbot.core.Config` (JSON-based per-user and global storage) |
| Economy | `redbot.core.bank` (deposit/withdraw credits, get balance) |
| Commands | `redbot.core.commands` (prefix-based command decorators) |
| Logging | Python `logging` module with per-module file + console handlers |
| Async | `asyncio` for background tasks, timeouts, and all I/O |

---

## 3. File Tree with Descriptions

```
ess-man-repo/
+-- README.md                          # Brief repo description
+-- CLAUDE.md                          # AI coding assistant guidance
+-- ARCHITECTURE.md                    # This file
+-- info.json                          # Red repo metadata (author, name, tags)
+-- fishing/
|   +-- __init__.py                    # Cog entry point: calls bot.add_cog(Fishing(bot))
|   +-- info.json                      # Red cog metadata (author, install_msg, tags)
|   +-- main.py                        # Main Fishing cog class (~1315 lines)
|   +-- data/
|   |   +-- __init__.py                # Empty
|   |   +-- fishing_data.py            # All game constants, TypedDicts, default schemas
|   +-- ui/
|   |   +-- __init__.py                # Empty
|   |   +-- base.py                    # BaseView, ConfirmView (shared view base classes)
|   |   +-- menu.py                    # FishingMenuView (main menu + fishing minigame)
|   |   +-- shop.py                    # ShopView, PurchaseConfirmView, BaitQuantityModal
|   |   +-- inventory.py               # InventoryView (browse/sell caught items)
|   |   +-- simulate.py               # SimulationMenuView (interactive profit simulation menu)
|   |   +-- components.py              # ConfirmationButton, NavigationButton, MessageManager
|   +-- utils/
|       +-- __init__.py                # Empty
|       +-- config_manager.py          # ConfigManager, ConfigResult (config + caching layer)
|       +-- inventory_manager.py       # InventoryManager (fish/bait/rod operations)
|       +-- level_manager.py           # LevelManager (XP thresholds, level calc, award_xp)
|       +-- task_manager.py            # TaskManager (weather rotation, stock reset tasks)
|       +-- timeout_manager.py         # TimeoutManager (singleton, view timeout hierarchy)
|       +-- logging_config.py          # LoggerManager (singleton), get_logger() factory
|       +-- profit_simulator.py        # ProfitSimulator (economy analysis tool)
+-- basewars/                          # Non-functional cog (not documented)
    +-- basewars.py
    +-- base_manager.py
    +-- basewars_data.py
    +-- economy_manager.py
    +-- inventory_manager.py
    +-- shop_manager.py
```

---

## 4. Detailed Module Documentation

### 4.1 `fishing/__init__.py`

Entry point for the cog. Red-DiscordBot calls `setup(bot)` which adds the `Fishing` cog instance.

```python
from .main import Fishing

async def setup(bot):
    await bot.add_cog(Fishing(bot))
```

### 4.2 `fishing/main.py` -- The `Fishing` Cog Class

**Class**: `Fishing(commands.Cog)`

Central orchestrator. Initializes all managers, defines bot commands, and contains core game logic.

#### Constructor (`__init__`)

```python
def __init__(self, bot: Red):
```

Initializes:
- `self.config_manager` = `ConfigManager(bot, identifier=123456789)`
- `self.level_manager` = `LevelManager(self.config_manager)`
- `self.data` = dict mapping `"fish"`, `"rods"`, `"bait"`, `"locations"`, `"weather"`, `"time"`, `"junk"` to their respective constants from `fishing_data.py`
- `self.inventory` = `InventoryManager(bot, self.config_manager, self.data)`
- `self.bg_task_manager` = `TaskManager(bot, self.config_manager, self.data)`

#### Lifecycle Methods

```python
async def cog_load(self) -> None
```
Called after cog is added. Initializes bait stock defaults if missing, sets `last_weather_change`, starts background tasks.

```python
def cog_unload(self) -> None
```
Stops background tasks and cleans up TimeoutManager.

#### Core Game Methods

```python
def get_time_of_day(self) -> str
```
Returns `"Dawn"` (5-7), `"Day"` (7-17), `"Dusk"` (17-19), or `"Night"` (19-5) based on system clock hour.

```python
async def create_menu(self, ctx, user_data) -> FishingMenuView
```
Factory method that creates and sets up a `FishingMenuView`.

```python
async def _ensure_user_data(self, user) -> Optional[dict]
```
Gets user data via `ConfigManager`, returns `None` on failure.

```python
async def _catch_fish(
    self, user: discord.Member, user_data: dict,
    bait_type: str, location: str, weather: str, time_of_day: str
) -> Optional[dict]
```
Core catch calculation. Returns a dict with keys:
- `"name"`: str -- fish/junk type name (e.g., `"Common Fish"`)
- `"value"`: int -- coin value
- `"xp_gained"`: int -- XP reward
- `"type"`: `"fish"` or `"junk"`
- `"bonus_catch"`: Optional[dict] -- if weather grants bonus catch (`{"name": str, "value": int}`)

**Catch logic flow**:
1. Sum modifiers: rod chance + bait bonus + weather bonus (if location affected) + time bonus
2. Roll `random.random()` against total chance
3. On success: weighted random selection from `FISH_TYPES` using location modifiers and rare bonuses; may roll bonus catch from weather `catch_quantity`
4. On failure: 75% chance to roll from `JUNK_TYPES` instead; junk gives 50% XP modifier

```python
async def _add_to_inventory(self, user: discord.Member, item_name: str) -> bool
```
Adds a fish or junk item to inventory via `InventoryManager.add_item()` using `"inventory"` item type.

```python
async def is_inventory_full(self, user_id: int) -> bool
```
Checks if user's inventory has reached `inventory_capacity` (default 5, per-user upgradeable via gear). Called by `do_fishing` to block fishing when full.

```python
async def _update_total_value(self, user, value: int, *, item_type: str = "fish") -> bool
```
Updates `total_value`, recalculates `level` (as `fish_caught // 50`), increments `fish_caught` if `item_type == "fish"`.

```python
async def _handle_bait_purchase(self, user, bait_name: str, amount: int, user_data: dict) -> tuple[bool, str]
```
Full bait purchase flow: validates stock, updates global stock, adds to inventory, withdraws credits. Includes rollback on failure.

```python
async def _handle_rod_purchase(self, user, rod_name: str, user_data: dict) -> tuple[bool, str]
```
Rod purchase flow: checks requirements, checks ownership, adds to inventory, withdraws credits. Includes rollback.

```python
async def _can_afford(self, user, cost: int) -> bool
```
Checks `bank.get_balance(user) >= cost`.

```python
async def _equip_rod(self, user: discord.Member, rod_name: str) -> tuple[bool, str]
```
Sets `user_data["rod"]` via ConfigManager. Validates rod is owned.

```python
async def _equip_bait(self, user: discord.Member, bait_name: str) -> tuple[bool, str]
```
Sets `user_data["equipped_bait"]` via ConfigManager. Validates bait quantity > 0.

```python
async def sell_fish(self, ctx: commands.Context) -> tuple[bool, int, str]
```
Sells all inventory items (fish + junk). Clears inventory list, deposits credits via `bank.deposit_credits()`.

```python
async def check_requirements(self, user_data: dict, requirements: dict) -> tuple[bool, str]
```
Checks if user meets level requirement from a requirements dict.

#### Bot Commands

| Command | Access | Description |
|---------|--------|-------------|
| `[p]fish` | Everyone | Opens the main fishing menu (FishingMenuView) |
| `[p]manage add <type> <member> <name> [amount]` | Owner | Add items to a user's inventory |
| `[p]manage remove <type> <member> <name> [amount]` | Owner | Remove items from a user's inventory |
| `[p]manage reset <member>` | Owner | Reset a user's fishing data to defaults |
| `[p]manage stock` | Owner | Reset bait shop stock to defaults |
| `[p]manage level <member> <level>` | Owner | Set a user's fishing level |
| `[p]stockstatus` | Owner | Show current bait stock and background task status |
| `[p]weathertest simulate <weather> [location] [trials]` | Owner | Simulate catches with specific weather (default 100 trials) |
| `[p]weathertest info [weather]` | Owner | Show weather effect details (all or specific) |
| `[p]weathertest set <weather>` | Owner | Manually set current weather |
| `[p]simulate` | Owner | Open interactive simulation menu (configure rod, bait, location, weather, time, duration) |

### 4.3 `fishing/data/fishing_data.py` -- Game Constants and Schemas

#### TypedDict Definitions

```python
class FishData(TypedDict):
    rarity: Literal["common", "uncommon", "rare", "legendary"]
    value: int
    chance: float
    variants: List[str]

class RodData(TypedDict):
    chance: float          # Catch bonus (0.0 to 0.32)
    cost: int
    durability: int        # Not currently used in gameplay
    description: str
    requirements: Union[None, Dict[str, int]]  # {"level": int}

class BaitData(TypedDict):
    value: int
    catch_bonus: float     # Added to catch chance (0.12 to 0.42)
    cost: int
    description: str
    daily_stock: int       # Restocked daily
    preferred_by: List[str]  # Not currently used in catch logic
    effectiveness: Dict[str, float]  # Per-location multipliers (not currently used)
    requirements: Union[None, Dict[str, int]]

class LocationData(TypedDict):
    description: str
    fish_modifiers: Dict[str, float]  # Multiplier per fish type
    weather_effects: bool   # Not currently checked (all locations check via affects_locations)
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
```

#### Game Data Constants

**`FISH_TYPES`** (4 entries):

| Name | Rarity | Value | Base Chance | Variants (5 each) |
|------|--------|-------|-------------|-----|
| Common Fish | common | 3 | 0.70 | Bluegill, Bass, Perch, Carp, Catfish |
| Uncommon Fish | uncommon | 8 | 0.20 | Salmon, Trout, Pike, Walleye, Tuna |
| Rare Fish | rare | 20 | 0.08 | Swordfish, Marlin, Sturgeon, Mahi-mahi, Barracuda |
| Legendary Fish | legendary | 60 | 0.02 | Golden Koi, Giant Tuna, Megalodon, Rainbow Trout, Ancient Sturgeon |

**`JUNK_TYPES`** (4 entries):

| Name | Rarity | Value | Base Chance | Variants (5 each) |
|------|--------|-------|-------------|-----|
| Common Junk | common | 1 | 0.70 | Old Boot, Tin Can, Seaweed, Broken Bottle, Plastic Bag |
| Uncommon Junk | uncommon | 2 | 0.15 | Rusty Chain, Waterlogged Book, etc. |
| Rare Junk | rare | 5 | 0.10 | Ancient Pottery, Ship's Compass, etc. |
| Legendary Junk | legendary | 15 | 0.05 | Sunken Treasure, Ancient Artifact, etc. |

**`ROD_TYPES`** (5 entries):

| Name | Catch Bonus | Cost | Durability | Level Req |
|------|-------------|------|------------|-----------|
| Basic Rod | +0% | 0 | 100 | None |
| Intermediate Rod | +8% | 250 | 200 | 5 |
| Advanced Rod | +16% | 500 | 300 | 10 |
| Expert Rod | +24% | 750 | 400 | 15 |
| Master Rod | +32% | 1000 | 500 | 20 |

**`BAIT_TYPES`** (6 entries):

| Name | Catch Bonus | Cost | Daily Stock | Level Req |
|------|-------------|------|-------------|-----------|
| Worm | +12% | 1 | 1000 | None |
| Shrimp | +20% | 2 | 500 | 5 |
| Cricket | +28% | 4 | 250 | 10 |
| Firefly | +32% | 6 | 150 | 12 |
| Nightcrawler | +35% | 8 | 100 | 15 |
| Anchovy | +42% | 10 | 80 | 18 |

**`LOCATIONS`** (5 entries):

| Name | Level Req | Common Mod | Uncommon Mod | Rare Mod | Legendary Mod |
|------|-----------|------------|--------------|----------|---------------|
| Pond | None | 1.2 | 0.9 | 0.7 | 0.4 |
| River | 5 | 1.0 | 1.2 | 0.9 | 0.6 |
| Lake | 8 | 0.8 | 1.1 | 1.2 | 0.8 |
| Ocean | 12 | 0.6 | 1.0 | 1.4 | 1.2 |
| Deep Sea | 18 | 0.4 | 0.8 | 1.6 | 2.0 |

**`WEATHER_TYPES`** (15 entries): Sunny, Rainy, Stormy, Foggy, Windy, Clear, Overcast, Heat Wave, Full Moon, Migration, Drought, Red Tide, Spring Flood, Aurora, School. Each has `catch_bonus`, `rare_bonus`, `affects_locations`, and optional `location_bonus`, `time_multiplier`, `catch_quantity`, `specific_rarity_bonus`, `duration_hours`.

**`TIME_EFFECTS`** (4 entries): Dawn (+15% catch, +5% rare), Day (0%), Dusk (+15% catch, +5% rare), Night (-10% catch, +20% rare).

#### Default Data Schemas

**`DEFAULT_USER_DATA`**:
```python
{
    "inventory": [],             # List[str] - fish/junk type names
    "rod": "Basic Rod",          # str - currently equipped rod
    "total_value": 0,            # int - lifetime earnings tracker
    "daily_quest": None,         # Not implemented
    "bait": {},                  # Dict[str, int] - bait_name -> quantity
    "purchased_rods": {"Basic Rod": True},  # Dict[str, bool]
    "equipped_bait": None,       # Optional[str] - equipped bait name
    "current_location": "Pond",  # str - current fishing location
    "fish_caught": 0,            # int - lifetime fish count
    "junk_caught": 0,            # int - lifetime junk count
    "level": 1,                  # int - current level (1-20)
    "experience": 0,             # int - total XP
    "inventory_capacity": 5,     # int - max fish+junk slots (upgradeable via gear)
    "purchased_gear": [],        # list - names of purchased gear items
    "settings": {
        "notifications": True,   # Not implemented
        "auto_sell": False       # Not implemented
    }
}
```

**`DEFAULT_GLOBAL_SETTINGS`**:
```python
{
    "bait_stock": {              # Dict[str, int] - bait_name -> available stock
        "Worm": 1000,
        "Shrimp": 500,
        "Cricket": 250,
        "Firefly": 150,
        "Nightcrawler": 100,
        "Anchovy": 80
    },
    "current_weather": "Sunny",  # str - active weather type
    "active_events": [],         # Not implemented
    "settings": {
        "daily_reset_hour": 0,   # Not actively used (midnight hardcoded)
        "weather_change_interval": 3600  # Not actively used (3600s hardcoded)
    }
}
```

### 4.4 `fishing/utils/config_manager.py` -- ConfigManager and ConfigResult

#### `ConfigResult[T]` (Generic Dataclass)

```python
@dataclass
class ConfigResult(Generic[T]):
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
```

Error codes used: `"FETCH_ERROR"`, `"VALIDATION_ERROR"`, `"GENERAL_ERROR"`, `"CACHE_ERROR"`, `"GET_ERROR"`, `"SAVE_ERROR"`, `"VERIFY_ERROR"`, `"RESET_ERROR"`.

#### `ConfigManager`

```python
class ConfigManager:
    def __init__(self, bot, identifier: int)
```

Wraps `redbot.core.Config` with:
- **Caching**: `self._cache: Dict[str, Any]` keyed by `"user_{id}"` or `"global_{key}"` or `"global_all"`
- **Validation**: All user data is validated/repaired on every read via `_validate_user_data()`
- **Transaction support**: `config_transaction()` async context manager

##### Public Methods

```python
async def invalidate_cache(self, key: Optional[str] = None) -> None
```
Clear specific cache key or entire cache.

```python
async def refresh_cache(self, user_id: int) -> ConfigResult[bool]
```
Force-fetch from Config, validate, and update cache.

```python
async def get_user_data(self, user_id: int) -> ConfigResult[Dict[str, Any]]
```
Returns validated user data. Checks cache first; fetches from Config on miss. Always validates via `_validate_user_data()`.

```python
async def update_user_data(
    self, user_id: int, updates: Dict[str, Any],
    fields: Optional[List[str]] = None
) -> ConfigResult[bool]
```
Updates user data. If `fields` is provided, only those keys are updated. Uses recursive dict merge for nested dicts. Special handling for `"experience"` (int conversion) and `"bait"` (dict merge). Invalidates cache after write, then verifies.

```python
async def get_global_setting(self, key: str) -> ConfigResult[Any]
```
Get a single global setting with caching.

```python
async def update_global_setting(self, key: str, value: Any) -> ConfigResult[bool]
```
Update a global setting. Validates `bait_stock` must be a dict.

```python
async def get_all_global_settings(self) -> ConfigResult[Dict[str, Any]]
```
Get all global settings, cached under `"global_all"`.

```python
async def reset_user_data(self, user_id: int) -> ConfigResult[bool]
```
Clear user data and re-set to validated defaults.

```python
@asynccontextmanager
async def config_transaction(self)
```
Yields a `transaction_cache: Dict`. On successful exit, applies all entries: `user_{id}` entries go through `update_user_data()`, `global_{key}` entries go through `update_global_setting()`. On exception, changes are discarded.

##### Private Methods

```python
async def _validate_user_data(self, data: Dict[str, Any]) -> Dict[str, Any]
```
Validates and repairs user data structure. Ensures:
- `inventory` is a list
- `bait` is a dict with int values > 0
- `purchased_rods` is a dict with bool values; `Basic Rod` always present
- Numeric fields (`total_value`, `fish_caught`, `junk_caught`, `level`, `experience`) are non-negative ints
- `rod` exists in `purchased_rods`; falls back to `"Basic Rod"`
- `equipped_bait` exists in `bait` dict; falls back to `None`
- `settings` is a dict with correct bool keys

```python
async def _validate_dictionary_merge(
    self, current: Dict, updates: Dict, path: str = ""
) -> Dict[str, Any]
```
Recursive dict merge. Logs type mismatches and skips them. Lists are replaced wholesale.

### 4.5 `fishing/utils/inventory_manager.py` -- InventoryManager

```python
class InventoryManager:
    def __init__(self, bot: Red, config_manager: ConfigManager, data: Dict)
```

#### Public Methods

```python
async def add_item(
    self, user_id: int, item_type: str, item_name: str, amount: int = 1
) -> Tuple[bool, str]
```
Adds items. `item_type` can be:
- `"inventory"` -- adds to the inventory list (fish or junk names); validates against both `data["fish"]` and `data["junk"]`
- `"bait"` -- adds to the bait dict, incrementing quantity
- `"rod"` -- adds to purchased_rods dict

Uses `config_transaction()` and verifies the write.

```python
async def remove_item(
    self, user_id: int, item_type: str, item_name: str, amount: int = 1
) -> Tuple[bool, str]
```
Removes items. Delegates to `_update_inventory()` with `operation="remove"`. For bait, auto-unequips if quantity reaches 0. For rods, falls back to Basic Rod if removing equipped rod.

```python
async def get_inventory_summary(self, user_id: int) -> Optional[Dict[str, Any]]
```
Returns:
```python
{
    "fish_count": int,      # Total items (fish + junk)
    "bait_count": int,      # Total bait across all types
    "rod_count": int,       # Number of owned rods
    "total_value": int,     # Sum of all inventory item values
    "equipped_rod": str,
    "equipped_bait": Optional[str]
}
```

### 4.6 `fishing/utils/level_manager.py` -- LevelManager

```python
class LevelManager:
    def __init__(self, config_manager: ConfigManager)
```

#### XP Thresholds (99 levels)

RuneScape-style exponential curve: `gap(L) = 50 + 3350 * (2^(L/24.5) - 2^(2/24.5))`. Halfway point (50% of total XP) falls at level 80. Full table in `level_manager.py`. Key milestones:

| Level | Total XP Required |
|-------|-------------------|
| 1 | 0 |
| 10 | 4,364 |
| 20 | 21,520 |
| 30 | 55,716 |
| 40 | 112,522 |
| 50 | 199,334 |
| 60 | 325,964 |
| 70 | 505,433 |
| 80 | 755,016 |
| 90 | 1,097,642 |
| 99 | 1,510,510 |

#### Rarity XP Rewards

| Rarity | Base XP |
|--------|---------|
| common | 15 |
| uncommon | 35 |
| rare | 100 |
| legendary | 250 |

#### Public Methods

```python
def calculate_xp_reward(self, fish_rarity: str, location_mod: float = 1.0) -> int
```
Returns `int(base_xp * location_mod)`. For junk items, `_catch_fish()` passes `location_mod=0.5`.

```python
def get_level_for_xp(self, xp: int) -> int
```
Iterates thresholds in reverse to find highest level where `xp >= threshold`.

```python
async def award_xp(self, user_id: int, xp_amount: int) -> Tuple[bool, Optional[int], Optional[int]]
```
Awards XP, updates level, returns `(success, old_level_if_leveled, new_level_if_leveled)`. Returns `(True, None, None)` if no level-up occurred.

```python
async def get_level_progress(self, user_id: int) -> Optional[Dict]
```
Returns:
```python
{
    "current_level": int,
    "current_xp": int,
    "xp_for_next": Optional[int],  # None if max level
    "progress": float              # 0-100 percentage
}
```

```python
async def initialize_user_xp(self, user_id: int) -> None
```
Ensures `"experience"` key exists in user data.

### 4.7 `fishing/utils/task_manager.py` -- TaskManager

```python
class TaskManager:
    def __init__(self, bot, config, data)
```

Manages two background `asyncio.Task` instances:

#### Tasks

1. **`_weather_task`**: Every 3600 seconds (1 hour), randomly selects a weather type from `data["weather"]` keys and updates via `config.update_global_setting("current_weather", weather)`.

2. **`_stock_task`**: Calculates seconds until next midnight, sleeps until then, resets bait stock to `daily_stock` values from `data["bait"]` via `config.update_global_setting("bait_stock", new_stock)`.

Both tasks have error recovery (sleep 60s or 300s on error) and handle `CancelledError` for clean shutdown.

#### Public Methods

```python
async def start(self) -> None       # Start both tasks (idempotent)
async def stop(self) -> None        # Cancel and await both tasks
@property
def status(self) -> Dict[str, dict] # Returns running/failed/exception per task
```

### 4.8 `fishing/utils/timeout_manager.py` -- TimeoutManager (Singleton)

```python
class TimeoutManager:  # Singleton via __new__
    def __init__(self)
```

Manages view timeouts centrally with a single background polling task (1-second interval). Uses `weakref.WeakValueDictionary` for view references to prevent memory leaks.

#### Internal State

- `_timeouts: Dict[str, Dict[str, Any]]` -- keyed by `"{ClassName}_{id(view)}"`, values contain `expiry`, `duration`, `last_interaction`, `paused`, optional `parent_id`
- `_views: WeakValueDictionary` -- weak refs to view objects

#### Public Methods

```python
async def start(self) -> None
async def stop(self) -> None
def generate_view_id(self, view) -> str
async def add_view(self, view, duration: int) -> None
async def remove_view(self, view) -> None
async def reset_timeout(self, view) -> None  # Resets view + parent + all children
async def handle_view_transition(self, parent_view, child_view) -> None
async def resume_parent_view(self, child_view) -> None
async def cleanup(self) -> None
```

#### Parent/Child Hierarchy

When transitioning from parent to child view:
1. Parent is **paused** (timeout stops expiring)
2. Child **inherits** parent's remaining timeout duration
3. Child stores `parent_id` in its timeout data
4. When child closes, `resume_parent_view()` transfers remaining time back to parent and unpauses it
5. `reset_timeout()` cascades: resets the view, its parent, and all children

### 4.9 `fishing/utils/logging_config.py` -- LoggerManager (Singleton)

```python
class LoggerManager:  # Singleton via __new__
```

Creates per-module loggers under the `fishing.{module_name}` namespace. Each logger gets:
- A **file handler** writing to `fishing/logs/{module_name}.log`
- A **console handler** writing to `sys.stdout`
- Level: `DEBUG`
- Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`

```python
def get_logger(module_name: str) -> logging.Logger  # Module-level convenience function
```

Loggers created (by module_name): `main`, `config`, `inventory_manager`, `level_manager`, `task_manager`, `tmanager`, `timeout_manager`, `profit_simulator`, `base.view`, `menu`, `menu.view`, `shop`, `shop.view`, `inventory`, `inventory.view`, `simulate`, `simulate.view`, `ui.components`, `setup`.

### 4.10 `fishing/utils/profit_simulator.py` -- ProfitSimulator

```python
class ProfitSimulator:
    def __init__(self, game_data: Dict)
```

Used by the interactive simulation menu (`SimulationMenuView`). Mirrors `_catch_fish` logic exactly — simulates fishing outcomes without modifying any state.

#### Data Classes

```python
@dataclass
class CatchResult:
    fish_name: str
    value: int
    rarity: str
```

#### XP Constants (mirrored from LevelManager)

```python
RARITY_XP = {"common": 15, "uncommon": 35, "rare": 100, "legendary": 250}
JUNK_RARITY_XP_MODIFIER = 0.5
```

#### Public Methods

```python
def analyze_full_setup(self, rod: str, bait: str, location: str, weather: str,
                       time_of_day: str, duration_hours: int = 1,
                       catches_per_hour: int = 360) -> Dict
```

`analyze_full_setup()` returns:
```python
{
    "rod": str, "bait": str, "location": str, "weather": str, "time_of_day": str,
    "duration_hours": int, "catches_per_hour": int,
    "rarity_breakdown": {"common": int, "uncommon": int, "rare": int, "legendary": int},
    "bonus_catches": int, "junk_caught": int, "junk_value": int, "missed": int,
    "gross_profit": int, "bait_cost": int, "net_profit": int, "estimated_xp": int,
    "modifiers": {
        "rod_bonus": float, "bait_bonus": float, "weather_bonus": float,
        "weather_rare_bonus": float, "weather_applies": bool,
        "time_bonus": float, "time_rare_bonus": float, "total_chance": float
    }
}
```

#### Internal Methods

```python
def _compute_modifiers(self, rod, bait, location, weather, time_of_day) -> Dict
def _build_fish_weights(self, location, mods) -> tuple  # (fish_names, weights)
def _build_junk_weights(self) -> tuple  # (junk_names, weights)
def _simulate_single(self, mods, fish_names, fish_weights, junk_names, junk_weights, location) -> Dict
```

### 4.12 `fishing/ui/simulate.py` -- SimulationMenuView

```python
class SimulationMenuView(BaseView):
    def __init__(self, cog, ctx, timeout=300)
```

Interactive simulation menu for owners. Two display modes:

**Config mode** (default): 4 Select menus (rows 0-3) + 1 button row (row 4)
- Rod Select (5 options), Bait Select (6 options), Location Select (5 options), Weather Select (15 options)
- Buttons: Time cycle (Dawn→Day→Dusk→Night), Duration -/+, Run Simulation

**Results mode**: Displays simulation results with a "Back to Config" button.

Uses `ProfitSimulator.analyze_full_setup()` to run the simulation. All state is held in instance variables (`selected_rod`, `selected_bait`, `selected_location`, `selected_weather`, `selected_time`, `duration_hours`, `results`).

#### Key Methods

```python
async def setup(self) -> SimulationMenuView
async def initialize_view(self) -> None
async def generate_embed(self) -> discord.Embed
async def handle_select(self, interaction) -> None
async def handle_button(self, interaction) -> None
async def run_simulation(self, interaction) -> None
```

### 4.11 `fishing/ui/base.py` -- BaseView and ConfirmView

#### `BaseView(discord.ui.View)`

```python
class BaseView(View):
    def __init__(self, cog, ctx: commands.Context, timeout: int = 600)
```

Base class for all views. Provides:
- **Interaction authorization**: `interaction_check()` verifies `interaction.user.id == ctx.author.id`
- **Timeout integration**: Resets `TimeoutManager` timeout on each valid interaction
- **Cleanup**: `cleanup()` disables all children, edits message, removes from TimeoutManager, resumes parent if applicable
- **Error handling**: `on_error()` sends ephemeral error message

##### Key Methods

```python
async def interaction_check(self, interaction: discord.Interaction) -> bool
async def on_timeout(self) -> None           # Calls cleanup(), disables children, edits message
async def cleanup(self) -> None              # Disable items, edit message, remove from timeout manager
async def on_error(self, interaction, error, item) -> None
async def update_message(self, **kwargs) -> None
async def delete_after_delay(self, message, delay: int = 2) -> None

# Session management
def _release_session(self) -> None      # Remove from cog._active_sessions if this view owns slot
```

#### `ConfirmView(BaseView)`

```python
class ConfirmView(BaseView):
    def __init__(self, cog, ctx, timeout: int = 30)
```

Simple confirm/cancel dialog. Sets `self.value` to `True` or `False` and calls `self.stop()`.

### 4.12 `fishing/ui/menu.py` -- FishingMenuView

```python
class FishingMenuView(BaseView):
    def __init__(self, cog, ctx, user_data: Dict)
```

The main interactive menu. Manages multiple "pages": `"main"`, `"location"`, `"weather"`.

#### Pages and Buttons

**Main page** buttons:
- "Fish" (green) -- starts fishing minigame
- "Shop" (blurple) -- transitions to ShopView
- "Inventory" (blurple) -- transitions to InventoryView
- "Location" (blurple) -- shows location selection
- "Weather" (blurple) -- shows weather info

**Location page**: One button per location (disabled if level-locked), plus Back.

**Weather page**: Shows current weather details, time until next change, all bonuses.

#### Fishing Minigame Flow (`do_fishing()` + `handle_catch_attempt()`)

`do_fishing` runs a **continuous loop** that keeps casting until the player stops or is forced out:

1. User clicks "Fish" button -> `do_fishing()` starts the loop
2. **Casting phase**: "Casting line..." embed with Stop Fishing button, wait `random(2, 5)` seconds
3. **Minigame phase**: 5 buttons (catch, grab, snag, hook, reel), one is `self.correct_action`, 5s timeout
4. **Result phase**: Show result embed for 3s, then loop back to step 2

**Loop exits** (returns to main menu):
- **Timeout**: No button pressed during minigame -> bait consumed, "Too Slow!", return to menu
- **Stop Fishing**: Player clicks Stop during casting phase -> "Session Ended", return to menu
- **Inventory full**: Detected after each catch -> "Inventory Full!", return to menu
- **Out of bait**: Detected after each catch -> "Out of Bait!", return to menu

On correct button: Bait consumed, `_catch_fish()` called, XP awarded, result stored in `_catch_result_embed`.
On wrong button: Bait consumed, "Wrong Move!" shown, loop continues.
On nothing caught (RNG): "Nothing!" shown, loop continues.
Bait is always consumed on any attempt or timeout.

#### Key Methods

```python
async def setup(self) -> FishingMenuView        # Init timeout manager, register view, initialize
async def initialize_view(self) -> None          # Build buttons for current page
async def generate_embed(self) -> discord.Embed  # Build embed for current page
async def handle_button(self, interaction) -> None
async def handle_location_select(self, interaction) -> None
async def do_fishing(self, interaction) -> None   # Continuous fishing loop
async def handle_catch_attempt(self, interaction) -> None  # Sets _catch_result_embed
async def _handle_stop_fishing(self, interaction) -> None  # Signals stop during casting
async def _return_to_menu(self, interaction) -> None       # Resets state, shows main menu
async def consume_bait(self, interaction) -> None
async def update_view(self) -> None
async def start(self) -> FishingMenuView         # Send initial message
def get_time_of_day(self) -> str                 # Delegates to cog
```

### 4.13 `fishing/ui/shop.py` -- ShopView, PurchaseConfirmView, BaitQuantityModal

#### `BaitQuantityModal(discord.ui.Modal)`

```python
class BaitQuantityModal(discord.ui.Modal):
    def __init__(self, shop_view, bait_name: str)
```

Text input modal asking for purchase quantity (1-4 digits). On submit: validates input, checks affordability, creates `PurchaseConfirmView`, processes purchase if confirmed.

#### `PurchaseConfirmView(BaseView)`

```python
class PurchaseConfirmView(BaseView):
    def __init__(self, cog, ctx, item_name: str, quantity: int, cost_per_item: int)
```

Confirm/Cancel buttons. Sets `self.value` to `True`/`False`. Deletes its own message after action. Timeout: 60 seconds.

#### `ShopView(BaseView)`

```python
class ShopView(BaseView):
    def __init__(self, cog, ctx, user_data: Dict)
```

Pages: `"main"`, `"bait"`, `"rods"`, `"gear"`.

**Main page**: "Buy Bait", "Buy Rods", "Back to Menu" buttons.

**Bait page**: One "Buy {name}" button per available bait (stock > 0, user meets level req). Clicking opens `BaitQuantityModal`.

**Rods page**: One "Buy {name}" button per unowned rod the user qualifies for. Clicking creates `PurchaseConfirmView` (quantity always 1).

Has `parent_menu_view` attribute set by FishingMenuView for data refresh propagation.

### 4.14 `fishing/ui/inventory.py` -- InventoryView

```python
class InventoryView(BaseView):
    def __init__(self, cog, ctx, user_data: Dict)
```

Pages: `"main"`, `"rods"`, `"bait"`, `"fish"`.

**Main page**: "View Rods", "View Bait", "View Inventory", "Back to Menu" buttons.

**Rods page**: Shows owned rods with catch bonus stats. "Equip {rod}" buttons for non-equipped rods.

**Bait page**: Shows owned bait with quantities and catch bonus. "Equip {bait}" buttons for non-equipped bait.

**Fish page**: Shows caught items (fish and junk) with counts and values. "Sell All Fish" button clears inventory and deposits credits.

### 4.15 `fishing/ui/components.py` -- Shared UI Components

```python
class ConfirmationButton(Button):
    def __init__(self, label: str, style: discord.ButtonStyle, callback: Callable, **kwargs)
```
Button that delegates to a provided callback. Not widely used (most views create buttons inline).

```python
class NavigationButton(Button):
    def __init__(self, label: str, destination: str, style=discord.ButtonStyle.grey, **kwargs)
```
Button with `custom_id=f"nav_{destination}"`. Not widely used.

```python
class MessageManager:
    @staticmethod
    async def send_temp_message(
        interaction: discord.Interaction, content: str,
        ephemeral: bool = True, duration: int = 2
    ) -> None
```
Sends a message via interaction. If `ephemeral=False`, auto-deletes after `duration` seconds. Handles both fresh and already-responded interactions.


---

## 5. Data Flow Diagrams

### 5.1 User Issues `[p]fish` Command

```
User -> [p]fish command
  |
  v
Fishing.fish_command(ctx)
  |-> _ensure_user_data(ctx.author)
  |     |-> ConfigManager.get_user_data(user_id)
  |           |-> Check _cache
  |           |-> If miss: Config.user_from_id(id).all()
  |           |-> _validate_user_data(data)
  |           |-> Store in _cache
  |           +-> Return ConfigResult(True, validated_data)
  |
  |-> FishingMenuView(cog, ctx, user_data).setup()
  |     |-> TimeoutManager.start()
  |     |-> TimeoutManager.add_view(self, 600)
  |     |-> initialize_view()  [builds buttons]
  |     +-> Return self
  |
  +-> view.start()  [sends embed + view as Discord message]
```

### 5.2 Fishing Minigame Flow

```
User clicks "Fish" button
  |
  v
FishingMenuView.handle_button("fish")
  |-> Set fishing_in_progress = True
  |-> interaction.response.defer()
  |-> do_fishing(interaction)
       |-> Check equipped_bait (abort if None)
       |-> Check inventory_capacity (abort if full)
       |
       |-> [LOOP START]
       |     |-> Show "Casting line..." + Stop Fishing button
       |     |-> Wait random(2-5s) or stop button
       |     |
       |     +-> [Stop pressed] -> "Session Ended" -> return to menu
       |     |
       |     |-> Show 5 action buttons (no stop button)
       |     |-> Wait 5s for button press
       |     |
       |     +-> [Timeout: no press] -> consume bait -> "Too Slow!" -> return to menu
       |     |
       |     +-> [Button pressed -> handle_catch_attempt()]
       |           |-> Disable buttons, consume bait
       |           |-> Correct: _catch_fish() -> award XP -> store result embed
       |           |-> Wrong: store "Wrong Move!" embed
       |           |
       |     |-> Show result embed (3s)
       |     |-> Refresh user data
       |     |-> Check bait (empty? -> "Out of Bait!" -> return to menu)
       |     |-> Check inventory (full? -> "Inventory Full!" -> return to menu)
       |     +-> [LOOP BACK TO START]
```

### 5.3 Purchase Flow (Bait)

```
User on ShopView bait page clicks "Buy {bait}"
  |
  v
ShopView.handle_purchase()
  |-> Open BaitQuantityModal
       |
       v
  BaitQuantityModal.on_submit()
    |-> Validate quantity (positive int)
    |-> Check affordability via _can_afford()
    |-> Create PurchaseConfirmView
    |-> User clicks Confirm/Cancel
    |
    +-> [If confirmed]
          |-> Fishing._handle_bait_purchase(user, bait, qty, user_data)
          |     |-> Validate bait type
          |     |-> Check balance
          |     |-> Check and update global bait_stock
          |     |-> InventoryManager.add_item(user_id, "bait", name, qty)
          |     |-> bank.withdraw_credits(user, total_cost)
          |     +-> Return (True, "Purchased X for Y coins!")
          |
          |-> Refresh user data in ShopView and parent FishingMenuView
          +-> Update both views' embeds
```

### 5.4 Config Data Flow

```
Any Operation Needing User Data
  |
  v
ConfigManager.get_user_data(user_id)
  |-> Check _cache["user_{id}"]
  |     +-> Hit: Return ConfigResult(True, cached_data)
  |
  |-> Miss: Config.user_from_id(id).all()  [Red Config API -> JSON storage]
  |-> _validate_user_data(raw_data)
  |     |-> Ensure all fields exist with correct types
  |     |-> Repair corrupted data (reset to defaults)
  |     +-> Return validated dict
  |
  |-> Store in _cache["user_{id}"]
  +-> Return ConfigResult(True, validated_data)

Write Operation
  |
  v
ConfigManager.update_user_data(user_id, updates, fields)
  |-> get_user_data(user_id)  [get current]
  |-> Merge updates (field-filtered or full)
  |-> _validate_user_data(merged)
  |-> Config.user_from_id(id).set_raw(key, value=val)  [per field]
  |-> invalidate_cache("user_{id}")
  +-> get_user_data(user_id)  [verify write]
```

---

## 6. Key Design Patterns

### 6.1 ConfigResult Pattern

All `ConfigManager` methods return `ConfigResult[T]`. Callers must check `.success` before accessing `.data`. Error information in `.error` (message) and `.error_code` (enum-like string).

```python
result = await config_manager.get_user_data(user_id)
if not result.success:
    logger.error(f"Failed: {result.error} ({result.error_code})")
    return
user_data = result.data  # Safe to use
```

### 6.2 View Hierarchy with Timeout Inheritance

Views form a parent-child tree managed by `TimeoutManager`:

```
FishingMenuView (parent, 300s timeout)
  +-- ShopView (child, inherits remaining timeout)
  +-- InventoryView (child, inherits remaining timeout)
```

Transitions:
- `handle_view_transition(parent, child)`: Pauses parent, child inherits timeout
- `resume_parent_view(child)`: Transfers remaining time back, unpauses parent
- `reset_timeout(view)`: Cascades to parent and all children

### 6.3 Singleton Managers

Two singletons using `__new__` override pattern:
- `TimeoutManager` -- single background task checks all view expirations
- `LoggerManager` -- ensures one logger per module name

### 6.4 Transaction Pattern

`ConfigManager.config_transaction()` provides pseudo-transactional writes:

```python
async with config_manager.config_transaction() as transaction:
    transaction[f"user_{user_id}"] = {"inventory": [...]}
    # Applied on successful exit; discarded on exception
```

### 6.5 Validation-on-Read

Every `get_user_data()` call passes data through `_validate_user_data()`, which repairs corrupted or incomplete data structures. This is a defensive pattern ensuring data integrity even if the underlying JSON is manually edited or corrupted.

### 6.6 Bait Consumption Model

Bait is consumed on every fishing attempt regardless of outcome (correct button, wrong button, or timeout). This creates consistent resource drain and economic pressure.

---

## 7. Configuration Schema Reference

### 7.1 Red Config Registration

```python
# In ConfigManager.__init__:
self.config = Config.get_conf(None, identifier=123456789)
self.config.register_user(**DEFAULT_USER_DATA)
self.config.register_global(**DEFAULT_GLOBAL_SETTINGS)
```

Config identifier: `123456789`

### 7.2 Per-User Schema

See `DEFAULT_USER_DATA` in Section 4.3.

### 7.3 Global Schema

See `DEFAULT_GLOBAL_SETTINGS` in Section 4.3.

---

## 8. Game Mechanics

### 8.1 Catch Chance Calculation

```
total_chance = rod_bonus + bait_bonus + weather_bonus + time_bonus
```

Where:
- `rod_bonus` = `ROD_TYPES[equipped_rod]["chance"]` (0.0 to 0.32)
- `bait_bonus` = `BAIT_TYPES[equipped_bait]["catch_bonus"]` (0.12 to 0.42)
- `weather_bonus` = `WEATHER_TYPES[weather]["catch_bonus"]` + `location_bonus[location]` + `time_multiplier[time_of_day]` (only if location is in `affects_locations`)
- `time_bonus` = `TIME_EFFECTS[time_of_day]["catch_bonus"]` (-0.1 to +0.15)

A `random.random()` roll below `total_chance` results in a fish catch attempt. Otherwise, 75% chance for junk.

### 8.2 Fish Rarity Selection

On a successful catch roll:
```
For each fish_type:
    weight = base_chance * location_modifier
    if rarity in [rare, legendary] and location affected by weather:
        weight *= (1 + weather_rare_bonus + time_rare_bonus)
    if specific_rarity_bonus exists for this rarity:
        weight *= (1 + specific_rarity_bonus)
```
Final selection via `random.choices(fish_types, weights=weights)`.

### 8.3 Leveling System

Two parallel level systems exist (architectural note):

1. **XP-based** (`LevelManager`): 99 levels (level 100 reserved for future cape item), XP from catches based on rarity. Used for `get_level_progress()` display and `award_xp()`.
2. **Fish-count-based** (`_update_total_value`): `level = max(1, fish_caught // 50)`. Overwrites level on every catch.

This means the XP-based level from `LevelManager.award_xp()` may be overwritten by the fish-count formula in `_update_total_value()`. Both write to the same `"level"` field. This is a known inconsistency.

### 8.4 Economy Flow

- **Earning**: Sell fish/junk via `sell_fish()` (clears entire inventory, deposits total value)
- **Spending**: Buy bait (per-unit cost, variable quantity) or rods (one-time cost)
- **Bait stock**: Global shared stock, daily reset at midnight, finite per day
- **Currency**: Uses Red-DiscordBot's bank system (`bank.deposit_credits`, `bank.withdraw_credits`, `bank.get_balance`)

### 8.5 Weather System

- 15 weather types, randomly rotated hourly by `TaskManager._weather_task()`
- Each weather type has:
  - A base `catch_bonus` (applied to catch chance if location is affected)
  - A `rare_bonus` (multiplier for rare/legendary fish weights)
  - `affects_locations` list (bonuses only apply at these locations)
  - Optional `location_bonus` (additional catch bonus at specific locations)
  - Optional `time_multiplier` (additional bonus during specific times of day)
  - Optional `catch_quantity` (% chance for bonus catch of a second fish)
  - Optional `specific_rarity_bonus` (extra multiplier for specific rarities)
  - Optional `duration_hours` (not actively used in rotation logic)

### 8.6 Time of Day

Based on system clock (server local time):
- **Dawn** (5:00-6:59): +15% catch, +5% rare
- **Day** (7:00-16:59): No bonus
- **Dusk** (17:00-18:59): +15% catch, +5% rare
- **Night** (19:00-4:59): -10% catch, +20% rare

### 8.7 Location Progression

Locations unlock by level. Higher-level locations shift fish distribution toward rarer catches:
- Pond (start): Heavily favors common fish
- Deep Sea (level 18): 2.0x legendary modifier, 0.4x common modifier

---

## 9. Inter-Module Dependencies

```
fishing/__init__.py
  +-- fishing/main.py (Fishing cog)
        |-- fishing/data/fishing_data.py (constants, TypedDicts, defaults)
        |-- fishing/utils/config_manager.py (ConfigManager, ConfigResult)
        |     +-- fishing/utils/logging_config.py (get_logger)
        |     +-- fishing/data/fishing_data.py (DEFAULT_USER_DATA, DEFAULT_GLOBAL_SETTINGS)
        |-- fishing/utils/inventory_manager.py (InventoryManager)
        |     +-- fishing/utils/config_manager.py
        |     +-- fishing/utils/logging_config.py
        |-- fishing/utils/level_manager.py (LevelManager)
        |     +-- fishing/utils/config_manager.py
        |     +-- fishing/utils/logging_config.py
        |-- fishing/utils/task_manager.py (TaskManager)
        |     +-- fishing/utils/logging_config.py
        |-- fishing/utils/profit_simulator.py (ProfitSimulator)
        |     +-- fishing/utils/logging_config.py
        |-- fishing/ui/menu.py (FishingMenuView)
        |     +-- fishing/ui/base.py (BaseView)
        |     |     +-- fishing/utils/timeout_manager.py (TimeoutManager)
        |     |     +-- fishing/ui/components.py (MessageManager)
        |     |     +-- fishing/utils/logging_config.py
        |     +-- fishing/ui/shop.py (ShopView) [imported in handle_button]
        |     +-- fishing/ui/inventory.py (InventoryView) [imported in handle_button]
        |-- fishing/ui/shop.py (ShopView, PurchaseConfirmView, BaitQuantityModal)
        |     +-- fishing/ui/base.py
        |     +-- fishing/ui/menu.py [TYPE_CHECKING only + lazy import in handle_button]
        |-- fishing/ui/inventory.py (InventoryView)
        |     +-- fishing/ui/base.py
        |     +-- fishing/utils/timeout_manager.py
        |-- fishing/ui/simulate.py (SimulationMenuView)
              +-- fishing/ui/base.py
              +-- fishing/utils/profit_simulator.py
              +-- fishing/utils/logging_config.py
```

**Circular dependency note**: `menu.py` imports `ShopView` at top level and `InventoryView` lazily. `shop.py` imports `FishingMenuView` under `TYPE_CHECKING` and lazily in `handle_button()` to avoid circular imports.

---

## 10. Known Architectural Decisions and Trade-offs

### 10.1 ~~Dual Leveling System Conflict~~ (FIXED)

Previously `_update_total_value()` calculated level as `fish_caught // 50`, conflicting with `LevelManager`. The fish-count formula has been removed. `LevelManager.award_xp` is now the sole authority on leveling.

### 10.2 ~~No Bait Effectiveness in Catch Logic~~ FIXED

**FIXED**: Bait `effectiveness` multipliers are now wired into `_catch_fish()` in `main.py`. The `catch_bonus` is multiplied by the location-specific effectiveness value (defaults to 1.0 if not defined). The `ProfitSimulator` mirrors this logic. The simulation UI displays effectiveness in both config and results embeds. Fish values were rebalanced (Common: 10, Uncommon: 25, Rare: 65, Legendary: 200) to ensure baits are profitable at their intended locations while remaining break-even or a loss at unintended ones.

### 10.3 Rod Durability Not Implemented

`ROD_TYPES` defines `durability` values (100-500) but no durability tracking or degradation logic exists.

### 10.4 daily_quest, notifications, auto_sell, active_events Not Implemented

These fields exist in `DEFAULT_USER_DATA` and `DEFAULT_GLOBAL_SETTINGS` but have no associated logic.

### 10.5 weather_effects Flag Unused

`LocationData` includes `weather_effects: bool` but the catch logic checks `affects_locations` on the weather type instead, not this flag.

### 10.6 Validation on Every Read

`ConfigManager.get_user_data()` validates data on every call (even cache hits are pre-validated). This is defensive but means validation runs frequently. The cache stores already-validated data, so cache hits skip re-validation.

### 10.7 ~~Cache Invalidation After Write~~ (FIXED)

Previously `update_user_data()` re-read after every write to verify. This has been simplified to invalidate cache without re-reading — the next read will pull fresh data.

### 10.8 No Pagination

Inventory, shop, and other list views have no pagination. Large inventories or many items could overflow Discord embed limits (6000 characters, 25 fields).

### 10.9 Global Bait Stock

Bait stock is global (shared across all users on all guilds). A single user could buy out the entire daily stock. There is no per-user purchase limit.

### 10.10 Sell All or Nothing

`sell_fish()` sells the entire inventory at once. There is no selective selling of individual items or types.

### 10.11 Redundant `setup()` Function

Both `fishing/__init__.py` and the bottom of `fishing/main.py` define a `setup()` function. The `__init__.py` version (async, using `await bot.add_cog()`) is the one Red actually calls. The `main.py` version (sync, using `bot.add_cog()`) appears to be legacy.

---

## 11. Quick Reference: All Public Method Signatures

### ConfigManager
```python
async def invalidate_cache(self, key: Optional[str] = None) -> None
async def refresh_cache(self, user_id: int) -> ConfigResult[bool]
async def get_user_data(self, user_id: int) -> ConfigResult[Dict[str, Any]]
async def update_user_data(self, user_id: int, updates: Dict[str, Any], fields: Optional[List[str]] = None) -> ConfigResult[bool]
async def get_global_setting(self, key: str) -> ConfigResult[Any]
async def update_global_setting(self, key: str, value: Any) -> ConfigResult[bool]
async def get_all_global_settings(self) -> ConfigResult[Dict[str, Any]]
async def reset_user_data(self, user_id: int) -> ConfigResult[bool]
@asynccontextmanager async def config_transaction(self) -> AsyncGenerator[Dict, None]
```

### InventoryManager
```python
async def add_item(self, user_id: int, item_type: str, item_name: str, amount: int = 1) -> Tuple[bool, str]
async def remove_item(self, user_id: int, item_type: str, item_name: str, amount: int = 1) -> Tuple[bool, str]
async def get_inventory_summary(self, user_id: int) -> Optional[Dict[str, Any]]
```

### LevelManager
```python
async def initialize_user_xp(self, user_id: int) -> None
def calculate_xp_reward(self, fish_rarity: str, location_mod: float = 1.0) -> int
def get_level_for_xp(self, xp: int) -> int
async def award_xp(self, user_id: int, xp_amount: int) -> Tuple[bool, Optional[int], Optional[int]]
async def get_level_progress(self, user_id: int) -> Optional[Dict]
```

### TaskManager
```python
async def start(self) -> None
async def stop(self) -> None
@property def status(self) -> Dict[str, dict]
```

### TimeoutManager
```python
async def start(self) -> None
async def stop(self) -> None
def generate_view_id(self, view) -> str
async def add_view(self, view, duration: int) -> None
async def remove_view(self, view) -> None
async def reset_timeout(self, view) -> None
async def handle_view_transition(self, parent_view, child_view) -> None
async def resume_parent_view(self, child_view) -> None
async def cleanup(self) -> None
```

### ProfitSimulator
```python
def analyze_full_setup(self, rod, bait, location, weather, time_of_day, duration_hours=1, catches_per_hour=360) -> Dict
```

### SimulationMenuView
```python
async def setup(self) -> SimulationMenuView
async def initialize_view(self) -> None
async def generate_embed(self) -> discord.Embed
async def handle_select(self, interaction) -> None
async def handle_button(self, interaction) -> None
async def run_simulation(self, interaction) -> None
```

### Fishing (Cog) -- Non-Command Methods
```python
def get_time_of_day(self) -> str
async def create_menu(self, ctx, user_data) -> FishingMenuView
async def _ensure_user_data(self, user) -> Optional[dict]
async def _catch_fish(self, user, user_data, bait_type, location, weather, time_of_day) -> Optional[dict]
async def _add_to_inventory(self, user, item_name) -> bool
async def is_inventory_full(self, user_id) -> bool
async def _update_total_value(self, user, value, *, item_type="fish") -> bool
async def _handle_bait_purchase(self, user, bait_name, amount, user_data) -> tuple[bool, str]
async def _handle_rod_purchase(self, user, rod_name, user_data) -> tuple[bool, str]
async def _can_afford(self, user, cost) -> bool
async def _equip_rod(self, user, rod_name) -> tuple[bool, str]
async def _equip_bait(self, user, bait_name) -> tuple[bool, str]
async def sell_fish(self, ctx) -> tuple[bool, int, str]
async def check_requirements(self, user_data, requirements) -> tuple[bool, str]
```

### BaseView
```python
async def interaction_check(self, interaction) -> bool
async def on_timeout(self) -> None
async def cleanup(self) -> None
async def on_error(self, interaction, error, item) -> None
async def update_message(self, **kwargs) -> None
def _release_session(self) -> None
```

### FishingMenuView
```python
async def setup(self) -> FishingMenuView
async def initialize_view(self) -> None
async def generate_embed(self) -> discord.Embed
async def handle_button(self, interaction) -> None
async def handle_location_select(self, interaction) -> None
async def do_fishing(self, interaction) -> None
async def handle_catch_attempt(self, interaction) -> None
async def consume_bait(self, interaction) -> None
async def update_view(self) -> None
async def start(self) -> FishingMenuView
def get_time_of_day(self) -> str
```

### ShopView
```python
async def setup(self) -> ShopView
async def initialize_view(self) -> None
async def generate_embed(self) -> discord.Embed
async def handle_button(self, interaction) -> None
async def handle_select(self, interaction) -> None
async def handle_purchase(self, interaction) -> None
async def delete_after_delay(self, message) -> None
async def update_view(self) -> None
```

### InventoryView
```python
async def generate_embed(self) -> discord.Embed
async def start(self) -> Optional[InventoryView]
async def initialize_view(self) -> None
async def handle_button(self, interaction) -> None
async def delete_after_delay(self, message) -> None
async def update_view(self) -> None
```

### MessageManager
```python
@staticmethod async def send_temp_message(interaction, content, ephemeral=True, duration=2) -> None
```
