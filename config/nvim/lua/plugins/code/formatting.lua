return {
    "stevearc/conform.nvim",
    event = { "BufReadPre", "BufNewFile" },
    cond = not vim.g.vscode,
    config = function()
        local conform = require("conform")

        conform.setup({
            formatters_by_ft = {
                sh = { "shfmt" },
                bash = { "shfmt" },
                lua = { "stylua" },
                javascript = { "prettier" },
                typescript = { "prettier" },
                css = { "prettier" },
                html = { "prettier" },
                json = { "prettier" },
                graphql = { "prettier" },
            },
            format_on_save = {
                lsp_format = "fallback",
                async = false,
                timeout_ms = 1000,
            },
        })

        vim.keymap.set({ "n", "v" }, "<leader>af", function()
            conform.format({
                lsp_format = "fallback",
                async = false,
                timeout_ms = 1000,
            })
        end, { desc = "Format (file or range)" })
    end,
}
