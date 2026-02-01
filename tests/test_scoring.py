"""Tests for the scoring engine and joker effects."""

from balatro_bot.jokers import create_joker
from balatro_bot.models import Card, GameState, HandType
from balatro_bot.scoring import calculate_score, quick_score


def cards(card_strings: list[str]) -> list[Card]:
    """Helper to create cards from strings."""
    return [Card.from_string(s) for s in card_strings]


class TestBasicScoring:
    """Test scoring without jokers."""

    def test_pair_base_score(self):
        """Pair of aces: base 10 chips + 22 (2 aces) = 32 chips, 2 mult = 64"""
        played = cards(["AS", "AH"])
        score = quick_score(played)
        assert score == 64

    def test_three_of_a_kind_base_score(self):
        """Three aces: base 30 chips + 33 (3 aces) = 63 chips, 3 mult = 189"""
        played = cards(["AS", "AH", "AC"])
        score = quick_score(played)
        assert score == 189

    def test_flush_base_score(self):
        """Flush: base 35 chips + card values, 4 mult"""
        played = cards(["2S", "5S", "7S", "9S", "KS"])
        # Cards: 2 + 5 + 7 + 9 + 10 = 33
        # Total chips = 35 + 33 = 68
        # Score = 68 * 4 = 272
        score = quick_score(played)
        assert score == 272


class TestJokerEffects:
    """Test individual joker effects."""

    def test_basic_joker_adds_mult(self):
        """Basic Joker adds +4 mult."""
        played = cards(["AS", "AH"])  # Pair
        jokers = [create_joker("joker")]
        breakdown = calculate_score(played, jokers, GameState())

        # Base: 32 chips, 2 mult
        # Joker: +4 mult -> 6 mult
        # Score: 32 * 6 = 192
        assert breakdown.final_mult == 6.0
        assert breakdown.final_score == 192

    def test_greedy_joker_with_diamonds(self):
        """Greedy Joker adds +3 mult per diamond."""
        played = cards(["AD", "KD"])  # Pair of... wait, not a pair
        # Let's do a pair with diamonds
        played = cards(["AD", "AH"])  # Pair with one diamond
        jokers = [create_joker("greedy_joker")]
        breakdown = calculate_score(played, jokers, GameState())

        # Base: 32 chips, 2 mult
        # Greedy: +3 mult (1 diamond in scoring cards) -> 5 mult
        # Score: 32 * 5 = 160
        assert breakdown.final_mult == 5.0
        assert breakdown.final_score == 160

    def test_greedy_joker_multiple_diamonds(self):
        """Greedy Joker with multiple diamonds."""
        played = cards(["AD", "KD", "QD", "JD", "9D"])  # Flush of diamonds
        jokers = [create_joker("greedy_joker")]
        breakdown = calculate_score(played, jokers, GameState())

        # Base: 35 + (11+10+10+10+9) = 35 + 50 = 85 chips, 4 mult
        # Greedy: +3 * 5 = +15 mult -> 19 mult
        # Score: 85 * 19 = 1615
        assert breakdown.final_mult == 19.0
        assert breakdown.final_score == 1615

    def test_half_joker_with_small_hand(self):
        """Half Joker gives +20 mult for 3 or fewer cards."""
        played = cards(["AS", "AH"])  # 2 cards
        jokers = [create_joker("half_joker")]
        breakdown = calculate_score(played, jokers, GameState())

        # Base: 32 chips, 2 mult
        # Half Joker: +20 mult -> 22 mult
        # Score: 32 * 22 = 704
        assert breakdown.final_mult == 22.0
        assert breakdown.final_score == 704

    def test_half_joker_with_large_hand(self):
        """Half Joker gives nothing for 4+ cards."""
        played = cards(["AS", "AH", "KS", "KH"])  # 4 cards, two pair
        jokers = [create_joker("half_joker")]
        breakdown = calculate_score(played, jokers, GameState())

        # Two pair: base 20 + (11+11+10+10) = 62 chips, 2 mult
        # Half Joker: no effect (4 cards)
        # Score: 62 * 2 = 124
        assert breakdown.final_mult == 2.0
        assert breakdown.final_score == 124

    def test_sly_joker_with_pair(self):
        """Sly Joker adds +50 chips if hand contains pair."""
        played = cards(["AS", "AH"])
        jokers = [create_joker("sly_joker")]
        breakdown = calculate_score(played, jokers, GameState())

        # Base: 32 chips, 2 mult
        # Sly: +50 chips -> 82 chips
        # Score: 82 * 2 = 164
        assert breakdown.final_chips == 82
        assert breakdown.final_score == 164


