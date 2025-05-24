# Dotfiles (vl-cr)

Tested on: macOS, Ubuntu (EC2), Amazon Linux (EC2)

## Prerequisites

```bash
# For Ubuntu
sudo apt update
sudo apt install git curl file build-essential procps
sudo apt autoremove && sudo apt clean
```

## Setup

1. Main bootstrap + universal terminal tools:

```bash
bash install.sh
```

2. Optional casks installation:

```bash
task -g casks
```
