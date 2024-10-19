local M = {}

-- Helper function to get real window count in current tab
local function get_real_window_count()
    local wins = vim.api.nvim_tabpage_list_wins(0)
    return #wins
end

-- Helper function to check if window is at edge
local function is_at_edge(direction)
    local cur_win = vim.api.nvim_get_current_win()
    local cur_pos = vim.api.nvim_win_get_position(cur_win)
    local win_width = vim.api.nvim_win_get_width(cur_win)
    local win_height = vim.api.nvim_win_get_height(cur_win)
    local total_width = vim.o.columns
    local total_height = vim.o.lines - vim.o.cmdheight

    if direction == "h" then
        return cur_pos[2] == 0
    elseif direction == "l" then
        return cur_pos[2] + win_width >= total_width
    elseif direction == "k" then
        return cur_pos[1] == 0
    elseif direction == "j" then
        return cur_pos[1] + win_height >= total_height
    end
    return false
end

-- Helper function to navigate between Neovim windows and Zellij panes
local function navigate(direction, use_tab)
    local cur_win = vim.api.nvim_get_current_win()
    vim.cmd("wincmd " .. direction)
    local new_win = vim.api.nvim_get_current_win()

    if cur_win == new_win and is_at_edge(direction) then
        local action = use_tab and "move-focus-or-tab" or "move-focus"
        local dir_map = {
            h = "left",
            j = "down",
            k = "up",
            l = "right",
        }
        vim.fn.system(string.format("zellij action %s %s", action, dir_map[direction]))

        -- Switch to normal mode if we're moving between tabs
        if use_tab and (direction == "h" or direction == "l") then
            M.set_mode("normal")
        end
    end
end

function M.set_mode(mode)
    vim.fn.system("zellij action switch-mode " .. mode)
end

function M.setup()
    local keymap_opts = { silent = true }

    -- Create navigation functions with improved edge detection
    local function create_nav_fn(direction, use_tab)
        return function()
            navigate(direction, use_tab)
        end
    end

    -- Set up keymaps with the new navigation functions
    vim.keymap.set("n", "<c-h>", create_nav_fn("h", true), keymap_opts)
    vim.keymap.set("n", "<c-l>", create_nav_fn("l", true), keymap_opts)
    vim.keymap.set("n", "<c-j>", create_nav_fn("j", false), keymap_opts)
    vim.keymap.set("n", "<c-k>", create_nav_fn("k", false), keymap_opts)

    -- Create autocommands with improved mode handling
    local group = vim.api.nvim_create_augroup("ZellijIntegration", { clear = true })

    vim.api.nvim_create_autocmd("VimEnter", {
        group = group,
        callback = function()
            vim.defer_fn(function()
                M.set_mode("locked")
            end, 100)
        end,
    })

    vim.api.nvim_create_autocmd("VimLeave", {
        group = group,
        callback = function()
            M.set_mode("normal")
        end,
    })

    vim.api.nvim_create_autocmd("FocusGained", {
        group = group,
        callback = function()
            vim.defer_fn(function()
                M.set_mode("locked")
            end, 50)
        end,
    })

    -- Add WinEnter autocmd to handle treesitter context
    vim.api.nvim_create_autocmd("WinEnter", {
        group = group,
        callback = function()
            vim.defer_fn(function()
                -- Ensure window calculations are updated after treesitter context
                vim.cmd("redraw")
            end, 10)
        end,
    })
end

return M
