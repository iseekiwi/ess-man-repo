# CLAUDE.md — Kiwisino Casino Cog

This file provides guidance to Claude Code when working with the Kiwisino cog.

## Overview

Kiwisino is a **casino gambling cog** for Red-DiscordBot by iseekiwi. It provides blackjack, slots, and coinflip games with an interactive Discord UI, stat tracking, leaderboards, progressive jackpot, and admin controls.

The cog uses Red's built-in bank (`redbot.core.bank`) for currency. Installed via `[p]cog install` and loaded with `[p]load kiwisino`.

## Architecture

### Entry Point

`__init__.py` calls `bot.add_cog(Kiwisino(bot))` loading the main `Kiwisino` class from `main.py`.

### Data Layer (`data/casino_data.py`)

Single source of truth for all game constants:

- **TypedDicts**: `SlotSymbolData`, `BlackjackPayouts`, `BetLimits`, `JackpotConfig`, `GameStatsData`, `BlackjackStatsData`, `SlotsStatsData`, `OverallStatsData`
- **Blackjack config**: `BLACKJACK_CONFIG` — 6-deck shoe, reshuffle at 25% remaining, dealer stands on soft 17, max 3 splits, double after split allowed
- **Slots symbols**: `SLOTS_SYMBOLS` — 7 fishing-themed symbols (Seaweed, Shell, Crab, Fish, Octopus, Treasure, Kiwi) with weights and payout multipliers. 3x Kiwi triggers jackpot.
- **Card constants**: `CARD_SUITS` (Unicode ♠♥♦♣), `CARD_RANKS`, `CARD_VALUES`
- **Default configs**: `DEFAULT_BET_LIMITS`, `DEFAULT_PAYOUT_MULTIPLIERS`, `DEFAULT_JACKPOT_CONFIG`
- **Schemas**: `DEFAULT_USER_DATA` (per-user stats), `DEFAULT_GUILD_SETTINGS` (per-guild config)
- **Canonical game list**: `GAME_NAMES = ["blackjack", "slots", "coinflip"]`

### Game Logic Layer (`games/`)

Pure Python — no Discord dependencies. Testable independently.

- **`base_game.py`** — `BaseGame` with `validate_bet(bet, min, max)` and `calculate_payout(bet, multiplier)`. All games inherit from this.
- **`blackjack.py`** — `Card`, `Deck`, `Hand`, `BlackjackGame`. Deck persists across hands (realistic shoe). State machine: `WAITING -> PLAYER_TURN -> DEALER_TURN -> RESOLVED`. Methods: `new_hand(bet)`, `hit()`, `stand()`, `double_down()`, `split()`, `surrender()`. Returns game state dicts.
- **`slots.py`** — `SlotsGame`. `spin(bet, slots_multiplier)` generates 3 weighted reel results, evaluates matches (3-of-a-kind, pairs), checks jackpot trigger. `get_ascii_display(emojis)` renders the slot machine.
- **`coinflip.py`** — `CoinflipGame`. `flip(bet, choice, payout_multiplier)` — 50/50 chance, configurable payout.

### Utils Layer (`utils/`)

- **`logging_config.py`** — `KiwisinoLoggerManager` singleton (separate from fishing). Logs to `kiwisino/logs/kiwisino.log`. Must call `KiwisinoLoggerManager.reset()` in `cog_unload`.
- **`timeout_manager.py`** — `KiwisinoTimeoutManager` singleton (separate from fishing). Identical behaviour to fishing's `TimeoutManager`. Must call `KiwisinoTimeoutManager.reset()` in `cog_unload`.
- **`config_manager.py`** — `ConfigManager` with `ConfigResult` pattern. Uses `register_user` for stats and `register_guild` for settings (per-server casino config). `_validate_user_data()` repairs corrupted stats on every read. Identifier: `987654321`.
- **`stats_manager.py`** — `StatsManager` — **sole authority** for recording game outcomes. `record_game()` updates per-game stats, overall stats, biggest wins. Do not write stats elsewhere.
- **`jackpot_manager.py`** — `JackpotManager` — manages progressive slots jackpot per guild. `contribute()` adds to pool from each bet. `award()` pays out and resets to seed. `reset()` and `set_seed()` for admin control.
- **`payout_log.py`** — `PayoutLog` — admin audit trail. Logs every payout to guild config (capped at 500 entries). `log_payout()`, `get_recent()`, `get_user_log()`.

### UI Layer (`ui/`)

- **`base.py`** — `BaseView` extends `discord.ui.View` with timeout=None, `KiwisinoTimeoutManager` integration, author-only interaction check, child-to-parent timeout delegation, session release, cleanup. Identical pattern to fishing's BaseView. Also has `ConfirmView`.
- **`components.py`** — `MessageManager` for temp/ephemeral messages, `ConfirmationButton`, `NavigationButton`.
- **`hub.py`** — `CasinoHubView(BaseView)` — root menu view. Buttons: Blackjack, Slots, Coinflip, My Stats, Leaderboard, Close. Shows balance, net profit, jackpot, bet limits. `BetModal` for bet input. Navigates to game/stats child views.
- **`blackjack.py`** — `BlackjackView(BaseView)` — betting -> playing (Hit/Stand/Double/Split/Surrender) -> result (Play Again/Back). Persistent deck per guild. Processes results via bank withdraw/deposit and StatsManager.
- **`slots.py`** — `SlotsView(BaseView)` — betting -> spin -> result (Spin Again/Change Bet/Back). ASCII slot machine display. Progressive jackpot integration.
- **`coinflip.py`** — `CoinflipView(BaseView)` — betting -> choosing (Heads/Tails) -> result (Play Again/Change Bet/Back).
- **`stats.py`** — `StatsView(BaseView)` — detailed per-game and overall stats display.

