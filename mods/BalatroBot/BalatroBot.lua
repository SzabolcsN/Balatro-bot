--- STEAMODDED HEADER
--- MOD_NAME: BalatroBot
--- MOD_ID: BalatroBot
--- MOD_AUTHOR: [BalatroBot]
--- MOD_DESCRIPTION: AI assistant for Balatro - displays play recommendations
--- PRIORITY: 100
--- PREFIX: bb

----------------------------------------------
------------MOD CODE -------------------------

-- Global bot object
BALATRO_BOT = BALATRO_BOT or {}

-- Configuration
BALATRO_BOT.config = {
    host = "127.0.0.1",
    port = 12345,
    update_interval = 0.5,
    debug = true,
    auto_execute = false,
}

-- State tracking
BALATRO_BOT.last_update = 0
BALATRO_BOT.last_state_hash = nil
BALATRO_BOT.connected = false
BALATRO_BOT.pending_action = nil
BALATRO_BOT.socket = nil

local function log(msg)
    if BALATRO_BOT.config.debug then
        print("[BalatroBot] " .. tostring(msg))
    end
end

log("Initializing BalatroBot...")

----------------------------------------------
-- Inlined Utils: JSON Serialization
----------------------------------------------

local function to_json(value)
    local value_type = type(value)

    if value_type == "nil" then
        return "null"
    elseif value_type == "boolean" then
        return value and "true" or "false"
    elseif value_type == "number" then
        if value ~= value then return "null" end
        if value == math.huge then return "999999999" end
        if value == -math.huge then return "-999999999" end
        return tostring(value)
    elseif value_type == "string" then
        local escaped = value:gsub('\\', '\\\\')
                             :gsub('"', '\\"')
                             :gsub('\n', '\\n')
                             :gsub('\r', '\\r')
                             :gsub('\t', '\\t')
        return '"' .. escaped .. '"'
    elseif value_type == "table" then
        local is_array = true
        local max_index = 0

        for k, _ in pairs(value) do
            if type(k) ~= "number" or k < 1 or math.floor(k) ~= k then
                is_array = false
                break
            end
            if k > max_index then max_index = k end
        end

        if is_array and max_index > 0 then
            for i = 1, max_index do
                if value[i] == nil then
                    is_array = false
                    break
                end
            end
        end

        if next(value) == nil then return "{}" end

        local parts = {}
        if is_array then
            for i = 1, max_index do
                table.insert(parts, to_json(value[i]))
            end
            return "[" .. table.concat(parts, ",") .. "]"
        else
            for k, v in pairs(value) do
                local key_str = type(k) == "string" and k or tostring(k)
                local json_key = '"' .. key_str:gsub('"', '\\"') .. '"'
                table.insert(parts, json_key .. ":" .. to_json(v))
            end
            return "{" .. table.concat(parts, ",") .. "}"
        end
    else
        return "null"
    end
end

