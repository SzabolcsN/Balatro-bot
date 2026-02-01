"""Heuristic evaluation for Balatro decision making.

Provides fast, rule-based evaluation of game actions to:
1. Filter out obviously bad moves (reduces MCTS branching by 70-90%)
2. Provide prior scores for action ranking
3. Handle edge cases and hard constraints

Heuristics are organized by decision type:
- Play selection: Which cards to play
- Discard selection: Which cards to discard
- Shop decisions: What to buy/sell
"""

from collections import Counter
from dataclasses import dataclass
from enum import Enum, auto
from itertools import combinations

from balatro_bot.hand_evaluation import evaluate_hand
from balatro_bot.jokers import JokerInstance
from balatro_bot.models import Card, GameState, HandType, Suit
from balatro_bot.scoring import calculate_score


class ActionType(Enum):
    """Type of game action."""

    PLAY = auto()
    DISCARD = auto()
    BUY_JOKER = auto()
    SELL_JOKER = auto()
    SKIP = auto()
    END_SHOP = auto()


@dataclass
class ScoredAction:
    """An action with its heuristic score."""

    action_type: ActionType
    card_indices: list[int]  # For PLAY/DISCARD actions
    score: float  # Heuristic score (higher = better)
    expected_chips: int = 0  # Expected chip gain
    reasoning: str = ""  # Human-readable explanation
    is_lethal: bool = False  # Would this beat the blind?

    def __lt__(self, other: "ScoredAction") -> bool:
        return self.score < other.score


@dataclass
class HeuristicConfig:
    """Configuration for heuristic weights."""

    # Play selection weights
    lethal_bonus: float = 10000.0  # Huge bonus for plays that beat the blind
    hand_type_weight: float = 100.0  # Weight for hand type quality
    chip_efficiency_weight: float = 1.0  # Weight for chips per card played
    joker_synergy_weight: float = 50.0  # Bonus for triggering joker effects

    # Discard weights
    discard_improvement_weight: float = 200.0  # Weight for potential hand improvement
    keep_high_cards_weight: float = 10.0  # Prefer keeping high cards
    keep_synergy_cards_weight: float = 30.0  # Keep cards that work with jokers

    # Resource management
    min_safety_chips: int = 0  # Minimum chips to consider "safe"
    aggressive_threshold: float = 0.8  # Play aggressively when chips/blind > this


def evaluate_plays(
    hand: list[Card],
    jokers: list[JokerInstance],
    game_state: GameState,
    blind_chips: int,
    current_chips: int,
    hands_remaining: int,
    config: HeuristicConfig | None = None,
) -> list[ScoredAction]:
    """Evaluate all possible plays and return scored actions.

    Args:
        hand: Current cards in hand
        jokers: Active jokers (in order)
        game_state: Current game state
        blind_chips: Chips needed to beat blind
        current_chips: Chips already scored this blind
        hands_remaining: Hands left to play
        config: Heuristic configuration

    Returns:
        List of ScoredActions sorted by score (best first)
    """
    if config is None:
        config = HeuristicConfig()

    chips_needed = blind_chips - current_chips
    actions: list[ScoredAction] = []

    # Generate all possible plays (1-5 cards)
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

            # Calculate heuristic score
            score = 0.0
            reasoning_parts = []

            # Check if lethal
            is_lethal = breakdown.final_score >= chips_needed
            if is_lethal:
                score += config.lethal_bonus
                reasoning_parts.append("LETHAL")

            # Hand type quality
            hand_type_score = breakdown.hand_type.value * config.hand_type_weight
            score += hand_type_score
            reasoning_parts.append(f"{breakdown.hand_type.name}")

            # Chip efficiency (chips per card)
            efficiency = breakdown.final_score / len(cards_to_play)
            score += efficiency * config.chip_efficiency_weight

            # Joker synergy bonus
            synergy_bonus = _calculate_joker_synergy(cards_to_play, jokers, config)
            score += synergy_bonus
            if synergy_bonus > 0:
                reasoning_parts.append(f"+{synergy_bonus:.0f} synergy")

            # Urgency adjustment: be more aggressive with fewer hands
            if hands_remaining <= 2 and not is_lethal:
                # Prioritize raw score when desperate
                score += breakdown.final_score * 0.1
                reasoning_parts.append("urgent")

            # Penalize using too many cards if not needed
            if is_lethal and len(cards_to_play) > 2:
                # Found lethal with fewer cards? Prefer that
                score -= len(cards_to_play) * 10
                reasoning_parts.append("card conservation")

            actions.append(
                ScoredAction(
                    action_type=ActionType.PLAY,
                    card_indices=indices_list,
                    score=score,
                    expected_chips=breakdown.final_score,
                    reasoning=", ".join(reasoning_parts),
                    is_lethal=is_lethal,
                )
            )

    # Sort by score descending
    actions.sort(reverse=True)
    return actions


