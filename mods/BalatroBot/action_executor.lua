--[[
    BalatroBot - Action Executor

    Executes bot decisions by interacting with Balatro's game functions.
    Handles card selection, playing, discarding, shop actions, etc.
]]

local action_executor = {}

-------------------------------------------------------------------------------
-- Card Selection Helpers
-------------------------------------------------------------------------------

local function clear_highlights()
    -- Deselect all cards in hand
    if G and G.hand and G.hand.cards then
        for _, card in ipairs(G.hand.cards) do
            if card.highlighted then
                card:click()  -- Toggle off
            end
        end
    end
end

local function select_cards_by_indices(indices)
    if not G or not G.hand or not G.hand.cards then
        return false, "Hand not available"
    end

    -- Clear existing selection
    clear_highlights()

    -- Select specified cards (indices are 0-based from Python)
    for _, idx in ipairs(indices) do
        local lua_idx = idx + 1  -- Convert to 1-based
        local card = G.hand.cards[lua_idx]
        if card then
            if not card.highlighted then
                card:click()
            end
        else
            print("[BalatroBot] Warning: Card at index " .. idx .. " not found")
        end
    end

    return true
end

-------------------------------------------------------------------------------
-- Action Handlers
-------------------------------------------------------------------------------

local function execute_play(action)
    local indices = action.card_indices or {}

    if #indices == 0 then
        return false, "No cards specified to play"
    end

    -- Select the cards
    local ok, err = select_cards_by_indices(indices)
    if not ok then
        return false, err
    end

    -- Small delay for selection to register
    -- (In practice, might need to wait a frame)

    -- Trigger play
    if G.FUNCS and G.FUNCS.play_cards_from_highlighted then
        G.FUNCS.play_cards_from_highlighted()
        return true
    else
        return false, "play_cards_from_highlighted not available"
    end
end

local function execute_discard(action)
    local indices = action.card_indices or {}

    if #indices == 0 then
        return false, "No cards specified to discard"
    end

    -- Check if discards remaining
    if G.GAME and G.GAME.current_round then
        if G.GAME.current_round.discards_left <= 0 then
            return false, "No discards remaining"
        end
    end

    -- Select the cards
    local ok, err = select_cards_by_indices(indices)
    if not ok then
        return false, err
    end

    -- Trigger discard
    if G.FUNCS and G.FUNCS.discard_cards_from_highlighted then
        G.FUNCS.discard_cards_from_highlighted()
        return true
    else
        return false, "discard_cards_from_highlighted not available"
    end
end

local function execute_shop(action)
    if action.skip then
        -- Skip/Leave shop
        if G.FUNCS and G.FUNCS.skip_booster then
            G.FUNCS.skip_booster()  -- This actually skips shop too
            return true
        elseif G.FUNCS and G.FUNCS.toggle_shop then
            G.FUNCS.toggle_shop()  -- Alternative
            return true
        end
        return false, "Cannot skip shop"

    elseif action.reroll then
        -- Reroll shop
        if G.FUNCS and G.FUNCS.reroll_shop then
            G.FUNCS.reroll_shop()
            return true
        end
        return false, "Cannot reroll shop"

    elseif action.buy_index ~= nil then
        -- Buy item at index
        local lua_idx = action.buy_index + 1  -- Convert to 1-based

        if G.shop and G.shop.cards and G.shop.cards[lua_idx] then
            local card = G.shop.cards[lua_idx]
            -- Check if we can afford it
            if G.GAME and G.GAME.dollars and card.cost then
                if G.GAME.dollars >= card.cost then
                    card:click()  -- Buying is usually just clicking
                    return true
                else
                    return false, "Cannot afford item"
                end
            end
        end
        return false, "Shop item not found at index " .. action.buy_index

    elseif action.buy_voucher_index ~= nil then
        -- Buy voucher
        local lua_idx = action.buy_voucher_index + 1
        if G.shop_vouchers and G.shop_vouchers.cards and G.shop_vouchers.cards[lua_idx] then
            G.shop_vouchers.cards[lua_idx]:click()
            return true
        end
        return false, "Voucher not found"

    elseif action.buy_booster_index ~= nil then
        -- Buy booster pack
        local lua_idx = action.buy_booster_index + 1
        if G.shop_booster and G.shop_booster.cards and G.shop_booster.cards[lua_idx] then
            G.shop_booster.cards[lua_idx]:click()
            return true
        end
        return false, "Booster not found"
    end

    return false, "Invalid shop action"
