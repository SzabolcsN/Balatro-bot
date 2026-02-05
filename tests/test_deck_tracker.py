"""Tests for deck state tracking."""

import pytest

from balatro_bot.deck_tracker import DeckState, create_standard_deck
from balatro_bot.models import Card, Suit, Rank


class TestCreateStandardDeck:
    """Tests for standard deck creation."""

    def test_creates_52_cards(self):
        """Standard deck has 52 cards."""
        deck = create_standard_deck()
        assert len(deck) == 52

    def test_has_all_suits(self):
        """Deck has 13 cards of each suit."""
        deck = create_standard_deck()
        for suit in Suit:
            suit_cards = [c for c in deck if c.suit == suit]
            assert len(suit_cards) == 13

    def test_has_all_ranks(self):
        """Deck has 4 cards of each rank."""
        deck = create_standard_deck()
        for rank in Rank:
            rank_cards = [c for c in deck if c.rank == rank]
            assert len(rank_cards) == 4

    def test_no_duplicates(self):
        """Each card appears exactly once."""
        deck = create_standard_deck()
        seen = set()
        for card in deck:
            key = (card.rank, card.suit)
            assert key not in seen
            seen.add(key)


class TestDeckStateBasics:
    """Tests for basic DeckState functionality."""

    def test_default_is_full_deck(self):
        """New DeckState starts with full deck."""
        state = DeckState()
        assert state.total_remaining == 52

    def test_suit_count_full_deck(self):
        """Each suit has 13 cards in full deck."""
        state = DeckState()
        for suit in Suit:
            assert state.suit_count(suit) == 13

    def test_rank_count_full_deck(self):
        """Each rank has 4 cards in full deck."""
        state = DeckState()
        for rank in Rank:
            assert state.rank_count(rank) == 4

    def test_card_count(self):
        """Specific card appears once in full deck."""
        state = DeckState()
        assert state.card_count(Rank.ACE, Suit.SPADES) == 1


class TestDeckStateRemoval:
    """Tests for removing cards from deck."""

    def test_remove_single_card(self):
        """Removing a card decreases counts."""
        state = DeckState()
        card = Card(Rank.ACE, Suit.SPADES)

        assert state.remove_card(card, played=True)

        assert state.total_remaining == 51
        assert state.rank_count(Rank.ACE) == 3
        assert state.suit_count(Suit.SPADES) == 12
        assert state.card_count(Rank.ACE, Suit.SPADES) == 0

    def test_remove_card_adds_to_played(self):
        """Removed card goes to played pile."""
        state = DeckState()
        card = Card(Rank.ACE, Suit.SPADES)

        state.remove_card(card, played=True)

        assert len(state.cards_played) == 1
        assert state.cards_played[0].rank == Rank.ACE

    def test_remove_card_adds_to_discarded(self):
        """Discarded card goes to discard pile."""
        state = DeckState()
        card = Card(Rank.ACE, Suit.SPADES)

        state.remove_card(card, played=False)

        assert len(state.cards_discarded) == 1
        assert len(state.cards_played) == 0

    def test_remove_nonexistent_card(self):
        """Removing card twice returns False."""
        state = DeckState()
        card = Card(Rank.ACE, Suit.SPADES)

        assert state.remove_card(card) == True
        assert state.remove_card(card) == False

    def test_remove_multiple_cards(self):
        """Remove multiple cards at once."""
        state = DeckState()
        cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.KING, Suit.SPADES),
        ]

        removed = state.remove_cards(cards, played=True)

        assert removed == 3
        assert state.total_remaining == 49
        assert state.rank_count(Rank.ACE) == 2

    def test_total_seen(self):
        """total_seen counts played + discarded."""
        state = DeckState()
        state.remove_card(Card(Rank.ACE, Suit.SPADES), played=True)
        state.remove_card(Card(Rank.KING, Suit.HEARTS), played=False)

        assert state.total_seen == 2


