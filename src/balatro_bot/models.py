"""Core data models for Balatro game state."""

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Self


class Enhancement(Enum):
    """Card enhancements that modify scoring behavior."""

    NONE = "none"
    BONUS = "bonus"  # +30 Chips when scored
    MULT = "mult"  # +4 Mult when scored
    WILD = "wild"  # Counts as all suits
    GLASS = "glass"  # x2 Mult, 1/4 chance to destroy
    STEEL = "steel"  # x1.5 Mult while held in hand
    STONE = "stone"  # +50 Chips, no rank/suit, always scores
    GOLD = "gold"  # $3 if held in hand at end of round
    LUCKY = "lucky"  # 1/5 chance +20 Mult, 1/15 chance $20


class Edition(Enum):
    """Card editions that provide bonus effects."""

    BASE = "base"
    FOIL = "foil"  # +50 Chips
    HOLOGRAPHIC = "holo"  # +10 Mult
    POLYCHROME = "polychrome"  # x1.5 Mult
    NEGATIVE = "negative"  # +1 Joker/Consumable slot


class Seal(Enum):
    """Card seals that trigger special effects."""

    NONE = "none"
    GOLD = "gold"  # $3 when played and scores
    RED = "red"  # Retrigger 1 time
    BLUE = "blue"  # Creates Planet card if held at end of round
    PURPLE = "purple"  # Creates Tarot card when discarded


class Suit(Enum):
    """Card suits."""

    SPADES = "S"
    HEARTS = "H"
    CLUBS = "C"
    DIAMONDS = "D"

    def __str__(self) -> str:
        symbols = {"S": "♠", "H": "♥", "C": "♣", "D": "♦"}
        return symbols[self.value]


class Rank(IntEnum):
    """Card ranks with numeric values for comparison."""

    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    def __str__(self) -> str:
        if self.value <= 10:
            return str(self.value)
        return {11: "J", 12: "Q", 13: "K", 14: "A"}[self.value]

    @property
    def chip_value(self) -> int:
        """Base chip value for scoring in Balatro."""
        if self.value <= 10:
            return self.value
        if self.value == 14:  # Ace
            return 11
        return 10  # Face cards


class HandType(IntEnum):
    """Poker hand types ordered by base strength.

    Includes Balatro-specific secret hands:
    - FLUSH_HOUSE: Full House where all 5 cards share the same suit
    - FLUSH_FIVE: Five of a Kind where all 5 cards share the same suit
    """

    HIGH_CARD = 1
    PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_FLUSH = 10
    FIVE_OF_A_KIND = 11  # Balatro special
    FLUSH_HOUSE = 12  # Balatro secret: Full House + Flush
    FLUSH_FIVE = 13  # Balatro secret: Five of a Kind + Flush

    @property
    def base_chips(self) -> int:
        """Base chip value for this hand type in Balatro."""
        chips = {
            HandType.HIGH_CARD: 5,
            HandType.PAIR: 10,
            HandType.TWO_PAIR: 20,
            HandType.THREE_OF_A_KIND: 30,
            HandType.STRAIGHT: 30,
            HandType.FLUSH: 35,
            HandType.FULL_HOUSE: 40,
            HandType.FOUR_OF_A_KIND: 60,
            HandType.STRAIGHT_FLUSH: 100,
            HandType.ROYAL_FLUSH: 100,
            HandType.FIVE_OF_A_KIND: 120,
            HandType.FLUSH_HOUSE: 140,
            HandType.FLUSH_FIVE: 160,
        }
        return chips[self]

    @property
    def base_mult(self) -> int:
        """Base multiplier for this hand type in Balatro."""
        mults = {
            HandType.HIGH_CARD: 1,
            HandType.PAIR: 2,
            HandType.TWO_PAIR: 2,
            HandType.THREE_OF_A_KIND: 3,
            HandType.STRAIGHT: 4,
            HandType.FLUSH: 4,
            HandType.FULL_HOUSE: 4,
            HandType.FOUR_OF_A_KIND: 7,
            HandType.STRAIGHT_FLUSH: 8,
            HandType.ROYAL_FLUSH: 8,
            HandType.FIVE_OF_A_KIND: 12,
            HandType.FLUSH_HOUSE: 14,
            HandType.FLUSH_FIVE: 16,
        }
        return mults[self]


