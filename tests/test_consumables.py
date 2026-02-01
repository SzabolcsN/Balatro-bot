"""Tests for consumables (Tarot, Planet, Spectral cards and Booster Packs)."""

import pytest

from balatro_bot.consumables import (
    BOOSTER_PACKS,
    PLANET_CARDS,
    SPECTRAL_CARDS,
    TAROT_CARDS,
    BoosterPack,
    BoosterPackSize,
    BoosterPackType,
    ConsumableInstance,
    ConsumableType,
    PlanetCard,
    SpectralCard,
    TarotCard,
    create_consumable,
    get_all_booster_pack_ids,
    get_all_planet_ids,
    get_all_spectral_ids,
    get_all_standard_planet_ids,
    get_all_tarot_ids,
    get_planet_for_hand_type,
)
from balatro_bot.hand_evaluation import evaluate_hand
from balatro_bot.models import Card, Enhancement, HandType, Rank, Suit


class TestTarotCards:
    """Test Tarot card definitions."""

    def test_all_22_tarots_exist(self):
        """Should have all 22 tarot cards."""
        assert len(TAROT_CARDS) == 22

    def test_tarot_card_has_required_fields(self):
        """Each tarot card should have id, name, description."""
        for tarot_id, tarot in TAROT_CARDS.items():
            assert tarot.id == tarot_id
            assert tarot.name
            assert tarot.description

    def test_enhancement_tarots(self):
        """Should have all enhancement tarots."""
        enhancement_tarots = [
            "the_magician",  # Lucky
            "the_empress",  # Mult
            "the_hierophant",  # Bonus
            "the_lovers",  # Wild
            "the_chariot",  # Steel
            "justice",  # Glass
            "the_devil",  # Gold
            "the_tower",  # Stone
        ]
        for tarot_id in enhancement_tarots:
            assert tarot_id in TAROT_CARDS

    def test_suit_conversion_tarots(self):
        """Should have all suit conversion tarots."""
        suit_tarots = {
            "the_star": "Diamonds",
            "the_moon": "Clubs",
            "the_sun": "Hearts",
            "the_world": "Spades",
        }
        for tarot_id, suit in suit_tarots.items():
            assert tarot_id in TAROT_CARDS
            assert suit in TAROT_CARDS[tarot_id].description

    def test_creation_tarots(self):
        """Should have tarots that create other cards."""
        assert "the_high_priestess" in TAROT_CARDS  # Creates planets
        assert "the_emperor" in TAROT_CARDS  # Creates tarots
        assert "judgement" in TAROT_CARDS  # Creates joker

    def test_the_fool(self):
        """The Fool should copy last used consumable."""
        fool = TAROT_CARDS["the_fool"]
        assert "last" in fool.description.lower()

    def test_get_all_tarot_ids(self):
        """Should return all tarot IDs."""
        ids = get_all_tarot_ids()
        assert len(ids) == 22
        assert set(ids) == set(TAROT_CARDS.keys())


class TestPlanetCards:
    """Test Planet card definitions."""

    def test_all_12_planets_exist(self):
        """Should have all 12 planet cards."""
        assert len(PLANET_CARDS) == 12

    def test_planet_card_has_required_fields(self):
        """Each planet card should have id, name, hand_type, description."""
        for planet_id, planet in PLANET_CARDS.items():
            assert planet.id == planet_id
            assert planet.name
            assert planet.hand_type
            assert planet.description

    def test_standard_planets_map_to_hand_types(self):
        """Standard planets should map to standard hand types."""
        mappings = {
            "pluto": "HIGH_CARD",
            "mercury": "PAIR",
            "uranus": "TWO_PAIR",
            "venus": "THREE_OF_A_KIND",
            "saturn": "STRAIGHT",
            "jupiter": "FLUSH",
            "earth": "FULL_HOUSE",
            "mars": "FOUR_OF_A_KIND",
            "neptune": "STRAIGHT_FLUSH",
        }
        for planet_id, hand_type in mappings.items():
            assert PLANET_CARDS[planet_id].hand_type == hand_type
            assert not PLANET_CARDS[planet_id].is_secret

    def test_secret_planets(self):
        """Secret planets should be marked as secret."""
        secret_planets = ["planet_x", "ceres", "eris"]
        for planet_id in secret_planets:
            assert PLANET_CARDS[planet_id].is_secret

    def test_secret_planets_map_to_secret_hands(self):
        """Secret planets should map to secret hand types."""
        assert PLANET_CARDS["planet_x"].hand_type == "FIVE_OF_A_KIND"
        assert PLANET_CARDS["ceres"].hand_type == "FLUSH_HOUSE"
        assert PLANET_CARDS["eris"].hand_type == "FLUSH_FIVE"

    def test_get_planet_for_hand_type(self):
        """Should return correct planet for hand type."""
        assert get_planet_for_hand_type("HIGH_CARD") == "pluto"
        assert get_planet_for_hand_type("FLUSH") == "jupiter"
        assert get_planet_for_hand_type("FIVE_OF_A_KIND") == "planet_x"

    def test_get_all_planet_ids(self):
        """Should return all planet IDs."""
        ids = get_all_planet_ids()
        assert len(ids) == 12

    def test_get_all_standard_planet_ids(self):
        """Should return only non-secret planet IDs."""
        ids = get_all_standard_planet_ids()
        assert len(ids) == 9
        for pid in ids:
            assert not PLANET_CARDS[pid].is_secret


