# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Red-DiscordBot cog repository** by iseekiwi. The primary cog is **Fishing** — a fishing game for Discord with an economy, leveling, inventory, and shop system. There is also a **Basewars** cog that is not functional.

The cog is installed into a Red-DiscordBot instance via `[p]cog install` and loaded with `[p]load fishing`. There is no standalone build/test system — the cog runs inside a Red bot.

## Architecture

### Fishing Cog (`fishing/`)

Entry point: `__init__.py` calls `bot.add_cog(Fishing(bot))` loading the main `Fishing` class from `main.py`.

**Data layer** (`data/fishing_data.py`):
- All game constants: `FISH_TYPES`, `JUNK_TYPES`, `ROD_TYPES`, `BAIT_TYPES`, `GEAR_TYPES`, `LOCATIONS`, `WEATHER_TYPES`, `TIME_EFFECTS`
- `DEFAULT_USER_DATA` and `DEFAULT_GLOBAL_SETTINGS` — canonical schema for per-user and global config
- Uses TypedDict classes for type hints on data structures
- Items have a rarity system (common/uncommon/rare/legendary) with probability-based catch chances

**Utils layer** (`utils/`):
- `ConfigManager` — wraps Red's `Config` API with caching (`_cache` dict), validation, and a transaction context manager (`config_transaction`). All data access goes through `ConfigResult` wrappers (success/data/error pattern). User data is validated and repaired on every read.
- `InventoryManager` — handles adding/removing fish, bait, and rods. Uses ConfigManager transactions.
- `LevelManager` — **sole authority on leveling**. XP-threshold system with 99 levels (level 100 reserved for future cape item). Awards XP on catch based on fish rarity. Do not calculate levels elsewhere.
- `TaskManager` — background asyncio tasks for hourly weather rotation and daily bait stock resets.
- `TimeoutManager` — singleton that manages Discord UI view timeouts with parent/child view hierarchies using weak references. Reset on cog unload.
- `logging_config` — centralized logger factory via `get_logger(name)`. All modules log to a single `fishing.log` file. Singleton reset on cog unload.

**UI layer** (`ui/`):
- `base.py` — `BaseView` extends `discord.ui.View` with timeout management, interaction auth checks (only command author can interact), cleanup, and `delete_after_delay`. Also has `ConfirmView`.
- `menu.py` — `FishingMenuView`, the main interactive menu with fishing, inventory, shop, and profile pages. Contains the core fishing minigame as a continuous loop (`do_fishing`): cast → minigame → result → cast again. The loop exits on: timeout (no button press), Stop Fishing button (shown during casting phase only), inventory full, or out of bait. A "Stop Fishing" button on the main menu ends the entire session.
- `shop.py` — `ShopView` and `PurchaseConfirmView` for buying rods, bait, gear, and location access. Gear is organized into 3 categories (Inventory, Gear, Tools) defined in `GEAR_TYPES`. Gear uses a Select dropdown instead of individual buttons. Long category listings are split across multiple embed fields to stay under Discord's 1024 char limit.
- `inventory.py` — `InventoryView` for browsing and selling caught items.
- `components.py` — shared UI components and `MessageManager` for ephemeral/temporary messages.
- `simulate.py` — `SimulationMenuView` for the interactive profit simulation menu (owner-only). Uses 4 Select menus (rod, bait, location, weather) + 1 button row (time cycle, duration ±, run) to configure and run simulations via `ProfitSimulator`.

### Key Patterns

- **ConfigResult pattern**: All config operations return `ConfigResult(success, data, error, error_code)` — always check `.success` before using `.data`.
- **View hierarchy**: Child views (shop, inventory) inherit timeout from parent `FishingMenuView` via `TimeoutManager.handle_view_transition()`. The parent view pauses while a child is active.
- **Data validation**: `ConfigManager._validate_user_data()` repairs corrupted user data on every read, ensuring `Basic Rod` is always available and numeric fields are non-negative.
- **Bait consumption**: Centralized in `FishingMenuView.consume_bait()` — do not duplicate inline.
- **Junk counting**: `_catch_fish` increments `junk_caught` — do not increment elsewhere.
- **Leveling**: `LevelManager.award_xp` is the sole authority — do not set level in `_update_total_value` or elsewhere.
- **Singleton cleanup**: `TimeoutManager` and `LoggerManager` are singletons that must be reset in `cog_unload` to avoid stale state on cog reload.
- **Active session guard**: `Fishing._active_sessions` (dict of user_id -> view) prevents users from opening multiple fishing menus. `BaseView._release_session()` frees the slot on cleanup/timeout using identity check (`is self`) so child→parent view transitions don't accidentally release sessions. When creating new menu views during navigation, always use `cog.create_menu()` which updates the session reference.
- **Redbot conventions**: Uses `redbot.core.Config` for persistence, `redbot.core.bank` for currency, `redbot.core.commands` for command decorators. Config identifier is `123456789`.
- **Inventory capacity**: Fish/junk inventory is capped at `inventory_capacity` (default 5, upgradeable via gear purchases). When full, fishing is blocked — the player must sell items first. The check happens in `do_fishing` before casting. Gear items in the "Inventory" category (Fish Basket I–IV) add slots.
- **Gear system**: `GEAR_TYPES` in `fishing_data.py` defines purchasable gear across 3 categories: Inventory, Gear, and Tools. Inventory items (16 tiers, Fanny Pack through Void Satchel of Hell) each SET total capacity (not additive) — buying a higher tier replaces the previous tier's bonus. Purchased gear is tracked in `user_data["purchased_gear"]` (list of names). Effects are applied at purchase time. Level requirements gate availability (levels span 1–99, with 100 for special items).
- **Data refresh**: After writes, invalidate cache then read once — do not triple-read or verify-after-every-write.
- **Bait effectiveness**: `_catch_fish` multiplies `catch_bonus` by the bait's location-specific `effectiveness` value (defaults to 1.0). This makes bait choice location-dependent — baits are profitable at intended locations but break-even/loss elsewhere. Fish values: Common=10, Uncommon=25, Rare=65, Legendary=200.
- **Simulation**: `ProfitSimulator.analyze_full_setup()` mirrors `_catch_fish` logic exactly. When catch logic changes, update the simulator to match. The `[p]simulate` command opens an interactive menu — it no longer uses subcommands. The simulator assumes perfect player input (no button-press misses). "Nothing caught" in results is pure RNG (25% of failed fish rolls produce nothing, matching the 75% junk fallback in `_catch_fish`).

## Basewars Cog (`basewars/`)

Non-functional cog with stub files for a base-building PvP game. Not ready for development.
