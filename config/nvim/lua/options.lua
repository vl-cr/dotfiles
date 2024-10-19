-- Lines
vim.opt.number = true -- Line start at 1
vim.opt.relativenumber = true -- Relative numbers
vim.opt.wrap = true -- Lines wrapped

-- Tabs and spaces
vim.opt.tabstop = 4 -- Number of spaces a <Tab> counts for
vim.opt.shiftwidth = 4 -- Number of spaces used for indentation
vim.opt.expandtab = true -- Use spaces instead of tabs
vim.opt.autoindent = true -- Apply previous line's indent to the new one

-- Search
vim.opt.hlsearch = true -- Set highlight on search
vim.opt.ignorecase = true -- Ignore case when searching
vim.opt.smartcase = true -- Assumes you want case-sensitive if you include mixed case

-- Splits
vim.opt.splitright = true -- Split vertical window to the right
vim.opt.splitbelow = true -- Split horizontal window to the bottom

-- Misc
vim.cmd("let g:netrw_liststyle = 3") -- Make netrw (vim file explorer) use tree-like structure
vim.opt.termguicolors = true -- Proper colorschemes
vim.opt.signcolumn = "yes" -- Show sign columns so that text doesn't shift
vim.opt.backspace = "indent,eol,start" -- Allow backspace on indent, end of line or insert mode start position
vim.opt.clipboard:append("unnamedplus") -- Use system clipboard as default register
