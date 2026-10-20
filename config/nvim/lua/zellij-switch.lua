local M = {}

local function in_zellij()
    return vim.env.ZELLIJ ~= nil and vim.env.ZELLIJ ~= ""
end

-- Helper function to navigate between Neovim windows and Zellij panes
local function navigate(direction, use_tab)
    local cur_win = vim.api.nvim_get_current_win()
    local is_float = vim.api.nvim_win_get_config(cur_win).relative ~= ""
    vim.cmd("wincmd " .. direction)
    local new_win = vim.api.nvim_get_current_win()

    if cur_win == new_win and not is_float and in_zellij() then
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
    if in_zellij() then
        vim.fn.system("zellij action switch-mode " .. mode)
    end
end

function M.setup()
    local keymap_opts = { silent = true }

    local function create_nav_fn(direction, use_tab)
        return function()
            navigate(direction, use_tab)
        end
    end

    vim.keymap.set("n", "<c-h>", create_nav_fn("h", true), keymap_opts)
    vim.keymap.set("n", "<c-l>", create_nav_fn("l", true), keymap_opts)
    vim.keymap.set("n", "<c-j>", create_nav_fn("j", false), keymap_opts)
    vim.keymap.set("n", "<c-k>", create_nav_fn("k", false), keymap_opts)

    local group = vim.api.nvim_create_augroup("ZellijIntegration", { clear = true })
    if not in_zellij() then
        return
    end

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
end

return M
