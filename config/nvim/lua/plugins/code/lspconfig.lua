return {
    "neovim/nvim-lspconfig",
    lazy = false, -- Mason needs the server configs before it enables installed servers.
    cond = not vim.g.vscode,
    dependencies = {
        { "hrsh7th/cmp-nvim-lsp" }, -- Integrate autocompletions with LSP
    },
    config = function()
        local cmp_nvim_lsp = require("cmp_nvim_lsp")

        -- Autocmd will execute everything inside on each LSP attach to a buffer
        vim.api.nvim_create_autocmd("LspAttach", {
            group = vim.api.nvim_create_augroup("UserLspConfig", {}),
            callback = function(ev)
                -- Buffer local mappings; See `:help vim.lsp.*` for documentation on any of the below functions
                local opts = { buffer = ev.buf, silent = true }

                opts.desc = "Go to declaration"
                vim.keymap.set("n", "gD", vim.lsp.buf.declaration, opts) -- go to declaration

                opts.desc = "Show LSP definitions"
                vim.keymap.set("n", "gd", ":Telescope lsp_definitions<CR>", opts) -- show lsp definitions

                opts.desc = "Show LSP implementations"
                vim.keymap.set("n", "gi", ":Telescope lsp_implementations<CR>", opts) -- show lsp implementations

                opts.desc = "Show LSP type definitions"
                vim.keymap.set("n", "gt", ":Telescope lsp_type_definitions<CR>", opts) -- show lsp type definitions

                opts.desc = "Rename (smart)"
                vim.keymap.set("n", "<leader>ar", vim.lsp.buf.rename, opts) -- smart rename

                opts.desc = "Diagnostics (buffer)"
                vim.keymap.set("n", "<leader>fd", ":Telescope diagnostics bufnr=0<CR>", opts)

                opts.desc = "Docs (hover at cursor)"
                vim.keymap.set("n", "K", vim.lsp.buf.hover, opts)

                opts.desc = "Line diagnostics"
                vim.keymap.set("n", "<leader>dl", vim.diagnostic.open_float, opts)

                opts.desc = "Actions list"
                vim.keymap.set({ "n", "v" }, "<leader>aa", vim.lsp.buf.code_action, opts)

                opts.desc = "Restart LSP"
                local restart = vim.fn.exists(":lsp") == 2 and ":lsp restart<CR>" or ":LspRestart<CR>"
                vim.keymap.set("n", "<leader>dr", restart, opts)
            end,
        })

        -- Enable autocompletion (assign to every LSP server config)
        local capabilities = cmp_nvim_lsp.default_capabilities()

        vim.lsp.config("*", {
            capabilities = capabilities,
        })

        vim.lsp.config("lua_ls", {
            settings = {
                Lua = {
                    diagnostics = {
                        globals = { "vim" },
                    },
                    completion = {
                        callSnippet = "Replace",
                    },
                },
            },
        })

        vim.lsp.config("taplo", {
            init_options = {
                configurationSection = "evenBetterToml",
                cachePath = vim.fs.joinpath(vim.fn.stdpath("cache"), "taplo"),
            },
            settings = {
                evenBetterToml = {
                    schema = {
                        enabled = false,
                        catalogs = {},
                    },
                },
            },
        })
    end,
}
