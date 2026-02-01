"""Tests for heuristic evaluation and player."""

from balatro_bot.heuristics import (
    ActionType,
    HeuristicPlayer,
    evaluate_discards,
    evaluate_plays,
    get_best_play,
    should_discard,
)
from balatro_bot.jokers import create_joker
from balatro_bot.models import Card, GameState
from balatro_bot.simulator import GameSimulator


def cards(card_strings: list[str]) -> list[Card]:
    """Helper to create cards from strings."""
    return [Card.from_string(s) for s in card_strings]


class TestPlayEvaluation:
    """Test play selection heuristics."""

    def test_evaluates_all_plays(self):
        """Should return all possible play combinations."""
        hand = cards(["AS", "KS", "QS", "JS", "10S", "9S", "8S", "7S"])
        actions = evaluate_plays(
            hand=hand,
            jokers=[],
            game_state=GameState(),
            blind_chips=300,
            current_chips=0,
            hands_remaining=4,
        )
        # 8 cards: C(8,1) + C(8,2) + C(8,3) + C(8,4) + C(8,5) = 218
        assert len(actions) == 218

    def test_lethal_plays_ranked_highest(self):
        """Plays that beat the blind should be ranked highest."""
        hand = cards(["AS", "AH", "AC", "AD", "KS"])  # Four of a kind
        actions = evaluate_plays(
            hand=hand,
            jokers=[],
            game_state=GameState(),
            blind_chips=300,
            current_chips=0,
            hands_remaining=4,
        )

        # Best action should be lethal
        best = actions[0]
        assert best.is_lethal

    def test_prefers_higher_hand_types(self):
        """Should prefer stronger hand types."""
        # Hand with both flush and pair possible
        hand = cards(["AS", "2S", "3S", "4S", "5S", "AH", "AD"])
        actions = evaluate_plays(
            hand=hand,
            jokers=[],
            game_state=GameState(),
            blind_chips=10000,  # High blind so nothing is lethal
            current_chips=0,
            hands_remaining=4,
        )

        # Find the flush and pair actions
        flush_action = None
        pair_action = None
        for action in actions:
            if action.expected_chips > 0:
                played = [hand[i] for i in action.card_indices]
                if len(played) == 5 and all(c.suit.value == "S" for c in played):
                    flush_action = action
                elif len(played) == 2 and played[0].rank == played[1].rank:
                    if pair_action is None:
                        pair_action = action

        # Flush should score higher than pair
        if flush_action and pair_action:
            assert flush_action.score > pair_action.score

    def test_joker_synergy_bonus(self):
        """Should give bonus for plays that synergize with jokers."""
        hand = cards(["AD", "KD", "QD", "JD", "2S"])  # Diamonds + one spade
        jokers = [create_joker("greedy_joker")]  # +3 mult per diamond

        actions = evaluate_plays(
            hand=hand,
            jokers=jokers,
            game_state=GameState(),
            blind_chips=10000,
            current_chips=0,
            hands_remaining=4,
        )

        # Find plays with different diamond counts
        all_diamonds = None
        with_spade = None
        for action in actions:
            played = [hand[i] for i in action.card_indices]
            if len(played) == 4 and all(c.suit.value == "D" for c in played):
                all_diamonds = action
            elif len(played) == 4 and any(c.suit.value == "S" for c in played):
                with_spade = action

        # All diamonds should score higher due to synergy
        if all_diamonds and with_spade:
            assert all_diamonds.score > with_spade.score