## Key Patterns

### Bank-First Pattern
Withdraw the bet **before** playing the game. Deposit winnings after. This avoids TOCTOU issues — if the game logic crashes, the player loses the bet (safe for the economy) rather than playing without paying.

### ConfigResult Pattern
All config operations return `ConfigResult(success, data, error, error_code)`. Always check `.success` before using `.data`.

### View Hierarchy
```
CasinoHubView (root, owns session)
  ├── BlackjackView (child)
  ├── SlotsView (child)
  ├── CoinflipView (child)
  └── StatsView (child)
```
Child views set `parent_menu_view = hub`. Timeout delegation and view transitions work identically to the fishing cog. "Back to Hub" reuses the parent view object.

### Timeout Architecture
Discord's built-in `View.timeout` is disabled (`timeout=None`). All expiry goes through `KiwisinoTimeoutManager`. Child views inherit timeout from parent via `handle_view_transition()`. Parent pauses while child is active.

### Active Session Guard
`Kiwisino._active_sessions` (dict of user_id -> view) prevents duplicate sessions. `BaseView._release_session()` frees the slot on cleanup/timeout using identity check (`is self`).

### Singleton Cleanup
`KiwisinoTimeoutManager` and `KiwisinoLoggerManager` must be reset in `cog_unload` to avoid stale state on cog reload.

### Persistent Blackjack Deck
Each guild has a persistent `Deck` stored in `Kiwisino._blackjack_decks[guild_id]`. The shoe survives across hands within a session (realistic card counting). Reshuffles automatically at 25% remaining. Cleared on cog unload.

## Config Schema

### User Data (global, per-user)
```python
{
    "stats": {
        "blackjack": {games_played, games_won, games_lost, games_pushed, blackjacks_hit, total_wagered, total_won, biggest_win},
        "slots": {games_played, games_won, games_lost, total_wagered, total_won, biggest_win, jackpots_won, jackpot_total},
        "coinflip": {games_played, games_won, games_lost, total_wagered, total_won, biggest_win},
    },
    "overall": {total_wagered, total_won, net_profit, biggest_win, biggest_win_game},
}
```

### Guild Settings (per-server)
```python
{
    "games_enabled": {"blackjack": True, "slots": True, "coinflip": True},
    "bet_limits": {"blackjack": {"min": 10, "max": 5000}, ...},
    "payout_multipliers": {
        "blackjack": {"blackjack": 1.5, "win": 1.0, "push": 0.0, "insurance": 2.0, "surrender": -0.5},
        "coinflip": 1.95,
        "slots": 1.0,
    },
    "jackpot": {"current_amount": 1000, "seed_amount": 1000, "contribution_rate": 0.02},
    "payout_log": [],
    "payout_log_max": 500,
}
```

## Commands

### User
- `[p]kiwisino` (alias: `[p]casino`) — Open the casino hub

### Admin (`[p]casinoadmin` / `[p]cadmin`)
- `toggle <game>` — Enable/disable a game
- `betlimit <game> <min> <max>` — Set bet limits
- `payout <game> <type> <multiplier>` — Set payout multiplier
- `jackpot view` — View current jackpot
- `jackpot reset` — Reset to seed
- `jackpot seed <amount>` — Set seed amount
- `payoutlog [count]` — View recent payout log
- `stats <member>` — View user stats
- `resetstats <member>` — Reset user stats (owner only)

## Game Rules

### Blackjack (Standard Vegas)
- 6-deck shoe, persistent across hands (reshuffles at 25% remaining)
- Dealer stands on soft 17
- Natural blackjack pays 3:2 (configurable)
- Double down on any two cards, including after split
- Split up to 3 times (4 hands max)
- Surrender available as first action on first hand only
- No insurance prompt (insurance payout is configurable but not offered in UI)

### Slots (3-Reel, Fishing Theme)
- 7 symbols: Seaweed (30w), Shell (25w), Crab (20w), Fish (15w), Octopus (7w), Treasure (2w), Kiwi (1w)
- 3-of-a-kind pays symbol's `payout_3` multiplier
- First two matching pays `payout_2`; other pairs pay `payout_2 * 0.5`
- 3x Kiwi triggers progressive jackpot
- 2% of each bet contributes to jackpot pool

### Coinflip
- 50/50 heads or tails
- Default payout: 1.95x (2.5% house edge)
- Configurable payout multiplier

## Key Invariants

- **Stats recording**: ONLY via `StatsManager.record_game()` — never write stats elsewhere
- **Bank operations**: Withdraw BEFORE game, deposit winnings AFTER
- **Jackpot**: ONLY on slots, triggered by 3x Kiwi, managed by `JackpotManager`
- **Singletons**: Reset in `cog_unload` — `KiwisinoTimeoutManager.reset()`, `KiwisinoLoggerManager.reset()`
- **Session guard**: One active session per user, released via identity check
- **Payout log**: Capped at 500 entries, trimmed on write
- **Deck persistence**: Per-guild, survives across hands, cleared on cog unload
