#!/bin/bash

echo "Linux: set Zsh as the default shell"

# Check if chsh command exists
if ! command -v chsh &>/dev/null; then
    # We are likely in Amazon Linux 2, check if yum is available
    if command -v yum &>/dev/null; then
        echo "chsh not found. Installing util-linux-user..."
        sudo yum install -y util-linux-user
    else
        echo "(!) chsh not found AND yum not found. Add support for alternative package manager?"
        exit 1
    fi
fi

# Add Zsh to /etc/shells if not already present
if ! grep -q "$(which zsh)" /etc/shells; then
    echo "$(which zsh)" | sudo tee -a /etc/shells
fi

# Change the default shell to Zsh for the current user
sudo chsh -s "$(which zsh)" "$USER"
