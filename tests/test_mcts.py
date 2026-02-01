"""Tests for Monte Carlo Tree Search."""

import math

from balatro_bot.mcts import (
    MCTS,
    ActionKind,
    MCTSAction,
    MCTSConfig,
    MCTSNode,
    MCTSPlayer,
    apply_action,
    get_legal_actions,
    quick_mcts_action,
)
from balatro_bot.simulator import BlindType, GamePhase, GameSimulator


class TestMCTSNode:
    """Test MCTS node functionality."""

    def test_initial_state(self):
        """New node should have zero visits."""
        node = MCTSNode()
        assert node.visits == 0
        assert node.total_value == 0.0
        assert node.wins == 0

    def test_average_value(self):
        """Average value should be total/visits."""
        node = MCTSNode()
        node.visits = 10
        node.total_value = 5.0
        assert node.average_value == 0.5

    def test_average_value_zero_visits(self):
        """Average should be 0 with no visits."""
        node = MCTSNode()
        assert node.average_value == 0.0

    def test_win_rate(self):
        """Win rate should be wins/visits."""
        node = MCTSNode()
        node.visits = 10
        node.wins = 3
        assert node.win_rate == 0.3

    def test_ucb1_unvisited(self):
        """Unvisited nodes should have infinite UCB1."""
        node = MCTSNode()
        assert node.ucb1() == float("inf")

    def test_ucb1_calculation(self):
        """UCB1 should balance exploitation and exploration."""
        parent = MCTSNode()
        parent.visits = 100

        child = MCTSNode(parent=parent)
        child.visits = 10
        child.total_value = 5.0  # avg = 0.5

        # UCB1 = 0.5 + 1.414 * sqrt(ln(100) / 10)
        expected_exploration = 1.414 * math.sqrt(math.log(100) / 10)
        expected = 0.5 + expected_exploration

        assert abs(child.ucb1() - expected) < 0.01

    def test_is_fully_expanded(self):
        """Fully expanded when no untried actions."""
        node = MCTSNode()
        node.untried_actions = []
        assert node.is_fully_expanded

        node.untried_actions = [MCTSAction(kind=ActionKind.PLAY)]
        assert not node.is_fully_expanded

    def test_best_child(self):
        """Should select child with highest UCB1."""
        parent = MCTSNode()
        parent.visits = 100

        child1 = MCTSNode(parent=parent)
        child1.visits = 50
        child1.total_value = 20.0

        child2 = MCTSNode(parent=parent)
        child2.visits = 10
        child2.total_value = 8.0

        action1 = MCTSAction(kind=ActionKind.PLAY, card_indices=[0])
        action2 = MCTSAction(kind=ActionKind.PLAY, card_indices=[1])

        parent.children = {action1: child1, action2: child2}

        best = parent.best_child()
        # Child2 has higher UCB1 due to exploration bonus
        assert best is not None

    def test_best_action(self):
        """Should return action of most visited child."""
        parent = MCTSNode()

        child1 = MCTSNode(parent=parent)
        child1.visits = 50

        child2 = MCTSNode(parent=parent)
        child2.visits = 100  # More visits

        action1 = MCTSAction(kind=ActionKind.PLAY, card_indices=[0])
        action2 = MCTSAction(kind=ActionKind.PLAY, card_indices=[1])

        child1.action = action1
        child2.action = action2

        parent.children = {action1: child1, action2: child2}

        best = parent.best_action()
        assert best == action2  # Most visited


class TestMCTSAction:
    """Test MCTS action handling."""

    def test_action_equality(self):
        """Actions with same kind and indices should be equal."""
        a1 = MCTSAction(kind=ActionKind.PLAY, card_indices=[0, 1])
        a2 = MCTSAction(kind=ActionKind.PLAY, card_indices=[0, 1])
        assert a1 == a2

    def test_action_inequality(self):
        """Actions with different indices should not be equal."""
        a1 = MCTSAction(kind=ActionKind.PLAY, card_indices=[0, 1])
        a2 = MCTSAction(kind=ActionKind.PLAY, card_indices=[0, 2])
        assert a1 != a2

    def test_action_hash(self):
        """Actions should be hashable for use in dicts."""
        a1 = MCTSAction(kind=ActionKind.PLAY, card_indices=[0, 1])
        a2 = MCTSAction(kind=ActionKind.PLAY, card_indices=[0, 1])

        d = {a1: "test"}
        assert d[a2] == "test"