class TestMultiplicativeJokers:
    """Test ×mult jokers."""

    def test_the_duo_multiplies_mult(self):
        """The Duo gives ×2 mult for pairs."""
        played = cards(["AS", "AH"])
        jokers = [create_joker("the_duo")]
        breakdown = calculate_score(played, jokers, GameState())

        # Base: 32 chips, 2 mult
        # The Duo: ×2 mult -> 4 mult
        # Score: 32 * 4 = 128
        assert breakdown.final_mult == 4.0
        assert breakdown.final_score == 128

    def test_the_trio_multiplies_mult(self):
        """The Trio gives ×3 mult for three of a kind."""
        played = cards(["AS", "AH", "AC"])
        jokers = [create_joker("the_trio")]
        breakdown = calculate_score(played, jokers, GameState())

        # Base: 63 chips, 3 mult
        # The Trio: ×3 mult -> 9 mult
        # Score: 63 * 9 = 567
        assert breakdown.final_mult == 9.0
        assert breakdown.final_score == 567


class TestJokerOrderMatters:
    """Test that joker order affects final score."""

    def test_add_mult_then_multiply(self):
        """Order: +mult joker, then ×mult joker."""
        played = cards(["AS", "AH"])  # Pair
        # Base: 32 chips, 2 mult

        # Order 1: Joker (+4 mult) then The Duo (×2)
        # (2 + 4) × 2 = 12 mult
        jokers_order1 = [create_joker("joker"), create_joker("the_duo")]
        result1 = calculate_score(played, jokers_order1, GameState())

        assert result1.final_mult == 12.0
        assert result1.final_score == 32 * 12  # 384

    def test_multiply_then_add_mult(self):
        """Order: ×mult joker, then +mult joker."""
        played = cards(["AS", "AH"])  # Pair
        # Base: 32 chips, 2 mult

        # Order 2: The Duo (×2) then Joker (+4 mult)
        # (2 × 2) + 4 = 8 mult
        jokers_order2 = [create_joker("the_duo"), create_joker("joker")]
        result2 = calculate_score(played, jokers_order2, GameState())

        assert result2.final_mult == 8.0
        assert result2.final_score == 32 * 8  # 256

    def test_order_difference_is_significant(self):
        """Verify the two orders give different results."""
        played = cards(["AS", "AH"])

        jokers_add_first = [create_joker("joker"), create_joker("the_duo")]
        jokers_mult_first = [create_joker("the_duo"), create_joker("joker")]

        result_add_first = calculate_score(played, jokers_add_first, GameState())
        result_mult_first = calculate_score(played, jokers_mult_first, GameState())

        # 384 vs 256 - order matters!
        assert result_add_first.final_score == 384
        assert result_mult_first.final_score == 256
        assert result_add_first.final_score != result_mult_first.final_score

    def test_multiple_multipliers_compound(self):
        """Multiple ×mult jokers compound multiplicatively."""
        played = cards(["AS", "AH", "AC"])  # Three of a kind
        # Base: 63 chips, 3 mult

        # Jolly (+8 for pair) + The Duo (×2) + The Trio (×3)
        # (3 + 8) × 2 × 3 = 66 mult
        jokers = [
            create_joker("jolly_joker"),
            create_joker("the_duo"),
            create_joker("the_trio"),
        ]
        result = calculate_score(played, jokers, GameState())

        assert result.final_mult == 66.0
        assert result.final_score == 63 * 66  # 4158


