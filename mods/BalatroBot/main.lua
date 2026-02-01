--[[
    BalatroBot - Main Entry Point

    This module initializes the bot and sets up the game hooks.
    It coordinates between state extraction, IPC, and action execution.
]]

-- Global bot object
BALATRO_BOT = BALATRO_BOT or {}

-- Configuration
BALATRO_BOT.config = {
    -- IPC settings
    host = "127.0.0.1",
    port = 12345,

    -- Timing
    update_interval = 0.1,  -- Seconds between state checks
    event_queue_threshold = 3,  -- Max events for "stable" state

    -- Mode
    auto_execute = false,  -- If false, just display recommendations
    debug = true,  -- Print debug messages
}

-- State tracking
BALATRO_BOT.last_update = 0
BALATRO_BOT.last_state = nil
BALATRO_BOT.connected = false
BALATRO_BOT.pending_action = nil

-- Load submodules
local state_extractor = require("BalatroBot.state_extractor")
local ipc_client = require("BalatroBot.ipc_client")
local action_executor = require("BalatroBot.action_executor")
local utils = require("BalatroBot.utils")

-------------------------------------------------------------------------------
-- Debug Logging
-------------------------------------------------------------------------------

local function log(msg)
    if BALATRO_BOT.config.debug then
        print("[BalatroBot] " .. tostring(msg))
    end
end

-------------------------------------------------------------------------------
-- State Stability Check
-------------------------------------------------------------------------------

local function is_state_stable()
    -- Check if event queue is nearly empty (animations done)
    if G and G.E_MANAGER and G.E_MANAGER.queues and G.E_MANAGER.queues.base then
        local queue_size = #G.E_MANAGER.queues.base
        return queue_size < BALATRO_BOT.config.event_queue_threshold
    end
    return false
end

local function is_decision_point()
    -- Check if game is at a point where player input is expected
    if not G or not G.STATE then return false end

    local decision_states = {
        [G.STATES.SELECTING_HAND] = true,
        [G.STATES.SHOP] = true,
        [G.STATES.BLIND_SELECT] = true,
        [G.STATES.TAROT_PACK] = true,
        [G.STATES.PLANET_PACK] = true,
        [G.STATES.SPECTRAL_PACK] = true,
        [G.STATES.STANDARD_PACK] = true,
        [G.STATES.BUFFOON_PACK] = true,
    }

    return decision_states[G.STATE] or false
end

-------------------------------------------------------------------------------
-- Main Update Loop
-------------------------------------------------------------------------------

function BALATRO_BOT.update(dt)
    -- Throttle updates
    BALATRO_BOT.last_update = BALATRO_BOT.last_update + dt
    if BALATRO_BOT.last_update < BALATRO_BOT.config.update_interval then
        return
    end
    BALATRO_BOT.last_update = 0

    -- Check if we're at a decision point with stable state
    if not is_decision_point() then
        return
    end

    if not is_state_stable() then
        return
    end

    -- Extract current game state
    local state, err = state_extractor.extract()
    if not state then
        log("State extraction failed: " .. tostring(err))
        return
    end

    -- Check if state has changed
    local state_hash = utils.hash_state(state)
    if state_hash == BALATRO_BOT.last_state then
        return  -- No change, don't re-query bot
    end
    BALATRO_BOT.last_state = state_hash

    -- Try to connect if not connected
    if not BALATRO_BOT.connected then
        local success = ipc_client.connect(
            BALATRO_BOT.config.host,
            BALATRO_BOT.config.port
        )
        if success then
            log("Connected to bot server")
            BALATRO_BOT.connected = true
        else
            -- Not connected, just log state for debugging
            if BALATRO_BOT.config.debug then
                log("State: " .. utils.state_summary(state))
            end
            return
        end
    end

    -- Send state and get action
    local action, action_err = ipc_client.get_action(state)
    if not action then
        log("Failed to get action: " .. tostring(action_err))
        BALATRO_BOT.connected = false
        return
    end

    -- Display recommendation
    BALATRO_BOT.display_recommendation(action)

    -- Execute if auto mode
    if BALATRO_BOT.config.auto_execute then
        action_executor.execute(action)
    else
        BALATRO_BOT.pending_action = action
    end
end

-------------------------------------------------------------------------------
-- Recommendation Display
-------------------------------------------------------------------------------

function BALATRO_BOT.display_recommendation(action)
    if not action then return end

    local msg = "Recommendation: "

    if action.action_type == "play" then
        msg = msg .. "PLAY cards at indices: " .. table.concat(action.card_indices or {}, ", ")
    elseif action.action_type == "discard" then
        msg = msg .. "DISCARD cards at indices: " .. table.concat(action.card_indices or {}, ", ")
    elseif action.action_type == "shop" then
        if action.skip then
            msg = msg .. "SKIP shop"
        elseif action.reroll then
            msg = msg .. "REROLL shop"
        elseif action.buy_index then
            msg = msg .. "BUY item at index " .. action.buy_index
        end
    elseif action.action_type == "blind" then
        if action.skip then
            msg = msg .. "SKIP blind"
        else
            msg = msg .. "SELECT blind"
        end
    elseif action.action_type == "use_consumable" then
        msg = msg .. "USE consumable " .. (action.consumable_index or "?")
    end

    log(msg)

    -- TODO: Overlay UI to display recommendation on screen
end

-------------------------------------------------------------------------------
-- Manual Execution (for semi-auto mode)
-------------------------------------------------------------------------------

function BALATRO_BOT.execute_pending()
    if BALATRO_BOT.pending_action then
        action_executor.execute(BALATRO_BOT.pending_action)
        BALATRO_BOT.pending_action = nil
    end
end

-------------------------------------------------------------------------------
-- Commands (can be called from console)
-------------------------------------------------------------------------------

function BALATRO_BOT.toggle_auto()
    BALATRO_BOT.config.auto_execute = not BALATRO_BOT.config.auto_execute
    log("Auto-execute: " .. tostring(BALATRO_BOT.config.auto_execute))
end

function BALATRO_BOT.toggle_debug()
    BALATRO_BOT.config.debug = not BALATRO_BOT.config.debug
    log("Debug: " .. tostring(BALATRO_BOT.config.debug))
end

function BALATRO_BOT.status()
    log("Status:")
    log("  Connected: " .. tostring(BALATRO_BOT.connected))
    log("  Auto-execute: " .. tostring(BALATRO_BOT.config.auto_execute))
    log("  Debug: " .. tostring(BALATRO_BOT.config.debug))
    log("  State: " .. tostring(G and G.STATE))
end

function BALATRO_BOT.extract_state()
    -- Debug helper to manually extract and print state
    local state = state_extractor.extract()
    if state then
        log("Extracted state:")
        log(utils.to_json(state))
    else
        log("Failed to extract state")
    end
end

-------------------------------------------------------------------------------
-- Initialization
-------------------------------------------------------------------------------

log("Initializing...")
log("Host: " .. BALATRO_BOT.config.host .. ":" .. BALATRO_BOT.config.port)
log("Commands: BALATRO_BOT.toggle_auto(), BALATRO_BOT.status(), BALATRO_BOT.extract_state()")

return BALATRO_BOT
