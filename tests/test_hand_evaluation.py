"""Tests for poker hand evaluation."""

import pytest

from balatro_bot.hand_evaluation import evaluate_hand, find_best_hand
from balatro_bot.models import Card, HandType


def cards(card_strings: list[str]) -> list[Card]:
    """Helper to create cards from strings."""
    return [Card.from_string(s) for s in card_strings]


class TestHandEvaluation:
    def test_high_card(self):
        result = evaluate_hand(cards(["AS"]))
        assert result.hand_type == HandType.HIGH_CARD
        assert len(result.scoring_cards) == 1

    def test_pair(self):
        result = evaluate_hand(cards(["AS", "AH"]))
        assert result.hand_type == HandType.PAIR
        assert len(result.scoring_cards) == 2

    def test_two_pair(self):
        result = evaluate_hand(cards(["AS", "AH", "KS", "KH", "2C"]))
        assert result.hand_type == HandType.TWO_PAIR
        assert len(result.scoring_cards) == 4

    def test_three_of_a_kind(self):
        result = evaluate_hand(cards(["AS", "AH", "AC"]))
        assert result.hand_type == HandType.THREE_OF_A_KIND
        assert len(result.scoring_cards) == 3

    def test_straight(self):
        result = evaluate_hand(cards(["5S", "6H", "7C", "8D", "9S"]))
        assert result.hand_type == HandType.STRAIGHT
        assert len(result.scoring_cards) == 5

    def test_wheel_straight(self):
        """A-2-3-4-5 straight."""
        result = evaluate_hand(cards(["AS", "2H", "3C", "4D", "5S"]))
        assert result.hand_type == HandType.STRAIGHT

    def test_flush(self):
        result = evaluate_hand(cards(["2S", "5S", "7S", "9S", "KS"]))
        assert result.hand_type == HandType.FLUSH
        assert len(result.scoring_cards) == 5

    def test_full_house(self):
        result = evaluate_hand(cards(["AS", "AH", "AC", "KS", "KH"]))
        assert result.hand_type == HandType.FULL_HOUSE
        assert len(result.scoring_cards) == 5

    def test_four_of_a_kind(self):
        result = evaluate_hand(cards(["AS", "AH", "AC", "AD", "2S"]))
        assert result.hand_type == HandType.FOUR_OF_A_KIND
        assert len(result.scoring_cards) == 4

    def test_straight_flush(self):
        result = evaluate_hand(cards(["5S", "6S", "7S", "8S", "9S"]))
        assert result.hand_type == HandType.STRAIGHT_FLUSH
        assert len(result.scoring_cards) == 5

    def test_royal_flush(self):
        result = evaluate_hand(cards(["10S", "JS", "QS", "KS", "AS"]))
        assert result.hand_type == HandType.ROYAL_FLUSH

    def test_five_of_a_kind(self):
        """Balatro special hand type."""
        result = evaluate_hand(cards(["AS", "AH", "AC", "AD", "AS"]))
        assert result.hand_type == HandType.FIVE_OF_A_KIND

    def test_base_score_calculation(self):
        """Verify chips * mult calculation."""
        result = evaluate_hand(cards(["AS", "AH"]))  # Pair of aces
        # Pair: base 10 chips + 2 mult
        # Scoring cards: 2 aces = 22 chip value
        # Total chips = 10 + 22 = 32
        # Score = 32 * 2 = 64
        assert result.base_chips == 32
        assert result.base_mult == 2
        assert result.base_score == 64

    def test_hand_level_bonus(self):
        """Hand levels increase base chips and mult."""
        result_lvl1 = evaluate_hand(cards(["AS", "AH"]), hand_level=1)
        result_lvl2 = evaluate_hand(cards(["AS", "AH"]), hand_level=2)

        # Level 2 adds another base chips (10) and +1 mult
        assert result_lvl2.base_chips == result_lvl1.base_chips + 10
        assert result_lvl2.base_mult == result_lvl1.base_mult + 1


class TestFindBestHand:
    def test_finds_best_from_7_cards(self):
        """Simulate having 7 cards and finding the best 5."""
        all_cards = cards(["AS", "AH", "KS", "KH", "QS", "QH", "2C"])
        best, result = find_best_hand(all_cards)
        # Best should be two pair (AA, KK) or (AA, QQ) or (KK, QQ)
        # Actually with these cards, three two-pairs are possible
        # The highest would include Aces
        assert result.hand_type == HandType.TWO_PAIR
        assert any(c.rank.value == 14 for c in best)  # Should include aces

    def test_prefers_flush_over_pair(self):
        """Should pick flush over a pair when available."""
        all_cards = cards(["2S", "5S", "7S", "9S", "KS", "AH", "AD"])
        best, result = find_best_hand(all_cards)
        assert result.hand_type == HandType.FLUSH


class TestCardParsing:
    def test_parse_ace_spades(self):
        card = Card.from_string("AS")
        assert str(card) == "A♠"

    def test_parse_ten_hearts(self):
        card = Card.from_string("10H")
        assert str(card) == "10♥"

    def test_parse_lowercase(self):
        card = Card.from_string("ks")
        assert str(card) == "K♠"

    def test_invalid_suit_raises(self):
        with pytest.raises(ValueError, match="Invalid suit"):
            Card.from_string("AX")

    def test_invalid_rank_raises(self):
        with pytest.raises(ValueError, match="Invalid rank"):
            Card.from_string("1S")
