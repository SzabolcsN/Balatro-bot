"""Probability calculations for Balatro decision making.

Provides hypergeometric probability functions for calculating
the likelihood of completing various poker hands given the
current hand and remaining deck composition.
"""

from dataclasses import dataclass
from math import comb
from collections import Counter
from typing import TYPE_CHECKING

from .models import Card, Suit, Rank, HandType

if TYPE_CHECKING:
    from .deck_tracker import DeckState


def hypergeometric_pmf(
    successes_in_pop: int,
    population_size: int,
    draws: int,
    exactly_k_successes: int,
) -> float:
    """Calculate probability of exactly k successes in hypergeometric distribution.

    This models drawing without replacement, which is exactly how
    Balatro's deck works.

    Args:
        successes_in_pop: Number of "success" cards in remaining deck
        population_size: Total cards in remaining deck
        draws: Number of cards to draw
        exactly_k_successes: Exact number of successes needed

    Returns:
        Probability of getting exactly k successes
    """
    if draws > population_size:
        return 0.0
    if exactly_k_successes > successes_in_pop:
        return 0.0
    if exactly_k_successes > draws:
        return 0.0
    if draws - exactly_k_successes > population_size - successes_in_pop:
        return 0.0

    failures_in_pop = population_size - successes_in_pop
    failures_needed = draws - exactly_k_successes

    numerator = comb(successes_in_pop, exactly_k_successes) * comb(failures_in_pop, failures_needed)
    denominator = comb(population_size, draws)

    if denominator == 0:
        return 0.0

    return numerator / denominator


def hypergeometric_cdf_at_least(
    successes_in_pop: int,
    population_size: int,
    draws: int,
    at_least_k_successes: int,
) -> float:
    """Calculate probability of at least k successes.

    P(X >= k) = 1 - P(X < k) = 1 - sum(P(X = i) for i in 0..k-1)

    Args:
        successes_in_pop: Number of "success" cards in remaining deck
        population_size: Total cards in remaining deck
        draws: Number of cards to draw
        at_least_k_successes: Minimum number of successes needed

    Returns:
        Probability of getting at least k successes
    """
    if at_least_k_successes <= 0:
        return 1.0

    prob_less_than_k = sum(
        hypergeometric_pmf(successes_in_pop, population_size, draws, i)
        for i in range(at_least_k_successes)
    )

    return 1.0 - prob_less_than_k


def flush_completion_probability(
    hand: list[Card],
    deck_state: "DeckState",
    draws: int,
) -> dict[Suit, float]:
    """Calculate probability of completing a flush for each suit.

    Args:
        hand: Current cards in hand
        deck_state: Current deck state with remaining cards
        draws: Number of cards to draw (usually discards available)

    Returns:
        Dict mapping each suit to its flush completion probability
    """
    results = {}
    hand_suits = Counter(c.suit for c in hand)
    total_remaining = deck_state.total_remaining

    if total_remaining == 0 or draws == 0:
        # Check if we already have a flush
        for suit in Suit:
            results[suit] = 1.0 if hand_suits.get(suit, 0) >= 5 else 0.0
        return results

    for suit in Suit:
        cards_in_hand = hand_suits.get(suit, 0)
        needed = max(0, 5 - cards_in_hand)

        if needed == 0:
            # Already have flush
            results[suit] = 1.0
        elif needed > draws:
            # Impossible to complete
            results[suit] = 0.0
        else:
            available_in_deck = deck_state.suit_count(suit)
            results[suit] = hypergeometric_cdf_at_least(
                successes_in_pop=available_in_deck,
                population_size=total_remaining,
                draws=draws,
                at_least_k_successes=needed,
            )

    return results


