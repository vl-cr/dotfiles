return {
    "williamboman/mason.nvim",
    dependencies = {
        "williamboman/mason-lspconfig.nvim",
        "WhoIsSethDaniel/mason-tool-installer.nvim",
    },
    cond = not vim.g.vscode,
    config = function()
        local mason = require("mason")
        local mason_lspconfig = require("mason-lspconfig")
        local mason_tool_installer = require("mason-tool-installer")

        mason.setup({
            ui = {
                icons = {
                    package_installed = "✓",
                    package_pending = "➜",
                    package_uninstalled = "✗",
                },
            },
        })

        -- https://github.com/williamboman/mason-lspconfig.nvim
        mason_lspconfig.setup({
            -- List of servers for mason to install
            ensure_installed = {
                "ruff",
                "pyright",
                "gopls", -- Go (official)
                "lua_ls", -- Lua
                "taplo", -- TOML
            },
        })

        mason_tool_installer.setup({
            ensure_installed = {
                "shellcheck", -- Bash lint
                "shfmt", -- Bash format
                "mypy",
                "prettier", -- Prettier formatter
                "stylua", -- Lua formatter
            },
        })
    end,
}
