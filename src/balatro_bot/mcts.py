"""Monte Carlo Tree Search for Balatro.

MCTS provides lookahead search to evaluate long-term consequences of actions.
Uses the heuristic player for fast rollouts during simulation.

Key components:
- UCB1 selection: balance exploitation vs exploration
- Heuristic-guided rollouts: fast simulation using rule-based play
- State cloning: perfect state capture for accurate simulation

The MCTS evaluates actions by:
1. Simulating many possible futures
2. Tracking win/survival rates
3. Returning action with highest expected value
"""

import math
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Self

from balatro_bot.heuristics import HeuristicPlayer, evaluate_plays, get_best_play
from balatro_bot.models import GameState
from balatro_bot.simulator import GamePhase, GameSimulator


class ActionKind(Enum):
    """Type of action in the MCTS tree."""

    PLAY = auto()
    DISCARD = auto()
    START_BLIND = auto()
    SKIP_BLIND = auto()
    END_SHOP = auto()


@dataclass
class MCTSAction:
    """An action that can be taken from a game state."""

    kind: ActionKind
    card_indices: list[int] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash((self.kind, tuple(self.card_indices)))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MCTSAction):
            return False
        return self.kind == other.kind and self.card_indices == other.card_indices


@dataclass
class MCTSNode:
    """A node in the MCTS tree.

    Each node represents a game state reached by taking an action.
    """

    # The action that led to this node (None for root)
    action: MCTSAction | None = None

    # Statistics
    visits: int = 0
    total_value: float = 0.0  # Sum of all rollout results
    wins: int = 0  # Number of wins in rollouts

    # Tree structure
    parent: Self | None = None
    children: dict[MCTSAction, Self] = field(default_factory=dict)

    # Untried actions from this state
    untried_actions: list[MCTSAction] = field(default_factory=list)

    # Cached game state for this node (optional, saves memory if None)
    _game_state: GameSimulator | None = None

    @property
    def is_fully_expanded(self) -> bool:
        """True if all actions have been tried."""
        return len(self.untried_actions) == 0

    @property
    def is_terminal(self) -> bool:
        """True if this is a terminal node (game over)."""
        return self._game_state is not None and self._game_state.is_game_over

    @property
    def average_value(self) -> float:
        """Average value from rollouts."""
        if self.visits == 0:
            return 0.0
        return self.total_value / self.visits

    @property
    def win_rate(self) -> float:
        """Win rate from rollouts."""
        if self.visits == 0:
            return 0.0
        return self.wins / self.visits

    def ucb1(self, exploration_constant: float = 1.414) -> float:
        """Calculate UCB1 value for node selection.

        UCB1 = average_value + C * sqrt(ln(parent_visits) / visits)

        Higher values are better - balances exploitation (high average)
        with exploration (less visited nodes).
        """
        if self.visits == 0:
            return float("inf")  # Prioritize unvisited nodes

        if self.parent is None or self.parent.visits == 0:
            return self.average_value

        exploitation = self.average_value
        exploration = exploration_constant * math.sqrt(
            math.log(self.parent.visits) / self.visits
        )
        return exploitation + exploration

    def best_child(self, exploration_constant: float = 1.414) -> Self | None:
        """Select best child using UCB1."""
        if not self.children:
            return None

        return max(
            self.children.values(),
            key=lambda c: c.ucb1(exploration_constant),
        )

    def best_action(self) -> MCTSAction | None:
        """Get the best action based on visit count (most robust)."""
        if not self.children:
            return None

        # Use visit count for final selection (more robust than average value)
        best_child = max(self.children.values(), key=lambda c: c.visits)
        return best_child.action


def get_legal_actions(game: GameSimulator) -> list[MCTSAction]:
    """Get all legal actions from the current game state."""
    actions: list[MCTSAction] = []

    if game.phase == GamePhase.BLIND_SELECT:
        actions.append(MCTSAction(kind=ActionKind.START_BLIND))
        # Can skip small/big blinds
        if game.blind_type.value != "boss":
            actions.append(MCTSAction(kind=ActionKind.SKIP_BLIND))

    elif game.phase == GamePhase.PLAYING:
        # Play actions
        for indices in game.get_legal_plays():
            actions.append(MCTSAction(kind=ActionKind.PLAY, card_indices=indices))

        # Discard actions (if discards remaining)
        if game.discards_remaining > 0:
            for indices in game.get_legal_discards():
                actions.append(MCTSAction(kind=ActionKind.DISCARD, card_indices=indices))

    elif game.phase == GamePhase.SHOP:
        # Simplified: just end shop for now
        # Could add buy/sell actions later
        actions.append(MCTSAction(kind=ActionKind.END_SHOP))

    return actions


