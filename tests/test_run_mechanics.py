"""Tests for run mechanics: Stakes, Blinds, Antes, and Tags."""

import pytest

from balatro_bot.run_mechanics import (
    BASE_ANTE_CHIPS,
    BIG_BLIND,
    BOSS_BLINDS,
    SMALL_BLIND,
    STAKES,
    TAGS,
    Blind,
    BlindType,
    BossBlind,
    JokerSticker,
    RunState,
    Stake,
    StakeLevel,
    Tag,
    TagType,
    calculate_blind_chips,
    calculate_blind_reward,
    create_run_state,
    get_all_boss_blind_ids,
    get_all_stake_levels,
    get_all_tag_types,
    get_showdown_blinds,
)


class TestStakes:
    """Test stake definitions."""

    def test_all_8_stakes_exist(self):
        """Should have all 8 stake levels."""
        assert len(STAKES) == 8

    def test_stake_order(self):
        """Stakes should be in order from White to Gold."""
        levels = list(StakeLevel)
        assert levels[0] == StakeLevel.WHITE
        assert levels[7] == StakeLevel.GOLD
        assert StakeLevel.WHITE.value == 1
        assert StakeLevel.GOLD.value == 8

    def test_stake_has_required_fields(self):
        """Each stake should have required fields."""
        for level, stake in STAKES.items():
            assert stake.level == level
            assert stake.name
            assert stake.color
            assert stake.description

    def test_white_stake_is_base(self):
        """White stake should have no penalties."""
        stake = STAKES[StakeLevel.WHITE]
        assert stake.small_blind_reward is True
        assert stake.score_scaling == 1.0
        assert stake.discards_penalty == 0
        assert stake.eternal_chance == 0.0
        assert stake.perishable_chance == 0.0
        assert stake.rental_chance == 0.0

    def test_red_stake_no_small_reward(self):
        """Red stake should disable small blind reward."""
        stake = STAKES[StakeLevel.RED]
        assert stake.small_blind_reward is False

    def test_green_stake_faster_scaling(self):
        """Green stake should have faster score scaling."""
        stake = STAKES[StakeLevel.GREEN]
        assert stake.score_scaling > 1.0

    def test_black_stake_eternal_chance(self):
        """Black stake should add Eternal sticker chance."""
        stake = STAKES[StakeLevel.BLACK]
        assert stake.eternal_chance == 0.30

    def test_blue_stake_discard_penalty(self):
        """Blue stake should reduce discards."""
        stake = STAKES[StakeLevel.BLUE]
        assert stake.discards_penalty == 1

    def test_purple_stake_even_faster_scaling(self):
        """Purple stake should have even faster scaling."""
        stake = STAKES[StakeLevel.PURPLE]
        assert stake.score_scaling >= STAKES[StakeLevel.GREEN].score_scaling

    def test_orange_stake_perishable_chance(self):
        """Orange stake should add Perishable sticker chance."""
        stake = STAKES[StakeLevel.ORANGE]
        assert stake.perishable_chance == 0.30

    def test_gold_stake_rental_chance(self):
        """Gold stake should add Rental sticker chance."""
        stake = STAKES[StakeLevel.GOLD]
        assert stake.rental_chance == 0.30

    def test_gold_stake_has_all_penalties(self):
        """Gold stake should have all cumulative penalties."""
        stake = STAKES[StakeLevel.GOLD]
        assert stake.small_blind_reward is False
        assert stake.score_scaling > 1.0
        assert stake.discards_penalty == 1
        assert stake.eternal_chance > 0
        assert stake.perishable_chance > 0
        assert stake.rental_chance > 0

    def test_get_all_stake_levels(self):
        """Should return all stake levels."""
        levels = get_all_stake_levels()
        assert len(levels) == 8
        assert levels[0] == StakeLevel.WHITE
        assert levels[-1] == StakeLevel.GOLD


class TestJokerStickers:
    """Test joker sticker definitions."""

    def test_sticker_types(self):
        """Should have all sticker types."""
        assert JokerSticker.NONE.value == "none"
        assert JokerSticker.ETERNAL.value == "eternal"
        assert JokerSticker.PERISHABLE.value == "perishable"
        assert JokerSticker.RENTAL.value == "rental"


class TestBlinds:
    """Test blind definitions."""

    def test_small_blind(self):
        """Small blind should have correct values."""
        assert SMALL_BLIND.blind_type == BlindType.SMALL
        assert SMALL_BLIND.chip_multiplier == 1.0
        assert SMALL_BLIND.can_skip is True

    def test_big_blind(self):
        """Big blind should have correct values."""
        assert BIG_BLIND.blind_type == BlindType.BIG
        assert BIG_BLIND.chip_multiplier == 1.5
        assert BIG_BLIND.can_skip is True


