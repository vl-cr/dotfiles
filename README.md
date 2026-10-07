# Dotfiles (vl-cr)

Tested on: macOS, Ubuntu (EC2), Amazon Linux (EC2)

## Prerequisites

For WSL2: open 64-bit PowerShell as Administrator → install Ubuntu with the command below → restart Windows.

```powershell
wsl --install -d Ubuntu-26.04
```

For Ubuntu, run:

```bash
sudo apt update && sudo apt upgrade
sudo apt install git curl file build-essential procps bubblewrap
sudo apt autoremove && sudo apt clean
```

## Setup

1. Main bootstrap + universal terminal tools:

```bash
bash install.sh
```

2. Optional installations:

Run these tasks once per machine, after the bootstrap:

```bash
tg setup-atuin    # Log in to the vl-cr Atuin account
tg setup-firefox  # Install Firefox and link its profile configuration
```

Install apps:

```bash
tg casks  # Other macOS apps
tg snaps  # Other Ubuntu Desktop apps
```
