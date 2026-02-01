"""Poker hand evaluation for Balatro.

Identifies the best poker hand from a set of cards and calculates base score.
Handles card modifiers like Wild (all suits) and Stone (+50 chips, always scores).
"""

from collections import Counter
from dataclasses import dataclass

from balatro_bot.models import Card, Enhancement, HandType, Rank, Suit


@dataclass
class HandResult:
    """Result of hand evaluation."""

    hand_type: HandType
    scoring_cards: list[Card]  # Cards that contribute to the score
    base_chips: int
    base_mult: int

    @property
    def base_score(self) -> int:
        """Base score before joker effects: chips * mult."""
        return self.base_chips * self.base_mult


def evaluate_hand(cards: list[Card], hand_level: int = 1) -> HandResult:
    """Evaluate a poker hand and return the best hand type with scoring cards.

    Args:
        cards: List of cards to evaluate (typically 1-5 cards played)
        hand_level: Level of the hand type (from planet cards), increases base values

    Returns:
        HandResult with the identified hand type and scoring information

    Note:
        - Wild cards count as all suits for flush detection
        - Stone cards have no rank/suit but always score with +50 chips
    """
    if not cards:
        raise ValueError("Cannot evaluate empty hand")

    if len(cards) > 5:
        raise ValueError("Cannot evaluate more than 5 cards")

    # Separate stone cards (they always score but don't contribute to hand type)
    stone_cards = [c for c in cards if c.enhancement == Enhancement.STONE]
    normal_cards = [c for c in cards if c.enhancement != Enhancement.STONE]

    # Get rank counts for pattern matching (excluding stone cards)
    rank_counts = Counter(card.rank for card in normal_cards)
    sorted_ranks = sorted([c.rank for c in normal_cards], reverse=True)

    # Check for flush considering wild cards
    is_flush = _check_flush(normal_cards)

    # Check for straight (stone cards don't contribute)
    is_straight = _is_straight(sorted_ranks)

    # Count of each rank frequency
    count_values = sorted(rank_counts.values(), reverse=True) if rank_counts else []

    # Identify hand type and scoring cards
    hand_type, scoring_cards = _identify_hand(
        normal_cards, rank_counts, count_values, is_flush, is_straight, sorted_ranks
    )

    # Stone cards always score in addition to hand scoring cards
    scoring_cards = scoring_cards + stone_cards

    # Calculate base chips from hand type + card chip values
    base_chips = hand_type.base_chips
    # Add level bonus (each level adds base chips again)
    base_chips += (hand_level - 1) * hand_type.base_chips

    # Add chip value of scoring cards
    for card in scoring_cards:
        if card.enhancement == Enhancement.STONE:
            base_chips += 50  # Stone cards give +50 chips
        else:
            base_chips += card.rank.chip_value

    base_mult = hand_type.base_mult + (hand_level - 1)

    return HandResult(
        hand_type=hand_type,
        scoring_cards=scoring_cards,
        base_chips=base_chips,
        base_mult=base_mult,
    )


def _check_flush(cards: list[Card]) -> bool:
    """Check if cards form a flush, considering wild cards.

    Wild cards count as all suits, so they can complete any flush.
    """
    if len(cards) < 5:
        return False

    # Count non-wild cards per suit
    wild_count = sum(1 for c in cards if c.is_wild)
    non_wild = [c for c in cards if not c.is_wild]

    if not non_wild:
        # All wild cards = flush in any suit
        return True

    # Check if any suit + wild cards = 5
    suit_counts = Counter(c.suit for c in non_wild)
    for suit in Suit:
        if suit_counts.get(suit, 0) + wild_count >= 5:
            return True

    return False


def _is_straight(sorted_ranks: list[Rank]) -> bool:
    """Check if ranks form a straight."""
    if len(sorted_ranks) < 5:
        return False

    # Check normal straight
    for i in range(len(sorted_ranks) - 1):
        if sorted_ranks[i] - sorted_ranks[i + 1] != 1:
            break
    else:
        return True

    # Check wheel (A-2-3-4-5)
    if sorted_ranks == [Rank.ACE, Rank.FIVE, Rank.FOUR, Rank.THREE, Rank.TWO]:
        return True

    return False


def _identify_hand(
    cards: list[Card],
    rank_counts: Counter[Rank],
    count_values: list[int],
    is_flush: bool,
    is_straight: bool,
    sorted_ranks: list[Rank],
) -> tuple[HandType, list[Card]]:
    """Identify the hand type and which cards score."""
    n_cards = len(cards)

    # Flush Five (Balatro secret - 5 cards same rank AND same suit)
    if count_values and count_values[0] == 5 and is_flush:
        return HandType.FLUSH_FIVE, cards

    # Five of a kind (Balatro special - requires 5 cards of same rank)
    if count_values and count_values[0] == 5:
        return HandType.FIVE_OF_A_KIND, cards

    # Royal Flush
    if is_flush and is_straight and sorted_ranks[0] == Rank.ACE and sorted_ranks[-1] == Rank.TEN:
        return HandType.ROYAL_FLUSH, cards

    # Straight Flush
    if is_flush and is_straight:
        return HandType.STRAIGHT_FLUSH, cards

    # Four of a kind
    if count_values and count_values[0] == 4:
        scoring = [c for c in cards if rank_counts[c.rank] == 4]
        return HandType.FOUR_OF_A_KIND, scoring

    # Flush House (Balatro secret - Full House AND Flush)
    if count_values[:2] == [3, 2] and is_flush:
        return HandType.FLUSH_HOUSE, cards

    # Full house (3 + 2)
    if count_values[:2] == [3, 2]:
        return HandType.FULL_HOUSE, cards

    # Flush
    if is_flush:
        return HandType.FLUSH, cards

    # Straight
    if is_straight:
        return HandType.STRAIGHT, cards

    # Three of a kind
    if count_values and count_values[0] == 3:
        scoring = [c for c in cards if rank_counts[c.rank] == 3]
        return HandType.THREE_OF_A_KIND, scoring

    # Two pair
    if count_values[:2] == [2, 2]:
        scoring = [c for c in cards if rank_counts[c.rank] == 2]
        return HandType.TWO_PAIR, scoring

    # Pair
    if count_values and count_values[0] == 2:
        scoring = [c for c in cards if rank_counts[c.rank] == 2]
        return HandType.PAIR, scoring

    # High card - only the highest card scores
    if n_cards > 0:
        highest_card = max(cards, key=lambda c: c.rank)
        return HandType.HIGH_CARD, [highest_card]

    return HandType.HIGH_CARD, []


def find_best_hand(cards: list[Card]) -> tuple[list[Card], HandResult]:
    """Find the best 5-card hand from a larger set of cards.

    Used when player has more than 5 cards and needs to find optimal play.

    Args:
        cards: List of cards to choose from

    Returns:
        Tuple of (best 5 cards to play, their evaluation)
    """
    from itertools import combinations

    if len(cards) <= 5:
        return cards, evaluate_hand(cards)

    best_cards: list[Card] = []
    best_result: HandResult | None = None

    for combo in combinations(cards, 5):
        combo_list = list(combo)
        result = evaluate_hand(combo_list)

        if best_result is None or _compare_hands(result, best_result) > 0:
            best_cards = combo_list
            best_result = result

    assert best_result is not None
    return best_cards, best_result


def _compare_hands(a: HandResult, b: HandResult) -> int:
    """Compare two hands. Returns positive if a > b, negative if a < b, 0 if equal."""
    # First compare by hand type
    if a.hand_type != b.hand_type:
        return a.hand_type - b.hand_type

    # Then compare by base score
    return a.base_score - b.base_score
