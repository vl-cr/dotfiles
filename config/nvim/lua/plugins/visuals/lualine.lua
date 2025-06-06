return {
    "nvim-lualine/lualine.nvim",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    cond = not vim.g.vscode,
    config = function()
        local lualine = require("lualine")

        lualine.setup({
            options = {
                theme = "catppuccin-mocha",
            },
            sections = {
                lualine_x = {
                    { "encoding" },
                    { "fileformat" },
                },
            },
        })
    end,
}