@dataclass(frozen=True, slots=True)
class Card:
    """A playing card with rank, suit, and optional modifiers.

    Card modifiers:
    - enhancement: Bonus, Mult, Wild, Glass, Steel, Stone, Gold, Lucky
    - edition: Base, Foil, Holographic, Polychrome, Negative
    - seal: Gold, Red, Blue, Purple
    """

    rank: Rank
    suit: Suit
    enhancement: Enhancement = Enhancement.NONE
    edition: Edition = Edition.BASE
    seal: Seal = Seal.NONE

    def __str__(self) -> str:
        base = f"{self.rank}{self.suit}"
        modifiers = []
        if self.enhancement != Enhancement.NONE:
            modifiers.append(self.enhancement.value)
        if self.edition != Edition.BASE:
            modifiers.append(self.edition.value)
        if self.seal != Seal.NONE:
            modifiers.append(f"{self.seal.value}-seal")
        if modifiers:
            return f"{base}[{','.join(modifiers)}]"
        return base

    def __repr__(self) -> str:
        return f"Card({self.rank!s}{self.suit!s})"

    @property
    def is_wild(self) -> bool:
        """Check if card is wild (counts as all suits)."""
        return self.enhancement == Enhancement.WILD

    @property
    def is_stone(self) -> bool:
        """Check if card is stone (no rank/suit, always scores)."""
        return self.enhancement == Enhancement.STONE

    def has_suit(self, suit: Suit) -> bool:
        """Check if card has a specific suit (considering wild)."""
        if self.is_stone:
            return False  # Stone cards have no suit
        if self.is_wild:
            return True  # Wild cards match all suits
        return self.suit == suit

    def with_enhancement(self, enhancement: Enhancement) -> "Card":
        """Return a new card with the given enhancement."""
        return Card(self.rank, self.suit, enhancement, self.edition, self.seal)

    def with_edition(self, edition: Edition) -> "Card":
        """Return a new card with the given edition."""
        return Card(self.rank, self.suit, self.enhancement, edition, self.seal)

    def with_seal(self, seal: Seal) -> "Card":
        """Return a new card with the given seal."""
        return Card(self.rank, self.suit, self.enhancement, self.edition, seal)

    @classmethod
    def from_string(cls, s: str) -> Self:
        """Parse card from string like 'AS' (Ace of Spades) or '10H' (Ten of Hearts)."""
        s = s.upper().strip()
        suit_char = s[-1]
        rank_str = s[:-1]

        suit_map = {"S": Suit.SPADES, "H": Suit.HEARTS, "C": Suit.CLUBS, "D": Suit.DIAMONDS}
        rank_map = {
            "2": Rank.TWO,
            "3": Rank.THREE,
            "4": Rank.FOUR,
            "5": Rank.FIVE,
            "6": Rank.SIX,
            "7": Rank.SEVEN,
            "8": Rank.EIGHT,
            "9": Rank.NINE,
            "10": Rank.TEN,
            "J": Rank.JACK,
            "Q": Rank.QUEEN,
            "K": Rank.KING,
            "A": Rank.ACE,
        }

        if suit_char not in suit_map:
            raise ValueError(f"Invalid suit: {suit_char}")
        if rank_str not in rank_map:
            raise ValueError(f"Invalid rank: {rank_str}")

        return cls(rank=rank_map[rank_str], suit=suit_map[suit_char])


@dataclass
class Joker:
    """A joker card with its effects.

    Note: Joker ORDER in the list matters for effect resolution.
    """

    id: str
    name: str
    level: int = 1
    # Additional state fields will be added as joker effects are implemented


@dataclass
class BlindInfo:
    """Information about the current blind."""

    name: str
    base_chips: int
    is_boss: bool = False
    modifier: str | None = None  # Boss blind modifiers


@dataclass
class GameState:
    """Complete game state for simulation and decision making.

    This must be perfectly serializable for MCTS state cloning.
    """

    # Deck state
    deck: list[Card] = field(default_factory=list)
    hand: list[Card] = field(default_factory=list)
    discarded: list[Card] = field(default_factory=list)

    # Jokers (ORDER MATTERS for effect resolution)
    jokers: list[Joker] = field(default_factory=list)

    # Economy
    money: int = 4

    # Round progress
    ante: int = 1
    round_in_ante: int = 1  # 1=small blind, 2=big blind, 3=boss blind
    hands_remaining: int = 4
    discards_remaining: int = 3

    # Scoring state
    current_chips: int = 0
    blind_requirement: int = 300

    # RNG state for deterministic simulation
    rng_seed: int | None = None

    # Hand level upgrades (from planet cards)
    hand_levels: dict[HandType, int] = field(
        default_factory=lambda: {ht: 1 for ht in HandType}
    )

    def clone(self) -> Self:
        """Create a deep copy for MCTS simulation."""
        return GameState(
            deck=list(self.deck),
            hand=list(self.hand),
            discarded=list(self.discarded),
            jokers=[Joker(j.id, j.name, j.level) for j in self.jokers],
            money=self.money,
            ante=self.ante,
            round_in_ante=self.round_in_ante,
            hands_remaining=self.hands_remaining,
            discards_remaining=self.discards_remaining,
            current_chips=self.current_chips,
            blind_requirement=self.blind_requirement,
            rng_seed=self.rng_seed,
            hand_levels=dict(self.hand_levels),
        )


def create_standard_deck() -> list[Card]:
    """Create a standard 52-card deck."""
    return [Card(rank=rank, suit=suit) for suit in Suit for rank in Rank]