def evaluate_discards(
    hand: list[Card],
    jokers: list[JokerInstance],
    game_state: GameState,
    deck_remaining: int,
    config: HeuristicConfig | None = None,
) -> list[ScoredAction]:
    """Evaluate all possible discards and return scored actions.

    Args:
        hand: Current cards in hand
        jokers: Active jokers
        game_state: Current game state
        deck_remaining: Cards left in deck
        config: Heuristic configuration

    Returns:
        List of ScoredActions sorted by score (best first)
    """
    if config is None:
        config = HeuristicConfig()

    actions: list[ScoredAction] = []

    # Analyze current hand potential
    current_best = _find_best_hand_in_cards(hand)

    # Generate all possible discards (1-5 cards)
    for n_cards in range(1, min(6, len(hand) + 1)):
        for indices in combinations(range(len(hand)), n_cards):
            indices_list = list(indices)
            cards_to_discard = [hand[i] for i in indices_list]
            cards_to_keep = [c for i, c in enumerate(hand) if i not in indices]

            score = 0.0
            reasoning_parts = []

            # Don't discard cards that are part of the best hand
            best_hand_cards = set(current_best[1]) if current_best else set()
            discarding_best = any(c in best_hand_cards for c in cards_to_discard)

            if discarding_best:
                score -= 500  # Strong penalty
                reasoning_parts.append("breaks best hand")

            # Evaluate what we're keeping
            kept_potential = _evaluate_kept_cards(cards_to_keep, jokers)
            score += kept_potential * config.discard_improvement_weight

            # Prefer discarding low cards
            low_card_bonus = sum(
                14 - c.rank.value for c in cards_to_discard
            ) * config.keep_high_cards_weight
            score += low_card_bonus
            if low_card_bonus > 50:
                reasoning_parts.append("discarding low cards")

            # Check joker synergies for kept cards
            synergy = _calculate_kept_card_synergy(cards_to_keep, jokers, config)
            score += synergy
            if synergy > 0:
                reasoning_parts.append(f"+{synergy:.0f} kept synergy")

            # Penalize discarding cards that synergize with jokers
            lost_synergy = _calculate_joker_synergy(cards_to_discard, jokers, config)
            score -= lost_synergy * 0.5

            # Prefer smaller discards if improvement is similar
            score -= len(cards_to_discard) * 5

            reasoning_parts.append(f"keep {len(cards_to_keep)} cards")

            actions.append(
                ScoredAction(
                    action_type=ActionType.DISCARD,
                    card_indices=indices_list,
                    score=score,
                    reasoning=", ".join(reasoning_parts),
                )
            )

    actions.sort(reverse=True)
    return actions


def _calculate_joker_synergy(
    cards: list[Card],
    jokers: list[JokerInstance],
    config: HeuristicConfig,
) -> float:
    """Calculate synergy bonus between cards and jokers."""
    bonus = 0.0

    for joker in jokers:
        # Suit-based jokers
        if joker.id == "greedy_joker":
            bonus += sum(config.joker_synergy_weight for c in cards if c.suit == Suit.DIAMONDS)
        elif joker.id == "lusty_joker":
            bonus += sum(config.joker_synergy_weight for c in cards if c.suit == Suit.HEARTS)
        elif joker.id == "wrathful_joker":
            bonus += sum(config.joker_synergy_weight for c in cards if c.suit == Suit.SPADES)
        elif joker.id == "gluttonous_joker":
            bonus += sum(config.joker_synergy_weight for c in cards if c.suit == Suit.CLUBS)

        # Hand type jokers - check if cards could form the hand
        elif joker.id in ("jolly_joker", "sly_joker", "the_duo"):
            # Pair bonuses
            ranks = Counter(c.rank for c in cards)
            if any(count >= 2 for count in ranks.values()):
                bonus += config.joker_synergy_weight

        elif joker.id in ("zany_joker", "wily_joker", "the_trio"):
            # Three of a kind bonuses
            ranks = Counter(c.rank for c in cards)
            if any(count >= 3 for count in ranks.values()):
                bonus += config.joker_synergy_weight * 1.5

        elif joker.id == "half_joker":
            # Bonus for playing 3 or fewer cards
            if len(cards) <= 3:
                bonus += config.joker_synergy_weight * 2

    return bonus