def apply_action(game: GameSimulator, action: MCTSAction) -> None:
    """Apply an action to a game state (mutates game)."""
    if action.kind == ActionKind.PLAY:
        game.play_hand(action.card_indices)
    elif action.kind == ActionKind.DISCARD:
        game.discard(action.card_indices)
    elif action.kind == ActionKind.START_BLIND:
        game.start_blind()
    elif action.kind == ActionKind.SKIP_BLIND:
        game.skip_blind()
    elif action.kind == ActionKind.END_SHOP:
        game.end_shop()


@dataclass
class MCTSConfig:
    """Configuration for MCTS search."""

    # Search limits (use one or both)
    max_iterations: int = 1000
    max_time_seconds: float = 5.0

    # UCB1 exploration constant
    exploration_constant: float = 1.414

    # Rollout settings
    max_rollout_depth: int = 50  # Max actions in a rollout
    use_heuristic_rollouts: bool = True  # Use heuristic player for rollouts

    # Value function weights
    win_value: float = 1.0
    ante_value: float = 0.1  # Value per ante reached
    blind_value: float = 0.03  # Value per blind beaten

    # Pruning
    min_visits_for_expansion: int = 1  # Expand after this many visits


class MCTS:
    """Monte Carlo Tree Search implementation for Balatro."""

    def __init__(self, config: MCTSConfig | None = None):
        self.config = config or MCTSConfig()
        self.root: MCTSNode | None = None
        self.heuristic_player = HeuristicPlayer()

        # Statistics
        self.iterations = 0
        self.total_rollouts = 0

    def search(self, game: GameSimulator) -> MCTSAction | None:
        """Run MCTS search and return the best action.

        Args:
            game: Current game state (will not be modified)

        Returns:
            Best action found, or None if no actions available
        """
        # Initialize root
        self.root = MCTSNode()
        self.root._game_state = game.clone()
        self.root.untried_actions = get_legal_actions(game)

        if not self.root.untried_actions:
            return None

        # Search loop
        start_time = time.time()
        self.iterations = 0

        while self._should_continue(start_time):
            self.iterations += 1

            # Clone game state for this iteration
            node = self.root
            sim_game = game.clone()

            # Selection: traverse tree using UCB1
            node = self._select(node, sim_game)

            # Expansion: add a new child node
            if not node.is_terminal and node.untried_actions:
                node = self._expand(node, sim_game)

            # Simulation: rollout to terminal state
            value = self._simulate(sim_game)
            self.total_rollouts += 1

            # Backpropagation: update values up the tree
            self._backpropagate(node, value, sim_game.is_won)

        return self.root.best_action()

    def _should_continue(self, start_time: float) -> bool:
        """Check if search should continue."""
        if self.iterations >= self.config.max_iterations:
            return False
        if time.time() - start_time >= self.config.max_time_seconds:
            return False
        return True

    def _select(self, node: MCTSNode, game: GameSimulator) -> MCTSNode:
        """Select a node to expand using UCB1.

        Traverses tree until reaching a node that:
        - Has untried actions, or
        - Is terminal
        """
        while node.is_fully_expanded and node.children:
            best = node.best_child(self.config.exploration_constant)
            if best is None:
                break

            # Apply action to game state
            if best.action:
                apply_action(game, best.action)

            node = best

            # Update untried actions for this node if needed
            if not node.untried_actions and not node.children:
                node.untried_actions = get_legal_actions(game)

        return node

    def _expand(self, node: MCTSNode, game: GameSimulator) -> MCTSNode:
        """Expand the tree by adding a new child node."""
        if not node.untried_actions:
            return node

        # Pick an untried action (could prioritize with heuristics)
        action = self._select_untried_action(node, game)
        node.untried_actions.remove(action)

        # Apply action
        apply_action(game, action)

        # Create child node
        child = MCTSNode(
            action=action,
            parent=node,
            untried_actions=get_legal_actions(game),
        )
        node.children[action] = child

        return child

    def _select_untried_action(
        self, node: MCTSNode, game: GameSimulator
    ) -> MCTSAction:
        """Select which untried action to expand.

        Uses heuristics to prioritize promising actions.
        """
        if not node.untried_actions:
            raise ValueError("No untried actions")

        # For play actions, use heuristic evaluation to prioritize
        if game.phase == GamePhase.PLAYING:
            play_actions = [
                a for a in node.untried_actions if a.kind == ActionKind.PLAY
            ]

            if play_actions:
                # Evaluate plays with heuristics
                scored = evaluate_plays(
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

                # Find the top-scored action that's still untried
                for scored_action in scored:
                    for untried in play_actions:
                        if untried.card_indices == scored_action.card_indices:
                            return untried

        # Default: return first untried action
        return node.untried_actions[0]

    def _simulate(self, game: GameSimulator) -> float:
        """Simulate a game to completion and return value.

        Uses heuristic player for fast rollouts.
        """
        depth = 0

        while not game.is_game_over and depth < self.config.max_rollout_depth:
            if self.config.use_heuristic_rollouts:
                # Use heuristic player for the rollout
                if game.phase == GamePhase.BLIND_SELECT:
                    game.start_blind()
                elif game.phase == GamePhase.PLAYING:
                    # Use heuristic to pick action
                    best = get_best_play(
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
                    if best:
                        game.play_hand(best.card_indices)
                    else:
                        break
                elif game.phase == GamePhase.SHOP:
                    game.end_shop()
            else:
                # Random rollout
                actions = get_legal_actions(game)
                if not actions:
                    break
                import random
                action = random.choice(actions)
                apply_action(game, action)

            depth += 1

        return self._evaluate_terminal(game)

    def _evaluate_terminal(self, game: GameSimulator) -> float:
        """Evaluate a terminal game state.

        Returns value between 0 and 1 based on:
        - Win: high value
        - Ante reached: medium value
        - Loss: low value
        """
        if game.is_won:
            return self.config.win_value

        # Partial credit for progress
        value = 0.0

        # Credit for antes reached
        value += game.ante * self.config.ante_value

        # Credit for blinds beaten in current ante
        blind_progress = {"small": 0, "big": 1, "boss": 2}
        value += blind_progress.get(game.blind_type.value, 0) * self.config.blind_value

        return min(value, self.config.win_value)

    def _backpropagate(self, node: MCTSNode, value: float, is_win: bool) -> None:
        """Backpropagate the result up the tree."""
        while node is not None:
            node.visits += 1
            node.total_value += value
            if is_win:
                node.wins += 1
            node = node.parent

    def get_action_stats(self) -> dict[str, dict]:
        """Get statistics for each action from the root."""
        if self.root is None:
            return {}

        stats = {}
        for action, child in self.root.children.items():
            action_str = f"{action.kind.name}"
            if action.card_indices:
                action_str += f":{action.card_indices}"

            stats[action_str] = {
                "visits": child.visits,
                "avg_value": child.average_value,
                "win_rate": child.win_rate,
                "ucb1": child.ucb1(self.config.exploration_constant),
            }

        return stats


class MCTSPlayer:
    """A player that uses MCTS to make decisions."""

    def __init__(self, config: MCTSConfig | None = None):
        self.config = config or MCTSConfig()
        self.mcts = MCTS(self.config)

        # Statistics
        self.stats = {
            "games_played": 0,
            "games_won": 0,
            "total_iterations": 0,
            "total_rollouts": 0,
        }

    def get_action(self, game: GameSimulator) -> MCTSAction | None:
        """Get the best action for the current game state using MCTS."""
        action = self.mcts.search(game)

        self.stats["total_iterations"] += self.mcts.iterations
        self.stats["total_rollouts"] += self.mcts.total_rollouts

        return action

    def play_game(self, game: GameSimulator) -> bool:
        """Play a complete game using MCTS.

        Args:
            game: Game simulator

        Returns:
            True if game was won
        """
        self.stats["games_played"] += 1

        while not game.is_game_over:
            action = self.get_action(game)
            if action is None:
                # No valid actions, use heuristic fallback
                if game.phase == GamePhase.BLIND_SELECT:
                    game.start_blind()
                elif game.phase == GamePhase.SHOP:
                    game.end_shop()
                else:
                    break
            else:
                apply_action(game, action)

        if game.is_won:
            self.stats["games_won"] += 1
            return True

        return False

    def get_win_rate(self) -> float:
        """Get current win rate."""
        if self.stats["games_played"] == 0:
            return 0.0
        return self.stats["games_won"] / self.stats["games_played"]


def quick_mcts_action(
    game: GameSimulator,
    iterations: int = 100,
    time_limit: float = 1.0,
) -> MCTSAction | None:
    """Quick MCTS search with specified limits.

    Convenience function for one-off searches.
    """
    config = MCTSConfig(
        max_iterations=iterations,
        max_time_seconds=time_limit,
    )
    mcts = MCTS(config)
    return mcts.search(game)
