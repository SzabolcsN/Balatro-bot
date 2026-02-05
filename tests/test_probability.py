"""Tests for probability calculations."""

import pytest
from math import isclose

from balatro_bot.probability import (
    hypergeometric_pmf,
    hypergeometric_cdf_at_least,
    flush_completion_probability,
    straight_completion_probability,
    pair_upgrade_probability,
    calculate_all_completion_probabilities,
)
from balatro_bot.deck_tracker import DeckState
from balatro_bot.models import Card, Suit, Rank, HandType


class TestHypergeometricPMF:
    """Tests for hypergeometric probability mass function."""

    def test_simple_case(self):
        """Drawing 1 success from pool of 4 successes in 10 cards, 1 draw."""
        # P(exactly 1 success) when drawing 1 card from 10, where 4 are successes
        prob = hypergeometric_pmf(
            successes_in_pop=4,
            population_size=10,
            draws=1,
            exactly_k_successes=1,
        )
        assert isclose(prob, 0.4, rel_tol=0.01)

    def test_impossible_case_not_enough_successes(self):
        """Can't draw more successes than exist."""
        prob = hypergeometric_pmf(
            successes_in_pop=2,
            population_size=10,
            draws=5,
            exactly_k_successes=3,
        )
        assert prob == 0.0

    def test_impossible_case_not_enough_draws(self):
        """Can't get more successes than draws."""
        prob = hypergeometric_pmf(
            successes_in_pop=10,
            population_size=20,
            draws=2,
            exactly_k_successes=3,
        )
        assert prob == 0.0

    def test_certain_case(self):
        """When all cards are successes, P(all successes) = 1."""
        prob = hypergeometric_pmf(
            successes_in_pop=5,
            population_size=5,
            draws=5,
            exactly_k_successes=5,
        )
        assert isclose(prob, 1.0, rel_tol=0.01)

    def test_flush_draw_scenario(self):
        """Realistic flush draw: 9 hearts in 47 cards, draw 5, need 2."""
        # This is a common scenario: have 3 hearts, deck has 9 hearts left
        prob = hypergeometric_pmf(
            successes_in_pop=9,
            population_size=47,
            draws=5,
            exactly_k_successes=2,
        )
        # Should be reasonable probability
        assert 0.1 < prob < 0.3


class TestHypergeometricCDF:
    """Tests for cumulative distribution (at least k)."""

    def test_at_least_zero(self):
        """P(X >= 0) is always 1."""
        prob = hypergeometric_cdf_at_least(
            successes_in_pop=5,
            population_size=20,
            draws=3,
            at_least_k_successes=0,
        )
        assert prob == 1.0

    def test_at_least_one(self):
        """P(X >= 1) = 1 - P(X = 0)."""
        # 4 aces in 52 cards, draw 5, P(at least 1 ace)
        prob = hypergeometric_cdf_at_least(
            successes_in_pop=4,
            population_size=52,
            draws=5,
            at_least_k_successes=1,
        )
        # Should be fairly high
        assert 0.3 < prob < 0.5

    def test_flush_completion(self):
        """P(completing flush): 3 hearts in hand, 9 in deck, draw 2, need 2."""
        prob = hypergeometric_cdf_at_least(
            successes_in_pop=9,
            population_size=44,
            draws=2,
            at_least_k_successes=2,
        )
        # Should be around 3-5%
        assert 0.02 < prob < 0.10


class TestFlushCompletionProbability:
    """Tests for flush completion calculations."""

    def test_already_have_flush(self):
        """If we already have 5 of a suit, probability is 1."""
        hand = [
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.JACK, Suit.HEARTS),
            Card(Rank.ACE, Suit.HEARTS),
        ]
        deck = DeckState.from_known_cards(hand)

        probs = flush_completion_probability(hand, deck, draws=3)
        assert probs[Suit.HEARTS] == 1.0

    def test_four_to_flush(self):
        """4 hearts, need 1 more, should have decent probability."""
        hand = [
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.JACK, Suit.HEARTS),
            Card(Rank.ACE, Suit.SPADES),  # One off-suit
        ]
        deck = DeckState.from_known_cards(hand)

        probs = flush_completion_probability(hand, deck, draws=3)

        # 9 hearts in 47 cards, drawing 3, need 1
        # P(at least 1) should be high
        assert probs[Suit.HEARTS] > 0.4

    def test_three_to_flush(self):
        """3 hearts, need 2 more, lower probability."""
        hand = [
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.JACK, Suit.SPADES),
            Card(Rank.ACE, Suit.SPADES),
        ]
        deck = DeckState.from_known_cards(hand)

        probs = flush_completion_probability(hand, deck, draws=3)

        # Need 2 hearts from 10 in 47 cards
        assert 0.05 < probs[Suit.HEARTS] < 0.25

    def test_no_draws_no_flush(self):
        """With 0 draws, can only have flush if already present."""
        hand = [
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.SEVEN, Suit.SPADES),
        ]
        deck = DeckState.from_known_cards(hand)

        probs = flush_completion_probability(hand, deck, draws=0)
        assert probs[Suit.HEARTS] == 0.0


