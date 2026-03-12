# games/base_game.py


class BaseGame:
    """Base class for casino games. Pure logic — no Discord dependencies."""

    def validate_bet(self, bet: int, min_bet: int, max_bet: int) -> tuple:
        """Validate a bet amount against limits.

        Returns (valid: bool, error_message: str).
        """
        if not isinstance(bet, int) or bet <= 0:
            return False, "Bet must be a positive whole number."
        if bet < min_bet:
            return False, f"Minimum bet is **${min_bet:,}**."
        if bet > max_bet:
            return False, f"Maximum bet is **${max_bet:,}**."
        return True, ""

    def calculate_payout(self, bet: int, multiplier: float) -> int:
        """Calculate integer payout from bet and multiplier.

        multiplier > 0 means profit on top of the bet.
        multiplier == 0 means push (bet returned, no profit).
        multiplier < 0 means partial loss (e.g. surrender = -0.5).
        """
        if multiplier < 0:
            # Partial loss — return portion of bet
            return max(0, int(bet + bet * multiplier))
        # Profit — bet is returned plus winnings
        return int(bet + bet * multiplier)