end

local function execute_blind(action)
    if action.skip then
        -- Skip blind
        if G.FUNCS and G.FUNCS.skip_blind then
            G.FUNCS.skip_blind()
            return true
        end
        return false, "Cannot skip blind"
    else
        -- Select/play blind
        if G.FUNCS and G.FUNCS.select_blind then
            G.FUNCS.select_blind()
            return true
        end
        return false, "Cannot select blind"
    end
end

local function execute_use_consumable(action)
    local idx = action.consumable_index
    if idx == nil then
        return false, "No consumable index specified"
    end

    local lua_idx = idx + 1

    if not G.consumeables or not G.consumeables.cards then
        return false, "Consumables not available"
    end

    local consumable = G.consumeables.cards[lua_idx]
    if not consumable then
        return false, "Consumable not found at index " .. idx
    end

    -- Some consumables need targets (cards to apply to)
    local target_indices = action.target_card_indices or {}

    if #target_indices > 0 then
        -- Select target cards first
        select_cards_by_indices(target_indices)
    end

    -- Use the consumable
    if G.FUNCS and G.FUNCS.use_card then
        G.FUNCS.use_card({ config = { ref_table = consumable } })
        return true
    else
        -- Try clicking the consumable
        consumable:click()
        return true
    end
end

local function execute_sell(action)
    local idx = action.joker_index
    if idx == nil then
        return false, "No joker index specified"
    end

    local lua_idx = idx + 1

    if not G.jokers or not G.jokers.cards then
        return false, "Jokers not available"
    end

    local joker = G.jokers.cards[lua_idx]
    if not joker then
        return false, "Joker not found at index " .. idx
    end

    -- Check if eternal
    if joker.ability and joker.ability.eternal then
        return false, "Cannot sell eternal joker"
    end

    -- Sell the joker
    if G.FUNCS and G.FUNCS.sell_card then
        G.FUNCS.sell_card({ config = { ref_table = joker } })
        return true
    end

    return false, "Cannot sell joker"
end

local function execute_booster_select(action)
    -- When opening a booster pack, select cards to take
    local indices = action.card_indices or {}

    -- TODO: Implement booster pack card selection
    -- This depends on the pack type and available cards

    return false, "Booster selection not implemented"
end

-------------------------------------------------------------------------------
-- Main Execution
-------------------------------------------------------------------------------

function action_executor.execute(action)
    if not action then
        return false, "No action provided"
    end

    local action_type = action.action_type

    print("[BalatroBot] Executing: " .. tostring(action_type))

    if action_type == "play" then
        return execute_play(action)

    elseif action_type == "discard" then
        return execute_discard(action)

    elseif action_type == "shop" then
        return execute_shop(action)

    elseif action_type == "blind" then
        return execute_blind(action)

    elseif action_type == "use_consumable" then
        return execute_use_consumable(action)

    elseif action_type == "sell" then
        return execute_sell(action)

    elseif action_type == "booster_select" then
        return execute_booster_select(action)

    elseif action_type == "wait" then
        -- Do nothing, just wait
        return true

    else
        return false, "Unknown action type: " .. tostring(action_type)
    end
end

-------------------------------------------------------------------------------
-- Debug Helpers
-------------------------------------------------------------------------------

function action_executor.test_play(card_indices)
    return execute_play({ card_indices = card_indices })
end

function action_executor.test_discard(card_indices)
    return execute_discard({ card_indices = card_indices })
end

return action_executor