class TestStraightCompletionProbability:
    """Tests for straight completion calculations."""

    def test_already_have_straight(self):
        """If we have a straight, probability is 1."""
        hand = [
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.SIX, Suit.SPADES),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.EIGHT, Suit.CLUBS),
            Card(Rank.NINE, Suit.DIAMONDS),
        ]
        deck = DeckState.from_known_cards(hand)

        prob = straight_completion_probability(hand, deck, draws=3)
        assert prob == 1.0

    def test_open_ended_straight_draw(self):
        """4 consecutive cards, need either end."""
        hand = [
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.SIX, Suit.SPADES),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.EIGHT, Suit.CLUBS),
            Card(Rank.TWO, Suit.DIAMONDS),  # Unrelated card
        ]
        deck = DeckState.from_known_cards(hand)

        prob = straight_completion_probability(hand, deck, draws=3)

        # Need a 4 or 9, 4 cards of each in 47 cards, drawing 3
        # P(at least one 4 or 9) should be reasonable
        assert prob > 0.2

    def test_gutshot_straight_draw(self):
        """Missing middle card for straight."""
        hand = [
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.SIX, Suit.SPADES),
            # Missing 7
            Card(Rank.EIGHT, Suit.CLUBS),
            Card(Rank.NINE, Suit.DIAMONDS),
            Card(Rank.TWO, Suit.HEARTS),
        ]
        deck = DeckState.from_known_cards(hand)

        prob = straight_completion_probability(hand, deck, draws=3)

        # Need exactly a 7, 4 available
        assert 0.1 < prob < 0.4

    def test_wheel_straight(self):
        """Ace-low straight (A-2-3-4-5)."""
        hand = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.TWO, Suit.SPADES),
            Card(Rank.THREE, Suit.HEARTS),
            Card(Rank.FOUR, Suit.CLUBS),
            Card(Rank.KING, Suit.DIAMONDS),  # Unrelated
        ]
        deck = DeckState.from_known_cards(hand)

        prob = straight_completion_probability(hand, deck, draws=3)

        # Need a 5
        assert prob > 0.2


class TestPairUpgradeProbability:
    """Tests for upgrading pairs to better hands."""

    def test_pair_to_trips(self):
        """Upgrade pair to three of a kind."""
        hand = [
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.SEVEN, Suit.CLUBS),
            Card(Rank.TWO, Suit.DIAMONDS),
        ]
        deck = DeckState.from_known_cards(hand)

        prob = pair_upgrade_probability(
            hand, deck, draws=3, target=HandType.THREE_OF_A_KIND
        )

        # 2 kings in 47 cards, draw 3, need 1
        assert prob > 0.1

    def test_trips_to_quads(self):
        """Upgrade trips to four of a kind."""
        hand = [
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.KING, Suit.CLUBS),
            Card(Rank.SEVEN, Suit.CLUBS),
            Card(Rank.TWO, Suit.DIAMONDS),
        ]
        deck = DeckState.from_known_cards(hand)

        prob = pair_upgrade_probability(
            hand, deck, draws=3, target=HandType.FOUR_OF_A_KIND
        )

        # 1 king in 47 cards, need to draw it
        assert 0.05 < prob < 0.15

    def test_no_pair_no_upgrade(self):
        """Can't upgrade to trips without a pair."""
        hand = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.QUEEN, Suit.HEARTS),
            Card(Rank.JACK, Suit.CLUBS),
            Card(Rank.TEN, Suit.DIAMONDS),
        ]
        deck = DeckState.from_known_cards(hand)

        prob = pair_upgrade_probability(
            hand, deck, draws=3, target=HandType.THREE_OF_A_KIND
        )

        assert prob == 0.0


class TestCalculateAllCompletionProbabilities:
    """Tests for the combined probability calculator."""

    def test_returns_all_probabilities(self):
        """Should return probabilities for all hand types."""
        hand = [
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.TWO, Suit.HEARTS),
        ]
        deck = DeckState.from_known_cards(hand)

        probs = calculate_all_completion_probabilities(hand, deck, draws=3)

        assert isinstance(probs.flush, dict)
        assert len(probs.flush) == 4  # All suits
        assert 0 <= probs.straight <= 1
        assert 0 <= probs.three_of_a_kind <= 1
        assert 0 <= probs.full_house <= 1
        assert 0 <= probs.four_of_a_kind <= 1

    def test_best_flush_property(self):
        """best_flush should return max flush probability."""
        hand = [
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.JACK, Suit.HEARTS),
            Card(Rank.ACE, Suit.SPADES),
        ]
        deck = DeckState.from_known_cards(hand)

        probs = calculate_all_completion_probabilities(hand, deck, draws=3)

        assert probs.best_flush == probs.flush[Suit.HEARTS]
        assert probs.best_flush > probs.flush[Suit.SPADES]

    def test_best_improvement(self):
        """best_improvement should return highest probability option."""
        hand = [
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.FIVE, Suit.CLUBS),
            Card(Rank.SEVEN, Suit.DIAMONDS),
            Card(Rank.TWO, Suit.HEARTS),
        ]
        deck = DeckState.from_known_cards(hand)

        probs = calculate_all_completion_probabilities(hand, deck, draws=3)
        name, prob = probs.best_improvement()

        assert name in ["flush", "straight", "three_of_a_kind", "full_house", "four_of_a_kind"]
        assert prob >= 0
