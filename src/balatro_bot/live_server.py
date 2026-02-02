"""
Live Game Server - IPC communication with Balatro mod.

This module provides a TCP server that:
1. Receives game state from the Lua mod
2. Parses it into Python objects
3. Runs the decision engine (MCTS/heuristics)
4. Sends back action recommendations
"""

import json
import socket
import threading
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum

from .models import Card, Suit, Rank, Joker, GameState, HandType
from .heuristics import HeuristicPlayer, evaluate_plays, get_best_play
from .hand_evaluation import evaluate_hand, find_best_hand
from .scoring import calculate_score
from .jokers import create_joker, JokerInstance

logger = logging.getLogger(__name__)


class GamePhase(Enum):
    """Game phases from Balatro's G.STATE."""
    SELECTING_HAND = "SELECTING_HAND"
    HAND_PLAYED = "HAND_PLAYED"
    DRAW_TO_HAND = "DRAW_TO_HAND"
    SHOP = "SHOP"
    BLIND_SELECT = "BLIND_SELECT"
    NEW_ROUND = "NEW_ROUND"
    GAME_OVER = "GAME_OVER"
    TAROT_PACK = "TAROT_PACK"
    PLANET_PACK = "PLANET_PACK"
    SPECTRAL_PACK = "SPECTRAL_PACK"
    STANDARD_PACK = "STANDARD_PACK"
    BUFFOON_PACK = "BUFFOON_PACK"
    MENU = "MENU"
    SPLASH = "SPLASH"
    UNKNOWN = "UNKNOWN"


@dataclass
class LiveCard:
    """Card from live game state."""
    suit: str
    rank: int  # 2-14 (14=Ace)
    rank_name: str
    index: int
    enhancement: Optional[str] = None
    seal: Optional[str] = None
    edition: Optional[dict] = None
    debuff: bool = False
    highlighted: bool = False
    bonus_chips: int = 0
    bonus_mult: int = 0
    h_mult: float = 0
    h_x_mult: float = 1.0

    def to_model_card(self) -> Card:
        """Convert to simulation Card model."""
        # Map rank ID to Rank enum
        rank_map = {
            2: Rank.TWO, 3: Rank.THREE, 4: Rank.FOUR, 5: Rank.FIVE,
            6: Rank.SIX, 7: Rank.SEVEN, 8: Rank.EIGHT, 9: Rank.NINE,
            10: Rank.TEN, 11: Rank.JACK, 12: Rank.QUEEN,
            13: Rank.KING, 14: Rank.ACE
        }

        # Map suit string to Suit enum
        suit_map = {
            "Spades": Suit.SPADES, "Hearts": Suit.HEARTS,
            "Clubs": Suit.CLUBS, "Diamonds": Suit.DIAMONDS
        }

        return Card(
            rank=rank_map.get(self.rank, Rank.TWO),
            suit=suit_map.get(self.suit, Suit.SPADES)
        )


@dataclass
class LiveJoker:
    """Joker from live game state."""
    id: str
    name: str
    position: int
    cost: int = 0
    sell_cost: int = 0
    edition: Optional[dict] = None
    debuff: bool = False
    state: dict = field(default_factory=dict)

    def to_model_joker(self) -> Joker:
        """Convert to simulation Joker model."""
        return Joker(
            id=self.id,
            name=self.name,
            level=1,
        )


@dataclass
class LiveBlind:
    """Blind info from live game state."""
    name: str
    chips_required: int
    chips_scored: int = 0
    boss_id: Optional[str] = None
    triggered: bool = False
    disabled: bool = False
    blind_type: str = "Small"  # Small, Big, Boss


@dataclass
class LiveShopItem:
    """Shop item from live game state."""
    index: int
    name: str
    cost: int
    item_type: str
    joker_id: Optional[str] = None
    suit: Optional[str] = None
    rank: Optional[int] = None
    edition: Optional[str] = None


@dataclass
class LiveShop:
    """Shop state from live game."""
    items: list[LiveShopItem] = field(default_factory=list)
    vouchers: list[LiveShopItem] = field(default_factory=list)
    boosters: list[LiveShopItem] = field(default_factory=list)
    reroll_cost: int = 5


