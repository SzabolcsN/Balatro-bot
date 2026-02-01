"""Scoring engine for Balatro.

Calculates final score by applying card and joker effects in order.

CRITICAL: Effect order matters! The full sequence is:
1. Base hand chips + base hand mult (from hand type)
2. For each scoring card (left to right):
   a. Card's chip value (rank-based, or +50 for Stone)
   b. Enhancement effects (Bonus +30, Mult +4, Glass ×2, etc.)
   c. Edition effects (Foil +50, Holo +10, Polychrome ×1.5)
   d. Seal effects (Red seal retriggers the card)
3. For each joker in order:
   a. Add chips (if any)
   b. Add mult (if any)
   c. Multiply mult (if any) - THIS IS WHERE ORDER MATTERS MOST
4. Final score = total_chips × total_mult

Example of why order matters:
- Joker A: +10 mult, Joker B: ×2 mult
- Order [A, B]: (base_mult + 10) × 2
- Order [B, A]: (base_mult × 2) + 10
These give very different results!
"""

import random
from dataclasses import dataclass, field

from balatro_bot.hand_evaluation import HandResult, evaluate_hand
from balatro_bot.jokers import JokerInstance
from balatro_bot.models import Card, Edition, Enhancement, GameState, HandType, Seal


@dataclass
class ScoringContext:
    """Context passed to jokers during scoring calculation.

    Contains all information a joker might need to calculate its effect.
    """

    # The cards that were played
    played_cards: list[Card]

    # Cards that actually score (subset of played_cards based on hand type)
    scoring_cards: list[Card]

    # Cards remaining in hand (not played)
    cards_in_hand: list[Card]

    # Hand evaluation result
    hand_result: HandResult

    # Full game state for context-dependent effects
    game_state: GameState

    # Current accumulated values (for some joker calculations)
    current_chips: int = 0
    current_mult: float = 0.0


@dataclass
class CardEffect:
    """Effect from a single card's modifiers."""

    card: Card
    chips: int = 0
    mult: int = 0
    mult_mult: float = 1.0
    money: int = 0  # Gold seal/enhancement money
    retrigger: int = 0  # Red seal retriggers
    destroyed: bool = False  # Glass card destruction


@dataclass
class ScoringBreakdown:
    """Detailed breakdown of how a score was calculated."""

    # Base values from hand type
    hand_type: HandType
    base_chips: int
    base_mult: int

    # Card modifier contributions
    card_effects: list[CardEffect] = field(default_factory=list)

    # Joker contributions in order
    joker_effects: list[tuple[str, int, int, float]] = field(default_factory=list)
    # Each tuple: (joker_name, chips_added, mult_added, mult_multiplied)

    # Economy effects
    money_earned: int = 0

    # Cards destroyed (Glass cards)
    destroyed_cards: list[Card] = field(default_factory=list)

    # Final values
    final_chips: int = 0
    final_mult: float = 0.0
    final_score: int = 0

    def add_card_effect(self, effect: CardEffect) -> None:
        """Record a card's contribution."""
        self.card_effects.append(effect)

    def add_joker_effect(
        self, name: str, chips: int = 0, mult: int = 0, mult_mult: float = 1.0
    ) -> None:
        """Record a joker's contribution."""
        self.joker_effects.append((name, chips, mult, mult_mult))


def apply_card_modifiers(
    card: Card, rng: random.Random | None = None
) -> CardEffect:
    """Calculate the scoring effect of a card's modifiers.

    Args:
        card: The card to process
        rng: Random number generator for Lucky card effects

    Returns:
        CardEffect with all bonuses from this card
    """
    effect = CardEffect(card=card)

    # Enhancement effects
    match card.enhancement:
        case Enhancement.BONUS:
            effect.chips += 30
        case Enhancement.MULT:
            effect.mult += 4
        case Enhancement.GLASS:
            effect.mult_mult *= 2.0
            # 1 in 4 chance to destroy
            if rng and rng.random() < 0.25:
                effect.destroyed = True
        case Enhancement.STEEL:
            # Steel only works while held in hand, not when scored
            # This is handled separately in calculate_score
            pass
        case Enhancement.STONE:
            # Stone cards add +50 chips (handled via chip_value override)
            # Already counted in hand_evaluation, no additional effect here
            pass
        case Enhancement.GOLD:
            # Gold enhancement gives money if held in hand at end of round
            # Not applicable during scoring - handled in game loop
            pass
        case Enhancement.LUCKY:
            if rng:
                # 1 in 5 chance for +20 Mult
                if rng.random() < 0.2:
                    effect.mult += 20
                # 1 in 15 chance for $20
                if rng.random() < 1 / 15:
                    effect.money += 20

    # Edition effects (applied to playing cards, not jokers)
    match card.edition:
        case Edition.FOIL:
            effect.chips += 50
        case Edition.HOLOGRAPHIC:
            effect.mult += 10
        case Edition.POLYCHROME:
            effect.mult_mult *= 1.5

    # Seal effects
    match card.seal:
        case Seal.GOLD:
            effect.money += 3
        case Seal.RED:
            effect.retrigger += 1
        # Blue and Purple seals don't affect scoring directly

    return effect


def apply_steel_cards_in_hand(
    cards_in_hand: list[Card],
) -> tuple[int, float]:
    """Calculate bonus from Steel cards held in hand.

    Steel cards give x1.5 Mult while held (not played).

    Returns:
        Tuple of (chips_bonus, mult_multiplier)
    """
    mult_mult = 1.0
    for card in cards_in_hand:
        if card.enhancement == Enhancement.STEEL:
            mult_mult *= 1.5
    return 0, mult_mult