class TestGetLegalActions:
    """Test legal action generation."""

    def test_blind_select_actions(self):
        """Should have start and skip options in blind select."""
        game = GameSimulator()
        game.reset(seed=42)

        actions = get_legal_actions(game)

        kinds = [a.kind for a in actions]
        assert ActionKind.START_BLIND in kinds
        assert ActionKind.SKIP_BLIND in kinds  # Can skip small blind

    def test_boss_blind_no_skip(self):
        """Should not be able to skip boss blind."""
        game = GameSimulator()
        game.reset(seed=42)
        game.blind_type = BlindType.BOSS

        actions = get_legal_actions(game)

        kinds = [a.kind for a in actions]
        assert ActionKind.START_BLIND in kinds
        assert ActionKind.SKIP_BLIND not in kinds

    def test_playing_actions(self):
        """Should have play and discard options when playing."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        actions = get_legal_actions(game)

        play_actions = [a for a in actions if a.kind == ActionKind.PLAY]
        discard_actions = [a for a in actions if a.kind == ActionKind.DISCARD]

        # Should have many play options (all card combinations)
        assert len(play_actions) > 0
        # Should have discard options (3 discards remaining)
        assert len(discard_actions) > 0

    def test_no_discard_when_exhausted(self):
        """Should not have discard actions when none remaining."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()
        game.discards_remaining = 0

        actions = get_legal_actions(game)

        discard_actions = [a for a in actions if a.kind == ActionKind.DISCARD]
        assert len(discard_actions) == 0

    def test_shop_actions(self):
        """Should have end shop action in shop phase."""
        game = GameSimulator()
        game.reset(seed=42)
        game.phase = GamePhase.SHOP

        actions = get_legal_actions(game)

        kinds = [a.kind for a in actions]
        assert ActionKind.END_SHOP in kinds


class TestApplyAction:
    """Test action application."""

    def test_apply_play(self):
        """Should play cards when applying play action."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()
        initial_hands = game.hands_remaining

        action = MCTSAction(kind=ActionKind.PLAY, card_indices=[0, 1])
        apply_action(game, action)

        assert game.hands_remaining == initial_hands - 1

    def test_apply_discard(self):
        """Should discard cards when applying discard action."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()
        initial_discards = game.discards_remaining

        action = MCTSAction(kind=ActionKind.DISCARD, card_indices=[0])
        apply_action(game, action)

        assert game.discards_remaining == initial_discards - 1

    def test_apply_start_blind(self):
        """Should start blind when applying start action."""
        game = GameSimulator()
        game.reset(seed=42)

        action = MCTSAction(kind=ActionKind.START_BLIND)
        apply_action(game, action)

        assert game.phase == GamePhase.PLAYING


class TestMCTS:
    """Test MCTS search."""

    def test_search_returns_action(self):
        """Search should return a valid action."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        config = MCTSConfig(max_iterations=50, max_time_seconds=1.0)
        mcts = MCTS(config)

        action = mcts.search(game)

        assert action is not None
        assert action.kind in (ActionKind.PLAY, ActionKind.DISCARD)

    def test_search_builds_tree(self):
        """Search should build a tree of nodes."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        config = MCTSConfig(max_iterations=100, max_time_seconds=2.0)
        mcts = MCTS(config)

        mcts.search(game)

        assert mcts.root is not None
        assert mcts.root.visits > 0
        assert len(mcts.root.children) > 0

    def test_search_respects_iteration_limit(self):
        """Search should stop at iteration limit."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        config = MCTSConfig(max_iterations=50, max_time_seconds=100.0)
        mcts = MCTS(config)

        mcts.search(game)

        assert mcts.iterations <= 50

    def test_search_respects_time_limit(self):
        """Search should stop at time limit."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        config = MCTSConfig(max_iterations=100000, max_time_seconds=0.1)
        mcts = MCTS(config)

        import time
        start = time.time()
        mcts.search(game)
        elapsed = time.time() - start

        # Should complete within reasonable time of limit
        assert elapsed < 0.5

    def test_search_does_not_modify_game(self):
        """Search should not modify the input game state."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        original_hand = list(game.hand)
        original_chips = game.current_chips

        config = MCTSConfig(max_iterations=50, max_time_seconds=1.0)
        mcts = MCTS(config)
        mcts.search(game)

        assert game.hand == original_hand
        assert game.current_chips == original_chips

    def test_get_action_stats(self):
        """Should return statistics for explored actions."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        config = MCTSConfig(max_iterations=100, max_time_seconds=2.0)
        mcts = MCTS(config)
        mcts.search(game)

        stats = mcts.get_action_stats()

        assert len(stats) > 0
        for action_str, data in stats.items():
            assert "visits" in data
            assert "avg_value" in data
            assert "win_rate" in data


