#!/bin/bash

set -euo pipefail
DOTFILES_DIR=$(dirname "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")")

if [[ -z "${WSL_DISTRO_NAME:-}" && -z "${WSL_INTEROP:-}" ]]; then
    echo "(!) Run setup/wsl.sh inside WSL" >&2
    exit 1
fi

for WSL_TOOL in powershell.exe wslpath yq; do
    if ! command -v "$WSL_TOOL" >/dev/null; then
        echo "(!) WSL setup requires $WSL_TOOL; check Windows interoperability and the dotfiles prerequisites" >&2
        exit 1
    fi
done

# Discover the Windows profile → convert its path → prepare the app's Codex home.
WSL_WINDOWS_PROFILE=$(powershell.exe -NoLogo -NoProfile -NonInteractive -Command \
    '[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); [Environment]::GetFolderPath("UserProfile")')
WSL_WINDOWS_PROFILE=${WSL_WINDOWS_PROFILE%$'\r'}
case "$WSL_WINDOWS_PROFILE" in
    [[:alpha:]]:\\?*|\\\\?*) ;;
    *) echo "(!) Could not determine the Windows user profile" >&2; exit 1 ;;
esac
if [[ "$WSL_WINDOWS_PROFILE" == *$'\n'* || "$WSL_WINDOWS_PROFILE" == *$'\r'* ]]; then
    echo "(!) Windows user profile must be a single path" >&2
    exit 1
fi
WSL_WINDOWS_PROFILE_PATH=$(wslpath -u "$WSL_WINDOWS_PROFILE")
if [[ "$WSL_WINDOWS_PROFILE_PATH" != /* || "$WSL_WINDOWS_PROFILE_PATH" == / || ! -d "$WSL_WINDOWS_PROFILE_PATH" || ! -w "$WSL_WINDOWS_PROFILE_PATH" ]]; then
    echo "(!) Windows user profile is not an accessible, writable directory: $WSL_WINDOWS_PROFILE_PATH" >&2
    exit 1
fi
WSL_CODEX_HOME="$WSL_WINDOWS_PROFILE_PATH/.codex"

# These copies must be readable by native Windows, independently of Linux symlinks.
for WSL_DIRECTORY in "$WSL_CODEX_HOME" "$WSL_CODEX_HOME/browser" "$WSL_CODEX_HOME/instructions" "$WSL_CODEX_HOME/rules"; do
    if [[ -L "$WSL_DIRECTORY" || ( -e "$WSL_DIRECTORY" && ! -d "$WSL_DIRECTORY" ) ]]; then
        echo "(!) Refusing to replace or follow the existing directory path: $WSL_DIRECTORY" >&2
        exit 1
    fi
done
WSL_MANAGED_FILES=(AGENTS.md keybindings.json rules/default.rules)
for WSL_INSTRUCTION in "$DOTFILES_DIR"/config/codex/instructions/*.md; do
    WSL_MANAGED_FILES+=("instructions/${WSL_INSTRUCTION##*/}")
done
for WSL_FILE in config.toml browser/config.toml "${WSL_MANAGED_FILES[@]}"; do
    if [[ -L "$WSL_CODEX_HOME/$WSL_FILE" || ( -e "$WSL_CODEX_HOME/$WSL_FILE" && ! -f "$WSL_CODEX_HOME/$WSL_FILE" ) ]]; then
        echo "(!) Refusing to replace or follow the existing managed file: $WSL_CODEX_HOME/$WSL_FILE" >&2
        exit 1
    fi
done

mkdir -p "$WSL_CODEX_HOME"/{browser,instructions,rules}
if [[ ! -e "$WSL_CODEX_HOME/config.toml" && ! -L "$WSL_CODEX_HOME/config.toml" ]]; then
    # Let Windows choose its own download directory and omit the macOS Dock setting.
    (umask 077; sed '/^dock-icon-preference[[:space:]]*=/d; /^browser-download-directory[[:space:]]*=/d' \
        "$DOTFILES_DIR/config/codex/config.toml" > "$WSL_CODEX_HOME/config.toml")
fi
# Apply the Windows-only preferences on every run, retaining other local settings.
yq -i -p toml -o toml \
    '.desktop.runCodexInWindowsSubsystemForLinux = true | .desktop.integratedTerminalShell = "wsl"' \
    "$WSL_CODEX_HOME/config.toml"
if [[ ! -e "$WSL_CODEX_HOME/browser/config.toml" && ! -L "$WSL_CODEX_HOME/browser/config.toml" ]]; then
    install -m 600 "$DOTFILES_DIR/config/codex/browser/config.toml" "$WSL_CODEX_HOME/browser/config.toml"
fi
for WSL_FILE in "${WSL_MANAGED_FILES[@]}"; do
    install -m 600 "$DOTFILES_DIR/config/codex/$WSL_FILE" "$WSL_CODEX_HOME/$WSL_FILE"
done

echo "WSL: prepared Windows Codex configuration at $WSL_CODEX_HOME"
echo "WSL: Codex agent and integrated terminal use the default WSL distro"
echo "Install Codex → sign in → fully restart → open a new terminal"