def straight_completion_probability(
    hand: list[Card],
    deck_state: "DeckState",
    draws: int,
) -> float:
    """Calculate probability of completing any straight.

    A straight is 5 consecutive ranks. Ace can be high (10-J-Q-K-A)
    or low (A-2-3-4-5).

    Args:
        hand: Current cards in hand
        deck_state: Current deck state with remaining cards
        draws: Number of cards to draw

    Returns:
        Probability of completing at least one straight
    """
    total_remaining = deck_state.total_remaining
    if total_remaining == 0 or draws == 0:
        return _has_straight(hand)

    # All possible straight sequences (using rank values)
    # Ace-low: A(14)->1, 2, 3, 4, 5
    # Regular: 2-6, 3-7, ..., 10-A
    straight_sequences = [
        [14, 2, 3, 4, 5],  # Ace-low (wheel)
        [2, 3, 4, 5, 6],
        [3, 4, 5, 6, 7],
        [4, 5, 6, 7, 8],
        [5, 6, 7, 8, 9],
        [6, 7, 8, 9, 10],
        [7, 8, 9, 10, 11],
        [8, 9, 10, 11, 12],
        [9, 10, 11, 12, 13],
        [10, 11, 12, 13, 14],  # Broadway
    ]

    hand_ranks = set(c.rank.value for c in hand)
    best_prob = 0.0

    for seq in straight_sequences:
        # Count how many of this sequence we already have
        have = sum(1 for r in seq if r in hand_ranks)
        needed = 5 - have

        if needed == 0:
            return 1.0  # Already have this straight

        if needed > draws:
            continue  # Can't complete this one

        # Calculate probability of drawing the needed ranks
        # This is complex because we need specific ranks, not just any card
        prob = _straight_sequence_probability(
            seq, hand_ranks, deck_state, draws
        )
        best_prob = max(best_prob, prob)

    return best_prob


def _straight_sequence_probability(
    sequence: list[int],
    hand_ranks: set[int],
    deck_state: "DeckState",
    draws: int,
) -> float:
    """Calculate probability of completing a specific straight sequence.

    Uses inclusion-exclusion or Monte Carlo for complex cases.
    """
    needed_ranks = [r for r in sequence if r not in hand_ranks]

    if len(needed_ranks) == 0:
        return 1.0
    if len(needed_ranks) > draws:
        return 0.0

    total_remaining = deck_state.total_remaining

    # For single card needed, exact calculation
    if len(needed_ranks) == 1:
        rank = needed_ranks[0]
        rank_enum = Rank(rank) if rank <= 14 else Rank.ACE
        available = deck_state.rank_count(rank_enum)
        return hypergeometric_cdf_at_least(
            successes_in_pop=available,
            population_size=total_remaining,
            draws=draws,
            at_least_k_successes=1,
        )

    # For multiple cards, use simplified approximation:
    # P(all needed) ≈ product of individual probabilities (upper bound)
    # This is an approximation that works well for small needed counts
    prob = 1.0
    remaining = total_remaining

    for rank_val in needed_ranks:
        rank_enum = Rank(rank_val) if rank_val <= 14 else Rank.ACE
        available = deck_state.rank_count(rank_enum)

        if available == 0:
            return 0.0

        # Approximate: P(draw at least 1 of this rank)
        # Using: 1 - P(draw none) = 1 - C(N-k, draws) / C(N, draws)
        if remaining < draws:
            return 0.0

        p_none = comb(remaining - available, draws) / comb(remaining, draws) if remaining >= draws else 0
        p_at_least_one = 1.0 - p_none
        prob *= p_at_least_one

        # Reduce remaining for next iteration (approximation)
        remaining -= 1

    return prob


def _has_straight(hand: list[Card]) -> float:
    """Check if hand already contains a straight."""
    if len(hand) < 5:
        return 0.0

    ranks = sorted(set(c.rank.value for c in hand))

    # Check for regular straights
    for i in range(len(ranks) - 4):
        if ranks[i + 4] - ranks[i] == 4:
            return 1.0

    # Check for ace-low straight (wheel)
    if set([14, 2, 3, 4, 5]).issubset(set(c.rank.value for c in hand)):
        return 1.0

    return 0.0