class TestBossBlinds:
    """Test boss blind definitions."""

    def test_boss_blind_count(self):
        """Should have 28 boss blinds."""
        assert len(BOSS_BLINDS) == 28

    def test_boss_blind_has_required_fields(self):
        """Each boss blind should have required fields."""
        for boss_id, boss in BOSS_BLINDS.items():
            assert boss.id == boss_id
            assert boss.name
            assert boss.description
            assert boss.chip_multiplier >= 2.0
            assert boss.effect_type

    def test_standard_boss_multiplier(self):
        """Standard boss blinds should have 2x multiplier."""
        standard_bosses = [b for b in BOSS_BLINDS.values() if b.chip_multiplier == 2.0]
        assert len(standard_bosses) > 20

    def test_the_wall_extra_large(self):
        """The Wall should have 4x multiplier."""
        wall = BOSS_BLINDS["the_wall"]
        assert wall.chip_multiplier == 4.0

    def test_violet_vessel_very_large(self):
        """Violet Vessel should have 6x multiplier."""
        vessel = BOSS_BLINDS["violet_vessel"]
        assert vessel.chip_multiplier == 6.0

    def test_suit_debuff_bosses(self):
        """Should have all suit debuff bosses."""
        suit_bosses = {
            "the_club": "Club",
            "the_goad": "Spade",
            "the_window": "Diamond",
            "the_head": "Heart",
        }
        for boss_id, suit in suit_bosses.items():
            assert boss_id in BOSS_BLINDS
            assert BOSS_BLINDS[boss_id].effect_type == "debuff_suit"

    def test_get_showdown_blinds(self):
        """Should return showdown boss blinds."""
        showdown = get_showdown_blinds()
        assert len(showdown) == 5
        assert "crimson_heart" in showdown
        assert "violet_vessel" in showdown
        assert "amber_acorn" in showdown

    def test_get_all_boss_blind_ids(self):
        """Should return all boss blind IDs."""
        ids = get_all_boss_blind_ids()
        assert len(ids) == 28


class TestAnteProgression:
    """Test ante chip requirements."""

    def test_base_ante_chips(self):
        """Base ante chips should be correct."""
        assert BASE_ANTE_CHIPS[1] == 300
        assert BASE_ANTE_CHIPS[2] == 800
        assert BASE_ANTE_CHIPS[3] == 2000
        assert BASE_ANTE_CHIPS[4] == 5000
        assert BASE_ANTE_CHIPS[5] == 11000
        assert BASE_ANTE_CHIPS[6] == 20000
        assert BASE_ANTE_CHIPS[7] == 35000
        assert BASE_ANTE_CHIPS[8] == 50000

    def test_small_blind_chips(self):
        """Small blind should be 1x base chips."""
        chips = calculate_blind_chips(1, BlindType.SMALL)
        assert chips == 300

    def test_big_blind_chips(self):
        """Big blind should be 1.5x base chips."""
        chips = calculate_blind_chips(1, BlindType.BIG)
        assert chips == 450  # 300 * 1.5

    def test_boss_blind_chips(self):
        """Boss blind should be 2x base chips."""
        chips = calculate_blind_chips(1, BlindType.BOSS)
        assert chips == 600  # 300 * 2.0

    def test_boss_blind_with_wall(self):
        """The Wall should be 4x base chips."""
        wall = BOSS_BLINDS["the_wall"]
        chips = calculate_blind_chips(1, BlindType.BOSS, boss_blind=wall)
        assert chips == 1200  # 300 * 4.0

    def test_higher_ante_chips(self):
        """Higher antes should require more chips."""
        ante1 = calculate_blind_chips(1, BlindType.SMALL)
        ante8 = calculate_blind_chips(8, BlindType.SMALL)
        assert ante8 > ante1

    def test_stake_scaling(self):
        """Higher stakes should scale chip requirements."""
        white = calculate_blind_chips(1, BlindType.SMALL, StakeLevel.WHITE)
        green = calculate_blind_chips(1, BlindType.SMALL, StakeLevel.GREEN)
        assert green > white

    def test_endless_mode_scaling(self):
        """Endless mode (ante 9+) should scale exponentially."""
        ante8 = calculate_blind_chips(8, BlindType.SMALL)
        ante9 = calculate_blind_chips(9, BlindType.SMALL)
        ante10 = calculate_blind_chips(10, BlindType.SMALL)
        assert ante9 > ante8
        assert ante10 > ante9
        # Endless mode scales very fast
        assert ante10 > ante9 * 1.5


