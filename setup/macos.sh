#!/bin/bash

echo "macOS: changing OS defaults..."

### Application Settings ###
# VSCode key repeat: https://github.com/vscode-neovim/vscode-neovim?tab=readme-ov-file#troubleshooting
defaults write com.microsoft.VSCode ApplePressAndHoldEnabled -bool false

### Finder ###
# Show hidden files
defaults write com.apple.finder AppleShowAllFiles -boolean true

# If change to Brew zsh is needed on macOS: https://rick.cogley.info/post/use-homebrew-zsh-instead-of-the-osx-default
echo "macOS: leaving pre-installed zsh as the default one (check if it's stale)"
