"""Tests for card modifiers (enhancements, editions, seals)."""

import pytest

from balatro_bot.hand_evaluation import evaluate_hand
from balatro_bot.models import Card, Edition, Enhancement, GameState, HandType, Rank, Seal, Suit
from balatro_bot.scoring import (
    CardEffect,
    apply_card_modifiers,
    apply_steel_cards_in_hand,
    calculate_score,
)


class TestEnhancementEnum:
    """Test Enhancement enum values."""

    def test_all_enhancements_exist(self):
        """Should have all 8 enhancement types plus NONE."""
        assert Enhancement.NONE.value == "none"
        assert Enhancement.BONUS.value == "bonus"
        assert Enhancement.MULT.value == "mult"
        assert Enhancement.WILD.value == "wild"
        assert Enhancement.GLASS.value == "glass"
        assert Enhancement.STEEL.value == "steel"
        assert Enhancement.STONE.value == "stone"
        assert Enhancement.GOLD.value == "gold"
        assert Enhancement.LUCKY.value == "lucky"


class TestEditionEnum:
    """Test Edition enum values."""

    def test_all_editions_exist(self):
        """Should have all 5 edition types."""
        assert Edition.BASE.value == "base"
        assert Edition.FOIL.value == "foil"
        assert Edition.HOLOGRAPHIC.value == "holo"
        assert Edition.POLYCHROME.value == "polychrome"
        assert Edition.NEGATIVE.value == "negative"


class TestSealEnum:
    """Test Seal enum values."""

    def test_all_seals_exist(self):
        """Should have all 4 seal types plus NONE."""
        assert Seal.NONE.value == "none"
        assert Seal.GOLD.value == "gold"
        assert Seal.RED.value == "red"
        assert Seal.BLUE.value == "blue"
        assert Seal.PURPLE.value == "purple"


class TestCardWithModifiers:
    """Test Card dataclass with modifiers."""

    def test_default_card_has_no_modifiers(self):
        """Card should default to no enhancement, base edition, no seal."""
        card = Card(Rank.ACE, Suit.SPADES)
        assert card.enhancement == Enhancement.NONE
        assert card.edition == Edition.BASE
        assert card.seal == Seal.NONE

    def test_card_with_enhancement(self):
        """Should create card with enhancement."""
        card = Card(Rank.ACE, Suit.SPADES, enhancement=Enhancement.BONUS)
        assert card.enhancement == Enhancement.BONUS

    def test_card_with_edition(self):
        """Should create card with edition."""
        card = Card(Rank.ACE, Suit.SPADES, edition=Edition.FOIL)
        assert card.edition == Edition.FOIL

    def test_card_with_seal(self):
        """Should create card with seal."""
        card = Card(Rank.ACE, Suit.SPADES, seal=Seal.GOLD)
        assert card.seal == Seal.GOLD

    def test_card_with_all_modifiers(self):
        """Should create card with all modifiers."""
        card = Card(
            Rank.ACE,
            Suit.SPADES,
            enhancement=Enhancement.GLASS,
            edition=Edition.POLYCHROME,
            seal=Seal.RED,
        )
        assert card.enhancement == Enhancement.GLASS
        assert card.edition == Edition.POLYCHROME
        assert card.seal == Seal.RED

    def test_with_enhancement_returns_new_card(self):
        """with_enhancement should return new card with enhancement."""
        card = Card(Rank.ACE, Suit.SPADES)
        bonus_card = card.with_enhancement(Enhancement.BONUS)
        assert bonus_card.enhancement == Enhancement.BONUS
        assert card.enhancement == Enhancement.NONE  # Original unchanged

    def test_with_edition_returns_new_card(self):
        """with_edition should return new card with edition."""
        card = Card(Rank.ACE, Suit.SPADES)
        foil_card = card.with_edition(Edition.FOIL)
        assert foil_card.edition == Edition.FOIL
        assert card.edition == Edition.BASE

    def test_with_seal_returns_new_card(self):
        """with_seal should return new card with seal."""
        card = Card(Rank.ACE, Suit.SPADES)
        gold_card = card.with_seal(Seal.GOLD)
        assert gold_card.seal == Seal.GOLD
        assert card.seal == Seal.NONE

    def test_card_str_with_modifiers(self):
        """Card string should show modifiers."""
        card = Card(Rank.ACE, Suit.SPADES, enhancement=Enhancement.BONUS)
        assert "bonus" in str(card)

        card = Card(Rank.ACE, Suit.SPADES, edition=Edition.FOIL)
        assert "foil" in str(card)

        card = Card(Rank.ACE, Suit.SPADES, seal=Seal.GOLD)
        assert "gold-seal" in str(card)


