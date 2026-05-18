local parsers = {
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
}

local filetypes = {
    "bash",
    "css",
    "dockerfile",
    "ecma",
    "ecmascript",
    "gitignore",
    "go",
    "gyp",
    "graphql",
    "html",
    "javascript",
    "javascriptreact",
    "js",
    "jsx",
    "json",
    "jsonc",
    "lua",
    "markdown",
    "pandoc",
    "py",
    "python",
    "regex",
    "rust",
    "sh",
    "sql",
    "terraform",
    "terraform-vars",
    "toml",
    "vim",
    "yaml",
}

return {
    {
        "nvim-treesitter/nvim-treesitter",
        branch = "main",
        lazy = false,
        cond = not vim.g.vscode,
        build = function()
            local treesitter = require("nvim-treesitter")
            if type(treesitter.install) ~= "function" then
                return
            end

            treesitter.install(parsers):wait(300000)
            treesitter.update(parsers):wait(300000)
        end,
        config = function()
            local treesitter = require("nvim-treesitter")
            if type(treesitter.install) ~= "function" then
                return
            end

            local function installed_parsers()
                local installed = {}

                for _, parser in ipairs(treesitter.get_installed("parsers")) do
                    installed[parser] = true
                end

                return installed
            end

            treesitter.setup()

            local installed = installed_parsers()
            local missing = vim.tbl_filter(function(parser)
                return not installed[parser]
            end, parsers)

            if #missing > 0 then
                treesitter.install(missing)
            end

            vim.api.nvim_create_autocmd("FileType", {
                pattern = filetypes,
                callback = function(event)
                    local filetype = vim.bo[event.buf].filetype
                    local lang = vim.treesitter.language.get_lang(filetype) or filetype

                    if not installed_parsers()[lang] then
                        return
                    end

                    local ok = pcall(vim.treesitter.start, event.buf)
                    if ok then
                        vim.bo[event.buf].indentexpr = "v:lua.require'nvim-treesitter'.indentexpr()"
                    end
                end,
            })

            vim.keymap.set("n", "<C-space>", "van", { desc = "Start Treesitter selection", remap = true })
            vim.keymap.set("x", "<C-space>", "an", { desc = "Expand Treesitter selection", remap = true })
            vim.keymap.set("x", "<backspace>", "in", { desc = "Shrink Treesitter selection", remap = true })
        end,
    },
    {
        "nvim-treesitter/nvim-treesitter-context",
        event = { "BufReadPre", "BufNewFile" },
        cond = not vim.g.vscode,
    },
}