local function from_json(json_str)
    if not json_str or json_str == "" then return nil end

    local pos = 1
    local str = json_str

    local function skip_whitespace()
        while pos <= #str do
            local c = str:sub(pos, pos)
            if c == " " or c == "\t" or c == "\n" or c == "\r" then
                pos = pos + 1
            else
                break
            end
        end
    end

    local parse_value

    parse_value = function()
        skip_whitespace()
        if pos > #str then return nil end

        local c = str:sub(pos, pos)

        if c == '"' then
            pos = pos + 1
            local result = ""
            while pos <= #str do
                local ch = str:sub(pos, pos)
                if ch == '"' then
                    pos = pos + 1
                    return result
                elseif ch == '\\' then
                    pos = pos + 1
                    local escaped = str:sub(pos, pos)
                    if escaped == 'n' then result = result .. '\n'
                    elseif escaped == 'r' then result = result .. '\r'
                    elseif escaped == 't' then result = result .. '\t'
                    elseif escaped == '"' then result = result .. '"'
                    elseif escaped == '\\' then result = result .. '\\'
                    else result = result .. escaped end
                    pos = pos + 1
                else
                    result = result .. ch
                    pos = pos + 1
                end
            end
            return nil

        elseif c == '{' then
            pos = pos + 1
            local result = {}
            skip_whitespace()
            if str:sub(pos, pos) == '}' then
                pos = pos + 1
                return result
            end
            while true do
                skip_whitespace()
                if str:sub(pos, pos) ~= '"' then return nil end
                local key = parse_value()
                if key == nil then return nil end
                skip_whitespace()
                if str:sub(pos, pos) ~= ':' then return nil end
                pos = pos + 1
                local value = parse_value()
                result[key] = value
                skip_whitespace()
                local sep = str:sub(pos, pos)
                if sep == '}' then
                    pos = pos + 1
                    return result
                elseif sep == ',' then
                    pos = pos + 1
                else
                    return nil
                end
            end

        elseif c == '[' then
            pos = pos + 1
            local result = {}
            skip_whitespace()
            if str:sub(pos, pos) == ']' then
                pos = pos + 1
                return result
            end
            while true do
                local value = parse_value()
                table.insert(result, value)
                skip_whitespace()
                local sep = str:sub(pos, pos)
                if sep == ']' then
                    pos = pos + 1
                    return result
                elseif sep == ',' then
                    pos = pos + 1
                else
                    return nil
                end
            end

        elseif str:sub(pos, pos + 3) == "true" then
            pos = pos + 4
            return true
        elseif str:sub(pos, pos + 4) == "false" then
            pos = pos + 5
            return false
        elseif str:sub(pos, pos + 3) == "null" then
            pos = pos + 4
            return nil
        elseif c == '-' or (c >= '0' and c <= '9') then
            local num_str = ""
            while pos <= #str do
                local ch = str:sub(pos, pos)
                if ch == '-' or ch == '+' or ch == '.' or ch == 'e' or ch == 'E' or
                   (ch >= '0' and ch <= '9') then
                    num_str = num_str .. ch
                    pos = pos + 1
                else
                    break
                end
            end
            return tonumber(num_str)
        else
            return nil
        end
    end

    return parse_value()
end