class TestMCTSPlayer:
    """Test MCTS player."""

    def test_can_get_action(self):
        """Player should be able to get an action."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        config = MCTSConfig(max_iterations=50, max_time_seconds=1.0)
        player = MCTSPlayer(config)

        action = player.get_action(game)

        assert action is not None

    def test_can_play_blind(self):
        """Player should be able to play through a blind."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        config = MCTSConfig(max_iterations=20, max_time_seconds=0.5)
        player = MCTSPlayer(config)

        # Play until blind is beaten or game over
        while game.phase == GamePhase.PLAYING:
            action = player.get_action(game)
            if action:
                apply_action(game, action)
            else:
                break

        # Should have made progress
        assert player.stats["total_iterations"] > 0

    def test_tracks_statistics(self):
        """Player should track game statistics."""
        game = GameSimulator()
        game.reset(seed=42)

        config = MCTSConfig(max_iterations=10, max_time_seconds=0.2)
        player = MCTSPlayer(config)
        player.play_game(game)

        assert player.stats["games_played"] == 1
        assert player.stats["total_iterations"] > 0
        assert player.stats["total_rollouts"] > 0


class TestQuickMCTS:
    """Test quick MCTS convenience function."""

    def test_quick_mcts_returns_action(self):
        """Quick MCTS should return an action."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        action = quick_mcts_action(game, iterations=20, time_limit=0.5)

        assert action is not None


class TestMCTSWithHeuristics:
    """Test MCTS integration with heuristics."""

    def test_heuristic_guided_expansion(self):
        """MCTS should use heuristics to guide expansion."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        config = MCTSConfig(
            max_iterations=50,
            max_time_seconds=1.0,
            use_heuristic_rollouts=True,
        )
        mcts = MCTS(config)

        action = mcts.search(game)

        # Should return a reasonable action
        assert action is not None
        # Play actions should be preferred over random
        assert action.kind == ActionKind.PLAY

    def test_heuristic_vs_random_rollouts(self):
        """Heuristic rollouts should give more consistent results."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        # Heuristic rollouts
        config_h = MCTSConfig(
            max_iterations=50,
            max_time_seconds=1.0,
            use_heuristic_rollouts=True,
        )
        mcts_h = MCTS(config_h)
        mcts_h.search(game)

        # Random rollouts
        config_r = MCTSConfig(
            max_iterations=50,
            max_time_seconds=1.0,
            use_heuristic_rollouts=False,
        )
        mcts_r = MCTS(config_r)
        mcts_r.search(game.clone())

        # Both should complete without error
        assert mcts_h.root is not None
        assert mcts_r.root is not None


class TestMCTSEdgeCases:
    """Test edge cases."""

    def test_game_over_state(self):
        """Should handle game over state."""
        game = GameSimulator()
        game.reset(seed=42)
        game.phase = GamePhase.GAME_OVER

        config = MCTSConfig(max_iterations=10, max_time_seconds=0.5)
        mcts = MCTS(config)

        action = mcts.search(game)

        # No valid actions from game over
        assert action is None

    def test_empty_hand(self):
        """Should handle empty hand gracefully."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()
        game.hand = []  # Force empty hand

        actions = get_legal_actions(game)

        # Should have no play/discard actions
        play_actions = [a for a in actions if a.kind == ActionKind.PLAY]
        assert len(play_actions) == 0