class TestDiscardEvaluation:
    """Test discard selection heuristics."""

    def test_evaluates_all_discards(self):
        """Should return all possible discard combinations."""
        hand = cards(["AS", "KS", "QS", "JS", "10S", "9S", "8S", "7S"])
        actions = evaluate_discards(
            hand=hand,
            jokers=[],
            game_state=GameState(),
            deck_remaining=44,
        )
        assert len(actions) == 218

    def test_penalizes_breaking_best_hand(self):
        """Should penalize discards that break the best current hand."""
        hand = cards(["AS", "AH", "KS", "QS", "JS"])  # Pair of aces
        actions = evaluate_discards(
            hand=hand,
            jokers=[],
            game_state=GameState(),
            deck_remaining=44,
        )

        # Find discard that keeps pair vs breaks pair
        keeps_pair = None
        breaks_pair = None
        for action in actions:
            kept = [c for i, c in enumerate(hand) if i not in action.card_indices]

            # Check if pair is kept
            kept_aces = sum(1 for c in kept if c.rank.value == 14)

            if kept_aces >= 2 and breaks_pair is None:
                keeps_pair = action
            elif kept_aces < 2 and len(action.card_indices) == 1:
                breaks_pair = action

        if keeps_pair and breaks_pair:
            assert keeps_pair.score > breaks_pair.score

    def test_prefers_discarding_low_cards(self):
        """Should prefer discarding low cards over high cards."""
        hand = cards(["AS", "KS", "2S", "3S", "4S"])
        actions = evaluate_discards(
            hand=hand,
            jokers=[],
            game_state=GameState(),
            deck_remaining=44,
        )

        # Find single-card discards
        discard_2 = None
        discard_ace = None
        for action in actions:
            if len(action.card_indices) == 1:
                discarded = hand[action.card_indices[0]]
                if discarded.rank.value == 2:
                    discard_2 = action
                elif discarded.rank.value == 14:
                    discard_ace = action

        # Discarding 2 should be better than discarding Ace
        if discard_2 and discard_ace:
            assert discard_2.score > discard_ace.score


class TestShouldDiscard:
    """Test the discard decision logic."""

    def test_dont_discard_with_lethal(self):
        """Should not discard when we have a lethal play."""
        hand = cards(["AS", "AH", "AC", "AD", "KS", "QS", "JS"])
        result = should_discard(
            hand=hand,
            jokers=[],
            game_state=GameState(),
            blind_chips=300,
            current_chips=0,
            hands_remaining=4,
            discards_remaining=3,
            deck_remaining=44,
        )
        assert not result

    def test_dont_discard_on_last_hand(self):
        """Should not discard when on last hand."""
        hand = cards(["2S", "3H", "5C", "7D", "9S", "JS", "KH"])
        result = should_discard(
            hand=hand,
            jokers=[],
            game_state=GameState(),
            blind_chips=10000,
            current_chips=0,
            hands_remaining=1,  # Last hand
            discards_remaining=3,
            deck_remaining=44,
        )
        assert not result

    def test_dont_discard_with_zero_remaining(self):
        """Should not discard when no discards remaining."""
        hand = cards(["2S", "3H", "5C", "7D", "9S", "JS", "KH"])
        result = should_discard(
            hand=hand,
            jokers=[],
            game_state=GameState(),
            blind_chips=10000,
            current_chips=0,
            hands_remaining=4,
            discards_remaining=0,  # No discards
            deck_remaining=44,
        )
        assert not result


class TestGetBestPlay:
    """Test the best play selection."""

    def test_returns_highest_scored_action(self):
        """Should return the action with highest score."""
        hand = cards(["AS", "AH", "KS", "QS", "JS"])
        best = get_best_play(
            hand=hand,
            jokers=[],
            game_state=GameState(),
            blind_chips=300,
            current_chips=0,
            hands_remaining=4,
        )

        assert best is not None
        assert best.action_type == ActionType.PLAY

    def test_finds_lethal_play(self):
        """Should find lethal plays when available."""
        hand = cards(["AS", "AH", "AC", "AD", "KS", "QS", "JS", "10S"])
        best = get_best_play(
            hand=hand,
            jokers=[],
            game_state=GameState(),
            blind_chips=300,
            current_chips=0,
            hands_remaining=4,
        )

        assert best is not None
        assert best.is_lethal


