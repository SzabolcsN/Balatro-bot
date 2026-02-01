"""Game simulator for Balatro.

Provides a deterministic simulation engine for playing through Balatro runs.
Supports state cloning for MCTS and rollout simulations.

Key design decisions:
- Deterministic RNG with seed support for reproducible simulations
- Complete state capture for MCTS cloning
- Phase-based game flow (blind, shop, etc.)
- Joker state management with ordered effects
"""

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Self

from balatro_bot.jokers import JokerInstance, create_joker
from balatro_bot.models import Card, HandType, Rank, create_standard_deck
from balatro_bot.scoring import ScoringBreakdown, calculate_score


class GamePhase(Enum):
    """Current phase of the game."""

    BLIND_SELECT = auto()  # Choosing to play or skip blind
    PLAYING = auto()  # Playing hands against a blind
    SHOP = auto()  # Shopping phase between blinds
    GAME_OVER = auto()  # Run ended (win or loss)


class BlindType(Enum):
    """Type of blind in the current ante."""

    SMALL = "small"
    BIG = "big"
    BOSS = "boss"


@dataclass
class BlindConfig:
    """Configuration for a blind."""

    blind_type: BlindType
    name: str
    base_chips: int
    reward: int  # Money reward for beating
    boss_effect: str | None = None  # Boss blind special effect


# Base blind chip requirements (scaled by ante)
BLIND_BASE_CHIPS = {
    BlindType.SMALL: 300,
    BlindType.BIG: 450,
    BlindType.BOSS: 600,
}

BLIND_REWARDS = {
    BlindType.SMALL: 3,
    BlindType.BIG: 4,
    BlindType.BOSS: 5,
}

# Chip scaling per ante
ANTE_SCALING = {
    1: 1.0,
    2: 1.5,
    3: 2.0,
    4: 3.0,
    5: 4.0,
    6: 6.0,
    7: 9.0,
    8: 15.0,
}


@dataclass
class ActionResult:
    """Result of performing an action."""

    success: bool
    message: str
    score: int = 0
    breakdown: ScoringBreakdown | None = None
    blind_beaten: bool = False
    game_over: bool = False
    won: bool = False


