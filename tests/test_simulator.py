"""Tests for the game simulator."""

from balatro_bot.jokers import create_joker
from balatro_bot.models import Rank
from balatro_bot.simulator import BlindType, GamePhase, GameSimulator


class TestGameInitialization:
    """Test game initialization and reset."""

    def test_new_game_has_standard_deck(self):
        """New game should have 52-card deck."""
        game = GameSimulator()
        game.reset(seed=42)
        assert len(game.deck) == 52
        assert len(game.hand) == 0

    def test_reset_with_seed_is_deterministic(self):
        """Same seed should produce same initial state."""
        game1 = GameSimulator()
        game1.reset(seed=42)

        game2 = GameSimulator()
        game2.reset(seed=42)

        assert game1.deck == game2.deck

    def test_initial_state(self):
        """Check initial game state values."""
        game = GameSimulator()
        game.reset(seed=42)

        assert game.money == 4
        assert game.ante == 1
        assert game.blind_type == BlindType.SMALL
        assert game.phase == GamePhase.BLIND_SELECT
        assert len(game.jokers) == 0


class TestBlindProgression:
    """Test blind and ante progression."""

    def test_start_blind(self):
        """Starting a blind should draw cards and set phase."""
        game = GameSimulator()
        game.reset(seed=42)

        result = game.start_blind()

        assert result.success
        assert game.phase == GamePhase.PLAYING
        assert len(game.hand) == 8  # Default hand size
        assert game.hands_remaining == 4
        assert game.discards_remaining == 3

    def test_cannot_start_blind_twice(self):
        """Cannot start blind when already playing."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        result = game.start_blind()
        assert not result.success

    def test_skip_small_blind(self):
        """Can skip small blind."""
        game = GameSimulator()
        game.reset(seed=42)

        result = game.skip_blind()

        assert result.success
        assert game.blind_type == BlindType.BIG

    def test_skip_big_blind(self):
        """Can skip big blind."""
        game = GameSimulator()
        game.reset(seed=42)
        game.skip_blind()  # Skip small

        result = game.skip_blind()  # Skip big

        assert result.success
        assert game.blind_type == BlindType.BOSS

    def test_cannot_skip_boss_blind(self):
        """Cannot skip boss blind."""
        game = GameSimulator()
        game.reset(seed=42)
        game.skip_blind()  # Skip small
        game.skip_blind()  # Skip big

        result = game.skip_blind()  # Try to skip boss

        assert not result.success
        assert game.blind_type == BlindType.BOSS


class TestPlayingHands:
    """Test playing hands during a blind."""

    def test_play_single_card(self):
        """Can play a single card."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        result = game.play_hand([0])

        assert result.success
        assert result.score > 0
        assert game.hands_remaining == 3

    def test_play_pair(self):
        """Playing a pair should score as pair."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        # Find a pair in hand
        ranks = {}
        pair_indices = []
        for i, card in enumerate(game.hand):
            if card.rank in ranks:
                pair_indices = [ranks[card.rank], i]
                break
            ranks[card.rank] = i

        if pair_indices:
            result = game.play_hand(pair_indices)
            assert result.success
            assert result.breakdown is not None
            # Could be pair or better depending on cards

    def test_play_five_cards(self):
        """Can play up to 5 cards."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        result = game.play_hand([0, 1, 2, 3, 4])

        assert result.success
        assert result.score > 0

    def test_cannot_play_more_than_five(self):
        """Cannot play more than 5 cards."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        result = game.play_hand([0, 1, 2, 3, 4, 5])

        assert not result.success

    def test_cannot_play_empty(self):
        """Must play at least one card."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        result = game.play_hand([])

        assert not result.success

    def test_hand_redraws_after_play(self):
        """Hand should redraw to full size after playing."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()
        initial_deck_size = len(game.deck)

        game.play_hand([0, 1])

        assert len(game.hand) == 8
        # Deck should be smaller by cards drawn
        assert len(game.deck) < initial_deck_size


class TestDiscarding:
    """Test discarding cards."""

    def test_discard_single_card(self):
        """Can discard a single card."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        result = game.discard([0])

        assert result.success
        assert game.discards_remaining == 2
        assert len(game.hand) == 8  # Should redraw

    def test_discard_multiple_cards(self):
        """Can discard multiple cards."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        result = game.discard([0, 1, 2])

        assert result.success
        assert game.discards_remaining == 2

    def test_cannot_discard_when_none_remaining(self):
        """Cannot discard when no discards left."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        game.discard([0])
        game.discard([0])
        game.discard([0])

        result = game.discard([0])

        assert not result.success

    def test_cannot_discard_more_than_five(self):
        """Cannot discard more than 5 cards."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        result = game.discard([0, 1, 2, 3, 4, 5])

        assert not result.success


class TestBlindCompletion:
    """Test completing blinds."""

    def test_blind_beaten_advances_game(self):
        """Beating a blind should advance the game."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        # Play hands until blind is beaten or game over
        while game.phase == GamePhase.PLAYING and game.hands_remaining > 0:
            result = game.play_hand([0, 1, 2, 3, 4])
            if result.blind_beaten:
                break

        # Should either beat blind or lose
        assert game.phase != GamePhase.PLAYING or game.blind_type != BlindType.SMALL

    def test_game_over_when_blind_not_beaten(self):
        """Game should end when hands run out without beating blind."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        # Set impossible blind
        game.blind_chips = 999999999

        # Play all hands
        for _ in range(4):
            if game.hands_remaining > 0:
                game.play_hand([0])

        assert game.phase == GamePhase.GAME_OVER
        assert not game.is_won


class TestJokerManagement:
    """Test joker buying, selling, and reordering."""

    def test_buy_joker(self):
        """Can buy a joker in shop."""
        game = GameSimulator()
        game.reset(seed=42)
        game.phase = GamePhase.SHOP
        game.money = 10

        result = game.buy_joker("joker", 2)

        assert result.success
        assert len(game.jokers) == 1
        assert game.jokers[0].name == "Joker"
        assert game.money == 8

    def test_cannot_buy_without_money(self):
        """Cannot buy joker without enough money."""
        game = GameSimulator()
        game.reset(seed=42)
        game.phase = GamePhase.SHOP
        game.money = 1

        result = game.buy_joker("joker", 2)

        assert not result.success
        assert len(game.jokers) == 0

    def test_cannot_exceed_max_jokers(self):
        """Cannot exceed max joker slots."""
        game = GameSimulator()
        game.reset(seed=42)
        game.phase = GamePhase.SHOP
        game.money = 100

        for i in range(5):
            game.buy_joker("joker", 2)

        result = game.buy_joker("joker", 2)

        assert not result.success
        assert len(game.jokers) == 5

    def test_sell_joker(self):
        """Can sell a joker."""
        game = GameSimulator()
        game.reset(seed=42)
        game.phase = GamePhase.SHOP
        game.money = 10

        game.buy_joker("joker", 2)  # Costs 2
        initial_money = game.money

        result = game.sell_joker(0)

        assert result.success
        assert len(game.jokers) == 0
        assert game.money == initial_money + 1  # Sells for half (2 // 2 = 1)

    def test_reorder_jokers(self):
        """Can reorder jokers."""
        game = GameSimulator()
        game.reset(seed=42)
        game.phase = GamePhase.SHOP
        game.money = 100

        game.buy_joker("joker", 2)
        game.buy_joker("the_duo", 8)
        game.buy_joker("half_joker", 5)

        original_order = [j.name for j in game.jokers]
        result = game.reorder_jokers([2, 0, 1])

        assert result.success
        new_order = [j.name for j in game.jokers]
        assert new_order == [original_order[2], original_order[0], original_order[1]]


class TestJokerEffectsInGame:
    """Test that jokers affect scoring in the simulator."""

    def test_joker_increases_score(self):
        """Joker should increase score."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        # Play without joker
        game_no_joker = game.clone()
        result_no_joker = game_no_joker.play_hand([0, 1])

        # Add joker and play same hand
        game.jokers.append(create_joker("joker"))
        result_with_joker = game.play_hand([0, 1])

        # Joker adds +4 mult, so score should be higher
        assert result_with_joker.score > result_no_joker.score


