-- TODO: remove Tab for VS Code extension: https://github.com/vscode-neovim/vscode-neovim?tab=readme-ov-file#code-navigation-bindings
if vim.g.vscode then
    -- VS Code-specific configuration
    require("keymaps")
    require("options")
    -- TODO add plugins: https://github.com/vscode-neovim/vscode-neovim?tab=readme-ov-file#neovim-configuration
else
    -- Full Neovim config
    require("keymaps")
    require("lazy-nvim")
    require("options")
    require("zellij-switch").setup()
end
