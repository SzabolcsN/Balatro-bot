"""Tests for neural network components."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from balatro_bot.neural import (
    TORCH_AVAILABLE,
    ActionEncoder,
    ExperienceBuffer,
    JOKER_ID_MAP,
    MAX_JOKERS,
    NUM_JOKER_TYPES,
    StateVector,
    TrainingExample,
    card_to_index,
    vectorize_state,
)
from balatro_bot.jokers import create_joker
from balatro_bot.simulator import GameSimulator


class TestCardToIndex:
    """Test card index encoding."""

    def test_card_indices_unique(self):
        """Each card should have a unique index."""
        indices = set()
        ranks = list(range(2, 15))  # 2-A
        suits = ["S", "H", "C", "D"]

        for suit in suits:
            for rank in ranks:
                idx = card_to_index(rank, suit)
                assert idx not in indices
                indices.add(idx)

        assert len(indices) == 52

    def test_card_index_range(self):
        """Indices should be 0-51."""
        ranks = list(range(2, 15))
        suits = ["S", "H", "C", "D"]

        for suit in suits:
            for rank in ranks:
                idx = card_to_index(rank, suit)
                assert 0 <= idx < 52

    def test_specific_cards(self):
        """Test specific card encodings."""
        # 2 of Spades should be index 0
        assert card_to_index(2, "S") == 0
        # Ace of Spades (rank 14) should be index 12
        assert card_to_index(14, "S") == 12
        # 2 of Hearts should be index 13
        assert card_to_index(2, "H") == 13


class TestStateVector:
    """Test state vector creation."""

    def test_input_size(self):
        """Input size should be 843 (with 150 joker types)."""
        assert StateVector.input_size() == 843

    def test_vectorize_basic_state(self):
        """Should vectorize a basic game state."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        state = vectorize_state(game)

        # Check dimensions
        assert state.hand_cards.shape == (52,)
        assert state.joker_ids.shape == (MAX_JOKERS, NUM_JOKER_TYPES)
        assert state.joker_states.shape == (MAX_JOKERS, 4)
        assert state.blind_type.shape == (3,)
        assert state.hand_levels.shape == (13,)

    def test_hand_cards_encoding(self):
        """Hand cards should be encoded as binary vector."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        state = vectorize_state(game)

        # Should have exactly 8 cards in hand
        assert state.hand_cards.sum() == 8

        # Values should be 0 or 1
        assert all(v in (0, 1) for v in state.hand_cards)

    def test_joker_encoding(self):
        """Jokers should be one-hot encoded."""
        game = GameSimulator()
        game.reset(seed=42)
        game.jokers.append(create_joker("joker"))
        game.start_blind()

        state = vectorize_state(game)

        # First joker slot should have one-hot encoding
        assert state.joker_ids[0].sum() == 1
        assert state.joker_ids[0, JOKER_ID_MAP["joker"]] == 1

        # Other slots should be empty
        assert state.joker_ids[1:].sum() == 0

    def test_blind_type_one_hot(self):
        """Blind type should be one-hot encoded."""
        game = GameSimulator()
        game.reset(seed=42)

        state = vectorize_state(game)

        # Should be exactly one-hot
        assert state.blind_type.sum() == 1
        assert state.blind_type[0] == 1  # Small blind

    def test_normalized_values(self):
        """Scalar values should be normalized."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        state = vectorize_state(game)

        # Ante normalized by 8
        assert 0 <= state.ante <= 1
        # Chips progress capped at 1
        assert 0 <= state.chips_progress <= 1
        # Money normalized
        assert 0 <= state.money <= 1


