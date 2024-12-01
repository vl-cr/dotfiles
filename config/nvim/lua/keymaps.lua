----------------
-- Essentials --
----------------
-- Set <leader>; Exit with "jj"; "U" = redo in normal mode
vim.g.mapleader = " "
vim.keymap.set("i", "jj", "<ESC>", { noremap = true, silent = true, desc = "Exit insert mode with jj" })
vim.keymap.set("n", "U", "<C-r>", { noremap = true, silent = true })
-- Save and quit and leader w / q
vim.keymap.set("n", "<leader>w", ":w<CR>", { desc = "which_key_ignore" })
vim.keymap.set("n", "<leader>q", ":qa<CR>", { desc = "which_key_ignore" })
-- Delete without cutting on d and D by using the blackhole register (use "vx" for cutting)
vim.keymap.set("n", "d", '"_d', { noremap = true, silent = true })
vim.keymap.set("v", "d", '"_d', { noremap = true, silent = true })
vim.keymap.set("n", "D", '"_D', { noremap = true, silent = true })
-- Make regular scrolls and search scrolls recenter on each command
vim.keymap.set("n", "<C-d>", "<C-d>zz", { noremap = true, silent = true })
vim.keymap.set("n", "<C-u>", "<C-u>zz", { noremap = true, silent = true })
vim.keymap.set("n", "n", "nzz", { noremap = true, silent = true })
vim.keymap.set("n", "N", "Nzz", { noremap = true, silent = true })

--------------------
-- Custom keymaps --
--------------------
-- Clear
vim.keymap.set("n", "<leader>cs", ":nohl<CR>", { desc = "Clear Search highlights" })
vim.keymap.set("n", "<leader>cb", ":bd<CR>", { desc = "Clear Buffer" })

-- Tabs (just in case, use fuzzy buffer instead)
vim.keymap.set("n", "<C-t>n", ":tabnew<CR>", { desc = "New tab" })
vim.keymap.set("n", "<C-t>x", ":tabclose<CR>", { desc = "Close tab" })
vim.keymap.set("n", "<C-t>l", ":tabn<CR>", { desc = "Next tab" })
vim.keymap.set("n", "<C-t>h", ":tabp<CR>", { desc = "Previous tab" })

-- Move lines in visual mode with Ctrl J-K
vim.keymap.set("v", "<C-j>", ":m '>+1<CR>gv=gv", { desc = "Move selected lines up" })
vim.keymap.set("v", "<C-k>", ":m '<-2<CR>gv=gv", { desc = "Move selected lines down" })

-- Ready-to-use substitution
vim.keymap.set("n", "<leader>as", ":%s/\\<<C-r><C-w>\\>/<C-r><C-w>/gI<Left><Left><Left>", { desc = "Substitute" })
