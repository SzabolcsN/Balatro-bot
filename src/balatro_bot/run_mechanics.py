"""Run mechanics: Stakes, Blinds, Antes, and Tags.

This module defines the core progression systems in Balatro:
- Stakes: Difficulty levels that stack penalties
- Blinds: Small, Big, and Boss blinds with chip requirements
- Antes: Progression through 8 antes (+ endless mode)
- Tags: Rewards for skipping blinds
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# =============================================================================
# Stakes (Difficulty Levels)
# =============================================================================


class StakeLevel(Enum):
    """Difficulty levels in ascending order."""

    WHITE = 1  # Base difficulty
    RED = 2  # Small blind gives no money
    GREEN = 3  # Faster scaling
    BLACK = 4  # Eternal sticker chance
    BLUE = 5  # -1 discard per round
    PURPLE = 6  # Even faster scaling
    ORANGE = 7  # Perishable sticker chance
    GOLD = 8  # Rental sticker chance


@dataclass
class Stake:
    """A stake difficulty definition."""

    level: StakeLevel
    name: str
    color: str
    description: str
    # Cumulative modifiers (each stake includes all previous)
    small_blind_reward: bool = True  # False at Red+
    score_scaling: float = 1.0  # Multiplier for chip requirements
    discards_penalty: int = 0  # Reduced discards per round
    eternal_chance: float = 0.0  # Chance for Eternal sticker
    perishable_chance: float = 0.0  # Chance for Perishable sticker
    rental_chance: float = 0.0  # Chance for Rental sticker


# Stake definitions with cumulative effects
STAKES: dict[StakeLevel, Stake] = {
    StakeLevel.WHITE: Stake(
        level=StakeLevel.WHITE,
        name="White Stake",
        color="white",
        description="Base difficulty",
    ),
    StakeLevel.RED: Stake(
        level=StakeLevel.RED,
        name="Red Stake",
        color="red",
        description="Small Blind gives no reward money",
        small_blind_reward=False,
    ),
    StakeLevel.GREEN: Stake(
        level=StakeLevel.GREEN,
        name="Green Stake",
        color="green",
        description="Required score scales faster",
        small_blind_reward=False,
        score_scaling=1.5,  # Approximate scaling increase
    ),
    StakeLevel.BLACK: Stake(
        level=StakeLevel.BLACK,
        name="Black Stake",
        color="black",
        description="Jokers may have Eternal sticker (30% chance)",
        small_blind_reward=False,
        score_scaling=1.5,
        eternal_chance=0.30,
    ),
    StakeLevel.BLUE: Stake(
        level=StakeLevel.BLUE,
        name="Blue Stake",
        color="blue",
        description="-1 discard per round",
        small_blind_reward=False,
        score_scaling=1.5,
        eternal_chance=0.30,
        discards_penalty=1,
    ),
    StakeLevel.PURPLE: Stake(
        level=StakeLevel.PURPLE,
        name="Purple Stake",
        color="purple",
        description="Required score scales even faster",
        small_blind_reward=False,
        score_scaling=2.0,  # Even higher scaling
        eternal_chance=0.30,
        discards_penalty=1,
    ),
    StakeLevel.ORANGE: Stake(
        level=StakeLevel.ORANGE,
        name="Orange Stake",
        color="orange",
        description="Jokers may have Perishable sticker (30% chance)",
        small_blind_reward=False,
        score_scaling=2.0,
        eternal_chance=0.30,
        discards_penalty=1,
        perishable_chance=0.30,
    ),
    StakeLevel.GOLD: Stake(
        level=StakeLevel.GOLD,
        name="Gold Stake",
        color="gold",
        description="Jokers may have Rental sticker ($3/round, 30% chance)",
        small_blind_reward=False,
        score_scaling=2.0,
        eternal_chance=0.30,
        discards_penalty=1,
        perishable_chance=0.30,
        rental_chance=0.30,
    ),
}


# =============================================================================
# Joker Stickers (from Stakes)
# =============================================================================


class JokerSticker(Enum):
    """Stickers that can be applied to Jokers at higher stakes."""

    NONE = "none"
    ETERNAL = "eternal"  # Cannot be sold or destroyed
    PERISHABLE = "perishable"  # Debuffed after 5 rounds
    RENTAL = "rental"  # Costs $3 per round


# =============================================================================
# Blinds
# =============================================================================


class BlindType(Enum):
    """Types of blinds in a round."""

    SMALL = "small"
    BIG = "big"
    BOSS = "boss"


@dataclass
class Blind:
    """A blind configuration."""

    blind_type: BlindType
    name: str
    chip_multiplier: float  # Multiplier of base ante chips
    can_skip: bool = True
    reward_multiplier: float = 1.0  # Money reward multiplier
    effect_id: str | None = None  # Boss blind effect


# Standard blinds (Small and Big have no special effects)
SMALL_BLIND = Blind(
    blind_type=BlindType.SMALL,
    name="Small Blind",
    chip_multiplier=1.0,
    can_skip=True,
    reward_multiplier=1.0,
)

BIG_BLIND = Blind(
    blind_type=BlindType.BIG,
    name="Big Blind",
    chip_multiplier=1.5,
    can_skip=True,
    reward_multiplier=1.0,
)


# =============================================================================
# Boss Blinds
# =============================================================================


@dataclass
class BossBlind:
    """A boss blind with special effects."""

    id: str
    name: str
    description: str
    chip_multiplier: float = 2.0
    # Effect type for implementation
    effect_type: str = "none"


# All boss blinds
BOSS_BLINDS: dict[str, BossBlind] = {
    # Debuff effects
    "the_hook": BossBlind(
        id="the_hook",
        name="The Hook",
        description="Discards 2 random cards per hand played",
        effect_type="discard_random",
    ),
    "the_ox": BossBlind(
        id="the_ox",
        name="The Ox",
        description="Playing a #1 most played hand sets money to $0",
        effect_type="money_penalty",
    ),
    "the_house": BossBlind(
        id="the_house",
        name="The House",
        description="All cards are drawn face down",
        effect_type="face_down",
    ),
    "the_wall": BossBlind(
        id="the_wall",
        name="The Wall",
        description="Extra large blind",
        chip_multiplier=4.0,
        effect_type="large_blind",
    ),
    "the_wheel": BossBlind(
        id="the_wheel",
        name="The Wheel",
        description="1 in 7 chance to draw face down",
        effect_type="random_face_down",
    ),
    "the_arm": BossBlind(
        id="the_arm",
        name="The Arm",
        description="Decrease level of played poker hand by 1",
        effect_type="level_down",
    ),
    "the_club": BossBlind(
        id="the_club",
        name="The Club",
        description="All Club cards are debuffed",
        effect_type="debuff_suit",
    ),
    "the_fish": BossBlind(
        id="the_fish",
        name="The Fish",
        description="Cards drawn face down after each hand",
        effect_type="face_down_after",
    ),
    "the_psychic": BossBlind(
        id="the_psychic",
        name="The Psychic",
        description="Must play 5 cards",
        effect_type="force_five",
    ),
    "the_goad": BossBlind(
        id="the_goad",
        name="The Goad",
        description="All Spade cards are debuffed",
        effect_type="debuff_suit",
    ),
    "the_water": BossBlind(
        id="the_water",
        name="The Water",
        description="Start with 0 discards",
        effect_type="no_discards",
    ),
    "the_window": BossBlind(
        id="the_window",
        name="The Window",
        description="All Diamond cards are debuffed",
        effect_type="debuff_suit",
    ),
    "the_manacle": BossBlind(
        id="the_manacle",
        name="The Manacle",
        description="-1 hand size",
        effect_type="hand_size_penalty",
    ),
    "the_eye": BossBlind(
        id="the_eye",
        name="The Eye",
        description="No repeat hand types this round",
        effect_type="no_repeat_hands",
    ),
    "the_mouth": BossBlind(
        id="the_mouth",
        name="The Mouth",
        description="Only play one hand type this round",
        effect_type="one_hand_type",
    ),
    "the_plant": BossBlind(
        id="the_plant",
        name="The Plant",
        description="All face cards are debuffed",
        effect_type="debuff_face",
    ),
    "the_serpent": BossBlind(
        id="the_serpent",
        name="The Serpent",
        description="After play or discard, always draw to full hand",
        effect_type="always_draw",
    ),
    "the_pillar": BossBlind(
        id="the_pillar",
        name="The Pillar",
        description="Cards played previously are debuffed",
        effect_type="debuff_played",
    ),
    "the_needle": BossBlind(
        id="the_needle",
        name="The Needle",
        description="Play only 1 hand",
        effect_type="one_hand",
    ),
    "the_head": BossBlind(
        id="the_head",
        name="The Head",
        description="All Heart cards are debuffed",
        effect_type="debuff_suit",
    ),
    "the_tooth": BossBlind(
        id="the_tooth",
        name="The Tooth",
        description="Lose $1 per card played",
        effect_type="money_per_card",
    ),
    "the_flint": BossBlind(
        id="the_flint",
        name="The Flint",
        description="Base chips and mult are halved",
        effect_type="halved_base",
    ),
    "the_mark": BossBlind(
        id="the_mark",
        name="The Mark",
        description="All face cards are drawn face down",
        effect_type="face_cards_down",
    ),
    # Showdown Blinds (Ante 8+)
    "crimson_heart": BossBlind(
        id="crimson_heart",
        name="Crimson Heart",
        description="One random Joker disabled per hand",
        chip_multiplier=2.0,
        effect_type="disable_joker",
    ),
    "cerulean_bell": BossBlind(
        id="cerulean_bell",
        name="Cerulean Bell",
        description="Forces 1 card to always be selected",
        chip_multiplier=2.0,
        effect_type="force_select",
    ),
    "verdant_leaf": BossBlind(
        id="verdant_leaf",
        name="Verdant Leaf",
        description="All cards debuffed until 1 Joker sold",
        chip_multiplier=2.0,
        effect_type="debuff_until_sell",
    ),
    "violet_vessel": BossBlind(
        id="violet_vessel",
        name="Violet Vessel",
        description="Very large blind",
        chip_multiplier=6.0,
        effect_type="very_large",
    ),
    "amber_acorn": BossBlind(
        id="amber_acorn",
        name="Amber Acorn",
        description="Flips and shuffles all Jokers",
        chip_multiplier=2.0,
        effect_type="shuffle_jokers",
    ),
}


# =============================================================================
# Ante Progression
# =============================================================================


# Base chip requirements by ante (White Stake)
BASE_ANTE_CHIPS: dict[int, int] = {
    1: 300,
    2: 800,
    3: 2000,
    4: 5000,
    5: 11000,
    6: 20000,
    7: 35000,
    8: 50000,
}


def calculate_blind_chips(
    ante: int,
    blind_type: BlindType,
    stake: StakeLevel = StakeLevel.WHITE,
    boss_blind: BossBlind | None = None,
) -> int:
    """Calculate chip requirement for a blind.

    Args:
        ante: Current ante number (1-8, or higher for endless)
        blind_type: Small, Big, or Boss
        stake: Current stake level
        boss_blind: Boss blind definition (for Boss blinds)

    Returns:
        Required chips to beat the blind
    """
    # Get base chips for ante
    if ante <= 8:
        base_chips = BASE_ANTE_CHIPS[ante]
    else:
        # Endless mode formula
        base_chips = _calculate_endless_chips(ante)

    # Apply stake scaling
    stake_def = STAKES[stake]
    base_chips = int(base_chips * stake_def.score_scaling)

    # Apply blind multiplier
    if blind_type == BlindType.SMALL:
        multiplier = SMALL_BLIND.chip_multiplier
    elif blind_type == BlindType.BIG:
        multiplier = BIG_BLIND.chip_multiplier
    else:  # Boss
        multiplier = boss_blind.chip_multiplier if boss_blind else 2.0

    return int(base_chips * multiplier)


def _calculate_endless_chips(ante: int) -> int:
    """Calculate chip requirement for endless mode (Ante 9+).

    Formula: Ante8 × (1.6 + 0.75(ante-8))^(1 + 0.2(ante-8)) ^ (ante-8)

    Results are rounded to 2 significant digits.
    """
    if ante <= 8:
        return BASE_ANTE_CHIPS[ante]

    ante_8_chips = BASE_ANTE_CHIPS[8]
    n = ante - 8

    # Calculate scaling factor
    base = 1.6 + (0.75 * n)
    exponent = 1 + (0.2 * n)
    scaling = (base ** exponent) ** n

    result = int(ante_8_chips * scaling)

    # Round to 2 significant digits
    if result >= 100:
        magnitude = 10 ** (len(str(result)) - 2)
        result = round(result / magnitude) * magnitude

    return result


def calculate_blind_reward(
    ante: int,
    blind_type: BlindType,
    stake: StakeLevel = StakeLevel.WHITE,
) -> int:
    """Calculate money reward for beating a blind.

    Args:
        ante: Current ante number
        blind_type: Small, Big, or Boss
        stake: Current stake level

    Returns:
        Money earned for beating the blind
    """
    # Base rewards
    base_rewards = {
        BlindType.SMALL: 3,
        BlindType.BIG: 4,
        BlindType.BOSS: 5,
    }
    base = base_rewards[blind_type]

    # Add ante bonus
    reward = base + (ante - 1)

    # Red+ stake: Small blind gives no reward
    if blind_type == BlindType.SMALL:
        stake_def = STAKES[stake]
        if not stake_def.small_blind_reward:
            return 0

    return reward


# =============================================================================
# Tags (Skip Rewards)
# =============================================================================


class TagType(Enum):
    """Types of tags that can be earned."""

    # Joker tags
    UNCOMMON = "uncommon"
    RARE = "rare"
    NEGATIVE = "negative"
    FOIL = "foil"
    HOLOGRAPHIC = "holographic"
    POLYCHROME = "polychrome"

    # Economy tags
    INVESTMENT = "investment"
    HANDY = "handy"
    GARBAGE = "garbage"
    SPEED = "speed"
    ECONOMY = "economy"

    # Shop tags
    VOUCHER = "voucher"
    COUPON = "coupon"
    D6 = "d6"

    # Booster tags
    STANDARD = "standard"
    CHARM = "charm"
    METEOR = "meteor"
    BUFFOON = "buffoon"
    ETHEREAL = "ethereal"

    # Special tags
    BOSS = "boss"
    DOUBLE = "double"
    JUGGLE = "juggle"
    TOP_UP = "top_up"
    ORBITAL = "orbital"


@dataclass
class Tag:
    """A tag reward definition."""

    tag_type: TagType
    name: str
    description: str
    # Effect timing
    immediate: bool = False  # Applied immediately vs next shop
    # Effect details
    free_joker_rarity: str | None = None
    free_joker_edition: str | None = None
    free_pack_type: str | None = None
    money_bonus: int = 0
    money_multiplier: float = 1.0
    per_hand_bonus: int = 0
    per_discard_bonus: int = 0
    per_skip_bonus: int = 0
    hand_size_bonus: int = 0
    hand_level_bonus: int = 0


TAGS: dict[TagType, Tag] = {
    # Joker tags - free joker in next shop
    TagType.UNCOMMON: Tag(
        tag_type=TagType.UNCOMMON,
        name="Uncommon Tag",
        description="Next shop has a free Uncommon Joker",
        free_joker_rarity="uncommon",
    ),
    TagType.RARE: Tag(
        tag_type=TagType.RARE,
        name="Rare Tag",
        description="Next shop has a free Rare Joker",
        free_joker_rarity="rare",
    ),
    TagType.NEGATIVE: Tag(
        tag_type=TagType.NEGATIVE,
        name="Negative Tag",
        description="Next base Joker becomes Negative and free",
        free_joker_edition="negative",
    ),
    TagType.FOIL: Tag(
        tag_type=TagType.FOIL,
        name="Foil Tag",
        description="Next base Joker becomes Foil and free",
        free_joker_edition="foil",
    ),
    TagType.HOLOGRAPHIC: Tag(
        tag_type=TagType.HOLOGRAPHIC,
        name="Holographic Tag",
        description="Next base Joker becomes Holographic and free",
        free_joker_edition="holographic",
    ),
    TagType.POLYCHROME: Tag(
        tag_type=TagType.POLYCHROME,
        name="Polychrome Tag",
        description="Next base Joker becomes Polychrome and free",
        free_joker_edition="polychrome",
    ),
    # Economy tags
    TagType.INVESTMENT: Tag(
        tag_type=TagType.INVESTMENT,
        name="Investment Tag",
        description="Earn $25 after beating next Boss Blind",
        money_bonus=25,
    ),
    TagType.HANDY: Tag(
        tag_type=TagType.HANDY,
        name="Handy Tag",
        description="Earn $1 per hand played this run",
        immediate=True,
        per_hand_bonus=1,
    ),
    TagType.GARBAGE: Tag(
        tag_type=TagType.GARBAGE,
        name="Garbage Tag",
        description="Earn $1 per unused discard this run",
        immediate=True,
        per_discard_bonus=1,
    ),
    TagType.SPEED: Tag(
        tag_type=TagType.SPEED,
        name="Speed Tag",
        description="Earn $5 per blind skipped this run",
        immediate=True,
        per_skip_bonus=5,
    ),
    TagType.ECONOMY: Tag(
        tag_type=TagType.ECONOMY,
        name="Economy Tag",
        description="Double your money (max $40 added)",
        immediate=True,
        money_multiplier=2.0,
    ),
    # Shop tags
    TagType.VOUCHER: Tag(
        tag_type=TagType.VOUCHER,
        name="Voucher Tag",
        description="Adds a Voucher to the next shop",
    ),
    TagType.COUPON: Tag(
        tag_type=TagType.COUPON,
        name="Coupon Tag",
        description="Next shop's items are free (except Vouchers)",
    ),
    TagType.D6: Tag(
        tag_type=TagType.D6,
        name="D6 Tag",
        description="Next shop's rerolls start at $0",
    ),
    # Booster tags - immediate free pack
    TagType.STANDARD: Tag(
        tag_type=TagType.STANDARD,
        name="Standard Tag",
        description="Opens a free Mega Standard Pack",
        immediate=True,
        free_pack_type="standard_mega",
    ),
    TagType.CHARM: Tag(
        tag_type=TagType.CHARM,
        name="Charm Tag",
        description="Opens a free Mega Arcana Pack",
        immediate=True,
        free_pack_type="arcana_mega",
    ),
    TagType.METEOR: Tag(
        tag_type=TagType.METEOR,
        name="Meteor Tag",
        description="Opens a free Mega Celestial Pack",
        immediate=True,
        free_pack_type="celestial_mega",
    ),
    TagType.BUFFOON: Tag(
        tag_type=TagType.BUFFOON,
        name="Buffoon Tag",
        description="Opens a free Mega Buffoon Pack",
        immediate=True,
        free_pack_type="buffoon_mega",
    ),
    TagType.ETHEREAL: Tag(
        tag_type=TagType.ETHEREAL,
        name="Ethereal Tag",
        description="Opens a free Spectral Pack",
        immediate=True,
        free_pack_type="spectral_normal",
    ),
    # Special tags
    TagType.BOSS: Tag(
        tag_type=TagType.BOSS,
        name="Boss Tag",
        description="Re-rolls the next Boss Blind",
    ),
    TagType.DOUBLE: Tag(
        tag_type=TagType.DOUBLE,
        name="Double Tag",
        description="Copies the next selected tag",
    ),
    TagType.JUGGLE: Tag(
        tag_type=TagType.JUGGLE,
        name="Juggle Tag",
        description="+3 hand size for next round only",
        hand_size_bonus=3,
    ),
    TagType.TOP_UP: Tag(
        tag_type=TagType.TOP_UP,
        name="Top-up Tag",
        description="Create up to 2 Common Jokers",
        immediate=True,
    ),
    TagType.ORBITAL: Tag(
        tag_type=TagType.ORBITAL,
        name="Orbital Tag",
        description="Upgrade a random poker hand by 3 levels",
        immediate=True,
        hand_level_bonus=3,
    ),
}


# =============================================================================
# Run State
# =============================================================================


@dataclass
class RunState:
    """State for tracking run-wide statistics and effects."""

    # Current progress
    ante: int = 1
    current_blind: BlindType = BlindType.SMALL
    stake: StakeLevel = StakeLevel.WHITE

    # Statistics
    hands_played: int = 0
    discards_used: int = 0
    discards_unused: int = 0
    blinds_skipped: int = 0

    # Active tags (for next shop/blind)
    active_tags: list[TagType] = field(default_factory=list)

    # Boss blind for current ante
    current_boss_id: str | None = None

    # Temporary effects
    temp_hand_size_bonus: int = 0  # From Juggle tag
    next_shop_free_items: bool = False  # From Coupon tag
    next_shop_free_reroll: bool = False  # From D6 tag
    investment_pending: bool = False  # From Investment tag

    def advance_blind(self) -> None:
        """Advance to the next blind."""
        if self.current_blind == BlindType.SMALL:
            self.current_blind = BlindType.BIG
        elif self.current_blind == BlindType.BIG:
            self.current_blind = BlindType.BOSS
        else:
            # Beat boss, advance ante
            self.ante += 1
            self.current_blind = BlindType.SMALL
            self.current_boss_id = None
            # Reset temporary effects
            self.temp_hand_size_bonus = 0

    def skip_blind(self) -> None:
        """Skip the current blind (Small or Big only)."""
        if self.current_blind == BlindType.BOSS:
            raise ValueError("Cannot skip Boss blind")
        self.blinds_skipped += 1
        self.advance_blind()

    def get_chip_requirement(self, boss_blind: BossBlind | None = None) -> int:
        """Get chip requirement for current blind."""
        return calculate_blind_chips(
            self.ante,
            self.current_blind,
            self.stake,
            boss_blind,
        )

    def get_blind_reward(self) -> int:
        """Get money reward for beating current blind."""
        return calculate_blind_reward(
            self.ante,
            self.current_blind,
            self.stake,
        )

    def is_game_won(self) -> bool:
        """Check if the run is won (beat Ante 8)."""
        return self.ante > 8

    def is_endless_mode(self) -> bool:
        """Check if in endless mode (past Ante 8)."""
        return self.ante > 8


# =============================================================================
# Helper Functions
# =============================================================================


def get_all_stake_levels() -> list[StakeLevel]:
    """Get all stake levels in order."""
    return list(StakeLevel)


def get_all_boss_blind_ids() -> list[str]:
    """Get all boss blind IDs."""
    return list(BOSS_BLINDS.keys())


def get_all_tag_types() -> list[TagType]:
    """Get all tag types."""
    return list(TagType)


def get_showdown_blinds() -> list[str]:
    """Get boss blinds that appear in showdown (Ante 8+)."""
    return [
        "crimson_heart",
        "cerulean_bell",
        "verdant_leaf",
        "violet_vessel",
        "amber_acorn",
    ]


def create_run_state(stake: StakeLevel = StakeLevel.WHITE) -> RunState:
    """Create a new run state."""
    return RunState(stake=stake)
