"""Deck state tracking for probability calculations.

Tracks the composition of the remaining deck to enable
accurate probability calculations for hand completion.
"""

from dataclasses import dataclass, field
from collections import Counter
from typing import Optional

from .models import Card, Suit, Rank


def create_standard_deck() -> list[Card]:
    """Create a standard 52-card deck."""
    return [
        Card(rank=rank, suit=suit)
        for suit in Suit
        for rank in Rank
    ]


@dataclass
class DeckState:
    """Tracks the current state of the deck.

    Maintains information about:
    - Cards remaining in the deck
    - Cards that have been seen (played or discarded)
    - Derived statistics for probability calculations
    """

    # Core state
    remaining_cards: list[Card] = field(default_factory=list)
    cards_played: list[Card] = field(default_factory=list)
    cards_discarded: list[Card] = field(default_factory=list)

    # Cached counts (updated on modifications)
    _suit_counts: Counter = field(default_factory=Counter, repr=False)
    _rank_counts: Counter = field(default_factory=Counter, repr=False)
    _dirty: bool = field(default=True, repr=False)

    def __post_init__(self):
        """Initialize with standard deck if empty."""
        if not self.remaining_cards and not self.cards_played and not self.cards_discarded:
            self.remaining_cards = create_standard_deck()
        self._update_counts()

    def _update_counts(self) -> None:
        """Update cached suit and rank counts."""
        self._suit_counts = Counter(c.suit for c in self.remaining_cards)
        self._rank_counts = Counter(c.rank for c in self.remaining_cards)
        self._dirty = False

    @property
    def total_remaining(self) -> int:
        """Total cards remaining in deck."""
        return len(self.remaining_cards)

    @property
    def total_seen(self) -> int:
        """Total cards that have been seen (played + discarded)."""
        return len(self.cards_played) + len(self.cards_discarded)

    def suit_count(self, suit: Suit) -> int:
        """Count of remaining cards of a specific suit."""
        if self._dirty:
            self._update_counts()
        return self._suit_counts.get(suit, 0)

    def rank_count(self, rank: Rank) -> int:
        """Count of remaining cards of a specific rank."""
        if self._dirty:
            self._update_counts()
        return self._rank_counts.get(rank, 0)

    def card_count(self, rank: Rank, suit: Suit) -> int:
        """Count of a specific card (0 or 1 in standard deck)."""
        return sum(1 for c in self.remaining_cards if c.rank == rank and c.suit == suit)

    def remove_card(self, card: Card, played: bool = True) -> bool:
        """Remove a card from the deck.

        Args:
            card: Card to remove
            played: If True, add to played pile; else add to discarded pile

        Returns:
            True if card was found and removed, False otherwise
        """
        for i, c in enumerate(self.remaining_cards):
            if c.rank == card.rank and c.suit == card.suit:
                self.remaining_cards.pop(i)
                if played:
                    self.cards_played.append(card)
                else:
                    self.cards_discarded.append(card)
                self._dirty = True
                return True
        return False

    def remove_cards(self, cards: list[Card], played: bool = True) -> int:
        """Remove multiple cards from the deck.

        Args:
            cards: Cards to remove
            played: If True, add to played pile; else add to discarded pile

        Returns:
            Number of cards successfully removed
        """
        removed = 0
        for card in cards:
            if self.remove_card(card, played):
                removed += 1
        return removed

    def reset(self) -> None:
        """Reset to a fresh standard deck."""
        self.remaining_cards = create_standard_deck()
        self.cards_played = []
        self.cards_discarded = []
        self._dirty = True

    def clone(self) -> "DeckState":
        """Create a deep copy of this deck state."""
        return DeckState(
            remaining_cards=self.remaining_cards.copy(),
            cards_played=self.cards_played.copy(),
            cards_discarded=self.cards_discarded.copy(),
        )

    def get_suit_distribution(self) -> dict[Suit, int]:
        """Get distribution of suits in remaining deck."""
        if self._dirty:
            self._update_counts()
        return dict(self._suit_counts)

    def get_rank_distribution(self) -> dict[Rank, int]:
        """Get distribution of ranks in remaining deck."""
        if self._dirty:
            self._update_counts()
        return dict(self._rank_counts)

    def get_high_card_count(self) -> int:
        """Count of high cards (10, J, Q, K, A) remaining."""
        high_ranks = {Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE}
        return sum(self.rank_count(r) for r in high_ranks)

    def get_face_card_count(self) -> int:
        """Count of face cards (J, Q, K) remaining."""
        face_ranks = {Rank.JACK, Rank.QUEEN, Rank.KING}
        return sum(self.rank_count(r) for r in face_ranks)

    def has_straight_potential(self, ranks_in_hand: set[Rank]) -> dict[str, float]:
        """Analyze straight potential given ranks in hand.

        Returns dict with:
        - 'open_ended': Number of open-ended straight draws
        - 'gutshot': Number of gutshot straight draws
        - 'best_outs': Maximum outs for any straight
        """
        hand_values = {r.value for r in ranks_in_hand}

        # Check each possible straight
        straights = [
            [14, 2, 3, 4, 5],  # Wheel
            [2, 3, 4, 5, 6],
            [3, 4, 5, 6, 7],
            [4, 5, 6, 7, 8],
            [5, 6, 7, 8, 9],
            [6, 7, 8, 9, 10],
            [7, 8, 9, 10, 11],
            [8, 9, 10, 11, 12],
            [9, 10, 11, 12, 13],
            [10, 11, 12, 13, 14],  # Broadway
        ]

        open_ended = 0
        gutshot = 0
        best_outs = 0

        for seq in straights:
            have = sum(1 for v in seq if v in hand_values)
            need = 5 - have

            if need == 1:
                # One card away - count outs
                missing = [v for v in seq if v not in hand_values][0]
                missing_rank = Rank(missing) if missing <= 14 else Rank.ACE
                outs = self.rank_count(missing_rank)
                best_outs = max(best_outs, outs)

                # Check if open-ended (missing card is at either end)
                if missing == seq[0] or missing == seq[-1]:
                    open_ended += 1
                else:
                    gutshot += 1

            elif need == 2 and have >= 3:
                # Two cards away but have 3 in sequence
                gutshot += 1

        return {
            "open_ended": open_ended,
            "gutshot": gutshot,
            "best_outs": best_outs,
        }

    @classmethod
    def from_known_cards(
        cls,
        cards_in_hand: list[Card],
        cards_played: Optional[list[Card]] = None,
        cards_discarded: Optional[list[Card]] = None,
    ) -> "DeckState":
        """Create deck state from known cards.

        Args:
            cards_in_hand: Cards currently in player's hand
            cards_played: Cards that have been played this round
            cards_discarded: Cards that have been discarded

        Returns:
            DeckState with remaining cards calculated
        """
        all_cards = create_standard_deck()
        seen = set()

        # Remove cards in hand
        for card in cards_in_hand:
            seen.add((card.rank, card.suit))

        # Remove played cards
        played = cards_played or []
        for card in played:
            seen.add((card.rank, card.suit))

        # Remove discarded cards
        discarded = cards_discarded or []
        for card in discarded:
            seen.add((card.rank, card.suit))

        remaining = [c for c in all_cards if (c.rank, c.suit) not in seen]

        return cls(
            remaining_cards=remaining,
            cards_played=played.copy() if played else [],
            cards_discarded=discarded.copy() if discarded else [],
        )

    @classmethod
    def from_remaining_count(
        cls,
        total_remaining: int,
        suit_counts: Optional[dict[Suit, int]] = None,
        rank_counts: Optional[dict[Rank, int]] = None,
    ) -> "DeckState":
        """Create approximate deck state from counts.

        Used when we don't know exact cards but have counts.
        Creates a representative deck matching the distribution.

        Args:
            total_remaining: Total cards remaining
            suit_counts: Known suit distribution (defaults to even)
            rank_counts: Known rank distribution (defaults to even)

        Returns:
            DeckState approximating the given distribution
        """
        # If no distribution given, assume even
        if suit_counts is None:
            per_suit = total_remaining // 4
            suit_counts = {s: per_suit for s in Suit}
            # Distribute remainder
            for i, suit in enumerate(Suit):
                if i < total_remaining % 4:
                    suit_counts[suit] += 1

        if rank_counts is None:
            per_rank = total_remaining // 13
            rank_counts = {r: per_rank for r in Rank}
            for i, rank in enumerate(Rank):
                if i < total_remaining % 13:
                    rank_counts[rank] += 1

        # Build a representative deck
        cards = []
        for suit in Suit:
            suit_need = suit_counts.get(suit, 0)
            for rank in Rank:
                if suit_need <= 0:
                    break
                rank_need = rank_counts.get(rank, 0)
                if rank_need > 0:
                    cards.append(Card(rank=rank, suit=suit))
                    suit_need -= 1
                    rank_counts[rank] -= 1

        return cls(remaining_cards=cards)

    def __str__(self) -> str:
        """Human-readable representation."""
        suits = ", ".join(f"{s.name[0]}:{self.suit_count(s)}" for s in Suit)
        return f"DeckState({self.total_remaining} cards: {suits})"
