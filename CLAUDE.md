# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Red-DiscordBot cog repository** by iseekiwi. The primary cog is **Fishing** — a fishing game for Discord with an economy, leveling, inventory, and shop system. There is also a **Basewars** cog that is not functional.

The cog is installed into a Red-DiscordBot instance via `[p]cog install` and loaded with `[p]load fishing`. There is no standalone build/test system — the cog runs inside a Red bot.

## Architecture

### Fishing Cog (`fishing/`)

Entry point: `__init__.py` calls `bot.add_cog(Fishing(bot))` loading the main `Fishing` class from `main.py`.

**Data layer** (`data/fishing_data.py`):
- All game constants: `FISH_TYPES`, `JUNK_TYPES`, `ROD_TYPES`, `BAIT_TYPES`, `GEAR_TYPES`, `MATERIAL_TYPES`, `LOCATIONS`, `WEATHER_TYPES`, `TIME_EFFECTS`
- `DEFAULT_USER_DATA` and `DEFAULT_GLOBAL_SETTINGS` — canonical schema for per-user and global config
- Uses TypedDict classes for type hints on data structures
- Items have a rarity system (common/uncommon/rare/legendary) with probability-based catch chances

**Utils layer** (`utils/`):
- `ConfigManager` — wraps Red's `Config` API with caching (`_cache` dict), validation, and a transaction context manager (`config_transaction`). All data access goes through `ConfigResult` wrappers (success/data/error pattern). User data is validated and repaired on every read.
- `InventoryManager` — handles adding/removing fish, bait, rods, and materials. Uses ConfigManager transactions.
- `LevelManager` — **sole authority on leveling**. XP-threshold system with 99 levels (level 100 reserved for future cape item). Awards XP on catch based on fish rarity. Do not calculate levels elsewhere.
- `TaskManager` — background asyncio tasks for weather rotation (duration varies per weather type via `duration_hours`, defaults to 1 hour) and daily bait stock resets.
- `TimeoutManager` — singleton that manages Discord UI view timeouts with parent/child view hierarchies using weak references. Reset on cog unload.
- `logging_config` — centralized logger factory via `get_logger(name)`. All modules log to a single `fishing.log` file. Singleton reset on cog unload.

**UI layer** (`ui/`):
- `base.py` — `BaseView` extends `discord.ui.View` with timeout management, interaction auth checks (only command author can interact), cleanup, and `delete_after_delay`. Discord's built-in `View.timeout` is disabled (`timeout=None`); all expiry is handled by `TimeoutManager` via `_custom_timeout`. Also has `ConfirmView`.
- `menu.py` — `FishingMenuView`, the main interactive menu with fishing, inventory, shop, and profile pages. Location selection uses a dedicated sub-page with all locations displayed (modifiers, requirements, status) and a Select dropdown for changing location. Contains the core fishing minigame as a continuous loop (`do_fishing`): cast → minigame → result → cast again. The loop exits on: timeout (no button press), Stop Fishing button (shown during casting phase only), inventory full, or out of bait. A "Stop Fishing" button on the main menu ends the entire session.
- `shop.py` — `ShopView` and `PurchaseConfirmView` for buying rods, bait, and gear. The shop main page has 5 category buttons: Buy Bait, Buy Rods, Buy Storage, Buy Outfits, Buy Tools. Each gear category (Inventory/Outfits/Tools from `GEAR_TYPES`) has its own page with Select dropdown and per-category pagination (5 items/page). Bait selection opens a quantity modal; rods and gear go to direct confirmation.
- `inventory.py` — `InventoryView` for browsing and selling caught items. Rod/bait equipping uses Select dropdowns. Has a dedicated Materials page for viewing and individually selling rare drop materials (separate from fish/junk, not affected by "Sell All").
- `components.py` — shared UI components and `MessageManager` for ephemeral/temporary messages.
- `simulate.py` — `SimulationMenuView` for the interactive profit simulation menu (owner-only). Uses 4 Select menus (rod, bait, location, weather) + 1 button row (time cycle, duration ±, run) to configure and run simulations via `ProfitSimulator`.

### Key Patterns

