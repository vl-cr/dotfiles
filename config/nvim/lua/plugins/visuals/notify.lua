return {
    "rcarriga/nvim-notify",
    config = function()
        require("notify").setup({
            stages = "static", -- Disable animations to prevent flickering
            timeout = 3000, -- Set timeout for notifications
            max_width = function()
                return math.floor(vim.o.columns * 0.75)
            end,
            max_height = function()
                return math.floor(vim.o.lines * 0.75)
            end,
        })

        -- Set nvim-notify as the default notification handler
        vim.notify = require("notify")
    end,
}
