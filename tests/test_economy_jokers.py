"""Tests for economy joker effects."""

import pytest

from balatro_bot.jokers import (
    ECONOMY_CALCULATORS,
    EconomyContext,
    EconomyEffect,
    EffectTiming,
    JokerInstance,
    calculate_discard_economy,
    calculate_end_of_round_economy,
    calculate_play_economy,
    create_joker,
)
from balatro_bot.models import Card, Rank, Suit


class TestEconomyContext:
    """Test EconomyContext dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        ctx = EconomyContext()
        assert ctx.money == 0
        assert ctx.ante == 1
        assert ctx.boss_blinds_defeated == 0
        assert ctx.discards_used == 0
        assert ctx.nines_in_deck == 4

    def test_custom_values(self):
        """Should accept custom values."""
        ctx = EconomyContext(
            money=50,
            ante=5,
            boss_blinds_defeated=3,
            nines_in_deck=6,
        )
        assert ctx.money == 50
        assert ctx.ante == 5
        assert ctx.boss_blinds_defeated == 3
        assert ctx.nines_in_deck == 6


class TestEconomyEffect:
    """Test EconomyEffect dataclass."""

    def test_default_is_falsy(self):
        """Empty effect should be falsy."""
        effect = EconomyEffect()
        assert not effect

    def test_money_is_truthy(self):
        """Effect with money should be truthy."""
        effect = EconomyEffect(money=5)
        assert effect

    def test_sell_value_is_truthy(self):
        """Effect with sell value change should be truthy."""
        effect = EconomyEffect(sell_value_change=3)
        assert effect

    def test_interest_bonus_is_truthy(self):
        """Effect with interest bonus should be truthy."""
        effect = EconomyEffect(interest_bonus=2)
        assert effect


class TestGoldenJokerEconomy:
    """Test Golden Joker economy effect."""

    def test_earns_4_dollars(self):
        """Should earn $4 at end of round."""
        joker = create_joker("golden_joker")
        ctx = EconomyContext()
        effect = joker.calculate_economy_effect(ctx, EffectTiming.END_OF_ROUND)
        assert effect.money == 4


class TestRocketEconomy:
    """Test Rocket economy effect."""

    def test_base_payout(self):
        """Should earn $1 at start."""
        joker = create_joker("rocket")
        ctx = EconomyContext()
        effect = joker.calculate_economy_effect(ctx, EffectTiming.END_OF_ROUND)
        assert effect.money == 1

    def test_scales_with_boss_blinds(self):
        """Should earn +$2 per boss blind defeated."""
        joker = create_joker("rocket")
        joker.state["boss_blinds_defeated"] = 3
        ctx = EconomyContext()
        effect = joker.calculate_economy_effect(ctx, EffectTiming.END_OF_ROUND)
        assert effect.money == 7  # 1 + (3 * 2)

    def test_many_boss_blinds(self):
        """Should scale for many boss blinds."""
        joker = create_joker("rocket")
        joker.state["boss_blinds_defeated"] = 8
        ctx = EconomyContext()
        effect = joker.calculate_economy_effect(ctx, EffectTiming.END_OF_ROUND)
        assert effect.money == 17  # 1 + (8 * 2)


class TestCloud9Economy:
    """Test Cloud 9 economy effect."""

    def test_default_nines(self):
        """Should earn $4 for default 4 nines in deck."""
        joker = create_joker("cloud_9")
        ctx = EconomyContext(nines_in_deck=4)
        effect = joker.calculate_economy_effect(ctx, EffectTiming.END_OF_ROUND)
        assert effect.money == 4

    def test_extra_nines(self):
        """Should earn more with extra nines."""
        joker = create_joker("cloud_9")
        ctx = EconomyContext(nines_in_deck=8)
        effect = joker.calculate_economy_effect(ctx, EffectTiming.END_OF_ROUND)
        assert effect.money == 8

    def test_no_nines(self):
        """Should earn nothing with no nines."""
        joker = create_joker("cloud_9")
        ctx = EconomyContext(nines_in_deck=0)
        effect = joker.calculate_economy_effect(ctx, EffectTiming.END_OF_ROUND)
        assert effect.money == 0


class TestToTheMoonEconomy:
    """Test To the Moon economy effect."""

    def test_interest_bonus(self):
        """Should give $1 interest per $5."""
        joker = create_joker("to_the_moon")
        ctx = EconomyContext(money=25)
        effect = joker.calculate_economy_effect(ctx, EffectTiming.END_OF_ROUND)
        assert effect.interest_bonus == 5  # 25 // 5

    def test_partial_amount(self):
        """Should floor division for partial amounts."""
        joker = create_joker("to_the_moon")
        ctx = EconomyContext(money=23)
        effect = joker.calculate_economy_effect(ctx, EffectTiming.END_OF_ROUND)
        assert effect.interest_bonus == 4  # 23 // 5

    def test_zero_money(self):
        """Should give no bonus with no money."""
        joker = create_joker("to_the_moon")
        ctx = EconomyContext(money=0)
        effect = joker.calculate_economy_effect(ctx, EffectTiming.END_OF_ROUND)
        assert effect.interest_bonus == 0


class TestEggEconomy:
    """Test Egg economy effect."""

    def test_increases_sell_value(self):
        """Should increase sell value by $3."""
        joker = create_joker("egg")
        ctx = EconomyContext()
        effect = joker.calculate_economy_effect(ctx, EffectTiming.END_OF_ROUND)
        assert effect.sell_value_change == 3

    def test_accumulates_sell_value(self):
        """Should accumulate sell value over rounds."""
        joker = create_joker("egg")
        ctx = EconomyContext()

        # First round
        joker.calculate_economy_effect(ctx, EffectTiming.END_OF_ROUND)
        assert joker.state["sell_value_bonus"] == 3

        # Second round
        joker.calculate_economy_effect(ctx, EffectTiming.END_OF_ROUND)
        assert joker.state["sell_value_bonus"] == 6


class TestSatelliteEconomy:
    """Test Satellite economy effect."""

    def test_no_planets_used(self):
        """Should earn nothing with no planets."""
        joker = create_joker("satellite")
        ctx = EconomyContext(unique_planets_used=0)
        effect = joker.calculate_economy_effect(ctx, EffectTiming.END_OF_ROUND)
        assert effect.money == 0

    def test_planets_used(self):
        """Should earn $1 per unique planet."""
        joker = create_joker("satellite")
        ctx = EconomyContext(unique_planets_used=5)
        effect = joker.calculate_economy_effect(ctx, EffectTiming.END_OF_ROUND)
        assert effect.money == 5


class TestDelayedGratificationEconomy:
    """Test Delayed Gratification economy effect."""

    def test_no_discards_used(self):
        """Should earn money if no discards used."""
        joker = create_joker("delayed_gratification")
        ctx = EconomyContext(discards_used=0, discards_remaining=3)
        effect = joker.calculate_economy_effect(ctx, EffectTiming.END_OF_ROUND)
        assert effect.money == 6  # 2 * 3 discards

    def test_discards_used(self):
        """Should earn nothing if discards were used."""
        joker = create_joker("delayed_gratification")
        ctx = EconomyContext(discards_used=1, discards_remaining=2)
        effect = joker.calculate_economy_effect(ctx, EffectTiming.END_OF_ROUND)
        assert effect.money == 0


class TestCreditCardEconomy:
    """Test Credit Card economy effect."""

    def test_debt_limit(self):
        """Should allow $20 debt."""
        joker = create_joker("credit_card")
        ctx = EconomyContext()
        effect = joker.calculate_economy_effect(ctx, EffectTiming.ON_SHOP)
        assert effect.debt_limit == 20


class TestTradingCardEconomy:
    """Test Trading Card economy effect."""

    def test_single_card_discard(self):
        """Should earn $3 when discarding single card."""
        joker = create_joker("trading_card")
        card = Card(Rank.ACE, Suit.SPADES)
        ctx = EconomyContext(discarded_cards=[card])
        effect = joker.calculate_economy_effect(ctx, EffectTiming.ON_DISCARD)
        assert effect.money == 3

    def test_multiple_cards_no_bonus(self):
        """Should earn nothing when discarding multiple cards."""
        joker = create_joker("trading_card")
        cards = [Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.HEARTS)]
        ctx = EconomyContext(discarded_cards=cards)
        effect = joker.calculate_economy_effect(ctx, EffectTiming.ON_DISCARD)
        assert effect.money == 0


class TestFacelessJokerEconomy:
    """Test Faceless Joker economy effect."""

    def test_three_face_cards(self):
        """Should earn $5 when discarding 3+ face cards."""
        joker = create_joker("faceless_joker")
        cards = [
            Card(Rank.JACK, Suit.SPADES),
            Card(Rank.QUEEN, Suit.HEARTS),
            Card(Rank.KING, Suit.CLUBS),
        ]
        ctx = EconomyContext(discarded_cards=cards)
        effect = joker.calculate_economy_effect(ctx, EffectTiming.ON_DISCARD)
        assert effect.money == 5

    def test_two_face_cards(self):
        """Should earn nothing with only 2 face cards."""
        joker = create_joker("faceless_joker")
        cards = [
            Card(Rank.JACK, Suit.SPADES),
            Card(Rank.QUEEN, Suit.HEARTS),
        ]
        ctx = EconomyContext(discarded_cards=cards)
        effect = joker.calculate_economy_effect(ctx, EffectTiming.ON_DISCARD)
        assert effect.money == 0

    def test_mixed_cards(self):
        """Should only count face cards."""
        joker = create_joker("faceless_joker")
        cards = [
            Card(Rank.JACK, Suit.SPADES),
            Card(Rank.QUEEN, Suit.HEARTS),
            Card(Rank.ACE, Suit.CLUBS),  # Not a face card
            Card(Rank.TWO, Suit.DIAMONDS),
        ]
        ctx = EconomyContext(discarded_cards=cards)
        effect = joker.calculate_economy_effect(ctx, EffectTiming.ON_DISCARD)
        assert effect.money == 0


class TestMailInRebateEconomy:
    """Test Mail-In Rebate economy effect."""

    def test_matching_rank(self):
        """Should earn $5 per matching rank."""
        joker = create_joker("mail_in_rebate")
        joker.state["target_rank"] = 14  # Ace
        cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.HEARTS),
        ]
        ctx = EconomyContext(discarded_cards=cards)
        effect = joker.calculate_economy_effect(ctx, EffectTiming.ON_DISCARD)
        assert effect.money == 10  # 2 * $5

    def test_no_matching_rank(self):
        """Should earn nothing if no matching rank."""
        joker = create_joker("mail_in_rebate")
        joker.state["target_rank"] = 14  # Ace
        cards = [
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.QUEEN, Suit.HEARTS),
        ]
        ctx = EconomyContext(discarded_cards=cards)
        effect = joker.calculate_economy_effect(ctx, EffectTiming.ON_DISCARD)
        assert effect.money == 0


class TestToDoListEconomy:
    """Test To Do List economy effect."""

    def test_matching_hand(self):
        """Should earn $4 when hand matches target."""
        joker = create_joker("to_do_list")
        joker.state["target_hand"] = "FLUSH"
        ctx = EconomyContext(played_hand_type="FLUSH")
        effect = joker.calculate_economy_effect(ctx, EffectTiming.ON_HAND_PLAYED)
        assert effect.money == 4

    def test_non_matching_hand(self):
        """Should earn nothing when hand doesn't match."""
        joker = create_joker("to_do_list")
        joker.state["target_hand"] = "FLUSH"
        ctx = EconomyContext(played_hand_type="PAIR")
        effect = joker.calculate_economy_effect(ctx, EffectTiming.ON_HAND_PLAYED)
        assert effect.money == 0