- **ConfigResult pattern**: All config operations return `ConfigResult(success, data, error, error_code)` — always check `.success` before using `.data`.
- **View hierarchy**: Child views (shop, inventory) inherit timeout from parent `FishingMenuView` via `TimeoutManager.handle_view_transition()`. The parent view pauses while a child is active. "Back to Menu" reuses the parent view object (does not create a new one) to preserve timeout state.
- **Timeout architecture**: Discord's built-in `View.timeout` is disabled (`super().__init__(timeout=None)`). All timeout management goes through the custom `TimeoutManager` using `_custom_timeout`. This prevents Discord from firing `on_timeout` independently during view transitions.
- **Child view timeout delegation**: When a child view (ShopView, InventoryView) times out, `BaseView.on_timeout()` delegates to the parent's `on_timeout()` — which shows the "Session Ended" embed and releases the session. `cleanup()` does NOT resume parent views; that is only done explicitly by navigation code ("Back to Menu"). The `TimeoutManager._check_timeouts` loop lets `on_timeout()` handle its own removal rather than pre-removing the view.
- **Data validation**: `ConfigManager._validate_user_data()` repairs corrupted user data on every read, ensuring `Basic Rod` is always available and numeric fields are non-negative.
- **Bait consumption**: Centralized in `FishingMenuView.consume_bait()` — do not duplicate inline.
- **Junk counting**: `_catch_fish` increments `junk_caught` — do not increment elsewhere.
- **Leveling**: `LevelManager.award_xp` is the sole authority — do not set level in `_update_total_value` or elsewhere.
- **Singleton cleanup**: `TimeoutManager` and `LoggerManager` are singletons that must be reset in `cog_unload` to avoid stale state on cog reload.
- **Active session guard**: `Fishing._active_sessions` (dict of user_id -> view) prevents users from opening multiple fishing menus. `BaseView._release_session()` frees the slot on cleanup/timeout using identity check (`is self`) so child→parent view transitions don't accidentally release sessions. When creating new menu views during navigation, always use `cog.create_menu()` which updates the session reference.
- **Redbot conventions**: Uses `redbot.core.Config` for persistence, `redbot.core.bank` for currency, `redbot.core.commands` for command decorators. Config identifier is `123456789`.
- **Inventory capacity**: Fish/junk inventory is capped at `inventory_capacity` (default 5, upgradeable via gear purchases). When full, fishing is blocked — the player must sell items first. The check happens in `do_fishing` before casting. Gear items in the "Inventory" category (Fish Basket I–IV) add slots.
- **Gear system**: `GEAR_TYPES` in `fishing_data.py` defines purchasable gear across 3 categories: Inventory (storage upgrades), Outfits (wearable gear), and Tools (fishing tools). Each has its own shop page. Inventory items (16 tiers, Fanny Pack through Void Satchel of Hell) each SET total capacity (not additive). Purchased gear is tracked in `user_data["purchased_gear"]` (list of names). Effects are applied at purchase time. Level requirements gate availability (levels span 1–99, with 100 for special items).
- **Sequential purchase requirement**: Rods and gear must be purchased in order — each item requires owning the previous tier. `Fishing.check_rod_prerequisite()` and `Fishing.check_gear_prerequisite()` enforce this. The shop UI only shows purchasable items (prerequisite met) in dropdowns and displays "Requires [previous item]" for locked items in the embed.
- **Materials system**: `MATERIAL_TYPES` defines rare drop materials (Iron Hinge, Steel Hinge, Magic Scale, Magic Fish, Void Scale). Any purchasable item can have an optional `material_cost: Dict[str, int]` field requiring materials to purchase. Materials are stored in `user_data["materials"]` as `Dict[str, int]`. `Fishing.check_material_cost()` validates ownership; `Fishing.consume_materials()` removes them via `InventoryManager`. Currently 5 gear items require materials. The system is universal — rods, bait, or future item types can use `material_cost` too.
- **Consumable tools system**: `CONSUMABLE_TOOL_TYPES` in `fishing_data.py` defines 4 consumable tools that enable material drops. Tools are stored in `user_data["tools"]` as `Dict[str, int]` (name -> quantity). Purchased from the shop "Buy Tools" page via quantity modal. When a player catches a fish of eligible rarity and owns the tool, one tool is consumed and a drop roll is made. Multiple tools trigger independently on the same catch (e.g., Rare fish with both Salvage Magnet and Arcane Scraper consumes one of each). Arcane Scraper is special: one consumption, rolls for Magic Scale on rare+, and additionally for Magic Fish on legendary. Tools: Salvage Magnet ($27, Lv35, uncommon+ -> Iron Hinge 1/329), Tempered Magnet ($58, Lv55, rare+ -> Steel Hinge 1/414), Arcane Scraper ($52, Lv70, rare+ -> Magic Scale 1/533, legendary -> Magic Fish 1/393), Void Lure ($282, Lv85, legendary -> Void Scale 1/245). Tool processing is centralized in `Fishing._process_tool_drops()`. `Fishing._handle_tool_purchase()` handles shop purchases. Tool prices are set so 30% tooling costs ~33% of fishing income — tools are a meaningful economic trade-off.
- **Data refresh**: After writes, invalidate cache then read once — do not triple-read or verify-after-every-write. All views call `BaseView._refresh_user_data()` at the top of `initialize_view()` to pick up external changes (admin commands, XP gains). This refreshes `self.user_data` from ConfigManager and syncs the parent menu view if present.
- **Catch chance formula**: `total_chance = clamp(0, 1, level_bonus + rod.chance + bait.catch_bonus * effectiveness + weather_bonus + time_bonus)`. The `level_catch_bonus(level)` function in `fishing_data.py` provides a curved bonus: `0.35 * ((level-1)/98)^0.7` (0% at Lv1, 35% at Lv99). This is the primary progression driver.
- **Bait effectiveness**: `_catch_fish` multiplies `catch_bonus` by the bait's location-specific `effectiveness` value (defaults to 1.0). This makes bait choice location-dependent. Fish values: Common=5, Uncommon=9, Rare=16, Legendary=35. Junk values: Common=0, Uncommon=1, Rare=2, Legendary=5. Generalist baits (Worm/Cricket/NC) are free; Anchovy/Leech and all specialist baits cost $1 each. Economy targets: ~$240/hr at Lv1, ~$2400/hr at Lv99, ~75% catch rate at Lv99.
- **Specialist baits**: Baits with a `preferred_by` list and `preference_bonus` float act as specialist baits. During fish weight calculation in `_catch_fish`, if the fish type is in the bait's `preferred_by` list, its selection weight is multiplied by `preference_bonus` (2.0x for all specialists). This allows specialist baits to boost specific rarities. The simulator's `_build_fish_weights()` applies the same logic. There are 5 generalist baits (no `preferred_by`) and 4 specialist baits spread across the level range, with the Legendary specialist (Glowworm, Lv75) as the capstone.
- **Specialist locations**: 9 total locations — 5 general (Pond Lv1, River Lv10, Lake Lv25, Ocean Lv45, Deep Sea Lv60) with balanced modifiers, plus 4 specialist (Shallow Creek Lv3 Common 1.8x, Marshlands Lv12 Uncommon 1.8x, Coral Reef Lv30 Rare 1.8x, Abyssal Trench Lv55 Legendary 1.5x) that heavily favor one rarity but penalize others. Specialist locations unlock before their matching specialist bait (e.g., Coral Reef Lv30 → Squid bait Lv40) so the bait upgrade is felt. The location page in menu.py and the location select dropdown both display Normal/Specialized section headers.
- **Simulation**: `ProfitSimulator.analyze_full_setup()` mirrors `_catch_fish` logic exactly. When catch logic changes, update the simulator to match. The `[p]simulate` command opens an interactive menu — it no longer uses subcommands. The simulator assumes perfect player input (no button-press misses). "Nothing caught" in results is pure RNG (25% of failed fish rolls produce nothing, matching the 75% junk fallback in `_catch_fish`).

## Basewars Cog (`basewars/`)

Non-functional cog with stub files for a base-building PvP game. Not ready for development.