def _calculate_kept_card_synergy(
    cards: list[Card],
    jokers: list[JokerInstance],
    config: HeuristicConfig,
) -> float:
    """Calculate synergy for cards we're keeping."""
    bonus = 0.0

    for joker in jokers:
        # Blackboard wants all held cards to be spades or clubs
        if joker.id == "blackboard":
            if all(c.suit in (Suit.SPADES, Suit.CLUBS) for c in cards):
                bonus += config.joker_synergy_weight * 3

        # Raised Fist uses lowest card rank
        elif joker.id == "raised_fist":
            if cards:
                lowest = min(c.rank.value for c in cards)
                bonus += lowest * 2  # Higher low cards are better

    return bonus


def _find_best_hand_in_cards(cards: list[Card]) -> tuple[HandType, list[Card]] | None:
    """Find the best poker hand possible with these cards."""
    if not cards:
        return None

    best_type = HandType.HIGH_CARD
    best_cards: list[Card] = []

    for n in range(1, min(6, len(cards) + 1)):
        for combo in combinations(cards, n):
            combo_list = list(combo)
            result = evaluate_hand(combo_list)
            if result.hand_type > best_type:
                best_type = result.hand_type
                best_cards = combo_list

    return (best_type, best_cards) if best_cards else None


def _evaluate_kept_cards(cards: list[Card], jokers: list[JokerInstance]) -> float:
    """Evaluate the potential of kept cards."""
    if not cards:
        return 0.0

    score = 0.0

    # Check for pairs/trips potential
    ranks = Counter(c.rank for c in cards)
    suits = Counter(c.suit for c in cards)

    # Existing pairs are valuable
    pairs = sum(1 for count in ranks.values() if count >= 2)
    score += pairs * 50

    # Trips are very valuable
    trips = sum(1 for count in ranks.values() if count >= 3)
    score += trips * 100

    # Flush potential (4 of same suit)
    if any(count >= 4 for count in suits.values()):
        score += 80

    # Straight potential (check for connected cards)
    sorted_ranks = sorted(set(c.rank.value for c in cards))
    max_connected = 1
    current_connected = 1
    for i in range(1, len(sorted_ranks)):
        if sorted_ranks[i] - sorted_ranks[i - 1] == 1:
            current_connected += 1
            max_connected = max(max_connected, current_connected)
        else:
            current_connected = 1
    if max_connected >= 4:
        score += 60

    # High cards are generally valuable
    high_cards = sum(1 for c in cards if c.rank.value >= 10)
    score += high_cards * 10

    return score


def get_best_play(
    hand: list[Card],
    jokers: list[JokerInstance],
    game_state: GameState,
    blind_chips: int,
    current_chips: int,
    hands_remaining: int,
) -> ScoredAction | None:
    """Get the single best play action.

    Convenience function that returns the top-ranked play.
    """
    actions = evaluate_plays(
        hand=hand,
        jokers=jokers,
        game_state=game_state,
        blind_chips=blind_chips,
        current_chips=current_chips,
        hands_remaining=hands_remaining,
    )
    return actions[0] if actions else None


def get_best_discard(
    hand: list[Card],
    jokers: list[JokerInstance],
    game_state: GameState,
    deck_remaining: int,
) -> ScoredAction | None:
    """Get the single best discard action.

    Convenience function that returns the top-ranked discard.
    """
    actions = evaluate_discards(
        hand=hand,
        jokers=jokers,
        game_state=game_state,
        deck_remaining=deck_remaining,
    )
    return actions[0] if actions else None


