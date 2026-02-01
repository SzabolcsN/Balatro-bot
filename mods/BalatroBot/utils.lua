--[[
    BalatroBot - Utility Functions

    Helper functions for JSON serialization, state hashing,
    and other common operations.
]]

local utils = {}

-------------------------------------------------------------------------------
-- JSON Serialization
-------------------------------------------------------------------------------

-- Simple JSON encoder (Balatro doesn't include a JSON library by default)
function utils.to_json(value, indent)
    indent = indent or 0
    local value_type = type(value)

    if value_type == "nil" then
        return "null"
    elseif value_type == "boolean" then
        return value and "true" or "false"
    elseif value_type == "number" then
        -- Handle special float values
        if value ~= value then  -- NaN
            return "null"
        elseif value == math.huge then
            return "999999999"
        elseif value == -math.huge then
            return "-999999999"
        else
            return tostring(value)
        end
    elseif value_type == "string" then
        -- Escape special characters
        local escaped = value:gsub('\\', '\\\\')
                             :gsub('"', '\\"')
                             :gsub('\n', '\\n')
                             :gsub('\r', '\\r')
                             :gsub('\t', '\\t')
        return '"' .. escaped .. '"'
    elseif value_type == "table" then
        -- Check if it's an array (consecutive integer keys starting at 1)
        local is_array = true
        local max_index = 0

        for k, _ in pairs(value) do
            if type(k) ~= "number" or k < 1 or math.floor(k) ~= k then
                is_array = false
                break
            end
            if k > max_index then
                max_index = k
            end
        end

        -- Also check for holes in the array
        if is_array and max_index > 0 then
            for i = 1, max_index do
                if value[i] == nil then
                    is_array = false
                    break
                end
            end
        end

        -- Empty table defaults to object
        if next(value) == nil then
            return "{}"
        end

        local parts = {}

        if is_array then
            for i = 1, max_index do
                table.insert(parts, utils.to_json(value[i], indent + 1))
            end
            return "[" .. table.concat(parts, ",") .. "]"
        else
            for k, v in pairs(value) do
                local key_str = type(k) == "string" and k or tostring(k)
                local json_key = '"' .. key_str:gsub('"', '\\"') .. '"'
                local json_value = utils.to_json(v, indent + 1)
                table.insert(parts, json_key .. ":" .. json_value)
            end
            return "{" .. table.concat(parts, ",") .. "}"
        end
    else
        -- Function, userdata, thread - not serializable
        return "null"
    end
end

-- Simple JSON decoder
function utils.from_json(json_str)
    if not json_str or json_str == "" then
        return nil, "Empty JSON string"
    end

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

    local function parse_value()
        skip_whitespace()

        if pos > #str then
            return nil, "Unexpected end of JSON"
        end

        local c = str:sub(pos, pos)

        if c == '"' then
            -- String
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
                    if escaped == 'n' then
                        result = result .. '\n'
                    elseif escaped == 'r' then
                        result = result .. '\r'
                    elseif escaped == 't' then
                        result = result .. '\t'
                    elseif escaped == '"' then
                        result = result .. '"'
                    elseif escaped == '\\' then
                        result = result .. '\\'
                    else
                        result = result .. escaped
                    end
                    pos = pos + 1
                else
                    result = result .. ch
                    pos = pos + 1
                end
            end
            return nil, "Unterminated string"

        elseif c == '{' then
            -- Object
            pos = pos + 1
            local result = {}
            skip_whitespace()

            if str:sub(pos, pos) == '}' then
                pos = pos + 1
                return result
            end

            while true do
                skip_whitespace()

                -- Parse key
                if str:sub(pos, pos) ~= '"' then
                    return nil, "Expected string key at position " .. pos
                end
                local key = parse_value()
                if key == nil then
                    return nil, "Failed to parse key"
                end

                skip_whitespace()
                if str:sub(pos, pos) ~= ':' then
                    return nil, "Expected ':' at position " .. pos
                end
                pos = pos + 1

                -- Parse value
                local value, err = parse_value()
                if err then
                    return nil, err
                end
                result[key] = value

                skip_whitespace()
                local sep = str:sub(pos, pos)
                if sep == '}' then
                    pos = pos + 1
                    return result
                elseif sep == ',' then
                    pos = pos + 1
                else
                    return nil, "Expected ',' or '}' at position " .. pos
                end
            end

        elseif c == '[' then
            -- Array
            pos = pos + 1
            local result = {}
            skip_whitespace()

            if str:sub(pos, pos) == ']' then
                pos = pos + 1
                return result
            end

            while true do
                local value, err = parse_value()
                if err then
                    return nil, err
                end
                table.insert(result, value)

                skip_whitespace()
                local sep = str:sub(pos, pos)
                if sep == ']' then
                    pos = pos + 1
                    return result
                elseif sep == ',' then
                    pos = pos + 1
                else
                    return nil, "Expected ',' or ']' at position " .. pos
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
            -- Number
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
            local num = tonumber(num_str)
            if num then
                return num
            else
                return nil, "Invalid number: " .. num_str
            end
        else
            return nil, "Unexpected character '" .. c .. "' at position " .. pos
        end
    end

    local result, err = parse_value()
    if err then
        return nil, err
    end
    return result
end

-------------------------------------------------------------------------------
-- State Hashing
-------------------------------------------------------------------------------

-- Create a simple hash of the game state for change detection
function utils.hash_state(state)
    if not state then return "nil" end

    -- Hash key elements that would indicate state change
    local parts = {
        "phase:" .. tostring(state.phase),
        "ante:" .. tostring(state.ante),
        "round:" .. tostring(state.round),
        "money:" .. tostring(state.money),
        "hands:" .. tostring(state.hands_remaining),
        "discards:" .. tostring(state.discards_remaining),
    }

    -- Include hand cards (by count and first/last card)
    if state.hand and #state.hand > 0 then
        table.insert(parts, "hand_count:" .. #state.hand)
        local first = state.hand[1]
        if first then
            table.insert(parts, "hand_first:" .. tostring(first.suit) .. tostring(first.rank))
        end
    end

    -- Include blind info
    if state.blind then
        table.insert(parts, "blind_chips:" .. tostring(state.blind.chips_scored))
    end

    -- Include joker count
    if state.jokers then
        table.insert(parts, "joker_count:" .. #state.jokers)
    end

    return table.concat(parts, "|")
end

-------------------------------------------------------------------------------
-- State Summary
-------------------------------------------------------------------------------

-- Create a human-readable summary of the game state
function utils.state_summary(state)
    if not state then return "No state" end

    local parts = {}

    -- Phase
    table.insert(parts, utils.get_phase_name(state.phase))

    -- Ante/Round
    table.insert(parts, "Ante " .. tostring(state.ante))

    -- Money
    table.insert(parts, "$" .. tostring(state.money))

    -- Resources
    if state.hands_remaining then
        table.insert(parts, state.hands_remaining .. "H/" .. (state.discards_remaining or 0) .. "D")
    end

    -- Hand cards
    if state.hand then
        table.insert(parts, #state.hand .. " cards")
    end

    -- Jokers
    if state.jokers then
        table.insert(parts, #state.jokers .. " jokers")
    end

    -- Blind
    if state.blind and state.blind.chips_required then
        local progress = state.blind.chips_scored or 0
        local required = state.blind.chips_required
        table.insert(parts, progress .. "/" .. required .. " chips")
    end

    return table.concat(parts, " | ")
end

-------------------------------------------------------------------------------
-- Phase Name Lookup
-------------------------------------------------------------------------------

-- Convert game phase enum to readable string
function utils.get_phase_name(phase)
    if not G or not G.STATES then
        return "UNKNOWN"
    end

    local phase_names = {
        [G.STATES.SELECTING_HAND] = "SELECTING_HAND",
        [G.STATES.HAND_PLAYED] = "HAND_PLAYED",
        [G.STATES.DRAW_TO_HAND] = "DRAW_TO_HAND",
        [G.STATES.SHOP] = "SHOP",
        [G.STATES.BLIND_SELECT] = "BLIND_SELECT",
        [G.STATES.NEW_ROUND] = "NEW_ROUND",
        [G.STATES.GAME_OVER] = "GAME_OVER",
        [G.STATES.TAROT_PACK] = "TAROT_PACK",
        [G.STATES.PLANET_PACK] = "PLANET_PACK",
        [G.STATES.SPECTRAL_PACK] = "SPECTRAL_PACK",
        [G.STATES.STANDARD_PACK] = "STANDARD_PACK",
        [G.STATES.BUFFOON_PACK] = "BUFFOON_PACK",
        [G.STATES.MENU] = "MENU",
        [G.STATES.SPLASH] = "SPLASH",
    }

    return phase_names[phase] or ("UNKNOWN_" .. tostring(phase))
end

-------------------------------------------------------------------------------
-- Table Helpers
-------------------------------------------------------------------------------

-- Shallow copy a table
function utils.shallow_copy(t)
    if type(t) ~= "table" then
        return t
    end

    local copy = {}
    for k, v in pairs(t) do
        copy[k] = v
    end
    return copy
end

-- Deep copy a table (for state cloning)
function utils.deep_copy(t)
    if type(t) ~= "table" then
        return t
    end

    local copy = {}
    for k, v in pairs(t) do
        copy[utils.deep_copy(k)] = utils.deep_copy(v)
    end
    return copy
end

-------------------------------------------------------------------------------
-- Game Stats Helpers
-------------------------------------------------------------------------------

-- Count defeated boss blinds in current run
function utils.count_defeated_bosses()
    if not G or not G.GAME then return 0 end

    -- Boss blinds are defeated once per ante
    -- Current ante - 1 = bosses defeated (if we're past ante 1)
    local ante = G.GAME.round_resets and G.GAME.round_resets.ante or 1

    -- If we're in blind select or shop after boss, count current ante's boss too
    local current_blind = G.GAME.blind_on_deck
    if current_blind == "Small" or current_blind == "Big" then
        -- Haven't beaten this ante's boss yet
        return math.max(0, ante - 1)
    else
        -- Either at boss or past it
        local blind_state = G.GAME.round_resets and G.GAME.round_resets.blind_states
        if blind_state and blind_state.Boss == "Defeated" then
            return ante
        else
            return math.max(0, ante - 1)
        end
    end
end

-- Count skipped blinds in current run
function utils.count_skipped_blinds()
    if not G or not G.GAME then return 0 end

    local count = 0
    local blind_states = G.GAME.round_resets and G.GAME.round_resets.blind_states

    if blind_states then
        if blind_states.Small == "Skipped" then count = count + 1 end
        if blind_states.Big == "Skipped" then count = count + 1 end
    end

    -- Also check historical skips if tracked
    if G.GAME.blinds_skipped then
        return G.GAME.blinds_skipped
    end

    return count
end

-------------------------------------------------------------------------------
-- Card Helpers
-------------------------------------------------------------------------------

-- Get suit name from suit identifier
function utils.get_suit_name(suit)
    local suits = {
        ["Spades"] = "Spades",
        ["Hearts"] = "Hearts",
        ["Clubs"] = "Clubs",
        ["Diamonds"] = "Diamonds",
        ["S"] = "Spades",
        ["H"] = "Hearts",
        ["C"] = "Clubs",
        ["D"] = "Diamonds",
    }
    return suits[suit] or suit
end

-- Get rank name from rank ID
function utils.get_rank_name(rank_id)
    local ranks = {
        [2] = "2", [3] = "3", [4] = "4", [5] = "5",
        [6] = "6", [7] = "7", [8] = "8", [9] = "9",
        [10] = "10", [11] = "Jack", [12] = "Queen",
        [13] = "King", [14] = "Ace"
    }
    return ranks[rank_id] or tostring(rank_id)
end

-- Format card for display
function utils.format_card(card)
    if not card then return "?" end

    local suit = utils.get_suit_name(card.suit or "?")
    local rank = utils.get_rank_name(card.rank or card.rank_name or "?")

    local suit_symbol = {
        Spades = "♠", Hearts = "♥", Clubs = "♣", Diamonds = "♦"
    }

    return rank .. (suit_symbol[suit] or suit:sub(1,1))
end

-------------------------------------------------------------------------------
-- Debug Helpers
-------------------------------------------------------------------------------

-- Dump a table structure for debugging
function utils.dump(value, indent, visited)
    indent = indent or 0
    visited = visited or {}

    local prefix = string.rep("  ", indent)

    if type(value) ~= "table" then
        return prefix .. tostring(value)
    end

    -- Prevent infinite recursion
    if visited[value] then
        return prefix .. "(circular reference)"
    end
    visited[value] = true

    local lines = {prefix .. "{"}
    for k, v in pairs(value) do
        local key_str = type(k) == "string" and k or ("[" .. tostring(k) .. "]")
        if type(v) == "table" then
            table.insert(lines, prefix .. "  " .. key_str .. " = ")
            table.insert(lines, utils.dump(v, indent + 2, visited))
        else
            table.insert(lines, prefix .. "  " .. key_str .. " = " .. tostring(v))
        end
    end
    table.insert(lines, prefix .. "}")

    return table.concat(lines, "\n")
end

return utils
