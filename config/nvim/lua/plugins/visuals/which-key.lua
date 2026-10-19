return {
    "folke/which-key.nvim",
    event = "VeryLazy",
    cond = not vim.g.vscode,
    init = function()
        vim.o.timeout = true
        vim.o.timeoutlen = 400
    end,
    opts = {
        spec = {
            { "<leader>a", group = "Action" },
            { "<leader>c", group = "Clear" },
            { "<leader>d", group = "Diagnostic" },
            { "<leader>e", group = "Explorer" },
            { "<leader>f", group = "Fuzzy" },
            { "<leader>o", group = "Session" },
            { "<leader>y", group = "Yazi" },
        },
    },
}
