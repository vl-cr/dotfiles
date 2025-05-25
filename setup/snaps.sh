#!/bin/bash

# Exit immediately; unset variable = error; pipeline fails return non-zero status
set -euo pipefail

sudo snap install --classic bitwarden
sudo snap install --classic code
sudo snap install --classic firefox
sudo snap install --classic ghostty
sudo snap install --classic obsidian
