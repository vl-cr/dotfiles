# Dotfiles (vl-cr)

Tested on: macOS, Ubuntu (EC2), Amazon Linux (EC2)

## Prerequisites

For WSL2, install Ubuntu in the 64-bit PowerShell (as Admin) with this command and then restart Windows:

```powershell
wsl --install -d Ubuntu-26.04
```

For Ubuntu, run:

```bash
sudo apt update
sudo apt install git curl file build-essential procps bubblewrap
sudo apt autoremove && sudo apt clean
```

## Setup

1. Main bootstrap + universal terminal tools:

```bash
bash install.sh
```

2. Optional installations:

```bash
tg casks  # For Macos apps
tg snaps  # For Ubuntu apps
```
