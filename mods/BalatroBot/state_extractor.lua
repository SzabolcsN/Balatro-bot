--[[
    BalatroBot - State Extractor

    Extracts the complete game state from Balatro's global G object
    and formats it for transmission to the Python bot.
]]

local state_extractor = {}

local utils = require("BalatroBot.utils")

-------------------------------------------------------------------------------
-- Card Extraction
-------------------------------------------------------------------------------

local function extract_card(card)
    if not card then return nil end

    local data = {
        -- Base card info
        suit = card.base and card.base.suit,
        rank = card.base and card.base.id,  -- 2-14 (14=Ace)
        rank_name = card.base and card.base.value,

        -- Unique identifier
        sort_id = card.sort_id,

        -- Enhancement
        enhancement = nil,

        -- Seal
        seal = card.seal,

        -- Edition
        edition = nil,

        -- State
        debuff = card.debuff or false,
        facing = card.facing or "front",
        highlighted = card.highlighted or false,
    }

    -- Extract enhancement from ability
    if card.ability then
        local effect = card.ability.effect
        if effect then
            data.enhancement = effect
        end

        -- Copy enhancement-specific values
        data.bonus_chips = card.ability.bonus
        data.bonus_mult = card.ability.mult
        data.h_mult = card.ability.h_mult
        data.h_x_mult = card.ability.h_x_mult
    end

    -- Extract edition
    if card.edition then
        data.edition = {
            type = card.edition.type,
            chips = card.edition.chips,
            mult = card.edition.mult,
            x_mult = card.edition.x_mult,
        }
    end

    return data
end

local function extract_cards(cards)
    if not cards then return {} end

    local result = {}
    for i, card in ipairs(cards) do
        local data = extract_card(card)
        if data then
            data.index = i - 1  -- 0-indexed for Python
            table.insert(result, data)
        end
    end
    return result
end

-------------------------------------------------------------------------------
-- Joker Extraction
-------------------------------------------------------------------------------

local function extract_joker(joker, position)
    if not joker then return nil end

    local data = {
        -- Identification
        id = joker.config and joker.config.center and joker.config.center.key,
        name = joker.config and joker.config.center and joker.config.center.name,
        position = position,  -- Order matters!

        -- Economy
        cost = joker.cost,
        sell_cost = joker.sell_cost,

        -- Unique identifier
        sort_id = joker.sort_id,

        -- Edition
        edition = nil,

        -- Debuff
        debuff = joker.debuff or false,

        -- Current state (for scaling/conditional jokers)
        state = {},
    }

    -- Extract edition
    if joker.edition then
        data.edition = {
            type = joker.edition.type,
            chips = joker.edition.chips,
            mult = joker.edition.mult,
            x_mult = joker.edition.x_mult,
        }
    end

    -- Extract ability state
    if joker.ability then
        local ability = joker.ability

        -- Static bonuses
        data.state.mult = ability.mult or 0
        data.state.chips = ability.chips or 0
        data.state.x_mult = ability.x_mult or 1

        -- Dynamic targets (for conditional jokers)
        data.state.target_suit = ability.suit
        data.state.target_rank = ability.rank
        data.state.target_hand = ability.poker_hand

        -- Counters
        data.state.counter = ability.extra and ability.extra.counter or ability.counter or 0

        -- Stickers
        data.state.eternal = ability.eternal or false
        data.state.perishable = ability.perishable or false
        data.state.rental = ability.rental or false

        -- Extra joker-specific data
        if ability.extra then
            data.state.extra = utils.shallow_copy(ability.extra)
        end
    end

    return data
end

local function extract_jokers(joker_area)
    if not joker_area or not joker_area.cards then return {} end

    local result = {}
    for i, joker in ipairs(joker_area.cards) do
        local data = extract_joker(joker, i)  -- 1-indexed position (order matters!)
        if data then
            table.insert(result, data)
        end
    end
    return result
end

-------------------------------------------------------------------------------
-- Consumable Extraction
-------------------------------------------------------------------------------

