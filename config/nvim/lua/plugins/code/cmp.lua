return {
    "hrsh7th/nvim-cmp",
    event = "InsertEnter",
    cond = not vim.g.vscode,
    dependencies = {
        "hrsh7th/cmp-buffer", -- Source for text in buffer
        "hrsh7th/cmp-path", -- Source for file system paths
        "L3MON4D3/LuaSnip",
        "saadparwaiz1/cmp_luasnip", -- For autocompletion
        "rafamadriz/friendly-snippets", -- Useful snippets for a variety of languages
        "onsails/lspkind.nvim", -- VS Code-like pictograms
    },
    config = function()
        local cmp = require("cmp")
        local luasnip = require("luasnip")
        local lspkind = require("lspkind")

        -- Loads VS Code style snippets from installed plugins (e.g. friendly-snippets)
        require("luasnip.loaders.from_vscode").lazy_load()

        cmp.setup({
            completion = {
                completeopt = "menu,menuone,preview,noselect",
            },
            snippet = {
                -- Set up snippets to use LuaSnip
                expand = function(args)
                    luasnip.lsp_expand(args.body)
                end,
            },
            mapping = cmp.mapping.preset.insert({
                ["<C-k>"] = cmp.mapping.select_prev_item(), -- Previous suggestion
                ["<C-j>"] = cmp.mapping.select_next_item(), -- Next suggestion
                ["<C-Space>"] = cmp.mapping.complete(), -- Show completion suggestions
                ["<C-x>"] = cmp.mapping.abort(), -- Close completion window
                ["<CR>"] = cmp.mapping.confirm({ select = false }),
            }),
            -- Sources for autocompletion
            sources = cmp.config.sources({
                { name = "nvim_lsp" },
                { name = "luasnip" },
                { name = "buffer" },
                { name = "path" },
            }),

            -- Configure lspkind for VS Code-like pictograms in completion menu
            formatting = {
                format = lspkind.cmp_format({
                    maxwidth = 50,
                    ellipsis_char = "...",
                }),
            },
        })
    end,
}
