"""Tests for starting decks."""

import pytest

from balatro_bot.decks import (
    DECKS,
    DeckDefinition,
    DeckState,
    DeckType,
    create_abandoned_deck_cards,
    create_checkered_deck_cards,
    create_deck_cards,
    create_deck_state,
    create_erratic_deck_cards,
    create_standard_deck_cards,
    get_all_deck_types,
    get_base_deck_types,
    get_deck_unlock_chain,
    get_stake_deck_types,
    get_win_deck_types,
)
from balatro_bot.models import Rank, Suit


class TestDeckDefinitions:
    """Test deck definitions."""

    def test_all_15_decks_exist(self):
        """Should have all 15 decks."""
        assert len(DECKS) == 15

    def test_deck_has_required_fields(self):
        """Each deck should have required fields."""
        for deck_type, deck in DECKS.items():
            assert deck.deck_type == deck_type
            assert deck.name
            assert deck.description
            assert deck.unlock_requirement

    def test_base_deck_count(self):
        """Should have 5 base decks."""
        base_decks = get_base_deck_types()
        assert len(base_decks) == 5
        assert DeckType.RED in base_decks
        assert DeckType.BLUE in base_decks
        assert DeckType.YELLOW in base_decks
        assert DeckType.GREEN in base_decks
        assert DeckType.BLACK in base_decks

    def test_win_deck_count(self):
        """Should have 5 win decks."""
        win_decks = get_win_deck_types()
        assert len(win_decks) == 5
        assert DeckType.MAGIC in win_decks
        assert DeckType.NEBULA in win_decks
        assert DeckType.GHOST in win_decks
        assert DeckType.ABANDONED in win_decks
        assert DeckType.CHECKERED in win_decks

    def test_stake_deck_count(self):
        """Should have 5 stake decks."""
        stake_decks = get_stake_deck_types()
        assert len(stake_decks) == 5
        assert DeckType.ZODIAC in stake_decks
        assert DeckType.PAINTED in stake_decks
        assert DeckType.ANAGLYPH in stake_decks
        assert DeckType.PLASMA in stake_decks
        assert DeckType.ERRATIC in stake_decks

    def test_get_all_deck_types(self):
        """Should return all 15 deck types."""
        all_decks = get_all_deck_types()
        assert len(all_decks) == 15


class TestBaseDeckEffects:
    """Test base deck effects."""

    def test_red_deck_bonus_discard(self):
        """Red deck should have +1 discard."""
        deck = DECKS[DeckType.RED]
        assert deck.bonus_discards == 1
        assert deck.bonus_hands == 0

    def test_blue_deck_bonus_hand(self):
        """Blue deck should have +1 hand."""
        deck = DECKS[DeckType.BLUE]
        assert deck.bonus_hands == 1
        assert deck.bonus_discards == 0

    def test_yellow_deck_bonus_money(self):
        """Yellow deck should have +$10 starting money."""
        deck = DECKS[DeckType.YELLOW]
        assert deck.bonus_money == 10

    def test_green_deck_economy(self):
        """Green deck should have economy effects and no interest."""
        deck = DECKS[DeckType.GREEN]
        assert deck.money_per_remaining_hand == 2
        assert deck.money_per_remaining_discard == 1
        assert deck.has_interest is False

    def test_black_deck_joker_slot(self):
        """Black deck should have +1 joker slot and -1 hand."""
        deck = DECKS[DeckType.BLACK]
        assert deck.bonus_joker_slots == 1
        assert deck.bonus_hands == -1


