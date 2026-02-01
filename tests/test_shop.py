"""Tests for shop and voucher system."""

import pytest

from balatro_bot.shop import (
    BASE_VOUCHERS,
    DEFAULT_SHOP_CONFIG,
    UPGRADED_VOUCHERS,
    VOUCHERS,
    JokerRarity,
    ShopConfig,
    ShopItemType,
    ShopState,
    Voucher,
    VoucherTier,
    create_shop_state,
    get_all_voucher_ids,
    get_base_voucher_ids,
    get_upgraded_voucher_ids,
    get_voucher_upgrade,
    is_voucher_available,
)


class TestVoucherDefinitions:
    """Test voucher definitions."""

    def test_base_voucher_count(self):
        """Should have 16 base vouchers."""
        assert len(BASE_VOUCHERS) == 16

    def test_upgraded_voucher_count(self):
        """Should have 16 upgraded vouchers."""
        assert len(UPGRADED_VOUCHERS) == 16

    def test_total_voucher_count(self):
        """Should have 32 total vouchers."""
        assert len(VOUCHERS) == 32

    def test_voucher_has_required_fields(self):
        """Each voucher should have id, name, description."""
        for voucher_id, voucher in VOUCHERS.items():
            assert voucher.id == voucher_id
            assert voucher.name
            assert voucher.description
            assert voucher.cost == 10

    def test_base_vouchers_are_base_tier(self):
        """Base vouchers should have BASE tier."""
        for voucher in BASE_VOUCHERS.values():
            assert voucher.tier == VoucherTier.BASE
            assert voucher.upgrades_from is None

    def test_upgraded_vouchers_are_upgraded_tier(self):
        """Upgraded vouchers should have UPGRADED tier."""
        for voucher in UPGRADED_VOUCHERS.values():
            assert voucher.tier == VoucherTier.UPGRADED
            assert voucher.upgrades_from is not None
            assert voucher.upgrades_from in BASE_VOUCHERS

    def test_each_base_has_upgrade(self):
        """Each base voucher should have an upgrade."""
        for base_id in BASE_VOUCHERS:
            upgrade = get_voucher_upgrade(base_id)
            assert upgrade is not None, f"No upgrade found for {base_id}"
            assert upgrade in UPGRADED_VOUCHERS

    def test_get_all_voucher_ids(self):
        """Should return all voucher IDs."""
        ids = get_all_voucher_ids()
        assert len(ids) == 32

    def test_get_base_voucher_ids(self):
        """Should return only base voucher IDs."""
        ids = get_base_voucher_ids()
        assert len(ids) == 16
        for vid in ids:
            assert vid in BASE_VOUCHERS

    def test_get_upgraded_voucher_ids(self):
        """Should return only upgraded voucher IDs."""
        ids = get_upgraded_voucher_ids()
        assert len(ids) == 16
        for vid in ids:
            assert vid in UPGRADED_VOUCHERS


class TestVoucherCategories:
    """Test specific voucher categories."""

    def test_shop_slot_vouchers(self):
        """Should have Overstock and Overstock Plus."""
        assert "overstock" in VOUCHERS
        assert "overstock_plus" in VOUCHERS
        assert "+1 card slot" in VOUCHERS["overstock"].description

    def test_discount_vouchers(self):
        """Should have Clearance Sale and Liquidation."""
        assert "clearance_sale" in VOUCHERS
        assert "liquidation" in VOUCHERS
        assert "25%" in VOUCHERS["clearance_sale"].description
        assert "50%" in VOUCHERS["liquidation"].description

    def test_hands_discards_vouchers(self):
        """Should have hand and discard vouchers."""
        assert "grabber" in VOUCHERS
        assert "nacho_tong" in VOUCHERS
        assert "wasteful" in VOUCHERS
        assert "recyclomancy" in VOUCHERS

    def test_interest_vouchers(self):
        """Should have interest cap vouchers."""
        assert "seed_money" in VOUCHERS
        assert "money_tree" in VOUCHERS
        assert "$10" in VOUCHERS["seed_money"].description
        assert "$20" in VOUCHERS["money_tree"].description

    def test_blank_and_antimatter(self):
        """Blank should do nothing, Antimatter adds joker slot."""
        assert "blank" in VOUCHERS
        assert "antimatter" in VOUCHERS
        assert "nothing" in VOUCHERS["blank"].description.lower()
        assert "joker slot" in VOUCHERS["antimatter"].description.lower()

    def test_ante_reduction_vouchers(self):
        """Should have Hieroglyph and Petroglyph."""
        assert "hieroglyph" in VOUCHERS
        assert "petroglyph" in VOUCHERS


