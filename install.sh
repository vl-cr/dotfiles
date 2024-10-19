#!/bin/bash

set -euo pipefail  # exit immediately; unset variable = error; pipeline fails return non-zero status

source ./config/zsh/zshenv
mkdir -p "$ZDOTDIR"

# 0. Install Homebrew if necessary
if ! command -v brew &> /dev/null; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        HOMEBREW_PREFIX="/opt/homebrew"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        HOMEBREW_PREFIX="/home/linuxbrew/.linuxbrew"
    else
        echo "(!) Unsupported OS"
        exit 1
    fi

    echo "Homebrew not found. Installing..."
    # Deps: https://docs.brew.sh/Homebrew-on-Linux#requirements
    export NONINTERACTIVE=1
    export HOMEBREW_NO_ANALYTICS=1
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    eval "$($HOMEBREW_PREFIX/bin/brew shellenv)"
    echo "eval \"\$(${HOMEBREW_PREFIX}/bin/brew shellenv)\"" >> ~/.config/zsh/.zprofile
    brew analytics off
fi

# 1. Brew bundle install
echo "1. Install brew bundle"
brew bundle install --no-lock

# 2. ZSH
echo "2. Set up zsh"
ln -sf "$(pwd)"/config/zsh/zshenv "$HOME"/.zshenv
ln -sf "$(pwd)"/config/zsh/zshrc "$ZDOTDIR"/.zshrc

# 3. Other symlinks
echo "3. Set up other symlinks"
ln -sf "$(pwd)"/config/git "$XDG_CONFIG_HOME"
ln -sf "$(pwd)"/config/k9s "$XDG_CONFIG_HOME"
ln -sf "$(pwd)"/config/nvim "$XDG_CONFIG_HOME"
ln -sf "$(pwd)"/config/starship "$XDG_CONFIG_HOME"
ln -sf "$(pwd)"/config/wezterm "$XDG_CONFIG_HOME"
ln -sf "$(pwd)"/config/zellij "$XDG_CONFIG_HOME"

# 4. Make zsh the default shell on Linux (on macOS it's pre-installed)
# If change to Brew zsh is needed on macOS: https://rick.cogley.info/post/use-homebrew-zsh-instead-of-the-osx-default
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "4. Linux: set Zsh as the default shell"
    
    # Check if chsh command exists
    if ! command -v chsh &> /dev/null; then
        # Check if yum is available
        if command -v yum &> /dev/null; then
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
    exec $SHELL
else
    echo "4. macOS: leaving pre-installed zsh as the default one..."
fi

echo "Done ✅"
