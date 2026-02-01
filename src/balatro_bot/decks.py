"""Starting decks with different effects and modifiers.

This module defines the 15 starting decks available in Balatro:
- 5 Base decks (Red, Blue, Yellow, Green, Black) - unlocked by collection
- 5 Win decks (Magic, Nebula, Ghost, Abandoned, Checkered) - unlocked by winning
- 5 Stake decks (Zodiac, Painted, Anaglyph, Plasma, Erratic) - unlocked by stakes
"""

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from balatro_bot.models import Card, Rank, Suit

if TYPE_CHECKING:
    pass


class DeckType(Enum):
    """All available starting deck types."""

    # Base decks (unlocked by discovering items)
    RED = "red"  # +1 discard
    BLUE = "blue"  # +1 hand
    YELLOW = "yellow"  # +$10 starting money
    GREEN = "green"  # Economy based on remaining hands/discards, no interest
    BLACK = "black"  # +1 joker slot, -1 hand

    # Win decks (unlocked by winning with base decks)
    MAGIC = "magic"  # Crystal Ball voucher, 2x The Fool
    NEBULA = "nebula"  # Telescope voucher, -1 consumable slot
    GHOST = "ghost"  # Spectral cards in shop, starts with Hex
    ABANDONED = "abandoned"  # No face cards (40 cards)
    CHECKERED = "checkered"  # 26 Spades, 26 Hearts only

    # Stake decks (unlocked by winning at specific stakes)
    ZODIAC = "zodiac"  # Tarot Merchant, Planet Merchant, Overstock vouchers
    PAINTED = "painted"  # +2 hand size, -1 joker slot
    ANAGLYPH = "anaglyph"  # Double Tag after each Boss Blind
    PLASMA = "plasma"  # Balance chips/mult, 2x blind size
    ERRATIC = "erratic"  # Randomized ranks and suits


@dataclass
class DeckDefinition:
    """Definition of a starting deck with all its modifiers."""

    deck_type: DeckType
    name: str
    description: str

    # Resource modifiers
    bonus_hands: int = 0  # Added hands per round
    bonus_discards: int = 0  # Added discards per round
    bonus_money: int = 0  # Starting money bonus
    bonus_hand_size: int = 0  # Hand size modifier
    bonus_joker_slots: int = 0  # Joker slot modifier
    bonus_consumable_slots: int = 0  # Consumable slot modifier

    # Economy modifiers
    money_per_remaining_hand: int = 0  # Green deck effect
    money_per_remaining_discard: int = 0  # Green deck effect
    has_interest: bool = True  # False for Green deck

    # Blind modifiers
    blind_size_multiplier: float = 1.0  # Plasma deck doubles blinds

    # Special effects
    balance_chips_mult: bool = False  # Plasma deck effect
    spectral_in_shop: bool = False  # Ghost deck effect
    double_tag_on_boss: bool = False  # Anaglyph deck effect

    # Starting vouchers (list of voucher IDs)
    starting_vouchers: list[str] = field(default_factory=list)

    # Starting consumables (list of (type, id) tuples)
    starting_consumables: list[tuple[str, str]] = field(default_factory=list)

    # Deck composition flags
    no_face_cards: bool = False  # Abandoned deck
    only_spades_hearts: bool = False  # Checkered deck
    randomize_cards: bool = False  # Erratic deck

    # Unlock conditions
    unlock_requirement: str = ""


# =============================================================================
# Deck Definitions
# =============================================================================