class TestContextDependentJokers:
    """Test jokers that depend on game state."""

    def test_banner_with_discards(self):
        """Banner adds +30 chips per discard remaining."""
        played = cards(["AS", "AH"])
        state = GameState(discards_remaining=3)
        jokers = [create_joker("banner")]

        breakdown = calculate_score(played, jokers, state)

        # Base: 32 chips, 2 mult
        # Banner: +90 chips (3 discards × 30)
        # Total: 122 chips × 2 mult = 244
        assert breakdown.final_chips == 122
        assert breakdown.final_score == 244

    def test_banner_with_no_discards(self):
        """Banner adds nothing with 0 discards."""
        played = cards(["AS", "AH"])
        state = GameState(discards_remaining=0)
        jokers = [create_joker("banner")]

        breakdown = calculate_score(played, jokers, state)

        # No chips added
        assert breakdown.final_chips == 32
        assert breakdown.final_score == 64

    def test_mystic_summit_with_no_discards(self):
        """Mystic Summit gives +15 mult when 0 discards remain."""
        played = cards(["AS", "AH"])
        state = GameState(discards_remaining=0)
        jokers = [create_joker("mystic_summit")]

        breakdown = calculate_score(played, jokers, state)

        # Base: 32 chips, 2 mult
        # Mystic Summit: +15 mult -> 17 mult
        # Score: 32 * 17 = 544
        assert breakdown.final_mult == 17.0
        assert breakdown.final_score == 544

    def test_raised_fist_with_cards_in_hand(self):
        """Raised Fist adds double the lowest card's rank to mult."""
        played = cards(["AS", "AH"])
        remaining = cards(["2S", "5H", "KD"])  # Lowest is 2
        jokers = [create_joker("raised_fist")]

        breakdown = calculate_score(played, jokers, GameState(), cards_in_hand=remaining)

        # Base: 32 chips, 2 mult
        # Raised Fist: +4 mult (2 × 2)
        # Score: 32 * 6 = 192
        assert breakdown.final_mult == 6.0
        assert breakdown.final_score == 192


class TestHandLevels:
    """Test hand level upgrades from planet cards."""

    def test_level_2_pair_increases_score(self):
        """Level 2 pair has higher base chips and mult."""
        played = cards(["AS", "AH"])
        state = GameState(hand_levels={HandType.PAIR: 2})

        breakdown = calculate_score(played, [], state)

        # Level 1 pair: 10 + 22 = 32 chips, 2 mult
        # Level 2 pair: 20 + 22 = 42 chips, 3 mult
        # Score: 42 * 3 = 126
        assert breakdown.base_chips == 42
        assert breakdown.base_mult == 3
        assert breakdown.final_score == 126

    def test_level_5_flush_is_powerful(self):
        """High level hands are much stronger."""
        played = cards(["2S", "5S", "7S", "9S", "KS"])
        state = GameState(hand_levels={HandType.FLUSH: 5})

        breakdown = calculate_score(played, [], state)

        # Level 1: 35 + 33 = 68 chips, 4 mult
        # Level 5: 35 + 4*35 + 33 = 208 chips, 8 mult
        # Score: 208 * 8 = 1664
        assert breakdown.final_score == 1664


class TestScoringBreakdown:
    """Test the scoring breakdown details."""

    def test_breakdown_records_joker_effects(self):
        """Breakdown should record each joker's contribution."""
        played = cards(["AS", "AH"])
        jokers = [
            create_joker("joker"),
            create_joker("sly_joker"),
            create_joker("the_duo"),
        ]

        breakdown = calculate_score(played, jokers, GameState())

        assert len(breakdown.joker_effects) == 3

        # Check each effect was recorded
        names = [effect[0] for effect in breakdown.joker_effects]
        assert "Joker" in names
        assert "Sly Joker" in names
        assert "The Duo" in names

    def test_breakdown_shows_base_values(self):
        """Breakdown should show base hand values."""
        played = cards(["AS", "AH", "AC"])  # Three of a kind

        breakdown = calculate_score(played, [], GameState())

        assert breakdown.hand_type == HandType.THREE_OF_A_KIND
        assert breakdown.base_chips == 63  # 30 + 33
        assert breakdown.base_mult == 3