def pair_upgrade_probability(
    hand: list[Card],
    deck_state: "DeckState",
    draws: int,
    target: HandType,
) -> float:
    """Calculate probability of upgrading pairs to better hands.

    Args:
        hand: Current cards in hand
        deck_state: Current deck state
        draws: Number of cards to draw
        target: Target hand type (THREE_OF_A_KIND, FULL_HOUSE, FOUR_OF_A_KIND)

    Returns:
        Probability of achieving target hand type
    """
    rank_counts = Counter(c.rank for c in hand)
    total_remaining = deck_state.total_remaining

    if total_remaining == 0 or draws == 0:
        return 0.0

    if target == HandType.THREE_OF_A_KIND:
        # Need to upgrade a pair to trips
        pairs = [rank for rank, count in rank_counts.items() if count == 2]
        if not pairs:
            return 0.0

        # Probability of hitting at least one of our pairs
        best_prob = 0.0
        for pair_rank in pairs:
            available = deck_state.rank_count(pair_rank)
            prob = hypergeometric_cdf_at_least(
                successes_in_pop=available,
                population_size=total_remaining,
                draws=draws,
                at_least_k_successes=1,
            )
            best_prob = max(best_prob, prob)

        return best_prob

    elif target == HandType.FULL_HOUSE:
        # Need trips + pair
        trips = [rank for rank, count in rank_counts.items() if count >= 3]
        pairs = [rank for rank, count in rank_counts.items() if count >= 2]

        if trips and len(pairs) >= 2:
            return 1.0  # Already have full house

        # Complex calculation - approximate
        if trips:
            # Have trips, need to make a pair from something else
            other_ranks = [r for r in rank_counts if rank_counts[r] == 1]
            if not other_ranks:
                return 0.0

            best_prob = 0.0
            for rank in other_ranks:
                available = deck_state.rank_count(rank)
                prob = hypergeometric_cdf_at_least(
                    available, total_remaining, draws, 1
                )
                best_prob = max(best_prob, prob)
            return best_prob

        elif pairs:
            # Have pair(s), need to upgrade one to trips and have another pair
            # Simplified: probability of upgrading best pair to trips
            best_pair = max(pairs, key=lambda r: deck_state.rank_count(r))
            available = deck_state.rank_count(best_pair)
            return hypergeometric_cdf_at_least(
                available, total_remaining, draws, 1
            )

        return 0.0

    elif target == HandType.FOUR_OF_A_KIND:
        # Need 4 of same rank
        trips = [rank for rank, count in rank_counts.items() if count >= 3]
        pairs = [rank for rank, count in rank_counts.items() if count >= 2]

        best_prob = 0.0

        # From trips
        for rank in trips:
            needed = 4 - rank_counts[rank]
            available = deck_state.rank_count(rank)
            prob = hypergeometric_cdf_at_least(
                available, total_remaining, draws, needed
            )
            best_prob = max(best_prob, prob)

        # From pairs (need 2 more)
        if draws >= 2:
            for rank in pairs:
                if rank in trips:
                    continue
                needed = 4 - rank_counts[rank]
                available = deck_state.rank_count(rank)
                prob = hypergeometric_cdf_at_least(
                    available, total_remaining, draws, needed
                )
                best_prob = max(best_prob, prob)

        return best_prob

    return 0.0


@dataclass
class HandCompletionProbabilities:
    """Probabilities of completing various hand types."""

    flush: dict[Suit, float]  # Per-suit flush probabilities
    straight: float
    three_of_a_kind: float
    full_house: float
    four_of_a_kind: float

    @property
    def best_flush(self) -> float:
        """Best flush probability across all suits."""
        return max(self.flush.values()) if self.flush else 0.0

    def best_improvement(self) -> tuple[str, float]:
        """Return the most likely improvement and its probability."""
        options = [
            ("flush", self.best_flush),
            ("straight", self.straight),
            ("three_of_a_kind", self.three_of_a_kind),
            ("full_house", self.full_house),
            ("four_of_a_kind", self.four_of_a_kind),
        ]
        return max(options, key=lambda x: x[1])


def calculate_all_completion_probabilities(
    hand: list[Card],
    deck_state: "DeckState",
    draws: int,
) -> HandCompletionProbabilities:
    """Calculate completion probabilities for all hand types.

    Args:
        hand: Current cards in hand
        deck_state: Current deck state
        draws: Number of cards to draw

    Returns:
        HandCompletionProbabilities with all calculations
    """
    return HandCompletionProbabilities(
        flush=flush_completion_probability(hand, deck_state, draws),
        straight=straight_completion_probability(hand, deck_state, draws),
        three_of_a_kind=pair_upgrade_probability(
            hand, deck_state, draws, HandType.THREE_OF_A_KIND
        ),
        full_house=pair_upgrade_probability(
            hand, deck_state, draws, HandType.FULL_HOUSE
        ),
        four_of_a_kind=pair_upgrade_probability(
            hand, deck_state, draws, HandType.FOUR_OF_A_KIND
        ),
    )
