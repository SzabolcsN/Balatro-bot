"""Joker definitions and effect system.

CRITICAL: Joker order matters for effect resolution. Effects are applied
in the order jokers appear in the player's joker slots.

Effect types:
- add_chips: Flat chip bonus
- add_mult: Flat multiplier bonus
- mult_mult: Multiplicative multiplier (×mult) - order-sensitive!
- trigger: Conditional effects based on hand/cards

Economy effects are calculated separately via EconomyContext:
- END_OF_ROUND: Golden Joker, Rocket, Cloud 9, etc.
- ON_DISCARD: Trading Card, Faceless Joker, etc.
- Conditional: To Do List, Matador, etc.

All 150 Balatro jokers are defined here.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Protocol
import random

if TYPE_CHECKING:
    from balatro_bot.scoring import ScoringContext


class EffectTiming(Enum):
    """When a joker effect triggers during scoring."""

    ON_SCORE = auto()  # During main scoring phase
    ON_CARD_SCORE = auto()  # For each scoring card
    ON_HAND_PLAYED = auto()  # When specific hand types are played
    ON_DISCARD = auto()  # When cards are discarded
    END_OF_ROUND = auto()  # After blind is beaten
    ON_SHOP = auto()  # In shop phase
    ON_BLIND_SELECT = auto()  # When blind is selected


class JokerRarity(Enum):
    """Joker rarity tiers."""

    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    LEGENDARY = "legendary"


@dataclass
class JokerEffect:
    """Result of a joker's effect calculation."""

    add_chips: int = 0
    add_mult: int = 0
    mult_mult: float = 1.0  # Multiplicative (×mult), 1.0 = no change
    retrigger: int = 0  # Number of extra triggers for scoring cards
    money: int = 0  # Money earned

    def __bool__(self) -> bool:
        """True if this effect does anything."""
        return (
            self.add_chips != 0
            or self.add_mult != 0
            or self.mult_mult != 1.0
            or self.retrigger > 0
            or self.money != 0
        )


@dataclass
class EconomyContext:
    """Context for economy-related joker effects.

    Used for effects that happen outside of scoring:
    - End of round money generation
    - Discard-triggered effects
    - Shop-related effects
    """

    # Current game state
    money: int = 0
    ante: int = 1
    boss_blinds_defeated: int = 0
    blinds_skipped: int = 0

    # Round state
    hands_played: int = 0
    hands_remaining: int = 4
    discards_used: int = 0
    discards_remaining: int = 3

    # Deck information
    deck_size: int = 52
    nines_in_deck: int = 4  # For Cloud 9

    # Cards being discarded (for ON_DISCARD effects)
    discarded_cards: list = field(default_factory=list)

    # Target poker hand for To Do List
    target_hand_type: str | None = None
    played_hand_type: str | None = None

    # Boss blind interaction
    boss_blind_triggered: bool = False  # For Matador

    # Planet cards used (for Satellite)
    unique_planets_used: int = 0

    # Joker state (for Egg sell value tracking)
    joker_sell_values: dict = field(default_factory=dict)

    # Interest calculation
    interest_rate: float = 0.20
    interest_cap: int = 5


@dataclass
class EconomyEffect:
    """Result of an economy joker's effect."""

    money: int = 0
    sell_value_change: int = 0  # For Egg, Gift Card
    interest_bonus: int = 0  # For To the Moon
    debt_limit: int = 0  # For Credit Card

    def __bool__(self) -> bool:
        """True if this effect does anything."""
        return (
            self.money != 0
            or self.sell_value_change != 0
            or self.interest_bonus != 0
            or self.debt_limit != 0
        )


class JokerBehavior(Protocol):
    """Protocol for joker behavior implementations."""

    def calculate_effect(self, ctx: "ScoringContext") -> JokerEffect:
        """Calculate this joker's effect given the current scoring context."""
        ...


@dataclass
class JokerDefinition:
    """Static definition of a joker type."""

    id: str
    name: str
    description: str
    rarity: JokerRarity
    base_cost: int
    timing: EffectTiming = EffectTiming.ON_SCORE

    def create_instance(self) -> "JokerInstance":
        """Create a new instance of this joker."""
        return JokerInstance(definition=self)


@dataclass
class JokerInstance:
    """A specific joker instance with its current state.

    Jokers can have mutable state (e.g., Hologram's level,
    Ice Cream's remaining chips).
    """

    definition: JokerDefinition
    state: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.definition.id

    @property
    def name(self) -> str:
        return self.definition.name

    def calculate_effect(self, ctx: "ScoringContext") -> JokerEffect:
        """Calculate effect based on joker type and context."""
        # Dispatch to specific joker logic
        calculator = JOKER_CALCULATORS.get(self.id)
        if calculator:
            return calculator(self, ctx)
        return JokerEffect()

    def calculate_economy_effect(
        self,
        ctx: EconomyContext,
        timing: EffectTiming,
    ) -> EconomyEffect:
        """Calculate economy effect based on timing.

        Args:
            ctx: Economy context with current game state
            timing: When this effect is being calculated

        Returns:
            EconomyEffect with money/value changes
        """
        calculator = ECONOMY_CALCULATORS.get((self.id, timing))
        if calculator:
            return calculator(self, ctx)
        return EconomyEffect()


# =============================================================================
# Helper Functions
# =============================================================================


def _is_face_card(rank_value: int) -> bool:
    """Check if rank is a face card (J, Q, K)."""
    return rank_value in (11, 12, 13)


def _is_even_rank(rank_value: int) -> bool:
    """Check if rank is even (10, 8, 6, 4, 2)."""
    return rank_value in (10, 8, 6, 4, 2)


def _is_odd_rank(rank_value: int) -> bool:
    """Check if rank is odd (A, 9, 7, 5, 3)."""
    return rank_value in (14, 9, 7, 5, 3)


def _is_fibonacci_rank(rank_value: int) -> bool:
    """Check if rank is a Fibonacci number (A, 2, 3, 5, 8)."""
    return rank_value in (14, 2, 3, 5, 8)


# =============================================================================
# Joker Effect Calculators - Simple +Mult
# =============================================================================


