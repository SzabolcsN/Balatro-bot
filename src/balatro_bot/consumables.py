"""Consumable cards: Tarot, Planet, and Spectral cards.

Consumables are single-use cards that provide powerful effects:
- Tarot cards: Enhance/convert playing cards, create other cards
- Planet cards: Level up specific poker hand types
- Spectral cards: Powerful effects with drawbacks

Booster packs are also defined here.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from balatro_bot.models import Card, GameState


class ConsumableType(Enum):
    """Types of consumable cards."""

    TAROT = "tarot"
    PLANET = "planet"
    SPECTRAL = "spectral"


class BoosterPackType(Enum):
    """Types of booster packs."""

    ARCANA = "arcana"  # Tarot cards
    CELESTIAL = "celestial"  # Planet cards
    STANDARD = "standard"  # Playing cards
    BUFFOON = "buffoon"  # Jokers
    SPECTRAL = "spectral"  # Spectral cards


class BoosterPackSize(Enum):
    """Booster pack sizes."""

    NORMAL = "normal"
    JUMBO = "jumbo"
    MEGA = "mega"


# =============================================================================
# Consumable Effect Results
# =============================================================================


@dataclass
class ConsumableEffect:
    """Result of using a consumable card."""

    # Cards affected
    enhanced_cards: list["Card"] = field(default_factory=list)
    destroyed_cards: list["Card"] = field(default_factory=list)
    created_cards: list["Card"] = field(default_factory=list)

    # Joker effects
    created_jokers: list[str] = field(default_factory=list)  # Joker IDs
    destroyed_jokers: list[str] = field(default_factory=list)
    modified_jokers: list[tuple[str, str]] = field(
        default_factory=list
    )  # (joker_id, edition)

    # Consumable creation
    created_consumables: list[str] = field(default_factory=list)  # Consumable IDs

    # Economy
    money_gained: int = 0
    money_set_to: int | None = None  # For Wraith

    # Hand level changes
    hand_level_ups: dict[str, int] = field(default_factory=dict)  # HandType name -> levels

    # Hand size changes
    hand_size_change: int = 0

    # Message for UI
    message: str = ""


# =============================================================================
# Tarot Card Definitions (22 cards)
# =============================================================================


@dataclass
class TarotCard:
    """A Tarot card definition."""

    id: str
    name: str
    description: str
    # Number of cards that can be selected (0 = no selection needed)
    cards_to_select: int = 0
    # Min/max for variable selection
    min_select: int = 0
    max_select: int = 0


TAROT_CARDS: dict[str, TarotCard] = {
    # The Fool - creates last used Tarot/Planet
    "the_fool": TarotCard(
        id="the_fool",
        name="The Fool",
        description="Creates the last Tarot or Planet card used during this run",
        cards_to_select=0,
    ),
    # Enhancement tarots
    "the_magician": TarotCard(
        id="the_magician",
        name="The Magician",
        description="Enhances up to 2 selected cards to Lucky Cards",
        min_select=1,
        max_select=2,
    ),
    "the_empress": TarotCard(
        id="the_empress",
        name="The Empress",
        description="Enhances up to 2 selected cards to Mult Cards",
        min_select=1,
        max_select=2,
    ),
    "the_hierophant": TarotCard(
        id="the_hierophant",
        name="The Hierophant",
        description="Enhances up to 2 selected cards to Bonus Cards",
        min_select=1,
        max_select=2,
    ),
    "the_lovers": TarotCard(
        id="the_lovers",
        name="The Lovers",
        description="Enhances 1 selected card into a Wild Card",
        cards_to_select=1,
    ),
    "the_chariot": TarotCard(
        id="the_chariot",
        name="The Chariot",
        description="Enhances 1 selected card into a Steel Card",
        cards_to_select=1,
    ),
    "justice": TarotCard(
        id="justice",
        name="Justice",
        description="Enhances 1 selected card into a Glass Card",
        cards_to_select=1,
    ),
    "the_devil": TarotCard(
        id="the_devil",
        name="The Devil",
        description="Enhances 1 selected card into a Gold Card",
        cards_to_select=1,
    ),
    "the_tower": TarotCard(
        id="the_tower",
        name="The Tower",
        description="Enhances 1 selected card into a Stone Card",
        cards_to_select=1,
    ),
    # Creation tarots
    "the_high_priestess": TarotCard(
        id="the_high_priestess",
        name="The High Priestess",
        description="Creates up to 2 random Planet cards",
        cards_to_select=0,
    ),
    "the_emperor": TarotCard(
        id="the_emperor",
        name="The Emperor",
        description="Creates up to 2 random Tarot cards",
        cards_to_select=0,
    ),
    "judgement": TarotCard(
        id="judgement",
        name="Judgement",
        description="Creates a random Joker card",
        cards_to_select=0,
    ),
    # Economy tarots
    "the_hermit": TarotCard(
        id="the_hermit",
        name="The Hermit",
        description="Doubles money (Max of $20)",
        cards_to_select=0,
    ),
    "temperance": TarotCard(
        id="temperance",
        name="Temperance",
        description="Gives the total sell value of all current Jokers (Max of $50)",
        cards_to_select=0,
    ),
    # Joker modifier
    "wheel_of_fortune": TarotCard(
        id="wheel_of_fortune",
        name="The Wheel of Fortune",
        description="1 in 4 chance to add Foil, Holographic, or Polychrome to a random Joker",
        cards_to_select=0,
    ),
    # Card manipulation
    "strength": TarotCard(
        id="strength",
        name="Strength",
        description="Increases rank of up to 2 selected cards by 1",
        min_select=1,
        max_select=2,
    ),
    "the_hanged_man": TarotCard(
        id="the_hanged_man",
        name="The Hanged Man",
        description="Destroys up to 2 selected cards",
        min_select=1,
        max_select=2,
    ),
    "death": TarotCard(
        id="death",
        name="Death",
        description="Select 2 cards, convert the left card into the right card",
        cards_to_select=2,
    ),
    # Suit conversion tarots
    "the_star": TarotCard(
        id="the_star",
        name="The Star",
        description="Converts up to 3 selected cards to Diamonds",
        min_select=1,
        max_select=3,
    ),
    "the_moon": TarotCard(
        id="the_moon",
        name="The Moon",
        description="Converts up to 3 selected cards to Clubs",
        min_select=1,
        max_select=3,
    ),
    "the_sun": TarotCard(
        id="the_sun",
        name="The Sun",
        description="Converts up to 3 selected cards to Hearts",
        min_select=1,
        max_select=3,
    ),
    "the_world": TarotCard(
        id="the_world",
        name="The World",
        description="Converts up to 3 selected cards to Spades",
        min_select=1,
        max_select=3,
    ),
}


# =============================================================================
# Planet Card Definitions (12 cards)
# =============================================================================


@dataclass
class PlanetCard:
    """A Planet card that levels up a hand type."""

    id: str
    name: str
    hand_type: str  # HandType name
    description: str
    is_secret: bool = False  # Secret planets only appear after playing the hand


PLANET_CARDS: dict[str, PlanetCard] = {
    "pluto": PlanetCard(
        id="pluto",
        name="Pluto",
        hand_type="HIGH_CARD",
        description="Level up High Card",
    ),
    "mercury": PlanetCard(
        id="mercury",
        name="Mercury",
        hand_type="PAIR",
        description="Level up Pair",
    ),
    "uranus": PlanetCard(
        id="uranus",
        name="Uranus",
        hand_type="TWO_PAIR",
        description="Level up Two Pair",
    ),
    "venus": PlanetCard(
        id="venus",
        name="Venus",
        hand_type="THREE_OF_A_KIND",
        description="Level up Three of a Kind",
    ),
    "saturn": PlanetCard(
        id="saturn",
        name="Saturn",
        hand_type="STRAIGHT",
        description="Level up Straight",
    ),
    "jupiter": PlanetCard(
        id="jupiter",
        name="Jupiter",
        hand_type="FLUSH",
        description="Level up Flush",
    ),
    "earth": PlanetCard(
        id="earth",
        name="Earth",
        hand_type="FULL_HOUSE",
        description="Level up Full House",
    ),
    "mars": PlanetCard(
        id="mars",
        name="Mars",
        hand_type="FOUR_OF_A_KIND",
        description="Level up Four of a Kind",
    ),
    "neptune": PlanetCard(
        id="neptune",
        name="Neptune",
        hand_type="STRAIGHT_FLUSH",
        description="Level up Straight Flush",
    ),
    # Secret planets (require playing the hand first)
    "planet_x": PlanetCard(
        id="planet_x",
        name="Planet X",
        hand_type="FIVE_OF_A_KIND",
        description="Level up Five of a Kind",
        is_secret=True,
    ),
    "ceres": PlanetCard(
        id="ceres",
        name="Ceres",
        hand_type="FLUSH_HOUSE",
        description="Level up Flush House",
        is_secret=True,
    ),
    "eris": PlanetCard(
        id="eris",
        name="Eris",
        hand_type="FLUSH_FIVE",
        description="Level up Flush Five",
        is_secret=True,
    ),
}

# Mapping from HandType to planet card ID
HAND_TYPE_TO_PLANET: dict[str, str] = {
    planet.hand_type: planet_id for planet_id, planet in PLANET_CARDS.items()
}


# =============================================================================
# Spectral Card Definitions (18 cards)
# =============================================================================


@dataclass
class SpectralCard:
    """A Spectral card with powerful effects."""

    id: str
    name: str
    description: str
    cards_to_select: int = 0
    has_drawback: bool = False  # Has negative side effect


SPECTRAL_CARDS: dict[str, SpectralCard] = {
    # Card creation spectrals (destroy 1 random card, add enhanced cards)
    "familiar": SpectralCard(
        id="familiar",
        name="Familiar",
        description="Destroy 1 random card in hand, add 3 random Enhanced face cards",
        has_drawback=True,
    ),
    "grim": SpectralCard(
        id="grim",
        name="Grim",
        description="Destroy 1 random card in hand, add 2 random Enhanced Aces",
        has_drawback=True,
    ),
    "incantation": SpectralCard(
        id="incantation",
        name="Incantation",
        description="Destroy 1 random card in hand, add 4 random Enhanced numbered cards",
        has_drawback=True,
    ),
    # Seal addition spectrals
    "talisman": SpectralCard(
        id="talisman",
        name="Talisman",
        description="Add a Gold Seal to 1 selected card",
        cards_to_select=1,
    ),
    "deja_vu": SpectralCard(
        id="deja_vu",
        name="Deja Vu",
        description="Add a Red Seal to 1 selected card",
        cards_to_select=1,
    ),
    "trance": SpectralCard(
        id="trance",
        name="Trance",
        description="Add a Blue Seal to 1 selected card",
        cards_to_select=1,
    ),
    "medium": SpectralCard(
        id="medium",
        name="Medium",
        description="Add a Purple Seal to 1 selected card",
        cards_to_select=1,
    ),
    # Edition spectrals
    "aura": SpectralCard(
        id="aura",
        name="Aura",
        description="Add Foil, Holographic, or Polychrome to 1 selected card",
        cards_to_select=1,
    ),
    # Joker spectrals
    "wraith": SpectralCard(
        id="wraith",
        name="Wraith",
        description="Creates a random Rare Joker, sets money to $0",
        has_drawback=True,
    ),
    "ectoplasm": SpectralCard(
        id="ectoplasm",
        name="Ectoplasm",
        description="Add Negative to a random Joker, -1 hand size",
        has_drawback=True,
    ),
    "ankh": SpectralCard(
        id="ankh",
        name="Ankh",
        description="Create a copy of a random Joker, destroy all other Jokers",
        has_drawback=True,
    ),
    "hex": SpectralCard(
        id="hex",
        name="Hex",
        description="Add Polychrome to a random Joker, destroy all other Jokers",
        has_drawback=True,
    ),
    "the_soul": SpectralCard(
        id="the_soul",
        name="The Soul",
        description="Creates a Legendary Joker",
    ),
    # Hand conversion spectrals
    "sigil": SpectralCard(
        id="sigil",
        name="Sigil",
        description="Converts all cards in hand to a single random suit",
    ),
    "ouija": SpectralCard(
        id="ouija",
        name="Ouija",
        description="Converts all cards in hand to a single random rank, -1 hand size",
        has_drawback=True,
    ),
    # Economy spectral
    "immolate": SpectralCard(
        id="immolate",
        name="Immolate",
        description="Destroys 5 random cards in hand, gain $20",
        has_drawback=True,
    ),
    # Card duplication
    "cryptid": SpectralCard(
        id="cryptid",
        name="Cryptid",
        description="Create 2 copies of 1 selected card",
        cards_to_select=1,
    ),
    # Universal level up
    "black_hole": SpectralCard(
        id="black_hole",
        name="Black Hole",
        description="Upgrade every poker hand by 1 level",
    ),
}


# =============================================================================
# Booster Pack Definitions
# =============================================================================


@dataclass
class BoosterPack:
    """A booster pack configuration."""

    pack_type: BoosterPackType
    size: BoosterPackSize
    cost: int
    cards_shown: int
    cards_to_choose: int

    @property
    def id(self) -> str:
        return f"{self.pack_type.value}_{self.size.value}"

    @property
    def name(self) -> str:
        size_names = {
            BoosterPackSize.NORMAL: "",
            BoosterPackSize.JUMBO: "Jumbo ",
            BoosterPackSize.MEGA: "Mega ",
        }
        type_names = {
            BoosterPackType.ARCANA: "Arcana Pack",
            BoosterPackType.CELESTIAL: "Celestial Pack",
            BoosterPackType.STANDARD: "Standard Pack",
            BoosterPackType.BUFFOON: "Buffoon Pack",
            BoosterPackType.SPECTRAL: "Spectral Pack",
        }
        return f"{size_names[self.size]}{type_names[self.pack_type]}"


# All booster pack configurations
BOOSTER_PACKS: dict[str, BoosterPack] = {
    # Arcana packs (Tarot cards)
    "arcana_normal": BoosterPack(
        BoosterPackType.ARCANA, BoosterPackSize.NORMAL, cost=4, cards_shown=3, cards_to_choose=1
    ),
    "arcana_jumbo": BoosterPack(
        BoosterPackType.ARCANA, BoosterPackSize.JUMBO, cost=6, cards_shown=5, cards_to_choose=1
    ),
    "arcana_mega": BoosterPack(
        BoosterPackType.ARCANA, BoosterPackSize.MEGA, cost=8, cards_shown=5, cards_to_choose=2
    ),
    # Celestial packs (Planet cards)
    "celestial_normal": BoosterPack(
        BoosterPackType.CELESTIAL, BoosterPackSize.NORMAL, cost=4, cards_shown=3, cards_to_choose=1
    ),
    "celestial_jumbo": BoosterPack(
        BoosterPackType.CELESTIAL, BoosterPackSize.JUMBO, cost=6, cards_shown=5, cards_to_choose=1
    ),
    "celestial_mega": BoosterPack(
        BoosterPackType.CELESTIAL, BoosterPackSize.MEGA, cost=8, cards_shown=5, cards_to_choose=2
    ),
    # Standard packs (Playing cards)
    "standard_normal": BoosterPack(
        BoosterPackType.STANDARD, BoosterPackSize.NORMAL, cost=4, cards_shown=3, cards_to_choose=1
    ),
    "standard_jumbo": BoosterPack(
        BoosterPackType.STANDARD, BoosterPackSize.JUMBO, cost=6, cards_shown=5, cards_to_choose=1
    ),
    "standard_mega": BoosterPack(
        BoosterPackType.STANDARD, BoosterPackSize.MEGA, cost=8, cards_shown=5, cards_to_choose=2
    ),
    # Buffoon packs (Jokers)
    "buffoon_normal": BoosterPack(
        BoosterPackType.BUFFOON, BoosterPackSize.NORMAL, cost=4, cards_shown=2, cards_to_choose=1
    ),
    "buffoon_jumbo": BoosterPack(
        BoosterPackType.BUFFOON, BoosterPackSize.JUMBO, cost=6, cards_shown=4, cards_to_choose=1
    ),
    "buffoon_mega": BoosterPack(
        BoosterPackType.BUFFOON, BoosterPackSize.MEGA, cost=8, cards_shown=4, cards_to_choose=2
    ),
    # Spectral packs
    "spectral_normal": BoosterPack(
        BoosterPackType.SPECTRAL, BoosterPackSize.NORMAL, cost=4, cards_shown=2, cards_to_choose=1
    ),
    "spectral_jumbo": BoosterPack(
        BoosterPackType.SPECTRAL, BoosterPackSize.JUMBO, cost=6, cards_shown=4, cards_to_choose=1
    ),
    "spectral_mega": BoosterPack(
        BoosterPackType.SPECTRAL, BoosterPackSize.MEGA, cost=8, cards_shown=4, cards_to_choose=2
    ),
}


# =============================================================================
# Consumable Instance (for game state)
# =============================================================================


@dataclass
class ConsumableInstance:
    """An instance of a consumable card in the game."""

    consumable_type: ConsumableType
    card_id: str

    @property
    def definition(self) -> TarotCard | PlanetCard | SpectralCard:
        """Get the card definition."""
        if self.consumable_type == ConsumableType.TAROT:
            return TAROT_CARDS[self.card_id]
        elif self.consumable_type == ConsumableType.PLANET:
            return PLANET_CARDS[self.card_id]
        else:
            return SPECTRAL_CARDS[self.card_id]

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def description(self) -> str:
        return self.definition.description


def create_consumable(consumable_type: ConsumableType, card_id: str) -> ConsumableInstance:
    """Create a consumable instance."""
    # Validate the card exists
    if consumable_type == ConsumableType.TAROT:
        if card_id not in TAROT_CARDS:
            raise ValueError(f"Unknown tarot card: {card_id}")
    elif consumable_type == ConsumableType.PLANET:
        if card_id not in PLANET_CARDS:
            raise ValueError(f"Unknown planet card: {card_id}")
    elif consumable_type == ConsumableType.SPECTRAL:
        if card_id not in SPECTRAL_CARDS:
            raise ValueError(f"Unknown spectral card: {card_id}")

    return ConsumableInstance(consumable_type, card_id)


# =============================================================================
# Helper Functions
# =============================================================================


def get_all_tarot_ids() -> list[str]:
    """Get all tarot card IDs."""
    return list(TAROT_CARDS.keys())


def get_all_planet_ids() -> list[str]:
    """Get all planet card IDs."""
    return list(PLANET_CARDS.keys())


def get_all_standard_planet_ids() -> list[str]:
    """Get non-secret planet card IDs."""
    return [pid for pid, p in PLANET_CARDS.items() if not p.is_secret]


def get_all_spectral_ids() -> list[str]:
    """Get all spectral card IDs."""
    return list(SPECTRAL_CARDS.keys())


def get_all_booster_pack_ids() -> list[str]:
    """Get all booster pack IDs."""
    return list(BOOSTER_PACKS.keys())


def get_planet_for_hand_type(hand_type_name: str) -> str | None:
    """Get the planet card ID for a hand type."""
    return HAND_TYPE_TO_PLANET.get(hand_type_name)