class TestVoucherAvailability:
    """Test voucher availability logic."""

    def test_base_voucher_available_initially(self):
        """Base vouchers should be available with no redeemed vouchers."""
        assert is_voucher_available("overstock", [])
        assert is_voucher_available("grabber", [])

    def test_upgraded_voucher_not_available_initially(self):
        """Upgraded vouchers should not be available without base."""
        assert not is_voucher_available("overstock_plus", [])
        assert not is_voucher_available("nacho_tong", [])

    def test_upgraded_voucher_available_after_base(self):
        """Upgraded vouchers should be available after redeeming base."""
        assert is_voucher_available("overstock_plus", ["overstock"])
        assert is_voucher_available("nacho_tong", ["grabber"])

    def test_voucher_not_available_if_already_redeemed(self):
        """Vouchers should not be available if already redeemed."""
        assert not is_voucher_available("overstock", ["overstock"])
        assert not is_voucher_available("overstock_plus", ["overstock", "overstock_plus"])

    def test_invalid_voucher_not_available(self):
        """Invalid voucher IDs should not be available."""
        assert not is_voucher_available("invalid_voucher", [])


class TestShopConfig:
    """Test shop configuration."""

    def test_default_config_values(self):
        """Default config should have expected values."""
        config = DEFAULT_SHOP_CONFIG

        assert config.base_card_slots == 2
        assert config.max_card_slots == 4
        assert config.base_reroll_cost == 5
        assert config.booster_pack_slots == 2
        assert config.voucher_cost == 10

    def test_card_probabilities_sum_to_one(self):
        """Card appearance probabilities should sum to ~1."""
        config = DEFAULT_SHOP_CONFIG
        total = config.joker_probability + config.tarot_probability + config.planet_probability
        assert abs(total - 1.0) < 0.01

    def test_joker_rarity_probabilities_sum_to_one(self):
        """Joker rarity probabilities should sum to 1."""
        config = DEFAULT_SHOP_CONFIG
        total = config.joker_common_prob + config.joker_uncommon_prob + config.joker_rare_prob
        assert abs(total - 1.0) < 0.01

    def test_base_prices(self):
        """Base prices should be set correctly."""
        config = DEFAULT_SHOP_CONFIG

        assert config.playing_card_base_cost == 1
        assert config.common_joker_base_cost == 4
        assert config.uncommon_joker_base_cost == 6
        assert config.rare_joker_base_cost == 8
        assert config.legendary_joker_base_cost == 20


class TestShopState:
    """Test shop state management."""

    def test_create_shop_state(self):
        """Should create shop state with default values."""
        state = create_shop_state()

        assert state.card_slots == 2
        assert state.discount_multiplier == 1.0
        assert state.bonus_hands == 0
        assert state.bonus_discards == 0
        assert len(state.redeemed_vouchers) == 0

    def test_reset_reroll_cost(self):
        """Should reset reroll cost correctly."""
        config = DEFAULT_SHOP_CONFIG
        state = create_shop_state()

        state.current_reroll_cost = 10
        state.reset_reroll_cost(config)
        assert state.current_reroll_cost == 5

    def test_reset_reroll_cost_with_surplus(self):
        """Reroll Surplus should reduce base reroll cost."""
        config = DEFAULT_SHOP_CONFIG
        state = create_shop_state()
        state.redeemed_vouchers.append("reroll_surplus")

        state.reset_reroll_cost(config)
        assert state.current_reroll_cost == 3  # 5 - 2

    def test_reset_reroll_cost_with_glut(self):
        """Reroll Glut should further reduce reroll cost."""
        config = DEFAULT_SHOP_CONFIG
        state = create_shop_state()
        state.redeemed_vouchers.extend(["reroll_surplus", "reroll_glut"])

        state.reset_reroll_cost(config)
        assert state.current_reroll_cost == 1  # 5 - 2 - 2

    def test_increment_reroll_cost(self):
        """Should increment reroll cost after reroll."""
        config = DEFAULT_SHOP_CONFIG
        state = create_shop_state()

        state.reset_reroll_cost(config)
        assert state.current_reroll_cost == 5

        state.increment_reroll_cost(config)
        assert state.current_reroll_cost == 6

        state.increment_reroll_cost(config)
        assert state.current_reroll_cost == 7


