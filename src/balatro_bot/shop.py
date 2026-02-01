"""Shop and Voucher system for Balatro.

The shop appears between blinds and offers:
- 2 random cards (Jokers, Tarots, Planets)
- 2 Booster Packs
- 1 Voucher

Vouchers provide permanent upgrades that affect gameplay.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# =============================================================================
# Voucher System
# =============================================================================


class VoucherTier(Enum):
    """Voucher tier - base or upgraded."""

    BASE = "base"
    UPGRADED = "upgraded"


@dataclass
class Voucher:
    """A voucher that provides a permanent upgrade."""

    id: str
    name: str
    description: str
    cost: int = 10
    tier: VoucherTier = VoucherTier.BASE
    # ID of the base voucher this upgrades (None for base vouchers)
    upgrades_from: str | None = None
    # Unlock condition description
    unlock_condition: str | None = None


# Base Vouchers ($10 each)
BASE_VOUCHERS: dict[str, Voucher] = {
    # Shop slots
    "overstock": Voucher(
        id="overstock",
        name="Overstock",
        description="+1 card slot in shop",
    ),
    # Discounts
    "clearance_sale": Voucher(
        id="clearance_sale",
        name="Clearance Sale",
        description="All cards and packs in shop are 25% off",
    ),
    # Card appearance
    "hone": Voucher(
        id="hone",
        name="Hone",
        description="Foil, Holographic, and Polychrome cards appear 2X more often",
    ),
    # Reroll
    "reroll_surplus": Voucher(
        id="reroll_surplus",
        name="Reroll Surplus",
        description="Rerolls cost $2 less",
    ),
    # Consumable slots
    "crystal_ball": Voucher(
        id="crystal_ball",
        name="Crystal Ball",
        description="+1 consumable slot",
    ),
    # Celestial targeting
    "telescope": Voucher(
        id="telescope",
        name="Telescope",
        description="Celestial Packs always contain the Planet for your most played hand",
    ),
    # Hands per round
    "grabber": Voucher(
        id="grabber",
        name="Grabber",
        description="Permanently gain +1 hand per round",
    ),
    # Discards per round
    "wasteful": Voucher(
        id="wasteful",
        name="Wasteful",
        description="Permanently gain +1 discard per round",
    ),
    # Card frequency
    "tarot_merchant": Voucher(
        id="tarot_merchant",
        name="Tarot Merchant",
        description="Tarot cards appear 2X more frequently in the shop",
    ),
    "planet_merchant": Voucher(
        id="planet_merchant",
        name="Planet Merchant",
        description="Planet cards appear 2X more frequently in the shop",
    ),
    # Interest
    "seed_money": Voucher(
        id="seed_money",
        name="Seed Money",
        description="Raise interest cap to $10 per round",
    ),
    # Blank (unlocks Antimatter)
    "blank": Voucher(
        id="blank",
        name="Blank",
        description="Does nothing",
    ),
    # Playing cards in shop
    "magic_trick": Voucher(
        id="magic_trick",
        name="Magic Trick",
        description="Playing cards can be purchased from the shop",
    ),
    # Ante reduction
    "hieroglyph": Voucher(
        id="hieroglyph",
        name="Hieroglyph",
        description="-1 Ante, -1 hand each round",
    ),
    # Boss reroll
    "directors_cut": Voucher(
        id="directors_cut",
        name="Director's Cut",
        description="Reroll Boss Blind once per Ante for $10",
    ),
    # Hand size
    "paint_brush": Voucher(
        id="paint_brush",
        name="Paint Brush",
        description="+1 hand size",
    ),
}


# Upgraded Vouchers ($10 each, require base voucher + unlock condition)
UPGRADED_VOUCHERS: dict[str, Voucher] = {
    "overstock_plus": Voucher(
        id="overstock_plus",
        name="Overstock Plus",
        description="+1 card slot in shop (4 total)",
        tier=VoucherTier.UPGRADED,
        upgrades_from="overstock",
        unlock_condition="Spend $2,500 total",
    ),
    "liquidation": Voucher(
        id="liquidation",
        name="Liquidation",
        description="All cards and packs in shop are 50% off",
        tier=VoucherTier.UPGRADED,
        upgrades_from="clearance_sale",
        unlock_condition="Redeem 10 vouchers",
    ),
    "glow_up": Voucher(
        id="glow_up",
        name="Glow Up",
        description="Foil, Holographic, and Polychrome cards appear 4X more often",
        tier=VoucherTier.UPGRADED,
        upgrades_from="hone",
        unlock_condition="Have 5+ Jokers with editions",
    ),
    "reroll_glut": Voucher(
        id="reroll_glut",
        name="Reroll Glut",
        description="Rerolls cost $4 less total",
        tier=VoucherTier.UPGRADED,
        upgrades_from="reroll_surplus",
        unlock_condition="Reroll 100 times",
    ),
    "omen_globe": Voucher(
        id="omen_globe",
        name="Omen Globe",
        description="Spectral cards may appear in Arcana Packs",
        tier=VoucherTier.UPGRADED,
        upgrades_from="crystal_ball",
        unlock_condition="Use 25 Tarot cards",
    ),
    "observatory": Voucher(
        id="observatory",
        name="Observatory",
        description="Planet cards give X1.5 Mult for their hand type",
        tier=VoucherTier.UPGRADED,
        upgrades_from="telescope",
        unlock_condition="Use 25 Planet cards",
    ),
    "nacho_tong": Voucher(
        id="nacho_tong",
        name="Nacho Tong",
        description="Permanently gain +1 hand per round (+2 total)",
        tier=VoucherTier.UPGRADED,
        upgrades_from="grabber",
        unlock_condition="Play 2,500 cards",
    ),
    "recyclomancy": Voucher(
        id="recyclomancy",
        name="Recyclomancy",
        description="Permanently gain +1 discard per round (+2 total)",
        tier=VoucherTier.UPGRADED,
        upgrades_from="wasteful",
        unlock_condition="Discard 2,500 cards",
    ),
    "tarot_tycoon": Voucher(
        id="tarot_tycoon",
        name="Tarot Tycoon",
        description="Tarot cards appear 4X more frequently in the shop",
        tier=VoucherTier.UPGRADED,
        upgrades_from="tarot_merchant",
        unlock_condition="Buy 50 Tarot cards",
    ),
    "planet_tycoon": Voucher(
        id="planet_tycoon",
        name="Planet Tycoon",
        description="Planet cards appear 4X more frequently in the shop",
        tier=VoucherTier.UPGRADED,
        upgrades_from="planet_merchant",
        unlock_condition="Buy 50 Planet cards",
    ),
    "money_tree": Voucher(
        id="money_tree",
        name="Money Tree",
        description="Raise interest cap to $20 per round",
        tier=VoucherTier.UPGRADED,
        upgrades_from="seed_money",
        unlock_condition="Max interest for 10 consecutive rounds",
    ),
    "antimatter": Voucher(
        id="antimatter",
        name="Antimatter",
        description="+1 Joker slot",
        tier=VoucherTier.UPGRADED,
        upgrades_from="blank",
        unlock_condition="Redeem Blank 10 times",
    ),
    "illusion": Voucher(
        id="illusion",
        name="Illusion",
        description="Playing cards may have Enhancements, Editions, or Seals",
        tier=VoucherTier.UPGRADED,
        upgrades_from="magic_trick",
        unlock_condition="Buy 20 playing cards",
    ),
    "petroglyph": Voucher(
        id="petroglyph",
        name="Petroglyph",
        description="-1 Ante again, -1 discard each round",
        tier=VoucherTier.UPGRADED,
        upgrades_from="hieroglyph",
        unlock_condition="Reach Ante 12",
    ),
    "retcon": Voucher(
        id="retcon",
        name="Retcon",
        description="Reroll Boss Blind unlimited times for $10 each",
        tier=VoucherTier.UPGRADED,
        upgrades_from="directors_cut",
        unlock_condition="Discover 25 different Blinds",
    ),
    "palette": Voucher(
        id="palette",
        name="Palette",
        description="+1 hand size (+2 total)",
        tier=VoucherTier.UPGRADED,
        upgrades_from="paint_brush",
        unlock_condition="Reduce hand size to 5 cards",
    ),
}


# Combined dictionary of all vouchers
VOUCHERS: dict[str, Voucher] = {**BASE_VOUCHERS, **UPGRADED_VOUCHERS}


# =============================================================================
# Shop Configuration
# =============================================================================


class ShopItemType(Enum):
    """Types of items that can appear in the shop."""

    JOKER = "joker"
    TAROT = "tarot"
    PLANET = "planet"
    PLAYING_CARD = "playing_card"
    BOOSTER_PACK = "booster_pack"
    VOUCHER = "voucher"


class JokerRarity(Enum):
    """Joker rarity tiers."""

    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    LEGENDARY = "legendary"


@dataclass
class ShopConfig:
    """Configuration for shop behavior."""

    # Number of card slots (affected by Overstock vouchers)
    base_card_slots: int = 2
    max_card_slots: int = 4

    # Base reroll cost
    base_reroll_cost: int = 5
    reroll_cost_increase: int = 1  # Per reroll

    # Card appearance probabilities (base, before voucher modifiers)
    joker_probability: float = 0.714  # 71.4%
    tarot_probability: float = 0.143  # 14.3%
    planet_probability: float = 0.143  # 14.3%

    # Joker rarity probabilities
    joker_common_prob: float = 0.70  # 70%
    joker_uncommon_prob: float = 0.25  # 25%
    joker_rare_prob: float = 0.05  # 5%
    # Legendary jokers only from special sources

    # Number of booster packs shown
    booster_pack_slots: int = 2

    # Base prices
    playing_card_base_cost: int = 1
    common_joker_base_cost: int = 4
    uncommon_joker_base_cost: int = 6
    rare_joker_base_cost: int = 8
    legendary_joker_base_cost: int = 20
    tarot_base_cost: int = 3
    planet_base_cost: int = 3
    voucher_cost: int = 10

    # Edition cost additions
    foil_cost_add: int = 2
    holo_cost_add: int = 3
    polychrome_cost_add: int = 5
    negative_cost_add: int = 5

    # Interest mechanics
    base_interest_cap: int = 5  # $5 max interest by default
    interest_rate: float = 0.20  # 20% of money, up to cap


@dataclass
class ShopState:
    """Current state of the shop."""

    # Active vouchers (redeemed this run)
    redeemed_vouchers: list[str] = field(default_factory=list)

    # Current card slots (base + voucher bonuses)
    card_slots: int = 2

    # Current reroll cost (resets each shop visit)
    current_reroll_cost: int = 5

    # Discount multiplier (1.0 = no discount, 0.75 = 25% off, 0.5 = 50% off)
    discount_multiplier: float = 1.0

    # Extra hands/discards from vouchers
    bonus_hands: int = 0
    bonus_discards: int = 0

    # Hand size bonus from vouchers
    bonus_hand_size: int = 0

    # Interest cap
    interest_cap: int = 5

    # Joker slots bonus
    bonus_joker_slots: int = 0

    # Consumable slots bonus
    bonus_consumable_slots: int = 0

    # Card appearance multipliers
    tarot_appearance_mult: float = 1.0
    planet_appearance_mult: float = 1.0
    edition_appearance_mult: float = 1.0

    # Special flags
    playing_cards_in_shop: bool = False
    playing_cards_can_have_modifiers: bool = False
    spectral_in_arcana: bool = False
    observatory_active: bool = False  # Planet cards give X1.5 mult

    # Ante reduction from Hieroglyph/Petroglyph
    ante_reduction: int = 0
    hands_penalty: int = 0  # Negative hands per round from Hieroglyph
    discards_penalty: int = 0  # Negative discards from Petroglyph

    # Boss reroll
    boss_rerolls_remaining: int = 0
    boss_reroll_unlimited: bool = False

    def reset_reroll_cost(self, config: ShopConfig) -> None:
        """Reset reroll cost when entering a new shop."""
        base = config.base_reroll_cost

        # Apply Reroll Surplus (-$2)
        if "reroll_surplus" in self.redeemed_vouchers:
            base -= 2

        # Apply Reroll Glut (additional -$2)
        if "reroll_glut" in self.redeemed_vouchers:
            base -= 2

        self.current_reroll_cost = max(0, base)

    def increment_reroll_cost(self, config: ShopConfig) -> None:
        """Increase reroll cost after a reroll."""
        self.current_reroll_cost += config.reroll_cost_increase

    def apply_voucher(self, voucher_id: str) -> None:
        """Apply a voucher's effects to the shop state."""
        if voucher_id in self.redeemed_vouchers:
            return  # Already applied

        self.redeemed_vouchers.append(voucher_id)
        voucher = VOUCHERS.get(voucher_id)
        if not voucher:
            return

        # Apply effects based on voucher
        match voucher_id:
            # Shop slots
            case "overstock":
                self.card_slots = 3
            case "overstock_plus":
                self.card_slots = 4

            # Discounts
            case "clearance_sale":
                self.discount_multiplier = 0.75
            case "liquidation":
                self.discount_multiplier = 0.50

            # Edition appearance
            case "hone":
                self.edition_appearance_mult = 2.0
            case "glow_up":
                self.edition_appearance_mult = 4.0

            # Consumable slots
            case "crystal_ball":
                self.bonus_consumable_slots += 1

            # Hands/discards
            case "grabber":
                self.bonus_hands += 1
            case "nacho_tong":
                self.bonus_hands += 1  # Total +2
            case "wasteful":
                self.bonus_discards += 1
            case "recyclomancy":
                self.bonus_discards += 1  # Total +2

            # Card frequency
            case "tarot_merchant":
                self.tarot_appearance_mult = 2.0
            case "tarot_tycoon":
                self.tarot_appearance_mult = 4.0
            case "planet_merchant":
                self.planet_appearance_mult = 2.0
            case "planet_tycoon":
                self.planet_appearance_mult = 4.0

            # Interest
            case "seed_money":
                self.interest_cap = 10
            case "money_tree":
                self.interest_cap = 20

            # Playing cards
            case "magic_trick":
                self.playing_cards_in_shop = True
            case "illusion":
                self.playing_cards_can_have_modifiers = True

            # Joker slots
            case "antimatter":
                self.bonus_joker_slots += 1

            # Hand size
            case "paint_brush":
                self.bonus_hand_size += 1
            case "palette":
                self.bonus_hand_size += 1  # Total +2

            # Ante reduction
            case "hieroglyph":
                self.ante_reduction += 1
                self.hands_penalty += 1
            case "petroglyph":
                self.ante_reduction += 1
                self.discards_penalty += 1

            # Boss reroll
            case "directors_cut":
                self.boss_rerolls_remaining = 1
            case "retcon":
                self.boss_reroll_unlimited = True

            # Special
            case "omen_globe":
                self.spectral_in_arcana = True
            case "observatory":
                self.observatory_active = True

    def calculate_price(
        self,
        base_cost: int,
        edition_cost: int = 0,
    ) -> int:
        """Calculate the final price of an item."""
        total = base_cost + edition_cost
        return int(total * self.discount_multiplier)

    def calculate_sell_value(self, buy_cost: int) -> int:
        """Calculate sell value (half of buy cost, rounded down)."""
        return buy_cost // 2

    def calculate_interest(self, money: int, config: ShopConfig) -> int:
        """Calculate interest earned at end of round."""
        interest = int(money * config.interest_rate)
        return min(interest, self.interest_cap)


