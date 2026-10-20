return {
    "mfussenegger/nvim-lint",
    event = { "BufReadPre", "BufNewFile" },
    cond = not vim.g.vscode,
    config = function()
        local lint = require("lint")

        lint.linters_by_ft = {
            python = { "mypy" }, -- Ruff diagnostics come from its language server.
            sh = { "shellcheck" },
            bash = { "shellcheck" },
        }

        local lint_augroup = vim.api.nvim_create_augroup("lint", { clear = true })

        local function saved_file()
            return not vim.bo.modified and vim.fn.filereadable(vim.api.nvim_buf_get_name(0)) == 1
        end

        local function reads_from_disk(linter)
            if not linter.stdin then
                return true
            end
            if linter.name ~= "shellcheck" then
                return false
            end
            -- ShellCheck prefers a readable filename over stdin for relative source paths.
            local file = vim.fn.fnameescape(vim.fn.fnamemodify(vim.api.nvim_buf_get_name(0), ":p"))
            return vim.bo.buftype == "" and vim.fn.filereadable(file) == 1
        end

        local function can_lint(linter)
            return not reads_from_disk(linter) or saved_file()
        end

        local function lint_buffer()
            lint.try_lint(nil, { filter = can_lint })
        end

        vim.api.nvim_create_autocmd({ "BufEnter", "BufWritePost" }, {
            group = lint_augroup,
            callback = lint_buffer,
        })

        vim.api.nvim_create_autocmd("InsertLeave", {
            group = lint_augroup,
            callback = function()
                lint.try_lint(nil, {
                    filter = function(linter)
                        return not reads_from_disk(linter)
                    end,
                })
            end,
        })

        vim.keymap.set("n", "<leader>al", function()
            lint.try_lint(nil, {
                filter = function(linter)
                    local allowed = can_lint(linter)
                    if not allowed then
                        vim.notify("Save the buffer before running " .. linter.name .. ".", vim.log.levels.INFO)
                    end
                    return allowed
                end,
            })
        end, { desc = "Lint (current buffer)" })
    end,
}