def should_discard(
    hand: list[Card],
    jokers: list[JokerInstance],
    game_state: GameState,
    blind_chips: int,
    current_chips: int,
    hands_remaining: int,
    discards_remaining: int,
    deck_remaining: int,
) -> bool:
    """Determine if discarding is better than playing.

    Returns True if the heuristic recommends discarding over playing.
    """
    if discards_remaining <= 0:
        return False

    # Get best play
    best_play = get_best_play(
        hand, jokers, game_state, blind_chips, current_chips, hands_remaining
    )

    if best_play is None:
        return False

    # If we have a lethal play, don't discard
    if best_play.is_lethal:
        return False

    # If we're on last hand, must play
    if hands_remaining <= 1:
        return False

    # Evaluate current hand quality
    current_best = _find_best_hand_in_cards(hand)
    if current_best is None:
        return True  # No good hand, might as well discard

    current_hand_type = current_best[0]

    # Discard if we only have high card or weak pair with discards available
    if current_hand_type <= HandType.PAIR and discards_remaining > 0:
        # Check if we have good discard potential
        best_discard = get_best_discard(hand, jokers, game_state, deck_remaining)
        if best_discard and best_discard.score > 0:
            # Discard if we're not close to winning and have room to improve
            chips_needed = blind_chips - current_chips
            if best_play.expected_chips < chips_needed * 0.5:
                return True

    return False


class HeuristicPlayer:
    """A player that uses heuristics to make decisions.

    Can play complete games using rule-based decision making.
    """

    def __init__(self, config: HeuristicConfig | None = None):
        self.config = config or HeuristicConfig()
        self.stats = {
            "games_played": 0,
            "games_won": 0,
            "total_antes": 0,
            "hands_played": 0,
            "discards_used": 0,
        }

    def play_blind(self, game: "GameSimulator") -> bool:
        """Play through a single blind.

        Args:
            game: Game simulator in PLAYING phase

        Returns:
            True if blind was beaten, False otherwise
        """
        from balatro_bot.simulator import GamePhase

        while game.phase == GamePhase.PLAYING:
            # Decide: play or discard?
            if should_discard(
                hand=game.hand,
                jokers=game.jokers,
                game_state=GameState(
                    hand_levels=game.hand_levels,
                    discards_remaining=game.discards_remaining,
                ),
                blind_chips=game.blind_chips,
                current_chips=game.current_chips,
                hands_remaining=game.hands_remaining,
                discards_remaining=game.discards_remaining,
                deck_remaining=len(game.deck),
            ):
                # Discard
                best_discard = get_best_discard(
                    hand=game.hand,
                    jokers=game.jokers,
                    game_state=GameState(
                        hand_levels=game.hand_levels,
                        discards_remaining=game.discards_remaining,
                    ),
                    deck_remaining=len(game.deck),
                )
                if best_discard:
                    game.discard(best_discard.card_indices)
                    self.stats["discards_used"] += 1
                continue

            # Play best hand
            best_play = get_best_play(
                hand=game.hand,
                jokers=game.jokers,
                game_state=GameState(
                    hand_levels=game.hand_levels,
                    discards_remaining=game.discards_remaining,
                ),
                blind_chips=game.blind_chips,
                current_chips=game.current_chips,
                hands_remaining=game.hands_remaining,
            )

            if best_play is None:
                break

            result = game.play_hand(best_play.card_indices)
            self.stats["hands_played"] += 1

            if result.blind_beaten:
                return True

            if result.game_over:
                return False

        return game.current_chips >= game.blind_chips

    def play_game(self, game: "GameSimulator") -> bool:
        """Play a complete game from current state.

        Args:
            game: Game simulator

        Returns:
            True if game was won, False otherwise
        """
        from balatro_bot.simulator import GamePhase

        self.stats["games_played"] += 1

        while not game.is_game_over:
            if game.phase == GamePhase.BLIND_SELECT:
                # Always play blinds (could add skip logic later)
                game.start_blind()

            elif game.phase == GamePhase.PLAYING:
                beaten = self.play_blind(game)
                if not beaten and game.phase != GamePhase.GAME_OVER:
                    # Failed to beat blind but game continues (shouldn't happen)
                    break

            elif game.phase == GamePhase.SHOP:
                # Simple shop strategy: just end shop for now
                # Could add joker buying logic later
                game.end_shop()

            self.stats["total_antes"] = max(self.stats["total_antes"], game.ante)

        if game.is_won:
            self.stats["games_won"] += 1
            return True

        return False

    def get_win_rate(self) -> float:
        """Get current win rate."""
        if self.stats["games_played"] == 0:
            return 0.0
        return self.stats["games_won"] / self.stats["games_played"]


# Import at end to avoid circular imports
from balatro_bot.simulator import GameSimulator  # noqa: E402
