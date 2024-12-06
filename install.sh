#!/bin/bash

# Exit immediately; unset variable = error; pipeline fails return non-zero status
set -euo pipefail
DOTFILES_DIR=$(dirname "$(readlink -f "${BASH_SOURCE[0]}")") # Get the directory of the install script

source "$DOTFILES_DIR"/config/zsh/zshenv
mkdir -p "$ZDOTDIR"

# 0. Install Homebrew if necessary
if ! command -v brew &>/dev/null; then
    echo "Homebrew not found. Installing..."
    # Deps: https://docs.brew.sh/Homebrew-on-Linux#requirements
    export NONINTERACTIVE=1
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    eval "$($HOMEBREW_PREFIX/bin/brew shellenv)"
    brew analytics off
fi

# 1. Brew bundle install
echo "1. Install brew bundle"
brew bundle install --file setup/Brewfile
brew cleanup

# 2. ZSH
echo "2. Set up zsh"
ln -sf "$DOTFILES_DIR"/config/zsh/zshenv "$HOME"/.zshenv
ln -sf "$DOTFILES_DIR"/config/zsh/zshrc "$ZDOTDIR"/.zshrc
ln -sf "$DOTFILES_DIR"/config/zsh/aliases "$ZDOTDIR"/aliases
ln -sf "$DOTFILES_DIR"/config/zsh/autocompletions "$ZDOTDIR"/autocompletions
ln -sf "$DOTFILES_DIR"/config/zsh/bindkeys "$ZDOTDIR"/bindkeys
ln -sf "$DOTFILES_DIR"/config/zsh/cli "$ZDOTDIR"/cli
ln -sf "$DOTFILES_DIR"/config/zsh/history "$ZDOTDIR"/history
ln -sf "$DOTFILES_DIR"/config/zsh/plugins.toml "$ZDOTDIR"/plugins.toml
ln -sf "$DOTFILES_DIR"/config/zsh/vi-mode "$ZDOTDIR"/vi-mode
ln -sf "$DOTFILES_DIR"/Taskfile.yaml "$HOME"/Taskfile.yaml

# Update or add DOTFILES_DIR export in .zprofile
touch "$ZDOTDIR"/.zprofile

if grep -q "^export DOTFILES_DIR=" "$ZDOTDIR"/.zprofile; then
    sd "export DOTFILES_DIR=.*" "export DOTFILES_DIR=\"$DOTFILES_DIR\"" "$ZDOTDIR"/.zprofile
else
    echo "export DOTFILES_DIR=\"$DOTFILES_DIR\"" >>"$ZDOTDIR"/.zprofile
fi

# 3. Other symlinks
echo "3. Set up other symlinks"
ln -sf "$DOTFILES_DIR"/config/bat "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/bottom "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/git "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/glow "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/k9s "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/lazygit "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/nvim "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/starship "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/tealdeer "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/wezterm "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/yazi "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/zellij "$XDG_CONFIG_HOME"

# 4. Misc setups
echo "4. Misc setups"
source setup/miscellaneous.sh

# 5. OS-specific setup
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "5. Set up macOS"
    source setup/macos.sh
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "5. Set up Linux"
    source setup/linux.sh
else
    echo "(!) Unsupported OS"
    exit 1
fi

if [ -n "${ZSH_VERSION+x}" ]; then
    echo "✅ You are all set!"
else
    echo "✅ Done, starting a new zsh session..." && zsh
fi