def _joker_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Joker (#1): +4 Mult"""
    return JokerEffect(add_mult=4)


def _greedy_joker_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Greedy Joker (#2): +3 Mult for each played Diamond"""
    diamond_count = sum(1 for c in ctx.scoring_cards if c.suit.value == "D")
    return JokerEffect(add_mult=3 * diamond_count)


def _lusty_joker_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Lusty Joker (#3): +3 Mult for each played Heart"""
    heart_count = sum(1 for c in ctx.scoring_cards if c.suit.value == "H")
    return JokerEffect(add_mult=3 * heart_count)


def _wrathful_joker_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Wrathful Joker (#4): +3 Mult for each played Spade"""
    spade_count = sum(1 for c in ctx.scoring_cards if c.suit.value == "S")
    return JokerEffect(add_mult=3 * spade_count)


def _gluttonous_joker_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Gluttonous Joker (#5): +3 Mult for each played Club"""
    club_count = sum(1 for c in ctx.scoring_cards if c.suit.value == "C")
    return JokerEffect(add_mult=3 * club_count)


def _jolly_joker_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Jolly Joker (#6): +8 Mult if hand contains a Pair"""
    from collections import Counter
    ranks = Counter(c.rank for c in ctx.scoring_cards)
    if any(count >= 2 for count in ranks.values()):
        return JokerEffect(add_mult=8)
    return JokerEffect()


def _zany_joker_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Zany Joker (#7): +12 Mult if hand contains a Three of a Kind"""
    from collections import Counter
    ranks = Counter(c.rank for c in ctx.scoring_cards)
    if any(count >= 3 for count in ranks.values()):
        return JokerEffect(add_mult=12)
    return JokerEffect()


def _mad_joker_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Mad Joker (#8): +10 Mult if hand contains a Two Pair"""
    from balatro_bot.models import HandType
    if ctx.hand_result.hand_type == HandType.TWO_PAIR:
        return JokerEffect(add_mult=10)
    return JokerEffect()


def _crazy_joker_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Crazy Joker (#9): +12 Mult if hand contains a Straight"""
    from balatro_bot.models import HandType
    if ctx.hand_result.hand_type in (
        HandType.STRAIGHT, HandType.STRAIGHT_FLUSH, HandType.ROYAL_FLUSH,
    ):
        return JokerEffect(add_mult=12)
    return JokerEffect()


def _droll_joker_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Droll Joker (#10): +10 Mult if hand contains a Flush"""
    from balatro_bot.models import HandType
    if ctx.hand_result.hand_type in (
        HandType.FLUSH, HandType.STRAIGHT_FLUSH, HandType.ROYAL_FLUSH, HandType.FLUSH_HOUSE,
        HandType.FLUSH_FIVE,
    ):
        return JokerEffect(add_mult=10)
    return JokerEffect()


def _half_joker_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Half Joker (#16): +20 Mult if hand contains 3 or fewer cards"""
    if len(ctx.played_cards) <= 3:
        return JokerEffect(add_mult=20)
    return JokerEffect()


def _banner_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Banner (#22): +30 Chips for each discard remaining"""
    return JokerEffect(add_chips=30 * ctx.game_state.discards_remaining)


def _mystic_summit_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Mystic Summit (#23): +15 Mult when 0 discards remaining"""
    if ctx.game_state.discards_remaining == 0:
        return JokerEffect(add_mult=15)
    return JokerEffect()


def _misprint_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Misprint (#27): +0-23 Mult (random)"""
    return JokerEffect(add_mult=random.randint(0, 23))


def _raised_fist_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Raised Fist (#29): Adds double the rank of lowest card held in hand to Mult"""
    if ctx.cards_in_hand:
        lowest = min(ctx.cards_in_hand, key=lambda c: c.rank.value)
        return JokerEffect(add_mult=2 * lowest.rank.value)
    return JokerEffect()


def _fibonacci_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Fibonacci (#31): Each played A, 2, 3, 5, or 8 gives +8 Mult when scored"""
    fib_count = sum(1 for c in ctx.scoring_cards if _is_fibonacci_rank(c.rank.value))
    return JokerEffect(add_mult=8 * fib_count)


def _abstract_joker_effect(joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Abstract Joker (#34): +3 Mult for each Joker card"""
    joker_count = joker.state.get("joker_count", 1)
    return JokerEffect(add_mult=3 * joker_count)


def _gros_michel_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Gros Michel (#38): +15 Mult"""
    return JokerEffect(add_mult=15)


def _even_steven_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Even Steven (#39): Played cards with even rank give +4 Mult when scored"""
    even_count = sum(1 for c in ctx.scoring_cards if _is_even_rank(c.rank.value))
    return JokerEffect(add_mult=4 * even_count)


def _scholar_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Scholar (#41): Played Aces give +20 Chips and +4 Mult when scored"""
    ace_count = sum(1 for c in ctx.scoring_cards if c.rank.value == 14)
    return JokerEffect(add_chips=20 * ace_count, add_mult=4 * ace_count)


def _supernova_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Supernova (#43): Adds number of times poker hand has been played to Mult"""
    times_played = joker.state.get("times_played", 0)
    return JokerEffect(add_mult=times_played)


def _erosion_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Erosion (#81): +4 Mult for each card below starting deck size"""
    cards_below = joker.state.get("cards_below", 0)
    return JokerEffect(add_mult=4 * cards_below)


def _fortune_teller_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Fortune Teller (#86): +1 Mult per Tarot card used this run"""
    tarots_used = joker.state.get("tarots_used", 0)
    return JokerEffect(add_mult=tarots_used)


def _popcorn_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Popcorn (#97): +20 Mult, -4 Mult per round played"""
    mult = joker.state.get("mult", 20)
    return JokerEffect(add_mult=max(0, mult))


def _smiley_face_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Smiley Face (#104): Played face cards give +5 Mult when scored"""
    face_count = sum(1 for c in ctx.scoring_cards if _is_face_card(c.rank.value))
    return JokerEffect(add_mult=5 * face_count)


def _swashbuckler_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Swashbuckler (#110): Adds sell value of all other Jokers to Mult"""
    sell_value = joker.state.get("sell_value", 1)
    return JokerEffect(add_mult=sell_value)


def _shoot_the_moon_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Shoot the Moon (#140): Each Queen held in hand gives +13 Mult"""
    queen_count = sum(1 for c in ctx.cards_in_hand if c.rank.value == 12)
    return JokerEffect(add_mult=13 * queen_count)


def _bootstraps_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Bootstraps (#145): +2 Mult for every $5 you have"""
    money = joker.state.get("money", 0)
    return JokerEffect(add_mult=2 * (money // 5))


def _onyx_agate_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Onyx Agate (#119): Played cards with Club suit give +7 Mult when scored"""
    club_count = sum(1 for c in ctx.scoring_cards if c.suit.value == "C")
    return JokerEffect(add_mult=7 * club_count)


def _walkie_talkie_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Walkie Talkie (#101): Each played 10 or 4 gives +10 Chips and +4 Mult"""
    count = sum(1 for c in ctx.scoring_cards if c.rank.value in (10, 4))
    return JokerEffect(add_chips=10 * count, add_mult=4 * count)


# =============================================================================
# Joker Effect Calculators - Simple +Chips
# =============================================================================


def _sly_joker_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Sly Joker (#11): +50 Chips if hand contains a Pair"""
    from collections import Counter
    ranks = Counter(c.rank for c in ctx.scoring_cards)
    if any(count >= 2 for count in ranks.values()):
        return JokerEffect(add_chips=50)
    return JokerEffect()


def _wily_joker_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Wily Joker (#12): +100 Chips if hand contains a Three of a Kind"""
    from collections import Counter
    ranks = Counter(c.rank for c in ctx.scoring_cards)
    if any(count >= 3 for count in ranks.values()):
        return JokerEffect(add_chips=100)
    return JokerEffect()


def _clever_joker_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Clever Joker (#13): +80 Chips if hand contains a Two Pair"""
    from balatro_bot.models import HandType
    if ctx.hand_result.hand_type == HandType.TWO_PAIR:
        return JokerEffect(add_chips=80)
    return JokerEffect()


def _devious_joker_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Devious Joker (#14): +100 Chips if hand contains a Straight"""
    from balatro_bot.models import HandType
    if ctx.hand_result.hand_type in (
        HandType.STRAIGHT, HandType.STRAIGHT_FLUSH, HandType.ROYAL_FLUSH,
    ):
        return JokerEffect(add_chips=100)
    return JokerEffect()


def _crafty_joker_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Crafty Joker (#15): +80 Chips if hand contains a Flush"""
    from balatro_bot.models import HandType
    if ctx.hand_result.hand_type in (
        HandType.FLUSH, HandType.STRAIGHT_FLUSH, HandType.ROYAL_FLUSH,
        HandType.FLUSH_HOUSE, HandType.FLUSH_FIVE,
    ):
        return JokerEffect(add_chips=80)
    return JokerEffect()


def _scary_face_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Scary Face (#33): Played face cards give +30 Chips when scored"""
    face_count = sum(1 for c in ctx.scoring_cards if _is_face_card(c.rank.value))
    return JokerEffect(add_chips=30 * face_count)


def _odd_todd_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Odd Todd (#40): Played cards with odd rank give +31 Chips when scored"""
    odd_count = sum(1 for c in ctx.scoring_cards if _is_odd_rank(c.rank.value))
    return JokerEffect(add_chips=31 * odd_count)


def _blue_joker_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Blue Joker (#53): +2 Chips for each remaining card in deck"""
    deck_size = joker.state.get("deck_remaining", 52)
    return JokerEffect(add_chips=2 * deck_size)


def _stone_joker_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Stone Joker (#89): +25 Chips for each Stone Card in full deck"""
    stone_count = joker.state.get("stone_cards", 0)
    return JokerEffect(add_chips=25 * stone_count)


def _bull_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Bull (#93): +2 Chips for each $1 you have"""
    money = joker.state.get("money", 0)
    return JokerEffect(add_chips=2 * money)


def _arrowhead_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Arrowhead (#118): Played cards with Spade suit give +50 Chips when scored"""
    spade_count = sum(1 for c in ctx.scoring_cards if c.suit.value == "S")
    return JokerEffect(add_chips=50 * spade_count)


def _stuntman_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Stuntman (#136): +250 Chips, -2 hand size"""
    return JokerEffect(add_chips=250)


# =============================================================================
# Joker Effect Calculators - Scaling (state-dependent)
# =============================================================================


def _ice_cream_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Ice Cream (#50): +100 Chips, -5 Chips for every hand played"""
    chips = joker.state.get("chips", 100)
    return JokerEffect(add_chips=chips)


def _runner_effect(joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Runner (#49): Gains +15 Chips if played hand contains a Straight"""
    from balatro_bot.models import HandType
    chips = joker.state.get("chips", 0)
    if ctx.hand_result.hand_type in (
        HandType.STRAIGHT, HandType.STRAIGHT_FLUSH, HandType.ROYAL_FLUSH,
    ):
        joker.state["chips"] = chips + 15
    return JokerEffect(add_chips=joker.state.get("chips", 0))


def _square_joker_effect(joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Square Joker (#65): Gains +4 Chips if played hand has exactly 4 cards"""
    chips = joker.state.get("chips", 0)
    if len(ctx.played_cards) == 4:
        joker.state["chips"] = chips + 4
    return JokerEffect(add_chips=joker.state.get("chips", 0))


def _castle_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Castle (#103): Gains +3 Chips per discarded card of specific suit"""
    chips = joker.state.get("chips", 0)
    return JokerEffect(add_chips=chips)


def _wee_joker_effect(joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Wee Joker (#124): Gains +8 Chips when each played 2 is scored"""
    chips = joker.state.get("chips", 0)
    twos = sum(1 for c in ctx.scoring_cards if c.rank.value == 2)
    if twos > 0:
        joker.state["chips"] = chips + (8 * twos)
    return JokerEffect(add_chips=joker.state.get("chips", 0))


def _ride_the_bus_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Ride the Bus (#44): +1 Mult per consecutive hand without face card"""
    mult = joker.state.get("mult", 0)
    return JokerEffect(add_mult=mult)


def _green_joker_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Green Joker (#58): +1 Mult per hand played, -1 per discard (min 0)"""
    mult = joker.state.get("mult", 0)
    return JokerEffect(add_mult=mult)


def _red_card_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Red Card (#63): Gains +3 Mult when any Booster Pack is skipped"""
    mult = joker.state.get("mult", 0)
    return JokerEffect(add_mult=mult)


def _flash_card_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Flash Card (#96): Gains +2 Mult per reroll in the shop"""
    mult = joker.state.get("mult", 0)
    return JokerEffect(add_mult=mult)


def _spare_trousers_effect(joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Spare Trousers (#98): Gains +2 Mult if played hand contains a Two Pair"""
    from balatro_bot.models import HandType
    mult = joker.state.get("mult", 0)
    if ctx.hand_result.hand_type == HandType.TWO_PAIR:
        joker.state["mult"] = mult + 2
    return JokerEffect(add_mult=joker.state.get("mult", 0))


# =============================================================================
# Joker Effect Calculators - X Mult (Multiplicative)
# =============================================================================


def _blackboard_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Blackboard (#48): ×3 Mult if all cards held in hand are Spades or Clubs"""
    if ctx.cards_in_hand and all(c.suit.value in ("S", "C") for c in ctx.cards_in_hand):
        return JokerEffect(mult_mult=3.0)
    return JokerEffect()


def _joker_stencil_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Joker Stencil (#17): X1 Mult for each empty Joker slot"""
    empty_slots = joker.state.get("empty_slots", 0)
    if empty_slots > 0:
        return JokerEffect(mult_mult=float(empty_slots))
    return JokerEffect()


def _loyalty_card_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Loyalty Card (#25): X4 Mult every 6 hands played"""
    hands_until = joker.state.get("hands_until", 5)
    if hands_until == 0:
        return JokerEffect(mult_mult=4.0)
    return JokerEffect()


def _steel_joker_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Steel Joker (#32): X0.2 Mult for each Steel Card in full deck"""
    steel_count = joker.state.get("steel_cards", 0)
    if steel_count > 0:
        return JokerEffect(mult_mult=1.0 + (0.2 * steel_count))
    return JokerEffect()


def _constellation_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Constellation (#55): Gains X0.1 Mult every time a Planet card is used"""
    mult = joker.state.get("mult", 1.0)
    if mult > 1.0:
        return JokerEffect(mult_mult=mult)
    return JokerEffect()


def _cavendish_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Cavendish (#61): X3 Mult"""
    return JokerEffect(mult_mult=3.0)


def _card_sharp_effect(joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Card Sharp (#62): X3 Mult if played poker hand was already played this round"""
    hands_played = joker.state.get("hands_this_round", [])
    current_hand = ctx.hand_result.hand_type
    if current_hand in hands_played:
        return JokerEffect(mult_mult=3.0)
    return JokerEffect()


def _madness_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Madness (#64): Gains X0.5 Mult when Small/Big Blind selected, destroys joker"""
    mult = joker.state.get("mult", 1.0)
    if mult > 1.0:
        return JokerEffect(mult_mult=mult)
    return JokerEffect()


def _hologram_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Hologram (#70): Gains X0.25 Mult every time a card is added to deck"""
    mult = joker.state.get("mult", 1.0)
    if mult > 1.0:
        return JokerEffect(mult_mult=mult)
    return JokerEffect()


def _vampire_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Vampire (#68): Gains X0.1 Mult per scoring Enhanced card played"""
    mult = joker.state.get("mult", 1.0)
    if mult > 1.0:
        return JokerEffect(mult_mult=mult)
    return JokerEffect()


def _obelisk_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Obelisk (#75): Gains X0.2 Mult per consecutive hand without most played hand"""
    mult = joker.state.get("mult", 1.0)
    if mult > 1.0:
        return JokerEffect(mult_mult=mult)
    return JokerEffect()


def _photograph_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Photograph (#78): First played face card gives X2 Mult when scored"""
    has_face = any(_is_face_card(c.rank.value) for c in ctx.scoring_cards)
    if has_face:
        return JokerEffect(mult_mult=2.0)
    return JokerEffect()


def _lucky_cat_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Lucky Cat (#91): Gains X0.25 Mult every time a Lucky card triggers"""
    mult = joker.state.get("mult", 1.0)
    if mult > 1.0:
        return JokerEffect(mult_mult=mult)
    return JokerEffect()


def _baseball_card_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Baseball Card (#92): Uncommon Jokers each give X1.5 Mult"""
    uncommon_count = joker.state.get("uncommon_jokers", 0)
    if uncommon_count > 0:
        return JokerEffect(mult_mult=1.5 ** uncommon_count)
    return JokerEffect()


def _ancient_joker_effect(joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Ancient Joker (#99): Each played card with specific suit gives X1.5 Mult"""
    target_suit = joker.state.get("suit", "S")
    count = sum(1 for c in ctx.scoring_cards if c.suit.value == target_suit)
    if count > 0:
        return JokerEffect(mult_mult=1.5 ** count)
    return JokerEffect()


def _ramen_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Ramen (#100): X2 Mult, loses X0.01 Mult per card discarded"""
    mult = joker.state.get("mult", 2.0)
    if mult > 1.0:
        return JokerEffect(mult_mult=mult)
    return JokerEffect()


def _acrobat_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Acrobat (#108): X3 Mult on final hand of round"""
    is_final_hand = joker.state.get("is_final_hand", False)
    if is_final_hand:
        return JokerEffect(mult_mult=3.0)
    return JokerEffect()


def _campfire_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Campfire (#105): Gains X0.25 Mult for each card sold"""
    mult = joker.state.get("mult", 1.0)
    if mult > 1.0:
        return JokerEffect(mult_mult=mult)
    return JokerEffect()


def _throwback_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Throwback (#114): X0.25 Mult for each Blind skipped this run"""
    blinds_skipped = joker.state.get("blinds_skipped", 0)
    if blinds_skipped > 0:
        return JokerEffect(mult_mult=1.0 + (0.25 * blinds_skipped))
    return JokerEffect()


def _bloodstone_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Bloodstone (#117): 1 in 2 chance for Hearts to give X1.5 Mult when scored"""
    hearts = [c for c in ctx.scoring_cards if c.suit.value == "H"]
    triggered = sum(1 for _ in hearts if random.random() < 0.5)
    if triggered > 0:
        return JokerEffect(mult_mult=1.5 ** triggered)
    return JokerEffect()


def _glass_joker_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Glass Joker (#120): Gains X0.75 Mult for every Glass Card destroyed"""
    mult = joker.state.get("mult", 1.0)
    if mult > 1.0:
        return JokerEffect(mult_mult=mult)
    return JokerEffect()


def _flower_pot_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Flower Pot (#122): X3 Mult if poker hand contains all 4 suits"""
    suits = {c.suit.value for c in ctx.scoring_cards}
    if suits >= {"D", "C", "H", "S"}:
        return JokerEffect(mult_mult=3.0)
    return JokerEffect()


def _the_duo_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """The Duo (#131): ×2 Mult if hand contains a Pair"""
    from collections import Counter
    ranks = Counter(c.rank for c in ctx.scoring_cards)
    if any(count >= 2 for count in ranks.values()):
        return JokerEffect(mult_mult=2.0)
    return JokerEffect()


def _the_trio_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """The Trio (#132): ×3 Mult if hand contains a Three of a Kind"""
    from collections import Counter
    ranks = Counter(c.rank for c in ctx.scoring_cards)
    if any(count >= 3 for count in ranks.values()):
        return JokerEffect(mult_mult=3.0)
    return JokerEffect()


def _the_family_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """The Family (#133): ×4 Mult if hand contains a Four of a Kind"""
    from collections import Counter
    ranks = Counter(c.rank for c in ctx.scoring_cards)
    if any(count >= 4 for count in ranks.values()):
        return JokerEffect(mult_mult=4.0)
    return JokerEffect()


def _the_order_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """The Order (#134): ×3 Mult if hand contains a Straight"""
    from balatro_bot.models import HandType
    if ctx.hand_result.hand_type in (
        HandType.STRAIGHT, HandType.STRAIGHT_FLUSH, HandType.ROYAL_FLUSH,
    ):
        return JokerEffect(mult_mult=3.0)
    return JokerEffect()


def _the_tribe_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """The Tribe (#135): ×2 Mult if hand contains a Flush"""
    from balatro_bot.models import HandType
    if ctx.hand_result.hand_type in (
        HandType.FLUSH, HandType.STRAIGHT_FLUSH, HandType.ROYAL_FLUSH,
        HandType.FLUSH_HOUSE, HandType.FLUSH_FIVE,
    ):
        return JokerEffect(mult_mult=2.0)
    return JokerEffect()


def _the_idol_effect(joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """The Idol (#127): Each played card of specific rank/suit gives X2 Mult"""
    target_rank = joker.state.get("rank", 14)
    target_suit = joker.state.get("suit", "S")
    count = sum(1 for c in ctx.scoring_cards
                if c.rank.value == target_rank and c.suit.value == target_suit)
    if count > 0:
        return JokerEffect(mult_mult=2.0 ** count)
    return JokerEffect()


def _seeing_double_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Seeing Double (#128): X2 Mult if hand has scoring Club and another suit"""
    has_club = any(c.suit.value == "C" for c in ctx.scoring_cards)
    has_other = any(c.suit.value != "C" for c in ctx.scoring_cards)
    if has_club and has_other:
        return JokerEffect(mult_mult=2.0)
    return JokerEffect()


def _hit_the_road_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Hit the Road (#130): Gains X0.5 Mult for every Jack discarded this round"""
    mult = joker.state.get("mult", 1.0)
    if mult > 1.0:
        return JokerEffect(mult_mult=mult)
    return JokerEffect()


def _drivers_license_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Driver's License (#141): X3 Mult if you have at least 16 Enhanced cards"""
    enhanced = joker.state.get("enhanced_cards", 0)
    if enhanced >= 16:
        return JokerEffect(mult_mult=3.0)
    return JokerEffect()


def _baron_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Baron (#72): Each King held in hand gives X1.5 Mult"""
    king_count = sum(1 for c in ctx.cards_in_hand if c.rank.value == 13)
    if king_count > 0:
        return JokerEffect(mult_mult=1.5 ** king_count)
    return JokerEffect()


def _triboulet_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Triboulet (#147): Played Kings and Queens each give X2 Mult when scored"""
    kq_count = sum(1 for c in ctx.scoring_cards if c.rank.value in (12, 13))
    if kq_count > 0:
        return JokerEffect(mult_mult=2.0 ** kq_count)
    return JokerEffect()


def _canio_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Canio (#146): Gains X1 Mult when a face card is destroyed"""
    mult = joker.state.get("mult", 1.0)
    if mult > 1.0:
        return JokerEffect(mult_mult=mult)
    return JokerEffect()


def _yorick_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Yorick (#148): Gains X1 Mult every 23 cards discarded"""
    mult = joker.state.get("mult", 1.0)
    if mult > 1.0:
        return JokerEffect(mult_mult=mult)
    return JokerEffect()


# =============================================================================
# Joker Effect Calculators - Retrigger
# =============================================================================


def _hack_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Hack (#36): Retrigger each played 2, 3, 4, or 5"""
    count = sum(1 for c in ctx.scoring_cards if c.rank.value in (2, 3, 4, 5))
    return JokerEffect(retrigger=count)


def _dusk_effect(joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Dusk (#28): Retrigger all played cards in final hand of the round"""
    is_final_hand = joker.state.get("is_final_hand", False)
    if is_final_hand:
        return JokerEffect(retrigger=len(ctx.scoring_cards))
    return JokerEffect()


def _sock_and_buskin_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Sock and Buskin (#109): Retrigger all played face cards"""
    face_count = sum(1 for c in ctx.scoring_cards if _is_face_card(c.rank.value))
    return JokerEffect(retrigger=face_count)


def _hanging_chad_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Hanging Chad (#115): Retrigger first played card 2 additional times"""
    return JokerEffect(retrigger=2)


def _seltzer_effect(joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Seltzer (#102): Retrigger all cards played for the next 10 hands"""
    hands_remaining = joker.state.get("hands_remaining", 0)
    if hands_remaining > 0:
        return JokerEffect(retrigger=len(ctx.scoring_cards))
    return JokerEffect()


def _mime_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Mime (#19): Retrigger all card held in hand abilities"""
    # This affects held-in-hand abilities, approximated as retrigger
    return JokerEffect(retrigger=len(ctx.cards_in_hand))


# =============================================================================
# Joker Effect Calculators - Economy/Special (placeholders for non-scoring)
# =============================================================================


def _credit_card_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Credit Card (#20): Go up to -$20 in debt (economy effect, no scoring)"""
    return JokerEffect()


def _ceremonial_dagger_effect(joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Ceremonial Dagger (#21): Destroy joker to right, add mult (scaling)"""
    mult = joker.state.get("mult", 0)
    return JokerEffect(add_mult=mult)


def _marble_joker_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Marble Joker (#24): Adds Stone card to deck (deck effect, no scoring)"""
    return JokerEffect()


def _eight_ball_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """8 Ball (#26): 1 in 4 chance for 8s to create Tarot (no scoring)"""
    return JokerEffect()


def _chaos_the_clown_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Chaos the Clown (#30): 1 free Reroll per shop (economy, no scoring)"""
    return JokerEffect()


def _delayed_gratification_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Delayed Gratification (#35): Earn $2 per discard if none used (economy)"""
    return JokerEffect()


def _pareidolia_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Pareidolia (#37): All cards are considered face cards (modifier)"""
    return JokerEffect()


def _business_card_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Business Card (#42): 1 in 2 chance for face cards to give $2"""
    face_count = sum(1 for c in ctx.scoring_cards if _is_face_card(c.rank.value))
    money = sum(2 for _ in range(face_count) if random.random() < 0.5)
    return JokerEffect(money=money)


def _space_joker_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Space Joker (#45): 1 in 4 chance to upgrade poker hand level"""
    return JokerEffect()


def _egg_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Egg (#46): Gains $3 of sell value at end of round (economy)"""
    return JokerEffect()


def _burglar_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Burglar (#47): +3 Hands, lose all discards when Blind selected"""
    return JokerEffect()


def _dna_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """DNA (#51): Copy first played card to deck if hand is 1 card"""
    return JokerEffect()


def _splash_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Splash (#52): Every played card counts in scoring (modifier)"""
    return JokerEffect()


def _sixth_sense_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Sixth Sense (#54): Destroy single 6 to create Spectral card"""
    return JokerEffect()


def _hiker_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Hiker (#56): Played cards permanently gain +5 Chips (card modifier)"""
    return JokerEffect()


def _faceless_joker_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Faceless Joker (#57): Earn $5 if 3+ face cards discarded (economy)"""
    return JokerEffect()


def _superposition_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Superposition (#59): Create Tarot if hand has Ace and Straight"""
    return JokerEffect()


def _to_do_list_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """To Do List (#60): Earn $4 if poker hand matches target"""
    return JokerEffect()


def _vagabond_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Vagabond (#71): Create Tarot if hand played with $4 or less"""
    return JokerEffect()


def _cloud_9_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Cloud 9 (#73): Earn $1 for each 9 in full deck at end of round"""
    return JokerEffect()


def _rocket_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Rocket (#74): Earn $1 at end of round, +$2 per Boss Blind defeated"""
    return JokerEffect()


def _midas_mask_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Midas Mask (#76): Played face cards become Gold cards (card modifier)"""
    return JokerEffect()


def _luchador_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Luchador (#77): Sell to disable current Boss Blind (special)"""
    return JokerEffect()


def _gift_card_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Gift Card (#79): Add $1 sell value to all Jokers/Consumables"""
    return JokerEffect()


def _turtle_bean_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Turtle Bean (#80): +5 hand size, -1 each round (modifier)"""
    return JokerEffect()


def _reserved_parking_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Reserved Parking (#82): Face cards held have 1/2 chance to give $1"""
    face_count = sum(1 for c in ctx.cards_in_hand if _is_face_card(c.rank.value))
    money = sum(1 for _ in range(face_count) if random.random() < 0.5)
    return JokerEffect(money=money)


def _mail_in_rebate_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Mail-In Rebate (#83): Earn $5 for each discarded rank (economy)"""
    return JokerEffect()


def _to_the_moon_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """To the Moon (#84): Extra $1 interest per $5 at end of round"""
    return JokerEffect()


def _hallucination_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Hallucination (#85): 1/2 chance to create Tarot when Pack opened"""
    return JokerEffect()


def _juggler_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Juggler (#87): +1 hand size (modifier)"""
    return JokerEffect()


def _drunkard_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Drunkard (#88): +1 discard each round (modifier)"""
    return JokerEffect()


def _golden_joker_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Golden Joker (#90): Earn $4 at end of round (economy)"""
    return JokerEffect()


def _diet_cola_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Diet Cola (#94): Sell to create Double Tag (special)"""
    return JokerEffect()


def _trading_card_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Trading Card (#95): Destroy first discard card, earn $3"""
    return JokerEffect()


def _golden_ticket_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Golden Ticket (#106): Played Gold cards earn $4"""
    return JokerEffect()


def _mr_bones_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Mr. Bones (#107): Prevents death if chips >= 25% of required"""
    return JokerEffect()


def _troubadour_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Troubadour (#111): +2 hand size, -1 hand each round"""
    return JokerEffect()


def _certificate_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Certificate (#112): Add random card with seal to hand at round start"""
    return JokerEffect()


def _smeared_joker_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Smeared Joker (#113): Hearts/Diamonds same suit, Spades/Clubs same"""
    return JokerEffect()


def _rough_gem_effect(_joker: JokerInstance, ctx: "ScoringContext") -> JokerEffect:
    """Rough Gem (#116): Played Diamonds earn $1 when scored"""
    diamond_count = sum(1 for c in ctx.scoring_cards if c.suit.value == "D")
    return JokerEffect(money=diamond_count)


def _showman_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Showman (#121): Cards may appear multiple times (modifier)"""
    return JokerEffect()


def _blueprint_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Blueprint (#123): Copies ability of Joker to the right"""
    return JokerEffect()


def _merry_andy_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Merry Andy (#125): +3 discards, -1 hand size"""
    return JokerEffect()


def _oops_all_6s_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Oops! All 6s (#126): Doubles all probabilities (modifier)"""
    return JokerEffect()


def _matador_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Matador (#129): Earn $8 if hand triggers Boss Blind ability"""
    return JokerEffect()


def _invisible_joker_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Invisible Joker (#137): After 2 rounds, sell to duplicate Joker"""
    return JokerEffect()


def _brainstorm_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Brainstorm (#138): Copies ability of leftmost Joker"""
    return JokerEffect()


def _satellite_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Satellite (#139): Earn $1 per unique Planet card used this run"""
    return JokerEffect()


def _cartomancer_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Cartomancer (#142): Create Tarot when Blind selected"""
    return JokerEffect()


def _astronomer_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Astronomer (#143): Planet cards and Celestial Packs are free"""
    return JokerEffect()


def _burnt_joker_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Burnt Joker (#144): Upgrade level of first discarded poker hand"""
    return JokerEffect()


def _chicot_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Chicot (#149): Disables effect of every Boss Blind"""
    return JokerEffect()


def _perkeo_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Perkeo (#150): Creates Negative copy of random consumable"""
    return JokerEffect()


def _four_fingers_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Four Fingers (#18): Flushes and Straights can be 4 cards (modifier)"""
    return JokerEffect()


def _shortcut_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Shortcut (#69): Straights can have gaps of 1 rank (modifier)"""
    return JokerEffect()


def _seance_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Seance (#66): Create Spectral if hand is Straight Flush"""
    return JokerEffect()


def _riff_raff_effect(_joker: JokerInstance, _ctx: "ScoringContext") -> JokerEffect:
    """Riff-Raff (#67): Create 2 Common Jokers when Blind selected"""
    return JokerEffect()


# =============================================================================
# Joker Registry - Effect Calculators
# =============================================================================

JOKER_CALCULATORS: dict[str, type] = {
    # Simple +Mult
    "joker": _joker_effect,
    "greedy_joker": _greedy_joker_effect,
    "lusty_joker": _lusty_joker_effect,
    "wrathful_joker": _wrathful_joker_effect,
    "gluttonous_joker": _gluttonous_joker_effect,
    "jolly_joker": _jolly_joker_effect,
    "zany_joker": _zany_joker_effect,
    "mad_joker": _mad_joker_effect,
    "crazy_joker": _crazy_joker_effect,
    "droll_joker": _droll_joker_effect,
    "half_joker": _half_joker_effect,
    "banner": _banner_effect,
    "mystic_summit": _mystic_summit_effect,
    "misprint": _misprint_effect,
    "raised_fist": _raised_fist_effect,
    "fibonacci": _fibonacci_effect,
    "abstract_joker": _abstract_joker_effect,
    "gros_michel": _gros_michel_effect,
    "even_steven": _even_steven_effect,
    "scholar": _scholar_effect,
    "supernova": _supernova_effect,
    "erosion": _erosion_effect,
    "fortune_teller": _fortune_teller_effect,
    "popcorn": _popcorn_effect,
    "smiley_face": _smiley_face_effect,
    "swashbuckler": _swashbuckler_effect,
    "shoot_the_moon": _shoot_the_moon_effect,
    "bootstraps": _bootstraps_effect,
    "onyx_agate": _onyx_agate_effect,
    "walkie_talkie": _walkie_talkie_effect,
    # Simple +Chips
    "sly_joker": _sly_joker_effect,
    "wily_joker": _wily_joker_effect,
    "clever_joker": _clever_joker_effect,
    "devious_joker": _devious_joker_effect,
    "crafty_joker": _crafty_joker_effect,
    "scary_face": _scary_face_effect,
    "odd_todd": _odd_todd_effect,
    "blue_joker": _blue_joker_effect,
    "stone_joker": _stone_joker_effect,
    "bull": _bull_effect,
    "arrowhead": _arrowhead_effect,
    "stuntman": _stuntman_effect,
    # Scaling
    "ice_cream": _ice_cream_effect,
    "runner": _runner_effect,
    "square_joker": _square_joker_effect,
    "castle": _castle_effect,
    "wee_joker": _wee_joker_effect,
    "ride_the_bus": _ride_the_bus_effect,
    "green_joker": _green_joker_effect,
    "red_card": _red_card_effect,
    "flash_card": _flash_card_effect,
    "spare_trousers": _spare_trousers_effect,
    # X Mult
    "blackboard": _blackboard_effect,
    "joker_stencil": _joker_stencil_effect,
    "loyalty_card": _loyalty_card_effect,
    "steel_joker": _steel_joker_effect,
    "constellation": _constellation_effect,
    "cavendish": _cavendish_effect,
    "card_sharp": _card_sharp_effect,
    "madness": _madness_effect,
    "hologram": _hologram_effect,
    "vampire": _vampire_effect,
    "obelisk": _obelisk_effect,
    "photograph": _photograph_effect,
    "lucky_cat": _lucky_cat_effect,
    "baseball_card": _baseball_card_effect,
    "ancient_joker": _ancient_joker_effect,
    "ramen": _ramen_effect,
    "acrobat": _acrobat_effect,
    "campfire": _campfire_effect,
    "throwback": _throwback_effect,
    "bloodstone": _bloodstone_effect,
    "glass_joker": _glass_joker_effect,
    "flower_pot": _flower_pot_effect,
    "the_duo": _the_duo_effect,
    "the_trio": _the_trio_effect,
    "the_family": _the_family_effect,
    "the_order": _the_order_effect,
    "the_tribe": _the_tribe_effect,
    "the_idol": _the_idol_effect,
    "seeing_double": _seeing_double_effect,
    "hit_the_road": _hit_the_road_effect,
    "drivers_license": _drivers_license_effect,
    "baron": _baron_effect,
    "triboulet": _triboulet_effect,
    "canio": _canio_effect,
    "yorick": _yorick_effect,
    # Retrigger
    "hack": _hack_effect,
    "dusk": _dusk_effect,
    "sock_and_buskin": _sock_and_buskin_effect,
    "hanging_chad": _hanging_chad_effect,
    "seltzer": _seltzer_effect,
    "mime": _mime_effect,
    # Economy/Special
    "credit_card": _credit_card_effect,
    "ceremonial_dagger": _ceremonial_dagger_effect,
    "marble_joker": _marble_joker_effect,
    "eight_ball": _eight_ball_effect,
    "chaos_the_clown": _chaos_the_clown_effect,
    "delayed_gratification": _delayed_gratification_effect,
    "pareidolia": _pareidolia_effect,
    "business_card": _business_card_effect,
    "space_joker": _space_joker_effect,
    "egg": _egg_effect,
    "burglar": _burglar_effect,
    "dna": _dna_effect,
    "splash": _splash_effect,
    "sixth_sense": _sixth_sense_effect,
    "hiker": _hiker_effect,
    "faceless_joker": _faceless_joker_effect,
    "superposition": _superposition_effect,
    "to_do_list": _to_do_list_effect,
    "vagabond": _vagabond_effect,
    "cloud_9": _cloud_9_effect,
    "rocket": _rocket_effect,
    "midas_mask": _midas_mask_effect,
    "luchador": _luchador_effect,
    "gift_card": _gift_card_effect,
    "turtle_bean": _turtle_bean_effect,
    "reserved_parking": _reserved_parking_effect,
    "mail_in_rebate": _mail_in_rebate_effect,
    "to_the_moon": _to_the_moon_effect,
    "hallucination": _hallucination_effect,
    "juggler": _juggler_effect,
    "drunkard": _drunkard_effect,
    "golden_joker": _golden_joker_effect,
    "diet_cola": _diet_cola_effect,
    "trading_card": _trading_card_effect,
    "golden_ticket": _golden_ticket_effect,
    "mr_bones": _mr_bones_effect,
    "troubadour": _troubadour_effect,
    "certificate": _certificate_effect,
    "smeared_joker": _smeared_joker_effect,
    "rough_gem": _rough_gem_effect,
    "showman": _showman_effect,
    "blueprint": _blueprint_effect,
    "merry_andy": _merry_andy_effect,
    "oops_all_6s": _oops_all_6s_effect,
    "matador": _matador_effect,
    "invisible_joker": _invisible_joker_effect,
    "brainstorm": _brainstorm_effect,
    "satellite": _satellite_effect,
    "cartomancer": _cartomancer_effect,
    "astronomer": _astronomer_effect,
    "burnt_joker": _burnt_joker_effect,
    "chicot": _chicot_effect,
    "perkeo": _perkeo_effect,
    "four_fingers": _four_fingers_effect,
    "shortcut": _shortcut_effect,
    "seance": _seance_effect,
    "riff_raff": _riff_raff_effect,
}


# =============================================================================
# Economy Effect Calculators
# =============================================================================


def _golden_joker_economy(
    _joker: JokerInstance, _ctx: EconomyContext
) -> EconomyEffect:
    """Golden Joker: Earn $4 at end of round."""
    return EconomyEffect(money=4)


def _rocket_economy(joker: JokerInstance, _ctx: EconomyContext) -> EconomyEffect:
    """Rocket: Earn $1 at end of round. Payout increases by $2 when Boss Blind is defeated."""
    # State tracks number of boss blinds defeated
    bosses = joker.state.get("boss_blinds_defeated", 0)
    return EconomyEffect(money=1 + (bosses * 2))


def _cloud_9_economy(_joker: JokerInstance, ctx: EconomyContext) -> EconomyEffect:
    """Cloud 9: Earn $1 for each 9 in your full deck at end of round."""
    return EconomyEffect(money=ctx.nines_in_deck)


def _to_the_moon_economy(_joker: JokerInstance, ctx: EconomyContext) -> EconomyEffect:
    """To the Moon: Earn an extra $1 of interest for every $5 you have."""
    # Calculate extra interest (on top of normal interest)
    extra_interest = ctx.money // 5
    return EconomyEffect(interest_bonus=extra_interest)


def _egg_economy(joker: JokerInstance, _ctx: EconomyContext) -> EconomyEffect:
    """Egg: Gains $3 of sell value at end of round."""
    # Increment egg's sell value
    current_bonus = joker.state.get("sell_value_bonus", 0)
    joker.state["sell_value_bonus"] = current_bonus + 3
    return EconomyEffect(sell_value_change=3)


def _satellite_economy(_joker: JokerInstance, ctx: EconomyContext) -> EconomyEffect:
    """Satellite: Earn $1 at end of round per unique Planet card used this run."""
    return EconomyEffect(money=ctx.unique_planets_used)


def _delayed_gratification_economy(
    _joker: JokerInstance, ctx: EconomyContext
) -> EconomyEffect:
    """Delayed Gratification: Earn $2 per discard if no discards used this round."""
    if ctx.discards_used == 0:
        # Earn $2 for each discard slot
        total_discards = ctx.discards_remaining + ctx.discards_used
        return EconomyEffect(money=2 * total_discards)
    return EconomyEffect()


def _credit_card_economy(_joker: JokerInstance, _ctx: EconomyContext) -> EconomyEffect:
    """Credit Card: Go up to -$20 in debt."""
    return EconomyEffect(debt_limit=20)


def _gift_card_economy(joker: JokerInstance, _ctx: EconomyContext) -> EconomyEffect:
    """Gift Card: Add $1 of sell value to all Jokers and Consumables at end of round."""
    # This affects all jokers, tracked via state
    joker.state["gift_card_triggered"] = True
    return EconomyEffect(sell_value_change=1)


def _trading_card_economy(
    _joker: JokerInstance, ctx: EconomyContext
) -> EconomyEffect:
    """Trading Card: If first discard of round has only 1 card, destroy it and earn $3."""
    if len(ctx.discarded_cards) == 1:
        return EconomyEffect(money=3)
    return EconomyEffect()


def _faceless_joker_economy(
    _joker: JokerInstance, ctx: EconomyContext
) -> EconomyEffect:
    """Faceless Joker: Earn $5 if 3 or more face cards are discarded at the same time."""
    face_count = sum(
        1 for c in ctx.discarded_cards if _is_face_card(c.rank.value)
    )
    if face_count >= 3:
        return EconomyEffect(money=5)
    return EconomyEffect()


def _mail_in_rebate_economy(
    joker: JokerInstance, ctx: EconomyContext
) -> EconomyEffect:
    """Mail-In Rebate: Earn $5 for each discarded card matching the target rank."""
    target_rank = joker.state.get("target_rank")
    if target_rank is None:
        return EconomyEffect()
    matching = sum(1 for c in ctx.discarded_cards if c.rank.value == target_rank)
    return EconomyEffect(money=5 * matching)


def _to_do_list_economy(joker: JokerInstance, ctx: EconomyContext) -> EconomyEffect:
    """To Do List: Earn $4 if poker hand is the listed poker hand. Hand changes each round."""
    target = joker.state.get("target_hand")
    if target and ctx.played_hand_type == target:
        return EconomyEffect(money=4)
    return EconomyEffect()


def _matador_economy(_joker: JokerInstance, ctx: EconomyContext) -> EconomyEffect:
    """Matador: Earn $8 if played hand triggers the Boss Blind ability."""
    if ctx.boss_blind_triggered:
        return EconomyEffect(money=8)
    return EconomyEffect()


def _golden_ticket_economy(
    _joker: JokerInstance, ctx: EconomyContext
) -> EconomyEffect:
    """Golden Ticket: Played Gold cards earn $4 when scored."""
    # Count gold cards in played cards (this would be in scoring context normally)
    # For economy context, we track this separately
    gold_count = ctx.__dict__.get("gold_cards_played", 0)
    return EconomyEffect(money=4 * gold_count)


# Economy Calculator Registry - maps (joker_id, timing) to calculator
ECONOMY_CALCULATORS: dict[tuple[str, EffectTiming], type] = {
    # End of Round effects
    ("golden_joker", EffectTiming.END_OF_ROUND): _golden_joker_economy,
    ("rocket", EffectTiming.END_OF_ROUND): _rocket_economy,
    ("cloud_9", EffectTiming.END_OF_ROUND): _cloud_9_economy,
    ("to_the_moon", EffectTiming.END_OF_ROUND): _to_the_moon_economy,
    ("egg", EffectTiming.END_OF_ROUND): _egg_economy,
    ("satellite", EffectTiming.END_OF_ROUND): _satellite_economy,
    ("delayed_gratification", EffectTiming.END_OF_ROUND): _delayed_gratification_economy,
    ("gift_card", EffectTiming.END_OF_ROUND): _gift_card_economy,
    # Shop effects
    ("credit_card", EffectTiming.ON_SHOP): _credit_card_economy,
    # Discard effects
    ("trading_card", EffectTiming.ON_DISCARD): _trading_card_economy,
    ("faceless_joker", EffectTiming.ON_DISCARD): _faceless_joker_economy,
    ("mail_in_rebate", EffectTiming.ON_DISCARD): _mail_in_rebate_economy,
    # Hand played effects (conditional economy)
    ("to_do_list", EffectTiming.ON_HAND_PLAYED): _to_do_list_economy,
    ("matador", EffectTiming.ON_HAND_PLAYED): _matador_economy,
    ("golden_ticket", EffectTiming.ON_HAND_PLAYED): _golden_ticket_economy,
}


# =============================================================================
# Economy Helper Functions
# =============================================================================


def calculate_end_of_round_economy(
    jokers: list[JokerInstance],
    ctx: EconomyContext,
) -> int:
    """Calculate total money earned at end of round from all jokers.

    Args:
        jokers: List of joker instances
        ctx: Economy context

    Returns:
        Total money earned
    """
    total = 0
    for joker in jokers:
        effect = joker.calculate_economy_effect(ctx, EffectTiming.END_OF_ROUND)
        total += effect.money
    return total


def calculate_discard_economy(
    jokers: list[JokerInstance],
    ctx: EconomyContext,
) -> int:
    """Calculate money earned from discarding cards.

    Args:
        jokers: List of joker instances
        ctx: Economy context with discarded_cards set

    Returns:
        Total money earned
    """
    total = 0
    for joker in jokers:
        effect = joker.calculate_economy_effect(ctx, EffectTiming.ON_DISCARD)
        total += effect.money
    return total


def calculate_play_economy(
    jokers: list[JokerInstance],
    ctx: EconomyContext,
) -> int:
    """Calculate conditional money earned from playing a hand.

    Args:
        jokers: List of joker instances
        ctx: Economy context with played_hand_type set

    Returns:
        Total money earned
    """
    total = 0
    for joker in jokers:
        effect = joker.calculate_economy_effect(ctx, EffectTiming.ON_HAND_PLAYED)
        total += effect.money
    return total


# =============================================================================
# Joker Definitions Registry
# =============================================================================

JOKERS: dict[str, JokerDefinition] = {
    # 1-10: Basic Jokers
    "joker": JokerDefinition(
        id="joker", name="Joker", description="+4 Mult",
        rarity=JokerRarity.COMMON, base_cost=2,
    ),
    "greedy_joker": JokerDefinition(
        id="greedy_joker", name="Greedy Joker",
        description="Played cards with Diamond suit give +3 Mult when scored",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    "lusty_joker": JokerDefinition(
        id="lusty_joker", name="Lusty Joker",
        description="Played cards with Heart suit give +3 Mult when scored",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    "wrathful_joker": JokerDefinition(
        id="wrathful_joker", name="Wrathful Joker",
        description="Played cards with Spade suit give +3 Mult when scored",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    "gluttonous_joker": JokerDefinition(
        id="gluttonous_joker", name="Gluttonous Joker",
        description="Played cards with Club suit give +3 Mult when scored",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    "jolly_joker": JokerDefinition(
        id="jolly_joker", name="Jolly Joker",
        description="+8 Mult if played hand contains a Pair",
        rarity=JokerRarity.COMMON, base_cost=3,
    ),
    "zany_joker": JokerDefinition(
        id="zany_joker", name="Zany Joker",
        description="+12 Mult if played hand contains a Three of a Kind",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "mad_joker": JokerDefinition(
        id="mad_joker", name="Mad Joker",
        description="+10 Mult if played hand contains a Two Pair",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "crazy_joker": JokerDefinition(
        id="crazy_joker", name="Crazy Joker",
        description="+12 Mult if played hand contains a Straight",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "droll_joker": JokerDefinition(
        id="droll_joker", name="Droll Joker",
        description="+10 Mult if played hand contains a Flush",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    # 11-20
    "sly_joker": JokerDefinition(
        id="sly_joker", name="Sly Joker",
        description="+50 Chips if played hand contains a Pair",
        rarity=JokerRarity.COMMON, base_cost=3,
    ),
    "wily_joker": JokerDefinition(
        id="wily_joker", name="Wily Joker",
        description="+100 Chips if played hand contains a Three of a Kind",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "clever_joker": JokerDefinition(
        id="clever_joker", name="Clever Joker",
        description="+80 Chips if played hand contains a Two Pair",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "devious_joker": JokerDefinition(
        id="devious_joker", name="Devious Joker",
        description="+100 Chips if played hand contains a Straight",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "crafty_joker": JokerDefinition(
        id="crafty_joker", name="Crafty Joker",
        description="+80 Chips if played hand contains a Flush",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "half_joker": JokerDefinition(
        id="half_joker", name="Half Joker",
        description="+20 Mult if played hand contains 3 or fewer cards",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    "joker_stencil": JokerDefinition(
        id="joker_stencil", name="Joker Stencil",
        description="X1 Mult for each empty Joker slot",
        rarity=JokerRarity.UNCOMMON, base_cost=8,
    ),
    "four_fingers": JokerDefinition(
        id="four_fingers", name="Four Fingers",
        description="All Flushes and Straights can be made with 4 cards",
        rarity=JokerRarity.UNCOMMON, base_cost=7,
    ),
    "mime": JokerDefinition(
        id="mime", name="Mime",
        description="Retrigger all card held in hand abilities",
        rarity=JokerRarity.UNCOMMON, base_cost=5,
    ),
    "credit_card": JokerDefinition(
        id="credit_card", name="Credit Card",
        description="Go up to -$20 in debt",
        rarity=JokerRarity.COMMON, base_cost=1,
    ),
    # 21-30
    "ceremonial_dagger": JokerDefinition(
        id="ceremonial_dagger", name="Ceremonial Dagger",
        description="When Blind is selected, destroy Joker to the right and add double its sell value to Mult",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "banner": JokerDefinition(
        id="banner", name="Banner",
        description="+30 Chips for each remaining discard",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    "mystic_summit": JokerDefinition(
        id="mystic_summit", name="Mystic Summit",
        description="+15 Mult when 0 discards remaining",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    "marble_joker": JokerDefinition(
        id="marble_joker", name="Marble Joker",
        description="Adds one Stone card to the deck when Blind is selected",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "loyalty_card": JokerDefinition(
        id="loyalty_card", name="Loyalty Card",
        description="X4 Mult every 6 hands played",
        rarity=JokerRarity.UNCOMMON, base_cost=5,
    ),
    "eight_ball": JokerDefinition(
        id="eight_ball", name="8 Ball",
        description="1 in 4 chance for each played 8 to create a Tarot card when scored",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    "misprint": JokerDefinition(
        id="misprint", name="Misprint",
        description="+0-23 Mult",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "dusk": JokerDefinition(
        id="dusk", name="Dusk",
        description="Retrigger all played cards in final hand of the round",
        rarity=JokerRarity.UNCOMMON, base_cost=5,
    ),
    "raised_fist": JokerDefinition(
        id="raised_fist", name="Raised Fist",
        description="Adds double the rank of lowest ranked card held in hand to Mult",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    "chaos_the_clown": JokerDefinition(
        id="chaos_the_clown", name="Chaos the Clown",
        description="1 free Reroll per shop",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    # 31-40
    "fibonacci": JokerDefinition(
        id="fibonacci", name="Fibonacci",
        description="Each played Ace, 2, 3, 5, or 8 gives +8 Mult when scored",
        rarity=JokerRarity.UNCOMMON, base_cost=8,
    ),
    "steel_joker": JokerDefinition(
        id="steel_joker", name="Steel Joker",
        description="Gives X0.2 Mult for each Steel Card in your full deck",
        rarity=JokerRarity.UNCOMMON, base_cost=7,
    ),
    "scary_face": JokerDefinition(
        id="scary_face", name="Scary Face",
        description="Played face cards give +30 Chips when scored",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "abstract_joker": JokerDefinition(
        id="abstract_joker", name="Abstract Joker",
        description="+3 Mult for each Joker card",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "delayed_gratification": JokerDefinition(
        id="delayed_gratification", name="Delayed Gratification",
        description="Earn $2 per discard if no discards are used by end of the round",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "hack": JokerDefinition(
        id="hack", name="Hack",
        description="Retrigger each played 2, 3, 4, or 5",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "pareidolia": JokerDefinition(
        id="pareidolia", name="Pareidolia",
        description="All cards are considered face cards",
        rarity=JokerRarity.UNCOMMON, base_cost=5,
    ),
    "gros_michel": JokerDefinition(
        id="gros_michel", name="Gros Michel",
        description="+15 Mult, 1 in 6 chance this is destroyed at end of round",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    "even_steven": JokerDefinition(
        id="even_steven", name="Even Steven",
        description="Played cards with even rank give +4 Mult when scored (10, 8, 6, 4, 2)",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "odd_todd": JokerDefinition(
        id="odd_todd", name="Odd Todd",
        description="Played cards with odd rank give +31 Chips when scored (A, 9, 7, 5, 3)",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    # 41-50
    "scholar": JokerDefinition(
        id="scholar", name="Scholar",
        description="Played Aces give +20 Chips and +4 Mult when scored",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "business_card": JokerDefinition(
        id="business_card", name="Business Card",
        description="Played face cards have a 1 in 2 chance to give $2 when scored",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "supernova": JokerDefinition(
        id="supernova", name="Supernova",
        description="Adds the number of times poker hand has been played this run to Mult",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    "ride_the_bus": JokerDefinition(
        id="ride_the_bus", name="Ride the Bus",
        description="This Joker gains +1 Mult per consecutive hand played without a scoring face card",
        rarity=JokerRarity.COMMON, base_cost=6,
    ),
    "space_joker": JokerDefinition(
        id="space_joker", name="Space Joker",
        description="1 in 4 chance to upgrade level of played poker hand",
        rarity=JokerRarity.UNCOMMON, base_cost=5,
    ),
    "egg": JokerDefinition(
        id="egg", name="Egg",
        description="Gains $3 of sell value at end of round",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "burglar": JokerDefinition(
        id="burglar", name="Burglar",
        description="When Blind is selected, gain +3 Hands and lose all discards",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "blackboard": JokerDefinition(
        id="blackboard", name="Blackboard",
        description="X3 Mult if all cards held in hand are Spades or Clubs",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "runner": JokerDefinition(
        id="runner", name="Runner",
        description="Gains +15 Chips if played hand contains a Straight",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    "ice_cream": JokerDefinition(
        id="ice_cream", name="Ice Cream",
        description="+100 Chips, -5 Chips for every hand played",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    # 51-60
    "dna": JokerDefinition(
        id="dna", name="DNA",
        description="If first hand of round has only 1 card, add a permanent copy to deck",
        rarity=JokerRarity.RARE, base_cost=8,
    ),
    "splash": JokerDefinition(
        id="splash", name="Splash",
        description="Every played card counts in scoring",
        rarity=JokerRarity.COMMON, base_cost=3,
    ),
    "blue_joker": JokerDefinition(
        id="blue_joker", name="Blue Joker",
        description="+2 Chips for each remaining card in deck",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    "sixth_sense": JokerDefinition(
        id="sixth_sense", name="Sixth Sense",
        description="If first hand of round is a single 6, destroy it and create a Spectral card",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "constellation": JokerDefinition(
        id="constellation", name="Constellation",
        description="This Joker gains X0.1 Mult every time a Planet card is used",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "hiker": JokerDefinition(
        id="hiker", name="Hiker",
        description="Every played card permanently gains +5 Chips when scored",
        rarity=JokerRarity.UNCOMMON, base_cost=5,
    ),
    "faceless_joker": JokerDefinition(
        id="faceless_joker", name="Faceless Joker",
        description="Earn $5 if 3 or more face cards are discarded at the same time",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "green_joker": JokerDefinition(
        id="green_joker", name="Green Joker",
        description="+1 Mult per hand played, -1 Mult per discard",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "superposition": JokerDefinition(
        id="superposition", name="Superposition",
        description="Create a Tarot card if poker hand contains an Ace and a Straight",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "to_do_list": JokerDefinition(
        id="to_do_list", name="To Do List",
        description="Earn $4 if poker hand is a specific hand, changes at end of round",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    # 61-70
    "cavendish": JokerDefinition(
        id="cavendish", name="Cavendish",
        description="X3 Mult, 1 in 1000 chance this card is destroyed at end of round",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "card_sharp": JokerDefinition(
        id="card_sharp", name="Card Sharp",
        description="X3 Mult if played poker hand has already been played this round",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "red_card": JokerDefinition(
        id="red_card", name="Red Card",
        description="This Joker gains +3 Mult when any Booster Pack is skipped",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    "madness": JokerDefinition(
        id="madness", name="Madness",
        description="When Small or Big Blind is selected, gain X0.5 Mult and destroy a random Joker",
        rarity=JokerRarity.UNCOMMON, base_cost=7,
    ),
    "square_joker": JokerDefinition(
        id="square_joker", name="Square Joker",
        description="This Joker gains +4 Chips if played hand has exactly 4 cards",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "seance": JokerDefinition(
        id="seance", name="Seance",
        description="If poker hand is a Straight Flush, create a random Spectral card",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "riff_raff": JokerDefinition(
        id="riff_raff", name="Riff-Raff",
        description="When Blind is selected, create 2 Common Jokers",
        rarity=JokerRarity.COMMON, base_cost=6,
    ),
    "vampire": JokerDefinition(
        id="vampire", name="Vampire",
        description="This Joker gains X0.1 Mult per scoring Enhanced card played",
        rarity=JokerRarity.UNCOMMON, base_cost=7,
    ),
    "shortcut": JokerDefinition(
        id="shortcut", name="Shortcut",
        description="Allows Straights to be made with gaps of 1 rank",
        rarity=JokerRarity.UNCOMMON, base_cost=7,
    ),
    "hologram": JokerDefinition(
        id="hologram", name="Hologram",
        description="This Joker gains X0.25 Mult every time a playing card is added to your deck",
        rarity=JokerRarity.UNCOMMON, base_cost=7,
    ),
    # 71-80
    "vagabond": JokerDefinition(
        id="vagabond", name="Vagabond",
        description="Create a Tarot card if hand is played with $4 or less",
        rarity=JokerRarity.RARE, base_cost=8,
    ),
    "baron": JokerDefinition(
        id="baron", name="Baron",
        description="Each King held in hand gives X1.5 Mult",
        rarity=JokerRarity.RARE, base_cost=8,
    ),
    "cloud_9": JokerDefinition(
        id="cloud_9", name="Cloud 9",
        description="Earn $1 for each 9 in your full deck at end of round",
        rarity=JokerRarity.UNCOMMON, base_cost=7,
    ),
    "rocket": JokerDefinition(
        id="rocket", name="Rocket",
        description="Earn $1 at end of round. Payout increases by $2 when Boss Blind is defeated",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "obelisk": JokerDefinition(
        id="obelisk", name="Obelisk",
        description="This Joker gains X0.2 Mult per consecutive hand played without your most played hand",
        rarity=JokerRarity.RARE, base_cost=8,
    ),
    "midas_mask": JokerDefinition(
        id="midas_mask", name="Midas Mask",
        description="All played face cards become Gold cards when scored",
        rarity=JokerRarity.UNCOMMON, base_cost=7,
    ),
    "luchador": JokerDefinition(
        id="luchador", name="Luchador",
        description="Sell this card to disable the current Boss Blind",
        rarity=JokerRarity.UNCOMMON, base_cost=5,
    ),
    "photograph": JokerDefinition(
        id="photograph", name="Photograph",
        description="First played face card gives X2 Mult when scored",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    "gift_card": JokerDefinition(
        id="gift_card", name="Gift Card",
        description="Add $1 of sell value to every Joker and Consumable card at end of round",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "turtle_bean": JokerDefinition(
        id="turtle_bean", name="Turtle Bean",
        description="+5 hand size, reduces by 1 each round",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    # 81-90
    "erosion": JokerDefinition(
        id="erosion", name="Erosion",
        description="+4 Mult for each card below the deck's starting size in your full deck",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "reserved_parking": JokerDefinition(
        id="reserved_parking", name="Reserved Parking",
        description="Each face card held in hand has a 1 in 2 chance to give $1",
        rarity=JokerRarity.COMMON, base_cost=6,
    ),
    "mail_in_rebate": JokerDefinition(
        id="mail_in_rebate", name="Mail-In Rebate",
        description="Earn $5 for each discarded card of specific rank, rank changes every round",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "to_the_moon": JokerDefinition(
        id="to_the_moon", name="To the Moon",
        description="Earn an extra $1 of interest for every $5 you have at end of round",
        rarity=JokerRarity.UNCOMMON, base_cost=5,
    ),
    "hallucination": JokerDefinition(
        id="hallucination", name="Hallucination",
        description="1 in 2 chance to create a Tarot card when any Booster Pack is opened",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "fortune_teller": JokerDefinition(
        id="fortune_teller", name="Fortune Teller",
        description="+1 Mult per Tarot card used this run",
        rarity=JokerRarity.COMMON, base_cost=6,
    ),
    "juggler": JokerDefinition(
        id="juggler", name="Juggler",
        description="+1 hand size",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "drunkard": JokerDefinition(
        id="drunkard", name="Drunkard",
        description="+1 discard each round",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "stone_joker": JokerDefinition(
        id="stone_joker", name="Stone Joker",
        description="Gives +25 Chips for each Stone Card in your full deck",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "golden_joker": JokerDefinition(
        id="golden_joker", name="Golden Joker",
        description="Earn $4 at end of round",
        rarity=JokerRarity.COMMON, base_cost=6,
    ),
    # 91-100
    "lucky_cat": JokerDefinition(
        id="lucky_cat", name="Lucky Cat",
        description="This Joker gains X0.25 Mult every time a Lucky card successfully triggers",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "baseball_card": JokerDefinition(
        id="baseball_card", name="Baseball Card",
        description="Uncommon Jokers each give X1.5 Mult",
        rarity=JokerRarity.RARE, base_cost=8,
    ),
    "bull": JokerDefinition(
        id="bull", name="Bull",
        description="+2 Chips for each $1 you have",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "diet_cola": JokerDefinition(
        id="diet_cola", name="Diet Cola",
        description="Sell this card to create a free Double Tag",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "trading_card": JokerDefinition(
        id="trading_card", name="Trading Card",
        description="If first discard of round has only 1 card, destroy it and earn $3",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "flash_card": JokerDefinition(
        id="flash_card", name="Flash Card",
        description="This Joker gains +2 Mult per reroll in the shop",
        rarity=JokerRarity.UNCOMMON, base_cost=5,
    ),
    "popcorn": JokerDefinition(
        id="popcorn", name="Popcorn",
        description="+20 Mult, -4 Mult per round played",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    "spare_trousers": JokerDefinition(
        id="spare_trousers", name="Spare Trousers",
        description="This Joker gains +2 Mult if played hand contains a Two Pair",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "ancient_joker": JokerDefinition(
        id="ancient_joker", name="Ancient Joker",
        description="Each played card with specific suit gives X1.5 Mult when scored, suit changes at end of round",
        rarity=JokerRarity.RARE, base_cost=8,
    ),
    "ramen": JokerDefinition(
        id="ramen", name="Ramen",
        description="X2 Mult, loses X0.01 Mult per card discarded",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    # 101-110
    "walkie_talkie": JokerDefinition(
        id="walkie_talkie", name="Walkie Talkie",
        description="Each played 10 or 4 gives +10 Chips and +4 Mult when scored",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "seltzer": JokerDefinition(
        id="seltzer", name="Seltzer",
        description="Retrigger all cards played for the next 10 hands",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "castle": JokerDefinition(
        id="castle", name="Castle",
        description="This Joker gains +3 Chips per discarded card of specific suit, suit changes every round",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "smiley_face": JokerDefinition(
        id="smiley_face", name="Smiley Face",
        description="Played face cards give +5 Mult when scored",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "campfire": JokerDefinition(
        id="campfire", name="Campfire",
        description="This Joker gains X0.25 Mult for each card sold, resets when Boss Blind is defeated",
        rarity=JokerRarity.RARE, base_cost=9,
    ),
    "golden_ticket": JokerDefinition(
        id="golden_ticket", name="Golden Ticket",
        description="Played Gold cards earn $4 when scored",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    "mr_bones": JokerDefinition(
        id="mr_bones", name="Mr. Bones",
        description="Prevents Death if chips scored are at least 25% of required chips, self destructs",
        rarity=JokerRarity.UNCOMMON, base_cost=5,
    ),
    "acrobat": JokerDefinition(
        id="acrobat", name="Acrobat",
        description="X3 Mult on final hand of round",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "sock_and_buskin": JokerDefinition(
        id="sock_and_buskin", name="Sock and Buskin",
        description="Retrigger all played face cards",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "swashbuckler": JokerDefinition(
        id="swashbuckler", name="Swashbuckler",
        description="Adds the sell value of all other owned Jokers to Mult",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    # 111-120
    "troubadour": JokerDefinition(
        id="troubadour", name="Troubadour",
        description="+2 hand size, -1 hand each round",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "certificate": JokerDefinition(
        id="certificate", name="Certificate",
        description="When round begins, add a random playing card with a random seal to your hand",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "smeared_joker": JokerDefinition(
        id="smeared_joker", name="Smeared Joker",
        description="Hearts and Diamonds count as the same suit, Spades and Clubs count as the same suit",
        rarity=JokerRarity.UNCOMMON, base_cost=7,
    ),
    "throwback": JokerDefinition(
        id="throwback", name="Throwback",
        description="X0.25 Mult for each Blind skipped this run",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "hanging_chad": JokerDefinition(
        id="hanging_chad", name="Hanging Chad",
        description="Retrigger first played card used in scoring 2 additional times",
        rarity=JokerRarity.COMMON, base_cost=4,
    ),
    "rough_gem": JokerDefinition(
        id="rough_gem", name="Rough Gem",
        description="Played cards with Diamond suit earn $1 when scored",
        rarity=JokerRarity.UNCOMMON, base_cost=7,
    ),
    "bloodstone": JokerDefinition(
        id="bloodstone", name="Bloodstone",
        description="1 in 2 chance for played cards with Heart suit to give X1.5 Mult when scored",
        rarity=JokerRarity.UNCOMMON, base_cost=7,
    ),
    "arrowhead": JokerDefinition(
        id="arrowhead", name="Arrowhead",
        description="Played cards with Spade suit give +50 Chips when scored",
        rarity=JokerRarity.UNCOMMON, base_cost=7,
    ),
    "onyx_agate": JokerDefinition(
        id="onyx_agate", name="Onyx Agate",
        description="Played cards with Club suit give +7 Mult when scored",
        rarity=JokerRarity.UNCOMMON, base_cost=7,
    ),
    "glass_joker": JokerDefinition(
        id="glass_joker", name="Glass Joker",
        description="This Joker gains X0.75 Mult for every Glass Card that is destroyed",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    # 121-130
    "showman": JokerDefinition(
        id="showman", name="Showman",
        description="Joker, Tarot, Planet, and Spectral cards may appear multiple times",
        rarity=JokerRarity.UNCOMMON, base_cost=5,
    ),
    "flower_pot": JokerDefinition(
        id="flower_pot", name="Flower Pot",
        description="X3 Mult if poker hand contains a Diamond, Club, Heart, and Spade card",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "blueprint": JokerDefinition(
        id="blueprint", name="Blueprint",
        description="Copies ability of Joker to the right",
        rarity=JokerRarity.RARE, base_cost=10,
    ),
    "wee_joker": JokerDefinition(
        id="wee_joker", name="Wee Joker",
        description="This Joker gains +8 Chips when each played 2 is scored",
        rarity=JokerRarity.RARE, base_cost=8,
    ),
    "merry_andy": JokerDefinition(
        id="merry_andy", name="Merry Andy",
        description="+3 discards each round, -1 hand size",
        rarity=JokerRarity.UNCOMMON, base_cost=7,
    ),
    "oops_all_6s": JokerDefinition(
        id="oops_all_6s", name="Oops! All 6s",
        description="Doubles all listed probabilities",
        rarity=JokerRarity.UNCOMMON, base_cost=4,
    ),
    "the_idol": JokerDefinition(
        id="the_idol", name="The Idol",
        description="Each played card of specific rank and suit gives X2 Mult when scored, card changes every round",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "seeing_double": JokerDefinition(
        id="seeing_double", name="Seeing Double",
        description="X2 Mult if played hand has a scoring Club card and a scoring card of any other suit",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "matador": JokerDefinition(
        id="matador", name="Matador",
        description="Earn $8 if played hand triggers the Boss Blind ability",
        rarity=JokerRarity.UNCOMMON, base_cost=7,
    ),
    "hit_the_road": JokerDefinition(
        id="hit_the_road", name="Hit the Road",
        description="This Joker gains X0.5 Mult for every Jack discarded this round",
        rarity=JokerRarity.RARE, base_cost=8,
    ),
    # 131-140
    "the_duo": JokerDefinition(
        id="the_duo", name="The Duo",
        description="X2 Mult if played hand contains a Pair",
        rarity=JokerRarity.RARE, base_cost=8,
    ),
    "the_trio": JokerDefinition(
        id="the_trio", name="The Trio",
        description="X3 Mult if played hand contains a Three of a Kind",
        rarity=JokerRarity.RARE, base_cost=8,
    ),
    "the_family": JokerDefinition(
        id="the_family", name="The Family",
        description="X4 Mult if played hand contains a Four of a Kind",
        rarity=JokerRarity.RARE, base_cost=8,
    ),
    "the_order": JokerDefinition(
        id="the_order", name="The Order",
        description="X3 Mult if played hand contains a Straight",
        rarity=JokerRarity.RARE, base_cost=8,
    ),
    "the_tribe": JokerDefinition(
        id="the_tribe", name="The Tribe",
        description="X2 Mult if played hand contains a Flush",
        rarity=JokerRarity.RARE, base_cost=8,
    ),
    "stuntman": JokerDefinition(
        id="stuntman", name="Stuntman",
        description="+250 Chips, -2 hand size",
        rarity=JokerRarity.RARE, base_cost=7,
    ),
    "invisible_joker": JokerDefinition(
        id="invisible_joker", name="Invisible Joker",
        description="After 2 rounds, sell this card to Duplicate a random Joker",
        rarity=JokerRarity.RARE, base_cost=8,
    ),
    "brainstorm": JokerDefinition(
        id="brainstorm", name="Brainstorm",
        description="Copies the ability of leftmost Joker",
        rarity=JokerRarity.RARE, base_cost=10,
    ),
    "satellite": JokerDefinition(
        id="satellite", name="Satellite",
        description="Earn $1 at end of round per unique Planet card used this run",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "shoot_the_moon": JokerDefinition(
        id="shoot_the_moon", name="Shoot the Moon",
        description="Each Queen held in hand gives +13 Mult",
        rarity=JokerRarity.COMMON, base_cost=5,
    ),
    # 141-150
    "drivers_license": JokerDefinition(
        id="drivers_license", name="Driver's License",
        description="X3 Mult if you have at least 16 Enhanced cards in your full deck",
        rarity=JokerRarity.RARE, base_cost=7,
    ),
    "cartomancer": JokerDefinition(
        id="cartomancer", name="Cartomancer",
        description="Create a Tarot card when Blind is selected",
        rarity=JokerRarity.UNCOMMON, base_cost=6,
    ),
    "astronomer": JokerDefinition(
        id="astronomer", name="Astronomer",
        description="All Planet cards and Celestial Packs in the shop are free",
        rarity=JokerRarity.UNCOMMON, base_cost=8,
    ),
    "burnt_joker": JokerDefinition(
        id="burnt_joker", name="Burnt Joker",
        description="Upgrade the level of the first discarded poker hand each round",
        rarity=JokerRarity.RARE, base_cost=8,
    ),
    "bootstraps": JokerDefinition(
        id="bootstraps", name="Bootstraps",
        description="+2 Mult for every $5 you have",
        rarity=JokerRarity.UNCOMMON, base_cost=7,
    ),
    "canio": JokerDefinition(
        id="canio", name="Canio",
        description="This Joker gains X1 Mult when a face card is destroyed",
        rarity=JokerRarity.LEGENDARY, base_cost=0,
    ),
    "triboulet": JokerDefinition(
        id="triboulet", name="Triboulet",
        description="Played Kings and Queens each give X2 Mult when scored",
        rarity=JokerRarity.LEGENDARY, base_cost=0,
    ),
    "yorick": JokerDefinition(
        id="yorick", name="Yorick",
        description="This Joker gains X1 Mult every 23 cards discarded",
        rarity=JokerRarity.LEGENDARY, base_cost=0,
    ),
    "chicot": JokerDefinition(
        id="chicot", name="Chicot",
        description="Disables effect of every Boss Blind",
        rarity=JokerRarity.LEGENDARY, base_cost=0,
    ),
    "perkeo": JokerDefinition(
        id="perkeo", name="Perkeo",
        description="Creates a Negative copy of 1 random consumable card at the end of the shop",
        rarity=JokerRarity.LEGENDARY, base_cost=0,
    ),
}


def create_joker(joker_id: str) -> JokerInstance:
    """Create a joker instance by ID."""
    if joker_id not in JOKERS:
        raise ValueError(f"Unknown joker: {joker_id}")
    return JOKERS[joker_id].create_instance()


def get_all_joker_ids() -> list[str]:
    """Get list of all joker IDs."""
    return list(JOKERS.keys())