local function extract_consumable(consumable, index)
    if not consumable then return nil end

    return {
        id = consumable.config and consumable.config.center and consumable.config.center.key,
        name = consumable.label,
        index = index - 1,  -- 0-indexed for Python
        type = consumable.ability and consumable.ability.set,  -- Tarot, Planet, Spectral
        cost = consumable.cost,
        sell_cost = consumable.sell_cost,
    }
end

local function extract_consumables(consumable_area)
    if not consumable_area or not consumable_area.cards then return {} end

    local result = {}
    for i, consumable in ipairs(consumable_area.cards) do
        local data = extract_consumable(consumable, i)
        if data then
            table.insert(result, data)
        end
    end
    return result
end

-------------------------------------------------------------------------------
-- Blind Extraction
-------------------------------------------------------------------------------

local function extract_blind_info()
    if not G or not G.GAME then return nil end

    local blind = G.GAME.blind
    if not blind then return nil end

    return {
        name = blind.name,
        chips_required = blind.chips,
        chips_scored = G.GAME.chips or 0,

        -- Boss blind info
        boss_id = blind.config and blind.config.blind and blind.config.blind.key,
        triggered = blind.triggered or false,
        disabled = blind.disabled or false,

        -- Current blind type
        blind_type = G.GAME.blind_on_deck,  -- "Small", "Big", "Boss"
    }
end

local function extract_blind_states()
    if not G or not G.GAME or not G.GAME.round_resets then return {} end

    local states = G.GAME.round_resets.blind_states
    if not states then return {} end

    return {
        small = states.Small,
        big = states.Big,
        boss = states.Boss,
    }
end

-------------------------------------------------------------------------------
-- Shop Extraction
-------------------------------------------------------------------------------

local function extract_shop_item(item, index)
    if not item then return nil end

    local data = {
        index = index - 1,
        name = item.label,
        cost = item.cost,
        type = item.ability and item.ability.set,  -- Joker, Tarot, Planet, etc.
    }

    -- For playing cards
    if item.ability and item.ability.set == "Playing" then
        data.suit = item.base and item.base.suit
        data.rank = item.base and item.base.id
        data.enhancement = item.ability and item.ability.effect
        data.seal = item.seal
    end

    -- For jokers
    if item.ability and item.ability.set == "Joker" then
        data.joker_id = item.config and item.config.center and item.config.center.key
        if item.edition then
            data.edition = item.edition.type
        end
    end

    return data
end

local function extract_shop()
    if not G or not G.shop or not G.shop.cards then return nil end

    local items = {}
    for i, item in ipairs(G.shop.cards) do
        local data = extract_shop_item(item, i)
        if data then
            table.insert(items, data)
        end
    end

    -- Vouchers
    local vouchers = {}
    if G.shop_vouchers and G.shop_vouchers.cards then
        for i, voucher in ipairs(G.shop_vouchers.cards) do
            table.insert(vouchers, {
                index = i - 1,
                id = voucher.config and voucher.config.center and voucher.config.center.key,
                name = voucher.label,
                cost = voucher.cost,
            })
        end
    end

    -- Booster packs
    local boosters = {}
    if G.shop_booster and G.shop_booster.cards then
        for i, booster in ipairs(G.shop_booster.cards) do
            table.insert(boosters, {
                index = i - 1,
                name = booster.label,
                cost = booster.cost,
            })
        end
    end

    return {
        items = items,
        vouchers = vouchers,
        boosters = boosters,
        reroll_cost = G.GAME and G.GAME.round_resets and G.GAME.round_resets.reroll_cost,
    }
end

-------------------------------------------------------------------------------
-- Game Stats Extraction
-------------------------------------------------------------------------------

local function extract_stats()
    if not G or not G.GAME then return {} end

    return {
        hands_played = G.GAME.hands_played or 0,
        cards_discarded = G.GAME.cards_discarded or 0,
        boss_blinds_defeated = utils.count_defeated_bosses(),
        blinds_skipped = utils.count_skipped_blinds(),
    }
end

-------------------------------------------------------------------------------
-- Hand Levels Extraction
-------------------------------------------------------------------------------