class TestSpectralCards:
    """Test Spectral card definitions."""

    def test_all_18_spectrals_exist(self):
        """Should have all 18 spectral cards."""
        assert len(SPECTRAL_CARDS) == 18

    def test_spectral_card_has_required_fields(self):
        """Each spectral card should have id, name, description."""
        for spectral_id, spectral in SPECTRAL_CARDS.items():
            assert spectral.id == spectral_id
            assert spectral.name
            assert spectral.description

    def test_seal_spectrals(self):
        """Should have spectrals that add seals."""
        seal_spectrals = {
            "talisman": "Gold Seal",
            "deja_vu": "Red Seal",
            "trance": "Blue Seal",
            "medium": "Purple Seal",
        }
        for spectral_id, seal in seal_spectrals.items():
            assert spectral_id in SPECTRAL_CARDS
            assert seal in SPECTRAL_CARDS[spectral_id].description

    def test_drawback_spectrals(self):
        """Spectrals with drawbacks should be marked."""
        drawback_spectrals = [
            "familiar",
            "grim",
            "incantation",
            "wraith",
            "ectoplasm",
            "ankh",
            "hex",
            "ouija",
            "immolate",
        ]
        for spectral_id in drawback_spectrals:
            assert SPECTRAL_CARDS[spectral_id].has_drawback

    def test_black_hole(self):
        """Black Hole should upgrade all hands."""
        black_hole = SPECTRAL_CARDS["black_hole"]
        assert "every" in black_hole.description.lower()
        assert "level" in black_hole.description.lower()

    def test_the_soul(self):
        """The Soul should create legendary joker."""
        soul = SPECTRAL_CARDS["the_soul"]
        assert "legendary" in soul.description.lower()

    def test_get_all_spectral_ids(self):
        """Should return all spectral IDs."""
        ids = get_all_spectral_ids()
        assert len(ids) == 18


class TestBoosterPacks:
    """Test Booster Pack definitions."""

    def test_all_15_packs_exist(self):
        """Should have 5 types x 3 sizes = 15 packs."""
        assert len(BOOSTER_PACKS) == 15

    def test_pack_types(self):
        """Should have all pack types."""
        pack_types = {bp.pack_type for bp in BOOSTER_PACKS.values()}
        assert BoosterPackType.ARCANA in pack_types
        assert BoosterPackType.CELESTIAL in pack_types
        assert BoosterPackType.STANDARD in pack_types
        assert BoosterPackType.BUFFOON in pack_types
        assert BoosterPackType.SPECTRAL in pack_types

    def test_pack_sizes(self):
        """Should have all pack sizes."""
        pack_sizes = {bp.size for bp in BOOSTER_PACKS.values()}
        assert BoosterPackSize.NORMAL in pack_sizes
        assert BoosterPackSize.JUMBO in pack_sizes
        assert BoosterPackSize.MEGA in pack_sizes

    def test_pack_costs(self):
        """Packs should have correct costs based on size."""
        for pack in BOOSTER_PACKS.values():
            if pack.size == BoosterPackSize.NORMAL:
                assert pack.cost == 4
            elif pack.size == BoosterPackSize.JUMBO:
                assert pack.cost == 6
            elif pack.size == BoosterPackSize.MEGA:
                assert pack.cost == 8

    def test_arcana_pack_contents(self):
        """Arcana packs should show correct number of cards."""
        assert BOOSTER_PACKS["arcana_normal"].cards_shown == 3
        assert BOOSTER_PACKS["arcana_jumbo"].cards_shown == 5
        assert BOOSTER_PACKS["arcana_mega"].cards_shown == 5

    def test_mega_packs_choose_two(self):
        """Mega packs should allow choosing 2 cards."""
        for pack_id, pack in BOOSTER_PACKS.items():
            if pack.size == BoosterPackSize.MEGA:
                assert pack.cards_to_choose == 2

    def test_pack_id_property(self):
        """Pack id should combine type and size."""
        pack = BOOSTER_PACKS["arcana_normal"]
        assert pack.id == "arcana_normal"

    def test_pack_name_property(self):
        """Pack name should be human readable."""
        assert BOOSTER_PACKS["arcana_normal"].name == "Arcana Pack"
        assert BOOSTER_PACKS["arcana_jumbo"].name == "Jumbo Arcana Pack"
        assert BOOSTER_PACKS["arcana_mega"].name == "Mega Arcana Pack"

    def test_get_all_booster_pack_ids(self):
        """Should return all booster pack IDs."""
        ids = get_all_booster_pack_ids()
        assert len(ids) == 15


