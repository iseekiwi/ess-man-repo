# games/blackjack.py

import random
from typing import Dict, List, Optional, Tuple
from .base_game import BaseGame
from ..data.casino_data import (
    BLACKJACK_CONFIG,
    CARD_SUITS,
    CARD_RANKS,
    CARD_VALUES,
)


class Card:
    """A single playing card."""

    __slots__ = ('rank', 'suit')

    def __init__(self, rank: str, suit: str):
        self.rank = rank
        self.suit = suit

    @property
    def value(self) -> int:
        return CARD_VALUES[self.rank]

    @property
    def display(self) -> str:
        return f"{self.rank}{self.suit}"

    def __repr__(self) -> str:
        return self.display


class Deck:
    """A multi-deck shoe with persistent state across hands.

    Reshuffles automatically when the remaining cards fall below
    ``reshuffle_threshold`` (fraction of total cards).
    """

    def __init__(
        self,
        deck_count: int = BLACKJACK_CONFIG["deck_count"],
        reshuffle_threshold: float = BLACKJACK_CONFIG["reshuffle_threshold"],
    ):
        self.deck_count = deck_count
        self.reshuffle_threshold = reshuffle_threshold
        self._total_cards = deck_count * 52
        self.cards: List[Card] = []
        self.shuffle()

    def shuffle(self):
        self.cards = [
            Card(rank, suit)
            for _ in range(self.deck_count)
            for suit in CARD_SUITS
            for rank in CARD_RANKS
        ]
        random.shuffle(self.cards)

    @property
    def needs_reshuffle(self) -> bool:
        return len(self.cards) < self._total_cards * self.reshuffle_threshold

    def deal(self) -> Card:
        if self.needs_reshuffle:
            self.shuffle()
        return self.cards.pop()

    @property
    def remaining(self) -> int:
        return len(self.cards)


class Hand:
    """A blackjack hand with automatic ace adjustment."""

    def __init__(self):
        self.cards: List[Card] = []
        self.is_doubled = False
        self.is_split_hand = False

    def add_card(self, card: Card):
        self.cards.append(card)

    @property
    def value(self) -> int:
        total = sum(c.value for c in self.cards)
        aces = sum(1 for c in self.cards if c.rank == "A")
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total

    @property
    def is_soft(self) -> bool:
        """True if the hand contains an ace counted as 11."""
        total = sum(c.value for c in self.cards)
        aces = sum(1 for c in self.cards if c.rank == "A")
        while total > 21 and aces:
            total -= 10
            aces -= 1
        # If we still have aces left uncollapsed, the hand is soft
        return aces > 0 and total <= 21

    @property
    def is_blackjack(self) -> bool:
        return len(self.cards) == 2 and self.value == 21 and not self.is_split_hand

    @property
    def is_bust(self) -> bool:
        return self.value > 21

    @property
    def is_pair(self) -> bool:
        return len(self.cards) == 2 and self.cards[0].rank == self.cards[1].rank

    @property
    def display(self) -> str:
        return " ".join(c.display for c in self.cards)

    @property
    def display_with_value(self) -> str:
        return f"{self.display} ({self.value})"


