return {
    -- Noice.nvim configuration
    "folke/noice.nvim",
    event = "VeryLazy",
    opts = {},
    dependencies = {
        "MunifTanjim/nui.nvim",
    },
    cond = not vim.g.vscode,
    config = function()
        require("noice").setup({
            lsp = {
                -- Override markdown rendering so that **cmp** and other plugins use **Treesitter**
                override = {
                    ["vim.lsp.util.convert_input_to_markdown_lines"] = true,
                    ["vim.lsp.util.stylize_markdown"] = true,
                    ["cmp.entry.get_documentation"] = true, -- requires hrsh7th/nvim-cmp
                },
            },
            presets = {
                bottom_search = true, -- Use a classic bottom cmdline for search
                command_palette = false, -- Appears on top if true
                long_message_to_split = true, -- Long messages will be sent to a split
                inc_rename = false, -- Enables an input dialog for inc-rename.nvim
                lsp_doc_border = false, -- Add a border to hover docs and signature help
            },
        })
    end,
}
