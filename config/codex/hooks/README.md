# Destructive-command guard

This `PreToolUse` hook catches common accidental attempts to recursively remove
protected paths or erase storage. It parses command text without executing it.

The guard is deliberately an extra warning layer, not a security boundary.
Codex's `workspace-write` sandbox and approval policy remain authoritative.
In particular, `write_stdin` does not trigger `PreToolUse` again, specialised
tool paths may opt out, and the guard does not interpret programs passed to
arbitrary language runtimes. No lightweight parser can prove inherited aliases,
generated programs, or every shell dialect safe.

The analyser fails closed when an executable, destructive argument, shell input,
or parser state is ambiguous. That conservatism can reject a complex harmless
command; simplify the command instead of treating the hook as an authorisation
boundary.

## Installation and trust

Run `install.sh` → reload Codex → open `/hooks` → review the exact command →
trust the hook.

Codex skips a user command hook until its current definition hash is trusted.
The installer never manufactures that trust. It installs the guard under a
content-addressed filename, so changing the guard changes the hook command and
forces a fresh review. It merges its handler into `~/.codex/hooks.json` without
discarding unrelated hooks and never replaces an existing `config.toml`. The
checked-in `hooks.json` is an inert template; only the installer writes the
absolute, content-addressed command used by Codex.

## Verification

The tests pass shell examples to Python as inert strings; they never invoke a
shell or any destructive utility.

```sh
python3 -B -m unittest discover -s config/codex/hooks -p 'test_*.py'
```
