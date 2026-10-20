return {
    { "nvim-lua/plenary.nvim" }, -- Lua functions that many plugins use
    {
        "rmagatti/auto-session",
        cond = not vim.g.vscode,
        config = function()
            local auto_session = require("auto-session")
            auto_session.setup({
                auto_restore = true,
                suppressed_dirs = { "~/", "~/Downloads", "/" },
                session_lens = { load_on_setup = false },
            })

            vim.keymap.set("n", "<leader>ow", ":SessionSearch<CR>", { desc = "Session Manager" })
            vim.keymap.set("n", "<leader>or", ":SessionRestore<CR>", { desc = "Restore session (cwd)" })
            vim.keymap.set("n", "<leader>os", ":SessionSave<CR>", { desc = "Save session (cwd)" })
        end,
    },
    {
        "lewis6991/gitsigns.nvim",
        event = { "BufReadPre", "BufNewFile" },
        cond = not vim.g.vscode,
        config = function()
            require("gitsigns").setup()
        end,
    },
    {
        "lukas-reineke/indent-blankline.nvim",
        event = { "BufReadPre", "BufNewFile" },
        cond = not vim.g.vscode,
        main = "ibl",
        opts = { indent = { char = "┊" } },
    },
    {
        "kylechui/nvim-surround",
        event = "VeryLazy",
        config = function()
            require("nvim-surround").setup({})
        end,
    },
}
