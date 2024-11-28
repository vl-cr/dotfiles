#!/bin/bash

# Install inshellisense (can be accessed on demand with 'is')
if ! command -v is &>/dev/null; then
    npm install -g @microsoft/inshellisense
fi

# Build bat cache (mostly for Catppuccin theme)
bat cache --build