class TestDeckStateFromKnownCards:
    """Tests for creating deck state from known cards."""

    def test_from_hand_only(self):
        """Create state knowing only the hand."""
        hand = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.QUEEN, Suit.DIAMONDS),
        ]

        state = DeckState.from_known_cards(hand)

        assert state.total_remaining == 49
        assert state.card_count(Rank.ACE, Suit.SPADES) == 0
        assert state.card_count(Rank.ACE, Suit.HEARTS) == 1

    def test_from_hand_and_played(self):
        """Create state with hand and played cards."""
        hand = [Card(Rank.ACE, Suit.SPADES)]
        played = [Card(Rank.KING, Suit.HEARTS)]

        state = DeckState.from_known_cards(
            cards_in_hand=hand,
            cards_played=played,
        )

        assert state.total_remaining == 50
        assert state.card_count(Rank.ACE, Suit.SPADES) == 0
        assert state.card_count(Rank.KING, Suit.HEARTS) == 0

    def test_from_all_known(self):
        """Create state with all card categories."""
        hand = [Card(Rank.ACE, Suit.SPADES)]
        played = [Card(Rank.KING, Suit.HEARTS)]
        discarded = [Card(Rank.QUEEN, Suit.DIAMONDS)]

        state = DeckState.from_known_cards(
            cards_in_hand=hand,
            cards_played=played,
            cards_discarded=discarded,
        )

        assert state.total_remaining == 49


class TestDeckStateClone:
    """Tests for cloning deck state."""

    def test_clone_is_independent(self):
        """Changes to clone don't affect original."""
        original = DeckState()
        clone = original.clone()

        clone.remove_card(Card(Rank.ACE, Suit.SPADES))

        assert original.total_remaining == 52
        assert clone.total_remaining == 51

    def test_clone_preserves_state(self):
        """Clone has same cards as original."""
        original = DeckState()
        original.remove_card(Card(Rank.ACE, Suit.SPADES))

        clone = original.clone()

        assert clone.total_remaining == 51
        assert clone.card_count(Rank.ACE, Suit.SPADES) == 0


class TestDeckStateReset:
    """Tests for resetting deck state."""

    def test_reset_restores_full_deck(self):
        """Reset returns to 52 cards."""
        state = DeckState()
        state.remove_cards([
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.KING, Suit.HEARTS),
        ])

        state.reset()

        assert state.total_remaining == 52
        assert len(state.cards_played) == 0
        assert len(state.cards_discarded) == 0


class TestDeckStateDistributions:
    """Tests for distribution queries."""

    def test_suit_distribution(self):
        """Get suit distribution."""
        state = DeckState()
        state.remove_cards([
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.KING, Suit.HEARTS),
        ])

        dist = state.get_suit_distribution()

        assert dist[Suit.HEARTS] == 11
        assert dist[Suit.SPADES] == 13

    def test_rank_distribution(self):
        """Get rank distribution."""
        state = DeckState()
        state.remove_cards([
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.SPADES),
        ])

        dist = state.get_rank_distribution()

        assert dist[Rank.ACE] == 2
        assert dist[Rank.KING] == 4

    def test_high_card_count(self):
        """Count high cards (10, J, Q, K, A)."""
        state = DeckState()

        # Full deck: 5 high ranks × 4 suits = 20
        assert state.get_high_card_count() == 20

        state.remove_card(Card(Rank.ACE, Suit.SPADES))
        assert state.get_high_card_count() == 19

    def test_face_card_count(self):
        """Count face cards (J, Q, K)."""
        state = DeckState()

        # Full deck: 3 face ranks × 4 suits = 12
        assert state.get_face_card_count() == 12


class TestDeckStateStraightPotential:
    """Tests for straight potential analysis."""

    def test_open_ended_straight_draw(self):
        """Detect open-ended straight draw."""
        state = DeckState()
        # Remove the 4s and 9s we need
        # Keep them in deck for potential

        hand_ranks = {Rank.FIVE, Rank.SIX, Rank.SEVEN, Rank.EIGHT}
        potential = state.has_straight_potential(hand_ranks)

        # Open-ended: can hit 4 or 9
        assert potential["open_ended"] >= 1
        assert potential["best_outs"] == 4  # 4 fours or 4 nines

    def test_gutshot_straight_draw(self):
        """Detect gutshot straight draw."""
        state = DeckState()

        # 5-6-X-8-9 (missing 7)
        hand_ranks = {Rank.FIVE, Rank.SIX, Rank.EIGHT, Rank.NINE}
        potential = state.has_straight_potential(hand_ranks)

        assert potential["gutshot"] >= 1
        assert potential["best_outs"] == 4  # 4 sevens

    def test_no_straight_potential(self):
        """No straight draw with scattered cards."""
        state = DeckState()

        hand_ranks = {Rank.TWO, Rank.FIVE, Rank.NINE, Rank.KING}
        potential = state.has_straight_potential(hand_ranks)

        assert potential["open_ended"] == 0
        assert potential["best_outs"] == 0


class TestDeckStateStr:
    """Tests for string representation."""

    def test_str_format(self):
        """String shows card counts."""
        state = DeckState()
        s = str(state)

        assert "52 cards" in s
        assert "S:13" in s or "SPADES" in s.upper()