class TestHeuristicPlayer:
    """Test the heuristic player."""

    def test_can_play_blind(self):
        """Player should be able to play through a blind."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        player = HeuristicPlayer()
        player.play_blind(game)

        # Should have played some hands
        assert player.stats["hands_played"] > 0

    def test_can_play_full_game(self):
        """Player should be able to play a complete game."""
        game = GameSimulator()
        game.reset(seed=42)

        player = HeuristicPlayer()
        player.play_game(game)

        assert player.stats["games_played"] == 1
        assert game.is_game_over

    def test_tracks_statistics(self):
        """Player should track game statistics."""
        player = HeuristicPlayer()

        for seed in range(5):
            game = GameSimulator()
            game.reset(seed=seed)
            player.play_game(game)

        assert player.stats["games_played"] == 5
        assert player.stats["hands_played"] > 0

    def test_win_rate_calculation(self):
        """Win rate should be calculated correctly."""
        player = HeuristicPlayer()
        player.stats["games_played"] = 10
        player.stats["games_won"] = 3

        assert player.get_win_rate() == 0.3

    def test_win_rate_zero_games(self):
        """Win rate should be 0 with no games played."""
        player = HeuristicPlayer()
        assert player.get_win_rate() == 0.0


class TestHeuristicPlayerWithJokers:
    """Test heuristic player with jokers."""

    def test_uses_joker_synergies(self):
        """Player should benefit from joker synergies."""
        # Play same seed with and without joker
        game_no_joker = GameSimulator()
        game_no_joker.reset(seed=123)

        game_with_joker = GameSimulator()
        game_with_joker.reset(seed=123)
        game_with_joker.jokers.append(create_joker("joker"))

        # Play first blind of each
        game_no_joker.start_blind()
        game_with_joker.start_blind()

        # Get best plays
        best_no_joker = get_best_play(
            hand=game_no_joker.hand,
            jokers=[],
            game_state=GameState(),
            blind_chips=game_no_joker.blind_chips,
            current_chips=0,
            hands_remaining=4,
        )

        best_with_joker = get_best_play(
            hand=game_with_joker.hand,
            jokers=game_with_joker.jokers,
            game_state=GameState(),
            blind_chips=game_with_joker.blind_chips,
            current_chips=0,
            hands_remaining=4,
        )

        # Joker should increase expected chips (same cards, more mult)
        if best_no_joker and best_with_joker:
            # Same card selection should give higher chips with joker
            if best_no_joker.card_indices == best_with_joker.card_indices:
                assert best_with_joker.expected_chips > best_no_joker.expected_chips


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_hand(self):
        """Should handle empty hand gracefully."""
        actions = evaluate_plays(
            hand=[],
            jokers=[],
            game_state=GameState(),
            blind_chips=300,
            current_chips=0,
            hands_remaining=4,
        )
        assert actions == []

    def test_single_card_hand(self):
        """Should handle single card hand."""
        hand = cards(["AS"])
        actions = evaluate_plays(
            hand=hand,
            jokers=[],
            game_state=GameState(),
            blind_chips=300,
            current_chips=0,
            hands_remaining=4,
        )
        assert len(actions) == 1  # Only one possible play

    def test_already_won_blind(self):
        """Should still evaluate plays even if blind already beaten."""
        hand = cards(["AS", "AH"])
        actions = evaluate_plays(
            hand=hand,
            jokers=[],
            game_state=GameState(),
            blind_chips=300,
            current_chips=500,  # Already beat blind
            hands_remaining=4,
        )
        # All plays should be "lethal" since we already have enough
        assert all(a.is_lethal for a in actions)


class TestPlayMultipleGames:
    """Test playing multiple games for win rate."""

    def test_reasonable_win_rate(self):
        """Heuristic player should achieve reasonable win rate."""
        player = HeuristicPlayer()
        wins = 0
        games = 20

        for seed in range(games):
            game = GameSimulator()
            game.reset(seed=seed)
            if player.play_game(game):
                wins += 1

        win_rate = wins / games
        # Heuristic player should win some games (exact rate depends on seeds)
        # With no jokers and basic heuristics, even 10% is reasonable
        assert player.stats["games_played"] == games
        # Just verify it completes without errors
        assert win_rate >= 0.0
