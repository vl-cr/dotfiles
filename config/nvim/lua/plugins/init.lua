return {
    { "nvim-lua/plenary.nvim" }, -- Lua functions that many plugins use
    {
        "rmagatti/auto-session",
        config = function()
            local auto_session = require("auto-session")
            auto_session.setup({
                auto_restore_enabled = true,
                auto_sesssion_supress_dirs = { "~/", "~/Downloads", "/" },
            })

            vim.keymap.set("n", "<leader>ow", ":SessionSearch<CR>", { desc = "Session Manager" })
            vim.keymap.set("n", "<leader>or", ":SessionRestore<CR>", { desc = "Restore session (cwd)" })
            vim.keymap.set("n", "<leader>os", ":SessionSave<CR>", { desc = "Save session (cwd)" })
        end,
    },
    {
        "lewis6991/gitsigns.nvim",
        event = { "BufReadPre", "BufNewFile" },
        config = function()
            require("gitsigns").setup()
        end,
    },
    {
        "lukas-reineke/indent-blankline.nvim",
        event = { "BufReadPre", "BufNewFile" },
        main = "ibl",
        opts = { indent = { char = "┊" } },
    },
}
