"""Tests for the deep decision engine."""

import pytest

from balatro_bot.decision_engine import (
    DeepDecisionEngine,
    DecisionConfig,
    EvaluatedAction,
)
from balatro_bot.models import Card, Suit, Rank, GameState, HandType
from balatro_bot.jokers import create_joker
from balatro_bot.deck_tracker import DeckState


class TestLethalityDetection:
    """Tests for lethality detection and safe play selection."""

    def test_detects_lethal_hand(self):
        """Should detect when a hand can beat the blind."""
        engine = DeepDecisionEngine()

        hand = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.QUEEN, Suit.HEARTS),
        ]
        game_state = GameState(hand=hand)

        decision = engine.decide(
            hand=hand,
            jokers=[],
            game_state=game_state,
            blind_chips=300,
            current_chips=200,  # Need 100 more
            hands_remaining=4,
            discards_remaining=3,
        )

        # Three aces should easily beat 100 chips needed
        assert decision.is_lethal
        assert decision.action_type == "play"
        assert "LETHAL" in decision.reasoning

    def test_plays_immediately_when_lethal(self):
        """Should play immediately when lethal, not discard."""
        engine = DeepDecisionEngine()

        # Hand with pair that beats the blind
        hand = [
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.TWO, Suit.DIAMONDS),
            Card(Rank.THREE, Suit.HEARTS),
            Card(Rank.FOUR, Suit.CLUBS),
        ]
        game_state = GameState(hand=hand)

        decision = engine.decide(
            hand=hand,
            jokers=[],
            game_state=game_state,
            blind_chips=50,  # Very low - pair of kings easily beats this
            current_chips=0,
            hands_remaining=4,
            discards_remaining=3,
        )

        # Should play, not discard even though hand could improve
        assert decision.action_type == "play"
        assert decision.is_lethal

    def test_chooses_safest_lethal(self):
        """When multiple lethal options, choose highest score."""
        engine = DeepDecisionEngine()

        # Hand with multiple lethal options
        hand = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.ACE, Suit.CLUBS),
            Card(Rank.KING, Suit.HEARTS),
        ]
        game_state = GameState(hand=hand)

        decision = engine.decide(
            hand=hand,
            jokers=[],
            game_state=game_state,
            blind_chips=100,
            current_chips=0,
            hands_remaining=4,
            discards_remaining=3,
        )

        # Should choose four aces over pair of aces
        assert decision.hand_type == HandType.FOUR_OF_A_KIND
        assert decision.is_lethal


class TestNonLethalDecisions:
    """Tests for decisions when no lethal hand is available."""

    def test_prefers_stronger_hand_types(self):
        """Should prefer stronger hand types when not lethal."""
        engine = DeepDecisionEngine()

        # Can make pair or high card
        hand = [
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.TWO, Suit.DIAMONDS),
            Card(Rank.THREE, Suit.HEARTS),
            Card(Rank.FOUR, Suit.CLUBS),
        ]
        game_state = GameState(hand=hand)

        decision = engine.decide(
            hand=hand,
            jokers=[],
            game_state=game_state,
            blind_chips=10000,  # Very high - not lethal
            current_chips=0,
            hands_remaining=4,
            discards_remaining=3,
        )

        # Should play pair of kings
        assert decision.hand_type == HandType.PAIR
        assert len(decision.cards) == 2

    def test_considers_discard_for_weak_hand(self):
        """May consider discard when hand is very weak."""
        engine = DeepDecisionEngine()

        # Very weak hand - all different ranks, no flush potential
        hand = [
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.FOUR, Suit.SPADES),
            Card(Rank.SIX, Suit.DIAMONDS),
            Card(Rank.EIGHT, Suit.CLUBS),
            Card(Rank.TEN, Suit.HEARTS),
        ]
        game_state = GameState(hand=hand)

        # Engine should at least evaluate discards
        # (whether it chooses to discard depends on EV calculations)
        decision = engine.decide(
            hand=hand,
            jokers=[],
            game_state=game_state,
            blind_chips=10000,
            current_chips=0,
            hands_remaining=4,
            discards_remaining=3,
        )

        # Should make some decision
        assert decision.action_type in ["play", "discard"]


class TestVarianceAwareness:
    """Tests for variance-adjusted decision making."""

    def test_high_variance_weight_late_game(self):
        """Should penalize variance heavily with few hands left."""
        config = DecisionConfig()
        engine = DeepDecisionEngine(config)

        hand = [
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.FIVE, Suit.DIAMONDS),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.NINE, Suit.CLUBS),
        ]
        game_state = GameState(hand=hand)

        # Late game - should prefer deterministic play
        weight = engine._get_variance_weight(
            chips_needed=5000,
            hands_remaining=1,  # Last hand
            blind_total=10000,
        )

        assert weight == config.late_game_variance_weight

    def test_low_variance_weight_early_game(self):
        """Should allow variance early in the game."""
        config = DecisionConfig()
        engine = DeepDecisionEngine(config)

        weight = engine._get_variance_weight(
            chips_needed=8000,
            hands_remaining=4,  # Full hands
            blind_total=10000,
        )

        assert weight == config.early_game_variance_weight


