"""Neural network components for Balatro AI.

Provides policy and value networks that can:
1. Bias MCTS exploration with learned priors
2. Estimate state values to reduce rollout needs
3. Learn non-obvious joker synergies from self-play

Architecture: Dual-head network with shared feature extraction
- Input: Vectorized game state
- Policy head: Action probabilities
- Value head: State value estimate (expected outcome)
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from balatro_bot.simulator import GameSimulator

# Try to import torch, but make it optional
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, Dataset

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None
    F = None


# =============================================================================
# State Vectorization
# =============================================================================

# Card encoding constants
NUM_RANKS = 13  # 2-A
NUM_SUITS = 4  # S, H, C, D
CARDS_PER_SUIT = 13
TOTAL_CARDS = 52

# Joker encoding
MAX_JOKERS = 5
NUM_JOKER_TYPES = 150  # Number of implemented jokers

# Action encoding
MAX_HAND_SIZE = 8
MAX_CARDS_TO_PLAY = 5


@dataclass
class StateVector:
    """Vectorized game state for neural network input."""

    # Hand representation (52-dim: 1 if card in hand, 0 otherwise)
    hand_cards: np.ndarray  # shape: (52,)

    # Joker representation (one-hot for each slot)
    joker_ids: np.ndarray  # shape: (MAX_JOKERS, NUM_JOKER_TYPES)
    joker_states: np.ndarray  # shape: (MAX_JOKERS, 4) - normalized state values

    # Game progress
    ante: float  # normalized 0-1 (ante/8)
    blind_type: np.ndarray  # one-hot (3,): small, big, boss
    chips_progress: float  # current_chips / blind_chips (capped at 1)

    # Economy
    money: float  # normalized (money / 100, capped)
    hands_remaining: float  # normalized (hands / 4)
    discards_remaining: float  # normalized (discards / 3)

    # Hand levels (13 hand types, normalized)
    hand_levels: np.ndarray  # shape: (13,)

    def to_tensor(self) -> "torch.Tensor":
        """Convert to a flat tensor for network input."""
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch is required for neural network features")

        # Flatten all components
        components = [
            self.hand_cards,  # 52
            self.joker_ids.flatten(),  # 5 * 150 = 750
            self.joker_states.flatten(),  # 5 * 4 = 20
            np.array([self.ante]),  # 1
            self.blind_type,  # 3
            np.array([self.chips_progress]),  # 1
            np.array([self.money]),  # 1
            np.array([self.hands_remaining]),  # 1
            np.array([self.discards_remaining]),  # 1
            self.hand_levels,  # 13
        ]
        # Total: 52 + 750 + 20 + 1 + 3 + 1 + 1 + 1 + 1 + 13 = 843

        flat = np.concatenate(components).astype(np.float32)
        return torch.from_numpy(flat)

    @staticmethod
    def input_size() -> int:
        """Size of the flattened input vector."""
        return 843


# Joker ID mapping (all 150 jokers)
JOKER_ID_MAP = {
    "abstract_joker": 0,
    "acrobat": 1,
    "ancient_joker": 2,
    "arrowhead": 3,
    "astronomer": 4,
    "banner": 5,
    "baron": 6,
    "baseball_card": 7,
    "blackboard": 8,
    "bloodstone": 9,
    "blue_joker": 10,
    "blueprint": 11,
    "bootstraps": 12,
    "brainstorm": 13,
    "bull": 14,
    "burglar": 15,
    "burnt_joker": 16,
    "business_card": 17,
    "campfire": 18,
    "canio": 19,
    "card_sharp": 20,
    "cartomancer": 21,
    "castle": 22,
    "cavendish": 23,
    "ceremonial_dagger": 24,
    "certificate": 25,
    "chaos_the_clown": 26,
    "chicot": 27,
    "clever_joker": 28,
    "cloud_9": 29,
    "constellation": 30,
    "crafty_joker": 31,
    "crazy_joker": 32,
    "credit_card": 33,
    "delayed_gratification": 34,
    "devious_joker": 35,
    "diet_cola": 36,
    "dna": 37,
    "drivers_license": 38,
    "droll_joker": 39,
    "drunkard": 40,
    "dusk": 41,
    "egg": 42,
    "eight_ball": 43,
    "erosion": 44,
    "even_steven": 45,
    "faceless_joker": 46,
    "fibonacci": 47,
    "flash_card": 48,
    "flower_pot": 49,
    "fortune_teller": 50,
    "four_fingers": 51,
    "gift_card": 52,
    "glass_joker": 53,
    "gluttonous_joker": 54,
    "golden_joker": 55,
    "golden_ticket": 56,
    "greedy_joker": 57,
    "green_joker": 58,
    "gros_michel": 59,
    "hack": 60,
    "half_joker": 61,
    "hallucination": 62,
    "hanging_chad": 63,
    "hiker": 64,
    "hit_the_road": 65,
    "hologram": 66,
    "ice_cream": 67,
    "invisible_joker": 68,
    "joker": 69,
    "joker_stencil": 70,
    "jolly_joker": 71,
    "juggler": 72,
    "loyalty_card": 73,
    "luchador": 74,
    "lucky_cat": 75,
    "lusty_joker": 76,
    "mad_joker": 77,
    "madness": 78,
    "mail_in_rebate": 79,
    "marble_joker": 80,
    "matador": 81,
    "merry_andy": 82,
    "midas_mask": 83,
    "mime": 84,
    "misprint": 85,
    "mr_bones": 86,
    "mystic_summit": 87,
    "obelisk": 88,
    "odd_todd": 89,
    "onyx_agate": 90,
    "oops_all_6s": 91,
    "pareidolia": 92,
    "perkeo": 93,
    "photograph": 94,
    "popcorn": 95,
    "raised_fist": 96,
    "ramen": 97,
    "red_card": 98,
    "reserved_parking": 99,
    "ride_the_bus": 100,
    "riff_raff": 101,
    "rocket": 102,
    "rough_gem": 103,
    "runner": 104,
    "satellite": 105,
    "scary_face": 106,
    "scholar": 107,
    "seance": 108,
    "seeing_double": 109,
    "seltzer": 110,
    "shoot_the_moon": 111,
    "shortcut": 112,
    "showman": 113,
    "sixth_sense": 114,
    "sly_joker": 115,
    "smeared_joker": 116,
    "smiley_face": 117,
    "sock_and_buskin": 118,
    "space_joker": 119,
    "spare_trousers": 120,
    "splash": 121,
    "square_joker": 122,
    "steel_joker": 123,
    "stone_joker": 124,
    "stuntman": 125,
    "supernova": 126,
    "superposition": 127,
    "swashbuckler": 128,
    "the_duo": 129,
    "the_family": 130,
    "the_idol": 131,
    "the_order": 132,
    "the_tribe": 133,
    "the_trio": 134,
    "throwback": 135,
    "to_do_list": 136,
    "to_the_moon": 137,
    "trading_card": 138,
    "triboulet": 139,
    "troubadour": 140,
    "turtle_bean": 141,
    "vagabond": 142,
    "vampire": 143,
    "walkie_talkie": 144,
    "wee_joker": 145,
    "wily_joker": 146,
    "wrathful_joker": 147,
    "yorick": 148,
    "zany_joker": 149,
}


def card_to_index(rank_value: int, suit_value: str) -> int:
    """Convert card to index 0-51."""
    suit_map = {"S": 0, "H": 1, "C": 2, "D": 3}
    suit_idx = suit_map[suit_value]
    rank_idx = rank_value - 2  # 2 is rank 0
    return suit_idx * 13 + rank_idx


def vectorize_state(game: "GameSimulator") -> StateVector:
    """Convert game state to vector representation."""
    # Hand cards (52-dim binary)
    hand_cards = np.zeros(52, dtype=np.float32)
    for card in game.hand:
        idx = card_to_index(card.rank.value, card.suit.value)
        hand_cards[idx] = 1.0

    # Joker IDs (one-hot)
    joker_ids = np.zeros((MAX_JOKERS, NUM_JOKER_TYPES), dtype=np.float32)
    joker_states = np.zeros((MAX_JOKERS, 4), dtype=np.float32)

    for i, joker in enumerate(game.jokers[:MAX_JOKERS]):
        joker_idx = JOKER_ID_MAP.get(joker.id, 0)
        joker_ids[i, joker_idx] = 1.0

        # Encode joker state (normalized)
        if "chips" in joker.state:
            joker_states[i, 0] = joker.state["chips"] / 100.0
        if "mult" in joker.state:
            joker_states[i, 1] = joker.state["mult"] / 10.0

    # Blind type (one-hot)
    blind_type = np.zeros(3, dtype=np.float32)
    blind_map = {"small": 0, "big": 1, "boss": 2}
    blind_type[blind_map.get(game.blind_type.value, 0)] = 1.0

    # Hand levels (normalized)
    from balatro_bot.models import HandType

    hand_levels = np.zeros(13, dtype=np.float32)
    for i, ht in enumerate(HandType):
        if i < 13:
            hand_levels[i] = game.hand_levels.get(ht, 1) / 5.0  # Normalize by max level

    return StateVector(
        hand_cards=hand_cards,
        joker_ids=joker_ids,
        joker_states=joker_states,
        ante=game.ante / 8.0,
        blind_type=blind_type,
        chips_progress=min(1.0, game.current_chips / max(1, game.blind_chips)),
        money=min(1.0, game.money / 100.0),
        hands_remaining=game.hands_remaining / 4.0,
        discards_remaining=game.discards_remaining / 3.0,
        hand_levels=hand_levels,
    )


# =============================================================================
# Action Encoding
# =============================================================================


@dataclass
class ActionEncoder:
    """Encodes actions to indices and vice versa.

    For simplicity, we encode a subset of common actions:
    - Top N play actions (by heuristic score)
    - Top M discard actions
    - Special actions (start blind, skip, end shop)
    """

    num_play_actions: int = 50  # Top 50 plays
    num_discard_actions: int = 20  # Top 20 discards
    num_special_actions: int = 3  # start, skip, end_shop

    @property
    def total_actions(self) -> int:
        return self.num_play_actions + self.num_discard_actions + self.num_special_actions

    def encode_play(self, rank: int) -> int:
        """Encode a play action by its heuristic rank (0 = best)."""
        return min(rank, self.num_play_actions - 1)

    def encode_discard(self, rank: int) -> int:
        """Encode a discard action by its heuristic rank."""
        return self.num_play_actions + min(rank, self.num_discard_actions - 1)

    def encode_special(self, action_type: str) -> int:
        """Encode a special action."""
        special_map = {"start_blind": 0, "skip_blind": 1, "end_shop": 2}
        return (
            self.num_play_actions
            + self.num_discard_actions
            + special_map.get(action_type, 0)
        )

    def is_play_action(self, idx: int) -> bool:
        return idx < self.num_play_actions

    def is_discard_action(self, idx: int) -> bool:
        return self.num_play_actions <= idx < self.num_play_actions + self.num_discard_actions

    def is_special_action(self, idx: int) -> bool:
        return idx >= self.num_play_actions + self.num_discard_actions


# =============================================================================
# Neural Network Architecture
# =============================================================================

if TORCH_AVAILABLE:

    class BalatroNet(nn.Module):
        """Dual-head neural network for Balatro.

        Architecture:
        - Shared feature extraction (MLP)
        - Policy head: outputs action logits
        - Value head: outputs state value
        """

        def __init__(
            self,
            input_size: int = 843,
            hidden_size: int = 256,
            num_actions: int = 73,  # 50 plays + 20 discards + 3 special
        ):
            super().__init__()

            self.input_size = input_size
            self.hidden_size = hidden_size
            self.num_actions = num_actions

            # Shared feature extraction
            self.shared = nn.Sequential(
                nn.Linear(input_size, hidden_size),
                nn.ReLU(),
                nn.Linear(hidden_size, hidden_size),
                nn.ReLU(),
                nn.Linear(hidden_size, hidden_size // 2),
                nn.ReLU(),
            )

            # Policy head
            self.policy_head = nn.Sequential(
                nn.Linear(hidden_size // 2, hidden_size // 2),
                nn.ReLU(),
                nn.Linear(hidden_size // 2, num_actions),
            )

            # Value head
            self.value_head = nn.Sequential(
                nn.Linear(hidden_size // 2, hidden_size // 4),
                nn.ReLU(),
                nn.Linear(hidden_size // 4, 1),
                nn.Tanh(),  # Value in [-1, 1]
            )

        def forward(
            self, x: torch.Tensor
        ) -> tuple[torch.Tensor, torch.Tensor]:
            """Forward pass.

            Args:
                x: Input tensor of shape (batch, input_size)

            Returns:
                policy_logits: Shape (batch, num_actions)
                value: Shape (batch, 1)
            """
            features = self.shared(x)
            policy_logits = self.policy_head(features)
            value = self.value_head(features)
            return policy_logits, value

        def get_policy(self, x: torch.Tensor) -> torch.Tensor:
            """Get policy probabilities (softmax of logits)."""
            logits, _ = self.forward(x)
            return F.softmax(logits, dim=-1)

        def get_value(self, x: torch.Tensor) -> torch.Tensor:
            """Get state value estimate."""
            _, value = self.forward(x)
            return value


# =============================================================================
# Training Data Collection
# =============================================================================


@dataclass
class TrainingExample:
    """A single training example from self-play."""

    state_vector: np.ndarray  # Flattened state
    action_idx: int  # Action taken (encoded)
    action_probs: np.ndarray  # MCTS visit counts (normalized)
    outcome: float  # Game outcome: 1 for win, 0 for loss, partial for progress


@dataclass
class ExperienceBuffer:
    """Buffer for collecting training data from self-play."""

    examples: list[TrainingExample] = field(default_factory=list)
    max_size: int = 100000

    def add(self, example: TrainingExample) -> None:
        """Add an example to the buffer."""
        self.examples.append(example)
        if len(self.examples) > self.max_size:
            # Remove oldest examples
            self.examples = self.examples[-self.max_size :]

    def sample(self, batch_size: int) -> list[TrainingExample]:
        """Sample a batch of examples."""
        if len(self.examples) < batch_size:
            return self.examples
        indices = np.random.choice(len(self.examples), batch_size, replace=False)
        return [self.examples[i] for i in indices]

    def __len__(self) -> int:
        return len(self.examples)

    def save(self, path: str) -> None:
        """Save buffer to file."""
        data = {
            "examples": [
                {
                    "state": ex.state_vector.tolist(),
                    "action": ex.action_idx,
                    "probs": ex.action_probs.tolist(),
                    "outcome": ex.outcome,
                }
                for ex in self.examples
            ]
        }
        Path(path).write_text(json.dumps(data))

    def load(self, path: str) -> None:
        """Load buffer from file."""
        data = json.loads(Path(path).read_text())
        self.examples = [
            TrainingExample(
                state_vector=np.array(ex["state"], dtype=np.float32),
                action_idx=ex["action"],
                action_probs=np.array(ex["probs"], dtype=np.float32),
                outcome=ex["outcome"],
            )
            for ex in data["examples"]
        ]


# =============================================================================
# Training Loop
# =============================================================================

if TORCH_AVAILABLE:

    class BalatroDataset(Dataset):
        """PyTorch dataset for training examples."""

        def __init__(self, examples: list[TrainingExample]):
            self.examples = examples

        def __len__(self) -> int:
            return len(self.examples)

        def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
            ex = self.examples[idx]
            state = torch.from_numpy(ex.state_vector)
            probs = torch.from_numpy(ex.action_probs)
            outcome = torch.tensor([ex.outcome], dtype=torch.float32)
            return state, probs, outcome

    class Trainer:
        """Training loop for the neural network."""

        def __init__(
            self,
            net: BalatroNet,
            learning_rate: float = 1e-3,
            policy_weight: float = 1.0,
            value_weight: float = 1.0,
        ):
            self.net = net
            self.optimizer = torch.optim.Adam(net.parameters(), lr=learning_rate)
            self.policy_weight = policy_weight
            self.value_weight = value_weight

            # Training stats
            self.train_steps = 0
            self.policy_losses: list[float] = []
            self.value_losses: list[float] = []

        def train_batch(
            self, states: torch.Tensor, target_probs: torch.Tensor, target_values: torch.Tensor
        ) -> tuple[float, float]:
            """Train on a single batch.

            Args:
                states: Shape (batch, input_size)
                target_probs: Shape (batch, num_actions) - MCTS policy targets
                target_values: Shape (batch, 1) - outcome targets

            Returns:
                (policy_loss, value_loss)
            """
            self.net.train()
            self.optimizer.zero_grad()

            # Forward pass
            policy_logits, values = self.net(states)

            # Policy loss: cross-entropy with MCTS policy
            log_probs = F.log_softmax(policy_logits, dim=-1)
            policy_loss = -torch.sum(target_probs * log_probs, dim=-1).mean()

            # Value loss: MSE with outcome
            value_loss = F.mse_loss(values, target_values)

            # Combined loss
            loss = self.policy_weight * policy_loss + self.value_weight * value_loss

            # Backward pass
            loss.backward()
            self.optimizer.step()

            self.train_steps += 1
            self.policy_losses.append(policy_loss.item())
            self.value_losses.append(value_loss.item())

            return policy_loss.item(), value_loss.item()

        def train_epoch(
            self, buffer: ExperienceBuffer, batch_size: int = 32
        ) -> tuple[float, float]:
            """Train for one epoch over the buffer.

            Returns:
                (avg_policy_loss, avg_value_loss)
            """
            if len(buffer) < batch_size:
                return 0.0, 0.0

            dataset = BalatroDataset(buffer.examples)
            loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

            total_policy_loss = 0.0
            total_value_loss = 0.0
            num_batches = 0

            for states, probs, outcomes in loader:
                p_loss, v_loss = self.train_batch(states, probs, outcomes)
                total_policy_loss += p_loss
                total_value_loss += v_loss
                num_batches += 1

            return total_policy_loss / num_batches, total_value_loss / num_batches

        def save(self, path: str) -> None:
            """Save model weights."""
            torch.save(self.net.state_dict(), path)

        def load(self, path: str) -> None:
            """Load model weights."""
            self.net.load_state_dict(torch.load(path, weights_only=True))


# =============================================================================
# Neural MCTS Integration
# =============================================================================


class NeuralMCTSPlayer:
    """MCTS player that uses neural network for priors and value estimation."""

    def __init__(
        self,
        net: "BalatroNet | None" = None,
        use_neural_value: bool = True,
        use_neural_policy: bool = True,
        mcts_iterations: int = 100,
        mcts_time_limit: float = 1.0,
    ):
        self.net = net
        self.use_neural_value = use_neural_value and net is not None
        self.use_neural_policy = use_neural_policy and net is not None
        self.mcts_iterations = mcts_iterations
        self.mcts_time_limit = mcts_time_limit

        self.action_encoder = ActionEncoder()

        # Stats
        self.games_played = 0
        self.games_won = 0

    def get_neural_prior(self, game: "GameSimulator") -> np.ndarray | None:
        """Get action probabilities from neural network."""
        if self.net is None or not TORCH_AVAILABLE:
            return None

        self.net.eval()
        with torch.no_grad():
            state = vectorize_state(game)
            x = state.to_tensor().unsqueeze(0)
            probs = self.net.get_policy(x)
            return probs.numpy()[0]

    def get_neural_value(self, game: "GameSimulator") -> float | None:
        """Get state value estimate from neural network."""
        if self.net is None or not TORCH_AVAILABLE:
            return None

        self.net.eval()
        with torch.no_grad():
            state = vectorize_state(game)
            x = state.to_tensor().unsqueeze(0)
            value = self.net.get_value(x)
            return value.item()

    def get_action(self, game: "GameSimulator") -> "MCTSAction | None":
        """Get best action using neural-guided MCTS."""
        from balatro_bot.mcts import MCTS, MCTSConfig

        config = MCTSConfig(
            max_iterations=self.mcts_iterations,
            max_time_seconds=self.mcts_time_limit,
            use_heuristic_rollouts=True,
        )

        mcts = MCTS(config)

        # If using neural value, we could modify rollout evaluation
        # For now, just use standard MCTS with heuristic rollouts
        action = mcts.search(game)

        return action

    def play_game(self, game: "GameSimulator") -> bool:
        """Play a complete game."""
        from balatro_bot.mcts import apply_action
        from balatro_bot.simulator import GamePhase

        self.games_played += 1

        while not game.is_game_over:
            if game.phase == GamePhase.BLIND_SELECT:
                game.start_blind()
            elif game.phase == GamePhase.PLAYING:
                action = self.get_action(game)
                if action:
                    apply_action(game, action)
                else:
                    break
            elif game.phase == GamePhase.SHOP:
                game.end_shop()

        if game.is_won:
            self.games_won += 1
            return True
        return False


# =============================================================================
# Self-Play Training
# =============================================================================


def collect_self_play_data(
    num_games: int = 100,
    mcts_iterations: int = 50,
    net: "BalatroNet | None" = None,
) -> ExperienceBuffer:
    """Collect training data from self-play games.

    Args:
        num_games: Number of games to play
        mcts_iterations: MCTS iterations per move
        net: Optional neural network for guided search

    Returns:
        ExperienceBuffer with collected examples
    """
    from balatro_bot.heuristics import evaluate_plays
    from balatro_bot.mcts import MCTS, MCTSConfig, apply_action
    from balatro_bot.models import GameState
    from balatro_bot.simulator import GamePhase, GameSimulator

    buffer = ExperienceBuffer()
    action_encoder = ActionEncoder()

    config = MCTSConfig(
        max_iterations=mcts_iterations,
        max_time_seconds=0.5,
        use_heuristic_rollouts=True,
    )

    for game_idx in range(num_games):
        game = GameSimulator()
        game.reset(seed=game_idx)

        game_examples: list[tuple[np.ndarray, int, np.ndarray]] = []

        while not game.is_game_over:
            if game.phase == GamePhase.BLIND_SELECT:
                game.start_blind()
                continue

            if game.phase == GamePhase.SHOP:
                game.end_shop()
                continue

            if game.phase != GamePhase.PLAYING:
                break

            # Vectorize current state
            state_vec = vectorize_state(game).to_tensor().numpy()

            # Run MCTS
            mcts = MCTS(config)
            action = mcts.search(game)

            if action is None:
                break

            # Get visit counts as policy target
            visit_counts = np.zeros(action_encoder.total_actions, dtype=np.float32)
            total_visits = sum(c.visits for c in mcts.root.children.values())

            if total_visits > 0:
                # Get heuristic rankings to map actions
                scored_plays = evaluate_plays(
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

                # Map actions to indices based on heuristic ranking
                play_rank_map = {
                    tuple(a.card_indices): i for i, a in enumerate(scored_plays)
                }

                for mcts_action, child in mcts.root.children.items():
                    if mcts_action.kind.name == "PLAY":
                        rank = play_rank_map.get(tuple(mcts_action.card_indices), 0)
                        idx = action_encoder.encode_play(rank)
                    elif mcts_action.kind.name == "DISCARD":
                        idx = action_encoder.encode_discard(0)  # Simplified
                    else:
                        idx = action_encoder.encode_special(mcts_action.kind.name.lower())

                    visit_counts[idx] = child.visits / total_visits

            # Determine action index
            if action.kind.name == "PLAY":
                scored_plays = evaluate_plays(
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
                play_rank_map = {
                    tuple(a.card_indices): i for i, a in enumerate(scored_plays)
                }
                rank = play_rank_map.get(tuple(action.card_indices), 0)
                action_idx = action_encoder.encode_play(rank)
            else:
                action_idx = 0

            game_examples.append((state_vec, action_idx, visit_counts))

            # Apply action
            apply_action(game, action)

        # Compute outcome
        outcome = 1.0 if game.is_won else game.ante / 8.0

        # Add examples to buffer
        for state_vec, action_idx, probs in game_examples:
            buffer.add(
                TrainingExample(
                    state_vector=state_vec,
                    action_idx=action_idx,
                    action_probs=probs,
                    outcome=outcome,
                )
            )

    return buffer


# Type alias for when torch is not available
if not TORCH_AVAILABLE:
    BalatroNet = None
    Trainer = None
    MCTSAction = None