class TestVoucherEffects:
    """Test applying voucher effects to shop state."""

    def test_apply_overstock(self):
        """Overstock should add 1 card slot."""
        state = create_shop_state()
        state.apply_voucher("overstock")

        assert state.card_slots == 3
        assert "overstock" in state.redeemed_vouchers

    def test_apply_overstock_plus(self):
        """Overstock Plus should add another card slot."""
        state = create_shop_state()
        state.apply_voucher("overstock")
        state.apply_voucher("overstock_plus")

        assert state.card_slots == 4

    def test_apply_clearance_sale(self):
        """Clearance Sale should apply 25% discount."""
        state = create_shop_state()
        state.apply_voucher("clearance_sale")

        assert state.discount_multiplier == 0.75

    def test_apply_liquidation(self):
        """Liquidation should apply 50% discount."""
        state = create_shop_state()
        state.apply_voucher("liquidation")

        assert state.discount_multiplier == 0.50

    def test_apply_grabber(self):
        """Grabber should add 1 bonus hand."""
        state = create_shop_state()
        state.apply_voucher("grabber")

        assert state.bonus_hands == 1

    def test_apply_nacho_tong(self):
        """Nacho Tong should add another bonus hand."""
        state = create_shop_state()
        state.apply_voucher("grabber")
        state.apply_voucher("nacho_tong")

        assert state.bonus_hands == 2

    def test_apply_wasteful(self):
        """Wasteful should add 1 bonus discard."""
        state = create_shop_state()
        state.apply_voucher("wasteful")

        assert state.bonus_discards == 1

    def test_apply_recyclomancy(self):
        """Recyclomancy should add another bonus discard."""
        state = create_shop_state()
        state.apply_voucher("wasteful")
        state.apply_voucher("recyclomancy")

        assert state.bonus_discards == 2

    def test_apply_seed_money(self):
        """Seed Money should raise interest cap to $10."""
        state = create_shop_state()
        state.apply_voucher("seed_money")

        assert state.interest_cap == 10

    def test_apply_money_tree(self):
        """Money Tree should raise interest cap to $20."""
        state = create_shop_state()
        state.apply_voucher("money_tree")

        assert state.interest_cap == 20

    def test_apply_antimatter(self):
        """Antimatter should add 1 joker slot."""
        state = create_shop_state()
        state.apply_voucher("antimatter")

        assert state.bonus_joker_slots == 1

    def test_apply_paint_brush(self):
        """Paint Brush should add 1 hand size."""
        state = create_shop_state()
        state.apply_voucher("paint_brush")

        assert state.bonus_hand_size == 1

    def test_apply_palette(self):
        """Palette should add another hand size."""
        state = create_shop_state()
        state.apply_voucher("paint_brush")
        state.apply_voucher("palette")

        assert state.bonus_hand_size == 2

    def test_apply_magic_trick(self):
        """Magic Trick should enable playing cards in shop."""
        state = create_shop_state()
        state.apply_voucher("magic_trick")

        assert state.playing_cards_in_shop is True

    def test_apply_illusion(self):
        """Illusion should enable modifiers on playing cards."""
        state = create_shop_state()
        state.apply_voucher("illusion")

        assert state.playing_cards_can_have_modifiers is True

    def test_apply_hieroglyph(self):
        """Hieroglyph should reduce ante and add hands penalty."""
        state = create_shop_state()
        state.apply_voucher("hieroglyph")

        assert state.ante_reduction == 1
        assert state.hands_penalty == 1

    def test_apply_petroglyph(self):
        """Petroglyph should reduce ante again and add discards penalty."""
        state = create_shop_state()
        state.apply_voucher("hieroglyph")
        state.apply_voucher("petroglyph")

        assert state.ante_reduction == 2
        assert state.discards_penalty == 1

    def test_apply_duplicate_voucher_ignored(self):
        """Applying same voucher twice should have no additional effect."""
        state = create_shop_state()
        state.apply_voucher("overstock")
        state.apply_voucher("overstock")

        assert state.card_slots == 3  # Still 3, not 4
        assert state.redeemed_vouchers.count("overstock") == 1