DECKS: dict[DeckType, DeckDefinition] = {
    # Base decks
    DeckType.RED: DeckDefinition(
        deck_type=DeckType.RED,
        name="Red Deck",
        description="+1 discard every round",
        bonus_discards=1,
        unlock_requirement="Available from start",
    ),
    DeckType.BLUE: DeckDefinition(
        deck_type=DeckType.BLUE,
        name="Blue Deck",
        description="+1 hand every round",
        bonus_hands=1,
        unlock_requirement="Discover 20 items",
    ),
    DeckType.YELLOW: DeckDefinition(
        deck_type=DeckType.YELLOW,
        name="Yellow Deck",
        description="Start with extra $10",
        bonus_money=10,
        unlock_requirement="Discover 50 items",
    ),
    DeckType.GREEN: DeckDefinition(
        deck_type=DeckType.GREEN,
        name="Green Deck",
        description="At end of round: $2 per remaining Hand, $1 per remaining Discard. No interest",
        money_per_remaining_hand=2,
        money_per_remaining_discard=1,
        has_interest=False,
        unlock_requirement="Discover 75 items",
    ),
    DeckType.BLACK: DeckDefinition(
        deck_type=DeckType.BLACK,
        name="Black Deck",
        description="+1 Joker slot, -1 hand every round",
        bonus_joker_slots=1,
        bonus_hands=-1,
        unlock_requirement="Discover 100 items",
    ),
    # Win decks
    DeckType.MAGIC: DeckDefinition(
        deck_type=DeckType.MAGIC,
        name="Magic Deck",
        description="Start with Crystal Ball voucher and 2 copies of The Fool",
        starting_vouchers=["crystal_ball"],
        starting_consumables=[("tarot", "the_fool"), ("tarot", "the_fool")],
        unlock_requirement="Win a run with Red Deck",
    ),
    DeckType.NEBULA: DeckDefinition(
        deck_type=DeckType.NEBULA,
        name="Nebula Deck",
        description="Start with Telescope voucher. -1 consumable slot",
        starting_vouchers=["telescope"],
        bonus_consumable_slots=-1,
        unlock_requirement="Win a run with Blue Deck",
    ),
    DeckType.GHOST: DeckDefinition(
        deck_type=DeckType.GHOST,
        name="Ghost Deck",
        description="Spectral cards may appear in shop. Start with Hex card",
        spectral_in_shop=True,
        starting_consumables=[("spectral", "hex")],
        unlock_requirement="Win a run with Yellow Deck",
    ),
    DeckType.ABANDONED: DeckDefinition(
        deck_type=DeckType.ABANDONED,
        name="Abandoned Deck",
        description="Start run with no Face Cards in your deck",
        no_face_cards=True,
        unlock_requirement="Win a run with Green Deck",
    ),
    DeckType.CHECKERED: DeckDefinition(
        deck_type=DeckType.CHECKERED,
        name="Checkered Deck",
        description="Start run with 26 Spades and 26 Hearts in deck",
        only_spades_hearts=True,
        unlock_requirement="Win a run with Black Deck",
    ),
    # Stake decks
    DeckType.ZODIAC: DeckDefinition(
        deck_type=DeckType.ZODIAC,
        name="Zodiac Deck",
        description="Start with Tarot Merchant, Planet Merchant, and Overstock vouchers",
        starting_vouchers=["tarot_merchant", "planet_merchant", "overstock"],
        unlock_requirement="Win a run on at least Red Stake",
    ),
    DeckType.PAINTED: DeckDefinition(
        deck_type=DeckType.PAINTED,
        name="Painted Deck",
        description="+2 hand size, -1 Joker slot",
        bonus_hand_size=2,
        bonus_joker_slots=-1,
        unlock_requirement="Win a run on at least Green Stake",
    ),
    DeckType.ANAGLYPH: DeckDefinition(
        deck_type=DeckType.ANAGLYPH,
        name="Anaglyph Deck",
        description="After defeating each Boss Blind, gain a Double Tag",
        double_tag_on_boss=True,
        unlock_requirement="Win a run on at least Black Stake",
    ),
    DeckType.PLASMA: DeckDefinition(
        deck_type=DeckType.PLASMA,
        name="Plasma Deck",
        description="Balance Chips and Mult when calculating score. X2 base Blind size",
        balance_chips_mult=True,
        blind_size_multiplier=2.0,
        unlock_requirement="Win a run on at least Blue Stake",
    ),
    DeckType.ERRATIC: DeckDefinition(
        deck_type=DeckType.ERRATIC,
        name="Erratic Deck",
        description="All Ranks and Suits in deck are randomized",
        randomize_cards=True,
        unlock_requirement="Win a run on at least Orange Stake",
    ),
}


# =============================================================================
# Deck Creation Functions
# =============================================================================


def create_standard_deck_cards() -> list[Card]:
    """Create a standard 52-card deck."""
    cards = []
    for suit in Suit:
        for rank in Rank:
            cards.append(Card(rank=rank, suit=suit))
    return cards


def create_abandoned_deck_cards() -> list[Card]:
    """Create deck without face cards (40 cards: A-10 in all suits)."""
    cards = []
    non_face_ranks = [r for r in Rank if r not in (Rank.JACK, Rank.QUEEN, Rank.KING)]
    for suit in Suit:
        for rank in non_face_ranks:
            cards.append(Card(rank=rank, suit=suit))
    return cards


def create_checkered_deck_cards() -> list[Card]:
    """Create deck with only Spades and Hearts (26 each, 52 total)."""
    cards = []
    for suit in [Suit.SPADES, Suit.HEARTS]:
        for rank in Rank:
            # Add each card twice to get 26 of each suit
            cards.append(Card(rank=rank, suit=suit))
    # We need 26 of each, but 13 ranks * 2 suits = 26 total
    # Actually the deck has 26 Spades and 26 Hearts = 52 cards
    # So we need 2 copies of each card in each suit
    additional = []
    for suit in [Suit.SPADES, Suit.HEARTS]:
        for rank in Rank:
            additional.append(Card(rank=rank, suit=suit))
    return cards + additional


def create_erratic_deck_cards(seed: int | None = None) -> list[Card]:
    """Create deck with randomized ranks and suits."""
    if seed is not None:
        random.seed(seed)

    cards = []
    all_ranks = list(Rank)
    all_suits = list(Suit)

    for _ in range(52):
        rank = random.choice(all_ranks)
        suit = random.choice(all_suits)
        cards.append(Card(rank=rank, suit=suit))

    return cards


