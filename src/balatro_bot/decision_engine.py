"""Deep Decision Engine for Balatro.

Implements the decision logic from deeper_decision_logic.md:
1. Lethality check (absolute priority)
2. Expected value comparison
3. Variance-aware selection
4. Deck health consideration
5. Joker synergy weighting
"""

import logging
from dataclasses import dataclass, field
from itertools import combinations
from typing import Optional

from .models import Card, GameState, HandType, Suit, Rank
from .hand_evaluation import evaluate_hand, find_best_hand
from .scoring import calculate_score, ScoringBreakdown
from .jokers import JokerInstance
from .deck_tracker import DeckState
from .probability import (
    calculate_all_completion_probabilities,
    HandCompletionProbabilities,
)

logger = logging.getLogger(__name__)


@dataclass
class DecisionConfig:
    """Configuration for decision engine weights and thresholds."""

    # Lethality
    lethal_probability_threshold: float = 0.95
    lethal_variance_penalty: float = 1000.0  # Heavy penalty for risky lethal plays

    # Variance weights by game phase
    early_game_variance_weight: float = 0.1  # Allow risk early
    mid_game_variance_weight: float = 0.3
    late_game_variance_weight: float = 0.5  # Penalize risk late
    lethal_range_variance_weight: float = 1.0  # Maximum penalty near lethal

    # Safety margins for discard decisions
    base_safety_margin: float = 50.0
    low_discard_margin_multiplier: float = 1.5
    boss_blind_margin_multiplier: float = 2.0
    near_lethal_margin_multiplier: float = 3.0

    # Deck health penalties
    rare_rank_loss_weight: float = 20.0  # Aces, face cards
    suit_imbalance_weight: float = 10.0
    straight_potential_weight: float = 15.0

    # Synergy bonuses
    joker_trigger_value_weight: float = 1.0
    future_frequency_weight: float = 0.5

    # Tie-breakers
    prefer_play_over_discard: float = 10.0
    prefer_fewer_cards: float = 5.0
    prefer_deterministic: float = 20.0


@dataclass
class EvaluatedAction:
    """An action with full evaluation details."""

    action_type: str  # "play" or "discard"
    card_indices: list[int]
    cards: list[Card]

    # Scoring
    expected_score: int
    variance: float = 0.0

    # Breakdown
    hand_type: Optional[HandType] = None
    scoring_breakdown: Optional[ScoringBreakdown] = None

    # Flags
    is_lethal: bool = False
    is_deterministic: bool = True

    # Final weighted score
    final_score: float = 0.0
    reasoning: list[str] = field(default_factory=list)

    def add_reason(self, reason: str) -> None:
        """Add a reasoning component."""
        self.reasoning.append(reason)