class TestWinDeckEffects:
    """Test win deck effects."""

    def test_magic_deck_starting_items(self):
        """Magic deck should start with Crystal Ball and 2 Fools."""
        deck = DECKS[DeckType.MAGIC]
        assert "crystal_ball" in deck.starting_vouchers
        assert len(deck.starting_consumables) == 2
        assert all(c[1] == "the_fool" for c in deck.starting_consumables)

    def test_nebula_deck_effects(self):
        """Nebula deck should have Telescope and -1 consumable slot."""
        deck = DECKS[DeckType.NEBULA]
        assert "telescope" in deck.starting_vouchers
        assert deck.bonus_consumable_slots == -1

    def test_ghost_deck_effects(self):
        """Ghost deck should have spectral in shop and start with Hex."""
        deck = DECKS[DeckType.GHOST]
        assert deck.spectral_in_shop is True
        assert ("spectral", "hex") in deck.starting_consumables

    def test_abandoned_deck_no_face_cards(self):
        """Abandoned deck should have no face cards flag."""
        deck = DECKS[DeckType.ABANDONED]
        assert deck.no_face_cards is True

    def test_checkered_deck_suits(self):
        """Checkered deck should only have Spades and Hearts."""
        deck = DECKS[DeckType.CHECKERED]
        assert deck.only_spades_hearts is True


class TestStakeDeckEffects:
    """Test stake deck effects."""

    def test_zodiac_deck_vouchers(self):
        """Zodiac deck should have 3 starting vouchers."""
        deck = DECKS[DeckType.ZODIAC]
        assert "tarot_merchant" in deck.starting_vouchers
        assert "planet_merchant" in deck.starting_vouchers
        assert "overstock" in deck.starting_vouchers

    def test_painted_deck_modifiers(self):
        """Painted deck should have +2 hand size and -1 joker slot."""
        deck = DECKS[DeckType.PAINTED]
        assert deck.bonus_hand_size == 2
        assert deck.bonus_joker_slots == -1

    def test_anaglyph_deck_double_tag(self):
        """Anaglyph deck should give Double Tag on boss."""
        deck = DECKS[DeckType.ANAGLYPH]
        assert deck.double_tag_on_boss is True

    def test_plasma_deck_effects(self):
        """Plasma deck should balance chips/mult and double blinds."""
        deck = DECKS[DeckType.PLASMA]
        assert deck.balance_chips_mult is True
        assert deck.blind_size_multiplier == 2.0

    def test_erratic_deck_randomize(self):
        """Erratic deck should randomize cards."""
        deck = DECKS[DeckType.ERRATIC]
        assert deck.randomize_cards is True


class TestDeckCardCreation:
    """Test deck card creation functions."""

    def test_standard_deck_52_cards(self):
        """Standard deck should have 52 cards."""
        cards = create_standard_deck_cards()
        assert len(cards) == 52

    def test_standard_deck_all_suits(self):
        """Standard deck should have all 4 suits."""
        cards = create_standard_deck_cards()
        suits = {card.suit for card in cards}
        assert len(suits) == 4

    def test_standard_deck_all_ranks(self):
        """Standard deck should have all 13 ranks."""
        cards = create_standard_deck_cards()
        ranks = {card.rank for card in cards}
        assert len(ranks) == 13

    def test_abandoned_deck_40_cards(self):
        """Abandoned deck should have 40 cards (no face cards)."""
        cards = create_abandoned_deck_cards()
        assert len(cards) == 40

    def test_abandoned_deck_no_face_cards(self):
        """Abandoned deck should have no Jacks, Queens, or Kings."""
        cards = create_abandoned_deck_cards()
        for card in cards:
            assert card.rank not in (Rank.JACK, Rank.QUEEN, Rank.KING)

    def test_abandoned_deck_has_aces(self):
        """Abandoned deck should still have Aces."""
        cards = create_abandoned_deck_cards()
        aces = [c for c in cards if c.rank == Rank.ACE]
        assert len(aces) == 4

    def test_checkered_deck_52_cards(self):
        """Checkered deck should have 52 cards."""
        cards = create_checkered_deck_cards()
        assert len(cards) == 52

    def test_checkered_deck_only_two_suits(self):
        """Checkered deck should only have Spades and Hearts."""
        cards = create_checkered_deck_cards()
        suits = {card.suit for card in cards}
        assert suits == {Suit.SPADES, Suit.HEARTS}

    def test_checkered_deck_26_each_suit(self):
        """Checkered deck should have 26 of each suit."""
        cards = create_checkered_deck_cards()
        spades = [c for c in cards if c.suit == Suit.SPADES]
        hearts = [c for c in cards if c.suit == Suit.HEARTS]
        assert len(spades) == 26
        assert len(hearts) == 26

    def test_erratic_deck_52_cards(self):
        """Erratic deck should have 52 cards."""
        cards = create_erratic_deck_cards(seed=42)
        assert len(cards) == 52

    def test_erratic_deck_deterministic_with_seed(self):
        """Erratic deck should be deterministic with same seed."""
        cards1 = create_erratic_deck_cards(seed=42)
        cards2 = create_erratic_deck_cards(seed=42)
        for c1, c2 in zip(cards1, cards2):
            assert c1.rank == c2.rank
            assert c1.suit == c2.suit

    def test_erratic_deck_different_with_different_seed(self):
        """Erratic deck should be different with different seeds."""
        cards1 = create_erratic_deck_cards(seed=42)
        cards2 = create_erratic_deck_cards(seed=123)
        # Very unlikely to be identical
        same_count = sum(
            1 for c1, c2 in zip(cards1, cards2)
            if c1.rank == c2.rank and c1.suit == c2.suit
        )
        assert same_count < 52  # Not all cards should match


