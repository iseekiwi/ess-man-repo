# games/slots.py

import random
from typing import Dict, List, Tuple
from .base_game import BaseGame
from ..data.casino_data import SLOTS_SYMBOLS, SLOTS_REEL_COUNT, JACKPOT_ODDS


class SlotsGame(BaseGame):
    """3-reel fishing-themed slot machine.

    Pure game logic — no Discord dependencies.

    Payout rules:
      - 3 matching symbols: payout_3 * bet * slots_multiplier
      - 2 matching symbols (leftmost pair): payout_2 * bet * slots_multiplier
      - 3x Kiwi: triggers progressive jackpot (no fixed payout_3)
      - No match: lose bet
    """

    def __init__(self):
        # Pre-compute symbol names and weights for random.choices
        self._symbols = list(SLOTS_SYMBOLS.keys())
        self._weights = [SLOTS_SYMBOLS[s]["weight"] for s in self._symbols]

    def spin(self, bet: int, slots_multiplier: float = 1.0) -> Dict:
        """Spin the reels and determine the outcome.

        Args:
            bet: The wager amount.
            slots_multiplier: Guild-configurable payout scalar (default 1.0).

        Returns:
            Dict with reels, match info, payout, and jackpot trigger flag.
        """
        # Jackpot check first — 1/JACKPOT_ODDS per spin, forces 3x Kiwi
        jackpot_trigger = random.randint(1, JACKPOT_ODDS) == 1
        if jackpot_trigger:
            reels = ["Kiwi", "Kiwi", "Kiwi"]
        else:
            reels = self._spin_reels()

        match_type, base_multiplier = self._evaluate(reels)

        if jackpot_trigger:
            # Jackpot payout is handled externally by JackpotManager
            payout = 0
        elif base_multiplier > 0:
            payout = int(bet * base_multiplier * slots_multiplier)
        else:
            payout = 0

        return {
            "reels": reels,
            "emojis": [SLOTS_SYMBOLS[s]["emoji"] for s in reels],
            "match_type": match_type,
            "multiplier": base_multiplier * slots_multiplier if not jackpot_trigger else 0,
            "payout": payout,
            "bet": bet,
            "jackpot_trigger": jackpot_trigger,
            "won": payout > 0 or jackpot_trigger,
        }

    def _spin_reels(self) -> List[str]:
        """Generate reel results using weighted random selection."""
        return random.choices(self._symbols, weights=self._weights, k=SLOTS_REEL_COUNT)

    def _evaluate(self, reels: List[str]) -> Tuple[str, float]:
        """Evaluate the reel result and return (match_type, multiplier).

        Match rules:
          - 3 of a kind: payout_3
          - 2 of a kind (first two match): payout_2
          - Any 2 of a kind: payout_2 * 0.5 (partial match)
          - No match: 0
        """
        a, b, c = reels

        if a == b == c:
            sym_data = SLOTS_SYMBOLS[a]
            return f"three_{a.lower()}", sym_data["payout_3"]

        if a == b:
            sym_data = SLOTS_SYMBOLS[a]
            return f"pair_{a.lower()}", sym_data["payout_2"]

        if b == c:
            sym_data = SLOTS_SYMBOLS[b]
            return f"pair_{b.lower()}", sym_data["payout_2"] * 0.5

        if a == c:
            sym_data = SLOTS_SYMBOLS[a]
            return f"pair_{a.lower()}", sym_data["payout_2"] * 0.5

        return "no_match", 0.0

    def _is_jackpot(self, reels: List[str]) -> bool:
        """Check if the reels show 3x Kiwi (used by _evaluate to skip payout_3)."""
        return all(s == "Kiwi" for s in reels)

    def get_ascii_display(self, emojis: List[str]) -> str:
        """Generate an ASCII slot machine display for embeds."""
        a, b, c = emojis
        lines = [
            "```",
            "\u2554\u2550\u2550\u2550\u2550\u2566\u2550\u2550\u2550\u2550\u2566\u2550\u2550\u2550\u2550\u2557",
            f"\u2551 {a} \u2551 {b} \u2551 {c} \u2551",
            "\u255a\u2550\u2550\u2550\u2550\u2569\u2550\u2550\u2550\u2550\u2569\u2550\u2550\u2550\u2550\u255d",
            "```",
        ]
        return "\n".join(lines)