# Default shop configuration
DEFAULT_SHOP_CONFIG = ShopConfig()


# =============================================================================
# Helper Functions
# =============================================================================


def get_all_voucher_ids() -> list[str]:
    """Get all voucher IDs."""
    return list(VOUCHERS.keys())


def get_base_voucher_ids() -> list[str]:
    """Get only base voucher IDs."""
    return list(BASE_VOUCHERS.keys())


def get_upgraded_voucher_ids() -> list[str]:
    """Get only upgraded voucher IDs."""
    return list(UPGRADED_VOUCHERS.keys())


def get_voucher_upgrade(base_voucher_id: str) -> str | None:
    """Get the upgraded version of a base voucher."""
    for voucher_id, voucher in UPGRADED_VOUCHERS.items():
        if voucher.upgrades_from == base_voucher_id:
            return voucher_id
    return None


def is_voucher_available(
    voucher_id: str,
    redeemed_vouchers: list[str],
) -> bool:
    """Check if a voucher is available to redeem.

    Base vouchers are always available if not redeemed.
    Upgraded vouchers require their base version to be redeemed first.
    """
    if voucher_id in redeemed_vouchers:
        return False

    voucher = VOUCHERS.get(voucher_id)
    if not voucher:
        return False

    if voucher.tier == VoucherTier.UPGRADED:
        # Need base voucher redeemed first
        if voucher.upgrades_from not in redeemed_vouchers:
            return False

    return True


def create_shop_state() -> ShopState:
    """Create a new shop state with default values."""
    return ShopState()