class TestWildCard:
    """Test Wild card behavior."""

    def test_is_wild_property(self):
        """Wild cards should report is_wild=True."""
        wild = Card(Rank.ACE, Suit.SPADES, enhancement=Enhancement.WILD)
        normal = Card(Rank.ACE, Suit.SPADES)
        assert wild.is_wild is True
        assert normal.is_wild is False

    def test_wild_has_all_suits(self):
        """Wild cards should match all suits."""
        wild = Card(Rank.ACE, Suit.SPADES, enhancement=Enhancement.WILD)
        assert wild.has_suit(Suit.SPADES) is True
        assert wild.has_suit(Suit.HEARTS) is True
        assert wild.has_suit(Suit.CLUBS) is True
        assert wild.has_suit(Suit.DIAMONDS) is True

    def test_wild_card_completes_flush(self):
        """Wild cards should help complete a flush."""
        # 4 hearts + 1 wild (spade) - non-sequential to avoid straight
        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.NINE, Suit.HEARTS),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.TWO, Suit.SPADES, enhancement=Enhancement.WILD),
        ]
        result = evaluate_hand(cards)
        assert result.hand_type == HandType.FLUSH

    def test_wild_card_completes_royal_flush(self):
        """Wild cards should help complete a royal flush."""
        # 4 hearts + 1 wild makes a royal flush
        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.QUEEN, Suit.HEARTS),
            Card(Rank.JACK, Suit.HEARTS),
            Card(Rank.TEN, Suit.SPADES, enhancement=Enhancement.WILD),
        ]
        result = evaluate_hand(cards)
        assert result.hand_type == HandType.ROYAL_FLUSH


class TestStoneCard:
    """Test Stone card behavior."""

    def test_is_stone_property(self):
        """Stone cards should report is_stone=True."""
        stone = Card(Rank.ACE, Suit.SPADES, enhancement=Enhancement.STONE)
        normal = Card(Rank.ACE, Suit.SPADES)
        assert stone.is_stone is True
        assert normal.is_stone is False

    def test_stone_has_no_suit(self):
        """Stone cards should not match any suit."""
        stone = Card(Rank.ACE, Suit.SPADES, enhancement=Enhancement.STONE)
        assert stone.has_suit(Suit.SPADES) is False
        assert stone.has_suit(Suit.HEARTS) is False

    def test_stone_card_gives_50_chips(self):
        """Stone cards should give +50 chips."""
        stone = Card(Rank.TWO, Suit.SPADES, enhancement=Enhancement.STONE)
        cards = [stone]
        result = evaluate_hand(cards)
        # High card base (5) + stone chip value (50) = 55
        assert result.base_chips == 55

    def test_stone_card_always_scores(self):
        """Stone cards should always be in scoring cards."""
        # Pair of aces + stone card
        cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.TWO, Suit.CLUBS, enhancement=Enhancement.STONE),
        ]
        result = evaluate_hand(cards)
        assert result.hand_type == HandType.PAIR
        # Stone card should be in scoring cards even though it's not part of pair
        assert len(result.scoring_cards) == 3


class TestEnhancementEffects:
    """Test enhancement effects during scoring."""

    def test_bonus_adds_30_chips(self):
        """Bonus enhancement should add +30 chips."""
        card = Card(Rank.ACE, Suit.SPADES, enhancement=Enhancement.BONUS)
        effect = apply_card_modifiers(card)
        assert effect.chips == 30

    def test_mult_adds_4_mult(self):
        """Mult enhancement should add +4 mult."""
        card = Card(Rank.ACE, Suit.SPADES, enhancement=Enhancement.MULT)
        effect = apply_card_modifiers(card)
        assert effect.mult == 4

    def test_glass_doubles_mult(self):
        """Glass enhancement should give x2 mult."""
        card = Card(Rank.ACE, Suit.SPADES, enhancement=Enhancement.GLASS)
        effect = apply_card_modifiers(card)
        assert effect.mult_mult == 2.0

    def test_glass_can_destroy(self):
        """Glass cards have 1/4 chance to be destroyed."""
        import random

        card = Card(Rank.ACE, Suit.SPADES, enhancement=Enhancement.GLASS)

        # Use seeded RNG for deterministic test
        rng = random.Random(42)
        destroyed_count = 0
        for _ in range(1000):
            effect = apply_card_modifiers(card, rng)
            if effect.destroyed:
                destroyed_count += 1

        # Should be approximately 25% (250 ± 50)
        assert 200 < destroyed_count < 300


