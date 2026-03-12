# games/coinflip.py

import random
from typing import Dict
from .base_game import BaseGame


class CoinflipGame(BaseGame):
    """Simple coin flip game. Pure logic — no Discord dependencies."""

    HEADS = "heads"
    TAILS = "tails"
    CHOICES = [HEADS, TAILS]

    def flip(self, bet: int, choice: str, payout_multiplier: float = 1.95) -> Dict:
        """Flip the coin and resolve the bet.

        Args:
            bet: The wager amount.
            choice: Player's choice ("heads" or "tails").
            payout_multiplier: Configurable win multiplier (default 1.95).

        Returns:
            Dict with result, win/loss, and payout.
        """
        result = random.choice(self.CHOICES)
        won = choice.lower() == result

        if won:
            payout = int(bet * payout_multiplier)
        else:
            payout = 0

        return {
            "result": result,
            "choice": choice.lower(),
            "won": won,
            "bet": bet,
            "payout": payout,
            "multiplier": payout_multiplier if won else 0,
        }
