#!/usr/bin/env bash

set -euo pipefail

SKILLS_DIR=$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")
SKILLS_FILE="$SKILLS_DIR/skills.txt"

install_skill() {
    local skill=$1

    if [[ ! "$skill" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
        echo "Error: '$skill' is not a GitHub repo in owner/repo format" >&2
        return 1
    fi

    if ! git ls-remote --exit-code "https://github.com/$skill.git" HEAD >/dev/null 2>&1; then
        echo "Error: GitHub repo '$skill' was not found" >&2
        return 1
    fi

    npx -y skills add "$skill" -a codex -g -y
}

if (( $# > 1 )); then
    echo "Usage: $0 [owner/repo]" >&2
    exit 1
fi

if (( $# == 1 )); then
    install_skill "$1"
    exit
fi

while IFS= read -r skill; do
    if [[ -z "$skill" || "$skill" == \#* ]]; then
        continue
    fi

    install_skill "$skill"
done <"$SKILLS_FILE"
