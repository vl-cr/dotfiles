-- TODO: remove Tab for VS Code extension: https://github.com/vscode-neovim/vscode-neovim?tab=readme-ov-file#code-navigation-bindings
if vim.g.vscode then
    require("keymaps")
    require("lazy-nvim")
    require("options")
else
    -- Full Neovim config
    require("keymaps")
    require("lazy-nvim")
    require("options")
    require("zellij-switch").setup()
end
