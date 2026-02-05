"""Performance benchmarks for the decision engine."""

import time
import pytest

from balatro_bot.decision_engine import DeepDecisionEngine, DecisionConfig
from balatro_bot.models import Card, Suit, Rank, GameState
from balatro_bot.jokers import create_joker
from balatro_bot.deck_tracker import DeckState


class TestDecisionPerformance:
    """Performance tests for decision making."""

    def test_decision_under_100ms_simple(self):
        """Decision should complete in under 100ms for simple hands."""
        engine = DeepDecisionEngine()

        hand = [
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.FIVE, Suit.DIAMONDS),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.NINE, Suit.CLUBS),
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.THREE, Suit.SPADES),
            Card(Rank.FOUR, Suit.DIAMONDS),
        ]
        game_state = GameState(hand=hand)
        deck_state = DeckState.from_known_cards(hand)

        start = time.perf_counter()
        decision = engine.decide(
            hand=hand,
            jokers=[],
            game_state=game_state,
            blind_chips=1000,
            current_chips=0,
            hands_remaining=4,
            discards_remaining=3,
            deck_state=deck_state,
        )
        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms

        assert elapsed < 100, f"Decision took {elapsed:.1f}ms, expected <100ms"
        assert decision is not None

    def test_decision_under_100ms_with_jokers(self):
        """Decision should complete in under 100ms with jokers."""
        engine = DeepDecisionEngine()

        hand = [
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.FIVE, Suit.DIAMONDS),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.NINE, Suit.CLUBS),
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.THREE, Suit.SPADES),
            Card(Rank.FOUR, Suit.DIAMONDS),
        ]

        jokers = [
            create_joker("joker"),
            create_joker("greedy_joker"),
            create_joker("half_joker"),
        ]

        game_state = GameState(hand=hand)
        deck_state = DeckState.from_known_cards(hand)

        start = time.perf_counter()
        decision = engine.decide(
            hand=hand,
            jokers=jokers,
            game_state=game_state,
            blind_chips=5000,
            current_chips=0,
            hands_remaining=4,
            discards_remaining=3,
            deck_state=deck_state,
        )
        elapsed = (time.perf_counter() - start) * 1000

        assert elapsed < 100, f"Decision took {elapsed:.1f}ms, expected <100ms"
        assert decision is not None

    def test_decision_under_200ms_worst_case(self):
        """Decision should complete in under 200ms for worst case (full hand, all discards)."""
        engine = DeepDecisionEngine()

        # Full 8-card hand
        hand = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.QUEEN, Suit.DIAMONDS),
            Card(Rank.JACK, Suit.CLUBS),
            Card(Rank.TEN, Suit.HEARTS),
            Card(Rank.NINE, Suit.SPADES),
            Card(Rank.EIGHT, Suit.DIAMONDS),
            Card(Rank.SEVEN, Suit.CLUBS),
        ]

        jokers = [
            create_joker("joker"),
            create_joker("lusty_joker"),
            create_joker("jolly_joker"),
            create_joker("the_duo"),
        ]

        game_state = GameState(hand=hand)
        deck_state = DeckState.from_known_cards(hand)

        start = time.perf_counter()
        decision = engine.decide(
            hand=hand,
            jokers=jokers,
            game_state=game_state,
            blind_chips=10000,
            current_chips=0,
            hands_remaining=4,
            discards_remaining=4,  # Full discards
            deck_state=deck_state,
        )
        elapsed = (time.perf_counter() - start) * 1000

        # Worst case with discard evaluation might take longer
        assert elapsed < 200, f"Decision took {elapsed:.1f}ms, expected <200ms"
        assert decision is not None

    def test_average_decision_time(self):
        """Average decision time across multiple scenarios."""
        engine = DeepDecisionEngine()

        scenarios = [
            # (hand, jokers, blind_chips, discards)
            (
                [Card(Rank.ACE, Suit.HEARTS), Card(Rank.ACE, Suit.SPADES),
                 Card(Rank.TWO, Suit.DIAMONDS), Card(Rank.THREE, Suit.CLUBS),
                 Card(Rank.FOUR, Suit.HEARTS)],
                [], 300, 3
            ),
            (
                [Card(Rank.KING, Suit.HEARTS), Card(Rank.QUEEN, Suit.HEARTS),
                 Card(Rank.JACK, Suit.HEARTS), Card(Rank.TEN, Suit.HEARTS),
                 Card(Rank.NINE, Suit.HEARTS), Card(Rank.TWO, Suit.SPADES)],
                [create_joker("joker")], 1000, 2
            ),
            (
                [Card(Rank.TWO, Suit.HEARTS), Card(Rank.FOUR, Suit.SPADES),
                 Card(Rank.SIX, Suit.DIAMONDS), Card(Rank.EIGHT, Suit.CLUBS),
                 Card(Rank.TEN, Suit.HEARTS), Card(Rank.QUEEN, Suit.SPADES),
                 Card(Rank.ACE, Suit.DIAMONDS)],
                [create_joker("half_joker"), create_joker("greedy_joker")], 5000, 4
            ),
        ]

        times = []
        for hand, jokers, blind, discards in scenarios:
            game_state = GameState(hand=hand)
            deck_state = DeckState.from_known_cards(hand)

            start = time.perf_counter()
            engine.decide(
                hand=hand,
                jokers=jokers,
                game_state=game_state,
                blind_chips=blind,
                current_chips=0,
                hands_remaining=4,
                discards_remaining=discards,
                deck_state=deck_state,
            )
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        assert avg_time < 50, f"Average decision time {avg_time:.1f}ms, expected <50ms"
        assert max_time < 150, f"Max decision time {max_time:.1f}ms, expected <150ms"

    def test_lethal_detection_fast(self):
        """Lethal detection should be very fast."""
        engine = DeepDecisionEngine()

        # Clear lethal hand
        hand = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.ACE, Suit.CLUBS),
            Card(Rank.KING, Suit.HEARTS),
        ]

        game_state = GameState(hand=hand)
        deck_state = DeckState.from_known_cards(hand)

        start = time.perf_counter()
        decision = engine.decide(
            hand=hand,
            jokers=[],
            game_state=game_state,
            blind_chips=100,  # Easy lethal
            current_chips=0,
            hands_remaining=4,
            discards_remaining=3,
            deck_state=deck_state,
        )
        elapsed = (time.perf_counter() - start) * 1000

        assert elapsed < 50, f"Lethal decision took {elapsed:.1f}ms, expected <50ms"
        assert decision.is_lethal