def create_deck_cards(
    deck_type: DeckType,
    seed: int | None = None,
) -> list[Card]:
    """Create the starting cards for a specific deck type.

    Args:
        deck_type: The type of deck to create
        seed: Random seed for Erratic deck

    Returns:
        List of cards for the deck
    """
    deck_def = DECKS[deck_type]

    if deck_def.no_face_cards:
        return create_abandoned_deck_cards()
    elif deck_def.only_spades_hearts:
        return create_checkered_deck_cards()
    elif deck_def.randomize_cards:
        return create_erratic_deck_cards(seed)
    else:
        return create_standard_deck_cards()


# =============================================================================
# Deck State
# =============================================================================


@dataclass
class DeckState:
    """State for tracking deck-specific effects during a run."""

    deck_type: DeckType
    definition: DeckDefinition

    # Calculated values (base + deck modifiers)
    total_hands: int = 4  # Base 4 + deck modifier
    total_discards: int = 3  # Base 3 + deck modifier
    total_hand_size: int = 8  # Base 8 + deck modifier
    total_joker_slots: int = 5  # Base 5 + deck modifier
    total_consumable_slots: int = 2  # Base 2 + deck modifier

    # Economy
    starting_money: int = 4  # Base $4 + deck modifier

    def calculate_end_of_round_bonus(
        self,
        remaining_hands: int,
        remaining_discards: int,
    ) -> int:
        """Calculate bonus money from Green deck effect.

        Args:
            remaining_hands: Hands not used this round
            remaining_discards: Discards not used this round

        Returns:
            Bonus money earned
        """
        bonus = 0
        bonus += remaining_hands * self.definition.money_per_remaining_hand
        bonus += remaining_discards * self.definition.money_per_remaining_discard
        return bonus

    def calculate_blind_chips(self, base_chips: int) -> int:
        """Apply deck's blind size multiplier.

        Args:
            base_chips: Base chip requirement

        Returns:
            Modified chip requirement
        """
        return int(base_chips * self.definition.blind_size_multiplier)

    def apply_plasma_balance(self, chips: int, mult: int) -> tuple[int, int]:
        """Apply Plasma deck's chip/mult balancing.

        Averages chips and mult, then uses that for both.

        Args:
            chips: Current chip value
            mult: Current mult value

        Returns:
            Tuple of (balanced_chips, balanced_mult)
        """
        if not self.definition.balance_chips_mult:
            return chips, mult

        # Balance by averaging
        balanced = (chips + mult) // 2
        return balanced, balanced


def create_deck_state(deck_type: DeckType) -> DeckState:
    """Create a deck state with all modifiers applied.

    Args:
        deck_type: The type of deck

    Returns:
        DeckState with calculated values
    """
    definition = DECKS[deck_type]

    # Base values
    base_hands = 4
    base_discards = 3
    base_hand_size = 8
    base_joker_slots = 5
    base_consumable_slots = 2
    base_money = 4

    return DeckState(
        deck_type=deck_type,
        definition=definition,
        total_hands=base_hands + definition.bonus_hands,
        total_discards=base_discards + definition.bonus_discards,
        total_hand_size=base_hand_size + definition.bonus_hand_size,
        total_joker_slots=base_joker_slots + definition.bonus_joker_slots,
        total_consumable_slots=base_consumable_slots + definition.bonus_consumable_slots,
        starting_money=base_money + definition.bonus_money,
    )


# =============================================================================
# Helper Functions
# =============================================================================


def get_all_deck_types() -> list[DeckType]:
    """Get all deck types."""
    return list(DeckType)


def get_base_deck_types() -> list[DeckType]:
    """Get base deck types (Red, Blue, Yellow, Green, Black)."""
    return [
        DeckType.RED,
        DeckType.BLUE,
        DeckType.YELLOW,
        DeckType.GREEN,
        DeckType.BLACK,
    ]


def get_win_deck_types() -> list[DeckType]:
    """Get win-unlocked deck types."""
    return [
        DeckType.MAGIC,
        DeckType.NEBULA,
        DeckType.GHOST,
        DeckType.ABANDONED,
        DeckType.CHECKERED,
    ]


def get_stake_deck_types() -> list[DeckType]:
    """Get stake-unlocked deck types."""
    return [
        DeckType.ZODIAC,
        DeckType.PAINTED,
        DeckType.ANAGLYPH,
        DeckType.PLASMA,
        DeckType.ERRATIC,
    ]


def get_deck_unlock_chain() -> dict[DeckType, DeckType | None]:
    """Get the deck unlock chain (which deck unlocks which).

    Returns:
        Dict mapping deck to the deck that unlocks it (None for base decks)
    """
    return {
        DeckType.RED: None,
        DeckType.BLUE: None,
        DeckType.YELLOW: None,
        DeckType.GREEN: None,
        DeckType.BLACK: None,
        DeckType.MAGIC: DeckType.RED,
        DeckType.NEBULA: DeckType.BLUE,
        DeckType.GHOST: DeckType.YELLOW,
        DeckType.ABANDONED: DeckType.GREEN,
        DeckType.CHECKERED: DeckType.BLACK,
        # Stake decks don't have deck prerequisites
        DeckType.ZODIAC: None,
        DeckType.PAINTED: None,
        DeckType.ANAGLYPH: None,
        DeckType.PLASMA: None,
        DeckType.ERRATIC: None,
    }