class TestCreateDeckCards:
    """Test the unified create_deck_cards function."""

    def test_red_deck_standard(self):
        """Red deck should create standard 52 cards."""
        cards = create_deck_cards(DeckType.RED)
        assert len(cards) == 52

    def test_abandoned_deck_no_faces(self):
        """Abandoned deck should create 40 cards."""
        cards = create_deck_cards(DeckType.ABANDONED)
        assert len(cards) == 40

    def test_checkered_deck_two_suits(self):
        """Checkered deck should create cards with 2 suits."""
        cards = create_deck_cards(DeckType.CHECKERED)
        suits = {card.suit for card in cards}
        assert len(suits) == 2

    def test_erratic_deck_with_seed(self):
        """Erratic deck should accept seed parameter."""
        cards = create_deck_cards(DeckType.ERRATIC, seed=42)
        assert len(cards) == 52


class TestDeckState:
    """Test deck state creation and methods."""

    def test_create_red_deck_state(self):
        """Red deck state should have +1 discard."""
        state = create_deck_state(DeckType.RED)
        assert state.total_discards == 4  # Base 3 + 1
        assert state.total_hands == 4  # Base 4

    def test_create_blue_deck_state(self):
        """Blue deck state should have +1 hand."""
        state = create_deck_state(DeckType.BLUE)
        assert state.total_hands == 5  # Base 4 + 1
        assert state.total_discards == 3  # Base 3

    def test_create_yellow_deck_state(self):
        """Yellow deck state should have +$10."""
        state = create_deck_state(DeckType.YELLOW)
        assert state.starting_money == 14  # Base 4 + 10

    def test_create_black_deck_state(self):
        """Black deck state should have +1 joker slot and -1 hand."""
        state = create_deck_state(DeckType.BLACK)
        assert state.total_joker_slots == 6  # Base 5 + 1
        assert state.total_hands == 3  # Base 4 - 1

    def test_create_painted_deck_state(self):
        """Painted deck state should have +2 hand size and -1 joker slot."""
        state = create_deck_state(DeckType.PAINTED)
        assert state.total_hand_size == 10  # Base 8 + 2
        assert state.total_joker_slots == 4  # Base 5 - 1

    def test_create_nebula_deck_state(self):
        """Nebula deck state should have -1 consumable slot."""
        state = create_deck_state(DeckType.NEBULA)
        assert state.total_consumable_slots == 1  # Base 2 - 1