class TestEditionEffects:
    """Test edition effects during scoring."""

    def test_foil_adds_50_chips(self):
        """Foil edition should add +50 chips."""
        card = Card(Rank.ACE, Suit.SPADES, edition=Edition.FOIL)
        effect = apply_card_modifiers(card)
        assert effect.chips == 50

    def test_holographic_adds_10_mult(self):
        """Holographic edition should add +10 mult."""
        card = Card(Rank.ACE, Suit.SPADES, edition=Edition.HOLOGRAPHIC)
        effect = apply_card_modifiers(card)
        assert effect.mult == 10

    def test_polychrome_multiplies_mult(self):
        """Polychrome edition should give x1.5 mult."""
        card = Card(Rank.ACE, Suit.SPADES, edition=Edition.POLYCHROME)
        effect = apply_card_modifiers(card)
        assert effect.mult_mult == 1.5


class TestSealEffects:
    """Test seal effects during scoring."""

    def test_gold_seal_gives_3_money(self):
        """Gold seal should give $3 when scoring."""
        card = Card(Rank.ACE, Suit.SPADES, seal=Seal.GOLD)
        effect = apply_card_modifiers(card)
        assert effect.money == 3

    def test_red_seal_retriggers(self):
        """Red seal should set retrigger count to 1."""
        card = Card(Rank.ACE, Suit.SPADES, seal=Seal.RED)
        effect = apply_card_modifiers(card)
        assert effect.retrigger == 1


class TestSteelCardInHand:
    """Test Steel cards held in hand."""

    def test_steel_in_hand_multiplies_mult(self):
        """Steel cards in hand should multiply mult by 1.5."""
        steel = Card(Rank.ACE, Suit.SPADES, enhancement=Enhancement.STEEL)
        _, mult = apply_steel_cards_in_hand([steel])
        assert mult == 1.5

    def test_multiple_steel_stack(self):
        """Multiple Steel cards should stack multiplicatively."""
        steel1 = Card(Rank.ACE, Suit.SPADES, enhancement=Enhancement.STEEL)
        steel2 = Card(Rank.KING, Suit.HEARTS, enhancement=Enhancement.STEEL)
        _, mult = apply_steel_cards_in_hand([steel1, steel2])
        assert mult == 2.25  # 1.5 * 1.5

    def test_no_steel_returns_1(self):
        """No Steel cards should return mult of 1.0."""
        normal = Card(Rank.ACE, Suit.SPADES)
        _, mult = apply_steel_cards_in_hand([normal])
        assert mult == 1.0


class TestCombinedModifierEffects:
    """Test combined modifier effects during scoring."""

    def test_bonus_and_foil_stack_chips(self):
        """Bonus enhancement + Foil edition should stack chips."""
        card = Card(
            Rank.ACE,
            Suit.SPADES,
            enhancement=Enhancement.BONUS,
            edition=Edition.FOIL,
        )
        effect = apply_card_modifiers(card)
        assert effect.chips == 80  # 30 + 50

    def test_mult_and_holo_stack_mult(self):
        """Mult enhancement + Holo edition should stack mult."""
        card = Card(
            Rank.ACE,
            Suit.SPADES,
            enhancement=Enhancement.MULT,
            edition=Edition.HOLOGRAPHIC,
        )
        effect = apply_card_modifiers(card)
        assert effect.mult == 14  # 4 + 10

    def test_glass_and_polychrome_stack_multipliers(self):
        """Glass + Polychrome should stack multipliers."""
        card = Card(
            Rank.ACE,
            Suit.SPADES,
            enhancement=Enhancement.GLASS,
            edition=Edition.POLYCHROME,
        )
        effect = apply_card_modifiers(card)
        assert effect.mult_mult == 3.0  # 2.0 * 1.5


