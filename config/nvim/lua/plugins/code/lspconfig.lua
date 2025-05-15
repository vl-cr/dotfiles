return {
    "neovim/nvim-lspconfig",
    event = { "BufReadPre", "BufNewFile" }, -- Only needed when in a buffer, plus loads after Mason
    dependencies = {
        { "hrsh7th/cmp-nvim-lsp" }, -- Integrate autocompletions with LSP
        { "antosha417/nvim-lsp-file-operations", config = true }, -- Modify imports when file renamed
        { "folke/neodev.nvim", opts = {} }, -- Improved LSP for Lua when working on Neovim config
    },
    config = function()
        local lspconfig = require("lspconfig")
        local mason_lspconfig = require("mason-lspconfig")
        local cmp_nvim_lsp = require("cmp_nvim_lsp")

        -- Autocmd will execute everything inside on each LSP attach to a buffer
        vim.api.nvim_create_autocmd("LspAttach", {
            group = vim.api.nvim_create_augroup("UserLspConfig", {}),
            callback = function(ev)
                -- Buffer local mappings; See `:help vim.lsp.*` for documentation on any of the below functions
                local opts = { buffer = ev.buf, silent = true }

                -- -- What does this do??
                -- opts.desc = "References (LSP)"
                -- vim.keymap.set("n", "gR", ":Telescope lsp_references<CR>", opts) -- show definition, references

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
                vim.keymap.set("n", "<leader>dr", ":LspRestart<CR>", opts) -- mapping to restart lsp if necessary
            end,
        })

        -- Enable autocompletion (assign to every LSP server config)
        local capabilities = cmp_nvim_lsp.default_capabilities()

        -- Change the Diagnostic symbols in the sign column (gutter)
        local signs = {
            Error = " ",
            Warn = " ",
            Hint = "󰠠 ",
            Info = " ",
        }

        -- for type, icon in pairs(signs) do
        --     local hl = "DiagnosticSign" .. type
        --     vim.fn.sign_define(hl, {
        --         text = icon,
        --         texthl = hl,
        --         numhl = "",
        --     })
        -- end

        -- This is an easy way to configure language-specific servers
        mason_lspconfig.setup_handlers({
            -- Default handler for installed servers
            function(server_name)
                lspconfig[server_name].setup({
                    capabilities = capabilities,
                })
            end,

            ["lua_ls"] = function()
                -- Configure lua server (with special settings)
                lspconfig["lua_ls"].setup({
                    capabilities = capabilities,
                    settings = {
                        Lua = {
                            -- Make the language server recognize "vim" global
                            diagnostics = {
                                globals = { "vim" },
                            },
                            completion = {
                                callSnippet = "Replace",
                            },
                        },
                    },
                })
            end,
        })
    end,
}