class TestDeckStateEffects:
    """Test deck state effect methods."""

    def test_green_deck_end_of_round_bonus(self):
        """Green deck should calculate end of round bonus."""
        state = create_deck_state(DeckType.GREEN)
        # 2 remaining hands, 1 remaining discard
        bonus = state.calculate_end_of_round_bonus(2, 1)
        assert bonus == 5  # 2*2 + 1*1

    def test_green_deck_no_remaining(self):
        """Green deck with no remaining should give no bonus."""
        state = create_deck_state(DeckType.GREEN)
        bonus = state.calculate_end_of_round_bonus(0, 0)
        assert bonus == 0

    def test_red_deck_no_end_of_round_bonus(self):
        """Red deck should not have end of round bonus."""
        state = create_deck_state(DeckType.RED)
        bonus = state.calculate_end_of_round_bonus(2, 1)
        assert bonus == 0

    def test_plasma_deck_blind_multiplier(self):
        """Plasma deck should double blind chips."""
        state = create_deck_state(DeckType.PLASMA)
        chips = state.calculate_blind_chips(300)
        assert chips == 600

    def test_normal_deck_blind_multiplier(self):
        """Normal deck should not modify blind chips."""
        state = create_deck_state(DeckType.RED)
        chips = state.calculate_blind_chips(300)
        assert chips == 300

    def test_plasma_deck_balance_chips_mult(self):
        """Plasma deck should balance chips and mult."""
        state = create_deck_state(DeckType.PLASMA)
        chips, mult = state.apply_plasma_balance(100, 50)
        assert chips == 75
        assert mult == 75

    def test_normal_deck_no_balance(self):
        """Normal deck should not balance chips and mult."""
        state = create_deck_state(DeckType.RED)
        chips, mult = state.apply_plasma_balance(100, 50)
        assert chips == 100
        assert mult == 50


class TestDeckUnlockChain:
    """Test deck unlock chain."""

    def test_base_decks_no_prerequisite(self):
        """Base decks should have no deck prerequisite."""
        chain = get_deck_unlock_chain()
        for deck in get_base_deck_types():
            assert chain[deck] is None

    def test_magic_unlocks_from_red(self):
        """Magic deck should unlock from Red deck."""
        chain = get_deck_unlock_chain()
        assert chain[DeckType.MAGIC] == DeckType.RED

    def test_nebula_unlocks_from_blue(self):
        """Nebula deck should unlock from Blue deck."""
        chain = get_deck_unlock_chain()
        assert chain[DeckType.NEBULA] == DeckType.BLUE

    def test_ghost_unlocks_from_yellow(self):
        """Ghost deck should unlock from Yellow deck."""
        chain = get_deck_unlock_chain()
        assert chain[DeckType.GHOST] == DeckType.YELLOW

    def test_abandoned_unlocks_from_green(self):
        """Abandoned deck should unlock from Green deck."""
        chain = get_deck_unlock_chain()
        assert chain[DeckType.ABANDONED] == DeckType.GREEN

    def test_checkered_unlocks_from_black(self):
        """Checkered deck should unlock from Black deck."""
        chain = get_deck_unlock_chain()
        assert chain[DeckType.CHECKERED] == DeckType.BLACK

    def test_stake_decks_no_deck_prerequisite(self):
        """Stake decks should have no deck prerequisite."""
        chain = get_deck_unlock_chain()
        for deck in get_stake_deck_types():
            assert chain[deck] is None


class TestDeckStateProperties:
    """Test deck state property access."""

    def test_deck_state_has_definition(self):
        """Deck state should have definition reference."""
        state = create_deck_state(DeckType.RED)
        assert state.definition == DECKS[DeckType.RED]

    def test_deck_state_has_deck_type(self):
        """Deck state should have deck type."""
        state = create_deck_state(DeckType.BLUE)
        assert state.deck_type == DeckType.BLUE

    def test_default_base_values(self):
        """Base values should be correct for neutral deck."""
        # Using a deck with no modifiers to verify base values
        state = create_deck_state(DeckType.ANAGLYPH)  # No stat modifiers
        assert state.total_hands == 4
        assert state.total_discards == 3
        assert state.total_hand_size == 8
        assert state.total_joker_slots == 5
        assert state.total_consumable_slots == 2
        assert state.starting_money == 4