class TestSafetyMargin:
    """Tests for discard safety margin calculation."""

    def test_higher_margin_near_lethal(self):
        """Safety margin should be higher when near lethal."""
        engine = DeepDecisionEngine()

        margin_near = engine._calculate_safety_margin(
            chips_needed=100,
            current_hand_score=90,  # Very close to lethal
            hands_remaining=4,
            discards_remaining=3,
            is_boss_blind=False,
        )

        margin_far = engine._calculate_safety_margin(
            chips_needed=10000,
            current_hand_score=100,  # Far from lethal
            hands_remaining=4,
            discards_remaining=3,
            is_boss_blind=False,
        )

        assert margin_near > margin_far

    def test_higher_margin_boss_blind(self):
        """Safety margin should be higher for boss blinds."""
        engine = DeepDecisionEngine()

        margin_boss = engine._calculate_safety_margin(
            chips_needed=5000,
            current_hand_score=100,
            hands_remaining=4,
            discards_remaining=3,
            is_boss_blind=True,
        )

        margin_normal = engine._calculate_safety_margin(
            chips_needed=5000,
            current_hand_score=100,
            hands_remaining=4,
            discards_remaining=3,
            is_boss_blind=False,
        )

        assert margin_boss > margin_normal

    def test_higher_margin_low_discards(self):
        """Safety margin should be higher with few discards left."""
        engine = DeepDecisionEngine()

        margin_low = engine._calculate_safety_margin(
            chips_needed=5000,
            current_hand_score=100,
            hands_remaining=4,
            discards_remaining=1,
            is_boss_blind=False,
        )

        margin_high = engine._calculate_safety_margin(
            chips_needed=5000,
            current_hand_score=100,
            hands_remaining=4,
            discards_remaining=3,
            is_boss_blind=False,
        )

        assert margin_low > margin_high


class TestJokerIntegration:
    """Tests for joker effect integration."""

    def test_joker_affects_score(self):
        """Jokers should affect expected score calculation."""
        engine = DeepDecisionEngine()

        hand = [
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.FIVE, Suit.DIAMONDS),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.NINE, Suit.CLUBS),
        ]
        game_state = GameState(hand=hand)

        # Without jokers
        decision_no_joker = engine.decide(
            hand=hand,
            jokers=[],
            game_state=game_state,
            blind_chips=10000,
            current_chips=0,
            hands_remaining=4,
            discards_remaining=3,
        )

        # With joker that adds mult
        joker = create_joker("joker")  # Basic +4 mult joker
        decision_with_joker = engine.decide(
            hand=hand,
            jokers=[joker],
            game_state=game_state,
            blind_chips=10000,
            current_chips=0,
            hands_remaining=4,
            discards_remaining=3,
        )

        # Score should be higher with joker
        assert decision_with_joker.expected_score > decision_no_joker.expected_score


class TestDeckDamage:
    """Tests for deck damage penalty calculation."""

    def test_penalizes_discarding_aces(self):
        """Should penalize discarding high value cards."""
        engine = DeepDecisionEngine()
        deck_state = DeckState()

        # Discarding an ace
        damage_ace = engine._calculate_deck_damage(
            cards_to_discard=[Card(Rank.ACE, Suit.HEARTS)],
            deck_state=deck_state,
            jokers=[],
        )

        # Discarding a two
        damage_two = engine._calculate_deck_damage(
            cards_to_discard=[Card(Rank.TWO, Suit.HEARTS)],
            deck_state=deck_state,
            jokers=[],
        )

        assert damage_ace > damage_two

    def test_penalizes_discarding_joker_synergy_cards(self):
        """Should penalize discarding cards that work with jokers."""
        engine = DeepDecisionEngine()
        deck_state = DeckState()

        # Greedy joker likes diamonds
        greedy = create_joker("greedy_joker")

        # Discarding a diamond when we have greedy joker
        damage_diamond = engine._calculate_deck_damage(
            cards_to_discard=[Card(Rank.TWO, Suit.DIAMONDS)],
            deck_state=deck_state,
            jokers=[greedy],
        )

        # Discarding a heart (no synergy)
        damage_heart = engine._calculate_deck_damage(
            cards_to_discard=[Card(Rank.TWO, Suit.HEARTS)],
            deck_state=deck_state,
            jokers=[greedy],
        )

        assert damage_diamond > damage_heart


class TestEvaluatedAction:
    """Tests for EvaluatedAction dataclass."""

    def test_add_reason(self):
        """Should accumulate reasoning."""
        action = EvaluatedAction(
            action_type="play",
            card_indices=[0, 1],
            cards=[],
            expected_score=100,
        )

        action.add_reason("PAIR")
        action.add_reason("high cards")

        assert "PAIR" in action.reasoning
        assert "high cards" in action.reasoning
        assert len(action.reasoning) == 2