class TestBlindRewards:
    """Test blind reward calculations."""

    def test_small_blind_reward_ante1(self):
        """Small blind at ante 1 should give base reward."""
        reward = calculate_blind_reward(1, BlindType.SMALL)
        assert reward == 3  # Base reward

    def test_big_blind_reward_ante1(self):
        """Big blind at ante 1 should give more reward."""
        reward = calculate_blind_reward(1, BlindType.BIG)
        assert reward == 4  # Base big reward

    def test_boss_blind_reward_ante1(self):
        """Boss blind at ante 1 should give most reward."""
        reward = calculate_blind_reward(1, BlindType.BOSS)
        assert reward == 5  # Base boss reward

    def test_reward_scales_with_ante(self):
        """Rewards should increase with ante."""
        ante1 = calculate_blind_reward(1, BlindType.SMALL)
        ante5 = calculate_blind_reward(5, BlindType.SMALL)
        assert ante5 > ante1

    def test_red_stake_no_small_reward(self):
        """Red+ stake should give no small blind reward."""
        white_reward = calculate_blind_reward(1, BlindType.SMALL, StakeLevel.WHITE)
        red_reward = calculate_blind_reward(1, BlindType.SMALL, StakeLevel.RED)
        assert white_reward == 3
        assert red_reward == 0

    def test_big_blind_still_rewarded_red_stake(self):
        """Big blind should still be rewarded at Red stake."""
        reward = calculate_blind_reward(1, BlindType.BIG, StakeLevel.RED)
        assert reward > 0


class TestTags:
    """Test tag definitions."""

    def test_all_24_tags_exist(self):
        """Should have all 24 tags."""
        assert len(TAGS) == 24

    def test_tag_has_required_fields(self):
        """Each tag should have required fields."""
        for tag_type, tag in TAGS.items():
            assert tag.tag_type == tag_type
            assert tag.name
            assert tag.description

    def test_joker_rarity_tags(self):
        """Should have joker rarity tags."""
        assert TAGS[TagType.UNCOMMON].free_joker_rarity == "uncommon"
        assert TAGS[TagType.RARE].free_joker_rarity == "rare"

    def test_joker_edition_tags(self):
        """Should have joker edition tags."""
        assert TAGS[TagType.NEGATIVE].free_joker_edition == "negative"
        assert TAGS[TagType.FOIL].free_joker_edition == "foil"
        assert TAGS[TagType.HOLOGRAPHIC].free_joker_edition == "holographic"
        assert TAGS[TagType.POLYCHROME].free_joker_edition == "polychrome"

    def test_economy_tags(self):
        """Should have economy tags."""
        assert TAGS[TagType.INVESTMENT].money_bonus == 25
        assert TAGS[TagType.HANDY].per_hand_bonus == 1
        assert TAGS[TagType.GARBAGE].per_discard_bonus == 1
        assert TAGS[TagType.SPEED].per_skip_bonus == 5
        assert TAGS[TagType.ECONOMY].money_multiplier == 2.0

    def test_booster_pack_tags(self):
        """Should have booster pack tags."""
        assert TAGS[TagType.STANDARD].free_pack_type == "standard_mega"
        assert TAGS[TagType.CHARM].free_pack_type == "arcana_mega"
        assert TAGS[TagType.METEOR].free_pack_type == "celestial_mega"
        assert TAGS[TagType.BUFFOON].free_pack_type == "buffoon_mega"
        assert TAGS[TagType.ETHEREAL].free_pack_type == "spectral_normal"

    def test_immediate_tags(self):
        """Some tags should be immediate effect."""
        assert TAGS[TagType.HANDY].immediate is True
        assert TAGS[TagType.ECONOMY].immediate is True
        assert TAGS[TagType.STANDARD].immediate is True
        assert TAGS[TagType.ORBITAL].immediate is True

    def test_delayed_tags(self):
        """Some tags should affect next shop."""
        assert TAGS[TagType.UNCOMMON].immediate is False
        assert TAGS[TagType.VOUCHER].immediate is False
        assert TAGS[TagType.COUPON].immediate is False

    def test_juggle_tag(self):
        """Juggle tag should give hand size bonus."""
        assert TAGS[TagType.JUGGLE].hand_size_bonus == 3

    def test_orbital_tag(self):
        """Orbital tag should give hand level bonus."""
        assert TAGS[TagType.ORBITAL].hand_level_bonus == 3

    def test_get_all_tag_types(self):
        """Should return all tag types."""
        types = get_all_tag_types()
        assert len(types) == 24


