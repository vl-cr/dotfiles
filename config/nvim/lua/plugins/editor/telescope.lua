return {
    "nvim-telescope/telescope.nvim",
    dependencies = {
        "nvim-lua/plenary.nvim",
        "nvim-tree/nvim-web-devicons",
        "folke/todo-comments.nvim",
        { "nvim-telescope/telescope-fzf-native.nvim", build = "make" },
    },
    cond = not vim.g.vscode,
    config = function()
        local telescope = require("telescope")
        local actions = require("telescope.actions")

        telescope.setup({
            defaults = {
                path_display = { "absolute" }, -- Do not truncate paths paths and wrap them
                wrap_results = true,
                mappings = {
                    -- Insert mode
                    i = {
                        ["<C-k>"] = actions.move_selection_previous, -- Move to prev result
                        ["<C-j>"] = actions.move_selection_next, -- Move to next result
                        ["<c-d>"] = actions.delete_buffer,
                    },
                    -- Normal mode
                    n = {
                        ["<c-d>"] = actions.delete_buffer,
                        ["dd"] = actions.delete_buffer,
                    },
                },
            },
            pickers = {
                marks = {
                    -- https://github.com/nvim-telescope/telescope.nvim/issues/3075
                    attach_mappings = function(prompt_bufnr, map)
                        map("i", "<C-d>", function()
                            require("telescope.actions").delete_mark(prompt_bufnr)
                        end)
                        return true -- Keep default mappings as well as the custom ones
                    end,
                },
            },
        })

        telescope.load_extension("fzf")

        vim.keymap.set("n", "<leader>fb", ":Telescope buffers<CR>", { desc = "Buffers" })
        vim.keymap.set("n", "<leader>ff", ":Telescope find_files<CR>", { desc = "Files" })
        vim.keymap.set("n", "<leader>fg", ":Telescope grep_string<CR>", { desc = "Grep (under cursor)" })
        vim.keymap.set("n", "<leader>fm", ":Telescope marks<CR>", { desc = "Marks" })
        vim.keymap.set("n", "<leader>fj", ":Telescope jumplist<CR>", { desc = "Jumps" })
        vim.keymap.set("n", "<leader>fr", ":Telescope oldfiles<CR>", { desc = "Recent" })
        vim.keymap.set("n", "<leader>fs", ":Telescope live_grep<CR>", { desc = "String (cwd)" })
        vim.keymap.set("n", "<leader>ft", ":TodoTelescope<CR>", { desc = "Todo" })
    end,
}