@dataclass
class GameSimulator:
    """Deterministic game simulator for Balatro.

    Manages complete game state and provides methods for all game actions.
    Supports cloning for MCTS simulations.
    """

    # Deck state
    deck: list[Card] = field(default_factory=list)
    hand: list[Card] = field(default_factory=list)
    played_this_round: list[Card] = field(default_factory=list)

    # Jokers (ORDER MATTERS)
    jokers: list[JokerInstance] = field(default_factory=list)
    max_jokers: int = 5

    # Economy
    money: int = 4

    # Progress
    ante: int = 1
    max_ante: int = 8  # Win condition
    blind_type: BlindType = BlindType.SMALL

    # Round state
    hands_remaining: int = 4
    discards_remaining: int = 3
    current_chips: int = 0
    blind_chips: int = 300

    # Hand size
    hand_size: int = 8

    # Game phase
    phase: GamePhase = GamePhase.BLIND_SELECT

    # Hand levels (from planet cards)
    hand_levels: dict[HandType, int] = field(
        default_factory=lambda: {ht: 1 for ht in HandType}
    )

    # RNG
    rng: random.Random = field(default_factory=random.Random)
    _seed: int | None = None

    def __post_init__(self):
        """Initialize the game if deck is empty."""
        if not self.deck and not self.hand:
            self.reset()

    def reset(self, seed: int | None = None) -> None:
        """Reset the game to initial state."""
        self._seed = seed
        if seed is not None:
            self.rng = random.Random(seed)
        else:
            self.rng = random.Random()

        # Create and shuffle deck
        self.deck = create_standard_deck()
        self.rng.shuffle(self.deck)

        # Reset all state
        self.hand = []
        self.played_this_round = []
        self.jokers = []
        self.money = 4
        self.ante = 1
        self.blind_type = BlindType.SMALL
        self.hands_remaining = 4
        self.discards_remaining = 3
        self.current_chips = 0
        self.blind_chips = self._calculate_blind_chips()
        self.phase = GamePhase.BLIND_SELECT
        self.hand_levels = {ht: 1 for ht in HandType}

    def clone(self) -> Self:
        """Create a deep copy for MCTS simulation.

        Critical: Must capture complete state for accurate rollouts.
        """
        cloned = GameSimulator(
            deck=[Card(c.rank, c.suit) for c in self.deck],
            hand=[Card(c.rank, c.suit) for c in self.hand],
            played_this_round=[Card(c.rank, c.suit) for c in self.played_this_round],
            jokers=[
                JokerInstance(j.definition, dict(j.state)) for j in self.jokers
            ],
            max_jokers=self.max_jokers,
            money=self.money,
            ante=self.ante,
            max_ante=self.max_ante,
            blind_type=self.blind_type,
            hands_remaining=self.hands_remaining,
            discards_remaining=self.discards_remaining,
            current_chips=self.current_chips,
            blind_chips=self.blind_chips,
            hand_size=self.hand_size,
            phase=self.phase,
            hand_levels=dict(self.hand_levels),
            rng=random.Random(),
            _seed=self._seed,
        )
        # Copy RNG state
        cloned.rng.setstate(self.rng.getstate())
        return cloned

    # =========================================================================
    # Blind Management
    # =========================================================================

    def _calculate_blind_chips(self) -> int:
        """Calculate chip requirement for current blind."""
        base = BLIND_BASE_CHIPS[self.blind_type]
        scale = ANTE_SCALING.get(self.ante, 15.0 + (self.ante - 8) * 5)
        return int(base * scale)

    def start_blind(self) -> ActionResult:
        """Start playing the current blind."""
        if self.phase != GamePhase.BLIND_SELECT:
            return ActionResult(False, "Not in blind select phase")

        self.phase = GamePhase.PLAYING
        self.hands_remaining = 4
        self.discards_remaining = 3
        self.current_chips = 0
        self.blind_chips = self._calculate_blind_chips()
        self.played_this_round = []

        # Draw initial hand
        self._draw_to_hand_size()

        return ActionResult(
            True, f"Started {self.blind_type.value} blind. Need {self.blind_chips} chips."
        )

    def skip_blind(self) -> ActionResult:
        """Skip the current blind (small/big only, not boss)."""
        if self.phase != GamePhase.BLIND_SELECT:
            return ActionResult(False, "Not in blind select phase")

        if self.blind_type == BlindType.BOSS:
            return ActionResult(False, "Cannot skip boss blind")

        # Get skip reward (tag system - simplified)
        skip_reward = 1 if self.blind_type == BlindType.SMALL else 1
        self.money += skip_reward

        # Advance to next blind
        self._advance_blind()

        return ActionResult(True, f"Skipped blind, got ${skip_reward}")

    def _advance_blind(self) -> None:
        """Advance to the next blind or ante."""
        if self.blind_type == BlindType.SMALL:
            self.blind_type = BlindType.BIG
            self.phase = GamePhase.BLIND_SELECT
        elif self.blind_type == BlindType.BIG:
            self.blind_type = BlindType.BOSS
            self.phase = GamePhase.BLIND_SELECT
        else:  # BOSS
            self.ante += 1
            self.blind_type = BlindType.SMALL

            if self.ante > self.max_ante:
                self.phase = GamePhase.GAME_OVER
            else:
                self.phase = GamePhase.SHOP

    # =========================================================================
    # Deck Management
    # =========================================================================

    def _draw_to_hand_size(self) -> int:
        """Draw cards until hand is at hand_size. Returns number drawn."""
        cards_to_draw = self.hand_size - len(self.hand)
        cards_drawn = 0

        for _ in range(cards_to_draw):
            if self.deck:
                self.hand.append(self.deck.pop())
                cards_drawn += 1

        return cards_drawn

    def _reshuffle_played(self) -> None:
        """Shuffle played cards back into deck."""
        self.deck.extend(self.played_this_round)
        self.played_this_round = []
        self.rng.shuffle(self.deck)

    # =========================================================================
    # Game Actions
    # =========================================================================

    def play_hand(self, card_indices: list[int]) -> ActionResult:
        """Play cards from hand.

        Args:
            card_indices: Indices of cards in hand to play (0-based)

        Returns:
            ActionResult with score and whether blind was beaten
        """
        if self.phase != GamePhase.PLAYING:
            return ActionResult(False, "Not in playing phase")

        if self.hands_remaining <= 0:
            return ActionResult(False, "No hands remaining")

        if not card_indices:
            return ActionResult(False, "Must play at least one card")

        if len(card_indices) > 5:
            return ActionResult(False, "Cannot play more than 5 cards")

        # Validate indices
        if any(i < 0 or i >= len(self.hand) for i in card_indices):
            return ActionResult(False, "Invalid card index")

        if len(card_indices) != len(set(card_indices)):
            return ActionResult(False, "Duplicate card indices")

        # Get cards to play
        cards_to_play = [self.hand[i] for i in sorted(card_indices, reverse=True)]

        # Remove from hand (reverse order to preserve indices)
        for i in sorted(card_indices, reverse=True):
            self.hand.pop(i)

        # Calculate score
        from balatro_bot.models import GameState

        game_state = GameState(
            hand_levels=self.hand_levels,
            discards_remaining=self.discards_remaining,
        )

        breakdown = calculate_score(
            played_cards=cards_to_play,
            jokers=self.jokers,
            game_state=game_state,
            cards_in_hand=self.hand,
        )

        # Update joker states (scaling jokers)
        self._update_joker_states_after_play(cards_to_play)

        # Add score
        self.current_chips += breakdown.final_score
        self.hands_remaining -= 1

        # Move played cards to played pile
        self.played_this_round.extend(cards_to_play)

        # Check if blind is beaten
        blind_beaten = self.current_chips >= self.blind_chips

        if blind_beaten:
            return self._handle_blind_beaten(breakdown)

        # Check for game over (no hands left and blind not beaten)
        if self.hands_remaining <= 0:
            self.phase = GamePhase.GAME_OVER
            msg = (
                f"Scored {breakdown.final_score}. "
                f"Total: {self.current_chips}/{self.blind_chips}. GAME OVER - blind not beaten!"
            )
            return ActionResult(
                True,
                msg,
                score=breakdown.final_score,
                breakdown=breakdown,
                game_over=True,
                won=False,
            )

        # Draw back to hand size
        self._draw_to_hand_size()

        msg = (
            f"Scored {breakdown.final_score}. "
            f"Total: {self.current_chips}/{self.blind_chips}. {self.hands_remaining} hands left."
        )
        return ActionResult(
            True,
            msg,
            score=breakdown.final_score,
            breakdown=breakdown,
        )

    def _handle_blind_beaten(self, breakdown: ScoringBreakdown) -> ActionResult:
        """Handle beating the current blind."""
        # Award money
        reward = BLIND_REWARDS[self.blind_type]
        interest = min(self.money // 5, 5)  # $1 per $5, max $5
        total_reward = reward + interest

        self.money += total_reward

        # Reshuffle played cards
        self._reshuffle_played()

        # Also put hand back
        self.deck.extend(self.hand)
        self.hand = []
        self.rng.shuffle(self.deck)

        # Check for win
        if self.blind_type == BlindType.BOSS and self.ante >= self.max_ante:
            self.phase = GamePhase.GAME_OVER
            return ActionResult(
                True,
                f"Scored {breakdown.final_score}. BLIND BEATEN! YOU WIN! Earned ${total_reward}.",
                score=breakdown.final_score,
                breakdown=breakdown,
                blind_beaten=True,
                game_over=True,
                won=True,
            )

        # Advance to next blind
        self._advance_blind()

        return ActionResult(
            True,
            f"Scored {breakdown.final_score}. BLIND BEATEN! Earned ${total_reward}.",
            score=breakdown.final_score,
            breakdown=breakdown,
            blind_beaten=True,
        )

    def discard(self, card_indices: list[int]) -> ActionResult:
        """Discard cards from hand.

        Args:
            card_indices: Indices of cards in hand to discard (0-based)

        Returns:
            ActionResult
        """
        if self.phase != GamePhase.PLAYING:
            return ActionResult(False, "Not in playing phase")

        if self.discards_remaining <= 0:
            return ActionResult(False, "No discards remaining")

        if not card_indices:
            return ActionResult(False, "Must discard at least one card")

        if len(card_indices) > 5:
            return ActionResult(False, "Cannot discard more than 5 cards")

        # Validate indices
        if any(i < 0 or i >= len(self.hand) for i in card_indices):
            return ActionResult(False, "Invalid card index")

        if len(card_indices) != len(set(card_indices)):
            return ActionResult(False, "Duplicate card indices")

        # Get cards to discard
        cards_to_discard = [self.hand[i] for i in sorted(card_indices, reverse=True)]

        # Remove from hand
        for i in sorted(card_indices, reverse=True):
            self.hand.pop(i)

        # Update joker states (green joker, etc.)
        self._update_joker_states_after_discard(cards_to_discard)

        self.discards_remaining -= 1

        # Move to played pile
        self.played_this_round.extend(cards_to_discard)

        # Draw back to hand size
        drawn = self._draw_to_hand_size()

        msg = (
            f"Discarded {len(cards_to_discard)} cards, drew {drawn}. "
            f"{self.discards_remaining} discards left."
        )
        return ActionResult(True, msg)

    def _update_joker_states_after_play(self, played_cards: list[Card]) -> None:
        """Update joker states after playing a hand."""
        for joker in self.jokers:
            if joker.id == "ice_cream":
                current = joker.state.get("chips", 100)
                joker.state["chips"] = max(0, current - 5)

            elif joker.id == "green_joker":
                current = joker.state.get("mult", 0)
                joker.state["mult"] = current + 1

            elif joker.id == "ride_the_bus":
                has_face = any(c.rank in (Rank.JACK, Rank.QUEEN, Rank.KING) for c in played_cards)
                if has_face:
                    joker.state["mult"] = 0
                else:
                    current = joker.state.get("mult", 0)
                    joker.state["mult"] = current + 1

    def _update_joker_states_after_discard(self, discarded_cards: list[Card]) -> None:
        """Update joker states after discarding."""
        for joker in self.jokers:
            if joker.id == "green_joker":
                current = joker.state.get("mult", 0)
                joker.state["mult"] = max(0, current - 1)

    # =========================================================================
    # Shop Actions
    # =========================================================================

    def end_shop(self) -> ActionResult:
        """End the shop phase and move to next blind."""
        if self.phase != GamePhase.SHOP:
            return ActionResult(False, "Not in shop phase")

        self.phase = GamePhase.BLIND_SELECT
        return ActionResult(True, f"Entering {self.blind_type.value} blind select.")

    def buy_joker(self, joker_id: str, cost: int) -> ActionResult:
        """Buy a joker from the shop.

        Args:
            joker_id: ID of joker to buy
            cost: Cost of the joker

        Returns:
            ActionResult
        """
        if self.phase != GamePhase.SHOP:
            return ActionResult(False, "Not in shop phase")

        if self.money < cost:
            return ActionResult(False, f"Not enough money (have ${self.money}, need ${cost})")

        if len(self.jokers) >= self.max_jokers:
            return ActionResult(False, f"Joker slots full ({self.max_jokers}/{self.max_jokers})")

        try:
            joker = create_joker(joker_id)
        except ValueError as e:
            return ActionResult(False, str(e))

        self.money -= cost
        self.jokers.append(joker)

        return ActionResult(True, f"Bought {joker.name} for ${cost}. ${self.money} remaining.")

    def sell_joker(self, joker_index: int) -> ActionResult:
        """Sell a joker.

        Args:
            joker_index: Index of joker to sell (0-based)

        Returns:
            ActionResult with sell price
        """
        if joker_index < 0 or joker_index >= len(self.jokers):
            return ActionResult(False, "Invalid joker index")

        joker = self.jokers.pop(joker_index)
        sell_price = joker.definition.base_cost // 2
        self.money += sell_price

        return ActionResult(True, f"Sold {joker.name} for ${sell_price}. ${self.money} total.")

    def reorder_jokers(self, new_order: list[int]) -> ActionResult:
        """Reorder jokers (order affects scoring!).

        Args:
            new_order: New indices for jokers (e.g., [2, 0, 1] moves joker 2 to front)

        Returns:
            ActionResult
        """
        if len(new_order) != len(self.jokers):
            return ActionResult(False, "Must specify position for all jokers")

        if sorted(new_order) != list(range(len(self.jokers))):
            return ActionResult(False, "Invalid joker order")

        self.jokers = [self.jokers[i] for i in new_order]
        return ActionResult(True, "Jokers reordered")

    # =========================================================================
    # State Queries
    # =========================================================================

    def get_legal_plays(self) -> list[list[int]]:
        """Get all legal card combinations to play.

        Returns list of card index lists (each representing a valid play).
        """
        if self.phase != GamePhase.PLAYING or self.hands_remaining <= 0:
            return []

        from itertools import combinations

        plays = []
        for n in range(1, min(6, len(self.hand) + 1)):
            for combo in combinations(range(len(self.hand)), n):
                plays.append(list(combo))

        return plays

    def get_legal_discards(self) -> list[list[int]]:
        """Get all legal discard combinations.

        Returns list of card index lists.
        """
        if self.phase != GamePhase.PLAYING or self.discards_remaining <= 0:
            return []

        from itertools import combinations

        discards = []
        for n in range(1, min(6, len(self.hand) + 1)):
            for combo in combinations(range(len(self.hand)), n):
                discards.append(list(combo))

        return discards

    @property
    def is_game_over(self) -> bool:
        """Check if the game has ended."""
        return self.phase == GamePhase.GAME_OVER

    @property
    def is_won(self) -> bool:
        """Check if the game was won."""
        return self.phase == GamePhase.GAME_OVER and self.ante > self.max_ante

    def get_state_summary(self) -> dict:
        """Get a summary of current game state."""
        return {
            "phase": self.phase.name,
            "ante": self.ante,
            "blind": self.blind_type.value,
            "chips": f"{self.current_chips}/{self.blind_chips}",
            "hands": self.hands_remaining,
            "discards": self.discards_remaining,
            "money": self.money,
            "hand_size": len(self.hand),
            "deck_size": len(self.deck),
            "jokers": [j.name for j in self.jokers],
        }