class TestShopPricing:
    """Test shop pricing calculations."""

    def test_calculate_price_no_discount(self):
        """Price with no discount should be base + edition."""
        state = create_shop_state()

        assert state.calculate_price(4, 0) == 4
        assert state.calculate_price(4, 2) == 6

    def test_calculate_price_with_clearance(self):
        """Price with Clearance Sale should be 75%."""
        state = create_shop_state()
        state.apply_voucher("clearance_sale")

        assert state.calculate_price(4, 0) == 3  # 4 * 0.75
        assert state.calculate_price(8, 0) == 6  # 8 * 0.75

    def test_calculate_price_with_liquidation(self):
        """Price with Liquidation should be 50%."""
        state = create_shop_state()
        state.apply_voucher("liquidation")

        assert state.calculate_price(4, 0) == 2  # 4 * 0.5
        assert state.calculate_price(8, 0) == 4  # 8 * 0.5

    def test_calculate_sell_value(self):
        """Sell value should be half of buy cost."""
        state = create_shop_state()

        assert state.calculate_sell_value(4) == 2
        assert state.calculate_sell_value(5) == 2  # Floor division
        assert state.calculate_sell_value(10) == 5

    def test_calculate_interest(self):
        """Interest should be 20% of money up to cap."""
        config = DEFAULT_SHOP_CONFIG
        state = create_shop_state()

        # 20% of $10 = $2, under cap of $5
        assert state.calculate_interest(10, config) == 2

        # 20% of $25 = $5, at cap
        assert state.calculate_interest(25, config) == 5

        # 20% of $50 = $10, capped at $5
        assert state.calculate_interest(50, config) == 5

    def test_calculate_interest_with_seed_money(self):
        """Interest cap should increase with Seed Money."""
        config = DEFAULT_SHOP_CONFIG
        state = create_shop_state()
        state.apply_voucher("seed_money")

        # 20% of $50 = $10, cap now $10
        assert state.calculate_interest(50, config) == 10

    def test_calculate_interest_with_money_tree(self):
        """Interest cap should increase with Money Tree."""
        config = DEFAULT_SHOP_CONFIG
        state = create_shop_state()
        state.apply_voucher("money_tree")

        # 20% of $100 = $20, cap now $20
        assert state.calculate_interest(100, config) == 20


class TestShopEnums:
    """Test shop-related enums."""

    def test_shop_item_types(self):
        """Should have all shop item types."""
        assert ShopItemType.JOKER.value == "joker"
        assert ShopItemType.TAROT.value == "tarot"
        assert ShopItemType.PLANET.value == "planet"
        assert ShopItemType.PLAYING_CARD.value == "playing_card"
        assert ShopItemType.BOOSTER_PACK.value == "booster_pack"
        assert ShopItemType.VOUCHER.value == "voucher"

    def test_joker_rarities(self):
        """Should have all joker rarities."""
        assert JokerRarity.COMMON.value == "common"
        assert JokerRarity.UNCOMMON.value == "uncommon"
        assert JokerRarity.RARE.value == "rare"
        assert JokerRarity.LEGENDARY.value == "legendary"

    def test_voucher_tiers(self):
        """Should have all voucher tiers."""
        assert VoucherTier.BASE.value == "base"
        assert VoucherTier.UPGRADED.value == "upgraded"