class TestMatadorEconomy:
    """Test Matador economy effect."""

    def test_boss_triggered(self):
        """Should earn $8 when boss blind triggered."""
        joker = create_joker("matador")
        ctx = EconomyContext(boss_blind_triggered=True)
        effect = joker.calculate_economy_effect(ctx, EffectTiming.ON_HAND_PLAYED)
        assert effect.money == 8

    def test_boss_not_triggered(self):
        """Should earn nothing if boss not triggered."""
        joker = create_joker("matador")
        ctx = EconomyContext(boss_blind_triggered=False)
        effect = joker.calculate_economy_effect(ctx, EffectTiming.ON_HAND_PLAYED)
        assert effect.money == 0


class TestCalculateEndOfRoundEconomy:
    """Test calculate_end_of_round_economy helper."""

    def test_multiple_jokers(self):
        """Should sum money from multiple jokers."""
        jokers = [
            create_joker("golden_joker"),  # $4
            create_joker("cloud_9"),  # $4 (default 4 nines)
        ]
        ctx = EconomyContext(nines_in_deck=4)
        total = calculate_end_of_round_economy(jokers, ctx)
        assert total == 8

    def test_no_economy_jokers(self):
        """Should return 0 for non-economy jokers."""
        jokers = [
            create_joker("joker"),  # Just +4 mult, no economy
        ]
        ctx = EconomyContext()
        total = calculate_end_of_round_economy(jokers, ctx)
        assert total == 0