@dataclass
class LiveGameState:
    """Complete game state from live Balatro game."""
    # Phase
    phase: GamePhase
    phase_name: str

    # Progress
    ante: int
    round: int
    stake: int

    # Economy
    money: int

    # Resources
    hands_remaining: int
    discards_remaining: int
    hand_size: int

    # Cards
    hand: list[LiveCard] = field(default_factory=list)

    # Deck info
    cards_in_deck: int = 0
    cards_in_hand: int = 0
    cards_in_discard: int = 0
    nines_in_deck: int = 4  # For Cloud 9
    deck_name: Optional[str] = None

    # Jokers
    jokers: list[LiveJoker] = field(default_factory=list)

    # Consumables
    consumables: list[dict] = field(default_factory=list)

    # Blind
    blind: Optional[LiveBlind] = None

    # Shop (when in shop phase)
    shop: Optional[LiveShop] = None

    # Stats
    hands_played: int = 0
    cards_discarded: int = 0
    boss_blinds_defeated: int = 0
    blinds_skipped: int = 0

    # Hand levels
    hand_levels: dict = field(default_factory=dict)

    # Vouchers owned
    vouchers_owned: list[str] = field(default_factory=list)

    # Seed info
    seeded: bool = False
    seed: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> "LiveGameState":
        """Parse JSON data into LiveGameState."""
        # Parse phase
        phase_name = data.get("phase_name", "UNKNOWN")
        try:
            phase = GamePhase(phase_name)
        except ValueError:
            phase = GamePhase.UNKNOWN

        # Parse hand cards
        hand = []
        for card_data in data.get("hand", []):
            hand.append(LiveCard(
                suit=card_data.get("suit", "Spades"),
                rank=card_data.get("rank", 2),
                rank_name=card_data.get("rank_name", "2"),
                index=card_data.get("index", 0),
                enhancement=card_data.get("enhancement"),
                seal=card_data.get("seal"),
                edition=card_data.get("edition"),
                debuff=card_data.get("debuff", False),
                highlighted=card_data.get("highlighted", False),
                bonus_chips=card_data.get("bonus_chips", 0),
                bonus_mult=card_data.get("bonus_mult", 0),
                h_mult=card_data.get("h_mult", 0),
                h_x_mult=card_data.get("h_x_mult", 1.0),
            ))

        # Parse jokers
        jokers = []
        for joker_data in data.get("jokers", []):
            jokers.append(LiveJoker(
                id=joker_data.get("id", "unknown"),
                name=joker_data.get("name", "Unknown"),
                position=joker_data.get("position", 0),
                cost=joker_data.get("cost", 0),
                sell_cost=joker_data.get("sell_cost", 0),
                edition=joker_data.get("edition"),
                debuff=joker_data.get("debuff", False),
                state=joker_data.get("state", {}),
            ))

        # Parse blind
        blind = None
        blind_data = data.get("blind")
        if blind_data:
            blind = LiveBlind(
                name=blind_data.get("name", "Unknown"),
                chips_required=blind_data.get("chips_required", 0),
                chips_scored=blind_data.get("chips_scored", 0),
                boss_id=blind_data.get("boss_id"),
                triggered=blind_data.get("triggered", False),
                disabled=blind_data.get("disabled", False),
                blind_type=blind_data.get("blind_type", "Small"),
            )

        # Parse shop
        shop = None
        shop_data = data.get("shop")
        if shop_data:
            def parse_shop_item(item_data):
                return LiveShopItem(
                    index=item_data.get("index", 0),
                    name=item_data.get("name", "Unknown"),
                    cost=item_data.get("cost", 0),
                    item_type=item_data.get("item_type") or item_data.get("type", "Unknown"),
                    joker_id=item_data.get("joker_id"),
                    suit=item_data.get("suit"),
                    rank=item_data.get("rank"),
                    edition=item_data.get("edition"),
                )

            items = [parse_shop_item(i) for i in shop_data.get("items", [])]
            vouchers = [parse_shop_item(v) for v in shop_data.get("vouchers", [])]
            boosters = [parse_shop_item(b) for b in shop_data.get("boosters", [])]

            shop = LiveShop(
                items=items,
                vouchers=vouchers,
                boosters=boosters,
                reroll_cost=shop_data.get("reroll_cost", 5),
            )

        # Parse deck info
        deck_info = data.get("deck_info", {})

        # Parse stats
        stats = data.get("stats", {})

        return cls(
            phase=phase,
            phase_name=phase_name,
            ante=data.get("ante", 1),
            round=data.get("round", 0),
            stake=data.get("stake", 1),
            money=data.get("money", 0),
            hands_remaining=data.get("hands_remaining", 4),
            discards_remaining=data.get("discards_remaining", 3),
            hand_size=data.get("hand_size", 8),
            hand=hand,
            cards_in_deck=deck_info.get("cards_in_deck", 0),
            cards_in_hand=deck_info.get("cards_in_hand", 0),
            cards_in_discard=deck_info.get("cards_in_discard", 0),
            nines_in_deck=deck_info.get("nines_in_deck", 4),
            deck_name=deck_info.get("deck_name"),
            jokers=jokers,
            consumables=data.get("consumables", []),
            blind=blind,
            shop=shop,
            hands_played=stats.get("hands_played", 0),
            cards_discarded=stats.get("cards_discarded", 0),
            boss_blinds_defeated=stats.get("boss_blinds_defeated", 0),
            blinds_skipped=stats.get("blinds_skipped", 0),
            hand_levels=data.get("hand_levels", {}),
            vouchers_owned=data.get("vouchers_owned", []),
            seeded=data.get("seeded", False),
            seed=data.get("seed"),
        )

    def to_simulation_state(self) -> GameState:
        """Convert to simulation GameState for decision making."""
        # Convert hand cards
        cards = [card.to_model_card() for card in self.hand]

        # Convert jokers
        jokers = [joker.to_model_joker() for joker in self.jokers]

        # Create GameState
        return GameState(
            deck=cards,  # Current hand as "deck" for evaluation
            hand=cards,
            jokers=jokers,
            hands_remaining=self.hands_remaining,
            discards_remaining=self.discards_remaining,
            money=self.money,
            ante=self.ante,
            blind_requirement=self.blind.chips_required if self.blind else 300,
            current_chips=self.blind.chips_scored if self.blind else 0,
        )


