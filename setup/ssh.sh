#!/bin/bash

set -euo pipefail
DOTFILES_DIR=$(dirname "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")")
SSH_CONFIG="${1:-"$HOME/.ssh/config"}"

if [[ -L "$SSH_CONFIG" || ( -e "$SSH_CONFIG" && ! -f "$SSH_CONFIG" ) ]]; then
    echo "(!) SSH setup requires a regular config file: $SSH_CONFIG" >&2
    exit 1
fi

mkdir -p -m 700 "$(dirname "$SSH_CONFIG")"
SSH_INCLUDE=$(printf 'Include "%s/config/ssh/config"' "$DOTFILES_DIR")

# Put the host settings before local defaults because SSH uses the first value.
if [[ ! -f "$SSH_CONFIG" ]] || [[ "$(head -n 1 "$SSH_CONFIG")" != "$SSH_INCLUDE" ]]; then
    SSH_CONFIG_TEMP=$(mktemp "${SSH_CONFIG}.XXXXXX")
    trap 'rm -f "$SSH_CONFIG_TEMP"' EXIT
    printf '%s\n' "$SSH_INCLUDE" > "$SSH_CONFIG_TEMP"
    if [[ -f "$SSH_CONFIG" ]]; then
        cat "$SSH_CONFIG" >> "$SSH_CONFIG_TEMP"
    fi
    ssh -G -T -F "$SSH_CONFIG_TEMP" github-work >/dev/null
    mv "$SSH_CONFIG_TEMP" "$SSH_CONFIG"
fi

chmod 600 "$SSH_CONFIG"