class TestStateCloning:
    """Test game state cloning for MCTS."""

    def test_clone_is_independent(self):
        """Cloned game should be independent of original."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        clone = game.clone()
        clone.play_hand([0, 1])

        # Original should be unchanged
        assert game.hands_remaining == 4
        assert clone.hands_remaining == 3

    def test_clone_has_same_state(self):
        """Clone should have identical initial state."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()
        game.jokers.append(create_joker("joker"))

        clone = game.clone()

        assert clone.money == game.money
        assert clone.ante == game.ante
        assert clone.blind_type == game.blind_type
        assert clone.hand == game.hand
        assert len(clone.jokers) == len(game.jokers)
        assert clone.jokers[0].id == game.jokers[0].id

    def test_clone_joker_state_independent(self):
        """Joker state in clone should be independent."""
        game = GameSimulator()
        game.reset(seed=42)
        game.jokers.append(create_joker("ice_cream"))
        game.jokers[0].state["chips"] = 100
        game.start_blind()

        clone = game.clone()
        clone.play_hand([0])  # Ice cream loses 5 chips

        assert clone.jokers[0].state["chips"] == 95
        assert game.jokers[0].state["chips"] == 100


class TestScalingJokers:
    """Test jokers with mutable state."""

    def test_ice_cream_decreases(self):
        """Ice Cream should lose chips each hand."""
        game = GameSimulator()
        game.reset(seed=42)
        game.jokers.append(create_joker("ice_cream"))
        game.start_blind()

        assert game.jokers[0].state.get("chips", 100) == 100

        game.play_hand([0])

        assert game.jokers[0].state["chips"] == 95

    def test_green_joker_increases_on_play(self):
        """Green Joker gains mult on play."""
        game = GameSimulator()
        game.reset(seed=42)
        game.jokers.append(create_joker("green_joker"))
        game.start_blind()

        game.play_hand([0])
        assert game.jokers[0].state["mult"] == 1

        game.play_hand([0])
        assert game.jokers[0].state["mult"] == 2

    def test_green_joker_decreases_on_discard(self):
        """Green Joker loses mult on discard."""
        game = GameSimulator()
        game.reset(seed=42)
        game.jokers.append(create_joker("green_joker"))
        game.jokers[0].state["mult"] = 5
        game.start_blind()

        game.discard([0])

        assert game.jokers[0].state["mult"] == 4

    def test_ride_the_bus_resets_on_face_card(self):
        """Ride the Bus resets when face card played."""
        game = GameSimulator()
        game.reset(seed=42)
        game.jokers.append(create_joker("ride_the_bus"))
        game.jokers[0].state["mult"] = 5
        game.start_blind()

        # Find and play a face card
        face_index = None
        for i, card in enumerate(game.hand):
            if card.rank in (Rank.JACK, Rank.QUEEN, Rank.KING):
                face_index = i
                break

        if face_index is not None:
            game.play_hand([face_index])
            assert game.jokers[0].state["mult"] == 0


class TestLegalActions:
    """Test legal action enumeration."""

    def test_get_legal_plays(self):
        """Should return all valid play combinations."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        plays = game.get_legal_plays()

        # With 8 cards, should have C(8,1) + C(8,2) + C(8,3) + C(8,4) + C(8,5) plays
        # = 8 + 28 + 56 + 70 + 56 = 218
        assert len(plays) == 218

    def test_get_legal_discards(self):
        """Should return all valid discard combinations."""
        game = GameSimulator()
        game.reset(seed=42)
        game.start_blind()

        discards = game.get_legal_discards()

        # Same as plays: 218 combinations
        assert len(discards) == 218

    def test_no_legal_plays_when_not_playing(self):
        """No legal plays when not in playing phase."""
        game = GameSimulator()
        game.reset(seed=42)

        plays = game.get_legal_plays()

        assert plays == []