class TestConsumableInstance:
    """Test consumable instance creation."""

    def test_create_tarot_instance(self):
        """Should create tarot consumable instance."""
        instance = create_consumable(ConsumableType.TAROT, "the_fool")
        assert instance.consumable_type == ConsumableType.TAROT
        assert instance.card_id == "the_fool"
        assert instance.name == "The Fool"

    def test_create_planet_instance(self):
        """Should create planet consumable instance."""
        instance = create_consumable(ConsumableType.PLANET, "jupiter")
        assert instance.consumable_type == ConsumableType.PLANET
        assert instance.card_id == "jupiter"
        assert instance.name == "Jupiter"

    def test_create_spectral_instance(self):
        """Should create spectral consumable instance."""
        instance = create_consumable(ConsumableType.SPECTRAL, "black_hole")
        assert instance.consumable_type == ConsumableType.SPECTRAL
        assert instance.card_id == "black_hole"
        assert instance.name == "Black Hole"

    def test_invalid_tarot_raises(self):
        """Should raise for invalid tarot ID."""
        with pytest.raises(ValueError, match="Unknown tarot"):
            create_consumable(ConsumableType.TAROT, "invalid")

    def test_invalid_planet_raises(self):
        """Should raise for invalid planet ID."""
        with pytest.raises(ValueError, match="Unknown planet"):
            create_consumable(ConsumableType.PLANET, "invalid")

    def test_invalid_spectral_raises(self):
        """Should raise for invalid spectral ID."""
        with pytest.raises(ValueError, match="Unknown spectral"):
            create_consumable(ConsumableType.SPECTRAL, "invalid")

    def test_instance_definition_property(self):
        """Instance should provide definition access."""
        instance = create_consumable(ConsumableType.TAROT, "the_hermit")
        definition = instance.definition
        assert isinstance(definition, TarotCard)
        assert definition.id == "the_hermit"

    def test_instance_description_property(self):
        """Instance should provide description access."""
        instance = create_consumable(ConsumableType.PLANET, "mars")
        assert "Four of a Kind" in instance.description


class TestSecretHandTypes:
    """Test Flush House and Flush Five detection."""

    def test_flush_house_detection(self):
        """Should detect Flush House (Full House + Flush)."""
        # Three Aces + Two Kings, all hearts
        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.HEARTS, enhancement=Enhancement.WILD),
            Card(Rank.ACE, Suit.HEARTS, enhancement=Enhancement.WILD),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.HEARTS, enhancement=Enhancement.WILD),
        ]
        result = evaluate_hand(cards)
        assert result.hand_type == HandType.FLUSH_HOUSE

    def test_flush_house_base_values(self):
        """Flush House should have correct base values."""
        assert HandType.FLUSH_HOUSE.base_chips == 140
        assert HandType.FLUSH_HOUSE.base_mult == 14

    def test_flush_five_detection(self):
        """Should detect Flush Five (Five of a Kind + Flush)."""
        # Five Aces, all hearts (requires wild cards for same suit)
        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.HEARTS, enhancement=Enhancement.WILD),
            Card(Rank.ACE, Suit.HEARTS, enhancement=Enhancement.WILD),
            Card(Rank.ACE, Suit.HEARTS, enhancement=Enhancement.WILD),
            Card(Rank.ACE, Suit.HEARTS, enhancement=Enhancement.WILD),
        ]
        result = evaluate_hand(cards)
        assert result.hand_type == HandType.FLUSH_FIVE

    def test_flush_five_base_values(self):
        """Flush Five should have correct base values."""
        assert HandType.FLUSH_FIVE.base_chips == 160
        assert HandType.FLUSH_FIVE.base_mult == 16

    def test_regular_full_house_not_flush_house(self):
        """Regular Full House (mixed suits) should not be Flush House."""
        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.CLUBS),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.DIAMONDS),
        ]
        result = evaluate_hand(cards)
        assert result.hand_type == HandType.FULL_HOUSE

    def test_regular_five_of_kind_not_flush_five(self):
        """Regular Five of a Kind (mixed suits) should not be Flush Five."""
        # Five Aces, different suits
        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.CLUBS),
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.ACE, Suit.HEARTS, enhancement=Enhancement.WILD),
        ]
        result = evaluate_hand(cards)
        # Should be Five of a Kind, not Flush Five (mixed suits)
        assert result.hand_type == HandType.FIVE_OF_A_KIND

    def test_hand_type_ordering(self):
        """Secret hands should be ranked higher than their components."""
        assert HandType.FLUSH_HOUSE > HandType.FULL_HOUSE
        assert HandType.FLUSH_HOUSE > HandType.FLUSH
        assert HandType.FLUSH_FIVE > HandType.FIVE_OF_A_KIND
        assert HandType.FLUSH_FIVE > HandType.FLUSH