def calculate_score(
    played_cards: list[Card],
    jokers: list[JokerInstance],
    game_state: GameState,
    cards_in_hand: list[Card] | None = None,
    rng_seed: int | None = None,
) -> ScoringBreakdown:
    """Calculate the score for a played hand with card and joker effects.

    Args:
        played_cards: Cards the player chose to play (1-5 cards)
        jokers: Jokers in order (ORDER MATTERS!)
        game_state: Current game state
        cards_in_hand: Cards remaining in hand (not played)
        rng_seed: Seed for random effects (Lucky cards, Glass destruction)

    Returns:
        ScoringBreakdown with full calculation details
    """
    if not played_cards:
        raise ValueError("Must play at least one card")

    if cards_in_hand is None:
        cards_in_hand = []

    # Set up RNG for random card effects
    rng = random.Random(rng_seed) if rng_seed is not None else None

    # Evaluate the hand
    hand_level = game_state.hand_levels.get(HandType.HIGH_CARD, 1)  # Default
    hand_result = evaluate_hand(played_cards)

    # Get the actual hand level for this hand type
    hand_level = game_state.hand_levels.get(hand_result.hand_type, 1)

    # Re-evaluate with correct hand level
    hand_result = evaluate_hand(played_cards, hand_level)

    # Initialize scoring breakdown
    breakdown = ScoringBreakdown(
        hand_type=hand_result.hand_type,
        base_chips=hand_result.base_chips,
        base_mult=hand_result.base_mult,
    )

    # Start with base values
    total_chips = hand_result.base_chips
    total_mult = float(hand_result.base_mult)
    total_money = 0

    # Apply card modifier effects for each SCORING card
    for card in hand_result.scoring_cards:
        # Calculate this card's modifier effects
        card_effect = apply_card_modifiers(card, rng)

        # Red seal causes retrigger - apply effects multiple times
        triggers = 1 + card_effect.retrigger
        for _ in range(triggers):
            # Apply in order: chips, +mult, ×mult
            total_chips += card_effect.chips
            total_mult += card_effect.mult
            total_mult *= card_effect.mult_mult
            total_money += card_effect.money

        # Record the effect
        breakdown.add_card_effect(card_effect)

        # Track destroyed cards (Glass)
        if card_effect.destroyed:
            breakdown.destroyed_cards.append(card)

    # Apply Steel card bonus from cards held in hand (not played)
    _, steel_mult = apply_steel_cards_in_hand(cards_in_hand)
    if steel_mult != 1.0:
        total_mult *= steel_mult

    # Record money earned from card effects
    breakdown.money_earned = total_money

    # Create scoring context for jokers
    ctx = ScoringContext(
        played_cards=played_cards,
        scoring_cards=hand_result.scoring_cards,
        cards_in_hand=cards_in_hand,
        hand_result=hand_result,
        game_state=game_state,
        current_chips=total_chips,
        current_mult=total_mult,
    )

    # Apply joker effects IN ORDER
    for joker in jokers:
        effect = joker.calculate_effect(ctx)

        if effect:
            # Apply in Balatro's order: chips, then +mult, then ×mult
            if effect.add_chips:
                total_chips += effect.add_chips

            if effect.add_mult:
                total_mult += effect.add_mult

            if effect.mult_mult != 1.0:
                total_mult *= effect.mult_mult

            # Record the effect
            breakdown.add_joker_effect(
                joker.name,
                chips=effect.add_chips,
                mult=effect.add_mult,
                mult_mult=effect.mult_mult,
            )

            # Update context for subsequent jokers
            ctx.current_chips = total_chips
            ctx.current_mult = total_mult

    # Calculate final score
    breakdown.final_chips = total_chips
    breakdown.final_mult = total_mult
    breakdown.final_score = int(total_chips * total_mult)

    return breakdown


def quick_score(
    played_cards: list[Card],
    jokers: list[JokerInstance] | None = None,
    game_state: GameState | None = None,
) -> int:
    """Quick score calculation returning just the final score.

    Convenience function for when you don't need the full breakdown.
    """
    if jokers is None:
        jokers = []
    if game_state is None:
        game_state = GameState()

    breakdown = calculate_score(played_cards, jokers, game_state)
    return breakdown.final_score


def estimate_hand_potential(
    hand: list[Card],
    jokers: list[JokerInstance],
    game_state: GameState,
) -> dict[str, int]:
    """Estimate potential scores for different card combinations from hand.

    Useful for AI decision making - evaluates what scores are possible
    with different subsets of the current hand.

    Returns:
        Dictionary mapping hand descriptions to their scores
    """
    from itertools import combinations

    results: dict[str, int] = {}

    # Try all possible plays (1-5 cards)
    for n_cards in range(1, min(6, len(hand) + 1)):
        for combo in combinations(hand, n_cards):
            cards = list(combo)
            remaining = [c for c in hand if c not in cards]

            try:
                breakdown = calculate_score(
                    played_cards=cards,
                    jokers=jokers,
                    game_state=game_state,
                    cards_in_hand=remaining,
                )
                key = f"{breakdown.hand_type.name}: {', '.join(str(c) for c in cards)}"
                results[key] = breakdown.final_score
            except ValueError:
                continue

    return dict(sorted(results.items(), key=lambda x: x[1], reverse=True))
