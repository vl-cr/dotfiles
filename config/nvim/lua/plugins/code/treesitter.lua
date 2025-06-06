return {
    {
        "nvim-treesitter/nvim-treesitter",
        event = { "BufReadPre", "BufNewFile" }, -- Load in event of opening already existing file or new file
        cond = not vim.g.vscode,
        build = ":TSUpdate", -- Update language parsers alongside plugin updates
        config = function()
            local treesitter = require("nvim-treesitter.configs")

            treesitter.setup({
                auto_install = true,
                highlight = {
                    enable = true,
                    additional_vim_regex_highlighting = false,
                },
                indent = { enable = true },
                -- https://github.com/nvim-treesitter/nvim-treesitter?tab=readme-ov-file#language-parsers
                ensure_installed = {
                    "bash",
                    "dockerfile",
                    "gitignore",
                    "go",
                    "graphql",
                    "json",
                    "lua",
                    "markdown",
                    "markdown_inline",
                    "python",
                    "regex",
                    "sql",
                    "toml",
                    "vim",
                    "yaml",
                    -- Misc extras
                    "css",
                    "html",
                    "javascript",
                    "rust",
                    "terraform",
                },
                incremental_selection = {
                    enable = true,
                    keymaps = {
                        init_selection = "<C-space>",
                        node_incremental = "<C-space>",
                        scope_incremental = false,
                        node_decremental = "<backspace>",
                    },
                },
            })
        end,
    },
    {
        "nvim-treesitter/nvim-treesitter-context",
        event = { "BufReadPre", "BufNewFile" },
        cond = not vim.g.vscode,
    },
}