class TestRunState:
    """Test run state management."""

    def test_create_run_state(self):
        """Should create run state with defaults."""
        state = create_run_state()
        assert state.ante == 1
        assert state.current_blind == BlindType.SMALL
        assert state.stake == StakeLevel.WHITE
        assert state.hands_played == 0
        assert state.blinds_skipped == 0

    def test_create_run_state_with_stake(self):
        """Should create run state with specified stake."""
        state = create_run_state(StakeLevel.GOLD)
        assert state.stake == StakeLevel.GOLD

    def test_advance_blind_small_to_big(self):
        """Should advance from Small to Big blind."""
        state = create_run_state()
        assert state.current_blind == BlindType.SMALL
        state.advance_blind()
        assert state.current_blind == BlindType.BIG
        assert state.ante == 1

    def test_advance_blind_big_to_boss(self):
        """Should advance from Big to Boss blind."""
        state = create_run_state()
        state.current_blind = BlindType.BIG
        state.advance_blind()
        assert state.current_blind == BlindType.BOSS
        assert state.ante == 1

    def test_advance_blind_boss_to_next_ante(self):
        """Should advance to next ante after Boss."""
        state = create_run_state()
        state.current_blind = BlindType.BOSS
        state.advance_blind()
        assert state.current_blind == BlindType.SMALL
        assert state.ante == 2

    def test_skip_blind(self):
        """Should skip current blind and increment counter."""
        state = create_run_state()
        state.skip_blind()
        assert state.current_blind == BlindType.BIG
        assert state.blinds_skipped == 1

    def test_cannot_skip_boss(self):
        """Should raise error when skipping Boss blind."""
        state = create_run_state()
        state.current_blind = BlindType.BOSS
        with pytest.raises(ValueError, match="Cannot skip Boss blind"):
            state.skip_blind()

    def test_get_chip_requirement(self):
        """Should return correct chip requirement."""
        state = create_run_state()
        chips = state.get_chip_requirement()
        assert chips == 300  # Ante 1, Small blind

    def test_get_blind_reward(self):
        """Should return correct reward."""
        state = create_run_state()
        reward = state.get_blind_reward()
        assert reward == 3  # Small blind base

    def test_is_game_won_false(self):
        """Should not be won at start."""
        state = create_run_state()
        assert state.is_game_won() is False

    def test_is_game_won_true(self):
        """Should be won after ante 8."""
        state = create_run_state()
        state.ante = 9
        assert state.is_game_won() is True

    def test_is_endless_mode(self):
        """Should detect endless mode."""
        state = create_run_state()
        assert state.is_endless_mode() is False
        state.ante = 9
        assert state.is_endless_mode() is True

    def test_temp_effects_reset_on_ante_advance(self):
        """Temporary effects should reset when advancing ante."""
        state = create_run_state()
        state.temp_hand_size_bonus = 3
        state.current_blind = BlindType.BOSS
        state.advance_blind()
        assert state.temp_hand_size_bonus == 0

    def test_active_tags(self):
        """Should track active tags."""
        state = create_run_state()
        state.active_tags.append(TagType.UNCOMMON)
        assert TagType.UNCOMMON in state.active_tags


class TestRunProgression:
    """Test full run progression scenarios."""

    def test_full_ante_cycle(self):
        """Should complete full ante cycle."""
        state = create_run_state()
        # Small -> Big -> Boss -> Small (Ante 2)
        state.advance_blind()  # Big
        state.advance_blind()  # Boss
        state.advance_blind()  # Ante 2, Small
        assert state.ante == 2
        assert state.current_blind == BlindType.SMALL

    def test_reach_ante_8(self):
        """Should reach ante 8 after 24 blinds."""
        state = create_run_state()
        for _ in range(21):  # 7 antes * 3 blinds = 21
            state.advance_blind()
        assert state.ante == 8
        assert state.current_blind == BlindType.SMALL

    def test_skip_vs_beat_progression(self):
        """Skipping should still advance correctly."""
        state1 = create_run_state()
        state2 = create_run_state()

        # Beat all blinds
        state1.advance_blind()
        state1.advance_blind()
        state1.advance_blind()

        # Skip small and big
        state2.skip_blind()
        state2.skip_blind()
        state2.advance_blind()

        # Both should be at ante 2
        assert state1.ante == 2
        assert state2.ante == 2
        assert state2.blinds_skipped == 2

    def test_chip_requirements_increase(self):
        """Chip requirements should increase through run."""
        state = create_run_state()
        chips_ante1 = state.get_chip_requirement()

        # Advance to ante 2
        state.advance_blind()
        state.advance_blind()
        state.advance_blind()
        chips_ante2 = state.get_chip_requirement()

        assert chips_ante2 > chips_ante1