class BlackjackGame(BaseGame):
    """Full Vegas blackjack game logic.

    State machine: WAITING -> PLAYER_TURN -> DEALER_TURN -> RESOLVED

    The deck persists across games (``new_hand()`` reuses the same shoe).
    """

    WAITING = "waiting"
    PLAYER_TURN = "player_turn"
    DEALER_TURN = "dealer_turn"
    RESOLVED = "resolved"

    def __init__(self, deck: Optional[Deck] = None):
        self.deck = deck or Deck()
        self.state = self.WAITING
        self.player_hands: List[Hand] = []
        self.dealer_hand: Optional[Hand] = None
        self.current_hand_index = 0
        self.bet = 0
        self.results: List[Dict] = []  # one result per player hand

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def new_hand(self, bet: int) -> Dict:
        """Start a new hand. Returns the initial game state dict."""
        self.bet = bet
        self.results = []
        self.current_hand_index = 0
        self.player_hands = [Hand()]
        self.dealer_hand = Hand()

        # Deal: player, dealer, player, dealer
        self.player_hands[0].add_card(self.deck.deal())
        self.dealer_hand.add_card(self.deck.deal())
        self.player_hands[0].add_card(self.deck.deal())
        self.dealer_hand.add_card(self.deck.deal())

        self.state = self.PLAYER_TURN

        # Check for natural blackjack
        player_bj = self.player_hands[0].is_blackjack
        dealer_bj = self.dealer_hand.is_blackjack

        if player_bj or dealer_bj:
            self.state = self.RESOLVED
            return self._resolve_naturals(player_bj, dealer_bj)

        return self._game_state()

    def hit(self) -> Dict:
        """Player hits on the current hand."""
        if self.state != self.PLAYER_TURN:
            return self._game_state()

        hand = self._current_hand()
        hand.add_card(self.deck.deal())

        if hand.is_bust:
            return self._advance_hand()

        if hand.value == 21:
            return self._advance_hand()

        return self._game_state()

    def stand(self) -> Dict:
        """Player stands on the current hand."""
        if self.state != self.PLAYER_TURN:
            return self._game_state()
        return self._advance_hand()

    def double_down(self) -> Dict:
        """Player doubles down — one card, then stand."""
        if self.state != self.PLAYER_TURN:
            return self._game_state()

        hand = self._current_hand()
        if len(hand.cards) != 2:
            return self._game_state()

        hand.is_doubled = True
        hand.add_card(self.deck.deal())
        return self._advance_hand()

    def split(self) -> Dict:
        """Split the current hand into two hands."""
        if self.state != self.PLAYER_TURN:
            return self._game_state()

        hand = self._current_hand()
        if not hand.is_pair:
            return self._game_state()

        if len(self.player_hands) > BLACKJACK_CONFIG["max_splits"]:
            return self._game_state()

        # Create new hand with the second card
        new_hand = Hand()
        new_hand.is_split_hand = True
        new_hand.add_card(hand.cards.pop())

        hand.is_split_hand = True
        # Deal one card to each hand
        hand.add_card(self.deck.deal())
        new_hand.add_card(self.deck.deal())

        # Insert new hand after current
        self.player_hands.insert(self.current_hand_index + 1, new_hand)

        # If the current hand is 21 after split, auto-advance
        if hand.value == 21:
            return self._advance_hand()

        return self._game_state()

    def surrender(self) -> Dict:
        """Player surrenders — only allowed as first action on first hand."""
        if self.state != self.PLAYER_TURN:
            return self._game_state()

        hand = self._current_hand()
        if len(hand.cards) != 2 or self.current_hand_index != 0 or len(self.player_hands) > 1:
            return self._game_state()

        self.state = self.RESOLVED
        self.results = [{
            "outcome": "surrender",
            "hand_index": 0,
            "player_hand": hand.display_with_value,
            "dealer_hand": self.dealer_hand.display_with_value,
            "bet": self.bet,
            "payout_multiplier": -0.5,
        }]
        return self._game_state()

    # ------------------------------------------------------------------
    # Available actions
    # ------------------------------------------------------------------

    def available_actions(self) -> List[str]:
        """Return list of valid actions for the current state."""
        if self.state != self.PLAYER_TURN:
            return []

        hand = self._current_hand()
        actions = ["hit", "stand"]

        if len(hand.cards) == 2:
            actions.append("double_down")

            if hand.is_pair and len(self.player_hands) <= BLACKJACK_CONFIG["max_splits"]:
                actions.append("split")

            if self.current_hand_index == 0 and len(self.player_hands) == 1:
                actions.append("surrender")

        return actions

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _current_hand(self) -> Hand:
        return self.player_hands[self.current_hand_index]

    def _advance_hand(self) -> Dict:
        """Move to the next hand, or to dealer turn if all hands are done."""
        self.current_hand_index += 1
        if self.current_hand_index >= len(self.player_hands):
            return self._play_dealer()
        # If next hand is already 21, auto-advance
        if self._current_hand().value == 21:
            return self._advance_hand()
        return self._game_state()

    def _play_dealer(self) -> Dict:
        """Play out the dealer's hand according to house rules."""
        self.state = self.DEALER_TURN

        # If all player hands are bust, no need to play dealer
        all_bust = all(h.is_bust for h in self.player_hands)
        if not all_bust:
            while self._dealer_should_hit():
                self.dealer_hand.add_card(self.deck.deal())

        self.state = self.RESOLVED
        self._resolve_hands()
        return self._game_state()

    def _dealer_should_hit(self) -> bool:
        dealer_val = self.dealer_hand.value
        if dealer_val < 17:
            return True
        if dealer_val == 17 and self.dealer_hand.is_soft:
            return not BLACKJACK_CONFIG["dealer_stands_on_soft_17"]
        return False

    def _resolve_naturals(self, player_bj: bool, dealer_bj: bool) -> Dict:
        """Resolve the hand when one or both sides have a natural blackjack."""
        if player_bj and dealer_bj:
            self.results = [{
                "outcome": "push",
                "hand_index": 0,
                "player_hand": self.player_hands[0].display_with_value,
                "dealer_hand": self.dealer_hand.display_with_value,
                "bet": self.bet,
                "payout_multiplier": 0.0,
            }]
        elif player_bj:
            self.results = [{
                "outcome": "blackjack",
                "hand_index": 0,
                "player_hand": self.player_hands[0].display_with_value,
                "bet": self.bet,
                "dealer_hand": self.dealer_hand.display_with_value,
                "payout_multiplier": 1.5,  # overridden by guild payout config
            }]
        else:  # dealer blackjack only
            self.results = [{
                "outcome": "dealer_blackjack",
                "hand_index": 0,
                "player_hand": self.player_hands[0].display_with_value,
                "dealer_hand": self.dealer_hand.display_with_value,
                "bet": self.bet,
                "payout_multiplier": -1.0,
            }]
        return self._game_state()

    def _resolve_hands(self):
        """Compare each player hand against the dealer and build results."""
        dealer_val = self.dealer_hand.value
        dealer_bust = self.dealer_hand.is_bust

        self.results = []
        for i, hand in enumerate(self.player_hands):
            bet = self.bet * (2 if hand.is_doubled else 1)

            if hand.is_bust:
                outcome = "bust"
                multiplier = -1.0
            elif dealer_bust:
                outcome = "win"
                multiplier = 1.0
            elif hand.value > dealer_val:
                outcome = "win"
                multiplier = 1.0
            elif hand.value < dealer_val:
                outcome = "lose"
                multiplier = -1.0
            else:
                outcome = "push"
                multiplier = 0.0

            self.results.append({
                "outcome": outcome,
                "hand_index": i,
                "player_hand": hand.display_with_value,
                "dealer_hand": self.dealer_hand.display_with_value,
                "bet": bet,
                "payout_multiplier": multiplier,
                "is_doubled": hand.is_doubled,
            })

    def _game_state(self) -> Dict:
        """Return the full game state for the UI to render."""
        dealer_cards = self.dealer_hand.display_with_value
        dealer_showing = self.dealer_hand.cards[0].display if self.dealer_hand.cards else ""

        # During player turn, hide the dealer's hole card
        if self.state == self.PLAYER_TURN:
            dealer_display = f"{dealer_showing} ??"
            dealer_value = self.dealer_hand.cards[0].value
        else:
            dealer_display = dealer_cards
            dealer_value = self.dealer_hand.value

        hands_display = []
        for i, hand in enumerate(self.player_hands):
            hands_display.append({
                "index": i,
                "cards": hand.display,
                "value": hand.value,
                "display": hand.display_with_value,
                "is_bust": hand.is_bust,
                "is_blackjack": hand.is_blackjack,
                "is_doubled": hand.is_doubled,
                "is_current": i == self.current_hand_index and self.state == self.PLAYER_TURN,
            })

        return {
            "state": self.state,
            "dealer": {
                "display": dealer_display,
                "value": dealer_value,
                "full_display": dealer_cards,
                "full_value": self.dealer_hand.value,
            },
            "hands": hands_display,
            "current_hand": self.current_hand_index,
            "bet": self.bet,
            "results": self.results,
            "actions": self.available_actions(),
            "deck_remaining": self.deck.remaining,
        }