class TestProbabilityPerformance:
    """Performance tests for probability calculations."""

    def test_flush_probability_fast(self):
        """Flush probability calculation should be fast."""
        from balatro_bot.probability import flush_completion_probability

        hand = [
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.JACK, Suit.SPADES),
            Card(Rank.ACE, Suit.DIAMONDS),
        ]
        deck_state = DeckState.from_known_cards(hand)

        start = time.perf_counter()
        for _ in range(100):
            flush_completion_probability(hand, deck_state, draws=3)
        elapsed = (time.perf_counter() - start) * 1000

        avg_time = elapsed / 100
        assert avg_time < 1, f"Average flush calc {avg_time:.2f}ms, expected <1ms"

    def test_all_probabilities_fast(self):
        """All probability calculations together should be fast."""
        from balatro_bot.probability import calculate_all_completion_probabilities

        hand = [
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.NINE, Suit.CLUBS),
        ]
        deck_state = DeckState.from_known_cards(hand)

        start = time.perf_counter()
        for _ in range(100):
            calculate_all_completion_probabilities(hand, deck_state, draws=3)
        elapsed = (time.perf_counter() - start) * 1000

        avg_time = elapsed / 100
        assert avg_time < 5, f"Average all probs calc {avg_time:.2f}ms, expected <5ms"
