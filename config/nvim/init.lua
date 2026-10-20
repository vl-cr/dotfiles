-- TODO: remove Tab for VS Code extension: https://github.com/vscode-neovim/vscode-neovim?tab=readme-ov-file#code-navigation-bindings
require("keymaps")
require("lazy-nvim")
require("options")

if not vim.g.vscode then
    require("zellij-switch").setup()
end
