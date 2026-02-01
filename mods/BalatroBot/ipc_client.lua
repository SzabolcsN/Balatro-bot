--[[
    BalatroBot - IPC Client

    Handles communication with the Python bot server via TCP socket.
    Sends game state as JSON, receives action commands.
]]

local ipc_client = {}

local utils = require("BalatroBot.utils")

-- Socket connection
local socket = nil
local connected = false

-- Try to load LuaSocket
local socket_available = false
local luasocket = nil

local function try_load_socket()
    if socket_available then return true end

    local status, result = pcall(function()
        return require("socket")
    end)

    if status then
        luasocket = result
        socket_available = true
        return true
    else
        print("[BalatroBot] LuaSocket not available: " .. tostring(result))
        print("[BalatroBot] IPC communication disabled, running in offline mode")
        return false
    end
end

-------------------------------------------------------------------------------
-- Connection Management
-------------------------------------------------------------------------------

function ipc_client.connect(host, port)
    if not try_load_socket() then
        return false
    end

    if connected then
        return true
    end

    local tcp = luasocket.tcp()
    tcp:settimeout(2)  -- 2 second connection timeout

    local success, err = tcp:connect(host, port)
    if not success then
        print("[BalatroBot] Connection failed: " .. tostring(err))
        return false
    end

    tcp:settimeout(5)  -- 5 second read/write timeout
    socket = tcp
    connected = true

    print("[BalatroBot] Connected to " .. host .. ":" .. port)
    return true
end

function ipc_client.disconnect()
    if socket then
        socket:close()
        socket = nil
    end
    connected = false
end

function ipc_client.is_connected()
    return connected
end

-------------------------------------------------------------------------------
-- Communication
-------------------------------------------------------------------------------

function ipc_client.send(data)
    if not connected or not socket then
        return false, "Not connected"
    end

    local json_data = utils.to_json(data)
    if not json_data then
        return false, "JSON encoding failed"
    end

    -- Add newline delimiter
    json_data = json_data .. "\n"

    local bytes_sent, err = socket:send(json_data)
    if not bytes_sent then
        connected = false
        return false, "Send failed: " .. tostring(err)
    end

    return true
end

function ipc_client.receive()
    if not connected or not socket then
        return nil, "Not connected"
    end

    -- Read until newline
    local data, err = socket:receive("*l")
    if not data then
        if err == "timeout" then
            return nil, "Timeout"
        end
        connected = false
        return nil, "Receive failed: " .. tostring(err)
    end

    -- Parse JSON
    local parsed = utils.from_json(data)
    if not parsed then
        return nil, "JSON parsing failed"
    end

    return parsed
end

-------------------------------------------------------------------------------
-- High-Level API
-------------------------------------------------------------------------------

function ipc_client.get_action(state)
    -- Send state
    local send_ok, send_err = ipc_client.send(state)
    if not send_ok then
        return nil, send_err
    end

    -- Receive action
    local action, recv_err = ipc_client.receive()
    if not action then
        return nil, recv_err
    end

    return action
end

-------------------------------------------------------------------------------
-- Fallback: File-based IPC
-------------------------------------------------------------------------------
-- If LuaSocket isn't available, we can use file-based communication
-- Python writes action to file, Lua reads it

local FILE_STATE_PATH = "balatro_bot_state.json"
local FILE_ACTION_PATH = "balatro_bot_action.json"

function ipc_client.file_send_state(state)
    local json_data = utils.to_json(state)
    if not json_data then
        return false, "JSON encoding failed"
    end

    local file = io.open(FILE_STATE_PATH, "w")
    if not file then
        return false, "Cannot open state file"
    end

    file:write(json_data)
    file:close()
    return true
end

function ipc_client.file_read_action()
    local file = io.open(FILE_ACTION_PATH, "r")
    if not file then
        return nil, "No action file"
    end

    local data = file:read("*all")
    file:close()

    -- Delete file after reading
    os.remove(FILE_ACTION_PATH)

    if not data or data == "" then
        return nil, "Empty action file"
    end

    local action = utils.from_json(data)
    return action
end

function ipc_client.file_get_action(state)
    -- Write state
    local ok, err = ipc_client.file_send_state(state)
    if not ok then
        return nil, err
    end

    -- Wait and poll for action file
    local max_wait = 5  -- seconds
    local poll_interval = 0.1
    local waited = 0

    while waited < max_wait do
        local action = ipc_client.file_read_action()
        if action then
            return action
        end

        -- Sleep (LÖVE provides this)
        if love and love.timer then
            love.timer.sleep(poll_interval)
        end
        waited = waited + poll_interval
    end

    return nil, "Timeout waiting for action"
end

return ipc_client