class TestStateVectorTensor:
    """Test state vector to tensor conversion."""

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_to_tensor_shape(self):
        """Tensor should have correct shape."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        state = vectorize_state(game)
        tensor = state.to_tensor()

        assert tensor.shape == (243,)

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_to_tensor_dtype(self):
        """Tensor should be float32."""
        import torch

        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        state = vectorize_state(game)
        tensor = state.to_tensor()

        assert tensor.dtype == torch.float32

    def test_to_tensor_without_torch(self):
        """Should raise error if torch not available."""
        if TORCH_AVAILABLE:
            pytest.skip("PyTorch is available")

        state = StateVector(
            hand_cards=np.zeros(52),
            joker_ids=np.zeros((5, 30)),
            joker_states=np.zeros((5, 4)),
            ante=0.0,
            blind_type=np.zeros(3),
            chips_progress=0.0,
            money=0.0,
            hands_remaining=1.0,
            discards_remaining=1.0,
            hand_levels=np.zeros(13),
        )

        with pytest.raises(RuntimeError):
            state.to_tensor()


class TestActionEncoder:
    """Test action encoding."""

    def test_total_actions(self):
        """Total actions should be sum of all action types."""
        encoder = ActionEncoder()
        expected = encoder.num_play_actions + encoder.num_discard_actions + encoder.num_special_actions
        assert encoder.total_actions == expected

    def test_default_total_actions(self):
        """Default should be 73 actions."""
        encoder = ActionEncoder()
        assert encoder.total_actions == 73  # 50 + 20 + 3

    def test_encode_play_in_range(self):
        """Play action indices should be in first section."""
        encoder = ActionEncoder()

        for rank in range(100):  # Test more than max
            idx = encoder.encode_play(rank)
            assert 0 <= idx < encoder.num_play_actions

    def test_encode_discard_in_range(self):
        """Discard action indices should be in middle section."""
        encoder = ActionEncoder()

        for rank in range(50):
            idx = encoder.encode_discard(rank)
            assert encoder.num_play_actions <= idx < encoder.num_play_actions + encoder.num_discard_actions

    def test_encode_special_in_range(self):
        """Special action indices should be in last section."""
        encoder = ActionEncoder()

        for action_type in ["start_blind", "skip_blind", "end_shop"]:
            idx = encoder.encode_special(action_type)
            assert idx >= encoder.num_play_actions + encoder.num_discard_actions

    def test_is_play_action(self):
        """Should correctly identify play actions."""
        encoder = ActionEncoder()

        assert encoder.is_play_action(0)
        assert encoder.is_play_action(49)
        assert not encoder.is_play_action(50)
        assert not encoder.is_play_action(70)

    def test_is_discard_action(self):
        """Should correctly identify discard actions."""
        encoder = ActionEncoder()

        assert not encoder.is_discard_action(0)
        assert encoder.is_discard_action(50)
        assert encoder.is_discard_action(69)
        assert not encoder.is_discard_action(70)

    def test_is_special_action(self):
        """Should correctly identify special actions."""
        encoder = ActionEncoder()

        assert not encoder.is_special_action(0)
        assert not encoder.is_special_action(50)
        assert encoder.is_special_action(70)
        assert encoder.is_special_action(72)


class TestExperienceBuffer:
    """Test experience buffer."""

    def test_add_example(self):
        """Should add examples to buffer."""
        buffer = ExperienceBuffer()

        example = TrainingExample(
            state_vector=np.zeros(243, dtype=np.float32),
            action_idx=0,
            action_probs=np.zeros(73, dtype=np.float32),
            outcome=1.0,
        )

        buffer.add(example)
        assert len(buffer) == 1

    def test_max_size_limit(self):
        """Should respect max size limit."""
        buffer = ExperienceBuffer(max_size=10)

        for i in range(20):
            example = TrainingExample(
                state_vector=np.ones(243, dtype=np.float32) * i,
                action_idx=i % 73,
                action_probs=np.zeros(73, dtype=np.float32),
                outcome=float(i),
            )
            buffer.add(example)

        assert len(buffer) == 10
        # Should have the most recent examples
        assert buffer.examples[-1].outcome == 19.0

    def test_sample_batch(self):
        """Should sample batch from buffer."""
        buffer = ExperienceBuffer()

        for i in range(100):
            example = TrainingExample(
                state_vector=np.zeros(243, dtype=np.float32),
                action_idx=i % 73,
                action_probs=np.zeros(73, dtype=np.float32),
                outcome=float(i),
            )
            buffer.add(example)

        batch = buffer.sample(32)
        assert len(batch) == 32

    def test_sample_small_buffer(self):
        """Should return all examples if buffer smaller than batch."""
        buffer = ExperienceBuffer()

        for i in range(10):
            example = TrainingExample(
                state_vector=np.zeros(243, dtype=np.float32),
                action_idx=i,
                action_probs=np.zeros(73, dtype=np.float32),
                outcome=float(i),
            )
            buffer.add(example)

        batch = buffer.sample(32)
        assert len(batch) == 10

    def test_save_and_load(self):
        """Should save and load buffer."""
        buffer = ExperienceBuffer()

        for i in range(5):
            example = TrainingExample(
                state_vector=np.ones(243, dtype=np.float32) * i,
                action_idx=i,
                action_probs=np.ones(73, dtype=np.float32) / 73,
                outcome=float(i) / 5,
            )
            buffer.add(example)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        try:
            buffer.save(path)

            # Verify file exists and is valid JSON
            data = json.loads(Path(path).read_text())
            assert "examples" in data
            assert len(data["examples"]) == 5

            # Load into new buffer
            new_buffer = ExperienceBuffer()
            new_buffer.load(path)

            assert len(new_buffer) == 5
            # Check first example
            assert new_buffer.examples[0].action_idx == 0
            assert abs(new_buffer.examples[0].outcome - 0.0) < 0.01
            np.testing.assert_array_almost_equal(
                new_buffer.examples[0].state_vector,
                np.zeros(243, dtype=np.float32),
            )
        finally:
            Path(path).unlink()


class TestTrainingExample:
    """Test training example."""

    def test_create_example(self):
        """Should create training example."""
        example = TrainingExample(
            state_vector=np.zeros(243, dtype=np.float32),
            action_idx=5,
            action_probs=np.zeros(73, dtype=np.float32),
            outcome=0.5,
        )

        assert example.action_idx == 5
        assert example.outcome == 0.5


@pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
class TestBalatroNet:
    """Test neural network architecture."""

    def test_create_network(self):
        """Should create network with default parameters."""
        from balatro_bot.neural import BalatroNet

        net = BalatroNet()

        assert net.input_size == 843
        assert net.hidden_size == 256
        assert net.num_actions == 73

    def test_forward_pass(self):
        """Should perform forward pass."""
        import torch
        from balatro_bot.neural import BalatroNet

        net = BalatroNet()

        # Create batch of inputs
        x = torch.randn(4, 843)
        policy_logits, value = net.forward(x)

        assert policy_logits.shape == (4, 73)
        assert value.shape == (4, 1)

    def test_policy_output(self):
        """Policy should output probabilities summing to 1."""
        import torch
        from balatro_bot.neural import BalatroNet

        net = BalatroNet()

        x = torch.randn(4, 243)
        probs = net.get_policy(x)

        # Should sum to 1
        sums = probs.sum(dim=1)
        torch.testing.assert_close(sums, torch.ones(4))

    def test_value_output_range(self):
        """Value should be in [-1, 1] due to tanh."""
        import torch
        from balatro_bot.neural import BalatroNet

        net = BalatroNet()

        x = torch.randn(100, 243)  # Large batch
        value = net.get_value(x)

        assert (value >= -1).all()
        assert (value <= 1).all()

    def test_custom_sizes(self):
        """Should support custom sizes."""
        from balatro_bot.neural import BalatroNet

        net = BalatroNet(input_size=128, hidden_size=64, num_actions=50)

        assert net.input_size == 128
        assert net.hidden_size == 64
        assert net.num_actions == 50


@pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
class TestTrainer:
    """Test training loop."""

    def test_create_trainer(self):
        """Should create trainer."""
        from balatro_bot.neural import BalatroNet, Trainer

        net = BalatroNet()
        trainer = Trainer(net)

        assert trainer.net is net
        assert trainer.train_steps == 0

    def test_train_batch(self):
        """Should train on a batch."""
        import torch
        from balatro_bot.neural import BalatroNet, Trainer

        net = BalatroNet()
        trainer = Trainer(net)

        # Create batch
        states = torch.randn(8, 243)
        target_probs = torch.softmax(torch.randn(8, 73), dim=-1)
        target_values = torch.randn(8, 1)

        policy_loss, value_loss = trainer.train_batch(states, target_probs, target_values)

        assert policy_loss > 0
        assert value_loss >= 0
        assert trainer.train_steps == 1

    def test_train_epoch(self):
        """Should train for one epoch."""
        from balatro_bot.neural import BalatroNet, Trainer

        net = BalatroNet()
        trainer = Trainer(net)

        # Create buffer with examples
        buffer = ExperienceBuffer()
        for i in range(100):
            example = TrainingExample(
                state_vector=np.random.randn(243).astype(np.float32),
                action_idx=i % 73,
                action_probs=np.ones(73, dtype=np.float32) / 73,
                outcome=np.random.rand(),
            )
            buffer.add(example)

        avg_policy_loss, avg_value_loss = trainer.train_epoch(buffer, batch_size=16)

        assert avg_policy_loss > 0
        assert avg_value_loss >= 0
        assert trainer.train_steps > 0

    def test_save_and_load(self):
        """Should save and load model weights."""
        import tempfile
        import torch
        from balatro_bot.neural import BalatroNet, Trainer

        net = BalatroNet()
        trainer = Trainer(net)

        # Get initial output
        x = torch.randn(1, 243)
        initial_policy, _ = net.forward(x)

        # Train a bit
        states = torch.randn(8, 243)
        target_probs = torch.softmax(torch.randn(8, 73), dim=-1)
        target_values = torch.randn(8, 1)
        trainer.train_batch(states, target_probs, target_values)

        # Save
        with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as f:
            path = f.name

        try:
            trainer.save(path)

            # Create new network and load
            new_net = BalatroNet()
            new_trainer = Trainer(new_net)
            new_trainer.load(path)

            # Output should match
            new_policy, _ = new_net.forward(x)
            torch.testing.assert_close(net.forward(x)[0], new_policy)
        finally:
            Path(path).unlink()


@pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
class TestNeuralMCTSPlayer:
    """Test neural MCTS player."""

    def test_create_player_without_net(self):
        """Should create player without network."""
        from balatro_bot.neural import NeuralMCTSPlayer

        player = NeuralMCTSPlayer()

        assert player.net is None
        assert not player.use_neural_value
        assert not player.use_neural_policy

    def test_create_player_with_net(self):
        """Should create player with network."""
        from balatro_bot.neural import BalatroNet, NeuralMCTSPlayer

        net = BalatroNet()
        player = NeuralMCTSPlayer(net)

        assert player.net is net
        assert player.use_neural_value
        assert player.use_neural_policy

    def test_get_action(self):
        """Should get action from game state."""
        from balatro_bot.neural import NeuralMCTSPlayer

        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        player = NeuralMCTSPlayer(mcts_iterations=10, mcts_time_limit=0.5)
        action = player.get_action(game)

        assert action is not None

    def test_play_game(self):
        """Should play a complete game."""
        from balatro_bot.neural import NeuralMCTSPlayer

        game = GameSimulator()
        game.reset(seed=42)

        player = NeuralMCTSPlayer(mcts_iterations=5, mcts_time_limit=0.2)
        player.play_game(game)

        assert game.is_game_over
        assert player.games_played == 1


class TestJokerIdMap:
    """Test joker ID mapping."""

    def test_all_jokers_mapped(self):
        """All jokers should have unique IDs."""
        ids = set(JOKER_ID_MAP.values())
        assert len(ids) == len(JOKER_ID_MAP)

    def test_ids_in_range(self):
        """All IDs should be in valid range."""
        for joker_id in JOKER_ID_MAP.values():
            assert 0 <= joker_id < NUM_JOKER_TYPES

    def test_common_jokers_present(self):
        """Common jokers should be in the map."""
        assert "joker" in JOKER_ID_MAP
        assert "greedy_joker" in JOKER_ID_MAP
        assert "half_joker" in JOKER_ID_MAP
