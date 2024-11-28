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
ln -sf "$DOTFILES_DIR"/config/git "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/glow "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/k9s "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/lazygit "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/nvim "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/starship "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/wezterm "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/yazi "$XDG_CONFIG_HOME"
ln -sf "$DOTFILES_DIR"/config/zellij "$XDG_CONFIG_HOME"

# 4. Others installs
echo "4. Other installs"
# Install inshellisense (can be accessed on demand with 'is')
if ! command -v is &>/dev/null; then
    npm install -g @microsoft/inshellisense
fi
# Build bat cache for Catppuccin theme
bat cache --build

# 5. Make zsh the default shell on Linux (on macOS it's pre-installed)
# If change to Brew zsh is needed on macOS: https://rick.cogley.info/post/use-homebrew-zsh-instead-of-the-osx-default
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "5. Linux: set Zsh as the default shell"

    # Check if chsh command exists
    if ! command -v chsh &>/dev/null; then
        # Check if yum is available
        if command -v yum &>/dev/null; then
            echo "chsh not found. Installing util-linux-user..."
            sudo yum install -y util-linux-user
        else
            echo "(!) yum not found. Please install chsh manually."
            exit 1
        fi
    fi

    # Add Zsh to /etc/shells if not already present
    if ! grep -q "$(which zsh)" /etc/shells; then
        echo "$(which zsh)" | sudo tee -a /etc/shells
    fi

    # Change the default shell to Zsh for the current user and restart with zsh
    sudo chsh -s "$(which zsh)" "$USER"
else
    echo "5. macOS: leaving pre-installed zsh as the default one..."
fi

echo "✅ Done, starting a new zsh session..." && zsh
