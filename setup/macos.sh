#!/bin/bash

echo "macOS: changing OS defaults..."

# Control key longpress in apps
defaults write md.obsidian ApplePressAndHoldEnabled -bool true
defaults write com.microsoft.VSCode ApplePressAndHoldEnabled -bool false

# Finder: Show hidden files
defaults write com.apple.finder AppleShowAllFiles -boolean true

# Add cmd+ctrl+click window feature: https://mmazzarolo.com/blog/2022-04-16-drag-window-by-clicking-anywhere-on-macos
defaults write -g NSWindowShouldDragOnGesture -bool true

# If change to Brew zsh is needed on macOS: https://rick.cogley.info/post/use-homebrew-zsh-instead-of-the-osx-default
echo "macOS: Leaving pre-installed zsh as the default one (check if it's stale)"

# Disable double-space full stop insert
defaults write -g NSAutomaticPeriodSubstitutionEnabled -bool false

# Trackpad: Disable "Natural scrolling"
defaults write NSGlobalDomain com.apple.swipescrolldirection -bool false

# Trackpad: Enable "Tap to click"
defaults write com.apple.AppleMultitouchTrackpad Clicking -bool true
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad Clicking -bool true
defaults -currentHost write NSGlobalDomain com.apple.mouse.tapBehavior -int 1
defaults write NSGlobalDomain com.apple.mouse.tapBehavior -int 1