class TestScoringWithModifiers:
    """Test full scoring with card modifiers."""

    def test_scoring_bonus_card(self):
        """Scoring with Bonus card should add chips."""
        bonus_ace = Card(Rank.ACE, Suit.SPADES, enhancement=Enhancement.BONUS)
        cards = [bonus_ace]
        game_state = GameState()

        breakdown = calculate_score(cards, [], game_state)

        # High card (5 chips) + Ace chip value (11) + Bonus (30) = 46 chips
        # Mult = 1 (high card base)
        # Score = 46 * 1 = 46
        assert breakdown.final_chips == 46
        assert breakdown.final_score == 46

    def test_scoring_foil_card(self):
        """Scoring with Foil card should add chips."""
        foil_ace = Card(Rank.ACE, Suit.SPADES, edition=Edition.FOIL)
        cards = [foil_ace]
        game_state = GameState()

        breakdown = calculate_score(cards, [], game_state)

        # High card (5) + Ace (11) + Foil (50) = 66 chips
        assert breakdown.final_chips == 66

    def test_scoring_mult_card(self):
        """Scoring with Mult card should add mult."""
        mult_ace = Card(Rank.ACE, Suit.SPADES, enhancement=Enhancement.MULT)
        cards = [mult_ace]
        game_state = GameState()

        breakdown = calculate_score(cards, [], game_state)

        # High card base mult (1) + Mult enhancement (4) = 5
        assert breakdown.final_mult == 5.0

    def test_scoring_glass_card(self):
        """Scoring with Glass card should multiply mult."""
        glass_ace = Card(Rank.ACE, Suit.SPADES, enhancement=Enhancement.GLASS)
        cards = [glass_ace]
        game_state = GameState()

        breakdown = calculate_score(cards, [], game_state)

        # High card mult (1) * Glass (2.0) = 2.0
        assert breakdown.final_mult == 2.0

    def test_scoring_polychrome_card(self):
        """Scoring with Polychrome card should multiply mult."""
        poly_ace = Card(Rank.ACE, Suit.SPADES, edition=Edition.POLYCHROME)
        cards = [poly_ace]
        game_state = GameState()

        breakdown = calculate_score(cards, [], game_state)

        # High card mult (1) * Polychrome (1.5) = 1.5
        assert breakdown.final_mult == 1.5

    def test_scoring_red_seal_retriggers(self):
        """Red seal should cause card effects to trigger twice."""
        # Red seal Foil card - Foil effect should apply twice
        red_foil = Card(Rank.ACE, Suit.SPADES, edition=Edition.FOIL, seal=Seal.RED)
        cards = [red_foil]
        game_state = GameState()

        breakdown = calculate_score(cards, [], game_state)

        # High card (5) + Ace (11) + Foil (50) * 2 triggers = 116 chips
        assert breakdown.final_chips == 116

    def test_scoring_gold_seal_earns_money(self):
        """Gold seal should earn money."""
        gold_ace = Card(Rank.ACE, Suit.SPADES, seal=Seal.GOLD)
        cards = [gold_ace]
        game_state = GameState()

        breakdown = calculate_score(cards, [], game_state)

        assert breakdown.money_earned == 3

    def test_scoring_steel_in_hand(self):
        """Steel cards in hand should multiply final mult."""
        played = [Card(Rank.ACE, Suit.SPADES)]
        held = [Card(Rank.KING, Suit.HEARTS, enhancement=Enhancement.STEEL)]
        game_state = GameState()

        breakdown = calculate_score(played, [], game_state, cards_in_hand=held)

        # High card mult (1) * Steel in hand (1.5) = 1.5
        assert breakdown.final_mult == 1.5

    def test_scoring_tracks_destroyed_cards(self):
        """Should track which Glass cards were destroyed."""
        import random

        glass = Card(Rank.ACE, Suit.SPADES, enhancement=Enhancement.GLASS)
        cards = [glass]
        game_state = GameState()

        # Use seed that causes destruction
        # Find a seed that destroys the card
        for seed in range(100):
            rng = random.Random(seed)
            if rng.random() < 0.25:
                # This seed will destroy
                breakdown = calculate_score(cards, [], game_state, rng_seed=seed)
                assert len(breakdown.destroyed_cards) == 1
                assert breakdown.destroyed_cards[0] == glass
                return

        pytest.fail("Could not find seed that destroys glass card")


class TestMultipleCardModifiers:
    """Test scoring with multiple modified cards."""

    def test_multiple_foil_cards(self):
        """Multiple Foil cards should each add chips."""
        foil1 = Card(Rank.ACE, Suit.SPADES, edition=Edition.FOIL)
        foil2 = Card(Rank.ACE, Suit.HEARTS, edition=Edition.FOIL)
        cards = [foil1, foil2]
        game_state = GameState()

        breakdown = calculate_score(cards, [], game_state)

        # Pair (10) + Ace (11) * 2 + Foil (50) * 2 = 132 chips
        assert breakdown.final_chips == 132

    def test_multiple_glass_cards_multiply(self):
        """Multiple Glass cards should multiply mult."""
        glass1 = Card(Rank.ACE, Suit.SPADES, enhancement=Enhancement.GLASS)
        glass2 = Card(Rank.ACE, Suit.HEARTS, enhancement=Enhancement.GLASS)
        cards = [glass1, glass2]
        game_state = GameState()

        # Use seed that doesn't destroy
        breakdown = calculate_score(cards, [], game_state, rng_seed=1)

        # Pair mult (2) * Glass (2.0) * Glass (2.0) = 8.0
        assert breakdown.final_mult == 8.0