class TestCalculateDiscardEconomy:
    """Test calculate_discard_economy helper."""

    def test_faceless_joker(self):
        """Should calculate discard money."""
        jokers = [create_joker("faceless_joker")]
        cards = [
            Card(Rank.JACK, Suit.SPADES),
            Card(Rank.QUEEN, Suit.HEARTS),
            Card(Rank.KING, Suit.CLUBS),
        ]
        ctx = EconomyContext(discarded_cards=cards)
        total = calculate_discard_economy(jokers, ctx)
        assert total == 5


class TestCalculatePlayEconomy:
    """Test calculate_play_economy helper."""

    def test_to_do_list(self):
        """Should calculate play money."""
        jokers = [create_joker("to_do_list")]
        jokers[0].state["target_hand"] = "PAIR"
        ctx = EconomyContext(played_hand_type="PAIR")
        total = calculate_play_economy(jokers, ctx)
        assert total == 4


class TestEconomyCalculatorRegistry:
    """Test economy calculator registry."""

    def test_end_of_round_calculators(self):
        """Should have end of round calculators."""
        eor_keys = [k for k in ECONOMY_CALCULATORS if k[1] == EffectTiming.END_OF_ROUND]
        assert len(eor_keys) >= 7

    def test_discard_calculators(self):
        """Should have discard calculators."""
        discard_keys = [k for k in ECONOMY_CALCULATORS if k[1] == EffectTiming.ON_DISCARD]
        assert len(discard_keys) >= 3

    def test_hand_played_calculators(self):
        """Should have hand played calculators."""
        play_keys = [k for k in ECONOMY_CALCULATORS if k[1] == EffectTiming.ON_HAND_PLAYED]
        assert len(play_keys) >= 3