local function extract_hand_levels()
    if not G or not G.GAME or not G.GAME.hands then return {} end

    local levels = {}
    for hand_type, data in pairs(G.GAME.hands) do
        levels[hand_type] = {
            level = data.level or 1,
            chips = data.chips,
            mult = data.mult,
            played = data.played or 0,
        }
    end
    return levels
end

-------------------------------------------------------------------------------
-- Deck Info Extraction
-------------------------------------------------------------------------------

local function extract_deck_info()
    local info = {
        deck_name = nil,
        cards_in_deck = 0,
        cards_in_hand = 0,
        cards_in_discard = 0,
        nines_in_deck = 0,  -- For Cloud 9
    }

    if G and G.GAME and G.GAME.selected_back then
        info.deck_name = G.GAME.selected_back.name
    end

    -- Count cards in various areas
    if G then
        if G.deck and G.deck.cards then
            info.cards_in_deck = #G.deck.cards
            -- Count 9s for Cloud 9
            for _, card in ipairs(G.deck.cards) do
                if card.base and card.base.id == 9 then
                    info.nines_in_deck = info.nines_in_deck + 1
                end
            end
        end

        if G.hand and G.hand.cards then
            info.cards_in_hand = #G.hand.cards
            -- Also count 9s in hand
            for _, card in ipairs(G.hand.cards) do
                if card.base and card.base.id == 9 then
                    info.nines_in_deck = info.nines_in_deck + 1
                end
            end
        end

        if G.discard and G.discard.cards then
            info.cards_in_discard = #G.discard.cards
            -- And in discard
            for _, card in ipairs(G.discard.cards) do
                if card.base and card.base.id == 9 then
                    info.nines_in_deck = info.nines_in_deck + 1
                end
            end
        end
    end

    return info
end

-------------------------------------------------------------------------------
-- Main Extraction Function
-------------------------------------------------------------------------------

function state_extractor.extract()
    -- Check if game is loaded
    if not G then
        return nil, "G not available"
    end

    -- Build state object
    local state = {
        -- Game phase
        phase = G.STATE,
        phase_name = utils.get_phase_name(G.STATE),

        -- Ante and round
        ante = G.GAME and G.GAME.round_resets and G.GAME.round_resets.ante or 1,
        round = G.GAME and G.GAME.round or 0,
        stake = G.GAME and G.GAME.stake or 1,

        -- Economy
        money = G.GAME and G.GAME.dollars or 0,

        -- Resources
        hands_remaining = G.GAME and G.GAME.current_round and G.GAME.current_round.hands_left or 0,
        discards_remaining = G.GAME and G.GAME.current_round and G.GAME.current_round.discards_left or 0,
        hand_size = G.GAME and G.GAME.current_round and G.GAME.current_round.hand_size or 8,

        -- Cards
        hand = extract_cards(G.hand and G.hand.cards),
        deck_info = extract_deck_info(),

        -- Jokers (with current state!)
        jokers = extract_jokers(G.jokers),

        -- Consumables
        consumables = extract_consumables(G.consumeables),

        -- Blind
        blind = extract_blind_info(),
        blind_states = extract_blind_states(),

        -- Shop (if in shop phase)
        shop = nil,

        -- Stats
        stats = extract_stats(),

        -- Hand levels
        hand_levels = extract_hand_levels(),

        -- Vouchers owned
        vouchers_owned = G.GAME and G.GAME.used_vouchers or {},

        -- Seeded run info
        seeded = G.GAME and G.GAME.seeded or false,
        seed = G.GAME and G.GAME.pseudorandom and G.GAME.pseudorandom.seed,
    }

    -- Add shop info if in shop
    if G.STATE == G.STATES.SHOP then
        state.shop = extract_shop()
    end

    return state, nil
end

-------------------------------------------------------------------------------
-- Specific Extractors (for targeted queries)
-------------------------------------------------------------------------------

function state_extractor.extract_hand()
    return extract_cards(G and G.hand and G.hand.cards)
end

function state_extractor.extract_jokers()
    return extract_jokers(G and G.jokers)
end

function state_extractor.extract_shop()
    return extract_shop()
end

function state_extractor.extract_blind()
    return extract_blind_info()
end

return state_extractor