@dataclass
class Action:
    """Action to send back to the game."""
    action_type: str  # play, discard, shop, blind, use_consumable
    card_indices: list[int] = field(default_factory=list)
    skip: bool = False
    reroll: bool = False
    buy_index: Optional[int] = None
    consumable_index: Optional[int] = None
    confidence: float = 0.0
    reasoning: str = ""

    def to_json(self) -> dict:
        """Convert to JSON for transmission."""
        return {
            "action_type": self.action_type,
            "card_indices": self.card_indices,
            "skip": self.skip,
            "reroll": self.reroll,
            "buy_index": self.buy_index,
            "consumable_index": self.consumable_index,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


class LiveDecisionEngine:
    """Decision engine for live game states."""

    def __init__(self):
        pass

    def decide(self, state: LiveGameState) -> Action:
        """Make a decision based on current game state."""
        if state.phase == GamePhase.SELECTING_HAND:
            return self._decide_hand(state)
        elif state.phase == GamePhase.SHOP:
            return self._decide_shop(state)
        elif state.phase == GamePhase.BLIND_SELECT:
            return self._decide_blind(state)
        elif state.phase in (GamePhase.TAROT_PACK, GamePhase.PLANET_PACK,
                             GamePhase.SPECTRAL_PACK, GamePhase.STANDARD_PACK,
                             GamePhase.BUFFOON_PACK):
            return self._decide_pack(state)
        else:
            return Action(action_type="wait", reasoning="Not at decision point")

    def _analyze_draw_potential(self, cards: list) -> dict:
        """Analyze hand for flush/straight draw potential."""
        from collections import Counter

        # Count suits
        suit_counts = Counter(c.suit for c in cards)
        best_suit = suit_counts.most_common(1)[0] if suit_counts else (None, 0)

        # Count ranks
        rank_counts = Counter(c.rank for c in cards)

        # Find cards of the most common suit (for flush draw)
        flush_suit = best_suit[0]
        flush_count = best_suit[1]
        flush_cards = [i for i, c in enumerate(cards) if c.suit == flush_suit]

        # Check for straight draw potential
        ranks = sorted(set(c.rank.value for c in cards))
        straight_potential = self._find_straight_draw(ranks)

        # Find pairs, trips, quads
        pairs = [(rank, count) for rank, count in rank_counts.items() if count >= 2]
        trips = [(rank, count) for rank, count in rank_counts.items() if count >= 3]

        return {
            "flush_suit": flush_suit,
            "flush_count": flush_count,
            "flush_cards": flush_cards,
            "straight_potential": straight_potential,
            "pairs": pairs,
            "trips": trips,
            "rank_counts": rank_counts,
            "suit_counts": suit_counts,
        }

    def _find_straight_draw(self, ranks: list) -> dict:
        """Find straight draw potential in sorted rank values."""
        if len(ranks) < 3:
            return {"type": None, "cards_needed": 5}

        # Check for connected cards (within range of 5)
        best_run = []
        for start_idx in range(len(ranks)):
            run = [ranks[start_idx]]
            for j in range(start_idx + 1, len(ranks)):
                if ranks[j] - run[-1] <= 2 and ranks[j] - run[0] < 5:
                    run.append(ranks[j])
            if len(run) > len(best_run):
                best_run = run

        # Also check Ace-low straight (A-2-3-4-5)
        if 14 in ranks:  # Ace
            low_ranks = [r for r in ranks if r <= 5] + [1]  # Ace counts as 1
            if len(low_ranks) >= 3:
                low_run = sorted(set(low_ranks))
                if len(low_run) > len(best_run):
                    best_run = low_run

        cards_needed = 5 - len(best_run)
        if cards_needed <= 2:
            return {"type": "open-ended" if cards_needed == 1 else "gutshot",
                    "cards_needed": cards_needed, "run": best_run}
        return {"type": None, "cards_needed": cards_needed}

    def _decide_discard(self, cards: list, state: LiveGameState,
                        hand_result, best_indices: list) -> tuple[list, str]:
        """Determine which cards to discard and why."""
        analysis = self._analyze_draw_potential(cards)

        keep_indices = set()
        reasons = []

        # Priority 1: Keep trips or better
        if analysis["trips"]:
            trip_rank = analysis["trips"][0][0]
            for i, c in enumerate(cards):
                if c.rank == trip_rank:
                    keep_indices.add(i)
            reasons.append(f"keeping triple {analysis['trips'][0][0]}")

        # Priority 2: Four-to-a-flush (keep all suited cards)
        elif analysis["flush_count"] >= 4:
            keep_indices.update(analysis["flush_cards"])
            reasons.append(f"{analysis['flush_count']}x {analysis['flush_suit']} = flush draw!")

        # Priority 3: Straight draw (4 connected)
        elif analysis["straight_potential"]["type"]:
            sp = analysis["straight_potential"]
            # Keep cards that are part of the straight draw
            for i, c in enumerate(cards):
                if c.rank.value in sp.get("run", []) or (c.rank.value == 14 and 1 in sp.get("run", [])):
                    keep_indices.add(i)
            reasons.append(f"{sp['type']} straight draw (need {sp['cards_needed']})")

        # Priority 4: Keep pairs
        elif analysis["pairs"]:
            for pair_rank, count in analysis["pairs"]:
                for i, c in enumerate(cards):
                    if c.rank == pair_rank:
                        keep_indices.add(i)
            pair_names = [str(p[0]) for p in analysis["pairs"]]
            reasons.append(f"keeping pair(s): {', '.join(pair_names)}")

        # Priority 5: Three-to-a-flush with high cards
        elif analysis["flush_count"] >= 3:
            flush_cards_obj = [cards[i] for i in analysis["flush_cards"]]
            high_flush = [c for c in flush_cards_obj if c.rank.value >= 10]
            if len(high_flush) >= 2:
                keep_indices.update(analysis["flush_cards"])
                reasons.append(f"3x {analysis['flush_suit']} with high cards")

        # Priority 6: Keep high cards (J, Q, K, A)
        if not keep_indices:
            for i, c in enumerate(cards):
                if c.rank.value >= 11:  # J, Q, K, A
                    keep_indices.add(i)
            if keep_indices:
                high_names = [str(cards[i].rank) for i in keep_indices]
                reasons.append(f"keeping high: {', '.join(high_names)}")

        # Determine which cards to discard
        discard_indices = [i for i in range(len(cards)) if i not in keep_indices]
        discard_indices = discard_indices[:5]  # Max 5 discards

        # Build detailed reasoning
        discard_cards = [str(cards[i]) for i in discard_indices]
        keep_cards = [str(cards[i]) for i in keep_indices]

        reason_str = "; ".join(reasons) if reasons else "no strong keeps"
        full_reason = f"{reason_str} | DISCARD: {', '.join(discard_cards)} | KEEP: {', '.join(keep_cards)}"

        return discard_indices, full_reason

    def _decide_hand(self, state: LiveGameState) -> Action:
        """Decide which cards to play or discard."""
        cards = [card.to_model_card() for card in state.hand]

        if not cards:
            return Action(action_type="wait", reasoning="No cards in hand")

        # Find best hand
        best_cards, hand_result = find_best_hand(cards)
        if not best_cards or not hand_result:
            return Action(
                action_type="play",
                card_indices=[0],
                confidence=0.1,
                reasoning="No valid hand found, playing first card"
            )

        # Get indices of cards in best hand
        best_indices = []
        for bc in best_cards:
            for i, c in enumerate(cards):
                if c.rank == bc.rank and c.suit == bc.suit and i not in best_indices:
                    best_indices.append(i)
                    break

        # Convert jokers to JokerInstances for scoring
        joker_instances = []
        for lj in state.jokers:
            # Try different ID formats: raw, without j_ prefix, normalized
            joker_id = lj.id
            normalized_id = joker_id.lower().replace(" ", "_").replace("-", "_")
            if normalized_id.startswith("j_"):
                normalized_id = normalized_id[2:]

            for try_id in [joker_id, normalized_id]:
                try:
                    joker_inst = create_joker(try_id)
                    joker_inst.state = lj.state.copy() if lj.state else {}
                    joker_instances.append(joker_inst)
                    logger.info(f"Loaded joker: {lj.name} (id={try_id})")
                    break
                except ValueError:
                    continue
            else:
                logger.warning(f"Unknown joker ID: {lj.id} (normalized: {normalized_id}), skipping")

        # Create minimal game state for scoring
        game_state = GameState(
            hand=cards,
            hand_levels=state.hand_levels.copy() if state.hand_levels else {},
            ante=state.ante,
            hands_remaining=state.hands_remaining,
            discards_remaining=state.discards_remaining,
        )

        # Calculate score with joker effects
        remaining_cards = [c for i, c in enumerate(cards) if i not in best_indices]
        breakdown = calculate_score(
            played_cards=best_cards,
            jokers=joker_instances,
            game_state=game_state,
            cards_in_hand=remaining_cards,
        )
        best_score = breakdown.final_score

        # Log scoring details
        if joker_instances:
            joker_names = [j.name for j in joker_instances]
            logger.info(f"Scoring: base={breakdown.base_chips}x{breakdown.base_mult}, "
                       f"final={breakdown.final_chips}x{breakdown.final_mult}={best_score}, "
                       f"jokers={joker_names}")
            if breakdown.joker_effects:
                for je in breakdown.joker_effects:
                    logger.info(f"  Joker effect: {je}")

        # Consider discarding if hand is weak and we have discards
        if state.discards_remaining > 0 and state.hands_remaining > 1:
            weak_hands = (HandType.HIGH_CARD, HandType.PAIR, HandType.TWO_PAIR)
            if hand_result and hand_result.hand_type in weak_hands:
                discard_indices, discard_reason = self._decide_discard(
                    cards, state, hand_result, best_indices
                )
                if discard_indices:
                    return Action(
                        action_type="discard",
                        card_indices=discard_indices,
                        confidence=0.6,
                        reasoning=f"{hand_result.hand_type.name} | {discard_reason}"
                    )

        # Play the best hand
        if best_indices:
            card_names = [str(cards[i]) for i in best_indices]
            return Action(
                action_type="play",
                card_indices=best_indices,
                confidence=min(1.0, best_score / 1000),
                reasoning=f"{hand_result.hand_type.name} ({', '.join(card_names)}) ~{best_score} chips"
            )

        return Action(
            action_type="play",
            card_indices=[0],
            confidence=0.1,
            reasoning="No good options, playing first card"
        )

    def _decide_shop(self, state: LiveGameState) -> Action:
        """Decide what to buy in the shop."""
        if not state.shop:
            return Action(action_type="wait", reasoning="Waiting for shop to load...")

        # Build summary of available items
        all_items = (state.shop.items or []) + (state.shop.vouchers or []) + (state.shop.boosters or [])

        if not all_items:
            return Action(
                action_type="wait",
                reasoning=f"Shop loading... | ${state.money}"
            )

        # Categorize items
        jokers = [i for i in all_items if i.item_type == "Joker"]
        planets = [i for i in all_items if i.item_type == "Planet"]
        tarots = [i for i in all_items if i.item_type == "Tarot"]
        vouchers = [i for i in all_items if i.item_type == "Voucher"]
        boosters = [i for i in all_items if i.item_type == "Booster"]

        # Build shop summary
        shop_summary = []
        if jokers:
            joker_names = [f"{j.name}(${j.cost})" for j in jokers]
            shop_summary.append(f"Jokers: {', '.join(joker_names)}")
        if planets:
            planet_names = [f"{p.name}(${p.cost})" for p in planets]
            shop_summary.append(f"Planets: {', '.join(planet_names)}")
        if tarots:
            tarot_names = [f"{t.name}(${t.cost})" for t in tarots]
            shop_summary.append(f"Tarots: {', '.join(tarot_names)}")
        if vouchers:
            voucher_names = [f"{v.name}(${v.cost})" for v in vouchers]
            shop_summary.append(f"Vouchers: {', '.join(voucher_names)}")
        if boosters:
            booster_names = [f"{b.name}(${b.cost})" for b in boosters]
            shop_summary.append(f"Packs: {', '.join(booster_names)}")

        shop_str = " | ".join(shop_summary) if shop_summary else "Empty shop"
        money_str = f"${state.money}"

        # Priority 1: Buy jokers if affordable (early game priority)
        affordable_jokers = [j for j in jokers if j.cost <= state.money]
        if affordable_jokers and len(state.jokers) < 5:
            best_joker = affordable_jokers[0]
            return Action(
                action_type="shop",
                buy_index=best_joker.index,
                confidence=0.8,
                reasoning=f"BUY {best_joker.name} (${best_joker.cost}) | {money_str} | {shop_str}"
            )

        # Priority 2: Buy planet cards
        affordable_planets = [p for p in planets if p.cost <= state.money]
        if affordable_planets:
            best_planet = affordable_planets[0]
            return Action(
                action_type="shop",
                buy_index=best_planet.index,
                confidence=0.6,
                reasoning=f"BUY {best_planet.name} (${best_planet.cost}) | {money_str} | {shop_str}"
            )

        # Priority 3: Buy tarot cards
        affordable_tarots = [t for t in tarots if t.cost <= state.money]
        if affordable_tarots:
            best_tarot = affordable_tarots[0]
            return Action(
                action_type="shop",
                buy_index=best_tarot.index,
                confidence=0.5,
                reasoning=f"BUY {best_tarot.name} (${best_tarot.cost}) | {money_str} | {shop_str}"
            )

        # Priority 4: Reroll if we have money and nothing good
        reroll_cost = state.shop.reroll_cost
        if state.money >= reroll_cost + 5:
            return Action(
                action_type="shop",
                reroll=True,
                confidence=0.4,
                reasoning=f"REROLL (${reroll_cost}) | {money_str} | {shop_str}"
            )

        # Skip shop
        return Action(
            action_type="shop",
            skip=True,
            confidence=0.8,
            reasoning=f"SKIP | {money_str} | {shop_str}"
        )

    def _decide_blind(self, state: LiveGameState) -> Action:
        """Decide whether to skip or select blind."""
        # Simple heuristic: skip small blind if we have enough jokers
        # In reality this needs more sophisticated analysis

        if len(state.jokers) >= 3 and state.ante <= 3:
            # Skip small blind early for tag rewards
            return Action(
                action_type="blind",
                skip=True,
                confidence=0.5,
                reasoning="Skipping blind for tag reward"
            )

        return Action(
            action_type="blind",
            skip=False,
            confidence=0.8,
            reasoning="Playing blind"
        )

    def _decide_pack(self, state: LiveGameState) -> Action:
        """Decide which cards to take from a pack."""
        # For now, just skip (more sophisticated logic needed)
        return Action(
            action_type="pack",
            skip=True,
            confidence=0.5,
            reasoning="Pack selection not implemented"
        )


class LiveServer:
    """TCP server for communication with Balatro mod."""

    def __init__(self, host: str = "127.0.0.1", port: int = 12345):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.decision_engine = LiveDecisionEngine()
        self.on_state_received: Optional[Callable[[LiveGameState], None]] = None
        self.on_action_sent: Optional[Callable[[Action], None]] = None

    def start(self):
        """Start the server."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(1)
        self.running = True

        logger.info(f"Live server started on {self.host}:{self.port}")
        print(f"BalatroBot server listening on {self.host}:{self.port}")

        while self.running:
            try:
                client, address = self.socket.accept()
                logger.info(f"Connection from {address}")
                print(f"Client connected from {address}")
                self._handle_client(client)
            except OSError:
                break
            except Exception as e:
                logger.error(f"Error accepting connection: {e}")

    def _handle_client(self, client: socket.socket):
        """Handle a client connection."""
        buffer = ""

        while self.running:
            try:
                data = client.recv(4096).decode("utf-8")
                if not data:
                    break

                buffer += data

                # Check for complete JSON message (newline-delimited)
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        self._process_message(client, line.strip())

            except ConnectionResetError:
                logger.info("Client disconnected")
                break
            except Exception as e:
                logger.error(f"Error handling client: {e}")
                break

        client.close()

    def _process_message(self, client: socket.socket, message: str):
        """Process a JSON message from the client."""
        try:
            data = json.loads(message)

            # Debug: log raw data
            if "shop" in data and data["shop"]:
                print(f"DEBUG: Shop data received: {data['shop']}")

            # Parse state
            state = LiveGameState.from_json(data)

            if self.on_state_received:
                self.on_state_received(state)

            logger.debug(f"Received state: {state.phase_name}, Ante {state.ante}")

            # Make decision
            action = self.decision_engine.decide(state)

            if self.on_action_sent:
                self.on_action_sent(action)

            # Send response
            response = json.dumps(action.to_json()) + "\n"
            client.send(response.encode("utf-8"))

            logger.debug(f"Sent action: {action.action_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
        except Exception as e:
            logger.exception(f"Error processing message: {e}")

    def stop(self):
        """Stop the server."""
        self.running = False
        if self.socket:
            self.socket.close()
        logger.info("Server stopped")


def run_server(host: str = "127.0.0.1", port: int = 12345):
    """Run the live server (blocking)."""
    server = LiveServer(host, port)

    def on_state(state: LiveGameState):
        base_info = (f"State: {state.phase_name} | Ante {state.ante} | ${state.money} | "
                     f"{state.hands_remaining}H/{state.discards_remaining}D | "
                     f"{len(state.hand)} cards | {len(state.jokers)} jokers")

        # Add shop info if in shop
        if state.phase_name == "SHOP" and state.shop:
            shop_info = (f" | Shop: {len(state.shop.items)} items, "
                        f"{len(state.shop.vouchers)} vouchers, "
                        f"{len(state.shop.boosters)} boosters")
            print(base_info + shop_info)
        else:
            print(base_info)

    def on_action(action: Action):
        print(f"Action: {action.action_type} | {action.reasoning}")

    server.on_state_received = on_state
    server.on_action_sent = on_action

    try:
        server.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_server()