local function hash_state(state)
    if not state then return "nil" end
    local parts = {
        "phase:" .. tostring(state.phase_name),
        "ante:" .. tostring(state.ante),
        "money:" .. tostring(state.money),
        "hands:" .. tostring(state.hands_remaining),
        "discards:" .. tostring(state.discards_remaining),
    }
    if state.hand and #state.hand > 0 then
        table.insert(parts, "hand_count:" .. #state.hand)
    end
    if state.blind then
        table.insert(parts, "blind_chips:" .. tostring(state.blind.chips_scored))
    end
    -- Include shop presence in hash so it retries when shop loads
    if state.shop then
        local shop_count = #state.shop.items + #state.shop.vouchers + #state.shop.boosters
        table.insert(parts, "shop:" .. shop_count)
    else
        table.insert(parts, "shop:nil")
    end
    return table.concat(parts, "|")
end

----------------------------------------------
-- Socket handling
----------------------------------------------

local socket_lib = nil
local function try_load_socket()
    if socket_lib then return true end

    local status, result = pcall(function()
        return require("socket")
    end)

    if status and result then
        socket_lib = result
        log("LuaSocket loaded successfully")
        return true
    else
        log("LuaSocket not available - running in offline mode")
        return false
    end
end

local function connect_to_server()
    if not try_load_socket() then
        return false
    end

    if BALATRO_BOT.socket then
        return true
    end

    local tcp = socket_lib.tcp()
    tcp:settimeout(1)

    local success, err = tcp:connect(BALATRO_BOT.config.host, BALATRO_BOT.config.port)
    if not success then
        log("Connection failed: " .. tostring(err))
        return false
    end

    tcp:settimeout(2)
    BALATRO_BOT.socket = tcp
    BALATRO_BOT.connected = true
    log("Connected to bot server!")
    return true
end

local function send_state_get_action(state)
    if not BALATRO_BOT.socket then
        return nil
    end

    local json_str = to_json(state)
    if not json_str then
        return nil
    end

    local ok, err = BALATRO_BOT.socket:send(json_str .. "\n")
    if not ok then
        log("Send failed: " .. tostring(err))
        BALATRO_BOT.socket:close()
        BALATRO_BOT.socket = nil
        BALATRO_BOT.connected = false
        return nil
    end

    local response, recv_err = BALATRO_BOT.socket:receive("*l")
    if not response then
        log("Receive failed: " .. tostring(recv_err))
        BALATRO_BOT.socket:close()
        BALATRO_BOT.socket = nil
        BALATRO_BOT.connected = false
        return nil
    end

    return from_json(response)
end

----------------------------------------------
-- State extraction
----------------------------------------------

local function extract_card(card, index)
    if not card or not card.base then return nil end

    local suit_map = {
        ["H"] = "Hearts", ["D"] = "Diamonds",
        ["C"] = "Clubs", ["S"] = "Spades",
        ["Hearts"] = "Hearts", ["Diamonds"] = "Diamonds",
        ["Clubs"] = "Clubs", ["Spades"] = "Spades"
    }

    local rank_map = {
        -- Number cards
        ["2"] = 2, ["3"] = 3, ["4"] = 4, ["5"] = 5,
        ["6"] = 6, ["7"] = 7, ["8"] = 8, ["9"] = 9,
        ["10"] = 10, ["T"] = 10,
        -- Face cards - short form
        ["J"] = 11, ["Q"] = 12, ["K"] = 13, ["A"] = 14,
        -- Face cards - full names (Balatro uses these)
        ["Jack"] = 11, ["Queen"] = 12, ["King"] = 13, ["Ace"] = 14
    }

    local rank_value = card.base.value
    local rank_num = rank_map[rank_value] or tonumber(rank_value) or 0

    return {
        suit = suit_map[card.base.suit] or card.base.suit or "Unknown",
        rank = rank_num,
        rank_name = rank_value or "?",
        index = index,
        highlighted = card.highlighted or false,
    }
end

local function extract_joker(joker, index)
    if not joker then return nil end

    return {
        id = joker.config and joker.config.center and joker.config.center.key or "unknown",
        name = joker.ability and joker.ability.name or "Unknown",
        position = index,
    }
end

local function extract_shop_item(card, index)
    if not card then return nil end

    local item = {
        index = index,
        name = "Unknown",
        cost = card.cost or 0,
        sell_cost = card.sell_cost or 0,
        item_type = "Unknown",
    }

    -- Determine item type and details
    if card.ability then
        item.name = card.ability.name or "Unknown"

        if card.ability.set then
            local set = card.ability.set
            if set == "Joker" then
                item.item_type = "Joker"
                item.joker_id = card.config and card.config.center and card.config.center.key
            elseif set == "Tarot" then
                item.item_type = "Tarot"
            elseif set == "Planet" then
                item.item_type = "Planet"
            elseif set == "Spectral" then
                item.item_type = "Spectral"
            elseif set == "Voucher" then
                item.item_type = "Voucher"
            elseif set == "Booster" then
                item.item_type = "Booster"
            elseif set == "Default" or set == "Enhanced" then
                item.item_type = "Card"
            else
                item.item_type = set
            end
        end
    end

    -- For playing cards in shop
    if card.base then
        item.suit = card.base.suit
        item.rank = card.base.value
    end

    return item
end

local function extract_shop()
    -- Only extract shop in SHOP state
    if not G.STATE or G.STATE ~= G.STATES.SHOP then
        return nil
    end

    local shop = {
        items = {},
        vouchers = {},
        boosters = {},
        reroll_cost = G.GAME.current_round and G.GAME.current_round.reroll_cost or 5,
    }

    -- Extract shop cards (jokers, tarots, planets, playing cards)
    if G.shop_jokers and G.shop_jokers.cards then
        for i, card in ipairs(G.shop_jokers.cards) do
            local item = extract_shop_item(card, i)
            if item then
                table.insert(shop.items, item)
            end
        end
    end

    -- Extract vouchers
    if G.shop_vouchers and G.shop_vouchers.cards then
        for i, card in ipairs(G.shop_vouchers.cards) do
            local item = extract_shop_item(card, i)
            if item then
                item.item_type = "Voucher"
                table.insert(shop.vouchers, item)
            end
        end
    end

    -- Extract booster packs
    if G.shop_booster and G.shop_booster.cards then
        for i, card in ipairs(G.shop_booster.cards) do
            local item = extract_shop_item(card, i)
            if item then
                item.item_type = "Booster"
                table.insert(shop.boosters, item)
            end
        end
    end

    -- Check if shop is actually loaded (has at least boosters which always exist)
    -- If shop appears empty, it might still be loading - return nil to retry
    local total_items = #shop.items + #shop.vouchers + #shop.boosters
    if total_items == 0 then
        log("Shop appears empty, may still be loading...")
        return nil  -- Will be retried on next update
    end

    log(string.format("Shop: %d items, %d vouchers, %d boosters",
        #shop.items, #shop.vouchers, #shop.boosters))

    return shop
end

local function extract_game_state()
    if not G or not G.GAME then
        return nil
    end

    local phase_name = "UNKNOWN"
    if G.STATE then
        for name, value in pairs(G.STATES or {}) do
            if value == G.STATE then
                phase_name = name
                break
            end
        end
    end

    local hand = {}
    if G.hand and G.hand.cards then
        for i, card in ipairs(G.hand.cards) do
            local card_data = extract_card(card, i)
            if card_data then
                table.insert(hand, card_data)
            end
        end
    end

    local jokers = {}
    if G.jokers and G.jokers.cards then
        for i, joker in ipairs(G.jokers.cards) do
            local joker_data = extract_joker(joker, i)
            if joker_data then
                table.insert(jokers, joker_data)
            end
        end
    end

    local blind = nil
    if G.GAME.blind then
        blind = {
            name = G.GAME.blind.name or "Unknown",
            chips_required = G.GAME.blind.chips or 0,
            chips_scored = G.GAME.chips or 0,
        }
    end

    -- Extract shop if in shop phase
    local shop = extract_shop()

    return {
        phase_name = phase_name,
        ante = G.GAME.round_resets and G.GAME.round_resets.ante or 1,
        round = G.GAME.round or 0,
        stake = G.GAME.stake or 1,
        money = G.GAME.dollars or 0,
        hands_remaining = G.GAME.current_round and G.GAME.current_round.hands_left or 0,
        discards_remaining = G.GAME.current_round and G.GAME.current_round.discards_left or 0,
        hand_size = G.hand and G.hand.config and G.hand.config.card_limit or 8,
        hand = hand,
        jokers = jokers,
        blind = blind,
        shop = shop,
    }
end

----------------------------------------------
-- Decision logic
----------------------------------------------

local function is_decision_point()
    if not G or not G.STATE or not G.STATES then return false end

    return G.STATE == G.STATES.SELECTING_HAND
        or G.STATE == G.STATES.SHOP
        or G.STATE == G.STATES.BLIND_SELECT
end

local function display_recommendation(action)
    if not action then return end

    local msg = ">>> "

    if action.action_type == "play" then
        msg = msg .. "PLAY cards: " .. table.concat(action.card_indices or {}, ", ")
    elseif action.action_type == "discard" then
        msg = msg .. "DISCARD cards: " .. table.concat(action.card_indices or {}, ", ")
    elseif action.action_type == "shop" then
        if action.skip then
            msg = msg .. "SKIP shop"
        elseif action.reroll then
            msg = msg .. "REROLL"
        elseif action.buy_index then
            msg = msg .. "BUY item " .. action.buy_index
        end
    elseif action.action_type == "blind" then
        msg = msg .. (action.skip and "SKIP blind" or "PLAY blind")
    end

    if action.reasoning and action.reasoning ~= "" then
        msg = msg .. " (" .. action.reasoning .. ")"
    end

    log(msg)
end

----------------------------------------------
-- Main update hook
----------------------------------------------

local _balatro_bot_hooked = false

local function bot_update(dt)
    -- Throttle updates
    BALATRO_BOT.last_update = (BALATRO_BOT.last_update or 0) + dt
    if BALATRO_BOT.last_update < BALATRO_BOT.config.update_interval then
        return
    end
    BALATRO_BOT.last_update = 0

    -- Only process at decision points
    if not is_decision_point() then
        return
    end

    -- Extract state
    local state = extract_game_state()
    if not state then
        return
    end

    -- Check if state changed
    local state_hash = hash_state(state)
    if state_hash == BALATRO_BOT.last_state_hash then
        return
    end
    BALATRO_BOT.last_state_hash = state_hash

    -- Log state summary
    log(string.format("State: %s | Ante %d | $%d | %dH/%dD | %d cards",
        state.phase_name,
        state.ante,
        state.money,
        state.hands_remaining,
        state.discards_remaining,
        #state.hand
    ))

    -- Try to connect and get action
    if connect_to_server() then
        local action = send_state_get_action(state)
        if action then
            display_recommendation(action)
            BALATRO_BOT.pending_action = action
        end
    else
        -- Offline mode
        if not BALATRO_BOT._logged_offline then
            log("Running in offline mode (no server connection)")
            BALATRO_BOT._logged_offline = true
        end
    end
end

-- Hook into love.update using Steamodded's method
local function setup_hook()
    if _balatro_bot_hooked then return end

    local original_update = love.update
    love.update = function(dt)
        original_update(dt)
        local ok, err = pcall(bot_update, dt)
        if not ok then
            log("Update error: " .. tostring(err))
        end
    end

    _balatro_bot_hooked = true
    log("Update hook installed")
end

-- Try to set up hook now, or defer if love.update isn't ready
if love and love.update then
    setup_hook()
else
    -- Defer hook setup
    local _bot_hook_timer = 0
    local _bot_orig_love_load = love.load
    love.load = function(...)
        if _bot_orig_love_load then _bot_orig_love_load(...) end
        setup_hook()
    end
end

----------------------------------------------
-- Console commands
----------------------------------------------

function BALATRO_BOT.status()
    log("=== BalatroBot Status ===")
    log("  Connected: " .. tostring(BALATRO_BOT.connected))
    log("  Auto-execute: " .. tostring(BALATRO_BOT.config.auto_execute))
    log("  Debug: " .. tostring(BALATRO_BOT.config.debug))
    if G and G.STATE then
        log("  Game state: " .. tostring(G.STATE))
    end
end

function BALATRO_BOT.toggle_debug()
    BALATRO_BOT.config.debug = not BALATRO_BOT.config.debug
    log("Debug mode: " .. tostring(BALATRO_BOT.config.debug))
end

function BALATRO_BOT.test()
    log("Testing state extraction...")
    local state = extract_game_state()
    if state then
        log("State extracted successfully:")
        log("  Phase: " .. state.phase_name)
        log("  Ante: " .. state.ante)
        log("  Money: $" .. state.money)
        log("  Hand cards: " .. #state.hand)
        log("  Jokers: " .. #state.jokers)
    else
        log("Failed to extract state (not in game?)")
    end
end

log("BalatroBot loaded! Commands: BALATRO_BOT.status(), BALATRO_BOT.test()")

----------------------------------------------
------------MOD CODE END----------------------