class DeepDecisionEngine:
    """Decision engine implementing deep play/discard logic.

    Decision flow:
    1. If lethal now → play lowest-variance lethal hand
    2. Else → compute EV for all actions, apply penalties/bonuses, choose best
    """

    def __init__(self, config: Optional[DecisionConfig] = None):
        self.config = config or DecisionConfig()

    def decide(
        self,
        hand: list[Card],
        jokers: list[JokerInstance],
        game_state: GameState,
        blind_chips: int,
        current_chips: int,
        hands_remaining: int,
        discards_remaining: int,
        deck_state: Optional[DeckState] = None,
        is_boss_blind: bool = False,
    ) -> EvaluatedAction:
        """Make the best decision given current game state.

        Args:
            hand: Cards in hand
            jokers: Active jokers (in order)
            game_state: Current game state
            blind_chips: Chips needed to beat blind
            current_chips: Chips already scored
            hands_remaining: Hands left to play
            discards_remaining: Discards left
            deck_state: Deck tracking state (optional)
            is_boss_blind: Whether facing a boss blind

        Returns:
            Best evaluated action to take
        """
        chips_needed = blind_chips - current_chips

        # Create deck state if not provided
        if deck_state is None:
            deck_state = DeckState.from_known_cards(hand)

        # Evaluate all possible plays
        play_actions = self._evaluate_all_plays(
            hand, jokers, game_state, chips_needed, hands_remaining
        )

        # Check for lethal plays
        lethal_plays = [a for a in play_actions if a.is_lethal]

        if lethal_plays:
            # GATE 1: Lethality - play the safest lethal hand
            best_lethal = self._find_safest_lethal(lethal_plays)
            best_lethal.add_reason("LETHAL - playing safe winning hand")
            logger.info(
                f"Lethal found: {best_lethal.hand_type.name} "
                f"~{best_lethal.expected_score} chips (need {chips_needed})"
            )
            return best_lethal

        # No lethal - evaluate discards if available
        discard_actions = []
        if discards_remaining > 0:
            discard_actions = self._evaluate_all_discards(
                hand, jokers, game_state, deck_state, chips_needed,
                hands_remaining, discards_remaining, is_boss_blind
            )

        # Combine and score all actions
        all_actions = play_actions + discard_actions

        # Apply variance penalties based on game phase
        variance_weight = self._get_variance_weight(
            chips_needed, hands_remaining, blind_chips
        )

        for action in all_actions:
            # Start with expected score
            action.final_score = float(action.expected_score)

            # Apply variance penalty
            action.final_score -= variance_weight * action.variance

            # Tie-breakers
            if action.action_type == "play":
                action.final_score += self.config.prefer_play_over_discard
            if action.is_deterministic:
                action.final_score += self.config.prefer_deterministic
            action.final_score -= len(action.cards) * self.config.prefer_fewer_cards

        # Sort by final score
        all_actions.sort(key=lambda a: a.final_score, reverse=True)

        if not all_actions:
            # Fallback: play first card
            return EvaluatedAction(
                action_type="play",
                card_indices=[0],
                cards=[hand[0]] if hand else [],
                expected_score=0,
                reasoning=["No valid actions, playing first card"],
            )

        best = all_actions[0]
        logger.info(
            f"Decision: {best.action_type} {best.hand_type.name if best.hand_type else ''} "
            f"score={best.final_score:.0f} ({', '.join(best.reasoning)})"
        )

        return best

    def _evaluate_all_plays(
        self,
        hand: list[Card],
        jokers: list[JokerInstance],
        game_state: GameState,
        chips_needed: int,
        hands_remaining: int,
    ) -> list[EvaluatedAction]:
        """Evaluate all possible plays."""
        actions = []

        for n_cards in range(1, min(6, len(hand) + 1)):
            for indices in combinations(range(len(hand)), n_cards):
                indices_list = list(indices)
                cards_to_play = [hand[i] for i in indices_list]
                remaining = [c for i, c in enumerate(hand) if i not in indices]

                # Calculate score
                breakdown = calculate_score(
                    played_cards=cards_to_play,
                    jokers=jokers,
                    game_state=game_state,
                    cards_in_hand=remaining,
                )

                is_lethal = breakdown.final_score >= chips_needed

                action = EvaluatedAction(
                    action_type="play",
                    card_indices=indices_list,
                    cards=cards_to_play,
                    expected_score=breakdown.final_score,
                    variance=0.0,  # Plays are deterministic
                    hand_type=breakdown.hand_type,
                    scoring_breakdown=breakdown,
                    is_lethal=is_lethal,
                    is_deterministic=True,
                )

                action.add_reason(f"{breakdown.hand_type.name}")
                if is_lethal:
                    action.add_reason("LETHAL")

                actions.append(action)

        return actions

    def _evaluate_all_discards(
        self,
        hand: list[Card],
        jokers: list[JokerInstance],
        game_state: GameState,
        deck_state: DeckState,
        chips_needed: int,
        hands_remaining: int,
        discards_remaining: int,
        is_boss_blind: bool,
    ) -> list[EvaluatedAction]:
        """Evaluate all possible discards with probability-weighted EV."""
        actions = []

        # Find current best hand for reference
        _, current_best = find_best_hand(hand)
        current_score = 0
        if current_best:
            breakdown = calculate_score(
                played_cards=[c for c in hand if c in (current_best.scoring_cards or [])],
                jokers=jokers,
                game_state=game_state,
                cards_in_hand=[],
            )
            current_score = breakdown.final_score

        # Calculate safety margin
        safety_margin = self._calculate_safety_margin(
            chips_needed, current_score, hands_remaining,
            discards_remaining, is_boss_blind
        )

        for n_cards in range(1, min(6, len(hand) + 1)):
            for indices in combinations(range(len(hand)), n_cards):
                indices_list = list(indices)
                cards_to_discard = [hand[i] for i in indices_list]
                cards_to_keep = [c for i, c in enumerate(hand) if i not in indices]

                # Calculate improvement probabilities
                probs = calculate_all_completion_probabilities(
                    cards_to_keep, deck_state, draws=n_cards
                )

                # Estimate expected value after discard
                ev, variance = self._estimate_discard_ev(
                    cards_to_keep, probs, jokers, game_state, n_cards
                )

                # Calculate deck damage
                deck_damage = self._calculate_deck_damage(
                    cards_to_discard, deck_state, jokers
                )

                # Adjusted EV
                adjusted_ev = ev - deck_damage

                # Only consider discard if it beats play + safety margin
                if adjusted_ev <= current_score + safety_margin:
                    continue

                action = EvaluatedAction(
                    action_type="discard",
                    card_indices=indices_list,
                    cards=cards_to_discard,
                    expected_score=int(adjusted_ev),
                    variance=variance,
                    is_deterministic=False,
                )

                best_improvement, best_prob = probs.best_improvement()
                action.add_reason(f"discard {n_cards}")
                action.add_reason(f"P({best_improvement})={best_prob:.1%}")
                action.add_reason(f"EV={adjusted_ev:.0f}")

                actions.append(action)

        return actions

    def _find_safest_lethal(
        self,
        lethal_plays: list[EvaluatedAction],
    ) -> EvaluatedAction:
        """Find the safest (lowest variance) lethal play.

        When winning is guaranteed, minimize risk:
        1. Prefer deterministic plays
        2. Prefer higher scoring (more margin)
        3. Prefer fewer cards used
        """
        # All plays are deterministic, so sort by:
        # 1. Expected score (higher = safer margin)
        # 2. Fewer cards (preserve resources)
        def safety_score(action: EvaluatedAction) -> tuple:
            return (
                action.expected_score,  # Higher score = more margin
                -len(action.cards),  # Fewer cards = better
                action.hand_type.value if action.hand_type else 0,  # Better hand type
            )

        return max(lethal_plays, key=safety_score)

    def _get_variance_weight(
        self,
        chips_needed: int,
        hands_remaining: int,
        blind_total: int,
    ) -> float:
        """Get variance weight based on game phase."""
        # Near lethal (can win with average hand)
        if chips_needed < blind_total * 0.3:
            return self.config.lethal_range_variance_weight

        # Late game (few hands left)
        if hands_remaining <= 2:
            return self.config.late_game_variance_weight

        # Mid game
        if hands_remaining <= 3:
            return self.config.mid_game_variance_weight

        # Early game
        return self.config.early_game_variance_weight

    def _calculate_safety_margin(
        self,
        chips_needed: int,
        current_hand_score: int,
        hands_remaining: int,
        discards_remaining: int,
        is_boss_blind: bool,
    ) -> float:
        """Calculate safety margin for discard decisions.

        Higher margin = harder to justify discarding.
        """
        margin = self.config.base_safety_margin

        # Near lethal - very high margin
        if current_hand_score >= chips_needed * 0.8:
            margin *= self.config.near_lethal_margin_multiplier

        # Low discards - be conservative
        if discards_remaining <= 1:
            margin *= self.config.low_discard_margin_multiplier

        # Boss blind - be conservative
        if is_boss_blind:
            margin *= self.config.boss_blind_margin_multiplier

        return margin

    def _estimate_discard_ev(
        self,
        kept_cards: list[Card],
        probs: HandCompletionProbabilities,
        jokers: list[JokerInstance],
        game_state: GameState,
        draws: int,
    ) -> tuple[float, float]:
        """Estimate expected value and variance after discard.

        Uses completion probabilities to weight possible outcomes.
        """
        # Estimate scores for different outcomes
        outcomes = []

        # Flush outcome
        if probs.best_flush > 0.01:
            flush_score = self._estimate_hand_score(
                HandType.FLUSH, kept_cards, jokers, game_state
            )
            outcomes.append((probs.best_flush, flush_score))

        # Straight outcome
        if probs.straight > 0.01:
            straight_score = self._estimate_hand_score(
                HandType.STRAIGHT, kept_cards, jokers, game_state
            )
            outcomes.append((probs.straight, straight_score))

        # Three of a kind outcome
        if probs.three_of_a_kind > 0.01:
            trips_score = self._estimate_hand_score(
                HandType.THREE_OF_A_KIND, kept_cards, jokers, game_state
            )
            outcomes.append((probs.three_of_a_kind, trips_score))

        # Full house outcome
        if probs.full_house > 0.01:
            fh_score = self._estimate_hand_score(
                HandType.FULL_HOUSE, kept_cards, jokers, game_state
            )
            outcomes.append((probs.full_house, fh_score))

        # Four of a kind outcome
        if probs.four_of_a_kind > 0.01:
            quads_score = self._estimate_hand_score(
                HandType.FOUR_OF_A_KIND, kept_cards, jokers, game_state
            )
            outcomes.append((probs.four_of_a_kind, quads_score))

        # No improvement - estimate current best
        prob_no_improve = 1.0 - sum(p for p, _ in outcomes)
        if prob_no_improve > 0:
            current_score = self._estimate_kept_cards_score(
                kept_cards, jokers, game_state
            )
            outcomes.append((prob_no_improve, current_score))

        if not outcomes:
            return 0.0, 0.0

        # Calculate EV
        ev = sum(p * s for p, s in outcomes)

        # Calculate variance
        variance = sum(p * (s - ev) ** 2 for p, s in outcomes)

        return ev, variance

    def _estimate_hand_score(
        self,
        hand_type: HandType,
        kept_cards: list[Card],
        jokers: list[JokerInstance],
        game_state: GameState,
    ) -> int:
        """Estimate score for achieving a specific hand type."""
        # Base chips and mult for hand type (level 1)
        base_values = {
            HandType.HIGH_CARD: (5, 1),
            HandType.PAIR: (10, 2),
            HandType.TWO_PAIR: (20, 2),
            HandType.THREE_OF_A_KIND: (30, 3),
            HandType.STRAIGHT: (30, 4),
            HandType.FLUSH: (35, 4),
            HandType.FULL_HOUSE: (40, 4),
            HandType.FOUR_OF_A_KIND: (60, 7),
            HandType.STRAIGHT_FLUSH: (100, 8),
            HandType.ROYAL_FLUSH: (100, 8),
            HandType.FIVE_OF_A_KIND: (120, 12),
            HandType.FLUSH_HOUSE: (140, 14),
            HandType.FLUSH_FIVE: (160, 16),
        }

        base_chips, base_mult = base_values.get(hand_type, (5, 1))

        # Apply hand level
        level = game_state.hand_levels.get(hand_type, 1)
        chips = base_chips + (level - 1) * 10
        mult = base_mult + (level - 1)

        # Estimate joker bonus based on hand type and cards
        joker_mult = self._estimate_joker_bonus(kept_cards, hand_type, jokers)
        # Ensure minimum multiplier
        joker_mult = max(1.0, joker_mult)

        return int(chips * mult * joker_mult)

    def _estimate_kept_cards_score(
        self,
        kept_cards: list[Card],
        jokers: list[JokerInstance],
        game_state: GameState,
    ) -> int:
        """Estimate score from kept cards (no improvement)."""
        if not kept_cards:
            return 0

        # Find best hand in kept cards
        _, result = find_best_hand(kept_cards)
        if not result:
            return 0

        return self._estimate_hand_score(
            result.hand_type, kept_cards, jokers, game_state
        )

    def _calculate_deck_damage(
        self,
        cards_to_discard: list[Card],
        deck_state: DeckState,
        jokers: list[JokerInstance],
    ) -> float:
        """Calculate penalty for damaging the deck.

        Penalize discarding:
        - Rare ranks (Aces, face cards)
        - Cards that break suit balance
        - Cards that reduce straight potential
        - Cards that synergize with jokers
        """
        damage = 0.0

        # Rare rank penalty
        rare_ranks = {Rank.ACE, Rank.KING, Rank.QUEEN, Rank.JACK}
        for card in cards_to_discard:
            if card.rank in rare_ranks:
                damage += self.config.rare_rank_loss_weight

        # Suit balance penalty
        suit_counts = deck_state.get_suit_distribution()
        if suit_counts:
            avg_suit = sum(suit_counts.values()) / len(suit_counts)
            for card in cards_to_discard:
                if suit_counts.get(card.suit, 0) < avg_suit:
                    damage += self.config.suit_imbalance_weight

        # Joker synergy penalty
        for joker in jokers:
            for card in cards_to_discard:
                if self._card_synergizes_with_joker(card, joker):
                    damage += self.config.joker_trigger_value_weight * 10

        return damage

    def _card_synergizes_with_joker(
        self,
        card: Card,
        joker: JokerInstance,
    ) -> bool:
        """Check if a card synergizes with a joker."""
        # Suit-based jokers
        suit_jokers = {
            "greedy_joker": Suit.DIAMONDS,
            "lusty_joker": Suit.HEARTS,
            "wrathful_joker": Suit.SPADES,
            "gluttonous_joker": Suit.CLUBS,
            "rough_gem": Suit.DIAMONDS,
            "bloodstone": Suit.HEARTS,
            "arrowhead": Suit.SPADES,
            "onyx_agate": Suit.CLUBS,
        }

        if joker.id in suit_jokers:
            return card.suit == suit_jokers[joker.id]

        # Face card jokers
        if joker.id in ("scary_face", "smiley_face", "photograph"):
            return card.rank in {Rank.JACK, Rank.QUEEN, Rank.KING}

        # Even/odd jokers
        if joker.id == "even_steven":
            return card.rank.value in {2, 4, 6, 8, 10}
        if joker.id == "odd_todd":
            return card.rank.value in {3, 5, 7, 9, 14}  # 14 = Ace

        # Fibonacci joker (2, 3, 5, 8, A)
        if joker.id == "fibonacci":
            return card.rank.value in {2, 3, 5, 8, 14}

        # Scholar (Aces and face cards)
        if joker.id == "scholar":
            return card.rank == Rank.ACE

        # Walkie Talkie (10s and 4s)
        if joker.id == "walkie_talkie":
            return card.rank.value in {10, 4}

        # Hack (2, 3, 4, 5)
        if joker.id == "hack":
            return card.rank.value in {2, 3, 4, 5}

        # Triboulet (Kings and Queens)
        if joker.id == "triboulet":
            return card.rank in {Rank.KING, Rank.QUEEN}

        # The Idol (random suit for x2 mult)
        # Can't know the suit without joker state, so skip

        # Hanging Chad (first card played)
        # Always relevant, skip

        return False

    def _estimate_joker_bonus(
        self,
        cards: list[Card],
        hand_type: HandType,
        jokers: list[JokerInstance],
    ) -> float:
        """Estimate additional score multiplier from jokers.

        Returns a multiplier to apply to base score.
        """
        multiplier = 1.0
        add_mult = 0
        add_chips = 0

        for joker in jokers:
            jid = joker.id

            # Simple +mult jokers
            if jid == "joker":
                add_mult += 4
            elif jid == "jolly_joker" and hand_type in (HandType.PAIR, HandType.TWO_PAIR, HandType.FULL_HOUSE):
                add_mult += 8
            elif jid == "zany_joker" and hand_type in (HandType.THREE_OF_A_KIND, HandType.FULL_HOUSE, HandType.FOUR_OF_A_KIND):
                add_mult += 12
            elif jid == "mad_joker" and hand_type == HandType.TWO_PAIR:
                add_mult += 10
            elif jid == "crazy_joker" and hand_type in (HandType.STRAIGHT, HandType.STRAIGHT_FLUSH):
                add_mult += 12
            elif jid == "droll_joker" and hand_type in (HandType.FLUSH, HandType.FLUSH_HOUSE, HandType.FLUSH_FIVE):
                add_mult += 10

            # Suit-based chip/mult jokers
            elif jid in ("greedy_joker", "lusty_joker", "wrathful_joker", "gluttonous_joker"):
                suit_map = {
                    "greedy_joker": Suit.DIAMONDS,
                    "lusty_joker": Suit.HEARTS,
                    "wrathful_joker": Suit.SPADES,
                    "gluttonous_joker": Suit.CLUBS,
                }
                target_suit = suit_map[jid]
                count = sum(1 for c in cards if c.suit == target_suit)
                add_mult += count * 3  # Each matching card gives +3 mult

            # x mult jokers
            elif jid == "steel_joker":
                # +0.2 x mult per steel card, estimate 0
                pass
            elif jid == "half_joker" and len(cards) <= 3:
                add_mult += 20

            # Hand type x mult jokers
            elif jid == "the_duo" and hand_type in (HandType.PAIR, HandType.TWO_PAIR, HandType.FULL_HOUSE):
                multiplier *= 2
            elif jid == "the_trio" and hand_type in (HandType.THREE_OF_A_KIND, HandType.FULL_HOUSE, HandType.FOUR_OF_A_KIND):
                multiplier *= 3
            elif jid == "the_family" and hand_type in (HandType.FOUR_OF_A_KIND, HandType.FIVE_OF_A_KIND):
                multiplier *= 4
            elif jid == "the_order" and hand_type in (HandType.STRAIGHT, HandType.STRAIGHT_FLUSH):
                multiplier *= 3
            elif jid == "the_tribe" and hand_type in (HandType.FLUSH, HandType.FLUSH_HOUSE, HandType.FLUSH_FIVE, HandType.STRAIGHT_FLUSH):
                multiplier *= 2

        # Apply flat bonuses
        # Rough estimate: assume 10 base chips, 2 base mult
        base_chips = 10 + add_chips
        base_mult = 2 + add_mult

        return base_chips * base_mult * multiplier / 20  # Normalize to multiplier
